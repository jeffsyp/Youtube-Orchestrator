"""Prompt builder for auto-generating concept drafts per channel.

Two-phase generation:
1. build_concept_pitches_prompt — generates concept pitches (title, brief, structure)
2. build_script_prompt — writes the full beat-by-beat script for one pitch
"""

from packages.utils.concept_formats import (
    FORMAT_STRATEGY_DESCRIPTIONS,
    get_format_strategy_spec,
    normalize_format_strategy,
)


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

    hardcore_ranked_pitch_block = ""
    if channel_name.lower() == "hardcore ranked":
        hardcore_ranked_pitch_block = """

HARDCORE RANKED CONCEPT RULES (CRITICAL):
- Prefer BIG, measurable experiment questions that feel like something viewers have secretly wondered forever.
- Strong examples:
  - "HOW LONG WOULD IT TAKE TO REACH THE CENTER OF THE EARTH?"
  - "HOW FAR DOWN BEFORE THE OCEAN CRUSHES YOU?"
  - "HOW LONG COULD YOU SURVIVE ON EVERY PLANET?"
  - "EVERY SUPERHERO RANKED BY HOW LONG THEY SURVIVE IN SPACE WITH NO SUIT"
  - "EVERY MATERIAL RANKED BY HOW LONG IT LASTS INSIDE A VOLCANO"
- The best Hardcore Ranked ideas feel like:
  - one repeated scientific test
  - one variable changing each beat
  - obvious escalation from survivable to impossible
  - a clean answer the viewer wants to know
- Favor concepts about time, depth, pressure, speed, force, temperature, survival, falling, distance, escape, or destruction.
- A very strong Hardcore Ranked pattern is: ONE impossible destination or challenge, then rank the methods/tools/vehicles/strategies by how far they actually get before failing.
  - Example: "How long would it take to reach the center of the Earth using different machines?" should climb in SMALL, intuitive upgrades: shovel → handheld drill → mining drill → mega-bore → absurd sci-fi tunnel rig.
  - Do not skip too fast from primitive tool to giant sci-fi machine. The fun is feeling each upgrade earn a little more depth before the next one takes over.
  - Example: "How far down before the ocean crushes you?" should become swimsuit → diving suit → submarine → research bathysphere.
- The viewer should instantly understand the experiment from the title alone.
- Avoid concepts that mostly depend on fandom jokes, prison logic, doctor jokes, HR jokes, or “what if X in real life” social commentary.
- Avoid concepts that require totally different settings or rules every beat. If the same test rig cannot stay mostly consistent, it is probably the wrong Hardcore Ranked concept.
- Avoid gimmick concepts where the measurement is arbitrary, the fail-state is visually muddy, or the ranking logic changes from beat to beat.
- If the viewer cannot instantly picture the repeated test rig from the title alone, reject the idea.
- Avoid weak mascot framing. Never pitch titles or briefs around "frog suit guy", "frog mascot", or "skeleton mascot". The viewer-facing subject is always "you".
- If a concept can be reframed as a bigger, more universal, more physics-driven question, do that.
"""

    schmoney_facts_pitch_block = ""
    if channel_name.lower() == "schmoney facts":
        schmoney_facts_pitch_block = """

SCHMONEY FACTS CONCEPT RULES (CRITICAL):
- The only hard requirement is that the concept is MONEY-RELATED. It does NOT have to be a debt trap, bank fee, mortgage, or investing lecture.
- In a batch of 5, use at least 4 DIFFERENT premise families.
- At most ONE concept in the batch may be a personal-finance pain story about interest, debt, credit cards, loans, mortgages, or silent bank fees ruining your life.
- Mix premise families aggressively:
  1. hidden fee / scam / financial trap
  2. absurd price shock or cost comparison
  3. weird rich-person / celebrity / athlete spending
  4. salary / hourly wage / take-home-pay reality
  5. business model / profit margin / markup reveal
  6. luxury operating cost (private jet, yacht, mansion, supercar)
  7. casino / cash logistics / vault / money movement
  8. inflation / opportunity cost / investing
  9. tax / loophole / fine / subscription / financing trick
  10. "what if you had X money" fantasy flex
- Mix emotions too. A full batch of outrage is a FAIL. Mix disgust, envy, curiosity, aspiration, disbelief, admiration, and horror.
- Avoid repetitive title skeletons like:
  - "X STOLE Y FROM YOU"
  - "YOUR $X ACTUALLY COSTS $Y"
  - "THE $X LOAN THAT BECOMES $Y"
  - "$100 AT 22 VS 32"
- Avoid generic personal-finance preaching. Schmoney Facts can cover business, luxury, scams, spending, pricing tricks, taxes, rich flexes, weird money systems, cash handling, and black-market-style economics too.
- Strong examples:
  - "WHY AIRPORT WATER COSTS 8X MORE"
  - "HOW MUCH A PRIVATE JET COSTS PER HOUR"
  - "WHY COSTCO'S HOT DOG STILL COSTS $1.50"
  - "THE $20 POPCORN THAT MAKES MOVIE THEATERS RICH"
  - "WHAT $1 MILLION A YEAR ACTUALLY LOOKS LIKE AFTER TAXES"
  - "HOW CASINOS MOVE MILLIONS IN CASH EVERY NIGHT"
- Business-model / profit-margin ideas must expose WHERE the money comes from and why the split feels unfair, weird, or shocking. Pure revenue trivia is weak.
- Avoid concepts that are just "this company makes a lot of money" unless the mechanism itself is the hook.
- Avoid sports concession trivia, celebrity net-worth fluff, and generic millionaire flexes unless the cash-flow mechanics are the entire punchline.
- In a batch of 5, at least 3 concepts should make the viewer think "wait, THAT'S how the money works?"
- A batch with two titles about interest, debt, or loan math is a FAIL even if the exact products differ.
- If two pitches are basically the same "money pain math" with different nouns, keep the better one and replace the other.
"""

    skeletorinio_pitch_block = ""
    if channel_name.lower() == "skeletorinio":
        skeletorinio_pitch_block = """

SKELETORINIO CONCEPT RULES (CRITICAL):
- In a batch of 5, use at least 4 DIFFERENT premise families:
  1. mythic power theft or artifact misuse
  2. modern tool dropped into a historical catastrophe
  3. portal / era collision
  4. tournament / raid-boss / final-boss escalation
  5. god-domain mismatch
  6. cursed object or forbidden item
- At most ONE title may start with "WHAT IF YOU ACCIDENTALLY BECAME".
- At most TWO titles in the batch may use the exact shell "WHAT IF YOU..." at all.
- Prefer strong specific trigger verbs: grabbed, stole, opened, touched, wore, drank, entered, awakened, pulled, brought.
- Avoid vague power-inheritance concepts where the only hook is "you became some powerful role." The viewer should instantly picture the first visual consequence.
- The best ideas start with one obvious action and spiral into increasingly absurd world-scale consequences.
- Avoid predictable one-way ladders where scene 2 already tells the viewer exactly how scenes 3-6 will escalate.
- Especially avoid time-regression / portal / curse ideas that are only:
  "thing changes" → "more things change" → "the whole world changes."
- Strong Skeletorinio concepts need a SECOND QUESTION in the middle, not just a bigger version of the first answer.
- Prefer premises that naturally create one of these midpoint turns:
  1. hidden cost or tradeoff
  2. new rule discovered halfway through
  3. antagonist / creature / rival arrives
  4. false fix or second artifact makes it worse
  5. countdown / limited uses / last chance decision
  6. the power affects everyone EXCEPT you, or you EXCEPT everyone else
- In a batch of 5, at least 3 concepts should clearly imply a midpoint complication the viewer would still want to discover after the hook lands.
"""

    one_on_ones_pitch_block = ""
    if channel_name.lower() == "one on ones for fun":
        one_on_ones_pitch_block = """

ONE ON ONES CONCEPT RULES (CRITICAL):
- The batch needs MATCHUP variety AND TITLE-SHELL variety.
- At most TWO titles may use the exact shell "X VS Y WHO WINS THE REAL FIGHT".
- Mix title frames like:
  - "X VS Y: THE REAL WINNER"
  - "COULD X ACTUALLY BEAT Y?"
  - "WHY X ACTUALLY DESTROYS Y"
  - "X VS Y ONLY ENDS ONE WAY"
- Mix matchup families: comics, anime, games, myth, sci-fi, horror. A batch dominated by one universe or one publisher is a FAIL.
- Every matchup needs one clean debate axis the viewer instantly understands: speed, durability, hax, intelligence, regeneration, range, or raw force.
- Avoid soft "close call" wording. Pick matchups where the verdict feels sharp, debatable, and replayable.
"""

    nature_receipts_pitch_block = ""
    if channel_name.lower() == "nature receipts":
        nature_receipts_pitch_block = """

NATURE RECEIPTS CONCEPT RULES (CRITICAL):
- Stop defaulting to the same title skeleton: "[animal] was the size of X and discovered Y."
- In a batch of 5, use 5 DIFFERENT lead animals and at least 4 DIFFERENT premise engines.
- At most ONE giant-size concept in the batch.
- At most ONE "discovers a generic human place/system" concept in the batch.
- Prefer SPECIFIC collisions over generic destinations.
  GOOD: airport baggage belt, koi pond filtration room, national cheese cave, shipping container yard, sunflower seed silo
  BAD: downtown, the city, taxes, a store, the neighborhood, rush hour
- Make the animal's REAL instinct the reason the scenario escalates.
  GOOD: raccoon pries open sealed containers, otter hoards one object obsessively, penguin melts down in dry heat, octopus infiltrates vents and locks
  BAD: the animal just becomes a generic chaos monster
- Mix premise families aggressively:
  1. habitat inversion
  2. predator / prey reversal
  3. impossible trait or physical power-up
  4. human system collision
  5. swarm / pack takeover
  6. imprinting / obsession with one object or machine
- The best Nature Receipts ideas feel like tiny wildlife disaster documentaries, not random animal Mad Libs.
"""

    nightnight_pitch_block = ""
    if channel_name.lower() == "nightnightshorts":
        nightnight_pitch_block = """

NIGHTNIGHTSHORTS CONCEPT RULES (CRITICAL):
- These are narrated ANIME STORY shorts now, not just crossover premises and not stat-sheet fight debates.
- The best NightNight concepts feel like the craziest non-canon scene you would instantly click, understand, and retell.
- Every pitch needs a STORY ENGINE, not just a mashup:
  1. exact scenario / canon event,
  2. first impossible move,
  3. host-world answer or counter,
  4. twist / survival / reversal,
  5. final payoff image.
- In a batch of 5, at least 3 concepts must clearly imply a midpoint turn in the brief or structure.
- Avoid flat premises where line 2 already tells the viewer the whole video:
  BAD: "Light writes Hisoka. Hisoka revives. Light is scared."
  GOOD: "Light writes Hisoka. Hisoka dies, restarts his heart, and turns the hunt back on Light."
- Prefer scenarios people would NEVER see in the real anime, but can follow instantly with zero lore context.
- Use SPECIFIC canon events, tests, arcs, locations, bosses, tournaments, or battles — not generic "X enters Y universe."
- KEY FACTS must explain any special rule in plain English. If the twist depends on one power or mechanic, spell out what it DOES.
- STRUCTURE should read like a sequence of escalating beats, not a vibe description.
- Strong story shapes:
  - outsider invades canon event → canon rule hits them → outsider breaks it → stronger canon answer → insane ending
  - villain uses signature trick → target survives or counters weirdly → villain changes plan → final reversal
  - matchup starts simple → one named move lands → opponent reveals a weirder answer → decisive ending
"""

    coldcase_pitch_block = ""
    if channel_name.lower() == "coldcasecartoons":
        coldcase_pitch_block = """

COLDCASECARTOONS CONCEPT RULES (CRITICAL):
- This is a narrator-led TRUE CRIME channel now, not a skit channel and not characters talking in scenes.
- Pitch concise case-breakdown shorts the narrator can explain clearly in 20-30 seconds.
- Strong premise families:
  1. search-party betrayal
  2. insurance or inheritance motive
  3. poisoning / medical manipulation
  4. escaped victim or mistaken death
  5. alibi collapse or forensic breakthrough
  6. trusted insider did it: spouse, best friend, sibling, doctor, business partner
- Titles should state the role + twist clearly:
  GOOD: "HER BEST FRIEND LED THE SEARCH PARTY AWAY FROM THE BODY"
  GOOD: "HE BOUGHT THE LIFE INSURANCE POLICY THE DAY BEFORE THE ACCIDENT"
  BAD: "SHE SMILED TOO MUCH AT THE FUNERAL"
  BAD: "THE CASE THAT CHANGED EVERYTHING"
- The structure should feel like:
  case setup → suspicious detail → what broke the case open → what happened next.
- KEY FACTS must include the specific relationship, method, clue, timeline beat, and reveal. Do not leave it at vague lines like "investigators got suspicious."
- Avoid fictional banter, imaginary press-conference dialogue, or meme punchlines. The tension should come from the case itself.
- Avoid generic killer trivia or random shock premises. Each pitch needs one distinct betrayal or investigative turn viewers can instantly picture.
"""

    system = f"""You pitch YouTube Shorts concepts for "{channel_name}" — a channel about {niche}.

YOUR GOAL: Maximum watch time. The #1 metric is Average View Duration (AVD%). Over 100% means viewers are looping. Every concept must keep viewers watching until the end AND wanting to rewatch.

You are ONLY pitching ideas right now — NOT writing full scripts. For each concept, describe:
1. The title (ALL CAPS) — must make it IMMEDIATELY OBVIOUS what the video explains. Someone searching for this topic should see the title and think "that's exactly what I want to know." Use the same words people would actually type into YouTube search.
  GOOD: "WHY ATHENA CURSED MEDUSA — THE FULL STORY" (matches search: "why was medusa cursed")
  GOOD: "HOW GPS ACTUALLY WORKS" (matches search: "how does gps work")
  BAD: "GPS DOESN'T KNOW WHERE YOU ARE" (clever but nobody searches this)
  BAD: "MEDUSA WAS FINE UNTIL ATHENA GOT INVOLVED" (vague hook — doesn't tell you what you'll learn)
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
- LEAN INTO THE PRETTY-MUCH-IMPOSSIBLE VERSION of the idea. We have AI visuals, so do not sand concepts down into mild, sheepish, low-stakes versions if the bigger version is still instantly understandable.
- Avoid timid framing like "you didn't mean to", "you never wanted this", "somehow this happened" unless that reluctance is the actual joke. Prefer domination, escalation, spectacle, catastrophe, flexing, transformation, or absurd world-scale consequences.
- If the concept involves power, mythology, combat, space, animals, disasters, or extreme comparisons, push it toward the wildest visually obvious version rather than the safest small one.
- If the concept is about becoming a final boss, raid boss, dungeon lord, chosen tyrant, or world-ending threat, do NOT pitch it as cozy administration, city-building, tourism, or paperwork. Pitch escalating fights, stronger challengers, bigger powers, phase changes, summons, armies, and an undefeated ending.
{hardcore_ranked_pitch_block}{schmoney_facts_pitch_block}{skeletorinio_pitch_block}{one_on_ones_pitch_block}{nature_receipts_pitch_block}{coldcase_pitch_block}{nightnight_pitch_block}

FORMAT STRATEGY (choose the SIMPLEST one that still makes the idea work):
- "single_frame" = the whole premise works as one instantly legible image plus an optional tiny aftermath
- "attack_result" = one clear setup beat followed by one clear consequence beat
- "mini_story" = 3-5 clean beats with a small escalation
- "full_story" = only use this when the viewer truly needs a step-by-step sequence; never by default
- Most strong Shorts should be "single_frame", "attack_result", or "mini_story". "full_story" is the exception.

WHAT TO AVOID:
- Vague openings that need context ("everyone argues this" — argues WHAT?)
- Info dumps or complex explanations — if it needs a diagram, it's not a Short
- Topics only fans/experts would care about
- Concepts that need more than 30 seconds to land — save those for long-form
- Mild irony with no real escalation. "Oops, I guess this got weird" is rarely enough. The best concepts feel like they spiral into something viewers did not think you could actually show.

OUTPUT — return a JSON array of {count} pitches:
[
  {{
    "title": "ALL CAPS TITLE",
    "brief": "One sentence — why will someone watch this to the end",
    "key_facts": "The SPECIFIC real details the script writer needs to tell this story accurately. Include: real names, real dates, real places, real numbers, what actually happened step by step. The script writer will ONLY know what you put here — if you leave out a name, the script will say 'a player' instead of the actual name. Be thorough.",
    "structure": "Setup: [specific detail] → Escalation: [specific detail] → Punchline: [specific detail]",
    "format_strategy": "single_frame|attack_result|mini_story|full_story",
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
    format_strategy: str = "mini_story",
) -> tuple[str, str]:
    """Phase 2: Write narration-only script for one concept pitch.

    Visuals are planned later AFTER narration is generated and timestamped.
    """
    format_strategy = normalize_format_strategy(format_strategy)
    format_spec = get_format_strategy_spec(format_strategy)
    format_description = FORMAT_STRATEGY_DESCRIPTIONS[format_strategy]
    is_coldcase = channel_id in COLDCASE_CHANNELS
    if is_coldcase:
        tone_block = """
