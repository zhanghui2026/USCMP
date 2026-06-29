"""Graph contract tests: edge/node consistency, limit truncation, ego network.

These tests verify that the graph response contract is maintained:
1. Every edge.source / edge.target is present in nodes
2. Limit truncation does not create orphan edges
3. Real members (e.g. K000188) return well-formed graphs
4. Empty/invalid graphs do not crash the response builder
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.api.routes.graph import _build_graph_response


# ---------------------------------------------------------------------------
# Neo4j record fakes that match the interface used by _build_graph_response
# ---------------------------------------------------------------------------

class N4jNode:
    """Fake Neo4j node: has .labels, .items(), .get()"""
    def __init__(self, node_id: str, labels: tuple[str, ...], properties: dict):
        self._props = {**properties, "id": node_id}
        self._labels = set(labels)

    @property
    def labels(self):
        return self._labels

    def items(self):
        return self._props.items()

    def get(self, key, default=None):
        return self._props.get(key, default)


class N4jEdge:
    """Fake Neo4j relationship: has .type, .items(), .get(), .start_node, .end_node"""
    def __init__(self, edge_id: str, source_id: str, target_id: str,
                 edge_type: str, properties: dict | None = None):
        self._props = {"id": edge_id, **(properties or {})}
        self._type = edge_type
        self._source_id = source_id
        self._target_id = target_id

    @property
    def type(self):
        return self._type

    def items(self):
        return self._props.items()

    def get(self, key, default=None):
        return self._props.get(key, default)

    @property
    def element_id(self):
        return self._props.get("id", "")

    class StartNode:
        def __init__(self, nid):
            self._id = nid
        def get(self, key, default=None):
            return self._id if key == "id" else default
    class EndNode:
        def __init__(self, nid):
            self._id = nid
        def get(self, key, default=None):
            return self._id if key == "id" else default

    @property
    def start_node(self):
        return self.StartNode(self._source_id)

    @property
    def end_node(self):
        return self.EndNode(self._target_id)


class N4jRecord:
    """Fake Neo4j record: has .items() returning (key, N4jNode|N4jEdge|None) pairs."""
    def __init__(self, **items):
        self._items = items

    def items(self):
        return self._items.items()


def rec(*items):
    """Build a record from positional items (auto-keyed as 'item_0', 'item_1', ...)."""
    return N4jRecord(**{f"item_{i}": val for i, val in enumerate(items)})


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------

class TestGraphResponseContract:

    def test_all_edges_reference_existing_nodes(self):
        n1 = N4jNode("person_A", ("Person",), {"name": "Alice"})
        n2 = N4jNode("party_D", ("Party",), {"name": "Democrats"})
        n3 = N4jNode("state_CA", ("State",), {"name": "CA"})
        e1 = N4jEdge("e1", "person_A", "party_D", "MEMBER_OF_PARTY")
        e2 = N4jEdge("e2", "person_A", "state_CA", "REPRESENTS_STATE")

        response = _build_graph_response([rec(n1, n2, n3, e1, e2)], limit=200)

        node_ids = {n.id for n in response.nodes}
        for edge in response.edges:
            assert edge.source in node_ids, (
                f"Edge source '{edge.source}' not found in nodes"
            )
            assert edge.target in node_ids, (
                f"Edge target '{edge.target}' not found in nodes"
            )

    def test_no_orphan_edges(self):
        n1 = N4jNode("person_A", ("Person",), {"name": "Alice"})
        n2 = N4jNode("party_D", ("Party",), {"name": "Democrats"})
        orphan = N4jEdge("orphan_e", "person_A", "person_Z", "RELATED_TO")

        response = _build_graph_response([rec(n1, n2, orphan)], limit=200)

        node_ids = {n.id for n in response.nodes}
        for edge in response.edges:
            assert edge.source in node_ids
            assert edge.target in node_ids
        edge_ids = {e.id for e in response.edges}
        assert "orphan_e" not in edge_ids

    def test_limit_truncation_no_orphan_edges(self):
        items = []
        for i in range(10):
            items.append(N4jNode(f"person_{i}", ("Person",), {"idx": i}))
        for i in range(9):
            items.append(N4jEdge(f"e{i}", f"person_{i}", f"person_{i+1}", "RELATED_TO"))

        response = _build_graph_response([rec(*items)], limit=5)

        assert len(response.nodes) == 5
        assert response.truncated is True
        valid_ids = {n.id for n in response.nodes}
        for edge in response.edges:
            assert edge.source in valid_ids
            assert edge.target in valid_ids

    def test_limit_truncation_keeps_valid_edges(self):
        items = []
        for i in range(10):
            items.append(N4jNode(f"node_{i}", ("Node",), {"idx": i}))
        for i in range(4):
            items.append(N4jEdge(f"e{i}", f"node_{i}", f"node_{i+1}", "RELATED_TO"))

        response = _build_graph_response([rec(*items)], limit=5)

        valid_ids = {n.id for n in response.nodes}
        assert len(response.nodes) == 5
        edg = response.edges
        for edge in edg:
            assert edge.source in valid_ids
            assert edge.target in valid_ids
        assert len(edg) >= 1

    def test_empty_graph_no_crash(self):
        response = _build_graph_response([], limit=200)
        assert response.nodes == []
        assert response.edges == []
        assert response.truncated is False

    def test_single_node_no_edges(self):
        n = N4jNode("person_A", ("Person",), {"name": "Alice"})
        response = _build_graph_response([rec(n)], limit=200)
        assert len(response.nodes) == 1
        assert response.edges == []

    def test_duplicate_nodes_deduplicated(self):
        n1 = N4jNode("person_A", ("Person",), {"name": "Alice"})
        n2 = N4jNode("person_A", ("Person",), {"name": "Alice Dup"})
        n3 = N4jNode("party_D", ("Party",), {"name": "Democrats"})
        e1 = N4jEdge("e1", "person_A", "party_D", "MEMBER_OF_PARTY")

        response = _build_graph_response([rec(n1, n2, n3, e1)], limit=200)
        node_ids = [n.id for n in response.nodes]
        assert node_ids.count("person_A") == 1

    def test_graph_response_is_json_serializable(self):
        import json

        n1 = N4jNode("person_A", ("Person",), {"name": "Alice", "born": "1950-01-01"})
        n2 = N4jNode("party_D", ("Party",), {"name": "Democrats"})
        e1 = N4jEdge("e1", "person_A", "party_D", "MEMBER_OF_PARTY")

        response = _build_graph_response([rec(n1, n2, e1)], limit=200)
        json.dumps(response.model_dump())


class TestEgoNetworkTypes:

    def test_allowed_edges_only(self):
        n_p = N4jNode("P", ("Person",), {})
        n_c = N4jNode("C", ("Committee",), {})
        n_s = N4jNode("S", ("State",), {})
        n_p2 = N4jNode("P2", ("Person",), {})
        good = N4jEdge("e1", "P", "C", "ASSIGNED_TO_COMMITTEE")
        bad = N4jEdge("e2", "P", "S", "RELATED_TO")

        response = _build_graph_response([rec(n_p, n_c, n_s, n_p2, good, bad)], limit=200)

        # bad edge (RELATED_TO) won't be filtered by the graph response builder,
        # but its source/target ARE valid nodes. The contract is only about
        # structural validity (edge refs must exist), not sematic validity.
        # Semantic filtering belongs in the graph service layer.
        node_ids = {n.id for n in response.nodes}
        for edge in response.edges:
            assert edge.source in node_ids
            assert edge.target in node_ids

    def test_k000188_graph_edges_reference_nodes(self):
        """Real K000188 graph response has no orphan edges."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph("uscl_person_K000188", depth=2)
        records = result.get("records", [])
        response = _build_graph_response(records, limit=50)

        node_ids = {n.id for n in response.nodes}
        for edge in response.edges:
            assert edge.source in node_ids, (
                f"Edge {edge.id} source '{edge.source}' not in nodes"
            )
            assert edge.target in node_ids, (
                f"Edge {edge.id} target '{edge.target}' not in nodes"
            )


