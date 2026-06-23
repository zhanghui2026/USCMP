"""Search API endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.postgres import get_db
from app.models.sqlalchemy.models import Member, Organization, Event as EventModelDB
from app.models.pydantic.models import (
    SearchResult, MemberSummary, OrganizationSummary, EventModel,
)
from app.core.errors import SearchQueryTooShortError
from app.api.routes.member_visibility import filter_visible_members

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResult)
def search(
    query: str = Query(..., min_length=2),
    limit: int = Query(50, ge=1, le=100),
    include_historical: bool = Query(False),
    db: Session = Depends(get_db),
):
    if len(query.strip()) < 2:
        raise SearchQueryTooShortError(
            "Search query must be at least 2 characters",
            {"query": query, "min_length": 2},
        )

    pattern = f"%{query}%"

    # Search members
    member_q = filter_visible_members(db.query(Member)).filter(
        or_(
            Member.canonical_name.ilike(pattern),
            Member.display_name.ilike(pattern),
            Member.state.ilike(pattern),
        )
    )
    if not include_historical:
        member_q = member_q.filter(Member.is_current == True)
    members = member_q.limit(limit).all()

    member_results = []
    for m in members:
        committee_tags = []
        if m.committee_memberships:
            for cm in m.committee_memberships:
                if cm.get("committee"):
                    committee_tags.append(cm["committee"])

        member_results.append(MemberSummary(
            id=m.id,
            canonical_name=m.canonical_name,
            display_name=m.display_name,
            party=m.party,
            chamber=m.chamber,
            state=m.state,
            district=m.district,
            official_photo_url=m.official_photo_url,
            committee_tags=committee_tags,
            congress=m.congress,
            source=m.source,
            member_scope=m.member_scope or "current",
        ))

    # Search organizations
    orgs = db.query(Organization).filter(
        or_(
            Organization.canonical_name.ilike(pattern),
            Organization.industry.ilike(pattern),
        )
    ).limit(limit).all()

    org_results = [
        OrganizationSummary(
            id=o.id,
            canonical_name=o.canonical_name,
            display_name=o.display_name,
            entity_type=o.entity_type,
            industry=o.industry,
            ticker=o.ticker,
            country=o.country,
        )
        for o in orgs
    ]

    # Search events
    events = db.query(EventModelDB).filter(
        EventModelDB.title.ilike(pattern)
    ).limit(limit).all()

    event_results = [
        EventModel(
            id=e.id,
            event_type=e.event_type,
            title=e.title,
            description=e.description,
            event_date=e.event_date,
            congress=e.congress,
            source_reliability=e.source_reliability,
        )
        for e in events
    ]

    total = len(member_results) + len(org_results) + len(event_results)

    return SearchResult(
        members=member_results,
        organizations=org_results,
        events=event_results,
        total_count=total,
        source="postgresql",
    )
