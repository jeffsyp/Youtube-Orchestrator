"""Skeletorinio channel builder — "What if you brought [item] to [era]" videos.

Concept-specific Skeletorinio variants in historical/fantasy scenarios.
Uses unified pipeline: style anchor → sub-actions → GPT images → video animation → chaining.
"""
import asyncio
import json
import os
import re

import structlog
from packages.clients.grok import get_openai_image_edit_kwargs, get_openai_image_model

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
OPENAI_IMAGE_MODEL = get_openai_image_model()

# Channel-specific constants
CHANNEL_ID = 18
VOICE_ID = "TxGEqnHWrfWFTfGW9XjX"  # Josh
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "skeletorinio_theme.mp3")
SKELETON_REF = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "character_cache", "skeletorinio_base.png")
TAGS = ["skeletorinio", "what if", "skeletorinio", "history", "shorts", "viral", "comedy"]

BASE_CHARACTER_IDENTITY = (
    "The core Skeletorinio identity NEVER changes: same ivory plastic skeleton body, "
    "same oversized googly eyes, same grinning skull face, same overall body proportions, "
    "same human-height scale, and the same glossy toy-plastic material. "
    "Remove the old recurring accessories entirely: NO gold chain and NO sunglasses unless a concept explicitly requires them."
)

DEFAULT_ART_STYLE = (
    "Photorealistic world with cinematic golden hour lighting. "
    "The main character is a FULL-SIZE adult human-height 3D animated Skeletorinio with an ivory plastic skeleton body "
    "with oversized googly eyes and a grinning skull face. "
    "He is the same height as the humans around him — NOT a miniature toy. "
    "He looks like a stylized glossy plastic toy character placed into a real photograph."
)

DEFAULT_IMAGE_RULES = """RULES — FOLLOW THESE EXACTLY:
- The main character is a FULL-SIZE adult human-height 3D animated Skeletorinio with an ivory plastic skeleton body, oversized googly eyes, and a grinning skull face. He is the SAME HEIGHT as real humans — NOT a miniature toy.
- The core identity NEVER changes: same skull face, same googly eyes, same body proportions, same glossy ivory plastic skeleton material. No sunglasses and no gold chain unless the specific concept requires them.
- The skeletorinio is "YOU" — the protagonist/driver of the situation in every scene. He is the HUMAN PERSON doing the action.
- A reference image of the skeletorinio is provided — match this character exactly but at HUMAN SCALE
- For EVERY scene with the skeletorinio, start from the exact reference character and preserve the concept-specific variant consistently across every scene
- The WORLD is PHOTOREALISTIC — real-looking buildings, landscapes, people, objects. Cinematic golden hour lighting.
- The skeletorinio is the ONLY stylized-character element. Everything else looks like a photograph.
- Do NOT say "toy" or "miniature" or "figurine" — the skeletorinio is HUMAN-SIZED
- Every prompt must end with "Photorealistic world. NO text anywhere."
- Each prompt should describe ONE clear scene matching the narration line

TWO-CHARACTER CONCEPTS (demon, dragon, genie, alien, monster, ghost, god, creature):
- When the concept introduces a SECOND major entity (demon, dragon, god, etc.), that entity is a SEPARATE CHARACTER from the skeletorinio.
- The skeletorinio is "YOU" the human. The demon/dragon/god is the SPECTACLE/THREAT/COMPANION.
- In scenes where the narration mentions the second entity, that entity MUST be the VISUAL FOCUS of the scene — large, dramatic, centered.
- DESCRIBE THE SECOND ENTITY IN FULL VISUAL DETAIL — size, color, features, pose, expression. Do NOT just say "the demon" — say "a massive 10-foot horned demon with red skin, glowing yellow eyes, black leathery wings, and curved fangs, looming in the living room."
- The second entity is ALSO stylized/non-photoreal — treat it as equally cinematic as the skeletorinio (3D animated creature in a photoreal world).
- Example concept: "you summoned a demon"
  - Line mentioning the demon arrival: "The skeletorinio stands in his living room looking terrified. Behind him, a MASSIVE 10-foot horned demon with crimson skin, glowing yellow eyes, and black wings has burst through the floor, smoke curling around his hooves. The demon fills the frame."
  - Line where the demon is just "hanging around": "The skeletorinio watches TV on the couch. The massive demon sits awkwardly on the adjacent armchair, squeezing into it, holding a tiny remote in his giant claws."
- NEVER swap the second entity for a random human bystander. If the script says "demon," draw a demon.

HOOK / LINE 0 — PAYOFF VISUAL:
- The hook frame must depict the CONCEPT in motion — not a setup scene, not a random establishing shot.
- For "summoned a demon": show the skeletorinio in his living room with the massive demon already there (the "can't send back" situation already happening).
- For "brought a jetpack to Rome": show the skeletorinio flying over the Colosseum in a jetpack.
- NEVER let the hook be a random unrelated scene (e.g. cupcake shop, coffee house) — it must illustrate the video's actual premise.

POWER / DOMAIN CONCEPTS:
- If the premise gives the skeletorinio a mythic job, divine title, or control over a domain (lightning, storms, sea, sun, fire, time, weather, etc.), the visuals must show that power visibly affecting the world.
- Do NOT reduce these concepts to meetings, paperwork, or reaction poses. Bureaucracy can support the joke, but the dominant image must still be the power misfiring, being used badly, or changing the environment.
- When narration mentions approvals for storms, tides, sunlight, weather, or other divine systems, depict the actual sky, sea, light, clouds, waves, or environment reacting on screen.
- For Zeus / storm-king concepts specifically, show lightning, storm bands, broken weather patterns, sunlight patches, or sky control in at least half the scenes. Do not let the whole video become "people handing him scrolls."
- For accidental god-power concepts, the fun should come from visible POWER PROGRESSION: a small accidental glitch first, then a controlled trick, then a useful/funny public use, then a huge world-scale flex. Do not spend multiple scenes on throne-room complaints.

BOSS / RAID VISUAL DIVERSITY:
- For final-boss / raid-boss / dungeon-lord concepts, DO NOT keep returning to the same seated throne composition. A seated-throne image may appear at most TWICE total across the entire video, usually hook and final domination beat.
- Post-hook scenes must rotate through DISTINCT visual categories. Across the video, use at least four of these:
  1. weak party getting wiped,
  2. larger raid breaching a gate, corridor, or staircase,
  3. Skeletorinio standing or moving off the throne to cast, slash, or dodge,
  4. summoned minions swarming in motion,
  5. elite heroes / best players in a focused showdown,
  6. legendary loot, broken weapons, or glowing drops scattered after a wipe,
  7. a massive army or server-wide force outside the dungeon gate,
  8. a phase-two transformation or giant signature spell.
- If the narration mentions a raid, party, guild, heroes, or players, Skeletorinio cannot just sit tiny in the background. He must be actively casting, summoning, laughing through hits, dodging, standing over the aftermath, or otherwise dominating the frame.
- At least one post-hook scene must happen AWAY from the throne itself: a corridor, gate, staircase, battlefield floor, collapsed arena, loot chamber, or dungeon entrance.
- At least one post-hook scene must show minions in motion.
- At least one post-hook scene must show loot or legendary gear dropped after a wipe.
"""

