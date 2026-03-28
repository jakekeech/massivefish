# JobSwarm Scrape-first MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a parallel job scraping swarm using TinyFish agents across 6 platforms with GPT-4o-mini relevance scoring and a React dashboard.

**Architecture:** FastAPI backend orchestrates parallel TinyFish agents via `asyncio.gather`, streams progress via SSE, scores results with OpenAI, and serves a React+Vite frontend with real-time SwarmStatusBar and JobFeed.

**Tech Stack:** Python 3.11+, FastAPI, TinyFish SDK, OpenAI API, React 19, Vite 6, Tailwind CSS 4

---

## File Structure

```
jobswarm/
├── backend/
│   ├── main.py              # FastAPI app, CORS, routes, SSE endpoints
│   ├── models.py            # Pydantic models (Job, UserProfile, HuntRequest, etc.)
│   ├── state.py             # In-memory store (profiles, hunts, jobs)
│   ├── platforms.py         # URL builders for 6 job boards
│   ├── orchestrator.py      # Parallel TinyFish execution + polling
│   ├── scorer.py            # GPT-4o-mini relevance scoring + dedup
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── index.html           # HTML entry point
│   ├── package.json         # NPM dependencies
│   ├── vite.config.js       # Vite config with React plugin
│   ├── tailwind.config.js   # Tailwind v4 config (minimal)
│   └── src/
│       ├── main.jsx         # React entry point
│       ├── index.css        # Tailwind imports + custom styles
│       ├── App.jsx          # Main app with step routing
│       └── components/
│           ├── Header.jsx           # App header
│           ├── ProfileSetup.jsx     # Container for setup step
│           ├── ProfileForm.jsx      # User profile form
│           ├── SearchConfig.jsx     # Role/location/keywords inputs
│           ├── HuntButton.jsx       # Launch hunt CTA
│           ├── HuntDashboard.jsx    # Container for hunt step
│           ├── SwarmStatusBar.jsx   # 6 agent progress lanes
│           ├── StatsRow.jsx         # Summary stats
│           ├── JobFeed.jsx          # Scrollable job list
│           └── JobCard.jsx          # Individual job card
├── .env.example             # Environment template
└── README.md                # Setup instructions
```

---

## Task 1: Project Scaffold + Environment

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/models.py`
- Create: `backend/state.py`
- Create: `.env.example`

- [ ] **Step 1.1: Create backend directory and requirements.txt**

```bash
mkdir -p backend
```

Create `backend/requirements.txt`:
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
tinyfish>=0.2.4
openai>=1.0.0
sse-starlette>=2.0.0
pydantic>=2.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
```

- [ ] **Step 1.2: Create .env.example**

Create `.env.example`:
```
TINYFISH_API_KEY=sk-tinyfish-your-key-here
OPENAI_API_KEY=sk-your-key-here
```

- [ ] **Step 1.3: Create models.py with all Pydantic models**

Create `backend/models.py`:
```python
from pydantic import BaseModel
from enum import Enum
from typing import Optional
import uuid


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
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
```

- [ ] **Step 1.4: Create state.py for in-memory storage**

Create `backend/state.py`:
```python
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
```

- [ ] **Step 1.5: Install Python dependencies**

```bash
cd backend && pip install -r requirements.txt
```

- [ ] **Step 1.6: Verify models import correctly**

```bash
cd backend && python -c "from models import Job, Platform, UserProfile; print('Models OK')"
```

- [ ] **Step 1.7: Commit scaffold**

```bash
git add backend/ .env.example
git commit -m "feat: add backend scaffold with models and state"
```

---

## Task 2: Platform URL Builders

**Files:**
- Create: `backend/platforms.py`

- [ ] **Step 2.1: Create platforms.py with URL builders**

