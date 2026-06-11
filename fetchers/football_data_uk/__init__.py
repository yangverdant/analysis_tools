"""
football-data.co.uk 数据获取工具

免费CSV数据源，无需API Key
提供五大联赛+多个欧洲联赛的比赛结果、赔率、统计历史数据

可用模块:
- config: 联赛映射、CSV列名说明
- get_csv: 下载并解析CSV数据

数据覆盖:
    英超(E0) 英冠(E1) 英甲(E2) 英乙(E3)
    西甲(SP1) 西乙(SP2)
    德甲(D1) 德乙(D2)
    意甲(I1) 意乙(I2)
    法甲(F1) 法乙(F2)
    荷甲(N1) 葡超(P1) 土超(T1) 比甲(B1) 苏超(SC0) 希腊超(G1)

数据内容:
    比赛结果 (比分、半场比分)
    赔率 (B365/WH/IW/PIN等公司欧赔、亚盘、大小球)
    比赛统计 (射门、角球、犯规、红黄牌)
    历史范围: 1993-94赛季起
"""

from fetchers.football_data_uk.config import LEAGUES, CURRENT_SEASON
from fetchers.football_data_uk.get_csv import (
    fetch_league, fetch_historical, fetch_all_leagues,
    get_season_code, save_csv
)
