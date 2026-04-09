---
title: Code Review Agent - OpenEnv
emoji: 🔍
colorFrom: blue
colorTo: purple
sdk: docker
pinned: true
app_port: 8000
base_path: /web
tags:
  - openenv
  - code-review
  - software-engineering
  - security
  - reinforcement-learning
---

# Code Review Agent — OpenEnv

An RL environment where AI agents perform pull request code review, identifying real bugs, security vulnerabilities, and style violations that have been deterministically seeded into code diffs.

Built for the **Scaler School of Technology × Meta PyTorch Hackathon 2026** (Round 1).

---

## Motivation

Every software engineering team reviews pull requests. It's high-stakes, repetitive, and requires deep domain knowledge — exactly where AI agents should excel. Existing RL benchmarks ignore this entirely.

This environment fills that gap: an agent receives a unified diff, submits structured findings (line number, severity, category, description), and is scored against ground-truth seeded issues using F1 over precision and recall. False positives are penalized. Partial credit is awarded for catching some issues. The agent must be precise, not just noisy.

Meta and Hugging Face engineers review PRs daily. This environment models their exact workflow.

---

## Environment Overview

| Property | Value |
|---|---|
| Observation | Unified diff text, file path, PR context, task name, step number |
| Action | List of findings: `{line_number, severity, category, description}` |
| Reward | F1 score (precision × recall) over seeded ground-truth issues |
| Episodes | Single-turn (one review submission per episode) |
| Max steps | 5 |

### Observation Space

```python
class Observation(BaseModel):
    diff: str              # Unified diff string
    file_path: str         # Path of file(s) being reviewed
    task_name: str         # Active task identifier
    step_number: int       # Current step (0-indexed)
    pr_context: str        # PR description / commit message
```

### Action Space

```python
class Action(BaseModel):
    findings: list[Finding]

class Finding(BaseModel):
    line_number: int       # 1-indexed line in diff
    severity: Severity     # critical | high | medium | low | info
    category: Category     # bug | security | style | performance
    description: str       # Explanation + fix recommendation
```

### Reward Function

Reward is computed as F1 score over ground-truth seeded issues:

- **True positive**: finding within ±10 lines of seeded issue, correct category, description contains at least one matching keyword
- **Precision penalty**: false positives beyond 1:1 ratio reduce precision
- **Partial credit**: catching 2 of 4 issues scores ~0.67 recall

**Why ±10 line tolerance?** AI models struggle with exact line counting in unified diffs due to hunk headers, context lines, and multi-file structures. This tolerance ensures models are graded on identifying the right issues rather than perfect line counting.

```
precision = adjusted_tp / total_findings
recall    = tp / total_ground_truth
f1        = 2 * precision * recall / (precision + recall)
```

---

## Tasks

### Task 1: `detect_logic_bug` — Easy

**File:** `src/pagination.py`  
**PR Context:** Refactor pagination to range-based cursor

The diff contains two seeded arithmetic bugs:
1. Off-by-one in `start` index calculation (`page * page_size` instead of `(page - 1) * page_size`)
2. Missing ceiling division in `total_pages` (truncated integer division drops the last partial page)

**Expected difficulty:** Easy — both are classic off-by-one patterns visible on first read.  
**Baseline score (GPT-4.1-mini):** ~0.70

---

### Task 2: `detect_security_flaw` — Medium

**File:** `app/db/users.py`  
**PR Context:** Add user search endpoint for admin panel

The diff contains two seeded security vulnerabilities:
1. **SQL Injection** — raw f-string interpolation in a `LIKE` query passed to `cursor.execute()`
2. **Hardcoded Secret** — JWT signing key committed as a string literal

**Expected difficulty:** Medium — SQL injection is obvious; hardcoded secret requires reading further into the diff.  
**Baseline score (GPT-4.1-mini):** ~0.80

---

### Task 3: `full_pr_review` — Hard

**Files:** `api/upload.py`, `workers/job_runner.py`, `utils/cache.py`, `config/settings.py`  
**PR Context:** Add file upload endpoint and background job processor

