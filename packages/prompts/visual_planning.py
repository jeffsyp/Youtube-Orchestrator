"""Prompt for timestamp-aware visual planning.

Called AFTER narration is generated and Whisper has word-level timestamps.
Claude acts as a visual director, planning exactly what to show at each moment.
"""


def build_visual_plan_prompt(
    channel_name: str,
    niche: str,
    title: str,
    timestamped_words: list[tuple[str, float, float]],
    total_duration: float,
    is_long_form: bool = False,
) -> tuple[str, str]:
    """Build the visual planning prompt with word-level timestamps.

    Args:
        timestamped_words: list of (word, start_seconds, end_seconds)
        total_duration: total audio duration in seconds
    """
    # Format transcript with timestamps
    transcript_lines = []
    for word, start, end in timestamped_words:
        transcript_lines.append(f"  {start:.2f}s-{end:.2f}s: \"{word}\"")
    transcript_block = "\n".join(transcript_lines)

    # Also build a readable version grouped by ~sentence
    readable_lines = []
    current_line = []
    current_start = 0.0
    for word, start, end in timestamped_words:
        if not current_line:
            current_start = start
        current_line.append(word)
        if word.endswith(('.', '!', '?', '...')) or len(current_line) > 12:
            readable_lines.append(f"  [{current_start:.1f}s - {end:.1f}s] \"{' '.join(current_line)}\"")
            current_line = []
    if current_line:
        readable_lines.append(f"  [{current_start:.1f}s - {timestamped_words[-1][2]:.1f}s] \"{' '.join(current_line)}\"")
    readable_block = "\n".join(readable_lines)

    aspect = "16:9 landscape" if is_long_form else "9:16 vertical portrait"

    system = f"""You are a visual director for "{channel_name}" — a YouTube Shorts channel about {niche}.

You have the FINAL narration audio with exact word-level timestamps. Your job is to plan every visual — what the viewer SEES at each moment, synced precisely to what they HEAR.

You are editing a video. You know exactly when every word is spoken. Plan the visuals so they HIT at the right moments.

VISUAL TYPES AVAILABLE:

1. "grok" — AI-generated VIDEO CLIP
   - Duration: 1-15 seconds per clip
   - Great for: action, movement, character moments, dramatic reveals, hooks
   - Video prompts MUST describe MOVEMENT — characters doing things, camera tracking/pushing, environmental motion
   - Cost: $0.07/sec — use strategically, not for everything

2. "image" — AI-generated STILL IMAGE with Ken Burns zoom
   - Great for: info visuals, maps, comparisons, number cards, dramatic stills, reaction shots
   - Cheaper and faster than video — use when motion isn't needed
   - Image prompts MUST describe ONE clear subject per image — never split screens, never collages, never multiple panels
   - Keep compositions SIMPLE — one character, one scene, one moment. The viewer sees this on a phone screen
   - Style: colorful cartoon style, bold outlines, bright colors, vertical composition

DIRECTING RULES:
- The FIRST visual MUST be type "grok" — video hooks grab attention
- Visual cuts do NOT have to align with sentence boundaries — cut mid-sentence if it serves the visual storytelling
- When the narration says something specific ("he EXPLODED", "the building collapsed"), the visual must show it AT THAT MOMENT, not before or after
- No single visual should last more than 6 seconds
- MINIMUM DURATION — THIS IS CRITICAL:
  - Video clips ("grok"): minimum 3 seconds. Anything shorter is a waste — the viewer can't even register what's happening
  - Images with detail: minimum 2.5 seconds. The viewer needs to SEE and PROCESS the image
  - Simple text/number cards: minimum 1.5 seconds
  - If you can't fill 3 seconds with a video clip, use an image instead
- DON'T CUT TOO FAST — rapid cuts are disorienting, not engaging. Let each visual LAND before moving to the next. The viewer needs to understand what they're looking at
- Mix video and images — use video for high-energy moments, images for info-dense moments
- Think about CONTRAST — a quiet image followed by an intense video clip creates impact
- Fewer visuals that land > many visuals that flash by

CONSISTENCY OPTIONS:
- "consistent_character": true — keeps the same character look across scenes (uses the first animated clip as the reference image)
- "extend_previous": true — chains this animated clip from the last frame of the previous one (continuous action)
- "label": "TEXT" — persistent text overlay (for rankings, location names, etc.). NO EMOJIS in labels — they break rendering

ASPECT RATIO: {aspect}

OUTPUT — return a JSON object:
{{
  "visuals": [
    {{
      "start": 0.0,
      "end": 3.2,
      "type": "grok",
      "prompt": "image fallback prompt if video fails",
      "video_prompt": "action-oriented video generation prompt with MOVEMENT",
      "label": null
    }},
    {{
      "start": 3.2,
      "end": 5.8,
      "type": "image",
      "prompt": "detailed image prompt",
      "label": "5"
    }}
  ]
}}

IMPORTANT:
- Visuals must cover the ENTIRE duration ({total_duration:.1f}s) with no gaps
- start of each visual = end of the previous visual
- First visual starts at 0.0
- Last visual ends at {total_duration:.1f}
- Return ONLY valid JSON, no markdown"""

    user = f"""Plan the visuals for "{title}"

NARRATION (sentence-level timing):
{readable_block}

WORD-LEVEL TIMESTAMPS:
{transcript_block}

Total duration: {total_duration:.1f}s

Direct this. Every visual must serve what's being said at that exact moment. The viewer should feel like the visuals were MADE for this narration."""

    return system, user
