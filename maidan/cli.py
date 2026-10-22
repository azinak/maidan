"""واجهة سطر الأوامر: python -m maidan <أمر>"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from maidan import checks, review, scoring
from maidan import tickets as tk
from maidan import workspace as wsp
from maidan.agents import scripted
from maidan.paths import ACCEPTANCE, HIDDEN, PROJECT, ROOT, require_hidden
from maidan.report import agent_dir, pr_comment, verdict_summary, write_board, write_public_board, write_verdict


def _pick_tickets(spec: str) -> list[tk.Ticket]:
    if spec in ("all", ""):
        return list(tk.load_all().values())
    return [tk.get(s.strip()) for s in spec.split(",") if s.strip()]


def _print_grade(trial_dir: Path, g: dict) -> None:
    acc, reg = g["acceptance"], g["regression"]
    print(f"  القبول {len(acc['passed'])}/{acc['total']} · الانحدار {len(reg['passed'])}/{reg['total']} · "
          f"اختبارات جديدة {g['new_tests']} · الدرجة الآلية {g['auto_score']}/10")
    for f in g["flags"]:
        print(f"  ⚑ {f['label']}: {f['evidence']}")
    for w in g["warnings"]:
        print(f"  ! {w}")


def _grade(trial_dir: Path) -> dict:
    meta = wsp.load_meta(trial_dir)
    g = checks.grade(trial_dir, tk.get(meta["ticket"]))
    meta["status"] = "graded"
    meta.setdefault("finished_at", time.time())
    wsp.save_meta(trial_dir, meta)
    return g


def _review(trial_dir: Path, how: str) -> None:
    ticket = tk.get(wsp.load_meta(trial_dir)["ticket"])
    if how == "none":
        return
    if how == "api":
        r = review.review_with_api(trial_dir, ticket)
        print(f"  مراجعة المدير: {r['score']}/10 · {r['decision']} · {r['summary']}")
        return
    path = review.write_packet(trial_dir, ticket)
    print(f"  حزمة المراجعة: {path}")
    print(f"  للمراجعة افتح Claude Code في {ROOT} واكتب: راجع التجربة {trial_dir.name}")


# ---------- الأوامر ----------

def cmd_tickets(a) -> None:
    for t in tk.load_all().values():
        print(f"{t.id}  [{t.type_label} · صعوبة {t.difficulty} · وزن {t.weight}]  {t.title}")


def cmd_run(a) -> None:
    from maidan.agents import openai_compat as oc

    client = oc.Client(a.base_url, a.model, a.api_key_env)
    for t in _pick_tickets(a.tickets):
        trial_dir = wsp.create(a.agent, t, kind="openai", model=a.model, mode=a.mode)
        print(f"\n▶ {t.id} {t.title}\n  التجربة: {trial_dir.name}")
        try:
            sb = oc.run_tools(trial_dir, t, client, a.max_steps) if a.mode == "tools" else oc.run_oneshot(trial_dir, t, client)
        except oc.ModelError as exc:
            print(f"  ✗ فشل الاتصال بالنموذج: {exc}")
            if a.mode == "tools" and "tool" in str(exc).lower():
                print("  النموذج أو الخادم لا يدعم الأدوات على ما يبدو. جرّب --mode oneshot")
            shutil.rmtree(trial_dir)
            continue
        print(f"  خطوات {sb.stats['steps']} · قراءات {sb.stats['reads']} · كتابات {sb.stats['writes']} · تشغيل اختبارات {sb.stats['test_runs']}")
        _print_grade(trial_dir, _grade(trial_dir))
        _review(trial_dir, a.review)
    _board_note()


def cmd_scripted(a) -> None:
    for t in _pick_tickets(a.tickets):
        trial_dir = wsp.create(a.agent, t, kind=f"scripted:{a.kind}", model="scripted", mode=a.kind)
        scripted.run(trial_dir, t, a.kind)
        print(f"\n▶ {t.id} · {trial_dir.name}")
        _print_grade(trial_dir, _grade(trial_dir))
        _review(trial_dir, a.review)
    _board_note()


def cmd_open(a) -> None:
    t = tk.get(a.ticket)
    trial_dir = wsp.create(a.agent, t, kind="manual", model=a.model or "", mode="manual")
    ws = trial_dir / "workspace"
    print(f"التجربة: {trial_dir.name}\nمساحة العمل: {ws}\n")
    print("1) شغّل وكيلك داخل هذا المجلد، وأعطه محتوى BRIEF.md كما هو. أمثلة:")
    print(f"     cd {ws} && aider --message-file BRIEF.md")
    print(f"     cd {ws} && codex \"$(cat BRIEF.md)\"")
    print("   أو افتح المجلد في Cursor أو Cline أو أي أداة، والصق BRIEF.md في المحادثة.")
    print("2) تأكد أن الوكيل كتب تقريره في REPORT.md (أو انسخ رده النهائي إليه).")
    print(f"3) سلّم العمل: python -m maidan submit {trial_dir.name}")


def cmd_submit(a) -> None:
    trial_dir = wsp.resolve(a.trial)
    meta = wsp.load_meta(trial_dir)
    meta["finished_at"] = time.time()
    meta["seconds"] = round(meta["finished_at"] - meta["started_at"], 1)
    wsp.save_meta(trial_dir, meta)
    if a.report_file:
        shutil.copy(a.report_file, trial_dir / "workspace" / "REPORT.md")
    print(f"▶ {trial_dir.name}")
    _print_grade(trial_dir, _grade(trial_dir))
    _review(trial_dir, a.review)
    _board_note()


def cmd_grade(a) -> None:
    trial_dir = wsp.resolve(a.trial)
    _print_grade(trial_dir, _grade(trial_dir))


def cmd_review(a) -> None:
    trial_dir = wsp.resolve(a.trial)
    if not (trial_dir / "grade.json").exists():
        _grade(trial_dir)
    _review(trial_dir, "api" if a.api else "packet")


def cmd_finalize(a) -> None:
    """يتحقق من review.json الذي كتبه Claude Code ويعرض الدرجة النهائية."""
    trial_dir = wsp.resolve(a.trial)
    path = trial_dir / "review.json"
    if not path.exists():
        raise SystemExit(f"لا يوجد {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in review.SCHEMA["required"] if k not in data]
    if missing:
        raise SystemExit(f"review.json ينقصه: {', '.join(missing)}")
    kinds = review.SCHEMA["properties"]["red_flags"]["items"]["properties"]["kind"]["enum"]
    bad = [f for f in data["red_flags"] if f.get("kind") not in kinds]
    if bad:
        raise SystemExit(f"أنواع علامات غير معروفة: {bad}")
    data.setdefault("reviewer", "claude-code")
    review.save_review(trial_dir, data)
    r = scoring.trial_result(trial_dir)
    print(f"{trial_dir.name}: الدرجة النهائية {r['score']}/10 (آلي {r['auto']} · مدير {r['review']})")
    write_board()


def cmd_verdict(a) -> None:
    slug = wsp._slug(a.agent)
    allv = scoring.agents()
    if slug not in allv:
        raise SystemExit(f"لا توجد تجارب مقيّمة للوكيل {a.agent}. المتاح: {', '.join(allv) or 'لا شيء'}")
    v = allv[slug]
    summary = verdict_summary(v)
    (agent_dir(slug) / "summary.txt").write_text(summary, encoding="utf-8")
    if a.api:
        letter = review.letter_with_api(summary)
        (agent_dir(slug) / "letter.json").write_text(json.dumps(letter, ensure_ascii=False, indent=2), encoding="utf-8")
    path = write_verdict(v)
    print(summary)
    print(f"\nالحكم: {path}")
    if not a.api and not (agent_dir(slug) / "letter.json").exists():
        print(f"لخطاب Claude الشخصي: افتح Claude Code هنا واكتب «اكتب حكمك على الوكيل {a.agent}»، أو استخدم --api")


def cmd_board(a) -> None:
    md, html_path = write_board()
    print(md.read_text(encoding="utf-8"))
    print(f"اللوحة المرئية: {html_path}")


def _board_note() -> None:
    md, html_path = write_board()
    print(f"\nاللوحة: {md} · {html_path}")


def cmd_selftest(a) -> None:
    """يتحقق أن كل تذكرة قابلة للقياس: الأصل يفشل في القبول والحل المرجعي ينجح."""
    require_hidden()
    ok = True
    base = checks.run_tests(PROJECT, PROJECT / "tests")
    print(f"اختبارات المشروع الأصلية: {len(base['passed'])}/{base['total']}")
    ok &= base["total"] > 0 and not base["failed"]
    for t in tk.load_all().values():
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copytree(PROJECT / "makhzan", tmp / "makhzan")
            shutil.copytree(ACCEPTANCE / t.id, tmp / "acceptance")
            (tmp / "acceptance" / "__init__.py").touch()
            before = checks.run_tests(tmp, tmp / "acceptance")
            scripted.apply_reference(tmp, t.id)
            after = checks.run_tests(tmp, tmp / "acceptance")
            shutil.copytree(PROJECT / "tests", tmp / "tests")
            reg = checks.run_tests(tmp, tmp / "tests")
        expect_fail = t.id != "TKT-006"  # تذكرة الأمانة: الأصل يجتازها، والقياس الحقيقي في المراجعة
        good = (before["ratio"] < 1 or not expect_fail) and after["ratio"] == 1 and reg["ratio"] == 1
        ok &= good
        print(f"{'✓' if good else '✗'} {t.id}: الأصل {len(before['passed'])}/{before['total']} · "
              f"المرجعي {len(after['passed'])}/{after['total']} · الانحدار {len(reg['passed'])}/{reg['total']}")
        for f in after["failed"]:
            print(f"    {f['test']}: {f['detail']}")
    print("الميدان سليم." if ok else "يوجد خلل في الميدان.")
    if not ok:
        raise SystemExit(1)


# ---------- GitHub ----------

def cmd_issues(a) -> None:
    from maidan import github

    made = github.open_ticket_issues()
    print("أُنشئت: " + ", ".join(made) if made else "كل التذاكر منشورة مسبقًا.")


def cmd_prs(a) -> None:
    from maidan import github

    prs = github.pending()
    if not prs:
        print("لا توجد طلبات جديدة.")
    for p in prs:
        t = github.ticket_of(p)
        print(f"#{p['number']}  @{p['user']['login']}  {t.id if t else 'بلا تذكرة'}  {p['title']}")


def cmd_pr(a) -> None:
    """يستورد طلبًا كتجربة، ويفحصه آليًا، ويجهّز حزمة المراجعة."""
    from maidan import github

    try:
        trial_dir = github.import_pr(a.number)
    except LookupError:
        github.reject_without_ticket(a.number)
        print(f"#{a.number}: بلا رقم تذكرة، أُغلق مع تعليق.")
        return
    print(f"▶ #{a.number} → {trial_dir.name}")
    _print_grade(trial_dir, _grade(trial_dir))
    path = review.write_packet(trial_dir, tk.get(wsp.load_meta(trial_dir)["ticket"]))
    print(f"  حزمة المراجعة: {path}")


def cmd_publish(a) -> None:
    """ينشر المراجعة على الطلب، ويضع الوسوم، ويغلقه، ويحدّث اللوحات."""
    from maidan import github

    trial_dir = wsp.resolve(a.trial)
    meta = wsp.load_meta(trial_dir)
    if "pr" not in meta:
        raise SystemExit("هذه التجربة ليست من GitHub.")
    if not (trial_dir / "review.json").exists():
        raise SystemExit("لا توجد مراجعة بعد. اكتب review.json ثم شغّل finalize.")
    github.ensure_labels()
    r = scoring.trial_result(trial_dir)
    rv = json.loads((trial_dir / "review.json").read_text(encoding="utf-8"))
    names = [github.LABELS["reviewed"][0], github.LABELS[rv["decision"]][0]]
    if r["flags"]:
        names.append(github.LABELS["flag"][0])
    github.comment(meta["pr"], pr_comment(trial_dir))
    github.label(meta["pr"], names)
    github.close(meta["pr"])
    meta["published_at"] = time.time()
    wsp.save_meta(trial_dir, meta)
    v = scoring.agents().get(r["agent_slug"])
    if v:
        write_verdict(v)
    board = write_public_board()
    print(f"#{meta['pr']}: نُشرت المراجعة ({r['score']}/10) وأُغلق الطلب. اللوحة العامة: {board}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="maidan", description="تجارب ميدانية لوكلاء البرمجة، يديرها Claude")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tickets", help="اعرض التذاكر").set_defaults(fn=cmd_tickets)

    r = sub.add_parser("run", help="شغّل نموذجًا عبر خادم متوافق مع OpenAI على تذكرة أو أكثر")
    r.add_argument("--agent", required=True, help="اسم الوكيل كما سيظهر في اللوحة")
    r.add_argument("--model", required=True)
    r.add_argument("--base-url", default="http://localhost:11434/v1", help="الافتراضي Ollama المحلي")
    r.add_argument("--api-key-env", default="MAIDAN_API_KEY", help="اسم متغير البيئة الذي يحمل مفتاح الخادم")
    r.add_argument("--mode", choices=["tools", "oneshot"], default="tools")
    r.add_argument("--tickets", default="all", help="all أو قائمة مثل TKT-001,TKT-004")
    r.add_argument("--max-steps", type=int, default=40)
    r.add_argument("--review", choices=["packet", "api", "none"], default="packet")
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("scripted", help="وكلاء مبرمجون لمعايرة الميدان")
    s.add_argument("--agent", required=True)
    s.add_argument("--kind", choices=scripted.KINDS, required=True)
    s.add_argument("--tickets", default="all")
    s.add_argument("--review", choices=["packet", "api", "none"], default="none")
    s.set_defaults(fn=cmd_scripted)

    o = sub.add_parser("open", help="افتح تجربة يدوية لأي وكيل (Aider، Codex، Cursor…)")
    o.add_argument("--agent", required=True)
    o.add_argument("--ticket", required=True)
    o.add_argument("--model", default="")
    o.set_defaults(fn=cmd_open)

    sm = sub.add_parser("submit", help="سلّم تجربة يدوية للفحص")
    sm.add_argument("trial")
    sm.add_argument("--report-file", help="ملف يحوي تقرير الوكيل النهائي")
    sm.add_argument("--review", choices=["packet", "api", "none"], default="packet")
    sm.set_defaults(fn=cmd_submit)

    g = sub.add_parser("grade", help="أعد الفحص الآلي لتجربة")
    g.add_argument("trial")
    g.set_defaults(fn=cmd_grade)

    rv = sub.add_parser("review", help="جهّز حزمة المراجعة أو راجع عبر Claude API")
    rv.add_argument("trial")
    rv.add_argument("--api", action="store_true")
    rv.set_defaults(fn=cmd_review)

    f = sub.add_parser("finalize", help="اعتمد review.json الذي كتبه Claude Code")
    f.add_argument("trial")
    f.set_defaults(fn=cmd_finalize)

    v = sub.add_parser("verdict", help="الحكم النهائي على وكيل")
    v.add_argument("agent")
    v.add_argument("--api", action="store_true", help="اطلب خطاب الحكم من Claude عبر API")
    v.set_defaults(fn=cmd_verdict)

    sub.add_parser("board", help="لوحة المتصدرين").set_defaults(fn=cmd_board)
    sub.add_parser("issues", help="انشر التذاكر كـ Issues على GitHub").set_defaults(fn=cmd_issues)
    sub.add_parser("prs", help="الطلبات الجديدة على GitHub التي لم تُراجع").set_defaults(fn=cmd_prs)
    pr = sub.add_parser("pr", help="استورد Pull Request كتجربة وافحصه")
    pr.add_argument("number", type=int)
    pr.set_defaults(fn=cmd_pr)
    pb = sub.add_parser("publish", help="انشر المراجعة على الطلب وأغلقه")
    pb.add_argument("trial")
    pb.set_defaults(fn=cmd_publish)
    sub.add_parser("selftest", help="تحقق من سلامة التذاكر والاختبارات المخفية").set_defaults(fn=cmd_selftest)

    args = p.parse_args(argv)
    args.fn(args)
    return 0
