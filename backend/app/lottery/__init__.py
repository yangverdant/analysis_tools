"""
体彩分析模块

提供体彩数据采集、分析、预测、验证的完整功能
"""

from .routers.lottery import router as lottery_router

__all__ = ['lottery_router']
