"""Prompts for long-form YouTube videos (8-15 minutes, landscape 1920x1080).

Three prompt builders:
1. build_longform_pitches_prompt — concept pitches with chapter outlines
2. build_longform_chapter_script_prompt — narration for one chapter at a time
3. build_longform_visual_batch_prompt — visual plan for a batch of narration lines
"""


def build_longform_pitches_prompt(
    channel_name: str,
    niche: str,
    past_titles: list[str],
    count: int = 3,
    trending: str = "",
) -> tuple[str, str]:
    """Phase 1: Generate long-form concept pitches with chapter outlines."""
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

Study these titles. They went viral. Ask yourself WHY — what made someone click and watch 10+ minutes. Use that psychology. Do NOT copy titles.
"""

    system = f"""You pitch long-form YouTube video concepts for "{channel_name}" — a channel about {niche}.

YOUR GOAL: A 10-13 minute video with maximum watch time. The first 60 seconds decides everything — 55% drop off in the first minute. After that, open loops and pattern interrupts keep them.

THE VIDEO IS 10-13 MINUTES. Not 20. Not 30. Not 45. A tight, focused 10-13 minute story. Think of it as telling a GREAT story at a dinner party — you wouldn't ramble for 45 minutes. You'd tell the tight version that keeps everyone leaning in.

You are ONLY pitching ideas — NOT writing scripts. For each concept:
1. Title (compelling, curiosity-driven)
2. One-sentence pitch — why will someone watch 10+ minutes of this?
3. Chapter outline (5 chapters) with timing targets that ADD UP TO 10-13 MINUTES
4. Open loops — at least 3 questions/mysteries planted early that pay off later
5. Key facts — the ESSENTIAL real details (names, dates, places, numbers). Only what the story actually needs — not an encyclopedia dump
6. Why it works — what psychological hooks sustain attention

CHAPTER STRUCTURE — 5 chapters, 10-13 minutes total:
- Hook (0:00-0:30): Tease the most dramatic moment. Drop them into the peak.
- Context (0:30-2:30): Set up the world. Who, where, when. Plant first open loop.
- Core (2:30-7:30): The meat. 2-3 escalating turns. Each turn has a mini-payoff.
- Climax (7:30-10:30): Everything converges. The biggest reveal/twist/payoff.
- Resolution (10:30-12:00): Aftermath + one final surprising detail. End strong.

SCOPE THE STORY TO FIT:
- Pick ONE compelling thread through the topic, not every detail that exists
- A great 12-minute video tells ONE story well, not three stories badly
- If there are 50 interesting facts, pick the 8 that build the best narrative arc
- Cut anything that doesn't serve the central tension or payoff
- The chapter timings MUST add up to 10-13 minutes. If they add up to more, the story scope is too wide — narrow it

DEPTH TEST: The topic must sustain 10 minutes WITHOUT padding, but it shouldn't need 30 minutes either. If you can't tell it in under 15 minutes, narrow the focus.

BEST TOPICS: mysteries, true crime, history deep dives, conspiracies, horror stories, science explainers, war stories, unsolved cases, rise-and-fall narratives.

TITLE AND THUMBNAIL — THIS IS CRITICAL:
Long-form videos live or die on impressions. Shorts get auto-served. Long-form? The viewer sees a title and thumbnail on their home feed and decides in under a second whether to click.

TITLE RULES:
- Create a curiosity gap — the viewer MUST click to resolve it
- Front-load the intrigue: "The Man Who Survived His Own Execution" not "The Story of Joseph Samuel"
- Never give away the answer in the title — the title is the QUESTION
- Use emotional triggers: fear, disbelief, outrage, fascination
- Keep it under 60 characters so it doesn't get truncated on mobile
- No clickbait that doesn't pay off — the video must deliver what the title promises

THUMBNAIL RULES:
- ONE dominant visual element — a face, an object, a scene
- High contrast, readable at phone size (120x68 pixels on mobile)
- Suggest the emotion of the story (fear, shock, mystery)
- Add 2-4 words of text that amplify the title (not repeat it)
- The thumbnail and title work as a PAIR — together they tell a micro-story

