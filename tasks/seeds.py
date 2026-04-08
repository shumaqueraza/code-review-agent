"""
Seeded diff library.
Each entry: diff text, list of ground-truth issues (line, severity, category, keywords).
Keywords used by grader for fuzzy description matching.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class GroundTruthIssue:
    line_number: int
    severity: str
    category: str
    keywords: list[str]  # at least one must appear in agent description (case-insensitive)


@dataclass
class SeededDiff:
    task_name: str
    file_path: str
    pr_context: str
    diff: str
    ground_truth: list[GroundTruthIssue]


# ─── EASY: single logic bug ───────────────────────────────────────────────────

EASY_DIFF = SeededDiff(
    task_name="detect_logic_bug",
    file_path="src/pagination.py",
    pr_context="Refactor: switch pagination to use range-based cursor",
    diff="""\
--- a/src/pagination.py
+++ b/src/pagination.py
@@ -12,10 +12,10 @@ def paginate(items: list, page: int, page_size: int) -> list:
     \"\"\"Return items for the requested page (1-indexed).\"\"\"
     if page < 1:
         raise ValueError("page must be >= 1")
-    start = (page - 1) * page_size
-    end   = start + page_size
+    start = page * page_size
+    end   = start + page_size
     return items[start:end]
 
 
@@ -25,7 +25,7 @@ def total_pages(total_items: int, page_size: int) -> int:
     if page_size <= 0:
         raise ValueError("page_size must be positive")
-    return (total_items + page_size - 1) // page_size
+    return total_items // page_size
 """,
    ground_truth=[
        GroundTruthIssue(
            line_number=17,
            severity="high",
            category="bug",
            keywords=["off-by-one", "off by one", "page - 1", "start index", "wrong start", "pagination"],
        ),
        GroundTruthIssue(
            line_number=28,
            severity="medium",
            category="bug",
            keywords=["total_pages", "ceiling", "last page", "truncat", "missing page", "integer division"],
        ),
    ],
)


# ─── MEDIUM: security vulnerability ───────────────────────────────────────────

MEDIUM_DIFF = SeededDiff(
    task_name="detect_security_flaw",
    file_path="app/db/users.py",
    pr_context="feat: add user search endpoint for admin panel",
    diff="""\
--- a/app/db/users.py
+++ b/app/db/users.py
@@ -1,6 +1,7 @@
 import sqlite3
+import os
 
-DB_PATH = "/var/app/users.db"
+DB_PATH = os.getenv("DB_PATH", "/var/app/users.db")
 
 
 @@ -18,12 +19,18 @@ def get_user_by_id(user_id: int) -> dict | None:
 
 
+def search_users(query: str) -> list[dict]:
+    \"\"\"Search users by username for the admin panel.\"\"\"
+    conn = sqlite3.connect(DB_PATH)
+    cursor = conn.cursor()
+    sql = f"SELECT id, username, email FROM users WHERE username LIKE '%{query}%'"
+    cursor.execute(sql)
+    rows = cursor.fetchall()
+    conn.close()
+    return [{"id": r[0], "username": r[1], "email": r[2]} for r in rows]
+
+
 @@ -34,5 +41,11 @@ def update_user(user_id: int, data: dict) -> bool:
+
+SECRET_KEY = "hardcoded_jwt_secret_do_not_commit_abc123"
+
+def generate_token(user_id: int) -> str:
+    import jwt
+    return jwt.encode({"sub": user_id}, SECRET_KEY, algorithm="HS256")
""",
    ground_truth=[
        GroundTruthIssue(
            line_number=15,
            severity="critical",
            category="security",
            keywords=["sql injection", "sql", "f-string", "format string", "parameterized", "unsanitized", "injection"],
        ),
        GroundTruthIssue(
            line_number=24,
            severity="critical",
            category="security",
            keywords=["hardcoded", "secret", "hard-coded", "credential", "jwt secret", "plaintext secret"],
        ),
    ],
)


# ─── HARD: multi-file PR with 4 seeded issues ─────────────────────────────────

HARD_DIFF = SeededDiff(
    task_name="full_pr_review",
    file_path="multiple files",
    pr_context="feat: add file upload endpoint and background job processor",
    diff="""\
--- a/api/upload.py
+++ b/api/upload.py
@@ -0,0 +1,42 @@
+import os
+from pathlib import Path
+from flask import Flask, request, jsonify
+
+UPLOAD_DIR = "/uploads"
+app = Flask(__name__)
+
+ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf"}
+
+
+def allowed_file(filename: str) -> bool:
+    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
+
+
+@app.route("/upload", methods=["POST"])
+def upload_file():
+    f = request.files.get("file")
+    if not f or not allowed_file(f.filename):
+        return jsonify({"error": "invalid file"}), 400
+    dest = Path(UPLOAD_DIR) / f.filename
+    f.save(dest)
+    return jsonify({"path": str(dest)}), 200
+
+
--- a/workers/job_runner.py
+++ b/workers/job_runner.py
@@ -0,0 +1,38 @@
+import subprocess
+import logging
+
+logger = logging.getLogger(__name__)
+
+
+def run_job(job_id: str, command: str) -> dict:
+    \"\"\"Execute a user-provided job command.\"\"\"
+    result = subprocess.run(command, shell=True, capture_output=True, text=True)
+    logger.info(f"Job {job_id} stdout: {result.stdout}")
+    return {"exit_code": result.returncode, "output": result.stdout}
+
+
+--- a/utils/cache.py
++++ b/utils/cache.py
+@@ -12,8 +12,8 @@ def get_cached(key: str) -> bytes | None:
+     \"\"\"Retrieve item from cache.\"\"\"
+     try:
+         raw = _store.get(key)
+-        return raw
++        return pickle.loads(raw) if raw else None
+     except Exception:
+         return None
+
+
+--- a/config/settings.py
++++ b/config/settings.py
+@@ -5,4 +5,4 @@ import os
+ DEBUG = os.getenv("DEBUG", "false").lower() == "true"
+-DATABASE_URL = os.getenv("DATABASE_URL")
++DATABASE_URL = "postgresql://admin:supersecret123@prod-db.internal:5432/appdb"
""",
    ground_truth=[
        GroundTruthIssue(
            line_number=23,
            severity="high",
            category="security",
            keywords=["path traversal", "directory traversal", "filename", "sanitize", "secure_filename", "arbitrary path"],
        ),
        GroundTruthIssue(
            line_number=39,
            severity="critical",
            category="security",
            keywords=["command injection", "shell=True", "shell injection", "subprocess", "arbitrary command", "user-provided"],
        ),
        GroundTruthIssue(
            line_number=50,
            severity="critical",
            category="security",
            keywords=["pickle", "deserialization", "unsafe deserialization", "pickle.loads", "arbitrary code"],
        ),
        GroundTruthIssue(
            line_number=61,
            severity="critical",
            category="security",
            keywords=["hardcoded", "credential", "database url", "password", "plaintext", "connection string"],
        ),
    ],
)


TASK_REGISTRY: dict[str, SeededDiff] = {
    "detect_logic_bug": EASY_DIFF,
    "detect_security_flaw": MEDIUM_DIFF,
    "full_pr_review": HARD_DIFF,
}
