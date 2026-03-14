from pydantic import BaseModel


class ChannelConfig(BaseModel):
    channel_id: int
    name: str
    niche: str
    search_terms: list[str]
    tone: str = "informative and engaging"
    scoring_weights: dict[str, float] = {
        "views_ratio": 0.4,
        "recency": 0.3,
        "topic_relevance": 0.3,
    }
