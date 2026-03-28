from pydantic import BaseModel
from enum import Enum
from typing import Optional
import uuid


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    CUSTOM = "custom"
    WELLFOUND = "wellfound"
    YC_WAAS = "yc_waas"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"


class AgentStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    id: str
    job_title: str
    company_name: str
    location: str = ""
    source_platform: Platform
    job_url: str
    posted_time: str = ""
    salary: Optional[str] = None
    employment_type: Optional[str] = None
    relevance_score: int = 0
    match_reasons: list[str] = []
    is_duplicate: bool = False

    @classmethod
    def create(cls, platform: Platform, **kwargs):
        return cls(id=str(uuid.uuid4())[:8], source_platform=platform, **kwargs)


class UserProfile(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    current_title: str = ""
    years_of_experience: str = ""
    education: str = ""
    skills: list[str] = []


class HuntRequest(BaseModel):
    role: str
    location: str
    keywords: list[str] = []
    target_urls: list[str] = []


class HuntResult(BaseModel):
    hunt_id: str
    role: str
    location: str
    total_scraped: int
    total_after_dedup: int
    jobs: list[Job]


class PlatformStatus(BaseModel):
    platform: Platform
    status: AgentStatus
    run_id: Optional[str] = None
    jobs_found: int = 0
    error: Optional[str] = None
    elapsed_seconds: float = 0
