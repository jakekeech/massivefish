import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from logging_utils import configure_logging, format_fields, get_logger
from models import HuntRequest, HuntResult, Job, UserProfile
from orchestrator import orchestrate_hunt
from scorer import filter_duplicates, score_jobs
from state import get_hunt, get_jobs_for_hunt, get_profile, save_hunt, set_profile


configure_logging()
logger = get_logger("jobswarm.api")

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
ENV_FILE_LOADED = load_dotenv(ENV_PATH)


def env_status() -> dict[str, bool | str]:
    """Return a safe, non-secret summary of environment loading."""
    return {
        "env_path": str(ENV_PATH),
        "env_file_exists": ENV_PATH.exists(),
        "env_file_loaded": ENV_FILE_LOADED,
        "tinyfish_api_key_present": bool(os.getenv("TINYFISH_API_KEY")),
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JobSwarm API starting")
    logger.info("Environment status %s", format_fields(**env_status()))
    yield
    logger.info("JobSwarm API shutting down")


app = FastAPI(
    title="JobSwarm API",
    description="Parallel job scraping swarm powered by TinyFish",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    logger.info(
        "HTTP request started %s",
        format_fields(
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            client=request.client.host if request.client else None,
        ),
    )

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "HTTP request failed %s",
            format_fields(method=request.method, path=request.url.path, elapsed_ms=elapsed_ms),
        )
        raise

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "HTTP request completed %s",
        format_fields(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        ),
    )
    return response


@app.get("/")
async def root():
    logger.info("Health check requested")
    return {"status": "ok", "service": "JobSwarm API"}


@app.get("/api/debug/env")
async def debug_env():
    """Inspect env loading without returning secret values."""
    status = env_status()
    logger.info("Environment debug requested %s", format_fields(**status))
    return status


@app.post("/api/profile")
async def save_profile(profile: UserProfile):
    """Save user profile to memory."""
    set_profile(profile)
    logger.info(
        "Profile saved %s",
        format_fields(
            email=profile.email,
            current_title=profile.current_title,
            skills_count=len(profile.skills),
        ),
    )
    return {"status": "saved", "name": f"{profile.first_name} {profile.last_name}"}


@app.get("/api/profile")
async def get_current_profile():
    """Get current user profile."""
    profile = get_profile()
    if not profile:
        logger.warning("Profile requested before being set")
        raise HTTPException(status_code=404, detail="No profile set")

    logger.info("Profile fetched %s", format_fields(email=profile.email))
    return profile


@app.post("/api/hunt")
async def start_hunt(request: HuntRequest):
    """
    Start a parallel job hunt across all platforms.
    Returns an SSE stream with progress updates.
    """
    hunt_id = str(uuid.uuid4())[:8]
    profile = get_profile()
    logger.info(
        "Hunt requested %s",
        format_fields(
            hunt_id=hunt_id,
            role=request.role,
            location=request.location,
            keywords=request.keywords,
            target_urls=request.target_urls,
            profile_present=profile is not None,
        ),
    )

    async def event_generator():
        all_jobs: list[Job] = []

        try:
            async for event in orchestrate_hunt(
                request.role,
                request.location,
                hunt_id=hunt_id,
                keywords=request.keywords,
                target_urls=request.target_urls,
            ):
                logger.info(
                    "Streaming SSE event %s",
                    format_fields(hunt_id=hunt_id, event=event["event"], data=event["data"]),
                )
                
                if event["event"] == "scraping_complete":
                    for job_data in event["data"]["jobs"]:
                        all_jobs.append(Job(**job_data))
                    continue

                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"]),
                }

            logger.info(
                "Scoring stage started %s",
                format_fields(hunt_id=hunt_id, jobs_to_score=len(all_jobs)),
            )
            yield {
                "event": "scoring",
                "data": json.dumps({"message": f"Scoring {len(all_jobs)} jobs with AI..."}),
            }

            scored_jobs = score_jobs(
                all_jobs,
                profile,
                request.role,
                request.location,
                request.keywords,
                hunt_id=hunt_id,
            )

            unique_jobs = filter_duplicates(scored_jobs)
            logger.info(
                "Deduplication complete %s",
                format_fields(
                    hunt_id=hunt_id,
                    total_scraped=len(all_jobs),
                    total_after_dedup=len(unique_jobs),
                ),
            )

            hunt_result = HuntResult(
                hunt_id=hunt_id,
                role=request.role,
                location=request.location,
                total_scraped=len(all_jobs),
                total_after_dedup=len(unique_jobs),
                jobs=unique_jobs,
            )
            save_hunt(hunt_result)

            final_data = {
                "hunt_id": hunt_id,
                "total_scraped": len(all_jobs),
                "total_jobs": len(unique_jobs),
            }
            logger.info("Hunt completed %s", format_fields(**final_data))
            yield {
                "event": "hunt_complete",
                "data": json.dumps(final_data),
            }
        except Exception as exc:
            logger.exception(
                "Hunt stream failed %s",
                format_fields(hunt_id=hunt_id, error=str(exc)),
            )
            yield {
                "event": "hunt_error",
                "data": json.dumps({
                    "hunt_id": hunt_id,
                    "error": str(exc),
                }),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/jobs")
async def get_jobs(hunt_id: str):
    """Get jobs for a completed hunt."""
    jobs = get_jobs_for_hunt(hunt_id)
    hunt = get_hunt(hunt_id)

    if not hunt:
        logger.warning("Jobs requested for unknown hunt %s", format_fields(hunt_id=hunt_id))
        raise HTTPException(status_code=404, detail="Hunt not found")

    logger.info(
        "Returning jobs for hunt %s",
        format_fields(hunt_id=hunt_id, jobs_count=len(jobs)),
    )
    return {
        "hunt_id": hunt_id,
        "role": hunt.role,
        "location": hunt.location,
        "total_jobs": len(jobs),
        "jobs": [j.model_dump() for j in jobs],
    }


@app.post("/api/apply")
async def apply_to_job(job_id: str):
    """Stubbed auto-apply endpoint."""
    logger.info("Apply endpoint hit %s", format_fields(job_id=job_id))
    return {
        "status": "not_implemented",
        "message": "Auto-apply coming soon!",
        "job_id": job_id,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
