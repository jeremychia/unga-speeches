"""Package the generated data for a release: the tables, the speech pages and a checksum file."""

import hashlib
import shutil
from datetime import date
from pathlib import Path

from unga_speeches.config import OUTPUT_DIR, PROJECT_ROOT, SPEECHES_DIR

DIST_DIR = PROJECT_ROOT / "dist"
TABLES = ("speeches.parquet", "speeches.csv", "rights_of_reply.parquet")


def package() -> Path:
    """Write dist/ and return it; the tag is data-<today>."""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()
    for name in TABLES:
        shutil.copy2(OUTPUT_DIR / name, DIST_DIR / name)
    shutil.make_archive(str(DIST_DIR / "speech-pages"), "zip", SPEECHES_DIR)
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in sorted(DIST_DIR.iterdir())]
    (DIST_DIR / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    (DIST_DIR / "TAG").write_text(f"data-{date.today().isoformat()}\n")
    return DIST_DIR