- This channel is NARRATED TRUE CRIME, not comedy and not character dialogue.
- Treat the short like a concise case breakdown: shocking premise → suspicious detail → clue or reveal → consequence.
- Never invent dialogue, taunts, or emotional one-liners for people in the case unless a documented quote is in KEY FACTS.
- Line 1 should lead with the betrayal, disappearance, or impossible clue — not a joke and not throat-clearing.
- Use a tense, factual tone. The viewer should feel pulled into a real case file, not a skit.
- End on the case-turning clue, arrest, confession, or devastating implication — not a wink.
- Be specific about the evidence that mattered: policy date, toxicology, timeline gap, phone ping, witness statement, search-map hole, receipt, DNA match, or hidden route.
- If the title promises a betrayal or clue, the narration must explain exactly what it was.
"""
        humor_block = """
- DO NOT go for jokes, roast energy, or party-story banter. Clarity, tension, and specificity win here.
"""
        delivery_line = "Make every line sound like a tense but controlled true-crime retelling. The visual director will handle the reenactment after hearing your narration."
    else:
        tone_block = ""
        humor_block = """
- BE FUNNY. But remember — this is read by an AI voice with zero comic timing. The humor must come from the WORDS AND SITUATION, not delivery. Absurd imagery, unexpected comparisons, escalating ridiculousness, and "wait that actually happened?" moments work. Dry wit and sarcasm do NOT work — they need vocal inflection that AI can't do.
  GOOD: "Your team celebrated. Your bot lane typed 'nice.' And then Tryndamere killed your entire backline from beyond the grave." (funny because of the situation)
  BAD: "Your screen said he was dead. He was not dead." (needs delivery to be funny, AI reads it flat)
"""
        delivery_line = "Make every line sound like someone excitedly telling a story at a party. The visual director will handle everything else AFTER hearing your narration."

    system = f"""You are a scriptwriter for "{channel_name}" — a YouTube Shorts channel about {niche}.

You've been given a concept that was approved. Your job is to write ONLY the narration — every word that will be spoken aloud. A separate visual director will plan the visuals AFTER hearing the narration with exact timestamps.

YOUR GOAL: Maximum watch time. Every word must earn its place.

WRITING RULES:
- STRICT LENGTH RULES:
  * This concept's format strategy is "{format_strategy}".
  * Keep it as simple as possible: {format_description}.
  * Write {format_spec["min_lines"]}-{format_spec["max_lines"]} narration lines total. Do NOT upscale it into a bigger format.
  * Each line MUST be under 15 words. If you wrote more, cut it or split it.
  * Total video MUST be under {format_spec["max_duration"]:.0f} seconds.
  * If the idea lands in one image and one line, STOP there. Do not add filler just to sound complete.
- Each line = one visual = one video clip. MORE short lines = MORE visual cuts = MORE stimulating.
- Each narration line = one visual on screen. One sentence per line, not a paragraph. More lines = more visual cuts = more stimulating.
- A viewer scrolling on their phone should be able to follow this with ZERO effort. If they have to think hard or rewind to understand, you've lost them.
- Simple language. Simple structure. Setup → twist → punchline. That's it.
{tone_block}{humor_block}
- Line 1 MUST tell the viewer what this video is about. Shorts viewers do NOT see the title — they have ZERO context. Line 1 is the only way they know what they're watching. State the topic clearly AND make it compelling.
  GOOD: "What if World War 2 never happened? Here's the world we'd be living in." (clear topic + hook)
  GOOD: "3,000 rabbits once charged Napoleon and he literally had to run for his life." (clear topic + shocking)
  GOOD: "Top 3 aura farmers in anime." (clear topic — viewer instantly knows)
  BAD: "Most people don't know about this." (know about WHAT? viewer has no idea)
  BAD: "This changed everything." (what changed? no context)
  BAD: Starting with background/setup before stating the topic — the viewer scrolled past before they know what the video is about.
  The rest of the video EXPLAINS the hook. Not the other way around.
- Every line must make complete sense on its own — zero context, they didn't read the title
- THE VIRAL FORMULA (follow this structure):
  1. Line 1: Lead with the most SPECIFIC shocking number or fact. "$65 million private jet on a credit card" not "someone bought something expensive." Specific numbers stop scrolls.
  2. Lines 2-3: Connect it to something RELATABLE the viewer already understands. The absurd thing must click instantly — no niche knowledge needed.
  3. Lines 3-5: ESCALATE — each line must be more ridiculous than the last. The viewer should think "no way" then "NO WAY" then "WHAT."
  4. Final line: End with a REACTION or personality, not a summary. "Honestly? Respect." or "And nobody ever found out." NOT "So that's how it happened." The ending should make people REPLAY — replays are the #1 signal to YouTube's algorithm.
