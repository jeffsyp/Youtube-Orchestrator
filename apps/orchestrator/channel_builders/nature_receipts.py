"""Nature Receipts channel builder — "What if [animal] was [absurd scenario]" videos.

Uses unified pipeline: style anchor → sub-actions → GPT images → Grok animation → chaining.
"""
import asyncio
import json
import os
import re

import structlog

from apps.orchestrator.channel_builders.shared import (
    generate_narration_with_timestamps,
    generate_and_animate_scenes,
    build_segments_from_clip_map,
    build_intro_teasers,
    concat_silent_video,
    build_numpy_audio,
    combine_video_audio,
    add_subtitles,
    update_database,
)

logger = structlog.get_logger()

CHANNEL_ID = 25
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"  # Liam (energetic)
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "dark", "rising.mp3")
TAGS = ["nature receipts", "what if", "animals", "nature", "shorts", "viral"]

ART_STYLE = "Photorealistic editorial wildlife photography — absurd animal scenarios rendered like real high-end press or documentary photos. Real feathers, fur, scales, anatomy, and lighting. Naturalistic textures, real camera depth of field, subtle lens imperfections, believable shadows, cinematic but still photographic. Human environments and props may be absurd, but the final image must still look like a real photograph captured in-camera. NOT cartoon, NOT illustrated, NOT cel-shaded."

IMAGE_RULES = """RULES:
- Everything must match the photoreal editorial wildlife style reference
- Real animal anatomy, real feathers/fur/scales, real lighting, real camera look
- Humans, props, podiums, vehicles, and rooms should also look photographic and physically present
- The same exact animal must stay consistent across scenes: same species, same coloring, same markings, same accessories
- Do NOT invent random new colors or redesign the animal between scenes
- Exaggerated SITUATIONS are good, but the rendering itself must stay realistic
- If the narration says chaos, show CHAOS — not a calm scene
- Every prompt must end with "Photorealistic editorial wildlife photo. NO text anywhere."
- Each prompt = ONE clear scene matching the narration line
- If the narration uses Day/Week/Month markers, treat them as SEQUENTIAL chapters of one continuous story, not disconnected skits
- Each new day should visually carry forward at least one consequence from the previous day: damage, crowd reaction, authorities arriving, a repeated object, a bigger version of the same problem
- Do NOT reset the world each line. If Day 1 destroys the fence, Day 2 should not show a perfect untouched fence again unless the narration says the setting changed
- Reuse the same animal, same location, and same supporting humans/objects across consecutive days whenever the story is still happening there
- If the concept does NOT specify a feather/fur color, species variant, or accessory color, do NOT make one up unless it is needed for realism"""

