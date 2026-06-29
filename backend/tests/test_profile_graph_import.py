"""Tests for profile graph import script (v0.7)."""

import pytest
from app.etl.import_profile_graph import (
    _slugify,
    _build_education_statements,
    _build_position_statements,
    _build_employer_statements,
    _build_source_statements,
)


class TestSlugify:
    def test_simple_name(self):
        assert _slugify("Harvard University") == "harvard_university"

    def test_special_chars(self):
        assert _slugify("U.S. Senate") == "u_s_senate"

    def test_mixed_case(self):
        assert _slugify("George Washington University") == \
            "george_washington_university"

    def test_empty(self):
        assert _slugify("") == "unknown"

    def test_only_spaces(self):
        assert _slugify("   ") == "unknown"


class TestBuildStatements:
    def test_education_statements(self):
        profile = {
            "education": [
                {"institution": "Harvard"},
                {"institution": "Yale"},
            ]
        }
        ops = _build_education_statements(profile, "p1")
        assert len(ops) == 2
        assert ops[0]["node_id"] == "edu_harvard"
        assert ops[0]["label"] == "EducationInstitution"
        assert ops[0]["edge_type"] == "EDUCATED_AT"
        assert ops[1]["node_id"] == "edu_yale"

    def test_education_empty_list(self):
        ops = _build_education_statements({"education": []}, "p1")
        assert len(ops) == 0

    def test_education_missing_field(self):
        ops = _build_education_statements({}, "p1")
        assert len(ops) == 0

    def test_education_empty_institution(self):
        ops = _build_education_statements(
            {"education": [{"institution": ""}]}, "p1"
        )
        assert len(ops) == 0

    def test_position_statements(self):
        profile = {
            "prior_positions": [
                {"position": "Governor of Virginia"},
                {"position": "U.S. Senator"},
            ]
        }
        ops = _build_position_statements(profile, "p1")
        assert len(ops) == 2
        assert ops[0]["label"] == "Position"
        assert ops[0]["edge_type"] == "HELD_POSITION"

    def test_employer_from_dict(self):
        profile = {
            "employers": [{"name": "Google"}, {"institution": "MIT"}]
        }
        ops = _build_employer_statements(profile, "p1")
        assert len(ops) == 2

    def test_source_statements(self):
        profile = {
            "profile_sources": {
                "wikipedia_title": "Mark Warner",
                "wikipedia_url": "https://en.wikipedia.org/wiki/Mark_Warner",
            }
        }
        ops = _build_source_statements(profile, "p1")
        assert len(ops) == 1
        assert ops[0]["label"] == "ProfileSource"
        assert ops[0]["edge_type"] == "HAS_PROFILE_SOURCE"

    def test_source_empty(self):
        ops = _build_source_statements({"profile_sources": {}}, "p1")
        assert len(ops) == 0

    def test_source_missing(self):
        ops = _build_source_statements({}, "p1")
        assert len(ops) == 0


class TestImportIdempotency:
    """Test that running import twice does not duplicate nodes."""

    def test_reimport_preserves_counts(self):
        from app.db.neo4j import run_cypher
        from app.etl.import_profile_graph import import_profile_graph

        before = {}
        for label in ["EducationInstitution", "Position", "Employer",
                       "ProfileSource"]:
            result = run_cypher(f"MATCH (n:{label}) RETURN count(n) AS cnt", {})
            before[label] = result[0]["cnt"] if result else 0

        total = import_profile_graph(dry_run=False)
        assert total["edges"] >= 0

        after = {}
        for label in before:
            result = run_cypher(f"MATCH (n:{label}) RETURN count(n) AS cnt", {})
            after[label] = result[0]["cnt"] if result else 0

        for label in before:
            assert after[label] == before[label], (
                f"{label}: before={before[label]}, after={after[label]}"
            )
