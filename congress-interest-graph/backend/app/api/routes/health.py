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
