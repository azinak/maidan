"""قراءة التذاكر من ملفات Markdown ذات الترويسة."""

from __future__ import annotations

from dataclasses import dataclass

from maidan.paths import TICKETS

TYPE_LABELS = {"bug": "إصلاح خلل", "feature": "ميزة جديدة", "integration": "تكامل خارجي", "refactor": "إعادة هيكلة"}


@dataclass(frozen=True)
class Ticket:
    id: str
    title: str
    type: str
    difficulty: int
    weight: float
    allowed_paths: tuple[str, ...]
    review_weight: float
    body: str

    @property
    def type_label(self) -> str:
        return TYPE_LABELS.get(self.type, self.type)

    def allows(self, rel_path: str) -> bool:
        return any(rel_path == p or rel_path.startswith(p.rstrip("/") + "/") or
                   (p.endswith("/") and rel_path.startswith(p)) for p in self.allowed_paths)

    def brief(self) -> str:
        return f"# {self.id}: {self.title}\n\n{self.body.strip()}\n\nالملفات المسموح بتعديلها: {', '.join(self.allowed_paths)}\n"


def _parse(text: str) -> Ticket:
    if not text.startswith("---"):
        raise ValueError("التذكرة بلا ترويسة")
    _, head, body = text.split("---", 2)
    meta: dict[str, str] = {}
    for line in head.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return Ticket(
        id=meta["id"],
        title=meta["title"],
        type=meta.get("type", "feature"),
        difficulty=int(meta.get("difficulty", "1")),
        weight=float(meta.get("weight", "1")),
        allowed_paths=tuple(p.strip() for p in meta.get("allowed_paths", "").split(",") if p.strip()),
        review_weight=float(meta.get("review_weight", "0.4")),
        body=body,
    )


def load_all() -> dict[str, Ticket]:
    tickets = {}
    for path in sorted(TICKETS.glob("TKT-*.md")):
        t = _parse(path.read_text(encoding="utf-8"))
        tickets[t.id] = t
    return tickets


def get(ticket_id: str) -> Ticket:
    tickets = load_all()
    key = ticket_id.upper()
    if not key.startswith("TKT-"):
        key = f"TKT-{int(key):03d}"
    if key not in tickets:
        raise SystemExit(f"لا توجد تذكرة {ticket_id}. المتاح: {', '.join(tickets)}")
    return tickets[key]