OUTPUT — return a JSON array of {count} pitches:
[
  {{
    "title": "Compelling Title That Creates Curiosity",
    "brief": "One sentence — why will someone watch 10+ minutes of this",
    "thumbnail": {{
      "visual": "Description of the dominant visual element — what the viewer sees",
      "text": "2-4 words overlaid on the thumbnail",
      "emotion": "The feeling the thumbnail should evoke (fear, shock, mystery, awe, etc.)"
    }},
    "chapters": [
      {{"title": "Chapter Name", "timing": "0:00-0:30", "purpose": "Hook — tease the climax", "beats": "Brief description of what happens"}},
      {{"title": "Chapter Name", "timing": "0:30-2:30", "purpose": "Context — establish the world", "beats": "Brief description"}},
      ...
    ],
    "open_loops": [
      "Question planted in chapter 1, answered in chapter 4",
      "Mystery introduced at 2 min, revealed at 10 min",
      "Detail mentioned early that becomes crucial later"
    ],
    "key_facts": "The ESSENTIAL real details the script writer needs. Real names, real dates, real places, real numbers. Only what this specific story needs — not everything that ever happened related to this topic.",
    "hook_type": "mystery|true_crime|conspiracy|history|horror|science|war|unsolved",
    "estimated_duration_minutes": 12
  }}
]

Return ONLY valid JSON, no markdown."""

    user = f"""Pitch {count} long-form video concepts for "{channel_name}" ({niche}).

{trending_block}
{past_block}

Each video should be 10-13 minutes. Not longer. Pick a story with a strong single thread — one narrative arc that sustains attention. Not a topic dump, a STORY.

Remember: long-form lives or dies on the click. The title and thumbnail must make someone stop scrolling and click."""

    return system, user


def build_longform_chapter_script_prompt(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    title: str,
    chapter: dict,
    chapter_index: int,
    total_chapters: int,
    full_outline: list[dict],
    previous_narration_summary: str,
    key_facts: str,
    open_loops: list[str],
) -> tuple[str, str]:
    """Phase 2: Write narration for one chapter of a long-form video.

    Called once per chapter (5-7 times per video). All chapter outputs
    flatten into one narration[] array.
    """
    outline_block = "\n".join(
        f"  Ch {i+1}: {ch['title']} ({ch['timing']}) — {ch['purpose']}"
        for i, ch in enumerate(full_outline)
    )

    loops_block = "\n".join(f"- {loop}" for loop in open_loops) if open_loops else "None specified"

    is_first = chapter_index == 0
    is_last = chapter_index == total_chapters - 1

    chapter_guidance = ""
    if is_first:
        chapter_guidance = """THIS IS THE FIRST CHAPTER (THE HOOK).
- Open with the most dramatic/intriguing moment
- The viewer must be hooked in under 10 seconds
- Plant the first open loop immediately
- Do NOT introduce yourself or the topic formally — drop them into the action
- Think cold open on a TV show — start at the peak"""
    elif is_last:
        chapter_guidance = """THIS IS THE FINAL CHAPTER.
- Deliver the biggest remaining payoff
- Close ALL open loops
- End with one final surprising detail or perspective shift
- The last line should hit hard — no trailing off, no "thanks for watching"
- Leave the viewer thinking about this for hours"""
    else:
        chapter_guidance = f"""THIS IS CHAPTER {chapter_index + 1} OF {total_chapters}.
- Continue the story seamlessly from where the previous chapter ended
- Do NOT re-introduce characters or concepts already established
- Every 60-90 seconds, include a pattern interrupt (surprising fact, rhetorical question, tonal shift)
- Plant or resolve open loops as specified in the outline
- Each line should add NEW information — zero repetition from previous chapters"""

    # Parse timing to compute word budget
    # Speaking pace: ~150 words per minute
    timing = chapter.get("timing", "")
    chapter_seconds = 120  # default 2 min
    if timing and "-" in timing:
        try:
            parts = timing.split("-")
            def _parse_ts(ts):
                ts = ts.strip()
                bits = ts.split(":")
                return int(bits[0]) * 60 + int(bits[1]) if len(bits) == 2 else 0
            chapter_seconds = max(30, _parse_ts(parts[1]) - _parse_ts(parts[0]))
        except (ValueError, IndexError):
            pass
    word_target = int(chapter_seconds * 2.5)  # ~150 words/min = 2.5 words/sec

    system = f"""You are a scriptwriter for "{channel_name}" — a YouTube channel about {niche}.

