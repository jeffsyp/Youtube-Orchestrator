"""Hardcoded fake data for Phase 1 end-to-end testing."""

from datetime import datetime, timezone

from packages.schemas.channel import ChannelConfig
from packages.schemas.media import ShotItem, VisualPlan, VoicePlan
from packages.schemas.packaging import PackagingPlan
from packages.schemas.research import CandidateVideo, TemplatePattern
from packages.schemas.writing import IdeaVariant, OutlineDraft, ScriptDraft, ScriptStage

FAKE_CHANNEL = ChannelConfig(
    channel_id=1,
    name="Signal Intel",
    niche="tech explainers",
    search_terms=["AI breakthrough", "tech explained", "future technology"],
    tone="informative and engaging",
)

FAKE_CANDIDATES = [
    CandidateVideo(
        video_id="abc123",
        title="This AI Can Now Think Like a Human",
        channel_name="TechVision",
        channel_subscribers=45000,
        views=1200000,
        published_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
        duration_seconds=612,
        tags=["AI", "AGI", "machine learning"],
        breakout_score=0.0,
    ),
    CandidateVideo(
        video_id="def456",
        title="Why Every Company Is Firing Their Data Scientists",
        channel_name="DataBytes",
        channel_subscribers=120000,
        views=890000,
        published_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
        duration_seconds=485,
        tags=["data science", "AI jobs", "automation"],
        breakout_score=0.0,
    ),
    CandidateVideo(
        video_id="ghi789",
        title="The $1 Chip That Changes Everything",
        channel_name="SiliconInsider",
        channel_subscribers=28000,
        views=2100000,
        published_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        duration_seconds=540,
        tags=["chips", "semiconductors", "hardware"],
        breakout_score=0.0,
    ),
    CandidateVideo(
        video_id="jkl012",
        title="I Replaced My Entire Workflow With AI Agents",
        channel_name="ProductivityPro",
        channel_subscribers=95000,
        views=560000,
        published_at=datetime(2026, 3, 8, tzinfo=timezone.utc),
        duration_seconds=720,
        tags=["AI agents", "productivity", "automation"],
        breakout_score=0.0,
    ),
    CandidateVideo(
        video_id="mno345",
        title="Quantum Computing Just Hit a Major Milestone",
        channel_name="QuantumLeap",
        channel_subscribers=15000,
        views=780000,
        published_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
        duration_seconds=390,
        tags=["quantum computing", "physics", "breakthrough"],
        breakout_score=0.0,
    ),
]

FAKE_SCORED_CANDIDATES = [
    c.model_copy(update={"breakout_score": score})
    for c, score in zip(
        FAKE_CANDIDATES, [26.7, 7.4, 75.0, 5.9, 52.0]
    )
]

FAKE_TEMPLATES = [
    TemplatePattern(
        pattern_name="Underdog Breakthrough",
        description="Small channel covers a massive tech breakthrough, uses shock hook and builds to explanation",
        hook_style="Bold claim + 'here is why'",
        structure=["Shock hook", "Context/background", "The breakthrough", "Why it matters", "What comes next"],
        source_video_ids=["ghi789", "mno345"],
    ),
    TemplatePattern(
        pattern_name="Industry Disruption",
        description="Frames a technology shift as threatening an entire profession or industry",
        hook_style="Fear-based question + contrarian take",
        structure=["Provocative claim", "Evidence montage", "Counter-argument", "Nuanced reality", "Action items"],
        source_video_ids=["def456"],
    ),
    TemplatePattern(
        pattern_name="Personal Experiment",
        description="Creator tests a tool/workflow and reports honest results",
        hook_style="'I tried X for Y days' format",
        structure=["Setup/promise", "Day-by-day highlights", "Failures", "Wins", "Final verdict"],
        source_video_ids=["jkl012"],
    ),
]

