"""Prompts for Gemini video review — permissive post-Sora standard.

Clips are already generated and paid for. Rendering is cheap (local FFmpeg).
The user makes the final publish decision in the review queue, so let more
videos through with honest scores rather than blocking them here.
"""


def build_review_prompt(concept: dict, channel_name: str = "", channel_niche: str = "",
                        video_feedback: list[str] | None = None) -> str:
    """Build a strict review prompt for any channel's video.

    The review must judge ENTERTAINMENT VALUE, not just visual quality.
    A pretty video that's boring should score LOW.
    """
    title = concept.get("title", "Unknown")
    caption = concept.get("caption", "")

    feedback_section = ""
    if video_feedback:
        feedback_section = "\n\nUSER VIDEO FEEDBACK — the creator has given these specific notes about what they care about. Factor these into your review and mention whether the video addresses them:\n"
        feedback_section += "\n".join(f"- {fb}" for fb in video_feedback)

    return f"""You are an honest YouTube Shorts reviewer. Score the video fairly — the Sora clips are already generated and paid for, so your job is to give an accurate assessment, not to gatekeep. The user will make the final publish decision.
{feedback_section}

TITLE: {title}
CHANNEL: {channel_name} ({channel_niche})
CAPTION: {caption}

Judge this video the way a real viewer scrolling YouTube Shorts would:

1. **SCROLL TEST (most important, score 1-10)**: If you were scrolling YouTube Shorts and this appeared, would you STOP scrolling in the first 2 seconds? Or would you swipe past?

2. **REWATCH VALUE (score 1-10)**: After watching once, would you watch it again? Would you send it to a friend?

3. **PROMISE DELIVERY (score 1-10)**: Does the video actually deliver what the title "{title}" promises? If the title says "house gets built brick by brick" but the video just shows branches moving, that's a 1/10. The video must MATCH its title.

4. **VISUAL QUALITY (score 1-10)**: Does it look good? Sharp, well-lit, no obvious AI glitches or distortions?

5. **ENTERTAINMENT (score 1-10)**: Is this actually interesting, funny, beautiful, satisfying, or compelling in any way? Or is it just... there? Pretty but boring = low score.

SCORING GUIDE — BE FAIR AND HONEST:
- 9-10: Exceptional — would go viral, people actively share this.
- 8-8.9: Strong — genuinely impressive, people watch to the end and feel satisfied.
- 7-7.9: Good — solid content, worth publishing.
- 6-6.9: Decent — not amazing but passable, recommend publish and let the user decide.
- 5-5.9: Mediocre — on the fence, might still be worth uploading.
- 3-4.9: Bad — boring, confusing, or doesn't deliver on concept.
- 1-2.9: Terrible — unwatchable, would damage the channel.

Recommend "yes" for 6+, "maybe" for 5-5.9, "no" below 5.

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
  "summary": "One sentence honest verdict",
  "suggestions": ["How to make the next video better"]
}}"""
