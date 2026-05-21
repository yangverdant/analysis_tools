#!/usr/bin/env python3
"""
启动FastAPI服务器
"""
import uvicorn
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=" * 60)
    print("足球数据分析API服务器")
    print("=" * 60)
    print()
    print("API文档: http://localhost:8000/docs")
    print("交互文档: http://localhost:8000/redoc")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=18888,
        reload=True,
        reload_dirs=[os.path.join(os.path.dirname(__file__), "app")]
    )
