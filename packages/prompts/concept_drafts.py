"""Prompt builder for auto-generating concept drafts per channel.

Two-phase generation:
1. build_concept_pitches_prompt — generates concept pitches (title, brief, structure)
2. build_script_prompt — writes the full beat-by-beat script for one pitch
"""


def build_concept_pitches_prompt(
    channel_name: str,
    niche: str,
    past_titles: list[str],
    count: int = 5,
    trending: str = "",
) -> tuple[str, str]:
    """Phase 1: Generate concept pitches — just ideas + structure, no full scripts yet."""
    past_block = ""
    if past_titles:
        titles_list = "\n".join(f"- {t}" for t in past_titles[-100:])
        past_block = f"""
ALREADY MADE OR REJECTED (do NOT repeat these or anything too similar):
{titles_list}
"""

    trending_block = ""
    if trending:
        trending_block = f"""
{trending}

Study these titles. They went viral as shorts. Ask yourself WHY each one worked — what made someone click, watch the whole thing, and share it. Use that understanding to create concepts that tap into the same psychology. Do NOT copy these titles. Create original concepts INSPIRED by what's working.
"""

    system = f"""You pitch YouTube Shorts concepts for "{channel_name}" — a channel about {niche}.

YOUR GOAL: Maximum watch time. The #1 metric is Average View Duration (AVD%). Over 100% means viewers are looping. Every concept must keep viewers watching until the end AND wanting to rewatch.

You are ONLY pitching ideas right now — NOT writing full scripts. For each concept, describe:
1. The title (ALL CAPS) — must be SIMPLE and CLEAR. The viewer should instantly know what the video is about. "HOW GPS ACTUALLY WORKS" not "GPS DOESN'T KNOW WHERE YOU ARE — YOU FIGURE IT OUT YOURSELF". Don't be clever, be obvious.
2. A one-sentence pitch — why will someone watch this to the end?
3. The story structure — what happens beat by beat in 2-3 sentences. Setup → escalation → punchline.
4. Why it works — what psychological hook keeps them watching? (curiosity gap, escalating stakes, identity/tribalism, shock value, etc.)

THESE ARE 20-30 SECOND VIDEOS. Scope accordingly:
- ONE idea. ONE twist. ONE punchline. That's all you have time for.
- A viewer on their phone should instantly get it with zero effort
- If the concept needs a paragraph to explain, it's too complex for a Short

WHAT MAKES A GOOD CONCEPT:
- The viewer must instantly understand what the video is about from the title/first beat
- There must be a reason to watch until the END — a reveal, a twist, an answer
- It should make people REACT — shock, disbelief, "no way", tag a friend
- It should work for someone who knows NOTHING about the topic
- Simple enough for a 10 year old to follow

WHAT TO AVOID:
- Vague openings that need context ("everyone argues this" — argues WHAT?)
- Info dumps or complex explanations — if it needs a diagram, it's not a Short
- Topics only fans/experts would care about
- Concepts that need more than 30 seconds to land — save those for long-form

OUTPUT — return a JSON array of {count} pitches:
[
  {{
    "title": "ALL CAPS TITLE",
    "brief": "One sentence — why will someone watch this to the end",
    "key_facts": "The SPECIFIC real details the script writer needs to tell this story accurately. Include: real names, real dates, real places, real numbers, what actually happened step by step. The script writer will ONLY know what you put here — if you leave out a name, the script will say 'a player' instead of the actual name. Be thorough.",
    "structure": "Setup: [specific detail] → Escalation: [specific detail] → Punchline: [specific detail]",
    "hook_type": "curiosity_gap|escalation|identity|shock|ranking|debate"
  }}
]

Return ONLY valid JSON, no markdown."""

    user = f"""Pitch {count} YouTube Shorts concepts for "{channel_name}" ({niche}).

{trending_block}
{past_block}

Return {count} concept pitches. Just ideas and structure — no full scripts yet. Focus on concepts where the viewer HAS to watch until the end."""

    return system, user


