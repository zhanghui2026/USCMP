"""
Import Member Profiles from Wikipedia.

Reads USCL members with Wikipedia identifiers, fetches structured
biographical data via WikipediaProfileAdapter, and upserts into
the member_profiles table.

Usage:
    python3 -m app.etl.import_member_profiles --dry-run
    python3 -m app.etl.import_member_profiles
    python3 -m app.etl.import_member_profiles --limit 10
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.postgres import SessionLocal, engine
from app.models.sqlalchemy.models import Base, Member, MemberProfile
from app.etl.adapters.wikipedia_profile_adapter import (
    WikipediaProfileAdapter,
    _load_uscl_wikipedia_ids,
)
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


def import_member_profiles(
    adapter: WikipediaProfileAdapter,
    vendor_dir: str,
    dry_run: bool = False,
    limit: int | None = None,
    fixture_db: dict[str, dict] | None = None,
) -> dict[str, int]:
    stats = {
        "total_members": 0,
        "with_wikipedia_id": 0,
        "missing_wikipedia_id": 0,
        "fetched": 0,
        "imported": 0,
        "updated": 0,
        "skipped": 0,
        "partial_profile": 0,
        "failed": 0,
    }

    wiki_map = _load_uscl_wikipedia_ids(vendor_dir)
    logger.info(f"Loaded {len(wiki_map)} Wikipedia ID mappings from USCL source")

    db = SessionLocal()
    try:
        query = db.query(Member).filter(Member.source == "uscl")
        if limit:
            query = query.limit(limit)
        members = query.all()

        stats["total_members"] = len(members)

        existing_profiles = {
            row[0]: row[1]
            for row in db.query(MemberProfile.bioguide_id, MemberProfile.id).all()
        }

        for member in members:
            if not member.bioguide_id:
                stats["missing_wikipedia_id"] += 1
                continue

            wiki_info = wiki_map.get(member.bioguide_id)
            if not wiki_info:
                stats["missing_wikipedia_id"] += 1
                continue

            wikipedia_title = wiki_info.get("wikipedia")
            wikidata_qid = wiki_info.get("wikidata")

            if not wikipedia_title and not wikidata_qid:
                stats["missing_wikipedia_id"] += 1
                continue

            stats["with_wikipedia_id"] += 1

            if dry_run:
                logger.info(f"[DRY RUN] Would fetch: {member.canonical_name} "
                           f"(wiki={wikipedia_title}, wikidata={wikidata_qid})")
                continue

            profile_data = adapter.fetch_profile(wikipedia_title, wikidata_qid)

            if profile_data is None:
                stats["failed"] += 1
                continue

            stats["fetched"] += 1

            has_content = bool(
                profile_data.get("short_summary")
                or profile_data.get("birth_date")
                or profile_data.get("education")
                or profile_data.get("occupations")
            )
            if not has_content:
                stats["partial_profile"] += 1

            profile_id = f"wikipedia_profile_{member.bioguide_id}"

            existing_id = existing_profiles.get(member.bioguide_id)

            profile_fields = {
                "wikipedia_title": profile_data.get("wikipedia_title"),
                "wikipedia_url": profile_data.get("wikipedia_url"),
                "wikidata_qid": profile_data.get("wikidata_qid"),
                "image_url": profile_data.get("image_url"),
                "short_summary": profile_data.get("short_summary"),
                "birth_date": profile_data.get("birth_date"),
                "birth_place": profile_data.get("birth_place"),
                "education": profile_data.get("education") or [],
                "occupations": profile_data.get("occupations") or [],
                "career_highlights": profile_data.get("career_highlights") or [],
                "prior_positions": profile_data.get("prior_positions") or [],
                "military_service": profile_data.get("military_service") or [],
                "external_links": profile_data.get("external_links") or [],
                "profile_sources": profile_data.get("profile_sources") or {},
                "source": profile_data.get("source", "wikipedia") or "wikipedia",
                "source_reliability": "external_open_content",
                "last_updated": profile_data["last_updated"],
                "raw_snapshot_hash": profile_data.get("raw_snapshot_hash"),
            }

            if existing_id:
                db.query(MemberProfile).filter(
                    MemberProfile.id == existing_id
                ).update(profile_fields, synchronize_session=False)
                stats["updated"] += 1
            else:
                new_profile = MemberProfile(
                    id=profile_id,
                    member_id=member.id,
                    bioguide_id=member.bioguide_id,
                    **profile_fields,
                )
                db.add(new_profile)
                stats["imported"] += 1

            if stats["fetched"] % 50 == 0:
                db.commit()

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    adapter_stats = adapter.get_stats()
    stats["skipped"] = adapter_stats.get("skipped_missing_page", 0)
    stats["failed"] += adapter_stats.get("failed", 0)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Import member profiles from Wikipedia"
    )
    parser.add_argument(
        "--commit-sha",
        default=DEFAULT_COMMIT_SHA,
        help=f"Vendor commit SHA (default: {DEFAULT_COMMIT_SHA[:12]}...)",
    )
    parser.add_argument(
        "--vendor-dir",
        default=None,
        help="Override vendor data directory path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would be imported",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of members to process",
    )
    parser.add_argument(
        "--use-fixtures",
        action="store_true",
        help="Load pre-fetched fixture profiles instead of live Wikipedia API",
    )
    args = parser.parse_args()

    vendor_dir = _resolve_vendor_dir(args.commit_sha, args.vendor_dir)
    if not os.path.isdir(vendor_dir):
        logger.error(f"Vendor directory not found: {vendor_dir}")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)

    fixture_db = None
    if args.use_fixtures:
        try:
            from tests.fixtures.wikipedia_profiles import FIXTURE_PROFILES as _f
            fixture_db = dict(_f)
            logger.info(f"Loaded {len(fixture_db)} base fixture profiles")
        except ImportError:
            logger.warning("Could not load base fixtures module")

        try:
            from tests.fixtures.priority_leadership_fixtures import FIXTURES as _pl
            pl_db = {f["wikipedia_title"]: f for f in _pl if f.get("wikipedia_title")}
            fixture_db = fixture_db or {}
            fixture_db.update(pl_db)
            logger.info(f"Loaded {len(pl_db)} priority leadership fixtures (total: {len(fixture_db)})")
        except ImportError:
            logger.warning("Could not load priority leadership fixtures module")

    adapter = WikipediaProfileAdapter(rate_delay=0.2, fixtures=fixture_db)

    try:
        stats = import_member_profiles(
            adapter, vendor_dir, dry_run=args.dry_run, limit=args.limit,
            fixture_db=fixture_db,
        )
    except Exception as exc:
        logger.error(f"Import failed: {exc}")
        sys.exit(1)

    print("\n=== Wikipedia Profile Import ===")
    print(f"  Total members:         {stats['total_members']}")
    print(f"  With Wikipedia ID:     {stats['with_wikipedia_id']}")
    print(f"  Missing Wikipedia ID:  {stats['missing_wikipedia_id']}")
    print(f"  Fetched from API:      {stats['fetched']}")
    print(f"  Imported (new):        {stats['imported']}")
    print(f"  Updated:               {stats['updated']}")
    print(f"  Skipped (no page):     {stats['skipped']}")
    print(f"  Partial profiles:      {stats['partial_profile']}")
    print(f"  Failed:                {stats['failed']}")


if __name__ == "__main__":
    main()
