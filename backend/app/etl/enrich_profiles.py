"""
Batch profile enrichment pipeline (v0.8).

Processes current members only, elevating profile status from summary_only
to partial/available using structured snapshot data.

Two modes:
  online   – fetch from Wikipedia/Wikidata API (requires network)
  snapshot – read from local data/external/wikipedia-profiles/

Matching: bioguide_id → wikidata_qid → wikipedia_title
Protection: existing available profiles are never downgraded

Usage:
    # Snapshot mode (primary)
    python3 -m app.etl.enrich_profiles --mode snapshot
    python3 -m app.etl.enrich_profiles --mode snapshot --dry-run
    python3 -m app.etl.enrich_profiles --mode snapshot --limit 20

    # Online mode (requires Wikipedia API access)
    python3 -m app.etl.enrich_profiles --mode online
    python3 -m app.etl.enrich_profiles --mode online --dry-run --limit 5

    # Generate coverage report
    python3 -m app.etl.enrich_profiles --mode report
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.postgres import SessionLocal, engine
from app.models.sqlalchemy.models import Base, Member, MemberProfile
from app.etl.profile_status import compute_profile_status
from app.core.logging import logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "external" / "wikipedia-profiles"


# ── snapshot loading ────────────────────────────────────────────────────────


def load_snapshots(
    snapshot_dir: str | None = None,
) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """Load JSON snapshot files, indexed three ways.

    Returns:
        (by_bioguide, by_qid, by_title)
    """
    sd = Path(snapshot_dir) if snapshot_dir else DEFAULT_SNAPSHOT_DIR

    by_bioguide: dict[str, dict] = {}
    by_qid: dict[str, dict] = {}
    by_title: dict[str, dict] = {}

    if not sd.is_dir():
        logger.warning(f"Snapshot directory not found: {sd}")
        return by_bioguide, by_qid, by_title

    for fpath in sd.glob("*.json"):
        try:
            snap = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning(f"Skipping invalid snapshot {fpath}: {exc}")
            continue

        bg = snap.get("bioguide_id")
        qid = snap.get("wikidata_qid")
        title = snap.get("wikipedia_title")

        if bg:
            by_bioguide[bg] = snap
        if qid:
            by_qid[qid] = snap
        if title:
            by_title[title] = snap

    json_files = list(sd.glob("*.json"))
    logger.info(
        f"Loaded {len(json_files)} snapshot files: "
        f"{len(by_bioguide)} by bioguide, {len(by_qid)} by qid, {len(by_title)} by title"
    )
    return by_bioguide, by_qid, by_title


# ── matching ─────────────────────────────────────────────────────────────────


def match_member(
    member: Member,
    by_bioguide: dict[str, dict],
    by_qid: dict[str, dict],
    by_title: dict[str, dict],
) -> dict | None:
    """Find best matching snapshot for a member."""
    if member.bioguide_id and member.bioguide_id in by_bioguide:
        return by_bioguide[member.bioguide_id]

    wiki_info = member.official_ids or {}
    wiki_qid = wiki_info.get("wikidata")
    wiki_title = wiki_info.get("wikipedia")

    if wiki_qid and wiki_qid in by_qid:
        return by_qid[wiki_qid]
    if wiki_title and wiki_title in by_title:
        return by_title[wiki_title]

    return None


# ── online fetch ─────────────────────────────────────────────────────────────


def _fetch_profiles_online(db, limit: int | None = None) -> dict[str, dict]:
    """Fetch profiles via Wikipedia API (online mode), save snapshots."""
    from app.etl.adapters.wikipedia_profile_adapter import WikipediaProfileAdapter

    sd = DEFAULT_SNAPSHOT_DIR
    sd.mkdir(parents=True, exist_ok=True)

    adapter = WikipediaProfileAdapter(rate_delay=0.3)
    snapshots: dict[str, dict] = {}

    members = db.query(Member).filter(Member.is_current == True).all()
    members = [m for m in members if m.bioguide_id]  # noqa: E712
    if limit:
        members = members[:limit]

    for i, member in enumerate(members):
        wiki_info = member.official_ids or {}
        wiki_title = wiki_info.get("wikipedia")
        wiki_qid = wiki_info.get("wikidata")

        if not wiki_title and not wiki_qid:
            continue

        logger.info(f"Fetching [{i + 1}/{len(members)}] {member.display_name}")
        profile_data = adapter.fetch_profile(wiki_title, wiki_qid)

        if profile_data and profile_data.get("short_summary"):
            snapshots[member.bioguide_id] = profile_data
            fpath = sd / f"{member.bioguide_id}.json"
            fpath.write_text(json.dumps(profile_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        else:
            logger.warning(f"No profile data for {member.display_name}")

    logger.info(f"Fetched {len(snapshots)} profiles via Wikipedia API (online)")
    return snapshots


# ── core enrichment ──────────────────────────────────────────────────────────


def _normalize_profile_fields(snapshot: dict) -> dict[str, Any]:
    """Convert snapshot data to canonical profile fields."""
    return {
        "wikipedia_title": snapshot.get("wikipedia_title"),
        "wikipedia_url": snapshot.get("wikipedia_url"),
        "wikidata_qid": snapshot.get("wikidata_qid"),
        "image_url": snapshot.get("image_url"),
        "short_summary": snapshot.get("short_summary"),
        "birth_date": snapshot.get("birth_date"),
        "birth_place": snapshot.get("birth_place"),
        "education": snapshot.get("education") or [],
        "occupations": snapshot.get("occupations") or [],
        "prior_positions": snapshot.get("prior_positions") or [],
        "employers": snapshot.get("employers") or [],
        "military_service": snapshot.get("military_service") or [],
        "profile_sources": snapshot.get("profile_sources") or {},
    }


def enrich_profiles(
    mode: str = "snapshot",
    snapshot_dir: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run the enrichment pipeline."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    stats = {
        "mode": mode,
        "snapshots_loaded": 0,
        "current_members": 0,
        "matched": 0,
        "imported": 0,
        "updated": 0,
        "upgraded_to_available": 0,
        "upgraded_to_partial": 0,
        "skipped_existing_available": 0,
        "skipped_no_match": 0,
    }

    try:
        # ── load snapshots ──
        if mode == "online":
            snapshots = _fetch_profiles_online(db, limit)
            by_bioguide = {k: v for k, v in snapshots.items()}
            by_qid: dict[str, dict] = {}
            by_title: dict[str, dict] = {}
            for snap in snapshots.values():
                qid = snap.get("wikidata_qid")
                title = snap.get("wikipedia_title")
                if qid:
                    by_qid[qid] = snap
                if title:
                    by_title[title] = snap
            stats["snapshots_loaded"] = len(snapshots)
        elif mode == "report":
            return _generate_coverage_report(db)
        else:
            by_bioguide, by_qid, by_title = load_snapshots(snapshot_dir)
            stats["snapshots_loaded"] = len(by_bioguide)

        if stats["snapshots_loaded"] == 0 and mode != "report":
            logger.warning("No snapshots loaded. Pipeline will produce no changes.")

        # ── iterate current members ──
        members = db.query(Member).filter(Member.is_current == True).all()  # noqa: E712
        members = [m for m in members if m.bioguide_id]
        if limit and mode != "report":
            members = members[:limit]
        stats["current_members"] = len(members)

        existing_profiles = {
            row[0]: (row[1], row[2], row[3])
            for row in db.query(
                MemberProfile.bioguide_id,
                MemberProfile.id,
                MemberProfile.profile_status,
                MemberProfile.source,
            ).all()
        }

        for member in members:
            snap = match_member(member, by_bioguide, by_qid, by_title)
            if snap is None:
                stats["skipped_no_match"] += 1
                continue

            stats["matched"] += 1
            existing = existing_profiles.get(member.bioguide_id)

            # Protection: existing available profiles are never downgraded or overwritten
            if existing:
                existing_id, existing_status, existing_source = existing
                if existing_status == "available":
                    stats["skipped_existing_available"] += 1
                    continue

            # Build profile fields
            profile_fields = _normalize_profile_fields(snap)
            profile_status, parsed, missing = compute_profile_status(profile_fields)

            source = profile_fields.get("wikipedia_title")
            profile_fields.update({
                "profile_status": profile_status,
                "parsed_fields": parsed,
                "missing_fields": missing,
                "source": "wikipedia_snapshot" if mode == "snapshot" else "wikipedia",
                "source_reliability": "external_open_content",
                "last_updated": datetime.now(timezone.utc),
            })

            if dry_run:
                logger.info(
                    f"  [DRY-RUN] {member.display_name}: "
                    f"{existing_status if existing else 'summary_only'} -> {profile_status}"
                )
                if existing_status == "summary_only" and profile_status == "available":
                    stats["upgraded_to_available"] += 1
                elif existing_status == "summary_only" and profile_status == "partial":
                    stats["upgraded_to_partial"] += 1
            else:
                profile_id = f"wikipedia_profile_{member.bioguide_id}"
                if existing:
                    db.query(MemberProfile).filter(
                        MemberProfile.bioguide_id == member.bioguide_id
                    ).update(profile_fields, synchronize_session=False)
                    stats["updated"] += 1
                    if existing[1] == "summary_only" and profile_status == "available":
                        stats["upgraded_to_available"] += 1
                    elif existing[1] == "summary_only" and profile_status == "partial":
                        stats["upgraded_to_partial"] += 1
                    logger.info(f"  Updated: {member.display_name} -> {profile_status}")
                else:
                    profile = MemberProfile(
                        id=profile_id,
                        member_id=member.id,
                        bioguide_id=member.bioguide_id,
                        **profile_fields,
                    )
                    db.add(profile)
                    stats["imported"] += 1
                    if profile_status == "available":
                        stats["upgraded_to_available"] += 1
                    elif profile_status == "partial":
                        stats["upgraded_to_partial"] += 1
                    logger.info(f"  Imported: {member.display_name} -> {profile_status}")

        if not dry_run:
            db.commit()
        else:
            db.rollback()

    except Exception as exc:
        db.rollback()
        logger.error(f"Enrichment failed: {exc}")
        raise
    finally:
        db.close()

    return stats


# ── coverage report ──────────────────────────────────────────────────────────


def _generate_coverage_report(db) -> dict[str, Any]:
    """Generate current-only profile coverage report."""
    from sqlalchemy import func

    total_current = db.query(Member).filter(Member.is_current == True).count()  # noqa: E712

    current_bioguides = {
        m.bioguide_id
        for m in db.query(Member.bioguide_id).filter(Member.is_current == True).all()  # noqa: E712
        if m.bioguide_id
    }

    profiles = db.query(MemberProfile).filter(
        MemberProfile.bioguide_id.in_(current_bioguides)
    ).all()

    by_status: dict[str, int] = {"available": 0, "partial": 0, "summary_only": 0}
    for p in profiles:
        by_status[p.profile_status] = by_status.get(p.profile_status, 0) + 1

    no_profile = total_current - sum(by_status.values())

    report = {
        "total_current_members": total_current,
        "profiles_with_status": {
            "available": by_status.get("available", 0),
            "partial": by_status.get("partial", 0),
            "summary_only": by_status.get("summary_only", 0),
            "no_profile": no_profile,
        },
        "coverage_pct": {
            "available": round(by_status.get("available", 0) / total_current * 100, 1) if total_current else 0,
            "partial": round(by_status.get("partial", 0) / total_current * 100, 1) if total_current else 0,
            "summary_only": round(by_status.get("summary_only", 0) / total_current * 100, 1) if total_current else 0,
            "enriched": round(
                (by_status.get("available", 0) + by_status.get("partial", 0)) / total_current * 100, 1
            ) if total_current else 0,
        },
    }

    logger.info(f"Coverage report: {json.dumps(report, indent=2)}")
    return report


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="v0.8 batch profile enrichment")
    parser.add_argument("--mode", choices=["snapshot", "online", "report"], default="snapshot",
                        help="Enrichment mode (default: snapshot)")
    parser.add_argument("--snapshot-dir", help="Path to snapshot directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing")
    parser.add_argument("--limit", type=int, help="Limit number of members to process")
    args = parser.parse_args()

    stats = enrich_profiles(
        mode=args.mode,
        snapshot_dir=args.snapshot_dir,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    if args.mode == "report":
        return

    print("\n=== Enrichment Results ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if args.dry_run:
        print("\n[Dry run — no changes committed]")


if __name__ == "__main__":
    main()
