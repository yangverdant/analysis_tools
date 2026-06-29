#!/usr/bin/env python3
"""
启动FastAPI服务器
"""
import os
import sys

import uvicorn

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

# Support both backend.app.* and legacy app.* imports in every launch mode.
for path in (PROJECT_ROOT, BACKEND_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

if __name__ == "__main__":
    port = int(os.environ.get("BACKEND_PORT", "8000"))
    host = os.environ.get("BACKEND_HOST", "127.0.0.1")

    print("=" * 60)
    print("足球数据分析API服务器")
    print("=" * 60)
    print()
    print(f"API文档: http://localhost:{port}/docs")
    print(f"交互文档: http://localhost:{port}/redoc")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)

    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=[os.path.join(BACKEND_DIR, "app")],
    )