Create `backend/platforms.py`:
```python
from urllib.parse import quote
from models import Platform


UNIVERSAL_JOB_GOAL = """
Extract all job listings visible on this page. For each job, extract:
- job_title: string (the position title)
- company_name: string (the hiring company)
- location: string (where the job is located)
- posted_time: string (e.g. "2 hours ago", "Just posted")
- job_url: string (the full URL to apply or view the job posting)
- salary: string or null (compensation if shown)
- employment_type: string or null (Internship, Full-time, Part-time, Contract)

Dismiss any cookie banners, popups, or signup prompts that appear.
Scroll down 1-2 times to load more results if the page uses infinite scroll.
Stop after extracting 15-20 listings or reaching the end of results.
Return the results as a JSON array.
"""


def build_search_urls(role: str, location: str) -> list[dict]:
    """Build search URLs for all 6 job platforms."""
    role_encoded = quote(role)
    loc_encoded = quote(location)
    role_plus = role.replace(" ", "+")
    loc_plus = location.replace(" ", "+")

    return [
        {
            "platform": Platform.LINKEDIN,
            "url": f"https://www.linkedin.com/jobs/search/?keywords={role_encoded}&location={loc_encoded}&f_TPR=r3600&sortBy=DD",
        },
        {
            "platform": Platform.INDEED,
            "url": f"https://www.indeed.com/jobs?q={role_encoded}&l={loc_encoded}&fromage=1&sort=date",
        },
        {
            "platform": Platform.WELLFOUND,
            "url": f"https://wellfound.com/role/l/{role_encoded}/{loc_encoded}",
        },
        {
            "platform": Platform.YC_WAAS,
            "url": f"https://www.workatastartup.com/jobs?query={role_encoded}&location={loc_encoded}",
        },
        {
            "platform": Platform.GREENHOUSE,
            "url": f"https://www.google.com/search?q={role_plus}+{loc_plus}+site:boards.greenhouse.io&tbs=qdr:d",
        },
        {
            "platform": Platform.LEVER,
            "url": f"https://www.google.com/search?q={role_plus}+{loc_plus}+site:jobs.lever.co&tbs=qdr:d",
        },
    ]


def get_platform_display_name(platform: Platform) -> str:
    """Get human-readable name for platform."""
    names = {
        Platform.LINKEDIN: "LinkedIn",
        Platform.INDEED: "Indeed",
        Platform.WELLFOUND: "Wellfound",
        Platform.YC_WAAS: "YC Startups",
        Platform.GREENHOUSE: "Greenhouse",
        Platform.LEVER: "Lever",
    }
    return names.get(platform, platform.value)
```

- [ ] **Step 2.2: Verify platforms module**

```bash
cd backend && python -c "from platforms import build_search_urls, UNIVERSAL_JOB_GOAL; urls = build_search_urls('Software Engineer', 'San Francisco'); print(f'{len(urls)} platforms configured')"
```

Expected: `6 platforms configured`

- [ ] **Step 2.3: Commit**

```bash
git add backend/platforms.py
git commit -m "feat: add platform URL builders with universal scrape goal"
```

---

## Task 3: TinyFish Orchestrator

**Files:**
- Create: `backend/orchestrator.py`

- [ ] **Step 3.1: Create orchestrator.py with parallel execution**

Create `backend/orchestrator.py`:
```python
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
```

- [ ] **Step 3.2: Verify orchestrator imports**

```bash
cd backend && python -c "from orchestrator import orchestrate_hunt; print('Orchestrator OK')"
```

- [ ] **Step 3.3: Commit**

```bash
git add backend/orchestrator.py
git commit -m "feat: add TinyFish orchestrator with parallel execution"
```

---

## Task 4: GPT-4o-mini Scorer

**Files:**
- Create: `backend/scorer.py`

- [ ] **Step 4.1: Create scorer.py with relevance scoring**

