# YouTube Orchestrator — Claude Code Guide

## What This Is
An automated YouTube Shorts/long-form video pipeline that generates AI-narrated and meme videos across 22 channels. Concepts → Scripts → Narration (ElevenLabs) → Images (gpt-image-1.5) → Video Animation (Grok) → Assembly (FFmpeg) → Upload (YouTube API).

## Architecture
- **API**: FastAPI on port 8000 (`apps/api/`)
- **Worker**: Background process that generates videos (`apps/worker/`)
- **Pipeline**: Each video runs as a subprocess (`apps/worker/pipeline_runner.py` → `apps/orchestrator/pipeline.py`)
- **Frontend**: React/Vite on port 5173 (`frontend/`)
- **DB**: PostgreSQL `youtube_orchestrator`

## Starting Services
```bash
# Worker (with auto-restart supervisor)
bash scripts/run_worker.sh > /tmp/worker.log 2>&1 &

# API
.venv/bin/uvicorn apps.api.main:app --port 8000 > /tmp/api.log 2>&1 &

# Frontend
cd frontend && npm run dev > /tmp/frontend.log 2>&1 &
```

## Key Commands
- `/status` — check running pipelines, worker health
- `/analyze <run_id>` — send video to Gemini for detailed analysis
- `/push-meme <channel> <desc>` — push a no-narration meme concept
- `/push-video <channel> <desc>` — push a narrated video concept
- `/retry <run_id>` — retry a failed run
- `/clear-failed` — clear all failed runs
- `/channels` — list all channels and their config

## Video Types

### Meme Videos (no narration)
Channels: Munchlax Lore (13), CrabRaveShorts (16), Deity Drama (22), NightNightShorts (28), Thats A Meme (33)
- Crude cartoon style, 2-3 scenes, 8-12 seconds
- Text baked into images by gpt-image (5-8 words max)
- video_prompt: CHARACTER MOVEMENT not camera movement. Grok does boring slow zooms if you say "camera pulls back"
- Sound effects in video_prompt are critical to comedy
- Proven patterns: escalation→anticlimax, setup→instant karma, expectation vs reality

### Narrated Shorts
- 4-6 lines, under 15 words each, 20-30 seconds total
- Line 1 states topic (viewers have zero context on shorts)
- Viral formula: specific number → relatable twist → escalating disbelief → reaction ending
- Leading silence trimmed from first line

### Narrated Long-form
- 30-40 lines (5 chapters × 8 max), 3-5 minutes
- Starts with context/setup, not frantic hook (viewer clicked to watch)
- No leading silence trim

## What NOT To Do
- Don't use `quality="high"` for gpt-image — use `quality="medium"` ($0.05 vs $0.20)
- Don't use copyrighted names in art style prompts (no "Caravaggio", "Marvel", "Pokemon Scarlet")
- Don't write "camera zooms" in video_prompts — describe character movement
- Don't push videos directly without storing full concept in content_bank
- Don't use the YouTube Data API for search/trends — use YouTube autocomplete (free)
- Don't use "today" in video titles — videos outlive the day
- Don't reuse visual_plan.json from failed runs (stale)
- Don't generate long-form concepts for channels that are shorts-only meme channels
- Always clear stale content when prompts/art styles change
- Always store full concept JSON (with narration/scenes) in content_bank

## Common Issues
- **Stuck runs**: Subprocess timeout is 15min shorts / 30min long. Worker supervisor auto-restarts.
- **Safety filter**: Soften art style prompt. Remove copyrighted references.
- **Billing limit**: Check OpenAI credits. gpt-image at medium quality = ~$0.05/image.
- **No text in video**: gpt-image sometimes skips text. Make text SHORT and prominent in the prompt.
- **Boring animation**: video_prompt said "camera zooms" — rewrite with character actions.

## Key Files
- `apps/orchestrator/pipeline.py` — main pipeline, art styles, visual planning prompt
- `packages/prompts/concept_drafts.py` — all script/concept generation prompts
- `packages/prompts/long_form.py` — long-form chapter prompts
- `packages/clients/grok.py` — gpt-image and Grok video API calls
- `packages/clients/gemini_video.py` — Gemini video analysis
- `packages/clients/usage_tracker.py` — API usage tracking
- `apps/worker/runner.py` — subprocess pipeline runner
- `apps/worker/concept_generator.py` — auto concept generation with YouTube trending
