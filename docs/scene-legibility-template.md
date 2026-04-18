## Scene Legibility Template

Use this when writing or reviewing any image/video beat for Shorts.

### Core Rule
Reduce every beat to one visual sentence a stranger would understand on mute.

If the sentence contains `and`, it is usually two beats.

### What A Strong Frame Needs
1. One dominant subject
2. One dominant action
3. One proof detail or prop
4. One clear location
5. Supporting characters only if they clarify the idea

### For Image-To-Video
If the model animates from a source image, the source image should usually be the strongest pre-impact setup, not the completed payoff.

- Too early: boring setup with no tension
- Too late: completed aftermath with nothing left to animate
- Best: half a second before the impact, with the action already clearly starting

### Image Prompt Order
Write image prompts in this order:
1. Framing
2. Main subject
3. Action state
4. Proof detail
5. Supporting characters
6. Location

Example:

```text
Wide side view. Zoro from One Piece in the left foreground raises all three swords for a slash. Killua stands several feet away bracing, clearly separated. Cracked arena stone underfoot. Tournament arena background. NO text anywhere.
```

### Grok-Safe Staging
- Multiple characters is fine.
- Direct contact is usually bad.
- Prefer attacker/setup beat first.
- Then show the victim/result beat separately.

Bad:

```text
Zoro hits Killua and knocks him into the wall while debris explodes.
```

Better:

```text
1. Zoro surges forward with blades raised while Killua braces several feet away.
2. Killua alone crashes into rubble and slides down the wall.
```

### Review Questions
1. What is the one thing the viewer should understand from this frame?
2. Would that still be obvious with no narration?
3. Is the action literal, not implied?
4. Is there one dominant subject, not split focus?
5. Is the proof detail visible at a glance?
6. Would this be easier to understand as two beats?

### Best Format By Idea
- `single_frame`: one thesis image, optional tiny aftermath
- `attack_result`: setup beat, then consequence beat
- `mini_story`: 3-5 connected beats
- `full_story`: only if the premise truly needs a longer sequence
