"""Backfill person_scope property on Neo4j Person nodes from PostgreSQL.

Existing Neo4j Person nodes were created before member_scope was tracked.
This script reads member_scope from PostgreSQL and sets the person_scope
property on the corresponding Neo4j Person node.

Nodes without a matching member in PostgreSQL are set to 'unknown'.
"""

from app.db.postgres import SessionLocal
from app.db.neo4j import get_driver
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def backfill_person_scope(batch_size: int = 500):
    db = SessionLocal()
    driver = get_driver()

    # Load member_id -> member_scope from PostgreSQL
    rows = db.execute(text(
        "SELECT id, member_scope FROM members"
    )).fetchall()
    scope_map = {r[0]: r[1] for r in rows}
    logger.info(f"Loaded {len(scope_map)} member scopes from PostgreSQL")

    with driver.session() as session:
        # Get all Person node IDs
        result = session.run("MATCH (p:Person) RETURN p.id AS person_id")
        person_ids = [r["person_id"] for r in result]
        logger.info(f"Found {len(person_ids)} Person nodes in Neo4j")

        updated = 0
        unknown = 0

        for i in range(0, len(person_ids), batch_size):
            batch = person_ids[i:i + batch_size]
            for pid in batch:
                scope = scope_map.get(pid, "unknown")
                if scope is None:
                    scope = "unknown"
                session.run(
                    "MATCH (p:Person {id: $id}) SET p.person_scope = $scope, p.is_current = $is_current",
                    id=pid, scope=scope, is_current=(scope == "current")
                )
                if scope == "unknown":
                    unknown += 1
                updated += 1

            if (i // batch_size) % 10 == 0:
                logger.info(f"  Progress: {updated}/{len(person_ids)}")

        logger.info(f"Backfill complete: {updated} updated, {unknown} unknown")

    db.close()
    driver.close()


def verify():
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (p:Person) "
            "RETURN p.person_scope AS scope, count(p) AS cnt "
            "ORDER BY scope"
        )
        for r in result:
            logger.info(f"  scope={r['scope']:12s} count={r['cnt']}")
    driver.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill_person_scope()
    verify()
