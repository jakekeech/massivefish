import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator

import httpx
from openai import OpenAI

from logging_utils import format_fields, get_logger
from models import Job, UserProfile
from orchestrator import (
    TINYFISH_SSE_URL,
    _cancel_run,
    _coerce_result_payload,
    _event_indicates_bot_challenge,
    _fetch_streaming_url,
)
from platforms import build_proxy_config, get_platform_display_name, infer_platform


logger = get_logger("jobswarm.apply")

APPLY_COVER_LETTER_SYSTEM_PROMPT = """You write concise, tailored cover letters for job applications.

Rules:
- Write in first person.
- Sound confident, specific, and human.
- Keep it between 180 and 260 words.
- Use only the profile and job context provided.
- Do not invent metrics, employers, or projects.
- Do not use placeholders like [Company].
- Do not include a mailing address block.
- End with a simple professional sign-off.
"""


@dataclass
class ApplyStepResult:
    payload: Any
    error: str | None
    preview_url: str | None
    run_id: str | None


def _normalize_text(value: Any, default: str = "", limit: int | None = None) -> str:
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    if limit is not None:
        return text[:limit]

    return text


def _normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def _normalize_string_list(value: Any, limit: int = 12) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _normalize_text(item)
        if not text:
            continue
        if text in seen:
            continue
        normalized.append(text)
        seen.add(text)
        if len(normalized) >= limit:
            break

    return normalized


def _infer_inspection_status(payload: dict[str, Any], default: str) -> str:
    raw_status = _normalize_text(payload.get("status")).lower()
    mapped = {
        "ready": "ready_to_apply",
        "ready_to_apply": "ready_to_apply",
        "fillable": "ready_to_apply",
        "login_required": "login_required",
        "requires_login": "login_required",
        "needs_login": "login_required",
        "manual_required": "manual_required",
        "needs_manual_review": "manual_required",
        "blocked": "manual_required",
        "unavailable": "unavailable",
        "closed": "unavailable",
        "expired": "unavailable",
    }
    if raw_status in mapped:
        return mapped[raw_status]

    reason = _normalize_text(payload.get("reason")).lower()
    notes = " ".join(_normalize_string_list(payload.get("notes"))).lower()
    haystack = f"{reason} {notes}".strip()

    if _normalize_bool(payload.get("requires_login")) or any(
        term in haystack for term in ("log in", "login", "sign in", "account")
    ):
        return "login_required"

    if any(term in haystack for term in ("closed", "unavailable", "no longer accepting", "not available")):
        return "unavailable"

    if _normalize_bool(payload.get("requires_manual_review")):
        return "manual_required"

    if payload.get("job_description") or payload.get("application_url") or payload.get("fields_detected"):
        return "ready_to_apply"

    return default


def parse_apply_inspection(result: Any, job: Job) -> dict[str, Any]:
    payload = _coerce_result_payload(result)
    platform = infer_platform(job.job_url)
    fallback = {
        "status": "manual_required",
        "reason": "TinyFish could not extract a structured application summary.",
        "job_title": job.job_title,
        "company_name": job.company_name,
        "application_url": job.job_url,
        "application_platform": get_platform_display_name(platform, job.job_url),
        "job_description": "",
        "fields_detected": [],
        "requires_resume_upload": False,
        "requires_login": False,
        "requires_manual_review": True,
        "notes": ["No structured application details were returned."],
    }

    if not isinstance(payload, dict):
        return fallback

    inspection = {
        "status": _infer_inspection_status(payload, fallback["status"]),
        "reason": _normalize_text(payload.get("reason"), fallback["reason"], limit=300),
        "job_title": _normalize_text(payload.get("job_title"), job.job_title, limit=200),
        "company_name": _normalize_text(payload.get("company_name"), job.company_name, limit=200),
        "application_url": _normalize_text(payload.get("application_url"), job.job_url, limit=600),
        "application_platform": _normalize_text(
            payload.get("application_platform"),
            get_platform_display_name(platform, job.job_url),
            limit=120,
        ),
        "job_description": _normalize_text(
            payload.get("job_description") or payload.get("job_summary"),
            "",
            limit=4000,
        ),
        "fields_detected": _normalize_string_list(payload.get("fields_detected") or payload.get("required_fields")),
        "requires_resume_upload": _normalize_bool(payload.get("requires_resume_upload")),
        "requires_login": _normalize_bool(payload.get("requires_login")),
        "requires_manual_review": _normalize_bool(payload.get("requires_manual_review")),
        "notes": _normalize_string_list(payload.get("notes")),
    }

    if not inspection["job_description"]:
        inspection["notes"].append("TinyFish did not surface a reusable job description excerpt.")

    if inspection["status"] == "ready_to_apply" and inspection["requires_login"]:
        inspection["status"] = "login_required"

    if inspection["status"] == "ready_to_apply" and inspection["requires_manual_review"]:
        inspection["notes"].append("TinyFish flagged the application flow for manual review.")

    return inspection


