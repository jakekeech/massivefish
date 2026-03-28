import asyncio
import json
import uuid
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from models import UserProfile, HuntRequest, HuntResult, Job
from state import set_profile, get_profile, save_hunt, get_hunt, get_jobs_for_hunt
from orchestrator import orchestrate_hunt
from scorer import score_jobs, filter_duplicates


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("JobSwarm API starting...")
    yield
    # Shutdown
    print("JobSwarm API shutting down...")


app = FastAPI(
    title="JobSwarm API",
    description="Parallel job scraping swarm powered by TinyFish",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "JobSwarm API"}


@app.post("/api/profile")
async def save_profile(profile: UserProfile):
    """Save user profile to memory."""
    set_profile(profile)
    return {"status": "saved", "name": f"{profile.first_name} {profile.last_name}"}


@app.get("/api/profile")
async def get_current_profile():
    """Get current user profile."""
    profile = get_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile set")
    return profile


@app.post("/api/hunt")
async def start_hunt(request: HuntRequest):
    """
    Start a parallel job hunt across all platforms.
    Returns an SSE stream with progress updates.
    """
    hunt_id = str(uuid.uuid4())[:8]
    profile = get_profile()

    async def event_generator():
        all_jobs: list[Job] = []

        # Stream orchestrator events
        async for event in orchestrate_hunt(request.role, request.location):
            if event["event"] == "scraping_complete":
                # Collect all jobs
                for job_data in event["data"]["jobs"]:
                    all_jobs.append(Job(**job_data))
            else:
                # Forward progress events
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"])
                }

        # Score jobs
        yield {
            "event": "scoring",
            "data": json.dumps({"message": f"Scoring {len(all_jobs)} jobs with AI..."})
        }

        scored_jobs = score_jobs(
            all_jobs,
            profile,
            request.role,
            request.location,
            request.keywords,
        )

        # Filter duplicates
        unique_jobs = filter_duplicates(scored_jobs)

        # Save hunt result
        hunt_result = HuntResult(
            hunt_id=hunt_id,
            role=request.role,
            location=request.location,
            total_scraped=len(all_jobs),
            total_after_dedup=len(unique_jobs),
            jobs=unique_jobs,
        )
        save_hunt(hunt_result)

        # Final event
        yield {
            "event": "hunt_complete",
            "data": json.dumps({
                "hunt_id": hunt_id,
                "total_scraped": len(all_jobs),
                "total_jobs": len(unique_jobs),
            })
        }

    return EventSourceResponse(event_generator())


@app.get("/api/jobs")
async def get_jobs(hunt_id: str):
    """Get jobs for a completed hunt."""
    jobs = get_jobs_for_hunt(hunt_id)
    hunt = get_hunt(hunt_id)

    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")

    return {
        "hunt_id": hunt_id,
        "role": hunt.role,
        "location": hunt.location,
        "total_jobs": len(jobs),
        "jobs": [j.model_dump() for j in jobs]
    }


@app.post("/api/apply")
async def apply_to_job(job_id: str):
    """Stubbed auto-apply endpoint."""
    return {
        "status": "not_implemented",
        "message": "Auto-apply coming soon!",
        "job_id": job_id
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