Create `backend/scorer.py`:
```python
import json
import os
from openai import OpenAI
from models import Job, UserProfile


SCORER_SYSTEM_PROMPT = """You are a job matching engine. Given a candidate profile and job listings, score each listing's relevance from 0-100 and provide 1-3 short match reasons.

Also identify duplicates (same job at same company appearing from multiple sources). For duplicates, mark all but the one with the most information.

Respond ONLY with valid JSON in this exact format:
{
  "scored_jobs": [
    {
      "id": "string",
      "relevance_score": number,
      "match_reasons": ["string"],
      "is_duplicate": false
    }
  ]
}

Scoring guide:
- 90-100: Strong match on role type, experience level, tech stack, and location
- 70-89: Good match, missing 1 dimension
- 50-69: Partial match, related but not ideal
- 0-49: Weak or no match"""


def build_scorer_prompt(profile: UserProfile, role: str, location: str, keywords: list[str], jobs: list[Job]) -> str:
    """Build the user prompt for scoring."""
    jobs_json = json.dumps([{
        "id": j.id,
        "job_title": j.job_title,
        "company_name": j.company_name,
        "location": j.location,
        "source": j.source_platform.value,
        "salary": j.salary,
        "employment_type": j.employment_type,
    } for j in jobs], indent=2)

    return f"""CANDIDATE PROFILE:
Role sought: {role}
Location preference: {location}
Keywords: {', '.join(keywords) if keywords else 'None specified'}
Current title: {profile.current_title if profile else 'Not specified'}
Experience: {profile.years_of_experience if profile else 'Not specified'}
Education: {profile.education if profile else 'Not specified'}
Skills: {', '.join(profile.skills) if profile and profile.skills else 'Not specified'}

JOB LISTINGS TO SCORE ({len(jobs)} jobs):
{jobs_json}"""


def score_jobs(
    jobs: list[Job],
    profile: UserProfile | None,
    role: str,
    location: str,
    keywords: list[str],
) -> list[Job]:
    """Score and deduplicate jobs using GPT-4o-mini."""
    if not jobs:
        return []

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = build_scorer_prompt(profile, role, location, keywords, jobs)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SCORER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        scored_data = {item["id"]: item for item in result.get("scored_jobs", [])}

        # Apply scores to jobs
        for job in jobs:
            if job.id in scored_data:
                data = scored_data[job.id]
                job.relevance_score = data.get("relevance_score", 0)
                job.match_reasons = data.get("match_reasons", [])
                job.is_duplicate = data.get("is_duplicate", False)

        # Sort by relevance score descending
        jobs.sort(key=lambda j: j.relevance_score, reverse=True)

    except Exception as e:
        print(f"Scoring failed: {e}")
        # Return jobs unsorted with score 0 on failure

    return jobs


def filter_duplicates(jobs: list[Job]) -> list[Job]:
    """Remove duplicate jobs from the list."""
    return [j for j in jobs if not j.is_duplicate]
```

- [ ] **Step 4.2: Verify scorer imports**

```bash
cd backend && python -c "from scorer import score_jobs; print('Scorer OK')"
```

- [ ] **Step 4.3: Commit**

```bash
git add backend/scorer.py
git commit -m "feat: add GPT-4o-mini relevance scorer with deduplication"
```

---

## Task 5: FastAPI Main App with SSE

**Files:**
- Create: `backend/main.py`

- [ ] **Step 5.1: Create main.py with all routes**

Create `backend/main.py`:
```python
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
```

- [ ] **Step 5.2: Test the API starts**

```bash
cd backend && python -c "from main import app; print('FastAPI app OK')"
```

- [ ] **Step 5.3: Commit backend**

```bash
git add backend/main.py
git commit -m "feat: add FastAPI main app with SSE hunt endpoint"
```

---

## Task 6: Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/App.jsx`

- [ ] **Step 6.1: Create frontend directory and package.json**

```bash
mkdir -p frontend/src/components
```

Create `frontend/package.json`:
```json
{
  "name": "jobswarm-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0"
  }
}
```

- [ ] **Step 6.2: Create index.html**

Create `frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>JobSwarm - AI Job Hunt</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 6.3: Create vite.config.js**

Create `frontend/vite.config.js`:
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 6.4: Create tailwind.config.js (minimal for v4)**

Create `frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 6.5: Create src/index.css**

Create `frontend/src/index.css`:
```css
@import "tailwindcss";

:root {
  --bg-primary: #09090b;
  --bg-card: #18181b;
  --border-color: #27272a;
  --text-primary: #fafafa;
  --text-secondary: #a1a1aa;
  --accent-green: #22c55e;
  --accent-yellow: #eab308;
  --accent-blue: #3b82f6;
  --accent-purple: #a855f7;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Inter', system-ui, sans-serif;
}

/* Glow effect for CTAs */
.glow-green {
  box-shadow: 0 0 20px rgba(34, 197, 94, 0.3);
}

.glow-green:hover {
  box-shadow: 0 0 30px rgba(34, 197, 94, 0.5);
}

/* Pulsing animation for active agents */
@keyframes pulse-blue {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.pulse-active {
  animation: pulse-blue 1.5s ease-in-out infinite;
}
```

- [ ] **Step 6.6: Create src/main.jsx**

Create `frontend/src/main.jsx`:
```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 6.7: Create src/App.jsx (shell)**

Create `frontend/src/App.jsx`:
```jsx
import { useState } from 'react'
import Header from './components/Header'
import ProfileSetup from './components/ProfileSetup'
import HuntDashboard from './components/HuntDashboard'

