"""Build index.html from src/content/*.txt, src/runner.py and src/template.html.

Usage:  python3 src/build.py
The output is one self-contained index.html in the project root.

Content file format (one file per module):
    @num 1                     module metadata lines (before the first @@)
    @title ...
    @@setup                    hidden Python that runs before every cell
    @@lesson Lesson title
    @@text                     markdown
    @@example [caption]        runnable code
    @@exercise [title]         markdown task, then @@starter @@hint @@solution @@check
    @@bug [title]              markdown context, then @@code @@hint @@solution @@check @@explain
    @@colab [title]            markdown note, then @@code
    @@tip                      "Guiding the AI" box (markdown)
    @@quiz                     question, then @@option / @@option* (correct) and @@explain
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

BLOCK_TYPES = {"text", "example", "exercise", "bug", "colab", "tip", "quiz"}
SUB_TYPES = {"starter", "hint", "solution", "check", "code", "option", "option*", "explain"}
CODE_FIELDS = {"example": "code", "starter": True, "solution": True, "check": True, "code": True}

# Plain-English error decoder. Used for "What this means" under errors and for
# the table on the Toolkit page. "match" (optional) is a regex tested against
# the error message; the most specific entry wins.
ERRORS = [
    {"type": "NameError", "meaning": "Python doesn't know this name.",
     "fix": "Check the spelling (capitals matter), create the variable before you use it, and put quotes around text."},
    {"type": "SyntaxError", "meaning": "Python can't read this line: something is missing or extra.",
     "fix": "Look for a missing bracket, quote, colon (:) or comma, on this line or the line just before it."},
    {"type": "SyntaxError", "match": r"unterminated string|EOL while scanning", "meaning": "A piece of text was opened with a quote but never closed.",
     "fix": "Add the closing quote. Opening and closing quotes must match: 'like this' or \"like this\"."},
    {"type": "SyntaxError", "match": r"was never closed|unexpected EOF", "meaning": "A bracket ( [ { was opened but never closed.",
     "fix": "Count your brackets. Every ( needs a ), every [ needs a ], every { needs a }."},
    {"type": "SyntaxError", "match": r"expected ':'", "meaning": "A line that starts a block (if, for, def, else) needs a colon at the end.",
     "fix": "Add : at the end of the line, then indent the next line by 4 spaces."},
    {"type": "IndentationError", "meaning": "The spaces at the start of a line are wrong.",
     "fix": "Lines inside if / for / def need 4 spaces more than the line above. Lines at the same level must line up exactly."},
    {"type": "TabError", "meaning": "Tabs and spaces are mixed in the indentation.",
     "fix": "Use 4 spaces for each level. In this course the Tab key already inserts 4 spaces."},
    {"type": "TypeError", "meaning": "You used a value of the wrong type, like adding text to a number.",
     "fix": "Convert first with int(), float() or str(). print(type(x)) shows what you have."},
    {"type": "TypeError", "match": r"NoneType", "meaning": "One of your values is None (empty). Often a function printed its result instead of returning it.",
     "fix": "Check that your function uses return, and that you saved the result of each step."},
    {"type": "TypeError", "match": r"missing \d+ required positional argument", "meaning": "You called a function without all the inputs it needs.",
     "fix": "Look at the def line to see which inputs (parameters) the function expects."},
    {"type": "TypeError", "match": r"not callable", "meaning": "You put () after something that is not a function.",
     "fix": "Check you didn't reuse a function name (like print or len) as a variable name."},
    {"type": "KeyError", "meaning": "This key or column name doesn't exist.",
     "fix": "Check spelling, capitals and spaces. print(df.columns) or print(my_dict.keys()) shows the real names."},
    {"type": "AttributeError", "meaning": "This kind of value doesn't have that method or attribute.",
     "fix": "Check the spelling. print(type(x)) shows what kind of value you have."},
    {"type": "AttributeError", "match": r"'NoneType'", "meaning": "Your value is None (empty), so it has no methods. Often a function forgot to return, or find() found nothing.",
     "fix": "Make sure functions use return. With BeautifulSoup, check if soup.find(...) is None before using it."},
    {"type": "ValueError", "meaning": "The type is right but the value isn't, e.g. int(\"twelve\").",
     "fix": "Print the value to see what it really contains, then clean it first."},
    {"type": "ValueError", "match": r"truth value of a (Series|DataFrame) is ambiguous", "meaning": "You used and / or / not (or a plain if) with a whole pandas column.",
     "fix": "In filters use & (and), | (or), ~ (not), and wrap each condition in brackets: df[(df[\"clicks\"] > 10) & (df[\"ctr\"] < 0.02)]."},
    {"type": "IndexError", "meaning": "You asked for a position that doesn't exist, like item 10 of a 5-item list.",
     "fix": "Positions start at 0. len(my_list) tells you how many items there are."},
    {"type": "ZeroDivisionError", "meaning": "You divided by zero, e.g. clicks / 0 impressions.",
     "fix": "Check for zero first: ctr = clicks / impressions if impressions > 0 else 0."},
    {"type": "ModuleNotFoundError", "meaning": "This library isn't installed or isn't available here.",
     "fix": "In the browser, only some libraries work. Use the Colab version of the code. In Colab, install with !pip install name."},
    {"type": "FileNotFoundError", "meaning": "Python can't find the file at that path.",
     "fix": "Check the file name and folder. In Colab, upload the file first and check the path in the Files panel."},
    {"type": "JSONDecodeError", "meaning": "The text isn't valid JSON.",
     "fix": "Print the text first. You may have an HTML error page or an empty response instead of JSON."},
]


# --------------------------------------------------------------------------- markdown
def inline(text):
    """Escape HTML, then apply `code`, **bold**, [link](url) and {{kbd}}."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append("<code>" + html.escape(part[1:-1]) + "</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\{\{(.+?)\}\}", r"<kbd>\1</kbd>", s)

        def link(m):
            label, url = m.group(1), m.group(2)
            if not re.match(r"^(https?://|#)", url):
                raise ValueError(f"Unsafe or relative link: {url}")
            ext = url.startswith("http")
            attrs = ' target="_blank" rel="noopener"' if ext else ""
            return f'<a href="{html.escape(url)}"{attrs}>{label}</a>'

        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)
        out.append(s)
    return "".join(out)


