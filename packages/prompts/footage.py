"""Prompts for generating stock footage search queries matched to script content."""


def generate_footage_queries_prompt(script_content: str, duration_seconds: float, clip_duration: int = 6) -> tuple[str, str]:
    """Return (system, user) prompts for generating footage search queries."""
    num_clips = int(duration_seconds / clip_duration) + 2
    words_per_clip = int(len(script_content.split()) / num_clips)

    system = (
        "You are a video editor selecting stock footage for a YouTube narration video. "
        "For each segment of the script, you pick a concrete, filmable scene that visually "
        "reinforces what the narrator is saying. You think in terms of what a stock footage "
        "site like Pexels would actually have available."
    )

    user = f"""Read this script and generate one stock footage search query for every ~{words_per_clip} words.
Each query will be used to find a {clip_duration}-second stock video clip from Pexels.

SCRIPT:
{script_content}

TOTAL CLIPS NEEDED: {num_clips}
CLIP DURATION: {clip_duration} seconds each

RULES:
- Generate exactly {num_clips} search queries
- Each query should be 2-4 words describing a REAL, FILMABLE scene
- Match the footage to what's being discussed at that point in the script
- Think about what Pexels actually has: real footage, not CGI or animations
- Good examples: "military jet takeoff", "scientist microscope lab", "server room lights"
- Bad examples: "hypersonic missile trajectory simulation", "quantum computing visualization"
- Vary the queries — don't repeat the same search twice
- For abstract concepts, find a visual metaphor (e.g., "speed" → "fast car highway", "danger" → "warning lights red")

Return ONLY a JSON array of strings, no markdown:
["query one", "query two", "query three", ...]"""

    return system, user
