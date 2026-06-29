"""Match intelligence package.

This module is the new match-driven orchestration layer. It keeps the
existing collectors and analytics intact, but gives them a common job,
requirement, artifact, and package model.
"""

from .routes import router as intelligence_router

__all__ = ["intelligence_router"]