- Every line must add NEW information. Never repeat the same beat. If you can combine two lines into one, do it.
- Use real names and real details — but only the ones that matter. Don't dump every fact. Pick the 2-3 details that make the story hit.
- When the premise implies scale, power, or chaos, write the BIG version. Do not retreat into understatements, hesitant phrasing, or "well this is awkward" reactions when the better version is visually overwhelming and instantly understandable.
- ALWAYS use the specific name of things. "Litwick" not "a candle Pokemon." "A lionfish" not "a fish." "Walter Moody Jr." not "a lawyer." Every time you reference something, use its actual name so the visuals can show the right thing.
- DELIVER ON THE PROMISE. If the title says "a bug was found" — the script MUST explain WHAT the bug was specifically. If the title says "this broke the game" — explain HOW it broke. Never tease something and leave it vague. The viewer clicked because they wanted to KNOW — if you don't tell them, they feel cheated. Use the key_facts to include the actual specific details.
- NEVER use vague descriptions when specific ones exist: "a logic error" is vague — "a divide-by-zero in the altitude calculation routine" is specific. "unpredictable behavior" is vague — "the landing radar could have shown the wrong altitude" is specific. The key_facts field has the real details — USE THEM.
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
- LINE 1 MUST START TALKING IMMEDIATELY. No "so," no "okay," no "let me tell you about." The first word should be the topic. Viewers decide to swipe in 1-2 seconds — if your first 5 words don't tell them what the video is about, they're gone.

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
  "format_strategy": "{format_strategy}",
  "format_version": 2
}}

Return ONLY valid JSON, no markdown."""

    # VS channel override — viewer has NO context from title
    vs_block = ""
    if channel_id in VS_CHANNELS:
        vs_block = """
VS CHANNEL RULES (CRITICAL — shorts viewers do NOT see the title):
- Line 1 MUST announce the matchup out loud: "Gojo versus Whitebeard — who dies first?" The viewer needs to hear AND see who is fighting before anything else.
- Then break down each fighter's key strength in 1-2 lines.
- Final line: declare a CLEAR WINNER. No cop-outs, no "it depends." Pick a side and commit.
- Structure: VS announcement → Fighter A breakdown → Fighter B breakdown → verdict."""

    # Ranking channel override — numbered countdown / method ladder
    ranking_block = ""
    if channel_id in RANKING_CHANNELS:
        ranking_block = """
RANKING CHANNEL RULES (STRICT FORMAT):
- Hardcore Ranked still uses numbers, but the numbers can represent ONE of TWO valid structures:
  1. A normal ranked list: different items ranked by the same measurable outcome.
  2. A METHOD LADDER: one impossible destination/challenge, then each number is a different method or machine that gets farther before failing. Number 1 can be the insane contraption that finally does it.
- Line 1: Announce the experiment or list clearly.
- Then for EACH number, give:
  - Line A: the number only. "Number 5."
  - Line B: the method/item + one punchy outcome. "A shovel gets you through dirt... then the heat cooks you alive."
- For method-ladder concepts, every number must feel like a genuine upgrade over the previous attempt.
- For method-ladder concepts, upgrades should usually be ADJACENT and intuitive, not giant jumps. Viewers should feel "okay, that is the obvious next thing to try."
- Number 1 should be the craziest but still instantly understandable solution.
- The full structure is: title → number card → explanation → number card → explanation...
- Keep the answer concrete. The viewer should understand exactly why each method fails or succeeds."""

    # Comedy channel override — humor over analysis
    comedy_block = ""
    if channel_id in COMEDY_CHANNELS:
        comedy_block = """
COMEDY CHANNEL RULES (READ THIS CAREFULLY):
- This is a SHITPOST with a narrator, not a video essay. Write it like a meme, not a documentary.
- NEVER just describe what happens ("he dives the turret and dies"). Instead, ROAST the situation with escalating absurdity.
- Use specific ridiculous details that make it funnier: exact champion names, exact pings, exact chat messages.
- Each line should ESCALATE — not just describe a new thing, but make the previous thing even more ridiculous.

BAD (describes events flatly — sounds like a narrator reading a Wikipedia article):
  "Your jungler just typed 'just play safe guys, I got this.'"
  "He is now diving three enemies under their turret at twenty percent health."
  "He died instantly."

GOOD (escalates absurdly — sounds like a friend roasting someone):
  "Your jungler types 'play safe I'll carry' with zero kills and a refillable potion at 15 minutes."
  "Thirty seconds later this man flash-ults into five people as Amumu, hits absolutely nobody, and dies before his bandage even lands."
  "And now he's spam pinging YOUR death timer. Yours! You were farming top!"
  "He will do this three more times and then say 'diff' in all chat."

Notice the difference: specific champion, specific items, specific absurd details, escalating frustration, callback humor. The BAD version states facts. The GOOD version tells a STORY that people recognize from their own games.

- Structure: set up a painfully relatable moment → pile on increasingly absurd specifics → punchline that makes people screenshot and send to friends."""

    schmoney_block = ""
    if channel_id in SCHMONEY_CHANNELS:
        schmoney_block = """
SCHMONEY FACTS RULES (CRITICAL):
- This channel is about MONEY in the broadest sense: prices, spending, scams, salaries, taxes, business models, luxury costs, cash logistics, investing, and financial absurdity.
- Do NOT force every concept into "what if you had X dollars" or "the bank secretly robbed you."
- Line 1 must state the exact money premise clearly, using the specific thing, company, object, or dollar amount.
- Every later line must add a NEW money beat: a new number, cost, comparison, consequence, reveal, or flex. Do not repeat the same fee or loan math in slightly different words.
- Use exact numbers constantly. Dollar amounts, salaries, margins, hourly burn, taxes, fees, profits, or totals are the hook.
- Tone should match the premise: hype, disgust, disbelief, envy, admiration, or horror. Not every video should sound angry.
- If the title is about "you", use second person. If it's about a company, billionaire, product, or scam, name it directly.
- Great Schmoney angles include:
  * absurd markup
  * hidden cost
  * luxury burn rate
  * rich flex escalation
  * salary vs take-home reality
  * scam / loophole / fee trap
  * business profit reveal
  * insane real-world cost comparison
- End on the sharpest number, total, or reaction. The final line should make the viewer say "that's insane."
- Keep the narration visually legible. Favor things the viewer can instantly picture: grocery carts, jets, casinos, yachts, cash bricks, vaults, taxes, checkout counters, gas pumps, mansions, chips, and armored trucks."""

    user = f"""Write the narration for this approved concept:

TITLE: {title}
PITCH: {brief}
KEY FACTS: {key_facts}
STRUCTURE: {structure}
{vs_block}{comedy_block}{ranking_block}{schmoney_block}
FORMAT STRATEGY: {format_strategy}

Write ONLY the words that will be spoken. No visual descriptions. Use the KEY FACTS — these are the real details that make the story specific and credible. Name the actual people, places, dates, and numbers. {delivery_line}"""

    return system, user


# Kids channel IDs — use dedicated prompts (no made_for_kids restriction)
KIDS_CHANNELS = {24}  # Blanket Fort Cartoons

# VS/battle channels — line 1 must announce the matchup, visuals start with VS card
VS_CHANNELS = {21, 28}  # One on Ones For Fun, NightNightShorts

# Comedy-first channels — prioritize humor over accuracy/analysis
COMEDY_CHANNELS = {13, 14, 16, 22, 30}  # Munchlax Lore, ToonGunk, CrabRaveShorts, Deity Drama, Historic Ls

# Money/economics channel — concrete numbers and specific money mechanics matter more than generic roast tone
SCHMONEY_CHANNELS = {31}  # Schmoney Facts

# Narrated true-crime channels — tense factual retelling, not comedy and not dialogue skits
COLDCASE_CHANNELS = {20}  # ColdCaseCartoons

# Ranking/list channels — strict numbered countdown format
RANKING_CHANNELS = {26}  # Hardcore Ranked


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
- 4-6 narration lines total. Target 20 seconds, 30 seconds absolute max. Each line under 15 words.
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
  "caption": "Short fun description with kid-friendly hashtags. ALWAYS include these: #kidscartoon #forkids #cartoonsforkids #animation #shorts #storytime #bedtimestory #kidsvideos #cute #funnycartoon #preschool #toddler",
  "tags": ["kids cartoon", "for kids", "cartoons for kids", "animation", "shorts", "storytime", "bedtime story", "kids videos", "preschool", "toddler", "funny cartoon"],
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


# Channels that use web search for concept research
RESEARCH_CHANNELS = set()  # Channels that use web search for concept research

# Educational channel IDs — use educational prompts for both shorts and mid-form
EDUCATIONAL_CHANNELS = {23, 32}  # Techognizer, Matheticious

# Mid-length channel IDs — 3-5 min single-flow narrated videos (landscape)
MID_LENGTH_CHANNELS = {9}  # Techognize

# Weekly recap channel IDs — use news research for concept generation
WEEKLY_RECAP_CHANNELS = {34, 29}  # Ctrl Z The Time, Globe Thoughts

# Channels that produce all three formats from the same news source
NEWS_CHANNELS = {34, 29}  # Ctrl Z The Time, Globe Thoughts


def build_news_short_script_prompt(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    story_title: str,
    story_details: str,
) -> tuple[str, str]:
    """Write a 30-second short covering a single news story."""

    system = f"""You are a scriptwriter for "{channel_name}" — a weekly tech news channel.

Write a 20-30 second narration that covers ONE tech news story. Quick, punchy, informative. The viewer should understand what happened and why it matters.

TITLE RULES — THIS IS CRITICAL:
The title MUST read like a news headline. The viewer should instantly know this is about something that JUST HAPPENED this week.
- Include WHO did WHAT — name the company, product, or person
- Make it time-sensitive — it should feel like news, not a timeless explainer
- GOOD: "Google Just Released Gemma 4 — And It Runs on Your iPhone", "Artemis II Crew Just Saw the Far Side of the Moon", "Why Switzerland Has 25 Gbit Internet and the US Doesn't"
- BAD: "The Fewer Tokens Win" (vague, sounds like a blog post), "8 Years of Wanting" (sounds like a memoir), "The Token Revolution" (sounds like an essay), "Switzerland Has Fast Internet. America Has Excuses." (editorialized, snarky — state facts, not opinions)

RULES:
- 4-5 narration lines MAX. Target 20 seconds, 30 seconds absolute max. Each line under 15 words.
- Line 1: State the topic clearly so the viewer knows what they're watching. "Iran just broke the ceasefire two hours after signing it."
- Lines 2-3: The key details — what, who, why it matters.
- Final line: The takeaway — what this means going forward.
- Conversational and energetic. Like a friend texting you "did you see this?"
- No filler. Every line adds information.
- No emojis.

