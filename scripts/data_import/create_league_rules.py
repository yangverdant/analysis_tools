import os

# 联赛配置
leagues = {
    'premier_league': {
        'name_en': 'Premier League',
        'name_cn': '英超',
        'country': '英格兰',
        'teams': 20,
        'matches_per_team': 38,
        'promotion': '前4名晋级欧冠',
        'relegation': '后3名降级英冠',
        'top_scorers': ['Alan Shearer (260)', 'Wayne Rooney (208)', 'Harry Kane (213+)']
    },
    'la_liga': {
        'name_en': 'La Liga',
        'name_cn': '西甲',
        'country': '西班牙',
        'teams': 20,
        'matches_per_team': 38,
        'promotion': '前4名晋级欧冠',
        'relegation': '后3名降级西乙',
        'top_scorers': ['Lionel Messi (474)', 'Cristiano Ronaldo (311)', 'Telmo Zarra (251)']
    },
    'bundesliga': {
        'name_en': 'Bundesliga',
        'name_cn': '德甲',
        'country': '德国',
        'teams': 18,
        'matches_per_team': 34,
        'promotion': '前4名晋级欧冠',
        'relegation': '后2名降级德乙，第16名参加升降级附加赛',
        'top_scorers': ['Gerd Müller (365)', 'Robert Lewandowski (312)', 'Klaus Fischer (268)']
    },
    'serie_a': {
        'name_en': 'Serie A',
        'name_cn': '意甲',
        'country': '意大利',
        'teams': 20,
        'matches_per_team': 38,
        'promotion': '前4名晋级欧冠',
        'relegation': '后3名降级意乙',
        'top_scorers': ['Silvio Piola (274)', 'Francesco Totti (250)', 'Gunnar Nordahl (225)']
    },
    'ligue_1': {
        'name_en': 'Ligue 1',
        'name_cn': '法甲',
        'country': '法国',
        'teams': 18,
        'matches_per_team': 34,
        'promotion': '前3名晋级欧冠',
        'relegation': '后2名降级法乙',
        'top_scorers': ['Delio Onnis (299)', 'Jean-Pierre Papin (156)', 'Kylian Mbappé (150+)']
    },
    'eredivisie': {
        'name_en': 'Eredivisie',
        'name_cn': '荷甲',
        'country': '荷兰',
        'teams': 18,
        'matches_per_team': 34,
        'promotion': '前2名晋级欧冠',
        'relegation': '后1名降级荷乙',
        'top_scorers': ['Johan Cruyff (215)', 'Ruud Geels (265)', 'Willem van Hanegem (146)']
    },
    'jupiler_league': {
        'name_en': 'Belgian Pro League',
        'name_cn': '比甲',
        'country': '比利时',
        'teams': 16,
        'matches_per_team': 30,
        'promotion': '前1名晋级欧冠',
        'relegation': '后1名降级比乙',
        'top_scorers': ['Erwin Vandenbergh (252)', 'Paul Van Himst (237)', 'Bernard Voorhoof (250)']
    },
    'primeira_liga': {
        'name_en': 'Primeira Liga',
        'name_cn': '葡超',
        'country': '葡萄牙',
        'teams': 18,
        'matches_per_team': 34,
        'promotion': '前2名晋级欧冠',
        'relegation': '后2名降级葡乙',
        'top_scorers': ['Eusébio (319)', 'Fernando Peyroteo (332)', 'José Águas (290)']
    },
    'championship': {
        'name_en': 'EFL Championship',
        'name_cn': '英冠',
        'country': '英格兰',
        'teams': 24,
        'matches_per_team': 46,
        'promotion': '前2名直接升级英超，3-6名附加赛',
        'relegation': '后3名降级英甲',
        'top_scorers': []
    },
    'bundesliga_2': {
        'name_en': '2. Bundesliga',
        'name_cn': '德乙',
        'country': '德国',
        'teams': 18,
        'matches_per_team': 34,
        'promotion': '前2名直接升级德甲，第3名附加赛',
        'relegation': '后2名降级德丙',
        'top_scorers': []
    },
    'serie_b': {
        'name_en': 'Serie B',
        'name_cn': '意乙',
        'country': '意大利',
        'teams': 20,
        'matches_per_team': 38,
        'promotion': '前2名直接升级意甲',
        'relegation': '后3名降级意丙',
        'top_scorers': []
    },
    'ligue_2': {
        'name_en': 'Ligue 2',
        'name_cn': '法乙',
        'country': '法国',
        'teams': 18,
        'matches_per_team': 34,
        'promotion': '前2名直接升级法甲',
        'relegation': '后2名降级法丙',
        'top_scorers': []
    },
    'segunda_division': {
        'name_en': 'Segunda División',
        'name_cn': '西乙',
        'country': '西班牙',
        'teams': 22,
        'matches_per_team': 42,
        'promotion': '前2名直接升级西甲',
        'relegation': '后4名降级西丙',
        'top_scorers': []
    },
    'super_lig': {
        'name_en': 'Süper Lig',
        'name_cn': '土超',
        'country': '土耳其',
        'teams': 19,
        'matches_per_team': 36,
        'promotion': '前1名晋级欧冠',
        'relegation': '后4名降级土乙',
        'top_scorers': ['Hakan Şükür (249)', 'Hamit Altıntop (76)', 'Burak Yılmaz (149+)']
    },
    'superleague': {
        'name_en': 'Super League Greece',
        'name_cn': '希腊超',
        'country': '希腊',
        'teams': 14,
        'matches_per_team': 26,
        'promotion': '前1名晋级欧冠',
        'relegation': '后2名降级希腊乙',
        'top_scorers': []
    },
    'eliteserien': {
        'name_en': 'Eliteserien',
        'name_cn': '挪超',
        'country': '挪威',
        'teams': 16,
        'matches_per_team': 30,
        'promotion': '前1名晋级欧冠',
        'relegation': '后2名降级挪乙',
        'top_scorers': []
    },
    'allsvenskan': {
        'name_en': 'Allsvenskan',
        'name_cn': '瑞典超',
        'country': '瑞典',
        'teams': 16,
        'matches_per_team': 30,
        'promotion': '前1名晋级欧冠',
        'relegation': '后2名降级瑞典乙',
        'top_scorers': []
    },
    'veikkausliiga': {
        'name_en': 'Veikkausliiga',
        'name_cn': '芬超',
        'country': '芬兰',
        'teams': 12,
        'matches_per_team': 27,
        'promotion': '前1名晋级欧冠',
        'relegation': '后1名降级芬兰乙',
        'top_scorers': []
    },
    'scotland_premier': {
        'name_en': 'Scottish Premiership',
        'name_cn': '苏超',
        'country': '苏格兰',
        'teams': 12,
        'matches_per_team': 38,
        'promotion': '前1名晋级欧冠',
        'relegation': '后1名降级苏冠',
        'top_scorers': ['Jimmy McGrory (410)', 'Kenny Dalglish (167)', 'Ally McCoist (251)']
    },
    'a_league': {
        'name_en': 'A-League',
        'name_cn': '澳超',
        'country': '澳大利亚',
        'teams': 12,
        'matches_per_team': 26,
        'promotion': '前1名晋级亚冠',
        'relegation': '无降级',
        'top_scorers': []
    },
    'j1_league': {
        'name_en': 'J1 League',
        'name_cn': '日职联',
        'country': '日本',
        'teams': 18,
        'matches_per_team': 34,
        'promotion': '前1名晋级亚冠',
        'relegation': '后2名降级日职乙',
        'top_scorers': ['Kunishige Kamamoto (202)', 'Masashi Nakayama (157)', 'Yoshikatsu Kawaguchi (0 GK)']
    },
    'j2_league': {
        'name_en': 'J2 League',
        'name_cn': '日职乙',
        'country': '日本',
        'teams': 22,
        'matches_per_team': 42,
        'promotion': '前2名直接升级日职联',
        'relegation': '后2名降级J3',
        'top_scorers': []
    },
    'k1_league': {
        'name_en': 'K League 1',
        'name_cn': '韩K1',
        'country': '韩国',
        'teams': 12,
        'matches_per_team': 33,
        'promotion': '前1名晋级亚冠',
        'relegation': '后1名降级韩K2',
        'top_scorers': []
    },
    'csl': {
        'name_en': 'Chinese Super League',
        'name_cn': '中超',
        'country': '中国',
        'teams': 16,
        'matches_per_team': 30,
        'promotion': '前1名晋级亚冠',
        'relegation': '后2名降级中甲',
        'top_scorers': []
    },
    'saudi_pro': {
        'name_en': 'Saudi Pro League',
        'name_cn': '沙特超',
        'country': '沙特阿拉伯',
        'teams': 16,
        'matches_per_team': 30,
        'promotion': '前1名晋级亚冠',
        'relegation': '后2名降级沙特乙',
        'top_scorers': []
    },
    'bundesliga_austria': {
        'name_en': 'Austrian Bundesliga',
        'name_cn': '奥地利超',
        'country': '奥地利',
        'teams': 12,
        'matches_per_team': 22,
        'promotion': '前1名晋级欧冠',
        'relegation': '后1名降级奥地利乙',
        'top_scorers': []
    },
    'bundesliga_3': {
        'name_en': '3. Liga',
        'name_cn': '德丙',
        'country': '德国',
        'teams': 20,
        'matches_per_team': 38,
        'promotion': '前2名升级德乙',
        'relegation': '后4名降级地区联赛',
        'top_scorers': []
    },
    'league_one': {
        'name_en': 'EFL League One',
        'name_cn': '英甲',
        'country': '英格兰',
        'teams': 24,
        'matches_per_team': 46,
        'promotion': '前3名升级英冠',
        'relegation': '后4名降级英乙',
        'top_scorers': []
    },
    'league_two': {
        'name_en': 'EFL League Two',
        'name_cn': '英乙',
        'country': '英格兰',
        'teams': 24,
        'matches_per_team': 46,
        'promotion': '前3名升级英甲',
        'relegation': '后2名降级英非联',
        'top_scorers': []
    },
    'scotland_div1': {
        'name_en': 'Scottish Championship',
        'name_cn': '苏冠',
        'country': '苏格兰',
        'teams': 10,
        'matches_per_team': 36,
        'promotion': '前1名升级苏超',
        'relegation': '后1名降级苏甲',
        'top_scorers': []
    },
    'scotland_div2': {
        'name_en': 'Scottish League One',
        'name_cn': '苏甲',
        'country': '苏格兰',
        'teams': 10,
        'matches_per_team': 36,
        'promotion': '前1名升级苏冠',
        'relegation': '后1名降级苏乙',
        'top_scorers': []
    },
    'scotland_div3': {
        'name_en': 'Scottish League Two',
        'name_cn': '苏乙',
        'country': '苏格兰',
        'teams': 10,
        'matches_per_team': 36,
        'promotion': '前1名升级苏甲',
        'relegation': '后1名降级低级别联赛',
        'top_scorers': []
    },
    'gambrinus_liga': {
        'name_en': 'Czech First League',
        'name_cn': '捷甲',
        'country': '捷克',
        'teams': 16,
        'matches_per_team': 30,
        'promotion': '前1名晋级欧冠',
        'relegation': '后2名降级捷克乙',
        'top_scorers': []
    },
    'nb1': {
        'name_en': 'NB I',
        'name_cn': '匈甲',
        'country': '匈牙利',
        'teams': 12,
        'matches_per_team': 33,
        'promotion': '前1名晋级欧冠',
        'relegation': '后2名降级匈乙',
        'top_scorers': []
    },
    'austria_2': {
        'name_en': '2. Liga',
        'name_cn': '奥地利乙',
        'country': '奥地利',
        'teams': 16,
        'matches_per_team': 30,
        'promotion': '前1名升级奥地利超',
        'relegation': '后2名降级地区联赛',
        'top_scorers': []
    },
    'swiss_2': {
        'name_en': 'Swiss Challenge League',
        'name_cn': '瑞士乙',
        'country': '瑞士',
        'teams': 10,
        'matches_per_team': 36,
        'promotion': '前1名升级瑞士超',
        'relegation': '后1名降级瑞士丙',
        'top_scorers': []
    },
    'turkey_2': {
        'name_en': 'TFF First League',
        'name_cn': '土乙',
        'country': '土耳其',
        'teams': 19,
        'matches_per_team': 36,
        'promotion': '前2名升级土超',
        'relegation': '后3名降级土丙',
        'top_scorers': []
    },
    'russia_2': {
        'name_en': 'Russian First Division',
        'name_cn': '俄乙',
        'country': '俄罗斯',
        'teams': 16,
        'matches_per_team': 30,
        'promotion': '前2名升级俄超',
        'relegation': '后2名降级俄丙',
        'top_scorers': []
    },
}

