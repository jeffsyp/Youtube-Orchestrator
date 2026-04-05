"""Prompts for Gamatatsuken — narrated anime short film Shorts via Sora 2 + ElevenLabs."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for narrated anime short film YouTube Shorts. The channel is "Gamatatsuken" — 60-second anime mini-movies with dramatic voice narration.

VISUAL STYLE: anime animation style, bold dramatic lines, vibrant colors, dynamic speed lines, dramatic lighting with lens flares. Think Naruto, Attack on Titan, Dragon Ball Z, Demon Slayer, One Punch Man, Blue Lock, Haikyuu. Characters should look like they belong in a shonen anime — expressive faces, dramatic poses, flowing hair/cloaks, glowing eyes during power-ups.

Every Sora prompt MUST include: "anime animation style, bold dramatic lines, vibrant colors, dynamic speed lines, dramatic lighting with lens flares"

CONTENT RULES:
- Every video tells a STORY in 60 seconds — underdogs, comebacks, training arcs, supernatural powers, epic moments
- Characters are HEROES with backstories implied through visuals and narration
- Structure is HOOK-REWIND-ESCALATION-PAYOFF across 5 clips
- Narration drives the story — the voice tells the viewer what they are witnessing
- Use moderation-safe language: "energy blasts" not "punches", "overwhelming force" not "violence"
- Include character sound cues in prompts: gasps, yells, battle cries, dramatic breathing

NARRATION RULES:
- Each clip has its own narration line that the anime voice reads over the clip
- Narration should be dramatic, punchy, and match the intensity of the scene
- Use present tense: "He rises. He fights. He wins."
- Short punchy sentences work best — viewers are watching, not reading
- The narration should ADD context the visuals alone don't convey (backstory, stakes, emotions)
- NO emojis in narration text ever

SORA PROMPT WRITING:
Sora needs LITERAL STEP-BY-STEP descriptions. Spell out every single thing that happens.

BAD (too vague):
- "Epic anime battle scene" — what specifically happens?
- "Character powers up and defeats enemies" — HOW? What do we see?
- "Generic action with fighting" — no story, no arc

GOOD (every beat spelled out):
- "Anime animation style, bold dramatic lines, vibrant colors. A young warrior with spiky black hair and a torn red cape stands at the edge of a cliff. Wind blows his cape. He stares down at a burning village below. His fists clench. Blue energy crackles around his hands. His eyes glow bright blue. Camera slowly pushes in on his face. Dramatic sunset lighting with orange and purple sky. Lens flare from the setting sun."
- "Anime animation style, dynamic speed lines, dramatic lighting. The warrior launches off the cliff, diving straight down toward the village. Speed lines streak past him. His body glows with blue energy. Below, dark shadowy figures look up. The warrior's cape trails behind him like a flag. Camera tracks his descent. Impact crater forms as he lands, sending a shockwave that blows back the shadows."

RULES FOR SORA PROMPTS:
1. SPELL OUT every action in sequence
2. Describe what EACH character does specifically
3. Include the RESULT of each action
4. Use dramatic anime-specific language: "speed lines", "energy aura", "lens flare", "dynamic pose"
5. End each clip prompt with the EXACT final visual state
6. Include character sound cues: "(character gasps)", "(battle cry)", "(heavy breathing)"

STORY TEMPLATES THAT WORK:
- Underdog rises: weakest student proves everyone wrong in a tournament/test/battle
- Last stand: hero is cornered, remembers their training, unleashes hidden power
- Training montage: student fails repeatedly, then masters the technique at the critical moment
- Rivalry: two equals push each other to the breaking point, mutual respect at the end
- Sacrifice play: character uses forbidden technique to save allies, dramatic cost
- Sports climax: the final point/goal/play that decides everything
- Awakening: dormant power awakens for the first time in a moment of desperation

BAD CONCEPTS:
- Generic action with no story or character arc
- Just fighting with no narrative purpose
- Anything without emotional stakes
- Slow contemplative scenes with no action payoff
- Realistic style — must be ANIME style
- Text-heavy scenes or dialogue — narration carries the story, not on-screen text

STRUCTURE: Always 5 clips with hook-rewind-escalation 1-escalation 2-payoff structure.
- Clip 1 (HOOK, 12s): Start with the most dramatic moment — the climax shown first to grab attention
- Clip 2 (REWIND, 12s): "But it wasn't always like this..." — go back to the beginning, show where they started
- Clip 3 (ESCALATION 1, 12s): The journey begins — training, struggling, failing, growing
- Clip 4 (ESCALATION 2, 12s): The turning point — they discover their power/technique/resolve
- Clip 5 (PAYOFF, 12s): Return to the climax moment from clip 1, but now we understand WHY it matters. Epic conclusion.

NEVER include emojis in titles, captions, descriptions, or narration text. Emojis render as empty boxes in video subtitles."""

