"""
Odds Feed API 配置
"""

RAPIDAPI_KEY = "36ce000ce1msh435e51a1d194fafp1883eejsn26b0639b7066"  # 新账号（2026-05）
RAPIDAPI_KEY_OLD = "232de9f410msh8da4a38f557b694p1d2d4fjsn978df1ba1263"  # 旧账号，下月配额恢复后可用
RAPIDAPI_HOST = "odds-feed.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}/api/v1"
REQUEST_TIMEOUT = 20

# tournament_id → standard league name (用户从oddsfe.com验证确认)
MAJOR_TOURNAMENTS = {
    430: "Premier League",
    560: "Bundesliga",
    719: "Serie A",
    1146: "LaLiga",
    # 扩展联赛
    431: "Championship",
    432: "League One",
    561: "Bundesliga 2",
    720: "Serie B",
    1147: "LaLiga2",
    862: "Eredivisie",
    763: "J1 League",
    1265: "MLS",
    322: "China Super League",
}
# Ligue 1 ID待确认 (之前445/540都不对)

# HugeAPI入口（与RapidAPI配额独立）
HUGEAPI_BASE_URL = "https://odds-feed-api.hgapi.top"
HUGEAPI_KEY = "1bef4599c8a1442d8cbb7f30e9b61499"

# 球队名映射: Odds Feed名 → 标准名 (常见差异)
TEAM_NAME_MAP = {
    "Tottenham Hotspur": "Tottenham",
    "West Ham United": "West Ham",
    "Brighton & Hove Albion": "Brighton",
    "Wolverhampton Wanderers": "Wolverhampton",
    "Newcastle United": "Newcastle",
    "Aston Villa": "Aston Villa",
    "Nottingham Forest": "Nottingham Forest",
    "Crystal Palace": "Crystal Palace",
    "Bournemouth": "Bournemouth",
    "Manchester United": "Manchester United",
    "Manchester City": "Manchester City",
    "Leicester City": "Leicester City",
    "Bayern Munich": "Bayern Munich",
    "Paris Saint-Germain": "Paris Saint-Germain",
    "Real Madrid": "Real Madrid",
    "Atletico Madrid": "Atletico Madrid",
    "Borussia Dortmund": "Borussia Dortmund",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "VfB Stuttgart": "Stuttgart",
    "VfL Wolfsburg": "Wolfsburg",
    "FC Augsburg": "Augsburg",
    "1. FC Union Berlin": "Union Berlin",
    "SC Freiburg": "Freiburg",
    "1. FSV Mainz 05": "Mainz 05",
    "TSG Hoffenheim": "Hoffenheim",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "Borussia Monchengladbach": "Monchengladbach",
    "AS Roma": "Roma",
    "Inter Milan": "Inter",
    "AC Milan": "Milan",
    "Lazio Rome": "Lazio",
    "SSC Napoli": "Napoli",
    "FC Barcelona": "Barcelona",
    "Athletic Bilbao": "Athletic Bilbao",
    "Sevilla FC": "Sevilla",
    "RC Celta de Vigo": "Celta Vigo",
    "RC Deportivo Alaves": "Alaves",
    "Real Betis Balompie": "Real Betis",
    "CA Osasuna": "Osasuna",
    "Villarreal CF": "Villarreal",
    "UD Las Palmas": "Las Palmas",
    "Getafe CF": "Getafe",
    "RCD Mallorca": "Mallorca",
    "Real Sociedad": "Real Sociedad",
    "Valencia CF": "Valencia",
    "CD Leganes": "Leganes",
    "RCD Espanyol": "Espanyol",
    "Girona FC": "Girona",
}