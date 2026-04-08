# CONTEXT_FOR_LLM.md
# Full Project Context — Code Review Agent (OpenEnv-Core)

This document is written for any LLM (Claude, GPT, etc.) that picks up this codebase mid-stream. Read this before touching any file.

---

## Hackathon Overview

**Event:** Scaler School of Technology × Meta PyTorch Hackathon 2026  
**Round 1 Deadline:** April 8, 2026 at 11:59 PM  
**Finale:** April 25–26, 2026  
**Participant:** MD Shumaque Raza  

**What Round 1 asks for:**
Build a complete, real-world OpenEnv environment using **openenv-core** that an AI agent can learn from via `step()/reset()/state()` API. Must NOT be a game or toy. Must have 3+ tasks (easy → hard), deterministic graders (0.0–1.0), meaningful reward function, baseline inference script, Docker deployment, and HF Spaces.

**Evaluation weights:**
- Real-world utility: 30%
- Task & grader quality: 25%
- Environment design: 20%
- Code quality & spec compliance: 15%
- Creativity & novelty: 10%

---

## What We Built

**Environment name:** `code-review-agent`  
**Core idea:** AI agent reviews pull requests. Diffs have deterministically seeded bugs/vulnerabilities. Agent submits structured findings. Grader computes F1 score (precision + recall) against ground truth.

**Why this wins:**
1. Every software team does code review — maximally real-world (30% weight)
2. Graders are fully deterministic, objective, seed-based — no ambiguity (25% weight)
3. Meta/HF judges do PR review daily — instant empathy, novel in OpenEnv space (10% weight)
4. Uses openenv-core base classes — full spec compliance (15% weight)
5. Single-turn review mimics how real agents would be deployed (20% weight)

---

## Critical: openenv-core Requirements

**This environment MUST use openenv-core base classes:**

1. **Environment base class:** `openenv.core.env_server.interfaces.Environment`
2. **Type system:** `openenv.core.env_server.types.Action`, `Observation`, `State`
3. **Server creation:** `openenv.core.env_server.http_server.create_app()`
4. **Port:** 8000 (not 7860)
5. **Structure:** `server/app.py` (not `app/server.py`)
6. **Package manager:** `pyproject.toml` + `uv` (not `requirements.txt` + `pip`)
7. **Docker base:** `ghcr.io/meta-pytorch/openenv-base:latest`

---

## File-by-File Explanation

### `server/models.py`
Pydantic models extending openenv-core types:
- `CodeReviewAction(Action)`: extends `openenv.core.env_server.types.Action`
- `CodeReviewObservation(Observation)`: extends `openenv.core.env_server.types.Observation`
- `CodeReviewState(State)`: extends `openenv.core.env_server.types.State`
- `Finding`: line_number, severity, category, description
- `Severity`, `Category`: enums

### `server/code_review_environment.py` — `CodeReviewEnv`
Core environment class extending `openenv.core.env_server.interfaces.Environment`:
- `reset(seed, episode_id, **kwargs)` → `CodeReviewObservation`
- `step(action, timeout_s, **kwargs)` → `CodeReviewObservation`
- `state` property → `CodeReviewState`

Episodes are single-turn by design (code review = one submission). `done = True` after first `step()`. Call `reset()` to start again.

### `server/app.py`
FastAPI app using `openenv.core.env_server.http_server.create_app()`:
```python
app = create_app(
    env=CodeReviewEnv,
    action_cls=CodeReviewAction,
    observation_cls=CodeReviewObservation,
    env_name="code_review_agent",
    max_concurrent_envs=1,
)
```

**Endpoints provided automatically by openenv-core:**
- `POST /reset` - Reset environment
- `POST /step` - Take a step
- `GET /state` - Get current state
- `GET /health` - Health check
- `GET /schema` - Combined action/observation/state schema
- `GET /metadata` - Environment metadata
- `WebSocket /ws` - WebSocket interface
- `POST /mcp` - MCP endpoint

### `tasks/seeds.py`
Library of seeded diffs. Each `SeededDiff` has:
- `task_name`: matches TASK_REGISTRY key
- `file_path`: realistic path
- `pr_context`: realistic commit/PR message
- `diff`: unified diff string
- `ground_truth`: list of `GroundTruthIssue` (line_number, severity, category, keywords)

**Keywords** are used for fuzzy description matching — agent doesn't need exact wording, just must mention one of the keywords in its finding description.

Three seeded diffs:
1. `detect_logic_bug` — `src/pagination.py` — 2 arithmetic bugs
2. `detect_security_flaw` — `app/db/users.py` — SQL injection + hardcoded JWT secret
3. `full_pr_review` — 4 files — path traversal + command injection + pickle deserialization + hardcoded DB creds

### `graders/grader.py`
`grade(task_name, action) → Reward`

Algorithm:
1. For each agent finding, try to match against unmatched ground-truth issues
2. Match criteria: line within ±3, same category, description contains at least one keyword
3. Compute precision (with FP penalty), recall, F1
4. F1 = final score

### `inference.py` (ROOT — CRITICAL)
**Must be in root directory.** Reads `HF_TOKEN` (mandatory, no default), `API_BASE_URL` (default: openai), `MODEL_NAME` (default: Qwen/Qwen2.5-72B-Instruct).

Uses OpenAI client (not raw HTTP, not another SDK). Calls `client.chat.completions.create()`. System prompt instructs model to return JSON with findings array.

**Uses openenv-core environment:**
```python
from server.code_review_environment import CodeReviewEnv
from server.models import CodeReviewAction, Finding
```