def build_script_prompt(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    title: str,
    brief: str,
    structure: str,
    key_facts: str = "",
) -> tuple[str, str]:
    """Phase 2: Write narration-only script for one concept pitch.

    Visuals are planned later AFTER narration is generated and timestamped.
    """

    system = f"""You are a scriptwriter for "{channel_name}" — a YouTube Shorts channel about {niche}.

You've been given a concept that was approved. Your job is to write ONLY the narration — every word that will be spoken aloud. A separate visual director will plan the visuals AFTER hearing the narration with exact timestamps.

YOUR GOAL: Maximum watch time. Every word must earn its place.

WRITING RULES:
- SHORTER IS BETTER. Aim for under 30 seconds. 45 seconds max. Only go above 45 in extreme cases where the story genuinely cannot be told shorter. Most shorts should be 5-8 narration lines. If you wrote 10+ lines, you almost certainly over-wrote it — go back and cut. Every word must earn its place.
- Each narration line = one visual on screen. One sentence per line, not a paragraph. More lines = more visual cuts = more stimulating.
- A viewer scrolling on their phone should be able to follow this with ZERO effort. If they have to think hard or rewind to understand, you've lost them.
- Simple language. Simple structure. Setup → twist → punchline. That's it.
- BE FUNNY. But remember — this is read by an AI voice with zero comic timing. The humor must come from the WORDS AND SITUATION, not delivery. Absurd imagery, unexpected comparisons, escalating ridiculousness, and "wait that actually happened?" moments work. Dry wit and sarcasm do NOT work — they need vocal inflection that AI can't do.
  GOOD: "Your team celebrated. Your bot lane typed 'nice.' And then Tryndamere killed your entire backline from beyond the grave." (funny because of the situation)
  BAD: "Your screen said he was dead. He was not dead." (needs delivery to be funny, AI reads it flat)
- Line 1 MUST talk directly TO the viewer and make them want to keep watching. Not a statement — a question, a challenge, or a direct address. "Do you know why every clock in every ad shows 10:10? Let me show you." not "Clocks in ads always show 10:10." "Nile Crocodile vs Bull Shark — who wins?" not "The Nile River is home to many predators." Start like you're talking TO someone, not reading an article.
- Every line must make complete sense on its own — zero context, they didn't read the title
- Build to one payoff. Not three. Not five. ONE moment that makes them go "wait what?"
- Every line must add NEW information. Never repeat the same beat twice ("Riot said nothing" then "Riot still said nothing" = same beat). No setup, no background, no explaining context the viewer doesn't need. If you can combine two lines into one without losing anything, do it. Tell the story once and move on.
- Final line = PUNCHLINE. End at the peak with humor or shock. Never trail off, never summarize
- Use real names and real details — but only the ones that matter. Don't dump every fact. Pick the 2-3 details that make the story hit.
- ALWAYS use the specific name of things. "Litwick" not "a candle Pokemon." "A lionfish" not "a fish." "Walter Moody Jr." not "a lawyer." Every time you reference something, use its actual name so the visuals can show the right thing.
- If you can say it in fewer words, do. "He ate his own son" hits harder than "He proceeded to cook and serve his own child to the assembled deities at the feast"
- Write like someone excitedly telling a friend, NOT like a script being read:
  - Add natural reactions and transitions: "Believe it or not", "Here's the thing", "And get this"
  - Connect thoughts the way people actually talk — don't just list facts as separate bullets
  - Use "..." for pauses
  - Mix short and long. "No body. No phone. Nothing." then a longer sentence for flow.
  - BAD: "In 2012, every champion became free. All 100 of them. Not a sale. Riot pushed a patch."
  - GOOD: "In 2012, every single League of Legends champion became free! Believe it or not, all 100 of them. This wasn't a sale or event or something. Riot just pushed a patch and broke the entire game."
  - The BAD version sounds like reading a list. The GOOD version sounds like a person talking.
- Do NOT drag out words ("coool", "actuallllly") — AI voice can't do this naturally
- Do NOT use ALL CAPS for emphasis — AI voice reads them the same
- No formal filler: no "well", "you see", "interestingly", "it should be noted"
- No emojis in narration — they break the subtitle rendering

THINK ABOUT THE VISUALS while writing — even though you're not planning them. Write narration that CREATES visual moments:
- "and then the whole building just... collapsed" — gives the visual director a clear moment to time an explosion
- "five... four... three..." — creates natural visual cut points
- Describe things the viewer can SEE, not abstract concepts

OUTPUT — return a JSON object:
{{
  "title": "{title}",
  "narration": [
    "First line of narration — the hook",
    "Second line — development",
    "Third line — escalation",
    "Final line — the punchline"
  ],
  "caption": "YouTube description — one compelling line that makes people want to watch. Include 5-8 hashtags that someone interested in this content would search for. Mix broad (#shorts #viral) with specific (#leagueoflegends #pokemon etc). Example: 'Tryndamere was unkillable for 8 years and Riot just left it. #leagueoflegends #riotgames #gaming #shorts #lol #tryndamere #gamingfacts'",
  "tags": ["specific_tag", "broader_tag", "niche_tag", "shorts"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Write the narration for this approved concept:

TITLE: {title}
PITCH: {brief}
KEY FACTS: {key_facts}
STRUCTURE: {structure}

Write ONLY the words that will be spoken. No visual descriptions. Use the KEY FACTS — these are the real details that make the story specific and credible. Name the actual people, places, dates, and numbers. Make every line sound like someone excitedly telling a story at a party. The visual director will handle everything else AFTER hearing your narration."""

    return system, user


