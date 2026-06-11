"""
API入口 — 代理到main.py的统一FastAPI应用

此文件保留向后兼容性。
所有路由已迁移到 main.py，使用 /api/v1/ 前缀。
"""

from backend.app.main import app

# api.py 的 /api/ 前缀端点已全部由 main.py 的 /api/v1/ 路由覆盖
# 如需旧路径兼容，可在main.py中添加重定向
