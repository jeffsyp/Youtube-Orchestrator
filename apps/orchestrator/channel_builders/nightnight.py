"""NightNightShorts channel builder — anime crossover and anime battle videos.

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
    get_duration,
    update_database,
)
from packages.utils.concept_formats import (
    FORMAT_STRATEGY_DESCRIPTIONS,
    get_format_strategy_spec,
    infer_format_strategy,
    normalize_format_strategy,
)

logger = structlog.get_logger()

CHANNEL_ID = 28
VOICE_ID = "TxGEqnHWrfWFTfGW9XjX"  # Josh
VOICE_SETTINGS = {"stability": 0.6, "similarity_boost": 0.8, "speed": 0.97}
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "dark", "rising.mp3")
TAGS = ["anime", "what if", "shorts", "viral", "nightnightshorts"]

ART_STYLE = "Clean anime-cartoon hybrid — bold clean outlines, flat cel shading, crisp anime silhouettes, simplified but recognizable faces, expressive webtoon energy. Characters stay recognizable by signature hair, outfit, makeup, weapons, and colors, but rendered like a polished 2D parody frame rather than a painterly anime screenshot. NOT photoreal, NOT plush chibi, NOT storybook soft, NOT grimy doodle, NOT glossy 3D mobile-game art."

IMAGE_RULES = """ART STYLE:
- CLEAN ANIME-CARTOON HYBRID — bold clean outlines, flat cel shading, crisp silhouettes, readable anime faces, expressive reactions
- Polished but still comedic — NOT photoreal, NOT painterly prestige-anime lighting, NOT plush/chibi mascot art, NOT children's-book softness
- Avoid grime and sketch wobble. Avoid glossy mobile-game rendering. Aim for sharp 2D parody/webtoon energy that keeps the characters accurate.
- Every character keeps their SIGNATURE IDENTITY (Goku's spiky hair + orange gi, Saitama's bald head + yellow suit + red gloves, Luffy's straw hat + red vest + scar under eye)
- Backgrounds should be simple but specific to the canon location — clean 2D environments, not muddy painted backdrops

ANIME CHARACTERS — USE THEIR NAMES:
- Use actual character names (Goku, Gon, Killua, Saitama, Luffy, Tanjiro, Naruto, etc.) in every prompt
- gpt-image knows these characters by name and will preserve their signature features automatically in this cleaner anime-cartoon style
- Always include signature identifiers in the prompt: "Goku (spiky black hair, orange gi with blue belt)", "Killua (white spiky hair, green turtleneck)", "Hisoka (red hair, jester makeup, star and teardrop face paint)"

FRANCHISE SEPARATION — CRITICAL:
- The VISITING character is from ONE franchise (e.g. Goku from Dragon Ball)
- The HOST WORLD is from a DIFFERENT franchise (e.g. Hunter x Hunter)
- ONLY characters from the HOST franchise may appear besides the visitor. NEVER include other characters from the visitor's home franchise.
- BAD: Goku + Master Roshi + Krillin in a Hunter Exam scene (Roshi/Krillin are Dragon Ball — they should NOT be there)
- BAD: Naruto + Sasuke + Sakura in a Demon Slayer Final Selection (Sasuke/Sakura are Naruto — they should NOT be there)
- GOOD: Goku (visiting) + Gon + Killua + Leorio + Netero (all Hunter x Hunter — the host world)
- Every image prompt MUST explicitly state "No other Dragon Ball characters" (or whichever the visitor's franchise is) to prevent gpt-image from hallucinating Roshi/Krillin/Bulma into host-franchise scenes.
- Backgrounds and settings must be from the HOST world. No Dragon Ball landscapes in a Hunter Exam scene. No ninja villages in a One Piece scene.

FIGHT/ACTION SCENES IN THIS STYLE:
- Keep motion readable with impact stars, motion lines, dust clouds, and clean silhouettes
- Each image shows the BEGINNING of the action, the ANIMATION creates the impact/aftermath
- Both fighters should stay present across the SEQUENCE, but they do NOT need to appear in every single clip
- Multiple characters in frame is fine, but avoid literal body-to-body contact, grappling, or hand-to-hand exchanges when a cleaner separated staging would work
- Prefer "attacker winding up while defender braces" or "defender alone getting blasted back" over the exact instant of contact
- For clean fight payoffs, it is often stronger to show the winner alone using a named attack, then cut to the loser alone in the aftermath
- Use stylized exaggeration: crater-shaped holes in walls, character-shaped dust outlines, giant sweat drops, exaggerated recoil, oversized signature attacks

COMEDY IN EVERY IMAGE:
- Characters should have EXAGGERATED readable expressions — bug eyes when shocked, giant sweat drops when nervous, smug grins when winning, tiny white dots for shocked eyes
- The visiting character should look out of place — confused by the world's rules, using their powers in stupid ways
- Background characters should be REACTING — jaw-on-the-floor drops, pointing, running away in panicked silhouettes
- Physical comedy: characters embedded in walls, comically oversized attacks, wobbly stretched limbs

MOOD MATCHING:
- Calm lines = calm scene. Only show fighting when narration describes a fight.
- BUT even calm scenes should be funny — the character doing something dumb, confused, or out of place
- Every prompt must end with "Clean anime-cartoon parody frame. NO text anywhere."

VS MATCHUPS / ANIME DUELS:
- If the concept title or narration is a direct matchup ("X vs Y", "X versus Y", "who wins"), DO NOT use visitor/host-world logic
- In matchup mode, BOTH named fighters are co-stars and should appear in most battle scenes
- Do NOT force "No other Dragon Ball characters" style negatives unless the narration explicitly frames one character invading another world
- Use a clear fight progression: face-off, first exchange, counter, signature move, decisive finish
- Both fighters must stay visually consistent across the entire video
- Show the START of each exchange in the image, then let the animation deliver the impact
- For verdict scenes, keep the loser visible — knocked back, cratered, stunned, wrapped up, etc. Never just make them disappear
- A clear named-attack clip followed by a loser-aftermath clip is GOOD visual storytelling for this channel
"""

SCRIPT_PROMPT = """Write a narration script for a NightNightShorts anime short.

CONCEPT: {title}
BRIEF: {brief}
KEY FACTS: {key_facts}
STRUCTURE NOTES: {structure}

NIGHTNIGHT HAS TWO VALID FORMATS:
1. ANIME CROSSOVER "WHAT IF" — one character enters a specific canon arc/event from another anime
2. CHARACTER VS CHARACTER — two anime characters directly fight, with a clear winner

CHOOSE THE FORMAT FROM THE TITLE/BRIEF:
- If the title says "X vs Y", "X versus Y", "who wins", "what if X fought Y", or clearly describes a direct matchup, use the CHARACTER VS CHARACTER format.
- Otherwise, use the ANIME CROSSOVER "WHAT IF" format.

GLOBAL RULES FOR BOTH FORMATS:
- This concept's format strategy is "{format_strategy}": {format_description}.
- Write {min_lines}-{max_lines} narration lines. Do NOT upscale it into a bigger story just because NightNight often uses longer scripts.
- Keep the spoken total under {max_duration:.0f} seconds.
- single_frame and attack_result are VALID if the premise already lands. Simpler is better when the image or action is strong enough.
- Each line UNDER 15 words
- Prefer the post-hook lines to stay under 12 words unless a canon name requires extra words
- Punchy, fast-paced, funny or hype
- Line 1 must tell the viewer EXACTLY what the video is about out loud. Shorts viewers do not see the title.
- If the written title is long, the spoken hook may use the SHORTEST clear version instead of reciting every franchise word.
- GOOD: "What if Light used the Death Note on Hisoka?"
- BAD: saying the full title word-for-word when a shorter hook is cleaner and more natural.
- Use SPECIFIC canon names, attacks, locations, and reactions. Never generic anime filler words.
- Every line must be VISUALLY DRAWABLE in a single still image. Prefer physical verbs and visible props. Avoid abstract-only lines like "everyone realizes", "he decides", "they beg", or "it becomes obvious" unless the line also includes a visible physical proof.
- If a line contains a setup action and then a reaction, phrase it so the setup can be shown FIRST and the reaction SECOND in separate visuals. Example: "Gojo jogs backward behind Satotz; Gon and Killua nearly trip staring." The weird action happens first, then the reaction.
- ENGAGEMENT FIRST: viewers clicked to see POWERS, COLLISIONS, and canon-specific chaos. Do NOT spend multiple lines on people merely staring, sweating, or reacting. Reaction only works after a real power/action beat.
- Most post-hook lines should contain a clearly visible power use, counter, physical stunt, or named ability with an obvious on-screen consequence.
- By line 2 if there is one — otherwise line 1 itself — the visitor must already be doing something impossible, signature, or power-specific. No slow warm-up.
- At least one host-world character should try their own known move, rule, or test against the visitor instead of only gawking.
- Every reaction line must be EARNED by a stronger action line immediately before it.
- GROK-SAFE WRITING: each line should describe ONE dominant animated event. Avoid packing multiple equally important actions into one line. If two big things happen, split them across two lines.
- Prefer clean cause→effect beats over crowded semicolon stacks. A viewer should instantly know what the clip is supposed to animate.
- COLD VIEWER RULE: assume the viewer got dropped into the short with zero context. If the joke depends on one special power, rule, or canon mechanic, the script must explain that rule in plain English before or during the payoff.
- Do NOT rely on raw fandom jargon alone. Named abilities are fine, but the viewer must also understand what they DO.
- GOOD: "Light expects Hisoka to die. Hisoka stands back up smiling."
- GOOD: "Gojo's Infinity stops the cards in midair."
- BAD: "Texture Surprise activates. Bungee Gum reacts." with no plain-English explanation.
- MINI-STORY RULE: after the hook, the script must feel like a CRAZY SCENE CLIP CHAIN, not a lore recap.
- Someone does something impossible, the canon world answers, the situation TURNS, and the final beat lands visibly.
- Do NOT spend two post-hook lines in a row just explaining feelings, themes, or who is rattled.
- Every post-hook line should either change who has control, reveal a new rule, escalate the damage, or force a new tactic.
- By line 3 or 4, there must be a STORY TURN: counterattack, survival reveal, power reversal, target change, timer, betrayal, failed plan, or canon-rule backfire.
- The last line must show the ENDING ON SCREEN. Avoid internal-summary endings like "he realizes", "she is rattled", or "the notebook met someone" unless the line also contains a visible physical payoff.
- MULTIPLE CHARACTERS ARE FINE, but avoid writing lines whose payoff depends on two characters physically touching in one shot. Prefer beats that can stage the attacker/setup first and the victim/result second.
- If a line implies "A hits B", "A knocks B out", "A grabs B", or "A hands B something", phrase it so the planner can show separated cause→effect beats instead of literal contact.
- For matchup/fight lines, the safest default is often "named move/setup" first and "loser aftermath/result" second.
- GOOD: "Zoro surges forward; Killua gets blasted into the wall."
- GOOD: "Zoro uses Onigiri. Dust clears — Killua is already down."
- BAD: "Zoro's swords hit Killua and launch him backward."

FORMAT A — ANIME CROSSOVER "WHAT IF":
- Line 1 MUST state the topic with the SPECIFIC SCENARIO from the title — not just the franchise.
  - If the title says "SAITAMA AT THE FINAL SELECTION", line 1 is "What if Saitama showed up to the Final Selection?" — NOT "What if Saitama was in Demon Slayer?"
  - If the title says "GOKU ENTERS THE CHUNIN EXAMS", line 1 is "What if Goku entered the Chunin Exams?" — NOT "What if Goku was in Naruto?"
  - Name the SPECIFIC arc, event, location, or fight from the title. Fans recognize these instantly — generic franchise names lose them.

EVERY SCRIPT MUST HAVE A STORY ARC — NOT A LIST OF MOMENTS:
The script must read as a sequence where EACH line builds on the last. Not vignettes, not a description, not a list of "things that happen." A story.

STORY ENGINE REQUIREMENT:
- A strong crossover answers four questions fast:
  1. what impossible thing happens first,
  2. how the canon world answers,
  3. what insane twist or survival move changes the story,
  4. what final ending image nobody expected.
- If line 2 already tells the viewer the exact rest of the video, the premise is too flat.
- GOOD: Light writes the name, Hisoka dies, Hisoka restarts his heart, Light tries again, Hisoka turns the hunt around.
- BAD: Light writes the name, Hisoka revives, Light feels scared. That is explanation, not a story.

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

FORMAT-SCALED STRUCTURE (pick the FEWEST beats that still land):
- Line 1: HOOK — say the specific scenario out loud.
- single_frame: one dominant impossible image/thesis beat, optional tiny aftermath.
- attack_result: arrival or attack setup, then one clean consequence/punchline.
- mini_story: arrival → canon collision → escalation → payoff.
- full_story: use more canon phases, but every beat must still advance and stay visually literal.
- If the whole crossover hinges on ONE special mechanic, spell that mechanic out in simple language by line 2 or 3.
  GOOD: "Light writes Hisoka's name. Hisoka dies — then restarts his own heart."
  BAD: "Texture Surprise. Bungee Gum. More Bungee Gum." without ever explaining the twist.
- For arrival lines, establish the visitor's weird behavior cleanly BEFORE background characters start freaking out. The audience needs one clean beat of "what is he doing?" before the reaction beat.
- The final beat should still end on a sharp anticlimax or verdict: license shoved across the desk, trophy handed over, guards bolting a gate, winner standing over rubble, etc.

POWER SHOWCASE REQUIREMENT:
- Fans are here to see the visitor's signature ability used in the wrong universe. Show it EARLY and MULTIPLE TIMES.
- GOOD: Gojo uses Infinity on the Man-Faced Apes, then embarrasses Netero's ball test, then casually takes the license.
- BAD: several lines in a row of Gon/Killua/Hisoka reacting while Gojo does nothing new.
- GOOD: host-world powers/rules collide with the visitor's power: Bungee Gum vs Infinity, Nen test vs Six Eyes, Forest of Death rules vs stretchy arms.
- BAD: generic "everyone stares" or "the examiner panics" without a fresh power beat causing it.

Every line must reference CANON by name. Generic "Phase One: a death march" is BAD. Specific "Phase 1: the 80km Zaban City marathon behind Satotz" is GOOD.

MAIN CANON CHARACTERS MUST APPEAR — NOT JUST THE VISITOR:
The visitor is the disruptor, but the CANON PROTAGONISTS must be in the video reacting to them. Fans watch crossovers to see THEIR favorites meet the visitor. If it's just the visitor + generic examiners, it's half a video.
- For single_frame or attack_result concepts, one or two named canon characters reacting clearly is enough.
- For mini_story or full_story concepts, spread the real cast across multiple lines so the world feels populated.
- Hunter Exam: for mini_story/full_story, spread Gon, Killua, Leorio, Kurapika, and Hisoka across the script when possible. For simpler formats, pick the 1-2 names that make the beat land hardest.
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
- The comedy should come from MISUSING signature powers in a canon situation, not from generic reaction faces. Viewers want to see the power do something weird.

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
- The final line must still be drawable in one image. If the ending is bureaucratic, include visible props and body language: license card shoved across desk, trophy handed over, officials bowing, forms stamped, guards dragging someone away, etc.

FORMAT B — CHARACTER VS CHARACTER:
- Line 1 MUST announce the matchup out loud. Example: "Naruto versus Luffy — who actually wins?"
- After the matchup line, choose the simplest structure that still works:
  * single_frame = matchup hook + one decisive winning image
  * attack_result = face-off/setup, then decisive consequence
  * mini_story = face-off, attacker edge, counter, finish
  * full_story = only when the matchup genuinely needs several exchanges
- Fighter A and Fighter B should still get distinct named abilities when there is room.
- The decisive finish must end with a CLEAR WINNER. No ties, no "it depends," no diplomatic cop-out.
- Keep it anime-first. This is not a stat-sheet debate video. It should feel like the fight is happening in front of you.
- Use attacks by name: Rasengan, Shadow Clone Jutsu, Gear Fifth, Red Hawk, Bankai, Hollow Purple, etc.
- The winner should win through a CHARACTER-SPECIFIC reason, not just "he's stronger."
- NightNight tone still applies: exaggerated reactions, absurd collateral damage, fans immediately understand the matchup.
- Anime vs anime IS allowed here. This is different from One on Ones.
- Stage exchanges in separated beats when possible: face-off, attacker wind-up, defender consequence. Do NOT assume one clip can cleanly animate literal sword-to-body or fist-to-face contact.
- If the named move itself is the hype, it is GOOD to skip the literal exchange entirely: show the move cleanly, then cut straight to the loser aftermath.
- GOOD: "Zoro draws and lunges." then "Killua crashes backward through rubble."
- GOOD: "Zoro uses Onigiri." then "Killua is already down in the crater."
- BAD: "Zoro slices Killua across the chest" as the whole visual idea for one clip.

GOOD VS STRUCTURE:
- Matchup announcement
- Naruto floods the field with clones
- Luffy stretches around the clones and laughs
- A named attack lands
- The other fighter counters with their signature move
- One ultimate move ends it
- Winner declared brutally and clearly

BAD VS STRUCTURE:
- Three lines of power-scaling jargon
- Generic "they trade blows"
- A non-answer ending like "depends on the writer"

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT TITLE", "format_strategy": "{format_strategy}"}}"""


DIALOGUE_SKIT_PROMPT = """Convert this NightNightShorts premise into a NATIVE-DIALOGUE anime skit.

CONCEPT: {title}
BRIEF: {brief}
KEY FACTS: {key_facts}
STRUCTURE NOTES: {structure}
FORMAT STRATEGY: {format_strategy} ({format_description})

This is for a cold-viewer short. The characters must SAY enough out loud that someone with zero context can instantly follow the scene.

RULES:
- Return 3-5 scenes. Use the FEWEST scenes that still make the story obvious.
- NO narrator. NO voiceover. One dominant speaker per scene.
- Spoken lines must sound like real speech, not typed lore notes. Short, natural, punchy.
- Every scene must visibly advance the story. No reaction-only filler.
- Scene 1 must say the topic or rule out loud in plain English.
- If the twist depends on a special mechanic, explain what it does in plain English by scene 1 or 2.
- For Death Note ideas, somebody must clearly establish: writing the name kills the target, then later clearly say or show that the target stands back up or restarts their heart.
- The final scene must end on a visible physical payoff, not just a creepy smile with no action.
- Use actual anime character names and signature details in every image prompt.
- Keep the style consistent with this channel: {art_style}
- Every image_prompt must end with: "Clean anime-cartoon parody frame. NO text anywhere."
- Every video_prompt must describe what the speaker DOES and SAYS, plus sound effects. Do not write camera directions.

Return ONLY a JSON object:
{{
  "title": "SHORT TITLE",
  "format_strategy": "{format_strategy}",
  "narration_style": "none",
  "audio_policy": "native_dialogue",
  "scenes": [
    {{
      "characters": ["Speaker Name", "Optional Silent Character"],
      "image_prompt": "Detailed anime-cartoon frame prompt",
      "video_prompt": "Speaker physically acts and says a short natural line. Include sound effects.",
      "duration": 3.0
    }}
  ]
}}"""


def _is_vs_matchup(title: str, brief: str = "") -> bool:
    text = f"{title} {brief}".lower()
    return any(
        token in text
        for token in [
            " vs ",
            " versus ",
            "who wins",
            "who would win",
            "fights ",
            " fought ",
            " battle ",
            " battles ",
            " against ",
        ]
    )


def _count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’:-]*", text))


STRONG_ACTION_MARKERS = (
    "infinity", "blue", "red", "purple", "domain", "black flash", "rasengan", "chidori",
    "bankai", "gear", "hollow", "kamehameha", "bungee gum", "nen", "clone", "clones",
    "punch", "punches", "kick", "kicks", "flick", "flicks", "grab", "grabs", "snatch",
    "snatches", "pull", "pulls", "freeze", "freezes", "stop", "stops", "slam", "slams",
    "smash", "smashes", "break", "breaks", "shatter", "shatters", "crash", "crashes",
    "bolt", "bolts", "launch", "launches", "rocket", "rockets", "teleport", "teleports",
    "stretch", "stretches", "swallow", "swallows", "bite", "bites", "explode", "explodes",
    "rebound", "rebounds", "block", "blocks", "slash", "slashes", "cut", "cuts",
    "sprint", "sprints", "jog", "jogs", "run", "runs", "dash", "dashes",
    "die", "dies", "kill", "kills", "drops dead", "restart", "restarts", "revive", "revives",
    "stands back up", "gets back up",
    "hit", "hits", "fold", "folds", "rush", "rushes", "licks", "pins", "burns", "rips",
    "dodge", "dodges", "walk", "walks", "step", "steps", "approach", "approaches",
    "steal", "steals", "pluck", "plucks",
)

REACTION_ONLY_MARKERS = (
    "stares", "staring", "watches", "watching", "sweats", "sweating", "gasps", "gasping",
    "realizes", "notices", "reacts", "reacting", "looks", "looking", "side-eyes",
    "side eyes", "jaw drops", "freezes up", "goes silent",
)

PASSIVE_PREMISE_MARKERS = (
    "refuses to",
    "won't",
    "will not",
    "doesn't",
    "does not",
    "just stands there",
    "stands there",
    "does nothing",
    "won't move",
    "refuses to move",
)

DEATH_OR_REVIVAL_MARKERS = (
    "death note",
    "dies",
    "die",
    "dead",
    "heart attack",
    "restart his own heart",
    "restart her own heart",
    "revive",
    "revives",
    "revived",
    "resurrect",
    "resurrection",
    "stands back up",
    "gets back up",
    "comes back",
)

PLAIN_LANGUAGE_DEATH_MARKERS = (
    "dies",
    "drops dead",
    "the death note kills",
    "kills anyone whose name",
    "if i write your name, you die",
    "write your name, you die",
    "the person dies",
    "heart stops",
    "falls dead",
    "dead on the floor",
    "kills him",
    "kills her",
)

PLAIN_LANGUAGE_COMEBACK_MARKERS = (
    "stands back up",
    "gets back up",
    "comes back",
    "won't stay dead",
    "is back up",
    "restart my own heart",
    "restarted my own heart",
    "restarts his own heart",
    "restarts his heart",
    "restarts her own heart",
    "restarts her heart",
    "revives",
    "revived",
    "resurrects",
    "back on his feet",
    "back on her feet",
)

STORY_TURN_MARKERS = (
    "but", "instead", "until", "then", "suddenly", "tries again", "writes again",
    "won't stay dead", "stands back up", "gets back up", "comes back",
    "backfires", "counter", "counters", "reverses", "turns on", "survives",
    "dodges", "snatches", "steals", "rips", "burns", "pins",
)

ABSTRACT_ENDING_MARKERS = (
    "realizes", "rattled", "interested than before", "finally met someone",
    "finally met", "enjoyed it", "understands", "learns", "knows now",
)

FINAL_VISUAL_MARKERS = (
    "hands", "hand", "shoves", "shove", "burns", "burn", "rips", "rip",
    "pins", "pin", "drops", "drop", "kneels", "kneel", "crashes", "crash",
    "collapses", "collapse", "explodes", "explode", "wins", "win", "loses",
    "lose", "dragged", "drags", "blasts", "blast", "snaps", "snap", "stamps", "stamp",
)

DIALOGUE_SKIT_PREMISE_MARKERS = (
    "death note",
    "notebook",
    "writes",
    "rewrites",
    "interrogates",
    "threatens",
    "warns",
    "bargains",
    "lies to",
    "bluffs",
    "stalks",
    "turns the hunt back",
    "turns the scene into a chase",
)

LARGE_EVENT_MARKERS = (
    "exam",
    "selection",
    "tournament",
    "war",
    "invasion",
    "arc",
    "raid",
    "forest of death",
    "hunter exam",
    "chunin",
)

_DIALOGUE_VERB_PATTERN = re.compile(
    r"\b("
    r"says|said|yells|yelled|asks|asked|blurts|mutters|whispers|shouts|shouted|"
    r"screams|screamed|laughs|laughing|snaps|snapped|groans|groaned|taunts|taunted|"
    r"replies|replied|calls out|called out|mocks|mocked|goes|cuts in|cut in"
    r")\b",
    re.IGNORECASE,
)


def _has_strong_action(line: str) -> bool:
    lowered = line.lower()
    return any(_contains_marker(lowered, marker) for marker in STRONG_ACTION_MARKERS)


def _is_reaction_only_line(line: str) -> bool:
    lowered = line.lower()
    return any(_contains_marker(lowered, marker) for marker in REACTION_ONLY_MARKERS) and not _has_strong_action(line)


def _is_passive_premise(title: str, brief: str) -> bool:
    lowered = f"{title} {brief}".lower()
    return any(_contains_marker(lowered, marker) for marker in PASSIVE_PREMISE_MARKERS)


def _needs_explicit_death_comeback_explanation(brief: str, key_facts: str) -> bool:
    lowered = f"{brief} {key_facts}".lower()
    if not _contains_marker(lowered, "death note"):
        return False
    return any(_contains_marker(lowered, marker) for marker in DEATH_OR_REVIVAL_MARKERS)


def _has_marker(lines: list[str], markers: tuple[str, ...], *, window: slice | None = None) -> bool:
    target_lines = lines[window] if window is not None else lines
    lowered = " ".join(target_lines).lower()
    return any(_contains_marker(lowered, marker) for marker in markers)


def _contains_marker(text: str, marker: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", text) is not None


def _has_story_turn(lines: list[str]) -> bool:
    if len(lines) < 4:
        return True
    return _has_marker(lines, STORY_TURN_MARKERS, window=slice(2, None))


def _has_final_visual_payoff(line: str) -> bool:
    lowered = line.lower()
    return _has_strong_action(line) or any(_contains_marker(lowered, marker) for marker in FINAL_VISUAL_MARKERS)


def _is_abstract_ending_line(line: str) -> bool:
    lowered = line.lower()
    return any(_contains_marker(lowered, marker) for marker in ABSTRACT_ENDING_MARKERS) and not _has_final_visual_payoff(line)


def _should_use_dialogue_skit(
    title: str,
    brief: str,
    key_facts: str,
    structure: str,
    format_strategy: str | None = None,
) -> bool:
    format_strategy = normalize_format_strategy(format_strategy)
    if format_strategy not in {"attack_result", "mini_story"}:
        return False
    if _is_vs_matchup(title, brief):
        return False

    lowered = f"{title} {brief} {key_facts} {structure}".lower()
    if not any(_contains_marker(lowered, marker) for marker in DIALOGUE_SKIT_PREMISE_MARKERS):
        return False

    # Big canon-event crossovers usually read better as voiceover mini-stories.
    if any(_contains_marker(lowered, marker) for marker in LARGE_EVENT_MARKERS) and not _contains_marker(lowered, "death note"):
        return False

    return True


def _scene_video_prompt_has_dialogue(video_prompt: str | None) -> bool:
    if not isinstance(video_prompt, str):
        return False
    return bool(_DIALOGUE_VERB_PATTERN.search(video_prompt))


def _validate_dialogue_skit_scenes(
    scenes: list[dict],
    *,
    brief: str = "",
    key_facts: str = "",
    format_strategy: str | None = None,
) -> None:
    format_strategy = normalize_format_strategy(format_strategy)
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("NightNight dialogue skit needs scene data.")
    if not 3 <= len(scenes) <= 5:
        raise ValueError(f"NightNight dialogue skit needs 3-5 scenes, got {len(scenes)}.")

    total_duration = 0.0
    for idx, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"NightNight scene {idx + 1} is not an object.")
        image_prompt = str(scene.get("image_prompt") or "").strip()
        video_prompt = str(scene.get("video_prompt") or "").strip()
        characters = scene.get("characters")
        duration = float(scene.get("duration") or 0)
        if not image_prompt or not video_prompt:
            raise ValueError(f"NightNight scene {idx + 1} is missing prompts.")
        if not isinstance(characters, list) or not characters:
            raise ValueError(f"NightNight scene {idx + 1} needs at least one named character.")
        if not _scene_video_prompt_has_dialogue(video_prompt):
            raise ValueError(
                f"NightNight scene {idx + 1} needs explicit spoken dialogue in video_prompt."
            )
        if duration <= 0 or duration > 4.5:
            raise ValueError(
                f"NightNight scene {idx + 1} duration should stay between 0 and 4.5 seconds."
            )
        total_duration += duration

    if total_duration > 18:
        raise ValueError(f"NightNight dialogue skit is too long ({total_duration:.1f}s > 18s).")

    early_prompts = " ".join(str(scene.get("video_prompt") or "") for scene in scenes[:2]).lower()
    if _needs_explicit_death_comeback_explanation(brief, key_facts):
        has_death = any(_contains_marker(early_prompts, marker) for marker in PLAIN_LANGUAGE_DEATH_MARKERS)
        has_comeback = any(_contains_marker(" ".join(str(scene.get("video_prompt") or "") for scene in scenes[:4]).lower(), marker) for marker in PLAIN_LANGUAGE_COMEBACK_MARKERS)
        if not (has_death and has_comeback):
            raise ValueError(
                "NightNight dialogue skit must clearly say the death rule and the comeback in plain English."
            )

    final_blob = f"{scenes[-1].get('image_prompt', '')} {scenes[-1].get('video_prompt', '')}".lower()
    if not any(_contains_marker(final_blob, marker) for marker in FINAL_VISUAL_MARKERS):
        raise ValueError(
            "NightNight dialogue skit ending needs a visible physical payoff, not just a mood beat."
        )


def _validate_nightnight_script_text(
    narration_lines: list[str],
    format_strategy: str | None = None,
    *,
    brief: str = "",
    key_facts: str = "",
) -> None:
    format_strategy = normalize_format_strategy(format_strategy)
    format_spec = get_format_strategy_spec(format_strategy)
    min_lines = int(format_spec["min_lines"])
    max_lines = int(format_spec["max_lines"])

    if not min_lines <= len(narration_lines) <= max_lines:
        raise ValueError(
            f"NightNight {format_strategy} script must have {min_lines}-{max_lines} lines, got {len(narration_lines)}"
        )

    too_long_lines = [
        f"line {idx + 1} ({_count_words(line)} words)"
        for idx, line in enumerate(narration_lines)
        if _count_words(line) > 15
    ]
    if too_long_lines:
        raise ValueError(f"NightNight lines exceed 15 words: {', '.join(too_long_lines)}")

    if len(narration_lines) >= 2 and not _has_strong_action(narration_lines[1]):
        raise ValueError(
            "NightNight line 2 needs a clear power/action beat early. "
            "Do not open with a soft reaction/setup line."
        )

    action_pool = narration_lines if len(narration_lines) == 1 else narration_lines[1:]
    action_lines = [
        idx + (1 if len(narration_lines) == 1 else 2)
        for idx, line in enumerate(action_pool)
        if _has_strong_action(line)
    ]
    if len(narration_lines) == 1:
        required_action_lines = 1
    else:
        required_action_lines = min(len(action_pool), int(format_spec["min_action_lines"]))
    if len(action_lines) < required_action_lines:
        raise ValueError(
            f"NightNight needs at least {required_action_lines} strong action/power lines for {format_strategy}; "
            f"only found {len(action_lines)}."
        )

    weak_reaction_lines = [
        idx + 1 for idx, line in enumerate(narration_lines[1:-1], start=1)
        if _is_reaction_only_line(line)
    ]
    if weak_reaction_lines:
        joined = ", ".join(str(idx) for idx in weak_reaction_lines)
        raise ValueError(
            f"NightNight has reaction-only mid-script lines ({joined}). "
            "Replace them with visible power use, collisions, or canon-rule breakage."
        )

    if format_strategy in {"mini_story", "full_story"} and not _has_story_turn(narration_lines):
        raise ValueError(
            "NightNight mini stories need a real midpoint turn. Add a counter, survival reveal, "
            "new tactic, betrayal, or canon-rule reversal by line 3 or 4."
        )

    if _is_abstract_ending_line(narration_lines[-1]):
        raise ValueError(
            "NightNight ending is too abstract. Finish on a visible final beat or verdict, "
            "not just a theme/reaction summary."
        )

    if _needs_explicit_death_comeback_explanation(brief, key_facts):
        early_window = slice(0, min(len(narration_lines), 4))
        has_death = _has_marker(narration_lines, PLAIN_LANGUAGE_DEATH_MARKERS, window=early_window)
        has_comeback = _has_marker(narration_lines, PLAIN_LANGUAGE_COMEBACK_MARKERS, window=early_window)
        if not (has_death and has_comeback):
            raise ValueError(
                "NightNight crossover needs the death/comeback rule explained in plain English early. "
                "Say the victim dies, then clearly say they stand back up or restart their heart."
            )


def _validate_nightnight_script_audio(
    narration_lines: list[str],
    narr_dir: str,
    format_strategy: str | None = None,
) -> None:
    format_strategy = normalize_format_strategy(format_strategy)
    format_spec = get_format_strategy_spec(format_strategy)
    total_duration = 0.0
    for idx in range(len(narration_lines)):
        narr_path = os.path.join(narr_dir, f"line_{idx:02d}.mp3")
        total_duration += get_duration(narr_path)

    max_duration = float(format_spec["max_duration"])
    # NightNight shorts often need a little extra room for canon names, rule explanations,
    # and now dialogue-style mini stories. Treat anything under ~40s as acceptable instead
    # of hard-failing on tiny overages like 28.1s.
    channel_max_duration = max(max_duration, 40.0)
    if total_duration > channel_max_duration:
        raise ValueError(
            f"NightNight narration is too long for {format_strategy} ({total_duration:.1f}s > {channel_max_duration:.1f}s). "
            "Tighten the script before image generation."
        )


async def build_nightnight(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full NightNightShorts video build using unified pipeline."""
    title = concept.get("title", "Untitled")
    narration_lines = concept.get("narration", [])
    brief = concept.get("brief", title)
    key_facts = str(concept.get("key_facts") or "")
    structure = str(concept.get("structure") or "")
    format_strategy = infer_format_strategy(concept, form_type="short")
    format_spec = get_format_strategy_spec(format_strategy)
    format_description = FORMAT_STRATEGY_DESCRIPTIONS[format_strategy]
    concept["format_strategy"] = format_strategy
    is_vs_matchup = _is_vs_matchup(title, brief)
    tags = TAGS + (["vs", "battle", "anime fight", "who would win"] if is_vs_matchup else [])

    narr_dir = os.path.join(output_dir, "narration")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [narr_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    # ─── STEP 1: Write script if not provided ───
    from packages.clients.claude import generate as claude_generate

    passive_premise = _is_passive_premise(title, brief)
    use_dialogue_skit = _should_use_dialogue_skit(
        title,
        brief,
        key_facts,
        structure,
        format_strategy,
    )

    def _generate_script(
        rewrite_reason: str | None = None,
        previous_lines: list[str] | None = None,
        rewrite_attempt: int = 0,
    ) -> tuple[list[str], str]:
        prompt = SCRIPT_PROMPT.format(
            title=title,
            brief=brief,
            key_facts=key_facts,
            structure=structure,
            format_strategy=format_strategy,
            format_description=format_description,
            min_lines=int(format_spec["min_lines"]),
            max_lines=int(format_spec["max_lines"]),
            max_duration=float(format_spec["max_duration"]),
        )
        if passive_premise:
            prompt += (
                "\n\nPassive-premise rule:\n"
                "- This premise sounds passive, stubborn, or unmoving.\n"
                "- Do NOT waste lines on the visitor merely refusing and everyone reacting.\n"
                "- Keep the refusal, but make the world force ACTION around it: tests, attacks, school rules, counters, or punishments slam into the visitor and visibly fail.\n"
                "- At least three post-hook lines must show distinct physical consequences while the visitor barely moves.\n"
                "- The humor should come from overwhelming collisions, busted rules, and embarrassed opponents — not from silence alone.\n"
            )
        if rewrite_reason:
            prompt += (
                "\n\nRewrite requirement:\n"
                f"- The last draft failed for this reason: {rewrite_reason}\n"
                "- Fix that problem while keeping the title idea and canon event the same.\n"
                "- Make the script more engaging, more power-heavy, and more visually literal.\n"
            )
        if previous_lines:
            prompt += (
                "\nPrevious failed draft:\n"
                + "\n".join(f"- {line}" for line in previous_lines)
                + "\n- Rewrite it into a stronger version instead of repeating the same structure.\n"
            )
        if rewrite_attempt >= 1:
            prompt += (
                "\nSecond-pass correction:\n"
                "- Be shorter and sharper than the previous draft.\n"
                "- No line may exceed 15 words.\n"
                "- If the hook or ending is too long, use the shortest clear spoken version.\n"
                "- Every post-hook line should contain a distinct visible move, blast, counter, aura burst, collapse, or impact.\n"
            )
        resp = claude_generate(
            prompt=prompt,
            max_tokens=2000,
        )
        json_match = re.search(r'\{.*\}', resp, re.DOTALL)
        generated_lines: list[str] = []
        generated_title = title
        if json_match:
            script_data = json.loads(json_match.group())
            generated_lines = script_data.get("narration", [])
            if script_data.get("title"):
                generated_title = script_data["title"]
            if script_data.get("format_strategy"):
                normalized = normalize_format_strategy(script_data.get("format_strategy"), default=format_strategy)
                if normalized != format_strategy:
                    logger.info(
                        "nightnight script format mismatch corrected",
                        requested=format_strategy,
                        generated=normalized,
                    )
        if not generated_lines:
            raise ValueError("Failed to generate narration script")
        return generated_lines, generated_title

    def _generate_dialogue_skit(
        rewrite_reason: str | None = None,
        previous_scenes: list[dict] | None = None,
        rewrite_attempt: int = 0,
    ) -> tuple[dict, str]:
        prompt = DIALOGUE_SKIT_PROMPT.format(
            title=title,
            brief=brief,
            key_facts=key_facts,
            structure=structure,
            format_strategy=format_strategy,
            format_description=format_description,
            art_style=ART_STYLE,
        )
        if rewrite_reason:
            prompt += (
                "\n\nRewrite requirement:\n"
                f"- The last skit draft failed for this reason: {rewrite_reason}\n"
                "- Fix that problem while keeping the premise and ending idea the same.\n"
                "- Make the spoken beats clearer and easier for a cold viewer to follow.\n"
            )
        if previous_scenes:
            prompt += "\nPrevious failed skit scenes:\n"
            for idx, scene in enumerate(previous_scenes, start=1):
                prompt += (
                    f"- Scene {idx}: image={scene.get('image_prompt', '')}\n"
                    f"  video={scene.get('video_prompt', '')}\n"
                )
            prompt += "- Rewrite into a cleaner, more obvious story instead of repeating the same beats.\n"
        if rewrite_attempt >= 1:
            prompt += (
                "\nSecond-pass correction:\n"
                "- Shorter lines, clearer cause-and-effect, stronger physical ending.\n"
                "- If the rule is confusing, have a character say it plainly.\n"
                "- Do not rely on silent reaction shots to explain the plot.\n"
            )

        resp = claude_generate(
            prompt=prompt,
            max_tokens=2500,
        )
        json_match = re.search(r'\{.*\}', resp, re.DOTALL)
        if not json_match:
            raise ValueError("Failed to generate dialogue skit JSON")
        skit_data = json.loads(json_match.group())
        scenes = skit_data.get("scenes", [])
        if not scenes:
            raise ValueError("Failed to generate dialogue skit scenes")

        skit_title = skit_data.get("title") or title
        skit_concept = dict(concept)
        skit_concept.update({
            "title": skit_title,
            "channel_id": CHANNEL_ID,
            "format_strategy": format_strategy,
            "narration_style": "none",
            "audio_policy": "native_dialogue",
            "scenes": scenes,
            "narration": [],
            "tags": tags + ["anime skit", "dialogue"],
        })
        return skit_concept, skit_title

    if use_dialogue_skit:
        dialogue_concept = dict(concept)
        dialogue_title = title
        if concept.get("scenes"):
            dialogue_concept = dict(concept)
            dialogue_concept.update({
                "title": title,
                "channel_id": CHANNEL_ID,
                "format_strategy": format_strategy,
                "narration_style": "none",
                "audio_policy": "native_dialogue",
                "narration": [],
                "tags": tags + ["anime skit", "dialogue"],
            })
        else:
            await _update_step("writing skit scenes")
            dialogue_concept, dialogue_title = _generate_dialogue_skit()

        rewrite_attempt = 0
        max_rewrite_attempts = 3
        while True:
            try:
                _validate_dialogue_skit_scenes(
                    dialogue_concept.get("scenes", []),
                    brief=brief,
                    key_facts=key_facts,
                    format_strategy=format_strategy,
                )
                break
            except ValueError as exc:
                if concept.get("script_locked") or rewrite_attempt >= max_rewrite_attempts:
                    raise
                rewrite_attempt += 1
                await _update_step("rewriting skit")
                dialogue_concept, dialogue_title = _generate_dialogue_skit(
                    rewrite_reason=str(exc),
                    previous_scenes=dialogue_concept.get("scenes", []),
                    rewrite_attempt=rewrite_attempt,
                )

        from apps.orchestrator.pipeline import _run_no_narration

        await _run_no_narration(run_id, dialogue_concept, output_dir, _update_step, db_url)
        logger.info("nightnight dialogue skit complete", run_id=run_id, title=dialogue_title)
        return

    if not narration_lines:
        await _update_step("writing script")
        narration_lines, title = _generate_script()

    rewrite_attempt = 0
    max_rewrite_attempts = 3
    while True:
        try:
            _validate_nightnight_script_text(
                narration_lines,
                format_strategy,
                brief=brief,
                key_facts=str(concept.get("key_facts") or ""),
            )
            break
        except ValueError as exc:
            if concept.get("script_locked") or rewrite_attempt >= max_rewrite_attempts:
                raise
            rewrite_attempt += 1
            await _update_step("rewriting script")
            narration_lines, title = _generate_script(
                rewrite_reason=str(exc),
                previous_lines=narration_lines,
                rewrite_attempt=rewrite_attempt,
            )

    n_lines = len(narration_lines)

    # ─── STEP 2: Narration ───
    await _update_step("generating narration")
    await generate_narration_with_timestamps(
        narration_lines, narr_dir, output_dir, VOICE_ID, _update_step,
        voice_settings=VOICE_SETTINGS,
    )
    _validate_nightnight_script_audio(narration_lines, narr_dir, format_strategy)

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
    actual_teaser_dur = build_intro_teasers(
        n_lines, narr_dir, clips_dir, segments_dir, line_clip_map,
        channel_id=CHANNEL_ID, concept=concept,
    )

    await _update_step("concatenating")
    teasers_path = os.path.join(segments_dir, "teasers.mp4")
    all_video_path, total_dur = concat_silent_video(teasers_path, segments_dir, n_lines, output_dir)

    await _update_step("building audio")
    audio_path, seg_starts = build_numpy_audio(
        n_lines, narr_dir, MUSIC_PATH, actual_teaser_dur, seg_durations, total_dur, output_dir,
        channel_id=CHANNEL_ID, concept=concept,
    )

    await _update_step("combining")
    combined = combine_video_audio(all_video_path, audio_path, output_dir)

    await _update_step("adding subtitles")
    with open(os.path.join(output_dir, "word_timestamps.json")) as f:
        word_data = json.load(f)
    add_subtitles(combined, word_data, seg_starts, output_dir)

    await update_database(run_id, CHANNEL_ID, title, output_dir, db_url, tags)
    logger.info("nightnight complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
