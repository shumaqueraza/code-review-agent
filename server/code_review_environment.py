"""Code Review Environment implementation using openenv-core."""

from __future__ import annotations

from typing import Any, Optional

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import Action, Observation, State

from server.models import CodeReviewAction, CodeReviewObservation, CodeReviewState
from graders.grader import grade
from tasks.seeds import TASK_REGISTRY


MAX_STEPS = 5


class CodeReviewEnv(
    Environment[CodeReviewAction, CodeReviewObservation, CodeReviewState]
):
    """
    OpenEnv-compliant environment for AI-driven pull request review.

    The agent receives a code diff and must submit findings (bugs, security
    issues, style violations). Graders compare findings against seeded ground
    truth using F1 over precision/recall.
    """

    def __init__(
        self,
        task_name: str = "detect_logic_bug",
        transform: Optional[Any] = None,
        rubric: Optional[Any] = None,
    ) -> None:
        super().__init__(transform=transform, rubric=rubric)

        if task_name not in TASK_REGISTRY:
            raise ValueError(
                f"Unknown task '{task_name}'. Valid: {list(TASK_REGISTRY)}"
            )

        self._task_name = task_name
        self._seed = TASK_REGISTRY[task_name]
        self._step_count = 0
        self._done = False
        self._last_reward: float = 0.0
        self._cumulative_reward: float = 0.0
        self._last_action: CodeReviewAction | None = None
        self._last_error: str | None = None

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> CodeReviewObservation:
        """Reset the environment and return initial observation."""
        self._step_count = 0
        self._done = False
        self._last_reward = 0.0
        self._cumulative_reward = 0.0
        self._last_action = None
        self._last_error = None

        return self._build_observation()

    def step(
        self,
        action: CodeReviewAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> CodeReviewObservation:
        """Take a step in the environment."""
        if self._done:
            raise RuntimeError("Episode done. Call reset() first.")

        self._step_count += 1
        self._last_action = action
        self._last_error = None

        try:
            reward = grade(self._task_name, action)
        except Exception as exc:
            self._last_error = str(exc)
            reward_value = 0.0
        else:
            reward_value = reward.value

        self._last_reward = reward_value
        self._cumulative_reward += reward_value

        # Episode ends after first submission (review is single-turn by nature)
        # or if max steps hit
        self._done = True

        obs = self._build_observation()
        obs.reward = reward_value
        obs.done = self._done

        return obs

    @property
    def state(self) -> CodeReviewState:
        """Get the current environment state."""
        return CodeReviewState(
            task_name=self._task_name,
            step_count=self._step_count,
            done=self._done,
            last_reward=self._last_reward,
            cumulative_reward=round(self._cumulative_reward, 4),
            last_action=self._last_action.model_dump() if self._last_action else None,
            last_error=self._last_error,
        )

    def _build_observation(self) -> CodeReviewObservation:
        """Build observation from current state."""
        return CodeReviewObservation(
            diff=self._seed.diff,
            file_path=self._seed.file_path,
            task_name=self._task_name,
            step_number=self._step_count,
            pr_context=self._seed.pr_context,
            done=self._done,
            reward=self._last_reward,
        )

    def close(self) -> None:
        """Clean up resources used by the environment."""
        # No resources to clean up for this environment
        pass
