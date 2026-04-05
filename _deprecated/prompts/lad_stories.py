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

GOOD STORIES (absurd, funny, story-driven):
- Lad robs a bank with his pet fish — fish flops out of the bag and triggers the alarm
- Lad tries to park a shopping cart — it rolls away and causes a chain reaction across the whole store
- Lad finds a remote control — presses a button and launches himself through the roof
- Lad tries to cook dinner — each ingredient explodes bigger than the last until the kitchen is gone
- Lad enters a talent show — his act accidentally destroys the stage but the audience loves it
- Lad tries to return a library book — the library fights back, shelves attack, books fly everywhere
- Lad orders pizza — a portal opens instead and things start falling out of it
- Lad tries to sit in a chair — the chair runs away, more chairs appear, chaos ensues

THE KEY: absurd SITUATIONS + escalating CHAOS + ironic PUNCHLINES. Not "Lad encounters nature."

BAD STORIES (boring, passive, no comedy) — AUTOMATIC SCORE BELOW 5:
- Lad watches a whale / sunset / Northern lights (he's just OBSERVING)
- Lad meets an animal and they become friends (too gentle, nothing happens)
- Lad faces a storm and waits it out (passive, no action)
- Lad walks through a pretty scene (literally nothing happens)
- Any story where Lad just DISCOVERS or OBSERVES something
- "Lad and the [nature thing]" — sleeping giant, river of stars, melting sun = BORING
- Any story where the main event is something HAPPENING TO Lad that he passively endures
- Any story that could be described as "Lad goes somewhere and sees something cool"

THE LITMUS TEST — ask yourself:
1. Does Lad DO something that causes a chain reaction? If no → REJECT
2. Would this make someone LAUGH out loud? If no → REJECT
3. Is there a clear PUNCHLINE or twist at the end? If no → REJECT
4. Could you describe this story to a friend and they'd say "haha what?!" If no → REJECT

STORY STRUCTURE — 3 clips:
- CLIP 1 (4 seconds): THE SETUP — Lad is about to do the thing. Show him reaching for it, stepping toward it, about to touch it. Build micro-tension. ACTION FROM FRAME 1.
- CLIP 2 (8 seconds): THE CHAOS — Lad does the thing and everything goes hilariously wrong. This is the FUNNY part. Physical comedy, things flying, Lad tumbling, chain reactions. ESCALATION IS KEY — it gets worse and worse.
- CLIP 3 (8 seconds): THE PUNCHLINE — The dust settles and the twist lands. Lad is in a ridiculous situation. The viewer LAUGHS. Maybe something ironic happened. This clip must deliver a clear comedic payoff.

STORY RULES:
- Every story needs PHYSICAL COMEDY — things falling, bouncing, launching, collapsing, growing, shrinking, exploding
- Lad must CAUSE the chaos through his own action (not just witness it)
- Think Tom & Jerry, Shaun the Sheep, Mr. Bean, Wile E. Coyote — slapstick, cause-and-effect humor, ESCALATION
- NO passive observation stories. NO "Lad watches something beautiful." NO atmospheric mood pieces.
- The viewer should LAUGH or say "oh no!" — not just "that's nice" or "that's pretty"
- ESCALATION: each clip must be more chaotic/funny than the last — the situation gets worse before the punchline
- IRONY: the best endings are ironic — Lad causes a huge disaster trying to do something simple

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
  "title": "Lad Tries to Return a Library Book",
  "sora_prompts": [
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Lad is standing in front of a tiny clay library building, holding a huge clay book almost bigger than himself, struggling to carry it. He pushes open the tiny door and squeezes inside. The door slams behind him ominously. 4 seconds, creaky door sound, comedic grunting.",
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Same clay library interior with tiny bookshelves. Lad tries to slide the book back onto a shelf but it doesn't fit. He pushes harder — the entire bookshelf tips backward like a domino into the next shelf, which hits the next, causing a massive chain reaction. Books fly everywhere, shelves collapse one after another, a globe rolls across the floor and smashes through a window. Lad stands frozen in the middle of the growing disaster, arms still outstretched. 8 seconds, escalating crashes and thuds.",
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Same clay library, now completely destroyed — books piled everywhere, shelves toppled, dust settling. Lad is buried up to his neck in fallen books. A tiny clay librarian figure appears, stamps OVERDUE on Lad's forehead, and walks away. Lad blinks. 8 seconds, comedic stamp sound, defeated silence."
  ],
  "caption": "The late fee was the least of his problems",
  "description": "Lad just wanted to return a book. The library had other plans. #claymation #animation #funny #Shorts",
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
