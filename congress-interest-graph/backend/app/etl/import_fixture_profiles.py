"""Targeted fixture import for priority leadership profiles.

Unlike the full profile import, this script only processes members that have
fixture data available. It skips the Wikipedia API for non-fixture members,
making it suitable for use when the Wikipedia API is unreachable.

Usage:
    python3 -m app.etl.import_fixture_profiles
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.db.postgres import SessionLocal, engine
from app.models.sqlalchemy.models import Base, Member, MemberProfile
from app.etl.adapters.wikipedia_profile_adapter import WikipediaProfileAdapter
from app.etl.profile_status import compute_profile_status
from app.core.logging import logger


def _load_all_fixtures() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """Load all fixture data, indexed three ways for flexible matching.

    Returns:
        (by_bioguide, by_title, by_qid) — each mapping ID to fixture dict
    """
    by_bioguide: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    by_qid: dict[str, dict] = {}

    def _index(fixture: dict):
        bg = fixture.get("bioguide_id")
        title = fixture.get("wikipedia_title")
        qid = fixture.get("wikidata_qid")
        if bg:
            by_bioguide[bg] = fixture
        if title:
            by_title[title] = fixture
        if qid:
            by_qid[qid] = fixture

    # Base fixtures (wikipedia_profiles)
    try:
        from tests.fixtures.wikipedia_profiles import FIXTURE_PROFILES as _f
        for title, val in _f.items():
            if not val.get("wikipedia_title"):
                val["wikipedia_title"] = title
            _index(dict(val))
        logger.info(f"Loaded {len(_f)} base fixtures")
    except ImportError:
        logger.warning("Could not load base fixtures")

    # Priority leadership fixtures
    try:
        from tests.fixtures.priority_leadership_fixtures import FIXTURES as _pl
        for f in _pl:
            _index(f)
        logger.info(f"Loaded {len(_pl)} priority leadership fixtures")
    except ImportError:
        logger.warning("Could not load priority leadership fixtures")

    logger.info(f"Fixture index: {len(by_bioguide)} by bioguide, {len(by_title)} by title, {len(by_qid)} by qid")
    return by_bioguide, by_title, by_qid


def _find_fixture(
    member,
    by_bioguide: dict[str, dict],
    by_title: dict[str, dict],
    by_qid: dict[str, dict],
) -> dict | None:
    """Find the best matching fixture for a member, in priority order."""
    if member.bioguide_id and member.bioguide_id in by_bioguide:
        return by_bioguide[member.bioguide_id]

    wiki_info = member.official_ids or {}
    wiki_title = wiki_info.get("wikipedia")
    wiki_qid = wiki_info.get("wikidata")

    if wiki_qid and wiki_qid in by_qid:
        return by_qid[wiki_qid]

    if wiki_title and wiki_title in by_title:
        return by_title[wiki_title]

    return None


def import_fixture_profiles() -> dict:
    """Import profiles only for members that have fixture data available."""
    Base.metadata.create_all(bind=engine)

    by_bioguide, by_title, by_qid = _load_all_fixtures()
    total_fixtures = len(set(list(by_bioguide.keys()) + list(by_title.keys())))

    db = SessionLocal()
    stats = {
        "fixtures_indexed": total_fixtures,
        "members_checked": 0,
        "imported": 0,
        "updated": 0,
        "skipped_already_available": 0,
        "no_match": 0,
        "no_bioguide": 0,
    }

    try:
        members = db.query(Member).filter(Member.source == "uscl").all()
        stats["members_checked"] = len(members)

        existing_profiles = {
            row[0]: (row[1], row[2], row[3])
            for row in db.query(
                MemberProfile.bioguide_id, MemberProfile.id, MemberProfile.profile_status, MemberProfile.source,
            ).all()
        }

        for member in members:
            if not member.bioguide_id:
                stats["no_bioguide"] += 1
                continue

            fixture = _find_fixture(member, by_bioguide, by_title, by_qid)
            if fixture is None:
                stats["no_match"] += 1
                continue

            # Protection: skip live Wikipedia profiles; allow upgrading summary_only and wikipedia_snapshot
            existing_info = existing_profiles.get(member.bioguide_id)
            if existing_info:
                _, existing_status, existing_source = existing_info
                if existing_status == "available" and existing_source == "wikipedia":
                    stats["skipped_already_available"] += 1
                    logger.debug(f"  Skipped (already available from live Wikipedia): {member.display_name}")
                    continue
                if existing_status == "available" and existing_source == "fixture":
                    stats["skipped_already_available"] += 1
                    logger.debug(f"  Skipped (already available from fixture): {member.display_name}")
                    continue

            # Fetch profile data through adapter
            from app.etl.adapters.wikipedia_profile_adapter import WikipediaProfileAdapter
            title = fixture.get("wikipedia_title") or (member.official_ids or {}).get("wikipedia", "")
            adapter = WikipediaProfileAdapter(rate_delay=0.0, fixtures={title: fixture})
            profile_data = adapter.fetch_profile(title, fixture.get("wikidata_qid"))

            if profile_data is None:
                stats["no_match"] += 1
                continue

            now = datetime.now(timezone.utc)
            profile_id = f"wikipedia_profile_{member.bioguide_id}"
            existing_id = existing_info[0] if existing_info else None

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
                "employers": profile_data.get("employers") or [],
                "external_links": profile_data.get("external_links") or [],
                "profile_sources": profile_data.get("profile_sources") or {},
                "source": profile_data.get("source", "fixture") or "fixture",
                "source_reliability": "external_open_content",
                "last_updated": now,
            }

            profile_status, parsed, missing = compute_profile_status(profile_fields)
            profile_fields["profile_status"] = profile_status
            profile_fields["parsed_fields"] = parsed
            profile_fields["missing_fields"] = missing

            if existing_id:
                db.query(MemberProfile).filter(
                    MemberProfile.id == existing_id
                ).update(profile_fields, synchronize_session=False)
                stats["updated"] += 1
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
                logger.info(f"  Imported: {member.display_name} -> {profile_status}")

        db.commit()
        logger.info(
            f"Fixture import complete: imported={stats['imported']}, "
            f"updated={stats['updated']}, skipped_already_available={stats['skipped_already_available']}, "
            f"no_match={stats['no_match']}"
        )

    except Exception as exc:
        db.rollback()
        logger.error(f"Fixture import failed: {exc}")
        raise
    finally:
        db.close()

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import_fixture_profiles()
