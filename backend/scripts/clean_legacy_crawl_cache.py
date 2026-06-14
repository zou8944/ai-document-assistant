#!/usr/bin/env python3
"""Clean legacy crawl cache directories (pages/, assets/, old manifests).

After the HTML preview feature was removed, the pages/ and assets/
subdirectories under each domain's crawl cache are no longer needed.
This script lists what would be deleted and asks for confirmation.

Usage:
    python backend/scripts/clean_legacy_crawl_cache.py [--dry-run]
"""

import argparse
import shutil
from pathlib import Path

from models.config import AppConfig


def main():
    parser = argparse.ArgumentParser(description="Clean legacy crawl cache")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list what would be deleted, do not delete",
    )
    args = parser.parse_args()

    cache_root = Path(AppConfig.get_crawl_cache_dir())
    if not cache_root.exists():
        print(f"Cache directory does not exist: {cache_root}")
        return

    targets: list[Path] = []
    for domain_dir in cache_root.iterdir():
        if not domain_dir.is_dir():
            continue
        for subdir in ("pages", "assets"):
            target = domain_dir / subdir
            if target.exists():
                targets.append(target)
        # Old manifest files that are no longer used
        for old_manifest in ("pages.json", "assets.json", "failed_assets.json"):
            target = domain_dir / "manifests" / old_manifest
            if target.exists():
                targets.append(target)

    if not targets:
        print("Nothing to clean.")
        return

    total_bytes = sum(
        sum(f.stat().st_size for f in t.rglob("*") if f.is_file()) for t in targets
    )
    total_mb = total_bytes / (1024 * 1024)

    print(f"Found {len(targets)} items to clean ({total_mb:.1f} MB):\n")
    for t in targets:
        print(f"  {t}")

    if args.dry_run:
        print("\n[dry-run] No files deleted.")
        return

    confirm = input(f"\nDelete {len(targets)} items ({total_mb:.1f} MB)? [y/N] ")
    if confirm.lower() != "y":
        print("Aborted.")
        return

    for t in targets:
        if t.is_dir():
            shutil.rmtree(t)
        else:
            t.unlink()
        print(f"  Deleted: {t}")

    print(f"\nDone. Freed ~{total_mb:.1f} MB.")


if __name__ == "__main__":
    main()
