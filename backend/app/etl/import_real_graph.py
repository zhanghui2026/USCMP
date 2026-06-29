"""Real Members Neo4j Graph Import.

Creates minimal identity graph nodes and relationships for real members.
Uses stable IDs from the congress-legislators dataset.  Idempotent
(MERGE-based) — re-running only updates existing nodes.

Nodes:
  - Person (id = uscl_person_{bioguide})
  - Party (id = party_{name_lower})
  - State (id = state_{code})
  - Chamber (id = chamber_{type})
  - Committee (id = committee_{thomas_id} or uscl_committee_{thomas_id})

Relationships:
  - MEMBER_OF_PARTY  (Person -> Party)
  - REPRESENTS_STATE (Person -> State)
  - SERVES_IN        (Person -> Chamber)
  - ASSIGNED_TO      (Person -> Committee)

Usage:
    python3 -m app.etl.import_real_graph
"""

import argparse
import logging
import sys
from pathlib import Path

from app.db.neo4j import get_driver
from app.etl.adapters.congress_legislators_adapter import CongressLegislatorsAdapter
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


def import_real_graph(adapter: CongressLegislatorsAdapter) -> dict[str, int]:
    """Create/update identity graph nodes and relationships."""

    norm = adapter.get_normalized()
    if "persons" not in norm:
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
        norm = adapter.get_normalized()

    persons = norm.get("persons", [])
    committees = norm.get("political_entities", [])
    memberships = norm.get("committee_memberships", [])

    driver = get_driver()
    stats = {
        "person_nodes": 0,
        "party_nodes": 0,
        "state_nodes": 0,
        "chamber_nodes": 0,
        "committee_nodes": 0,
        "member_of_party": 0,
        "represents_state": 0,
        "serves_in": 0,
        "assigned_to": 0,
    }

    with driver.session() as session:
        # Constraints
        session.run("CREATE CONSTRAINT real_person_id IF NOT EXISTS FOR (n:Person) REQUIRE n.id IS UNIQUE")
        session.run("CREATE CONSTRAINT real_party_id IF NOT EXISTS FOR (n:Party) REQUIRE n.id IS UNIQUE")
        session.run("CREATE CONSTRAINT real_state_id IF NOT EXISTS FOR (n:State) REQUIRE n.id IS UNIQUE")
        session.run("CREATE CONSTRAINT real_chamber_id IF NOT EXISTS FOR (n:Chamber) REQUIRE n.id IS UNIQUE")
        session.run("CREATE CONSTRAINT real_committee_id IF NOT EXISTS FOR (n:Committee) REQUIRE n.id IS UNIQUE")
        session.run("CREATE CONSTRAINT bg_person_id IF NOT EXISTS FOR (n:BackgroundPerson) REQUIRE n.id IS UNIQUE")

        # Committee nodes (small set, create first)
        for comm in committees:
            session.run(
                """
                MERGE (n:Committee {id: $id})
                SET n.name = $name,
                    n.chamber = $chamber,
                    n.entity_type = $entity_type,
                    n.data_mode = 'real',
                    n.data_source = 'unitedstates/congress-legislators'
                """,
                {
                    "id": comm["entity_id"],
                    "name": comm["name"],
                    "chamber": comm.get("chamber", ""),
                    "entity_type": comm.get("entity_type", "committee"),
                },
            )
            stats["committee_nodes"] += 1

        # Person nodes + Party/State/Chamber nodes + relationships
        for p in persons:
            if p.get("_scope") != "current":
                continue
            person_id = p["person_id"]
            bioguide = p.get("bioguide_id", "")
            party = p.get("party")
            state = p.get("state")
            chamber = p.get("chamber")

            # Person node
            session.run(
                """
                MERGE (n:Person {id: $id})
                SET n.canonical_name = $name,
                    n.display_name = $display,
                    n.party = $party,
                    n.chamber = $chamber,
                    n.state = $state,
                    n.person_type = $person_type,
                    n.bioguide_id = $bioguide,
                    n.data_mode = 'real',
                    n.data_source = 'unitedstates/congress-legislators',
                    n.person_scope = $scope,
                    n.is_current = $is_current
                """,
                {
                    "id": person_id,
                    "name": p["canonical_name"],
                    "display": p.get("display_name", ""),
                    "party": party,
                    "chamber": chamber,
                    "state": state,
                    "person_type": p.get("person_type", "legislator"),
                    "bioguide": bioguide,
                    "scope": p.get("_scope", "historical"),
                    "is_current": p.get("_scope") == "current",
                },
            )
            stats["person_nodes"] += 1

            # Party node + MEMBER_OF_PARTY
            if party:
                party_id = f"party_{party.lower().replace(' ', '_')}"
                session.run(
                    """
                    MERGE (p:Party {id: $party_id})
                    SET p.name = $party_name,
                        p.data_mode = 'real'
                    """,
                    {"party_id": party_id, "party_name": party},
                )
                session.run(
                    """
                    MATCH (n:Person {id: $person_id})
                    MATCH (p:Party {id: $party_id})
                    MERGE (n)-[r:MEMBER_OF_PARTY]->(p)
                    SET r.data_mode = 'real',
                        r.data_source = 'unitedstates/congress-legislators'
                    """,
                    {"person_id": person_id, "party_id": party_id},
                )
                stats["party_nodes"] += 1
                stats["member_of_party"] += 1

            # State node + REPRESENTS_STATE
            if state:
                state_id = f"state_{state.upper()}"
                session.run(
                    """
                    MERGE (s:State {id: $state_id})
                    SET s.code = $state_code,
                        s.data_mode = 'real'
                    """,
                    {"state_id": state_id, "state_code": state.upper()},
                )
                session.run(
                    """
                    MATCH (n:Person {id: $person_id})
                    MATCH (s:State {id: $state_id})
                    MERGE (n)-[r:REPRESENTS_STATE]->(s)
                    SET r.data_mode = 'real',
                        r.data_source = 'unitedstates/congress-legislators'
                    """,
                    {"person_id": person_id, "state_id": state_id},
                )
                stats["state_nodes"] += 1
                stats["represents_state"] += 1

            # Chamber node + SERVES_IN
            if chamber:
                chamber_id = f"chamber_{chamber}"
                session.run(
                    """
                    MERGE (c:Chamber {id: $chamber_id})
                    SET c.name = $chamber_name,
                        c.data_mode = 'real'
                    """,
                    {"chamber_id": chamber_id, "chamber_name": chamber.capitalize()},
                )
                session.run(
                    """
                    MATCH (n:Person {id: $person_id})
                    MATCH (c:Chamber {id: $chamber_id})
                    MERGE (n)-[r:SERVES_IN]->(c)
                    SET r.data_mode = 'real',
                        r.data_source = 'unitedstates/congress-legislators'
                    """,
                    {"person_id": person_id, "chamber_id": chamber_id},
                )
                stats["chamber_nodes"] += 1
                stats["serves_in"] += 1

            if (stats["person_nodes"]) % 1000 == 0:
                logger.info(f"  Processed {stats['person_nodes']} persons...")

        # Committee memberships: ASSIGNED_TO
        for m in memberships:
            session.run(
                """
                MATCH (n:Person {id: $person_id})
                MATCH (c:Committee {id: $entity_id})
                MERGE (n)-[r:ASSIGNED_TO]->(c)
                SET r.role = $role,
                    r.rank = $rank,
                    r.data_mode = 'real',
                    r.data_source = 'unitedstates/congress-legislators'
                """,
                {
                    "person_id": m["person_id"],
                    "entity_id": m["committee_entity_id"],
                    "role": m.get("role", "member"),
                    "rank": str(m.get("rank", "")),
                },
            )
            stats["assigned_to"] += 1

    driver.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Import real members identity graph into Neo4j")
    parser.add_argument("--commit-sha", default=DEFAULT_COMMIT_SHA)
    parser.add_argument("--vendor-dir", default=None)
    args = parser.parse_args()

    vendor_dir = _resolve_vendor_dir(args.commit_sha, args.vendor_dir)
    adapter = CongressLegislatorsAdapter(commit_sha=args.commit_sha, vendor_dir=vendor_dir)

    try:
        stats = import_real_graph(adapter)
        print("\nReal Members Graph Import Complete:")
        print(f"  Person nodes: {stats['person_nodes']}")
        print(f"  Party nodes: {stats['party_nodes']}")
        print(f"  State nodes: {stats['state_nodes']}")
        print(f"  Chamber nodes: {stats['chamber_nodes']}")
        print(f"  Committee nodes: {stats['committee_nodes']}")
        print(f"  MEMBER_OF_PARTY: {stats['member_of_party']}")
        print(f"  REPRESENTS_STATE: {stats['represents_state']}")
        print(f"  SERVES_IN: {stats['serves_in']}")
        print(f"  ASSIGNED_TO: {stats['assigned_to']}")
    except Exception as exc:
        logger.error(f"Graph import failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
