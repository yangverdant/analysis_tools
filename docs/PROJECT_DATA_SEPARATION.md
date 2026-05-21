# 项目与数据分离方案

## 推荐架构

```
┌─────────────────────────────────────────────────────────────┐
│                        GitHub仓库                            │
│  football_tools (私有/公开)                                  │
│  ├── scripts/          # 脚本代码                            │
│  ├── docs/             # 文档                                │
│  ├── .gitignore        # 排除数据文件                        │
│  └── README.md         # 项目说明                            │
│                                                              │
│  不包含: data/, new_data/ (数据文件)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ git clone/pull
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      云服务器                                │
│  /home/football_tools/                                       │
│  ├── scripts/          # 代码（来自Git）                     │
│  ├── docs/             # 文档（来自Git）                     │
│  ├── data/             # 原始数据（本地存储/OSS）            │
│  ├── new_data/         # 清洗数据（本地存储/OSS）            │
│  ├── logs/             # 日志                                │
│  └── backups/          # 备份                                │
└─────────────────────────────────────────────────────────────┘
```

## 为什么分开？

| 项目代码 | 数据文件 |
|----------|----------|
| 体积小（几MB） | 体积大（几百MB~几GB） |
| 频繁修改 | 相对稳定 |
| 适合Git版本控制 | 不适合Git |
| 需要多人协作 | 只需要同步 |

## .gitignore 配置

```gitignore
# 数据文件（不提交到Git）
data/
new_data/
*.csv
*.xlsx

# 日志文件
logs/
*.log

# 配置文件（敏感信息）
config/secrets.json
.env

# Python
__pycache__/
*.pyc
venv/

# IDE
.idea/
.vscode/
*.swp

# 系统文件
.DS_Store
Thumbs.db
```

## 数据同步方案

### 方案1：rsync同步（推荐）

```powershell
# Windows → 云服务器 上传数据
rsync -avz d:/football_tools/data/ root@1.117.70.20:/home/football_tools/data/
rsync -avz d:/football_tools/new_data/ root@1.117.70.20:/home/football_tools/new_data/

# 云服务器 → Windows 下载数据
rsync -avz root@1.117.70.20:/home/football_tools/new_data/ d:/football_tools/new_data/
```

### 方案2：OSS对象存储

```
本地电脑 ──▶ ossutil ──▶ 阿里云OSS/腾讯云COS
                              │
                              ▼
                         云服务器
```

### 方案3：网盘同步

```
本地电脑 ──▶ 百度网盘/阿里云盘 ──▶ 云服务器挂载
```

## 目录结构最终方案

```
d:/football_tools/                  # 本地项目
├── .git/                           # Git仓库
├── .gitignore                      # 排除数据文件
├── scripts/                        # 脚本代码 ✓ Git管理
├── docs/                           # 文档 ✓ Git管理
├── README.md                       # 说明 ✓ Git管理
│
├── data/                           # 原始数据 ✗ 不同步Git
│   └── ... (CSV文件)
│
└── new_data/                       # 清洗数据 ✗ 不同步Git
    └── ... (CSV文件)


云服务器 /home/football_tools/
├── scripts/                        # git pull 更新
├── docs/                           # git pull 更新
├── data/                           # rsync/ossutil 同步
├── new_data/                       # rsync/ossutil 同步
└── logs/                           # 本地生成
```

## 完整部署流程

### 步骤1：创建GitHub仓库

```bash
# 在GitHub创建私有仓库 football_tools
# 不要勾选 README、.gitignore（本地已有）
```

### 步骤2：本地初始化

```powershell
cd d:/football_tools

# 创建.gitignore
# （内容见上方）

# 初始化并推送
git init
git add scripts/ docs/ README.md .gitignore
git commit -m "初始化项目"
git branch -M main
git remote add origin https://github.com/你的用户名/football_tools.git
git push -u origin main
```

### 步骤3：云服务器部署

```bash
# SSH连接
ssh root@1.117.70.20

# 安装环境
apt update && apt install -y git python3 python3-pip

# 克隆代码
git clone https://github.com/你的用户名/football_tools.git /home/football_tools

# 创建数据目录
cd /home/football_tools
mkdir -p data new_data logs backups

# 安装Python依赖
pip3 install pandas requests beautifulsoup4 lxml
```

### 步骤4：同步数据

```powershell
# 本地Windows执行，上传数据到云服务器
scp -r d:/football_tools/data/* root@1.117.70.20:/home/football_tools/data/
scp -r d:/football_tools/new_data/* root@1.117.70.20:/home/football_tools/new_data/
```

## 日常更新流程

```
1. 更新代码（本地 → GitHub → 云服务器）
   本地: git add scripts/ && git commit -m "新增爬虫" && git push
   云服务器: cd /home/football_tools && git pull

2. 更新数据（本地 ↔ 云服务器）
   上传: rsync -avz d:/football_tools/new_data/ root@1.117.70.20:/home/football_tools/new_data/
   下载: rsync -avz root@1.117.70.20:/home/football_tools/new_data/ d:/football_tools/new_data/
```
