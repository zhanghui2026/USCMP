"""Members API endpoints."""

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.db.neo4j import run_cypher
from app.models.sqlalchemy.models import Member
from app.models.pydantic.models import (
    MemberSummary, MemberDetail, MemberListResponse, CommitteeMembership,
)
from app.core.errors import NotFoundError

router = APIRouter(tags=["members"])


@router.get("/members", response_model=MemberListResponse)
def list_members(
    chamber: str | None = Query(None),
    party: str | None = Query(None),
    state: str | None = Query(None),
    committee: str | None = Query(None),
    congress: int | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Member)

    if chamber:
        query = query.filter(Member.chamber == chamber)
    if party:
        query = query.filter(Member.party == party)
    if state:
        query = query.filter(Member.state == state)
    if congress:
        query = query.filter(Member.congress == congress)
    if search:
        query = query.filter(Member.canonical_name.ilike(f"%{search}%"))
    if committee:
        query = query.filter(Member.committee_memberships.cast(str).ilike(f"%{committee}%"))

    total = query.count()
    members = query.offset(skip).limit(limit).all()

    summaries = []
    for m in members:
        committee_tags = []
        if m.committee_memberships:
            for cm in m.committee_memberships:
                if cm.get("committee"):
                    committee_tags.append(cm["committee"])

        summaries.append(MemberSummary(
            id=m.id,
            canonical_name=m.canonical_name,
            display_name=m.display_name,
            party=m.party,
            chamber=m.chamber,
            state=m.state,
            district=m.district,
            official_photo_url=m.official_photo_url,
            committee_tags=committee_tags[:5],
            congress=m.congress,
            source=m.source,
        ))

    return MemberListResponse(
        members=summaries,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/members/{member_id}", response_model=MemberDetail)
def get_member(member_id: str, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": member_id})

    committee_memberships = []
    if member.committee_memberships:
        for cm in member.committee_memberships:
            committee_memberships.append(CommitteeMembership(
                committee=cm.get("committee", ""),
                role=cm.get("role", "Member"),
                congress=cm.get("congress", member.congress),
                committee_type=cm.get("committee_type", "committee"),
            ))

    return MemberDetail(
        id=member.id,
        canonical_name=member.canonical_name,
        display_name=member.display_name,
        aliases=member.aliases or [],
        person_type=member.person_type,
        party=member.party,
        chamber=member.chamber,
        state=member.state,
        district=member.district,
        official_photo_url=member.official_photo_url,
        bioguide_id=member.bioguide_id,
        govtrack_id=member.govtrack_id,
        fec_candidate_id=member.fec_candidate_id,
        opensecrets_id=member.opensecrets_id,
        top_contributors=member.top_contributors or [],
        top_holdings=member.top_holdings or [],
        committee_memberships=committee_memberships,
        career_summary=member.career_summary or [],
        china_stance_summary=member.china_stance_summary,
        controversies=member.controversies or [],
        congress=member.congress,
        source=member.source,
        latest_term_start=member.latest_term_start,
        latest_term_end=member.latest_term_end,
        official_ids=member.official_ids or {},
    )