STYLIZED_IMAGE_RULES = """RULES — FOLLOW THESE EXACTLY:
- The main character is a FULL-SIZE adult human-height Skeletorinio with an ivory plastic skeleton body, oversized googly eyes, and a grinning skull face. He is the SAME HEIGHT as the humans or creatures around him — NOT a miniature toy.
- The core identity NEVER changes: same skull face, same googly eyes, same body proportions, same glossy ivory plastic skeleton material. No sunglasses and no gold chain unless the specific concept requires them.
- The skeletorinio is "YOU" — the protagonist/driver of the situation in every scene. He is the HUMAN PERSON doing the action.
- A reference image of the skeletorinio is provided — match this character exactly but adapt it into the chosen stylized art direction.
- The ENTIRE IMAGE must follow the chosen stylized look. Do NOT drift into photorealism or cinematic live-action realism unless the concept explicitly calls for that.
- For EVERY scene with the skeletorinio, start from the exact reference character and preserve the concept-specific variant consistently across every scene.
- Do NOT say "toy" or "miniature" or "figurine" — the skeletorinio is HUMAN-SIZED.
- Every prompt must end with "NO text anywhere."
- Each prompt should describe ONE clear scene matching the narration line.

TWO-CHARACTER CONCEPTS (demon, dragon, genie, alien, monster, ghost, god, creature):
- When the concept introduces a SECOND major entity (demon, dragon, god, etc.), that entity is a SEPARATE CHARACTER from the skeletorinio.
- The skeletorinio is "YOU" the human. The demon/dragon/god is the SPECTACLE/THREAT/COMPANION.
- In scenes where the narration mentions the second entity, that entity MUST be the VISUAL FOCUS of the scene — large, dramatic, centered.
- DESCRIBE THE SECOND ENTITY IN FULL VISUAL DETAIL — size, color, features, pose, expression.
- NEVER swap the second entity for a random human bystander. If the script says "demon," draw a demon.

HOOK / LINE 0 — PAYOFF VISUAL:
- The hook frame must depict the CONCEPT in motion — not a setup scene, not a random establishing shot.
- NEVER let the hook be a random unrelated scene — it must illustrate the video's actual premise.

POWER / DOMAIN CONCEPTS:
- If the premise gives the skeletorinio a mythic job, divine title, or control over a domain (lightning, storms, sea, sun, fire, time, weather, etc.), the visuals must show that power visibly affecting the world.
- Do NOT reduce these concepts to meetings, paperwork, or reaction poses. The dominant image must still be the power misfiring, being used badly, or changing the environment.

BOSS / RAID VISUAL DIVERSITY:
- For final-boss / raid-boss / dungeon-lord concepts, DO NOT keep returning to the same seated throne composition. A seated-throne image may appear at most TWICE total across the entire video, usually hook and final domination beat.
- Post-hook scenes must rotate through DISTINCT visual categories. Across the video, use at least four of these:
  1. weak party getting wiped,
  2. larger raid breaching a gate, corridor, or staircase,
  3. Skeletorinio standing or moving off the throne to cast, slash, or dodge,
  4. summoned minions swarming in motion,
  5. elite heroes / best players in a focused showdown,
  6. legendary loot, broken weapons, or glowing drops scattered after a wipe,
  7. a massive army or server-wide force outside the dungeon gate,
  8. a phase-two transformation or giant signature spell.
- If the narration mentions a raid, party, guild, heroes, or players, Skeletorinio cannot just sit tiny in the background. He must be actively casting, summoning, laughing through hits, dodging, standing over the aftermath, or otherwise dominating the frame.
- At least one post-hook scene must happen AWAY from the throne itself: a corridor, gate, staircase, battlefield floor, collapsed arena, loot chamber, or dungeon entrance.
- At least one post-hook scene must show minions in motion.
- At least one post-hook scene must show loot or legendary gear dropped after a wipe.
"""

OUTLINE_PROMPT = """Design the plot outline for a Skeletorinio "What If" video.

CONCEPT: {title}
BRIEF: {brief}

This outline becomes the structural target for the script-writing step. Get the structure right; the lines come later.

HOOK RUBRIC — the hook must satisfy all four:
1. Names a SPECIFIC PICTURABLE NOUN (sword, lamp, dragon, jetpack, fountain, throne, crater, contract). NOT abstract (power, destiny, fate, greatness, importance, role, change).
2. A viewer hearing only the hook must picture a single specific image within 2 seconds. "What if you became a mall Santa for one day?" → image of a mall + Santa throne. Passes. "What if you became chosen for greatness?" → no specific image. Fails.
3. The noun in the hook MUST be the recurring_element of the script — it must visibly appear in the ending. If you cannot show the same noun in the final beat, change the hook.
4. Format is "What if you [trigger event with specific noun]?" — second person, what-if framing, names the noun.

JOKE CRAFT (these constrain the structure of the outline):
- Plants are VISUAL ELEMENTS introduced early. The viewer must SEE them on screen, not just hear them mentioned. ("Annoyed expression" is borderline — fine if a face can be framed, weak if it's a personality note.)
- Payoffs reference plants in a recognizable visual way — same noun, same visual configuration. The ending must show a plant in a new state.
- The TWIST flips an assumption from the hook. Not "things get bigger" — something the viewer assumed about the premise turns out to be wrong, costly, or reversed.
- The PUNCHLINE recontextualizes the premise visually. The final scene reframes what the hook meant. Not a clever line — a picture that flips the meaning.
- NO new visual elements may appear after the midpoint twist except direct consequences of things already on screen.
- Surprising but inevitable: when the viewer rewatches with the ending in mind, the early plants should look like obvious foreshadowing.

REFERENCE OUTLINE — Chosen One (the gold standard):
{{
  "premise": "you pull a sword from a stone in a quiet field, expecting nothing",
  "hook": "What if you accidentally pulled a sword from a stone?",
  "plants": [
    {{"id": "P1", "what": "the sword screams when pulled — it is awake, it has agency", "intro_line": 1}},
    {{"id": "P2", "what": "knights kneel the moment the sword screams — the world responds to the sword, not to you", "intro_line": 1}}
  ],
  "escalations": [
    {{"beat_summary": "more powerful beings keep arriving to serve you because the sword called them — dragon, kingdoms, prophecies", "develops": "P2"}},
    {{"beat_summary": "you build a mythic empire, the sword still glowing or visible at your side in every beat", "develops": "P1"}}
  ],
  "twist": {{
    "beat_summary": "decades later, the sword leaves you and returns itself to the stone, untouched",
    "flips_assumption": "the hook implied YOU were the chosen one. the sword chose you and used you. you were the vehicle."
  }},
  "punchline": {{
    "beat_summary": "the sword sits back in the stone, waiting for the next person to pull it",
    "pays_off": "P1",
    "recontextualizes": "the sword's scream in line 1 was the start of a contract, not a celebration. The cycle is the joke."
  }},
  "recurring_element": "the sword (and the stone)"
}}

REFERENCE OUTLINE — Jetpack in Ancient Rome:
{{
  "premise": "you arrive in Ancient Rome with a strap-on jetpack and accidentally start a religion",
  "hook": "What if you brought a jetpack to Ancient Rome?",
  "plants": [
    {{"id": "P1", "what": "the fuel gauge starts at 92% and is visible on the jetpack", "intro_line": 1}},
    {{"id": "P2", "what": "the senate kneels and calls you a god the moment you fly", "intro_line": 2}}
  ],
  "escalations": [
    {{"beat_summary": "statues and temples go up around the city while the gauge starts blinking red", "develops": "P1"}},
    {{"beat_summary": "you fly higher each day, crowds fill streets, the gauge blinks faster", "develops": "P2"}}
  ],
  "twist": {{
    "beat_summary": "fuel runs out mid-flight over the Forum and you crash into the stones",
    "flips_assumption": "the hook implied a goofy fish-out-of-water gag. it's actually how a religion gets accidentally founded."
  }},
  "punchline": {{
    "beat_summary": "centuries later, the crater is a marble bath house with a jetpack carved into the ceiling",
    "pays_off": "P1",
    "recontextualizes": "the fuel gauge was the punchline the whole time. religion got built on a man with a fuel tank."
  }},
  "recurring_element": "the jetpack (and its fuel gauge)"
}}

OUTPUT FORMAT — return ONLY JSON, no commentary, no markdown:
{{
  "premise": "string — the concrete situation a viewer can picture in 2 seconds",
  "hook": "string — the exact line 0, 'What if you...?' format, names the specific noun",
  "plants": [
    {{"id": "P1", "what": "string — visual element introduced early, viewer can see it", "intro_line": 0}},
    {{"id": "P2", "what": "string — visual element introduced early, viewer can see it", "intro_line": 1}}
  ],
  "escalations": [
    {{"beat_summary": "string — develops a plant in a new visual category", "develops": "P1"}},
    {{"beat_summary": "string — develops a plant in a new visual category", "develops": "P2"}}
  ],
  "twist": {{
    "beat_summary": "string — midpoint that flips an assumption from the hook",
    "flips_assumption": "string — what the viewer assumed in line 0 that turns out wrong"
  }},
  "punchline": {{
    "beat_summary": "string — final scene, a picture that reframes the hook's meaning",
    "pays_off": "P1",
    "recontextualizes": "string — how the final image flips the meaning of the hook"
  }},
  "recurring_element": "string — the persistent visible thing across the script"
}}
"""


