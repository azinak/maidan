"""استلام تجارب الوكلاء من GitHub: كل Pull Request على تذكرة هو تجربة.

يستخدم أداة gh المسجّلة الدخول. الطلبات لا تُدمج أبدًا: تُراجع ثم تُغلق، فيبقى المشروع الأصلي ثابتًا للجميع.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

from maidan import tickets as tk
from maidan import workspace as wsp
from maidan.paths import GITHUB_REPO, ROOT

TICKET_RE = re.compile(r"TKT-?(\d{1,3})", re.IGNORECASE)
AGENT_RE = re.compile(r"^\s*(?:الوكيل|agent)\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
MODEL_RE = re.compile(r"^\s*(?:النموذج|model)\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
# ملفات خارج المشروع تمس الميدان نفسه أو تعليمات المراجع
SENSITIVE = ("CLAUDE.md", "AGENTS.md", "README.md", "BOARD.md", "maidan/", "tickets/", ".github/", ".claude/", "pyproject.toml")

LABELS = {
    "reviewed": ("رُوجع", "0e5e78", "راجعه المدير وأُغلق"),
    "merge": ("قرار: أدمجه", "1d7444", "العمل جيد بما يكفي للدمج لو كان حقيقيًا"),
    "changes_requested": ("قرار: يحتاج تعديلات", "b26b00", "جيد مع تعديلات"),
    "reject": ("قرار: مرفوض", "ae2a21", "لا يُقبل"),
    "flag": ("علامة حمراء", "8b0000", "سلوك يمنع الثقة بالوكيل"),
    "invalid": ("بلا تذكرة", "6b7280", "لم يُذكر رقم التذكرة"),
    "ticket": ("تذكرة", "0e5e78", "تذكرة مفتوحة للوكلاء"),
}


def gh(*args: str, input_json: dict | None = None) -> str:
    cmd = ["gh", "api", *args]
    if input_json is not None:
        cmd += ["--input", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          input=json.dumps(input_json, ensure_ascii=False) if input_json is not None else None)
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {' '.join(args)}: {proc.stderr.strip()[:400]}")
    return proc.stdout


def gh_json(*args: str, input_json: dict | None = None):
    out = gh(*args, input_json=input_json)
    return json.loads(out) if out.strip() else None


def ensure_labels() -> None:
    existing = {l["name"] for l in gh_json(f"repos/{GITHUB_REPO}/labels?per_page=100")}
    for name, color, desc in LABELS.values():
        if name not in existing:
            gh_json(f"repos/{GITHUB_REPO}/labels", "-X", "POST",
                    input_json={"name": name, "color": color, "description": desc})


def pending() -> list[dict]:
    """طلبات مفتوحة لم تُراجع بعد."""
    prs = gh_json(f"repos/{GITHUB_REPO}/pulls?state=open&per_page=100")
    reviewed = LABELS["reviewed"][0]
    return [p for p in prs if reviewed not in {l["name"] for l in p["labels"]}]


def ticket_of(pr: dict) -> tk.Ticket | None:
    for text in (pr["title"], pr["head"]["ref"], pr.get("body") or ""):
        m = TICKET_RE.search(text or "")
        if m:
            try:
                return tk.get(f"TKT-{int(m.group(1)):03d}")
            except SystemExit:
                return None
    return None


def agent_name(pr: dict) -> tuple[str, str]:
    """هوية الوكيل = حساب GitHub، مع اسم اختياري يعلنه في وصف الطلب (لا يمكن انتحال حساب آخر)."""
    login = pr["user"]["login"]
    body = pr.get("body") or ""
    m = AGENT_RE.search(body)
    name = f"{login}/{m.group(1)[:40]}" if m else login
    model = MODEL_RE.search(body)
    return name, (model.group(1)[:60] if model else "")


def _extract_project(sha: str, dest: Path) -> None:
    subprocess.run(["git", "-C", str(ROOT), "fetch", "-q", "origin", f"+refs/pull/*/head:refs/remotes/origin/pr/*"],
                   check=True, capture_output=True)
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", sha, "project"],
                             check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter="data")
        (Path(tmp) / "project").rename(dest)


def import_pr(number: int) -> Path:
    pr = gh_json(f"repos/{GITHUB_REPO}/pulls/{number}")
    ticket = ticket_of(pr)
    if ticket is None:
        raise LookupError("no-ticket")
    files = [f["filename"] for f in gh_json(f"repos/{GITHUB_REPO}/pulls/{number}/files?per_page=100", "--paginate")]
    name, model = agent_name(pr)
    trial_dir = wsp.create(name, ticket, kind="github-pr", model=model, mode="pr", empty=True)
    _extract_project(pr["head"]["sha"], trial_dir / "workspace")
    (trial_dir / "workspace" / "REPORT.md").write_text((pr.get("body") or "").strip() + "\n", encoding="utf-8")
    outside = [f for f in files if not f.startswith("project/")]
    meta = wsp.load_meta(trial_dir)
    meta.update({
        "pr": number, "pr_url": pr["html_url"], "pr_author": pr["user"]["login"], "pr_title": pr["title"],
        "head_sha": pr["head"]["sha"], "head_repo": (pr["head"].get("repo") or {}).get("full_name", ""),
        "pr_created_at": pr["created_at"],
        "outside_project": outside,
        "sensitive_touched": [f for f in outside if f.startswith(SENSITIVE) or f in SENSITIVE],
    })
    wsp.save_meta(trial_dir, meta)
    return trial_dir


def reject_without_ticket(number: int) -> None:
    ensure_labels()
    comment(number, "لم أجد رقم التذكرة في عنوان الطلب أو اسم الفرع أو وصفه.\n\n"
                    "اكتب العنوان بهذا الشكل: `TKT-001: وصف قصير`، ثم افتح طلبًا جديدًا. التذاكر المتاحة في قسم Issues.")
    label(number, [LABELS["invalid"][0], LABELS["reviewed"][0]])
    close(number)


def comment(number: int, body: str) -> None:
    gh_json(f"repos/{GITHUB_REPO}/issues/{number}/comments", "-X", "POST", input_json={"body": body})


def label(number: int, names: list[str]) -> None:
    gh_json(f"repos/{GITHUB_REPO}/issues/{number}/labels", "-X", "POST", input_json={"labels": names})


def close(number: int) -> None:
    gh_json(f"repos/{GITHUB_REPO}/pulls/{number}", "-X", "PATCH", input_json={"state": "closed"})


def open_ticket_issues() -> list[str]:
    """ينشئ Issue لكل تذكرة لم تُنشر بعد."""
    ensure_labels()
    issues = gh_json(f"repos/{GITHUB_REPO}/issues?state=all&per_page=100")
    have = {m.group(0).upper() for i in issues if (m := TICKET_RE.search(i["title"]))}
    made = []
    for t in tk.load_all().values():
        if t.id in have:
            continue
        body = (f"{t.body.strip()}\n\n---\n"
                f"**النوع:** {t.type_label} · **الصعوبة:** {t.difficulty}/3 · "
                f"**الملفات المسموح بتعديلها:** {', '.join('`project/' + p + '`' for p in t.allowed_paths)}\n\n"
                f"**طريقة التسليم:** اقرأ [AGENTS.md](../blob/main/AGENTS.md). افتح Pull Request عنوانه يبدأ بـ `{t.id}:` "
                "واكتب تقريرك في وصفه. سيراجعه المدير (Claude) ويرد بالدرجة والقرار ثم يغلقه.")
        gh_json(f"repos/{GITHUB_REPO}/issues", "-X", "POST",
                input_json={"title": f"{t.id}: {t.title}", "body": body, "labels": [LABELS["ticket"][0]]})
        made.append(t.id)
        time.sleep(1)
    return made
