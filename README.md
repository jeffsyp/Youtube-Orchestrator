# YouTube Orchestrator

Automated YouTube content factory that generates, renders, and publishes videos end-to-end. Concept ideation, script writing, AI image/video generation, voice narration, subtitle rendering, and YouTube upload — all orchestrated through a single pipeline.

## How It Works

1. **Concept Generation** -- Claude generates video concepts tailored to each channel's niche, filtered against past content to avoid duplicates
2. **Script Writing** -- Approved concepts get full narration scripts with per-line timing
3. **Visual Planning** -- Claude plans visuals for each narration line: video clips (Grok), diagrams (gpt-image-1.5), or still images
4. **Asset Generation** -- ElevenLabs TTS for narration, Grok for images and video clips, gpt-image-1.5 for diagrams/infographics
5. **Rendering** -- FFmpeg stitches everything together with karaoke subtitles, background music, and transitions
6. **Publishing** -- Upload to YouTube via API with per-channel categories, descriptions, and tags

## Architecture

```
apps/
  api/            # FastAPI REST API (channel management, runs, concepts, uploads)
  orchestrator/   # Video generation pipeline
  worker/         # Background worker (concept generation, run execution, monitoring)
  publishing_service/  # YouTube OAuth and upload

packages/
  clients/        # API clients (Claude, Grok, ElevenLabs, OpenAI, YouTube)
  prompts/        # Prompt templates for concept/script generation
  schemas/        # Shared data models

frontend/         # React dashboard (Vite + TypeScript)
```

## Pipeline Formats

| Format | Duration | Resolution | Use Case |
|--------|----------|------------|----------|
| Shorts | 20-30s | 720x1280 (portrait) | Quick-hit narrated stories |
| Mid-form | 3-5 min | 1920x1080 (landscape) | Educational explainers |
| Long-form | 10-13 min | 1920x1080 (landscape) | Deep-dive narratives |
| No-narration | 15-20s | 720x1280 (portrait) | Memes, satisfying videos |

## Visual Types

- **Video clips** (Grok) -- AI-generated image animated into a video clip. Default for most content.
- **Diagrams** (gpt-image-1.5) -- Text, charts, infographics. Used when the viewer needs to read key info.
- **Still images** (Grok) -- Static images with Ken Burns effect. Used sparingly.

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, PostgreSQL
- **Frontend**: React, TypeScript, Vite, TailwindCSS
- **AI**: Claude (scripts/planning), Grok (images/video), gpt-image-1.5 (diagrams), ElevenLabs (TTS)
- **Rendering**: FFmpeg
- **Task runner**: uv

## Setup

```bash
# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Fill in API keys: ANTHROPIC_API_KEY, XAI_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY

# Start PostgreSQL and run migrations
uv run alembic upgrade head

# Start services
bash scripts/run_api.sh       # API supervisor (detached, auto-restarts)
bash scripts/run_worker.sh > /tmp/worker.log 2>&1 &  # Worker supervisor
bash scripts/run_frontend.sh  # Frontend supervisor (detached, auto-restarts)

# YouTube auth (per channel)
uv run python -m apps.publishing_service.auth --token-file youtube_token_<channel>.json
```

## License

Private project.