Output format (REQUIRED by guidelines):
```
[START] task=<name> env=code-review-agent model=<model>
[STEP] step=<n> action=<str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> rewards=<r1,...>
```

### `pyproject.toml`
Dependencies using `uv` package manager:
- `openenv-core>=0.2.2`
- `fastapi>=0.115.0`
- `uvicorn[standard]>=0.32.0`
- `pydantic>=2.10.0`
- `openai>=1.58.0`

### `Dockerfile`
- Base: `ghcr.io/meta-pytorch/openenv-base:latest`
- Non-root user `appuser`
- Copies all files
- Exposes 8000 (not 7860)
- Uses `uv sync` for dependencies
- CMD: `uv run python server/app.py`

### `openenv.yaml`
Metadata file required by `openenv validate`. Contains name, version, description, tags (includes `openenv`), task list with difficulties, observation/action space definitions, reward range, max_steps.

---

## Critical Constraints (Don't Break These)

1. **MUST use openenv-core base classes** — `Environment`, `Action`, `Observation`, `State`
2. **MUST use `create_app()`** from `openenv.core.env_server.http_server`
3. **Port MUST be 8000** (not 7860)
4. **Structure MUST be `server/app.py`** (not `app/server.py`)
5. **MUST use `pyproject.toml` + `uv`** (not `requirements.txt` + `pip`)
6. **Dockerfile MUST use `ghcr.io/meta-pytorch/openenv-base:latest`**
7. `inference.py` MUST be in root directory
8. Must use `OpenAI` client — no `requests`, no `httpx` direct calls, no other LLM SDKs
9. `HF_TOKEN` has no default — raise `ValueError` if missing
10. `API_BASE_URL` must have default `"https://api-inference.huggingface.co/v1"`
11. `MODEL_NAME` must have default `"Qwen/Qwen2.5-72B-Instruct"`
12. Log format must be exact: `[START]`, `[STEP]`, `[END]` with exact field names
13. `reward` and `rewards` must be 2 decimal places
14. `done` and `success` must be lowercase `true`/`false`

---

## Known Limitations / Future Work

- Grader uses keyword matching — a more robust version could use embedding similarity or an LLM-as-judge
- Seeded diffs are static — a v2 could procedurally generate diffs from a bug database
- Task difficulty could be auto-calibrated from model performance across multiple runs
- Style/performance category tasks not seeded yet — only bug and security

---

## Deployment Checklist

Before submitting to hackathon:

- [ ] `docker build -t code-review-agent .` passes
- [ ] `docker run -p 8000:8000 -e HF_TOKEN=xxx code-review-agent` starts cleanly
- [ ] `GET /health` returns 200
- [ ] `POST /reset` returns valid Observation JSON
- [ ] `GET /schema` returns action/observation/state schemas
- [ ] `python inference.py` completes without error and prints [START]/[STEP]/[END] lines
- [ ] HF Space is in "Running" state
- [ ] No other HF Spaces active during submission window
- [ ] `openenv.yaml` present in root
- [ ] Uses openenv-core base classes (not custom Pydantic)

---

## Environment Variables Reference

| Var | Required | Default | Where Used |
|---|---|---|---|
| `HF_TOKEN` | YES | none | `inference.py` (as OpenAI client api_key), HF Space auth |
| `API_BASE_URL` | no | `https://router.huggingface.co/v1` | `inference.py` OpenAI client base_url |
| `MODEL_NAME` | no | `Qwen/Qwen2.5-72B-Instruct` | `inference.py` model param |

---

## Tech Stack

- **Python 3.11**
- **openenv-core 0.2.2+** — Environment base classes and server
- **FastAPI 0.115+** — REST API server (via openenv-core)
- **Pydantic v2** — typed models
- **Uvicorn** — ASGI server
- **OpenAI SDK 1.58+** — LLM inference
- **uv** — Package manager
- **Docker** — containerization
- **Hugging Face Spaces** — deployment target

---

## Repo Structure

```
code-review-env/
├── server/
│   ├── __init__.py
│   ├── app.py                 # FastAPI app using openenv-core create_app()
│   ├── code_review_environment.py  # Environment extending openenv.core.Environment
│   └── models.py              # Pydantic models extending openenv-core types
├── graders/
│   ├── __init__.py
│   └── grader.py              # Deterministic F1 grader
├── tasks/
│   ├── __init__.py
│   └── seeds.py               # Seeded diff library + ground truth
├── tests/
│   └── __init__.py
├── inference.py               # Baseline inference script (root)
├── pyproject.toml             # Dependencies using uv
├── openenv.yaml               # OpenEnv metadata
├── Dockerfile                 # Based on openenv-base
├── README.md
└── CONTEXT_FOR_LLM.md         # this file
```

---

## Key Differences from Old Structure

| Old (Wrong) | New (Correct - openenv-core) |
|-------------|------------------------------|
| Custom Pydantic base classes | `openenv.core.env_server.interfaces.Environment` |
| Custom Action/Observation/State | `openenv.core.env_server.types.Action/Observation/State` |
| Raw FastAPI app | `create_app()` from `openenv.core.env_server.http_server` |
| Port 7860 | Port 8000 |
| `app/server.py` | `server/app.py` |
| `requirements.txt` + pip | `pyproject.toml` + uv |
| Custom Dockerfile | Uses `ghcr.io/meta-pytorch/openenv-base:latest` |
| Manual endpoint registration | Automatic via `create_app()` |
