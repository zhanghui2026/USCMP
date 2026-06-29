"""Member finance summary API.

v1.1: Pre-aggregated per-member finance summary to avoid scanning
the large contributions table on every member detail load.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.models.sqlalchemy.models import Member, MemberFinanceSummary
from app.models.pydantic.models import MemberFinanceSummaryResponse
from app.core.errors import NotFoundError
from app.api.routes.member_visibility import visible_member_filter

router = APIRouter(tags=["finance"])


@router.get("/members/{member_id}/finance/summary", response_model=MemberFinanceSummaryResponse)
def get_member_finance_summary(
    member_id: str,
    db: Session = Depends(get_db),
):
    member = db.query(Member).filter(Member.id == member_id, visible_member_filter()).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": member_id})

    summary = db.query(MemberFinanceSummary).filter(
        MemberFinanceSummary.member_id == member_id,
    ).first()

    if not summary:
        return MemberFinanceSummaryResponse(member_id=member_id)

    return MemberFinanceSummaryResponse(
        member_id=summary.member_id,
        total_received=summary.total_received,
        total_count=summary.total_count,
        by_cycle=summary.by_cycle or {},
        by_type=summary.by_type or {},
        top_donors=summary.top_donors or [],
        top_industries=summary.top_industries or [],
        by_cycle_count=summary.by_cycle_count or {},
        by_industry_count=summary.by_industry_count or {},
        data_mode=summary.data_mode,
        source=summary.source,
        source_reliability=summary.source_reliability,
        last_contribution_date=summary.last_contribution_date,
        updated_at=summary.updated_at,
    )
