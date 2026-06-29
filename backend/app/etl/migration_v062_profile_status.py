"""
v0.6.2 Schema Migration: Add profile_status, parsed_fields, missing_fields, employers
to member_profiles table.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import Column, String, JSON, text
from app.db.postgres import engine, SessionLocal
from app.core.logging import logger

MIGRATION_ID = "v062_profile_status"


def migrate():
    columns_to_add = [
        ("profile_status", String(32), "summary_only"),
        ("parsed_fields", JSON, "[]"),
        ("missing_fields", JSON, "[]"),
        ("employers", JSON, "[]"),
    ]

    with engine.connect() as conn:
        for col_name, col_type, default_val in columns_to_add:
            try:
                result = conn.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = 'member_profiles' AND column_name = '{col_name}'"
                )).fetchone()
                if result:
                    logger.info(f"Column {col_name} already exists, skipping")
                    continue
                conn.execute(text(
                    f"ALTER TABLE member_profiles ADD COLUMN {col_name} "
                    f"{'JSON' if str(col_type) == 'JSON' else 'VARCHAR(32)'} "
                    f"DEFAULT '{default_val}'"
                ))
                conn.commit()
                logger.info(f"Added column {col_name} to member_profiles")
            except Exception as e:
                logger.warning(f"Failed to add {col_name}: {e}")

    logger.info(f"Migration {MIGRATION_ID} complete")


if __name__ == "__main__":
    migrate()
