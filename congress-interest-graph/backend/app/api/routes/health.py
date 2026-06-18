"""Health check endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import text
from app.db.postgres import SessionLocal
from app.db.neo4j import get_driver
from app.models.pydantic.models import HealthResponse
from app.core.logging import logger

router = APIRouter(tags=["health"])


def _detect_data_mode() -> str:
    """Detect whether data is mock, mixed, or real from members.source."""
    mock_count = 0
    real_count = 0
    try:
        db = SessionLocal()
        r = db.execute(text(
            "SELECT source, COUNT(*) as cnt FROM members GROUP BY source"
        )).fetchall()
        db.close()
        for row in r:
            if row[0] == "mock":
                mock_count = row[1]
            else:
                real_count += row[1]
    except Exception:
        return "unknown"

    if real_count == 0 and mock_count > 0:
        return "mock"
    elif mock_count > 0 and real_count > 0:
        return "mixed"
    elif real_count > 0 and mock_count == 0:
        return "real"
    return "unknown"


@router.get("/health", response_model=HealthResponse)
def health_check():
    postgres_status = "ok"
    neo4j_status = "ok"

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        logger.warning(f"PostgreSQL health check failed: {e}")
        postgres_status = "error"

    try:
        driver = get_driver()
        with driver.session() as session:
            session.run("RETURN 1")
    except Exception as e:
        logger.warning(f"Neo4j health check failed: {e}")
        neo4j_status = "error"

    overall = "ok" if postgres_status == "ok" and neo4j_status == "ok" else "degraded"
    data_mode = _detect_data_mode()

    return HealthResponse(
        status=overall,
        postgres=postgres_status,
        neo4j=neo4j_status,
        data_mode=data_mode,
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/stats/profiles")
def profile_statistics():
    """Return profile source and status statistics."""
    stats = {
        "total_members": 0,
        "current_members": 0,
        "historical_members": 0,
        "uscl_profiles": 0,
        "wikipedia_profiles": 0,
        "missing_profiles": 0,
        "available_profiles": 0,
        "partial_profiles": 0,
        "summary_only_profiles": 0,
        "profiles_with_graph_facts": 0,
        "profiles_without_graph_facts": 0,
    }
    try:
        db = SessionLocal()
        total = db.execute(text("SELECT COUNT(*) FROM members")).fetchone()[0]
        current = db.execute(text(
            "SELECT COUNT(*) FROM members WHERE is_current = TRUE"
        )).fetchone()[0]
        historical = db.execute(text(
            "SELECT COUNT(*) FROM members WHERE is_current = FALSE"
        )).fetchone()[0]
        uscl = db.execute(text(
            "SELECT COUNT(*) FROM member_profiles WHERE source = 'uscl'"
        )).fetchone()[0]
        wiki = db.execute(text(
            "SELECT COUNT(*) FROM member_profiles WHERE source = 'wikipedia'"
        )).fetchone()[0]
        available = db.execute(text(
            "SELECT COUNT(*) FROM member_profiles WHERE profile_status = 'available'"
        )).fetchone()[0]
        partial = db.execute(text(
            "SELECT COUNT(*) FROM member_profiles WHERE profile_status = 'partial'"
        )).fetchone()[0]
        summary = db.execute(text(
            "SELECT COUNT(*) FROM member_profiles WHERE profile_status = 'summary_only'"
        )).fetchone()[0]
        db.close()

        stats["total_members"] = total
        stats["current_members"] = current
        stats["historical_members"] = historical
        stats["uscl_profiles"] = uscl
        stats["wikipedia_profiles"] = wiki
        stats["missing_profiles"] = total - uscl - wiki
        stats["available_profiles"] = available
        stats["partial_profiles"] = partial
        stats["summary_only_profiles"] = summary
        stats["profiles_with_graph_facts"] = available + partial
        stats["profiles_without_graph_facts"] = total - stats["profiles_with_graph_facts"]
    except Exception:
        pass
    return stats


@router.get("/stats/profiles/current-coverage")
def current_profile_coverage():
    """Return profile coverage statistics for current members only."""
    coverage = {
        "total_current_members": 0,
        "with_profile": 0,
        "without_profile": 0,
        "available": 0,
        "partial": 0,
        "summary_only": 0,
        "available_pct": 0.0,
        "partial_pct": 0.0,
        "summary_only_pct": 0.0,
        "enriched_pct": 0.0,
    }
    try:
        db = SessionLocal()
        total_current = db.execute(text(
            "SELECT COUNT(*) FROM members WHERE is_current = TRUE"
        )).fetchone()[0]
        coverage["total_current_members"] = total_current

        counts = db.execute(text("""
            SELECT mp.profile_status, COUNT(*)
            FROM member_profiles mp
            INNER JOIN members m ON mp.bioguide_id = m.bioguide_id
            WHERE m.is_current = TRUE
            GROUP BY mp.profile_status
        """)).fetchall()

        for status, cnt in counts:
            if status == "available":
                coverage["available"] = cnt
            elif status == "partial":
                coverage["partial"] = cnt
            elif status == "summary_only":
                coverage["summary_only"] = cnt

        coverage["with_profile"] = coverage["available"] + coverage["partial"] + coverage["summary_only"]
        coverage["without_profile"] = total_current - coverage["with_profile"]

        if total_current > 0:
            coverage["available_pct"] = round(coverage["available"] / total_current * 100, 1)
            coverage["partial_pct"] = round(coverage["partial"] / total_current * 100, 1)
            coverage["summary_only_pct"] = round(coverage["summary_only"] / total_current * 100, 1)
            coverage["enriched_pct"] = round(
                (coverage["available"] + coverage["partial"]) / total_current * 100, 1
            )

        db.close()
    except Exception:
        pass
    return coverage
