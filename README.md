# Python for SEO & GEO

An interactive, beginner-friendly Python course for SEO and GEO/AEO specialists. Real Python runs in your browser (via [Pyodide](https://pyodide.org/)), so there's nothing to install.

**Open the course:** `index.html` (or the GitHub Pages link for this repository).

## What's inside

- 8 modules, about 10 weeks at 20–30 minutes a day: Python basics, text, loops, functions, pandas, HTML and on-page audits, APIs (Search Console), and Python for GEO (brand mentions, cited domains, share of voice).
- Runnable examples, exercises with automatic checks, "spot the bug" cells with AI-written mistakes, and Colab-only code for live requests and API keys.
- A "Guiding the AI" tip in every lesson, plus a Toolkit page: a review checklist for AI-written code, a prompt template, an error decoder and final project ideas.
- All sample data is fictional (the Singapore home-fitness store "Sweat & Co" and its competitors "FitHub" and "GymPro").

Progress and code edits are saved in your browser only (localStorage).

## Needs the internet

Python (Pyodide, about 10–20 MB the first time, then cached by the browser) and the fonts load from CDNs. Without a connection the page opens, but the Run buttons won't work.

## Editing the course

`index.html` is generated. Don't edit it by hand. Edit the source and rebuild:

```
src/content/*.txt   lesson text and code cells (one file per module)
src/template.html   page layout, styles and JavaScript
src/runner.py       the Python that runs each cell (in the browser and in tests)
src/build.py        builds index.html from the files above
tests/              cell tests (local Python) and browser tests (Playwright)
```

```
python3.12 -m venv .venv
.venv/bin/pip install pandas==2.2.3 numpy==2.0.2 matplotlib==3.8.4 beautifulsoup4==4.12.3 pyparsing==3.1.2 pillow==10.2.0 playwright
.venv/bin/python -m playwright install chromium

.venv/bin/python src/build.py          # rebuild index.html
.venv/bin/python tests/test_cells.py   # every example, exercise solution and bug fix, in local Python
.venv/bin/python tests/test_browser.py # every cell again in real Pyodide, UI checks, screenshots
```

The library versions match Pyodide 0.27.7, so local results match the browser.
