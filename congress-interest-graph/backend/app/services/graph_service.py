"""Graph service - all Cypher queries centralized here.

v0.7: Profile facts layer with include_profile_facts control.
v0.6.2: Ego network with include_related_people control.
Default: depth 1 only (center Person -> Party/State/Chamber/Committee +
EducationInstitution/Employer/Position/ProfileSource if available).
"""

from datetime import date
from typing import Optional
from app.db.neo4j import run_cypher


IDENTITY_EDGE_TYPES = frozenset({
    "MEMBER_OF_PARTY", "REPRESENTS_STATE", "SERVES_IN", "ASSIGNED_TO",
})

PROFILE_EDGE_TYPES = frozenset({
    "EDUCATED_AT", "EMPLOYED_BY", "HELD_POSITION", "HAS_PROFILE_SOURCE",
})

FINANCE_EDGE_TYPES = frozenset({
    "ASSOCIATED_WITH_COMMITTEE", "CONTRIBUTED_TO", "HAS_CONTRIBUTION_SOURCE",
})

HOLDINGS_EDGE_TYPES = frozenset({
    "DISCLOSED_HOLDING", "REPORTED_IN", "HAS_HOLDING_SOURCE",
})

EGO_EDGE_TYPES = frozenset((*IDENTITY_EDGE_TYPES, *PROFILE_EDGE_TYPES, *FINANCE_EDGE_TYPES, *HOLDINGS_EDGE_TYPES))

_IDENTITY_EDGE_LIST = (
    "['MEMBER_OF_PARTY','REPRESENTS_STATE','SERVES_IN','ASSIGNED_TO']"
)
_PROFILE_EDGE_LIST = (
    "['EDUCATED_AT','EMPLOYED_BY','HELD_POSITION','HAS_PROFILE_SOURCE']"
)
_FINANCE_EDGE_LIST = (
    "['ASSOCIATED_WITH_COMMITTEE','CONTRIBUTED_TO','HAS_CONTRIBUTION_SOURCE']"
)
_HOLDINGS_EDGE_LIST = (
    "['DISCLOSED_HOLDING','REPORTED_IN','HAS_HOLDING_SOURCE']"
)
_ALL_EDGE_LIST = (
    "['MEMBER_OF_PARTY','REPRESENTS_STATE','SERVES_IN','ASSIGNED_TO',"
    "'EDUCATED_AT','EMPLOYED_BY','HELD_POSITION','HAS_PROFILE_SOURCE',"
    "'ASSOCIATED_WITH_COMMITTEE','CONTRIBUTED_TO','HAS_CONTRIBUTION_SOURCE',"
    "'DISCLOSED_HOLDING','REPORTED_IN','HAS_HOLDING_SOURCE']"
)


def _edge_filter(rel_var: str, include_profile_facts: bool = True, include_finance: bool = True, include_holdings: bool = True) -> str:
    parts = [_IDENTITY_EDGE_LIST]
    if include_profile_facts:
        parts.append(_PROFILE_EDGE_LIST)
    if include_finance:
        parts.append(_FINANCE_EDGE_LIST)
    if include_holdings:
        parts.append(_HOLDINGS_EDGE_LIST)
    edges = "+".join(parts)
    return f"type({rel_var}) IN {edges}"