FAKE_IDEAS = [
    IdeaVariant(
        title="The 5-Cent Chip That Could Kill NVIDIA",
        hook="A chip smaller than a grain of rice just outperformed a $40,000 GPU.",
        angle="Explain RISC-V open-source chip developments and why they threaten the GPU monopoly",
        target_length_seconds=480,
        score=8.7,
        selected=True,
    ),
    IdeaVariant(
        title="Why AI Agents Are About to Replace Your Entire Team",
        hook="By 2027, 40% of knowledge work will be done by AI agents. Here is what that actually means.",
        angle="Break down the real state of AI agents and separate hype from reality",
        target_length_seconds=600,
        score=7.2,
        selected=False,
    ),
    IdeaVariant(
        title="Quantum Computers Just Solved an Impossible Problem",
        hook="Last week, a quantum computer solved in 4 minutes what would take a supercomputer 10,000 years.",
        angle="Explain the latest quantum supremacy milestone in plain English",
        target_length_seconds=420,
        score=6.8,
        selected=False,
    ),
    IdeaVariant(
        title="I Let AI Run My Life for a Week",
        hook="I handed every decision — from what to eat to how to invest — to an AI. Here is what happened.",
        angle="Personal experiment format testing AI decision-making in daily life",
        target_length_seconds=540,
        score=5.5,
        selected=False,
    ),
]

FAKE_OUTLINE = OutlineDraft(
    idea_title="The 5-Cent Chip That Could Kill NVIDIA",
    sections=[
        "Hook: Show the chip next to a grain of rice, state the performance claim",
        "Context: NVIDIA's dominance, why GPUs cost so much, the monopoly problem",
        "The challenger: RISC-V open-source architecture, who is behind it",
        "The benchmarks: What this chip actually achieved and what it means",
        "Why NVIDIA should be worried: market forces, open-source momentum",
        "The reality check: what still needs to happen, timeline",
        "CTA: Subscribe for more tech breakdowns",
    ],
    estimated_duration_seconds=480,
    key_points=[
        "RISC-V is an open-source chip architecture gaining serious momentum",
        "New designs are matching proprietary chips at a fraction of the cost",
        "This does not kill NVIDIA overnight, but changes the game long-term",
    ],
)

FAKE_SCRIPT_DRAFT = ScriptDraft(
    idea_title="The 5-Cent Chip That Could Kill NVIDIA",
    stage=ScriptStage.DRAFT,
    content=(
        "This chip costs less than a piece of gum. But it just outperformed a GPU that costs "
        "more than a car. And it could change the entire tech industry.\n\n"
        "Right now, if you want to train an AI model, you need NVIDIA GPUs. There is no real "
        "alternative. That is why NVIDIA is worth over 3 trillion dollars and Jensen Huang "
        "is the most powerful person in tech.\n\n"
        "But a group of engineers working on something called RISC-V — an open-source chip "
        "architecture — just proved that you do not need NVIDIA anymore. At least, not for "
        "everything.\n\n"
        "Here is what happened. A team at [University] built a RISC-V based accelerator that "
        "ran a standard AI benchmark 12% faster than an NVIDIA A100. The chip costs roughly "
        "5 cents to manufacture at scale. The A100 costs $10,000.\n\n"
        "Now, before you sell your NVIDIA stock, there are caveats..."
    ),
    word_count=156,
    critique_notes=None,
)

FAKE_SCRIPT_CRITIQUE = ScriptDraft(
    idea_title="The 5-Cent Chip That Could Kill NVIDIA",
    stage=ScriptStage.CRITIQUE,
    content=FAKE_SCRIPT_DRAFT.content,
    word_count=156,
    critique_notes=(
        "Strengths: Strong hook, clear narrative arc, good use of contrast.\n"
        "Weaknesses: (1) The [University] placeholder needs to be filled. "
        "(2) The script ends abruptly — needs a full reality check section and CTA. "
        "(3) Word count is too low for a 480-second video — aim for 700+ words. "
        "(4) Add more specific benchmarks beyond the single 12% claim."
    ),
)

