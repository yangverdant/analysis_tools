# 云服务器部署方案

## 部署架构

```
云服务器（轻量级）
├── /home/football_tools/          # 项目主目录
│   ├── data/                      # 原始数据（来自数据源）
│   ├── new_data/                  # 清洗后的标准化数据
│   ├── scripts/                   # 数据处理脚本
│   └── logs/                      # 运行日志
│
├── /home/football_tools/.git/     # Git版本控制
│
└── 定时任务                        # 自动数据采集/更新
```

## 部署步骤

### 1. 连接服务器

```bash
# SSH连接（Windows用PowerShell或Git Bash）
ssh root@你的服务器IP

# 或使用密钥连接
ssh -i ~/.ssh/your_key.pem root@你的服务器IP
```

### 2. 环境准备

```bash
# 更新系统
apt update && apt upgrade -y   # Ubuntu/Debian
# 或
yum update -y                   # CentOS

# 安装Python
apt install python3 python3-pip -y
# 或
yum install python3 python3-pip -y

# 安装必要的Python包
pip3 install pandas requests beautifulsoup4 lxml

# 安装Git
apt install git -y
# 或
yum install git -y
```

### 3. 项目部署

```bash
# 创建项目目录
mkdir -p /home/football_tools
cd /home/football_tools

# 方案A: 从本地上传（推荐）
# 在本地Windows执行：
scp -r d:/football_tools/* root@服务器IP:/home/football_tools/

# 方案B: 使用Git克隆（如果有远程仓库）
git clone https://github.com/your_repo/football_tools.git .

# 方案C: 使用rsync同步（更高效，支持增量）
rsync -avz --delete d:/football_tools/ root@服务器IP:/home/football_tools/
```

### 4. 配置定时任务

```bash
# 编辑crontab
crontab -e

# 添加定时任务示例：
# 每天凌晨3点更新数据
0 3 * * * cd /home/football_tools && python3 scripts/update_data.py >> logs/update.log 2>&1

# 每周一凌晨5点备份
0 5 * * 1 cd /home/football_tools && tar -czf logs/backup_$(date +\%Y\%m\%d).tar.gz new_data/
```

### 5. 数据同步策略

#### 本地 → 云端（上传）
```bash
# Windows PowerShell
# 同步整个项目
rsync -avz --delete d:/football_tools/ root@服务器IP:/home/football_tools/

# 只同步new_data目录
rsync -avz d:/football_tools/new_data/ root@服务器IP:/home/football_tools/new_data/
```

#### 云端 → 本地（下载）
```bash
# 下载最新数据
rsync -avz root@服务器IP:/home/football_tools/new_data/ d:/football_tools/new_data/
```

## 数据存储建议

### 轻量服务器存储方案

| 数据类型 | 存储位置 | 大小估算 |
|----------|----------|----------|
| 原始数据 data/ | 云服务器本地 | ~500MB |
| 清洗数据 new_data/ | 云服务器本地 | ~200MB |
| 脚本 scripts/ | 云服务器本地 | ~5MB |
| 备份数据 | OSS对象存储 | 按需 |

### OSS对象存储（可选）

如果数据量大，建议使用阿里云OSS或腾讯云COS：

```bash
# 安装ossutil工具
# 阿里云
wget https://gosspublic.alicdn.com/ossutil/1.7.14/ossutil64
chmod 755 ossutil64

# 配置
./ossutil64 config -e oss-cn-beijing.aliyuncs.com -i your_access_key -k your_secret_key

# 上传备份
./ossutil64 cp -r /home/football_tools/new_data/ oss://your_bucket/football_data/
```

## 安全建议

1. **SSH密钥登录**：禁用密码登录，使用密钥
2. **防火墙**：只开放必要端口（SSH 22）
3. **定期备份**：数据备份到OSS或本地
4. **日志监控**：记录所有数据更新操作

## 连接工具推荐

| 工具 | 用途 | Windows下载 |
|------|------|-------------|
| PuTTY | SSH终端 | putty.org |
| WinSCP | 文件传输 | winscp.net |
| VSCode Remote | 远程开发 | VSCode插件 |
| MobaXterm | 综合工具 | mobaxterm.mobatek.net |

## 下一步

1. 提供服务器IP和登录方式
2. 确认服务器操作系统（Ubuntu/CentOS）
3. 选择数据同步方案
4. 开始部署