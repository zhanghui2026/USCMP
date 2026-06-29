"""Real Members Import.

Reads normalized data from the Congress Legislators adapter and
upserts into the main `members` table with idempotent bioguide_id
conflict resolution.

Usage:
    python3 -m app.etl.import_real_members --commit-sha {sha}
    python3 -m app.etl.import_real_members --commit-sha {sha} --vendor-dir /path/to/data
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.postgres import SessionLocal, engine
from app.models.sqlalchemy.models import Base, Member
from app.etl.adapters.congress_legislators_adapter import CongressLegislatorsAdapter
from app.core.logging import logger

DEFAULT_COMMIT_SHA = "dfa9622263dd4c8d08636926e498f1845704d7eb"


class RealMembersImportError(Exception):
    """Raised when the import cannot proceed."""


def _resolve_vendor_dir(commit_sha: str, vendor_dir_override: str | None = None) -> str:
    if vendor_dir_override:
        path = vendor_dir_override
    else:
        here = Path(__file__).resolve()
        path = str(
            here.parent.parent.parent
            / "data" / "external" / "congress-legislators" / commit_sha
        )
    return path


def check_vendor_data_exists(vendor_dir: str) -> None:
    if not os.path.isdir(vendor_dir):
        raise RealMembersImportError(
            f"Vendor data directory not found: {vendor_dir}\n"
            "Please initialize vendor data first:\n"
            "  1. Clone https://github.com/unitedstates/congress-legislators\n"
            "  2. Place it at: backend/data/external/congress-legislators/{commit_sha}/\n"
            "  3. Ensure legislators-current.yaml and other YAML files are present"
        )
    required_files = [
        "legislators-current.yaml",
        "legislators-historical.yaml",
        "committees-current.yaml",
        "committee-membership-current.yaml",
    ]
    missing = [f for f in required_files if not os.path.exists(os.path.join(vendor_dir, f))]
    if missing:
        raise RealMembersImportError(
            f"Required vendor files missing in {vendor_dir}: {missing}"
        )


def _assemble_committee_memberships(
    memberships: list[dict],
    entities: list[dict],
    person_id: str,
) -> list[dict]:
    entity_map = {e["entity_id"]: e for e in entities}
    result = []
    for m in memberships:
        if m.get("person_id") != person_id:
            continue
        entity = entity_map.get(m.get("committee_entity_id", ""))
        result.append({
            "committee": entity["name"] if entity else m.get("committee_entity_id", "Unknown"),
            "role": m.get("role", "Member"),
            "congress": m.get("congress"),
            "committee_type": "committee",
            "start_date": m.get("start_date"),
            "end_date": m.get("end_date"),
        })
    return result


def import_members_from_adapter(
    adapter: CongressLegislatorsAdapter,
    vendor_dir: str,
) -> dict[str, int]:
    """Core import function: normalize, map, upsert.

    Returns:
        dict with keys: inserted, updated, skipped_no_bioguide, total
    """
    check_vendor_data_exists(vendor_dir)

    existing = adapter.get_normalized()
    if "persons" not in existing:
        logger.info("Loading vendor dataset...")
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
    norm = adapter.get_normalized()

    persons = norm.get("persons", [])
    terms = norm.get("person_terms", [])
    entities = norm.get("political_entities", [])
    committee_memberships = norm.get("committee_memberships", [])

    if not persons:
        raise RealMembersImportError("No persons found in normalized data")

    now = datetime.now(timezone.utc)
    inserted = 0
    updated = 0
    skipped_no_bioguide = 0

    db = SessionLocal()
    try:
        # Pre-load all existing bioguide_ids for O(1) lookup
        existing_ids = set()
        existing_rows = db.query(Member.bioguide_id, Member.id).filter(
            Member.bioguide_id.isnot(None)
        ).all()
        existing_map = {row[0]: row[1] for row in existing_rows}
        logger.info(f"Pre-loaded {len(existing_map)} existing members by bioguide_id")

        to_insert = []
        to_update = []

        for p in persons:
            bioguide_id = p.get("bioguide_id")
            if not bioguide_id:
                logger.warning(
                    f"Skipping person without bioguide_id: {p.get('canonical_name', 'unknown')} "
                    f"(person_id={p.get('person_id', 'N/A')})"
                )
                skipped_no_bioguide += 1
                continue

            fec_ids = p.get("fec_ids", []) or []
            wiki_title = p.get("wikipedia_title")
            wiki_qid = p.get("wikidata_qid")
            official_ids = {"fec": fec_ids}
            if wiki_title:
                official_ids["wikipedia"] = wiki_title
            if wiki_qid:
                official_ids["wikidata"] = wiki_qid

            member_committees = _assemble_committee_memberships(
                committee_memberships, entities, p["person_id"]
            )

            party = p.get("party")
            if party and len(party) > 64:
                party = party[:64]

            congress_val = _infer_congress_from_terms(terms, p["person_id"])
            scope = p.get("_scope", "historical")
            is_current = (scope == "current")

            if bioguide_id in existing_map:
                existing_id = existing_map[bioguide_id]
                to_update.append({
                    "id": existing_id,
                    "canonical_name": p["canonical_name"],
                    "display_name": p.get("display_name") or p["canonical_name"],
                    "aliases": p.get("aliases", []),
                    "person_type": p.get("person_type", "legislator"),
                    "party": party,
                    "chamber": p.get("chamber"),
                    "state": p.get("state"),
                    "district": p.get("district"),
                    "bioguide_id": bioguide_id,
                    "govtrack_id": p.get("govtrack_id"),
                    "opensecrets_id": p.get("opensecrets_id"),
                    "fec_candidate_id": fec_ids[0] if fec_ids else None,
                    "committee_memberships": member_committees,
                    "last_updated": now,
                    "latest_term_start": p.get("latest_term_start"),
                    "latest_term_end": p.get("latest_term_end"),
                    "official_ids": official_ids,
                    "congress": congress_val,
                    "member_scope": scope,
                    "is_current": is_current,
                })
                updated += 1
            else:
                to_insert.append(Member(
                    id=p["person_id"],
                    canonical_name=p["canonical_name"],
                    display_name=p.get("display_name") or p["canonical_name"],
                    aliases=p.get("aliases", []),
                    person_type=p.get("person_type", "legislator"),
                    party=party,
                    chamber=p.get("chamber"),
                    state=p.get("state"),
                    district=p.get("district"),
                    bioguide_id=bioguide_id,
                    govtrack_id=p.get("govtrack_id"),
                    opensecrets_id=p.get("opensecrets_id"),
                    fec_candidate_id=fec_ids[0] if fec_ids else None,
                    committee_memberships=member_committees,
                    source="uscl",
                    source_reliability="secondary",
                    extraction_method="yaml",
                    congress=congress_val,
                    last_updated=now,
                    latest_term_start=p.get("latest_term_start"),
                    latest_term_end=p.get("latest_term_end"),
                    official_ids=official_ids,
                    member_scope=scope,
                    is_current=is_current,
                ))
                inserted += 1

        # Bulk insert
        if to_insert:
            batch_size = 500
            for i in range(0, len(to_insert), batch_size):
                db.bulk_save_objects(to_insert[i:i + batch_size])
                db.flush()
            logger.info(f"Bulk inserted {len(to_insert)} members")

        # Bulk update
        if to_update:
            for batch in [to_update[i:i + 500] for i in range(0, len(to_update), 500)]:
                for upd in batch:
                    db.query(Member).filter(Member.id == upd["id"]).update({
                        "canonical_name": upd["canonical_name"],
                        "display_name": upd["display_name"],
                        "aliases": upd["aliases"],
                        "person_type": upd["person_type"],
                        "party": upd["party"],
                        "chamber": upd["chamber"],
                        "state": upd["state"],
                        "district": upd["district"],
                        "govtrack_id": upd["govtrack_id"],
                        "opensecrets_id": upd["opensecrets_id"],
                        "fec_candidate_id": upd["fec_candidate_id"],
                        "committee_memberships": upd["committee_memberships"],
                        "source": "uscl",
                        "source_reliability": "secondary",
                        "extraction_method": "yaml",
                        "last_updated": upd["last_updated"],
                        "latest_term_start": upd["latest_term_start"],
                        "latest_term_end": upd["latest_term_end"],
                        "official_ids": upd["official_ids"],
                        "congress": upd["congress"],
                        "member_scope": upd["member_scope"],
                        "is_current": upd["is_current"],
                    }, synchronize_session=False)
                db.flush()
            logger.info(f"Bulk updated {len(to_update)} members")

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info(
        f"Import complete: inserted={inserted}, updated={updated}, "
        f"skipped_no_bioguide={skipped_no_bioguide}, "
        f"total_persons={len(persons)}"
    )
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped_no_bioguide": skipped_no_bioguide,
        "total_persons": len(persons),
    }


def _infer_congress_from_terms(terms: list[dict], person_id: str) -> int | None:
    person_terms = [t for t in terms if t.get("person_id") == person_id]
    if not person_terms:
        return None
    sorted_terms = sorted(
        person_terms,
        key=lambda t: t.get("start_date", ""),
        reverse=True,
    )
    return sorted_terms[0].get("congress")


# ── CLI ──

def main():
    parser = argparse.ArgumentParser(
        description="Import real members from congress-legislators into main members table"
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
    args = parser.parse_args()

    vendor_dir = _resolve_vendor_dir(args.commit_sha, args.vendor_dir)

    try:
        check_vendor_data_exists(vendor_dir)
    except RealMembersImportError as exc:
        logger.error(str(exc))
        sys.exit(1)

    adapter = CongressLegislatorsAdapter(
        commit_sha=args.commit_sha,
        vendor_dir=vendor_dir,
    )

    try:
        Base.metadata.create_all(bind=engine)
        result = import_members_from_adapter(adapter, vendor_dir)
        print(f"\nReal members import complete:")
        print(f"  Inserted: {result['inserted']}")
        print(f"  Updated: {result['updated']}")
        print(f"  Skipped (no bioguide): {result['skipped_no_bioguide']}")
        print(f"  Total persons in source: {result['total_persons']}")
    except RealMembersImportError as exc:
        logger.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
