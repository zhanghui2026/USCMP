# v0.93 实施摘要：Campaign Finance Graph Sync

## 1. 实施摘要

### 新增文件
- `backend/app/etl/import_finance_graph.py` — PostgreSQL → Neo4j 同步脚本

### 修改文件
| 文件 | 变更 |
|------|------|
| `backend/app/services/graph_service.py` | 边类型从 `HAS_COMMITTEE/RECEIVED_CONTRIBUTION` 改为 `ASSOCIATED_WITH_COMMITTEE/CONTRIBUTED_TO/HAS_CONTRIBUTION_SOURCE` |
| `backend/app/api/routes/graph.py` | `include_finance` 默认值从 `True` 改为 `False` |
| `backend/app/models/pydantic/models.py` | `GraphExpandRequest` 新增 `include_finance: bool = False` |
| `frontend/src/app/components/GraphCanvas/GraphCanvas.tsx` | 新增 CampaignCommittee/Donor/ContributionSource 节点样式、边颜色、边标签、底部免责声明 |
| `backend/tests/test_v092_finance.py` | 更新边类型名称以匹配 v0.93 变更 |
| `backend/tests/test_v093_finance_graph.py` | 新增 15 个 v0.93 测试 |

---

## 2. Neo4j Finance 节点/边导入统计

| 类型 | 数量 |
|------|------|
| **CampaignCommittee 节点** | 580 |
| **Donor 节点** | 3,624 |
| **ContributionSource 节点** | 1 |
| **ASSOCIATED_WITH_COMMITTEE 边** (Person → CampaignCommittee) | 580 |
| **CONTRIBUTED_TO 边** (Donor → CampaignCommittee) | 3,636 |
| **HAS_CONTRIBUTION_SOURCE 边** (CampaignCommittee → ContributionSource) | 580 |

### 边属性
每条边包含：
- `cycle` (选举周期)
- `amount_total` (总金额)
- `contribution_count` (贡献笔数)
- `source` (来源: fec)
- `source_reliability` (可靠性: high)
- `last_updated` (最后更新时间)

### 幂等性验证
第二次导入结果与第一次完全相同，使用 MERGE 保证幂等。

---

## 3. include_finance 验证结果

| 场景 | 边数 | 节点数 | has_finance | 结果 |
|------|------|--------|-------------|------|
| 默认 (include_finance=false) | 10 | 11 | False | ✅ 无 finance 节点 |
| include_finance=true (depth=1) | 13 | 14 | True | ✅ 有 CampaignCommittee 节点 |
| include_finance=true (depth=2) | 13 | 14 | True | ✅ 同上 |
| 从 CampaignCommittee 展开 | 199 | 200 | True | ✅ 198 个 Donor 节点 |
| 无 FEC 数据成员 | 5 | 6 | False | ✅ 无 finance 节点 |
| 不存在成员 | 0 | 0 | False | ✅ 空结果 |

### 孤立边检查
- orphan_edges: 0 ✅

### Person-Person 推断边检查
- person_person_edges: 0 ✅

---

## 4. 前端图谱变化

### 新增节点样式
| 节点类型 | 颜色 | 形状 | 大小 |
|----------|------|------|------|
| CampaignCommittee | #eb2f96 (粉) | hexagon | 30 |
| Donor | #ff4d4f (红) | diamond | 28 |
| ContributionSource | #9254de (紫) | star | 26 |

### 新增边样式
| 边类型 | 颜色 | 中文标签 |
|--------|------|---------|
| ASSOCIATED_WITH_COMMITTEE | #eb2f96 | 竞选委员会 |
| CONTRIBUTED_TO | #ff4d4f | 捐赠 |
| HAS_CONTRIBUTION_SOURCE | #9254de | 数据来源 |

### 免责声明
当图中存在 finance 节点时，底部显示：
> "公开献金节点仅表示 FEC 公开记录，不构成利益冲突判断。"

---

## 5. 测试结果

| 测试文件 | 用例数 | 结果 |
|----------|--------|------|
| test_v092_finance.py | 13 | ✅ 全部通过 |
| test_v093_finance_graph.py | 15 | ✅ 全部通过 |
| **合计** | **28** | **✅ 全部通过** |
| 前端测试 | 46 | ✅ 全部通过 |

### v0.93 测试覆盖
- finance edge types 定义正确
- edge_filter with/without finance
- import 函数存在且可调用
- GraphAPI include_finance 参数存在
- GraphExpandRequest include_finance 参数存在
- CampaignCommittee/Donor/ContributionSource 标签
- 边属性包含 cycle/amount_total/contribution_count/source/source_reliability/last_updated
- orphan 边过滤存在
- MERGE 幂等性

---

## 6. 结论

**可以进入 holdings 结构化表**。

v0.93 已完成 PostgreSQL → Neo4j 的献金数据同步。`include_finance=true` 现在能真实显示：
- Person → CampaignCommittee 关联
- CampaignCommittee → Donor 捐赠关系
- CampaignCommittee → ContributionSource 数据来源

默认 `include_finance=false` 不展示 finance 节点，符合需求。
