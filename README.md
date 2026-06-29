# 美国国会利益关联图谱系统 (USCMP)

智库级美国政治研究工具，通过开源情报 (OSINT) 分析美国参众两院议员的身份背景、商业利益、社会关系、委员会职务、涉华相关行为、政治资金流和公开争议记录。

## 合规声明

- 仅供研究参考，不构成事实认定、法律判断或投资建议
- Mock 数据明确标记 `source = "mock"`
- 真实数据明确标记 `source = "uscl"`，来源于 unitedstates/congress-legislators (CC0-1.0)
- 所有预测基于可解释规则模型，不依赖 LLM 黑箱生成
- 争议与调查记录使用 `allegation / investigation / lawsuit / conviction / correction` 分类
- 禁止输出未经法院/监管机构/权威媒体确认的事实性指控

## 架构

```
├── backend/          # Python FastAPI 后端
│   ├── app/
│   │   ├── api/routes/     # API 路由
│   │   ├── core/           # 配置、日志、错误处理
│   │   ├── db/             # SQLite (默认) / PostgreSQL + Neo4j(可选)
│   │   ├── models/         # Pydantic + SQLAlchemy 模型
│   │   ├── services/       # 图查询服务 (集中 Cypher)
│   │   ├── etl/            # ETL Adapters + 真实导入
│   │   └── scripts/        # Mock 数据生成与种子
│   └── tests/              # pytest 测试
├── frontend/         # React + TypeScript + Ant Design 前端
│   └── src/app/
│       ├── api/            # API 客户端 + TypeScript 类型
│       ├── components/     # GraphCanvas, ContributionsTab, HoldingsTab, ProfileTab
│       ├── pages/          # OverviewPage, MemberDetailPage
│       └── store/          # Zustand 状态管理
├── data/
│   └── congress-profiles/  # 544 份议员档案 (Markdown)
├── docker-compose.yml
└── deploy.sh
```

## 版本历史

### v1.1 - 资金聚合与轻量化改造
- 新增 `MemberFinanceSummary` 聚合表：成员级资金预汇总，不再每次扫全量明细表
- 新增 `GET /api/members/{id}/finance/summary` 优先使用聚合数据
- 修复 `CampaignCommittee.candidate_id` 关联 bug（改用 fec_candidate_id），回填 25,299 个委员会
- 为 530 位当前议员重建资金汇总
- 前端 ContributionsTab 优先读取聚合接口，明细记录按需补充加载
- 移除 12,275 名历史议员，仅保留 544 名现任议员
- 移除 12,224 条历史议员画像、250 条历史持股资产
- Neo4j 降级为可选：后端可在无 Neo4j 时正常启动
- 默认启用 SQLite fallback 模式，无需 PostgreSQL
- 简化 docker-compose.yml，合并 dev/prod 为单一部署入口
- 精简 backend Dockerfile（去掉 gcc 编译依赖和 dev 包）
- 删除 `.cursor/`、`nginx/` 根目录 `node_modules/` 等残留文件
- 项目文件移至仓库根目录，去除 `congress-interest-graph/` 嵌套层级

### v1.0 - 数据覆盖、FEC 优化、持股披露
- 新增数据覆盖 API `/api/data-coverage`，展示基础资料、画像、FEC 献金、持股披露的数据覆盖状态
- 优化 FEC 导入：仅保留现任议员，限制 2022/2024 周期，降低磁盘压力
- 修复 FEC candidate ID 匹配：补正多位参议员 Senate ID，提升现任议员委员会覆盖率至 97.4%
- 新增政治献金 (`ContributionsTab`) 与持股 (`HoldingsTab`) 前端页面
- 新增持股披露 ETL：支持 CSV/JSON 格式的公开财务披露数据导入
- 优化 API 稳定性：统一议员可见性过滤，避免部分接口失败阻塞整体页面加载
- 新增 `export_to_sqlite.py` 导出脚本

