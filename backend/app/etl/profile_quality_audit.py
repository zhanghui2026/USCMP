"""Profile Quality Audit for v0.7.2.

Audits only current members. Identifies high-value legislators whose profiles
are still summary_only, and recommends which ones to fix with fixtures.

Output:
  1. Overall profile coverage statistics (current members only)
  2. Top 20 high-value candidates for fixture/snapshot
  3. Per-member status for the priority check list
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from app.db.postgres import SessionLocal

logger = logging.getLogger(__name__)

# High-priority check list from v0.7.2 spec
PRIORITY_CHECK_LIST = [
    "Pelosi", "Schumer", "McConnell", "Jeffries", "Johnson",
    "Sanders", "Warren", "Cruz", "Rubio", "Ocasio-Cortez",
    "Omar", "Paul", "Hawley", "Graham", "Schiff",
]

# High-value indicators for ranking
LEADERSHIP_TITLES = [
    "Speaker", "Majority Leader", "Minority Leader", "Majority Whip",
    "Minority Whip", "President pro tempore", "Chair",
]

HIGH_PROFILE_LAST_NAMES = (
    "Pelosi", "Schumer", "McConnell", "Jeffries", "Johnson",
    "Sanders", "Warren", "Cruz", "Rubio", "Ocasio-Cortez",
    "Omar", "Paul", "Hawley", "Graham", "Schiff",
    "AOC", "Tlaib", "Boebert", "Greene", "Gaetz",
    "Crenshaw", "Cheney", "Klobuchar", "Booker", "Murphy",
    "Cotton", "Scott", "Menendez", "Durbin", "Grassley",
    "Feinstein", "Markey", "Wyden", "Portman", "Collins",
    "Murkowski", "Manchin", "Sinema", "Kelly", "Ossoff",
)


@dataclass
class ProfileAuditEntry:
    member_id: str
    canonical_name: str
    display_name: str
    party: str | None
    chamber: str | None
    state: str | None
    bioguide_id: str | None
    congress: int | None
    wikipedia_title: str | None
    wikidata_qid: str | None
    profile_status: str
    source: str
    has_education: bool
    has_prior_positions: bool
    has_occupations: bool
    has_graph_facts: bool
    missing_fields: list[str] = field(default_factory=list)
    parsed_fields: list[str] = field(default_factory=list)
    why_high_value: str = ""
    suggested_fix: str = ""


def run_audit() -> dict[str, Any]:
    """Run full profile quality audit on current members."""
    db = SessionLocal()

    # 1. Overall stats
    stats = _get_overall_stats(db)
    print_statistics(stats)

    # 2. Find high-value summary_only profiles
    candidates = _find_high_value_candidates(db)
    print(f"\nFound {len(candidates)} high-value summary_only candidates")

    # 3. Check priority list
    priority_results = _check_priority_list(db)
    print("\n--- Priority Check List ---")
    for entry in priority_results:
        icon = _status_icon(entry.profile_status)
        print(f"  {icon} {entry.display_name:30s} ({entry.party}/{entry.state}) "
              f"status={entry.profile_status} edu={entry.has_education} "
              f"pos={entry.has_prior_positions} wiki={entry.wikipedia_title or 'none'}")

    # 4. Top 20
    top20 = sorted(
        candidates,
        key=lambda e: (
            0 if e.wikipedia_title else 1,
            0 if e.profile_status == "summary_only" else 1,
            -(len(e.parsed_fields)),
        ),
    )[:20]
    print("\n--- Top 20 Candidates for Fixture ---")
    for i, entry in enumerate(top20, 1):
        print(f"  {i:2d}. {entry.display_name:30s} {entry.party}/{entry.state} "
              f"status={entry.profile_status} wiki={entry.wikipedia_title or 'none'} "
              f"why={entry.why_high_value or 'general'} "
              f"fix={entry.suggested_fix}")

    db.close()

    return {
        "statistics": stats,
        "candidate_count": len(candidates),
        "top20": [
            {
                "name": e.display_name,
                "bioguide_id": e.bioguide_id,
                "wikipedia_title": e.wikipedia_title,
                "wikidata_qid": e.wikidata_qid,
                "profile_status": e.profile_status,
                "missing_fields": e.missing_fields,
                "why_high_value": e.why_high_value,
                "suggested_fix": e.suggested_fix,
            }
            for e in top20
        ],
        "priority_check": [
            {
                "name": e.display_name,
                "bioguide_id": e.bioguide_id,
                "profile_status": e.profile_status,
                "has_education": e.has_education,
                "has_prior_positions": e.has_prior_positions,
                "wikipedia_title": e.wikipedia_title,
            }
            for e in priority_results
        ],
    }


def _get_overall_stats(db) -> dict:
    stats = {}

    total = db.execute(text(
        "SELECT COUNT(*) FROM members WHERE is_current = TRUE"
    )).fetchone()[0]
    stats["current_members_total"] = total

    available = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE AND mp.profile_status = 'available'"
    )).fetchone()[0]
    stats["available_profiles"] = available

    partial = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE AND mp.profile_status = 'partial'"
    )).fetchone()[0]
    stats["partial_profiles"] = partial

    summary_only = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE AND mp.profile_status = 'summary_only'"
    )).fetchone()[0]
    stats["summary_only_profiles"] = summary_only

    with_profile = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE"
    )).fetchone()[0]
    stats["profiles_with_data"] = with_profile

    missing = total - with_profile
    stats["missing_profiles"] = missing

    with_edu = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE "
        "AND mp.education IS NOT NULL "
        "AND json_array_length(mp.education) > 0"
    )).fetchone()[0]
    stats["profiles_with_education"] = with_edu

    with_pos = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE "
        "AND mp.prior_positions IS NOT NULL "
        "AND json_array_length(mp.prior_positions) > 0"
    )).fetchone()[0]
    stats["profiles_with_prior_positions"] = with_pos

    with_occ = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE "
        "AND mp.occupations IS NOT NULL "
        "AND json_array_length(mp.occupations) > 0"
    )).fetchone()[0]
    stats["profiles_with_occupations"] = with_occ

    # Profiles that have been imported into the graph (available + partial)
    stats["profiles_with_graph_facts"] = available + partial

    with_wiki_id = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE "
        "AND mp.wikipedia_title IS NOT NULL"
    )).fetchone()[0]
    stats["profiles_with_wikipedia_title"] = with_wiki_id

    with_wiki_summary_only = db.execute(text(
        "SELECT COUNT(*) FROM member_profiles mp "
        "JOIN members m ON mp.member_id = m.id "
        "WHERE m.is_current = TRUE "
        "AND mp.wikipedia_title IS NOT NULL "
        "AND mp.profile_status = 'summary_only'"
    )).fetchone()[0]
    stats["wikipedia_titles_still_summary_only"] = with_wiki_summary_only

    return stats


def _find_high_value_candidates(db) -> list[ProfileAuditEntry]:
    """Find current members whose profiles are summary_only but are high-value."""
    rows = db.execute(text("""
        SELECT
            m.id, m.canonical_name, m.display_name,
            m.party, m.chamber, m.state,
            m.bioguide_id, m.congress,
            mp.wikipedia_title, mp.wikidata_qid,
            mp.profile_status, mp.source,
            CASE WHEN mp.education IS NOT NULL
                 AND json_array_length(mp.education) > 0 THEN TRUE ELSE FALSE END,
            CASE WHEN mp.prior_positions IS NOT NULL
                 AND json_array_length(mp.prior_positions) > 0 THEN TRUE ELSE FALSE END,
            CASE WHEN mp.occupations IS NOT NULL
                 AND json_array_length(mp.occupations) > 0 THEN TRUE ELSE FALSE END,
            COALESCE(mp.parsed_fields, '[]'::json) AS parsed_fields,
            COALESCE(mp.missing_fields, '[]'::json) AS missing_fields
        FROM members m
        LEFT JOIN member_profiles mp ON m.id = mp.member_id
        WHERE m.is_current = TRUE
        ORDER BY
            CASE WHEN mp.profile_status = 'summary_only' THEN 0
                 WHEN mp.profile_status IS NULL THEN 1
                 WHEN mp.profile_status = 'partial' THEN 2
                 ELSE 3 END,
            m.canonical_name
    """))

    candidates = []
    for row in rows:
        parsed = _jsonb_to_list(row[15])
        missing = _jsonb_to_list(row[16])

        entry = ProfileAuditEntry(
            member_id=row[0],
            canonical_name=row[1],
            display_name=row[2],
            party=row[3],
            chamber=row[4],
            state=row[5],
            bioguide_id=row[6],
            congress=row[7],
            wikipedia_title=row[8],
            wikidata_qid=row[9],
            profile_status=row[10] or "missing",
            source=row[11] or "unknown",
            has_education=bool(row[12]),
            has_prior_positions=bool(row[13]),
            has_occupations=bool(row[14]),
            has_graph_facts=row[10] in ("available", "partial"),
            missing_fields=missing,
            parsed_fields=parsed,
        )

        # Assign high-value reason and suggested fix
        entry.why_high_value = _classify_high_value(entry)
        entry.suggested_fix = _suggest_fix(entry)

        # Only include summary_only or missing for candidates
        if entry.profile_status in ("summary_only", "missing"):
            if entry.why_high_value:
                candidates.append(entry)

    return candidates


def _check_priority_list(db) -> list[ProfileAuditEntry]:
    """Check specific priority legislators."""
    results = []
    for name in PRIORITY_CHECK_LIST:
        row = db.execute(text("""
            SELECT
                m.id, m.canonical_name, m.display_name,
                m.party, m.chamber, m.state,
                m.bioguide_id, m.congress,
                mp.wikipedia_title, mp.wikidata_qid,
                mp.profile_status, mp.source,
                CASE WHEN mp.education IS NOT NULL
                     AND json_array_length(mp.education) > 0 THEN TRUE ELSE FALSE END,
                CASE WHEN mp.prior_positions IS NOT NULL
                     AND json_array_length(mp.prior_positions) > 0 THEN TRUE ELSE FALSE END,
                CASE WHEN mp.occupations IS NOT NULL
                     AND json_array_length(mp.occupations) > 0 THEN TRUE ELSE FALSE END,
                COALESCE(mp.parsed_fields, '[]'::json) AS parsed_fields,
                COALESCE(mp.missing_fields, '[]'::json) AS missing_fields
            FROM members m
            LEFT JOIN member_profiles mp ON m.id = mp.member_id
            WHERE m.is_current = TRUE AND m.canonical_name ILIKE :name
            LIMIT 1
        """), {"name": f"%{name}%"})

        r = row.fetchone()
        if not r:
            continue

        parsed = _jsonb_to_list(r[15])
        missing = _jsonb_to_list(r[16])

        entry = ProfileAuditEntry(
            member_id=r[0],
            canonical_name=r[1],
            display_name=r[2],
            party=r[3],
            chamber=r[4],
            state=r[5],
            bioguide_id=r[6],
            congress=r[7],
            wikipedia_title=r[8],
            wikidata_qid=r[9],
            profile_status=r[10] or "missing",
            source=r[11] or "unknown",
            has_education=bool(r[12]),
            has_prior_positions=bool(r[13]),
            has_occupations=bool(r[14]),
            has_graph_facts=r[10] in ("available", "partial"),
            missing_fields=missing,
            parsed_fields=parsed,
        )
        results.append(entry)

    return results


def _classify_high_value(entry: ProfileAuditEntry) -> str:
    reasons = []

    name = entry.display_name or entry.canonical_name
    last_name = name.split()[-1] if name else ""

    if last_name in HIGH_PROFILE_LAST_NAMES:
        reasons.append("high_profile")

    if entry.wikipedia_title and entry.profile_status == "summary_only":
        reasons.append("has_wikipedia_id_but_unparsed")

    if entry.congress and entry.congress >= 117:
        reasons.append("recent_congress")

    if entry.chamber == "senate":
        reasons.append("senator")

    if not reasons:
        reasons.append("current_member")

    return ", ".join(reasons)


def _suggest_fix(entry: ProfileAuditEntry) -> str:
    if entry.wikipedia_title and entry.profile_status == "summary_only":
        return "fixture"
    if entry.profile_status == "missing":
        if entry.wikipedia_title:
            return "fixture"
        return "wait_for_api"
    return "wait_for_api"


def _status_icon(status: str) -> str:
    icons = {
        "available": "[OK]",
        "partial": "[--]",
        "summary_only": "[!!]",
        "missing": "[XX]",
    }
    return icons.get(status, "[??]")


def _jsonb_to_list(val) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return []
    return list(val) if hasattr(val, "__iter__") else []


def print_statistics(stats: dict) -> None:
    print("=" * 60)
    print("PROFILE QUALITY AUDIT - Current Members Only")
    print("=" * 60)
    print(f"  Current members total:           {stats['current_members_total']:>6}")
    print(f"  Available profiles:              {stats['available_profiles']:>6}  ({_pct(stats['available_profiles'], stats['current_members_total'])}%)")
    print(f"  Partial profiles:                {stats['partial_profiles']:>6}  ({_pct(stats['partial_profiles'], stats['current_members_total'])}%)")
    print(f"  Summary-only profiles:           {stats['summary_only_profiles']:>6}  ({_pct(stats['summary_only_profiles'], stats['current_members_total'])}%)")
    print(f"  Missing profiles:                {stats['missing_profiles']:>6}  ({_pct(stats['missing_profiles'], stats['current_members_total'])}%)")
    print(f"  Profiles with education:         {stats['profiles_with_education']:>6}")
    print(f"  Profiles with prior positions:   {stats['profiles_with_prior_positions']:>6}")
    print(f"  Profiles with occupations:       {stats['profiles_with_occupations']:>6}")
    print(f"  Profiles with graph facts:       {stats['profiles_with_graph_facts']:>6}")
    print(f"  Profiles with Wikipedia title:   {stats['profiles_with_wikipedia_title']:>6}")
    print(f"  Wikipedia titles still s/o:      {stats['wikipedia_titles_still_summary_only']:>6}")
    print()


def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0.0"
    return f"{part / total * 100:.1f}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_audit()
