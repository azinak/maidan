"""أدوات الوكيل المقيّدة بمساحة العمل، مع سجل لكل ما يفعله."""

from __future__ import annotations

import json
import time
from pathlib import Path

from maidan.checks import run_tests
from maidan.paths import IGNORED_PARTS

MAX_READ = 60_000


class Sandbox:
    def __init__(self, trial_dir: Path) -> None:
        self.trial_dir = trial_dir
        self.root = (trial_dir / "workspace").resolve()
        self.log_path = trial_dir / "transcript.jsonl"
        self.stats = {"steps": 0, "reads": 0, "writes": 0, "test_runs": 0, "list_calls": 0,
                      "invalid_calls": 0, "write_before_read": 0, "tokens_in": 0, "tokens_out": 0}
        self.violations: list[str] = []
        self._read: set[str] = set()
        self.report: str | None = None

    # --- السجل ---
    def log(self, event: dict) -> None:
        event = {"t": round(time.time(), 2), **event}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            self.violations.append(rel)
            (self.trial_dir / "sandbox_violations.json").write_text(
                json.dumps(self.violations, ensure_ascii=False), encoding="utf-8")
            raise PermissionError(f"المسار خارج مساحة العمل: {rel}")
        return p

    # --- الأدوات ---
    def list_files(self) -> str:
        self.stats["list_calls"] += 1
        files = [p.relative_to(self.root).as_posix() for p in sorted(self.root.rglob("*"))
                 if p.is_file() and not (set(p.relative_to(self.root).parts) & IGNORED_PARTS)]
        return "\n".join(files)

    def read_file(self, path: str) -> str:
        p = self._path(path)
        if not p.is_file():
            raise FileNotFoundError(f"لا يوجد ملف: {path}")
        self.stats["reads"] += 1
        self._read.add(p.relative_to(self.root).as_posix())
        return p.read_text(encoding="utf-8")[:MAX_READ]

    def write_file(self, path: str, content: str) -> str:
        p = self._path(path)
        rel = p.relative_to(self.root).as_posix()
        if p.exists() and rel not in self._read:
            self.stats["write_before_read"] += 1
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        self.stats["writes"] += 1
        self._read.add(rel)
        return f"كُتب {rel} ({len(content)} حرفًا)"

    def run_tests(self) -> str:
        self.stats["test_runs"] += 1
        r = run_tests(self.root, self.root / "tests")
        lines = [f"ran {r['total']} tests, passed {len(r['passed'])}, failed {len(r['failed'])}"]
        if r.get("load_error"):
            lines.append(f"load error: {r['load_error']}")
        lines += [f"FAIL {f['test']}: {f['detail']}" for f in r["failed"][:15]]
        return "\n".join(lines)

    def finish(self, report: str) -> str:
        self.report = report
        (self.root / "REPORT.md").write_text(report.strip() + "\n", encoding="utf-8")
        return "تم استلام التقرير."

    def save_stats(self, **extra) -> None:
        data = {**self.stats, **extra}
        (self.trial_dir / "process.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