def get_member_graph(
    member_id: str,
    depth: int = 2,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_confidence: float = 0.0,
    limit: int = 200,
    include_related_people: bool = False,
    include_profile_facts: bool = True,
    include_historical_background: bool = False,
    include_finance: bool = False,
    include_holdings: bool = False,
) -> dict:
    """Get ego network centered on a member.

    Default (include_related_people=False, include_profile_facts=True):
      Depth 1 only: center Person -> Party/State/Chamber/Committee
                    + EducationInstitution/Employer/Position/ProfileSource

    include_related_people=True:
      Depth 2: expands to other Persons through shared entities.
      No direct Person-Person edges are traversed.

    include_profile_facts=False:
      Only identity edges (MEMBER_OF_PARTY, REPRESENTS_STATE,
      SERVES_IN, ASSIGNED_TO). No profile fact edges.

    include_historical_background=True:
      Includes BackgroundPerson nodes with BACKGROUND_RELATION edges
      for historical members with documented connections to current members.

    start_date/end_date filter relationships by their date range.
    """
    params = {
        "member_id": member_id,
        "min_confidence": min_confidence,
        "limit": min(limit, 500),
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }

    date_clause = (
        "AND ($start_date IS NULL OR coalesce(r.start_date, $start_date) >= $start_date) "
        "AND ($end_date IS NULL OR coalesce(r.end_date, $end_date) <= $end_date)"
    )

    edge_f = _edge_filter("r", include_profile_facts, include_finance, include_holdings)

    scope_filter = (
        "AND (NOT n:Person OR n.person_scope = 'current' OR n.person_scope IS NULL)"
    ) if not include_historical_background else ""

    edge_f1 = _edge_filter("r1", include_profile_facts, include_finance, include_holdings)
    edge_f2 = _edge_filter("r2", include_profile_facts, include_finance, include_holdings)

    if depth == 1 or not include_related_people:
        query = f"""
            MATCH (p:Person {{id: $member_id}})-[r]-(n)
            WHERE (r.confidence_score >= $min_confidence OR r.confidence_score IS NULL)
              AND ({edge_f})
              {date_clause}
              {scope_filter}
            WITH p, r, n,
                 CASE type(r)
                   WHEN 'ASSIGNED_TO' THEN 0
                   WHEN 'HELD_POSITION' THEN 1
                   WHEN 'EMPLOYED_BY' THEN 2
                   WHEN 'ASSOCIATED_WITH_COMMITTEE' THEN 3
                   WHEN 'CONTRIBUTED_TO' THEN 4
                   WHEN 'DISCLOSED_HOLDING' THEN 5
                   ELSE 6
                 END AS rel_priority
            RETURN p, r, n
            ORDER BY rel_priority, coalesce(r.amount, r.value_low, 0) DESC, coalesce(n.name, n.display_name, n.id)
            LIMIT $limit
        """
        if include_historical_background:
            query += f"""
            UNION
            MATCH (p:Person {{{{id: $member_id}}}})-[r:BACKGROUND_RELATION]-(n:BackgroundPerson)
            WHERE (r.confidence_score >= $min_confidence OR r.confidence_score IS NULL)
              {date_clause}
            RETURN p, r, n
            """
    else:
        edge_f1 = _edge_filter("r1", include_profile_facts, include_finance, include_holdings)
        edge_f2 = _edge_filter("r2", include_profile_facts, include_finance, include_holdings)
        scope_filter_n2 = (
            "AND (NOT n2:Person OR n2.person_scope = 'current' OR n2.person_scope IS NULL)"
        ) if not include_historical_background else ""
        query = f"""
            MATCH (p:Person {{id: $member_id}})-[r1]-(n1)
            WHERE (r1.confidence_score >= $min_confidence OR r1.confidence_score IS NULL)
              AND ({edge_f1})
              {date_clause.replace('r.', 'r1.')}
            OPTIONAL MATCH (n1)-[r2]-(n2:Person)
            WHERE (r2.confidence_score >= $min_confidence OR r2.confidence_score IS NULL)
              AND n2 <> p
              AND ({edge_f2})
              {scope_filter_n2}
              {date_clause.replace('r.', 'r2.')}
            WITH p, r1, r2, n1, n2,
                 CASE type(r1)
                   WHEN 'ASSIGNED_TO' THEN 0
                   WHEN 'HELD_POSITION' THEN 1
                   WHEN 'EMPLOYED_BY' THEN 2
                   WHEN 'ASSOCIATED_WITH_COMMITTEE' THEN 3
                   WHEN 'CONTRIBUTED_TO' THEN 4
                   WHEN 'DISCLOSED_HOLDING' THEN 5
                   ELSE 6
                 END AS rel_priority
            RETURN p, r1, r2, n1, n2
            ORDER BY rel_priority, coalesce(r1.amount, r1.value_low, 0) DESC, coalesce(n1.name, n1.display_name, n1.id)
            LIMIT $limit
        """
        if include_historical_background:
            query += f"""
            UNION
            MATCH (p:Person {{{{id: $member_id}}}})-[r1:BACKGROUND_RELATION]-(n1:BackgroundPerson)
            WHERE (r1.confidence_score >= $min_confidence OR r1.confidence_score IS NULL)
              {date_clause.replace('r.', 'r1.')}
            OPTIONAL MATCH (n1)-[r2]-(n2:Person)
            WHERE (r2.confidence_score >= $min_confidence OR r2.confidence_score IS NULL)
              AND n2 <> p
            RETURN p, r1, r2, n1, n2
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
    include_finance: bool = False,
    include_holdings: bool = False,
) -> dict:
    """Expand a single node to show direct ego-network connections."""
    params = {
        "node_id": node_id,
        "min_confidence": min_confidence,
        "limit": min(limit, 500),
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }
    query = f"""
        MATCH (n {{id: $node_id}})-[r]-(m)
        WHERE (r.confidence_score >= $min_confidence OR r.confidence_score IS NULL)
          AND ({_edge_filter('r', include_profile_facts=True, include_finance=include_finance, include_holdings=include_holdings)})
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
