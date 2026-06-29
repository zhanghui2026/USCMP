"""Evidence API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.db.neo4j import run_cypher
from app.models.pydantic.models import (
    EvidenceResponse, ClaimModel, SourceDocumentModel,
)
from app.models.sqlalchemy.models import Claim, SourceDocument
from app.core.errors import NotFoundError

router = APIRouter(tags=["evidence"])


@router.get("/evidence/{claim_id}", response_model=EvidenceResponse)
def get_evidence(claim_id: str, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise NotFoundError("Claim not found", {"claim_id": claim_id})

    claim_model = ClaimModel(
        claim_id=claim.claim_id,
        claim_type=claim.claim_type,
        subject_id=claim.subject_id,
        object_id=claim.object_id,
        relation_type=claim.relation_type,
        claim_text=claim.claim_text,
        original_snippet=claim.original_snippet,
        confidence_score=claim.confidence_score,
        extraction_method=claim.extraction_method,
        source_reliability=claim.source_reliability,
        review_status=claim.review_status,
    )

    # Get linked source documents via Neo4j
    params = {"claim_id": claim_id}
    query = """
        MATCH (c:Claim {claim_id: $claim_id})-[:EVIDENCED_BY]->(s:SourceDocument)
        RETURN s
    """
    records = run_cypher(query, params)

    source_docs = []
    for record in records:
        if "s" in record:
            s = record["s"]
            source_docs.append(SourceDocumentModel(
                id=s.get("id", ""),
                source_name=s.get("source_name", "Unknown"),
                source_url=s.get("source_url"),
                title=s.get("title"),
                publisher=s.get("publisher"),
                published_at=s.get("published_at"),
                collected_at=s.get("collected_at"),
                document_type=s.get("document_type"),
                snippet=s.get("snippet"),
                source_reliability=s.get("source_reliability", "mock"),
                license_note=s.get("license_note"),
            ))

    # Fallback: query from PostgreSQL if Neo4j returns none
    if not source_docs:
        ev_rels_query = """
            MATCH (c:Claim {claim_id: $claim_id})-[:EVIDENCED_BY]->(s:SourceDocument)
            RETURN s.id as id
        """
        ev_results = run_cypher(ev_rels_query, params)
        doc_ids = [r.get("id") for r in ev_results if r.get("id")]
        if doc_ids:
            pgsdocs = db.query(SourceDocument).filter(SourceDocument.id.in_(doc_ids)).all()
            for sdoc in pgsdocs:
                source_docs.append(SourceDocumentModel(
                    id=sdoc.id,
                    source_name=sdoc.source_name,
                    source_url=sdoc.source_url,
                    title=sdoc.title,
                    publisher=sdoc.publisher,
                    published_at=sdoc.published_at,
                    collected_at=sdoc.collected_at,
                    document_type=sdoc.document_type,
                    snippet=sdoc.snippet,
                    source_reliability=sdoc.source_reliability,
                    license_note=sdoc.license_note,
                ))

    return EvidenceResponse(claim=claim_model, source_documents=source_docs)
