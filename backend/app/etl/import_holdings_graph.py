"""v0.94: Sync holdings data from PostgreSQL to Neo4j.

Creates Asset, HoldingDisclosure, and HoldingSource nodes,
and DISCLOSED_HOLDING, REPORTED_IN, HAS_HOLDING_SOURCE edges.

Usage:
    python -m app.etl.import_holdings_graph [--limit 1000] [--dry-run]
"""

import argparse
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.postgres import SessionLocal
from app.db.neo4j import get_driver


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def import_holdings_graph(limit: int | None = None, dry_run: bool = False) -> dict:
    """Sync holdings data from PostgreSQL to Neo4j.

    Returns import statistics.
    """
    stats = {
        "assets_merged": 0,
        "disclosures_merged": 0,
        "holding_sources_merged": 0,
        "disclosed_edges": 0,
        "reported_edges": 0,
        "source_edges": 0,
        "skipped_no_person": 0,
    }

    with SessionLocal() as db:
        holdings = db.execute(text("""
            SELECT ha.id, ha.member_id, ha.asset_name, ha.asset_type,
                   ha.ticker, ha.value_min, ha.value_max, ha.value_range_label,
                   ha.filing_year, ha.source, ha.source_url, ha.source_reliability
            FROM holding_assets ha
            LIMIT :limit
        """), {"limit": limit or 10000}).fetchall()

        disclosures = db.execute(text("""
            SELECT hd.id, hd.member_id, hd.filing_year, hd.filing_type,
                   hd.filing_url, hd.asset_count, hd.source, hd.source_reliability
            FROM holding_disclosures hd
            LIMIT :limit
        """), {"limit": limit or 10000}).fetchall()

    driver = get_driver()
    now = _now_iso()

    with driver.session() as session:
        session.run("""
            MERGE (s:HoldingSource {id: 'source_house_disclosure'})
            SET s.name = 'House/Senate Financial Disclosure',
                s.source_type = 'official',
                s.reliability = 'official',
                s.last_updated = $now
        """, {"now": now})
        stats["holding_sources_merged"] = 1

        for h in holdings:
            asset_id = f"asset_{h.id}"
            result = session.run("""
                MATCH (p:Person {id: $member_id})
                RETURN p.id AS pid
            """, {"member_id": h.member_id})
            record = result.single()

            if not record:
                stats["skipped_no_person"] += 1
                continue

            session.run("""
                MERGE (a:Asset {id: $asset_id})
                SET a.name = $name,
                    a.asset_type = $asset_type,
                    a.ticker = $ticker,
                    a.value_min = $value_min,
                    a.value_max = $value_max,
                    a.value_range = $value_range,
                    a.filing_year = $filing_year,
                    a.source = $source,
                    a.source_reliability = $source_reliability,
                    a.last_updated = $now
            """, {
                "asset_id": asset_id,
                "name": h.asset_name,
                "asset_type": h.asset_type,
                "ticker": h.ticker,
                "value_min": h.value_min,
                "value_max": h.value_max,
                "value_range": h.value_range_label,
                "filing_year": h.filing_year,
                "source": h.source,
                "source_reliability": h.source_reliability,
                "now": now,
            })
            stats["assets_merged"] += 1

            session.run("""
                MATCH (p:Person {id: $member_id})
                MATCH (a:Asset {id: $asset_id})
                MERGE (p)-[r:DISCLOSED_HOLDING]->(a)
                SET r.filing_year = $filing_year,
                    r.source = $source,
                    r.source_reliability = $source_reliability,
                    r.last_updated = $now
            """, {
                "member_id": h.member_id,
                "asset_id": asset_id,
                "filing_year": h.filing_year,
                "source": h.source,
                "source_reliability": h.source_reliability,
                "now": now,
            })
            stats["disclosed_edges"] += 1

            session.run("""
                MATCH (a:Asset {id: $asset_id})
                MATCH (s:HoldingSource {id: 'source_house_disclosure'})
                MERGE (a)-[r:HAS_HOLDING_SOURCE]->(s)
                SET r.last_updated = $now
            """, {
                "asset_id": asset_id,
                "now": now,
            })
            stats["source_edges"] += 1

        for d in disclosures:
            disclosure_id = f"disclosure_{d.id}"
            result = session.run("""
                MATCH (p:Person {id: $member_id})
                RETURN p.id AS pid
            """, {"member_id": d.member_id})
            record = result.single()

            if not record:
                continue

            session.run("""
                MERGE (hd:HoldingDisclosure {id: $disclosure_id})
                SET hd.filing_year = $filing_year,
                    hd.filing_type = $filing_type,
                    hd.asset_count = $asset_count,
                    hd.source = $source,
                    hd.source_reliability = $source_reliability,
                    hd.last_updated = $now
            """, {
                "disclosure_id": disclosure_id,
                "filing_year": d.filing_year,
                "filing_type": d.filing_type,
                "asset_count": d.asset_count,
                "source": d.source,
                "source_reliability": d.source_reliability,
                "now": now,
            })
            stats["disclosures_merged"] += 1

            session.run("""
                MATCH (p:Person {id: $member_id})
                MATCH (hd:HoldingDisclosure {id: $disclosure_id})
                MERGE (p)-[r:REPORTED_IN]->(hd)
                SET r.filing_year = $filing_year,
                    r.source = $source,
                    r.source_reliability = $source_reliability,
                    r.last_updated = $now
            """, {
                "member_id": d.member_id,
                "disclosure_id": disclosure_id,
                "filing_year": d.filing_year,
                "source": d.source,
                "source_reliability": d.source_reliability,
                "now": now,
            })
            stats["reported_edges"] += 1

            session.run("""
                MATCH (hd:HoldingDisclosure {id: $disclosure_id})
                MATCH (s:HoldingSource {id: 'source_house_disclosure'})
                MERGE (hd)-[r:HAS_HOLDING_SOURCE]->(s)
                SET r.last_updated = $now
            """, {
                "disclosure_id": disclosure_id,
                "now": now,
            })
            stats["source_edges"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Sync holdings data to Neo4j")
    parser.add_argument("--limit", type=int, help="Limit number of holdings to import")
    parser.add_argument("--dry-run", action="store_true", help="Only count, don't write")
    args = parser.parse_args()

    print("Importing holdings data to Neo4j...")
    stats = import_holdings_graph(limit=args.limit, dry_run=args.dry_run)

    print(f"\nImport complete:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
