import json
import os
from urllib.parse import urlsplit, urlunsplit

from anthropic import Anthropic
from openai import OpenAI

from logging_utils import format_fields, get_logger
from models import Job, UserProfile


logger = get_logger("jobswarm.scorer")
SCORING_JOB_LIMIT = max(1, int(os.getenv("SCORING_JOB_LIMIT", "10")))

SCORER_SYSTEM_PROMPT = """You are a job matching engine. Given a candidate profile and job listings, score each listing's relevance from 0-100 and provide 1-3 short match reasons.

Also identify duplicates (same job at same company appearing from multiple sources). For duplicates, mark all but the one with the most information.

Respond ONLY with valid JSON in this exact format:
{
  "scored_jobs": [
    {
      "id": "string",
      "relevance_score": number,
      "match_reasons": ["string"],
      "is_duplicate": false
    }
  ]
}

Scoring guide:
- 90-100: Strong match on role type, experience level, tech stack, and location
- 70-89: Good match, missing 1 dimension
- 50-69: Partial match, related but not ideal
- 0-49: Weak or no match"""


def build_scorer_prompt(profile: UserProfile, role: str, location: str, keywords: list[str], jobs: list[Job]) -> str:
    """Build the user prompt for scoring."""
    jobs_json = json.dumps([{
        "id": j.id,
        "job_title": j.job_title,
        "company_name": j.company_name,
        "location": j.location,
        "source": j.source_platform.value,
        "salary": j.salary,
        "employment_type": j.employment_type,
    } for j in jobs], indent=2)

    return f"""CANDIDATE PROFILE:
Role sought: {role}
Location preference: {location}
Keywords: {', '.join(keywords) if keywords else 'None specified'}
Current title: {profile.current_title if profile else 'Not specified'}
Experience: {profile.years_of_experience if profile else 'Not specified'}
Education: {profile.education if profile else 'Not specified'}
Skills: {', '.join(profile.skills) if profile and profile.skills else 'Not specified'}

JOB LISTINGS TO SCORE ({len(jobs)} jobs):
{jobs_json}"""


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().split())


def _normalize_job_url(job_url: str | None) -> str:
    if not job_url:
        return ""
    parsed = urlsplit(job_url.strip())
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


def _job_dedupe_key(job: Job) -> tuple[str, ...]:
    normalized_url = _normalize_job_url(job.job_url)
    if normalized_url:
        return ("url", normalized_url)

    return (
        "meta",
        _normalize_text(job.company_name),
        _normalize_text(job.job_title),
        _normalize_text(job.location),
    )


def _mark_local_duplicates(jobs: list[Job]) -> list[Job]:
    seen_keys: set[tuple[str, ...]] = set()
    unique_jobs: list[Job] = []

    for job in jobs:
        key = _job_dedupe_key(job)
        if key in seen_keys:
            job.is_duplicate = True
            if not job.match_reasons:
                job.match_reasons = ["Possible duplicate removed during fast local dedupe."]
            continue

        seen_keys.add(key)
        unique_jobs.append(job)

    return unique_jobs


def score_jobs(
    jobs: list[Job],
    profile: UserProfile | None,
    role: str,
    location: str,
    keywords: list[str],
    hunt_id: str | None = None,
) -> list[Job]:
    """Score and deduplicate jobs using AI (OpenAI or Anthropic fallback)."""
    if not jobs:
        logger.info("Skipping scoring because there are no jobs %s", format_fields(hunt_id=hunt_id))
        return []

    unique_jobs = _mark_local_duplicates(jobs)
    jobs_to_score = unique_jobs[:SCORING_JOB_LIMIT]

    # Check which API to use
    use_openai = bool(os.getenv("OPENAI_API_KEY"))
    use_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

    logger.info(
        "Scoring started %s",
        format_fields(
            hunt_id=hunt_id,
            jobs_count=len(jobs),
            unique_jobs_count=len(unique_jobs),
            jobs_selected_for_scoring=len(jobs_to_score),
            role=role,
            location=location,
            keywords=keywords,
            profile_present=profile is not None,
            openai_api_key_present=use_openai,
            anthropic_api_key_present=use_anthropic,
            using_api="openai" if use_openai else "anthropic" if use_anthropic else "none",
        ),
    )

    prompt = build_scorer_prompt(profile, role, location, keywords, jobs_to_score)

    try:
        if use_openai:
            # Use OpenAI API
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SCORER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            logger.info(
                "Scoring response received (OpenAI) %s",
                format_fields(
                    hunt_id=hunt_id,
                    choices=len(response.choices),
                    model=getattr(response, "model", None),
                ),
            )
            result = json.loads(response.choices[0].message.content)
        elif use_anthropic:
            # Fallback to Anthropic API
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4000,
                temperature=0.3,
                system=SCORER_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )
            logger.info(
                "Scoring response received (Anthropic) %s",
                format_fields(
                    hunt_id=hunt_id,
                    model=response.model,
                    stop_reason=response.stop_reason,
                ),
            )
            result = json.loads(response.content[0].text)
        else:
            logger.error("No API key available for scoring %s", format_fields(hunt_id=hunt_id))
            return jobs
        scored_data = {item["id"]: item for item in result.get("scored_jobs", [])}
        logger.info(
            "Parsed scoring payload %s",
            format_fields(hunt_id=hunt_id, scored_items=len(scored_data)),
        )

        for job in jobs_to_score:
            if job.id in scored_data:
                data = scored_data[job.id]
                job.relevance_score = data.get("relevance_score", 0)
                job.match_reasons = data.get("match_reasons", [])
                job.is_duplicate = data.get("is_duplicate", False)

        jobs.sort(key=lambda job: job.relevance_score, reverse=True)
        logger.info(
            "Scoring finished successfully %s",
            format_fields(
                hunt_id=hunt_id,
                top_score=jobs[0].relevance_score if jobs else None,
                duplicates=sum(1 for job in jobs if job.is_duplicate),
            ),
        )
    except Exception as exc:
        logger.exception(
            "Scoring failed %s",
            format_fields(hunt_id=hunt_id, error=str(exc)),
        )

    return jobs


def filter_duplicates(jobs: list[Job]) -> list[Job]:
    """Remove duplicate jobs from the list."""
    unique_jobs = [job for job in jobs if not job.is_duplicate]
    logger.info(
        "Filtered duplicate jobs %s",
        format_fields(total_jobs=len(jobs), unique_jobs=len(unique_jobs)),
    )
    return unique_jobs
