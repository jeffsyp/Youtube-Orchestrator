# Channel Strategy Matrix

This is the working source of truth for how each channel should behave after the Veo migration audit.

## Shared Rules

- Default to `Grok` for cartoon, anime, meme, dialogue-timed, text-heavy, or IP-sensitive channels.
- Default to `Veo` only when the channel is cinematic, photoreal, motion-led, and not dependent on permissive IP handling.
- Use `hybrid` when the channel wants better motion realism but still depends on deterministic still-image anchors, readable staging, or strict review control.
- `builder_pitch` means the concept generator should create pitch-level drafts and let the custom builder write the final narration.
- `cold_open` means the hook is the intro; do not add a separate title card or bumper.

## Matrix

| ID | Channel | Draft Mode | Core Lane | Provider | Audio | Intro | Anchor | Primary Formats | Proven Concept Families |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 13 | Munchlax Lore | `builder_pitch` | photoreal Pokemon-in-real-life escalation | `hybrid` | `voiceover` | `teaser_intro` | `none` | `attack_result`, `mini_story` | mundane real-world collision, disaster escalation, public panic, news takeover, power-move punchline |
| 14 | ToonGunk | `dialogue_short` | retro cartoon and animation lore | `hybrid` | `native_dialogue` | `cold_open` | `none` | `attack_result`, `mini_story` | cartoon physics, production weirdness, dub lore, network mysteries, rivalry history |
| 15 | Very Clean Very Good | `satisfying` | impossible precision satisfaction | `grok` | `native_sfx` | `cold_open` | `none` | `single_frame`, `attack_result` | restoration, sorting, packing, symmetry, micro-precision setups |
| 16 | CrabRaveShorts | `no_narration` | crude game meme slapstick | `grok` | `native_sfx` | `cold_open` | `none` | `single_frame`, `attack_result` | instant karma, setup-fail, celebration collapse, ranked-game misery, game-character humiliation |
| 17 | Smooth Brain Academy | `educational_short` | crayon body science and perception myths | `grok` | `voiceover` | `cold_open` | `recurring_host` | `single_frame`, `attack_result`, `mini_story` | hiccups/yawns/sneezes, sleep glitches, immune battles, earth-space myths, weird body facts |
| 18 | Skeletorinio | `builder_pitch` | mythic what-if power escalation | `hybrid` | `voiceover` | `cold_open` | `recurring_character` | `attack_result`, `mini_story` | power progression, boss-fight takeovers, era portal chaos, god-domain flex, raid-boss ascension |
| 19 | SpookLand | `builder_pitch` | narrated horror scenario escalation | `grok` | `voiceover` | `cold_open` | `none` | `attack_result`, `mini_story` | cursed-location encounters, survival mistakes, reveal-driven hauntings, entity rules, escalating panic |
| 20 | ColdCaseCartoons | `short_script` | narrated true-crime betrayals and case twists | `grok` | `voiceover` | `cold_open` | `none` | `attack_result`, `mini_story` | search-party betrayal, poisoning clues, insurance motive, escaped-victim reversals, forensic breakthrough |
| 21 | One on Ones For Fun | `builder_pitch` | cross-franchise verdict battles | `grok` | `voiceover` | `matchup_card` | `none` | `attack_result`, `mini_story` | matchup verdicts, stat mismatch, signature-move counters, upset wins, final blow declarations |
| 22 | Deity Drama | `builder_pitch` | mythic beings colliding with modern systems | `hybrid` | `voiceover` | `cold_open` | `none` | `attack_result`, `mini_story` | god in modern life, divine punishment, mythic flex, cosmic overreaction, mortal humiliation |
| 23 | Techognizer | `educational_short` | AI and software systems explained simply | `grok` | `voiceover` | `cold_open` | `recurring_host` | `mini_story`, `full_story` | how it works, why it fails, tool comparisons, hidden algorithms, infra and security explainers |
| 24 | Blanket Fort Cartoons | `kids` | cozy preschool animal slice-of-life | `hybrid` | `voiceover` | `cold_open` | `recurring_pair` | `mini_story` | bedtime mishaps, backyard play, teamwork, weather surprises, pretend-play rescue errands |
| 25 | Nature Receipts | `builder_pitch` | wildlife anomaly documentary | `grok` | `voiceover` | `cold_open` | `none` | `attack_result`, `mini_story` | habitat inversion, predator reversal, impossible trait, system collision, swarm takeover |
| 26 | Hardcore Ranked | `builder_pitch` | measurable experiment ladders | `hybrid` | `voiceover` | `teaser_intro` | `recurring_character` | `mini_story`, `full_story` | depth, time, survival, pressure, distance, repeated test rig comparisons |
| 27 | Deep We Go | `builder_pitch` | body-horror science descent with the glass person | `hybrid` | `voiceover` | `cold_open` | `recurring_character` | `mini_story`, `full_story` | pressure, depth, heat, poison, collapse, survival-threshold breakdowns |
| 28 | NightNightShorts | `builder_pitch` | anime canon-collision what-ifs | `grok` | `voiceover` | `cold_open` | `none` | `attack_result`, `mini_story` | outsider in another verse, exam disruption, villain encounter, overpowered flex, reaction collapse |
| 29 | Globe Thoughts | `weekly_recap` | geopolitics and world power shifts | `hybrid` | `voiceover` | `cold_open` | `recurring_host` | `mini_story`, `full_story` | breaking headlines, war and sanctions, elections, trade routes, country comparisons |
| 30 | Historic Ls | `builder_pitch` | history's biggest humiliations and blunders | `grok` | `voiceover` | `cold_open` | `none` | `attack_result`, `mini_story` | tactical disasters, vanity decisions, absurd miscalculations, failed flexes, public humiliation |
| 31 | Schmoney Facts | `builder_pitch` | money mechanics with visual proof | `grok` | `voiceover` | `teaser_intro` | `proof_props` | `attack_result`, `mini_story`, `full_story` | pricing tricks, rich-person operating costs, markup reveals, salary reality, weird cash systems |
| 32 | Mathematicious | `educational_short` | intuition-breaking math and probability | `grok` | `voiceover` | `cold_open` | `recurring_host` | `mini_story`, `full_story` | probability traps, paradoxes, infinity, fraud math, computer-number weirdness |
| 33 | Thats A Meme | `no_narration` | universal everyday micro-cringe | `grok` | `native_sfx` | `cold_open` | `none` | `single_frame`, `attack_result` | phone interruptions, door etiquette fails, payment awkwardness, mistaken signals, tiny tech dependency |
| 34 | Ctrl Z The Time | `weekly_recap` | builder-facing tech news rewind | `grok` | `voiceover` | `cold_open` | `none` | `mini_story`, `full_story` | security incidents, model launches, workflow changes, infrastructure bottlenecks, robotics and hardware shifts |

## Transition Priorities

1. Move all custom-builder channels onto `builder_pitch` draft generation so concepts stop arriving in the wrong format.
2. Centralize channel media policy in `channels/profiles.json` and resolve it through `packages/clients/channel_profiles.py`.
3. Make shared planning and review prompts provider-neutral before widening Veo usage.
4. Keep Veo focused on the cinematic lanes first: 18, 22, 24, 26, 27, and parts of 29.
5. Keep text-heavy and timing-heavy channels on Grok for now: 15, 16, 17, 20, 23, 32, 33, 34.

## Open Questions

- Whether 17 should stay native-dialogue for shorts or move fully to narrated explainers.
- Whether 29 should remain a recurring news channel or get a stronger evergreen geopolitical explainer lane.
- Whether 14 should keep native dialogue or eventually get a custom builder for more controlled pacing.
- When to expose Veo native audio operationally; the client supports it, but the orchestration layer does not yet use it.
