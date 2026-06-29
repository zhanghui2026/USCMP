"""Data Quality Summary API endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import text
from app.db.postgres import SessionLocal
from app.db.neo4j import run_cypher
from app.models.pydantic.models import DataQualitySummaryResponse

router = APIRouter(tags=["data-quality"])


@router.get("/data-quality/summary", response_model=DataQualitySummaryResponse)
def data_quality_summary():
    total_claims = 0
    total_source_documents = 0
    needs_review_claims = 0
    source_reliability_dist = {}
    extraction_method_dist = {}

    # PostgreSQL stats
    try:
        db = SessionLocal()

        r = db.execute(text("SELECT COUNT(*) FROM claims")).fetchone()
        total_claims = r[0] if r else 0

        r = db.execute(text("SELECT COUNT(*) FROM source_documents")).fetchone()
        total_source_documents = r[0] if r else 0

        r = db.execute(text(
            "SELECT COUNT(*) FROM claims WHERE review_status = 'needs_review'"
        )).fetchone()
        needs_review_claims = r[0] if r else 0

        r = db.execute(text(
            "SELECT source_reliability, COUNT(*) FROM claims GROUP BY source_reliability"
        )).fetchall()
        source_reliability_dist = {row[0]: row[1] for row in r}

        r = db.execute(text(
            "SELECT extraction_method, COUNT(*) FROM claims GROUP BY extraction_method"
        )).fetchall()
        extraction_method_dist = {row[0]: row[1] for row in r}

        db.close()
    except Exception:
        pass

    # Neo4j stats
    total_nodes = 0
    total_edges = 0
    low_confidence_edges = 0
    node_type_dist = {}
    edge_type_dist = {}

    try:
        records = run_cypher("MATCH (n) RETURN count(n) as cnt", {})
        if records:
            total_nodes = records[0].get("cnt", 0)

        records = run_cypher("MATCH ()-[r]->() RETURN count(r) as cnt", {})
        if records:
            total_edges = records[0].get("cnt", 0)

        records = run_cypher(
            "MATCH ()-[r]->() WHERE r.confidence_score IS NOT NULL AND r.confidence_score < 0.5 RETURN count(r) as cnt",
            {},
        )
        if records:
            low_confidence_edges = records[0].get("cnt", 0)

        records = run_cypher(
            "MATCH (n) RETURN labels(n)[0] as label, count(*) as cnt ORDER BY cnt DESC",
            {},
        )
        for rec in records:
            node_type_dist[rec.get("label", "Unknown")] = rec.get("cnt", 0)

        records = run_cypher(
            "MATCH ()-[r]->() RETURN type(r) as rel_type, count(*) as cnt ORDER BY cnt DESC",
            {},
        )
        for rec in records:
            edge_type_dist[rec.get("rel_type", "Unknown")] = rec.get("cnt", 0)
    except Exception:
        pass

    # Detect data_mode
    mock_count = source_reliability_dist.get("mock", 0)
    real_count = sum(v for k, v in source_reliability_dist.items() if k != "mock")

    # Check sandbox tables
    sandbox_persons = 0
    sandbox_claims = 0
    sandbox_source_documents = 0
    sandbox_safe = 0
    sandbox_needs_review = 0
    try:
        db2 = SessionLocal()
        r = db2.execute(text("SELECT COUNT(*) FROM sandbox_persons")).fetchone()
        sandbox_persons = r[0] if r else 0
        r = db2.execute(text("SELECT COUNT(*) FROM sandbox_claims")).fetchone()
        sandbox_claims = r[0] if r else 0
        r = db2.execute(text("SELECT COUNT(*) FROM sandbox_source_documents")).fetchone()
        sandbox_source_documents = r[0] if r else 0
        r = db2.execute(text(
            "SELECT COUNT(*) FROM sandbox_entity_resolution_reviews WHERE safe_match = true"
        )).fetchone()
        sandbox_safe = r[0] if r else 0
        r = db2.execute(text(
            "SELECT COUNT(*) FROM sandbox_entity_resolution_reviews WHERE needs_review = true"
        )).fetchone()
        sandbox_needs_review = r[0] if r else 0
        db2.close()
    except Exception:
        pass

    if real_count == 0 and mock_count > 0:
        data_mode = "real_sandbox" if sandbox_persons > 0 else "mock"
    elif mock_count > 0 and real_count > 0:
        data_mode = "mixed"
    elif real_count > 0 and mock_count == 0:
        data_mode = "real"
    else:
        data_mode = "real_sandbox" if sandbox_persons > 0 else "unknown"

    return DataQualitySummaryResponse(
        total_nodes=total_nodes,
        total_edges=total_edges,
        total_claims=total_claims,
        total_source_documents=total_source_documents,
        low_confidence_edges=low_confidence_edges,
        needs_review_claims=needs_review_claims,
        source_reliability_distribution=source_reliability_dist,
        extraction_method_distribution=extraction_method_dist,
        node_type_distribution=node_type_dist,
        edge_type_distribution=edge_type_dist,
        data_mode=data_mode,
        sandbox_persons=sandbox_persons,
        sandbox_claims=sandbox_claims,
        sandbox_source_documents=sandbox_source_documents,
        sandbox_entity_resolution_safe=sandbox_safe,
        sandbox_entity_resolution_needs_review=sandbox_needs_review,
        generated_at=datetime.now(timezone.utc),
    )
