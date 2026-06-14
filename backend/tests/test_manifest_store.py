"""Tests for crawler.manifest_store.ManifestStore."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from crawler.manifest_store import ManifestStore, _domain_key


class FakeConfig:
    """Minimal config stub for ManifestStore."""

    def __init__(self, cache_dir: Path):
        self._cache_dir = cache_dir

    def get_crawl_cache_dir(self) -> Path:
        return self._cache_dir


@pytest.fixture()
def cache_dir(tmp_path: Path):
    return tmp_path / "crawl-cache"


@pytest.fixture()
def store(cache_dir: Path):
    return ManifestStore(FakeConfig(cache_dir))


class TestDomainKey:
    def test_basic(self):
        assert _domain_key("https://example.com/page") == "example.com"

    def test_port(self):
        assert _domain_key("http://localhost:8080/api") == "localhost_8080"

    def test_www_preserved(self):
        assert _domain_key("https://www.example.com/") == "www.example.com"


class TestRecordLinks:
    def test_basic_record(self, store: ManifestStore, cache_dir: Path):
        store.record_links("https://example.com/page1", ["/a", "/b"])
        manifest_path = cache_dir / "example.com" / "manifests" / "links.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["https://example.com/page1"] == ["/a", "/b"]

    def test_merge_same_page(self, store: ManifestStore):
        store.record_links("https://example.com/p", ["/a", "/b"])
        store.record_links("https://example.com/p", ["/b", "/c"])
        data = json.loads(
            (store._manifest_path("example.com")).read_text()
        )
        assert set(data["https://example.com/p"]) == {"/a", "/b", "/c"}

    def test_multiple_pages(self, store: ManifestStore):
        store.record_links("https://example.com/p1", ["/a"])
        store.record_links("https://example.com/p2", ["/b"])
        data = json.loads(
            (store._manifest_path("example.com")).read_text()
        )
        assert "/a" in data["https://example.com/p1"]
        assert "/b" in data["https://example.com/p2"]

    def test_empty_links_noop(self, store: ManifestStore, cache_dir: Path):
        store.record_links("https://example.com/p", [])
        assert not (cache_dir / "example.com" / "manifests" / "links.json").exists()


class TestRecoverLinks:
    def test_basic_recovery(self, store: ManifestStore):
        store.record_links("https://example.com/p1", ["/a", "/b"])
        result = store.recover_links("example.com", skip_urls=set())
        assert result == {"/a", "/b"}

    def test_skip_urls_filtered(self, store: ManifestStore):
        store.record_links("https://example.com/p1", ["/a", "/b"])
        result = store.recover_links("example.com", skip_urls={"/a"})
        assert result == {"/b"}

    def test_prefix_filter(self, store: ManifestStore):
        store.record_links("https://example.com/p1", ["/docs/a", "/api/b", "/other/c"])
        result = store.recover_links(
            "example.com", skip_urls=set(), prefixes=["/docs/"]
        )
        assert result == {"/docs/a"}

    def test_multiple_prefixes(self, store: ManifestStore):
        store.record_links("https://example.com/p1", ["/docs/a", "/api/b", "/other/c"])
        result = store.recover_links(
            "example.com", skip_urls=set(), prefixes=["/docs/", "/api/"]
        )
        assert result == {"/docs/a", "/api/b"}

    def test_dedup_across_pages(self, store: ManifestStore):
        store.record_links("https://example.com/p1", ["/a", "/b"])
        store.record_links("https://example.com/p2", ["/b", "/c"])
        result = store.recover_links("example.com", skip_urls=set())
        assert result == {"/a", "/b", "/c"}

    def test_empty_manifest(self, store: ManifestStore):
        result = store.recover_links("example.com", skip_urls=set())
        assert result == set()

    def test_all_skipped(self, store: ManifestStore):
        store.record_links("https://example.com/p1", ["/a", "/b"])
        result = store.recover_links("example.com", skip_urls={"/a", "/b"})
        assert result == set()


class TestMergeAndDedup:
    def test_dedup(self, store: ManifestStore):
        # Manually write a manifest with duplicates
        path = store._manifest_path("example.com")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"https://example.com/p": ["/a", "/b", "/a", "/c", "/b"]}),
            encoding="utf-8",
        )
        store.merge_and_dedup("example.com")
        data = json.loads(path.read_text())
        assert data["https://example.com/p"] == ["/a", "/b", "/c"]

    def test_no_change(self, store: ManifestStore):
        store.record_links("https://example.com/p", ["/a", "/b"])
        path = store._manifest_path("example.com")
        original = path.read_text()
        store.merge_and_dedup("example.com")
        assert path.read_text() == original

    def test_empty_manifest(self, store: ManifestStore):
        # Should not raise
        store.merge_and_dedup("nonexistent.com")


class TestConcurrency:
    def test_concurrent_writes(self, store: ManifestStore):
        """Multiple threads writing to the same manifest should not corrupt it."""
        import threading

        errors: list[Exception] = []

        def writer(page_id: int):
            try:
                links = [f"/link-{page_id}-{i}" for i in range(5)]
                store.record_links(f"https://example.com/p{page_id}", links)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        path = store._manifest_path("example.com")
        data = json.loads(path.read_text())
        assert len(data) == 10
        for i in range(10):
            assert f"https://example.com/p{i}" in data
