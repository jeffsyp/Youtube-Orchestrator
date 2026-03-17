"""Prompts for Gemini video review — strict entertainment quality standard."""


def build_review_prompt(concept: dict, channel_name: str = "", channel_niche: str = "") -> str:
    """Build a strict review prompt for any channel's video.

    The review must judge ENTERTAINMENT VALUE, not just visual quality.
    A pretty video that's boring should score LOW.
    """
    title = concept.get("title", "Unknown")
    caption = concept.get("caption", "")

    return f"""You are a HARSH YouTube Shorts critic. Your job is to decide if this video is good enough to publish. Be brutally honest — most AI-generated videos are mediocre and should NOT be published.

TITLE: {title}
CHANNEL: {channel_name} ({channel_niche})
CAPTION: {caption}

Judge this video the way a real viewer scrolling YouTube Shorts would:

1. **SCROLL TEST (most important, score 1-10)**: If you were scrolling YouTube Shorts and this appeared, would you STOP scrolling in the first 2 seconds? Or would you swipe past? Be honest — most videos fail this test. A score of 7+ means "yes, I'd actually stop."

2. **REWATCH VALUE (score 1-10)**: After watching once, would you watch it again? Would you send it to a friend? A 7+ means "yes, I'd rewatch or share this."

3. **PROMISE DELIVERY (score 1-10)**: Does the video actually deliver what the title "{title}" promises? If the title says "house gets built brick by brick" but the video just shows branches moving, that's a 1/10. The video must MATCH its title.

4. **VISUAL QUALITY (score 1-10)**: Does it look good? Sharp, well-lit, no obvious AI glitches or distortions?

5. **ENTERTAINMENT (score 1-10)**: Is this actually interesting, funny, beautiful, satisfying, or compelling in any way? Or is it just... there? Pretty but boring = low score.

SCORING GUIDE — BE STRICT:
- 9-10: Exceptional — would go viral, people share this
- 7-8: Good — worth publishing, people would watch to the end
- 5-6: Mediocre — technically fine but nobody would care
- 3-4: Bad — boring, confusing, or doesn't deliver on concept
- 1-2: Terrible — unwatchable, would damage the channel

Most AI videos are 4-6. Only recommend publish for 7+.

Return JSON (no markdown):
{{
  "scroll_test_score": 5,
  "scroll_test_note": "Would I stop scrolling? Why or why not?",
  "rewatch_score": 4,
  "rewatch_note": "Would I watch again or share?",
  "promise_score": 6,
  "promise_note": "Does it deliver what the title promises?",
  "quality_score": 7,
  "quality_note": "Visual quality assessment",
  "entertainment_score": 5,
  "entertainment_note": "Is this actually interesting/funny/beautiful/satisfying?",
  "overall_score": 5.4,
  "publish_recommendation": "no",
  "top_issue": "The single biggest reason this video fails or succeeds",
  "summary": "One sentence brutal honest verdict",
  "suggestions": ["How to make the next video better"]
}}"""


# Keep backward compatibility — old channel-specific functions redirect to the universal one
def build_synthzoo_review_prompt(concept: dict) -> str:
    return build_review_prompt(concept, "Synth Meow", "AI-generated animal videos")
