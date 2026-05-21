# Git项目管理方案

## 方案选择

| 方案 | 可见性 | 适合场景 |
|------|--------|----------|
| 私有仓库 | 仅自己可见 | 数据敏感、个人项目 |
| 公开仓库 | 所有人可见 | 开源项目、分享学习 |

## 推荐方案：GitHub私有仓库

```
GitHub私有仓库（免费）
        │
        ├── 本地电脑 ──▶ git push ──▶ GitHub
        │
        └── 云服务器 ──▶ git pull ──▶ GitHub
```

## 操作步骤

### 1. 在GitHub创建私有仓库

1. 登录 https://github.com
2. 点击 New repository
3. 仓库名: football_tools
4. 选择 **Private**（私有）
5. 点击 Create repository

### 2. 本地初始化Git（Windows）

```powershell
# 进入项目目录
cd d:/football_tools

# 初始化Git
git init

# 创建.gitignore（排除大文件和敏感数据）
```

### 3. 云服务器克隆仓库

```bash
# SSH连接服务器
ssh root@1.117.70.20

# 安装Git
apt install git -y

# 克隆仓库（需要GitHub Token或SSH密钥）
git clone https://github.com/你的用户名/football_tools.git /home/football_tools

# 或使用SSH方式（更安全）
git clone git@github.com:你的用户名/football_tools.git /home/football_tools
```

### 4. 日常更新流程

**本地更新数据后：**
```bash
# 本地
cd d:/football_tools
git add .
git commit -m "更新2026解放者杯数据"
git push
```

**云服务器拉取更新：**
```bash
# 云服务器
cd /home/football_tools
git pull
```

## 自动同步方案

### 方案A：云服务器定时拉取

```bash
# 云服务器crontab
# 每小时检查更新
0 * * * * cd /home/football_tools && git pull >> /home/football_tools/logs/git.log 2>&1
```

### 方案B：GitHub Actions自动部署

```yaml
# .github/workflows/deploy.yml
name: Deploy to Server

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: 1.117.70.20
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /home/football_tools
            git pull
```

## 注意事项

1. **敏感数据**：不要提交密钥、密码等
2. **大文件**：CSV数据文件可以用Git LFS或单独存储
3. **分支管理**：main分支为稳定版本，dev分支为开发版本
