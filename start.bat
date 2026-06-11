@echo off
chcp 65001 >nul 2>&1
echo ============================================================
echo   足球分析师系统 — 一键启动
echo ============================================================
echo.

REM 检查Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker未安装或未启动
    echo 请先安装Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM 检查.env文件
if not exist .env (
    echo [创建] .env配置文件
    (
        echo ANTHROPIC_API_KEY=your_key_here
        echo ANTHROPIC_BASE_URL=
    ) > .env
    echo [提示] 请编辑 .env 填入API Key后重新运行
    pause
    exit /b 0
)

REM 构建并启动
echo [启动] 构建Docker镜像...
docker-compose build
if errorlevel 1 (
    echo [错误] Docker构建失败
    pause
    exit /b 1
)

echo [启动] 启动服务...
docker-compose up -d
if errorlevel 1 (
    echo [错误] Docker启动失败
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   系统已启动!
echo   前端: http://localhost
echo   后端API: http://localhost:8000/docs
echo ============================================================
echo.
echo 查看日志: docker-compose logs -f
echo 停止服务: docker-compose down
pause
