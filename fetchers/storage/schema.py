"""
统一存储表结构定义

新数据库文件: data/unified_football.db (不覆盖原有 football_v2.db)

核心设计:
- matches 表: 以match_key为主键，存储比赛的锚定信息
- match_data 表: 每个源的每种数据类型一条记录，JSON存储详情
- 其他表: standings, players, injuries, news, weather, fetch_log
"""

# SQL建表语句
SCHEMA_SQL = """
-- 比赛主表：所有源的锚点
CREATE TABLE IF NOT EXISTS matches (
    match_key TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    time TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    league TEXT,
    league_standard TEXT,
    season TEXT,
    status TEXT DEFAULT 'scheduled',
    home_score INTEGER,
    away_score INTEGER,
    venue TEXT,
    referee TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 比赛扩展数据：带源标签
CREATE TABLE IF NOT EXISTS match_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_key TEXT NOT NULL,
    source TEXT NOT NULL,
    data_type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(match_key, source, data_type)
);

-- 积分榜
CREATE TABLE IF NOT EXISTS standings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league TEXT NOT NULL,
    league_standard TEXT,
    season TEXT,
    team TEXT NOT NULL,
    team_standard TEXT,
    source TEXT NOT NULL,
    data_json TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(league_standard, season, team_standard, source)
);

-- 球员
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    team_standard TEXT,
    player_name TEXT NOT NULL,
    source TEXT NOT NULL,
    data_json TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(team_standard, player_name, source)
);

-- 伤病
CREATE TABLE IF NOT EXISTS injuries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    team_standard TEXT,
    player_name TEXT NOT NULL,
    date TEXT,
    league TEXT,
    source TEXT NOT NULL,
    data_json TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(team_standard, player_name, source)
);

-- 新闻
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    date TEXT,
    matched_teams TEXT,
    data_json TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 天气
CREATE TABLE IF NOT EXISTS weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_key TEXT,
    city TEXT NOT NULL,
    date TEXT NOT NULL,
    source TEXT NOT NULL,
    data_json TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(match_key, source)
);

-- 采集日志
CREATE TABLE IF NOT EXISTS fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetcher TEXT NOT NULL,
    func_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    status TEXT NOT NULL,
    record_count INTEGER DEFAULT 0,
    error_msg TEXT,
    started_at TEXT,
    finished_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(home_team);
CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(away_team);
CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_standard);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_match_data_key ON match_data(match_key);
CREATE INDEX IF NOT EXISTS idx_match_data_type ON match_data(data_type);
CREATE INDEX IF NOT EXISTS idx_standings_league ON standings(league_standard);
CREATE INDEX IF NOT EXISTS idx_standings_season ON standings(season);
CREATE INDEX IF NOT EXISTS idx_injuries_team ON injuries(team_standard);
CREATE INDEX IF NOT EXISTS idx_injuries_date ON injuries(date);
CREATE INDEX IF NOT EXISTS idx_news_date ON news(date);
CREATE INDEX IF NOT EXISTS idx_news_source ON news(source);
CREATE INDEX IF NOT EXISTS idx_weather_match ON weather(match_key);
CREATE INDEX IF NOT EXISTS idx_fetch_log_fetcher ON fetch_log(fetcher);
"""

# 表名 → 主键映射
TABLE_KEYS = {
    "matches": "match_key",
    "match_data": ("match_key", "source", "data_type"),
    "standings": ("league_standard", "season", "team_standard", "source"),
    "players": ("team_standard", "player_name", "source"),
    "injuries": ("team_standard", "player_name", "source"),
    "weather": ("match_key", "source"),
}

# 数据类型 → 存储表映射
DATA_TYPE_TO_TABLE = {
    "match": "match_data",
    "odds": "match_data",
    "prediction": "match_data",
    "lineup": "match_data",
    "standing": "standings",
    "player": "players",
    "injury": "injuries",
    "news": "news",
    "weather": "weather",
}