### v0.95 - 国会议员档案导入
- 导入 537 份议员档案文件 (Markdown 格式)
- 新增 `core_positions` (核心政治主张) 和 `comprehensive_evaluation` (综合评价) 字段
- 支持 3 种档案格式: detailed (92), short (290), very-short (155)
- 模糊姓名匹配: 536/537 成功匹配
- 新增 ProfileTab 组件展示对华立场、核心主张、综合评价
- OverviewPage 性能优化: React.memo、懒加载、分页显示
- 委员会按常设/专门/特别分类分组展示
- 移除未使用的 echarts 依赖

### v0.94 - 结构化持股披露
- 新增 `holding_assets` / `holding_disclosures` 表
- 新增 `GET /api/members/{id}/holdings` 端点
- Neo4j 同步: Asset / HoldingDisclosure / HoldingSource 节点
- 边类型: DISCLOSED_HOLDING / REPORTED_IN / HAS_HOLDING_SOURCE
- `include_holdings=false` 默认不展示持股节点
- 金额区间保持原样，不伪造精确金额

### v0.93 - FEC 献金数据 Neo4j 同步
- 从 PostgreSQL 同步 FEC 数据到 Neo4j
- 新增 CampaignCommittee / Donor / ContributionSource 节点
- 边类型: ASSOCIATED_WITH_COMMITTEE / CONTRIBUTED_TO / HAS_CONTRIBUTION_SOURCE
- `include_finance=false` 默认不展示献金节点

### v0.92 - FEC 献金数据集成
- 接入 FEC bulk-data (indiv24.zip, cm24.zip)
- 新增 `campaign_committees` / `donors` / `contributions` 表
- 新增 `GET /api/members/{id}/contributions` 端点
- 导入: 20,937 committees, 3,637 donors, 5,000 contributions

### v0.7 - 履历事实图谱
- Wikipedia 履历接入
- 履历事实节点: EducationInstitution / Position / Employer / ProfileSource
- 边类型: EDUCATED_AT / HELD_POSITION / EMPLOYED_BY / HAS_PROFILE_SOURCE

### v0.4 - 真实数据接入
- 接入 unitedstates/congress-legislators (CC0-1.0)
- 支持 mock / real / mixed 三种数据模式
- 12,767 议员基础数据

## 数据统计

### 真实数据 (v0.95)

| 指标 | 数量 |
|------|------|
| 当前议员 (current) | 544 |
| 历史议员 (historical) | 0（v1.1 清理，仅保留现任） |
| 委员会 | 49 |
| 委员会任职 | 3,879 |
| 竞选委员会 | 25,963 |
| 捐赠者 | 416,141 |
| 献金记录 | 2,217,720 |
| 持股资产 | 0（历史数据已清理） |
| 议员画像 | 544 |

### Neo4j 图谱节点（需部署 Neo4j 时可用，默认可选）

| 节点类型 | 说明 |
|----------|------|
| Person | 在任议员 |
| Party / State / Chamber | 身份节点 |
| Committee | 委员会 |
| EducationInstitution / Position / Employer / ProfileSource | 履历事实节点 |
| CampaignCommittee | 竞选委员会 |
| Donor | 捐赠者 |
| Asset | 持股资产 |
| HoldingDisclosure | 持股披露 |

### 边类型（需部署 Neo4j 时可用）

| 边类型 | 说明 |
|--------|------|
| MEMBER_OF_PARTY / REPRESENTS_STATE / SERVES_IN / ASSIGNED_TO | 身份关系 |
| EDUCATED_AT / HELD_POSITION / EMPLOYED_BY / HAS_PROFILE_SOURCE | 履历事实 |
| ASSOCIATED_WITH_COMMITTEE / CONTRIBUTED_TO / HAS_CONTRIBUTION_SOURCE | 献金关系 |
| DISCLOSED_HOLDING / REPORTED_IN / HAS_HOLDING_SOURCE | 持股关系 |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Python 3.10+, FastAPI, Pydantic v2 |
| 数据库 | SQLite (默认) / PostgreSQL (可选) + Neo4j (可选) |
| ORM/驱动 | SQLAlchemy 2.x, neo4j-python-driver |
| 前端 | React 18, TypeScript, Vite |
| UI 组件 | Ant Design 5 |
| 图谱渲染 | AntV G6 (WebGL) |
| 状态管理 | Zustand |
| 测试 | pytest, vitest |
| 容器化 | Docker Compose |

