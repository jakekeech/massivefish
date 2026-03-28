import asyncio
import json
import os
import time
from typing import Any, AsyncGenerator
from urllib.parse import urljoin

import httpx

from logging_utils import format_fields, get_logger
from models import Job
from platforms import build_search_targets


logger = get_logger("jobswarm.orchestrator")
TINYFISH_SSE_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"
TINYFISH_RUNS_URL = "https://agent.tinyfish.ai/v1/runs"
BOT_CHALLENGE_TERMS = (
    "captcha",
    "verify you are human",
    "verify you're human",
    "are you human",
    "human verification",
    "security check",
    "bot detection",
    "unusual traffic",
    "access denied",
    "press and hold",
    "cf-challenge",
    "cloudflare",
    "robot check",
)

JOB_LIST_KEYS = ("jobs", "results", "listings", "items", "data")
TITLE_KEYS = ("job_title", "title", "position", "role")
COMPANY_KEYS = ("company_name", "company", "organization", "employer")
URL_KEYS = ("job_url", "url", "link", "posting_url", "apply_url")
LOCATION_KEYS = ("location", "job_location", "city")
POSTED_TIME_KEYS = ("posted_time", "posted", "date_posted", "posted_at")
SALARY_KEYS = ("salary", "compensation", "pay")
EMPLOYMENT_TYPE_KEYS = ("employment_type", "type", "job_type")


async def _run_sse_agent(
    target: dict,
    hunt_id: str,
    event_queue: asyncio.Queue,
) -> tuple[dict, list[Job], str | None]:
    """Run a TinyFish automation through the documented SSE endpoint."""
    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key:
        return (target, [], "TINYFISH_API_KEY is missing")

    logger.info(
        "SSE agent run started %s",
        format_fields(
            hunt_id=hunt_id,
            target_id=target["id"],
            label=target["label"],
            url=target["url"],
            browser_profile=target["browser_profile"],
        ),
    )

    result_text = ""
    final_error = None
    preview_emitted = False
    run_id = None
    cancelled_for_bot_challenge = False

    headers = {
        "X-API-Key": api_key,
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    payload = {
        "url": target["url"],
        "goal": target["goal"],
        "browser_profile": target["browser_profile"],
    }
    if target.get("proxy_config"):
        payload["proxy_config"] = target["proxy_config"]

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
                    error = event.get("error")
                    purpose = event.get("purpose")
                    message = event.get("message")
                    run_id = event.get("run_id") or run_id
                    logger.info(
                        "SSE agent event received %s",
                        format_fields(
                            hunt_id=hunt_id,
                            target_id=target["id"],
                            label=target["label"],
                            event_type=event_type,
                            status=status,
                            run_id=run_id,
                            purpose=purpose,
                            message=message,
                            has_streaming_url=bool(event.get("streaming_url")),
                            has_result=bool(event.get("result") or event.get("resultJson")),
                            has_error=bool(error),
                        ),
                    )
                    await event_queue.put({
                        "event": "agent_trace",
                        "data": {
                            "platform": target["id"],
                            "label": target["label"],
                            "tinyfish_type": event_type,
                            "status": status,
                            "run_id": run_id,
                            "purpose": purpose,
                            "message": message,
                            "error": error,
                            "has_streaming_url": bool(event.get("streaming_url")),
                        },
                    })

                    if run_id and _event_indicates_bot_challenge(event):
                        cancelled_for_bot_challenge = True
                        cancellation_message = await _cancel_run(http_client, headers, run_id)
                        final_error = cancellation_message or "Bot protection challenge detected; run cancelled"
                        logger.warning(
                            "Cancelling TinyFish run due to bot challenge %s",
                            format_fields(
                                hunt_id=hunt_id,
                                target_id=target["id"],
                                label=target["label"],
                                run_id=run_id,
                                event_type=event_type,
                                purpose=purpose,
                                message=message,
                                error=error,
                            ),
                        )
                        break

                    if not preview_emitted and run_id and event_type == "STARTED":
                        recovered_streaming_url = await _fetch_streaming_url(http_client, headers, run_id)
                        if recovered_streaming_url:
                            preview_emitted = True
                            await event_queue.put({
                                "event": "agent_preview",
                                "data": {
                                    "platform": target["id"],
                                    "label": target["label"],
                                    "streaming_url": recovered_streaming_url,
                                },
                            })

                    if event_type == "STREAMING_URL" and event.get("streaming_url"):
                        preview_emitted = True
                        await event_queue.put({
                            "event": "agent_preview",
                            "data": {
                                "platform": target["id"],
                                "label": target["label"],
                                "streaming_url": event["streaming_url"],
                            },
                        })
                        continue

                    if event_type == "COMPLETE":
                        result = event.get("result") or event.get("resultJson") or ""
                        result_text = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        break

                    if event_type in {"ERROR", "FAILED"}:
                        final_error = event.get("error") or f"SSE run failed with event type {event_type}"
                        break

            if not preview_emitted and run_id:
                recovered_streaming_url = await _fetch_streaming_url(http_client, headers, run_id)
                if recovered_streaming_url:
                    preview_emitted = True
                    await event_queue.put({
                        "event": "agent_preview",
                        "data": {
                            "platform": target["id"],
                            "label": target["label"],
                            "streaming_url": recovered_streaming_url,
                        },
                    })

    except Exception as exc:
        logger.exception(
            "SSE agent failed %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"], error=str(exc)),
        )
        return (target, [], str(exc))

    if final_error:
        logger.warning(
            "SSE agent completed with failure %s",
            format_fields(
                hunt_id=hunt_id,
                target_id=target["id"],
                label=target["label"],
                error=final_error,
                cancelled_for_bot_challenge=cancelled_for_bot_challenge,
            ),
        )
        return (target, [], final_error)

    if not preview_emitted:
        logger.warning(
            "SSE agent completed without streaming URL %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"]),
        )
        await event_queue.put({
            "event": "agent_preview_missing",
            "data": {
                "platform": target["id"],
                "label": target["label"],
                "message": "TinyFish completed without exposing a retrievable streaming URL",
            },
        })

    jobs = parse_jobs_from_result(result_text, target, hunt_id)
    return (target, jobs, None)