def create_rules_md(league_key, config):
    """Create rules.md for a league"""
    content = f"""# {config['name_cn']}规则

## 基本信息

- **赛事名称**：{config['name_en']}（{config['name_cn']}）
- **主办国家**：{config['country']}
- **参赛队伍**：{config['teams']}队
- **赛季周期**：{config['matches_per_team']}轮

## 赛制规则

### 比赛形式

- **赛制**：双循环联赛制
- **每队比赛**：{config['matches_per_team']}场
- **总比赛数**：{config['teams'] * config['matches_per_team'] // 2}场

### 积分规则

- 获胜：3分
- 平局：1分
- 失败：0分

### 排名规则

若积分相同，按以下规则排序：

1. 净胜球
2. 进球数
3. 相互比赛结果
4. 公平竞赛积分

### 晋级规则

{config['promotion']}

### 降级规则

{config['relegation']}

## 数据统计

| 赛季 | 文件 | 备注 |
|------|------|------|
| 2000-01 | {league_key}_2000-01.csv | |
| ... | ... | |
| 2025-26 | {league_key}_2025-26.csv | |

## 数据字段说明

- `season`：赛季（如 2024-25）
- `match_date`：比赛日期
- `match_time`：比赛时间
- `home_team`：主队名称
- `away_team`：客队名称
- `home_goals`：主队进球
- `away_goals`：客队进球
- `result`：结果（H=主胜, D=平, A=客胜）
- `status`：状态（finished/scheduled）

## 历史射手榜（部分联赛）

"""
    if config['top_scorers']:
        for scorer in config['top_scorers']:
            content += f"- {scorer}\n"
    else:
        content += "- 待补充\n"

    return content

# 创建所有联赛的rules.md
base_path = 'd:/football_tools/new_data/matches/clubs/leagues'

for league_key, config in leagues.items():
    league_dir = os.path.join(base_path, league_key)
    if os.path.exists(league_dir):
        rules_path = os.path.join(league_dir, 'rules.md')
        content = create_rules_md(league_key, config)
        with open(rules_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created: {rules_path}")
    else:
        print(f"Directory not found: {league_dir}")

print("\nDone!")