"""
Import minimal member profiles from USCL vendor YAML data.

Reads biographical fields directly from USCL YAML (bio.birthday, bio.gender,
id.wikipedia, id.wikidata) and creates member_profiles without needing
Wikipedia API access. Designed for environments where Wikipedia is blocked.

Usage:
    python3 -m app.etl.import_uscl_profiles --dry-run
    python3 -m app.etl.import_uscl_profiles
    python3 -m app.etl.import_uscl_profiles --limit 20
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.db.postgres import SessionLocal, engine
from app.models.sqlalchemy.models import Base, Member, MemberProfile
from app.etl.profile_status import compute_profile_status
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


def _load_uscl_bios(vendor_dir: str) -> dict[str, dict[str, str]]:
    """Load {bioguide_id: {birthday, gender, wikipedia, wikidata, name, party, chamber, state}} from USCL data."""
    mapping: dict[str, dict[str, str]] = {}
    files = [
        os.path.join(vendor_dir, "legislators-current.yaml"),
        os.path.join(vendor_dir, "legislators-historical.yaml"),
    ]

    for filepath in files:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, list):
            continue
        for leg in data:
            ids = leg.get("id", {})
            bioguide = ids.get("bioguide")
            if not bioguide:
                continue
            bio = leg.get("bio", {})
            name = leg.get("name", {})
            terms = leg.get("terms", [])
            latest = terms[-1] if terms else {}
            info = {
                "birthday": bio.get("birthday", ""),
                "gender": bio.get("gender", ""),
                "wikipedia": ids.get("wikipedia", ""),
                "wikidata": ids.get("wikidata", ""),
                "full_name": name.get("official_full", f"{name.get('first', '')} {name.get('last', '')}".strip()),
                "party": latest.get("party", ""),
                "chamber": "senate" if latest.get("type") == "sen" else "house",
                "state": latest.get("state", ""),
            }
            if bioguide not in mapping:
                mapping[bioguide] = info

    return mapping


def _build_short_summary(info: dict) -> str | None:
    """Build a minimal one-line summary from available USCL fields."""
    parts = []
    if info.get("full_name"):
        parts.append(info["full_name"])
    if info.get("birthday"):
        parts.append(f"(born {info['birthday']})")
    if info.get("party") and info.get("chamber") and info.get("state"):
        chamber_label = "senator" if info["chamber"] == "senate" else "representative"
        parts.append(f"is a {info['party']} {chamber_label} from {info['state']}")
    return " ".join(parts) if len(parts) >= 2 else None


def import_uscl_profiles(vendor_dir: str, dry_run: bool = False, limit: int | None = None) -> dict[str, int]:
    stats = {
        "total_members": 0,
        "with_bio": 0,
        "without_bioguide": 0,
        "imported": 0,
        "updated": 0,
        "skipped": 0,
    }

    bio_map = _load_uscl_bios(vendor_dir)
    logger.info(f"Loaded {len(bio_map)} bioguide->bio mappings from USCL source")

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
                stats["without_bioguide"] += 1
                continue

            bio_info = bio_map.get(member.bioguide_id)
            if not bio_info:
                stats["skipped"] += 1
                continue

            stats["with_bio"] += 1

            if dry_run:
                logger.info(f"[DRY RUN] Would upsert profile: {member.canonical_name}")
                continue

            wikipedia_title = bio_info.get("wikipedia")
            wikidata_qid = bio_info.get("wikidata")
            wikipedia_url = f"https://en.wikipedia.org/wiki/{wikipedia_title.replace(' ', '_')}" if wikipedia_title else None
            birth_date = bio_info.get("birthday") or None
            short_summary = _build_short_summary(bio_info)

            now = datetime.now(timezone.utc)

            profile_sources = {
                "uscl_commit": DEFAULT_COMMIT_SHA[:8],
                "data_source": "unitedstates/congress-legislators",
            }
            if wikipedia_title:
                profile_sources["wikipedia_title"] = wikipedia_title
                profile_sources["wikipedia_url"] = wikipedia_url
            if wikidata_qid:
                profile_sources["wikidata_qid"] = wikidata_qid

            raw_snapshot = json.dumps(bio_info, sort_keys=True, ensure_ascii=False)
            raw_snapshot_hash = hashlib.sha256(raw_snapshot.encode()).hexdigest()

            profile_id = f"uscl_profile_{member.bioguide_id}"
            existing_id = existing_profiles.get(member.bioguide_id)

            profile_fields = {
                "wikipedia_title": wikipedia_title,
                "wikipedia_url": wikipedia_url,
                "wikidata_qid": wikidata_qid,
                "image_url": None,
                "short_summary": short_summary,
                "birth_date": birth_date,
                "birth_place": None,
                "education": [],
                "occupations": [],
                "career_highlights": [],
                "prior_positions": [],
                "military_service": [],
                "employers": [],
                "external_links": [],
                "profile_sources": profile_sources,
                "source": "uscl",
                "source_reliability": "secondary",
                "last_updated": now,
                "raw_snapshot_hash": raw_snapshot_hash,
            }

            status, parsed, missing = compute_profile_status(profile_fields)
            profile_fields["profile_status"] = status
            profile_fields["parsed_fields"] = parsed
            profile_fields["missing_fields"] = missing

            if existing_id:
                existing = db.query(MemberProfile).filter(MemberProfile.id == existing_id).first()
                if existing and existing.source != "wikipedia":
                    db.query(MemberProfile).filter(MemberProfile.id == existing_id).update(
                        profile_fields, synchronize_session=False
                    )
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

            if stats["imported"] + stats["updated"] % 500 == 0:
                db.flush()

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import USCL bio-based member profiles")
    parser.add_argument("--commit-sha", default=DEFAULT_COMMIT_SHA)
    parser.add_argument("--vendor-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    vendor_dir = _resolve_vendor_dir(args.commit_sha, args.vendor_dir)
    if not os.path.isdir(vendor_dir):
        logger.error(f"Vendor directory not found: {vendor_dir}")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)

    stats = import_uscl_profiles(vendor_dir, dry_run=args.dry_run, limit=args.limit)

    print("\n=== USCL Bio Profile Import ===")
    print(f"  Total members:         {stats['total_members']}")
    print(f"  With bio data:         {stats['with_bio']}")
    print(f"  Without bioguide_id:   {stats['without_bioguide']}")
    print(f"  Imported (new):        {stats['imported']}")
    print(f"  Updated:               {stats['updated']}")
    print(f"  Skipped:               {stats['skipped']}")


if __name__ == "__main__":
    main()
