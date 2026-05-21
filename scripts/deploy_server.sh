#!/bin/bash
# 腾讯云轻量服务器一键部署脚本
# 服务器IP: 1.117.70.20
# 运行方式: ssh root@1.117.70.20 然后执行此脚本

set -e

echo "=========================================="
echo "  Football Tools 云服务器部署脚本"
echo "  服务器: 腾讯云轻量应用服务器 (上海)"
echo "=========================================="

# 1. 更新系统
echo "[1/6] 更新系统..."
apt update && apt upgrade -y

# 2. 安装Python环境
echo "[2/6] 安装Python环境..."
apt install -y python3 python3-pip python3-venv

# 3. 安装必要工具
echo "[3/6] 安装必要工具..."
apt install -y git curl wget vim

# 4. 创建项目目录
echo "[4/6] 创建项目目录..."
mkdir -p /home/football_tools
mkdir -p /home/football_tools/logs
mkdir -p /home/football_tools/backups

# 5. 创建Python虚拟环境并安装依赖
echo "[5/6] 安装Python依赖..."
cd /home/football_tools
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install pandas requests beautifulsoup4 lxml numpy

# 6. 配置定时任务
echo "[6/6] 配置定时任务..."
(crontab -l 2>/dev/null; echo "# Football Tools 每日数据更新"; echo "0 3 * * * cd /home/football_tools && /home/football_tools/venv/bin/python scripts/daily_update.py >> logs/update.log 2>&1") | crontab -

# 7. 配置防火墙（如需要）
echo "[7/6] 配置防火墙..."
# 腾讯云轻量服务器默认安全组已开放SSH端口
# 如需开放其他端口，在腾讯云控制台配置安全组

# 完成
echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "项目目录: /home/football_tools"
echo "Python环境: /home/football_tools/venv"
echo ""
echo "下一步操作："
echo "1. 从本地上传数据:"
echo "   scp -r d:/football_tools/* root@1.117.70.20:/home/football_tools/"
echo ""
echo "2. SSH连接服务器:"
echo "   ssh root@1.117.70.20"
echo ""
echo "3. 激活Python环境:"
echo "   source /home/football_tools/venv/bin/activate"
echo ""
