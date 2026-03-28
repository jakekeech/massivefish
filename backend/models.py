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


class ResumeMetadata(BaseModel):
    id: str
    filename: str
    content_type: str = "application/pdf"
    size_bytes: int
    uploaded_at: str
    download_url: str = ""


class StoredResume(BaseModel):
    id: str
    filename: str
    content_type: str = "application/pdf"
    size_bytes: int
    uploaded_at: str
    storage_path: str
    extracted_text: str = ""

    def to_public(self, download_url: str = "") -> ResumeMetadata:
        return ResumeMetadata(
            id=self.id,
            filename=self.filename,
            content_type=self.content_type,
            size_bytes=self.size_bytes,
            uploaded_at=self.uploaded_at,
            download_url=download_url,
        )


class HuntRequest(BaseModel):
    role: str
    location: str
    keywords: list[str] = []
    target_urls: list[str] = []


class ApplyRequest(BaseModel):
    job_id: str


class ResumeParseResponse(BaseModel):
    profile: UserProfile
    resume: ResumeMetadata


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
