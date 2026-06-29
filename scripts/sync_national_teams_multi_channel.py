"""
多渠道国家队队名映射整合

目标：
1. 统一所有渠道的国家队英文名到标准名
2. 映射到中文队名
3. 记录各渠道的队名别名

渠道包括：
- oddsfe: 英文队名（如 "Germany", "Korea Republic"）
- sporttery: 中文队名（如 "德国", "韩国"）
- apifootball: 英文队名

teams 表字段：
- name_en: 标准英文名
- name_cn: 标准中文名
- oddsfe_team_id: oddsfe 球队 ID
- oddsfe_name_en: oddsfe 英文队名（可能不同于标准名）
- sporttery_name_cn: 体彩中文队名
- sporttery_name_en: 体彩英文队名（通过映射）
"""
import sqlite3
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'data/football_v2.db'
ODDSFE_DB = 'fetchers/odds_feed_api/oddsfe_merged.db'

# 标准国家队名称映射（各渠道别名 -> 标准英文名）
NATIONAL_TEAM_ALIASES = {
    # oddsfe 别名 -> 标准名
    'South Korea': 'Korea Republic',
    'North Korea': 'Korea DPR',
    'USA': 'United States',
    'UAE': 'United Arab Emirates',
    'Czechia': 'Czech Republic',
    'Bosnia & Herzegovina': 'Bosnia and Herzegovina',
    'Bosnia-Herzegovina': 'Bosnia and Herzegovina',
    'D.R. Congo': 'DR Congo',
    'Congo DR': 'DR Congo',
    'Republic of Ireland': 'Ireland',
    'Guinea Bissau': 'Guinea-Bissau',
    'Ivory Coast': 'Cote dIvoire',
}

