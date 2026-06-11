"""
数据获取工具集 (fetchers)

每个子目录是一个独立的数据渠道，可单独使用:

=== 赔率类 ===
- okooo:            澳客网爬虫 (赔率/亚盘/大小球/凯利) [需Cookie]
- sporttery:        体彩官网API (开售比赛/赔率/开奖结果) [免费]
- odds_api:         RapidAPI赔率 (OddsFeed/Bet365/FBOdds) [需Key]
- the_odds_api:     The Odds API (多家公司实时赔率) [免费500次/月]
- apifootball:      API-Football (赔率/赛程/积分榜/预测) [需Key]

=== 比赛数据类 ===
- sofascore:        Sofascore+football-data.org (实时比分/赛程/事件) [免费]
- football_data_uk:  football-data.co.uk CSV下载 (历史比赛+赔率) [免费]
- football_data_org: football-data.org API (赛程/积分榜/射手榜) [需Token]
- sportmonks:       Sportmonks API (xG/阵容/预测) [需Key]
- scores365:        365Scores (实时比分/比赛事件/统计) [免费]
- thesportsdb:      TheSportsDB (比赛/球队/阵容) [免费]
- openligadb:       OpenLigaDB (德甲/德乙/英超比赛) [免费]
- api_sports:       api-sports.io (RapidAPI, 与apifootball同源) [需Key]
- flashlive:        FlashLive (RapidAPI, 实时比分) [需Key]

=== 爬虫类 ===
- fbref:            FBref爬虫 (积分榜/xG/球员统计) [免费爬虫]
- soccerway:        Soccerway爬虫 (比赛/积分榜) [免费爬虫]
- espn:             ESPN爬虫 (实时比分) [免费爬虫]
- transfermarkt:    Transfermarkt爬虫 (球员身价/转会) [爬虫]
- flashscore:       FlashScore爬虫 (JS渲染受限) [爬虫]
- premierleague:    英超官网 (伤病/赛程) [爬虫]
- bifen188:         188比分 (阵容预测) [爬虫]

=== xG/高级统计类 ===
- understat:        Understat (球员/球队xG/xA) [免费需解析]
- statsbomb:        StatsBomb本地数据 (高级xG/事件) [本地JSON]

=== 新闻类 ===
- news:             直播吧新闻 (伤病/转会/教练) [免费]
- dongqiudi:        懂球帝 (中文足球新闻) [爬虫]
- hupu:             虎扑足球 (中文足球新闻) [爬虫]

=== 环境类 ===
- weather:          天气数据 (wttr.in) (比赛天气/影响评估) [免费]
- openweathermap:   OpenWeatherMap (天气预报/空气质量) [需Key]

=== AI/搜索类 ===
- deepseek:         DeepSeek AI (分析/翻译) [需Key]
- wikipedia:        Wikipedia (联赛历史/球队传记) [免费]
- search_api:       搜索API (Tavily/Brave) (互联网搜索) [需Key]

=== 视频类 ===
- scorebat:         ScoreBat视频集锦 (比赛视频/进球) [免费]

使用示例:
    from fetchers.okooo.get_odds import get_full_odds_matrix
    from fetchers.apifootball.get_data import get_livescores
    from fetchers.the_odds_api.get_odds import get_odds
    from fetchers.deepseek.chat import analyze_match
    from fetchers.fbref.get_stats import get_standings
    from fetchers.news.get_news import get_zhibo8_news
    from fetchers.weather.get_weather import get_match_weather
"""