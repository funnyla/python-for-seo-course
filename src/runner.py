# Runs one course cell. The same file runs in the browser (Pyodide) and in the
# local test suite, so what the tests check is what the learner gets.
import ast
import base64
import contextlib
import io
import json
import os
import sys
import traceback
import warnings

os.environ.setdefault("MPLBACKEND", "AGG")
warnings.filterwarnings("ignore", message=".*non-interactive.*")
warnings.filterwarnings("ignore", message=".*cannot show the figure.*")


def _exec_with_last_value(code, ns, filename):
    """Run code like a notebook: return the value of a final bare expression."""
    tree = ast.parse(code, filename=filename)
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
    exec(compile(tree, filename, "exec"), ns)
    if last is not None:
        return eval(compile(last, filename, "eval"), ns)
    return None


def _display(value):
    if value is None:
        return None
    if not isinstance(value, type):
        rh = getattr(value, "_repr_html_", None)
        if callable(rh):
            try:
                html = rh()
                if html:
                    return {"html": html}
            except Exception:
                pass
    try:
        return {"text": repr(value)}
    except Exception as e:  # a broken __repr__ should not hide the result
        return {"text": f"<value could not be shown: {e}>"}


def _error_info(exc, filename, code):
    lines = code.splitlines()
    etype = type(exc).__name__
    if isinstance(exc, SyntaxError) and exc.filename == filename:
        line = exc.lineno
        message = exc.msg
        frames = []
    else:
        tb = traceback.extract_tb(exc.__traceback__)
        frames = [f for f in tb if f.filename == filename]
        line = frames[-1].lineno if frames else None
        message = str(exc)
    trace = []
    for f in frames:
        src = lines[f.lineno - 1].strip() if f.lineno and 0 < f.lineno <= len(lines) else ""
        where = "" if f.name == "<module>" else f" (inside {f.name})"
        trace.append({"line": f.lineno, "code": src, "where": where})
    code_line = lines[line - 1] if line and 0 < line <= len(lines) else ""
    return {"type": etype, "message": message, "line": line,
            "code_line": code_line, "trace": trace}


def _figures():
    plt = sys.modules.get("matplotlib.pyplot")
    if plt is None:
        return []
    images = []
    for num in plt.get_fignums():
        fig = plt.figure(num)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
        images.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    plt.close("all")
    return images


def run_cell(setup, code, check=None):
    """Run module setup, then the learner's code, then (optionally) the hidden check.

    Every run starts from a fresh namespace, so cells never depend on each other.
    Returns a JSON string the page renders.
    """
    result = {"stdout": "", "stderr": "", "display": None, "images": [],
              "error": None, "setup_error": None, "check": None}
    ns = {"__name__": "__main__"}
    plt = sys.modules.get("matplotlib.pyplot")
    if plt is not None:
        plt.close("all")

    if setup and setup.strip():
        sink = io.StringIO()
        try:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                exec(compile(setup, "<setup>", "exec"), ns)
        except BaseException as exc:  # noqa: BLE001 - report everything
            result["setup_error"] = f"{type(exc).__name__}: {exc}"
            return json.dumps(result)

    out, err = io.StringIO(), io.StringIO()
    ok = True
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with warnings.catch_warnings():
                warnings.simplefilter("default")
                warnings.filterwarnings("ignore", message=".*non-interactive.*")
                warnings.filterwarnings("ignore", message=".*cannot show the figure.*")
                value = _exec_with_last_value(code, ns, "<cell>")
        result["display"] = _display(value)
    except SystemExit:
        ok = False
        result["error"] = {"type": "SystemExit", "message": "exit() stops a script. You don't need it here.",
                           "line": None, "code_line": "", "trace": []}
    except BaseException as exc:  # noqa: BLE001
        ok = False
        result["error"] = _error_info(exc, "<cell>", code)
    result["stdout"] = out.getvalue()
    result["stderr"] = err.getvalue()

    if check:
        if not ok:
            result["check"] = {"ok": False, "reason": "Your code stopped with an error, so it could not be checked. Fix the error first."}
        else:
            ns["printed"] = result["stdout"]
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    exec(compile(check, "<check>", "exec"), ns)
                result["check"] = {"ok": True, "reason": ""}
            except AssertionError as exc:
                result["check"] = {"ok": False, "reason": str(exc) or "The result is not what the task asks for yet."}
            except NameError as exc:
                name = getattr(exc, "name", None) or str(exc)
                result["check"] = {"ok": False, "reason": f"I couldn't find `{name}`. Keep the names the task asks for."}
            except BaseException as exc:  # noqa: BLE001
                result["check"] = {"ok": False, "reason": f"Your result caused a {type(exc).__name__} in the check: {exc}"}

    try:
        result["images"] = _figures()
    except Exception as exc:  # noqa: BLE001
        result["stderr"] += f"\n(Could not draw the chart: {exc})"
    return json.dumps(result)