async def run_single_agent(
    target: dict,
    hunt_id: str,
    event_queue: asyncio.Queue,
) -> tuple[dict, list[Job], str | None]:
    """Run a single TinyFish agent and return parsed jobs."""
    return await _run_sse_agent(target, hunt_id, event_queue)


def _event_indicates_bot_challenge(event: dict) -> bool:
    text_parts = [
        str(event.get("type", "")),
        str(event.get("status", "")),
        str(event.get("purpose", "")),
        str(event.get("message", "")),
        str(event.get("error", "")),
    ]
    haystack = " ".join(text_parts).lower()
    return any(term in haystack for term in BOT_CHALLENGE_TERMS)


async def _cancel_run(
    http_client: httpx.AsyncClient,
    headers: dict[str, str],
    run_id: str,
) -> str:
    try:
        response = await http_client.post(f"{TINYFISH_RUNS_URL}/{run_id}/cancel", headers=headers)
        response.raise_for_status()
        data = response.json()
        message = data.get("message")
        status = data.get("status")
        if message:
            return f"Bot protection challenge detected; TinyFish run cancelled ({message})"
        if status:
            return f"Bot protection challenge detected; TinyFish run ended with status {status}"
    except Exception as exc:
        return f"Bot protection challenge detected; cancellation attempt failed: {exc}"

    return "Bot protection challenge detected; run cancelled"


async def _fetch_streaming_url(
    http_client: httpx.AsyncClient,
    headers: dict[str, str],
    run_id: str,
    attempts: int = 4,
    delay_seconds: float = 0.5,
) -> str | None:
    for attempt in range(attempts):
        try:
            response = await http_client.get(f"{TINYFISH_RUNS_URL}/{run_id}", headers=headers)
            response.raise_for_status()
            data = response.json()
        except Exception:
            data = None

        if isinstance(data, dict):
            streaming_url = data.get("streaming_url")
            if streaming_url:
                return streaming_url

            status = str(data.get("status", "")).upper()
            if status in {"COMPLETED", "FAILED", "ERROR", "CANCELLED"}:
                break

        if attempt < attempts - 1:
            await asyncio.sleep(delay_seconds)

    return None


def _extract_first(item: dict, keys: tuple[str, ...], default=None):
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_job_url(raw_url, base_url: str) -> str:
    if raw_url in (None, ""):
        return ""

    normalized = str(raw_url).strip()
    if not normalized:
        return ""

    return urljoin(base_url, normalized)


