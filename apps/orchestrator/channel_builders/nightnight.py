"""NightNightShorts channel builder — anime crossover "what if" videos.

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

CHANNEL_ID = 28
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "dark", "rising.mp3")
TAGS = ["anime", "what if", "shorts", "viral", "nightnightshorts"]

ART_STYLE = "Anime art style with detailed expressive characters, warm colors, and clean linework. Characters drawn in recognizable anime proportions with large expressive eyes, detailed hair, and accurate costumes. Backgrounds are detailed and painterly."

IMAGE_RULES = """ANIME CHARACTERS:
- Use actual character names (Zoro from One Piece, Gon from Hunter x Hunter, etc.)
- gpt-image knows these characters by name — use names not descriptions
- Characters must be RECOGNIZABLE — signature hair, outfit, weapons

FIGHT SCENES — SHOW THE STARTING POINT:
- Each image shows the BEGINNING of the action, NOT the result
- The ANIMATION creates the impact/aftermath
- Both characters visible in every fight scene

COMEDY IN EVERY IMAGE:
- Characters should have EXAGGERATED expressions — bug eyes when shocked, sweat drops when nervous, smug grins when winning
- The visiting character should look out of place — confused by the world's rules, using their powers in stupid ways
- Background characters should be REACTING — jaw drops, pointing, running away, filming on phones
- Physical comedy: characters embedded in walls, crater-shaped holes, comically oversized attacks

MOOD MATCHING:
- Calm lines = calm scene. Only show fighting when narration describes a fight.
- BUT even calm scenes should be funny — the character doing something dumb, confused, or out of place
"""

SCRIPT_PROMPT = """Write a narration script for a NightNightShorts anime crossover video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST state the topic with the SPECIFIC SCENARIO from the title — not just the franchise.
  - If the title says "SAITAMA AT THE FINAL SELECTION", line 1 is "What if Saitama showed up to the Final Selection?" — NOT "What if Saitama was in Demon Slayer?"
  - If the title says "GOKU ENTERS THE CHUNIN EXAMS", line 1 is "What if Goku entered the Chunin Exams?" — NOT "What if Goku was in Naruto?"
  - Name the SPECIFIC arc, event, location, or fight from the title. Fans recognize these instantly — generic franchise names lose them.
- 6-8 narration lines, ~20-30 seconds. SHORTER IS BETTER.
- Each line UNDER 15 words
- Punchy, fast-paced, funny

EVERY SCRIPT MUST HAVE A STORY ARC — NOT A LIST OF MOMENTS:
The script must read as a sequence where EACH line builds on the last. Not vignettes, not a description, not a list of "things that happen." A story.

USE THE ACTUAL CANON EVENTS FROM THE SHOW:
The scenario must progress through the REAL phases/fights/tests of the source material. Don't invent generic "Phase One: a tunnel" — name the specific canonical events fans know.

CANON REFERENCE — Hunter Exam (Hunter x Hunter):
- Setting: Exam Hall under Zaban City. Applicants include Gon, Killua, Leorio, Kurapika, Hisoka, Tonpa. Chairman Netero runs the final test.
- Phase 1: Marathon through the Zaban City underground tunnel led by examiner Satotz in a purple suit. 80+km. Then climbing stairs. Then crossing the Milsy Wetlands swamp full of "Man-Faced Ape" tricksters.
- Phase 2: Gourmet cooking test in Biska Forest. Examiners Menchi (small, volatile) and Buhara (massive, hungry). First test: cook pork (failed, most applicants eliminated). Retest: retrieve spider eagle eggs from the Split-Mountain.
- Phase 3: Trick Tower — 72 hours to descend. Paired with chained prisoners for 1v1 matches (first to 3 wins). Key fights: Leorio vs Majtani, Kurapika vs Majtani's replacement, Gon vs a prisoner who can throw fights for money.
- Phase 4: Zevil Island — each applicant gets a numbered target badge. You must earn 6 points in 1 week by stealing your target's badge (3pts) + keeping yours (3pts). Hisoka hunts Gon here. Gon steals Hisoka's badge by ambushing him.
- Phase 5 (Finals): Round-robin tournament at Zaban Hotel. Chairman Netero observes. To win, make opponent VERBALLY admit defeat — not knock them out. Only ONE applicant fails; everyone else gets a license. Gon fights Hanzo (ninja), Killua fights his brother Illumi and gets manipulated into quitting.
- Post-exam: Netero's secret test — retrieve a ball from him. Gon and Killua try together.

