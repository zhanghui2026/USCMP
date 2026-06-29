"""
Schema migration: add member_profiles table for v0.6 Wikipedia profiles.

Usage:
    python3 -m app.etl.schema_migration add_member_profiles
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import inspect, text
from sqlalchemy.exc import ProgrammingError

from app.db.postgres import engine, SessionLocal
from app.models.sqlalchemy.models import Base, MemberProfile
from app.core.logging import logger


MIGRATION_ID = "add_member_profiles"


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def run() -> dict:
    result = {"migration": MIGRATION_ID, "actions": []}

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "member_profiles" in existing_tables:
        result["actions"].append("table_exists")
        return result

    MemberProfile.__table__.create(bind=engine)
    result["actions"].append("table_created")
    return result


def main():
    parser = argparse.ArgumentParser(description="Run schema migrations")
    parser.add_argument("migration_name", nargs="?", default=MIGRATION_ID)
    args = parser.parse_args()

    if args.migration_name != MIGRATION_ID:
        logger.error(f"Unknown migration: {args.migration_name}")
        sys.exit(1)

    result = run()
    logger.info(f"Migration result: {result}")


if __name__ == "__main__":
    main()
