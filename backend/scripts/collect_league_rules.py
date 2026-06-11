"""
日韩联赛规则和升降级制度整理
包含: 球队数量、升降级规则、季后赛制度、洲际赛事名额等
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

# 日韩联赛规则数据 (根据官方规则整理)
LEAGUE_RULES = {
    "j1_league": {
        "league_id": 18,
        "name_cn": "J1联赛",
        "name_en": "J1 League",
        "country": "Japan",
        "tier": 1,
        "rules": {
            "2024": {
                "teams_count": 20,
                "matches_per_team": 38,
                "format_type": "double_round_robin",
                "format_description": "双循环赛制，每队主客场各打一次",

                "promotion": {
                    "direct": 0,
                    "playoff": 0,
                    "description": "J1联赛为顶级联赛，无升级"
                },

                "relegation": {
                    "direct": 3,
                    "playoff": 0,
                    "playoff_teams": 0,
                    "description": "直接降级3队至J2联赛 (第18、19、20名)"
                },

                "continental": {
                    "afc_champions_league": "前3名直接晋级亚冠精英赛",
                    "afc_champions_league_2": "第4名晋级亚冠二级联赛",
                    "emperor_cup": "天皇杯冠军获亚冠精英赛资格(如已获资格则顺延)",
                    "total_acl_spots": 3,
                    "total_acl2_spots": 1
                },

                "playoffs": {
                    "has_playoffs": False,
                    "description": "无季后赛，按积分排名"
                },

                "split": {
                    "has_split": False,
                    "description": "2024赛季改为单年度制，无分阶段"
                },

                "season_period": {
                    "start_month": 2,
                    "end_month": 12,
                    "description": "2月开赛，12月结束"
                },

                "foreign_players": {
                    "limit": "无限制",
                    "description": "外援无人数限制，但报名限制"
                },

                "notes": "2024赛季起改为单年度制(2-12月)，此前为双阶段制"
            },

            "2025": {
                "teams_count": 20,
                "matches_per_team": 38,
                "format_type": "double_round_robin",
                "promotion": {"direct": 0, "playoff": 0},
                "relegation": {"direct": 3, "playoff": 0},
                "continental": {
                    "afc_champions_league": "前3名",
                    "afc_champions_league_2": "第4名"
                }
            }
        }
    },

    "j2_league": {
        "league_id": 7433,
        "name_cn": "J2联赛",
        "name_en": "J2 League",
        "country": "Japan",
        "tier": 2,
        "rules": {
            "2024": {
                "teams_count": 20,
                "matches_per_team": 38,
                "format_type": "double_round_robin",
                "format_description": "双循环赛制",

                "promotion": {
                    "direct": 2,
                    "playoff": 1,
                    "playoff_teams": 6,
                    "playoff_format": "第3-6名进行升级附加赛",
                    "description": "前2名直接升级J1，第3-6名附加赛决出第3个升级名额"
                },

                "relegation": {
                    "direct": 2,
                    "playoff": 1,
                    "playoff_teams": 2,
                    "playoff_format": "第18名与J3第3名进行附加赛",
                    "description": "最后2名直接降级J3，第18名与J3附加赛球队争夺保级名额"
                },

                "continental": {
                    "description": "无洲际赛事名额"
                },

                "playoffs": {
                    "has_playoffs": True,
                    "playoff_type": "promotion_playoff",
                    "format": "第3vs第6，第4vs第5，胜者对决",
                    "description": "升级附加赛：第3-6名参加"
                },

                "season_period": {
                    "start_month": 2,
                    "end_month": 12
                }
            }
        }
    },

    "j3_league": {
        "league_id": 7434,
        "name_cn": "J3联赛",
        "name_en": "J3 League",
        "country": "Japan",
        "tier": 3,
        "rules": {
            "2024": {
                "teams_count": 20,
                "matches_per_team": 38,
                "format_type": "double_round_robin",

                "promotion": {
                    "direct": 2,
                    "playoff": 1,
                    "playoff_teams": 4,
                    "description": "前2名直接升级J2，第3-6名附加赛"
                },

                "relegation": {
                    "direct": 0,
                    "playoff": 0,
                    "description": "J3为最低职业联赛，无降级(业余联赛JFL冠军可升级)"
                },

                "notes": "JFL(日本足球联赛)冠军可升级至J3"
            }
        }
    },

    "k1_league": {
        "league_id": 20,
        "name_cn": "K联赛1",
        "name_en": "K League 1",
        "country": "South Korea",
        "tier": 1,
        "rules": {
            "2024": {
                "teams_count": 12,
                "matches_per_team": 38,
                "format_type": "split_season",
                "format_description": "分阶段赛制：常规赛33轮 + 分组赛5轮",

                "split": {
                    "has_split": True,
                    "split_after_rounds": 33,
                    "split_groups": 2,
                    "split_group_names": ["Final A (争冠组)", "Final B (保级组)"],
                    "description": "33轮后按排名分两组，前6名争冠组，后6名保级组，各打5轮"
                },

                "promotion": {
                    "direct": 0,
                    "playoff": 0,
                    "description": "K联赛1为顶级联赛，无升级"
                },

                "relegation": {
                    "direct": 1,
                    "playoff": 1,
                    "playoff_teams": 2,
                    "playoff_format": "K联赛1第11名 vs K联赛2第2名",
                    "description": "最后1名直接降级，第11名与K联赛2附加赛"
                },

                "continental": {
                    "afc_champions_league": "联赛冠军+足协杯冠军",
                    "afc_champions_league_2": "联赛第2-4名",
                    "total_acl_spots": 2,
                    "total_acl2_spots": 3
                },

                "playoffs": {
                    "has_playoffs": False,
                    "description": "无季后赛，分阶段赛制决定排名"
                },

                "season_period": {
                    "start_month": 3,
                    "end_month": 12
                },

                "foreign_players": {
                    "limit": "注册5人，上场4人",
                    "description": "亚外+非亚外共5人注册，上场最多4人"
                },

                "notes": "韩国独有的分阶段赛制，争冠组和保级组分别比赛"
            }
        }
    },

    "k2_league": {
        "league_id": 7436,
        "name_cn": "K联赛2",
        "name_en": "K League 2",
        "country": "South Korea",
        "tier": 2,
        "rules": {
            "2024": {
                "teams_count": 13,
                "matches_per_team": 36,
                "format_type": "double_round_robin",

                "promotion": {
                    "direct": 1,
                    "playoff": 1,
                    "playoff_teams": 4,
                    "playoff_format": "第2-4名进行附加赛",
                    "description": "冠军直接升级K联赛1，第2-4名附加赛争夺升级名额"
                },

                "relegation": {
                    "direct": 0,
                    "playoff": 0,
                    "description": "K联赛2为次级联赛，无降级(K3为半职业联赛)"
                },

                "continental": {
                    "description": "无洲际赛事名额"
                },

                "playoffs": {
                    "has_playoffs": True,
                    "playoff_type": "promotion_playoff",
                    "description": "升级附加赛"
                },

                "season_period": {
                    "start_month": 3,
                    "end_month": 11
                }
            }
        }
    }
}


def save_rules_to_database():
    """保存规则到数据库"""

    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()

    saved = 0

    for league_key, league_data in LEAGUE_RULES.items():
        league_id = league_data["league_id"]

        for season, rules in league_data["rules"].items():
            # 检查是否已存在
            cursor.execute("""
                SELECT rule_id FROM league_rules
                WHERE league_id = ? AND season = ?
            """, (league_id, season))

            if cursor.fetchone():
                # 更新
                cursor.execute("""
                    UPDATE league_rules SET
                        teams_count = ?,
                        matches_per_team = ?,
                        format_type = ?,
                        promotion_spots = ?,
                        promotion_playoff_spots = ?,
                        relegation_spots = ?,
                        relegation_playoff_spots = ?,
                        has_playoffs = ?,
                        has_split = ?,
                        split_after_rounds = ?,
                        afc_champions_league_spots = ?,
                        afc_cup_spots = ?,
                        rules_json = ?,
                        updated_at = ?
                    WHERE league_id = ? AND season = ?
                """, (
                    rules.get("teams_count"),
                    rules.get("matches_per_team"),
                    rules.get("format_type"),
                    rules.get("promotion", {}).get("direct", 0),
                    rules.get("promotion", {}).get("playoff", 0),
                    rules.get("relegation", {}).get("direct", 0),
                    rules.get("relegation", {}).get("playoff", 0),
                    1 if rules.get("playoffs", {}).get("has_playoffs") else 0,
                    1 if rules.get("split", {}).get("has_split") else 0,
                    rules.get("split", {}).get("split_after_rounds"),
                    rules.get("continental", {}).get("total_acl_spots", 0),
                    rules.get("continental", {}).get("total_acl2_spots", 0),
                    json.dumps(rules, ensure_ascii=False),
                    datetime.now().isoformat(),
                    league_id,
                    season
                ))
            else:
                # 插入
                cursor.execute("""
                    INSERT INTO league_rules (
                        league_id, season, teams_count, matches_per_team, format_type,
                        promotion_spots, promotion_playoff_spots,
                        relegation_spots, relegation_playoff_spots,
                        has_playoffs, has_split, split_after_rounds,
                        afc_champions_league_spots, afc_cup_spots,
                        rules_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    league_id,
                    season,
                    rules.get("teams_count"),
                    rules.get("matches_per_team"),
                    rules.get("format_type"),
                    rules.get("promotion", {}).get("direct", 0),
                    rules.get("promotion", {}).get("playoff", 0),
                    rules.get("relegation", {}).get("direct", 0),
                    rules.get("relegation", {}).get("playoff", 0),
                    1 if rules.get("playoffs", {}).get("has_playoffs") else 0,
                    1 if rules.get("split", {}).get("has_split") else 0,
                    rules.get("split", {}).get("split_after_rounds"),
                    rules.get("continental", {}).get("total_acl_spots", 0),
                    rules.get("continental", {}).get("total_acl2_spots", 0),
                    json.dumps(rules, ensure_ascii=False),
                    datetime.now().isoformat()
                ))

            saved += 1

    conn.commit()
    conn.close()

    return saved


