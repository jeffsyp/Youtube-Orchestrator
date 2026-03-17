"""Prompts for Lad Stories — claymation-style character adventures via Sora 2.

Uses a consistent character bible + style lock for visual consistency across all videos.
No dialogue — stories told through animation, sound effects, and physical comedy.
"""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper

# Character bible — injected into every single Sora prompt
CHARACTER_BIBLE = (
    "A small round clay character called Lad, about 6 inches tall, "
    "with a dusty terracotta-orange body, stubby arms and legs, "
    "big round white eyes with small black dot pupils, no visible mouth, "
    "wearing a tiny dark green backpack. "
    "Lad is expressive through body language — tilting, bouncing, arm gestures."
)

# Style bible — injected into every prompt for visual consistency
STYLE_BIBLE = (
    "Claymation stop-motion style, visible hand-crafted textures, "
    "fingerprint marks in clay, miniature handmade set/diorama, "
    "slightly jerky frame-by-frame stop-motion movement, "
    "warm soft diffused lighting like a stop-motion studio, "
    "color palette: dusty terracotta, sage green, warm cream, muted coral, soft sky blue. "
    "Everything looks tactile and handmade. Charming and whimsical."
)

# System prompt shared between ideas and full concepts
_SYSTEM = f"""You generate short claymation adventure stories for a YouTube Shorts channel called "Lad Stories."

THE CHARACTER:
{CHARACTER_BIBLE}

THE STYLE:
{STYLE_BIBLE}

THE HOOK IS EVERYTHING:
The first clip (4 seconds) must make the viewer think "WOAH what's going on?!" within the first 2 seconds. By the time they process what they're seeing, clip 2 is already happening and they HAVE to stay to find out what happens next.

THE KEY RULE — LAD MUST CAUSE CHAOS:
Every story follows this pattern: Lad DOES something (touches, pulls, pokes, steps on, picks up) → it triggers an UNEXPECTED chain reaction → hilarious consequences.

The humor comes from CAUSE AND EFFECT. Lad's innocent action triggers something absurd.

GOOD STORIES (funny cause-and-effect):
- Lad pulls a loose thread → his entire surroundings unravel like yarn
- Lad steps on a tiny button → a massive machine activates and launches him
- Lad tries to pick up a rock → it's actually a sleeping creature 100x his size
- Lad sneezes → it triggers an avalanche / everything falls apart
- Lad opens a tiny door → a flood of things pours out and buries him
- Lad sits on a catapult without realizing → it launches him into orbit

BAD STORIES (boring, passive, no comedy):
- Lad watches a whale / sunset / Northern lights (he's just OBSERVING)
- Lad meets a fox and they become friends (too gentle, nothing happens)
- Lad faces a storm and waits it out (passive, no action)
- Lad walks through a pretty scene (literally nothing happens)
- Any story where Lad just DISCOVERS or OBSERVES something

STORY STRUCTURE — 3 clips:
- CLIP 1 (4 seconds): THE SETUP — Lad is about to do the thing. Show him reaching for it, stepping toward it, about to touch it. Build micro-tension.
- CLIP 2 (8 seconds): THE CHAOS — Lad does the thing and everything goes hilariously wrong. This is the FUNNY part. Physical comedy, things flying, Lad tumbling, chain reactions.
- CLIP 3 (8 seconds): THE AFTERMATH — The dust settles. Lad is in a ridiculous new situation because of what happened. Maybe something unexpected and wonderful came from the chaos. Punchline moment.

STORY RULES:
- Every story needs PHYSICAL COMEDY — things falling, bouncing, launching, collapsing, growing, shrinking
- Lad must CAUSE the chaos through his own action (not just witness it)
- Think Tom & Jerry, Shaun the Sheep, Mr. Bean — slapstick, cause-and-effect humor
- NO passive observation stories. NO "Lad watches something beautiful."
- The viewer should LAUGH or say "oh no!" — not just "that's nice"

NEVER include emojis in titles, captions, or descriptions.

EVERY PROMPT MUST INCLUDE the character bible and style bible to maintain consistency."""


