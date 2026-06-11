#!/bin/bash
set -e

echo "[1/7] 安装系统依赖..."
apt update
apt install -y python3-pip python3-venv nginx git curl logrotate

echo "[2/7] 创建项目目录..."
mkdir -p /opt/football_tools/{data,logs,config,backups,frontend/dist}

echo "[3/7] 创建Python虚拟环境..."
python3 -m venv /opt/football_tools/venv
source /opt/football_tools/venv/bin/activate
pip install --upgrade pip

echo "[4/7] 等待代码上传后安装依赖..."
if [ -f /opt/football_tools/backend/requirements.txt ]; then
    pip install -r /opt/football_tools/backend/requirements.txt
    echo "  依赖安装完成"
else
    echo "  requirements.txt不存在, 等上传代码后再装"
fi

echo "[5/7] 配置systemd服务..."
cat > /etc/systemd/system/football-analyst.service << 'EOF'
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
ExecStart=/opt/football_tools/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5
StandardOutput=append:/opt/football_tools/logs/uvicorn.log
StandardError=append:/opt/football_tools/logs/uvicorn_error.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable football-analyst

echo "[6/7] 配置nginx..."
cat > /etc/nginx/sites-available/football-analyst << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        root /opt/football_tools/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
        expires 1h;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    location /assets/ {
        root /opt/football_tools/frontend/dist;
        expires 30d;
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_min_length 1000;

    access_log /opt/football_tools/logs/nginx_access.log;
    error_log /opt/football_tools/logs/nginx_error.log;
}
EOF

ln -sf /etc/nginx/sites-available/football-analyst /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable nginx

echo "[7/7] 配置日志轮转..."
cat > /etc/logrotate.d/football-analyst << 'EOF'
/opt/football_tools/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
EOF

echo ""
echo "=== 基础环境部署完成 ==="
echo "下一步: 上传项目代码和数据库"
