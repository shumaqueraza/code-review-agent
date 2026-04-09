"""
Inference Script for Code Review Agent
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

- Defaults are set only for API_BASE_URL and MODEL_NAME
    (and should reflect your active inference setup):
    API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
    MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT
- The script must emit exactly three line types to stdout, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

  Rules:
    - One [START] line at episode begin.
    - One [STEP] line per step, immediately after env.step() returns.
    - One [END] line after env.close(), always emitted (even on exception).
    - reward and rewards are formatted to 2 decimal places.
    - done and success are lowercase booleans: true or false.
    - error is the raw last_action_error string, or null if none.
    - All fields on a single line with no newlines within a line.
    - Each tasks should return score in [0, 1]

  Example:
    [START] task=detect_logic_bug env=code-review-agent model=Qwen/Qwen2.5-72B-Instruct
    [STEP] step=1 action=submit_findings(count=2) reward=0.70 done=true error=null
    [END] success=true steps=1 score=0.700 rewards=0.70
"""

import os
import json
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from openai import OpenAI

API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
BENCHMARK = "code-review-agent"
MAX_STEPS = 5
SUCCESS_SCORE_THRESHOLD = 0.5  # F1 score threshold for success

if API_KEY is None:
    raise ValueError("HF_TOKEN or API_KEY environment variable is required")

client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

SYSTEM_PROMPT = """You are a senior software engineer performing a code review.
You will receive a unified diff of a pull request.
Your job is to identify ALL bugs, security vulnerabilities, and significant issues.

CRITICAL INSTRUCTIONS:
1. Line Numbers: Count from the START of the diff text shown (line 1 is the first line of the diff output)
2. Keywords: Use EXACT terms in descriptions - "sql injection", "hardcoded", "off-by-one", "path traversal", "command injection", "pickle", "deserialization", "ceiling division"
3. Precision: Only report REAL issues - don't hallucinate or report non-issues
4. Categories: Use "bug", "security", "style", or "performance"
5. Severity: Use "critical", "high", "medium", "low", or "info"

COMMON PATTERNS TO IDENTIFY:
- SQL Injection: f-string or string formatting in SQL queries
- Hardcoded Secrets: API keys, passwords, JWT secrets in code
- Command Injection: subprocess.run with shell=True and user input
- Path Traversal: Using unsanitized filenames in file paths
- Unsafe Deserialization: pickle.loads() on untrusted data
- Off-by-one Errors: Wrong index math like (page * size) instead of ((page-1) * size)
- Missing Edge Cases: Integer division instead of ceiling division

Respond ONLY with a valid JSON object matching this exact schema:
{
  "findings": [
    {
      "line_number": <integer, 1-indexed line in diff where issue appears>,
      "severity": "<critical|high|medium|low|info>",
      "category": "<bug|security|style|performance>",
      "description": "<clear explanation using exact keywords>"
    }
  ]
}

EXAMPLES:
Example 1 - SQL Injection:
Diff shows: sql = f"SELECT * FROM users WHERE name LIKE '%{query}%'"
Finding: {"line_number": 5, "severity": "critical", "category": "security", "description": "SQL injection vulnerability - unsanitized user input in f-string query allows SQL injection"}

Example 2 - Off-by-one Error:
Diff shows: start = page * page_size (should be (page - 1) * page_size)
Finding: {"line_number": 3, "severity": "high", "category": "bug", "description": "Off-by-one error in pagination - should use (page - 1) * page_size instead of page * page_size"}

Example 3 - Hardcoded Secret:
Diff shows: SECRET_KEY = "hardcoded_jwt_secret_abc123"
Finding: {"line_number": 10, "severity": "critical", "category": "security", "description": "Hardcoded JWT secret key exposed in source code - should use environment variable"}

Example 4 - Missing Ceiling Division:
Diff shows: return total_items // page_size (should be (total_items + page_size - 1) // page_size)
Finding: {"line_number": 8, "severity": "medium", "category": "bug", "description": "Missing ceiling division in total_pages calculation - use (total_items + page_size - 1) // page_size to include last partial page"}

Rules:
- Count line numbers from the FIRST line of the diff output shown
- Use the exact keywords listed above in descriptions
- Do NOT include findings for things that are fine
- Return only the JSON, no preamble, no markdown fences"""


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def review_diff(diff: str, file_path: str, pr_context: str, task_name: str) -> dict:
    user_content = f"""PR Context: {pr_context}
File: {file_path}
Task: {task_name}

Diff:
{diff}"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if model added them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return {"findings": []}


def run_task(task_name: str, diff: str, file_path: str, pr_context: str) -> dict:
    from server.code_review_environment import CodeReviewEnv
    from server.models import CodeReviewAction, Finding
    from server.models import Severity, Category

    env = CodeReviewEnv(task_name=task_name)
    obs = env.reset()

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    last_error = None

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = review_diff(obs.diff, obs.file_path, obs.pr_context, task_name)
        findings = []
        for f in result.get("findings", []):
            try:
                findings.append(
                    Finding(
                        line_number=int(f["line_number"]),
                        severity=Severity(f["severity"]),
                        category=Category(f["category"]),
                        description=str(f["description"]),
                    )
                )
            except Exception:
                continue

        action = CodeReviewAction(findings=findings)
        obs = env.step(action)
        reward = obs.reward or 0.0
        done = obs.done
        error = None

        rewards.append(reward)
        steps_taken = 1
        action_str = f"submit_findings(count={len(findings)})"

        log_step(
            step=steps_taken, action=action_str, reward=reward, done=done, error=error
        )

        # Clamp score to (0, 1) range - hackathon requires strictly between 0 and 1
        score = min(0.999, max(0.001, reward))
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as exc:
        last_error = str(exc).replace("\n", " ")
        log_step(step=1, action="error", reward=0.0, done=True, error=last_error)

    finally:
        try:
            env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return {
        "task": task_name,
        "score": score,
        "success": success,
        "steps": steps_taken,
    }


if __name__ == "__main__":
    from tasks.seeds import TASK_REGISTRY

    all_results = []
    for task_name, seed in TASK_REGISTRY.items():
        result = run_task(task_name, seed.diff, seed.file_path, seed.pr_context)
        all_results.append(result)

    print("\n--- BASELINE SCORES ---", flush=True)
    total = 0.0
    for r in all_results:
        print(f"  {r['task']}: {r['score']:.4f} | success={r['success']}", flush=True)
        total += r["score"]
    print(f"  AVERAGE: {total / len(all_results):.4f}", flush=True)