def _infer_fill_status(payload: dict[str, Any], default: str) -> str:
    raw_status = _normalize_text(payload.get("status")).lower()
    mapped = {
        "ready_for_review": "ready_for_review",
        "review": "ready_for_review",
        "review_required": "ready_for_review",
        "partial": "partial",
        "login_required": "login_required",
        "needs_login": "login_required",
        "manual_required": "manual_required",
        "blocked": "manual_required",
    }
    if raw_status in mapped:
        return mapped[raw_status]

    reason = _normalize_text(payload.get("reason")).lower()
    notes = " ".join(_normalize_string_list(payload.get("notes"))).lower()
    haystack = f"{reason} {notes}".strip()

    if any(term in haystack for term in ("log in", "login", "sign in", "account")):
        return "login_required"

    if any(term in haystack for term in ("captcha", "upload", "manual", "authorization", "salary", "sponsorship")):
        return "manual_required"

    filled = _normalize_string_list(payload.get("filled_fields"))
    remaining = _normalize_string_list(payload.get("remaining_fields"))
    if filled and not remaining:
        return "ready_for_review"
    if filled or remaining:
        return "partial"

    return default


def parse_fill_result(result: Any, inspection: dict[str, Any]) -> dict[str, Any]:
    payload = _coerce_result_payload(result)
    fallback = {
        "status": "partial",
        "reason": "TinyFish could not confirm which application fields were filled.",
        "filled_fields": [],
        "remaining_fields": inspection.get("fields_detected", []),
        "cover_letter_used": False,
        "notes": ["No structured fill summary was returned."],
        "final_page_summary": "",
    }

    if not isinstance(payload, dict):
        return fallback

    fill_result = {
        "status": _infer_fill_status(payload, fallback["status"]),
        "reason": _normalize_text(payload.get("reason"), fallback["reason"], limit=300),
        "filled_fields": _normalize_string_list(payload.get("filled_fields")),
        "remaining_fields": _normalize_string_list(payload.get("remaining_fields")),
        "cover_letter_used": _normalize_bool(payload.get("cover_letter_used")),
        "notes": _normalize_string_list(payload.get("notes")),
        "final_page_summary": _normalize_text(
            payload.get("final_page_summary") or payload.get("page_summary"),
            "",
            limit=500,
        ),
    }

    if not fill_result["remaining_fields"] and inspection.get("requires_resume_upload"):
        fill_result["remaining_fields"] = ["Resume upload"]

    return fill_result


def _format_profile_for_prompt(profile: UserProfile) -> str:
    profile_payload = {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "linkedin_url": profile.linkedin_url,
        "github_url": profile.github_url,
        "current_title": profile.current_title,
        "years_of_experience": profile.years_of_experience,
        "education": profile.education,
        "skills": profile.skills,
    }
    return json.dumps(profile_payload, indent=2)


def build_apply_inspection_goal(job: Job) -> str:
    return f"""
You are helping a candidate start a job application.

Target posting:
- Job title: {job.job_title}
- Company: {job.company_name}
- URL: {job.job_url}

Instructions:
1. Open the posting and read the visible job details.
2. If there is a clear Apply / Apply now / Easy Apply button, follow it into the first actual application screen.
3. If the posting redirects to an external ATS, follow it.
4. Do not create an account, do not upload files, and do not submit anything.
5. If login, account creation, CAPTCHA, OTP, email verification, or any irreversible step is required to continue, stop there and note it.
6. Capture the most relevant job description content you can see, but keep it concise and under 4000 characters.
7. Identify the visible fields or documents required to continue.
8. Return ONLY valid JSON matching the contract below. No markdown.

JSON contract:
{{
  "status": "ready_to_apply" | "login_required" | "manual_required" | "unavailable",
  "reason": "short string",
  "job_title": "string",
  "company_name": "string",
  "application_url": "absolute url",
  "application_platform": "string",
  "job_description": "string",
  "fields_detected": ["string"],
  "requires_resume_upload": true,
  "requires_login": false,
  "requires_manual_review": false,
  "notes": ["string"]
}}

Use empty strings for unknown strings and [] for unknown arrays.
""".strip()


