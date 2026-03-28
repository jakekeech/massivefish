import asyncio
import json
import time
from typing import AsyncGenerator
from tinyfish import AsyncTinyFish
from models import Platform, Job, AgentStatus, PlatformStatus
from platforms import build_search_urls, UNIVERSAL_JOB_GOAL


async def run_single_agent(
    client: AsyncTinyFish,
    platform: Platform,
    url: str,
) -> tuple[Platform, list[Job], str | None]:
    """Run a single TinyFish agent and return parsed jobs."""
    try:
        # Use the synchronous run method which waits for completion
        response = await client.agent.run(
            url=url,
            goal=UNIVERSAL_JOB_GOAL,
        )

        # Parse the result - check for completion status
        if hasattr(response, 'status') and response.status == "COMPLETED":
            result_text = getattr(response, 'result', '') or ''
            jobs = parse_jobs_from_result(result_text, platform)
            return (platform, jobs, None)
        elif hasattr(response, 'result') and response.result:
            # Some SDK versions return result directly
            jobs = parse_jobs_from_result(str(response.result), platform)
            return (platform, jobs, None)
        else:
            error = getattr(response, 'error', None) or 'No results returned'
            return (platform, [], str(error))

    except Exception as e:
        return (platform, [], str(e))


def parse_jobs_from_result(result: str, platform: Platform) -> list[Job]:
    """Parse job listings from TinyFish result string."""
    jobs = []
    try:
        # Try to extract JSON array from the result
        # TinyFish may return JSON wrapped in text
        json_start = result.find('[')
        json_end = result.rfind(']') + 1

        if json_start >= 0 and json_end > json_start:
            json_str = result[json_start:json_end]
            data = json.loads(json_str)

            for item in data:
                if isinstance(item, dict) and 'job_title' in item:
                    jobs.append(Job.create(
                        platform=platform,
                        job_title=item.get('job_title', 'Unknown'),
                        company_name=item.get('company_name', 'Unknown'),
                        location=item.get('location', ''),
                        job_url=item.get('job_url', ''),
                        posted_time=item.get('posted_time', ''),
                        salary=item.get('salary'),
                        employment_type=item.get('employment_type'),
                    ))
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Failed to parse jobs from {platform}: {e}")

    return jobs


async def orchestrate_hunt(
    role: str,
    location: str,
) -> AsyncGenerator[dict, None]:
    """
    Orchestrate parallel scraping across all platforms.
    Yields SSE events as agents progress.
    """
    client = AsyncTinyFish()
    targets = build_search_urls(role, location)
    all_jobs: list[Job] = []
    start_time = time.time()

    # Emit initial queued status for all platforms
    for target in targets:
        platform = target["platform"]
        yield {
            "event": "agent_started",
            "data": {"platform": platform.value, "status": "queued"}
        }

    # Create async tasks for all agents
    async def run_and_track(target: dict) -> tuple[Platform, list[Job], str | None, float]:
        platform = target["platform"]
        url = target["url"]
        platform_result, jobs, error = await run_single_agent(client, platform, url)
        elapsed = time.time() - start_time
        return (platform, jobs, error, elapsed)

    tasks = [run_and_track(t) for t in targets]

    # Process results as each agent completes
    for coro in asyncio.as_completed(tasks):
        platform, jobs, error, elapsed = await coro

        if error:
            yield {
                "event": "agent_failed",
                "data": {
                    "platform": platform.value,
                    "error": error,
                    "elapsed": round(elapsed, 1)
                }
            }
        else:
            all_jobs.extend(jobs)
            yield {
                "event": "agent_complete",
                "data": {
                    "platform": platform.value,
                    "jobs_found": len(jobs),
                    "elapsed": round(elapsed, 1)
                }
            }

    # Return all collected jobs
    yield {
        "event": "scraping_complete",
        "data": {
            "total_jobs": len(all_jobs),
            "jobs": [job.model_dump() for job in all_jobs]
        }
    }
