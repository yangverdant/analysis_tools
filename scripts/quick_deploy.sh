#!/bin/bash
# 云服务器快速部署脚本
# 服务器: 1.117.70.20 (腾讯云轻量应用服务器)
# 执行方式: ssh root@1.117.70.20 然后运行此脚本

set -e

echo "=========================================="
echo "  Football Tools 云服务器部署"
echo "=========================================="

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
  echo "请使用root用户执行此脚本"
  exit 1
fi

# 1. 更新系统
echo "[1/5] 更新系统..."
apt update && apt upgrade -y

# 2. 安装依赖
echo "[2/5] 安装依赖..."
apt install -y git python3 python3-pip

# 3. 克隆代码
echo "[3/5] 克隆代码..."
if [ -d "/home/football_tools" ]; then
  echo "目录已存在，跳过克隆"
else
  git clone https://github.com/yangverdant/analysis_tools.git /home/football_tools
fi

# 4. 创建数据目录
echo "[4/5] 创建数据目录..."
cd /home/football_tools
mkdir -p data new_data logs backups

# 5. 安装Python依赖
echo "[5/5] 安装Python依赖..."
pip3 install pandas requests beautifulsoup4 lxml numpy

# 完成
echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "项目目录: /home/football_tools"
echo ""
echo "下一步："
echo "1. 从本地上传数据:"
echo "   scp -r d:/football_tools/data/* root@1.117.70.20:/home/football_tools/data/"
echo "   scp -r d:/football_tools/new_data/* root@1.117.70.20:/home/football_tools/new_data/"
echo ""
echo "2. 更新代码:"
echo "   cd /home/football_tools && git pull"
echo ""