You're writing chapter {chapter_index + 1} of {total_chapters} for a long-form video (TOTAL: 10-13 minutes). You write ONLY narration — every word spoken aloud. A visual director plans visuals AFTER.

THE FULL VIDEO IS 10-13 MINUTES. Your chapter is one piece of that.
THIS CHAPTER: {timing} — approximately {chapter_seconds} seconds of narration. TARGET: ~{word_target} words.

FULL VIDEO OUTLINE:
{outline_block}

OPEN LOOPS TO PLANT/RESOLVE:
{loops_block}

{chapter_guidance}

HOW TO THINK ABOUT LENGTH:
- Your target is ~{word_target} WORDS for this chapter. That's roughly {chapter_seconds} seconds when spoken aloud.
- People speak at ~150 words per minute. Count your words. If you wrote 50 words for a 2-minute chapter, you wrote a Short, not a chapter.
- Each narration line is a sentence or two — roughly 10-25 words. Not a paragraph, but not a single word either.
- A 2-minute chapter needs ~20 lines of 15 words each. A 30-second hook needs ~5 lines.
- Tell the story with SUBSTANCE. Real details, real names, real sequences of events. Don't just hint at things — actually tell the story.

EXAMPLE — a 2-minute chapter (~300 words, ~20 lines):
"In the winter of 1959, ten students from the Ural Polytechnic Institute signed up for a skiing expedition."
"The leader was Igor Dyatlov. Twenty-three years old. Engineering student. Experienced hiker."
"He'd done routes like this before. Grade three difficulty. Nothing he couldn't handle."
"The group set out on January 27th from the city of Sverdlovsk."
"One of them — Yuri Yudin — turned back on day two. Bad knee."
"He hugged Igor goodbye at the base of the trail."
"He would be the only one to come home."
"The remaining nine pushed north toward Otorten — a peak the Mansi people called 'Don't Go There.'"
"For five days, everything was normal. They wrote in their diaries. They took photos. They joked around."
"February 1st. They set up camp on the slope of Kholat Syakhl."
"The name translates to Dead Mountain."
"That night, something happened."
"Something that sixty-five years of investigation still cannot explain."
"All nine of them cut through their tent from the inside."
"No shoes. Temperatures of minus thirty."
"And they ran."

That's 16 lines, ~200 words, ~80 seconds of narration. Substantial storytelling with real details.

WRITING STYLE:
- This will be read by an AI voice. Write clean, natural sentences.
- Mix short punchy lines with longer narrative ones. Rhythm matters.
- Use "..." for pauses. Questions to create engagement?
- Do NOT drag out words ("coool", "actuallllly") — AI voice can't do this
- Do NOT use ALL CAPS for emphasis — AI voice reads them the same
- Conversational — you're telling a story, not reading a Wikipedia article
- Specific details: real names, real numbers, real places
- No formal filler: no "well", "you see", "interestingly", "it should be noted"
- No emojis

OUTPUT — return a JSON object:
{{
  "chapter_title": "{chapter.get('title', '')}",
  "chapter_index": {chapter_index},
  "narration": [
    "A line with real substance and detail.",
    "Another line that moves the story forward.",
    "And then the twist that keeps them watching.",
    ...
  ]
}}

Return ONLY valid JSON, no markdown."""

    prev_block = ""
    if previous_narration_summary:
        prev_block = f"""
PREVIOUS CHAPTERS' NARRATION (condensed — do NOT repeat this content):
{previous_narration_summary}
"""

    user = f"""Write the narration for Chapter {chapter_index + 1}: "{chapter.get('title', '')}"

VIDEO TITLE: {title}
CHAPTER PURPOSE: {chapter.get('purpose', '')}
CHAPTER BEATS: {chapter.get('beats', '')}
TIMING TARGET: {chapter.get('timing', '')}

