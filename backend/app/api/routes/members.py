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
    CircleExpandResponse,
)
from app.core.errors import NotFoundError
from app.api.routes.member_visibility import filter_visible_members, visible_member_filter

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


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) else None

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
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = filter_visible_members(db.query(Member))

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
                committee = cm.get("committee", "")
                # Filter out uscl_committee_* format, keep only full names
                if committee and not committee.startswith("uscl_"):
                    committee_tags.append(committee)

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
            committee_tags=committee_tags,
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
    member = db.query(Member).filter(Member.id == member_id, visible_member_filter()).first()
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
        core_positions=_optional_text(member.core_positions),
        comprehensive_evaluation=_optional_text(member.comprehensive_evaluation),
        controversies=member.controversies or [],
        congress=member.congress,
        source=member.source,
        latest_term_start=member.latest_term_start,
        latest_term_end=member.latest_term_end,
        official_ids=member.official_ids or {},
    )


@router.get("/members/{member_id}/profile", response_model=MemberProfileResponse)
def get_member_profile(member_id: str, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id, visible_member_filter()).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": member_id})

    profile = db.query(MemberProfile).filter(
        MemberProfile.member_id == member_id,
    ).first()

    if not profile:
        return MemberProfileResponse(
            member_id=member_id,
            bioguide_id=member.bioguide_id,
            profile_status="no_data",
        )

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


CATEGORY_MAP: dict[str, tuple[str, str, str, str, str | None]] = {
    "EducationInstitution": ("education", "共同教育背景", "EDUCATED_AT", "Wikipedia infobox", "medium"),
    "Committee": ("committee", "共同委员会", "ASSIGNED_TO", "UnitedStates/Congress-Legislators", "medium"),
    "State": ("state", "相同代表州", "REPRESENTS_STATE", "UnitedStates/Congress-Legislators", "weak"),
    "Party": ("party", "相同党派", "MEMBER_OF_PARTY", "UnitedStates/Congress-Legislators", "weak"),
    "Position": ("occupation", "共同职业经历", "HELD_POSITION", "Wikipedia infobox", "strong"),
    "Employer": ("employer", "共同任职机构", "EMPLOYED_BY", "Wikipedia infobox", "strong"),
}


def _get_strength_level(entity_type: str) -> str:
    info = CATEGORY_MAP.get(entity_type)
    return info[4] if info else "weak"


def _get_source_name(entity_type: str) -> str:
    info = CATEGORY_MAP.get(entity_type)
    return info[3] if info else "unknown"


def _get_circle_name(entity_type: str) -> str:
    info = CATEGORY_MAP.get(entity_type)
    return info[1] if info else entity_type


def _get_evidence_type(entity_type: str) -> str:
    info = CATEGORY_MAP.get(entity_type)
    return info[2] if info else "UNKNOWN"


@router.get("/members/{member_id}/circles", response_model=CircleResponse)
def get_member_circles(member_id: str):
    cypher = """
    MATCH (m1:Person {id: $mid})-[r1]-(entity)-[r2]-(m2:Person)
    WHERE m1.id <> m2.id
    RETURN DISTINCT labels(entity)[0] AS entity_type,
           entity.display_name AS shared_via,
           count(DISTINCT m2.id) AS cnt
    ORDER BY cnt DESC
    LIMIT 500
    """
    results = run_cypher(cypher, {"mid": member_id})
    if not results:
        return CircleResponse()

    aggregated: dict[str, int] = {}
    for row in results:
        et = row.get("entity_type", "")
        cnt = row.get("cnt", 0) or 0
        if et not in CATEGORY_MAP:
            continue
        aggregated[et] = aggregated.get(et, 0) + cnt

    categories = []
    for entity_type, (cat_key, cat_name, ev_type, src, _strength) in CATEGORY_MAP.items():
        total = aggregated.get(entity_type, 0)
        if total == 0:
            continue
        categories.append(CircleCategory(
            circle_type=cat_key,
            circle_name=cat_name,
            evidence_type=ev_type,
            source=src,
            source_url=None,
            related_count=total,
            strength_level=_strength,
        ))

    return CircleResponse(categories=categories)


@router.get("/members/{member_id}/circles/{circle_type}", response_model=CircleExpandResponse)
def get_circle_members(member_id: str, circle_type: str):
    entity_type_map = {v[0]: k for k, v in CATEGORY_MAP.items()}
    et = entity_type_map.get(circle_type)
    if not et:
        return CircleExpandResponse(circle_type=circle_type, circle_name=circle_type)

    cypher = """
    MATCH (m1:Person {id: $mid})-[r1]-(entity)-[r2]-(m2:Person)
    WHERE m1.id <> m2.id AND labels(entity)[0] = $et
    RETURN DISTINCT m2.id AS member_id,
           m2.display_name AS display_name,
           m2.party AS party,
           m2.state AS state,
           entity.display_name AS shared_via
    ORDER BY m2.display_name
    LIMIT 200
    """
    results = run_cypher(cypher, {"mid": member_id, "et": et})
    members = []
    if results:
        for row in results:
            members.append(CircleMember(
                member_id=row["member_id"],
                display_name=row["display_name"],
                party=row.get("party"),
                state=row.get("state"),
                shared_via=row.get("shared_via", ""),
            ))

    return CircleExpandResponse(
        circle_type=circle_type,
        circle_name=_get_circle_name(et),
        members=members,
    )
