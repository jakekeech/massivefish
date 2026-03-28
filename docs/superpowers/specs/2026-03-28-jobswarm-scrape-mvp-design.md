# JobSwarm Scrape-first MVP — Design Spec

**Date:** 2026-03-28
**Deadline:** 2026-03-29 (TinyFish Hackathon)
**Scope:** Parallel job scraping swarm + polished UI. Auto-apply stubbed.

---

## Overview

JobSwarm deploys parallel TinyFish web agents across 6 job boards to scrape postings matching user criteria. Results are deduplicated, scored for relevance via GPT-4o-mini, and displayed in a unified feed.

### In Scope
- Backend: FastAPI with parallel TinyFish agents (6 platforms)
- General-purpose scraping goal (works on any job board)
- Relevance scoring + deduplication via OpenAI GPT-4o-mini
- SSE streaming of scrape progress to frontend
- Frontend: Profile setup → Hunt dashboard with SwarmStatusBar + JobFeed
- Dark hacker aesthetic, green accent CTAs

### Stubbed
- Auto-apply: Button shows "Coming Soon"
- Resume upload: UI exists, stored in memory, unused

### Out of Scope
- Database persistence
- User authentication
- Actual form-filling agents

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      FRONTEND (React + Vite)                 │
│  ┌────────────────┐  ┌───────────────┐  ┌────────────────┐   │
│  │ ProfileSetup   │  │ HuntDashboard │  │ JobFeed        │   │
│  │ (form + config)│  │ (SwarmStatus) │  │ (scored jobs)  │   │
│  └────────────────┘  └───────────────┘  └────────────────┘   │
└───────────────────────────┬──────────────────────────────────┘
                            │ SSE (EventSource)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                          │
│  POST /api/profile     POST /api/hunt (SSE)    GET /api/jobs │
│       │                      │                      │        │
│       ▼                      ▼                      ▼        │
│  ┌─────────┐    ┌────────────────────────┐    ┌──────────┐   │
│  │ state.py│    │ orchestrator.py        │    │ state.py │   │
│  │ (memory)│    │ - 6 parallel TinyFish  │    │ (read)   │   │
│  └─────────┘    │ - asyncio.gather       │    └──────────┘   │
│                 └───────────┬────────────┘                   │
│                             │                                │
│                 ┌───────────▼────────────┐                   │
│                 │ scorer.py              │                   │
│                 │ - OpenAI GPT-4o-mini   │                   │
│                 │ - Dedup + relevance    │                   │
│                 └────────────────────────┘                   │
└──────────────────────────────────────────────────────────────┘
```

---

## TinyFish Integration

### Universal Job Extraction Goal

One goal works across all platforms:

```python
UNIVERSAL_JOB_GOAL = """
Extract all job listings visible on this page. For each job, extract:
- job_title: string
- company_name: string
- location: string
- posted_time: string (e.g. "2 hours ago", "Just posted")
- job_url: string (full URL to the job posting)
- salary: string or null
- employment_type: string or null (Internship, Full-time, etc.)

Dismiss any cookie banners, popups, or signup prompts.
Scroll down 1-2 times to load more results.
Stop after 15-20 listings or end of results.
Return as JSON array.
"""
```

### Platform URL Builder

Only platform-aware code — simple string formatting:

```python
def build_search_urls(role: str, location: str) -> list[dict]:
    role_encoded = quote(role)
    loc_encoded = quote(location)

    return [
        {"platform": "linkedin", "url": f"https://www.linkedin.com/jobs/search/?keywords={role_encoded}&location={loc_encoded}&f_TPR=r3600"},
        {"platform": "indeed", "url": f"https://www.indeed.com/jobs?q={role_encoded}&l={loc_encoded}&fromage=1&sort=date"},
        {"platform": "wellfound", "url": f"https://wellfound.com/jobs?role={role_encoded}&location={loc_encoded}"},
        {"platform": "yc_waas", "url": f"https://www.workatastartup.com/jobs?query={role_encoded}&location={loc_encoded}"},
        {"platform": "greenhouse", "url": f"https://www.google.com/search?q={role_encoded}+{loc_encoded}+site:boards.greenhouse.io&tbs=qdr:d"},
        {"platform": "lever", "url": f"https://www.google.com/search?q={role_encoded}+{loc_encoded}+site:jobs.lever.co&tbs=qdr:d"},
    ]
