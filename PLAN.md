# YouTube Orchestrator — Project Plan

## Vision

Build a fully automated, faceless YouTube content channel system that researches viral videos, generates scripts, produces media packages, and publishes content — with a human-in-the-loop approval layer that gradually gets automated away as confidence grows.

The system should be **quality-first**. It is better to publish nothing than to publish bad content. Every major decision should be logged, reviewable, and improvable over time.

---

## Core Philosophy

- **Start manual, automate gradually.** Every step starts with a human approval gate. As the system proves itself, gates get removed one by one.
- **Data drives decisions.** Every idea scored, every script graded, every video's performance tracked. Nothing is vibes-based.
- **Durable over clever.** Simple workflows that always finish beat fancy systems that sometimes break.
- **One thing at a time.** Build research first. Then writing. Then media. Then publishing. Do not jump ahead.

---

## What This System Does (End State)

1. Every day, automatically discovers viral YouTube videos in the target niche
2. Scores them for breakout potential (views vs channel size, recency, topic patterns)
3. Extracts content templates and patterns from top performers
4. Generates 3–5 video ideas based on those patterns
5. Selects the best idea, builds an outline, writes a full script
6. Critiques and revises the script automatically
7. Produces a shot list, narration plan, subtitle file, and asset manifest
8. Generates voiceover instructions (later: actual audio via ElevenLabs)
9. Packages everything for upload
10. Publishes to YouTube with optimized title, description, and tags
11. Tracks performance (views, CTR, retention) and feeds it back into scoring

---

## Automation Confidence Model

Jeff starts by approving most things. Gates are removed as each layer proves reliable.

| Gate | Start | Remove When |
|---|---|---|
| Approve selected idea | Manual | System picks winners consistently for 4+ weeks |
| Approve outline | Manual | Outlines rarely need changes for 3+ weeks |
| Approve script | Manual | Scripts hit quality bar 90%+ of the time |
| Approve media package | Manual | Shot lists and assets are consistently usable |
| Approve publish | Manual | Full pipeline proven end-to-end for 30+ videos |

**No gate gets removed without a conscious decision. The default is always: keep the gate.**

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12+ |
| Package manager | uv |
| Workflow engine | Temporal |
| Database | Postgres |
| Migrations | Alembic |
| Object storage | S3 or Cloudflare R2 (Phase 4+) |
| API framework | FastAPI |
| AI reasoning | Anthropic Claude API (`claude-sonnet-4-6`) |
| Voice (later) | ElevenLabs |
| Publishing | YouTube Data API v3 |
| Local dev | Docker Compose |
| Logging | structlog |

> **Note on AI:** Use the Anthropic Claude API (not OpenAI) for all reasoning steps — script writing, critique, scoring, idea generation. Model: `claude-sonnet-4-6`. Consider `claude-haiku-4-5-20251001` for cheaper tasks (scoring, simple extraction).

---

## Architecture: Multi-Channel Awareness

The data model is **multi-channel from day one**. Every table has a `channel_id` foreign key. Workflows are parameterized by channel. Config (niche, search terms, tone, scoring weights) is per-channel. This means spinning up a second channel is just adding a row to the `channels` table and starting another workflow — no schema migration needed.

We do NOT build multi-channel management UI, dashboards, or cross-channel features until after Phase 5. But the data model is ready.

---

## Repo Structure

```
youtube-orchestrator/
├── apps/
│   ├── orchestrator/        # Temporal workflows and activities
│   ├── research_service/    # Candidate discovery and scoring
│   ├── writing_service/     # Outline, script, critique, revision
│   ├── media_service/       # Shot list, narration, subtitles, assets
│   └── publishing_service/  # YouTube upload, scheduling
├── packages/
│   ├── schemas/             # Shared Pydantic models (the contract between workers)
│   ├── prompts/             # All LLM prompts, versioned
│   └── clients/             # Shared API clients (YouTube, Claude, ElevenLabs)
├── infra/
│   └── docker/              # Docker Compose configs
├── migrations/              # Alembic migrations
├── admin/                   # Simple CLI for human approval gates
├── tests/                   # Schema and workflow tests
├── pyproject.toml           # uv project config
├── .env.example             # Required env vars template
├── PLAN.md                  # This file
└── README.md
```

---

## Database Tables

All tables include `channel_id` as a foreign key to support multi-channel from day one.

```sql
channels              -- id, name, niche, config (JSON), created_at
content_runs          -- one row per daily pipeline run (per channel)
source_candidates     -- viral videos discovered during research
templates             -- extracted content patterns
ideas                 -- generated video ideas with scores
scripts               -- outlines, drafts, critiques, final versions
assets                -- media files, shot lists, subtitle files
packages              -- final video packages ready for upload
performance_snapshots -- post-publish metrics (views, CTR, retention)
```

---

## Shared Pydantic Schemas (packages/schemas)

These are the contracts between all workers. Every service reads and writes these:

- `RunState` — overall state of one pipeline run
- `CandidateVideo` — a discovered viral video with metadata and scores
- `TemplatePattern` — an extracted content pattern from top performers
- `IdeaVariant` — a generated video idea with scoring
- `OutlineDraft` — a structured video outline
- `ScriptDraft` — a full script with sections, hooks, CTAs
- `VisualPlan` — shot list and scene descriptions
- `VoicePlan` — narration style, pacing, tone instructions
- `PackagingPlan` — final asset manifest and upload metadata

