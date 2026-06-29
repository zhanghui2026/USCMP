"""Test mock data generator coverage and constraints."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scripts.mock_data_generator import MockDataGenerator


def test_member_count():
    gen = MockDataGenerator()
    gen.generate_all()
    stats = gen.get_statistics()
    assert stats["members"] == 50, f"Expected 50 members, got {stats['members']}"


def test_org_count():
    gen = MockDataGenerator()
    gen.generate_all()
    stats = gen.get_statistics()
    assert stats["organizations"] == 100, f"Expected 100 orgs, got {stats['organizations']}"


def test_events_count():
    gen = MockDataGenerator()
    gen.generate_all()
    stats = gen.get_statistics()
    assert stats["events"] == 100, f"Expected 100 events, got {stats['events']}"


def test_claims_count():
    gen = MockDataGenerator()
    gen.generate_all()
    stats = gen.get_statistics()
    assert stats["claims"] == 300, f"Expected 300 claims, got {stats['claims']}"


def test_source_docs_count():
    gen = MockDataGenerator()
    gen.generate_all()
    stats = gen.get_statistics()
    assert stats["source_documents"] == 500, f"Expected 500 source docs, got {stats['source_documents']}"


def test_congress_coverage():
    gen = MockDataGenerator()
    gen.generate_all()
    stats = gen.get_statistics()
    congress_coverage = stats["congress_coverage"]
    assert 117 in congress_coverage, "Missing 117th congress"
    assert 118 in congress_coverage, "Missing 118th congress"
    assert 119 in congress_coverage, "Missing 119th congress"


def test_low_confidence_relations():
    gen = MockDataGenerator()
    gen.generate_all()
    stats = gen.get_statistics()
    assert stats["low_confidence_relationships"] >= 20, (
        f"Expected at least 20 low-confidence relations, got {stats['low_confidence_relationships']}"
    )


def test_all_mock_marked():
    gen = MockDataGenerator()
    gen.generate_all()
    for m in gen.members:
        assert m["source"] == "mock", f"Member {m['id']} not marked as mock source"
        assert m["source_reliability"] == "mock", f"Member {m['id']} not marked as mock"
        assert m["extraction_method"] == "mock", f"Member {m['id']} not marked as mock"
        assert m["official_ids"] == {}, f"Mock member {m['id']} official_ids should be empty"
        assert m["latest_term_start"] is None, f"Mock member {m['id']} latest_term_start should be None"
        assert m["latest_term_end"] is None, f"Mock member {m['id']} latest_term_end should be None"

    for o in gen.orgs:
        assert o["source_reliability"] == "mock", f"Org {o['id']} not marked as mock"

    for c in gen.claims:
        assert c["extraction_method"] == "mock", f"Claim {c['claim_id']} not marked as mock"
        assert c["source_reliability"] == "mock", f"Claim {c['claim_id']} not marked as mock"


def test_relations_have_claim_ids():
    gen = MockDataGenerator()
    gen.generate_all()
    main_rels = [
        r for r in gen.relationships
        if r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY")
    ]
    for r in main_rels:
        assert r.get("claim_id"), f"Relation {r['id']} missing claim_id"
        assert r.get("confidence_score") is not None, f"Relation {r['id']} missing confidence_score"


def test_neo4j_nodes_generated():
    gen = MockDataGenerator()
    gen.generate_all()
    nodes = gen.to_neo4j_nodes()
    assert len(nodes) > 0
    labels = {n["label"] for n in nodes}
    assert "Person" in labels
    assert "Organization" in labels
    assert "PoliticalEntity" in labels
    assert "Event" in labels
    assert "Claim" in labels
    assert "SourceDocument" in labels


def test_neo4j_edges_generated():
    gen = MockDataGenerator()
    gen.generate_all()
    edges = gen.to_neo4j_edges()
    assert len(edges) > 300  # including evidence edges

    edge_types = {e["type"] for e in edges}
    for flow_type in ["RECEIVED_CONTRIBUTION", "SERVED_ON_COMMITTEE",
                       "VOTED_FOR", "HAS_CLAIM", "EVIDENCED_BY"]:
        assert flow_type in edge_types, f"Missing edge type: {flow_type}"


def test_members_have_committees():
    gen = MockDataGenerator()
    gen.generate_all()
    for m in gen.members:
        assert len(m["committee_memberships"]) >= 1, f"Member {m['id']} has no committee"


def test_controversy_members():
    gen = MockDataGenerator()
    gen.generate_all()
    members_with_controversies = [
        m for m in gen.members if m.get("controversies")
    ]
    assert len(members_with_controversies) > 0, "No members have controversy records"


def test_postgres_data_structure():
    gen = MockDataGenerator()
    gen.generate_all()
    pg_data = gen.to_postgres_data()
    assert "members" in pg_data
    assert "organizations" in pg_data
    assert "events" in pg_data
    assert "claims" in pg_data
    assert "source_documents" in pg_data
