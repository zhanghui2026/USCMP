"""Safe schema migration for v0.4 column additions.

Run once before deployment or on app startup to add new columns
and indexes to existing databases without data loss.

Usage:
    python3 -m app.etl.schema_migration
"""

from __future__ import annotations

from sqlalchemy import text
from app.db.postgres import engine
from app.core.logging import logger


MIGRATIONS = [
    # New columns on members table
    ("source", "ALTER TABLE members ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'mock' NOT NULL"),
    ("source_idx", "CREATE INDEX IF NOT EXISTS idx_members_source ON members (source)"),
    ("last_updated", "ALTER TABLE members ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE"),
    ("latest_term_start", "ALTER TABLE members ADD COLUMN IF NOT EXISTS latest_term_start VARCHAR(16)"),
    ("latest_term_end", "ALTER TABLE members ADD COLUMN IF NOT EXISTS latest_term_end VARCHAR(16)"),
    ("official_ids", "ALTER TABLE members ADD COLUMN IF NOT EXISTS official_ids JSONB DEFAULT '{}'"),

    # bioguide_id unique index
    ("bioguide_unique_idx", "CREATE UNIQUE INDEX IF NOT EXISTS idx_members_bioguide_unique ON members (bioguide_id)"),
]


def run_migrations() -> list[str]:
    applied = []
    with engine.connect() as conn:
        for name, sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
                applied.append(name)
                logger.info(f"Migration applied: {name}")
            except Exception as exc:
                conn.rollback()
                logger.warning(f"Migration skipped ({name}): {exc}")
    return applied


if __name__ == "__main__":
    applied = run_migrations()
    print(f"Migrations complete. Applied: {applied}")
