"""
Import member profile facts into Neo4j graph (v0.7).

Reads structured fields from member_profiles (education, prior_positions,
employers, profile_sources) and creates corresponding Neo4j nodes and
relationships. Uses MERGE for idempotency.

Node types:
  - EducationInstitution (edu_*)
  - Position (pos_*)
  - Employer (emp_*)
  - ProfileSource (src_*)

Edge types:
  - EDUCATED_AT: Person -> EducationInstitution
  - HELD_POSITION: Person -> Position
  - EMPLOYED_BY: Person -> Employer
  - HAS_PROFILE_SOURCE: Person -> ProfileSource

Rules:
  - Only available/partial profiles generate nodes
  - summary_only profiles skipped
  - Empty fields skipped
  - MERGE ensures idempotency
  - Each edge carries source and source_reliability

Usage:
    python3 -m app.etl.import_profile_graph --dry-run
    python3 -m app.etl.import_profile_graph
    python3 -m app.etl.import_profile_graph --limit 20
"""

from __future__ import annotations

import argparse
import re
from typing import Any

from app.db.postgres import SessionLocal
from app.db.neo4j import get_driver
from app.models.sqlalchemy.models import MemberProfile
from app.core.logging import logger

_EDGE_SOURCE = "wikipedia"
_EDGE_SOURCE_RELIABILITY = "external_open_content"


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "unknown"


def _ensure_constraints(driver):
    with driver.session() as session:
        constraints = [
            ("CREATE CONSTRAINT profile_edu_id IF NOT EXISTS "
             "FOR (n:EducationInstitution) REQUIRE n.id IS UNIQUE"),
            ("CREATE CONSTRAINT profile_pos_id IF NOT EXISTS "
             "FOR (n:Position) REQUIRE n.id IS UNIQUE"),
            ("CREATE CONSTRAINT profile_emp_id IF NOT EXISTS "
             "FOR (n:Employer) REQUIRE n.id IS UNIQUE"),
            ("CREATE CONSTRAINT profile_src_id IF NOT EXISTS "
             "FOR (n:ProfileSource) REQUIRE n.id IS UNIQUE"),
        ]
        for cypher in constraints:
            session.run(cypher)


def _build_education_statements(profile, member_id):
    ops = []
    for item in profile.get("education") or []:
        name = item.get("institution", "")
        if not name:
            continue
        node_id = f"edu_{_slugify(name)}"
        ops.append({
            "node_id": node_id,
            "label": "EducationInstitution",
            "props": {"name": name},
            "edge_type": "EDUCATED_AT",
        })
    return ops


def _build_position_statements(profile, member_id):
    ops = []
    for item in profile.get("prior_positions") or []:
        pos_text = item.get("position", "")
        if not pos_text:
            continue
        node_id = f"pos_{_slugify(pos_text)}"
        ops.append({
            "node_id": node_id,
            "label": "Position",
            "props": {"name": pos_text},
            "edge_type": "HELD_POSITION",
        })
    return ops


def _build_employer_statements(profile, member_id):
    ops = []
    for item in profile.get("employers") or []:
        name = ""
        if isinstance(item, dict):
            name = item.get("name", item.get("institution", ""))
        elif isinstance(item, str):
            name = item
        if not name:
            continue
        node_id = f"emp_{_slugify(name)}"
        ops.append({
            "node_id": node_id,
            "label": "Employer",
            "props": {"name": name},
            "edge_type": "EMPLOYED_BY",
        })
    return ops


def _build_source_statements(profile, member_id):
    ops = []
    sources = profile.get("profile_sources") or {}
    if not sources:
        return ops

    wikipedia_title = sources.get("wikipedia_title", "")
    if wikipedia_title:
        node_id = f"src_wikipedia_{_slugify(wikipedia_title)}"
        ops.append({
            "node_id": node_id,
            "label": "ProfileSource",
            "props": {
                "name": f"Wikipedia: {wikipedia_title}",
                "url": sources.get("wikipedia_url", ""),
                "wikidata_qid": sources.get("wikidata_qid", ""),
                "retrieved_at": sources.get("retrieved_at", ""),
            },
            "edge_type": "HAS_PROFILE_SOURCE",
        })
    return ops