export default function App() {
  const [step, setStep] = useState('setup') // 'setup' | 'hunting'
  const [huntId, setHuntId] = useState(null)
  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    email: '',
    current_title: '',
    education: '',
    skills: [],
  })
  const [searchConfig, setSearchConfig] = useState({
    role: '',
    location: '',
    keywords: [],
  })

  const handleStartHunt = (newHuntId) => {
    setHuntId(newHuntId)
    setStep('hunting')
  }

  const handleReset = () => {
    setStep('setup')
    setHuntId(null)
  }

  return (
    <div className="min-h-screen bg-[#09090b]">
      <Header onReset={step === 'hunting' ? handleReset : null} />
      <main className="max-w-6xl mx-auto px-4 py-8">
        {step === 'setup' && (
          <ProfileSetup
            profile={profile}
            setProfile={setProfile}
            searchConfig={searchConfig}
            setSearchConfig={setSearchConfig}
            onStartHunt={handleStartHunt}
          />
        )}
        {step === 'hunting' && (
          <HuntDashboard
            huntId={huntId}
            searchConfig={searchConfig}
          />
        )}
      </main>
    </div>
  )
}
```

- [ ] **Step 6.8: Install frontend dependencies**

```bash
cd frontend && npm install
```

- [ ] **Step 6.9: Commit frontend scaffold**

```bash
git add frontend/
git commit -m "feat: add frontend scaffold with Vite, React, Tailwind"
```

---

## Task 7: Frontend Components - Header & ProfileSetup

**Files:**
- Create: `frontend/src/components/Header.jsx`
- Create: `frontend/src/components/ProfileSetup.jsx`
- Create: `frontend/src/components/ProfileForm.jsx`
- Create: `frontend/src/components/SearchConfig.jsx`
- Create: `frontend/src/components/HuntButton.jsx`

- [ ] **Step 7.1: Create Header.jsx**

Create `frontend/src/components/Header.jsx`:
```jsx
import { Zap } from 'lucide-react'