```

### Parallel Execution Pattern

```python
async def scrape_all(role: str, location: str) -> list[Job]:
    client = AsyncTinyFish()
    targets = build_search_urls(role, location)

    # Fire all agents in parallel using queue()
    tasks = [client.agent.queue(url=t["url"], goal=UNIVERSAL_JOB_GOAL) for t in targets]
    runs = await asyncio.gather(*tasks)

    # Poll until complete, yield SSE events
    results = await poll_all_runs(client, runs, targets)
    return results
```

---

## Data Models

```python
from pydantic import BaseModel
from enum import Enum

class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    WELLFOUND = "wellfound"
    YC_WAAS = "yc_waas"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"

class Job(BaseModel):
    id: str
    job_title: str
    company_name: str
    location: str = ""
    source_platform: Platform
    job_url: str
    posted_time: str = ""
    salary: str | None = None
    employment_type: str | None = None
    relevance_score: int = 0
    match_reasons: list[str] = []
    is_duplicate: bool = False

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
```

---

## API Endpoints

### POST /api/profile
Store user profile in memory.

**Request:**
```json
{
  "first_name": "Zheng Feng",
  "last_name": "Kwok",
  "email": "zhengfeng@example.com",
  "current_title": "CS Student",
  "education": "NUS, Computer Science, 2027"
}
```

### POST /api/hunt
Launch parallel scrape. Returns SSE stream.

**Request:**
```json
{
  "role": "Software Engineer Intern",
  "location": "San Francisco",
  "keywords": ["AI", "Python"]
}
```

**SSE Events:**
```
event: agent_started
data: {"platform": "linkedin", "run_id": "run_abc123"}

event: agent_progress
data: {"platform": "linkedin", "message": "Navigating to search results..."}

event: agent_complete
data: {"platform": "linkedin", "jobs_found": 12}

event: agent_failed
data: {"platform": "indeed", "error": "Blocked by CAPTCHA"}

event: scoring
data: {"message": "Scoring 47 jobs with GPT-4o-mini..."}

event: hunt_complete
data: {"hunt_id": "hunt_xyz", "total_jobs": 38, "platforms_completed": 5}
```

### GET /api/jobs?hunt_id={id}
Fetch scored and deduplicated jobs.

**Response:**
```json
{
  "hunt_id": "hunt_xyz",
  "jobs": [
    {
      "id": "j1",
      "job_title": "AI Engineer Intern",
      "company_name": "Anthropic",
      "location": "San Francisco, CA",
      "source_platform": "linkedin",
      "job_url": "https://...",
      "posted_time": "34 minutes ago",
      "salary": "$60/hr",
      "relevance_score": 95,
      "match_reasons": ["AI focus", "Internship", "SF location"]
    }
  ]
}
```

### POST /api/apply (Stubbed)
Returns coming soon message.

**Response:**
```json
{
  "status": "not_implemented",
  "message": "Auto-apply coming soon!"
}
```

---

## GPT-4o-mini Scoring

### System Prompt
```
You are a job matching engine. Given a candidate profile and job listings, score each listing's relevance from 0-100 and provide 1-3 match reasons.

Identify duplicates (same job at same company from multiple boards). Keep the one with most info.

Respond ONLY with valid JSON:
{
  "scored_jobs": [
    {
      "id": "string",
      "relevance_score": number,
      "match_reasons": ["string"],
      "is_duplicate_of": "string or null"
    }
  ]
}

Scoring guide:
- 90-100: Strong match on role, experience, tech stack, location
- 70-89: Good match, 1 dimension off
- 50-69: Partial match
- 0-49: Weak match
```

### User Prompt Template
```
CANDIDATE PROFILE:
Role sought: {role}
Location preference: {location}
Keywords: {keywords}
Experience: {years_of_experience}
Education: {education}