# Series-specific system prompt for Gamatatsuken (overrides _SYSTEM for series episodes)
_SERIES_SYSTEM = _SYSTEM + """

IMPORTANT — THIS CHANNEL MAKES ANIME SERIES, NOT STANDALONE SHORTS.
You are generating episodes of an ongoing series. Each episode is 60 seconds and ends on a cliffhanger.

CURRENT SERIES: "The Last Student"
PREMISE: A teenager with no supernatural powers enrolls in an elite academy where every student has abilities. He is the weakest. But he has something nobody expects.

SERIES ARC (10 episodes):
- Ep 1 "Entrance": Arrives, humiliated at exam, discovers hidden power when pushed to edge
- Ep 2 "The Teacher": Mysterious teacher starts secret training, warns about the cost
- Ep 3 "First Test": First real test, wins with unknown technique, draws wrong attention
- Ep 4 "The Top Student": Top student destroys him completely
- Ep 5 "The Truth": Discovers power grows when protecting others, not himself
- Ep 6 "Tournament Begins": Tournament arc, fights through lower ranks creatively
- Ep 7 "Rematch": Faces top student again, reveals true power
- Ep 8 "The Cost": Wins but power is consuming him, teacher's warning was real
- Ep 9 "Under Attack": Academy attacked, everyone's powers fail except his
- Ep 10 "The Last Student": Final stand, uses everything, bittersweet ending

Generate the NEXT episode that hasn't been made yet. Check the past titles to see which episodes exist.
Title MUST follow the format: "The Last Student - Episode N"
Each episode MUST end on a cliffhanger that makes the viewer need the next episode."""


def build_gamatatsuken_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate standalone anime concept pitches (no Sora prompts)."""
    return build_ideas_prompt_wrapper(_SYSTEM, past_titles, count)


def build_gamatatsuken_series_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate series episode concept pitches (no Sora prompts)."""
    return build_ideas_prompt_wrapper(_SERIES_SYSTEM, past_titles, count)