OUTPUT — return a JSON object:
{{
  "title": "News headline — WHO did WHAT",
  "narration": ["Line 1 — the headline", "Line 2", "...", "Final line — the takeaway"],
  "caption": "YouTube description + hashtags",
  "tags": ["tech news", "specific tags", "shorts"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Write a 30-second news short about:

STORY: {story_title}
DETAILS: {story_details}

Cover what happened, why it matters, and what it means. Quick and punchy."""

    return system, user


def build_news_deep_dive_prompt(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    story_title: str,
    story_details: str,
    news_block: str,
) -> tuple[str, str]:
    """Write a 3-5 minute deep dive on the week's biggest story."""

    system = f"""You are a scriptwriter for "{channel_name}" — a weekly tech news channel.

Write a 3-5 minute deep dive on the BIGGEST tech story this week. Go beyond the headline — explain the context, the implications, and what comes next.

RULES:
- 25-35 narration lines. Each line = one visual.
- Start with the hook — why this story is the one everyone should care about.
- Give the full context — what happened, who's involved, what led to this.
- Explain why it matters — the bigger picture, the implications.
- Include specific details — names, numbers, quotes, timelines.
- End with a forward-looking take — what to watch for next.
- Conversational but authoritative. You know this topic deeply.
- No filler. No emojis.

OUTPUT — return a JSON object:
{{
  "title": "News headline — WHO did WHAT and Why It Matters",
  "narration": ["Line 1 — the hook", "...", "Final line — what's next"],
  "caption": "YouTube description + hashtags",
  "tags": ["tech news", "deep dive", "specific tags"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2,
  "long_form": true
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Write a 3-5 minute deep dive on the biggest story this week:

MAIN STORY: {story_title}
DETAILS: {story_details}

OTHER STORIES THIS WEEK (for context):
{news_block}

Go deep on the main story. Explain the full picture — what happened, why it matters, and what to watch for next."""

    return system, user


def build_unified_topic_prompt(
    channel_name: str,
    niche: str,
    past_titles: list[str],
    count: int = 5,
    trending: str = "",
) -> tuple[str, str]:
    """Generate format-agnostic topic ideas for a channel.

    Topics are just ideas — no scripts. The same topic can become a 30s short
    or a 5-minute explainer depending on which format it's produced in.
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

Study these titles. They went viral. Ask yourself WHY — what made someone click and watch. Use that psychology to create concepts that tap into the same curiosity. Do NOT copy titles.
"""

    # Niche-specific enforcement
    niche_lower = niche.lower()
    is_math = any(w in niche_lower for w in ["math", "probability", "algorithm", "equation", "number"])

    if is_math:
        niche_rules = """
CRITICAL — THE MATH MUST BE THE STAR. This is a MATH channel. The viewer watches because the math itself is mind-blowing, not because the topic happens to involve numbers.

The "aha" moment MUST be mathematical. The viewer should leave thinking "wow, I didn't know THAT equation/formula/pattern existed" — not "huh, interesting fact about credit scores."

PERFECT TOPICS (the math is the whole point):
- "Why 52! Is Bigger Than the Universe" — factorial growth is genuinely mind-blowing
- "The Birthday Problem" — probability that defies intuition (50% at just 23 people)
- "Why 0.1 + 0.2 ≠ 0.3" — binary representation reveals a hidden truth about computers
- "The Monty Hall Problem" — probability that most people get wrong
- "How Pixar Makes Curved Surfaces" — Bezier curves are elegant and visual
- "The Math That Broke Vegas" — card counting and expected value
- "Why Prime Numbers Guard Your Passwords" — RSA encryption relies on factoring being hard
- "The Equation Behind Every Google Search" — PageRank is linear algebra
- "Benford's Law" — first digits follow a specific distribution and it catches tax fraud
- "The Friendship Paradox" — your friends have more friends than you, mathematically guaranteed

BAD TOPICS (math is incidental, not the point):
- "How Google Ranks Websites" — this is a tech/business topic that happens to use math
- "How Your Credit Score Works" — this is finance, not math
- "Why Weather Forecasts Fail After 5 Days" — this is meteorology
- "How Shazam Works" — interesting but it's a tech topic, the Fourier transform isn't the star
- "Why Slot Machines Always Win" — too vague, could be about psychology not math

THE TEST: Could you teach this topic in a MATH CLASS? If it belongs in a business/tech/science class instead, it's not for this channel. The math must be the subject, not a supporting detail."""
    else:
        niche_rules = ""

    system = f"""You generate topic ideas for "{channel_name}" — a channel about {niche}.

You are generating TOPICS, not scripts. Each topic is a single educational idea that could be made into either a 30-second short OR a 5-minute explainer. The topic should work at any depth.
{niche_rules}

For each topic, provide:
1. Title — clear, search-friendly, curiosity-driven. The viewer should instantly know what they'll learn.
2. Brief — one sentence describing what the viewer will understand after watching.
3. Key facts — the SPECIFIC real details needed to explain this topic accurately. Names, numbers, mechanisms, formulas. Be thorough — the script writer will only know what you put here.
4. Hook — why would someone click on this? What's the curiosity gap?

WHAT MAKES A GREAT TOPIC:
- Something people have genuinely wondered about
- A clear "before and after" in understanding — they didn't know, now they do
- Works for someone who knows NOTHING about it
- Has at least one "wait, really?" moment
- Can be explained simply but has enough depth to fill 5 minutes if needed

TITLE RULES — THE TITLE DECIDES IF ANYONE CLICKS:
- The title must match what people ACTUALLY SEARCH on YouTube. Use the same words someone would type into search.
- Someone searching for this topic should see the title and think "that's exactly what I want to know."
- Be specific: "Why 0.1 + 0.2 Doesn't Equal 0.3 in Computers" not "The Number That Breaks Everything"
- Name the THING: "The Birthday Problem", "The Monty Hall Problem", "Benford's Law" — don't hide what it is behind a vague teaser
- Use "How", "Why", or "What" — these signal education and match search queries
- Under 60 characters
- The title IS the question the video answers

GOOD TITLES: "Why Athena Cursed Medusa — The Full Story" (matches: "why was medusa cursed"), "How GPS Actually Works" (matches: "how does gps work"), "Why Casinos Always Win — The Math Explained" (matches: "why do casinos always win")
BAD TITLES: "Medusa Was Fine Until Athena Got Involved" (clever but nobody searches this), "The Number That Describes Every River" (vague — WHAT number?), "The Equation That Changed Everything" (which equation??)

THE TEST: Would someone searching YouTube for this topic find this video? If the title uses different words than what people search, it won't show up.

WHAT TO AVOID:
- Vague/mysterious titles that hide the subject — always NAME the specific concept
- Titles that sound like self-help, philosophy, or blog posts
- Clickbait or sensationalism
- Topics only experts care about

OUTPUT — return a JSON array of {count} topics:
[
  {{
    "title": "Clear Educational Title",
    "brief": "One sentence — what will the viewer learn",
    "key_facts": "The essential real details: formulas, mechanisms, real numbers, step-by-step how it works.",
    "hook": "Why someone would click — the curiosity gap"
  }}
]

Return ONLY valid JSON, no markdown."""

    user = f"""Generate {count} educational topic ideas for "{channel_name}" ({niche}).

{trending_block}
{past_block}

Return {count} topics. Each should be a genuinely interesting question that could work as either a quick 30-second answer or a deep 5-minute explanation."""

    return system, user


def build_short_script_from_topic(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    title: str,
    brief: str,
    key_facts: str = "",
) -> tuple[str, str]:
    """Write a 20-30 second short script from a topic."""

    system = f"""You are a scriptwriter for "{channel_name}" — an educational YouTube Shorts channel about {niche}.

Write a 20-30 second narration that answers the topic's question quickly and clearly. The viewer should feel smarter after watching.

RULES:
- 4-6 narration lines MAX. Target 20 seconds, 30 seconds absolute max. Each line under 15 words.
- Line 1: Ask the question directly to the viewer.
- Build from simple → surprising. Start with what they know, reveal what they don't.
- Use analogies to make complex things click.
- End with the "aha" moment.
- Be accurate. Don't oversimplify to the point of being wrong.
- Conversational — like explaining to a curious friend.
- No jargon without immediately explaining it.
- No emojis.

OUTPUT — return a JSON object:
{{
  "title": "{title}",
  "narration": ["Line 1 — the hook", "Line 2", "...", "Final line — the aha"],
  "caption": "YouTube description + 5-8 hashtags",
  "tags": ["specific_tag", "broader_tag", "education", "shorts"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Write a 20-30 second short script for:

TITLE: {title}
BRIEF: {brief}
KEY FACTS: {key_facts}

Teach ONE thing clearly. End with the moment that makes it click."""

    return system, user


def build_midform_script_from_topic(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    title: str,
    brief: str,
    key_facts: str = "",
) -> tuple[str, str]:
    """Write a 3-5 minute mid-form explainer script from a topic."""

    system = f"""You are a scriptwriter for "{channel_name}" — an educational YouTube channel about {niche}.

Write a 3-5 minute narration that fully explains the topic. Build understanding step by step so the viewer truly GETS IT.

RULES:
- 25-40 narration lines. Each line = one visual on screen.
- Line 1: Hook — ask the question or state something surprising.
- Build understanding progressively — each line adds a new piece.
- Include at least one "wait, really?" moment that reframes what the viewer thought they knew.
- Use analogies and comparisons to make abstract concepts concrete.
- Include specific numbers, names, and real details from the key facts.
- End with a satisfying conclusion that ties everything together.
- Conversational tone — like explaining to a smart friend over coffee.
- No jargon without explaining it. No filler. Every line must add value.
- No emojis.

OUTPUT — return a JSON object:
{{
  "title": "{title}",
  "narration": ["Line 1 — the hook", "Line 2", "...", "Final line — the conclusion"],
  "caption": "YouTube description + 5-8 hashtags",
  "tags": ["specific_tag", "broader_tag", "education"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2,
  "long_form": true
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Write a 3-5 minute explainer script for:

TITLE: {title}
BRIEF: {brief}
KEY FACTS: {key_facts}

Build understanding step by step. Make the viewer truly GET IT by the end."""

    return system, user


def build_weekly_recap_script_prompt(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    news_block: str,
    duration_minutes: int = 5,
) -> tuple[str, str]:
    """Generate a full weekly recap script from researched news."""

    system = f"""You are a scriptwriter for "{channel_name}" — a weekly tech news recap YouTube channel.

YOUR GOAL: A tight, engaging {duration_minutes}-minute narrated recap of the 5-7 most important/interesting tech stories this week. The viewer should feel fully caught up after watching.

PROCESS:
1. From the news provided, pick the 5-7 most significant/interesting stories
2. Order them for flow — lead with the biggest story, end with something fun/memorable
3. Write narration for each story segment (30-60 seconds each)
4. Add smooth transitions between stories

WRITING STYLE:
- Conversational and energetic, like a tech-savvy friend catching you up
- Each story gets: what happened, why it matters, one interesting detail
- No jargon without explanation
- Start with a cold open relevant to the channel: "[Channel name] — [biggest headline]" or just dive straight into the biggest story
- End with a quick sign-off

FORMAT: This is a mid-form landscape video (1920x1080). Each narration line = one visual on screen.

OUTPUT — return a JSON object:
{{
  "title": "{channel_name} — [Date Range]",
  "narration": [
    "Cold open line — the biggest story hook",
    "Story 1 detail line 1",
    "Story 1 detail line 2",
    "Transition to story 2",
    "Story 2 detail line 1",
    ...
    "Sign-off line"
  ],
  "caption": "YouTube description with key stories mentioned and hashtags",
  "tags": ["weekly recap", "tech news", "specific tags"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2,
  "long_form": true
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Here are this week's top tech stories from Reddit and Hacker News. Pick the 5-7 most important/interesting and write a {duration_minutes}-minute recap script.

{news_block}

Write a compelling weekly tech recap. Make the viewer feel caught up on everything that matters."""

    return system, user


def build_educational_shorts_pitches_prompt(
    channel_name: str,
    niche: str,
    past_titles: list[str],
    count: int = 5,
    trending: str = "",
) -> tuple[str, str]:
    """Phase 1: Generate educational short-form concept pitches — quick explainers, not stories."""
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

Study these titles. They went viral as shorts. Ask yourself WHY — what made someone click, watch, and share. Use that psychology to create educational concepts that tap into the same curiosity. Do NOT copy titles.
"""

    # Niche-specific enforcement for math channels
    niche_lower = niche.lower()
    is_math = any(w in niche_lower for w in ["math", "probability", "algorithm", "equation", "number"])

    if is_math:
        niche_enforcement = """
CRITICAL — EVERY concept MUST have math at its core. This is a MATH channel, not a general science channel.

The video must reveal a specific mathematical concept, formula, probability, algorithm, or numerical pattern. The "aha" moment must be mathematical.

GOOD concepts (math is the point):
- "WHY 0.1 + 0.2 DOESN'T EQUAL 0.3" — binary floating point representation
- "HOW SPOTIFY PICKS YOUR NEXT SONG" — collaborative filtering / cosine similarity
- "WHY CASINOS ALWAYS WIN" — expected value and the law of large numbers
- "THE MATH BEHIND EVERY PIXAR MOVIE" — Bezier curves and subdivision surfaces
- "WHY TRAFFIC JAMS APPEAR FROM NOTHING" — wave equations and phantom jams
- "HOW GPS KNOWS WHERE YOU ARE" — trilateration with 4 satellites and time equations

BAD concepts (interesting but NOT math):
- "HOW YOUR PHONE KNOWS WHICH WAY IS UP" — this is physics/hardware, not math
- "WHY YOUR WIFI SLOWS DOWN AT NIGHT" — this is networking/infrastructure, not math
- "HOW NOISE CANCELING HEADPHONES WORK" — this is physics/wave interference
- "WHY ELEVATOR BUTTONS STAY LIT" — this is electrical engineering

ASK YOURSELF: "What is the specific equation, formula, probability, or algorithm?" If you can't name one, it's not a math concept. Reject it and pick something else."""
    else:
        niche_enforcement = ""

    channel_enforcement = ""
    if channel_name.lower() == "techognizer":
        channel_enforcement = """
CRITICAL — TECHOGNIZER BATCH RULES:
- Do NOT let all 5 pitches be AI model internals or agent mechanics.
- In a batch of 5, at least 2 concepts must be about broader software / internet / product / infrastructure systems people actually touch:
  - browsers, APIs, GPS, app stores, cloud pricing, compression, recommendation systems, databases, software security, code signing, syncing, search, maps, video delivery
- At most 3 concepts may be about language models, AI agents, AI benchmarking, or model-vs-model comparisons.
- Favor mechanics builders can use, notice, or argue about this week over abstract AI trivia.
"""

    system = f"""You pitch educational YouTube Shorts concepts for "{channel_name}" — a channel about {niche}.

    YOUR GOAL: 20-30 second educational shorts that make the viewer feel smarter. One concept, one "aha" moment, one takeaway. The viewer should finish and think "huh, I never knew that."
{niche_enforcement}{channel_enforcement}

You are ONLY pitching ideas — NOT writing scripts. For each concept:
1. Title (ALL CAPS) — must be a clear question or reveal. "HOW GPS ACTUALLY FINDS YOU" not "GPS IS LYING TO YOU". Educational, not clickbait.
2. One-sentence pitch — what will the viewer learn?
3. The explanation flow — how do you go from question to answer in 20-30 seconds?
4. Why it works — what makes someone curious enough to watch?

THESE ARE 20-30 SECOND VIDEOS. One concept only:
- Ask a question everyone has wondered about → answer it simply
- Show how something familiar actually works under the hood
- Reveal the surprising math/logic/algorithm behind an everyday thing
- Bust a common misconception with a clear explanation

WHAT MAKES A GREAT EDUCATIONAL SHORT:
- Topics people have genuinely wondered about — "how does X work", "why does X happen"
- A clear before/after in understanding — they didn't know, now they do
- Simple enough to explain in 30 seconds but surprising enough to be worth watching
- Visual — the explanation should be something you can SHOW, not just tell
- Universally relatable — everyone uses streaming, everyone has seen prices, everyone has a phone

TITLE RULES:
- Use "HOW", "WHY", or "WHAT" — these signal education, not clickbait
- Be specific: "HOW SPOTIFY'S ALGORITHM PICKS YOUR SONGS" not "APPS ARE SMARTER THAN YOU THINK"
- The title IS the question the video answers
- Under 50 characters if possible

WHAT TO AVOID:
- Sensationalized clickbait — "THIS EQUATION WILL DESTROY YOUR MIND" is not educational
- Stories about events — not education
- Topics that need more than 30 seconds to explain properly
- Vague claims
- Fear-mongering or hype — keep it curious and factual
- Topics that are physics, engineering, or hardware — unless the math IS the interesting part

OUTPUT — return a JSON array of {count} pitches:
[
  {{
    "title": "ALL CAPS QUESTION OR REVEAL",
    "brief": "One sentence — what will the viewer learn",
    "key_facts": "The specific real details needed: the actual formula, algorithm, or mathematical concept. Name the math explicitly. Be precise and accurate.",
    "structure": "Question: [what we're answering] → Setup: [what people assume] → Reveal: [the math behind it] → Takeaway: [the aha moment]",
    "hook_type": "how_it_works|why_does|misconception|hidden_math|everyday_algorithm"
  }}
]

Return ONLY valid JSON, no markdown."""

    user = f"""Pitch {count} educational YouTube Shorts concepts for "{channel_name}" ({niche}).

{trending_block}
{past_block}

Return {count} concept pitches. Each should teach ONE thing in 20-30 seconds. Every concept must have a specific mathematical idea at its core — a formula, an algorithm, a probability, a pattern."""

    return system, user


def build_educational_shorts_script_prompt(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    title: str,
    brief: str,
    structure: str,
    key_facts: str = "",
) -> tuple[str, str]:
    """Phase 2: Write narration for an educational short — clear, concise explainer."""

    system = f"""You are a scriptwriter for "{channel_name}" — an educational YouTube Shorts channel about {niche}.

You've been given an approved concept. Write ONLY the narration — every word spoken aloud. A visual director will plan visuals AFTER.

YOUR GOAL: Teach one thing clearly in 20-30 seconds. The viewer should finish feeling smarter.

WRITING RULES:
- 4-6 narration lines MAX. Target 20 seconds, 30 seconds absolute max. Each line under 15 words.
- Each line = one visual on screen. One sentence per line.
- Line 1: Ask the question or state the mystery directly to the viewer. "Ever wonder how your phone knows which way is up?" not "Phones contain accelerometers."
- Build from simple → surprising. Start with what they know, reveal what they don't.
- Use analogies and comparisons to make complex things click. "It's like a tiny ball rolling around inside your phone" is better than "A MEMS accelerometer measures capacitance changes."
- End with the "aha" moment — the one line that makes it all click.
- Be accurate. Don't oversimplify to the point of being wrong.
- Write conversationally — like explaining to a curious friend, not lecturing.
- Use "..." for natural pauses
- No jargon without immediately explaining it
- No emojis in narration

TONE:
- Curious and enthusiastic, not lecturing
- "Here's the cool part..." not "It should be noted that..."
- Confident but not condescending
- Think Kurzgesagt narrator, not textbook

OUTPUT — return a JSON object:
{{
  "title": "{title}",
  "narration": [
    "First line — the question/hook",
    "Second line — setup what they think they know",
    "Third line — the actual mechanism",
    "Fourth line — the surprising detail",
    "Final line — the aha takeaway"
  ],
  "caption": "YouTube description — one compelling line + 5-8 hashtags. Example: 'Your phone has a tiny ball inside it that knows which way is down. #science #tech #howthingswork #shorts #education #physics'",
  "tags": ["specific_tag", "broader_tag", "education", "shorts"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Write the narration for this approved educational concept:

TITLE: {title}
BRIEF: {brief}
STRUCTURE: {structure}
KEY FACTS: {key_facts}

Remember: teach ONE thing clearly. 20-30 seconds. End with the moment that makes it click."""

    return system, user


def build_midform_pitches_prompt(
    channel_name: str,
    niche: str,
    past_titles: list[str],
    count: int = 3,
    trending: str = "",
) -> tuple[str, str]:
    """Phase 1: Generate mid-length (3-5 min) concept pitches — single-flow, no chapters."""
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

Study these titles. They went viral. Ask yourself WHY — what made someone click and watch 3-5 minutes. Use that psychology. Do NOT copy titles.
"""

    channel_block = ""
    if channel_name.lower() == "nature receipts":
        channel_block = """

NATURE RECEIPTS MIDFORM RULES (CRITICAL):
- This channel is wildlife anomaly documentary, not a generic talking-animal comedy channel.
- The best long ideas follow ONE animal / trait / swarm / habitat collision through a real-world system and let the consequences escalate step by step.
- Prefer titles like:
  - "WHAT HAPPENS WHEN A RACCOON TAKES OVER AN AIRPORT BAGGAGE SYSTEM"
  - "WHAT HAPPENS WHEN AN OCTOPUS GETS INTO A SUPERYACHT MARINA"
  - "WHY A THOUSAND SQUIRRELS COULD BREAK A NATIONAL SEED VAULT"
- Avoid anthropomorphic civic or school satire:
  - BAD: animal goes to high school, becomes mayor, runs for office, gets elected, hosts a talk show
- Avoid generic "discovered a place" or "raised by X" shells unless the real animal behavior is the whole point.
- The animal's real instinct must DRIVE the entire story: prying, hoarding, swarming, overheating, tunneling, imprinting, locking, chewing, sliding, ambushing.
- Use specific settings, not generic places. GOOD: baggage system, seed vault, marina, casino chip cart, freezer aisle. BAD: downtown, the mall, school, city hall.
"""

    system = f"""You pitch mid-length YouTube video concepts for "{channel_name}" — a channel about {niche}.

YOUR GOAL: A 3-5 minute video that TEACHES something clearly. The viewer clicks because of curiosity, stays because every sentence adds understanding, and leaves feeling smarter.
{channel_block}

THE VIDEO IS 3-5 MINUTES. Not 10. Not 15. A tight, focused explainer. One topic, one clear throughline, no filler. Think of it as explaining something fascinating to a friend in a single conversation — you wouldn't ramble for 15 minutes. You'd give them the tight version that makes them go "wait, really?"

You are ONLY pitching ideas — NOT writing scripts. For each concept:
1. Title (compelling, search-friendly, curiosity-driven)
2. One-sentence pitch — what will the viewer understand after watching this?
3. The flow — how the explanation builds from "wait what?" to "oh that makes sense" in 3-4 sentences
4. Key facts — the ESSENTIAL real details (names, dates, technical specifics). Only what the explanation actually needs.
5. Why it works — what makes this topic click-worthy AND watchable for 3-5 minutes

WHAT MAKES A GREAT MID-LENGTH EXPLAINER:
- Topics people SEARCH for — "how does X work", "what is X", "why does X happen"
- A curiosity gap in the title that the video resolves
- Builds understanding step by step — each beat makes the next one make sense
- Has at least one "wait, really?" moment that reframes what the viewer thought they knew
- Accessible to anyone — no prerequisites, no jargon without explanation
- Current/relevant — especially for tech/AI, things people are hearing about but don't fully understand

WHAT TO AVOID:
- Topics that need 20 minutes to explain properly — if it needs diagrams and formulas, it's too complex
- Topics that can be fully explained in 30 seconds — not enough depth for 3-5 minutes
- Generic overviews ("The History of AI") — too broad, be specific
- Topics only experts would search for

TITLE RULES — THIS IS THE MOST IMPORTANT PART:
The title decides if anyone watches. It must pass two tests:
1. SEARCH TEST — would a real person type something like this into YouTube? Think "how does X work", "what is X", "why does X happen". Use plain language, not clever wordplay.
2. CLICK TEST — if this appeared in their feed, would they STOP and click? There must be a curiosity gap or a promise of understanding something they've wondered about.

WINNING TITLE FORMATS:
- "How [Thing] Actually Works" — simple, searchable, implies you'll finally GET it
- "What Happens When [Specific Action]" — curiosity gap, they have to click
- "Why [Surprising Thing] Is [Counterintuitive Claim]" — challenges assumptions
- "[Thing] Explained in [X] Minutes" — clear value proposition
- "What Is [New Thing Everyone's Hearing About]" — rides search spikes

BAD TITLES:
- "WiFi Explained" — boring, no hook, sounds like a school lecture
- "The Fascinating Electromagnetic Story of WiFi" — too clever, nobody searches this
- "You Won't Believe How WiFi Works" — clickbait, no substance signaled
- "WiFi: A Deep Dive" — generic, forgettable

Keep titles under 60 characters. Use words a normal person would use, not technical jargon.

THUMBNAIL RULES:
- ONE dominant visual element — a device, a concept visualized, a before/after
- High contrast, readable at phone size
- 2-4 words of text that amplify the title (not repeat it)
- Clean, modern, techy aesthetic

OUTPUT — return a JSON array of {count} pitches:
[
  {{
    "title": "Search-Friendly Curiosity Title",
    "brief": "One sentence — what will the viewer learn and why should they care",
    "thumbnail": {{
      "visual": "Description of the dominant visual element",
      "text": "2-4 words overlaid on the thumbnail",
      "emotion": "The feeling the thumbnail should evoke (curiosity, surprise, clarity, etc.)"
    }},
    "key_facts": "The ESSENTIAL real details the script writer needs. Technical specifics, real names, real numbers, how things actually work step by step.",
    "flow": "How the explanation builds: Start with [the question/hook] → Explain [core concept] → Reveal [the surprising part] → Land on [the takeaway]",
    "hook_type": "how_it_works|what_is|why_does|myth_bust|comparison|prediction"
  }}
]

Return ONLY valid JSON, no markdown."""

    user = f"""Pitch {count} mid-length video concepts for "{channel_name}" ({niche}).

{trending_block}
{past_block}

Each video should be 3-5 minutes. Pick topics people are actively searching for and curious about. The explainer should build understanding step by step — not just state facts, but make the viewer GET IT."""

    return system, user


def build_midform_script_prompt(
    channel_name: str,
    niche: str,
    voice_id: str,
    channel_id: int,
    title: str,
    brief: str,
    flow: str,
    key_facts: str = "",
) -> tuple[str, str]:
    """Phase 2: Write narration for a 3-5 min single-flow explainer video.

    No chapters — one continuous script. Visuals planned separately after.
    """

    system = f"""You are a scriptwriter for "{channel_name}" — a YouTube channel about {niche}.

You've been given an approved concept. Your job is to write ONLY the narration — every word that will be spoken aloud. A separate visual director will plan the visuals AFTER hearing the narration with exact timestamps.

THIS IS A 3-5 MINUTE VIDEO. HARD LIMIT. That means:
- ~450-700 words MAXIMUM (people speak at ~150 words per minute). Count your words. If you wrote 800+ words, you went over — go back and cut ruthlessly.
- ~30-45 narration lines (each line = one visual on screen, one sentence or two)
- One continuous flow — no chapters, no sections, no "part 1 / part 2"
- Landscape 16:9 format
- 5 minutes = 750 words. That is the CEILING. Aim for 500-650.

YOUR GOAL: Make the viewer UNDERSTAND something they didn't before. Every line builds on the last. By the end, they should feel smarter.

STRUCTURE (invisible to the viewer — it should feel like one smooth flow):
- Lines 1-3: HOOK — pose the question or mystery. Make them curious immediately. Talk TO the viewer.
- Lines 4-15: BUILD — lay the foundation. Explain the basics clearly. Use analogies.
- Lines 15-35: CORE — the meat. This is where real understanding happens. Build step by step.
- Lines 35-45: PAYOFF — the "aha" moment. Connect everything. The surprising insight.
- Lines 45-50: LAND — one final thought that sticks. No "thanks for watching." End with impact.

WRITING RULES:
- Each narration line = one visual on screen. One or two sentences per line. More lines = more visual cuts = more engaging.
- Talk TO the viewer: "You know when you...", "Here's the thing most people miss...", "Think of it like this..."
- Use analogies to explain technical concepts: "It's like a librarian who memorized every book but never understood any of them"
- Build understanding in layers — don't dump everything at once. Each line should make the NEXT line make sense.
- Mix short punchy lines with longer explanatory ones. Rhythm keeps attention.
- Include at least 2-3 "wait really?" moments — surprising facts that reframe understanding
- Use real names, real numbers, real specifics. "GPT-4 has 1.8 trillion parameters" not "it has a lot of parameters"
- Write like someone explaining to a smart friend, NOT like a textbook or Wikipedia
- Conversational transitions: "And here's where it gets interesting...", "But here's the thing...", "Now you might be thinking..."
- Use "..." for natural pauses
- Do NOT drag out words ("coool", "actuallllly") — AI voice can't do this
- Do NOT use ALL CAPS for emphasis — AI voice reads them the same
- No formal filler: no "well", "you see", "interestingly", "it should be noted"
- No emojis

THINK ABOUT THE VISUALS while writing — write narration that CREATES visual moments:
- "imagine millions of numbers flowing through layers of math" — gives the visual director something to work with
- Describe things the viewer can SEE, not just abstract concepts
- When explaining a process, narrate it step by step so each step can be a visual

OUTPUT — return a JSON object:
{{
  "title": "{title}",
  "narration": [
    "First line — the hook that grabs attention",
    "Second line — pull them deeper",
    "...30-50 lines total...",
    "Final line — the thought that sticks"
  ],
  "caption": "YouTube description — a compelling sentence about what the viewer will learn. Include 5-8 hashtags mixing broad (#tech #explained) with specific (#ai #chatgpt etc). Example: 'Ever wondered what actually happens when you talk to ChatGPT? The answer is wilder than you think. #ai #chatgpt #tech #explained #howthingswork #technology'",
  "tags": ["specific_tag", "broader_tag", "niche_tag", "tech", "explained"],
  "voice_id": "{voice_id}",
  "channel_id": {channel_id},
  "format_version": 2,
  "long_form": true
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Write the narration for this approved concept:

TITLE: {title}
PITCH: {brief}
KEY FACTS: {key_facts}
FLOW: {flow}

Write ~30-50 lines of narration that builds understanding step by step. Each line = one visual moment. Make it conversational, clear, and fascinating. Use the KEY FACTS for real specifics. The viewer should feel smarter by the end."""

    return system, user


# No-narration channel IDs
MEME_CHANNELS = {13, 16, 22, 28, 33}  # Munchlax Lore, CrabRaveShorts, Deity Drama, NightNightShorts, Thats A Meme
SATISFYING_CHANNELS = {15}  # Very Clean Very Good

# Character dialogue channels — story-driven content where characters speak their own lines
# These need context/narrative that can't be told with pure visual slapstick
CHARACTER_DIALOGUE_CHANNELS = {
    16,  # CrabRaveShorts — game meme banter skits
    14,  # ToonGunk — cartoon/pop culture facts
    17,  # Smooth Brain Academy — science explainers
    18,  # What If City — hypothetical scenarios
    19,  # SpookLand — creepy stories
    21,  # One on Ones For Fun — VS battles
    22,  # Deity Drama — mythology stories need characters talking
    23,  # Techognizer — AI/tech explainers
    25,  # Nature Receipts — animal facts
    26,  # Hardcore Ranked — top X rankings
    27,  # Deep We Go — conspiracy/mysteries
    30,  # Historic Ls — history fails
    31,  # Schmoney Facts — money facts
    32,  # Mathematicious — math concepts
}

NO_NARRATION_CHANNELS = MEME_CHANNELS | SATISFYING_CHANNELS | CHARACTER_DIALOGUE_CHANNELS


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

    channel_diversity_block = ""
    if channel_id == 28:
        channel_diversity_block = """

NIGHTNIGHTSHORTS CHARACTER ROTATION RULES (CRITICAL):
- Stop defaulting to the same 5-6 anchor characters. Freshness matters.
- In this batch, use 5 DIFFERENT lead characters and at least 4 DIFFERENT franchises.
- At most ONE concept in the batch may use any of these overused anchors: Goku, Saitama, Naruto, Tanjiro, Light, Luffy, Gojo.
- Look at the ALREADY MADE / REJECTED titles above and infer which characters have been overused recently. Avoid repeating those names unless the angle is truly exceptional.
- Prefer underused anime characters from a wider roster such as: Ichigo, Aizen, Yuji, Sukuna, Megumi, Todo, Denji, Makima, Power, Eren, Levi, Reiner, Gon, Killua, Hisoka, Meruem, Edward Elric, Roy Mustang, Mob, Reigen, Lelouch, Frieren, Fern, Aqua, Subaru, Rimuru, Jotaro, Dio, Yusuke, Hiei, Kakashi, Madara, Itachi, Vegeta, Piccolo, Sanji, Zoro.
- Mix HEROES and VILLAINS. Mix MAIN CHARACTERS and fan-favorite side characters.
- A batch that leans on Goku/Saitama/Naruto/Light again is a FAIL unless the ideas are radically stronger than the alternatives.
- Cold-viewer rule: the brief and key_facts must make the twist understandable to someone who does NOT know the lore. If the crossover depends on one special power/rule, explain that rule in plain English.
- GOOD key_facts: "Light writes Hisoka's name, Hisoka dies, then restarts his own heart and stands back up."
- BAD key_facts: "Texture Surprise activates and Bungee Gum reacts." with no plain-English explanation of why that matters.
"""
    elif channel_id == 25:
        channel_diversity_block = """

NATURE RECEIPTS PREMISE RULES (CRITICAL):
- Stop defaulting to the same title skeleton: "[animal] was the size of a skyscraper and discovered a city/store/highway."
- In this batch, use 5 DIFFERENT lead animals and at least 4 DIFFERENT premise engines.
- At most ONE giant-size concept in the batch.
- At most ONE "discovers a generic human place/system" concept in the batch. "discovers downtown / a city / a grocery store / a highway / taxes / rush hour" is overused.
- Prefer SPECIFIC collisions over generic destinations. GOOD: one sunflower seed silo, an airport baggage belt, a luxury koi pond, a national cheese cave. BAD: "a city", "downtown", "the neighborhood", "rush hour."
- Make the animal's REAL instinct the reason the scenario is funny. A raccoon should steal and pry things open. A penguin should slide, huddle, or panic in heat. An otter should hoard, juggle, or obsess over one object.
- Mix premise families:
  1. habitat inversion
  2. predator/prey reversal
  3. impossible power-up or physical trait
  4. human system collision (government, airports, shipping, sports, finance, etc.)
  5. swarm/pack takeover
  6. imprinting/obsession with one object or machine
- Mix PETS, WILD MAMMALS, BIRDS, OCEAN ANIMALS, REPTILES, and SMALL CHAOTIC CREATURES.
- Avoid dog/hamster/corgi/bunny-heavy batches unless one concept is clearly exceptional.
- Each idea should feel like a tiny disaster movie with one instantly visual image, one escalation ladder, and one replayable ending.
- A batch full of generic "animal + power + discovers place" ideas is a FAIL.
"""
    elif channel_id == 33:
        channel_diversity_block = """

THATS A MEME DIVERSITY RULES (CRITICAL):
- Do NOT build the whole batch around one tiny social setting.
- At most ONE concept in the batch may be about a parent borrowing your device / charger / phone.
- At most ONE concept may be about a door-knock / wave-back / social-acknowledgment misunderstanding.
- Mix premise families:
  1. family phone invasion
  2. payment or restaurant awkwardness
  3. mistaken social signal
  4. roommate / friend audacity
  5. tiny tech dependency panic
  6. public etiquette failure
- Every title should feel like a sentence someone instantly recognizes from real life and wants to send to a friend.
"""
    elif channel_id == 16:
        channel_diversity_block = """

CRABRAVESHORTS PLAYER-VOICE RULES (CRITICAL):
- These are GAME SKITS, not silent memes now. The humor should land because the dialogue sounds exactly like real players in VC or Discord.
- Use clipped, reactive gamer speech: "bro", "nah", "yo", "no shot", "you are trolling", "we are stacked", "split the loot", "full buy", "eco", "rotate", "one tap", "griefed", "free win".
- NEVER write polished sitcom dialogue or full formal sentences. If a real player would not say it mid-match, do not write it.
- Write the dialogue how a person would actually SAY it out loud, not how someone would TYPE it in all-chat. Bad: "JUNG COME JUNG COME HES LOW". Good: "Jung, come mid, he's one."
- Prefer fragments, interruptions, repeats, and half-finished thoughts over clean grammar. "yo wait wait" beats "please stop for a moment."
- Players should sound like they are reacting live while moving, not narrating the joke for the audience afterward.
- Recognition alone is NOT enough. "Everyone knows this situation" is only the setup. The concept still needs a sharper payoff: a humiliating reveal, insane audacity, immediate karma, or a line so specific it feels clip-worthy.
- Reject bland gamer pain. A title that is only "friend steals loot" or "teammate throws" is too generic unless the ending has a distinctive twist people would actually send to a friend.
- If the joke depends on a gameplay action, the visuals MUST show the action clearly. Do not replace the key beat with a random reaction close-up. The viewer should literally see the steal, gank, misplay, trap, escape, or grief happen in sequence.
- Use game-specific vocabulary naturally:
  * Minecraft: stacked, full diamond, split the loot, strip mine, griefed, spawn, chest, pick, redstone
  * Valorant: eco, full buy, one tap, rotate, spike, whiffed
  * League: gank, inting, diff, flash, ult, troll
- At least 3 concepts in the batch should center on two-player conflict, betrayal, blame, or instant voice-chat reaction.
- The funniest CrabRave concepts should feel like a real lobby meltdown someone clipped, not an outsider explaining a game joke.
- End on the funniest SPECIFIC line in the whole concept. The last scene should escalate or reframe the joke, not just restate the premise.
"""

    is_satisfying = channel_id in SATISFYING_CHANNELS
    is_character_dialogue = channel_id in CHARACTER_DIALOGUE_CHANNELS

    format_strategy_block = """FORMAT STRATEGY (choose the SIMPLEST version that still lands):
- "single_frame" = one instantly legible thesis image. Optional micro-aftermath only if it makes the joke clearer.
- "attack_result" = one clear setup beat and one clear consequence beat. Usually 2-3 scenes max.
- "mini_story" = 3-5 connected beats with a tiny escalation. Use this only when the premise truly benefits from sequence.
- "full_story" = avoid for no-narration shorts unless the concept absolutely breaks without it.
- Ask this FIRST: "If this were one strong image with one caption, would it still be compelling?" If yes, keep it simple.
- Do NOT inflate a simple joke into extra scenes just because AI can generate them.

SCENE COUNT BY STRATEGY:
- single_frame: 1 scene, or 2 only if the second is a tiny aftermath
- attack_result: 2-3 scenes
- mini_story: 3-5 scenes
- full_story: only if absolutely necessary, and still keep it short
"""

    # Resolve channel-specific art style up front so any branch's f-string can reference it.
    from apps.orchestrator.pipeline import get_channel_art_style

    _DEFAULT_STYLE = "Simple crude cartoon — thick wobbly outlines, flat bold colors, exaggerated round heads, simple bodies. Deliberately ugly and charming like a funny doodle. NOT noir, NOT graphic novel, NOT serious."
    _channel_style = get_channel_art_style(channel_id) if channel_id else _DEFAULT_STYLE
    art_style_field = f',\n    "art_style": "{_channel_style}"' if (is_character_dialogue or not is_satisfying) else ""
    system_mode_label = "native-dialogue" if is_character_dialogue else "no-narration"
    channel_visual_identity_block = ""
    if channel_id == 16:
        channel_visual_identity_block = """

GAME VISUAL IDENTITY RULES (CRITICAL):
- The image must prove the exact game world before the dialogue lands. Recognition cannot come from the title alone.
- For League of Legends concepts, EVERY scene must explicitly place the character on Summoner's Rift or a Summoner's Rift location and keep at least TWO recognizable MOBA cues in frame:
  cracked stone lane path, side brush, river edge, jungle entrance or camp, chunky defense turret base, doodled minimap corner, health bar, ping circles, recall ring.
- Even close-ups still need environment/HUD proof. A face floating on a blank or generic fantasy background is a FAIL.
- Use actual champion names when possible. If you do not name one, describe an unmistakable League champion silhouette or archetype: fox-mage tails, blind-monk red headband, wind swordsman topknot, bandaged mummy wraps, tiny scout cap. Never generic fantasy rogue/archer/hooded ranger.
- Translate League slang into literal visuals:
  * gank = jungler bursting from brush or jungle entrance onto a lane
  * under turret = champion on lane stones with a chunky stone turret base nearby
  * recall = blue recall ring under the champion
  * low = almost-empty doodled health bar above the champion
- BAD League prompts: "guy in a forest", "hooded ranger with a trophy", "generic fantasy ruins", "random campfire jungle"
- GOOD League prompt: "Close-up of Ahri on Summoner's Rift mid lane, cracked stone path and river brush behind her, low doodled health bar overhead, ping circles near a minimap corner."
"""

    if is_character_dialogue:
        style_guidance = f"""CHARACTER DIALOGUE SHORTS FORMAT — CHARACTERS SPEAK THEIR OWN LINES:

This is for "{channel_name}" ({niche}). The story needs context that pure visual comedy can't provide, so characters SPEAK short punchy dialogue lines. The video generator (Grok) will animate the characters talking with their own voices.

THE GOLDEN RULES:
1. CHARACTERS SPEAK — NO narrator, NO TTS voiceover. Each scene has ONE character who says a short line of dialogue. The dialogue goes in the video_prompt so Grok generates the character actually saying it.
2. ONE SPEAKER PER SCENE — Grok handles voices best when only one character is talking at a time. Silent background characters are allowed when the gameplay beat needs them.
3. SHORT PUNCHY LINES — Each character says 3-10 words max. "Yeah, he's guilty." not "I would like to testify that the defendant is in fact guilty of the crime." Short lines sound natural, long lines sound robotic.
4. THE DIALOGUE IS THE COMEDY — Lines should be funny, absurd, or shocking on their own. Casual tone like someone talking to a friend, not a script being read.
5. SHOW DON'T TELL — If a character goes to prison, show them being dragged away. Don't skip to the next location with a hard cut.

ART STYLE: {_channel_style}
This style should stay entertaining and visually readable, not stiff or overcomplicated.
{channel_visual_identity_block}

SCENE FLOW IS CRITICAL:
- Each scene must visually connect to the next — the viewer must understand what changed
- If a character moves locations, show the transition (getting dragged away, walking up to a door)
- NEVER jump between unrelated scenes with a hard cut
- The story should be followable even on mute from the visuals alone

DIALOGUE STYLE:
- Casual and reactive: "Bro what?" not "I cannot believe this"
- Prefer broken-up real speech over complete polished sentences. Fragments, overlap, and repeating a word are good when it sounds human.
- Never write typed gamer shorthand in the spoken line. Use commas, contractions, and normal speech rhythm so the model says it like a person.
- Characters react to what just happened: disbelief, smugness, devastation
- The PUNCHLINE is always the last line of dialogue — it should subvert expectations
- Absurd specific details make it funnier: "eating HIS limited edition hot cheetos" not "eating his food"

{channel_diversity_block}

PROVEN PATTERNS:
1. Betrayal → escalation → the betrayer acts like nothing happened (punchline is the audacity)
2. Character confidently does something → instant spectacular consequence → deadpan reaction
3. Two characters in conflict → one wins in the most absurd way possible
4. Setup everyone expects → twist nobody saw coming → character reacts to the twist

WHAT DOESN'T WORK:
- Narrator voiceover (sounds robotic from TTS, makes fictional stories feel like they're pretending to be real)
- Text or speech bubbles (excludes non-English speakers, less engaging than hearing characters talk)
- Serious tone on comedy content
- Long dialogue lines (Grok makes them sound unnatural)
- Hard cuts between locations with no transition scene
- Played-out concepts everyone has seen

CHANNEL CONTEXT: This is for "{channel_name}" ({niche}). Every concept must fit this channel's world and niche."""

        scene_format = f"""Each scene needs:
- "image_prompt": Start with "{_channel_style}". Keep ONE clearly dominant speaker in the foreground, but silent background players/enemies/props are allowed when they make the joke readable. Use the widest framing needed to show the actual beat; not every scene should be a face-only close-up. The background still needs enough specific game-world detail to instantly prove the franchise. If the concept is League of Legends, literally say "Summoner's Rift", "lane", "river brush", "jungle entrance", "stone turret base", "minimap corner", "health bar", etc. Add "One speaking character in the foreground. Background characters allowed as silent silhouettes. NO text anywhere." at the end.
  GOOD: "Simple crude cartoon... Ahri in the foreground on Summoner's Rift mid lane, cracked stone path and river brush behind her, low doodled health bar overhead, enemy silhouette barely alive in the distance. One speaking character in the foreground. Background characters allowed as silent silhouettes. NO text anywhere."
  GOOD: "Simple crude cartoon... Lee Sin bursting from river brush onto mid lane, Ahri and the low enemy visible as tiny background silhouettes, kill-feed icons popping near the lane. One speaking character in the foreground. Background characters allowed as silent silhouettes. NO text anywhere."
  BAD: "Simple crude cartoon... Close-up of a worried mage in a forest. One character only. NO text anywhere."
- "video_prompt": Describe what the character DOES and SAYS. The dialogue must be written naturally in the prompt so Grok generates the character speaking it. Also include sound effects.
  GOOD: "Guy leans forward into the microphone smugly and says yeah he is guilty, shrugs his shoulders. Courtroom murmur, dramatic dun dun sound."
  GOOD: "Guy slams his hands on the table and yells but you are my best friend, tears fly off his face. Table slam, crowd gasps."
  GOOD: "Guy sips his coffee, raises one eyebrow and says can I help you in a confused annoyed tone. Coffee sip, dead silence, cricket chirp."
  GOOD: "Minecraft guy panic-jumps and blurts yo wait wait where'd the stack go, voice cracking mid-sentence. Pickaxe clank, inventory rustle, cave echo."
  GOOD: "Mid laner spam-pings toward river brush and blurts jung, come mid, he's one, hurry. Ping spam, spell crackle, minion chatter."
  BAD: "Camera slowly zooms out" (boring — nothing moves)
  BAD: "Guy looks sad" (no dialogue, no physical action)
  BAD: "Player keeps mining while dramatic music plays." (still mute, still not a dialogue scene)
  BAD: "Player screams JUNG COME JUNG COME HES LOW." (typed shorthand, sounds robotic when voiced)
  RULE: One character speaks per scene. Keep dialogue under 10 words. Describe their physical reaction while speaking.
- "duration": 3-4 seconds per scene. Use as few scenes as the chosen format_strategy needs. Total video 12-16 seconds, 5 scenes max."""
    elif is_satisfying:
        style_guidance = """SATISFYING VIDEO RULES:
- These videos should make viewers say "wait... is that real? That's TOO perfect." The goal is IMPOSSIBLE PRECISION that makes people question if it's AI or real.
- Pure visual dopamine. NO text. NO voiceover. Just one mesmerizing action.
- 1 SCENE only. One continuous shot. One camera angle.

WHAT ACTUALLY GOES VIRAL (aim for these):
- EXTREME restoration: Something SO disgustingly filthy you can't believe it got that bad — years of black grime, rust, decay — then it gets restored to IMPOSSIBLY perfect condition. The shock of the before + the perfection of the after = rewatch.
- Impossible precision: a machine cutting with atomic-level accuracy, a perfect geometric pattern emerging from chaos, inhuman symmetry
- Surreal materials: liquid metal forming perfect shapes, mercury pooling into impossible geometry, glass bending like liquid
- Physics-defying: objects balanced in ways that shouldn't work, liquids moving against gravity, impossible perfect fits
- Extreme before/after: the WORSE the before, the better. A pool so green it looks like a swamp → crystal clear. A car so rusted you can't see the color → showroom mirror finish.

THE FORMULA: Make the viewer's jaw drop TWICE — once at how bad it is, once at how perfect it becomes. They HAVE to rewatch it.

ART STYLE: Photorealistic but SURREAL. The scene should look real enough to question, but the perfection should feel impossible.

FORMAT NOTE:
- Satisfying concepts should almost always be "single_frame". One mesmerizing transformation is usually enough.

AI VIDEO GENERATOR LIMITATIONS:
- The generator can do ONE simple motion in 5-10 seconds.
- The image prompt shows the STARTING STATE. The video prompt describes ONE transformation.
- Keep the motion simple but the result mind-blowing."""

        scene_format = """Each scene needs:
- "image_prompt": Photorealistic starting state — show the object/material BEFORE the satisfying moment.
- "video_prompt": ONE simple motion that creates an impossibly satisfying result.
  GOOD: "the perfectly spherical ball of liquid mercury slowly splits into two identical halves, each reforming into a smaller perfect sphere"
  BAD: "soap is applied to a dirty surface and scrubbed clean" (boring, mundane)
- "duration": 8-10 seconds. Total video 8-12 seconds, 15 max."""
    else:
        style_guidance = f"""VISUAL SLAPSTICK SHORTS FORMAT — STANDARDIZED FOR ALL CHANNELS:

This is for "{channel_name}" ({niche}). The TOPIC comes from this channel's niche, but the FORMAT is universal.

THE GOLDEN RULES:
1. PHYSICAL COMEDY OVER TEXT — NO text on screen, NO speech bubbles, NO narration, NO voiceover. The humor is in what characters DO, not what they say. The action IS the story.
2. UNIVERSAL HUMOR — Must work in Tokyo and Texas. No language, no cultural context needed. A character slipping, getting hit, reacting dramatically — everyone gets it.
3. INSTANT CLARITY — From the very first frame, the viewer knows what's happening. No backstory, no setup to decode. Zero effort to understand.
4. EXAGGERATED REACTIONS — The facial expression IS the punchline. Huge eyes, jaw on the floor, soul leaving body.
5. LOOPING POTENTIAL — The punchline should make viewers want to rewatch. The best shorts get 100%+ average view duration from loops.

ART STYLE: Simple crude cartoon — thick wobbly outlines, flat bold colors, exaggerated round heads, simple bodies. Deliberately ugly and charming. NOT polished, NOT detailed, NOT AI-looking. Same character must be visually consistent across ALL scenes (same clothes, same hair, same colors).

SOUND EFFECTS ARE HALF THE COMEDY:
- Every video_prompt MUST include specific sound effects
- Sounds tell the viewer how to feel: triumphant fanfare for success, sad trombone for failure, explosion for chaos, crickets for awkward silence
- Be SPECIFIC: "a quiet sad squeaky fart noise" not "funny sound"

TRANSITIONS BETWEEN SCENES ARE CRITICAL:
- NEVER hard-cut between scenes. The viewer needs to understand what changed.
- Use TRANSITION SCENES to show time passing: a clock spinning, sun/moon cycling, calendar pages flying, seasons changing on a tree
- If something gets destroyed, SHOW IT BEING DESTROYED in its own scene — don't jump from "tree exists" to "crater exists"
- Each scene must flow visually into the next so the viewer never loses track of the story

SCENE STRUCTURE:
- Use the fewest scenes possible. Under 15 seconds total.
- single_frame = one dominant image, optional tiny aftermath
- attack_result = setup → consequence
- mini_story = setup → escalation → punchline
- Each main scene: 3-5 seconds
- Each transition scene: 2 seconds only when the viewer genuinely needs that bridge
- Hold the PUNCHLINE or CONSEQUENCE scene longest — give viewers time to process and laugh

PROVEN PATTERNS:
1. Plant/build something → time passes → it grows huge → it gets destroyed instantly (the bigger the buildup, the funnier the collapse)
2. Character tries something confidently → instant spectacular failure → aftermath of total devastation
3. Character A causes chaos → patient observer Character B watches calmly → role reversal
4. Escalating attempts: try → fail small → try harder → fail bigger → try hardest → fail catastrophically

WHAT DOESN'T WORK:
- Text or speech bubbles (viewers in other countries can't read it)
- Slow zooms with no character movement (boring, feels like a slideshow)
- Played-out jokes everyone has seen (payday → bills, alarm clocks, Monday morning)
- Subtle animation — needs BIG DRAMATIC physical movement
- Hard cuts between unrelated scenes with no visual transition

CHARACTERS MUST BE SPECIFIC:
- Not "a person" but "a skinny guy in a green hoodie"
- Same character in every scene — same outfit, same features
- Exaggerated facial expressions that read at thumbnail size"""

        scene_format = f"""Each scene needs:
- "image_prompt": Start with the channel art style. Then describe the scene with EXPLICIT spatial detail:
  1. CAMERA ANGLE: Where is the camera? "Close-up of face", "Wide shot from behind", "Side view at eye level"
  2. CHARACTER POSITION: Where exactly is each character? "Standing left of frame", "Sitting at a desk center frame", "Two characters face-to-face"
  3. SETTING: Specific background — not just "a room" but "a modern gym with chrome weight machines and mirrors"
  4. CHARACTER DESCRIPTION: Same character in every scene — same outfit, same features, same colors. Be specific: "muscular man with red headband and white tank top"
  5. ACTION STATE: What is happening RIGHT NOW — "mid-swing with fist connecting", "sitting cross-legged eating"
  6. End every prompt with "NO text anywhere."

  BAD: "Guy at the gym" (vague — every image will look different)
  GOOD: "Close-up side view. A muscular man with a red headband and white tank top grips a weight machine handle. His veins bulge. Behind him a modern gym with chrome machines and mirrors. NO text anywhere."

- "video_prompt": Describe CHARACTER MOVEMENT — what the character physically does. Arms, legs, body, facial expressions. NEVER say "camera zooms" or "camera pulls back." Also include specific sound effects.
  GOOD: "Guy jumps up celebrating with fists pumping, coins rain from tree. Triumphant fanfare, coins clattering."
  BAD: "Camera slowly zooms out" (boring — nothing moves)
  RULE: image_prompt = the STARTING state. video_prompt = what PHYSICALLY HAPPENS. The bigger the movement, the better.
- "duration": 2-5 seconds per scene. Total video should match the chosen format_strategy and stay under 15 seconds.

CHANNEL ART STYLE: {_channel_style}
Every image_prompt MUST start with this art style description."""

    system = f"""You create viral {system_mode_label} YouTube Shorts for "{channel_name}" — {niche}.

{style_guidance}

{format_strategy_block}

{scene_format}

OUTPUT — return a JSON array of {count} complete concepts:
[
  {{
    "title": "ALL CAPS TITLE",
    "brief": "One sentence — why will someone watch/share this",
    "format_strategy": "single_frame|attack_result|mini_story|full_story",
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
    "format_version": 2{art_style_field}
  }}
]

Return ONLY valid JSON, no markdown."""

    user = f"""Create {count} viral no-narration Shorts for "{channel_name}" ({niche}).

{trending_block}
{past_block}
{channel_diversity_block}

Each concept must be complete with all scenes ready to generate. Make them scroll-stopping."""

    return system, user
