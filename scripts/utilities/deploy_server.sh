#!/bin/bash
# 足球分析师系统 — 腾讯云生产部署
# 服务器: 1.117.70.20 (上海轻量应用服务器)
# 用法: ssh root@1.117.70.20 然后执行此脚本
#
# 包含: Python venv + FastAPI + nginx + systemd + crontab + 日志轮转

set -e

SERVER_IP="1.117.70.20"
APP_DIR="/opt/football_tools"
VENV_DIR="$APP_DIR/venv"
DATA_DIR="$APP_DIR/data"
LOG_DIR="$APP_DIR/logs"
CONFIG_DIR="$APP_DIR/config"
BACKUP_DIR="$APP_DIR/backups"

echo "=========================================="
echo "  足球分析师系统 — 生产部署"
echo "  服务器: $SERVER_IP"
echo "=========================================="

# ─── 1. 系统基础 ───
echo "[1/8] 更新系统 + 安装依赖..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv \
    nginx git curl wget vim unzip \
    certbot python3-certbot-nginx \
    logrotate

# ─── 2. 创建目录 ───
echo "[2/8] 创建项目目录..."
mkdir -p $APP_DIR $DATA_DIR $LOG_DIR $CONFIG_DIR $BACKUP_DIR

# ─── 3. Python虚拟环境 ───
echo "[3/8] 创建Python虚拟环境..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv $VENV_DIR
fi
source $VENV_DIR/bin/activate
pip install --upgrade pip

# 安装项目依赖
if [ -f "$APP_DIR/backend/requirements.txt" ]; then
    pip install -r $APP_DIR/backend/requirements.txt
else
    echo "[警告] requirements.txt不存在, 安装核心依赖..."
    pip install fastapi uvicorn pandas numpy scikit-learn xgboost \
        python-multipart anthropic openai pyyaml requests beautifulsoup4 lxml
fi

# ─── 4. 配置文件 ───
echo "[4/8] 检查配置文件..."
if [ ! -f "$CONFIG_DIR/api_keys.yaml" ]; then
    cat > $CONFIG_DIR/api_keys.yaml << 'YAML_EOF'
# API密钥配置 — 请填入真实Key
anthropic:
  api_key: ""
  base_url: ""

openai:
  api_key: ""
  base_url: ""

push:
  serverchan_sendkey: ""
  email_smtp_host: ""
  email_smtp_port: 465
  email_user: ""
  email_password: ""
  email_to: ""
YAML_EOF
    echo "[提示] 请编辑 $CONFIG_DIR/api_keys.yaml 填入API Key"
fi

# ─── 5. 数据库 ───
echo "[5/8] 检查数据库..."
if [ ! -f "$DATA_DIR/football_v2.db" ]; then
    echo "[警告] 数据库不存在, 需要从本地上传:"
    echo "  scp d:/football_tools/data/football_v2.db root@$SERVER_IP:$DATA_DIR/"
fi

# ─── 6. systemd服务 ───
echo "[6/8] 配置systemd服务..."
cat > /etc/systemd/system/football-analyst.service << 'SYSTEMD_EOF'
[Unit]
Description=Football Analyst API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/football_tools
Environment=PATH=/opt/football_tools/venv/bin:/usr/bin:/bin
Environment=DB_PATH=/opt/football_tools/data/football_v2.db
Environment=TZ=Asia/Shanghai
ExecStart=/opt/football_tools/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=append:/opt/football_tools/logs/uvicorn.log
StandardError=append:/opt/football_tools/logs/uvicorn_error.log

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

systemctl daemon-reload
systemctl enable football-analyst
if systemctl is-active --quiet football-analyst; then
    systemctl restart football-analyst
    echo "[OK] 服务已重启"
else
    echo "[提示] 服务已配置, 启动前需先上传项目代码和数据库"
fi

# ─── 7. nginx配置 ───
echo "[7/8] 配置nginx..."
cat > /etc/nginx/sites-available/football-analyst << 'NGINX_EOF'
server {
    listen 80;
    server_name _;

    # 前端静态文件
    location / {
        root /opt/football_tools/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }

    # API反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # 静态资源长缓存
    location /assets/ {
        root /opt/football_tools/frontend/dist;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 日志
    access_log /opt/football_tools/logs/nginx_access.log;
    error_log /opt/football_tools/logs/nginx_error.log;
}
NGINX_EOF

# 启用站点
ln -sf /etc/nginx/sites-available/football-analyst /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx && systemctl enable nginx

# ─── 8. 日志轮转 + 定时任务 ───
echo "[8/8] 配置日志轮转和定时任务..."

# 日志轮转
cat > /etc/logrotate.d/football-analyst << 'LOGROTATE_EOF'
/opt/football_tools/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        systemctl reload football-analyst > /dev/null 2>&1 || true
    endscript
}
LOGROTATE_EOF

# crontab: 日循环
(crontab -l 2>/dev/null | grep -v football_tools; cat << 'CRON_EOF'
# Football Analyst 日循环
# 6:00 自感知
0 6 * * * cd /opt/football_tools && /opt/football_tools/venv/bin/python -m backend.app.core.daily_runner --mode perceive >> /opt/football_tools/logs/cron.log 2>&1
# 7:00 采集+分析+推送
0 7 * * * cd /opt/football_tools && /opt/football_tools/venv/bin/python -m backend.app.core.daily_runner --mode morning >> /opt/football_tools/logs/cron.log 2>&1
# 14:00 CLV更新
0 14 * * * cd /opt/football_tools && /opt/football_tools/venv/bin/python -m backend.app.core.daily_runner --mode clv >> /opt/football_tools/logs/cron.log 2>&1
# 次日6:30 复盘
30 6 * * * cd /opt/football_tools && /opt/football_tools/venv/bin/python -m backend.app.core.daily_runner --mode validate >> /opt/football_tools/logs/cron.log 2>&1
CRON_EOF
) | crontab -

# ─── 完成 ───
echo ""
echo "=========================================="
echo "  部署完成!"
echo "=========================================="
echo ""
echo "项目目录: $APP_DIR"
echo "Python:   $VENV_DIR"
echo "数据库:   $DATA_DIR/football_v2.db"
echo "日志:     $LOG_DIR"
echo ""
echo "=== 下一步 ==="
echo ""
echo "1. 上传项目代码:"
echo "   rsync -avz --exclude='data/*.db' --exclude='__pycache__' --exclude='.git' \\"
echo "     d:/football_tools/ root@$SERVER_IP:$APP_DIR/"
echo ""
echo "2. 上传数据库:"
echo "   scp d:/football_tools/data/football_v2.db root@$SERVER_IP:$DATA_DIR/"
echo ""
echo "3. 编辑API配置:"
echo "   ssh root@$SERVER_IP"
echo "   vim $CONFIG_DIR/api_keys.yaml"
echo ""
echo "4. 启动服务:"
echo "   systemctl start football-analyst"
echo "   systemctl status football-analyst"
echo ""
echo "5. 查看日志:"
echo "   tail -f $LOG_DIR/uvicorn.log"
echo ""
echo "6. (可选) 配置HTTPS:"
echo "   certbot --nginx -d your-domain.com"
echo ""
echo "前端访问: http://$SERVER_IP"
echo "API文档:  http://$SERVER_IP/api/docs"