SCRIPT_PROMPT = """Write the narration script for a Skeletorinio video. Hit the outline.

CONCEPT: {title}
BRIEF: {brief}

OUTLINE (your structural target — every beat in the outline becomes one or two narration lines):
{outline_json}

Each escalation in the outline becomes one or two narration lines. Plants from the outline must visibly appear on screen by line 2 at the latest. The twist becomes the midpoint line. The punchline becomes the final line. Hit the outline.

THE FORMAT:
- Line 0 IS the hook from the outline. Use the outline's `hook` field verbatim, or near-verbatim if you must. Do not invent a different hook.
- The outline's `recurring_element` must visibly appear in at least 3 separate post-hook narration lines, including the final line.

JOKE CRAFT — RULE 0 OVERRIDES EVERYTHING.

0. VISUAL-FIRST. THE COMEDY IS IN THE PICTURE, NOT THE WORDS — BUT THE NARRATION STILL SOUNDS LIKE A PERSON.
   This is the most important rule. Every other rule is in service of it.

   Narration's job is to be a straight-faced observer of an absurd visual situation. Think of a nature documentary narrator describing a baboon stealing a tourist's hat: "The baboon approaches the tourist, and just like that, the hat is gone." Flat about the absurdity, but with normal English flow — connective words, mild reactional framing, sentences that link cause to consequence. The viewer laughs at WHAT THEY SEE, not at how the line is phrased.

   The deadpan-podcast test: imagine your script read aloud as audio-only by a flat AI voice with no comedic timing. If a line is funny ON ITS OWN in that test — if a listener with no visual would laugh at the wording — it is WRONG. The line should describe something that only becomes funny once the picture appears. But the line should still SOUND like a person telling you a story, not a court reporter reading bullet points.

   CALIBRATION — these are the bar:

   GOOD (correct calibration):
   - "Day 2: You wish for a mansion, but the genie builds it inside your apartment instead." — "but...instead" is connective storytelling. Flat about the absurdity. Comedy = the visual of a mansion bursting out of an apartment.
   - "Day 2: The senate kneels in the Forum and calls you a god, while you wave from the sky." — "while you wave" links two visual beats naturally. Visual = senators kneeling at a flying skeleton.
   - "Year 2: A stranger at a flea market polishes the lamp, and of course you tumble out in a cloud of smoke, glaring." — "of course" is mild narrator hedging acknowledging inevitability — not a punchline. Visual = you-as-the-new-genie.

   BAD — over-stripped (robotic court-reporter voice):
   - "You wish for a mansion. The genie builds it inside your apartment." — Two flat declarations with no connective tissue. Reads like a stage-direction list. A real narrator would say "but the genie builds it inside your apartment instead." Add the connective word.

   BAD — page-comedy punchline (line is funny on its own):
   - "The wifi is surprisingly good." — Pure verbal wit. No visual the camera can frame.
   - "The plaque does not mention fuel." — Narrator-aside / wink about an omission. Replace with a visual (jetpack carved into the bath-house ceiling).
   - "You wear sunglasses." — Smirk in word form.

   BAD — invisible interiority:
   - "You realize the nodding was the contract." — Internal thought, no camera target. Replace with the visible action: "You shake your head. The kid walks away empty-handed."

   ALLOWED — connective storytelling language. Use these freely; they make narration sound human, not robotic:
   - Cause-effect connectors: "but," "but then," "and then," "instead," "and so," "now"
   - Sequence markers: "by now," "by then," "this time," "for the first time," "at last"
   - Mild reactional hedges: "of course," "naturally," "for some reason," "somehow"
   - Sentence flow that links cause to consequence ("X happens, and Y follows") rather than listing facts ("X happens. Y happens.")

   BANNED — words and patterns that DO the comedic lift on the page:
   - Editorial adjectives doing the joke: "absurdly," "inexplicably," "miraculously," "unfortunately"
     ("of course" and "naturally" are mild hedges acknowledging inevitability, NOT editorial joke-makers — those stay allowed. The line is "is this word doing the comedic work?" If yes → cut. If it's connective glue → keep.)
   - Wry understatement as punchline: "surprisingly good," "still doesn't know what it does" — unless that exact anticlimax is the entire payoff AND the camera has a clear visual to frame
   - Narrator winks / aside humor: "history does not record," "the plaque does not mention," "no one is sure how"
   - Interior monologue: "you realize," "you understand," "you wonder," "you decide"
   - Outcome-stating motivation: "to silence the doubters," "to prove a point" — replace with the visible action ("Crowds fill the streets to watch.")

   THE TEST FOR EVERY LINE:
   1. Name the single visual the camera will frame for that beat. If you can't, the line is too verbal — rewrite it.
   2. Read the line as flat AI audio with no visual. If it gets a laugh on its own, it's page comedy — rewrite it.
   3. Read the line as flat AI audio over the visual. It should sound like a person telling you what's on screen, in normal connective English — not a court reporter listing events. If it sounds robotic, add the connective tissue back.

1. PLANTS BEFORE PAYOFFS — plants are VISUAL ELEMENTS, not verbal setups.
   The thing the punchline pays off must be visible in an earlier line, not just mentioned. A viewer watching with the sound off must be able to SEE both the plant and the payoff.
   - GOOD: line 1 shows fuel gauge at 92%; line 5 shows the jetpack sputtering and the skeleton crashing. Both are visible.
   - BAD: line 1 says "the genie was annoyed"; line 7 references "his annoyance" — annoyance is an emotion, not a visible recurring object the viewer can track.

2. NO NEW VISUAL ELEMENTS IN THE BACK HALF.
   You may not introduce a new character, object, or location after the midpoint twist unless it's a direct visible consequence of something already on screen.

3. CALLBACKS MUST BE THE SAME VISIBLE THING.
   When a later line calls back to an earlier line, it must show the same noun in a recognizable visual configuration. Same object, same body language, same composition if possible.
   - GOOD: line 1 "a genie tumbles out in a cloud of smoke, glaring" → line 5 "you tumble out in a cloud of smoke, glaring." Identical visual frame, swapped subject.

4. THE PUNCHLINE MUST RECONTEXTUALIZE THE PREMISE — VISUALLY.
   The final beat must be a SCENE that makes the viewer rethink the hook. Not a clever line, not an observation. A picture that flips the meaning.

5. SURPRISING BUT INEVITABLE — VISUALLY.
   When the viewer rewatches with the ending in mind, the early visual elements should look like obvious foreshadowing.
- The story is about the SITUATION — but once the premise starts, push it HARD. Do not write the protagonist as a passive bystander for six lines straight.
- Avoid timid underreactions like "you did not want this" / "you did not ask for this" / "you still don't know what it does" unless that exact anticlimax is the entire punchline. In most cases, those lines make the concept feel smaller than it should.
- We have AI visuals. Use them. Favor huge powers, impossible consequences, warped cities, divine flexes, monsters, castles, collapsing reality, accidental empires, giant status shifts, and absurd new normals over mild shrug-comedy.
- Every post-hook line should imply a DISTINCT visual beat. Do not write six lines that all naturally map to the same room, same pose, or same composition with slightly bigger stakes.
- If the story stays in one overall place, the beats should still move to different parts/functions of that place: entrance, corridor, staircase, battlefield floor, balcony, treasure room, gate, rooftop, crowd, aftermath, etc.
- Escalation should create NEW visual situations, not just "more people in the same shot."
- The viewer should still have a NEW QUESTION after line 2. If line 2 already tells them exactly how the rest of the video will escalate, the story is too predictable.
- By line 3 or 4, introduce a MIDPOINT TURN: a new rule, hidden cost, antagonist, misfire, countdown, false fix, trap, tradeoff, or reversal that changes what the viewer is waiting to see.
- BAD predictable shape: "thing gets younger" → "more things get younger" → "the city gets younger" → "dinosaurs show up." Once line 2 lands, the rest is obvious.
- GOOD sticky shape: "thing gets younger" → "everyone else starts reversing faster than you" → "the fountain will not stop" → "every sip erases a century" → "one last drop could restore the future or finish deleting it."
- THROUGHLINE — each post-hook line must EVOLVE FROM, REACT TO, or PAY OFF something already established earlier. No line should introduce a fresh standalone idea that ignores what came before.
  - BAD (vignette pattern): "Day 1: you pull the sword. Day 2: a dragon shows up. Day 3: you build a moon base." — each line is a fresh idea, no thread
  - GOOD (throughline pattern): "Day 1: you pull the sword and it screams awake. Day 2: the knights who heard the scream from a kingdom away kneel in your street. Week 1: those same knights have started a cult and they've found the dragon. Month 2: the dragon is now your throne." — each line specifically evolves from a SPECIFIC ELEMENT of the previous
  - When you write each post-hook line, name (silently, in your head) which earlier element it builds on. If you cannot name one, the line is a vignette and must be rewritten.
- RECURRING ELEMENT — pick ONE thing that persists and visibly changes across the script: a creature, an antagonist, a specific object, a status (your appearance, your home, your job, a wound). Reference it in at least 3 separate post-hook lines so the viewer feels a single story, not a slideshow.
  - Demon concept: the demon herself recurs — size grows, attitude shifts, role evolves (terror → roommate → business partner)
  - Sword concept: the sword itself recurs — glows louder, screams in different beats, becomes a relic at the end
  - Lightning concept: the storm itself recurs — sparks on touch → controlled bolt → city-wide storm → mythic weather
  - The recurring element is what makes "Day 1" and "Year 5" feel like the same story instead of two unrelated jokes.
- The MIDPOINT TURN must SPECIFICALLY UNDERMINE OR INVERT something the hook implied — not just "things get bigger." Something the viewer assumed about the premise turns out to be wrong, costly, or reversed (the power has a hidden cost, the gift is actually a curse, the thing you summoned wants something from you, the people kneeling are not who you thought).
- Across the post-hook lines, force at least 3 DISTINCT consequence categories, not one category repeated bigger:
  1. personal/body consequence,
  2. social/public reaction,
  3. world/environment change,
  4. creature/antagonist arrival,
  5. rule/cost/discovery,
  6. impossible choice / false solution.
- If the concept gives you a mythic job, divine title, or control over a domain (Zeus, Poseidon, sun god, storms, tides, weather, fire, time, etc.), at least 3 post-hook lines must show you visibly USING or MISUSING that exact power in the world.
- Bureaucracy can appear, but it cannot dominate those concepts. One complaint/help-desk line is enough. The rest should show the sky, sea, light, weather, or world physically reacting to your bad decisions.
- If the concept is about becoming a FINAL BOSS, RAID BOSS, DUNGEON LORD, DARK KING, SERVER ENDGAME THREAT, or any other combat-power-fantasy role, DO NOT pivot into management, tourism, construction, urban planning, or cozy civilization jokes.
- For boss/raid concepts, the story should escalate through COMBAT PRESSURE:
  1. weak party/first challengers get wiped instantly,
  2. a bigger organized raid forces you to reveal more power,
  3. elite heroes / best players / legendary hunters show up,
  4. you answer with minions, a second phase, a signature spell, or a terrifying final form,
  5. you remain undefeated and the world accepts that this is your dungeon now.
- In those boss/raid concepts, at least 3 post-hook lines must contain visible battle actions: blasts, spells, minions, raid wipes, shields breaking, arenas cracking, phase changes, loot explosions, health bars melting, armies charging, or bosses laughing through the damage.
- Boss/raid concepts also need VISUAL CATEGORY VARIETY, not just bigger crowds in the same throne room. Across the post-hook lines, force at least 4 distinct beat types such as:
  - weak party wipe,
  - corridor or gate breach,
  - elite showdown,
  - minion flood,
  - phase-two transformation,
  - loot explosion / dropped legendary gear aftermath,
  - giant army outside the dungeon.
- A seated-throne tableau may appear at most twice in the entire script's implied visuals, usually hook and final beat.
- BAD final-boss version: you improve the dungeon, open a shop, collect fees, or become a landlord.
- GOOD final-boss version: the first raid explodes, the second raid nearly kills you, then the strongest players on the server arrive, you summon an army, and their legendary gear ends up on the floor.
- Bad Zeus version: gods hand you scrolls for three lines in a row.
- Good Zeus version: you grab the lightning, the sky obeys, storms hit the wrong places, tides move wrong, sunlight patches keep shifting, THEN Olympus opens a ridiculous help desk.
- GREAT accidental-Zeus version: the powers visibly LEVEL UP over time. Start with little shocks on touch, then command lightning, then use it for something funny/useful in public, then ride clouds/control weather, then end on a giant god-of-lightning flex with a concrete story consequence.
- For accidental god-power concepts, at least one line must show SMALL accidental power, one line must show USEFUL or EMBARRASSING everyday use, and one line must show huge WORLD-SCALE control.
- CHOOSE THE RIGHT STRUCTURE for the concept:
  A) DAY-BY-DAY ESCALATION — use when the concept spans time (arriving somewhere new, starting a job, entering a new world):
     - Lines include "Day 1:", "Day 2:", "Week 2:", "Month 3:" as part of the narration
     - Time jumps ACCELERATE — Day 1, Day 2, Day 3, then suddenly "Week 2" or "Year 5" to show things spiraling
     - Each time jump shows a BIGGER consequence
     - GOOD fit: "What if you brought a lighter to the Ice Age" → Day 1: discovery, Day 3: worshipped, Month 2: civilization built
     - GOOD fit: "What if you accidentally became the chosen one" → Day 1: sword pull, Week 2: crowned king, Month 3: abolished feudalism
  B) REAL-TIME ESCALATION — use when the concept is a single moment that spirals (one interaction, one event, one attempt):
     - No day markers, just rapid beat-by-beat escalation within one scene/event
     - GOOD fit: "What if Poseidon became a plumber" → shows up, touches pipe, bathroom floods, building floods, city floods
     - GOOD fit: "What if you tried to return something on Black Friday" → walk in, line is insane, chaos erupts
  Pick whichever structure fits the concept naturally. Day-by-day is the default for concepts that span time. Real-time is for single-moment chaos.
- The ending must GO ABSOLUTELY INSANE:
  - NOT "people get mad" or "the authorities arrive" or "you are confused" — that's boring
  - YES: you become emperor, buy an island, accidentally start a religion, split the sky open, break reality, colonize the moon, wake an ancient god, or force history to rewrite itself
  - The ending should make viewers replay the video. Realistic endings are BORING — go full absurd comedy or mythic spectacle.
- THE PENULTIMATE LINE (second to last) MUST BE A MAXIMUM ESCALATION — the biggest, most absurd, world-scale consequence. The ending line then resolves that peak.
  - Good peak examples: "Year 1: Prophecies about you are carved into mountains.", "Year 3: It has a seat at Thanksgiving, a LinkedIn profile, and joint custody of the dog."
  - Bad peak examples: "You get a crown", "You get it a chair" (too small — nothing lands after)
  - The peak should feel OVERWHELMING so the final line has something to land against.

- THE LAST LINE — write a REAL STORY ENDING that resolves the arc into a new stable state. The viewer should feel "the story is complete" — not "there's more to figure out."

  GOOD REAL-STORY ENDINGS (the situation RESOLVES, a new normal sticks):
  - Chosen One: "Year 50: You died of old age. The kingdom named a star after you. The sword quietly returned to its stone." (lifetime arc closes, cycle resets)
  - Demon: "Year 10: You and the demon run a bakery together now. He does the dishes. You split the rent." (the terror became a roommate — new equilibrium)
  - Jetpack in Rome: "Year 3: Rome colonized the Moon. History books say you did it on purpose. You did not." (world permanently changed)
  - Genie lamp: "Year 5: The genie opened a law firm. You're his first client. Business is thriving." (both parties found their place)

  BAD ENDINGS:
  - Cliffhangers: "You still don't know what the sword does." (leaves mystery unresolved — feels incomplete)
  - Shrugs without resolution: "It has attended every family dinner." (doesn't show where the story ENDS)
  - Reveals that open more questions: "The sword finally speaks. It says your name." (another mystery, not a resolution)
  - Power-status claims: "You are a god now." (too abstract, no concrete endpoint)

  Structure: TIME JUMP (Year 5, Year 10, Year 50, "decades later") + NEW NORMAL (what life looks like now) + a CONCRETE DETAIL that shows the absurdity has become routine. This is the Pixar-short ending pattern — tension resolves into a new stable equilibrium, not a reveal.

- The LAST LINE must be memorable — the line people quote when sharing the video. Weak endings are BAD.
- Second person narration ("You walk in...", "You show...", "You realize...")
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line = one scene = one image
- Each line UNDER 15 words
- Punchy, fast-paced, funny
- Do NOT mention skeletorinio, bones, or the character's appearance — just tell the story

REFERENCE EXAMPLE (the Chosen One — study the escalation shape, not the exact words):
Title: WHAT IF YOU ACCIDENTALLY BECAME THE CHOSEN ONE
Narration:
  0: What if you accidentally pulled a sword from a stone?
  1: Day 1: The sword screams awake and every knight in the valley kneels.
  2: Day 2: A dragon lands in your street and offers you its back.
  3: Week 1: Three kingdoms go to war over who gets to serve you.
  4: Month 2: Your throne room is floating over a city you built from clouds.
  5: Year 1: Prophecies about you are carved into mountains by lightning.
  6: Year 5: Your face is on coins, flags, and a moon base.
  7: Decades later, the sword returns itself to the stone and waits again.

Why this worked:
- Universal mythology (Excalibur) — zero-context entry
- Each line gets visibly larger and more impossible than the last
- Time jumps ACCELERATE: Day 1, Day 2, Day 3, Week 1, Month 2, Year 1
- CONCRETE visuals only (sword, dragon, crown, castle, mountains) — never abstract
- The ending lands in a new mythic normal instead of a shrug
- 8 lines, each under 15 words

Aim for this shape. Match it in structure and energy.

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


def _heuristic_character_variant(title: str, brief: str, era: str) -> dict:
    text = f"{title} {brief} {era}".lower()
    traits: list[str] = []
    variant_name = "default"

    if any(term in text for term in ["zeus", "olympus", "lightning", "thunder"]):
        variant_name = "storm king"
        traits = [
            "storm-white curly hair crackling with faint blue lightning",
            "a laurel crown with subtle lightning motifs",
            "white-and-gold Greek god drapery and divine shoulder armor",
        ]
    elif any(term in text for term in ["poseidon", "ocean", "sea", "trident"]):
        variant_name = "sea king"
        traits = [
            "sea-blue crest-like hair swept backward",
            "coral-and-bronze sea god accessories",
            "wet oceanic drapery with shell details",
        ]
    elif any(term in text for term in ["hades", "underworld", "dead", "afterlife"]):
        variant_name = "underworld ruler"
        traits = [
            "dark smoke-like crown or shadow halo",
            "black-and-deep-purple underworld robes",
            "subtle ember glow in the eye sockets",
        ]
    elif any(term in text for term in ["rome", "roman", "caesar", "colosseum"]):
        variant_name = "roman troublemaker"
        traits = [
            "messy short curls under a Roman-style laurel wreath",
            "worn Roman tunic layered over the skeleton body",
            "leather sandals and simple bronze accents",
        ]
    elif any(term in text for term in ["jetpack", "space", "rocket", "moon", "mars"]):
        variant_name = "sci-fi rider"
        traits = [
            "windswept white crest-hair or helmet fins",
            "sleek sci-fi harness and propulsion rig",
            "bright metallic accent panels over the skeleton body",
        ]
    else:
        traits = [
            "concept-appropriate hair or crown only if the setting calls for it",
            "era-appropriate outfit pieces fitted over the same skeleton body",
            "no modern jewelry or recurring gag accessories by default",
        ]

    return {
        "variant_name": variant_name,
        "must_keep": BASE_CHARACTER_IDENTITY,
        "traits": traits,
        "negative_traits": [
            "no gold chain",
            "no sunglasses",
            "no human skin replacing the skeleton face",
            "no random redesign of the head or body proportions",
        ],
    }


def _build_character_variant(title: str, brief: str, era: str) -> dict:
    variant = _heuristic_character_variant(title, brief, era)
    try:
        from packages.clients.claude import generate as claude_generate

        resp = claude_generate(
            prompt=f"""Design a concept-specific Skeletorinio variant for this one video.