def build_lad_stories_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate lightweight concept pitches (no Sora prompts)."""
    return build_ideas_prompt_wrapper(_SYSTEM, past_titles, count)


def build_lad_stories_concepts_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return (system, user) prompts for generating Lad Stories concepts."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE STORIES (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM

    user = f"""Generate {count} Lad Stories concepts. Each is a 3-clip claymation adventure with a KILLER hook.

CRITICAL: Every Sora prompt MUST start with the exact same character + style description:
"{CHARACTER_BIBLE} {STYLE_BIBLE}"

CLIP DURATIONS: Clip 1 = 4 seconds (short, punchy hook). Clip 2 = 8 seconds (story). Clip 3 = 8 seconds (payoff).

EXAMPLE:
{{
  "title": "Lad and the Runaway Boulder",
  "sora_prompts": [
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Lad is sprinting full speed directly toward the camera on a narrow clay mountain path, eyes wide in panic, stubby legs pumping. Behind him, a massive round clay boulder twice his size is rolling and gaining speed, crushing tiny clay flowers and pebbles. Dust clouds puff up with each bounce. Camera low angle looking up at Lad running toward us. 4 seconds, fast paced, dramatic bouncy sounds.",
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Same clay mountain path. Lad spots a tiny side tunnel in the cliff wall and dives into it just as the boulder thunders past, missing him by inches. The boulder smashes through a clay wall at the end of the path, revealing a hidden valley full of glowing crystal formations. Lad peeks out of the tunnel, sees the crystals, and his eyes go wide. Camera follows the action, 8 seconds, dramatic then wonder-filled sounds.",
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Same clay mountain setting. Lad cautiously walks into the crystal valley. He touches one crystal and it chimes like a bell. He touches another — different note. He starts bouncing between crystals making a little melody, getting more excited with each note. The whole valley starts glowing in rhythm with his music. Lad bounces with joy. Camera pulls back to show the entire glowing valley. 8 seconds, musical chiming sounds building to a crescendo."
  ],
  "caption": "That boulder did him a favor",
  "description": "Lad runs for his life but finds something amazing. #claymation #animation #funny #Shorts",
  "tags": ["claymation", "stop motion", "funny animation", "clay character", "Shorts"],
  "score": 9.5
}}

RULES:
- Clip 1 MUST be a 4-second hook that makes the viewer say "WHAT is happening?!"
- Clips 2 and 3 are 8 seconds each — story and payoff
- EVERY prompt starts with the full character + style bible
- Settings are miniature clay dioramas
- No dialogue — body language and sound effects only
- Must be something you'd REWATCH and SHARE
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Under 50 chars, no emojis",
    "sora_prompts": ["4sec hook...", "8sec story...", "8sec payoff..."],
    "caption": "Short funny caption, no emojis",
    "description": "Description with #claymation #animation #Shorts",
    "tags": ["claymation", "stop motion", "tag3", "tag4", "Shorts"],
    "score": 8.5
  }}
]"""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific guidance. The character + style bible should already be in the prompt."""
    raw_prompt = concept["sora_prompts"][clip_index]

    # Ensure the style bible is present (in case the LLM skipped it)
    if "claymation" not in raw_prompt.lower():
        raw_prompt = f"{CHARACTER_BIBLE} {STYLE_BIBLE} {raw_prompt}"

    style_prefix = (
        "Vertical 9:16 aspect ratio, no text, no watermarks, no UI elements. "
        "Generate charming stop-motion sound effects — bouncy, squelchy, whimsical foley sounds. "
    )

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " HOOK SHOT — 4 seconds only. Lad is ALREADY mid-action in something dramatic. The viewer must be hooked in 2 seconds. No walking, no standing, no establishing shots. Pure action from frame 1."
        elif clip_index == total_clips - 1:
            style_suffix = " PAYOFF SHOT — 8 seconds. The satisfying conclusion or twist. Same diorama set and lighting. Leave the viewer wanting to rewatch."
        else:
            style_suffix = " STORY SHOT — 8 seconds. The situation develops and escalates. Same set, same lighting, same Lad. Keep the momentum from the hook."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