# Kids channel IDs — use dedicated prompts
KIDS_CHANNELS = {38}  # Blanket Fort Cartoons


def build_kids_pitches_prompt(
    channel_name: str,
    niche: str,
    past_titles: list[str],
    count: int = 5,
    trending: str = "",
) -> tuple[str, str]:
    """Pitch concepts for kids cartoon channels — animal characters, silly adventures."""
    past_block = ""
    if past_titles:
        titles_list = "\n".join(f"- {t}" for t in past_titles[-100:])
        past_block = f"""
ALREADY MADE (do NOT repeat):
{titles_list}
"""

    system = f"""You pitch YouTube Shorts for "{channel_name}" — a kids cartoon channel.

You create SHORT animated stories (30-50 seconds) starring cute animal characters on silly adventures. Think Bluey, Peppa Pig, Bluey's style of humor that kids AND parents enjoy.

RECURRING CHARACTERS (use these — don't invent new ones every time):
- **Biscuit** — a golden retriever puppy, always excited, runs into things, thinks everything is the best thing ever
- **Mochi** — a round little cat, cautious and skeptical, the straight man to everyone else's chaos
- **Pip** — a tiny frog, brave beyond his size, terrible at planning, great at improvising
- **Waffles** — a duck, says obvious things like they're profound wisdom, accidentally helpful

You can use 2-3 characters per story. Not all four every time.

WHAT WORKS FOR KIDS SHORTS:
- ONE simple situation with a funny outcome. "Biscuit tries to catch a butterfly" not an epic quest.
- Physical comedy — falling, bumping, things going hilariously wrong
- Silly misunderstandings — Pip thinks a puddle is the ocean
- Unexpected solutions — the "wrong" approach somehow works
- Gentle lessons learned through funny situations (but NEVER preach)
- Repetition that builds (try, fail bigger, fail BIGGEST, then succeed in a silly way)

WHAT TO AVOID:
- Scary, mean, or sad content
- Complex plots — if it needs explaining, it's too much
- Pop culture references kids won't get
- Morals delivered like a lecture

OUTPUT — return a JSON array of {count} pitches:
[
  {{
    "title": "SHORT FUN TITLE",
    "brief": "One sentence — what's the silly situation?",
    "key_facts": "Which characters, what they're trying to do, what goes wrong, and the funny ending",
    "structure": "Setup → funny problem → escalation → silly resolution",
    "hook_type": "silly_situation"
  }}
]

Return ONLY valid JSON, no markdown."""

    user = f"""Pitch {count} kids cartoon shorts for "{channel_name}".

{past_block}

Make them simple, silly, and fun. Each story stars 2-3 of the animal characters (Biscuit, Mochi, Pip, Waffles). One situation, one funny payoff."""

    return system, user


