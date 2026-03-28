from typing import Optional

from logging_utils import format_fields, get_logger
from models import HuntResult, Job, StoredResume, UserProfile


logger = get_logger("jobswarm.state")

# In-memory state
_profile: Optional[UserProfile] = None
_resume: Optional[StoredResume] = None
_hunts: dict[str, HuntResult] = {}
_jobs: dict[str, Job] = {}


def set_profile(profile: UserProfile) -> None:
    global _profile
    _profile = profile
    logger.info(
        "In-memory profile updated %s",
        format_fields(email=profile.email, skills_count=len(profile.skills)),
    )


def get_profile() -> Optional[UserProfile]:
    logger.info("In-memory profile requested %s", format_fields(profile_present=_profile is not None))
    return _profile


def set_resume(resume: StoredResume) -> None:
    global _resume
    _resume = resume
    logger.info(
        "In-memory resume updated %s",
        format_fields(
            resume_id=resume.id,
            filename=resume.filename,
            size_bytes=resume.size_bytes,
        ),
    )


def get_resume() -> Optional[StoredResume]:
    logger.info("In-memory resume requested %s", format_fields(resume_present=_resume is not None))
    return _resume


def save_hunt(hunt: HuntResult) -> None:
    _hunts[hunt.hunt_id] = hunt
    for job in hunt.jobs:
        _jobs[job.id] = job

    logger.info(
        "Hunt stored in memory %s",
        format_fields(hunt_id=hunt.hunt_id, jobs_count=len(hunt.jobs)),
    )


def get_hunt(hunt_id: str) -> Optional[HuntResult]:
    hunt = _hunts.get(hunt_id)
    logger.info(
        "Hunt lookup performed %s",
        format_fields(hunt_id=hunt_id, found=hunt is not None),
    )
    return hunt


def get_jobs_for_hunt(hunt_id: str) -> list[Job]:
    hunt = _hunts.get(hunt_id)
    if not hunt:
        logger.warning("Jobs requested for missing hunt %s", format_fields(hunt_id=hunt_id))
        return []

    jobs = [job for job in hunt.jobs if not job.is_duplicate]
    logger.info(
        "Returning in-memory jobs %s",
        format_fields(hunt_id=hunt_id, jobs_count=len(jobs)),
    )
    return jobs


def get_job(job_id: str) -> Optional[Job]:
    job = _jobs.get(job_id)
    logger.info(
        "Job lookup performed %s",
        format_fields(job_id=job_id, found=job is not None),
    )
    return job
