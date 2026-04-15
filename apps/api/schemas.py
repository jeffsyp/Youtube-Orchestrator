"""Pydantic v2 models for the YouTube Orchestrator API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# --- Channels ---


class ChannelStats(BaseModel):
    published: int = 0
    completed: int = 0
    failed: int = 0
    total: int = 0


class ChannelResponse(BaseModel):
    id: int
    name: str
    niche: str
    pipeline: str = "unified"
    description: str | None = None
    stats: ChannelStats = Field(default_factory=ChannelStats)


# --- Runs ---


class RunSummary(BaseModel):
    id: int
    channel_id: int
    channel_name: str
    content_type: str = "unified"
    status: str
    current_step: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    title: str | None = None
    review_score: float | None = None
    review_recommendation: str | None = None
    production_qa_verdict: str | None = None
    video_path: str | None = None
    thumbnail_path: str | None = None
    elapsed_seconds: int | None = None
    stalled: bool = False
    youtube_url: str | None = None
    youtube_privacy: str | None = None
    last_change: str | None = None


class AssetDetail(BaseModel):
    id: int
    asset_type: str
    content: str | None = None


class RunDetail(RunSummary):
    assets: list[AssetDetail] = Field(default_factory=list)


# --- Dashboard ---


class SystemCheck(BaseModel):
    name: str
    active: bool


class DashboardResponse(BaseModel):
    running_pipelines: list[RunSummary] = Field(default_factory=list)
    recent_runs: list[RunSummary] = Field(default_factory=list)
    channel_stats: list[ChannelResponse] = Field(default_factory=list)
    system_checks: list[SystemCheck] = Field(default_factory=list)
    today_stats: dict = Field(default_factory=dict)


# --- Actions ---


class ClipSpec(BaseModel):
    prompt: str
    narration: str = ""
    duration: int | None = None
    label: str = ""
    image_path: str | None = None
    image_url: str | None = None
    dialogue: list[str] = Field(default_factory=list)


class ExecuteConceptRequest(BaseModel):
    title: str
    channel_id: int
    visual_style: str = "cinematic photorealistic"
    clips: list[ClipSpec]
    caption: str = ""
    tags: list[str] = Field(default_factory=list)
    voice_id: str = "George"
    sora_volume: float = 0.4
    narration_volume: float = 1.3
    privacy: str = "private"
    video_engine: str = "grok"
    skip_subtitles: bool = False
    frame_chain: bool = False
    reference_image: str | None = None


class ExecuteConceptResponse(BaseModel):
    run_id: int
    workflow_id: str
    channel_name: str


# --- Metrics ---


class VideoMetrics(BaseModel):
    run_id: int
    video_id: str
    title: str | None = None
    views: int = 0
    likes: int = 0
    comments: int = 0
    youtube_url: str | None = None
    privacy: str | None = None
    published_at: str | None = None


class ChannelMetrics(BaseModel):
    channel_id: int
    channel_name: str
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    video_count: int = 0
    avg_views_per_video: float = 0