def build_kids_script_prompt(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    title: str,
    brief: str,
    structure: str,
    key_facts: str = "",
) -> tuple[str, str]:
    """Write a kids cartoon narration — storybook style, simple words, silly fun."""

    system = f"""You write narration for "{channel_name}" — animated YouTube Shorts for little kids.

You're writing a storybook that gets read aloud over cute cartoon visuals. A child's voice reads it. Think: the narrator in Peppa Pig or the warm storytelling in Bluey.

THE CHARACTERS:
- **Biscuit** — golden retriever puppy, over-excited about everything
- **Mochi** — round cautious cat, skeptical face, reluctant adventurer
- **Pip** — tiny brave frog, no plan, all heart
- **Waffles** — duck, says obvious things wisely, accidentally helpful

WRITING RULES:
- Write like a storybook being read aloud to a 4 year old
- Short simple sentences. "Biscuit found a box. A really big box. The biggest box he had EVER seen."
- Use the character names constantly — kids need to know who's doing what
- Sound effects in narration are great: "SPLASH!", "BONK!", "Wheeeee!"
- Repetition is GOOD for kids. Try something three times, each time funnier.
- Each line = one visual moment. Keep lines short so visuals change often.
- 6-9 narration lines total. Aim for under 30 seconds, 45 max.
- Narrator speaks in third person: "Biscuit looked at the puddle. It was very big." NOT "I looked at the puddle."
- End with something funny and warm. Not a moral — a punchline. "And Biscuit? Biscuit was already asleep."
- No complex words. No sarcasm. No mean humor. Everything is gentle and silly.
- The humor comes from: characters being silly, things going wrong in funny ways, sound effects, exaggerated reactions

OUTPUT — return a JSON object:
{{
  "title": "{title}",
  "narration": [
    "First line — set the scene simply",
    "More lines building the silly situation",
    "Funny ending"
  ],
  "caption": "Short fun description with kid-friendly hashtags. Example: 'Biscuit found the biggest puddle ever! #kidscartoon #animation #funnycartoon #shorts #cute #storytime #bedtimestory'",
  "tags": ["kids", "cartoon", "animation", "shorts", "funny", "storytime"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Write the storybook narration for this kids cartoon:

TITLE: {title}
WHAT HAPPENS: {brief}
DETAILS: {key_facts}
STRUCTURE: {structure}

Write it like a warm, funny storybook. Simple words. Silly moments. Sound effects welcome. The visuals will be cute colorful cartoon animals."""

    return system, user


# No-narration channel IDs
MEME_CHANNELS = {37}  # Thats A Meme
SATISFYING_CHANNELS = {36}  # Very Clean Very Good
NO_NARRATION_CHANNELS = MEME_CHANNELS | SATISFYING_CHANNELS


