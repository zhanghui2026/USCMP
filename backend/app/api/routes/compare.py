"""Compare API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.models.sqlalchemy.models import Member
from app.models.pydantic.models import (
    CompareRequest, CompareResponse, MemberDetail, CommitteeMembership,
)
from app.core.errors import CompareTooFewMembersError, NotFoundError
from app.services.compare_service import compute_radar_metrics
from app.api.routes.member_visibility import visible_member_filter

router = APIRouter(tags=["compare"])


@router.post("/compare", response_model=CompareResponse)
def compare_members(request: CompareRequest, db: Session = Depends(get_db)):
    if len(request.member_ids) < 2:
        raise CompareTooFewMembersError(
            "At least 2 members required for comparison",
            {"member_count": len(request.member_ids), "min_required": 2},
        )

    members = db.query(Member).filter(Member.id.in_(request.member_ids), visible_member_filter()).all()
    if len(members) < len(request.member_ids):
        found_ids = {m.id for m in members}
        missing = [mid for mid in request.member_ids if mid not in found_ids]
        raise NotFoundError("Some members not found", {"missing_ids": missing})

    member_details = []
    for m in members:
        committee_memberships = []
        if m.committee_memberships:
            for cm in m.committee_memberships:
                committee_memberships.append(CommitteeMembership(
                    committee=cm.get("committee", ""),
                    role=cm.get("role", "Member"),
                    congress=cm.get("congress", m.congress),
                    committee_type=cm.get("committee_type", "committee"),
                ))

        member_details.append(MemberDetail(
            id=m.id,
            canonical_name=m.canonical_name,
            display_name=m.display_name,
            aliases=m.aliases or [],
            person_type=m.person_type,
            party=m.party,
            chamber=m.chamber,
            state=m.state,
            district=m.district,
            official_photo_url=m.official_photo_url,
            bioguide_id=m.bioguide_id,
            govtrack_id=m.govtrack_id,
            fec_candidate_id=m.fec_candidate_id,
            opensecrets_id=m.opensecrets_id,
            top_contributors=m.top_contributors or [],
            top_holdings=m.top_holdings or [],
            committee_memberships=committee_memberships,
            career_summary=m.career_summary or [],
            china_stance_summary=m.china_stance_summary,
            controversies=m.controversies or [],
            congress=m.congress,
        ))

    # Compute radar metrics for all members
    radar_metrics = []
    for m in members:
        radar_metrics.extend(compute_radar_metrics(m))

    # Find common donors (mock)
    common_donors = []
    donor_sets = []
    for m in members:
        donors = set()
        for tc in (m.top_contributors or []):
            oid = tc.get("organization_id", tc.get("organization", ""))
            if oid:
                donors.add(oid)
        donor_sets.append(donors)

    if len(donor_sets) >= 2:
        common = donor_sets[0]
        for ds in donor_sets[1:]:
            common = common & ds
        for donor_id in list(common)[:5]:
            common_donors.append({"organization_id": donor_id, "shared_by": len(members)})

    # Find common committees (mock)
    common_committees = []
    for m in members:
        for cm in (m.committee_memberships or []):
            committee_name = cm.get("committee", "")
            if committee_name:
                found = next((c for c in common_committees if c["committee"] == committee_name), None)
                if found:
                    found["member_count"] += 1
                else:
                    common_committees.append({"committee": committee_name, "member_count": 1})

    common_committees = [c for c in common_committees if c["member_count"] >= 2]

    return CompareResponse(
        members=member_details,
        radar_metrics=radar_metrics,
        common_donors=common_donors,
        common_committees=common_committees,
        opposing_votes=[],
        disclaimer="仅供研究参考，不构成事实认定、法律判断或投资建议。所有指标评分基于 Mock 演示数据，不代表真实分析结果。",
    )
