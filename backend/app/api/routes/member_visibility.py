"""Shared member visibility filters for public API routes."""

from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Query

from app.models.sqlalchemy.models import Member


def visible_member_filter():
    return and_(
        Member.source != "mock",
        or_(Member.member_scope.is_(None), not_(Member.member_scope.in_(["mock", "test"]))),
        not_(Member.id.ilike("test_%")),
    )


def filter_visible_members(query: Query) -> Query:
    return query.filter(visible_member_filter())
