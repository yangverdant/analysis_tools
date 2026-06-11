"""FIFA World Ranking fetcher configuration.

Data sources:
- Static ranking data (built-in, updated monthly)
- FIFA official ranking page (Playwright, optional)
"""
import os

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_MODULE_DIR, 'data')

FIFA_BASE_URL = "https://www.fifa.com/fifa-world-ranking/men"
REQUEST_TIMEOUT = 30

# Confederation strength bonus (used for cross-confederation Elo calibration)
CONFEDERATION_STRENGTH = {
    "UEFA": 1.00,
    "CONMEBOL": 0.95,
    "CONCACAF": 0.80,
    "CAF": 0.75,
    "AFC": 0.70,
    "OFC": 0.50,
}