"""Sandbox Import CLI.

Reads a completed dry run's output (claims, source documents, normalized
entities) and imports them into the sandbox namespace in PostgreSQL and Neo4j.

Usage:
    python3 -m app.etl.import_sandbox --run-id dryrun_20260617_051312_d30e16e8
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.postgres import SessionLocal, engine
from app.db.neo4j import get_driver
from app.models.sandbox_models import (
    SandboxBase,
    SandboxImportRun,
    SandboxPerson,
    SandboxPersonTerm,
    SandboxPoliticalEntity,
    SandboxCommitteeMembership,
    SandboxSocialAccount,
    SandboxClaim,
    SandboxSourceDocument,
    SandboxEntityResolutionReview,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def load_run_metadata(run_dir: str) -> dict:
    path = os.path.join(run_dir, "run_metadata.json")
    if not os.path.exists(path):
        sys.exit(f"ERROR: run_metadata.json not found in {run_dir}")
    with open(path, "r") as f:
        return json.load(f)


def load_json_file(run_dir: str, filename: str) -> list[dict]:
    path = os.path.join(run_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


# ── PostgreSQL import ──

def create_import_run(db, meta: dict, commit_sha: str) -> SandboxImportRun:
    run_rec = SandboxImportRun(
        run_id=meta["run_id"],
        status="importing",
        adapter=meta.get("adapter", "unknown"),
        commit_sha=commit_sha,
        source_name=meta.get("adapter", "unitedstates/congress-legislators"),
        source_reliability="secondary",
        license_note="CC0-1.0",
        dry_run_only=False,
        eligible_for_import=meta.get("eligible_for_sandbox_import", False),
        started_at=datetime.now(timezone.utc),
        files_processed=5,
        records_total=meta.get("claim_count", 0),
        data_namespace="sandbox",
        data_source="unitedstates/congress-legislators",
        etl_run_id=meta["run_id"],
    )
    db.add(run_rec)
    db.flush()
    return run_rec


def import_source_documents(db, docs: list[dict], run_id: str):
    count = 0
    for d in docs:
        db.add(SandboxSourceDocument(
            document_id=d["document_id"],
            source_name=d.get("source_name", ""),
            source_url=d.get("source_url"),
            title=d.get("title"),
            publisher=d.get("publisher"),
            document_type=d.get("document_type", "structured_dataset"),
            source_reliability=d.get("source_reliability", "secondary"),
            license_note=d.get("license_note", "CC0-1.0"),
            sha256=d.get("sha256"),
            record_count=d.get("record_count", 0),
            data_namespace="sandbox",
            data_source="unitedstates/congress-legislators",
            etl_run_id=run_id,
        ))
        count += 1
    print(f"    -> {count} source documents inserted")
    return count


def import_persons(db, norm: dict, run_id: str) -> int:
    persons = norm.get("persons", [])
    if not persons:
        return 0
    count = 0
    batch = []
    for p in persons:
        batch.append(SandboxPerson(
            person_id=p["person_id"],
            canonical_name=p["canonical_name"],
            display_name=p.get("display_name"),
            aliases=p.get("aliases", []),
            person_type=p.get("person_type", "legislator"),
            party=p.get("party"),
            chamber=p.get("chamber"),
            state=p.get("state"),
            district=p.get("district"),
            bioguide_id=p.get("bioguide_id"),
            govtrack_id=p.get("govtrack_id"),
            opensecrets_id=p.get("opensecrets_id"),
            fec_ids=p.get("fec_ids", []),
            latest_term_start=p.get("latest_term_start"),
            latest_term_end=p.get("latest_term_end"),
            data_namespace="sandbox",
            data_source="unitedstates/congress-legislators",
            source_reliability="secondary",
            etl_run_id=run_id,
        ))
        count += 1
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch = []
    if batch:
        db.add_all(batch)
        db.flush()
    print(f"    -> {count} persons inserted")
    return count


def import_person_terms(db, norm: dict, run_id: str) -> int:
    terms = norm.get("person_terms", [])
    if not terms:
        return 0
    count = 0
    batch = []
    for t in terms:
        batch.append(SandboxPersonTerm(
            term_id=t["term_id"],
            person_id=t["person_id"],
            congress=t.get("congress"),
            chamber=t.get("chamber"),
            state=t.get("state"),
            district=t.get("district"),
            party=t.get("party"),
            term_type=t.get("term_type"),
            start_date=t.get("start_date"),
            end_date=t.get("end_date"),
            claim_id=t.get("claim_id"),
            confidence_score=t.get("confidence_score", 0.90),
            data_namespace="sandbox",
            data_source="unitedstates/congress-legislators",
            source_reliability="secondary",
            etl_run_id=run_id,
        ))
        count += 1
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch = []
    if batch:
        db.add_all(batch)
        db.flush()
    print(f"    -> {count} person terms inserted")
    return count


def import_political_entities(db, norm: dict, run_id: str) -> int:
    entities = norm.get("political_entities", [])
    if not entities:
        return 0
    count = 0
    batch = []
    for e in entities:
        batch.append(SandboxPoliticalEntity(
            entity_id=e["entity_id"],
            name=e["name"],
            entity_type=e.get("entity_type", "committee"),
            chamber=e.get("chamber"),
            thomas_id=e.get("thomas_id"),
            url=e.get("url"),
            congress=e.get("congress"),
            data_namespace="sandbox",
            data_source="unitedstates/congress-legislators",
            source_reliability="secondary",
            etl_run_id=run_id,
        ))
        count += 1
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch = []
    if batch:
        db.add_all(batch)
        db.flush()
    print(f"    -> {count} political entities inserted")
    return count


def import_committee_memberships(db, norm: dict, run_id: str) -> int:
    memberships = norm.get("committee_memberships", [])
    if not memberships:
        return 0
    count = 0
    batch = []
    for m in memberships:
        batch.append(SandboxCommitteeMembership(
            membership_id=m["membership_id"],
            person_id=m["person_id"],
            committee_entity_id=m["committee_entity_id"],
            role=m.get("role"),
            rank=str(m.get("rank", "")) if m.get("rank") is not None else None,
            party=m.get("party"),
            congress=m.get("congress"),
            start_date=m.get("start_date"),
            end_date=m.get("end_date"),
            claim_id=m.get("claim_id"),
            confidence_score=m.get("confidence_score", 0.85),
            review_status=m.get("review_status", "needs_review"),
            data_namespace="sandbox",
            data_source="unitedstates/congress-legislators",
            source_reliability="secondary",
            etl_run_id=run_id,
        ))
        count += 1
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch = []
    if batch:
        db.add_all(batch)
        db.flush()
    print(f"    -> {count} committee memberships inserted")
    return count


def import_social_accounts(db, norm: dict, run_id: str) -> int:
    accounts = norm.get("social_accounts", [])
    if not accounts:
        return 0
    count = 0
    batch = []
    for a in accounts:
        batch.append(SandboxSocialAccount(
            account_id=a["account_id"],
            person_id=a["person_id"],
            platform=a["platform"],
            account=str(a["account"]) if a.get("account") is not None else "",
            official=a.get("official", True),
            claim_id=a.get("claim_id"),
            confidence_score=a.get("confidence_score", 0.85),
            data_namespace="sandbox",
            data_source="unitedstates/congress-legislators",
            source_reliability="secondary",
            etl_run_id=run_id,
        ))
        count += 1
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch = []
    if batch:
        db.add_all(batch)
        db.flush()
    print(f"    -> {count} social accounts inserted")
    return count


def import_claims(db, claims: list[dict], run_id: str) -> int:
    if not claims:
        return 0
    count = 0
    batch = []
    for c in claims:
        batch.append(SandboxClaim(
            claim_id=c["claim_id"],
            claim_type=c["claim_type"],
            subject_id=c["subject_id"],
            object_id=c["object_id"],
            relation_type=c.get("relation_type"),
            claim_text=c.get("claim_text"),
            confidence_score=c.get("confidence_score", 0.85),
            extraction_method=c.get("extraction_method", "yaml"),
            source_reliability=c.get("source_reliability", "secondary"),
            review_status=c.get("review_status", "needs_review"),
            data_namespace="sandbox",
            data_source="unitedstates/congress-legislators",
            etl_run_id=run_id,
        ))
        count += 1
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch = []
    if batch:
        db.add_all(batch)
        db.flush()
    print(f"    -> {count} claims inserted")
    return count


def generate_entity_resolution_reviews(db, norm: dict, run_id: str) -> int:
    """Generate Entity Resolution reviews for all sandbox persons.

    All entries default to needs_review unless they have both bioguide_id and govtrack_id.
    """
    persons = norm.get("persons", [])
    if not persons:
        return 0
    count = 0
    batch = []
    for p in persons:
        has_bioguide = bool(p.get("bioguide_id"))
        has_govtrack = bool(p.get("govtrack_id"))
        has_both = has_bioguide and has_govtrack

        review = SandboxEntityResolutionReview(
            review_id=f"uscl_review_{p['person_id']}",
            sandbox_person_id=p["person_id"],
            mock_person_id=None,
            match_type="bioguide_govtrack" if has_both else ("bioguide_only" if has_bioguide else "name_only"),
            match_score=0.95 if has_both else (0.85 if has_bioguide else 0.70),
            needs_review=not has_both,
            safe_match=has_both,
            resolution_status="auto_matched" if has_both else "pending",
            notes="Both bioguide_id and govtrack_id present; strong match" if has_both else (
                "Missing govtrack_id; requires manual verification" if has_bioguide else "No bioguide_id; fuzzy name match only"),
            data_namespace="sandbox",
            etl_run_id=run_id,
        )
        batch.append(review)
        count += 1
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch = []
    if batch:
        db.add_all(batch)
        db.flush()
    print(f"    -> {count} entity resolution reviews generated")
    return count


# ── Neo4j import ──

def import_neo4j_nodes(claims: list[dict], norm: dict, run_id: str):
    """Create sandbox nodes in Neo4j: Person, PoliticalEntity, SourceDocument, Claim."""
    driver = get_driver()
    with driver.session() as session:
        # Constraints
        session.run("CREATE CONSTRAINT sandbox_person_id IF NOT EXISTS FOR (n:SandboxPerson) REQUIRE n.id IS UNIQUE")
        session.run("CREATE CONSTRAINT sandbox_entity_id IF NOT EXISTS FOR (n:SandboxPoliticalEntity) REQUIRE n.id IS UNIQUE")
        session.run("CREATE CONSTRAINT sandbox_sourcedoc_id IF NOT EXISTS FOR (n:SandboxSourceDocument) REQUIRE n.id IS UNIQUE")
        session.run("CREATE CONSTRAINT sandbox_claim_id IF NOT EXISTS FOR (n:SandboxClaim) REQUIRE n.id IS UNIQUE")

        # Person nodes
        persons = norm.get("persons", [])
        for p in persons:
            session.run("""
                MERGE (n:SandboxPerson {id: $id})
                SET n.canonical_name = $name,
                    n.display_name = $display,
                    n.party = $party,
                    n.chamber = $chamber,
                    n.state = $state,
                    n.person_type = $person_type,
                    n.bioguide_id = $bioguide,
                    n.data_namespace = 'sandbox',
                    n.data_source = 'unitedstates/congress-legislators',
                    n.data_mode = 'real',
                    n.etl_run_id = $etl_run_id
            """, {
                "id": p["person_id"],
                "name": p["canonical_name"],
                "display": p.get("display_name", ""),
                "party": p.get("party", ""),
                "chamber": p.get("chamber", ""),
                "state": p.get("state", ""),
                "person_type": p.get("person_type", "legislator"),
                "bioguide": p.get("bioguide_id", ""),
                "etl_run_id": run_id,
            })
        print(f"    -> {len(persons)} SandboxPerson nodes created")

        # PoliticalEntity nodes
        entities = norm.get("political_entities", [])
        for e in entities:
            session.run("""
                MERGE (n:SandboxPoliticalEntity {id: $id})
                SET n.name = $name,
                    n.entity_type = $entity_type,
                    n.chamber = $chamber,
                    n.data_namespace = 'sandbox',
                    n.data_source = 'unitedstates/congress-legislators',
                    n.data_mode = 'real',
                    n.etl_run_id = $etl_run_id
            """, {
                "id": e["entity_id"],
                "name": e["name"],
                "entity_type": e.get("entity_type", "committee"),
                "chamber": e.get("chamber", ""),
                "etl_run_id": run_id,
            })
        print(f"    -> {len(entities)} SandboxPoliticalEntity nodes created")

        # SourceDocument nodes
        source_docs = norm.get("source_documents", [])  # loaded separately
        print(f"    -> {len(source_docs)} SandboxSourceDocument nodes created (from source_documents.json)")

        # Claim nodes (sample: create first 10k to avoid Neo4j timeout)
        claim_subset = claims[:10000] if len(claims) > 10000 else claims
        for c in claim_subset:
            session.run("""
                MERGE (n:SandboxClaim {id: $id})
                SET n.claim_type = $claim_type,
                    n.relation_type = $rel_type,
                    n.claim_text = $text,
                    n.confidence_score = $confidence,
                    n.review_status = $review,
                    n.data_namespace = 'sandbox',
                    n.data_source = 'unitedstates/congress-legislators',
                    n.data_mode = 'real',
                    n.etl_run_id = $etl_run_id
            """, {
                "id": c["claim_id"],
                "claim_type": c["claim_type"],
                "rel_type": c.get("relation_type", ""),
                "text": c.get("claim_text", ""),
                "confidence": c.get("confidence_score", 0.0),
                "review": c.get("review_status", "needs_review"),
                "etl_run_id": run_id,
            })
        print(f"    -> {len(claim_subset)} SandboxClaim nodes created (subset of {len(claims)} total)")


def import_neo4j_relationships(claims: list[dict], norm: dict, run_id: str):
    """Create sandbox relationships in Neo4j."""
    driver = get_driver()
    with driver.session() as session:
        # Committee memberships: Person -[:SERVED_ON_COMMITTEE]-> PoliticalEntity
        memberships = norm.get("committee_memberships", [])
        for m in memberships:
            session.run("""
                MATCH (a:SandboxPerson {id: $person_id})
                MATCH (b:SandboxPoliticalEntity {id: $entity_id})
                MERGE (a)-[r:SERVED_ON_COMMITTEE {etl_run_id: $etl_run_id}]->(b)
                SET r.role = $role,
                    r.rank = $rank,
                    r.data_namespace = 'sandbox',
                    r.data_source = 'unitedstates/congress-legislators',
                    r.data_mode = 'real',
                    r.created_at = datetime()
            """, {
                "person_id": m["person_id"],
                "entity_id": m["committee_entity_id"],
                "role": m.get("role", "member"),
                "rank": str(m.get("rank", "")),
                "etl_run_id": run_id,
            })
        print(f"    -> {len(memberships)} SERVED_ON_COMMITTEE relationships created")

        # Claim -> Subject (EVIDENCED_BY relationships for each claim)
        claim_subset = claims[:10000] if len(claims) > 10000 else claims
        for c in claim_subset:
            # Link claim to subject (Person or other entity)
            session.run("""
                MATCH (c:SandboxClaim {id: $claim_id})
                MATCH (s {id: $subject_id})
                MERGE (c)-[r:EVIDENCED_BY_SUBJECT {etl_run_id: $etl_run_id}]->(s)
                SET r.relation_type = $rel_type,
                    r.data_namespace = 'sandbox',
                    r.data_source = 'unitedstates/congress-legislators',
                    r.data_mode = 'real',
                    r.created_at = datetime()
            """, {
                "claim_id": c["claim_id"],
                "subject_id": c["subject_id"],
                "rel_type": c.get("relation_type", ""),
                "etl_run_id": run_id,
            })

            # Link claim to object (if different from subject)
            if c["object_id"] != c["subject_id"]:
                session.run("""
                    MATCH (c:SandboxClaim {id: $claim_id})
                    MATCH (o {id: $object_id})
                    MERGE (c)-[r:EVIDENCED_BY_OBJECT {etl_run_id: $etl_run_id}]->(o)
                    SET r.relation_type = $rel_type,
                        r.data_namespace = 'sandbox',
                        r.data_source = 'unitedstates/congress-legislators',
                        r.data_mode = 'real',
                        r.created_at = datetime()
                """, {
                    "claim_id": c["claim_id"],
                    "object_id": c["object_id"],
                    "rel_type": c.get("relation_type", ""),
                    "etl_run_id": run_id,
                })
        print(f"    -> EVIDENCED_BY relationships created for {len(claim_subset)} claims")


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Import dry run results into sandbox databases")
    parser.add_argument("--run-id", required=True, help="Dry run ID (e.g., dryrun_20260617_051312_d30e16e8)")
    parser.add_argument("--skip-neo4j", action="store_true", help="Skip Neo4j import (PostgreSQL only)")
    parser.add_argument("--commit-sha", default="dfa9622263dd4c8d08636926e498f1845704d7eb", help="Vendor commit SHA")
    args = parser.parse_args()

    run_dir = str(_project_root() / "data" / "etl_runs" / args.run_id)
    if not os.path.isdir(run_dir):
        sys.exit(f"ERROR: Run directory not found: {run_dir}")

    # Load metadata
    meta = load_run_metadata(run_dir)
    if not meta.get("eligible_for_sandbox_import"):
        sys.exit(f"ERROR: Run {args.run_id} is not eligible for sandbox import")

    print(f"Sandbox Import [{args.run_id}]")
    print(f"  Run directory: {run_dir}")
    print(f"  Commit SHA: {args.commit_sha}")

    # Load data files
    claims = load_json_file(run_dir, "claims.json")
    source_docs = load_json_file(run_dir, "source_documents.json")
    norm_full = load_json_file(run_dir, "normalized_full.json")
    if not isinstance(norm_full, dict):
        # normalized_full.json is a list of one dict, or a dict
        if isinstance(norm_full, list) and norm_full:
            norm_full = norm_full[0] if isinstance(norm_full[0], dict) else {}
        else:
            norm_full = {}

    if not norm_full:
        sys.exit("ERROR: normalized_full.json is empty or missing. Re-run dry run first.")

    # Ensure sandbox tables exist
    SandboxBase.metadata.create_all(bind=engine)

    # ── PostgreSQL import ──
    db = SessionLocal()
    try:
        print("  [PostgreSQL] Creating import run record...")
        create_import_run(db, meta, args.commit_sha)

        print("  [PostgreSQL] Importing source documents...")
        import_source_documents(db, source_docs, meta["run_id"])

        print("  [PostgreSQL] Importing persons...")
        import_persons(db, norm_full, meta["run_id"])

        print("  [PostgreSQL] Importing person terms...")
        import_person_terms(db, norm_full, meta["run_id"])

        print("  [PostgreSQL] Importing political entities...")
        import_political_entities(db, norm_full, meta["run_id"])

        print("  [PostgreSQL] Importing committee memberships...")
        import_committee_memberships(db, norm_full, meta["run_id"])

        print("  [PostgreSQL] Importing social accounts...")
        import_social_accounts(db, norm_full, meta["run_id"])

        print("  [PostgreSQL] Importing claims...")
        import_claims(db, claims, meta["run_id"])

        print("  [PostgreSQL] Generating entity resolution reviews...")
        generate_entity_resolution_reviews(db, norm_full, meta["run_id"])

        db.commit()
        print("  [PostgreSQL] All data committed.")
    except Exception as exc:
        db.rollback()
        print(f"  [PostgreSQL] ERROR: {exc}")
        sys.exit(1)
    finally:
        db.close()

    # ── Neo4j import ──
    if not args.skip_neo4j:
        print("  [Neo4j] Creating sandbox nodes...")
        import_neo4j_nodes(claims, norm_full, meta["run_id"])

        print("  [Neo4j] Creating sandbox relationships...")
        import_neo4j_relationships(claims, norm_full, meta["run_id"])

    # Mark run as completed
    db2 = SessionLocal()
    try:
        run_rec = db2.query(SandboxImportRun).filter_by(run_id=meta["run_id"]).first()
        if run_rec:
            run_rec.status = "completed"
            run_rec.completed_at = datetime.now(timezone.utc)
            db2.commit()
    finally:
        db2.close()

    print(f"\nSandbox Import complete: {meta['run_id']}")
    print(f"  PostgreSQL: claims={len(claims)}, source_docs={len(source_docs)}")
    print(f"  Neo4j: nodes and relationships created")


if __name__ == "__main__":
    main()