def _extract_job_items(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in JOB_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value
            nested_items = _extract_job_items(value)
            if nested_items:
                return nested_items
        for value in payload.values():
            nested_items = _extract_job_items(value)
            if nested_items:
                return nested_items
            if isinstance(value, list) and value and all(isinstance(entry, dict) for entry in value):
                return value
        if any(key in payload for key in TITLE_KEYS) and any(key in payload for key in URL_KEYS):
            return [payload]

    return []


def _serialize_result_preview(result: Any, preview_chars: int = 200) -> tuple[str, int]:
    if isinstance(result, str):
        return (result[:preview_chars], len(result))

    if isinstance(result, (dict, list)):
        serialized = json.dumps(result)
        return (serialized[:preview_chars], len(serialized))

    if result is None:
        return ("", 0)

    serialized = str(result)
    return (serialized[:preview_chars], len(serialized))


def _coerce_result_payload(result: Any):
    if isinstance(result, (dict, list)):
        return result

    if result is None:
        return None

    if not isinstance(result, str):
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if hasattr(result, "dict"):
            return result.dict()
        result = str(result)

    stripped = result.strip()
    if not stripped:
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    candidate_starts = [index for index, char in enumerate(result) if char in "{["]

    for start in candidate_starts:
        try:
            payload, _ = decoder.raw_decode(result[start:])
        except json.JSONDecodeError:
            continue

        if isinstance(payload, (dict, list)):
            return payload

    return None


def parse_jobs_from_result(result: Any, target: dict, hunt_id: str) -> list[Job]:
    """Parse job listings from TinyFish result string."""
    jobs = []
    result_preview, result_length = _serialize_result_preview(result)
    logger.info(
        "Parsing agent result %s",
        format_fields(
            hunt_id=hunt_id,
            target_id=target["id"],
            label=target["label"],
            result_length=result_length,
            result_preview=result_preview,
        ),
    )

    try:
        payload = _coerce_result_payload(result)

        for item in _extract_job_items(payload):
            if not isinstance(item, dict):
                continue

            job_title = _extract_first(item, TITLE_KEYS)
            company_name = _extract_first(item, COMPANY_KEYS, "Unknown")
            job_url = _normalize_job_url(_extract_first(item, URL_KEYS, ""), target["url"])

            if not job_title or not job_url:
                continue

            jobs.append(
                Job.create(
                    platform=target["platform"],
                    job_title=job_title,
                    company_name=company_name,
                    location=_extract_first(item, LOCATION_KEYS, ""),
                    job_url=job_url,
                    posted_time=_extract_first(item, POSTED_TIME_KEYS, ""),
                    salary=_extract_first(item, SALARY_KEYS),
                    employment_type=_extract_first(item, EMPLOYMENT_TYPE_KEYS),
                )
            )

        logger.info(
            "Parsed jobs from result %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"], parsed_jobs=len(jobs)),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.exception(
            "Failed parsing jobs %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"], error=str(exc)),
        )

    return jobs


async def orchestrate_hunt(
    role: str,
    location: str,
    hunt_id: str,
    keywords: list[str] | None = None,
    target_urls: list[str] | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Orchestrate parallel scraping across all platforms.
    Yields SSE events as agents progress.
    """
    keywords = keywords or []
    logger.info(
        "Orchestration started %s",
        format_fields(hunt_id=hunt_id, role=role, location=location, keywords=keywords, target_urls=target_urls),
    )
    targets = build_search_targets(role.lower(), location, keywords, target_urls=target_urls)
    all_jobs: list[Job] = []
    start_time = time.time()
    event_queue: asyncio.Queue = asyncio.Queue()

    logger.info(
        "Built platform targets %s",
        format_fields(
            hunt_id=hunt_id,
            targets=[
                {
                    "id": target["id"],
                    "label": target["label"],
                    "platform": target["platform"].value,
                    "url": target["url"],
                    "browser_profile": target["browser_profile"],
                }
                for target in targets
            ],
        ),
    )

    for target in targets:
        yield {
            "event": "agent_started",
            "data": {"platform": target["id"], "label": target["label"], "status": "queued"},
        }

    async def run_and_track(target: dict) -> tuple[dict, list[Job], str | None, float]:
        completed_target, jobs, error = await run_single_agent(target, hunt_id, event_queue)
        elapsed = time.time() - start_time
        return (completed_target, jobs, error, elapsed)

    tasks = [asyncio.create_task(run_and_track(target)) for target in targets]

    for target in targets:
        logger.info(
            "Agent scheduled %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"]),
        )
        yield {
            "event": "agent_running",
            "data": {"platform": target["id"], "label": target["label"], "status": "running"},
        }

    pending_tasks = set(tasks)
    while pending_tasks:
        while not event_queue.empty():
            queued_event = await event_queue.get()
            yield queued_event

        done, pending_tasks = await asyncio.wait(
            pending_tasks,
            timeout=0.2,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            target, jobs, error, elapsed = await task

            if error:
                logger.warning(
                    "Agent completed with failure %s",
                    format_fields(
                        hunt_id=hunt_id,
                        target_id=target["id"],
                        label=target["label"],
                        error=error,
                        elapsed=round(elapsed, 1),
                    ),
                )
                yield {
                    "event": "agent_failed",
                    "data": {
                        "platform": target["id"],
                        "label": target["label"],
                        "error": error,
                        "elapsed": round(elapsed, 1),
                    },
                }
            else:
                all_jobs.extend(jobs)
                logger.info(
                    "Agent completed successfully %s",
                    format_fields(
                        hunt_id=hunt_id,
                        target_id=target["id"],
                        label=target["label"],
                        jobs_found=len(jobs),
                        elapsed=round(elapsed, 1),
                    ),
                )
                yield {
                    "event": "agent_complete",
                    "data": {
                        "platform": target["id"],
                        "label": target["label"],
                        "jobs_found": len(jobs),
                        "elapsed": round(elapsed, 1),
                    },
                }

    while not event_queue.empty():
        queued_event = await event_queue.get()
        yield queued_event

    logger.info(
        "Scraping complete %s",
        format_fields(hunt_id=hunt_id, total_jobs=len(all_jobs)),
    )
    yield {
        "event": "scraping_complete",
        "data": {
            "total_jobs": len(all_jobs),
            "jobs": [job.model_dump() for job in all_jobs],
        },
    }