def markdown(md):
    lines = md.strip("\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append('<pre class="static-code"><code>' + html.escape("\n".join(buf)) + "</code></pre>")
            continue
        if line.startswith("<"):  # raw HTML block, passed through as written
            buf = []
            while i < len(lines) and lines[i].strip():
                buf.append(lines[i])
                i += 1
            out.append("\n".join(buf))
            continue
        if line.startswith("### "):
            out.append("<h3>" + inline(line[4:]) + "</h3>")
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))
                rows.append([c.strip().replace("\\|", "|") for c in cells])
                i += 1
            head, body = rows[0], [r for r in rows[1:] if not re.match(r"^:?-+:?$", r[0] or "-")]
            t = ['<div class="table-wrap"><table><thead><tr>']
            t += ["<th scope=\"col\">" + inline(c) + "</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in body:
                t.append("<tr>" + "".join("<td>" + inline(c) + "</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue
        if re.match(r"^(- |\d+\. )", line):
            ordered = re.match(r"^(\d+)\. ", line)
            tag = "ol" if ordered else "ul"
            start = f' start="{ordered.group(1)}"' if ordered and ordered.group(1) != "1" else ""
            items = []  # [text, [sub-items]]
            while i < len(lines) and re.match(r"^(- |\d+\. |  )", lines[i]) and lines[i].strip():
                cur = lines[i]
                if cur.startswith("  - ") and items:
                    items[-1][1].append(cur[4:])
                elif cur.startswith("  ") and items:
                    if items[-1][1]:
                        items[-1][1][-1] += " " + cur.strip()
                    else:
                        items[-1][0] += " " + cur.strip()
                else:
                    items.append([re.sub(r"^(- |\d+\. )", "", cur), []])
                i += 1
            html_items = []
            for text, subs in items:
                sub = "<ul>" + "".join("<li>" + inline(s) + "</li>" for s in subs) + "</ul>" if subs else ""
                html_items.append("<li>" + inline(text) + sub + "</li>")
            out.append(f"<{tag}{start}>" + "".join(html_items) + f"</{tag}>")
            continue
        if line.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith("> "):
                buf.append(lines[i][2:])
                i += 1
            out.append('<div class="note">' + markdown("\n".join(buf)) + "</div>")
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(- |\d+\. |\||```|### |> )", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out)


# --------------------------------------------------------------------------- parsing
def clean_code(s):
    lines = s.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(l.rstrip() for l in lines)


def parse_file(path):
    text = path.read_text(encoding="utf-8")
    meta, chunks = {}, []
    current = None
    for raw in text.split("\n"):
        m = re.match(r"^@@(\S+)\s*(.*)$", raw)
        if m:
            current = {"tag": m.group(1), "arg": m.group(2).strip(), "body": []}
            chunks.append(current)
            continue
        if current is None:
            mm = re.match(r"^@(\w+)\s+(.*)$", raw)
            if mm:
                meta[mm.group(1)] = mm.group(2).strip()
            elif raw.strip():
                raise ValueError(f"{path.name}: text before first @@ tag: {raw!r}")
            continue
        current["body"].append(raw)

    module = dict(meta)
    module["setup"] = ""
    module["lessons"] = []
    lesson = block = None
    counter = 0
    for ch in chunks:
        tag, arg, body = ch["tag"], ch["arg"], "\n".join(ch["body"])
        if tag == "setup":
            module["setup"] = clean_code(body)
        elif tag == "lesson":
            lesson = {"title": re.sub(r"`", "", arg), "title_html": inline(arg), "blocks": [], "quiz": None}
            lesson["id"] = f"{module['id']}-l{len(module['lessons']) + 1}"
            module["lessons"].append(lesson)
            block = None
        elif tag in BLOCK_TYPES:
            if lesson is None:
                raise ValueError(f"{path.name}: @@{tag} before any @@lesson")
            counter += 1
            block = {"type": tag, "title": arg, "id": f"{lesson['id']}-c{counter}"}
            if tag == "example":
                block["code"] = clean_code(body)
            elif tag == "quiz":
                block["question"] = markdown(body)
                block["options"] = []
                block["answer"] = None
            else:
                block["html"] = markdown(body) if body.strip() else ""
            if tag == "quiz":
                if lesson["quiz"] is not None:
                    raise ValueError(f"{path.name}: two quizzes in lesson {lesson['title']}")
                lesson["quiz"] = block
            else:
                lesson["blocks"].append(block)
        elif tag in SUB_TYPES:
            if block is None:
                raise ValueError(f"{path.name}: @@{tag} outside a block")
            if tag in ("option", "option*"):
                if block["type"] != "quiz":
                    raise ValueError(f"{path.name}: option outside quiz")
                if tag == "option*":
                    block["answer"] = len(block["options"])
                block["options"].append(inline(body.strip()))
            elif tag in ("hint", "explain"):
                block[tag] = markdown(body)
            else:
                block[tag] = clean_code(body)
        else:
            raise ValueError(f"{path.name}: unknown tag @@{tag}")
    return module


def validate(module):
    problems = []
    name = module.get("id")
    for key in ("id", "num", "title", "path", "desc", "goal", "time"):
        if key not in module:
            problems.append(f"{name}: missing @{key}")
    if module.get("kind") == "page":
        return problems
    if not 3 <= len(module["lessons"]) <= 5:
        problems.append(f"{name}: has {len(module['lessons'])} lessons (want 3-5)")
    n_ex = 0
    for lesson in module["lessons"]:
        types = [b["type"] for b in lesson["blocks"]]
        if "tip" not in types:
            problems.append(f"{lesson['id']}: no Guiding the AI tip")
        q = lesson["quiz"]
        if not q or q["answer"] is None or len(q["options"]) < 2 or not q.get("explain"):
            problems.append(f"{lesson['id']}: quiz missing, no correct option, or no explanation")
        for b in lesson["blocks"]:
            need = {"exercise": ["starter", "hint", "solution", "check"],
                    "bug": ["code", "hint", "solution", "check", "explain"],
                    "colab": ["code"], "example": ["code"]}.get(b["type"], [])
            for k in need:
                if not b.get(k):
                    problems.append(f"{b['id']}: {b['type']} missing @@{k}")
            if b["type"] == "exercise":
                n_ex += 1
    if n_ex < 2:
        problems.append(f"{name}: only {n_ex} exercises (want 2+)")
    return problems


def build():
    files = sorted((SRC / "content").glob("*.txt"))
    modules, problems = [], []
    for f in files:
        m = parse_file(f)
        problems += validate(m)
        modules.append(m)
    order = {"start": -1, "toolkit": 99}
    modules.sort(key=lambda m: order.get(m["id"], int(m["num"]) if m["num"].isdigit() else 50))
    if problems:
        print("Content problems:\n  " + "\n  ".join(problems))
        sys.exit(1)

    error_rows = "".join(
        f"<tr><td><code>{html.escape(e['type'])}</code></td><td>{html.escape(e['meaning'])}</td><td>{html.escape(e['fix'])}</td></tr>"
        for e in ERRORS)
    error_table = ('<div class="table-wrap"><table class="error-table"><thead><tr><th scope="col">Error</th>'
                   '<th scope="col">What it means</th><th scope="col">What to try</th></tr></thead><tbody>'
                   + error_rows + "</tbody></table></div>")
    for m in modules:
        for lesson in m["lessons"]:
            for b in lesson["blocks"]:
                if b.get("html") and "{{ERROR_TABLE}}" in b["html"]:
                    b["html"] = b["html"].replace("<p>{{ERROR_TABLE}}</p>", error_table)

    data = {"modules": modules, "errors": ERRORS, "runner": (SRC / "runner.py").read_text(encoding="utf-8")}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    template = (SRC / "template.html").read_text(encoding="utf-8")
    if "/*__COURSE_DATA__*/" not in template:
        raise SystemExit("template.html is missing the /*__COURSE_DATA__*/ placeholder")
    out = template.replace("/*__COURSE_DATA__*/", payload)
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    cells = sum(1 for m in modules for l in m["lessons"] for b in l["blocks"]
                if b["type"] in ("example", "exercise", "bug", "colab"))
    print(f"Built index.html: {len(modules)} views, "
          f"{sum(len(m['lessons']) for m in modules)} lessons, {cells} code cells, {len(out) // 1024} KB")


if __name__ == "__main__":
    build()
