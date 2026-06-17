"""Graph service - all Cypher queries centralized here.

Phase 1: Stub implementations. Full queries implemented in Phase 2.
All user inputs are parameterized. No Cypher string concatenation.
"""

from datetime import date
from typing import Optional
from app.db.neo4j import run_cypher


def get_member_graph(
    member_id: str,
    depth: int = 2,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_confidence: float = 0.0,
    limit: int = 200,
) -> dict:
    """Get graph centered on a member up to depth 2.

    start_date/end_date filter relationships by their date range.
    Relationships with null start_date pass any start_date filter.
    Relationships with null end_date pass any end_date filter.
    """
    params = {
        "member_id": member_id,
        "min_confidence": min_confidence,
        "limit": min(limit, 500),
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }

    date_clause = "AND ($start_date IS NULL OR coalesce(r.start_date, $start_date) >= $start_date) AND ($end_date IS NULL OR coalesce(r.end_date, $end_date) <= $end_date)"

    if depth == 1:
        query = f"""
            MATCH (p:Person {{id: $member_id}})-[r]-(n)
            WHERE (r.confidence_score >= $min_confidence OR r.confidence_score IS NULL)
              {date_clause}
            RETURN p, r, n
            LIMIT $limit
        """
    else:
        query = f"""
            MATCH path = (p:Person {{id: $member_id}})-[r1]-(n1)
            WHERE (r1.confidence_score >= $min_confidence OR r1.confidence_score IS NULL)
              {date_clause.replace('r.', 'r1.')}
            OPTIONAL MATCH (n1)-[r2]-(n2)
            WHERE (r2.confidence_score >= $min_confidence OR r2.confidence_score IS NULL)
              AND n2 <> p
              {date_clause.replace('r.', 'r2.')}
            RETURN p, r1, r2, n1, n2
            LIMIT $limit
        """

    records = run_cypher(query, params)
    return {"records": records, "truncated": len(records) >= limit}


def expand_node(
    node_id: str,
    depth: int = 1,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_confidence: float = 0.0,
    limit: int = 200,
) -> dict:
    """Expand a single node to show its direct connections (depth=1)."""
    params = {
        "node_id": node_id,
        "min_confidence": min_confidence,
        "limit": min(limit, 500),
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }
    query = """
        MATCH (n {id: $node_id})-[r]-(m)
        WHERE (r.confidence_score >= $min_confidence OR r.confidence_score IS NULL)
          AND ($start_date IS NULL OR coalesce(r.start_date, $start_date) >= $start_date)
          AND ($end_date IS NULL OR coalesce(r.end_date, $end_date) <= $end_date)
        RETURN n, r, m
        LIMIT $limit
    """
    records = run_cypher(query, params)
    return {"records": records, "truncated": len(records) >= limit}


def get_evidence(claim_id: str) -> dict:
    """Get evidence chain for a claim."""
    params = {"claim_id": claim_id}
    query = """
        MATCH (c:Claim {claim_id: $claim_id})-[e:EVIDENCED_BY]->(s:SourceDocument)
        RETURN c, e, s
    """
    records = run_cypher(query, params)
    return {"records": records}


