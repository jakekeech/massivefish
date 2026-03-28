import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from apply_orchestrator import orchestrate_application
from logging_utils import configure_logging, format_fields, get_logger
from models import ApplyRequest, HuntRequest, HuntResult, Job, UserProfile
from orchestrator import orchestrate_hunt
from resume_parser import extract_text_from_pdf, parse_resume_with_ai
from scorer import filter_duplicates, score_jobs
from state import get_hunt, get_job, get_jobs_for_hunt, get_profile, save_hunt, set_profile


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
            format_fields(
                method=request.method, path=request.url.path, elapsed_ms=elapsed_ms
            ),
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


@app.post("/api/resume/parse")
async def parse_resume(file: UploadFile):
    """
    Parse a PDF resume and extract structured profile data using AI.
    Validates file type and size before processing.
    """
    logger.info(
        "Resume parse requested %s",
        format_fields(
            filename=file.filename,
            content_type=file.content_type,
        ),
    )

    # Validate file type
    if file.content_type != "application/pdf":
        logger.warning(
            "Invalid file type uploaded %s",
            format_fields(filename=file.filename, content_type=file.content_type),
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Expected PDF, got {file.content_type}",
        )

    # Read file content
    file_bytes = await file.read()
    file_size_mb = len(file_bytes) / (1024 * 1024)

    # Validate file size (10MB max)
    if file_size_mb > 10:
        logger.warning(
            "File too large %s",
            format_fields(filename=file.filename, size_mb=round(file_size_mb, 2)),
        )
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is 10MB, got {file_size_mb:.2f}MB",
        )

    logger.info(
        "File validation passed %s",
        format_fields(filename=file.filename, size_mb=round(file_size_mb, 2)),
    )

    try:
        # Extract text from PDF
        resume_text = extract_text_from_pdf(file_bytes)

        if not resume_text.strip():
            logger.warning(
                "No text extracted from PDF %s", format_fields(filename=file.filename)
            )
            raise HTTPException(
                status_code=422,
                detail="Could not extract text from PDF. The file may be empty or corrupted.",
            )

        # Parse with AI
        profile = parse_resume_with_ai(resume_text)

        logger.info(
            "Resume parsed successfully %s",
            format_fields(
                filename=file.filename,
                first_name=profile.first_name,
                last_name=profile.last_name,
                email=profile.email,
            ),
        )

        return profile

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Resume parsing failed %s",
            format_fields(filename=file.filename, error=str(exc)),
        )
        # Check if it's an OpenAI error
        if "openai" in str(exc).lower() or "api" in str(exc).lower():
            raise HTTPException(
                status_code=503,
                detail=f"AI service unavailable: {str(exc)}",
            )
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse resume: {str(exc)}",
        )


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
                    format_fields(
                        hunt_id=hunt_id, event=event["event"], data=event["data"]
                    ),
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
                "data": json.dumps(
                    {"message": f"Scoring {len(all_jobs)} jobs with AI..."}
                ),
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
                "data": json.dumps(
                    {
                        "hunt_id": hunt_id,
                        "error": str(exc),
                    }
                ),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/jobs")
async def get_jobs(hunt_id: str):
    """Get jobs for a completed hunt."""
    jobs = get_jobs_for_hunt(hunt_id)
    hunt = get_hunt(hunt_id)

    if not hunt:
        logger.warning(
            "Jobs requested for unknown hunt %s", format_fields(hunt_id=hunt_id)
        )
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
async def apply_to_job(request: ApplyRequest):
    """Start a guided application copilot stream for a job."""
    application_id = str(uuid.uuid4())[:8]
    profile = get_profile()
    job = get_job(request.job_id)

    logger.info(
        "Application requested %s",
        format_fields(
            application_id=application_id,
            job_id=request.job_id,
            profile_present=profile is not None,
            job_found=job is not None,
        ),
    )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not profile:
        raise HTTPException(status_code=400, detail="Profile must be saved before applying")

    async def event_generator():
        try:
            async for event in orchestrate_application(job, profile, application_id):
                logger.info(
                    "Streaming application SSE event %s",
                    format_fields(
                        application_id=application_id,
                        job_id=job.id,
                        event=event["event"],
                        data=event["data"],
                    ),
                )
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"]),
                }
        except Exception as exc:
            logger.exception(
                "Application stream failed %s",
                format_fields(application_id=application_id, job_id=job.id, error=str(exc)),
            )
            yield {
                "event": "apply_error",
                "data": json.dumps({
                    "application_id": application_id,
                    "job_id": job.id,
                    "error": str(exc),
                }),
            }

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
