"""Prompts for Gemini video review — watches rendered Shorts and critiques them."""


def build_synthzoo_review_prompt(concept: dict) -> str:
    """Build a review prompt for a Synth Meow Short.

    Args:
        concept: The concept dict with title, caption, sora_prompts.
    """
    title = concept.get("title", "Unknown")
    caption = concept.get("caption", "")
    sora_prompts = concept.get("sora_prompts", [])

    prompts_text = ""
    for i, p in enumerate(sora_prompts, 1):
        prompts_text += f"\nClip {i}: {p}"

    return f"""You are a YouTube Shorts quality reviewer AND a production pipeline consultant. Watch this AI-generated animal video and give two things: a critique AND specific suggestions to improve the pipeline that made it.

CONTEXT — HOW THIS VIDEO WAS MADE:
1. An LLM (Claude) generated the concept: title, 3 Sora video prompts, and a caption
2. Each Sora prompt was sent to OpenAI's Sora 2 separately to generate an 8-second vertical video clip
3. The 3 clips were concatenated with FFmpeg, background music was mixed in, and the caption was burned in as a subtitle
4. The clips are generated independently — Sora has no knowledge of the other clips

CONCEPT:
Title: {title}
Caption: {caption}
Sora prompts used:{prompts_text}

PART 1 — REVIEW (score each 1-10):

1. **HOOK (first 2 seconds)**: Does the video grab attention immediately? Is there action from frame 1, or is it a boring establishing shot?

2. **VISUAL CONTINUITY**: Do the clips feel like they belong in the same video? Same animal appearance, environment, lighting across cuts? Or do they look like different videos spliced together?

3. **STORY ARC**: Is there a clear progression — escalation and payoff? Does the video build to something? Would a viewer watch to the end?

4. **VISUAL QUALITY**: How good does the AI generation look? Any glitches, distortions, or uncanny-valley moments?

5. **CAPTION FIT**: Does the caption "{caption}" work with what's actually shown?

PART 2 — PIPELINE IMPROVEMENTS:
Based on what you saw go wrong (or right), suggest specific, actionable changes to the production pipeline. Think about:

- **Prompt engineering**: How should the Sora prompts be written differently to get better results? Be specific — what words/phrases to add or remove, what details to emphasize.
- **Continuity tricks**: Since each clip is generated independently, what can we add to the prompts to make clips match better? (e.g., specific color descriptions, camera angles, consistent prop details)
- **Concept selection**: What types of concepts/scenarios tend to work well with AI video generation, and which should be avoided?
- **Rendering/editing**: Any changes to how clips are assembled? (transitions, speed ramps, color grading, timing)
- **Caption/text**: How could the caption or text overlays be improved?

Return your review as JSON (no markdown):
{{
  "hook_score": 7,
  "hook_note": "Brief explanation",
  "continuity_score": 6,
  "continuity_note": "Brief explanation",
  "story_score": 8,
  "story_note": "Brief explanation",
  "quality_score": 7,
  "quality_note": "Brief explanation",
  "caption_score": 8,
  "caption_note": "Brief explanation",
  "overall_score": 7.2,
  "publish_recommendation": "yes/no/maybe",
  "top_issue": "The single biggest problem",
  "summary": "One sentence overall verdict",
  "prompt_suggestions": [
    "Specific suggestion for improving Sora prompts — e.g. 'Add exact hex color codes for the animal to maintain appearance across clips'",
    "Another specific suggestion"
  ],
  "continuity_suggestions": [
    "Specific suggestion for improving clip-to-clip consistency"
  ],
  "concept_suggestions": [
    "What types of concepts to prefer or avoid based on what you saw"
  ],
  "rendering_suggestions": [
    "Specific suggestion for the FFmpeg editing/compositing step"
  ],
  "general_suggestions": [
    "Any other pipeline improvement ideas"
  ]
}}"""
