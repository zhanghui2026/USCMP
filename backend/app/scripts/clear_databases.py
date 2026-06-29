"""Clear all data from PostgreSQL and Neo4j databases."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import engine, SessionLocal
from app.db.neo4j import get_driver
from app.models.sqlalchemy.models import Base
from app.core.logging import logger


def clear_postgres():
    logger.info("Clearing PostgreSQL...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("PostgreSQL tables recreated.")


def clear_neo4j():
    logger.info("Clearing Neo4j...")
    driver = get_driver()
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    logger.info("Neo4j graph cleared.")


def main():
    clear_postgres()
    clear_neo4j()
    logger.info("All databases cleared.")


if __name__ == "__main__":
    main()
