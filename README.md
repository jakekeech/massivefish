# InternShip

> **A Multi-Layer Agentic Swarm Architecture for Autonomous Job Discovery & Application**

Deploy a coordinated swarm of TinyFish AI agents that autonomously navigate, scrape, and process job postings across 6 major platforms in parallel—then leverage a multi-model reasoning pipeline for intelligent scoring and guided application orchestration.

**Built for the TinyFish $2M Pre-Accelerator Hackathon**

---

## Why InternShip?

Traditional job hunting is broken: manual searches across fragmented platforms, copy-pasting the same info, and zero personalization. InternShip reimagines this with **agentic automation**—AI agents that think, adapt, and act on your behalf.

---

## Agentic Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LAYER 3: PRESENTATION                             │
│                        Real-time SSE Event Stream                           │
│              React 19 + Tailwind v4 (Dark Hacker Aesthetic)                 │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│                      LAYER 2: ORCHESTRATION LAYER                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  Hunt Conductor  │  │  Score Pipeline  │  │  Application Copilot    │   │
│  │  (Async Fan-out) │  │  (GPT-4o-mini)   │  │  (Claude + Form Agent)  │   │
│  └────────┬─────────┘  └────────┬─────────┘  └────────────┬─────────────┘   │
│           │                     │                         │                 │
│           │    Deduplication    │    Cover Letter Gen     │                 │
│           │    + Batch Scoring  │    + Field Detection    │                 │
└───────────┼─────────────────────┼─────────────────────────┼─────────────────┘
            │                     │                         │
┌───────────▼─────────────────────▼─────────────────────────▼─────────────────┐
│                        LAYER 1: AGENT SWARM (TinyFish)                      │
│                                                                             │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│   │LinkedIn │ │ Indeed  │ │Wellfound│ │YC WaaS  │ │Greenhouse│ │  Lever  │   │
│   │ Agent   │ │ Agent   │ │ Agent   │ │ Agent   │ │  Agent   │ │  Agent  │   │
│   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘ └────┬────┘   │
│        │           │           │           │           │            │       │
│        └───────────┴───────────┴─────┬─────┴───────────┴────────────┘       │
│                                      │                                      │
│                    TinyFish Headless Browser Automation                     │
│               (Anti-Detection, CAPTCHA Handling, JS Rendering)              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Multi-Layer Swarm Intelligence

| Layer | Component | Technology | Function |
|-------|-----------|------------|----------|
| **L1** | Agent Swarm | TinyFish SDK | 6 parallel browser agents with anti-detection, dynamic DOM traversal, and adaptive scraping |
| **L2** | Orchestrator | FastAPI + AsyncIO | Fan-out/fan-in coordination, real-time SSE streaming, fault-tolerant agent supervision |
| **L2** | Scorer | GPT-4o-mini | Semantic relevance scoring (0-100), match reason extraction, cross-platform deduplication |
| **L2** | Copilot | Claude 3.5 | Resume intelligence, cover letter synthesis, form field inference |
| **L3** | UI | React 19 + Vite 6 | Real-time agent status visualization, job feed with relevance badges |

---

## Key Innovations

### 1. Parallel Agent Dispatch via TinyFish
```python
# Simultaneous agent deployment across 6 platforms
async def dispatch_swarm(targets: list[str]):
    agents = [spawn_tinyfish_agent(url) for url in targets]
    return await asyncio.gather(*agents)  # True parallelism
```
- **6 concurrent TinyFish agents** scraping simultaneously
- **Real-time SSE streaming** of agent progress events
- **Fault isolation**: one agent failure doesn't crash the swarm

### 2. Multi-Model Reasoning Pipeline
- **TinyFish** → Autonomous web navigation & data extraction
- **GPT-4o-mini** → Semantic job-profile matching & scoring
- **Claude 3.5 Sonnet** → Resume parsing & cover letter generation

### 3. Intelligent Deduplication
Same job posted on LinkedIn AND Indeed? Our cross-platform deduplication engine catches it via:
- URL normalization
- Company + Title fuzzy matching
- Semantic similarity detection

### 4. Application Copilot (Agentic Workflow)
Not just job discovery—**end-to-end application assistance**:
- AI extracts your profile from uploaded resume (Claude)
- Generates tailored cover letters per job
- Guides form completion with live preview

---

## Features

- **Swarm Parallelism** — 6 TinyFish agents scrape LinkedIn, Indeed, Wellfound, YC Work at a Startup, Greenhouse, and Lever simultaneously
- **Event-Driven Architecture** — Real-time SSE streaming with agent lifecycle events
- **Multi-Model Intelligence** — GPT-4o-mini scoring + Claude resume parsing + TinyFish web automation
- **Semantic Relevance Engine** — AI scores each job 0-100 with explainable match reasons
- **Cross-Platform Deduplication** — Fuzzy matching eliminates duplicates across job boards
- **Resume-to-Profile Pipeline** — Upload PDF → Claude extracts structured profile data
- **Application Copilot** — AI-guided application flow with auto-generated cover letters
- **Dark Hacker Aesthetic** — Because job hunting should feel powerful

---

## Quick Start

### 1. Environment Setup

```bash
cp .env.example .env
# Configure your API keys:
# - TINYFISH_API_KEY from https://agent.tinyfish.ai/api-keys
# - OPENAI_API_KEY from https://platform.openai.com
# - ANTHROPIC_API_KEY from https://console.anthropic.com
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

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Agent Runtime** | TinyFish SDK | Headless browser automation, anti-detection, parallel execution |
| **Orchestration** | Python 3.11+, FastAPI, AsyncIO | Async fan-out, SSE streaming, agent coordination |
| **Scoring LLM** | OpenAI GPT-4o-mini | Job-profile relevance scoring, match reasoning |
| **Reasoning LLM** | Anthropic Claude 3.5 | Resume parsing, cover letter generation |
| **Frontend** | React 19, Vite 6, Tailwind CSS 4 | Real-time UI with agent status visualization |
| **State** | In-memory | Hackathon-speed, no DB overhead |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/profile` | Save user profile |
| GET | `/api/profile` | Retrieve current profile |
| POST | `/api/resume/parse` | Upload & parse PDF resume via Claude |
| GET | `/api/resume/current` | Get resume metadata |
| GET | `/api/resume/current/file` | Download stored resume |
| POST | `/api/hunt` | Dispatch agent swarm (SSE stream) |
| GET | `/api/jobs?hunt_id={id}` | Retrieve scored & deduplicated jobs |
| POST | `/api/apply` | Start application copilot (SSE stream) |

---

## The Vision

InternShip demonstrates the power of **agentic swarms** for real-world automation. By combining TinyFish's browser automation with multi-model AI reasoning, we've built a system that doesn't just find jobs—it **understands** them, **scores** them, and **helps you apply**.

This is the future of AI-assisted productivity: **autonomous agents working in parallel, orchestrated by intelligent pipelines, delivering real value.**

---

## License

MIT
