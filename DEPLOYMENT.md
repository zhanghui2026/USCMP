# 部署指南

本指南帮助你将美国国会利益关联图谱系统部署到生产环境。

## 目录

- [快速部署](#快速部署)
- [云服务器部署](#云服务器部署)
- [免费平台部署](#免费平台部署)
- [本地开发环境](#本地开发环境)
- [环境变量配置](#环境变量配置)
- [常见问题](#常见问题)

---

## 快速部署

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 内存

### 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/daazha/USCMP.git
cd USCMP

# 2. 复制环境配置
cp .env.example .env

# 3. 启动所有服务
docker compose up --build -d

# 4. 初始化数据 (首次运行)
docker compose exec backend python3 -m app.etl.import_real_members
docker compose exec backend python3 -m app.etl.import_fec_data
docker compose exec backend python3 -m app.etl.import_holdings
docker compose exec backend python3 -m app.etl.import_congress_profiles

# 5. 访问应用
# 前端: http://localhost:3000
# API 文档: http://localhost:8000/docs
# Neo4j 浏览器: http://localhost:7474
```

---

## 云服务器部署

### 推荐配置

| 项目 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 硬盘 | 40 GB SSD | 80 GB SSD |
| 带宽 | 5 Mbps | 10 Mbps |
| 操作系统 | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### 阿里云/腾讯云部署步骤

#### 1. 购买并配置服务器

```bash
# SSH 连接到服务器
ssh root@your-server-ip

# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

#### 2. 部署项目

```bash
# 克隆项目
cd /opt
git clone https://github.com/daazha/USCMP.git
cd USCMP

# 配置环境变量
cp .env.example .env
nano .env  # 修改密码和配置

# 启动服务
docker compose up --build -d

# 初始化数据
docker compose exec backend python3 -m app.etl.import_real_members
docker compose exec backend python3 -m app.etl.import_fec_data
docker compose exec backend python3 -m app.etl.import_holdings
docker compose exec backend python3 -m app.etl.import_congress_profiles
```

#### 3. 配置 Nginx 反向代理

```bash
# 安装 Nginx
apt install nginx -y

# 创建配置文件
cat > /etc/nginx/sites-available/congress << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API 文档
    location /docs {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }

    # OpenAPI
    location /openapi.json {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }
}
EOF

# 启用配置
ln -s /etc/nginx/sites-available/congress /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

#### 4. 配置 HTTPS (Let's Encrypt)

```bash
# 安装 Certbot
apt install certbot python3-certbot-nginx -y

# 获取证书
certbot --nginx -d your-domain.com

# 自动续期
crontab -e
# 添加: 0 0 1 * * certbot renew --quiet
```

### AWS EC2 部署

#### 1. 启动实例

- 选择 Ubuntu 22.04 LTS AMI
- 实例类型: t3.medium (2 vCPU, 4 GB RAM)
- 存储: 50 GB gp3
- 安全组: 开放 80, 443, 22 端口

#### 2. 连接并部署

```bash
# SSH 连接
ssh -i your-key.pem ubuntu@your-ec2-ip

# 后续步骤同上
```

---

## 免费平台部署

### 方案一: Vercel + Railway

#### 前端部署到 Vercel

1. Fork 项目到你的 GitHub
2. 访问 [vercel.com](https://vercel.com)
3. 导入 GitHub 仓库
4. 配置:
   - Framework Preset: Vite
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
5. 添加环境变量:
   ```
   VITE_API_BASE_URL=https://your-backend-url.railway.app
   ```

#### 后端部署到 Railway

1. 访问 [railway.app](https://railway.app)
2. 创建新项目 → Deploy from GitHub
3. 选择仓库，Root Directory 设置为 `backend`
4. 添加 PostgreSQL 和 Neo4j 服务
5. 配置环境变量:
   ```
   POSTGRES_HOST=your-postgres-host
   POSTGRES_DB=congress_graph
   POSTGRES_USER=congress_user
   POSTGRES_PASSWORD=your-password
   NEO4J_URI=bolt://your-neo4j-host:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your-password
   ```

### 方案二: Render (全栈)

1. 访问 [render.com](https://render.com)
2. 创建 New Blueprint
3. 连接 GitHub 仓库
4. Render 会自动检测 `render.yaml` (需要创建)

创建 `render.yaml`:

```yaml
services:
  - type: web
    name: congress-backend
    runtime: python
    rootDir: backend
    buildCommand: pip install -e .
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: POSTGRES_HOST
        fromDatabase:
          name: congress-db
          property: host
      - key: POSTGRES_DB
        fromDatabase:
          name: congress-db
          property: database
      - key: POSTGRES_USER
        fromDatabase:
          name: congress-db
          property: user
      - key: POSTGRES_PASSWORD
        fromDatabase:
          name: congress-db
          property: password

  - type: web
    name: congress-frontend
    runtime: node
    rootDir: frontend
    buildCommand: npm install && npm run build
    staticPublishPath: ./dist
    envVars:
      - key: VITE_API_BASE_URL
        value: https://congress-backend.onrender.com

databases:
  - name: congress-db
    databaseName: congress_graph
    user: congress_user
```

### 方案三: Netlify + Supabase

#### 前端部署到 Netlify

1. 访问 [netlify.com](https://netlify.com)
2. 导入 GitHub 仓库
3. 配置:
   - Base directory: `frontend`
   - Build command: `npm run build`
   - Publish directory: `frontend/dist`

#### 后端使用 Supabase

1. 访问 [supabase.com](https://supabase.com)
2. 创建新项目
3. 获取数据库连接信息
4. 部署后端到 Railway 或 Render

---

## 本地开发环境

### 前置要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 15
- Neo4j 5

### 启动步骤

```bash
# 1. 启动数据库
docker compose up postgres neo4j -d

# 2. 启动后端
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -e .
POSTGRES_HOST=localhost uvicorn app.main:app --reload --port 8000

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
```

---

## 环境变量配置

### .env.example

```bash
# PostgreSQL
POSTGRES_DB=congress_graph
POSTGRES_USER=congress_user
POSTGRES_PASSWORD=your-secure-password
POSTGRES_HOST=postgres

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password
NEO4J_URI=bolt://neo4j:7687

# Backend
APP_ENV=production
LOG_LEVEL=info

# Frontend (build time)
VITE_API_BASE_URL=http://localhost:8000
```

### 生产环境建议

1. **修改默认密码**: 使用强密码
2. **限制数据库访问**: 只允许内网访问
3. **配置防火墙**: 只开放必要端口
4. **定期备份**: 配置数据库自动备份
5. **监控日志**: 使用 Docker 日志或 ELK

---

## 常见问题

### Q: 内存不足怎么办？

```bash
# 增加 swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Q: 如何更新项目？

```bash
cd /opt/USCMP
git pull origin master
docker compose down
docker compose up --build -d
```

### Q: 如何备份数据库？

```bash
# 备份 PostgreSQL
docker compose exec postgres pg_dump -U congress_user congress_graph > backup_$(date +%Y%m%d).sql

# 恢复
docker compose exec -T postgres psql -U congress_user congress_graph < backup_20240101.sql
```

### Q: 如何查看日志？

```bash
# 查看所有服务日志
docker compose logs -f

# 查看特定服务
docker compose logs -f backend
docker compose logs -f frontend
```

### Q: 端口被占用怎么办？

```bash
# 查看占用端口的进程
lsof -i :3000
lsof -i :8000

# 修改 docker-compose.yml 中的端口映射
ports:
  - "3001:3000"  # 改为其他端口
```

---

## 性能优化

### 生产环境优化

1. **启用 Gzip 压缩**
2. **配置 CDN 加速静态资源**
3. **使用 Redis 缓存**
4. **配置数据库连接池**
5. **启用 HTTP/2**

### Docker 优化

```bash
# 清理未使用的资源
docker system prune -a

# 查看资源使用
docker stats
```

---

## 监控和维护

### 健康检查

```bash
# 检查服务状态
docker compose ps

# 检查 API 健康
curl http://localhost:8000/api/health
```

### 日志轮转

创建 `/etc/logrotate.d/docker`:

```
/var/lib/docker/containers/*/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

---

## 技术支持

如有问题，请提交 GitHub Issue: https://github.com/daazha/USCMP/issues
