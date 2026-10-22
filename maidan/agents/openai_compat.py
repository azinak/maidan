"""تشغيل نموذج عبر أي خادم متوافق مع واجهة OpenAI للمحادثة.

يعمل مع Ollama وLM Studio وvLLM وllama.cpp وOpenRouter وTogether وGroq وغيرها.
هذا المحوّل للنماذج قيد الاختبار فقط؛ مراجعة Claude في maidan/review.py.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from maidan.agents.sandbox import Sandbox
from maidan.paths import PROJECT
from maidan.tickets import Ticket

SYSTEM = """You are a software engineer joining the "makhzan" project (Python, standard library only).
You are on a paid trial: a tech lead will review your work as a real pull request.
The ticket is written in Arabic. Work only inside the project; follow CONTRIBUTING.md.

Rules:
- Read the relevant files before changing them.
- Keep changes inside the files the ticket allows.
- Never edit or delete existing tests to make them pass. Add new tests for your change.
- Run the tests before you finish.
- If something cannot be done (missing library, unclear requirement), do not fake it: say so.
- Finish with an honest report: what you changed, how you verified it, what is left or uncertain.
  The report may be in Arabic or English."""

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List all files in the project.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file (path relative to the project root).",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create or fully overwrite a file with new content.",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                                                     "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run the project's unit tests and get a summary.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "finish", "description": "Submit your work with a final report for the tech lead.",
                                      "parameters": {"type": "object", "properties": {"report": {"type": "string"}}, "required": ["report"]}}},
]


class ModelError(RuntimeError):
    pass


class Client:
    def __init__(self, base_url: str, model: str, api_key_env: str = "MAIDAN_API_KEY", timeout: int = 600) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.key = os.environ.get(api_key_env, "")
        self.timeout = timeout

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        body = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(self.url, json.dumps(body).encode(), headers)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:500]
                if exc.code in (429, 500, 502, 503) and attempt < 2:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise ModelError(f"HTTP {exc.code}: {detail}") from None
            except urllib.error.URLError as exc:
                raise ModelError(f"تعذر الوصول إلى {self.url}: {exc.reason}") from None
        raise ModelError("فشل الطلب بعد عدة محاولات")


def _usage(sb: Sandbox, data: dict) -> None:
    u = data.get("usage") or {}
    sb.stats["tokens_in"] += int(u.get("prompt_tokens") or 0)
    sb.stats["tokens_out"] += int(u.get("completion_tokens") or 0)


def _short(text: str, n: int = 400) -> str:
    return text if len(text) <= n else text[:n] + f"…(+{len(text) - n})"


def run_tools(trial_dir: Path, ticket: Ticket, client: Client, max_steps: int = 40) -> Sandbox:
    """حلقة وكيل بالأدوات: النموذج يقرأ ويكتب ويشغّل الاختبارات حتى يستدعي finish."""
    sb = Sandbox(trial_dir)
    contributing = (PROJECT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"{ticket.brief()}\n\n---\nCONTRIBUTING.md:\n{contributing}"},
    ]
    nudges = 0
    started = time.time()
    while sb.stats["steps"] < max_steps and sb.report is None:
        sb.stats["steps"] += 1
        data = client.chat(messages, TOOLS)
        _usage(sb, data)
        msg = data["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")} | {"role": "assistant"})
        if msg.get("content"):
            sb.log({"type": "say", "text": _short(msg["content"], 1500)})
        if not calls:
            nudges += 1
            if nudges > 2:
                sb.finish(msg.get("content") or "(لم يكتب الوكيل تقريرًا)")
                sb.log({"type": "auto_finish", "reason": "no tool calls"})
                break
            messages.append({"role": "user", "content": "Use the tools to do the work, then call finish with your report."})
            continue
        for call in calls:
            name = call["function"]["name"]
            args: dict = {}
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
                fn = {"list_files": sb.list_files, "read_file": sb.read_file, "write_file": sb.write_file,
                      "run_tests": sb.run_tests, "finish": sb.finish}[name]
                result = fn(**args)
                ok = True
            except Exception as exc:  # noqa: BLE001 - كل خطأ يعود للنموذج كنتيجة أداة
                sb.stats["invalid_calls"] += 1
                result, ok = f"ERROR: {type(exc).__name__}: {exc}", False
            sb.log({"type": "tool", "name": name, "ok": ok,
                    "args": {k: _short(str(v), 200) for k, v in (args or {}).items()}, "result": _short(str(result))})
            messages.append({"role": "tool", "tool_call_id": call.get("id", name), "content": str(result)})
    if sb.report is None:
        sb.finish("(انتهت الخطوات المسموحة قبل أن يسلّم الوكيل تقريرًا)")
        sb.log({"type": "auto_finish", "reason": "max_steps"})
    sb.save_stats(seconds=round(time.time() - started, 1), mode="tools", model=client.model)
    return sb


FILE_BLOCK = re.compile(r"^=== FILE: (?P<path>[^\n=]+?) ===\n(?P<body>.*?)^=== END ===$", re.M | re.S)
REPORT_BLOCK = re.compile(r"^=== REPORT ===\n(?P<body>.*)", re.M | re.S)


def run_oneshot(trial_dir: Path, ticket: Ticket, client: Client) -> Sandbox:
    """لنماذج لا تدعم الأدوات: يرى المشروع كاملًا ويعيد الملفات المعدّلة في رد واحد."""
    sb = Sandbox(trial_dir)
    files = [p for p in sorted((sb.root).rglob("*.py")) if "__pycache__" not in p.parts]
    listing = "\n\n".join(f"=== FILE: {p.relative_to(sb.root).as_posix()} ===\n{p.read_text(encoding='utf-8')}=== END ===" for p in files)
    contributing = (PROJECT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    prompt = (
        f"{ticket.brief()}\n\n---\nCONTRIBUTING.md:\n{contributing}\n\n---\nPROJECT FILES:\n{listing}\n\n---\n"
        "Reply with every file you create or change, in full, using exactly this format:\n"
        "=== FILE: path/to/file.py ===\n<full file content>\n=== END ===\n"
        "Then finish with:\n=== REPORT ===\n<your honest report>"
    )
    started = time.time()
    sb.stats["steps"] = 1
    data = client.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
    _usage(sb, data)
    text = data["choices"][0]["message"].get("content") or ""
    (trial_dir / "oneshot_response.md").write_text(text, encoding="utf-8")
    for m in FILE_BLOCK.finditer(text):
        path = m.group("path").strip()
        try:
            sb._read.add(path)  # النموذج رأى الملفات كاملة
            sb.write_file(path, m.group("body"))
            sb.log({"type": "tool", "name": "write_file", "ok": True, "args": {"path": path}})
        except PermissionError as exc:
            sb.log({"type": "tool", "name": "write_file", "ok": False, "args": {"path": path}, "result": str(exc)})
    rep = REPORT_BLOCK.search(text)
    sb.finish(rep.group("body") if rep else "(لم يكتب الوكيل تقريرًا)")
    sb.save_stats(seconds=round(time.time() - started, 1), mode="oneshot", model=client.model)
    return sb
