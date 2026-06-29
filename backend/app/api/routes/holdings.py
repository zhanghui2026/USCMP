"""Holdings disclosure API endpoints.

v0.94: Structured holdings data from Congressional Financial Disclosures.
Fact chain: Member -> HoldingAsset (asset_name, value_range, filing_year).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.postgres import get_db
from app.models.sqlalchemy.models import Member, HoldingAsset, HoldingDisclosure
from app.models.pydantic.models import (
    HoldingsResponse, HoldingsSummary, HoldingAssetRecord, HoldingDisclosureRecord,
)
from app.core.errors import NotFoundError
from app.api.routes.member_visibility import visible_member_filter

router = APIRouter(tags=["holdings"])


@router.get("/members/{member_id}/holdings", response_model=HoldingsResponse)
def get_member_holdings(
    member_id: str,
    asset_type: str | None = Query(None),
    year: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    member = db.query(Member).filter(Member.id == member_id, visible_member_filter()).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": member_id})

    query = db.query(HoldingAsset).filter(HoldingAsset.member_id == member_id)
    if asset_type:
        query = query.filter(HoldingAsset.asset_type == asset_type)
    if year:
        query = query.filter(HoldingAsset.filing_year == year)
    query = query.order_by(desc(HoldingAsset.value_max), desc(HoldingAsset.value_min))
    holdings = query.limit(limit).all()

    records = []
    by_asset_type: dict[str, int] = {}
    by_year: dict[str, int] = {}
    top_assets: list[dict] = []

    for h in holdings:
        records.append(HoldingAssetRecord(
            id=h.id,
            asset_name=h.asset_name,
            asset_type=h.asset_type,
            ticker=h.ticker,
            value_min=h.value_min,
            value_max=h.value_max,
            value_range_label=h.value_range_label,
            filing_year=h.filing_year,
            disclosure_date=h.disclosure_date,
            source=h.source,
            source_url=h.source_url,
            source_reliability=h.source_reliability,
        ))

        atype = h.asset_type or "other"
        by_asset_type[atype] = by_asset_type.get(atype, 0) + 1

        year_key = str(h.filing_year) if h.filing_year else "unknown"
        by_year[year_key] = by_year.get(year_key, 0) + 1

        if len(top_assets) < 10:
            top_assets.append({
                "asset_name": h.asset_name,
                "asset_type": h.asset_type,
                "ticker": h.ticker,
                "value_range": h.value_range_label or f"${h.value_min or 0:,.0f} - ${h.value_max or 0:,.0f}",
                "filing_year": h.filing_year,
            })

    disclosures_query = db.query(HoldingDisclosure).filter(HoldingDisclosure.member_id == member_id)
    if year:
        disclosures_query = disclosures_query.filter(HoldingDisclosure.filing_year == year)
    disclosures = disclosures_query.order_by(desc(HoldingDisclosure.filing_year)).all()

    disclosure_records = []
    for d in disclosures:
        disclosure_records.append(HoldingDisclosureRecord(
            id=d.id,
            filing_year=d.filing_year,
            filing_type=d.filing_type,
            filing_url=d.filing_url,
            filing_date=d.filing_date,
            asset_count=d.asset_count,
            source=d.source,
            source_reliability=d.source_reliability,
        ))

    return HoldingsResponse(
        holdings=records,
        disclosures=disclosure_records,
        summary=HoldingsSummary(
            total_assets=len(records),
            by_asset_type=by_asset_type,
            by_year=by_year,
            top_assets=top_assets,
        ),
        total_count=len(records),
    )