# 国家队中文名映射
NATIONAL_TEAM_CHINESE = {
    'Korea Republic': '韩国',
    'Korea DPR': '朝鲜',
    'United States': '美国',
    'United Arab Emirates': '阿联酋',
    'Czech Republic': '捷克',
    'Bosnia and Herzegovina': '波黑',
    'DR Congo': '刚果民主共和国',
    'Ireland': '爱尔兰',
    'Guinea-Bissau': '几内亚比绍',
    'Cote dIvoire': '科特迪瓦',
    'Saudi Arabia': '沙特阿拉伯',
    'Germany': '德国',
    'France': '法国',
    'Spain': '西班牙',
    'England': '英格兰',
    'Italy': '意大利',
    'Netherlands': '荷兰',
    'Portugal': '葡萄牙',
    'Belgium': '比利时',
    'Croatia': '克罗地亚',
    'Japan': '日本',
    'China PR': '中国',
    'Argentina': '阿根廷',
    'Brazil': '巴西',
    'Mexico': '墨西哥',
    'Canada': '加拿大',
    'Australia': '澳大利亚',
    'Morocco': '摩洛哥',
    'Senegal': '塞内加尔',
    'Cameroon': '喀麦隆',
    'Ghana': '加纳',
    'Nigeria': '尼日利亚',
    'Egypt': '埃及',
    'Algeria': '阿尔及利亚',
    'Tunisia': '突尼斯',
    'Iran': '伊朗',
    'Uruguay': '乌拉圭',
    'Colombia': '哥伦比亚',
    'Chile': '智利',
    'Peru': '秘鲁',
    'Ecuador': '厄瓜多尔',
    'Paraguay': '巴拉圭',
    'Denmark': '丹麦',
    'Sweden': '瑞典',
    'Norway': '挪威',
    'Finland': '芬兰',
    'Iceland': '冰岛',
    'Scotland': '苏格兰',
    'Wales': '威尔士',
    'Poland': '波兰',
    'Slovakia': '斯洛伐克',
    'Hungary': '匈牙利',
    'Romania': '罗马尼亚',
    'Bulgaria': '保加利亚',
    'Greece': '希腊',
    'Turkey': '土耳其',
    'Russia': '俄罗斯',
    'Ukraine': '乌克兰',
    'Serbia': '塞尔维亚',
    'Switzerland': '瑞士',
    'Austria': '奥地利',
    'Slovenia': '斯洛文尼亚',
    'Latvia': '拉脱维亚',
    'Lithuania': '立陶宛',
    'Estonia': '爱沙尼亚',
    'Belarus': '白俄罗斯',
    'Georgia': '格鲁吉亚',
    'Armenia': '亚美尼亚',
    'Azerbaijan': '阿塞拜疆',
    'Curacao': '库拉索',
    'Jamaica': '牙买加',
    'Costa Rica': '哥斯达黎加',
    'Panama': '巴拿马',
    'Honduras': '洪都拉斯',
    'Guatemala': '危地马拉',
    'El Salvador': '萨尔瓦多',
    'Nicaragua': '尼加拉瓜',
    'Trinidad and Tobago': '特立尼达和多巴哥',
    'Haiti': '海地',
    'Cuba': '古巴',
    'Dominican Republic': '多米尼加共和国',
    'New Zealand': '新西兰',
    'Fiji': '斐济',
    'Papua New Guinea': '巴布亚新几内亚',
    'South Africa': '南非',
    'Burundi': '布隆迪',
    'Mali': '马里',
    'Burkina Faso': '布基纳法索',
    'Niger': '尼日尔',
    'Chad': '乍得',
    'Sudan': '苏丹',
    'Libya': '利比亚',
    'Zambia': '赞比亚',
    'Zimbabwe': '津巴布韦',
    'Botswana': '博茨瓦纳',
    'Namibia': '纳米比亚',
    'Mozambique': '莫桑比克',
    'Angola': '安哥拉',
    'Kenya': '肯尼亚',
    'Tanzania': '坦桑尼亚',
    'Uganda': '乌干达',
    'Ethiopia': '埃塞俄比亚',
    'Gabon': '加蓬',
    'Congo': '刚果',
    'Togo': '多哥',
    'Benin': '贝宁',
    'Mauritania': '毛里塔尼亚',
    'Gambia': '冈比亚',
    'Sierra Leone': '塞拉利昂',
    'Liberia': '利比里亚',
    'Central African Republic': '中非共和国',
    'Equatorial Guinea': '赤道几内亚',
    'Seychelles': '塞舌尔',
    'Comoros': '科摩罗',
    'Madagascar': '马达加斯加',
    'Mauritius': '毛里求斯',
    'Djibouti': '吉布提',
    'Somalia': '索马里',
    'Eritrea': '厄立特里亚',
    'South Sudan': '南苏丹',
    'Rwanda': '卢旺达',
    'Malawi': '马拉维',
    'Lesotho': '莱索托',
    'Eswatini': '斯威士兰',
    'Afghanistan': '阿富汗',
    'Albania': '阿尔巴尼亚',
    'Andorra': '安道尔',
    'Anguilla': '安圭拉',
    'Antigua and Barbuda': '安提瓜和巴布达',
    'Armenia': '亚美尼亚',
    'Aruba': '阿鲁巴',
    'Bahamas': '巴哈马',
    'Bahrain': '巴林',
    'Bangladesh': '孟加拉国',
    'Barbados': '巴巴多斯',
    'Belize': '伯利兹',
    'Bermuda': '百慕大',
    'Bhutan': '不丹',
    'Bolivia': '玻利维亚',
    'British Virgin Islands': '英属维尔京群岛',
    'Cambodia': '柬埔寨',
    'Cape Verde': '佛得角',
    'Cayman Islands': '开曼群岛',
    'Cyprus': '塞浦路斯',
    'Dominica': '多米尼克',
    'Faroe Islands': '法罗群岛',
    'Guam': '关岛',
    'Guyana': '圭亚那',
    'Hong Kong': '中国香港',
    'Indonesia': '印度尼西亚',
    'Iraq': '伊拉克',
    'Israel': '以色列',
    'Jordan': '约旦',
    'Kazakhstan': '哈萨克斯坦',
    'Kosovo': '科索沃',
    'Kuwait': '科威特',
    'Kyrgyzstan': '吉尔吉斯斯坦',
    'Laos': '老挝',
    'Lebanon': '黎巴嫩',
    'Liechtenstein': '列支敦士登',
    'Luxembourg': '卢森堡',
    'Macau': '中国澳门',
    'Malaysia': '马来西亚',
    'Maldives': '马尔代夫',
    'Malta': '马耳他',
    'Moldova': '摩尔多瓦',
    'Mongolia': '蒙古',
    'Montenegro': '黑山',
    'Myanmar': '缅甸',
    'Nepal': '尼泊尔',
    'New Caledonia': '新喀里多尼亚',
    'Oman': '阿曼',
    'Pakistan': '巴基斯坦',
    'Palestine': '巴勒斯坦',
    'Philippines': '菲律宾',
    'Puerto Rico': '波多黎各',
    'Qatar': '卡塔尔',
    'San Marino': '圣马力诺',
    'Singapore': '新加坡',
    'Solomon Islands': '所罗门群岛',
    'Sri Lanka': '斯里兰卡',
    'St. Kitts and Nevis': '圣基茨和尼维斯',
    'Saint Lucia': '圣卢西亚',
    'Suriname': '苏里南',
    'Syria': '叙利亚',
    'Tahiti': '塔希提',
    'Tajikistan': '塔吉克斯坦',
    'Thailand': '泰国',
    'Timor-Leste': '东帝汶',
    'Tonga': '汤加',
    'Turkmenistan': '土库曼斯坦',
    'Turks and Caicos Islands': '特克斯和凯科斯群岛',
    'Uzbekistan': '乌兹别克斯坦',
    'Vanuatu': '瓦努阿图',
    'Venezuela': '委内瑞拉',
    'Vietnam': '越南',
    'Yemen': '也门',
}