def build_safe_fill_goal(
    job: Job,
    profile: UserProfile,
    inspection: dict[str, Any],
    cover_letter: str,
) -> str:
    application_url = inspection.get("application_url") or job.job_url
    candidate_profile = _format_profile_for_prompt(profile)
    detected_fields = json.dumps(inspection.get("fields_detected", []))

    return f"""
You are safely drafting a job application for review.

Target job:
- Job title: {job.job_title}
- Company: {job.company_name}
- Application URL: {application_url}

Candidate profile JSON:
{candidate_profile}

Known fields from the previous inspection:
{detected_fields}

Cover letter to use if a text area is present:
\"\"\"
{cover_letter}
\"\"\"

Instructions:
1. Open the application flow and get as far as you safely can.
2. Fill only fields that exactly match the provided candidate profile.
3. Paste the cover letter only into a cover letter / message / additional information text area if one exists.
4. Do not create an account.
5. Do not upload files.
6. Do not answer sensitive questions about work authorization, sponsorship, salary expectations, demographics, disability, veteran status, legal attestations, or checkboxes that submit consent.
7. Do not click the final submit button.
8. Stop on the final review screen or the furthest safe point you can reach.
9. Return ONLY valid JSON matching the contract below. No markdown.

JSON contract:
{{
  "status": "ready_for_review" | "login_required" | "manual_required" | "partial",
  "reason": "short string",
  "filled_fields": ["string"],
  "remaining_fields": ["string"],
  "cover_letter_used": true,
  "notes": ["string"],
  "final_page_summary": "string"
}}

Use [] for unknown arrays and empty strings for unknown strings.
""".strip()


def _build_cover_letter_prompt(profile: UserProfile, job: Job, inspection: dict[str, Any]) -> str:
    skills = ", ".join(profile.skills) if profile.skills else "Not specified"
    return f"""Candidate profile:
- Name: {profile.first_name} {profile.last_name}
- Current title: {profile.current_title or 'Not specified'}
- Years of experience: {profile.years_of_experience or 'Not specified'}
- Education: {profile.education or 'Not specified'}
- Location: {profile.location or 'Not specified'}
- Skills: {skills}

Target job:
- Title: {inspection.get('job_title') or job.job_title}
- Company: {inspection.get('company_name') or job.company_name}
- Platform: {inspection.get('application_platform') or get_platform_display_name(infer_platform(job.job_url), job.job_url)}

Job description / summary:
{inspection.get('job_description') or 'Not available'}

Write a tailored cover letter."""


def _build_fallback_cover_letter(profile: UserProfile, job: Job, inspection: dict[str, Any]) -> str:
    skills = ", ".join(profile.skills[:5]) if profile.skills else "a strong willingness to learn quickly"
    current_title = profile.current_title or "an early-career candidate"
    education = profile.education or "my academic background"
    company_name = inspection.get("company_name") or job.company_name or "your team"
    job_title = inspection.get("job_title") or job.job_title
    full_name = " ".join(part for part in [profile.first_name, profile.last_name] if part).strip() or "Candidate"

    return (
        f"Dear Hiring Team,\n\n"
        f"I am excited to apply for the {job_title} role at {company_name}. "
        f"As {current_title}, I bring a foundation in {education} along with experience building and learning through hands-on work.\n\n"
        f"I am especially drawn to this opportunity because it aligns with my interest in practical, high-impact work. "
        f"My background includes {skills}, and I would be eager to contribute that combination of curiosity, execution, and ownership to your team.\n\n"
        f"Thank you for your time and consideration. I would welcome the opportunity to discuss how I can contribute to {company_name}.\n\n"
        f"Sincerely,\n{full_name}"
    )


def generate_cover_letter(profile: UserProfile, job: Job, inspection: dict[str, Any]) -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning(
            "OpenAI API key missing for cover letter generation %s",
            format_fields(job_id=job.id, company_name=job.company_name),
        )
        return (_build_fallback_cover_letter(profile, job, inspection), "template")

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": APPLY_COVER_LETTER_SYSTEM_PROMPT},
                {"role": "user", "content": _build_cover_letter_prompt(profile, job, inspection)},
            ],
            temperature=0.6,
        )
        cover_letter = _normalize_text(response.choices[0].message.content)
        if not cover_letter:
            raise ValueError("OpenAI returned an empty cover letter")
        return (cover_letter, "openai")
    except Exception as exc:
        logger.exception(
            "OpenAI cover letter generation failed %s",
            format_fields(job_id=job.id, company_name=job.company_name, error=str(exc)),
        )
        return (_build_fallback_cover_letter(profile, job, inspection), "template")


