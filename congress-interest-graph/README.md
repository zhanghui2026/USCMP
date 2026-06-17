# 美国国会利益关联图谱系统 (Congress Interest Graph System)

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
congress-interest-graph/
├── backend/          # Python FastAPI 后端
│   ├── app/
│   │   ├── api/routes/     # API 路由 (10 个端点)
│   │   ├── core/           # 配置、日志、错误处理
│   │   ├── db/             # PostgreSQL + Neo4j 连接
│   │   ├── models/         # Pydantic + SQLAlchemy 模型
│   │   ├── services/       # 图查询服务 (集中 Cypher)
│   │   ├── etl/            # ETL Adapters + 真实导入 + Schema 迁移
│   │   ├── importers/      # (deprecated, 逻辑已迁移到 etl/)
│   │   └── scripts/        # Mock 数据生成与种子
│   ├── data/
│   │   ├── external/congress-legislators/  # Vendor pinned 真实数据 (CC0-1.0)
│   │   └── etl_runs/       # Dry Run 输出 + Import 运行记录
│   └── tests/              # pytest (148 个测试，含 16 个 API 集成测试 + 40 个导入/Phase3 测试)
├── frontend/         # React + TypeScript + Ant Design 前端
│   └── src/app/
│       ├── api/            # API 客户端 + TypeScript 类型
│       ├── components/     # GraphCanvas, EvidenceDrawer, TimeSliceControl
│       ├── pages/          # OverviewPage, MemberDetailPage, SearchPage, ComparePage
│       └── store/          # Zustand 状态管理
├── docs/             # 项目文档
└── docker-compose.yml
```

## v0.4 真实数据接入

已接入 [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) (CC0-1.0) 真实议员基础数据到主 API。支持 mock / real / mixed 三种数据模式，由 `/api/health` 自动检测。

### 初始化 Vendor Data

```bash
mkdir -p backend/data/external
git clone --depth 1 https://github.com/unitedstates/congress-legislators.git backend/data/external/congress-legislators
# 获取 commit SHA 并放置到对应子目录
```

### 运行真实导入

```bash
cd backend
python3 -m app.etl.schema_migration          # 安全 ALTER (可重复执行)
python3 -m app.etl.import_real_members        # 幂等导入 12,767 人
python3 -m app.etl.import_real_graph           # 幂等导入 Neo4j 身份图谱
python3 app/scripts/seed_mock_data.py          # 同时保留 Mock 数据
```

### 已接入 vs 未接入

| 已接入 | 说明 |
|--------|------|
| 议员基础身份 | 12,767 人 (current + historical), source=uscl |
| 委员会任职 | 49 个委员会, 3,879 条任职 |
| 任期信息 | 45,532 条记录 |
| FEC ID | 1,530 人有 FEC ID, 保留完整数组于 official_ids.fec |
| 基础 Neo4j 图谱 | Person/Party/State/Chamber/Committee + 4 种关系 |

| 未接入 | 说明 |
|--------|------|
| official_photo_url | 数据源不含 |
| top_contributors / top_holdings | 需接入 OpenSecrets/FEC API |
| career_summary | 需接入 Wikipedia/Ballotpedia |
| china_stance_summary | 需 NLP + 人工标注 |
| controversies | 需多源新闻聚合 |
| 预测/风险评分/利益冲突 | 未开发 |

### 图谱范围

仅基础身份关系: `MEMBER_OF_PARTY`, `REPRESENTS_STATE`, `SERVES_IN`, `ASSIGNED_TO`。
不包含 donor/holding/risk/prediction 等关系。

### 报告范围

包含: 基本信息、委员会任职、任期、数据来源。
不包含: 预测、风险评分、利益冲突判断。

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
| 测试 | pytest |
| 容器化 | Docker Compose |

## 本地启动

### Docker Compose (推荐)

```bash
# 1. 复制环境配置
cp .env.example .env

# 2. 启动所有服务 (PostgreSQL + Neo4j + Backend + Frontend)
docker compose up --build

# 3. 初始化 Mock 数据
docker compose exec backend python app/scripts/seed_mock_data.py

# 4. 访问
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# OpenAPI Docs: http://localhost:8000/docs
# Neo4j Browser: http://localhost:7474
```

### 本地开发 (不依赖 Docker)

```bash
# 1. 确保 PostgreSQL 和 Neo4j 已运行

# 2. 启动后端
cd backend
cp ../.env.example .env
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 启动前端 (Vite 代理默认指向 localhost:8000)
cd frontend
npm install
npm run dev

