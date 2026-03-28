# JobSwarm

Deploy a swarm of AI agents to scrape job postings from 6 major job boards in parallel, then get AI-powered relevance scoring.

**Built for the TinyFish $2M Pre-Accelerator Hackathon**

## Features

- **Parallel Scraping** — 6 TinyFish agents scrape LinkedIn, Indeed, Wellfound, YC Work at a Startup, Greenhouse, and Lever simultaneously
- **Real-time Progress** — Watch agents complete in real-time via SSE streaming
- **AI Relevance Scoring** — GPT-4o-mini scores each job against your profile
- **Smart Deduplication** — Same job posted on multiple boards? We catch that
- **Dark Hacker Aesthetic** — Because job hunting should feel powerful

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

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  FRONTEND (React + Vite)                 │
│    ProfileSetup → HuntDashboard → SwarmStatus + JobFeed  │
└──────────────────────────┬───────────────────────────────┘
                           │ SSE
                           ▼
┌──────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI)                      │
│  POST /api/hunt → Orchestrator (6x TinyFish parallel)    │
│                        → Scorer (GPT-4o-mini)            │
│                        → GET /api/jobs                   │
└──────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, TinyFish SDK, OpenAI API
- **Frontend:** React 19, Vite 6, Tailwind CSS 4
- **Fonts:** JetBrains Mono + Inter
- **State:** In-memory (no database)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/profile` | Save user profile |
| POST | `/api/hunt` | Start parallel scrape (SSE stream) |
| GET | `/api/jobs?hunt_id={id}` | Get scored jobs |
| POST | `/api/apply` | Stubbed auto-apply (coming soon) |

## License

MIT
