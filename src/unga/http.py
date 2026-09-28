"""Polite, cached HTTP with a provenance record for every file kept."""

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import RAW_DIR, REQUEST_INTERVAL_SECONDS, USER_AGENT

MANIFEST = RAW_DIR / "manifest.jsonl"


@dataclass
class Fetched:
    url: str
    path: Path
    sha256: str
    retrieved_at: str
    content_type: str


class Client:
    def __init__(self, refresh: bool = False):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.refresh = refresh
        self._last_request = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        for attempt in range(4):
            self._wait()
            try:
                response = self.session.request(method, url, timeout=60, **kwargs)
            except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError):
                if attempt == 3:
                    raise
                time.sleep(2**attempt * 5)
                continue
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2**attempt * 5)
                continue
            return response
        response.raise_for_status()
        return response

    def is_cached(self, dest: Path, force: bool = False) -> bool:
        return not (self.refresh or force) and dest.exists() and dest.with_suffix(dest.suffix + ".meta.json").exists()

    def fetch(
        self, url: str, dest: Path, *, source_url: str | None = None, follow_redirects: bool = True, force: bool = False
    ) -> Fetched | None:
        """Download url to dest unless cached; returns None on 404, or on a redirect when follow_redirects is off.

        source_url is the stable address recorded as provenance when url is a signed, expiring link.
        """
        meta_path = dest.with_suffix(dest.suffix + ".meta.json")
        if self.is_cached(dest, force):
            return Fetched(**{**json.loads(meta_path.read_text()), "path": dest})
        response = self.request("GET", url, allow_redirects=follow_redirects)
        if response.status_code == 404 or response.is_redirect:
            return None
        if b"<title>Human Verification</title>" in response.content[:2000]:
            raise RuntimeError(f"blocked by the site's bot check: {url}")
        response.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        fetched = Fetched(
            url=source_url or url,
            path=dest,
            sha256=hashlib.sha256(response.content).hexdigest(),
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            content_type=response.headers.get("content-type", ""),
        )
        record = {k: v for k, v in asdict(fetched).items() if k != "path"}
        meta_path.write_text(json.dumps(record, indent=2))
        with MANIFEST.open("a") as f:
            f.write(json.dumps({**record, "path": str(dest.relative_to(RAW_DIR))}) + "\n")
        return fetched