def build_no_narration_prompt(
    channel_name: str,
    niche: str,
    past_titles: list[str],
    channel_id: int,
    count: int = 5,
    trending: str = "",
) -> tuple[str, str]:
    """Generate complete no-narration concepts (memes or satisfying) in one shot.

    Returns concepts with scenes[] instead of narration[].
    """
    past_block = ""
    if past_titles:
        titles_list = "\n".join(f"- {t}" for t in past_titles[-100:])
        past_block = f"""
ALREADY MADE OR REJECTED (do NOT repeat these or anything too similar):
{titles_list}
"""

    trending_block = ""
    if trending:
        trending_block = f"""
{trending}

Study these. What made them go viral? Use that psychology — don't copy.
"""

    is_meme = channel_id in MEME_CHANNELS

    if is_meme:
        style_guidance = """MEME FORMAT RULES:
- Each video has 2-3 scenes that tell a visual joke. NO voiceover. NO narration.
- Text is BAKED INTO the image by the image generator. Keep text SHORT (max 2 lines, ~8 words per line).
- The text goes at the top of the image. The image shows the funny situation.
- Art style: Intentionally crude drawing style like MS Paint or early internet memes. Wobbly lines, flat colors, no shading. Characters are simple with round heads and basic expressions. Think classic internet meme energy — ugly on purpose, funny because of it.
- The humor comes from the VISUAL GAP between what the text says and what the image shows, or from escalating absurdity across scenes. Dry humor, deadpan situations.
- Scene 1 sets up the situation. Scene 2 (and optionally 3) is the punchline — the absurd/relatable thing that happens.
- These are RELATABLE memes. The viewer should think "that's literally me" or tag a friend.
- Topics: gaming fails, daily life struggles, work/school moments, relationship dynamics, pet behavior, social media, cooking disasters.

GOOD MEME: Text "when you say 'one more game' at midnight" → Scene 1: guy at desk, clock shows 12am → Scene 2: same guy, clock shows 6am, dark circles, 5 empty energy drinks
BAD MEME: Text "gaming is fun sometimes" → Generic gamer at desk (not specific, not funny, no escalation)"""

        scene_format = """Each scene needs:
- "image_prompt": Full prompt for gpt-image-1.5 INCLUDING the text to bake in. Format: "Intentionally crude drawing style like MS Paint or early internet memes. Wobbly lines, flat colors, no shading, simple characters with round heads and basic expressions. Text at top: '[YOUR TEXT HERE]'. [Description of the funny scene]."
- "video_prompt": Short animation direction. Keep it subtle — character reacts, object moves, expression changes. 1 sentence.
- "duration": 3-5 seconds per scene."""
    else:
        style_guidance = """SATISFYING VIDEO RULES:
- Pure visual dopamine. NO text. NO voiceover. Just mesmerizing visuals.
- EXACTLY 3-4 scenes. No more. Keep it tight — 15-20 seconds total.
- Types that work: cutting/slicing objects, perfect fits, symmetry, fluid dynamics, squishy/soft body, peeling, pouring, melting, folding, stacking.
- Make it SPECIFIC — not "satisfying cutting" but "a crystal-clear ice sphere being sliced in half with a hot knife, water droplets catching light."
- Art should be photorealistic with slight AI flair (unusual materials, impossible physics, perfect symmetry).
- Each scene should be slightly more satisfying than the last — build to a climax.
- The last scene should be the most satisfying moment."""

        scene_format = """Each scene needs:
- "image_prompt": Photorealistic prompt for the starting frame. Detailed, specific materials and lighting.
- "video_prompt": What happens in the animation — the satisfying action. Be specific about the movement.
- "duration": 4-5 seconds per scene. Total video should be 15-20 seconds."""

    system = f"""You create viral no-narration YouTube Shorts for "{channel_name}" — {niche}.

{style_guidance}

{scene_format}

OUTPUT — return a JSON array of {count} complete concepts:
[
  {{
    "title": "ALL CAPS TITLE",
    "brief": "One sentence — why will someone watch/share this",
    "scenes": [
      {{
        "image_prompt": "Full image generation prompt",
        "video_prompt": "Animation direction",
        "duration": 4
      }}
    ],
    "caption": "YouTube description with 5-8 hashtags",
    "tags": ["tag1", "tag2", "shorts"],
    "narration_style": "none",
    "channel_id": {channel_id},
    "format_version": 2
  }}
]

Return ONLY valid JSON, no markdown."""

    user = f"""Create {count} viral no-narration Shorts for "{channel_name}" ({niche}).

{trending_block}
{past_block}

Each concept must be complete with all scenes ready to generate. Make them scroll-stopping."""

    return system, user