SCRIPT_PROMPT = """Write a narration script for a Nature Receipts YouTube video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST state the topic as a question: "What if [animal] was [absurd scenario]?" — this IS the title. Shorts viewers don't see video titles so line 1 gives them context.
- Line 2 goes STRAIGHT into the first time period (Day 1, Week 1, etc.) — NO story intro, NO setup, NO "imagine this"
- CHOOSE THE RIGHT STRUCTURE:
  A) DAY-BY-DAY — use when the animal is in a new environment over time:
     - "Day 1:", "Day 2:", "Week 2:" as part of narration
     - GOOD fit: "What if a golden retriever was the size of a building" → Day 1: noticed, Day 3: famous, Month 1: worshipped
  B) REAL-TIME — use when it's a single moment of chaos:
     - No day markers, rapid escalation
     - GOOD fit: "What if a cat pressed the nuclear button" → paw on button, alarms, chaos, aftermath
  Pick whichever fits.
- Use whatever time structure fits the story — days, weeks, months, years, or no time labels at all. A penguin growing up takes months not days. A giant dog causes chaos in hours. Let the story decide.
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line = one scene = one image
- Each line UNDER 15 words
- If you use Day/Week/Month structure, EVERY time marker must feel like a mini story beat:
  1. start from the new situation created by the previous line
  2. show the animal doing one concrete action
  3. end with the immediate consequence that sets up the NEXT time marker
- In other words: each day should have a tiny beginning, middle, and payoff inside the larger escalation.
- Every line after line 1 must answer: "What changed because of the previous line?"
- Do NOT write random vignettes. BAD: Day 1 at a farm, Day 2 suddenly at Wall Street, Day 3 randomly in space, with no causal bridge.
- GOOD progression: Day 1 the animal causes one contained problem. Day 2 humans react to that problem. Week 2 the reaction backfires and the animal gains even more power. Month 1 the situation has fully transformed the world.
- Reuse story elements so the viewer feels continuity: the same crowd, same city block, same handlers, same object the animal fixates on, same authorities trying and failing.
- The scenarios should be EXTREME — absolute chaos, not mild inconvenience
- Wholesome chaos is good (giant retriever), dark chaos is fine too
- The comedy comes from the ESCALATION — each step is more ridiculous
- The animal must ACTUALLY DO the things you describe — if it's raised by predators, show it HUNTING, SPRINTING, POUNCING, KILLING. Not just standing near other animals looking confused. It should BECOME what raised it.
- Each narration line must describe a SPECIFIC VISUAL ACTION — "The penguin sprints on all fours and tackles a gazelle" NOT "The penguin tries to hunt"
- The ending must GO COMPLETELY INSANE — not "and everyone was confused." The animal becomes the apex predator, conquers an ecosystem, gets its own Netflix documentary, breaks the food chain, scientists lose their minds. Absurd endings that make people replay the video.
- The LAST LINE should be a punchline that lands hard

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


async def build_nature_receipts(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Nature Receipts video build using unified pipeline."""
    title = concept.get("title", "Untitled")
    narration_lines = concept.get("narration", [])

    narr_dir = os.path.join(output_dir, "narration")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [narr_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    # ─── STEP 1: Write script if not provided ───
    if not narration_lines:
        await _update_step("writing script")
        from packages.clients.claude import generate as claude_generate
        brief = concept.get("brief", title)
        resp = claude_generate(
            prompt=SCRIPT_PROMPT.format(title=title, brief=brief),
            max_tokens=2000,
        )
        json_match = re.search(r'\{.*\}', resp, re.DOTALL)
        if json_match:
            script_data = json.loads(json_match.group())
            narration_lines = script_data.get("narration", [])
            if script_data.get("title"):
                title = script_data["title"]
        if not narration_lines:
            raise ValueError("Failed to generate narration script")

    n_lines = len(narration_lines)

    # ─── STEP 2: Narration ───
    await _update_step("generating narration")
    await generate_narration_with_timestamps(
        narration_lines, narr_dir, output_dir, VOICE_ID, _update_step,
        voice_settings={"stability": 0.4, "similarity_boost": 0.8, "speed": 1.1},
    )

    # ─── STEP 3: Unified pipeline — style anchor + sub-actions + chaining ───
    clips_dir, clip_paths, n_clips, line_clip_map = await generate_and_animate_scenes(
        narration_lines, concept, IMAGE_RULES, ART_STYLE, output_dir, _update_step, run_id=run_id,
    )

    # ─── STEP 4: Build segments from clip map ───
    await _update_step("building video")
    style_anchor = os.path.join(output_dir, "images", "style_anchor.png")
    seg_durations = build_segments_from_clip_map(
        n_lines, line_clip_map, clips_dir, narr_dir, segments_dir, style_anchor,
    )

    # ─── STEP 5: Intro, audio, subtitles ───
    await _update_step("building intro")
    actual_teaser_dur = build_intro_teasers(n_lines, narr_dir, clips_dir, segments_dir)

    await _update_step("concatenating")
    teasers_path = os.path.join(segments_dir, "teasers.mp4")
    all_video_path, total_dur = concat_silent_video(teasers_path, segments_dir, n_lines, output_dir)

    await _update_step("building audio")
    audio_path, seg_starts = build_numpy_audio(
        n_lines, narr_dir, MUSIC_PATH, actual_teaser_dur, seg_durations, total_dur, output_dir,
    )

    await _update_step("combining")
    combined = combine_video_audio(all_video_path, audio_path, output_dir)

    await _update_step("adding subtitles")
    with open(os.path.join(output_dir, "word_timestamps.json")) as f:
        word_data = json.load(f)
    add_subtitles(combined, word_data, seg_starts, output_dir)

    await update_database(run_id, CHANNEL_ID, title, output_dir, db_url, TAGS)
    logger.info("nature receipts complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
