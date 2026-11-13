"""Run every cell of the built index.html in local Python, using the page's own runner.

    .venv/bin/python tests/test_cells.py            # all modules
    .venv/bin/python tests/test_cells.py module-5   # one module

Pass rules
- example:   runs without an error (cells marked "demo error" in their code must error)
- exercise:  solution + check passes; starter + check fails
- bug:       buggy code + check fails; fixed code + check passes
- colab:     parses as Python (lines starting with ! or % are notebook commands and are skipped)
Results are written to tests/results.json so a failed run can be inspected.
"""
import ast
import json
import os
import re
import sys
from pathlib import Path

os.environ["MPLBACKEND"] = "AGG"
ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / "index.html").read_text(encoding="utf-8")
m = re.search(r'<script type="application/json" id="course-data">(.*?)</script>', html, re.S)
if not m:
    sys.exit("Could not find course data in index.html")
data = json.loads(m.group(1))

ns = {"__name__": "course_runner"}
exec(compile(data["runner"], "runner.py", "exec"), ns)
run_cell = ns["run_cell"]

# Example cells that are meant to show an error (lesson demos). Matched by text in the code.
DEMO_ERROR_MARK = "run me"

only = sys.argv[1] if len(sys.argv) > 1 else None
results, failures = [], []


def run(setup, code, check=None):
    return json.loads(run_cell(setup, code, check))


for mod in data["modules"]:
    if only and mod["id"] != only:
        continue
    setup = mod.get("setup", "")
    for lesson in mod["lessons"]:
        for b in lesson["blocks"]:
            t, cid = b["type"], b["id"]
            label = f"{cid} [{t}] {b.get('title', '')}".strip()
            problems = []
            if t == "example":
                r = run(setup, b["code"])
                expect_error = DEMO_ERROR_MARK in b["code"]
                if r["setup_error"]:
                    problems.append("setup failed: " + r["setup_error"])
                elif expect_error and not r["error"]:
                    problems.append("demo was meant to raise an error but did not")
                elif not expect_error and r["error"]:
                    problems.append(f"error: {r['error']['type']}: {r['error']['message']} (line {r['error']['line']})")
                if r["stderr"].strip() and not expect_error:
                    problems.append("warning printed: " + r["stderr"].strip()[:200])
            elif t in ("exercise", "bug"):
                before = b["starter"] if t == "exercise" else b["code"]
                r1 = run(setup, before, b["check"])
                r2 = run(setup, b["solution"], b["check"])
                if r1["setup_error"] or r2["setup_error"]:
                    problems.append("setup failed: " + (r1["setup_error"] or r2["setup_error"]))
                if r1["check"]["ok"]:
                    problems.append(("starter" if t == "exercise" else "buggy code") + " PASSES the check (it should fail)")
                if not r2["check"]["ok"]:
                    err = r2["error"]
                    detail = f"{err['type']}: {err['message']} (line {err['line']})" if err else r2["check"]["reason"]
                    problems.append("solution FAILS: " + detail)
                if r2["stderr"].strip():
                    problems.append("solution printed a warning: " + r2["stderr"].strip()[:200])
                results.append({"id": cid, "before_reason": r1["check"]["reason"]})
            elif t == "colab":
                code = "\n".join(l for l in b["code"].splitlines() if not l.lstrip().startswith(("!", "%")))
                try:
                    ast.parse(code)
                except SyntaxError as e:
                    problems.append(f"colab code does not parse: {e}")
            else:
                continue
            status = "FAIL" if problems else "ok"
            print(f"{status:4}  {label}")
            for p in problems:
                print("      - " + p)
            if problems:
                failures.append({"id": cid, "problems": problems})

(ROOT / "tests" / "results.json").write_text(json.dumps({"failures": failures, "checks": results}, indent=2))
print()
print(f"{len(failures)} failing cell(s)" if failures else "All cells passed.")
sys.exit(1 if failures else 0)
