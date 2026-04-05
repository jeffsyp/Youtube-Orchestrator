"""Prompts for trend research agent — analyzes what's performing well and feeds insights into concept generation."""


def build_trend_research_prompt(channel_name: str, channel_niche: str, past_titles: list[str],
                                 past_reviews: list[dict], channel_rules: str = "") -> tuple[str, str]:
    """Build a prompt that analyzes past performance and generates fresh concept directions.

    Args:
        channel_name: Channel name.
        channel_niche: Channel niche description.
        past_titles: Titles of previously made videos.
        past_reviews: Gemini review results from past videos (scores, issues, suggestions).

    Returns:
        (system, user) prompt tuple.
    """
    # Build performance summary from reviews
    review_summary = ""
    if past_reviews:
        scored = [r for r in past_reviews if r.get("overall_score", 0) > 0]
        if scored:
            avg_score = sum(r["overall_score"] for r in scored) / len(scored)
            best = max(scored, key=lambda r: r.get("overall_score", 0))
            worst = min(scored, key=lambda r: r.get("overall_score", 0))

            review_summary = f"""
PAST PERFORMANCE (from AI video review):
- Average score: {avg_score:.1f}/10 across {len(scored)} videos
- Best video scored {best.get('overall_score')}/10: {best.get('summary', '')}
- Worst video scored {worst.get('overall_score')}/10: {worst.get('top_issue', '')}

RECURRING ISSUES FROM REVIEWS:
"""
            # Collect all suggestions
            all_issues = [r.get("top_issue", "") for r in scored if r.get("top_issue")]
            for issue in all_issues[-5:]:
                review_summary += f"- {issue}\n"

            all_suggestions = []
            for r in scored:
                for key in ["prompt_suggestions", "suggestions", "concept_suggestions"]:
                    if key in r and isinstance(r[key], list):
                        all_suggestions.extend(r[key])
            if all_suggestions:
                review_summary += "\nPAST SUGGESTIONS TO INCORPORATE:\n"
                for s in all_suggestions[-5:]:
                    review_summary += f"- {s}\n"

    past_text = ""
    if past_titles:
        past_text = "\nPREVIOUS VIDEOS (avoid repeating):\n" + "\n".join(f"- {t}" for t in past_titles[-20:])

    system = f"""You are a creative director for "{channel_name}" — a YouTube Shorts channel focused on {channel_niche}.

Your job is to generate FRESH CONCEPT DIRECTIONS that will perform well. You learn from:
1. What worked before (high-scoring videos)
2. What didn't work (low-scoring videos and their issues)
3. Current trends in the Shorts space
4. What the AI video model (Sora 2) is good and bad at generating

You must EVOLVE — don't just repeat the same formula. Push into new territory while staying on-brand.
Each batch of concepts should explore at least 2-3 DIFFERENT themes or styles.

SORA 2 CAPABILITIES (design around these):
GOOD AT: fluid dynamics, nature scenes, landscapes, atmospheric lighting, color, animals in motion, large-scale environments, smooth transformations, architectural scenes
BAD AT: precise hand/tool interactions, text rendering, exact physics (cutting, splitting), detailed facial expressions, mechanical actions

{f"CHANNEL-SPECIFIC RULES (MUST FOLLOW):{chr(10)}{channel_rules}" if channel_rules else ""}"""

    user = f"""Generate 5 fresh, evolved concept directions for {channel_name}.
{review_summary}
{past_text}

Based on past performance, LEAN INTO what scored well and AVOID what scored poorly.
Explore at least 3 different themes/styles — don't just repeat the top formula.

SCORING — BE EXTREMELY CRITICAL:
You are the gatekeeper before we spend expensive Sora credits. A score of 8+ means this concept would genuinely stop someone scrolling. Most concepts should score 5-7. Only truly exceptional concepts deserve 8+.

Ask yourself for each concept:
- Would I actually stop scrolling to watch this? Would I share it? If not, score below 7.
- A weak hook, subtle transformation, or boring subject = automatic score below 7.
- Has this been done to death already? Unoriginal = score below 7 unless there's a genuinely fresh twist.
- Is this CONCRETE enough that Sora will nail it? Vague or abstract = score below 7.

SCORE GUIDE:
- 9-10: Truly exceptional — viral potential, never been done, incredible hook + payoff
- 8-8.9: Very strong — scroll-stopping, dramatic, worth the Sora cost
- 6-7.9: Decent but not strong enough to justify expensive AI generation
- 1-5.9: Weak — skip it

Do NOT inflate scores. If every concept gets 8+, you are wasting money. Be the harsh filter.

Return ONLY valid JSON, no markdown:
{{
  "insights": "One paragraph analyzing what's working and what needs to change",
  "concepts": [
    {{
      "title": "Under 60 chars",
      "theme": "What category/style this explores",
      "why": "Why this concept should work based on past data",
      "sora_prompts": ["Detailed prompt 1...", "Detailed prompt 2...", "Detailed prompt 3..."],
      "caption": "Short caption",
      "description": "YouTube description with hashtags",
      "tags": ["tag1", "tag2", "tag3", "tag4", "Shorts"],
      "score": 7.2
    }}
  ]
}}

NEVER include emojis in titles, captions, or descriptions."""
    return system, user


def build_youtube_trend_scan_prompt(niche: str) -> str:
    """Build a prompt for scanning YouTube trending content in a niche.

    Used with web search to find what's currently trending.
    """
    return f"""Search for the top trending YouTube Shorts in the "{niche}" niche from the past week.

I need:
1. What types of content are getting the most views right now?
2. What visual styles/aesthetics are trending?
3. What captions/hooks are performing well?
4. Any new formats or trends emerging?
5. What's oversaturated/played out?

Focus on actionable insights for an AI-generated content channel."""