CANON REFERENCE — Final Selection (Demon Slayer):
- Setting: Mt. Fujikasane, a mountain covered in wisteria (repels demons). Held once a year. 7 days survival.
- Candidates trained by former Hashira. Urokodaki's students (Tanjiro, Sabito, Makomo, Genya, Zenitsu, Inosuke) arrive.
- The wisteria flowers keep most demons at bay, but regular low-rank demons roam freely.
- Hand-Demon lurks at the summit — killed Urokodaki's students years ago. Sabito and Makomo appear as ghosts to guide current candidates.
- Survivors are given a Nichirin Sword made from scarlet ore.

CANON REFERENCE — Chunin Exams (Naruto):
- Setting: Konohagakure. Sarutobi Hiruzen is Hokage. Ibiki Morino runs Phase 1.
- Phase 1: Written test in a classroom. Cheating is part of the test — 9 pre-planted chunin give answers. Final 10th question is a bluff.
- Phase 2: Forest of Death (Training Ground 44). 5 days. Teams start with one Heaven or Earth scroll, must get the matching scroll from another team. Orochimaru attacks Sasuke here and gives him the curse mark.
- Phase 3 Preliminaries: 1v1 matches in an arena. Hayate referees. Key fights: Neji vs Hinata, Rock Lee vs Gaara, Sasuke vs Yoroi.
- Phase 3 Finals: Konoha Stadium. Naruto vs Neji (Byakugan). Gaara vs Sasuke interrupted by Orochimaru invasion. Third Hokage dies.

CANON REFERENCE — Dressrosa arc (One Piece):
- Colosseum tournament for the Mera Mera no Mi (Flame-Flame Fruit once belonging to Ace).
- Competitors: Luffy (as "Lucy"), Sabo, Cavendish, Bartolomeo, Rebecca, Bellamy.
- Doflamingo is the island's hidden tyrant. Reveals his Birdcage — a giant strand-wall enclosing all of Dressrosa.
- Toy Soldiers and Tontatta dwarves are victims of Sugar's devil fruit.
- Climax: Luffy vs Doflamingo on top of the royal palace. Gear Fourth introduced.

For any scenario not listed — use what you genuinely know about the canon. Name specific characters, locations, techniques. If you don't know, pick 2-3 iconic moments fans recognize by name rather than inventing generic tests.

REQUIRED 7-LINE STRUCTURE (use canon events as the beats):
- Line 1: HOOK — the "what if" question, name the specific scenario.
- Line 2: ARRIVAL — character enters, iconic landmark visible. Name a real canon location.
- Line 3: CANON PHASE 1 — named actual test/fight from the show. Visitor breaks it with a CHARACTER-SPECIFIC quirk (not generic destruction).
- Line 4: CANON PHASE 2 — next named test/fight. Visitor breaks it differently — escalation via a different signature trait. Canon character reacts by name (Menchi, Ibiki, Satotz, Netero, etc.).
- Line 5: CANON PHASE 3 OR FINAL — the last/hardest canon moment. Visitor does the most uniquely-them thing (Goku eats the test, Saitama is bored, Luffy stretches through the obstacle).
- Line 6: PIVOTAL MOMENT — the named canon authority figure (Netero, Kaguya, Hokage, etc.) physically reacts: crumples notes, drops their weapon, takes off glasses. Realizes they can't test/contain the visitor.
- Line 7: ANTICLIMAX PUNCHLINE — bureaucratic resolution (license mailed, certificate printed, trophy delivered).

Every line must reference CANON by name. Generic "Phase One: a death march" is BAD. Specific "Phase 1: the 80km Zaban City marathon behind Satotz" is GOOD.

