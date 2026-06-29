"""
Backfill wikipedia/wikidata IDs into members.official_ids for existing USCL members.

Reads the USCL vendor data YAML files, finds the wikipedia and wikidata IDs
for each bioguide_id, and updates the `official_ids` JSON column.

Usage:
    python3 -m app.etl.backfill_wikipedia_ids --dry-run
    python3 -m app.etl.backfill_wikipedia_ids
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from app.db.postgres import SessionLocal, engine
from app.models.sqlalchemy.models import Base, Member
from app.etl.adapters.wikipedia_profile_adapter import _load_uscl_wikipedia_ids
from app.core.logging import logger

DEFAULT_COMMIT_SHA = "dfa9622263dd4c8d08636926e498f1845704d7eb"


def _resolve_vendor_dir(commit_sha: str, vendor_dir_override: str | None = None) -> str:
    if vendor_dir_override:
        return vendor_dir_override
    here = Path(__file__).resolve()
    return str(
        here.parent.parent.parent
        / "data" / "external" / "congress-legislators" / commit_sha
    )


def backfill_wikipedia_ids(vendor_dir: str, dry_run: bool = False) -> dict[str, int]:
    stats = {"total_uscl": 0, "updated": 0, "already_has": 0, "no_match": 0, "skipped_no_bioguide": 0}

    wiki_map = _load_uscl_wikipedia_ids(vendor_dir)
    logger.info(f"Loaded {len(wiki_map)} bioguide->wikipedia mappings from USCL source")

    db = SessionLocal()
    try:
        members = db.query(Member).filter(Member.source == "uscl").all()
        stats["total_uscl"] = len(members)

        for member in members:
            if not member.bioguide_id:
                stats["skipped_no_bioguide"] += 1
                continue

            wiki_info = wiki_map.get(member.bioguide_id)
            if not wiki_info:
                stats["no_match"] += 1
                continue

            current_ids = dict(member.official_ids or {})
            modified = False

            if wiki_info.get("wikipedia") and "wikipedia" not in current_ids:
                current_ids["wikipedia"] = wiki_info["wikipedia"]
                modified = True
            if wiki_info.get("wikidata") and "wikidata" not in current_ids:
                current_ids["wikidata"] = wiki_info["wikidata"]
                modified = True

            if modified:
                if not dry_run:
                    db.query(Member).filter(Member.id == member.id).update(
                        {"official_ids": current_ids}, synchronize_session=False
                    )
                stats["updated"] += 1
            else:
                stats["already_has"] += 1

        if not dry_run:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Backfill Wikipedia IDs into members.official_ids")
    parser.add_argument("--commit-sha", default=DEFAULT_COMMIT_SHA)
    parser.add_argument("--vendor-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    vendor_dir = _resolve_vendor_dir(args.commit_sha, args.vendor_dir)
    if not os.path.isdir(vendor_dir):
        logger.error(f"Vendor directory not found: {vendor_dir}")
        sys.exit(1)

    stats = backfill_wikipedia_ids(vendor_dir, dry_run=args.dry_run)

    print("\n=== Wikipedia ID Backfill ===")
    print(f"  Total USCL members:    {stats['total_uscl']}")
    print(f"  Updated:               {stats['updated']}")
    print(f"  Already had IDs:       {stats['already_has']}")
    print(f"  No match in source:    {stats['no_match']}")
    print(f"  Skipped (no bioguide): {stats['skipped_no_bioguide']}")


if __name__ == "__main__":
    main()
