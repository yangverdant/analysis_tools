"""北京时间窗口工具 — 统一"今日比赛"定义

核心定义:
  今日比赛 = 北京时间今天00:00 ~ 明天12:00之间的比赛

不同数据源时区:
  - 体彩(sporttery): 北京时间(UTC+8)
  - oddsfe: UTC
  - apifootball: UTC
  - football-data.co.uk: 英国时间(BST/GMT)

lottery_matches.match_date 存储的是体彩日期(北京时间),
所以查询窗口: match_date IN (today_beijing, tomorrow_beijing)
对于明天部分只取凌晨0:00-12:00的比赛。
"""

from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc


def now_beijing() -> datetime:
    """当前北京时间"""
    return datetime.now(BEIJING_TZ)


def today_beijing() -> str:
    """北京时间今天的日期字符串"""
    return now_beijing().strftime('%Y-%m-%d')


def tomorrow_beijing() -> str:
    """北京时间明天的日期字符串"""
    return (now_beijing() + timedelta(days=1)).strftime('%Y-%m-%d')


def yesterday_beijing() -> str:
    """北京时间昨天的日期字符串"""
    return (now_beijing() - timedelta(days=1)).strftime('%Y-%m-%d')


def match_date_window() -> tuple:
    """返回今日比赛的日期窗口 (today, tomorrow)

    用法:
        today, tomorrow = match_date_window()
        SELECT ... WHERE match_date IN (?, ?) AND ...

    返回:
        (today_str, tomorrow_str) — 北京时间日期
    """
    return today_beijing(), tomorrow_beijing()


def match_date_sql(column='match_date') -> tuple:
    """生成今日比赛窗口的SQL条件和参数

    用法:
        sql_cond, params = match_date_sql()
        cursor.execute(f"SELECT ... WHERE {sql_cond}", params)

    返回:
        (sql_fragment, params_tuple)
    """
    today, tomorrow = match_date_window()
    # 今天全天 + 明天凌晨(0:00-12:00)
    return (
        f"({column} = ? OR ({column} = ? AND substr(match_time, 1, 2) < '12'))",
        (today, tomorrow)
    )


def match_date_list() -> list:
    """返回今日比赛窗口的日期列表，用于 IN 查询

    用法:
        dates = match_date_list()
        placeholders = ','.join(['?'] * len(dates))
        cursor.execute(f"SELECT ... WHERE match_date IN ({placeholders})", dates)
    """
    today, tomorrow = match_date_window()
    return [today, tomorrow]


def beijing_to_utc(dt_beijing: datetime) -> datetime:
    """北京时间 → UTC"""
    if dt_beijing.tzinfo is None:
        dt_beijing = dt_beijing.replace(tzinfo=BEIJING_TZ)
    return dt_beijing.astimezone(UTC_TZ)


def utc_to_beijing(dt_utc: datetime) -> datetime:
    """UTC → 北京时间"""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=UTC_TZ)
    return dt_utc.astimezone(BEIJING_TZ)


def oddsfe_date_range(match_date_beijing: str) -> list:
    """给定体彩日期, 返回需要查询oddsfe的UTC日期列表

    体彩日期是北京时间, oddsfe日期是UTC。
    北京时间晚间20:00+的比赛, UTC日期是前一天。

    返回:
        [d-1_utc, d_utc, d-2_utc] — 优先查D-1
    """
    from datetime import date
    try:
        d = datetime.strptime(match_date_beijing, '%Y-%m-%d').date()
    except ValueError:
        d = date.today()

    return [
        (d - timedelta(days=1)).strftime('%Y-%m-%d'),  # D-1 (晚间比赛)
        d.strftime('%Y-%m-%d'),                          # D
        (d - timedelta(days=2)).strftime('%Y-%m-%d'),   # D-2 (极早比赛)
    ]
