"""Graph API endpoints."""

from datetime import date
from fastapi import APIRouter, Query
from app.models.pydantic.models import (
    GraphResponse, GraphNode, GraphEdge, GraphExpandRequest,
)
from app.services.graph_service import (
    get_member_graph, expand_node,
)
from app.core.config import settings
from app.core.errors import GraphDepthExceededError, GraphQueryTooLargeError

router = APIRouter(tags=["graph"])


def _build_graph_response(records, limit: int) -> GraphResponse:
    """Build GraphResponse from Neo4j records."""
    nodes_map: dict[str, GraphNode] = {}
    edges_map: dict[str, GraphEdge] = {}

    for record in records:
        for key, value in record.items():
            if value is None:
                continue
            if hasattr(value, "labels"):
                labels = list(value.labels)
                node_id = value.get("id", "")
                label = labels[0] if labels else "Unknown"
                if node_id and node_id not in nodes_map:
                    props = dict(value.items())
                    nodes_map[node_id] = GraphNode(
                        id=node_id, label=label, properties=props,
                    )
            elif hasattr(value, "type"):
                edge_type = value.type
                edge_id = value.get("id", "") or value.element_id
                if edge_id and edge_id not in edges_map:
                    props = dict(value.items())
                    edges_map[edge_id] = GraphEdge(
                        id=edge_id,
                        source=value.start_node.get("id", ""),
                        target=value.end_node.get("id", ""),
                        type=edge_type,
                        properties=props,
                        claim_id=props.get("claim_id"),
                        confidence_score=props.get("confidence_score"),
                    )

    truncated = len(nodes_map) > limit
    nodes_list = list(nodes_map.values())[:limit]

    node_ids = {n.id for n in nodes_list}
    filtered_edges = [
        e for e in edges_map.values()
        if e.source in node_ids and e.target in node_ids
    ]

    return GraphResponse(
        nodes=nodes_list,
        edges=filtered_edges,
        total_node_count=len(nodes_map),
        truncated=truncated,
    )


@router.get("/members/{member_id}/graph", response_model=GraphResponse)
def member_graph(
    member_id: str,
    depth: int = Query(2, ge=1, le=settings.max_graph_depth),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(settings.default_graph_limit, ge=1, le=settings.max_graph_limit),
    include_related_people: bool = Query(False),
    include_profile_facts: bool = Query(True),
    include_historical_background: bool = Query(False),
    include_finance: bool = Query(False),
    include_holdings: bool = Query(False),
):
    if depth > settings.max_graph_depth:
        raise GraphDepthExceededError(
            f"Graph query depth exceeds maximum allowed depth of {settings.max_graph_depth}",
            {"requested_depth": depth, "max_depth": settings.max_graph_depth},
        )

    result = get_member_graph(
        member_id, depth, start_date, end_date, min_confidence, limit,
        include_related_people=include_related_people,
        include_profile_facts=include_profile_facts,
        include_historical_background=include_historical_background,
        include_finance=include_finance,
        include_holdings=include_holdings,
    )
    records = result.get("records", [])

    response = _build_graph_response(records, limit)

    if len(response.nodes) > 500:
        raise GraphQueryTooLargeError(
            "The graph query returned too many nodes. Please narrow your filters.",
            {"node_count": len(response.nodes), "max_allowed": 500},
        )

    return response


@router.post("/graph/expand", response_model=GraphResponse)
def graph_expand(request: GraphExpandRequest):
    result = expand_node(
        request.node_id, 1,
        request.start_date, request.end_date,
        request.min_confidence, request.limit,
        include_finance=request.include_finance,
        include_holdings=request.include_holdings,
    )
    records = result.get("records", [])

    response = _build_graph_response(records, request.limit)

    if len(response.nodes) > 500:
        raise GraphQueryTooLargeError(
            "The graph query returned too many nodes. Please narrow your filters.",
            {"node_count": len(response.nodes), "max_allowed": 500},
        )

    return response
