"""The analysis notebooks as pages in site/, each with its code hidden behind a button so readers see the findings first."""

import html as htmllib
import json
import re
import subprocess

from unga_speeches.config import PROJECT_ROOT

SOURCE_URL = "https://github.com/jeremychia/unga-speeches/blob/main/notebooks/"
# notebook in notebooks/, page in site/, page title
PAGES = [
    ("unga_2026_questions.ipynb", "questions.html", "Four questions on the 2026 debate"),
    ("unga_2026_wars.ipynb", "wars.html", "How the debate names its wars"),
]

HEAD = """<style>
.page-bar{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;max-width:1100px;margin:0 auto;padding:16px;display:flex;gap:16px;
  flex-wrap:wrap;align-items:center;font-size:14px;border-bottom:1px solid #e1e0d9}
.page-bar button{font:inherit;padding:4px 12px;border:1px solid #c3c2b7;border-radius:6px;background:#fcfcfb;cursor:pointer}
body:not(.show-code) .jp-CodeCell .jp-Cell-inputWrapper{display:none}
</style>
<noscript><style>body:not(.show-code) .jp-CodeCell .jp-Cell-inputWrapper{display:block}</style></noscript>
"""

BAR = """<header class="page-bar">
<a href="./">← The 2026 analysis</a>
<button type="button" id="code-toggle" aria-pressed="false">Show the code</button>
<a href="{source}">The notebook on GitHub</a>
</header>
<script>
document.getElementById("code-toggle").addEventListener("click", (e) => {{
  const on = document.body.classList.toggle("show-code");
  e.target.setAttribute("aria-pressed", on);
  e.target.textContent = on ? "Hide the code" : "Show the code";
}});
</script>
"""


def _alt_text(html: str, notebook) -> str:
    """Put each chart's headline, which the notebook stores with the image, on the image as its alt text, in page order."""
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    alts = iter(
        o.get("metadata", {}).get("image/png", {}).get("alt", "")
        for c in cells
        for o in c.get("outputs", [])
        if "image/png" in o.get("data", {})
    )
    return re.sub(
        r'<img alt="No description has been provided for this image"', lambda _: f'<img alt="{htmllib.escape(next(alts, ""))}"', html
    )


def build(notebook_name: str, page_name: str, title: str) -> None:
    """Export one notebook as it was last run, then add the title, the bar and the code toggle."""
    notebook, page = PROJECT_ROOT / "notebooks" / notebook_name, PROJECT_ROOT / "site" / page_name
    subprocess.run(
        ["jupyter", "nbconvert", "--to", "html", "--output-dir", str(page.parent), "--output", page.stem, str(notebook)], check=True
    )
    html = page.read_text(encoding="utf-8")
    html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", html, count=1, flags=re.S)
    html = _alt_text(html, notebook)
    html = html.replace("</head>", HEAD + "</head>", 1)
    bar = BAR.format(source=SOURCE_URL + notebook_name)
    html, n = re.subn(r"(<body[^>]*>)", lambda m: m.group(1) + bar, html, count=1)
    if n != 1:
        raise ValueError(f"the exported {notebook_name} has no <body> tag")
    page.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    for args in PAGES:
        build(*args)
