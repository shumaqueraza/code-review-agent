"""
Graders — deterministic, 0.0–1.0 scoring.

Scoring logic per task:
- For each ground-truth issue, check if agent submitted a finding that:
  1. Has line_number within ±LINE_NUMBER_TOLERANCE lines of the seeded issue
  2. Has correct category
  3. Description contains at least one keyword (case-insensitive)

Precision/recall F1 used as final score.
False positives that exceed 2x true positive count penalize precision.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from server.models import Finding
from tasks.seeds import GroundTruthIssue, TASK_REGISTRY

# Line number tolerance for matching findings
# Models struggle with exact line counting in diffs, so we use ±10 line tolerance
# This accounts for model limitations while still requiring approximate correctness
LINE_NUMBER_TOLERANCE = 10


class Reward(BaseModel):
    """Reward model for grading results."""

    value: float = Field(..., ge=0.0, le=1.0)
    breakdown: dict[str, float] = Field(default_factory=dict)
    message: str = Field(default="")


def _finding_matches(finding: Finding, truth: GroundTruthIssue) -> bool:
    line_ok = abs(finding.line_number - truth.line_number) <= LINE_NUMBER_TOLERANCE
    category_ok = finding.category.value == truth.category
    desc_lower = finding.description.lower()
    keyword_ok = any(kw in desc_lower for kw in truth.keywords)
    return line_ok and category_ok and keyword_ok


def grade(task_name: str, action) -> Reward:
    seed = TASK_REGISTRY.get(task_name)
    if seed is None:
        return Reward(value=0.0, message=f"unknown task: {task_name}")

    ground_truth = seed.ground_truth
    findings = action.findings

    true_positives = 0
    matched_truths: set[int] = set()

    for finding in findings:
        for idx, truth in enumerate(ground_truth):
            if idx in matched_truths:
                continue
            if _finding_matches(finding, truth):
                true_positives += 1
                matched_truths.add(idx)
                break

    total_truth = len(ground_truth)
    total_findings = len(findings)

    recall = true_positives / total_truth if total_truth > 0 else 0.0

    # Precision with false-positive penalty
    false_positives = total_findings - true_positives
    adjusted_tp = max(0, true_positives - max(0, false_positives - true_positives))
    precision = adjusted_tp / total_findings if total_findings > 0 else 0.0

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    score = round(min(1.0, max(0.0, f1)), 4)

    breakdown = {
        "true_positives": float(true_positives),
        "false_positives": float(false_positives),
        "total_ground_truth": float(total_truth),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }

    message = (
        f"Caught {true_positives}/{total_truth} issues. "
        f"Precision={precision:.2f} Recall={recall:.2f} F1={f1:.2f}"
    )

    return Reward(value=score, breakdown=breakdown, message=message)
