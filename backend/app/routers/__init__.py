"""
Routers Package
拆分后的路由模块
"""

from .matches import router as matches_router
from .teams import router as teams_router
from .leagues import router as leagues_router
from .cups import router as cups_router
from .sync import router as sync_router
from .rankings import router as rankings_router

__all__ = [
    'matches_router',
    'teams_router',
    'leagues_router',
    'cups_router',
    'sync_router',
    'rankings_router'
]