"""Manifest-based link store for crawl checkpoint resume.

Stores discovered outbound links per crawled page in a per-domain
``links.json`` file inside the crawl cache directory.  This replaces the
previous mechanism that re-extracted links from stored ``html_content`` at
resume time.

File layout::

    <crawl-cache>/<domain_key>/manifests/links.json

Format::

    {
      "<canonical_page_url>": ["<link1>", "<link2>", ...],
      ...
}

Concurrency: a ``threading.Lock`` protects all read-modify-write cycles.
Writes are atomic (temp-file + ``Path.replace``).
"""

import json
import logging
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

from models.config import AppConfig

logger = logging.getLogger(__name__)


def _domain_key(url: str) -> str:
    """Derive the cache subdirectory name from a URL."""
    return urlparse(url).netloc.lower().replace(":", "_")


class ManifestStore:
    """Read/write links manifest for crawl checkpoint resume."""

    def __init__(self, config: AppConfig):
        self._cache_root: Path = Path(config.get_crawl_cache_dir())
        self._lock = threading.Lock()

    def _manifest_path(self, domain_key: str) -> Path:
        return self._cache_root / domain_key / "manifests" / "links.json"

    def _read(self, domain_key: str) -> dict[str, list[str]]:
        path = self._manifest_path(domain_key)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read manifest %s: %s", path, exc)
            return {}

    def _write(self, domain_key: str, data: dict[str, list[str]]) -> None:
        path = self._manifest_path(domain_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp file then rename
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix="links_"
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Path(tmp).replace(path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def record_links(self, page_url: str, links: list[str]) -> None:
        """Append outbound links for *page_url* to its domain manifest.

        Idempotent: calling multiple times for the same *page_url* merges
        (deduplicates) the link list.
        """
        if not links:
            return
        domain = _domain_key(page_url)
        with self._lock:
            data = self._read(domain)
            existing = set(data.get(page_url, []))
            new_links = [l for l in links if l not in existing]
            if not new_links:
                return
            data[page_url] = list(existing) + new_links
            self._write(domain, data)

    def recover_links(
        self,
        domain_key: str,
        skip_urls: set[str],
        prefixes: list[str] | None = None,
    ) -> set[str]:
        """Return not-yet-crawled links from the manifest for *domain_key*.

        Applies dedup, *skip_urls* filtering, and optional *prefixes*
        matching.  Used at task start to seed the BFS queue with links
        discovered during a previous (interrupted) run.
        """
        with self._lock:
            data = self._read(domain_key)

        # Collect and dedup all outbound links
        all_links: set[str] = set()
        for links in data.values():
            all_links.update(links)

        # Filter already-crawled pages
        candidates = all_links - skip_urls

        # Apply prefix filter
        if prefixes:
            candidates = {
                link
                for link in candidates
                if any(link.lower().startswith(p.lower()) for p in prefixes)
            }

        return candidates

    def merge_and_dedup(self, domain_key: str) -> None:
        """Deduplicate link lists for *domain_key* (write-time cleanup).

        Safe to call after a crawl completes; idempotent.
        """
        with self._lock:
            data = self._read(domain_key)
            changed = False
            for page_url, links in data.items():
                deduped = list(dict.fromkeys(links))
                if len(deduped) != len(links):
                    data[page_url] = deduped
                    changed = True
            if changed:
                self._write(domain_key, data)
