"""يشغّل اختبارات unittest ويطبع النتيجة JSON. يُستدعى في عملية منفصلة.

python _runner.py <root> <start_dir>
"""

import json
import sys
import unittest

root, start = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)


class _Collect(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())


loader = unittest.TestLoader()
out = {"total": 0, "passed": [], "failed": [], "load_error": None}
try:
    suite = loader.discover(start, top_level_dir=root)
except Exception as exc:  # noqa: BLE001 - كل خطأ تحميل يُسجَّل
    out["load_error"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(out, ensure_ascii=False))
    raise SystemExit(0)

with open("/dev/null", "w") if sys.platform != "win32" else open("nul", "w") as sink:
    runner = unittest.TextTestRunner(stream=sink, resultclass=_Collect, verbosity=0)
    result = runner.run(suite)

out["total"] = result.testsRun
out["passed"] = result.passed
for test, tb in result.failures + result.errors:
    out["failed"].append({"test": test.id(), "detail": tb.strip().splitlines()[-1][:300]})
for test, _reason in result.skipped:
    out["failed"].append({"test": test.id(), "detail": "skipped"})
# أخطاء الاستيراد تظهر كاختبار _FailedTest
print(json.dumps(out, ensure_ascii=False))
