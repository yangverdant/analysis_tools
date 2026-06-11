"""
补充球队中文名称
"""

import sqlite3
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 球队中文名称映射
TEAM_CN_NAMES = {
    # 德国球队
    "Preußen Münster": "普鲁士明斯特",
    "VfL Bochum 1848": "波鸿",
    "FC St. Pauli 1910": "圣保利",
    "1. FC Heidenheim 1846": "海登海姆",
    "SV Darmstadt 98": "达姆施塔特",

    # 英格兰球队
    "Rochdale": "罗奇代尔",
    "Luton Town FC": "卢顿",

    # 西班牙球队
    "UD Las Palmas": "拉斯帕尔马斯",
    "CD Leganés": "莱加内斯",
    "Real Valladolid CF": "巴拉多利德",
    "RCD Espanyol de Barcelona": "西班牙人",
    "UD Almería": "阿尔梅里亚",
    "Granada CF": "格拉纳达",
    "Sporting Clube de Braga": "布拉加",

    # 意大利球队
    "Parma Calcio 1913": "帕尔马",
    "Empoli FC": "恩波利",
    "AC Monza": "蒙扎",
    "Frosinone Calcio": "弗罗西诺内",
    "US Salernitana 1919": "萨勒尼塔纳",

    # 法国球队
    "Le Havre AC": "勒阿弗尔",
    "AS Saint-Étienne": "圣埃蒂安",
    "AJ Auxerre": "欧塞尔",
    "Clermont Foot 63": "克莱蒙",

    # 比利时球队
    "Seraing": "瑟兰",
    "Royal Antwerp FC": "安特卫普",

    # 瑞典球队
    "Varberg": "瓦尔贝里",

    # 瑞士球队
    "BSC Young Boys": "年轻人",

    # 克罗地亚球队
    "GNK Dinamo Zagreb": "萨格勒布迪纳摩",

    # 乌克兰球队
    "FK Shakhtar Donetsk": "顿涅茨克矿工",

    # 捷克球队
    "AC Sparta Praha": "布拉格斯巴达",

    # 奥地利球队
    "FC Red Bull Salzburg": "萨尔茨堡红牛",
    "SK Sturm Graz": "格拉茨风暴",

    # 苏格兰球队
    "Celtic FC": "凯尔特人",

    # 斯洛伐克球队
    "ŠK Slovan Bratislava": "布拉迪斯拉发",

    # 塞尔维亚球队
    "FK Crvena Zvezda": "贝尔格莱德红星",

    # 国家队
    "South Sudan": "南苏丹",
    "São Tomé and Príncipe": "圣多美和普林西比",
    "Tamil Eelam": "泰米尔伊拉姆",
}


def update_team_cn_names(db_path=None):
    """更新球队中文名称"""

    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), 'data', 'football_v2.db')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    updated = 0

    for name_en, name_cn in TEAM_CN_NAMES.items():
        cursor.execute('''
            UPDATE teams SET name_cn = ?
            WHERE name_en = ? AND (name_cn IS NULL OR name_cn = '')
        ''', (name_cn, name_en))
        if cursor.rowcount > 0:
            updated += 1
            print(f"更新: {name_en} -> {name_cn}")

    conn.commit()

    # 统计结果
    cursor.execute("SELECT COUNT(*) FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''")
    with_cn = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teams")
    total = cursor.fetchone()[0]

    conn.close()

    print(f"\n更新了 {updated} 个球队")
    print(f"有中文名: {with_cn}/{total}")
    print(f"缺少中文名: {total - with_cn}")

    return {"updated": updated, "with_cn": with_cn, "total": total}


if __name__ == "__main__":
    update_team_cn_names()
