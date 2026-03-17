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
    pipeline: str = "shorts"
    description: str | None = None
    stats: ChannelStats = Field(default_factory=ChannelStats)


# --- Runs ---


class RunSummary(BaseModel):
    id: int
    channel_id: int
    channel_name: str
    content_type: str = "longform"
    status: str
    current_step: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    review_score: float | None = None
    review_recommendation: str | None = None
    video_path: str | None = None
    thumbnail_path: str | None = None
    elapsed_seconds: int | None = None
    youtube_url: str | None = None
    youtube_privacy: str | None = None


class IdeaDetail(BaseModel):
    id: int
    title: str
    hook: str | None = None
    angle: str | None = None
    score: float = 0
    selected: bool = False


class ScriptDetail(BaseModel):
    id: int
    stage: str
    idea_title: str | None = None
    word_count: int = 0
    content: str | None = None
    critique_notes: str | None = None


class AssetDetail(BaseModel):
    id: int
    asset_type: str
    content: str | None = None


class PackageDetail(BaseModel):
    id: int
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    category: str | None = None
    status: str = "draft"


class RunDetail(RunSummary):
    ideas: list[IdeaDetail] = Field(default_factory=list)
    scripts: list[ScriptDetail] = Field(default_factory=list)
    assets: list[AssetDetail] = Field(default_factory=list)
    packages: list[PackageDetail] = Field(default_factory=list)


# --- Dashboard ---


class SystemCheck(BaseModel):
    name: str
    active: bool


class DashboardResponse(BaseModel):
    running_pipelines: list[RunSummary] = Field(default_factory=list)
    recent_runs: list[RunSummary] = Field(default_factory=list)
    channel_stats: list[ChannelResponse] = Field(default_factory=list)
    system_checks: list[SystemCheck] = Field(default_factory=list)


# --- Actions ---


class CreateRunRequest(BaseModel):
    channel_id: int
    auto_pick: bool = True
    privacy: str = "private"


class BatchRunRequest(BaseModel):
    channel_ids: list[int]
    privacy: str = "private"


class CreateRunResponse(BaseModel):
    run_id: int
    workflow_id: str
    channel_name: str
    pipeline: str


class BatchRunResponse(BaseModel):
    runs: list[CreateRunResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


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
