"""
core/ — 日循环核心模块(独立入口)

独立运行，不依赖FastAPI。
入口: python -m core.daily_runner --mode <mode>

注意: 正式的日循环入口在 backend/app/core/daily_runner.py
此目录为备用独立入口，使用CompetitionRuleEngine等核心组件。
"""