JOB LISTINGS TO SCORE:
{jobs_json}
```

---

## Frontend Components

### Component Tree
```
<App>
  <Header />
  {step === "setup" && <ProfileSetup />}
  {step === "hunting" && <HuntDashboard />}
</App>

<ProfileSetup>
  <ProfileForm />
  <SearchConfig />
  <HuntButton />
</ProfileSetup>

<HuntDashboard>
  <SwarmStatusBar />
  <StatsRow />
  <JobFeed>
    <JobCard />
  </JobFeed>
</HuntDashboard>
```

### Design System

| Element | Value |
|---------|-------|
| Background | `#09090b` (zinc-950) |
| Cards | `#18181b` with `#27272a` border |
| Primary CTA | `#22c55e` (green-500) with glow |
| High relevance (90+) | `#22c55e` green |
| Medium relevance (70-89) | `#eab308` yellow |
| Low relevance (<70) | `#71717a` gray |
| Active agent | pulsing `#3b82f6` blue |
| Text primary | `#fafafa` |
| Text secondary | `#a1a1aa` |
| Font (stats) | JetBrains Mono |
| Font (body) | Inter |

### SwarmStatusBar
Six horizontal lanes showing parallel agent progress:
```
┌──────────────────────────────────────────────────────────┐
│  SWARM DEPLOYED                            38 jobs found │
│                                                          │
│  LinkedIn    ██████████████████░░  12 jobs   ✓ 0:34s     │
│  Indeed      █████████████░░░░░░░   8 jobs   ✓ 0:41s     │
│  Wellfound   ██████████░░░░░░░░░░   6 jobs   ✓ 0:38s     │
│  YC WaaS     █████████████████░░░   7 jobs   ✓ 0:29s     │
│  Greenhouse  ████████░░░░░░░░░░░░  crawling  ◌ 0:22s     │
│  Lever       █████░░░░░░░░░░░░░░░  queued    ○ —         │
└──────────────────────────────────────────────────────────┘
```

### JobCard
```
┌──────────────────────────────────────────────────────────┐
│  AI Engineer Intern                        Score: 94 🟢  │
│  Anthropic · San Francisco, CA · 34 min ago              │
│  via LinkedIn                                            │
│                                                          │
│  Match: AI focus · Internship · Python · SF location     │
│  Salary: $60/hr                                          │
│                                                          │
│  [ Apply For Me (Coming Soon) ]         [ View Posting ] │
└──────────────────────────────────────────────────────────┘
```

---

## File Structure

```
jobswarm/
├── backend/
│   ├── main.py              # FastAPI app, CORS, SSE routes
│   ├── orchestrator.py      # Parallel TinyFish execution
│   ├── platforms.py         # URL builders
│   ├── scorer.py            # GPT-4o-mini scoring
│   ├── models.py            # Pydantic models
│   ├── state.py             # In-memory store
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       │   ├── ProfileSetup.jsx
│       │   ├── ProfileForm.jsx
│       │   ├── SearchConfig.jsx
│       │   ├── HuntButton.jsx
│       │   ├── HuntDashboard.jsx
│       │   ├── SwarmStatusBar.jsx
│       │   ├── StatsRow.jsx
│       │   ├── JobFeed.jsx
│       │   └── JobCard.jsx
│       └── hooks/
│           └── useHuntStream.js
├── .env.example
└── README.md
```

---

## Dependencies

### Backend (requirements.txt)
```
fastapi>=0.115.0
uvicorn>=0.30.0
tinyfish>=0.2.4
openai>=1.0.0
sse-starlette>=2.0.0
pydantic>=2.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
```

### Frontend (package.json)
```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "vite": "^6.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0"
  }
}
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Agent timeout (5min) | Return partial results, mark platform as `timeout` |
| CAPTCHA block | Return empty, send `agent_failed` event |
| Login wall | Extract visible data, mark `partial: true` |
| Single agent fails | Continue with others, don't block hunt |
| Scoring fails | Return jobs unsorted with `relevance_score: 0` |
| All agents fail | Return error state, prompt retry |

---

## Environment Variables

```env
TINYFISH_API_KEY=sk-tinyfish-xxxxx
OPENAI_API_KEY=sk-xxxxx
```
