from models import UserProfile, Job, HuntResult
from typing import Optional

# In-memory state
_profile: Optional[UserProfile] = None
_hunts: dict[str, HuntResult] = {}
_jobs: dict[str, Job] = {}


def set_profile(profile: UserProfile) -> None:
    global _profile
    _profile = profile


def get_profile() -> Optional[UserProfile]:
    return _profile


def save_hunt(hunt: HuntResult) -> None:
    _hunts[hunt.hunt_id] = hunt
    for job in hunt.jobs:
        _jobs[job.id] = job


def get_hunt(hunt_id: str) -> Optional[HuntResult]:
    return _hunts.get(hunt_id)


def get_jobs_for_hunt(hunt_id: str) -> list[Job]:
    hunt = _hunts.get(hunt_id)
    if not hunt:
        return []
    return [j for j in hunt.jobs if not j.is_duplicate]
