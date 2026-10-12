"""The four-questions notebook as a page in site/, its code hidden behind a button so readers see the findings first."""

import html as htmllib
import json
import re
import subprocess

from unga_speeches.config import PROJECT_ROOT

NOTEBOOK = PROJECT_ROOT / "notebooks/unga_2026_questions.ipynb"
PAGE = PROJECT_ROOT / "site/questions.html"
TITLE = "Four questions on the 2026 debate"
SOURCE_URL = "https://github.com/jeremychia/unga-speeches/blob/main/notebooks/unga_2026_questions.ipynb"

HEAD = """<style>
.page-bar{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;max-width:1100px;margin:0 auto;padding:16px;display:flex;gap:16px;
  flex-wrap:wrap;align-items:center;font-size:14px;border-bottom:1px solid #e1e0d9}
.page-bar button{font:inherit;padding:4px 12px;border:1px solid #c3c2b7;border-radius:6px;background:#fcfcfb;cursor:pointer}
body:not(.show-code) .jp-CodeCell .jp-Cell-inputWrapper{display:none}
</style>
<noscript><style>body:not(.show-code) .jp-CodeCell .jp-Cell-inputWrapper{display:block}</style></noscript>
"""

BAR = f"""<header class="page-bar">
<a href="./">← The 2026 analysis</a>
<button type="button" id="code-toggle" aria-pressed="false">Show the code</button>
<a href="{SOURCE_URL}">The notebook on GitHub</a>
</header>
<script>
document.getElementById("code-toggle").addEventListener("click", (e) => {{
  const on = document.body.classList.toggle("show-code");
  e.target.setAttribute("aria-pressed", on);
  e.target.textContent = on ? "Hide the code" : "Show the code";
}});
</script>
"""


def _alt_text(html: str) -> str:
    """Put each chart's headline, which the notebook stores with the image, on the image as its alt text, in page order."""
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    alts = iter(
        o.get("metadata", {}).get("image/png", {}).get("alt", "")
        for c in cells
        for o in c.get("outputs", [])
        if "image/png" in o.get("data", {})
    )
    return re.sub(
        r'<img alt="No description has been provided for this image"', lambda _: f'<img alt="{htmllib.escape(next(alts, ""))}"', html
    )


def build() -> None:
    """Export the notebook as it was last run, then add the title, the bar and the code toggle."""
    subprocess.run(
        ["jupyter", "nbconvert", "--to", "html", "--output-dir", str(PAGE.parent), "--output", PAGE.stem, str(NOTEBOOK)], check=True
    )
    html = PAGE.read_text(encoding="utf-8")
    html = re.sub(r"<title>.*?</title>", f"<title>{TITLE}</title>", html, count=1, flags=re.S)
    html = _alt_text(html)
    html = html.replace("</head>", HEAD + "</head>", 1)
    html, n = re.subn(r"(<body[^>]*>)", lambda m: m.group(1) + BAR, html, count=1)
    if n != 1:
        raise ValueError("the exported notebook has no <body> tag")
    PAGE.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build()