---

## Temporal Workflow: `daily_content_pipeline`

Activities in order:

1. `discover_candidates` — pull viral videos from YouTube
2. `score_breakouts` — score each candidate
3. `extract_templates` — identify content patterns
4. `generate_variants` — produce 3–5 video ideas
5. `select_best_idea` — pick the top idea (human gate in Phase 1)
6. `build_outline` — generate structured outline (human gate in Phase 1)
7. `write_script` — write full script (human gate in Phase 1)
8. `critique_script` — AI self-critique pass
9. `revise_script` — rewrite based on critique
10. `build_visual_plan` — shot list and scene plan
11. `build_voice_plan` — narration instructions
12. `package_video` — assemble final package (human gate in Phase 1)
13. `qa_check` — final automated quality check
14. `publish` — upload to YouTube (human gate in Phase 1)

---

## Build Phases

### Phase 1 — Foundation (Build This First)

**Goal:** One complete run, start to finish, with fake data writing state to Postgres.

- [ ] Repo structure created
- [ ] Docker Compose with Postgres + Temporal running locally
- [ ] All DB tables created
- [ ] All Pydantic schemas defined
- [ ] Temporal workflow with all activity stubs
- [ ] One full run with hardcoded fake data completes and writes to Postgres
- [ ] Basic admin CLI for human approval gates

**Done when:** `daily_content_pipeline` runs end-to-end with fake data and all state is in the DB.

---

### Phase 2 — Real Research

**Goal:** Discover and score real YouTube videos.

- [ ] YouTube Data API v3 integration
- [ ] `research_service` pulls real candidate videos
- [ ] Breakout scoring (views/channel size ratio, recency)
- [ ] Candidates stored in `source_candidates` table
- [ ] Human reviews candidates via admin CLI

**Done when:** System finds real viral videos daily and stores them.

---

### Phase 3 — Real Writing

**Goal:** Generate real scripts using Claude.

- [ ] Anthropic Claude API integration
- [ ] `writing_service` generates outlines and scripts
- [ ] AI critique + one revision pass
- [ ] Human approves script via admin CLI

**Done when:** System produces scripts a human would be willing to publish.

---

### Phase 4 — Media Package

**Goal:** Produce everything needed to make the video.

- [ ] Shot list generation
- [ ] Narration/voiceover instructions
- [ ] Subtitle file (.srt)
- [ ] Asset manifest

**Done when:** A video editor (or future automation) could take the package and make the video.

---

### Phase 5 — Publishing

**Goal:** Upload real videos to YouTube.

- [ ] YouTube upload integration
- [ ] Title/description/tags generation
- [ ] Scheduled publishing
- [ ] Performance tracking starts

**Done when:** First real video published via the system.

---

### Phase 6 — Feedback Loops + Automation

**Goal:** Close the loop and start removing approval gates.

- [ ] Performance snapshots collected post-publish
- [ ] Scoring models updated from real data
- [ ] Approval gates removed one by one based on confidence
- [ ] ElevenLabs voice integration

---

## What NOT to Build Yet

Do not touch these until Phase 5 is complete:

- Multi-channel management UI (data model already supports it)
- Thumbnail generation
- Fully autonomous publishing (no human gates)
- Complex memory systems
- Browser automation / computer use
- 15 agents talking to each other

---

## Config and Secrets

All config via environment variables loaded from `.env`:
- `DATABASE_URL` — Postgres connection string
- `TEMPORAL_HOST` — Temporal server address (default: `localhost:7233`)
- `TEMPORAL_NAMESPACE` — Temporal namespace (default: `default`)
- `ANTHROPIC_API_KEY` — needed from Phase 3
- `YOUTUBE_API_KEY` — needed from Phase 2
- `ELEVENLABS_API_KEY` — needed from Phase 6

---

## Logging

Use `structlog` for structured JSON logging throughout. Every activity logs:
- Activity name, run ID, channel ID
- Input summary and output summary
- Duration

---

## Testing Strategy

- `tests/test_schemas.py` — all Pydantic models instantiate and serialize correctly
- `tests/test_workflow.py` — workflow runs end-to-end with mocked/test DB
- Tests run via `uv run pytest`

---

## YouTube API Quotas

YouTube Data API v3 has a default quota of 10,000 units/day. Search costs 100 units per call. Plan research queries carefully — batch searches, cache results, and stay well under the limit. Monitor usage from Phase 2 onward.

---

## APIs Needed (set up in order, not all at once)

1. **Anthropic API** — needed for Phase 3
2. **YouTube Data API v3** — needed for Phase 2 (research) and Phase 5 (publishing)
3. **ElevenLabs** — needed for Phase 6

---

## First Session Checklist

Start here. Do nothing else until these are done:

1. Create full repo folder structure
2. Create `docker-compose.yml` with Postgres and Temporal
3. Create all DB tables with migration script
4. Create all Pydantic schemas in `packages/schemas`
5. Create Temporal workflow with all activity stubs in `apps/orchestrator`
6. Run the workflow end-to-end with hardcoded fake data
7. Confirm all state is written to Postgres

---

## Definition of Done (Phase 1)

Running `docker compose up` starts the stack.
Running the workflow produces a completed run in the `content_runs` table.
All fake data flows through every activity and lands in the correct tables.
The admin CLI can display the run and its state.
