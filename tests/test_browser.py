"""Browser test: real Pyodide in headless Chromium, UI checks and screenshots.

    .venv/bin/python tests/test_browser.py

1. Runs every cell through the page's own Pyodide runner (same pass rules as test_cells.py).
2. Clicks through the UI: Run, exercise check, hint, quiz, mark-as-done (survives reload),
   routing, Previous/Next, mobile menu.
3. Checks for horizontal page overflow at desktop and mobile widths.
4. Saves screenshots to tests/screenshots/.
"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = (ROOT / "index.html").resolve().as_uri()
SHOTS = ROOT / "tests" / "screenshots"
SHOTS.mkdir(exist_ok=True)
VIEWS = ["start"] + [f"module-{i}" for i in range(1, 9)] + ["toolkit"]
fails = []


def fail(msg):
    fails.append(msg)
    print("FAIL", msg)


RUN_ALL_JS = """
async () => {
  const out = [];
  for (const m of Course.data.modules) {
    for (const l of m.lessons) {
      for (const b of l.blocks) {
        if (b.type === "example") {
          const r = await Course.run(m.setup, b.code, null);
          const expectErr = b.code.includes("run me");
          out.push({id: b.id, ok: !r.setup_error && (!!r.error === expectErr),
                    detail: r.setup_error || (r.error ? r.error.type + ": " + r.error.message : "") });
        } else if (b.type === "exercise" || b.type === "bug") {
          const before = await Course.run(m.setup, b.type === "exercise" ? b.starter : b.code, b.check);
          const after = await Course.run(m.setup, b.solution, b.check);
          out.push({id: b.id, ok: !before.check.ok && after.check.ok,
                    detail: "before=" + before.check.ok + " after=" + after.check.ok + " " + (after.check.reason || "") +
                            (after.error ? " " + after.error.type + ": " + after.error.message : "")});
        }
      }
    }
  }
  return out;
}
"""


async def no_overflow(page, label):
    w = await page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    if w[0] > w[1] + 1:
        fail(f"{label}: page scrolls sideways ({w[0]}px content in a {w[1]}px window)")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        await page.goto(URL)
        await page.wait_for_function("document.querySelector('.py-status').dataset.state === 'ready'", timeout=120000)
        print("Pyodide ready:", await page.inner_text(".side-status .py-status"))

        # 1. every cell in Pyodide
        results = await page.evaluate(RUN_ALL_JS)
        bad = [r for r in results if not r["ok"]]
        for r in bad:
            fail(f"pyodide cell {r['id']}: {r['detail']}")
        print(f"Pyodide: {len(results) - len(bad)}/{len(results)} runnable cells passed")
        (ROOT / "tests" / "pyodide_results.json").write_text(json.dumps(results, indent=2))

        # 2. UI flow
        await page.goto(URL + "#module-5")
        await page.wait_for_selector("#module-5-l1 h2")
        ex = "#module-5-l1 .cell-exercise"
        await page.click(f"{ex} .btn-run")
        await page.wait_for_selector(f"{ex} .check", timeout=60000)
        if "Not yet" not in await page.inner_text(f"{ex} .check"):
            fail("starter code of the first pandas exercise did not say 'Not yet'")
        await page.click(f"{ex} >> text=Show hint")
        if not await page.is_visible(f"{ex} .reveal >> nth=0"):
            fail("Show hint did not reveal the hint")
        await page.click(f"{ex} >> text=Show solution")
        await page.click(f"{ex} >> text=Put it in the editor")
        await page.click(f"{ex} .btn-run")
        await page.wait_for_selector(f"{ex} .check.ok", timeout=60000)
        print("Exercise flow: Not yet -> hint -> solution -> Correct!")

        # Ctrl+Enter shortcut and DataFrame HTML output
        first = "#module-5-l1 .cell-example >> nth=1"
        await page.click(f"{first} >> textarea")
        await page.keyboard.press("Control+Enter")
        await page.wait_for_selector("#module-5-l1 .cell-example >> nth=1 >> .out-html table", timeout=60000)
        print("Ctrl+Enter ran the cell and df.head() showed as a table")

        # Tab inserts 4 spaces
        ta = "#module-1-l1 .cell-example >> nth=0 >> textarea"
        await page.goto(URL + "#module-1")
        await page.wait_for_selector(ta)
        await page.click(ta)
        await page.eval_on_selector("#module-1-l1 .cell-example textarea", "t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }")
        await page.keyboard.press("Enter")
        await page.keyboard.press("Tab")
        await page.keyboard.type("x")
        val = await page.input_value(ta)
        if not val.endswith("\n    x"):
            fail(f"Tab did not insert 4 spaces (got {val[-12:]!r})")
        await page.click("#module-1-l1 .cell-example >> nth=0 >> text=Reset")

        # matplotlib image
        await page.goto(URL + "#module-8")
        chart = "#module-8-l4 .cell-example >> nth=2"
        await page.wait_for_selector(chart)
        await page.click(f"{chart} >> .btn-run")
        await page.wait_for_selector("#module-8-l4 .cell-example >> nth=2 >> .out-img img", timeout=90000)
        print("matplotlib chart rendered as an image")

        # error explanation for the pandas 'and' bug
        await page.goto(URL + "#module-5")
        bug = "#module-5-l2 .cell-bug"
        await page.click(f"{bug} .btn-run")
        await page.wait_for_selector(f"{bug} .out-error", timeout=60000)
        etext = await page.inner_text(f"{bug} .out-error")
        if "ambiguous" not in etext or "What this means" not in etext or "line 1" not in etext:
            fail("pandas ambiguous error box is missing the message, line number or explanation: " + etext)
        if "Traceback" in etext or "pyodide" in etext.lower():
            fail("error box shows internal traceback lines")
        print("Error box:", " | ".join(etext.splitlines()[:2]))

        # quiz + mark done + persistence
        await page.click("#module-5-l1 .quiz label >> nth=1")
        fb = await page.inner_text("#module-5-l1 .quiz-feedback")
        if "right" not in fb:
            fail("quiz feedback missing")
        await page.click("#module-5-l1 .done-btn")
        await page.reload()
        await page.wait_for_selector("#module-5-l1 .done-btn")
        if await page.get_attribute("#module-5-l1 .done-btn", "aria-pressed") != "true":
            fail("Mark as done did not survive a reload")
        count = await page.inner_text('.nav-item[data-view="module-5"] .nav-count')
        if count != "1/5":
            fail(f"sidebar progress shows {count!r}, expected '1/5'")
        print("Quiz, mark-as-done and sidebar progress work; progress survives reload")

        # routing + pager
        await page.click(".pager .next")
        try:
            await page.wait_for_function("document.getElementById('view-title').textContent.includes('Module 6')", timeout=5000)
        except Exception:
            fail("Next button did not open Module 6")
        await page.goto(URL + "#module-3/module-3-l3")
        await page.wait_for_timeout(300)
        top = await page.evaluate("document.getElementById('module-3-l3').getBoundingClientRect().top")
        if abs(top) > 120:
            fail(f"lesson deep link did not scroll to the lesson (top={top})")
        await page.goto(URL + "#nonsense")
        if "start here" not in (await page.inner_text("#view-title")).lower():
            fail("unknown hash did not fall back to the start page")

        # 3/4. screenshots + overflow, desktop
        for v in VIEWS:
            await page.goto(URL + "#" + v)
            await page.wait_for_selector("#view-title")
            await no_overflow(page, f"desktop {v}")
        for v, name in [("start", "desktop-start"), ("module-5", "desktop-module5"), ("toolkit", "desktop-toolkit")]:
            await page.goto(URL + "#" + v)
            await page.wait_for_timeout(400)
            await page.screenshot(path=str(SHOTS / f"{name}.png"))
        await page.goto(URL + "#module-5")
        await page.click("#module-5-l2 .cell-bug .btn-run")
        await page.wait_for_selector("#module-5-l2 .cell-bug .out-error", timeout=60000)
        await page.locator("#module-5-l2 .cell-bug").screenshot(path=str(SHOTS / "desktop-bug-cell.png"))

        # dark mode
        dark = await browser.new_context(viewport={"width": 1366, "height": 900}, color_scheme="dark")
        dp = await dark.new_page()
        await dp.goto(URL + "#module-2")
        await dp.wait_for_selector("#view-title")
        await dp.wait_for_timeout(400)
        await dp.screenshot(path=str(SHOTS / "desktop-dark-module2.png"))
        await dark.close()

        # mobile
        mob = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        mp = await mob.new_page()
        mp.on("pageerror", lambda e: errors.append(str(e)))
        for v in VIEWS:
            await mp.goto(URL + "#" + v)
            await mp.wait_for_selector("#view-title")
            await no_overflow(mp, f"mobile {v}")
        await mp.goto(URL + "#module-5")
        await mp.wait_for_timeout(400)
        await mp.screenshot(path=str(SHOTS / "mobile-module5-top.png"))
        await mp.wait_for_function("document.querySelector('.py-status').dataset.state === 'ready'", timeout=120000)
        await mp.click("#module-5-l3 .cell-example >> nth=2 >> .btn-run")
        await mp.wait_for_selector("#module-5-l3 .cell-example >> nth=2 >> .out-html", timeout=60000)
        await no_overflow(mp, "mobile after DataFrame output")
        await mp.locator("#module-5-l3 .cell-example >> nth=2").screenshot(path=str(SHOTS / "mobile-dataframe-cell.png"))
        await mp.goto(URL + "#module-8")
        await mp.wait_for_selector("#view-title")
        await mp.click("#menu-btn")
        await mp.wait_for_timeout(400)
        if not await mp.is_visible("#sidebar"):
            fail("mobile menu did not open")
        await mp.screenshot(path=str(SHOTS / "mobile-menu-open.png"))
        await mp.click('.nav-item[data-view="toolkit"] a')
        await mp.wait_for_function("location.hash === '#toolkit'")
        if await mp.evaluate("document.body.classList.contains('nav-open')"):
            fail("mobile menu did not close after choosing a page")
        await mp.wait_for_timeout(300)
        await mp.screenshot(path=str(SHOTS / "mobile-toolkit.png"))
        await mob.close()

        real_errors = [e for e in errors if "favicon" not in e]
        for e in real_errors:
            fail("console error: " + e)
        await browser.close()

    print()
    print(f"{len(fails)} problem(s)" if fails else "Browser test passed.")
    sys.exit(1 if fails else 0)


asyncio.run(main())