def _execute_merge(driver, member_id, ops, dry_run=False):
    stats = {"nodes_created": 0, "edges_created": 0, "skipped_empty": 0}
    if not ops:
        stats["skipped_empty"] = 1
        return stats

    with driver.session() as session:
        for op in ops:
            if dry_run:
                stats["nodes_created"] += 1
                stats["edges_created"] += 1
                continue

            node_id = op["node_id"]
            label = op["label"]
            edge_type = op["edge_type"]
            props = op["props"]

            # MERGE node
            set_clauses = ", ".join(
                f"n.{k} = ${k}" for k in props
            )
            if set_clauses:
                set_clauses = "SET " + set_clauses
            cypher = (
                f"MERGE (n:{label} {{id: $node_id}}) "
                f"{set_clauses}"
            )
            params = {"node_id": node_id, **props}
            node_result = session.run(cypher, params)
            node_result.consume()

            # MERGE edge
            edge_cypher = (
                f"MATCH (p:Person {{id: $member_id}}) "
                f"MATCH (t:{label} {{id: $node_id}}) "
                f"MERGE (p)-[r:{edge_type}]->(t) "
                f"SET r.source = $source, "
                f"r.source_reliability = $source_reliability"
            )
            edge_params = {
                "member_id": member_id,
                "node_id": node_id,
                "source": _EDGE_SOURCE,
                "source_reliability": _EDGE_SOURCE_RELIABILITY,
            }
            edge_result = session.run(edge_cypher, edge_params)
            edge_result.consume()
            stats["edges_created"] += 1

    return stats


def import_profile_graph(dry_run=False, limit=None):
    session = SessionLocal()
    driver = get_driver()

    _ensure_constraints(driver)

    query = session.query(MemberProfile).filter(
        MemberProfile.profile_status.in_(["available", "partial"])
    )
    if limit:
        query = query.limit(limit)

    profiles = query.all()
    logger.info(f"Found {len(profiles)} available/partial profiles to import")

    total = {"nodes": 0, "edges": 0, "skipped": 0}
    for profile in profiles:
        member_id = profile.member_id
        if not member_id:
            continue

        data = {
            "education": profile.education,
            "prior_positions": profile.prior_positions,
            "employers": profile.employers,
            "profile_sources": profile.profile_sources,
        }

        ops = []
        ops.extend(_build_education_statements(data, member_id))
        ops.extend(_build_position_statements(data, member_id))
        ops.extend(_build_employer_statements(data, member_id))
        ops.extend(_build_source_statements(data, member_id))

        stats = _execute_merge(driver, member_id, ops, dry_run=dry_run)
        if not any(ops):
            total["skipped"] += 1
            continue

        node_count = len(ops)
        edge_count = len(ops)
        total["nodes"] += node_count
        total["edges"] += edge_count
        logger.debug(
            f"  {member_id}: {node_count} nodes, {edge_count} edges"
        )

    session.close()

    if dry_run:
        logger.info(f"[DRY RUN] Would create {total['nodes']} nodes, "
                     f"{total['edges']} edges, skip {total['skipped']}")
    else:
        logger.info(f"Created {total['nodes']} nodes, {total['edges']} edges, "
                     f"skipped {total['skipped']}")

    return total


def main():
    parser = argparse.ArgumentParser(description="Import profile facts into Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--limit", type=int, default=None, help="Limit profiles")
    args = parser.parse_args()

    total = import_profile_graph(dry_run=args.dry_run, limit=args.limit)

    labels = [
        "EducationInstitution",
        "Position",
        "Employer",
        "ProfileSource",
    ]
    driver = get_driver()
    with driver.session() as s:
        for label in labels:
            result = s.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            cnt = result.single()["cnt"]
            print(f"  {label}: {cnt}")

    return total


if __name__ == "__main__":
    main()