## 快速启动

### Docker Compose (推荐，轻量模式)

```bash
# 启动前后端
docker compose up --build -d

# 访问
# 前端: http://localhost:3000
# API 文档: http://localhost:8000/docs
```

后端默认使用 SQLite 数据库（无需 PostgreSQL/Neo4j），数据已预导入（544 名现任议员的身份、献金、档案数据）。

### 本地开发

```bash
# 1. 启动后端 (SQLite 模式)
cd backend
USE_SQLITE_FALLBACK=true uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. 启动前端
cd frontend
npm install
npm run dev

# 初始化数据（首次或重置时执行）
cd backend
USE_SQLITE_FALLBACK=true python3 -m app.etl.import_real_members
USE_SQLITE_FALLBACK=true python3 -m app.etl.import_fec_data
```

## API 文档

启动服务后访问 `http://localhost:8000/docs` 查看 OpenAPI 交互文档。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/members` | GET | 议员列表 |
| `/api/members/{id}` | GET | 议员详情 |
| `/api/members/{id}/graph` | GET | 议员图谱 |
| `/api/members/{id}/finance/summary` | GET | 献金聚合汇总(v1.1) |
| `/api/members/{id}/contributions` | GET | 献金明细记录 |
| `/api/members/{id}/holdings` | GET | 持股披露 |
| `/api/members/{id}/profile` | GET | 议员画像 |
| `/api/data-coverage` | GET | 数据源覆盖状态 |
| `/api/graph/expand` | POST | 节点展开 |
| `/api/search` | GET | 全局搜索 |
| `/api/reports/markdown` | POST | Markdown 简报 |

## 图谱控制参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `include_profile_facts` | true | 履历事实节点 |
| `include_finance` | false | 献金节点 |
| `include_holdings` | false | 持股节点 |
| `include_related_people` | false | 同事关系 |
| `include_historical_background` | false | 历史背景 |

## 测试

```bash
# 后端测试
cd backend && USE_SQLITE_FALLBACK=true python3 -m pytest tests/ -v

# 前端测试
cd frontend && npm test

# 前端类型检查
cd frontend && npx tsc --noEmit
```

## 数据来源

| 数据源 | 说明 | 许可 |
|--------|------|------|
| unitedstates/congress-legislators | 议员基础数据 | CC0-1.0 |
| FEC.gov bulk-downloads | 竞选献金数据 | Public Domain |
| 国会财务公开报告 | 持股披露数据 | Public Domain |
| Wikipedia | 履历信息 | CC BY-SA 4.0 |

## 数据覆盖状态

- `unitedstates/congress-legislators`: 基础成员、任期、委员会数据已作为主数据源导入。
- `FEC.gov bulk-downloads`: ETL 支持通过 `--contributions-zip` 对已下载 indiv zip 进行流式全量导入；当前演示库可能只包含样本规模记录，前端会显示覆盖状态。
- `国会财务公开报告`: 当前结构化表优先迁移 `Member.top_holdings` 子集；完整披露文件导入需要提供 House/Senate 原始 disclosure 文件或下载源。
- `Wikipedia / 本地 Markdown 档案`: 当前导入本地 537 份议员档案，前端展示已匹配档案字段。

## 免责声明

本项目为技术架构原型。当前版本数据包含 Mock 生成数据 (source=mock) 和真实国会数据 (source=uscl, CC0-1.0)。任何基于该系统的分析结果仅供研究参考，不构成:

- 事实认定 (finding of fact)
- 法律判断 (legal judgment)
- 投资建议 (investment advice)
- 政治立场 (political position)

使用本系统的用户应自行承担相关风险与责任。
