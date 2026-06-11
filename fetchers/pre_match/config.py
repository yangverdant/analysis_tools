"""赛前情报采集配置"""

# FIFA世界杯东道主(2026)
WC_HOSTS_2026 = ["Mexico", "Canada", "United States"]

# 高原城市(海拔>1500m)
HIGH_ALTITUDE_CITIES = {
    "Mexico City": 2240, "Bogota": 2640, "Quito": 2850, "La Paz": 3640,
    "Cusco": 3400, "Addis Ababa": 2355, "Nairobi": 1795, "Sanaa": 2300,
    "Johannesburg": 1753, "Denver": 1609, "Salt Lake City": 1300,
    "Guadalajara": 1566, "Toluca": 2680, "Puebla": 2135,
    "Sofia": 590, "Madrid": 667, "Bogota": 2640, "Quito": 2850,
}

# 球迷跨境效应: 地理邻近国家配对(主→客: 球迷比例估计)
CROSS_BORDER_FAN_PAIRS = {
    # 欧洲内部(近距离)
    ("Netherlands", "Belgium"): 0.15, ("Netherlands", "Germany"): 0.10,
    ("France", "Belgium"): 0.10, ("France", "Switzerland"): 0.08,
    ("Germany", "Austria"): 0.10, ("Germany", "Netherlands"): 0.10,
    ("England", "Ireland"): 0.12, ("England", "Wales"): 0.15,
    ("Spain", "Portugal"): 0.10, ("Italy", "Croatia"): 0.08,
    # 北非→欧洲(历史移民, 大量客场球迷)
    ("France", "Algeria"): 0.35, ("France", "Morocco"): 0.30,
    ("France", "Tunisia"): 0.25, ("France", "Ivory Coast"): 0.20,
    ("Netherlands", "Morocco"): 0.25, ("Netherlands", "Turkey"): 0.20,
    ("Netherlands", "Algeria"): 0.20, ("Netherlands", "Suriname"): 0.15,
    ("Belgium", "Morocco"): 0.30, ("Belgium", "Algeria"): 0.15,
    ("Spain", "Morocco"): 0.20, ("Spain", "Algeria"): 0.10,
    ("England", "Nigeria"): 0.15, ("England", "Ghana"): 0.15,
    ("Italy", "Albania"): 0.20, ("Germany", "Turkey"): 0.25,
    # 中东
    ("England", "Pakistan"): 0.10, ("Saudi Arabia", "Egypt"): 0.15,
}

# 友谊赛类型推断规则
FRIENDLY_TYPE_RULES = {
    "wc_warmup": {
        "desc": "世界杯热身赛",
        "home_motivation": "high",
        "away_motivation": "medium",
        "months": [5, 6],  # 5-6月世界杯前
        "competitions": ["friendly", "international"],
    },
    "post_season": {
        "desc": "赛季结束友谊赛",
        "home_motivation": "medium",
        "away_motivation": "low",
        "months": [5, 6, 7],
    },
    "pre_season": {
        "desc": "赛季前热身赛",
        "home_motivation": "medium",
        "away_motivation": "medium",
        "months": [7, 8],
    },
    "mid_season": {
        "desc": "赛季中友谊赛",
        "home_motivation": "low",
        "away_motivation": "low",
        "months": [9, 10, 11, 3],
    },
}

# 疲劳临界阈值
FATIGUE_THRESHOLDS = {
    "games_critical": 45,     # 赛季45+场 = 临界疲劳
    "games_high": 40,         # 40+场 = 高疲劳
    "games_moderate": 35,     # 35+场 = 中疲劳
    "cl_final_penalty": 2,    # 欧冠决赛额外+2级
    "nt_semi_penalty": 1,     # 国家队半决赛+1级
    "wc_days_before": 7,       # 世界杯前N天=临界窗口
}

# 伤病关键词(扩展zhibo8已有列表)
INJURY_KEYWORDS_EN = [
    "injured", "injury", "doubtful", "ruled out", "misses out",
    "unavailable", "not in squad", "rested", "knock", "strain",
    "hamstring", "ankle", "knee", "muscle", "calf", "groin",
    "ACL", "MCL", "concussion", "fracture", "surgery",
]

# 核心球员关键词(影响级别判断)
KEY_PLAYER_KEYWORDS = [
    "captain", "star", "key", "main", "top scorer", "playmaker",
    "goalkeeper", "striker", "主力", "核心", "队长", "头号",
]
