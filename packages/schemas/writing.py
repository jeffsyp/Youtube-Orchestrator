from enum import Enum

from pydantic import BaseModel


class IdeaVariant(BaseModel):
    title: str
    hook: str
    angle: str
    target_length_seconds: int
    score: float = 0.0
    selected: bool = False


class OutlineDraft(BaseModel):
    idea_title: str
    sections: list[str]
    estimated_duration_seconds: int
    key_points: list[str]


class ScriptStage(str, Enum):
    OUTLINE = "outline"
    DRAFT = "draft"
    CRITIQUE = "critique"
    FINAL = "final"


class ScriptDraft(BaseModel):
    idea_title: str
    stage: ScriptStage
    content: str
    word_count: int = 0
    critique_notes: str | None = None
