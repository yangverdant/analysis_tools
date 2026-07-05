#!/usr/bin/env python3
"""One-shot backfill of teams.name_cn for known oddsfe team names.

Sources the EN name list from lottery_matches (oddsfe-sourced rows with
EN-only home_team_cn), looks up the team in teams table by name_en, and
updates name_cn if currently NULL.

CN translations are based on common Chinese football media usage.
"""
import sqlite3
import sys

DB = "/opt/football_tools/data/football_v2.db"

# EN -> CN mapping for teams seen in oddsfe schedule that have no CN name
# in the teams table. Curated from Chinese football media usage.
EN_TO_CN = {
    # K League 2
    "Gimhae": "金海",
    "Gimpo FC": "金浦FC",
    "Jeonnam": "全南",
    "Gyeongnam": "庆南",
    "Cheonan City": "天安市",
    "Asan": "牙山",
    "Seoul E-Land": "首尔衣恋",
    "Busan": "釜山",
    "Daegu": "大邱",
    "Seongnam": "城南",
    "Suwon Bluewings": "水原蓝翼",
    "Suwon FC": "水原FC",
    "Yongin": "龙仁",
    "Ansan Greeners": "安山绿人",
    "Cheongju FC": "清州FC",
    "Paju Citizen": "坡州",
    # Korean Cup
    "Busan Kyotong": "釜山交通",
    "Geoje": "巨济",
    "Gyeongju KHNP": "庆州韩电",
    "Gijang United": "机张联合",
    "Incheon Seogot": "仁川西谷",
    "Jecheon Citizen": "堤川",
    "Jincheon": "镇川",
    "Jinju Citizen": "晋州",
    "Mokpo": "木浦",
    "Namyangju Citizen": "南杨州",
    "Pocheon": "抱川",
    "Pyeongtaek Citizen": "平泽",
    "Sejong SA": "世宗",
    "Seosan Pioneer": "瑞山先锋",
    "Seoul Jungnang": "首尔中浪",
    "Siheung Citizen": "始兴",
    "Ulsan Citizen": "蔚山市民",
    "Ulsan FC": "蔚山FC",
    "Yangpyeong": "杨平",
    "Yeoju Citizen": "骊州",
    "Anseong": "安城",
    "Changwon": "昌原",
    "Chuncheon": "春川",
    "Daejeon Korail": "大田铁道",
    "Dangjin Citizen": "唐津",
    "Gangneung": "江陵",
    "Geumsan Insam": "锦山人参",
    "Haman": "咸安",
    # China Super League (中超)
    "Qingdao Hainiu": "青岛海牛",
    "Chengdu Rongcheng": "成都蓉城",
    "Shanghai Shenhua": "上海申花",
    "Zhejiang Professional": "浙江职业",
    # China League One (中甲)
    "Meizhou Hakka": "梅州客家",
    "Changchun Yatai": "长春亚泰",
    "Guangxi Hengchen": "广西恒宸",
    "Dalian K'un City": "大连鲲城",
    "Nanjing City": "南京城市",
    "Foshan Nanshi": "佛山南狮",
    # China League Two (中乙)
    "Xiamen Feilu": "厦门鹭岛",
    "Shanxi Chongde Ronghai": "陕西崇德荣海",
    "Shanghai Second": "上海二队",
    "Taian Tiankuang": "泰安天贶",
    "Changchun Xidu": "长春喜都",
    "Dalian Yingbo B": "大连英博B",
    "Qingdao Red Lions": "青岛红狮",
    "Hangzhou Linping": "杭州临平",
    "Wenzhou Professional": "温州职业",
    "Guizhou Zhucheng": "贵州筑城",
    "Jiangxi Lushan": "江西庐山",
    "Shenzhen": "深圳",
    "Shenzhen Peng City": "深圳鹏城",
    "Shenzhen Xinpengcheng": "深圳新鹏城",
    "Shenzhen Jixiang": "深圳吉祥",
    "Shenzhen Juniors": "深圳青年人",
    # USL Championship (美乙)
    "Louisville City": "路易维尔",
    "Hartford Athletic": "哈特福德竞技",
    "FC Tulsa": "塔尔萨FC",
    "Sacramento Republic": "萨克拉门托共和",
    "Monterey Bay": "蒙特雷湾",
    "Colorado Springs": "科罗拉多泉",
    "Phoenix Rising": "凤凰城崛起",
    "New Mexico United": "新墨西哥联",
    "Oakland Roots": "奥克兰根源",
    "Las Vegas Lights": "拉斯维加斯之光",
    "El Paso": "埃尔帕索",
    # Copa Chile (智利杯)
    "U. Catolica": "天主教大学",
    "Copiapo": "科皮亚波",
    "S. Wanderers": "圣地亚哥漫游者",
    "U. De Concepcion": "康塞普西翁大学",
    "Rangers": "兰格斯",
    "Cobreloa": "科布雷洛亚",
    "D. Puerto Montt": "德波多蒙特",
    "Curico Unido": "库里科联",
    "U. Espanola": "西班牙联合",
    # Ecuador Liga Pro (厄甲)
    "Barcelona SC": "巴塞罗那SC",
    "Dep. Cuenca": "库恩卡",
    "Macara": "马卡拉",
    "LDU Quito": "基多大学",
    "Emelec": "埃梅莱克",
    "Orense": "奥伦塞",
    "Delfin": "德尔芬",
    "Tecnico U.": "技术大学",
    "Nautico": "纳乌蒂科",
    # Sweden Allsvenskan (瑞超)
    "AIK Stockholm": "AIK索尔纳",
    "Orgryte": "奥格里特",
    "Kalmar": "卡尔马",
    "IFK Goteborg": "哥德堡",
    "Elfsborg": "埃尔夫斯堡",
    "Hammarby": "哈马比",
    "Mjallby": "米亚尔比",
    "Haugesund": "海于格松",
    "Odd": "奥德",
    # Finland Ykkosliiga (芬甲)
    "Mikkeli": "米凯利",
    "Haka": "哈卡",
    # Norway OBOS-ligaen (挪甲)
    # (already covered above)
    # Brazil
    "Botafogo SP": "博塔弗戈SP",
    "Sao Bernardo": "圣贝尔纳多",
    "Juventude": "尤文图德",
    "Vila Nova": "维拉诺瓦",
    "CD Santa Cruz": "圣克鲁斯",
    "Operario": "奥瓦里奥",
    # Europe
    "TNS": "新圣徒",
    "Levski Sofia": "列夫斯基索菲亚",
    "Borac Banja Luka": "博拉茨",
    "Sabah Baku": "萨巴赫",
    "UNA Strassen": "乌纳斯特拉森",
    "AF Elbasani": "爱尔巴桑",
}


def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    updated = 0
    not_in_teams = []
    for en, cn in EN_TO_CN.items():
        cur = conn.execute(
            "UPDATE teams SET name_cn = ? WHERE name_en = ? AND (name_cn IS NULL OR name_cn = '')",
            (cn, en)
        )
        if cur.rowcount > 0:
            updated += 1
        # Verify the team exists
        row = conn.execute("SELECT team_id FROM teams WHERE name_en = ?", (en,)).fetchone()
        if not row:
            not_in_teams.append(f"{en} -> {cn}")
    conn.commit()

    # Also: for EN names that don't exist in teams table at all, we can't add them
    # here (we don't know their team_id, country, etc.). They'll stay as EN in
    # lottery_matches. Future ESPN/API-Sports sync can populate them.
    print(f"Updated {updated} team name_cn mappings")
    if not_in_teams:
        print(f"\nTeams not in teams table ({len(not_in_teams)}):")
        for x in not_in_teams:
            print(f"  {x}")
    conn.close()


if __name__ == "__main__":
    main()