async def _run_apply_step(
    *,
    application_id: str,
    stage: str,
    label: str,
    url: str,
    goal: str,
    proxy_config: dict[str, Any] | None,
    event_queue: asyncio.Queue,
) -> ApplyStepResult:
    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key:
        return ApplyStepResult(payload=None, error="TINYFISH_API_KEY is missing", preview_url=None, run_id=None)

    headers = {
        "X-API-Key": api_key,
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "goal": goal,
        "browser_profile": "stealth",
    }
    if proxy_config:
        payload["proxy_config"] = proxy_config

    logger.info(
        "Apply step started %s",
        format_fields(
            application_id=application_id,
            stage=stage,
            label=label,
            url=url,
            has_proxy=bool(proxy_config),
        ),
    )

    preview_url = None
    preview_emitted = False
    run_id = None
    result_text = ""
    final_error = None

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=30.0)) as http_client:
            async with http_client.stream(
                "POST",
                TINYFISH_SSE_URL,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    stripped_line = line.strip()
                    if not stripped_line.startswith("data:"):
                        continue

                    payload_text = stripped_line[5:].lstrip()
                    if not payload_text:
                        continue

                    event = json.loads(payload_text)
                    event_type = event.get("type")
                    status = event.get("status")
                    purpose = event.get("purpose")
                    message = event.get("message")
                    error = event.get("error")
                    run_id = event.get("run_id") or run_id

                    if event_type in {"STARTED", "PROGRESS", "ERROR", "FAILED"} or purpose or message:
                        await event_queue.put({
                            "event": "apply_trace",
                            "data": {
                                "stage": stage,
                                "label": label,
                                "run_id": run_id,
                                "tinyfish_type": event_type,
                                "status": status,
                                "purpose": purpose,
                                "message": message,
                                "error": error,
                            },
                        })

                    if run_id and _event_indicates_bot_challenge(event):
                        final_error = await _cancel_run(http_client, headers, run_id)
                        break

                    if event_type == "STREAMING_URL" and event.get("streaming_url"):
                        preview_url = event["streaming_url"]
                        preview_emitted = True
                        await event_queue.put({
                            "event": "apply_preview",
                            "data": {
                                "stage": stage,
                                "label": label,
                                "streaming_url": preview_url,
                            },
                        })
                        continue

                    if not preview_emitted and run_id and event_type == "STARTED":
                        recovered_streaming_url = await _fetch_streaming_url(http_client, headers, run_id)
                        if recovered_streaming_url:
                            preview_url = recovered_streaming_url
                            preview_emitted = True
                            await event_queue.put({
                                "event": "apply_preview",
                                "data": {
                                    "stage": stage,
                                    "label": label,
                                    "streaming_url": preview_url,
                                },
                            })

                    if event_type == "COMPLETE":
                        result = event.get("result") or event.get("resultJson") or ""
                        result_text = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        break

                    if event_type in {"ERROR", "FAILED"}:
                        final_error = error or f"Apply step failed with event type {event_type}"
                        break

            if not preview_emitted and run_id:
                recovered_streaming_url = await _fetch_streaming_url(http_client, headers, run_id)
                if recovered_streaming_url:
                    preview_url = recovered_streaming_url
                    preview_emitted = True
                    await event_queue.put({
                        "event": "apply_preview",
                        "data": {
                            "stage": stage,
                            "label": label,
                            "streaming_url": preview_url,
                        },
                    })
    except Exception as exc:
        logger.exception(
            "Apply step crashed %s",
            format_fields(application_id=application_id, stage=stage, label=label, error=str(exc)),
        )
        return ApplyStepResult(payload=None, error=str(exc), preview_url=preview_url, run_id=run_id)

    if final_error:
        logger.warning(
            "Apply step ended with failure %s",
            format_fields(application_id=application_id, stage=stage, label=label, error=final_error),
        )
        return ApplyStepResult(payload=None, error=final_error, preview_url=preview_url, run_id=run_id)

    return ApplyStepResult(
        payload=_coerce_result_payload(result_text),
        error=None,
        preview_url=preview_url,
        run_id=run_id,
    )


async def orchestrate_application(
    job: Job,
    profile: UserProfile,
    application_id: str,
) -> AsyncGenerator[dict[str, Any], None]:
    platform = infer_platform(job.job_url)
    platform_label = get_platform_display_name(platform, job.job_url)
    proxy_config = build_proxy_config(platform, job.job_url)

    yield {
        "event": "apply_started",
        "data": {
            "application_id": application_id,
            "job_id": job.id,
            "job_title": job.job_title,
            "company_name": job.company_name,
            "platform": platform.value,
            "platform_label": platform_label,
        },
    }

    yield {
        "event": "apply_phase",
        "data": {
            "phase": "Inspecting",
            "message": f"TinyFish is opening the {platform_label} application flow and mapping the form.",
        },
    }

    event_queue: asyncio.Queue = asyncio.Queue()
    inspect_task = asyncio.create_task(
        _run_apply_step(
            application_id=application_id,
            stage="inspect",
            label=f"{platform_label} Application Scout",
            url=job.job_url,
            goal=build_apply_inspection_goal(job),
            proxy_config=proxy_config,
            event_queue=event_queue,
        )
    )

    while not inspect_task.done() or not event_queue.empty():
        while not event_queue.empty():
            yield await event_queue.get()
        if not inspect_task.done():
            await asyncio.sleep(0.15)

    inspection_step = await inspect_task

    while not event_queue.empty():
        yield await event_queue.get()

    if inspection_step.error:
        error_text = inspection_step.error
        lowered_error = error_text.lower()
        if any(term in lowered_error for term in ("bot protection", "captcha", "access denied")):
            yield {
                "event": "apply_blocked",
                "data": {
                    "status": "manual_required",
                    "reason": error_text,
                    "job_id": job.id,
                    "job_url": job.job_url,
                },
            }
        else:
            yield {
                "event": "apply_error",
                "data": {
                    "job_id": job.id,
                    "error": error_text,
                },
            }
        return

    inspection = parse_apply_inspection(inspection_step.payload, job)
    yield {
        "event": "apply_inspection",
        "data": {
            **inspection,
            "job_id": job.id,
        },
    }

    if inspection["status"] != "ready_to_apply":
        yield {
            "event": "apply_blocked",
            "data": {
                **inspection,
                "job_id": job.id,
                "job_url": job.job_url,
            },
        }
        return

    yield {
        "event": "apply_phase",
        "data": {
            "phase": "Drafting",
            "message": "OpenAI is tailoring a cover letter from the job description and your profile.",
        },
    }

    cover_letter, cover_letter_source = await asyncio.to_thread(generate_cover_letter, profile, job, inspection)

    yield {
        "event": "cover_letter_ready",
        "data": {
            "job_id": job.id,
            "source": cover_letter_source,
            "cover_letter": cover_letter,
        },
    }

    fill_url = inspection.get("application_url") or job.job_url
    yield {
        "event": "apply_phase",
        "data": {
            "phase": "Safe Fill",
            "message": "TinyFish is filling the safe, reversible fields and stopping before submit.",
        },
    }

    fill_task = asyncio.create_task(
        _run_apply_step(
            application_id=application_id,
            stage="fill",
            label=f"{platform_label} AutoFill",
            url=fill_url,
            goal=build_safe_fill_goal(job, profile, inspection, cover_letter),
            proxy_config=proxy_config,
            event_queue=event_queue,
        )
    )

    while not fill_task.done() or not event_queue.empty():
        while not event_queue.empty():
            yield await event_queue.get()
        if not fill_task.done():
            await asyncio.sleep(0.15)

    fill_step = await fill_task

    while not event_queue.empty():
        yield await event_queue.get()

    if fill_step.error:
        fill_result = {
            "status": "manual_required",
            "reason": fill_step.error,
            "filled_fields": [],
            "remaining_fields": inspection.get("fields_detected", []),
            "cover_letter_used": False,
            "notes": [fill_step.error],
            "final_page_summary": "",
        }
    else:
        fill_result = parse_fill_result(fill_step.payload, inspection)

    yield {
        "event": "apply_fill_result",
        "data": {
            **fill_result,
            "job_id": job.id,
            "application_url": fill_url,
        },
    }

    final_messages = {
        "ready_for_review": "Application draft is staged and ready for a final human review.",
        "partial": "TinyFish filled part of the form and surfaced the remaining blockers.",
        "login_required": "A logged-in session is still required before the application can continue.",
        "manual_required": "A manual step is still required before the application can continue.",
    }

    yield {
        "event": "apply_complete",
        "data": {
            "job_id": job.id,
            "status": fill_result["status"],
            "message": final_messages.get(fill_result["status"], "Application copilot finished its pass."),
            "application_url": fill_url,
        },
    }
