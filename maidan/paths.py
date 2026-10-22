from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "project"
TICKETS = ROOT / "tickets"
ACCEPTANCE = ROOT / "acceptance"
REFERENCE = ROOT / "reference"
TRIALS = ROOT / "trials"

# ملفات يضعها الميدان داخل مساحة العمل وليست جزءًا من عمل الوكيل
WORKSPACE_META = {"BRIEF.md", "REPORT.md"}
IGNORED_PARTS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".aider.tags.cache.v3"}