FAKE_SCRIPT_FINAL = ScriptDraft(
    idea_title="The 5-Cent Chip That Could Kill NVIDIA",
    stage=ScriptStage.FINAL,
    content=(
        FAKE_SCRIPT_DRAFT.content
        + "\n\nThe RISC-V chip excels at specific inference tasks, not general-purpose training. "
        "NVIDIA's CUDA ecosystem is a massive moat — thousands of libraries and tools built "
        "specifically for their hardware. Switching is not just about the chip, it is about "
        "the entire software stack.\n\n"
        "But here is what makes RISC-V different from every other 'NVIDIA killer' before it: "
        "it is open source. Anyone can build on it. Anyone can improve it. And the momentum "
        "is real — Google, Samsung, and Qualcomm are all investing heavily.\n\n"
        "The question is not whether RISC-V will compete with NVIDIA. It is when. And based "
        "on what we are seeing, that timeline just got a lot shorter.\n\n"
        "If you want to stay ahead of the biggest shifts in tech, subscribe and hit the bell. "
        "I break down one major trend every week."
    ),
    word_count=312,
    critique_notes=None,
)

FAKE_VISUAL_PLAN = VisualPlan(
    shots=[
        ShotItem(scene_number=1, description="Extreme close-up of tiny chip next to grain of rice", duration_seconds=8, visual_style="dramatic macro shot"),
        ShotItem(scene_number=2, description="NVIDIA GPU rack in data center, price tag overlay", duration_seconds=15, visual_style="b-roll with text overlay"),
        ShotItem(scene_number=3, description="RISC-V logo animation, open-source concept visualization", duration_seconds=12, visual_style="motion graphics"),
        ShotItem(scene_number=4, description="Benchmark comparison chart, side by side", duration_seconds=20, visual_style="animated infographic"),
        ShotItem(scene_number=5, description="Company logos: Google, Samsung, Qualcomm investing", duration_seconds=10, visual_style="logo montage"),
        ShotItem(scene_number=6, description="Timeline graphic showing RISC-V adoption curve", duration_seconds=15, visual_style="animated chart"),
    ],
    total_duration_seconds=480,
    style_notes="Clean, modern tech aesthetic. Dark background with accent colors. Minimal text on screen — let narration carry the story.",
)

FAKE_VOICE_PLAN = VoicePlan(
    narration_style="Conversational authority — like explaining to a smart friend",
    pacing="Start fast on the hook (energetic), slow down for explanation sections, build energy toward the conclusion",
    tone="Confident but not arrogant. Genuinely curious about the topic.",
    emphasis_points=[
        "FIVE CENTS — emphasize the cost contrast",
        "Open source — stress this is the key differentiator",
        "The question is not whether... it is WHEN — pause before 'when' for impact",
    ],
    script_with_directions=FAKE_SCRIPT_FINAL.content,
)

FAKE_PACKAGE = PackagingPlan(
    title="The 5-Cent Chip That Could Kill NVIDIA",
    description=(
        "A chip that costs less than a piece of gum just outperformed a $10,000 NVIDIA GPU. "
        "Here is how RISC-V open-source chips are about to change everything.\n\n"
        "In this video, we break down the latest RISC-V benchmarks, why open-source silicon "
        "is gaining momentum, and what it means for the future of AI hardware.\n\n"
        "#RISCV #NVIDIA #TechExplained #AIHardware #OpenSource"
    ),
    tags=["RISC-V", "NVIDIA", "GPU", "AI hardware", "open source", "chips", "semiconductors", "tech explained"],
    category="Science & Technology",
    thumbnail_text="5c vs $10K",
    srt_content=(
        "1\n00:00:00,000 --> 00:00:04,000\nThis chip costs less than a piece of gum.\n\n"
        "2\n00:00:04,000 --> 00:00:08,000\nBut it just outperformed a GPU\nthat costs more than a car.\n\n"
    ),
    asset_manifest=[
        "script_final.txt",
        "visual_plan.json",
        "voice_plan.json",
        "subtitles.srt",
        "thumbnail_brief.txt",
    ],
    status="ready",
)
