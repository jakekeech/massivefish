import json
import os
from openai import OpenAI
from models import Job, UserProfile


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


def score_jobs(
    jobs: list[Job],
    profile: UserProfile | None,
    role: str,
    location: str,
    keywords: list[str],
) -> list[Job]:
    """Score and deduplicate jobs using GPT-4o-mini."""
    if not jobs:
        return []

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = build_scorer_prompt(profile, role, location, keywords, jobs)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SCORER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        scored_data = {item["id"]: item for item in result.get("scored_jobs", [])}

        # Apply scores to jobs
        for job in jobs:
            if job.id in scored_data:
                data = scored_data[job.id]
                job.relevance_score = data.get("relevance_score", 0)
                job.match_reasons = data.get("match_reasons", [])
                job.is_duplicate = data.get("is_duplicate", False)

        # Sort by relevance score descending
        jobs.sort(key=lambda j: j.relevance_score, reverse=True)

    except Exception as e:
        print(f"Scoring failed: {e}")
        # Return jobs unsorted with score 0 on failure

    return jobs


def filter_duplicates(jobs: list[Job]) -> list[Job]:
    """Remove duplicate jobs from the list."""
    return [j for j in jobs if not j.is_duplicate]
