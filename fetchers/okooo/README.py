"""
Okooo 爬虫 - 返回参数格式说明

每个函数的返回数据结构
"""

# ==================== get_match_ids.py ====================

"""
get_match_ids_by_date("2025-05-25")
→ List[Dict]

[
    {
        "match_id":   "12345",           # okooo比赛ID
        "home_team":  "阿森纳",           # 主队名
        "away_team":  "切尔西",           # 客队名
        "home_score": 2,                  # 主队得分 (int or None, 未开赛=None)
        "away_score": 1,                  # 客队得分 (int or None)
        "match_time": "",                 # 开赛时间
        "league_name": "",                # 联赛名
    },
    ...
]


get_match_ids_by_league("英超", round_num=38)
→ List[Dict]

[
    {
        "match_id":   "12345",
        "home_team":  "阿森纳",
        "away_team":  "切尔西",
        "home_score": None,
        "away_score": None,
        "match_time": "",
        "league_name": "英超",            # 按联赛获取时会填充
        "round":       38,                # 轮次号
    },
    ...
]
"""


# ==================== get_odds.py ====================

"""
get_match_basic("12345")
→ Dict

{
    "match_id":   "12345",
    "home_team":  "阿森纳",
    "away_team":  "切尔西",
    "home_score": "2",                    # str or "N/A"
    "away_score": "1",                    # str or "N/A"
}


get_odds_change("12345", 27)             # 27 = B365
→ Optional[List[Dict]]

成功:
[
    {"h": 0.0,    "v": "2.10|3.25|3.10", "time_label": "closing"},    # 终盘
    {"h": 1.0,    "v": "2.12|3.22|3.08", "time_label": "1h"},
    {"h": 24.0,   "v": "2.15|3.20|3.05", "time_label": "24h"},
    {"h": 9999.0, "v": "2.20|3.15|3.00", "time_label": "opening"},   # 初盘
]

v 值含义 (管道符分隔, 三段):
    欧赔(odds):      主胜赔率|平局赔率|客胜赔率      例: "2.15|3.20|3.05"
    亚盘(ah):        主队水位|让球数|客队水位         例: "0.90|0.5|0.95"
    大小球(overunder): 大球水位|盘口线|小球水位       例: "0.90|2.5|0.95"

h 值含义:
    0.0    = 终盘(closing, 比赛开始时)
    9999.0 = 初盘(opening, 最早开出时)
    其他   = 赛前N小时

特殊情况:
    None = 抓取失败 (被WAF拦截或网络错误)
    []   = 机构未开盘 (该公司没开出该盘口)


get_ah_change("12345", 27)
→ 同 get_odds_change 结构, v = 主队水位|让球数|客队水位


get_ou_change("12345", 27)
→ 同 get_odds_change 结构, v = 大球水位|盘口线|小球水位


get_full_odds_matrix("12345")
→ Dict (完整赔率矩阵, 9家公司 × 3种盘口 × 13个时间节点)

{
    "match_id":   "12345",
    "home_team":  "阿森纳",
    "away_team":  "切尔西",
    "home_score": "2",
    "away_score": "1",
    "odds": {
        "WH": {                                    # 威廉希尔
            "odds": {                              # 欧赔
                "opening":  "2.20|3.15|3.00",
                "48h":     "2.18|3.17|3.02",
                "36h":     "N/A",                  # 该时间节点无数据
                "24h":     "2.15|3.20|3.05",
                "12h":     "2.15|3.20|3.05",
                "6h":      "2.15|3.20|3.05",
                "3h":      "2.13|3.21|3.07",
                "2h":      "2.12|3.22|3.08",
                "1h":      "2.12|3.22|3.08",
                "0.5h":    "2.11|3.23|3.09",
                "0.25h":   "2.10|3.24|3.10",
                "0.1h":    "2.10|3.25|3.10",
                "closing": "2.10|3.25|3.10"
            },
            "ah": {                                # 亚盘
                "opening":  "0.85|0.25|1.02",
                "closing": "0.90|0.5|0.95"
                # ...同上的时间节点
            },
            "overunder": {                          # 大小球
                "opening":  "0.88|2.25|0.98",
                "closing": "0.90|2.5|0.95"
                # ...同上的时间节点
            }
        },
        "B365": {                                  # Bet365
            "odds":      "FETCH_FAILED",           # 抓取失败
            "ah":        "NO_DATA",                # 机构未开盘
            "overunder": {                          # 大小球成功获取
                "opening":  "0.90|2.5|0.95",
                "closing": "0.92|2.5|0.93"
            }
        },
        # ... 其余7家公司
    }
}


calc_kelly_from_odds(2.15, 3.20, 3.05)
→ Dict

{
    "kelly_home":  -0.083,            # 凯利指数-主胜 (负=博彩公司有利润空间)
    "kelly_draw":  -0.0434,           # 凯利指数-平局
    "kelly_away":  -0.0465,           # 凯利指数-客胜
    "return_rate": 0.9046,            # 返还率 (0-1, 从赔率计算)
    "prob_home":   0.4207,            # 隐含概率-主胜 (0-1)
    "prob_draw":   0.2827,            # 隐含概率-平局
    "prob_away":   0.2966             # 隐含概率-客胜
}

解读:
    返还率 = 1 / (1/home + 1/draw + 1/away)
    隐含概率 = 返还率 / 赔率
    凯利指数 = (赔率 × 概率 - 1) / (赔率 - 1)
    凯利>1: 博彩公司低估该结果概率 → 可能值得投
    凯利<1: 博彩公司高估该结果概率 → 不建议投
    凯利≈0: 博彩公司评估准确


batch_fetch_to_csv(match_ids, "output.csv")
→ CSV文件, 每行一场比赛

列名: match_id, home_team, away_team, home_score, away_score,
      WH_odds_opening, WH_odds_48h, ..., WH_odds_closing,
      WH_ah_opening, ..., WH_ah_closing,
      WH_overunder_opening, ..., WH_overunder_closing,
      B365_odds_opening, ..., (9家公司 × 3盘口 × 13时间节点 = 351列)
"""

"""
公司代码对照:
    WH     = 威廉希尔 (William Hill, id=14)
    B365   = Bet365 (id=27)
    IW     = Interwetten (id=43)
    1XBET  = 1xBet (id=744)
    BF     = Betfair (id=19)
    SBO    = SBOBET (id=280)
    188BET = 188BET (id=322)
    SABA   = 沙巴体育 (id=220)
    PIN    = 平博 (Pinnacle, id=50)

时间节点:
    opening → 初盘 (最早开出)
    48h → 赛前48小时
    36h → 赛前36小时
    24h → 赛前24小时
    12h → 赛前12小时
    6h  → 赛前6小时
    3h  → 赛前3小时
    2h  → 赛前2小时
    1h  → 赛前1小时
    0.5h  → 赛前30分钟
    0.25h → 赛前15分钟
    0.1h  → 赛前6分钟
    closing → 终盘 (比赛开始时)
"""