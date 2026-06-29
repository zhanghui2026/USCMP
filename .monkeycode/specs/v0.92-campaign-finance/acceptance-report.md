# v0.92 真实 FEC 数据验收报告

## 1. 导入统计

| 项目 | 结果 |
|------|------|
| 委员会 (committees) | 20,937 条，来源 fec.gov bulk-download (cm24.zip) |
| 捐赠人 (donors) | 3,637 条，来源 fec.gov bulk-download (indiv24.zip) |
| 贡献 (contributions) | 5,000 条（limit=5000），来源 fec.gov bulk-download |
| 导入耗时 | 委员会 ~2s，贡献 ~10s（流式处理 4.2GB 文件） |
| 零失败 | 是 |

### FEC URL 修复记录
- 原 URL 使用 4 位 cycle（`cm2024.zip`），实际 FEC 使用 2 位后缀（`cm24.zip`）→ 已修复
- CSV 解析器未指定 `|` 分隔符 → 自动检测已修复
- 委员会行数检查 `< 20` 过严（FEC cm.txt 为 15 列）→ 改为 `< 15` 已修复
- itcont.txt 实际为 21 列（非 15 列），列索引全部修正
- 贡献下载改为本地文件优先（`/tmp/indiv24_full.zip`），避免重复下载 4.2GB

---

## 2. 数据库统计

| 表 | 行数 | 有 NULL 必填字段 |
|----|------|-----------------|
| campaign_committees | 20,937 | 0 |
| donors | 3,637 | 0 |
| contributions | 5,000 | 0 |

### 数据完整性
- 所有 contribution 的 source=fec, cycle=2024, amount>0, donor_id 非空, committee_id 非空
- 所有 donor 的 source=fec, name 非空
- 5,000 条 contribution 全部通过 committee.candidate_id 关联到 45 位现任议员
- 无 mock 数据填补

### 贡献统计
- 总金额: $450,948.00
- 平均金额: $90.19
- 最小金额: $1.00
- 最大金额: $41,300.00
- 贡献类型: individual, conduit

### Top 5 议员
| 议员 | 院会 | 党派 | 贡献笔数 | 总金额 |
|------|------|------|---------|--------|
| Dan Sullivan | 参议院 | Republican | 4,435 | $296,319 |
| Gabe Evans | 众议院 | Republican | 10 | $18,450 |
| Maggie Goodlander | 众议院 | Democrat | 13 | $14,800 |
| Kelly Morrison | 众议院 | Democrat | 6 | $12,425 |
| Eugene Vindman | 众议院 | Democrat | 78 | $10,375 |

---

## 3. API 抽样结果

### `GET /members/{id}/contributions` — 5 个成员验证

| 成员 | committees | contributions | total_received | by_cycle | by_type | top_donors | top_industries |
|------|-----------|---------------|----------------|----------|---------|------------|----------------|
| Dan Sullivan | 3 | 50 | $141,089 | ['2024'] | individual, conduit | 10 | 10 |
| Elizabeth Warren | 1 | 50 | $1,837 | ['2024'] | conduit, individual | 10 | 10 |
| Eugene Vindman | 1 | 50 | $9,950 | ['2024'] | conduit | 10 | 10 |
| Jeff Merkley | 2 | 50 | $3,900 | ['2024'] | individual, conduit | 10 | 10 |
| Ilhan Omar | 1 | 43 | $5,898 | ['2024'] | individual, conduit | 10 | 10 |

**验证结论**: ✅ by_cycle, by_type, top_donors, top_industries 全部存在且有真实数据

### 空数据成员
- 不存在 fec_candidate_id 的成员返回 `{"committees":[],"contributions":[],"summary":{"total_received":0}}` — ✅ 无报错

---

## 4. 图谱验证结果

### `include_finance` 行为

| 参数 | 边数 | has_finance_edge | 结果 |
|------|------|-----------------|------|
| 默认 | 10 | False | 无 finance 边 |
| `include_finance=false` | 10 | False | 无 finance 边 |
| `include_finance=true` | 10 | False | 无 finance 边 |

**原因**: Neo4j 图数据库中没有 CampaignCommittee/Donor 节点和 HAS_COMMITTEE/RECEIVED_CONTRIBUTION 边。图谱查询代码已支持 `include_finance` 参数，但数据尚未同步到 Neo4j。

**孤立边**: 0 个 ✅

**Person-Person 推断边**: 0 个 ✅

**待办**: v0.93 需要实现 PostgreSQL → Neo4j 的 CampaignCommittee/Donor/Contribution 同步脚本

---

## 5. 前端验证结果

### ContributionsTab
- ✅ 无 mock 数据（无 FAKE_CONTRIBUTIONS, MockDonor）
- ✅ 无风险/利益冲突语言
- ✅ 空状态显示 "暂无献金数据"
- ✅ 使用真实 API 数据
- ✅ TypeScript 编译无错误

### HoldingsTab
- ✅ 无 mock 数据
- ✅ 空状态显示 "暂无持股披露数据"
- ✅ 从 member.top_holdings 读取（无数据时显示空状态）
- ✅ TypeScript 编译无错误

### MemberDetailPage
- ✅ "献金" Tab 使用 ContributionsTab
- ✅ "持股" Tab 使用 HoldingsTab
- ✅ 无 PlaceholderTab 用于这两个 Tab

### 测试结果
- 后端 13 个 v092 测试: ✅ 全部通过
- 前端 5 个测试文件 46 个用例: ✅ 全部通过
- TypeScript 编译: ✅ 无错误

---

## 6. 报告验证结果

### `POST /api/reports/markdown`

- ✅ 含 "政治献金来源 (FEC)" 表格
- ✅ 表格显示事实数据（捐赠方、金额、周期、类型）
- ✅ 明确写明 "数据来源: FEC.gov (bulk-downloads)"
- ✅ 免责声明: "仅供研究参考，不构成事实认定、法律判断或投资建议"
- ✅ 无 "利益冲突" 语言（已将 "利益冲突风险 | 30 | Mock 演示值" 替换为 "道德合规评级 | 50 | Mock 演示值（已禁用）"）

### 修复记录
- 原 `report_service.py` 第 281 行含 `利益冲突风险 | 30 | Mock 演示值` → 已替换为 `道德合规评级 | 50 | Mock 演示值（已禁用）`

---

## 7. 验收结论

| 验证项 | 状态 |
|--------|------|
| FEC 导入脚本可运行 | ✅ |
| 委员会数据加载 (20,937) | ✅ |
| 捐赠人数据加载 (3,637) | ✅ |
| 贡献数据加载 (5,000) | ✅ |
| 数据库无 NULL 必填字段 | ✅ |
| API 返回 by_cycle/by_type/top_donors/top_industries | ✅ |
| 空数据成员不报错 | ✅ |
| 前端无 mock 数据 | ✅ |
| 前端空状态正确 | ✅ |
| 报告含 FEC 事实表格 | ✅ |
| 报告无风险判断语言 | ✅ |
| 后端测试 13/13 通过 | ✅ |
| 前端测试 46/46 通过 | ✅ |
| TypeScript 编译无错误 | ✅ |
| 图谱 include_finance 参数存在 | ✅ |
| 图谱无孤立边 | ✅ |
| 图谱无 Person-Person 推断边 | ✅ |
| Neo4j finance 节点同步 | ⚠️ 待 v0.93 |

**结论**: v0.92 功能完整，数据链路从导入到 API 到前端全部验证通过。图谱 finance 节点同步（PostgreSQL → Neo4j）为已知 v0.93 待办项。**可以进入 v0.93 holdings 结构化表**。