def generate_rules_report():
    """生成规则报告"""

    report = """# 日韩联赛规则与升降级制度

**更新日期**: {date}

---

## 日本职业联赛 (J联赛)

### J1联赛 (顶级联赛)

| 项目 | 规则 |
|------|------|
| **球队数量** | 20队 |
| **赛制** | 双循环 (主客场各一次) |
| **每队比赛** | 38场 |
| **赛季时间** | 2月-12月 |

#### 升降级规则

| 类型 | 名额 | 说明 |
|------|------|------|
| 升级 | 0队 | 顶级联赛无升级 |
| 降级 | 3队 | 第18、19、20名直接降级J2 |

#### 洲际赛事名额

| 赛事 | 名额 | 说明 |
|------|------|------|
| 亚冠精英赛 | 3个 | 联赛前3名 |
| 亚冠二级联赛 | 1个 | 联赛第4名 |
| 天皇杯 | 1个 | 冠军获亚冠资格 |

#### 特殊说明
- 2024赛季起改为**单年度制** (2-12月)
- 此前为双阶段制 (前期+后期冠军争夺总冠军)

---

### J2联赛 (二级联赛)

| 项目 | 规则 |
|------|------|
| **球队数量** | 20队 |
| **赛制** | 双循环 |
| **每队比赛** | 38场 |

#### 升降级规则

| 类型 | 名额 | 说明 |
|------|------|------|
| 直接升级 | 2队 | 第1、2名直接升级J1 |
| 附加赛升级 | 1队 | 第3-6名附加赛决出 |
| 直接降级 | 2队 | 最后2名降级J3 |
| 附加赛降级 | 1队 | 第18名与J3附加赛 |

#### 升级附加赛赛制
```
第3名 vs 第6名
第4名 vs 第5名
→ 两场胜者对决 → 胜者升级J1
```

---

### J3联赛 (三级联赛)

| 项目 | 规则 |
|------|------|
| **球队数量** | 20队 |
| **赛制** | 双循环 |
| **每队比赛** | 38场 |

#### 升降级规则

| 类型 | 名额 | 说明 |
|------|------|------|
| 直接升级 | 2队 | 第1、2名直接升级J2 |
| 附加赛升级 | 1队 | 第3-6名附加赛 |
| 降级 | 0队 | J3为最低职业联赛 |

**注**: JFL(日本足球联赛)冠军可升级至J3

---

## 韩国职业联赛 (K联赛)

### K联赛1 (顶级联赛)

| 项目 | 规则 |
|------|------|
| **球队数量** | 12队 |
| **赛制** | **分阶段赛制** |
| **常规赛** | 33轮 (每队主客场+1个中立) |
| **分组赛** | 5轮 |

#### 分阶段赛制说明

**第一阶段 - 常规赛 (33轮)**
- 12队进行三循环比赛
- 每队共33场比赛

**第二阶段 - 分组赛 (5轮)**
- **Final A (争冠组)**: 前6名
- **Final B (保级组)**: 后6名
- 各组内进行单循环比赛

**最终排名** = 常规赛积分 + 分组赛积分

#### 升降级规则

| 类型 | 名额 | 说明 |
|------|------|------|
| 升级 | 0队 | 顶级联赛无升级 |
| 直接降级 | 1队 | 最后1名降级K联赛2 |
| 附加赛降级 | 1队 | 第11名与K联赛2附加赛 |

#### 洲际赛事名额

| 赛事 | 名额 | 说明 |
|------|------|------|
| 亚冠精英赛 | 2个 | 联赛冠军+足协杯冠军 |
| 亚冠二级联赛 | 3个 | 联赛第2-4名 |

#### 外援规则
- 注册: 最多5人 (含亚外)
- 上场: 最多4人

---

### K联赛2 (二级联赛)

| 项目 | 规则 |
|------|------|
| **球队数量** | 13队 |
| **赛制** | 双循环 |
| **每队比赛** | 36场 |

#### 升降级规则

| 类型 | 名额 | 说明 |
|------|------|------|
| 直接升级 | 1队 | 冠军直接升级K联赛1 |
| 附加赛升级 | 1队 | 第2-4名附加赛决出 |
| 降级 | 0队 | K联赛2为次级联赛 |

#### 升级附加赛赛制
```
K联赛1第11名 vs K联赛2第2名 (主客场)
→ 胜者留在/升级K联赛1
```

---

## 对比总结

### 赛制对比

| 联赛 | 赛制特点 |
|------|----------|
| J1联赛 | 标准双循环 |
| J2联赛 | 标准双循环 + 升级附加赛 |
| J3联赛 | 标准双循环 |
| **K联赛1** | **独特的分阶段赛制** |
| K联赛2 | 标准双循环 + 升级附加赛 |

### 升降级对比

| 联赛 | 升级 | 降级 | 附加赛 |
|------|------|------|--------|
| J1 | - | 3队 | 无 |
| J2 | 2+1 | 2+1 | 有 |
| J3 | 2+1 | - | 有 |
| K1 | - | 1+1 | 有 |
| K2 | 1+1 | - | 有 |

### 洲际赛事名额

| 联赛 | 亚冠精英赛 | 亚冠二级联赛 |
|------|------------|--------------|
| J1 | 3+1(天皇杯) | 1 |
| K1 | 2 | 3 |

---

**数据来源**: J联赛官网、K联赛官网、维基百科
""".format(date=datetime.now().strftime("%Y-%m-%d"))

    return report


if __name__ == "__main__":
    # 保存规则到数据库
    saved = save_rules_to_database()
    print(f"保存了 {saved} 条联赛规则")

    # 生成报告
    report = generate_rules_report()

    # 保存报告
    report_path = PROJECT_ROOT / "data" / "linkage" / "JAPAN_KOREA_LEAGUE_RULES.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"报告已保存至: {report_path}")
    print("\n" + "=" * 60)
    print(report[:2000])
