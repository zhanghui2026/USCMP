"""Data source coverage API."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.postgres import get_db
from app.models.pydantic.models import DataCoverageResponse, DataSourceCoverage
from app.models.sqlalchemy.models import (
    CampaignCommittee,
    Contribution,
    HoldingAsset,
    HoldingDisclosure,
    Member,
    MemberProfile,
)

router = APIRouter(tags=["data-coverage"])


@router.get("/data-coverage", response_model=DataCoverageResponse)
def get_data_coverage(db: Session = Depends(get_db)):
    current_members = db.query(func.count(Member.id)).filter(Member.is_current == True).scalar() or 0
    historical_members = db.query(func.count(Member.id)).filter(Member.member_scope == "historical").scalar() or 0
    profiles = db.query(func.count(MemberProfile.id)).scalar() or 0
    matched_profiles = db.query(func.count(func.distinct(MemberProfile.member_id))).scalar() or 0
    committees = db.query(func.count(CampaignCommittee.id)).scalar() or 0
    contributions = db.query(func.count(Contribution.id)).scalar() or 0
    contribution_members = (
        db.query(func.count(func.distinct(CampaignCommittee.candidate_id)))
        .join(Contribution, Contribution.committee_id == CampaignCommittee.id)
        .join(Member, Member.id == CampaignCommittee.candidate_id)
        .filter(Member.is_current == True)
        .scalar()
        or 0
    )
    holdings = db.query(func.count(HoldingAsset.id)).scalar() or 0
    holding_members = db.query(func.count(func.distinct(HoldingAsset.member_id))).scalar() or 0
    disclosures = db.query(func.count(HoldingDisclosure.id)).scalar() or 0

    return DataCoverageResponse(sources=[
        DataSourceCoverage(
            source_id="uscl",
            label="unitedstates/congress-legislators",
            status="full",
            records=current_members + historical_members,
            covered_members=current_members,
            note=f"现任 {current_members}，历史 {historical_members}；用于基础资料与委员会任职。",
        ),
        DataSourceCoverage(
            source_id="profiles_markdown",
            label="本地议员档案 Markdown",
            status="partial",
            records=profiles,
            covered_members=matched_profiles,
            note="本地 537 份档案中已导入并匹配的结构化档案。",
        ),
        DataSourceCoverage(
            source_id="fec",
            label="FEC bulk-downloads",
            status="sample" if contributions <= 5000 else "partial",
            records=contributions,
            covered_members=contribution_members,
            note=f"竞选委员会 {committees}；当前献金记录量为 {contributions}，仅限现任议员关联委员会。",
        ),
        DataSourceCoverage(
            source_id="holdings",
            label="Congressional Financial Disclosures",
            status="subset" if disclosures == 0 else "partial",
            records=holdings,
            covered_members=holding_members,
            note=f"当前持股资产 {holdings}，披露文件 {disclosures}；现阶段来自 top_holdings 结构化子集。",
        ),
    ])