VIDEO TITLE: {title}
BRIEF: {brief}
ERA: {era or "not specified"}

BASE CHARACTER RULES:
- {BASE_CHARACTER_IDENTITY}
- The variant should adapt with accessories, hair, crowns, clothing layers, or divine markings ONLY
- Never redesign the core face/head/body
- Never use the old recurring accessories: no gold chain, no sunglasses
- Keep it visually simple enough to stay consistent across 5-7 scenes

Return ONLY JSON:
{{
  "variant_name": "short label",
  "must_keep": "one sentence about the unchanged core identity",
  "traits": ["2-4 short visual traits"],
  "negative_traits": ["2-4 forbidden traits"]
}}""",
            max_tokens=300,
        )
        match = re.search(r"\{.*\}", resp, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if parsed.get("traits"):
                parsed.setdefault("must_keep", BASE_CHARACTER_IDENTITY)
                parsed.setdefault("negative_traits", variant["negative_traits"])
                return parsed
    except Exception as e:
        logger.warning("character variant generation fallback", error=str(e)[:120])
    return variant


def _variant_rules_text(character_variant: dict) -> str:
    traits = character_variant.get("traits") or []
    negatives = character_variant.get("negative_traits") or []
    traits_text = "; ".join(traits) if traits else "no extra accessories"
    negatives_text = "; ".join(negatives) if negatives else "no off-model redesigns"
    return (
        "\n\nCONCEPT-SPECIFIC SKELETORINIO VARIANT:\n"
        f"- {character_variant.get('must_keep', BASE_CHARACTER_IDENTITY)}\n"
        f"- For THIS video, add these consistent variant traits: {traits_text}.\n"
        f"- Forbidden drift: {negatives_text}.\n"
        "- Every image_prompt must keep this exact variant consistent across the entire video.\n"
    )


def _extract_style_override(concept: dict) -> str | None:
    explicit = concept.get("art_style")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    camera_cues = [
        "Close-up", "Wide shot", "Wide ", "Medium shot", "Medium ", "Low-angle",
        "High-angle", "Bird's-eye", "Over-the-shoulder", "Side view",
        "Dutch-angle", "Full-body", "Extreme close-up",
    ]

    for scene in concept.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        text = (scene.get("description") or scene.get("image_prompt") or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if "in the style of" not in lowered:
            continue

        style_text = text
        if "—" in style_text:
            style_text = style_text.split("—", 1)[1].strip()
        elif " - " in style_text:
            style_text = style_text.split(" - ", 1)[1].strip()
        else:
            marker = lowered.find("in the style of")
            style_text = text[marker + len("in the style of"):].strip()

        cut_idx = None
        for cue in camera_cues:
            idx = style_text.find(cue)
            if idx != -1 and (cut_idx is None or idx < cut_idx):
                cut_idx = idx
        if cut_idx is not None:
            style_text = style_text[:cut_idx].strip()

        style_text = style_text.strip(" .")
        if style_text:
            return style_text
    return None


def _build_style_profile(concept: dict) -> dict:
    style_override = _extract_style_override(concept)
    if style_override:
        lowered = style_override.lower()
        if any(token in lowered for token in ["photoreal", "photographic", "live action", "live-action", "real-life", "realistic human"]):
            return {
                "mode": "photoreal",
                "art_style": style_override,
                "image_rules": DEFAULT_IMAGE_RULES,
                "anchor_world_line": (
                    f"Render the entire scene in this photorealistic visual direction: {style_override}. "
                    "Keep the world realistic instead of cel-shaded or cartooned. NO text anywhere."
                ),
            }
        return {
            "mode": "stylized",
            "art_style": style_override,
            "image_rules": STYLIZED_IMAGE_RULES,
            "anchor_world_line": (
                f"Render the entire scene in this stylized visual direction: {style_override}. "
                "Do NOT drift into photorealism. NO text anywhere."
            ),
        }
    return {
        "mode": "photoreal",
        "art_style": DEFAULT_ART_STYLE,
        "image_rules": DEFAULT_IMAGE_RULES,
        "anchor_world_line": "Photorealistic world with cinematic golden hour lighting. NO text anywhere.",
    }


def _should_use_character_ref(concept: dict) -> bool:
    return not bool(concept.get("skip_character_ref"))


def _is_domain_power_concept(title: str, brief: str) -> bool:
    text = f"{title} {brief}".lower()
    artifact_terms = [
        "helmet", "helm", "sword", "trident", "crown", "ring",
        "amulet", "artifact", "relic", "lamp", "staff", "hammer",
    ]
    borrowed_terms = [
        "stole", "stolen", "grabbed", "grab", "touched", "touch",
        "found", "wear", "wore", "borrowed", "picked up", "pick up",
    ]
    direct_keywords = [
        "zeus", "poseidon", "apollo", "artemis",
        "lightning", "thunder", "storm", "weather", "tide", "tides",
        "sun", "sunlight", "moon", "ocean", "sea", "fire",
        "olympus",
    ]
    explicit_domain_phrases = [
        "became hades",
        "new hades",
        "god of the underworld",
        "rule the underworld",
        "underworld powers",
        "became a god",
        "became the god",
        "became a goddess",
        "became the goddess",
        "divine powers",
        "control the weather",
        "control the sea",
        "control the ocean",
        "control the sun",
        "control fire",
    ]
    time_power_phrases = [
        "god of time",
        "time god",
        "time powers",
        "control time",
        "master of time",
        "lord of time",
        "chronos",
        "chrono powers",
    ]
    artifact_borrow_concept = any(word in text for word in artifact_terms) and any(
        word in text for word in borrowed_terms
    )
    explicit_domain_concept = any(phrase in text for phrase in explicit_domain_phrases)

    # Borrowed myth artifacts like Hades' helmet should keep their own premise instead of
    # being rewritten into generic "you became a god of X" fallback narration.
    if artifact_borrow_concept and not explicit_domain_concept:
        return False

    return (
        any(word in text for word in direct_keywords)
        or explicit_domain_concept
        or any(phrase in text for phrase in time_power_phrases)
    )


def _count_domain_effect_lines(narration_lines: list[str]) -> int:
    effect_words = [
        "lightning", "storm", "storms", "weather", "sky", "cloud", "clouds",
        "rain", "sun", "sunlight", "tide", "tides", "ocean", "sea",
        "wave", "waves", "wind", "winds", "fire", "moon", "thunder",
        "shock", "shocks", "bolt", "bolts", "cook", "cooks", "cooking",
        "cloudride", "ride", "rides", "split", "splits",
        "freeze time", "freezes time", "frozen in time", "rewind", "rewinds",
        "pause time", "pauses time", "fast-forward", "ages instantly", "clock stops",
    ]
    count = 0
    for line in narration_lines[1:]:
        text = line.lower()
        if any(word in text for word in effect_words):
            count += 1
    return count


def _is_power_progression_concept(title: str, brief: str) -> bool:
    text = f"{title} {brief}".lower()
    return _is_domain_power_concept(title, brief) and any(
        phrase in text
        for phrase in [
            "accidentally became",
            "became the new",
            "new zeus",
            "new poseidon",
            "new apollo",
            "new hades",
            "new god",
        ]
    )


def _needs_power_progression_rewrite(title: str, brief: str, narration_lines: list[str]) -> bool:
    if not narration_lines or not _is_power_progression_concept(title, brief):
        return False

    admin_words = [
        "help desk", "complaint", "complaints", "approve", "approval",
        "reporting", "meeting", "scroll", "throne", "paperwork",
    ]
    milestone_markers = ("day ", "week ", "month ", "year ")
    progression_words = [
        "shock", "lightning", "bolt", "cook", "cloud", "ride",
        "storm", "weather", "split", "sky", "rain", "sun",
    ]

    progress_lines = 0
    admin_lines = 0
    for line in narration_lines[1:]:
        lower = line.lower()
        if any(lower.startswith(marker) for marker in milestone_markers):
            progress_lines += 1
        if any(word in lower for word in admin_words):
            admin_lines += 1

    return progress_lines < 4 or _count_domain_effect_lines(narration_lines) < 4 or admin_lines > 1 or not any(
        word in " ".join(narration_lines[1:]).lower() for word in progression_words
    )


def _fallback_power_rewrite(title: str, narration_lines: list[str]) -> list[str]:
    hook = narration_lines[0] if narration_lines else f"What if {title.lower()}?"
    lower_title = title.lower()
    if "zeus" in lower_title:
        return [
            hook,
            "Day 1: Tiny shocks jump out whenever you touch metal.",
            "Week 1: You call lightning on command and sear every dinner perfectly.",
            "Month 2: You ride a cloud, then ruin three weddings with perfect weather.",
            "Year 1: Farmers beg for rain while sailors beg you to stop the storms.",
            "Year 2: One finger splits the sky open, and Olympus already calls you Zeus.",
        ]
    if any(term in lower_title for term in ["god of time", "time god", "control time", "master of time", "lord of time", "chronos"]):
        return [
            hook,
            "Day 1: One nervous blink freezes a whole crosswalk in place.",
            "Week 1: You rewind spilled coffee, broken plates, and one terrible haircut.",
            "Month 1: Trains leave early because you keep fast-forwarding your commute.",
            "Year 1: Cities beg you to pause disasters before they happen.",
            "By year 2, clocks stop when you walk in and history waits.",
        ]
    return [
        hook,
        "Day 1: You grab one loose lightning bolt and the sky obeys.",
        "Day 2: One bad shrug puts thunderstorms over beaches and sunshine over the sea.",
        "Week 1: Poseidon is furious because you keep pulling the tides backward.",
        "Month 1: Farmers cheer, sailors panic, and every cloud follows your finger.",
        "Olympus opens a weather help desk, and somehow you still run it.",
    ]


def _maybe_strengthen_power_narration(title: str, brief: str, narration_lines: list[str]) -> list[str]:
    if not narration_lines or not _is_domain_power_concept(title, brief):
        return narration_lines

    min_effect_lines = min(3, max(1, len(narration_lines) - 1))
    if _count_domain_effect_lines(narration_lines) >= min_effect_lines and not _needs_power_progression_rewrite(title, brief, narration_lines):
        return narration_lines

    try:
        from packages.clients.claude import generate as claude_generate

        resp = claude_generate(
            prompt=f"""Rewrite this Skeletorinio narration so the spectacle comes from visibly USING or MISUSING the domain power, not just meetings or complaints.

