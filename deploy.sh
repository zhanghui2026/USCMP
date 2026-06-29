#!/bin/bash
set -e

usage() {
    echo "USCMP 部署脚本"
    echo "  用法: ./deploy.sh [start|stop|restart|init|logs]"
    echo "  start  启动 Docker Compose 服务"
    echo "  stop   停止服务"
    echo "  init   初始化数据（导入议员/FEC/持股/档案）"
    echo "  logs   查看日志"
    exit 0
}

start() {
    echo "启动服务..."
    docker compose up --build -d
    echo "前端: http://localhost:3000"
    echo "API:  http://localhost:8000/docs"
}

stop() {
    echo "停止服务..."
    docker compose down
}

init() {
    echo "初始化数据..."
    docker compose exec backend python3 -m app.etl.import_real_members
    docker compose exec backend python3 -m app.etl.import_fec_data
    echo "数据初始化完成。"
}

case "${1:-help}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop && start ;;
    init)    init ;;
    logs)    docker compose logs -f ;;
    help|*)  usage ;;
esac