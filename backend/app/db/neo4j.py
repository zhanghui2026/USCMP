"""Neo4j database connection and session management."""

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
from app.core.config import settings
from app.core.logging import logger

_driver = None
_available = True


def is_available() -> bool:
    global _available
    if not _available:
        return False
    try:
        get_driver()
        return True
    except Exception:
        return False


def get_driver():
    global _driver, _available
    if not _available:
        return None
    if _driver is None:
        try:
            _driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_lifetime=3600,
            )
        except (ServiceUnavailable, AuthError, OSError) as e:
            _available = False
            logger.warning(f"Neo4j unavailable, graph features disabled: {e}")
            return None
    return _driver


def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def run_cypher(query: str, parameters: dict | None = None):
    try:
        driver = get_driver()
        if not driver:
            return []
        with driver.session() as session:
            result = session.run(query, parameters or {})
            return [record for record in result]
    except (ServiceUnavailable, OSError) as e:
        logger.warning(f"Neo4j query failed: {e}")
        return []


def run_cypher_with_summary(query: str, parameters: dict | None = None):
    try:
        driver = get_driver()
        if not driver:
            return [], None
        with driver.session() as session:
            result = session.run(query, parameters or {})
            records = [record.data() for record in result]
            summary = result.consume()
            return records, summary
    except (ServiceUnavailable, OSError) as e:
        logger.warning(f"Neo4j query failed: {e}")
        return [], None
