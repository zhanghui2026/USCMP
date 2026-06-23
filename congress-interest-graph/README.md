# 美国国会利益关联图谱系统 (USCMP)

智库级美国政治研究工具，通过开源情报 (OSINT) 分析美国参众两院议员的身份背景、商业利益、社会关系、委员会职务、涉华相关行为、政治资金流和公开争议记录。

## 快速演示

### 一键启动

```bash
# 克隆项目
git clone https://github.com/daazha/USCMP.git
cd USCMP

# 使用部署脚本
./deploy.sh dev

# 或手动启动
docker compose up --build -d
```

### 访问地址

- **前端界面**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **Neo4j 浏览器**: http://localhost:7474

### 初始化数据

```bash
# 使用脚本
./deploy.sh init

# 或手动初始化
docker compose exec backend python3 -m app.etl.import_real_members
docker compose exec backend python3 -m app.etl.import_fec_data
docker compose exec backend python3 -m app.etl.import_holdings
docker compose exec backend python3 -m app.etl.import_congress_profiles

# 可选: 使用已下载的 FEC indiv zip 执行流式全量献金导入
docker compose exec backend python3 -m app.etl.import_fec_data --cycle 2024 --contributions-only --contributions-zip /data/indiv24.zip
```

> 详细部署说明请参考 [DEPLOYMENT.md](DEPLOYMENT.md)
> 演示指南请参考 [DEMO.md](DEMO.md)

---

## 合规声明

- 仅供研究参考，不构成事实认定、法律判断或投资建议
- Mock 数据明确标记 `source = "mock"`
- 真实数据明确标记 `source = "uscl"`，来源于 unitedstates/congress-legislators (CC0-1.0)
- 所有预测基于可解释规则模型，不依赖 LLM 黑箱生成
- 争议与调查记录使用 `allegation / investigation / lawsuit / conviction / correction` 分类
- 禁止输出未经法院/监管机构/权威媒体确认的事实性指控

## 架构

```
congress-interest-graph/
├── backend/          # Python FastAPI 后端
│   ├── app/
│   │   ├── api/routes/     # API 路由
│   │   ├── core/           # 配置、日志、错误处理
│   │   ├── db/             # PostgreSQL + Neo4j 连接
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
│   └── congress-profiles/  # 537 份议员档案 (Markdown)
└── docker-compose.yml
```

## 版本历史

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
| 历史议员 (historical) | 12,225 |
| 委员会 | 49 |
| 委员会任职 | 3,879 |
| 竞选委员会 | 20,937 |
| 捐赠者 | 3,637 |
| 献金记录 | 5,000 |
| 持股资产 | 250 |
| 议员档案 | 537 |

### Neo4j 图谱节点

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

### 边类型

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
| 数据库 | PostgreSQL 15, Neo4j 5 |
| ORM/驱动 | SQLAlchemy 2.x, neo4j-python-driver |
| 前端 | React 18, TypeScript, Vite |
| UI 组件 | Ant Design 5 |
| 图谱渲染 | AntV G6 (WebGL) |
| 状态管理 | Zustand |
| 测试 | pytest, vitest |
| 容器化 | Docker Compose |

## 本地启动

### Docker Compose (推荐)

```bash
# 1. 复制环境配置
cp .env.example .env

# 2. 启动所有服务
docker compose up --build

# 3. 初始化数据
docker compose exec backend python3 -m app.etl.import_real_members
docker compose exec backend python3 -m app.etl.import_real_graph
docker compose exec backend python3 -m app.etl.import_fec_data
docker compose exec backend python3 -m app.etl.import_holdings
docker compose exec backend python3 -m app.etl.import_congress_profiles

# 4. 访问
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# OpenAPI Docs: http://localhost:8000/docs
```

### 本地开发

```bash
# 1. 确保 PostgreSQL 和 Neo4j 已运行

# 2. 启动后端
cd backend
pip install -r requirements.txt
POSTGRES_HOST=localhost uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 启动前端
cd frontend
npm install
npm run dev

# 4. 初始化数据
cd backend
python3 -m app.etl.import_real_members
python3 -m app.etl.import_fec_data
python3 -m app.etl.import_holdings
python3 -m app.etl.import_congress_profiles

# 可选: 使用已下载的 FEC indiv zip 执行流式全量献金导入
python3 -m app.etl.import_fec_data --cycle 2024 --contributions-only --contributions-zip /data/indiv24.zip
```

## API 文档

启动服务后访问 `http://localhost:8000/docs` 查看 OpenAPI 交互文档。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/members` | GET | 议员列表 |
| `/api/members/{id}` | GET | 议员详情 |
| `/api/members/{id}/graph` | GET | 议员图谱 |
| `/api/members/{id}/contributions` | GET | 献金记录 |
| `/api/members/{id}/holdings` | GET | 持股披露 |
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
cd backend && POSTGRES_HOST=localhost python3 -m pytest tests/ -v

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
