from datetime import datetime

from pydantic import BaseModel


class CandidateVideo(BaseModel):
    video_id: str
    title: str
    channel_name: str
    channel_subscribers: int
    views: int
    published_at: datetime
    duration_seconds: int
    tags: list[str] = []
    breakout_score: float = 0.0


class TemplatePattern(BaseModel):
    pattern_name: str
    description: str
    hook_style: str
    structure: list[str]
    source_video_ids: list[str]