# 4. 初始化 Mock 数据
cd backend
python app/scripts/seed_mock_data.py
```

### 代理配置

前端使用 Vite 开发服务器代理将 `/api` 请求转发到后端:

| 运行环境 | 代理目标 |
|---------|---------|
| 本地开发 | `http://localhost:8000` (默认) |
| Docker Compose | `http://backend:8000` (通过 `VITE_API_PROXY_TARGET` 环境变量) |

环境变量 `VITE_API_PROXY_TARGET` 在 `vite.config.ts` 中读取，`docker-compose.yml` 已预置 `VITE_API_PROXY_TARGET=http://backend:8000`。

## v0.4 数据统计

### 真实数据 (unitedstates/congress-legislators @ dfa9622)

接入 [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) (CC0-1.0) 真实议员数据，采用 Vendor Pinned + Dry Run First + Sandbox Only 方案。

| 指标 | 数量 |
|------|------|
| 真实议员 | 12,767 |
| 任期记录 | 45,532 |
| 委员会 | 49 |
| 委员会任职 | 3,879 |
| 官方社媒账号 | 2,354 |
| 提取 Claims | 64,532 |
| Source Documents | 5 (YAML files @ dfa9622) |

```bash
# ETL Dry Run (不写数据库，仅验证数据质量)
cd backend
python3 -m app.etl.dry_run --adapter congress_legislators --commit-sha dfa9622263dd4c8d08636926e498f1845704d7eb

# Sandbox Import (写入 sandbox namespace 的 PostgreSQL)
python3 -m app.etl.import_sandbox --run-id <dry_run_id>
```

### 数据护栏
- 所有 sandbox 数据使用独立 `data_namespace="sandbox"`，不覆盖 Mock 主图谱
- Prediction 护栏: identity/committee-only 证据返回 `predicted_position="unknown"`
- Entity Resolution: 仅 bioguide_id + govtrack_id 双 ID 强匹配 → safe_match
- 置信度: identity=0.95, term=0.90, committee=0.85, social=0.85

## Mock 数据

| 实体 | 数量 |
|------|------|
| 议员 (Person) | 50 |
| 组织 (Organization) | 100 |
| 政治实体 (PoliticalEntity) | 20 |
| 事件 (Event) | 100 |
| 声明 (Claim) | 300 |
| 来源文档 (SourceDocument) | 500 |
| 图关系 | ~1180 |
| 低置信度关系 | 20+ |
| 覆盖届次 | 117, 118, 119 |

重新初始化 Mock 数据:

```bash
docker compose exec backend python app/scripts/clear_databases.py
docker compose exec backend python app/scripts/seed_mock_data.py
```

## API 文档

启动服务后访问 `http://localhost:8000/docs` 查看 OpenAPI 交互文档。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/members` | GET | 议员列表 (支持筛选) |
| `/api/members/{id}` | GET | 议员详情 |
| `/api/members/{id}/graph` | GET | 议员图谱 (depth <= 2) |
| `/api/graph/expand` | POST | 节点展开 (depth = 1) |
| `/api/evidence/{claim_id}` | GET | 证据溯源 |
| `/api/search` | GET | 全局搜索 |
| `/api/compare` | POST | 多人对比 |
| `/api/reports/markdown` | POST | Markdown 简报导出 |
| `/api/predictions/vote` | POST | 投票预测 |

## 前端页面

| 页面 | 路由 | 说明 |
|------|------|------|
| 概览页 | `/` | 议员卡片、筛选、搜索 |
| 议员详情 | `/member/:id` | 身份详情 + 2 度图谱 |
| 搜索页 | `/search` | 全局搜索 (议员/组织/事件) |
| 对比页 | `/compare` | 多人对比 + 指标表 |

## 测试

```bash
# 后端测试
cd backend && python3 -m pytest tests/ -v

# 前端类型检查
cd frontend && npx tsc --noEmit

# 前端构建验证
cd frontend && npx vite build
```

## 真实数据 Adapter

第二阶段可选接入的真实数据源 (当前为空壳):

- `CongressGovAdapter` - Congress.gov API
- `FECAdapter` - Federal Election Commission API
- `OpenSecretsAdapter` - OpenSecrets.org API

每个 Adapter 必须声明 `source_name / source_url / license_note / robots_policy_note / rate_limit`。

## 免责声明

本项目为技术架构原型。当前版本数据包含 Mock 生成数据 (source=mock) 和真实国会数据 (source=uscl, CC0-1.0)。任何基于该系统的分析结果仅供研究参考，不构成:

- 事实认定 (finding of fact)
- 法律判断 (legal judgment)
- 投资建议 (investment advice)
- 政治立场 (political position)

使用本系统的用户应自行承担相关风险与责任。
