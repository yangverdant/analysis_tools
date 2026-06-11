#!/bin/bash
set -e
source /opt/football_tools/venv/bin/activate

echo "[1/3] 安装Python依赖..."
cd /opt/football_tools
pip install -r backend/requirements.txt

echo "[2/3] 启动API服务..."
systemctl start football-analyst
sleep 3
systemctl status football-analyst --no-pager -l | head -15

echo "[3/3] 启动nginx..."
systemctl start nginx

echo ""
echo "=== 验证 ==="
sleep 2
curl -s http://localhost:8000/api/cycle/status | python3 -m json.tool 2>/dev/null || echo "API未响应"
echo ""
curl -s -o /dev/null -w "Frontend HTTP: %{http_code}\n" http://localhost/
echo ""
echo "=== 部署完成 ==="
echo "前端: http://1.117.70.20"
echo "API:  http://1.117.70.20/api/cycle/status"