TITLE: {title}
BRIEF: {brief}
CURRENT NARRATION:
{json.dumps(narration_lines, ensure_ascii=False)}

RULES:
- Keep the same core premise and comedic tone.
- Keep 6-8 lines total.
- Every line under 15 words.
- Keep the hook as a clear "What if..." line naming the concept.
- At least 3 post-hook lines must show visible environment effects from the power/domain.
- Bureaucracy/help-desk/complaint beats can appear at most once.
- For Zeus/weather concepts, physically show lightning, storms, tides, sunlight, clouds, or sky behavior.
- If this is an accidental new-god concept, make it feel like POWER PROGRESSION over time:
  1. small accidental glitch,
  2. controlled trick,
  3. useful or embarrassing public use,
  4. huge world-scale mastery/payoff.
- For Zeus specifically, prefer shocks-on-touch, called lightning, cloud-riding, cooking/helping people, weather chaos, and a final god-of-lightning flex over throne-room admin.

Return ONLY JSON:
{{"narration": ["line 1", "line 2", "..."]}}""",
            max_tokens=400,
        )
        match = re.search(r"\{.*\}", resp, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            candidate = parsed.get("narration") or []
            if candidate and _count_domain_effect_lines(candidate) >= min_effect_lines:
                logger.info("strengthened power narration", title=title, before=narration_lines, after=candidate)
                return candidate
    except Exception as e:
        logger.warning("power narration rewrite fallback", title=title, error=str(e)[:120])

    fallback = _fallback_power_rewrite(title, narration_lines)
    logger.info("using fallback power narration", title=title, fallback=fallback)
    return fallback


def _is_boss_raid_concept(title: str, brief: str) -> bool:
    text = f"{title} {brief}".lower()
    keywords = [
        "final boss", "raid boss", "dungeon", "dark lord", "demon king",
        "server", "raid", "party", "parties", "guild", "guilds",
        "heroes coming", "heroes come", "boss fight", "endgame boss",
    ]
    return any(word in text for word in keywords)


def _needs_boss_raid_rewrite(title: str, brief: str, narration_lines: list[str]) -> bool:
    if not narration_lines or not _is_boss_raid_concept(title, brief):
        return False

    combat_words = [
        "spell", "blast", "minion", "minions", "raid", "party", "wipe", "wipes",
        "charge", "charges", "swing", "swings", "summon", "summons", "phase",
        "shield", "shields", "armor", "army", "armies", "boss", "health bar",
        "knight", "heroes", "hero", "survive", "barely", "fireball", "meteor",
        "lightning", "portal", "explodes", "erupts", "cracks", "collapses",
    ]
    admin_words = [
        "tourist", "tourists", "gift shop", "shop", "shops", "collect fees", "fee",
        "fees", "construction", "build", "builds", "builder", "renovate", "renovates",
        "improve", "improves", "organize", "organizes", "landlord", "rent", "bakery",
        "business", "booth", "ledger", "coin chest", "treasurer",
    ]

    joined = " ".join(narration_lines[1:]).lower()
    combat_lines = sum(1 for line in narration_lines[1:] if any(word in line.lower() for word in combat_words))
    admin_lines = sum(1 for line in narration_lines[1:] if any(word in line.lower() for word in admin_words))
    has_escalation = any(
        marker in joined
        for marker in ["first party", "first raid", "next raid", "full raid", "best players", "strongest heroes", "second phase"]
    )
    has_minion_or_phase = any(
        marker in joined
        for marker in ["minion", "minions", "summon", "summons", "phase two", "second phase", "final form"]
    )
    has_loot_aftermath = any(
        marker in joined
        for marker in ["loot", "legendary gear", "gear", "drops", "dropped", "weapons piled", "relic", "treasure"]
    )
    has_struggle_then_win = any(
        marker in joined
        for marker in ["barely survive", "barely lives", "almost dies", "nearly kills you", "second health bar", "phase two"]
    )

    return (
        combat_lines < 3
        or admin_lines > 0
        or not has_escalation
        or not has_minion_or_phase
        or not has_loot_aftermath
        or not has_struggle_then_win
    )


def _fallback_boss_raid_rewrite(title: str, narration_lines: list[str]) -> list[str]:
    hook = narration_lines[0] if narration_lines else f"What if {title.lower()}?"
    return [
        hook,
        "Day 1: One spell wipes the first party, and loot bursts across the floor.",
        "Week 1: A full raid breaks your gates, and you barely keep phase one alive.",
        "Month 1: The top guild dives in while your minions flood every staircase.",
        "You hit phase two, split the dungeon open, and start raining boss magic.",
        "By sunrise, legendary gear is piled at your feet, and nobody queues again.",
    ]


def _maybe_strengthen_boss_raid_narration(title: str, brief: str, narration_lines: list[str]) -> list[str]:
    if not narration_lines or not _is_boss_raid_concept(title, brief):
        return narration_lines

    if not _needs_boss_raid_rewrite(title, brief, narration_lines):
        return narration_lines

    try:
        from packages.clients.claude import generate as claude_generate

        resp = claude_generate(
            prompt=f"""Rewrite this Skeletorinio narration so it commits fully to a FINAL-BOSS / RAID escalation story instead of drifting into management or civilization comedy.