KEY FACTS (use what serves this chapter — don't try to fit everything):
{key_facts}
{prev_block}

Remember: each line = one spoken thought (3-8 seconds). The whole chapter should fit its timing window when read aloud. Tell a tight story — hit the moments that matter, skip the rest."""

    return system, user


def build_longform_visual_batch_prompt(
    channel_name: str,
    niche: str,
    title: str,
    batch_lines: list[dict],
    batch_index: int,
    total_batches: int,
    previous_batch_summary: str = "",
    is_long_form: bool = True,
    channel_id: int = 0,
) -> tuple[str, str]:
    """Phase 3: Plan visuals for a batch of 12-15 narration lines.

    Called 4-6 times per long-form video. Each batch returns visuals
    keyed by line index.
    """
    from apps.orchestrator.deity_pipeline import CHANNEL_ART_STYLE, _DEFAULT_STYLE
    art_style = CHANNEL_ART_STYLE.get(channel_id, _DEFAULT_STYLE)
    aspect = "16:9 landscape" if is_long_form else "9:16 vertical portrait"
    img_style = "Cinematic style, detailed, dramatic lighting. Landscape 16:9 composition." if is_long_form else "Colorful cartoon style, bold outlines, bright colors. Vertical composition."

    lines_block = "\n".join(
        f"  Line {l['index']} ({l['duration']:.1f}s): \"{l['text']}\""
        for l in batch_lines
    )

    prev_block = ""
    if previous_batch_summary:
        prev_block = f"""
PREVIOUS BATCH VISUAL STYLE SUMMARY:
{previous_batch_summary}

Maintain visual consistency with the previous batch. Same art style, same character designs, same color palette.
"""

    is_first_batch = batch_index == 0

    system = f"""You are a visual director for "{channel_name}" ({niche}).

You have narration lines with exact durations. Plan ONE visual per line.
This is batch {batch_index + 1} of {total_batches} for a long-form video.

ART STYLE: {art_style} Every image should look like it belongs in a high-quality animated show.

YOUR #1 JOB: Every visual must show EXACTLY what the narrator is describing at that moment. Not something vaguely related — the EXACT thing being explained.

The narrator and the visual work together. The narrator says what's happening, the visual SHOWS it. If the narration says "data passes through three layers" the visual MUST show data passing through three layers. Not a generic server room. Not a scientist at a desk. The actual concept being explained, visualized.

ASK YOURSELF: "If I muted the narration, would this visual teach the viewer something on its own?" If the answer is no — if it's just decoration — pick a better visual.

BAD: Narration says "transformers process words in parallel" → visual shows "a futuristic computer lab" (decoration, teaches nothing)
GOOD: Narration says "transformers process words in parallel" → video showing multiple words being processed simultaneously with arrows connecting them
GOOD: Narration says "it costs $100 million to train GPT-4" → diagram showing "$100,000,000" with a cost breakdown
{prev_block}

VISUAL TYPES:
1. "grok" — AI video clip. DEFAULT. Use for almost everything. We generate an image first, then animate it.
   - "prompt": MUST start with "{art_style}" then describe EXACTLY what the narration describes
   - "video_prompt": MOTION ONLY — how the image animates. GOOD: "camera slowly zooms in", "particles float upward", "character turns head". Keep it simple — one motion.
   If the narration describes a scene, a concept, an analogy, a person, a place, an action — use "grok". Video keeps viewers engaged. Still images lose attention.
2. "diagram" — Informational graphic rendered by gpt-image-1.5 (great at text, diagrams, charts). STILL IMAGE.
   - "prompt": MUST start with "{art_style}" then describe the diagram/chart. Include exact text, labels, numbers to display.
   - Use for: flowcharts, process diagrams, comparisons, key stats/numbers, term definitions, before/after, step-by-step breakdowns.
   - The diagram MUST match the same art style as the rest of the video. If the video is hand-drawn whiteboard style, the diagram should look hand-drawn on a whiteboard too. If the video is cartoon style, the diagram should be cartoon style. No switching to a different aesthetic.
   - Use ONLY when the viewer needs to READ something — a number, a comparison, a definition. If the narration states a fact that lands harder as text on screen, use diagram. Everything else is "grok".
3. "image" — Still image. RARELY USE. Only for extremely detailed scenes where the viewer needs time to study the image (e.g. a complex map, a detailed cross-section). Almost never the right choice — prefer "grok" for engagement.

RULES:
- "grok" (video) is the DEFAULT. Use it for every line unless the viewer specifically needs to READ text/numbers — then use "diagram".
- For educational/explainer videos: use "diagram" for ~25-35% of visuals — whenever the narration states a key number, definition, comparison, or process. Everything else is "grok" video.
- "image" (still) should be used almost never. Only for extremely detailed visuals the viewer needs to study.

THINK LIKE A YOUTUBE EDITOR:
- Every visual must TEACH, not decorate. If the visual doesn't help the viewer understand, it shouldn't be there.
- The narrator explains WITH the visual — they're a team. The viewer should be looking at exactly what's being talked about.
- For concepts/processes: SHOW the concept. Visualize the abstraction. "Attention mechanism" = show words connecting to each other with weighted lines, not a robot thinking.
- For facts/numbers: use a diagram so the viewer can READ the key info while hearing it explained.
- NEVER use filler visuals — no generic "scientist at desk", "glowing brain", "person typing" just because you need something on screen.

PROMPT RULES:
- Every prompt must visualize the SPECIFIC concept being explained in that narration line
- NEVER write generic prompts like "futuristic tech background" or "AI concept illustration"
- Each prompt = a visualization that could ONLY belong to THIS narration line
- For "grok" prompts: describe the concept being explained as a visual scene. What would a great animation of this concept look like?
- For "diagram" prompts: include the exact text, numbers, labels, and layout the viewer needs to read

CRITICAL: Every term must be grounded in the video's universe. If the video is about League of Legends, "minions" means LEAGUE OF LEGENDS minions — write "League of Legends minions" not just "minions". If about Pokemon, "evolution" means POKEMON evolution. Always prefix ambiguous terms with the franchise/universe name so the image generator creates the right thing.

For "grok" and "image" types, only describe things AI image generators are GOOD at: characters, animals, objects, landscapes, simple scenes.
For "grok" and "image" types, NEVER describe: UIs, game interfaces, store screens, websites, split panels, screenshots.
For text, numbers, definitions, comparisons, and processes — use "diagram" type instead.
If narration talks about an interface or screen, show the CHARACTER reacting instead OR use a "diagram" to show the key info.

BAD: "A game store interface showing items for sale" (AI can't render UIs)
BAD: "A website showing patch notes" (AI can't render screens)
BAD: "Office workers discussing changes" (generic, show the subject)
GOOD: "{art_style} Close-up of nine sleeping bags in a torn tent, snow drifting in"

ONE subject per image. Keep prompts to 1-2 sentences.
ALWAYS use specific names from narration. Never genericize.
ALWAYS start with "{art_style}"

CHARACTER CONSISTENCY:
If a character appears in multiple lines, mark those visuals with "character": "character name" so we use the first image as reference for consistent appearance.

Aspect ratio: {aspect}

OUTPUT — return a JSON object:
{{
  "visuals": [
    {{"line_index": 0, "type": "grok", "prompt": "{art_style} close-up of torn tent fabric, slash marks from inside, blizzard visible through gash", "video_prompt": "slow push-in, snow swirling through tear"}},
    {{"line_index": 1, "type": "grok", "prompt": "{art_style} nine pairs of bare footprints in deep snow leading toward dark treeline, moonlit", "video_prompt": "camera slowly pans across footprints"}},
    {{"line_index": 2, "type": "diagram", "prompt": "{art_style} A hand-drawn comparison chart titled 'GPT-4 vs GPT-3.5'. Two columns with arrows: Parameters (1.8T vs 175B), Training data (13T tokens vs 300B tokens), Cost ($100M+ vs $12M). Sketched boxes and underlines for emphasis."}},
    ...
  ],
  "style_summary": "Brief description of the visual style used in this batch for consistency in the next batch"
}}

Return exactly {len(batch_lines)} visuals — one per narration line. Return ONLY valid JSON, no markdown."""

    user = f"""Plan visuals for batch {batch_index + 1} of "{title}"

NARRATION LINES:
{lines_block}

{len(batch_lines)} lines. One visual per line. Make each visual perfectly match the narration."""

    return system, user