def main():
    conn = sqlite3.connect(DB_PATH)
    conn_oddsfe = sqlite3.connect(ODDSFE_DB)
    c = conn.cursor()
    c_oddsfe = conn_oddsfe.cursor()

    print('=== 多渠道国家队队名映射整合 ===\n')

    # 1. 获取 oddsfe 中的所有国家队
    c_oddsfe.execute('''
        SELECT DISTINCT team_home_id, team_home_name
        FROM oddsfe
        WHERE tournament_name LIKE '%International%'
           OR tournament_name LIKE '%World Cup%'
           OR tournament_name LIKE '%Euro%'
           OR tournament_name LIKE '%Nations League%'
    ''')
    oddsfe_teams = c_oddsfe.fetchall()

    print(f'oddsfe 中的国际赛事球队数量：{len(oddsfe_teams)}\n')

    # 2. 过滤出真正的国家队并建立映射
    national_team_mapping = {}  # oddsfe_id -> (oddsfe_name, standard_name, cn_name)

    for oddsfe_id, team_name in oddsfe_teams:
        # 跳过俱乐部和青年队
        skip_keywords = [' U19', ' U21', ' U23', ' U17', ' U20', ' W', ' B ', ' II',
                         'FC', 'AC', 'AS', 'United', 'City', 'Ajax', 'Roma',
                         'Club', 'FK', 'BK', 'IF', 'SK', 'TSV', 'VfL', 'SV', 'SC']
        if any(x in team_name for x in skip_keywords):
            continue

        # 标准化队名
        standard_name = NATIONAL_TEAM_ALIASES.get(team_name, team_name)

        # 获取中文名
        cn_name = NATIONAL_TEAM_CHINESE.get(standard_name, None)

        if cn_name:
            national_team_mapping[oddsfe_id] = (team_name, standard_name, cn_name)

    print(f'识别到 {len(national_team_mapping)} 支国家队\n')

    # 3. 更新 teams 表 - 多字段更新
    updated = 0
    inserted = 0
    updates_sql = []

    for oddsfe_id, (oddsfe_name, standard_name, cn_name) in national_team_mapping.items():
        # 检查是否已存在
        c.execute('SELECT team_id, name_en, oddsfe_team_id, oddsfe_name_en, sporttery_name_cn FROM teams WHERE name_cn = ?', (cn_name,))
        row = c.fetchone()

        if row:
            team_id, existing_name_en, existing_oddsfe_id, existing_oddsfe_name, existing_sporttery = row

            # 需要更新的条件：
            # 1. oddsfe_team_id 为空或不匹配
            # 2. oddsfe_name_en 为空或与当前 oddsfe 名称不同
            # 3. name_en 不是标准名

            needs_update = False
            if not existing_oddsfe_id or existing_oddsfe_id != str(oddsfe_id):
                needs_update = True
            if not existing_oddsfe_name or existing_oddsfe_name != oddsfe_name:
                needs_update = True

            if needs_update:
                c.execute('''
                    UPDATE teams
                    SET oddsfe_team_id = ?,
                        oddsfe_name_en = ?,
                        name_en = ?,
                        sporttery_name_cn = ?
                    WHERE team_id = ?
                ''', (str(oddsfe_id), oddsfe_name, standard_name, cn_name, team_id))
                updated += 1
                if updated <= 15:
                    updates_sql.append(f'UPDATE teams SET oddsfe_team_id="{oddsfe_id}", oddsfe_name_en="{oddsfe_name}" WHERE name_cn="{cn_name}";')
        else:
            # 插入新记录
            c.execute('SELECT COALESCE(MAX(team_id), 0) + 1 FROM teams')
            next_id = c.fetchone()[0]

            c.execute('''
                INSERT INTO teams (team_id, name_en, name_cn, oddsfe_team_id, oddsfe_name_en, sporttery_name_cn, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (next_id, standard_name, cn_name, str(oddsfe_id), oddsfe_name, cn_name))
            inserted += 1
            if inserted <= 10:
                print(f'新增：{cn_name} ({standard_name}) -> oddsfe_id={oddsfe_id}, oddsfe_name={oddsfe_name}')

    conn.commit()

    print(f'\n=== 完成 ===')
    print(f'更新：{updated} 支')
    print(f'新增：{inserted} 支')

    # 4. 验证关键国家队（显示所有字段）
    print('\n=== 验证关键国家队映射（多字段）===')
    key_teams = ['韩国', '朝鲜', '美国', '捷克', '波黑', '刚果民主共和国', '爱尔兰', '科特迪瓦',
                 '德国', '法国', '西班牙', '英格兰', '巴西', '阿根廷', '日本', '中国', '沙特阿拉伯']

    for cn_name in key_teams:
        c.execute('''
            SELECT name_en, name_cn, oddsfe_team_id, oddsfe_name_en, sporttery_name_cn
            FROM teams
            WHERE name_cn = ?
        ''', (cn_name,))
        row = c.fetchone()
        if row:
            print(f'  {cn_name}:')
            print(f'    name_en={row[0]}, oddsfe_team_id={row[2]}, oddsfe_name_en={row[3] or "无"}, sporttery={row[4] or "无"}')
        else:
            print(f'  {cn_name}: [未找到]')

    conn.close()
    conn_oddsfe.close()

    # 输出 SQL 更新语句
    if updates_sql:
        print('\n=== SQL 更新语句 ===')
        for sql in updates_sql[:20]:
            print(sql)

if __name__ == '__main__':
    main()
