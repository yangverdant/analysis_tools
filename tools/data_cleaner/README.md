# 数据清洗工具

用于清洗和标准化足球比赛数据的工具集。

## 目录结构

```
tools/data_cleaner/
├── README.md                   # 本文档
├── clean_data.py               # 数据清洗主脚本
├── generate_team_tables.py     # 球队表生成脚本
└── config/                     # 配置文件目录 (待扩展)
```

## 功能说明

### 1. clean_data.py - 数据清洗

将原始CSV数据转换为标准格式：
- 统一字段名 (210+ 标准字段)
- 空值用 `null` 替代
- 自动填充赛季信息
- 自动计算轮次
- 统一日期格式 (YYYY-MM-DD)
- 中文球队名转英文标准名

**用法：**
```bash
# 清洗五大联赛
python clean_data.py all

# 清洗单个联赛
python clean_data.py one premier_league

# 测试单个文件
python clean_data.py test
```

**支持的联赛：**
- premier_league (英超) - 每轮10场
- la_liga (西甲) - 每轮10场
- bundesliga (德甲) - 每轮9场
- serie_a (意甲) - 每轮10场
- ligue_1 (法甲) - 每轮9场

### 2. generate_team_tables.py - 球队表生成

从清洗后的数据中提取球队信息：
- 英文球队名 + 中文球队名对照
- 按联赛和赛季分类
- 输出格式: 赛季, 联赛英文名, 联赛中文名, 英文球队名, 中文球队名

**用法：**
```bash
python generate_team_tables.py
```

## 输入输出

### 输入目录
- 原始数据: `D:/football_tools/data/01_europe_leagues/`

### 输出目录
- 清洗后数据: `D:/football_tools/new_data/leagues/`
- 球队表: `D:/football_tools/new_data/teams/`

## 标准字段说明

### 核心字段 (10个)
| 字段 | 说明 |
|------|------|
| season | 赛季 (如 2024-2025) |
| match_date | 比赛日期 (YYYY-MM-DD) |
| match_time | 比赛时间 (当地时间) |
| round_num | 轮次 |
| home_team | 主队名称 |
| away_team | 客队名称 |
| home_goals | 主队进球 |
| away_goals | 客队进球 |
| result | 结果 (H/D/A) |
| status | 比赛状态 (Finished/Scheduled) |

### 统计字段 (14个)
| 字段 | 说明 |
|------|------|
| home_shots | 主队射门 |
| away_shots | 客队射门 |
| home_shots_target | 主队射正 |
| away_shots_target | 客队射正 |
| home_corners | 主队角球 |
| away_corners | 客队角球 |
| home_fouls | 主队犯规 |
| away_fouls | 客队犯规 |
| home_yellow | 主队黄牌 |
| away_yellow | 客队黄牌 |
| home_red | 主队红牌 |
| away_red | 客队红牌 |
| home_hit_woodwork | 主队射中门框 |
| away_hit_woodwork | 客队射中门框 |

### 赔率字段
- 开场赔率: b365_home, b365_draw, b365_away 等
- 收盘赔率: b365_c_home, b365_c_draw, b365_c_away 等
- 大小球: b365_over_2_5, b365_under_2_5 等
- 亚盘: asian_handicap, b365_ah_home, b365_ah_away 等

## 时间说明

CSV中的时间为**当地时间**，非北京时间。详见 `new_data/TIME_DEFINITION.md`

## 扩展配置

### 添加新联赛

1. 在 `clean_data.py` 中添加联赛配置:
```python
matches_per_round = {
    'new_league': 10,  # 每轮比赛数
}
```

2. 在 `generate_team_tables.py` 中添加联赛名称:
```python
LEAGUE_NAMES = {
    'new_league': '新联赛',
}
```

3. 添加球队中文名映射:
```python
TEAM_CN_NAMES = {
    'Team Name': '球队中文名',
}
```

### 添加新字段映射

在 `clean_data.py` 的 `FIELD_MAPPING` 中添加:
```python
FIELD_MAPPING = {
    'OldFieldName': 'new_field_name',
}
```

## 注意事项

1. 原始数据不会被修改，清洗后的数据存放在 `new_data/` 目录
2. 轮次根据联赛球队数自动计算
3. 中文球队名会自动转换为英文标准名
4. 空值统一用 `null` 字符串替代
