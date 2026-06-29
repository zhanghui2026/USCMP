"""Campaign finance API endpoints.

v0.92: FEC/OpenSecrets campaign contribution data.
Fact chain: Member -> CampaignCommittee -> Donor -> Contribution.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.postgres import get_db
from app.models.sqlalchemy.models import Member, CampaignCommittee, Donor, Contribution
from app.models.pydantic.models import (
    ContributionsResponse, ContributionSummary, ContributionRecord,
    CommitteeBrief, DonorModel,
)
from app.core.errors import NotFoundError
from app.api.routes.member_visibility import visible_member_filter

router = APIRouter(tags=["finance"])


@router.get("/members/{member_id}/contributions", response_model=ContributionsResponse)
def get_member_contributions(
    member_id: str,
    cycle: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    member = db.query(Member).filter(Member.id == member_id, visible_member_filter()).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": member_id})

    committees = db.query(CampaignCommittee).filter(
        CampaignCommittee.candidate_id == member_id,
    ).all()

    if not committees:
        return ContributionsResponse()

    committee_ids = [c.id for c in committees]

    query = db.query(Contribution).filter(
        Contribution.committee_id.in_(committee_ids),
    )
    if cycle:
        query = query.filter(Contribution.cycle == cycle)
    query = query.order_by(desc(Contribution.amount))
    contributions = query.limit(limit).all()

    records = []
    total_received = 0.0
    by_cycle: dict[str, float] = {}
    by_type: dict[str, float] = {}
    donor_agg: dict[str, dict] = {}
    industry_agg: dict[str, dict] = {}

    committee_map = {c.id: c for c in committees}

    for c in contributions:
        committee = committee_map.get(c.committee_id)
        if not committee:
            continue

        donor = db.query(Donor).filter(Donor.id == c.donor_id).first()
        if not donor:
            continue

        records.append(ContributionRecord(
            id=c.id,
            committee=CommitteeBrief(
                id=committee.id,
                fec_committee_id=committee.fec_committee_id,
                name=committee.name,
                party=committee.party,
                state=committee.state,
                chamber=committee.chamber,
                cycle=committee.cycle,
            ),
            donor=DonorModel(
                id=donor.id,
                name=donor.name,
                donor_type=donor.donor_type,
                industry=donor.industry,
                employer=donor.employer,
                city=donor.city,
                state=donor.state,
            ),
            amount=c.amount,
            contribution_date=c.contribution_date,
            cycle=c.cycle,
            contribution_type=c.contribution_type,
        ))

        total_received += c.amount

        cycle_key = str(c.cycle) if c.cycle else "unknown"
        by_cycle[cycle_key] = by_cycle.get(cycle_key, 0) + c.amount

        ctype = c.contribution_type or "individual"
        by_type[ctype] = by_type.get(ctype, 0) + c.amount

        did = donor.id
        if did not in donor_agg:
            donor_agg[did] = {"name": donor.name, "total": 0.0, "count": 0, "type": donor.donor_type}
        donor_agg[did]["total"] += c.amount
        donor_agg[did]["count"] += 1

        ind = donor.industry or "未知"
        if ind not in industry_agg:
            industry_agg[ind] = {"industry": ind, "total": 0.0, "count": 0}
        industry_agg[ind]["total"] += c.amount
        industry_agg[ind]["count"] += 1

    top_donors = sorted(donor_agg.values(), key=lambda x: x["total"], reverse=True)[:10]
    top_industries = sorted(industry_agg.values(), key=lambda x: x["total"], reverse=True)[:10]

    return ContributionsResponse(
        committees=[CommitteeBrief(
            id=cm.id,
            fec_committee_id=cm.fec_committee_id,
            name=cm.name,
            party=cm.party,
            state=cm.state,
            chamber=cm.chamber,
            cycle=cm.cycle,
        ) for cm in committees],
        contributions=records,
        summary=ContributionSummary(
            total_received=total_received,
            total_count=len(records),
            by_cycle=by_cycle,
            by_type=by_type,
            top_donors=top_donors,
            top_industries=top_industries,
        ),
        total_count=len(records),
    )
