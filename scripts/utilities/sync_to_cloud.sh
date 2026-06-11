#!/bin/bash
# 本地→云服务器 一键同步部署
# 用法: 在本地Windows Git Bash中运行
#   bash scripts/utilities/sync_to_cloud.sh

set -e

SERVER_IP="1.117.70.20"
SERVER_USER="root"
REMOTE_DIR="/opt/football_tools"

echo "=== 同步项目到云服务器 $SERVER_IP ==="

# 1. 同步代码(排除大文件和缓存)
echo "[1/3] 同步项目代码..."
rsync -avz --progress \
    --exclude='data/*.db' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='*.pyc' \
    --exclude='logs/' \
    --exclude='venv/' \
    --exclude='.env' \
    ./ ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/

# 2. 同步数据库(单独传, 大文件)
echo "[2/3] 同步数据库..."
rsync -avz --progress \
    data/football_v2.db ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/data/

# 3. 重启服务
echo "[3/3] 重启服务..."
ssh ${SERVER_USER}@${SERVER_IP} << 'REMOTE_EOF'
cd /opt/football_tools

# 安装/更新Python依赖
source venv/bin/activate
pip install -r backend/requirements.txt -q

# 重启
systemctl restart football-analyst
sleep 2
systemctl status football-analyst --no-pager -l | head -15

# 检查
curl -s http://localhost:8000/api/cycle/status | python3 -m json.tool 2>/dev/null || echo "API未响应, 检查日志: tail -f /opt/football_tools/logs/uvicorn_error.log"
REMOTE_EOF

echo ""
echo "=== 同步完成 ==="
echo "前端: http://$SERVER_IP"
echo "API:  http://$SERVER_IP/api/docs"