A multi-file PR with four seeded issues across different severity levels:
1. **Path Traversal** — unsanitized `f.filename` written directly to `UPLOAD_DIR`
2. **Command Injection** — `subprocess.run(command, shell=True)` with user-controlled input
3. **Unsafe Deserialization** — `pickle.loads()` on untrusted cache bytes
4. **Hardcoded Credentials** — production database URL with password committed

**Expected difficulty:** Hard — four issues spread across four files, requires full diff comprehension.  
**Baseline score (GPT-4.1-mini):** ~0.65

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/reset?task_name=<task>` | Reset env, returns initial observation |
| `POST` | `/step?task_name=<task>` | Submit action, returns obs/reward/done/info |
| `GET` | `/state?task_name=<task>` | Current env state |
| `GET` | `/tasks` | All tasks + action schema |
| `POST` | `/grader?task_name=<task>` | Score an action without advancing state |
| `POST` | `/baseline` | Run full inference.py baseline |
| `GET` | `/health` | Health check |

---

## Setup & Usage

### Local

```bash
git clone <repo>
cd code-review-env
uv sync
uv run python server/app.py
```

Server starts at `http://localhost:8000`.

### Docker

```bash
docker build -t code-review-agent .
docker run -p 8000:8000 \
  -e HF_TOKEN=<your_token> \
  -e API_BASE_URL=https://api-inference.huggingface.co/v1 \
  -e MODEL_NAME=Qwen/Qwen2.5-72B-Instruct \
  code-review-agent
```

### Run Baseline Inference

```bash
export HF_TOKEN=<your_huggingface_token>
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

uv run python inference.py
```

#### Expected output format

```
[START] task=detect_logic_bug env=code-review-agent model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=submit_findings(count=2) reward=0.70 done=true error=null
[END] success=true steps=1 rewards=0.70

[START] task=detect_security_flaw env=code-review-agent model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=submit_findings(count=2) reward=0.80 done=true error=null
[END] success=true steps=1 rewards=0.80

[START] task=full_pr_review env=code-review-agent model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=submit_findings(count=4) reward=0.65 done=true error=null
[END] success=true steps=1 rewards=0.65

--- BASELINE SCORES ---
  detect_logic_bug: 0.7000 | success=True
  detect_security_flaw: 0.8000 | success=True
  full_pr_review: 0.6500 | success=True
  AVERAGE: 0.7167
```

---

## Baseline Scores

| Task | Model | Score |
|---|---|---|
| detect_logic_bug | Qwen/Qwen2.5-72B-Instruct | 0.999 |
| detect_security_flaw | Qwen/Qwen2.5-72B-Instruct | 0.999 |
| full_pr_review | Qwen/Qwen2.5-72B-Instruct | 0.999 |
| **Average** | | **~1.0** |

**Note:** Scores achieved with line-numbered diffs (each line prefixed with "LINE X:"). This eliminates AI line-counting errors and ensures precise bug location reporting. All scores clamped to (0, 1) range per hackathon requirements.

---

## Project Structure

```
code-review-env/
├── server/
│   ├── __init__.py
│   ├── app.py                 # FastAPI app using openenv-core create_app()
│   ├── code_review_environment.py  # Core OpenEnv-compliant env
│   └── models.py              # Pydantic Observation/Action/State
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
└── README.md
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `HF_TOKEN` | Yes | — | Hugging Face API token |
| `API_BASE_URL` | No | `https://api-inference.huggingface.co/v1` | LLM API endpoint |
| `MODEL_NAME` | No | `Qwen/Qwen2.5-72B-Instruct` | Model identifier |

---

## Hugging Face Spaces

Tag: `openenv`

Deploy:
1. Create new Space → Docker SDK
2. Push this repo
3. Add `HF_TOKEN` as a Space secret
4. Space auto-builds and serves on port 7860

---

## OpenEnv Validation

```bash
openenv validate
```

All three tasks pass automated spec compliance checks: typed models, valid `step()/reset()/state()` endpoints, `openenv.yaml` metadata, and Docker build.