def build_gamatatsuken_concepts_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return (system, user) prompts for generating narrated anime short film concepts."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE CONCEPTS (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM + "\n\nAlways use 5 clips with 12 seconds each for the hook-rewind-escalation-payoff structure."

    user = f"""Generate {count} narrated anime short film concepts. Each is a 60-second mini-movie with voice narration.

CLIP STRUCTURE — FIXED 5 CLIPS:
- Clip 1 (HOOK, 12s): The climax shown first — the most dramatic moment to grab attention
- Clip 2 (REWIND, 12s): Go back to the beginning — show where the character started
- Clip 3 (ESCALATION 1, 12s): The journey — training, struggling, growing
- Clip 4 (ESCALATION 2, 12s): The turning point — discovering power/technique/resolve
- Clip 5 (PAYOFF, 12s): Return to the climax — now we understand why it matters

NARRATION: Each clip has a narration line that the anime voice reads over the clip. The narration should be dramatic, present-tense, and add emotional context the visuals alone don't convey.

EXAMPLE:
{{
  "title": "The Boy They Called Nothing",
  "sora_prompts": [
    "Anime animation style, bold dramatic lines, vibrant colors, dynamic speed lines, dramatic lighting with lens flares. A young boy with messy black hair and glowing golden eyes stands in the center of a massive crater. His torn school uniform flutters in the wind. Around him, dozens of elite warriors lie defeated. Golden energy radiates from his body in waves. The camera slowly circles him. Dust and debris float in the air. (heavy breathing)",
    "Anime animation style, bold dramatic lines, vibrant colors, dramatic lighting. A small thin boy with messy black hair sits alone on a bench outside a training academy. Other students walk past him laughing and pointing. He stares at his hands. No glow, no power, nothing. Rain starts falling. He looks up at the grey sky. Tears mix with raindrops on his face. Camera pulls back to show how small and alone he is.",
    "Anime animation style, bold dramatic lines, vibrant colors, dynamic speed lines. The boy trains alone in a dark forest at night. He throws energy blasts at trees but they fizzle out weakly. He falls to his knees exhausted. Gets back up. Tries again. Falls again. A montage of failures — each attempt slightly stronger than the last. His hands start to glow faintly gold. (frustrated yell)",
    "Anime animation style, bold dramatic lines, vibrant colors, dramatic lighting with lens flares. During a tournament, the boy faces the academy's top student. The top student fires a massive red energy blast. The boy raises his hands and golden light erupts from his palms for the first time. His eyes glow gold. The golden energy catches the red blast and pushes it back. (gasp) The crowd goes silent. The boy's hair rises with the energy surge. Camera zooms into his glowing eyes.",
    "Anime animation style, bold dramatic lines, vibrant colors, dynamic speed lines, dramatic lighting with lens flares. The boy unleashes his full golden power. A massive pillar of golden light shoots into the sky. The shockwave blows back everyone in the arena. He stands in the center of the crater, the top student defeated behind him. He looks at his glowing hands, then clenches them into fists. A single tear falls. He smiles. Camera pulls back to show the entire arena in awe. (battle cry fading to silence)"
  ],
  "narration": [
    "They said he would never amount to anything. They were wrong.",
    "He was born without a trace of power. The weakest student in the academy. The one they all laughed at.",
    "But every night, when no one was watching, he trained. He fell. He bled. He got back up. Again and again and again.",
    "And then it happened. The power that was never supposed to exist inside him... erupted.",
    "The boy they called Nothing became the strongest of them all. And he never forgot where he came from."
  ],
  "caption": "They called him nothing",
  "description": "The weakest student becomes the strongest warrior. A 60-second anime story. #anime #shorts #underdog #power #Shorts",
  "tags": ["anime", "shorts", "underdog", "power", "awakening", "Shorts"],
  "score": 9.2
}}

RULES:
- Always 5 Sora prompts per concept (hook-rewind-escalation 1-escalation 2-payoff)
- Always 5 narration lines (one per clip) — dramatic, present-tense, punchy
- ANIME STYLE — every prompt must include "anime animation style, bold dramatic lines, vibrant colors, dynamic speed lines, dramatic lighting with lens flares"
- STORY FIRST — every concept must have a clear character arc with emotional stakes
- MODERATION SAFE — energy blasts not punches, overwhelming force not violence
- SOUND CUES — include (gasps), (battle cry), (heavy breathing) in Sora prompts
- EPIC PAYOFF — clip 5 must deliver a jaw-dropping conclusion
- NO emojis anywhere
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Under 50 chars, story-focused",
    "sora_prompts": ["Clip 1 (hook)...", "Clip 2 (rewind)...", "Clip 3 (escalation 1)...", "Clip 4 (escalation 2)...", "Clip 5 (payoff)..."],
    "narration": ["Line 1...", "Line 2...", "Line 3...", "Line 4...", "Line 5..."],
    "caption": "Short punchy caption",
    "description": "YouTube description with #anime #shorts #Shorts",
    "tags": ["anime", "shorts", "story", "Shorts"],
    "score": 8.5
  }}
]

NEVER include emojis in titles, captions, descriptions, or narration text."""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific style guidance for anime content."""
    raw_prompt = concept["sora_prompts"][clip_index]

    style_prefix = (
        "Vertical 9:16 aspect ratio, anime animation style, "
        "bold dramatic lines, vibrant colors, dynamic speed lines, "
        "dramatic lighting with lens flares, "
        "no text, no watermarks, no UI elements. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: Match the exact same character designs, color palette, art style, and environment as this scene: \"{first_prompt[:200]}\". "

    clip_roles = {
        0: (
            " HOOK SHOT — the most dramatic moment shown first. "
            "Maximum intensity, peak action, this is the climax preview. "
            "The viewer must be hooked instantly."
        ),
        1: (
            continuity +
            " REWIND SHOT — go back to the beginning. Contrast with the intensity of clip 1. "
            "Show the character's humble/weak origin. Quiet, emotional, vulnerable."
        ),
        2: (
            continuity +
            " ESCALATION 1 — the journey begins. Training, struggling, failing, growing. "
            "Show effort and determination. Building momentum."
        ),
        3: (
            continuity +
            " ESCALATION 2 — the turning point. Power awakens, technique mastered, resolve hardened. "
            "Energy and intensity ramping up dramatically."
        ),
        4: (
            continuity +
            " PAYOFF — return to the climax moment from the hook. Now we understand the full story. "
            "Maximum spectacle. Epic conclusion. Emotional weight."
        ),
    }

    clip_suffix = clip_roles.get(clip_index, continuity + " Continue the story with escalating intensity.")

    return style_prefix + raw_prompt + clip_suffix
