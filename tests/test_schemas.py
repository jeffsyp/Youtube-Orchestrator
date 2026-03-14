"""Test that all Pydantic schemas can be instantiated and serialized."""

from datetime import datetime, timezone

from packages.schemas import (
    CandidateVideo,
    ChannelConfig,
    IdeaVariant,
    OutlineDraft,
    PackagingPlan,
    RunState,
    RunStatus,
    ScriptDraft,
    ScriptStage,
    ShotItem,
    TemplatePattern,
    VisualPlan,
    VoicePlan,
)


def test_channel_config():
    c = ChannelConfig(channel_id=1, name="Test", niche="tech", search_terms=["AI"])
    data = c.model_dump(mode="json")
    assert data["name"] == "Test"
    assert ChannelConfig.model_validate(data)


def test_run_state():
    r = RunState(run_id=1, channel_id=1, status=RunStatus.RUNNING, started_at=datetime.now(timezone.utc))
    data = r.model_dump(mode="json")
    assert data["status"] == "running"
    assert RunState.model_validate(data)


def test_candidate_video():
    v = CandidateVideo(
        video_id="abc", title="Test", channel_name="Ch", channel_subscribers=1000,
        views=50000, published_at=datetime.now(timezone.utc), duration_seconds=300,
    )
    data = v.model_dump(mode="json")
    assert CandidateVideo.model_validate(data)


def test_template_pattern():
    t = TemplatePattern(
        pattern_name="Test", description="A pattern", hook_style="Bold claim",
        structure=["Hook", "Body", "CTA"], source_video_ids=["abc"],
    )
    assert t.model_dump(mode="json")


def test_idea_variant():
    i = IdeaVariant(title="Idea", hook="Hook", angle="Angle", target_length_seconds=300, score=7.5)
    assert i.model_dump(mode="json")


def test_outline_draft():
    o = OutlineDraft(
        idea_title="Idea", sections=["Intro", "Body", "CTA"],
        estimated_duration_seconds=300, key_points=["Point 1"],
    )
    assert o.model_dump(mode="json")


def test_script_draft():
    s = ScriptDraft(idea_title="Idea", stage=ScriptStage.DRAFT, content="Hello world", word_count=2)
    data = s.model_dump(mode="json")
    assert data["stage"] == "draft"
    assert ScriptDraft.model_validate(data)


def test_visual_plan():
    shot = ShotItem(scene_number=1, description="Shot 1", duration_seconds=10, visual_style="cinematic")
    v = VisualPlan(shots=[shot], total_duration_seconds=10, style_notes="Dark")
    assert v.model_dump(mode="json")


def test_voice_plan():
    v = VoicePlan(
        narration_style="Conversational", pacing="Medium", tone="Confident",
        emphasis_points=["Key point"], script_with_directions="Read this.",
    )
    assert v.model_dump(mode="json")


def test_packaging_plan():
    p = PackagingPlan(
        title="Video", description="Desc", tags=["tag1"],
        thumbnail_text="TEXT", srt_content="1\n00:00:00...",
        asset_manifest=["file.txt"],
    )
    assert p.model_dump(mode="json")


def test_fake_data_imports():
    """Verify all fake data objects are valid schema instances."""
    from apps.orchestrator.fake_data import (
        FAKE_CANDIDATES,
        FAKE_CHANNEL,
        FAKE_IDEAS,
        FAKE_OUTLINE,
        FAKE_PACKAGE,
        FAKE_SCORED_CANDIDATES,
        FAKE_SCRIPT_CRITIQUE,
        FAKE_SCRIPT_DRAFT,
        FAKE_SCRIPT_FINAL,
        FAKE_TEMPLATES,
        FAKE_VISUAL_PLAN,
        FAKE_VOICE_PLAN,
    )

    assert len(FAKE_CANDIDATES) == 5
    assert len(FAKE_SCORED_CANDIDATES) == 5
    assert len(FAKE_TEMPLATES) == 3
    assert len(FAKE_IDEAS) == 4
    assert FAKE_OUTLINE.idea_title
    assert FAKE_SCRIPT_DRAFT.stage == ScriptStage.DRAFT
    assert FAKE_SCRIPT_CRITIQUE.critique_notes
    assert FAKE_SCRIPT_FINAL.stage == ScriptStage.FINAL
    assert len(FAKE_VISUAL_PLAN.shots) == 6
    assert FAKE_VOICE_PLAN.narration_style
    assert FAKE_PACKAGE.status == "ready"
    assert FAKE_CHANNEL.niche == "tech explainers"
