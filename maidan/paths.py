import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "project"
TICKETS = ROOT / "tickets"

# الجزء الخاص (اختبارات القبول، والحلول المرجعية، وسجل التجارب) في مستودع منفصل لا يراه الوكلاء
HIDDEN = Path(os.environ.get("MAIDAN_HIDDEN", ROOT.parent / "maidan-hidden")).resolve()
ACCEPTANCE = HIDDEN / "acceptance"
REFERENCE = HIDDEN / "reference"
TRIALS = Path(os.environ.get("MAIDAN_TRIALS", HIDDEN / "trials")).resolve()

GITHUB_REPO = os.environ.get("MAIDAN_GITHUB_REPO", "azinak/maidan")

# ملفات يضعها الميدان داخل مساحة العمل وليست جزءًا من عمل الوكيل
WORKSPACE_META = {"BRIEF.md", "REPORT.md"}
IGNORED_PARTS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".aider.tags.cache.v3"}


def require_hidden() -> None:
    if not ACCEPTANCE.is_dir():
        raise SystemExit(
            f"لم أجد الاختبارات المخفية في {HIDDEN}.\n"
            "انسخ المستودع الخاص بجوار هذا المستودع:  git clone https://github.com/azinak/maidan-hidden ../maidan-hidden\n"
            "أو حدّد مكانه بالمتغير MAIDAN_HIDDEN."
        )
