"""
Extract existing member_profiles as snapshot files for the v0.8 pipeline.

Reads available/partial profiles from PostgreSQL and writes them as
structured JSON files to data/external/wikipedia-profiles/.

Usage:
    python3 -m app.etl.extract_profile_snapshots
    python3 -m app.etl.extract_profile_snapshots --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.db.postgres import SessionLocal
from app.models.sqlalchemy.models import MemberProfile
from app.core.logging import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "external" / "wikipedia-profiles"


def extract_snapshots(snapshot_dir: str | None = None, limit: int | None = None) -> dict[str, int]:
    sd = Path(snapshot_dir) if snapshot_dir else SNAPSHOT_DIR
    sd.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    stats = {"total": 0, "extracted": 0, "skipped_no_bioguide": 0}

    try:
        query = db.query(MemberProfile).filter(
            MemberProfile.profile_status.in_(["available", "partial"])
        )
        if limit:
            query = query.limit(limit)
        profiles = query.all()
        stats["total"] = len(profiles)

        for p in profiles:
            if not p.bioguide_id:
                stats["skipped_no_bioguide"] += 1
                continue

            snapshot = {
                "bioguide_id": p.bioguide_id,
                "wikipedia_title": p.wikipedia_title,
                "wikipedia_url": p.wikipedia_url,
                "wikidata_qid": p.wikidata_qid,
                "image_url": p.image_url,
                "short_summary": p.short_summary,
                "birth_date": p.birth_date,
                "birth_place": p.birth_place,
                "education": p.education or [],
                "occupations": p.occupations or [],
                "prior_positions": p.prior_positions or [],
                "employers": p.employers or [],
                "military_service": p.military_service or [],
                "profile_sources": p.profile_sources or {},
            }

            fpath = sd / f"{p.bioguide_id}.json"
            fpath.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            stats["extracted"] += 1
            logger.info(f"  Extracted: {p.bioguide_id} ({p.wikipedia_title})")

        logger.info(
            f"Extracted {stats['extracted']}/{stats['total']} profiles to {sd}"
        )
    except Exception as exc:
        logger.error(f"Snapshot extraction failed: {exc}")
        raise
    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Extract profile snapshots")
    parser.add_argument("--snapshot-dir", help="Output directory")
    parser.add_argument("--limit", type=int, help="Limit number of profiles")
    args = parser.parse_args()

    stats = extract_snapshots(snapshot_dir=args.snapshot_dir, limit=args.limit)
    print(f"\nExtracted {stats['extracted']} snapshots from {stats['total']} profiles")


if __name__ == "__main__":
    main()
