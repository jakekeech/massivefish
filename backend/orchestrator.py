import asyncio
import json
import os
import time
from typing import AsyncGenerator

import httpx
from tinyfish import AsyncTinyFish

from logging_utils import format_fields, get_logger
from models import Job, Platform
from platforms import build_search_targets


logger = get_logger("jobswarm.orchestrator")
TINYFISH_SSE_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"


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

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "url": target["url"],
        "goal": target["goal"],
        "browser_profile": target["browser_profile"],
    }

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
                    if not line.startswith("data: "):
                        continue

                    event = json.loads(line[6:])
                    event_type = event.get("type")
                    status = event.get("status")
                    error = event.get("error")
                    logger.info(
                        "SSE agent event received %s",
                        format_fields(
                            hunt_id=hunt_id,
                            target_id=target["id"],
                            label=target["label"],
                            event_type=event_type,
                            status=status,
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
                            "error": error,
                            "has_streaming_url": bool(event.get("streaming_url")),
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

    except Exception as exc:
        logger.exception(
            "SSE agent failed %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"], error=str(exc)),
        )
        return (target, [], str(exc))

    if final_error:
        logger.warning(
            "SSE agent completed with failure %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"], error=final_error),
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
                "message": "TinyFish completed without emitting STREAMING_URL",
            },
        })

    jobs = parse_jobs_from_result(result_text, target, hunt_id)
    return (target, jobs, None)


async def run_single_agent(
    client: AsyncTinyFish,
    target: dict,
    hunt_id: str,
    event_queue: asyncio.Queue,
) -> tuple[dict, list[Job], str | None]:
    """Run a single TinyFish agent and return parsed jobs."""
    if target["platform"] == Platform.LINKEDIN:
        return await _run_sse_agent(target, hunt_id, event_queue)

    logger.info(
        "Agent run started %s",
        format_fields(
            hunt_id=hunt_id,
            target_id=target["id"],
            label=target["label"],
            url=target["url"],
            browser_profile=target["browser_profile"],
        ),
    )

    try:
        response = await client.agent.run(
            url=target["url"],
            goal=target["goal"],
            browser_profile=target["browser_profile"],
        )
        logger.info(
            "Agent raw response received %s",
            format_fields(
                hunt_id=hunt_id,
                target_id=target["id"],
                label=target["label"],
                response_type=type(response).__name__,
                status=getattr(response, "status", None),
                has_result=bool(getattr(response, "result", None)),
                has_error=bool(getattr(response, "error", None)),
            ),
        )

        if hasattr(response, "status") and response.status == "COMPLETED":
            result_text = getattr(response, "result", "") or ""
            jobs = parse_jobs_from_result(result_text, target, hunt_id)
            return (target, jobs, None)

        if hasattr(response, "result") and response.result:
            jobs = parse_jobs_from_result(str(response.result), target, hunt_id)
            return (target, jobs, None)

        error = getattr(response, "error", None) or "No results returned"
        logger.warning(
            "Agent returned no usable results %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"], error=str(error)),
        )
        return (target, [], str(error))
    except Exception as exc:
        logger.exception(
            "Agent run failed %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"], error=str(exc)),
        )
        return (target, [], str(exc))


def parse_jobs_from_result(result: str, target: dict, hunt_id: str) -> list[Job]:
    """Parse job listings from TinyFish result string."""
    jobs = []
    logger.info(
        "Parsing agent result %s",
        format_fields(
            hunt_id=hunt_id,
            target_id=target["id"],
            label=target["label"],
            result_length=len(result),
            result_preview=result[:200],
        ),
    )

    try:
        json_start = result.find("[")
        json_end = result.rfind("]") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = result[json_start:json_end]
            data = json.loads(json_str)

            for item in data:
                if isinstance(item, dict) and "job_title" in item:
                    jobs.append(
                        Job.create(
                            platform=target["platform"],
                            job_title=item.get("job_title", "Unknown"),
                            company_name=item.get("company_name", "Unknown"),
                            location=item.get("location", ""),
                            job_url=item.get("job_url", ""),
                            posted_time=item.get("posted_time", ""),
                            salary=item.get("salary"),
                            employment_type=item.get("employment_type"),
                        )
                    )

        logger.info(
            "Parsed jobs from result %s",
            format_fields(hunt_id=hunt_id, target_id=target["id"], label=target["label"], parsed_jobs=len(jobs)),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
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
    client = AsyncTinyFish()
    targets = build_search_targets(role, location, keywords, target_urls=target_urls)
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
        completed_target, jobs, error = await run_single_agent(client, target, hunt_id, event_queue)
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