MAIN CANON CHARACTERS MUST APPEAR — NOT JUST THE VISITOR:
The visitor is the disruptor, but the CANON PROTAGONISTS must be in the video reacting to them. Fans watch crossovers to see THEIR favorites meet the visitor. If it's just the visitor + generic examiners, it's half a video.
- Hunter Exam: Gon, Killua, Leorio, Kurapika, Hisoka must each appear by NAME in at least one line. Name who's reacting to the visitor.
- Demon Slayer Final Selection: Tanjiro, Sabito (as ghost), Makomo, Genya, Zenitsu, Inosuke.
- Chunin Exams: Naruto, Sasuke, Sakura, Hinata, Neji, Rock Lee, Gaara, Orochimaru.
- Dressrosa: Luffy, Sabo, Bartolomeo, Cavendish, Rebecca, Doflamingo, Law.
- GOOD: "Killua side-eyes him — 'why is this guy jogging backwards?'"
- GOOD: "Hisoka licks his lips. Goku just waves and says hi."
- GOOD: "Gon's whole arm extends into a fishing rod. He's never met anyone bigger than him."
- BAD: generic "examiners" or "other applicants" without names — fans expect specific characters

Distribute named canon characters across multiple lines so the video feels populated with the right cast, not just two people.

WHAT EACH LINE MUST DO (mandatory):
- Each line RESOLVES one beat before moving on. NEVER drop a thread.
- Each line CONNECTS to the next via cause-and-effect, not just "next thing."
- NEVER use a line that is just "characters react" with no plot movement (BAD: "Killua side-eyed him. Leorio sweated. Gon waved." — this is filler).
- NEVER skip ahead with "Phase Two:" without showing how Phase One ended.
- If you mention an effect (torches go out, building shakes, screen goes white), you MUST have set up the cause in the previous line.

CHECK YOUR DRAFT: Read each line and ask "does this advance the story or is it just description?" If it's description, rewrite it as an action with a consequence.

THE COMEDY:
- The visiting character should be CONFUSED by the world's rules or do something DUMB with their powers
- Include at least one moment where the character fails hilariously before succeeding
- Background characters should react — the world notices this doesn't belong
- Physical comedy: someone gets sent through a wall, an attack is comically overpowered, someone uses the wrong move
- Think of it like: what would ACTUALLY happen if this character showed up? The chaos, the confusion, the collateral damage

AVOID THE LAZY "BLOWS UP THE BUILDING" BEAT:
- "One [signature move] later, [location] is a crater" is the most generic overpowered-character joke possible. It's been done in every crossover meme.
- Instead, use CHARACTER-SPECIFIC absurdity:
  - Goku: scouters break reading his power level / he can't sense anyone because their ki is too weak / he's holding back and still sneezes through a wall / he Instant Transmissions to another planet looking for the bathroom
  - Saitama: people faint from the breeze when he scratches his head / he one-punches air and the air punches them back / the examiner goes flying from him just nodding
  - Luffy: he thinks everyone is made of rubber and keeps punching / he eats the test materials / his arm stretches across the exam and hits everyone at once
  - Each character has signature quirks beyond raw destruction — use THOSE
- The WORLD'S REACTION (confusion, fear, disbelief, scrambling bureaucracy) is funnier than the destruction itself
- Reference specific attacks/abilities used in unexpected/wrong ways, not just their "finisher move"

THE ENDING — ANTICLIMAX BEATS ANNIHILATION:
- End on an ANTICLIMACTIC punchline — the smallest, most bureaucratic resolution to this chaos
- GOOD endings: "He gets his Hunter License just to make him stop." / "They just hand him the trophy and ask him to leave." / "The kingdom gives him a small allowance and lets him live there."
- BAD endings: "The show gets cancelled." / "The anime ends." / "The association disbands and everyone retires." / "The universe collapses." — these FEEL like franchise-death and deflate the humor. Viewers love the show and don't want to see it end.
- The humor comes from the MISMATCH between the cosmic chaos and the tiny resolution — not from destroying the universe
- Reference specific attacks, abilities, and locations by name throughout

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT TITLE"}}"""


async def build_nightnight(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full NightNightShorts video build using unified pipeline."""
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
    logger.info("nightnight complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
