import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = PROJECT_ROOT / "reference"
REPORTS_DIR = PROJECT_ROOT / "reports"
# downloads and outputs run to gigabytes, so they can live outside the checkout
DATA_DIR = Path(os.environ.get("UNGA_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
SPEECHES_DIR = DATA_DIR / "speeches"
OUTPUT_DIR = DATA_DIR / "output"

GADEBATE_BASE = "https://gadebate.un.org"
# the site's firewall challenges clients without a browser user agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 unga-general-debate-research"
)
REQUEST_INTERVAL_SECONDS = 1.0

# the six official UN languages, the only ones the site transcribes
UN_LANGUAGES = ("ar", "zh", "en", "fr", "ru", "es")

# session n opened in september of year 1945 + n
FIRST_SESSION_YEAR_OFFSET = 1945


def session_year(session: int) -> int:
    return FIRST_SESSION_YEAR_OFFSET + session
