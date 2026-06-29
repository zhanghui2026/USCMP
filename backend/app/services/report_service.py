"""Markdown report generation service.

Phase 1: Template-based formatting from mock member data.
v0.92: Campaign finance data from FEC tables.
"""

from datetime import datetime, timezone

from app.models.sqlalchemy.models import Member, CampaignCommittee, Donor, Contribution, MemberProfile, HoldingAsset


def build_markdown(member: Member, include_graph: bool, include_predictions: bool) -> str:
    lines = []

    lines.append(f"# 议员简报: {member.canonical_name}")
    lines.append("")
    lines.append(f"**生成时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")

    # Basic info
    lines.append("## 基本信息")
    lines.append("")
    lines.append(f"- **姓名**: {member.canonical_name}")
    lines.append(f"- **显示名称**: {member.display_name}")
    lines.append(f"- **党派**: {member.party or '未知'}")
    lines.append(f"- **议院**: {'参议院' if member.chamber == 'senate' else '众议院' if member.chamber == 'house' else member.chamber or '未知'}")
    if member.state:
        lines.append(f"- **州**: {member.state}")
    if member.district:
        lines.append(f"- **选区**: {member.district}")
    lines.append(f"- **届次**: 第{member.congress or '未知'}届")
    if member.latest_term_start:
        lines.append(f"- **本届任期开始**: {member.latest_term_start}")
    if member.latest_term_end:
        lines.append(f"- **本届任期结束**: {member.latest_term_end}")
    lines.append(f"- **数据来源**: {member.source}")
    if member.last_updated:
        lu = member.last_updated
        if hasattr(lu, 'strftime'):
            lines.append(f"- **最后更新**: {lu.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            lines.append(f"- **最后更新**: {lu}")
    else:
        lines.append(f"- **最后更新**: 未知")
    lines.append("")

    # Committee memberships
    if member.committee_memberships:
        lines.append("## 委员会任职")
        lines.append("")
        for cm in member.committee_memberships:
            role = cm.get("role", "Member")
            committee = cm.get("committee", "未知委员会")
            congress = cm.get("congress", "")
            lines.append(f"- **{committee}** ({role}, 第{congress}届)")
        lines.append("")

    # Career summary
    if member.career_summary:
        lines.append("## 履历摘要")
        lines.append("")
        for entry in member.career_summary[:5]:
            pos = entry.get("position", "")
            org = entry.get("organization", "")
            lines.append(f"- {pos} @ {org}")
        lines.append("")

    # Wikipedia Profile
    profile = None
    try:
        from app.models.sqlalchemy.models import MemberProfile
        from app.db.postgres import SessionLocal
        local_db = SessionLocal()
        try:
            profile = local_db.query(MemberProfile).filter(
                MemberProfile.member_id == member.id,
            ).first()
        finally:
            local_db.close()
    except Exception:
        pass

    if profile:
        source_label = "Wikipedia 履历" if profile.source == "wikipedia" else "USCL 基础资料"
        source_name = "Wikipedia" if profile.source == "wikipedia" else "US Congress Legislators Dataset"
        lines.append(f"## 履历信息 ({source_label})")
        lines.append("")
        lines.append(f"- **数据来源**: {source_name}")
        if profile.source == "wikipedia":
            lines.append(f"- **Wikipedia 标题**: {profile.wikipedia_title or '--'}")
            if profile.wikipedia_url:
                lines.append(f"- **Wikipedia 链接**: {profile.wikipedia_url}")
        else:
            if profile.wikipedia_title:
                lines.append(f"- **Wikipedia 标题**: {profile.wikipedia_title}")
            if profile.wikidata_qid:
                lines.append(f"- **Wikidata ID**: {profile.wikidata_qid}")
            if profile.wikipedia_url:
                lines.append(f"- **Wikipedia 链接**: {profile.wikipedia_url}")
            lines.append(f"- **数据范围**: 仅包含出生日期和基本信息；职业/教育/职位等结构化字段待接入 Wikipedia 后补充")
        if profile.birth_date:
            lines.append(f"- **出生日期**: {profile.birth_date}")
        if profile.birth_place:
            lines.append(f"- **出生地**: {profile.birth_place}")
        if profile.short_summary:
            lines.append(f"- **摘要**: {profile.short_summary[:300]}{'...' if len(profile.short_summary or '') > 300 else ''}")
        if profile.occupations:
            lines.append(f"- **职业**: {', '.join(profile.occupations[:5])}")
        if profile.education:
            lines.append("")
            lines.append("### 教育经历")
            lines.append("")
            for edu in profile.education[:5]:
                inst = edu.get("institution", "未知")
                lines.append(f"- {inst}")
        if profile.prior_positions:
            lines.append("")
            lines.append("### 过往职位")
            lines.append("")
            for pos in profile.prior_positions[:5]:
                p = pos.get("position", "未知")
                lines.append(f"- {p}")
        if profile.military_service:
            lines.append("")
            lines.append("### 军事经历")
            lines.append("")
            for ms in profile.military_service[:3]:
                lines.append(f"- {ms.get('detail', '')}")
        if profile.last_updated:
            lu = profile.last_updated
            if hasattr(lu, 'strftime'):
                lines.append(f"- **最后更新**: {lu.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            else:
                lines.append(f"- **最后更新**: {lu}")
        lines.append("")
    else:
        lines.append("## 履历信息")
        lines.append("")
        lines.append("暂未接入。需接入 USCL 数据源与 Wikipedia 数据源。")
        lines.append("")

    # Profile facts in graph (v0.7)
    lines.append("## 履历事实节点 (知识图谱)")
    lines.append("")
    try:
        from app.db.neo4j import run_cypher
        facts_query = """
            MATCH (p:Person {id: $member_id})-[r]-(n)
            WHERE type(r) IN ['EDUCATED_AT', 'HELD_POSITION', 'EMPLOYED_BY', 'HAS_PROFILE_SOURCE']
            RETURN n, type(r) AS rel_type, r.source AS source
            ORDER BY rel_type, n.name
        """
        facts = run_cypher(facts_query, {"member_id": member.id})
        if facts:
            by_type: dict[str, list] = {}
            for record in facts:
                rt = record["rel_type"]
                node = record["n"]
                name = node.get("name", node.get("id", ""))
                src = record.get("source", "")
                if rt not in by_type:
                    by_type[rt] = []
                by_type[rt].append((name, src))

            type_labels = {
                "EDUCATED_AT": "教育经历",
                "HELD_POSITION": "任职履历",
                "EMPLOYED_BY": "雇主/机构",
                "HAS_PROFILE_SOURCE": "资料来源",
            }
            for rt, label in type_labels.items():
                items = by_type.get(rt, [])
                if items:
                    lines.append(f"### {label}")
                    lines.append("")
                    for name, src in items:
                        lines.append(f"- {name} (来源: {src})")
                    lines.append("")
            lines.append("> 以上节点已入知识图谱，可在议员详情页图谱中查看。")
        else:
            lines.append("暂无履历事实节点。完整的履历事实需导入 Wikipedia 履历数据。")
    except Exception:
        lines.append("知识图谱查询暂时不可用。")
    lines.append("")

    # Top contributors from campaign finance tables (v0.92)
    try:
        from app.db.postgres import SessionLocal
        local_db = SessionLocal()
        try:
            committees = local_db.query(CampaignCommittee).filter(
                CampaignCommittee.candidate_id == member.id,
            ).all()

            if committees:
                cids = [c.id for c in committees]
                contribs = local_db.query(Contribution).filter(
                    Contribution.committee_id.in_(cids),
                ).order_by(Contribution.amount.desc()).limit(10).all()

                if contribs:
                    lines.append("## 政治献金来源 (FEC)")
                    lines.append("")
                    lines.append("| 捐赠方 | 金额 | 周期 | 类型 |")
                    lines.append("|--------|------|------|------|")
                    for c in contribs:
                        donor = local_db.query(Donor).filter(Donor.id == c.donor_id).first()
                        dname = donor.name if donor else "未知"
                        lines.append(f"| {dname} | ${c.amount:,.0f} | 第{c.cycle}届 | {c.contribution_type} |")
                    lines.append("")
                    lines.append("> 数据来源: FEC.gov (bulk-downloads)")
                    lines.append("")
        finally:
            local_db.close()
    except Exception:
        pass

    # Top contributors from member JSON field (legacy)
    if member.top_contributors:
        lines.append("## TOP5 政治献金来源 (历史)")
        lines.append("")
        lines.append("| 组织 | 金额 | 周期 |")
        lines.append("|------|------|------|")
        for tc in member.top_contributors[:5]:
            org = tc.get("organization", "未知")
            amount = tc.get("amount", 0)
            cycle = tc.get("cycle", "")
            lines.append(f"| {org} | ${amount:,} | {cycle} |")
        lines.append("")

    # Top holdings from structured table (v0.94)
    try:
        from app.db.postgres import SessionLocal
        local_db = SessionLocal()
        try:
            holdings = local_db.query(HoldingAsset).filter(
                HoldingAsset.member_id == member.id,
            ).order_by(HoldingAsset.value_max.desc().nullslast()).limit(10).all()

            if holdings:
                lines.append("## 持股披露")
                lines.append("")
                lines.append("| 资产名称 | 类型 | 代码 | 金额区间 | 披露年份 | 来源 |")
                lines.append("|----------|------|------|----------|----------|------|")
                for h in holdings:
                    asset_name = h.asset_name or "未知"
                    asset_type = h.asset_type or "未知"
                    ticker = h.ticker or "N/A"
                    value_range = h.value_range_label or f"${h.value_min or 0:,.0f} - ${h.value_max or 0:,.0f}"
                    filing_year = h.filing_year or "N/A"
                    source = h.source or "house_disclosure"
                    lines.append(f"| {asset_name} | {asset_type} | {ticker} | {value_range} | {filing_year} | {source} |")
                lines.append("")
                lines.append("> 数据来源: 国会财务公开报告 (House/Senate Financial Disclosure)")
                lines.append("> 金额为区间值，不构成精确估值。")
                lines.append("> 不构成投资建议、法律判断或利益冲突判断。")
                lines.append("")
        finally:
            local_db.close()
    except Exception:
        pass

    # Top holdings from member JSON field (legacy fallback)
    if not holdings and member.top_holdings:
        lines.append("## TOP5 持股 (历史)")
        lines.append("")
        lines.append("| 公司 | 代码 | 估算价值范围 |")
        lines.append("|------|------|-------------|")
        for th in member.top_holdings[:5]:
            company = th.get("company", "未知")
            ticker = th.get("ticker", "N/A")
            lo = th.get("amount_min", 0)
            hi = th.get("amount_max", 0)
            lines.append(f"| {company} | {ticker} | ${lo:,} - ${hi:,} |")
        lines.append("")

    # China stance
    lines.append("## 涉华立场摘要")
    lines.append("")
    if member.china_stance_summary:
        lines.append(member.china_stance_summary)
    else:
        lines.append("暂无相关记录。")
    lines.append("")

    # Controversies
    lines.append("## 争议与调查记录")
    lines.append("")
    if member.controversies:
        for c in member.controversies:
            ctype = c.get("type", "未知")
            desc = c.get("description", "")
            source = c.get("source_name", "未知来源")
            cstatus = c.get("status", "未知状态")
            lines.append(f"- **[{ctype.upper()}]** {desc}")
            lines.append(f"  - 来源: {source}")
            lines.append(f"  - 状态: {cstatus}")
            lines.append(f"  - 需人工复核: {'是' if c.get('needs_review') else '否'}")
        lines.append("")
    else:
        lines.append("暂无公开争议与调查记录。")
        lines.append("")

    if include_predictions:
        lines.append("## 指标评估 (Mock 演示数据)")
        lines.append("")
        lines.append("> 以下指标基于 Mock 演示数据，使用固定基线值，不代表真实分析结果。")
        lines.append("")
        lines.append("| 指标 | 分值 | 数据说明 |")
        lines.append("|------|------|---------|")
        lines.append("| 党派一致性 | 50 | Mock 演示值 |")
        lines.append("| 涉华立场指数 | 50 | Mock 演示值 |")
        lines.append("| 道德合规评级 | 50 | Mock 演示值（已禁用） |")
        lines.append(f"| 委员会相关度 | {min(100.0, len(member.committee_memberships or []) * 20.0):.0f} | 基于 Mock 委员会数据 |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 免责声明")
    lines.append("")
    lines.append("> 仅供研究参考，不构成事实认定、法律判断或投资建议。")
    if member.source != "mock":
        lines.append("> 本报告数据来源于 unitedstates/congress-legislators (CC0-1.0) 真实数据集。")
        lines.append("> 该报告需人工审核。部分字段可能不完整，分析数据采集进行中。")
    else:
        lines.append("> 本报告数据来源于 Mock 生成数据，非真实情报。")
        lines.append("> 该报告需人工审核。所有指标评估基于 Mock 演示数据。")
    lines.append("")

    return "\n".join(lines)
