"""FastAPI app for Code Review Agent using openenv-core."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from openenv.core.env_server.http_server import create_app

from server.code_review_environment import CodeReviewEnv
from server.models import CodeReviewAction, CodeReviewObservation


app = create_app(
    env=CodeReviewEnv,
    action_cls=CodeReviewAction,
    observation_cls=CodeReviewObservation,
    env_name="code_review_agent",
    max_concurrent_envs=1,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