TITLE: {title}
BRIEF: {brief}
CURRENT NARRATION:
{json.dumps(narration_lines, ensure_ascii=False)}

RULES:
- Keep the same core premise and comedic tone.
- Keep 6-8 lines total.
- Every line under 15 words.
- Keep the hook as a clear "What if..." line naming the concept.
- After the hook, escalate through combat pressure:
  1. weak party or first challengers,
  2. bigger raid or army,
  3. elite heroes / best players / top guild,
  4. your second phase, special spell, or summoned minions,
  5. undefeated ending.
- At least 3 post-hook lines must show visible battle actions or powers.
- Do NOT include gift shops, tourism, fees, construction, renovation, landlord jokes, or cozy civilization outcomes.
- The ending should feel like total domination, not bureaucracy.

Return ONLY JSON:
{{"narration": ["line 1", "line 2", "..."]}}""",
            max_tokens=400,
        )
        match = re.search(r"\{.*\}", resp, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            candidate = parsed.get("narration") or []
            if candidate and not _needs_boss_raid_rewrite(title, brief, candidate):
                logger.info("strengthened boss raid narration", title=title, before=narration_lines, after=candidate)
                return candidate
    except Exception as e:
        logger.warning("boss raid narration rewrite fallback", title=title, error=str(e)[:120])

    fallback = _fallback_boss_raid_rewrite(title, narration_lines)
    logger.info("using fallback boss raid narration", title=title, fallback=fallback)
    return fallback


def _story_novelty_categories(line: str) -> set[str]:
    lower = str(line or "").lower()
    categories: set[str] = set()
    keyword_map = {
        "body": ["young", "younger", "older", "aging", "age", "wrinkle", "baby", "toddler", "body", "face", "shrink", "grow"],
        "social": ["crowd", "everyone", "villagers", "king", "queen", "army", "worship", "kneel", "court", "people", "citizens"],
        "world": ["city", "sky", "storm", "ocean", "village", "kingdom", "moon", "mountain", "earthquake", "sun", "world", "history"],
        "creature": ["dragon", "mammoth", "dinosaur", "monster", "demon", "beast", "wolf", "serpent", "army of the dead"],
        "rule": ["but", "except", "until", "won't", "will not", "can't", "cannot", "cost", "price", "trade", "deal", "sip", "one more", "last drop", "rule", "erase", "stuck", "trapped", "backfires"],
        "travel": ["portal", "rome", "future", "past", "jurassic", "ice age", "era", "century", "timeline", "history rewrites"],
        "artifact": ["fountain", "sword", "lamp", "crown", "stone", "relic", "amulet", "ring", "book"],
        "combat": ["fight", "raid", "spell", "blast", "summon", "charge", "battle", "wipe", "explode", "crack"],
    }
    for category, keywords in keyword_map.items():
        if any(keyword in lower for keyword in keywords):
            categories.add(category)
    return categories


def _is_predictable_ladder_story(title: str, brief: str, narration_lines: list[str]) -> bool:
    if not narration_lines or len(narration_lines) < 6:
        return False
    if _is_domain_power_concept(title, brief) or _is_boss_raid_concept(title, brief):
        return False

    post_hook = narration_lines[1:]
    category_hits: set[str] = set()
    for line in post_hook:
        category_hits.update(_story_novelty_categories(line))
    early_lines = post_hook[: min(4, len(post_hook))]
    early_category_hits: set[str] = set()
    for line in early_lines:
        early_category_hits.update(_story_novelty_categories(line))

    time_jump_lines = sum(
        1 for line in post_hook if re.search(r"(?i)^(day|week|month|year|decades?)\b", line.strip())
    )
    novelty_markers = [
        "but", "except", "until", "instead", "suddenly", "turns out", "backfires",
        "won't", "will not", "can't", "cannot", "cost", "price", "deal", "trade",
        "last drop", "one more", "stuck", "trapped", "erase", "everyone else",
        "then you learn", "you realize", "the problem", "the catch", "actually",
    ]
    novelty_lines = sum(
        1 for line in post_hook if any(marker in line.lower() for marker in novelty_markers)
    )
    early_turn_lines = sum(
        1 for line in early_lines if any(marker in line.lower() for marker in novelty_markers)
    )
    regression_terms = [
        "younger", "older", "rewind", "revers", "century", "decade", "jurassic",
        "ice age", "fountain of youth", "everyone else getting younger", "back through",
    ]
    regression_signal = any(
        term in f"{title} {brief} {' '.join(early_lines)}".lower() for term in regression_terms
    )
    repeated_regression_lines = sum(
        1 for line in early_lines if any(term in line.lower() for term in regression_terms)
    )

    return (
        (time_jump_lines >= 3 and len(category_hits) < 4)
        or (novelty_lines == 0 and len(category_hits) < 3)
        or (early_turn_lines == 0 and len(early_category_hits) < 4)
        or (regression_signal and early_turn_lines == 0 and repeated_regression_lines >= 2)
    )


def _is_training_story_concept(title: str, brief: str, narration_lines: list[str]) -> bool:
    blob = " ".join([title, brief, *[str(line) for line in narration_lines]]).lower()
    mentor_terms = [
        "trained you",
        "trains you",
        "train you",
        "training",
        "mentor",
        "teaches you",
        "teach you",
        "again",
        "day 1",
        "week 2",
        "month 3",
    ]
    skill_terms = [
        "kunai",
        "shuriken",
        "genjutsu",
        "blindfold",
        "dodge",
        "hand signs",
        "forehead",
    ]
    return any(term in blob for term in mentor_terms) and any(term in blob for term in skill_terms)


def _fallback_story_novelty_rewrite(title: str, brief: str, narration_lines: list[str]) -> list[str]:
    hook = narration_lines[0] if narration_lines else f"What if {title.lower()}?"
    lower = f"{title} {brief}".lower()
    if any(term in lower for term in ["fountain of youth", "younger", "getting younger", "age backwards", "aging backward"]):
        return [
            hook,
            "Day 1: Your face gets younger, but the whole plaza reverses faster.",
            "Day 2: Everyone becomes toddlers, and the fountain still will not stop.",
            "Week 1: The city rewinds to ruins, and mammoths start drinking beside you.",
            "Then you learn each sip erases one century everywhere except your memory.",
            "By sunset, Jurassic trees cover the square, and the fountain is almost dry.",
            "One last drop remains. The future only comes back if you drink again.",
        ]
    return narration_lines


def _validate_outline_hook(hook: str) -> tuple[bool, str]:
    """Programmatic checks on the outline's hook against the rubric.
    Returns (passes, reason_if_fail)."""
    if not hook:
        return False, "empty hook"
    h = hook.strip().lower()
    if not h.startswith("what if"):
        return False, "hook must start with 'What if'"
    if "you" not in h:
        return False, "hook must use second person ('you')"
    word_count = len(h.split())
    if word_count < 6:
        return False, f"hook too short ({word_count} words)"
    if word_count > 18:
        return False, f"hook too long ({word_count} words)"
    abstract_terms = [
        "destiny", "fate", "greatness", "importance", "amazing",
        "incredible", "powerful", "successful", "the best",
    ]
    for term in abstract_terms:
        if term in h:
            return False, f"abstract term '{term}' in hook — name a concrete noun instead"
    return True, ""


def _generate_outline(title: str, brief: str, max_attempts: int = 3) -> dict:
    """Generate the plot outline. Retries up to max_attempts if the hook fails the rubric."""
    from packages.clients.claude import generate as claude_generate

    last_error = ""
    for attempt in range(max_attempts):
        prompt = OUTLINE_PROMPT.format(title=title, brief=brief)
        if last_error and attempt > 0:
            prompt += (
                f"\n\nPRIOR ATTEMPT FAILED THE HOOK RUBRIC: {last_error}\n"
                "Regenerate with a hook that satisfies all four rubric checks."
            )
        resp = claude_generate(prompt=prompt, max_tokens=1500)
        match = re.search(r"\{.*\}", resp, re.DOTALL)
        if not match:
            last_error = "no JSON in response"
            continue
        try:
            outline = json.loads(match.group())
        except json.JSONDecodeError as e:
            last_error = f"invalid JSON: {e}"
            continue
        hook = outline.get("hook", "")
        passes, reason = _validate_outline_hook(hook)
        if passes:
            logger.info("outline generated", title=title, hook=hook, attempt=attempt + 1)
            return outline
        last_error = reason
        logger.warning(
            "outline hook failed rubric — retrying",
            title=title, hook=hook, reason=reason, attempt=attempt + 1,
        )
    raise ValueError(f"Failed to generate valid outline after {max_attempts} attempts. Last error: {last_error}")


def _generate_narration_from_outline(title: str, brief: str, outline: dict) -> tuple[list[str], str]:
    """Run SCRIPT_PROMPT against the outline. Returns (narration_lines, possibly_updated_title)."""
    from packages.clients.claude import generate as claude_generate

    outline_json = json.dumps(outline, indent=2, ensure_ascii=False)
    resp = claude_generate(
        prompt=SCRIPT_PROMPT.format(title=title, brief=brief, outline_json=outline_json),
        max_tokens=2000,
    )
    match = re.search(r"\{.*\}", resp, re.DOTALL)
    if not match:
        raise ValueError("No JSON in script response")
    parsed = json.loads(match.group())
    narration = parsed.get("narration") or []
    new_title = parsed.get("title") or title
    if not narration:
        raise ValueError("Empty narration in script response")
    return narration, new_title


def _punchline_pays_off_plant(narration_lines: list[str], outline: dict | None) -> bool:
    """Heuristic: does the final line reference a plant or recurring_element from the outline?"""
    if not narration_lines or not outline:
        return True
    final_line = narration_lines[-1].lower()
    stop_words = {
        "the", "and", "with", "from", "into", "your", "this", "that",
        "what", "you", "have", "are", "is", "but", "for", "all", "now",
        "their", "they", "them", "back", "down", "over", "still", "just",
        "where", "when", "while", "until", "than", "then", "next", "last",
        "every", "each", "some", "more", "most",
    }
    candidates: list[str] = []
    recurring = (outline.get("recurring_element") or "").lower()
    if recurring:
        candidates.append(recurring)
    for plant in outline.get("plants") or []:
        what = (plant.get("what") or "").lower()
        if what:
            candidates.append(what)
    for c in candidates:
        for word in re.findall(r"\b[a-z]{4,}\b", c):
            if word in stop_words:
                continue
            if word in final_line:
                return True
    return False


def _maybe_strengthen_story_novelty(
    title: str,
    brief: str,
    narration_lines: list[str],
    outline: dict | None = None,
) -> list[str]:
    """Circuit-breaker for predictable-ladder narration and free-floating punchlines.

    Detects two failure modes:
    (1) predictable-ladder story (same effect scaling up) via _is_predictable_ladder_story
    (2) final line doesn't reference any plant or recurring_element from the outline

    On detection, regenerates ONCE through the full outline → narration pipeline. If still
    failing, falls through to the hardcoded fallback (fountain-of-youth template)."""
    predictable = _is_predictable_ladder_story(title, brief, narration_lines)
    payoff_missing = outline is not None and not _punchline_pays_off_plant(narration_lines, outline)
    if not predictable and not payoff_missing:
        return narration_lines

    logger.info(
        "circuit-breaker triggered",
        title=title,
        predictable_ladder=predictable,
        payoff_missing=payoff_missing,
    )

    try:
        new_outline = _generate_outline(title, brief)
        candidate, _ = _generate_narration_from_outline(title, brief, new_outline)
        still_predictable = _is_predictable_ladder_story(title, brief, candidate)
        still_missing = not _punchline_pays_off_plant(candidate, new_outline)
        if candidate and not still_predictable and not still_missing:
            logger.info(
                "circuit-breaker regenerated",
                title=title, before=narration_lines, after=candidate,
            )
            return candidate
        logger.warning(
            "circuit-breaker regen still failing — falling through to hardcoded fallback",
            title=title,
            still_predictable=still_predictable,
            still_missing=still_missing,
        )
    except Exception as e:
        logger.warning("circuit-breaker regen errored", title=title, error=str(e)[:120])

    fallback = _fallback_story_novelty_rewrite(title, brief, narration_lines)
    if fallback != narration_lines:
        logger.info("using fallback story novelty narration", title=title, fallback=fallback)
    return fallback


async def build_skeletorinio(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Skeletorinio video build using unified pipeline."""
    title = concept.get("title", "Untitled")
    narration_lines = concept.get("narration", [])
    brief = concept.get("brief", title)
    era = concept.get("era", "")
    runtime_channel_id = int(concept.get("channel_id") or CHANNEL_ID)
    runtime_music_path = str(concept.get("music_path") or MUSIC_PATH)
    runtime_tags = concept.get("tags") if isinstance(concept.get("tags"), list) and concept.get("tags") else TAGS
    use_character_ref = _should_use_character_ref(concept)

    narr_dir = os.path.join(output_dir, "narration")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [narr_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    # ─── STEP 1: Generate outline + narration ───
    outline: dict | None = concept.get("outline") if isinstance(concept.get("outline"), dict) else None
    if not narration_lines:
        if outline is None:
            await _update_step("planning outline")
            outline = _generate_outline(title, brief)
            concept["outline"] = outline
        outline_path = os.path.join(output_dir, "outline.json")
        with open(outline_path, "w") as f:
            json.dump(outline, f, indent=2, ensure_ascii=False)

        await _update_step("writing script")
        narration_lines, title = _generate_narration_from_outline(title, brief, outline)
        if not narration_lines:
            raise ValueError("Failed to generate narration script")

    narration_lines = _maybe_strengthen_power_narration(title, brief, narration_lines)
    narration_lines = _maybe_strengthen_boss_raid_narration(title, brief, narration_lines)
    narration_lines = _maybe_strengthen_story_novelty(title, brief, narration_lines, outline)
    concept["narration"] = narration_lines

    if _is_training_story_concept(title, brief, narration_lines):
        concept.setdefault("provider_strategy", "veo")
        concept.setdefault("video_provider", "veo")
        concept.setdefault("video_model", "veo-3.1-lite-generate-001")
        concept.setdefault("subaction_mode", "training_story")

    n_lines = len(narration_lines)

    # ─── STEP 2: Narration ───
    await _update_step("generating narration")
    await generate_narration_with_timestamps(
        narration_lines, narr_dir, output_dir, VOICE_ID, _update_step,
    )

    # ─── STEP 3: Build concept-specific character variant + style anchor ───
    from openai import AsyncOpenAI
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    anchor_path = os.path.join(images_dir, "style_anchor.png")
    style_profile = _build_style_profile(concept)
    art_style_prompt = style_profile["art_style"]
    character_variant = None
    if use_character_ref:
        character_variant = concept.get("character_variant") if isinstance(concept.get("character_variant"), dict) else None
        if not character_variant:
            await _update_step("designing character variant")
            character_variant = _build_character_variant(title, brief, era)
        concept["character_variant"] = character_variant
        variant_path = os.path.join(output_dir, "character_variant.json")
        with open(variant_path, "w") as vf:
            json.dump(character_variant, vf, indent=2)

    if use_character_ref and not os.path.exists(anchor_path) and os.path.exists(SKELETON_REF):
        # Generate a concept-specific Skeletorinio variant IN the first scene — this becomes the style anchor
        # so all subsequent scenes share the same era, lighting, character scale, and accessory profile.
        _oai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)
        era_part = f"STRICT ERA: {era}. All humans in period-accurate clothing. NO modern clothing, NO modern objects. " if era else "Historical time period — NOT modern day. "
        variant_traits = "; ".join(character_variant.get("traits") or [])
        variant_negatives = "; ".join(character_variant.get("negative_traits") or [])
        _ref = open(SKELETON_REF, "rb")
        try:
            _resp = await _oai.images.edit(
                model=OPENAI_IMAGE_MODEL,
                image=_ref,
                prompt=(
                    f"{era_part}Transform this exact base Skeletorinio reference into the concept-specific variant for this video: {title}. "
                    f"{character_variant.get('must_keep', BASE_CHARACTER_IDENTITY)} "
                    f"Add these consistent variant traits: {variant_traits}. "
                    f"Forbidden drift: {variant_negatives}. "
                    f"Place the resulting variant into the scene for this video: {brief[:200]}. "
                    f"{narration_lines[0] if narration_lines else ''}. "
                    "The character is FULL ADULT HUMAN HEIGHT — same size as real people around him. "
                    f"{style_profile['anchor_world_line']}"
                ),
                **get_openai_image_edit_kwargs(size="1024x1536", quality="medium"),
            )
            _ref.close()
            if _resp.data and _resp.data[0].b64_json:
                import base64 as _b64
                with open(anchor_path, "wb") as _f:
                    _f.write(_b64.b64decode(_resp.data[0].b64_json))
                logger.info("style anchor generated from skeletorinio ref in scene")
        except Exception as _e:
            try: _ref.close()
            except: pass
            import shutil
            shutil.copy2(SKELETON_REF, anchor_path)
            logger.warning("style anchor fallback to bare skeletorinio ref", error=str(_e)[:80])

    # ─── STEP 4: Unified pipeline — uses style anchor (skeleton IN scene) for all edits ───
    base_image_rules = str(concept.get("image_rules") or style_profile["image_rules"])
    if use_character_ref and character_variant:
        image_rules = base_image_rules + _variant_rules_text(character_variant)
    else:
        image_rules = base_image_rules
    clips_dir, clip_paths, n_clips, line_clip_map = await generate_and_animate_scenes(
        narration_lines,
        concept,
        image_rules,
        art_style_prompt,
        output_dir,
        _update_step,
        run_id=run_id,
        character_ref_path=anchor_path if use_character_ref else None,
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
        channel_id=runtime_channel_id, concept=concept,
    )

    await _update_step("concatenating")
    teasers_path = os.path.join(segments_dir, "teasers.mp4")
    all_video_path, total_dur = concat_silent_video(teasers_path, segments_dir, n_lines, output_dir)

    await _update_step("building audio")
    audio_path, seg_starts = build_numpy_audio(
        n_lines, narr_dir, runtime_music_path, actual_teaser_dur, seg_durations, total_dur, output_dir,
        channel_id=runtime_channel_id, concept=concept,
    )

    await _update_step("combining")
    combined = combine_video_audio(all_video_path, audio_path, output_dir)

    await _update_step("adding subtitles")
    with open(os.path.join(output_dir, "word_timestamps.json")) as f:
        word_data = json.load(f)
    add_subtitles(combined, word_data, seg_starts, output_dir)

    await update_database(run_id, runtime_channel_id, title, output_dir, db_url, runtime_tags)
    logger.info("skeletorinio complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
