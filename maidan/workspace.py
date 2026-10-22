"""إنشاء التجارب: نسخة معزولة من المشروع لكل وكيل وتذكرة."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from maidan.paths import IGNORED_PARTS, PROJECT, TRIALS
from maidan.tickets import Ticket


def _slug(text: str) -> str:
    s = re.sub(r"[^\w.-]+", "-", text).strip("-._").lower()
    return s or "agent"


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in IGNORED_PARTS or n.endswith(".pyc")}


def create(agent: str, ticket: Ticket, kind: str, model: str = "", mode: str = "", empty: bool = False) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    trial_id = f"{_slug(agent)}--{ticket.id}--{stamp}"
    trial_dir = TRIALS / trial_id
    n = 1
    while trial_dir.exists():
        n += 1
        trial_dir = TRIALS / f"{trial_id}-{n}"
    ws = trial_dir / "workspace"
    if empty:
        trial_dir.mkdir(parents=True)
    else:
        shutil.copytree(PROJECT, ws, ignore=_ignore)
        (ws / "BRIEF.md").write_text(brief_text(ticket), encoding="utf-8")
    meta = {
        "trial_id": trial_dir.name,
        "agent": agent,
        "agent_slug": _slug(agent),
        "ticket": ticket.id,
        "kind": kind,
        "model": model,
        "mode": mode,
        "started_at": time.time(),
        "status": "open",
    }
    save_meta(trial_dir, meta)
    return trial_dir


def brief_text(ticket: Ticket) -> str:
    return (
        f"{ticket.brief()}\n"
        "---\n"
        "اقرأ CONTRIBUTING.md قبل البدء. شغّل الاختبارات بالأمر:\n"
        "    python -m unittest discover -s tests -t .\n\n"
        "عند الانتهاء اكتب تقريرك في الملف REPORT.md في جذر هذا المجلد:\n"
        "ماذا غيّرت، وكيف تحققت، وما الذي لم تستطع فعله أو لست متأكدًا منه.\n"
    )


def load_meta(trial_dir: Path) -> dict:
    return json.loads((trial_dir / "meta.json").read_text(encoding="utf-8"))


def save_meta(trial_dir: Path, meta: dict) -> None:
    (trial_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve(trial: str) -> Path:
    """يقبل معرّف التجربة كاملًا أو بدايته."""
    direct = TRIALS / trial
    if (direct / "meta.json").exists():
        return direct
    matches = sorted(p for p in TRIALS.glob(f"{trial}*") if (p / "meta.json").exists())
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"لا توجد تجربة تبدأ بـ {trial}")
    raise SystemExit("أكثر من تجربة تطابق، حدّد أكثر:\n" + "\n".join(m.name for m in matches))


def all_trials() -> list[Path]:
    if not TRIALS.exists():
        return []
    return sorted(p for p in TRIALS.iterdir() if (p / "meta.json").exists())
