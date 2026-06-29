"""Rebuild per-member finance summary from contributions.

v1.1 light-data architecture: pre-aggregate member-level finance
totals so member detail queries avoid scanning the full
contributions table.
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.postgres import Base
from app.models.sqlalchemy.models import (
    CampaignCommittee, Contribution, Member, MemberFinanceSummary,
)

logger = logging.getLogger(__name__)


def rebuild(session, member_id: str | None = None) -> int:
    query = session.query(Member)
    if member_id:
        query = query.filter(Member.id == member_id)
    members = query.all()

    updated = 0
    for member in members:
        committees = session.query(CampaignCommittee).filter(
            CampaignCommittee.candidate_id == member.id,
        ).all()
        if not committees:
            continue

        committee_ids = [c.id for c in committees]
        contributions = session.query(Contribution).filter(
            Contribution.committee_id.in_(committee_ids),
        ).all()

        total_received = 0.0
        by_cycle: dict[str, float] = defaultdict(float)
        by_type: dict[str, float] = defaultdict(float)
        by_cycle_count: dict[str, int] = defaultdict(int)
        by_industry_count: dict[str, int] = defaultdict(int)
        donor_agg: dict[str, dict] = {}
        industry_agg: dict[str, dict] = {}
        last_contribution_date: date | None = None

        for c in contributions:
            amount = c.amount or 0.0
            total_received += amount

            cycle_key = str(c.cycle) if c.cycle else "unknown"
            by_cycle[cycle_key] += amount
            by_cycle_count[cycle_key] += 1

            ctype = c.contribution_type or "individual"
            by_type[ctype] += amount

            if c.donor_id not in donor_agg:
                donor_agg[c.donor_id] = {
                    "id": c.donor_id,
                    "name": None,
                    "total": 0.0,
                    "count": 0,
                    "type": None,
                    "industry": None,
                }
            donor_agg[c.donor_id]["total"] += amount
            donor_agg[c.donor_id]["count"] += 1

            if c.contribution_date and (
                last_contribution_date is None or c.contribution_date > last_contribution_date
            ):
                last_contribution_date = c.contribution_date

        if donor_agg:
            donor_rows = session.execute(
                text("SELECT id, name, donor_type, industry FROM donors WHERE id IN :ids"),
                {"ids": tuple(donor_agg.keys())},
            ).fetchall()
            for row in donor_rows:
                donor_agg[row.id]["name"] = row.name
                donor_agg[row.id]["type"] = row.donor_type
                donor_agg[row.id]["industry"] = row.industry
                ind = row.industry or "未知"
                by_industry_count[ind] += donor_agg[row.id]["count"]

        top_donors = sorted(donor_agg.values(), key=lambda x: x["total"], reverse=True)[:10]
        top_industries = sorted(
            [
                {"industry": k, "count": v}
                for k, v in by_industry_count.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        summary = session.query(MemberFinanceSummary).filter(
            MemberFinanceSummary.member_id == member.id,
        ).first()

        if not summary:
            summary = MemberFinanceSummary(member_id=member.id)
            session.add(summary)

        summary.total_received = total_received
        summary.total_count = len(contributions)
        summary.by_cycle = dict(by_cycle)
        summary.by_type = dict(by_type)
        summary.top_donors = top_donors
        summary.top_industries = top_industries
        summary.by_cycle_count = dict(by_cycle_count)
        summary.by_industry_count = dict(by_industry_count)
        summary.last_contribution_date = last_contribution_date
        summary.updated_at = datetime.now(timezone.utc)
        summary.source = "fec"
        summary.source_reliability = "official"

        updated += 1

    return updated


def main():
    parser = argparse.ArgumentParser(description="Rebuild member finance summary.")
    parser.add_argument("--member-id", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = create_engine(settings.postgres_url_sync, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine, tables=[MemberFinanceSummary.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        updated = rebuild(session, member_id=args.member_id)
        if args.dry_run:
            logger.info("Dry run: would update %d members", updated)
            session.rollback()
        else:
            session.commit()
            logger.info("Updated finance summary for %d members", updated)
    except Exception:
        session.rollback()
        logger.exception("Failed to rebuild finance summary")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
