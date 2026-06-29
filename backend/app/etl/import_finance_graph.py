"""v0.93: Sync campaign finance data from PostgreSQL to Neo4j.

Creates CampaignCommittee, Donor, and ContributionSource nodes,
and ASSOCIATED_WITH_COMMITTEE, CONTRIBUTED_TO, HAS_CONTRIBUTION_SOURCE edges.

Usage:
    python -m app.etl.import_finance_graph [--cycle 2024] [--limit 1000] [--dry-run]
"""

import argparse
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import text

from app.db.postgres import SessionLocal
from app.db.neo4j import get_driver


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aggregate_contributions(db, committee_ids: set[str]) -> dict:
    """Aggregate contributions by (committee_id, donor_id) pair.

    Returns dict mapping (committee_id, donor_id) -> {
        total_amount, count, first_date, last_date, types
    }
    """
    if not committee_ids:
        return {}

    result = db.execute(text("""
        SELECT committee_id, donor_id,
               SUM(amount) as total_amount,
               COUNT(*) as cnt,
               MIN(contribution_date) as first_date,
               MAX(contribution_date) as last_date,
               ARRAY_AGG(DISTINCT contribution_type) as types
        FROM contributions
        WHERE committee_id = ANY(:ids)
        GROUP BY committee_id, donor_id
    """), {"ids": list(committee_ids)}).fetchall()

    agg = {}
    for r in result:
        agg[(r.committee_id, r.donor_id)] = {
            "total_amount": float(r.total_amount or 0),
            "count": r.cnt,
            "first_date": str(r.first_date) if r.first_date else None,
            "last_date": str(r.last_date) if r.last_date else None,
            "types": r.types or [],
        }
    return agg


def _aggregate_by_committee(db, committee_ids: set[str]) -> dict:
    """Aggregate contributions by committee_id.

    Returns dict mapping committee_id -> {total_amount, count, donor_count}
    """
    if not committee_ids:
        return {}

    result = db.execute(text("""
        SELECT committee_id,
               SUM(amount) as total_amount,
               COUNT(*) as cnt,
               COUNT(DISTINCT donor_id) as donor_count
        FROM contributions
        WHERE committee_id = ANY(:ids)
        GROUP BY committee_id
    """), {"ids": list(committee_ids)}).fetchall()

    agg = {}
    for r in result:
        agg[r.committee_id] = {
            "total_amount": float(r.total_amount or 0),
            "count": r.cnt,
            "donor_count": r.donor_count,
        }
    return agg


