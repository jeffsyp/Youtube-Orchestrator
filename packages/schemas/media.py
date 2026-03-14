from pydantic import BaseModel


class ShotItem(BaseModel):
    scene_number: int
    description: str
    duration_seconds: int
    visual_style: str
    text_overlay: str | None = None


class VisualPlan(BaseModel):
    shots: list[ShotItem]
    total_duration_seconds: int
    style_notes: str


class VoicePlan(BaseModel):
    narration_style: str
    pacing: str
    tone: str
    emphasis_points: list[str]
    script_with_directions: str
