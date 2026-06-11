#!/bin/bash
set -e

echo "============================================================"
echo "  足球分析师系统 — 一键启动"
echo "============================================================"
echo

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "[错误] Docker未安装"
    echo "请先安装Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "[错误] docker-compose未安装"
    exit 1
fi

# 使用docker compose或docker-compose
COMPOSE="docker-compose"
if docker compose version &> /dev/null 2>&1; then
    COMPOSE="docker compose"
fi

# 检查.env文件
if [ ! -f .env ]; then
    echo "[创建] .env配置文件"
    cat > .env << 'EOF'
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_BASE_URL=
EOF
    echo "[提示] 请编辑 .env 填入API Key后重新运行"
    exit 0
fi

# 构建并启动
echo "[启动] 构建Docker镜像..."
$COMPOSE build

echo "[启动] 启动服务..."
$COMPOSE up -d

echo
echo "============================================================"
echo "  系统已启动!"
echo "  前端: http://localhost"
echo "  后端API: http://localhost:8000/docs"
echo "============================================================"
echo
echo "查看日志: $COMPOSE logs -f"
echo "停止服务: $COMPOSE down"