def import_finance_graph(cycle: int = 2024, limit: int | None = None, dry_run: bool = False) -> dict:
    """Sync campaign finance data from PostgreSQL to Neo4j.

    Returns import statistics.
    """
    stats = {
        "committees_merged": 0,
        "donors_merged": 0,
        "contribution_sources_merged": 0,
        "associated_edges": 0,
        "contributed_edges": 0,
        "source_edges": 0,
        "skipped_no_person": 0,
        "skipped_no_donor": 0,
    }

    db = SessionLocal()
    try:
        # Step 1: Get committees linked to current members
        committees = db.execute(text("""
            SELECT cc.id, cc.fec_committee_id, cc.name, cc.party, cc.state,
                   cc.chamber, cc.cycle, cc.source, cc.candidate_id
            FROM campaign_committees cc
            JOIN members m ON cc.candidate_id = m.id
            WHERE m.is_current = true AND cc.candidate_id IS NOT NULL
        """)).fetchall()

        committee_map = {c.id: c for c in committees}
        committee_ids = set(committee_map.keys())
        print(f"Found {len(committees)} committees linked to current members")

        # Step 2: Get donors for these committees
        contrib_aggs = _aggregate_contributions(db, committee_ids)
        donor_ids = {did for (_, did) in contrib_aggs.keys()}
        donors = {}
        if donor_ids:
            donor_rows = db.execute(text("""
                SELECT id, name, donor_type, industry, state, employer, source
                FROM donors WHERE id = ANY(:ids)
            """), {"ids": list(donor_ids)}).fetchall()
            donors = {d.id: d for d in donor_rows}
        print(f"Found {len(donors)} unique donors across {len(contrib_aggs)} contribution pairs")

        # Step 3: Aggregate by committee for committee-level stats
        cmte_aggs = _aggregate_by_committee(db, committee_ids)

        # Step 4: Get person IDs (member id -> Neo4j person id)
        member_ids = {c.candidate_id for c in committees}
        persons = db.execute(text("""
            SELECT id, display_name FROM members WHERE id = ANY(:ids)
        """), {"ids": list(member_ids)}).fetchall()
        person_ids = {p.id for p in persons}
        print(f"Found {len(person_ids)} current members with person nodes")

        # Filter committees to only those with existing person nodes
        valid_committees = [c for c in committees if c.candidate_id in person_ids]
        print(f"Valid committees (person exists): {len(valid_committees)}")

        if dry_run:
            print("[DRY RUN] Would import:")
            print(f"  - {len(valid_committees)} CampaignCommittee nodes")
            print(f"  - {len(donors)} Donor nodes")
            print(f"  - 1 ContributionSource node")
            print(f"  - {len(valid_committees)} ASSOCIATED_WITH_COMMITTEE edges")
            print(f"  - {len(contrib_aggs)} CONTRIBUTED_TO edges")
            print(f"  - {len(valid_committees)} HAS_CONTRIBUTION_SOURCE edges")
            return stats

        # Apply limit
        if limit:
            valid_committees = valid_committees[:limit]
            print(f"Limited to {limit} committees")

        driver = get_driver()
        now = _now_iso()

        with driver.session() as session:
            # Step 5: Merge ContributionSource node (single FEC source)
            session.run("""
                MERGE (cs:ContributionSource {id: 'fec_bulk_2024'})
                SET cs.name = 'FEC.gov Bulk Downloads',
                    cs.source_type = 'government',
                    cs.url = 'https://www.fec.gov/data/browse-data/?tab=bulk-data',
                    cs.reliability = 'high',
                    cs.last_updated = $now
            """, {"now": now})
            stats["contribution_sources_merged"] = 1

            # Step 6: Merge CampaignCommittee nodes
            for cmte in valid_committees:
                agg = cmte_aggs.get(cmte.id, {})
                session.run("""
                    MERGE (cc:CampaignCommittee {id: $id})
                    SET cc.fec_committee_id = $fec_id,
                        cc.name = $name,
                        cc.party = $party,
                        cc.state = $state,
                        cc.chamber = $chamber,
                        cc.cycle = $cycle,
                        cc.source = $source,
                        cc.amount_total = $amount_total,
                        cc.contribution_count = $contrib_count,
                        cc.donor_count = $donor_count,
                        cc.last_updated = $now
                """, {
                    "id": f"cmte_{cmte.id}",
                    "fec_id": cmte.fec_committee_id,
                    "name": cmte.name,
                    "party": cmte.party,
                    "state": cmte.state,
                    "chamber": cmte.chamber,
                    "cycle": cmte.cycle,
                    "source": cmte.source,
                    "amount_total": agg.get("total_amount", 0),
                    "contrib_count": agg.get("count", 0),
                    "donor_count": agg.get("donor_count", 0),
                    "now": now,
                })
                stats["committees_merged"] += 1

            # Step 7: Merge Donor nodes (only for donors with contributions)
            for donor_id, donor in donors.items():
                # Check if this donor has any contributions to valid committees
                has_contrib = any(
                    (cmte_id, donor_id) in contrib_aggs
                    for cmte_id in committee_ids
                )
                if not has_contrib:
                    stats["skipped_no_donor"] += 1
                    continue

                session.run("""
                    MERGE (d:Donor {id: $id})
                    SET d.name = $name,
                        d.donor_type = $donor_type,
                        d.industry = $industry,
                        d.state = $state,
                        d.employer = $employer,
                        d.source = $source,
                        d.last_updated = $now
                """, {
                    "id": f"donor_{donor_id}",
                    "name": donor.name,
                    "donor_type": donor.donor_type,
                    "industry": donor.industry,
                    "state": donor.state,
                    "employer": donor.employer,
                    "source": donor.source,
                    "now": now,
                })
                stats["donors_merged"] += 1

            # Step 8: Create ASSOCIATED_WITH_COMMITTEE edges (Person -> CampaignCommittee)
            for cmte in valid_committees:
                agg = cmte_aggs.get(cmte.id, {})
                session.run("""
                    MATCH (p:Person {id: $person_id})
                    MATCH (cc:CampaignCommittee {id: $cmte_id})
                    MERGE (p)-[r:ASSOCIATED_WITH_COMMITTEE]->(cc)
                    SET r.cycle = $cycle,
                        r.amount_total = $amount_total,
                        r.contribution_count = $contrib_count,
                        r.source = $source,
                        r.source_reliability = 'high',
                        r.last_updated = $now
                """, {
                    "person_id": cmte.candidate_id,
                    "cmte_id": f"cmte_{cmte.id}",
                    "cycle": cmte.cycle,
                    "amount_total": agg.get("total_amount", 0),
                    "contrib_count": agg.get("count", 0),
                    "source": "fec",
                    "now": now,
                })
                stats["associated_edges"] += 1

            # Step 9: Create CONTRIBUTED_TO edges (Donor -> CampaignCommittee)
            for (cmte_id, donor_id), agg in contrib_aggs.items():
                if cmte_id not in committee_ids:
                    continue
                if donor_id not in donors:
                    stats["skipped_no_donor"] += 1
                    continue

                cmte = committee_map.get(cmte_id)
                if not cmte or cmte.candidate_id not in person_ids:
                    stats["skipped_no_person"] += 1
                    continue

                # Parse types
                types = agg.get("types", [])
                primary_type = types[0] if types else "individual"

                session.run("""
                    MATCH (d:Donor {id: $donor_id})
                    MATCH (cc:CampaignCommittee {id: $cmte_id})
                    MERGE (d)-[r:CONTRIBUTED_TO]->(cc)
                    SET r.cycle = $cycle,
                        r.amount_total = $amount_total,
                        r.contribution_count = $count,
                        r.contribution_type = $contrib_type,
                        r.first_date = $first_date,
                        r.last_date = $last_date,
                        r.source = 'fec',
                        r.source_reliability = 'high',
                        r.last_updated = $now
                """, {
                    "donor_id": f"donor_{donor_id}",
                    "cmte_id": f"cmte_{cmte_id}",
                    "cycle": cmte.cycle,
                    "amount_total": agg["total_amount"],
                    "count": agg["count"],
                    "contrib_type": primary_type,
                    "first_date": agg.get("first_date"),
                    "last_date": agg.get("last_date"),
                    "now": now,
                })
                stats["contributed_edges"] += 1

            # Step 10: Create HAS_CONTRIBUTION_SOURCE edges (CampaignCommittee -> ContributionSource)
            for cmte in valid_committees:
                session.run("""
                    MATCH (cc:CampaignCommittee {id: $cmte_id})
                    MATCH (cs:ContributionSource {id: 'fec_bulk_2024'})
                    MERGE (cc)-[r:HAS_CONTRIBUTION_SOURCE]->(cs)
                    SET r.cycle = $cycle,
                        r.source = 'fec',
                        r.source_reliability = 'high',
                        r.last_updated = $now
                """, {
                    "cmte_id": f"cmte_{cmte.id}",
                    "cycle": cmte.cycle,
                    "now": now,
                })
                stats["source_edges"] += 1

    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import finance graph data")
    parser.add_argument("--cycle", type=int, default=2024, help="Election cycle")
    parser.add_argument("--limit", type=int, default=None, help="Max committees to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported")
    args = parser.parse_args()

    print(f"Importing finance graph for cycle {args.cycle}...")
    stats = import_finance_graph(args.cycle, args.limit, args.dry_run)

    print("\n=== Import Statistics ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("\nDone.")


if __name__ == "__main__":
    main()