export default function Header({ onReset }) {
  return (
    <header className="border-b border-[#27272a] bg-[#18181b]">
      <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-6 h-6 text-[#22c55e]" />
          <h1 className="text-xl font-bold font-mono">JobSwarm</h1>
        </div>
        {onReset && (
          <button
            onClick={onReset}
            className="text-sm text-[#a1a1aa] hover:text-white transition-colors"
          >
            New Hunt
          </button>
        )}
      </div>
    </header>
  )
}
```

- [ ] **Step 7.2: Create ProfileForm.jsx**

Create `frontend/src/components/ProfileForm.jsx`:
```jsx
export default function ProfileForm({ profile, setProfile }) {
  const handleChange = (field) => (e) => {
    setProfile({ ...profile, [field]: e.target.value })
  }

  return (
    <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-6">
      <h2 className="text-lg font-semibold mb-4">Your Profile</h2>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-[#a1a1aa] mb-1">First Name</label>
          <input
            type="text"
            value={profile.first_name}
            onChange={handleChange('first_name')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded px-3 py-2 text-white focus:border-[#22c55e] focus:outline-none"
            placeholder="John"
          />
        </div>
        <div>
          <label className="block text-sm text-[#a1a1aa] mb-1">Last Name</label>
          <input
            type="text"
            value={profile.last_name}
            onChange={handleChange('last_name')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded px-3 py-2 text-white focus:border-[#22c55e] focus:outline-none"
            placeholder="Doe"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-sm text-[#a1a1aa] mb-1">Email</label>
          <input
            type="email"
            value={profile.email}
            onChange={handleChange('email')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded px-3 py-2 text-white focus:border-[#22c55e] focus:outline-none"
            placeholder="john@example.com"
          />
        </div>
        <div>
          <label className="block text-sm text-[#a1a1aa] mb-1">Current Title</label>
          <input
            type="text"
            value={profile.current_title}
            onChange={handleChange('current_title')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded px-3 py-2 text-white focus:border-[#22c55e] focus:outline-none"
            placeholder="Software Engineer"
          />
        </div>
        <div>
          <label className="block text-sm text-[#a1a1aa] mb-1">Education</label>
          <input
            type="text"
            value={profile.education}
            onChange={handleChange('education')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded px-3 py-2 text-white focus:border-[#22c55e] focus:outline-none"
            placeholder="BS Computer Science, MIT"
          />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 7.3: Create SearchConfig.jsx**

Create `frontend/src/components/SearchConfig.jsx`:
```jsx
import { useState } from 'react'
import { X } from 'lucide-react'

export default function SearchConfig({ config, setConfig }) {
  const [keywordInput, setKeywordInput] = useState('')

  const handleChange = (field) => (e) => {
    setConfig({ ...config, [field]: e.target.value })
  }

  const addKeyword = () => {
    if (keywordInput.trim() && !config.keywords.includes(keywordInput.trim())) {
      setConfig({ ...config, keywords: [...config.keywords, keywordInput.trim()] })
      setKeywordInput('')
    }
  }

  const removeKeyword = (keyword) => {
    setConfig({ ...config, keywords: config.keywords.filter(k => k !== keyword) })
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addKeyword()
    }
  }

  return (
    <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-6">
      <h2 className="text-lg font-semibold mb-4">Job Search</h2>
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-[#a1a1aa] mb-1">Role / Title *</label>
          <input
            type="text"
            value={config.role}
            onChange={handleChange('role')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded px-3 py-2 text-white focus:border-[#22c55e] focus:outline-none"
            placeholder="Software Engineer Intern"
          />
        </div>
        <div>
          <label className="block text-sm text-[#a1a1aa] mb-1">Location *</label>
          <input
            type="text"
            value={config.location}
            onChange={handleChange('location')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded px-3 py-2 text-white focus:border-[#22c55e] focus:outline-none"
            placeholder="San Francisco, CA"
          />
        </div>
        <div>
          <label className="block text-sm text-[#a1a1aa] mb-1">Keywords (optional)</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex-1 bg-[#09090b] border border-[#27272a] rounded px-3 py-2 text-white focus:border-[#22c55e] focus:outline-none"
              placeholder="Python, AI, React..."
            />
            <button
              onClick={addKeyword}
              className="px-4 py-2 bg-[#27272a] rounded hover:bg-[#3f3f46] transition-colors"
            >
              Add
            </button>
          </div>
          {config.keywords.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {config.keywords.map(kw => (
                <span
                  key={kw}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-[#27272a] rounded text-sm"
                >
                  {kw}
                  <button onClick={() => removeKeyword(kw)} className="hover:text-red-400">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 7.4: Create HuntButton.jsx**

Create `frontend/src/components/HuntButton.jsx`:
```jsx
import { Zap } from 'lucide-react'

export default function HuntButton({ onClick, disabled, loading }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        w-full py-4 rounded-lg font-semibold text-lg
        flex items-center justify-center gap-2
        transition-all duration-200
        ${disabled || loading
          ? 'bg-[#27272a] text-[#71717a] cursor-not-allowed'
          : 'bg-[#22c55e] text-black hover:bg-[#16a34a] glow-green'
        }
      `}
    >
      {loading ? (
        <>
          <div className="w-5 h-5 border-2 border-black border-t-transparent rounded-full animate-spin" />
          Deploying Swarm...
        </>
      ) : (
        <>
          <Zap className="w-5 h-5" />
          Hunt Jobs
        </>
      )}
    </button>
  )
}
```

- [ ] **Step 7.5: Create ProfileSetup.jsx (container)**

Create `frontend/src/components/ProfileSetup.jsx`:
```jsx
import { useState } from 'react'
import ProfileForm from './ProfileForm'
import SearchConfig from './SearchConfig'
import HuntButton from './HuntButton'

export default function ProfileSetup({
  profile,
  setProfile,
  searchConfig,
  setSearchConfig,
  onStartHunt,
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const canHunt = searchConfig.role.trim() && searchConfig.location.trim()

  const handleHunt = async () => {
    if (!canHunt) return

    setLoading(true)
    setError(null)

    try {
      // Save profile first
      await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      })

      // Start hunt via SSE - we just trigger it here
      // The actual SSE handling happens in HuntDashboard
      onStartHunt('pending')
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold mb-2">Deploy Your Job Hunt Swarm</h1>
        <p className="text-[#a1a1aa]">
          6 AI agents will scrape job boards in parallel
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <ProfileForm profile={profile} setProfile={setProfile} />
        <SearchConfig config={searchConfig} setConfig={setSearchConfig} />
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      <HuntButton onClick={handleHunt} disabled={!canHunt} loading={loading} />
    </div>
  )
}
```

- [ ] **Step 7.6: Commit profile components**

```bash
git add frontend/src/components/
git commit -m "feat: add profile setup components"
```

---

## Task 8: Frontend Components - HuntDashboard

**Files:**
- Create: `frontend/src/components/HuntDashboard.jsx`
- Create: `frontend/src/components/SwarmStatusBar.jsx`
- Create: `frontend/src/components/StatsRow.jsx`
- Create: `frontend/src/components/JobFeed.jsx`
- Create: `frontend/src/components/JobCard.jsx`

- [ ] **Step 8.1: Create SwarmStatusBar.jsx**

Create `frontend/src/components/SwarmStatusBar.jsx`:
```jsx
import { Check, X, Loader2 } from 'lucide-react'

const PLATFORMS = [
  { id: 'linkedin', name: 'LinkedIn' },
  { id: 'indeed', name: 'Indeed' },
  { id: 'wellfound', name: 'Wellfound' },
  { id: 'yc_waas', name: 'YC Startups' },
  { id: 'greenhouse', name: 'Greenhouse' },
  { id: 'lever', name: 'Lever' },
]

export default function SwarmStatusBar({ statuses, totalJobs }) {
  return (
    <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold font-mono flex items-center gap-2">
          <span className="text-[#22c55e]">SWARM DEPLOYED</span>
        </h2>
        <span className="text-[#a1a1aa] font-mono">
          {totalJobs} jobs found
        </span>
      </div>

      <div className="space-y-3">
        {PLATFORMS.map(platform => {
          const status = statuses[platform.id] || { status: 'queued', jobs: 0 }
          return (
            <div key={platform.id} className="flex items-center gap-4">
              <span className="w-24 text-sm text-[#a1a1aa]">{platform.name}</span>
              <div className="flex-1 h-2 bg-[#27272a] rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    status.status === 'completed' ? 'bg-[#22c55e]' :
                    status.status === 'failed' ? 'bg-red-500' :
                    status.status === 'running' ? 'bg-[#3b82f6] pulse-active' :
                    'bg-[#3f3f46]'
                  }`}
                  style={{
                    width: status.status === 'completed' ? '100%' :
                           status.status === 'failed' ? '100%' :
                           status.status === 'running' ? '60%' :
                           '20%'
                  }}
                />
              </div>
              <div className="w-20 text-right text-sm font-mono">
                {status.status === 'completed' && (
                  <span className="text-[#22c55e] flex items-center justify-end gap-1">
                    <Check className="w-4 h-4" />
                    {status.jobs}
                  </span>
                )}
                {status.status === 'failed' && (
                  <span className="text-red-400 flex items-center justify-end gap-1">
                    <X className="w-4 h-4" />
                    failed
                  </span>
                )}
                {status.status === 'running' && (
                  <span className="text-[#3b82f6] flex items-center justify-end gap-1">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </span>
                )}
                {status.status === 'queued' && (
                  <span className="text-[#71717a]">queued</span>
                )}
              </div>
              <span className="w-16 text-right text-xs text-[#71717a] font-mono">
                {status.elapsed ? `${status.elapsed}s` : '—'}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 8.2: Create StatsRow.jsx**

Create `frontend/src/components/StatsRow.jsx`:
```jsx
export default function StatsRow({ totalScraped, totalAfterDedup, avgScore }) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-4 text-center">
        <div className="text-2xl font-bold font-mono text-[#22c55e]">
          {totalScraped}
        </div>
        <div className="text-sm text-[#a1a1aa]">Total Scraped</div>
      </div>
      <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-4 text-center">
        <div className="text-2xl font-bold font-mono text-white">
          {totalAfterDedup}
        </div>
        <div className="text-sm text-[#a1a1aa]">After Dedup</div>
      </div>
      <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-4 text-center">
        <div className="text-2xl font-bold font-mono text-[#eab308]">
          {avgScore}%
        </div>
        <div className="text-sm text-[#a1a1aa]">Avg Match</div>
      </div>
    </div>
  )
}
```

- [ ] **Step 8.3: Create JobCard.jsx**

Create `frontend/src/components/JobCard.jsx`:
```jsx
import { ExternalLink, MapPin, Clock, DollarSign } from 'lucide-react'

function getScoreColor(score) {
  if (score >= 90) return 'text-[#22c55e] bg-[#22c55e]/10'
  if (score >= 70) return 'text-[#eab308] bg-[#eab308]/10'
  return 'text-[#71717a] bg-[#71717a]/10'
}

function getPlatformLabel(platform) {
  const labels = {
    linkedin: 'LinkedIn',
    indeed: 'Indeed',
    wellfound: 'Wellfound',
    yc_waas: 'YC',
    greenhouse: 'Greenhouse',
    lever: 'Lever',
  }
  return labels[platform] || platform
}

export default function JobCard({ job }) {
  return (
    <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-5 hover:border-[#3f3f46] transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-lg truncate">{job.job_title}</h3>
          <p className="text-[#a1a1aa] flex items-center gap-2 mt-1">
            <span className="font-medium text-white">{job.company_name}</span>
            {job.location && (
              <>
                <span>·</span>
                <span className="flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  {job.location}
                </span>
              </>
            )}
            {job.posted_time && (
              <>
                <span>·</span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {job.posted_time}
                </span>
              </>
            )}
          </p>
        </div>
        <div className={`px-3 py-1 rounded-full font-mono text-sm font-semibold ${getScoreColor(job.relevance_score)}`}>
          {job.relevance_score}%
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <span className="text-xs px-2 py-0.5 rounded bg-[#27272a] text-[#a1a1aa]">
          via {getPlatformLabel(job.source_platform)}
        </span>
        {job.employment_type && (
          <span className="text-xs px-2 py-0.5 rounded bg-[#27272a] text-[#a1a1aa]">
            {job.employment_type}
          </span>
        )}
        {job.salary && (
          <span className="text-xs px-2 py-0.5 rounded bg-[#22c55e]/10 text-[#22c55e] flex items-center gap-1">
            <DollarSign className="w-3 h-3" />
            {job.salary}
          </span>
        )}
      </div>

      {job.match_reasons && job.match_reasons.length > 0 && (
        <p className="mt-3 text-sm text-[#a1a1aa]">
          <span className="text-[#22c55e]">Match:</span> {job.match_reasons.join(' · ')}
        </p>
      )}

      <div className="mt-4 flex gap-3">
        <button
          disabled
          className="flex-1 py-2 rounded bg-[#27272a] text-[#71717a] cursor-not-allowed text-sm"
          title="Coming Soon"
        >
          Apply For Me (Soon)
        </button>
        <a
          href={job.job_url}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 rounded bg-[#27272a] hover:bg-[#3f3f46] transition-colors flex items-center gap-2 text-sm"
        >
          View <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </div>
  )
}
```

- [ ] **Step 8.4: Create JobFeed.jsx**

Create `frontend/src/components/JobFeed.jsx`:
```jsx
import JobCard from './JobCard'

export default function JobFeed({ jobs, loading }) {
  if (loading) {
    return (
      <div className="text-center py-12 text-[#a1a1aa]">
        <div className="w-8 h-8 border-2 border-[#22c55e] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        Scoring jobs with AI...
      </div>
    )
  }

  if (!jobs || jobs.length === 0) {
    return (
      <div className="text-center py-12 text-[#a1a1aa]">
        No jobs found yet. The swarm is still hunting...
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {jobs.map(job => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  )
}
```

- [ ] **Step 8.5: Create HuntDashboard.jsx (container with SSE)**

Create `frontend/src/components/HuntDashboard.jsx`:
```jsx
import { useState, useEffect, useRef } from 'react'
import SwarmStatusBar from './SwarmStatusBar'
import StatsRow from './StatsRow'
import JobFeed from './JobFeed'

export default function HuntDashboard({ huntId, searchConfig }) {
  const [statuses, setStatuses] = useState({})
  const [jobs, setJobs] = useState([])
  const [totalScraped, setTotalScraped] = useState(0)
  const [scoring, setScoring] = useState(false)
  const [complete, setComplete] = useState(false)
  const [error, setError] = useState(null)
  const startedRef = useRef(false)

  useEffect(() => {
    if (huntId === 'pending' && !startedRef.current) {
      startedRef.current = true
      startHunt()
    }
  }, [huntId])

  const startHunt = async () => {
    try {
      // Use fetch with streaming response for SSE
      const response = await fetch('/api/hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: searchConfig.role,
          location: searchConfig.location,
          keywords: searchConfig.keywords,
        }),
      })

      if (!response.ok) {
        throw new Error(`Hunt failed: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim())
              handleEvent(data)
            } catch (e) {
              // Skip malformed JSON
            }
          }
        }
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const handleEvent = (data) => {
    // Determine event type from data content
    if (data.platform && data.status === 'queued') {
      setStatuses(prev => ({
        ...prev,
        [data.platform]: { status: 'queued', jobs: 0 }
      }))
    } else if (data.platform && data.jobs_found !== undefined) {
      setStatuses(prev => ({
        ...prev,
        [data.platform]: {
          status: 'completed',
          jobs: data.jobs_found,
          elapsed: data.elapsed
        }
      }))
    } else if (data.platform && data.error) {
      setStatuses(prev => ({
        ...prev,
        [data.platform]: {
          status: 'failed',
          jobs: 0,
          elapsed: data.elapsed,
          error: data.error
        }
      }))
    } else if (data.message && data.message.includes('Scoring')) {
      setScoring(true)
    } else if (data.hunt_id) {
      // Hunt complete
      setScoring(false)
      setComplete(true)
      setTotalScraped(data.total_scraped || 0)
      fetchJobs(data.hunt_id)
    }
  }

  const fetchJobs = async (id) => {
    try {
      const res = await fetch(`/api/jobs?hunt_id=${id}`)
      const data = await res.json()
      setJobs(data.jobs || [])
    } catch (err) {
      setError('Failed to fetch jobs')
    }
  }

  const totalJobs = Object.values(statuses).reduce((sum, s) => sum + (s.jobs || 0), 0)
  const avgScore = jobs.length > 0
    ? Math.round(jobs.reduce((sum, j) => sum + j.relevance_score, 0) / jobs.length)
    : 0

  return (
    <div className="space-y-6">
      <div className="text-center mb-4">
        <h1 className="text-2xl font-bold">
          Hunting: <span className="text-[#22c55e]">{searchConfig.role}</span>
        </h1>
        <p className="text-[#a1a1aa]">{searchConfig.location}</p>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      <SwarmStatusBar statuses={statuses} totalJobs={totalJobs} />

      {complete && (
        <StatsRow
          totalScraped={totalScraped}
          totalAfterDedup={jobs.length}
          avgScore={avgScore}
        />
      )}

      <JobFeed jobs={jobs} loading={scoring} />
    </div>
  )
}
```

- [ ] **Step 8.6: Commit dashboard components**

```bash
git add frontend/src/components/
git commit -m "feat: add hunt dashboard components with SSE"
```

---

## Task 9: Integration & Testing

**Files:**
- Modify: All files as needed for integration

- [ ] **Step 9.1: Create README.md with setup instructions**

Create `README.md`:
```markdown
# JobSwarm

Deploy a swarm of AI agents to scrape job postings from 6 major job boards in parallel, then get AI-powered relevance scoring.

Built for the TinyFish $2M Pre-Accelerator Hackathon.

## Quick Start

### 1. Environment Setup

```bash
cp .env.example .env
# Edit .env with your API keys:
# - TINYFISH_API_KEY from https://agent.tinyfish.ai/api-keys
# - OPENAI_API_KEY from https://platform.openai.com
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Backend runs on http://localhost:8000

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5173

## Features

- Parallel scraping across LinkedIn, Indeed, Wellfound, YC Work at a Startup, Greenhouse, and Lever
- Real-time progress streaming via SSE
- AI relevance scoring with GPT-4o-mini
- Automatic deduplication across platforms
- Dark hacker aesthetic UI

## Architecture

- **Backend:** FastAPI + TinyFish SDK + OpenAI API
- **Frontend:** React 19 + Vite + Tailwind CSS v4
- **State:** In-memory (no database)
```

- [ ] **Step 9.2: Test backend runs**

```bash
cd backend && timeout 5 python main.py || echo "Server started OK"
```

- [ ] **Step 9.3: Test frontend builds**

```bash
cd frontend && npm run build
```

- [ ] **Step 9.4: Final commit**

```bash
git add .
git commit -m "feat: complete JobSwarm scrape MVP"
```

---

## Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | Project scaffold + models | 10 min |
| 2 | Platform URL builders | 5 min |
| 3 | TinyFish orchestrator | 15 min |
| 4 | GPT-4o-mini scorer | 10 min |
| 5 | FastAPI main app | 15 min |
| 6 | Frontend scaffold | 15 min |
| 7 | Profile setup components | 20 min |
| 8 | Hunt dashboard components | 30 min |
| 9 | Integration & testing | 15 min |
| **Total** | | **~135 min** |
