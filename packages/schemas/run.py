from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class RunState(BaseModel):
    run_id: int
    channel_id: int
    status: RunStatus
    current_step: str = ""
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
