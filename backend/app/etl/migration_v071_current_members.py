"""
v0.7.1 migration: Add is_current and member_scope columns to members table.

member_scope values: current | historical | mock | test
is_current: True iff member_scope == 'current'

Backfill logic:
  - source='uscl' + latest_term_end >= 2026 -> current
  - source='uscl' + latest_term_end < 2026 -> historical
  - source='mock' -> mock
  - otherwise -> historical (conservative default)
"""

from sqlalchemy import text
from app.db.postgres import engine
from app.core.logging import logger


def migrate():
    with engine.connect() as conn:
        # Add columns if they don't exist
        logger.info("Adding is_current column...")
        conn.execute(text("""
            ALTER TABLE members ADD COLUMN IF NOT EXISTS
            is_current BOOLEAN DEFAULT FALSE
        """))
        conn.execute(text("""
            ALTER TABLE members ADD COLUMN IF NOT EXISTS
            member_scope VARCHAR(16) DEFAULT 'current'
        """))
        conn.commit()

        # Create index
        logger.info("Creating index on is_current...")
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_members_is_current ON members (is_current)"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        logger.info("Creating index on member_scope...")
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_members_scope ON members (member_scope)"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # Backfill: mock source -> mock
        logger.info("Backfilling mock members...")
        conn.execute(text("""
            UPDATE members
            SET member_scope = 'mock', is_current = FALSE
            WHERE source = 'mock'
        """))
        conn.commit()

        # Backfill: uscl current (latest_term_end >= 2026-01-01)
        logger.info("Backfilling current USCL members...")
        conn.execute(text("""
            UPDATE members
            SET member_scope = 'current', is_current = TRUE
            WHERE source = 'uscl' AND latest_term_end >= '2026-01-01'
        """))
        conn.commit()

        # Backfill: uscl historical (latest_term_end < 2026-01-01)
        logger.info("Backfilling historical USCL members...")
        conn.execute(text("""
            UPDATE members
            SET member_scope = 'historical', is_current = FALSE
            WHERE source = 'uscl' AND latest_term_end < '2026-01-01'
        """))
        conn.commit()

        # Backfill: uscl with NULL term_end -> use congress to infer
        logger.info("Backfilling NULL term_end members...")
        conn.execute(text("""
            UPDATE members
            SET member_scope = 'historical', is_current = FALSE
            WHERE source = 'uscl'
            AND latest_term_end IS NULL
        """))
        conn.commit()

        # Report counts
        result = conn.execute(text(
            "SELECT member_scope, COUNT(*) FROM members GROUP BY member_scope ORDER BY member_scope"
        ))
        for row in result.fetchall():
            logger.info(f"  {row[0]}: {row[1]}")


def rollback():
    with engine.connect() as conn:
        try:
            conn.execute(text("DROP INDEX IF EXISTS idx_members_scope"))
            conn.execute(text("DROP INDEX IF EXISTS idx_members_is_current"))
        except Exception:
            conn.rollback()
        conn.execute(text("ALTER TABLE members DROP COLUMN IF EXISTS member_scope"))
        conn.execute(text("ALTER TABLE members DROP COLUMN IF EXISTS is_current"))
        conn.commit()
        logger.info("Rollback complete")


if __name__ == "__main__":
    migrate()
