"""Pydantic models for Code Review Agent environment."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from openenv.core.env_server.types import Action, Observation, State


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    STYLE = "style"
    PERFORMANCE = "performance"


class Finding(BaseModel):
    """A single finding in a code review."""

    line_number: int = Field(
        ..., ge=1, description="1-indexed line in the diff where issue lives"
    )
    severity: Severity
    category: Category
    description: str = Field(..., min_length=5)


class CodeReviewAction(Action):
    """Action for code review environment - list of findings."""

    findings: list[Finding]


class CodeReviewObservation(Observation):
    """Observation for code review environment - diff and context."""

    diff: str
    file_path: str
    task_name: str
    step_number: int
    pr_context: str


class CodeReviewState(State):
    """State for code review environment."""

    task_name: str
    step_count: int
    done: bool
    last_reward: float
    cumulative_reward: float
    last_action: dict[str, Any] | None
    last_error: str | None