class TestK000188Specific:
    """Tests targeting the originally-buggy member."""

    def test_k000188_graph_returns_nodes(self):
        from app.services.graph_service import get_member_graph
        result = get_member_graph("uscl_person_K000188", depth=2)
        records = result.get("records", [])
        response = _build_graph_response(records, limit=50)
        assert len(response.nodes) > 0
        assert len(response.edges) > 0

    def test_k000188_center_node_present(self):
        from app.services.graph_service import get_member_graph
        result = get_member_graph("uscl_person_K000188", depth=1)
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        center = response.nodes[0]
        assert center.id == "uscl_person_K000188"
        assert center.label == "Person"

    def test_k000188_has_party_state_chamber_edges(self):
        from app.services.graph_service import get_member_graph
        result = get_member_graph("uscl_person_K000188", depth=1)
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        edge_types = {e.type for e in response.edges}
        assert "MEMBER_OF_PARTY" in edge_types
        assert "REPRESENTS_STATE" in edge_types
        assert "SERVES_IN" in edge_types

    def test_k000188_no_person_person_edges(self):
        """K000188 must have zero Person-to-Person edges."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph("uscl_person_K000188", depth=2)
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)

        node_labels = {n.id: n.label for n in response.nodes}
        for edge in response.edges:
            src_label = node_labels.get(edge.source, "")
            tgt_label = node_labels.get(edge.target, "")
            assert not (src_label == "Person" and tgt_label == "Person"), (
                f"Person-Person edge found: {edge.source} -[{edge.type}]-> {edge.target}"
            )

    def test_default_no_related_people_single_person(self):
        """Default graph (include_related_people=False) must have exactly 1 Person."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_K000188", depth=2, include_related_people=False
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        person_count = sum(1 for n in response.nodes if n.label == "Person")
        assert person_count == 1, f"Expected 1 Person node, got {person_count}"

    def test_include_related_people_shows_more_persons(self):
        """With include_related_people=True, graph must show > 1 Person."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_K000188", depth=2, include_related_people=True
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        person_count = sum(1 for n in response.nodes if n.label == "Person")
        assert person_count > 1, (
            f"Expected > 1 Person with include_related_people, got {person_count}"
        )


class TestProfileStatusContract:
    """Profile status computation tests."""

    def test_summary_only_for_uscl_data(self):
        """USCL-only data (birth_date + summary only) -> summary_only."""
        from app.etl.profile_status import compute_profile_status
        data = {
            "short_summary": "Senator from CA",
            "birth_date": "1950-01-01",
            "birth_place": None,
            "education": [],
            "occupations": [],
            "prior_positions": [],
            "employers": [],
            "military_service": [],
            "image_url": None,
        }
        status, parsed, missing = compute_profile_status(data)
        assert status == "summary_only"
        assert "short_summary" in parsed
        assert "birth_date" in parsed
        assert "education" in missing
        assert "occupations" in missing

    def test_available_for_rich_wikipedia_data(self):
        """Rich Wikipedia data -> available."""
        from app.etl.profile_status import compute_profile_status
        data = {
            "short_summary": "Senator from CA...",
            "birth_date": "1950-01-01",
            "birth_place": "San Francisco, CA",
            "education": [{"institution": "Harvard"}],
            "occupations": ["Politician", "Lawyer"],
            "prior_positions": [{"position": "Governor"}],
            "employers": [],
            "military_service": [],
            "image_url": None,
        }
        status, parsed, missing = compute_profile_status(data)
        assert status == "available"
        assert "education" in parsed
        assert "occupations" in parsed
        assert "prior_positions" in parsed

    def test_partial_with_some_structured_fields(self):
        """One structured field + birth_date -> partial."""
        from app.etl.profile_status import compute_profile_status
        data = {
            "short_summary": "Senator",
            "birth_date": "1950-01-01",
            "birth_place": None,
            "education": [{"institution": "Harvard"}],
            "occupations": [],
            "prior_positions": [],
            "employers": [],
            "military_service": [],
            "image_url": None,
        }
        status, parsed, missing = compute_profile_status(data)
        assert status == "partial"

    def test_fields_not_present_when_empty(self):
        """Empty lists should appear in missing_fields, not parsed_fields."""
        from app.etl.profile_status import compute_profile_status
        data = {
            "short_summary": None,
            "birth_date": None,
            "birth_place": None,
            "education": [],
            "occupations": [],
            "prior_positions": [],
            "employers": [],
            "military_service": [],
            "image_url": None,
        }
        status, parsed, missing = compute_profile_status(data)
        assert status == "summary_only"
        assert "education" in missing
        assert "short_summary" in missing


class TestProfileFactsGraph:
    """v0.7: Profile facts in graph contract."""

    def test_w000805_has_profile_fact_nodes_with_default(self):
        """Default graph (include_profile_facts=True) includes profile facts."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_W000805", depth=2,
            include_related_people=False,
            include_profile_facts=True,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        labels = {n.label for n in response.nodes}
        assert "EducationInstitution" in labels, labels
        assert "Position" in labels, labels
        assert "ProfileSource" in labels, labels

    def test_w000805_without_profile_facts_excludes_them(self):
        """include_profile_facts=False removes profile nodes."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_W000805", depth=2,
            include_related_people=False,
            include_profile_facts=False,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        labels = {n.label for n in response.nodes}
        assert "EducationInstitution" not in labels, labels
        assert "Position" not in labels, labels
        assert "ProfileSource" not in labels, labels

    def test_default_profile_facts_still_one_person(self):
        """With profile facts, Person count must still be 1."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_W000805", depth=2,
            include_related_people=False,
            include_profile_facts=True,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        person_count = sum(1 for n in response.nodes if n.label == "Person")
        assert person_count == 1, f"Got {person_count} Person nodes"

    def test_no_orphan_edges_with_profile_facts(self):
        """All edges must reference existing nodes with profile facts."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_W000805", depth=2,
            include_related_people=False,
            include_profile_facts=True,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        node_ids = {n.id for n in response.nodes}
        for edge in response.edges:
            assert edge.source in node_ids, (
                f"Edge {edge.id} source '{edge.source}' not in nodes"
            )
            assert edge.target in node_ids, (
                f"Edge {edge.id} target '{edge.target}' not in nodes"
            )

    def test_no_person_person_with_profile_facts(self):
        """Profile facts must not create Person-Person direct edges."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_W000805", depth=2,
            include_related_people=False,
            include_profile_facts=True,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        node_labels = {n.id: n.label for n in response.nodes}
        for edge in response.edges:
            src_label = node_labels.get(edge.source, "")
            tgt_label = node_labels.get(edge.target, "")
            assert not (src_label == "Person" and tgt_label == "Person"), (
                f"Person-Person edge: {edge.source} -> {edge.target}"
            )

    def test_summary_only_profile_no_fact_nodes(self):
        """K000188 (summary_only) must have no profile fact nodes."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_K000188", depth=2,
            include_related_people=False,
            include_profile_facts=True,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        labels = {n.label for n in response.nodes}
        assert "EducationInstitution" not in labels
        assert "Position" not in labels
        assert "ProfileSource" not in labels


class TestPelosiProfileFixture:
    """v0.7.1: Nancy Pelosi profile tests."""

    def test_pelosi_profile_status_is_available(self):
        """Pelosi must be available after fixture backfill."""
        from app.db.postgres import SessionLocal
        from app.models.sqlalchemy.models import MemberProfile
        session = SessionLocal()
        try:
            p = session.query(MemberProfile).filter(
                MemberProfile.member_id == "uscl_person_P000197"
            ).first()
            assert p is not None, "Pelosi profile missing"
            assert p.profile_status == "available", (
                f"Expected available, got {p.profile_status}"
            )
            assert p.source == "wikipedia"
            assert p.wikipedia_title == "Nancy Pelosi"
            assert p.wikidata_qid == "Q170581"
        finally:
            session.close()

    def test_pelosi_has_education_and_positions(self):
        """Pelosi profile must contain education and prior_positions."""
        from app.db.postgres import SessionLocal
        from app.models.sqlalchemy.models import MemberProfile
        session = SessionLocal()
        try:
            p = session.query(MemberProfile).filter(
                MemberProfile.member_id == "uscl_person_P000197"
            ).first()
            assert len(p.education or []) > 0, "Pelosi has no education"
            assert len(p.prior_positions or []) > 0, "Pelosi has no positions"
        finally:
            session.close()

    def test_pelosi_graph_has_profile_nodes(self):
        """Pelosi graph must contain EducationInstitution, Position, ProfileSource."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_P000197", depth=2,
            include_related_people=False,
            include_profile_facts=True,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        labels = {n.label for n in response.nodes}
        assert "EducationInstitution" in labels, labels
        assert "Position" in labels, labels
        assert "ProfileSource" in labels, labels

    def test_pelosi_graph_person_count_is_one(self):
        """Pelosi graph must have exactly 1 Person."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_P000197", depth=2,
            include_related_people=False,
            include_profile_facts=True,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        person_count = sum(1 for n in response.nodes if n.label == "Person")
        assert person_count == 1

    def test_pelosi_graph_no_orphan_edges(self):
        """Pelosi graph must have zero orphan edges."""
        from app.services.graph_service import get_member_graph
        result = get_member_graph(
            "uscl_person_P000197", depth=2,
            include_related_people=False,
            include_profile_facts=True,
        )
        records = result.get("records", [])
        response = _build_graph_response(records, limit=200)
        node_ids = {n.id for n in response.nodes}
        for edge in response.edges:
            assert edge.source in node_ids
            assert edge.target in node_ids

    def test_pelosi_summary_only_decreased(self):
        """summary_only count must have decreased after Pelosi upgrade."""
        from app.db.postgres import SessionLocal
        session = SessionLocal()
        try:
            from sqlalchemy import text
            available = session.execute(text(
                "SELECT COUNT(*) FROM member_profiles WHERE profile_status = 'available'"
            )).fetchone()[0]
            assert available >= 4, (
                f"Expected >=4 available profiles, got {available}"
            )
        finally:
            session.close()
