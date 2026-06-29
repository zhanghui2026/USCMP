"""Seed all mock data into PostgreSQL and Neo4j."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, date
from app.db.postgres import engine, SessionLocal
from app.models.sqlalchemy.models import Base, Member, Organization, Event, Claim, SourceDocument, MockSeedManifest
from app.db.neo4j import get_driver, run_cypher
from app.scripts.mock_data_generator import MockDataGenerator
from app.core.logging import logger
from app.core.config import settings


def seed_postgres(data: dict) -> str:
    """Insert mock data into PostgreSQL."""
    db = SessionLocal()
    try:
        members = []
        for m in data["members"]:
            members.append(Member(**{
                k: v for k, v in m.items()
                if k in [c.name for c in Member.__table__.columns]
            }))

        orgs = []
        for o in data["organizations"]:
            orgs.append(Organization(**{
                k: v for k, v in o.items()
                if k in [c.name for c in Organization.__table__.columns]
            }))

        events = []
        for e in data["events"]:
            events.append(Event(**{
                k: v for k, v in e.items()
                if k in [c.name for c in Event.__table__.columns]
            }))

        claims = []
        for c in data["claims"]:
            claims.append(Claim(**{
                k: v for k, v in c.items()
                if k in [c.name for c in Claim.__table__.columns]
            }))

        sdocs = []
        for s in data["source_documents"]:
            sdocs.append(SourceDocument(**{
                k: v for k, v in s.items()
                if k in [c.name for c in SourceDocument.__table__.columns]
            }))

        db.add_all(members)
        db.add_all(orgs)
        db.add_all(events)
        db.add_all(claims)
        db.add_all(sdocs)

        db.commit()
        logger.info(
            f"PostgreSQL seeded: {len(members)} members, {len(orgs)} orgs, "
            f"{len(events)} events, {len(claims)} claims, {len(sdocs)} source_docs"
        )

        version = "0.1.0"
        for entity_type, count in [
            ("members", len(members)),
            ("organizations", len(orgs)),
            ("events", len(events)),
            ("claims", len(claims)),
            ("source_documents", len(sdocs)),
        ]:
            manifest = MockSeedManifest(
                seed_version=version,
                entity_type=entity_type,
                entity_count=count,
            )
            db.add(manifest)
        db.commit()

        return version
    finally:
        db.close()


def seed_neo4j(nodes: list[dict], edges: list[dict]):
    """Insert mock data into Neo4j."""
    driver = get_driver()

    with driver.session() as session:
        # Create constraints
        constraints = [
            "CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (n:Person) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT org_id_unique IF NOT EXISTS FOR (n:Organization) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT pol_entity_id_unique IF NOT EXISTS FOR (n:PoliticalEntity) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT event_id_unique IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (n:Claim) REQUIRE n.claim_id IS UNIQUE",
            "CREATE CONSTRAINT source_doc_id_unique IF NOT EXISTS FOR (n:SourceDocument) REQUIRE n.id IS UNIQUE",
        ]
        for c in constraints:
            try:
                session.run(c)
            except Exception:
                pass

        logger.info("Neo4j constraints created.")

        # Create indexes
        indexes = [
            "CREATE INDEX person_name_idx IF NOT EXISTS FOR (n:Person) ON (n.canonical_name)",
            "CREATE INDEX org_name_idx IF NOT EXISTS FOR (n:Organization) ON (n.canonical_name)",
            "CREATE INDEX pol_entity_name_idx IF NOT EXISTS FOR (n:PoliticalEntity) ON (n.name)",
            "CREATE INDEX event_date_idx IF NOT EXISTS FOR (n:Event) ON (n.event_date)",
            "CREATE INDEX claim_id_idx IF NOT EXISTS FOR (n:Claim) ON (n.claim_id)",
            "CREATE INDEX confidence_score_idx IF NOT EXISTS FOR (n:Claim) ON (n.confidence_score)",
        ]
        for idx in indexes:
            try:
                session.run(idx)
            except Exception:
                pass

        logger.info("Neo4j indexes created.")

        # Insert nodes in batches
        batch_size = 200
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            for node in batch:
                label = node["label"]
                node_id = node["id"]
                props = node["properties"]
                safe_props = {}
                for k, v in props.items():
                    if isinstance(v, (list, dict)):
                        safe_props[k] = json.dumps(v, default=str)
                    elif isinstance(v, (date, datetime)):
                        safe_props[k] = str(v)
                    else:
                        safe_props[k] = v
                prop_str = ", ".join(f"n.{k} = ${k}" for k in safe_props.keys())
                query = f"MERGE (n:{label} {{id: $id}}) SET {prop_str}"
                params = {"id": node_id, **safe_props}
                try:
                    session.run(query, params)
                except Exception as e:
                    logger.warning(f"Failed to insert node {node_id}: {e}")

        logger.info(f"Neo4j nodes created: {len(nodes)}")

        # Insert edges
        for edge in edges:
            rel_type = edge["type"]
            source_id = edge["source_id"]
            target_id = edge["target_id"]
            source_label = edge["source_label"]
            target_label = edge["target_label"]
            rel_props = {
                k: v for k, v in edge.items()
                if k not in ("id", "type", "source_id", "target_id", "source_label", "target_label")
            }
            rel_props["id"] = edge.get("id", "")

            safe_props = {}
            for k, v in rel_props.items():
                if v is None:
                    continue
                if isinstance(v, (list, dict)):
                    safe_props[k] = json.dumps(v, default=str)
                elif isinstance(v, (date, datetime)):
                    safe_props[k] = str(v)
                else:
                    safe_props[k] = v

            prop_str = ", ".join(f"r.{k} = ${k}" for k in safe_props.keys())
            query = (
                f"MATCH (a:{source_label} {{id: $source_id}}) "
                f"MATCH (b:{target_label} {{id: $target_id}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET {prop_str}"
            )
            params = {"source_id": source_id, "target_id": target_id, **safe_props}
            try:
                session.run(query, params)
            except Exception as e:
                logger.warning(f"Failed to create edge {rel_type}: {e}")

        logger.info(f"Neo4j edges created: {len(edges)}")


def main():
    logger.info("=" * 60)
    logger.info("Starting mock data seed...")
    logger.info(f"Config: max_depth={settings.max_graph_depth}, "
                 f"default_limit={settings.default_graph_limit}")

    # Clear only mock data (not real/uscl data)
    logger.info("Clearing existing mock data...")
    db_clear = SessionLocal()
    try:
        # Delete only mock-sourced records, preserve real data
        for model in [Member, Organization, Event, SourceDocument, MockSeedManifest]:
            db_clear.query(model).filter(model.source == "mock").delete(synchronize_session=False)
        # Claims use source_reliability instead of source column
        db_clear.query(Claim).filter(Claim.source_reliability == "mock").delete(synchronize_session=False)
        db_clear.commit()
    except Exception:
        db_clear.rollback()
    finally:
        db_clear.close()
    logger.info("Mock data cleared.")

    # Generate mock data
    logger.info("Generating mock data...")
    generator = MockDataGenerator()
    generator.generate_all()

    stats = generator.get_statistics()
    logger.info(f"Mock data generated: {json.dumps(stats, indent=2)}")

    # Seed PostgreSQL
    logger.info("Seeding PostgreSQL...")
    version = seed_postgres(generator.to_postgres_data())
    logger.info(f"PostgreSQL seeded successfully (version={version})")

    # Seed Neo4j
    logger.info("Seeding Neo4j...")
    seed_neo4j(generator.to_neo4j_nodes(), generator.to_neo4j_edges())
    logger.info("Neo4j seeded successfully.")

    logger.info("=" * 60)
    logger.info("Mock data seed complete!")
    logger.info(f"Members: {stats['members']}")
    logger.info(f"Organizations: {stats['organizations']}")
    logger.info(f"Political Entities: {stats['political_entities']}")
    logger.info(f"Events: {stats['events']}")
    logger.info(f"Claims: {stats['claims']}")
    logger.info(f"Source Documents: {stats['source_documents']}")
    logger.info(f"Relationships: {stats['relationships']}")
    logger.info(f"Low Confidence Relations: {stats['low_confidence_relationships']}")
    logger.info(f"Congress Coverage: {stats['congress_coverage']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
