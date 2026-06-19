"""Members API endpoints."""

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.db.neo4j import run_cypher
from app.models.sqlalchemy.models import Member, MemberProfile
from app.models.pydantic.models import (
    MemberSummary, MemberDetail, MemberListResponse, CommitteeMembership,
    MemberProfileResponse, CircleResponse, CircleCategory, CircleMember,
)
from app.core.errors import NotFoundError

from typing import Any



def _normalize_career_highlights(raw: list | None) -> list[dict]:
    if not raw:
        return []
    results: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            results.append(item)
        elif isinstance(item, str):
            results.append({"title": item})
    return results

router = APIRouter(tags=["members"])


@router.get("/members", response_model=MemberListResponse)
def list_members(
    chamber: str | None = Query(None),
    party: str | None = Query(None),
    state: str | None = Query(None),
    committee: str | None = Query(None),
    congress: int | None = Query(None),
    search: str | None = Query(None),
    include_historical: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Member)

    if not include_historical:
        query = query.filter(Member.is_current == True)

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

    profile_map: dict[str, str | None] = {}
    member_ids = [m.id for m in members]
    if member_ids:
        try:
            profiles = db.query(MemberProfile.member_id, MemberProfile.image_url).filter(
                MemberProfile.member_id.in_(member_ids),
                MemberProfile.image_url.isnot(None),
            ).all()
            profile_map = {p.member_id: p.image_url for p in profiles if hasattr(p, 'member_id')}
        except Exception:
            profile_map = {}

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
            image_url=profile_map.get(m.id),
            committee_tags=committee_tags[:5],
            congress=m.congress,
            source=m.source,
            member_scope=m.member_scope or "current",
        ))

    return MemberListResponse(
        members=summaries,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/members/{member_id}", response_model=MemberDetail)
def get_member(member_id: str, include_historical: bool = Query(False), db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": member_id})

    if not include_historical and not member.is_current:
        raise NotFoundError("Member not found in current scope", {
            "member_id": member_id,
            "member_scope": member.member_scope or "unknown",
        })

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


@router.get("/members/{member_id}/profile", response_model=MemberProfileResponse)
def get_member_profile(member_id: str, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": member_id})

    profile = db.query(MemberProfile).filter(
        MemberProfile.member_id == member_id,
    ).first()

    if not profile:
        raise NotFoundError("Profile not found for member", {"member_id": member_id})

    return MemberProfileResponse(
        member_id=profile.member_id,
        bioguide_id=profile.bioguide_id,
        wikipedia_title=profile.wikipedia_title,
        wikipedia_url=profile.wikipedia_url,
        wikidata_qid=profile.wikidata_qid,
        image_url=profile.image_url,
        short_summary=profile.short_summary,
        birth_date=profile.birth_date,
        birth_place=profile.birth_place,
        education=profile.education or [],
        occupations=profile.occupations or [],
        career_highlights=_normalize_career_highlights(profile.career_highlights),
        prior_positions=profile.prior_positions or [],
        military_service=profile.military_service or [],
        employers=profile.employers or [],
        profile_status=profile.profile_status or "summary_only",
        parsed_fields=profile.parsed_fields or [],
        missing_fields=profile.missing_fields or [],
        source=profile.source or "wikipedia",
        source_reliability=profile.source_reliability or "external_open_content",
        last_updated=profile.last_updated.isoformat() if profile.last_updated else None,
        profile_sources=profile.profile_sources or {},
    )


CATEGORY_MAP = {
    "EducationInstitution": ("education", "教育圈层", "EDUCATED_AT"),
    "Committee": ("committee", "委员会圈层", "ASSIGNED_TO"),
    "State": ("state", "州圈层", "REPRESENTS_STATE"),
    "Party": ("party", "党派圈层", "MEMBER_OF_PARTY"),
    "Position": ("occupation", "职业圈层", "HELD_POSITION"),
    "Employer": ("employer", "任职机构圈层", "EMPLOYED_BY"),
}


@router.get("/members/{member_id}/circles", response_model=CircleResponse)
def get_member_circles(member_id: str):
    cypher = """
    MATCH (m1:Person {id: $mid})-[r1]-(entity)-[r2]-(m2:Person)
    WHERE m1.id <> m2.id
    RETURN DISTINCT m2.id AS member_id,
           m2.display_name AS display_name,
           m2.party AS party,
           m2.state AS state,
           labels(entity)[0] AS entity_type,
           entity.display_name AS shared_via,
           type(r1) AS rel_type
    LIMIT 500
    """
    results = run_cypher(cypher, {"mid": member_id})
    if not results:
        return CircleResponse()

    by_type: dict[str, list[dict]] = {}
    for row in results:
        et = row.get("entity_type", "")
        if et not in CATEGORY_MAP:
            continue
        cat_key, _, _ = CATEGORY_MAP[et]
        entry = {
            "member_id": row["member_id"],
            "display_name": row["display_name"],
            "party": row.get("party"),
            "state": row.get("state"),
            "shared_via": row.get("shared_via", ""),
        }
        by_type.setdefault(cat_key, []).append(entry)

    categories = []
    for cat_key, cat_label, _ in CATEGORY_MAP.values():
        members_data = by_type.get(cat_key, [])
        if members_data:
            categories.append(CircleCategory(
                category=cat_key,
                label=cat_label,
                members=[CircleMember(**m) for m in members_data],
            ))

    return CircleResponse(categories=categories)
