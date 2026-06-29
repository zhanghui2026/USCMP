# v0.92 国会利益冲突查询系统 — 竞选献金模块集成总结

## 一、需求概述

本次迭代（v0.92）在 v0.91（利益关系图谱）基础上，将竞选献金数据库（FEC）集成到系统中，构建 "议员 → 竞选委员会 → 捐赠人 → 捐赠" 的事实链，并在前端可视化展示。

## 二、数据库层 — SQLAlchemy 模型

三张新表，位于 `backend/app/models/sqlalchemy/models.py`，通过外键形成完整事实链：

| 表 | 关键字段 | 用途 |
|----|---------|------|
| `campaign_committees` | fec_committee_id, name, candidate_id (FK→members), cycle, party, chamber, data (JSONB), source | 竞选委员会 |
| `donors` | name, donor_type (individual/pac/party), industry, state, employer, data (JSONB), source | 捐赠人/捐赠实体 |
| `contributions` | committee_id (FK→campaign_committees), donor_id (FK→donors), amount, contribution_date, cycle, contribution_type, data (JSONB), source | 每笔捐赠记录 |

所有表均包含 `created_at`/`updated_at` 时间戳。

## 三、API 层

### 3.1 竞选献金 API

`GET /members/{member_id}/contributions` — `backend/app/api/routes/finance.py`

返回结构:

```typescript
ContributionsResponse {
  total_count: number;
  committees: CommitteeBrief[];  // id, fec_committee_id, name, cycle
  contributions: ContributionRecord[];  // 每笔捐赠详情
  summary: ContributionSummary {
    total_received: number;
    total_count: number;
    by_cycle: Record<string, number>;       // 按选举周期汇总
    by_type: Record<string, number>;         // 按捐赠类型汇总
    top_donors: TopDonor[];                  // 金额排序
    top_industries: TopIndustry[];           // 行业汇总
  };
}
```

API 通过 Python 层实时计算汇总统计（by_cycle、by_type、top_donors、top_industries），不对 PostgreSQL 执行聚合 SQL。

### 3.2 图谱 API 扩展

`GET /graph/members/{member_id}` 和 `GET /graph/expand/{node_id}` 新增 `include_finance` 参数（默认为 True）：

- `backend/app/services/graph_service.py` 定义 `FINANCE_EDGE_TYPES = frozenset({"HAS_COMMITTEE", "RECEIVED_CONTRIBUTION"})`
- 图谱查询新增 `_edge_filter()` 函数，根据 `include_finance` 决定是否包含边
- `EGO_EDGE_TYPES` 中已包含 `HAS_COMMITTEE` 和 `RECEIVED_CONTRIBUTION`

### 3.3 报告 API 扩展

`backend/app/services/report_service.py` 在 Markdown 报告末尾新增"政治献金来源 (FEC)"表格，展示按金额排序的 Top 10 捐赠记录。原有 `member.top_contributors` 仍作为"历史"部分保留。

### 3.4 健康检查扩展

`GET /health` 返回新增字段：`campaign_committees`、`campaign_donors`、`campaign_contributions`，表示各表的记录数。

## 四、FEC 数据导入

`backend/app/etl/import_fec_data.py` — 命令行脚本：

- 从 `https://www.fec.gov/files/bulk-downloads/` 下载 `cm{cycle}.zip`（委员会）和 `indiv{cycle}.zip`（个人捐赠）
- 每次处理 1000 行后 `session.commit()`，避免大文件内存溢出
- 自动跳过已存在的委员会/捐赠人记录（基于 fec_committee_id/donor fingerprint）
- 选举周期（cycle）推论：存储 FEC 原始 `transaction_dt` 后由脚本推算
- 委员会 chamber 从 FEC 委员会 ID 前缀推断（H→众议院，S→参议院）

运行命令：`python -m app.etl.import_fec_data --cycle 2024 --limit 10000`

## 五、Neo4j 图数据库扩展

**节点标签**：
- `CampaignCommittee` — 竞选委员会
- `Donor` — 捐赠人

**边类型**：
- `HAS_COMMITTEE` — Person → CampaignCommittee（某议员的竞选委员会）
- `RECEIVED_CONTRIBUTION` — CampaignCommittee → Donor（委员会收到的捐赠）

目前仅在查询层支持新标签和边类型。实际数据写入仍通过 PostgreSQL 进行，图数据库同步是独立步骤（v0.93+）。

## 六、前端页面

### 6.1 献金标签页（ContributionsTab）

`frontend/src/app/components/ContributionsTab.tsx`

展示内容（当有数据时）：
- 统计数据行：总金额、总笔数、委员会数
- 委员会卡片：委员会名称、届数、所属党派/院会
- By-cycle 卡片：按选举周期的金额柱状图
- By-type 卡片：按捐赠类型的金额柱状图
- Top Donors 表格：金额、笔数、类型
- Top Industries 表格：行业、金额、笔数
- 免责声明："数据来源: FEC.gov (bulk-downloads) 及 OpenSecrets.org。仅供研究参考。"

空状态：显示"暂无献金数据"。

### 6.2 持股标签页（HoldingsTab）

`frontend/src/app/components/HoldingsTab.tsx`

展示内容：
- 从 `member.top_holdings` JSONB 字段读取持股数据
- 公司名、股票代码、持有金额
- 空状态：显示"暂无持股披露数据"。

不包含 mock 数据。

### 6.3 MemberDetailPage

献金标签页和持股标签页已替换原有的 PlaceholderTab，通过 TabBar 切换。

## 七、补充性改进

### 7.1 代码清理

- 删除了 `CampaignFinanceTab.tsx` 中的 mock 数据结构（MockDonor/FAKE_CONTRIBUTIONS）
- 删除了 `CampaignFinanceTab.tsx` 中未使用的 `useMemo` 导入
- 将 `backend/app/services/report_service.py` 中的 `__import__` 动态导入替换为顶层模型引用

### 7.2 测试

`backend/tests/test_v092_finance.py` — 13 个测试用例覆盖：
- SQLAlchemy 模型字段存在性
- ContributionsResponse Pydantic 模型的空数据/有数据/结构验证
- 图边类型定义验证
- Finance 路由模块导入
- FEC 导入脚本函数存在性与 parse_amount 解析逻辑
- 报告模块导入

## 八、后续规划（v0.93+）

1. **执行 FEC 导入**：在部署环境运行 `python -m app.etl.import_fec_data --cycle 2024 --limit 10000`
2. **股票持股结构化表**：将 `member.top_holdings` JSON 拆为独立 `holdings` 表
3. **Neo4j 同步**：编写 Cypher 导入脚本，将 CampaignCommittee/Donor/Contribution 写入图数据库
4. **OpenSecrets API 适配**：作为 FEC 数据的补充来源，丰富捐赠人行业/雇主信息
5. **可视化增强**：在图谱视图中展示捐赠关系
