"""Build complete FIFA ranking dict for today_final.py from database + FD data."""
import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/football_v2.db')
cur = conn.cursor()

# Get all FIFA rankings from DB
cur.execute('SELECT t.name_en, t.name_cn, f.rank FROM fifa_rankings f JOIN teams t ON f.team_id=t.team_id ORDER BY f.rank')
db_data = cur.fetchall()

# Manual CN name mapping for national teams (DB has wrong CN names for some)
cn_map = {
    'Spain': '西班牙', 'France': '法国', 'Senegal': '塞内加尔', 'Argentina': '阿根廷',
    'Morocco': '摩洛哥', 'Nigeria': '尼日利亚', 'England': '英格兰', 'Japan': '日本',
    'Turkey': '土耳其', 'Algeria': '阿尔及利亚', 'Portugal': '葡萄牙',
    'DR Congo': '刚果(金)', 'Germany': '德国', 'Iran': '伊朗', 'Netherlands': '荷兰',
    'Uzbekistan': '乌兹别克斯坦', 'Colombia': '哥伦比亚', 'Egypt': '埃及',
    'Ivory Coast': '科特迪瓦', "Côte d'Ivoire": '科特迪瓦', 'Ecuador': '厄瓜多尔',
    'Switzerland': '瑞士', 'Austria': '奥地利', 'Croatia': '克罗地亚',
    'Belgium': '比利时', 'Norway': '挪威', 'Panama': '巴拿马',
    'South Korea': '韩国', 'Brazil': '巴西', 'Uruguay': '乌拉圭', 'Italy': '意大利',
    'Mexico': '墨西哥', 'Tunisia': '突尼斯', 'Australia': '澳大利亚',
    'Kosovo': '科索沃', 'Jordan': '约旦', 'Iraq': '伊拉克', 'Denmark': '丹麦',
    'Sweden': '瑞典', 'Slovenia': '斯洛文尼亚', 'Cape Verde': '佛得角',
    'Cape Verde Islands': '佛得角', 'Paraguay': '巴拉圭',
    'Czech Republic': '捷克', 'South Africa': '南非', 'Haiti': '海地',
    'Venezuela': '委内瑞拉', 'Costa Rica': '哥斯达黎加', 'Honduras': '洪都拉斯',
    'Serbia': '塞尔维亚', 'Saudi Arabia': '沙特', 'Slovakia': '斯洛伐克',
    'Wales': '威尔士', 'Romania': '罗马尼亚', 'Poland': '波兰',
    'United States': '美国', 'Hungary': '匈牙利', 'North Macedonia': '北马其顿',
    'Curaçao': '库拉索', 'Republic of Ireland': '爱尔兰', 'Albania': '阿尔巴尼亚',
    'Cameroon': '喀麦隆', 'Ghana': '加纳', 'Canada': '加拿大', 'Scotland': '苏格兰',
    'Bosnia and Herzegovina': '波黑', 'Qatar': '卡塔尔', 'New Zealand': '新西兰',
    'Ukraine': '乌克兰', 'Greece': '希腊', 'Russia': '俄罗斯',
    'China PR': '中国', 'China': '中国', 'Georgia': '格鲁吉亚',
    'Bulgaria': '保加利亚', 'Montenegro': '黑山', 'Finland': '芬兰',
    'Iceland': '冰岛', 'Israel': '以色列', 'Chile': '智利',
    'Ivory Coast': '科特迪瓦',
}

# Build mapping: CN name -> best rank (dedup)
result = {}
for name_en, name_cn, rank in db_data:
    cn = cn_map.get(name_en)
    if not cn:
        continue
    if cn not in result or rank < result[cn]:
        result[cn] = rank

# Sort by rank
sorted_items = sorted(result.items(), key=lambda x: x[1])

# Output as Python dict
print("fifa_ranking = {")
for cn, rank in sorted_items:
    print(f"    '{cn}': {rank},")
print("}")
print(f"\nTotal: {len(result)} teams")

# Check WC 2026 coverage
wc_needed = [
    '阿根廷', '阿尔及利亚', '澳大利亚', '奥地利', '比利时', '巴西', '加拿大',
    '哥伦比亚', '克罗地亚', '捷克', '厄瓜多尔', '埃及', '英格兰', '法国',
    '德国', '加纳', '伊朗', '伊拉克', '科特迪瓦', '日本', '约旦', '韩国',
    '墨西哥', '摩洛哥', '荷兰', '新西兰', '挪威', '巴拿马', '巴拉圭',
    '葡萄牙', '卡塔尔', '沙特', '苏格兰', '塞内加尔', '南非', '西班牙',
    '瑞典', '瑞士', '突尼斯', '土耳其', '美国', '乌拉圭', '乌兹别克斯坦',
    '波黑', '佛得角', '刚果(金)', '库拉索', '海地',
]

missing = [t for t in wc_needed if t not in result]
if missing:
    print(f"\nMissing WC teams: {missing}")
else:
    print(f"\nAll {len(wc_needed)} WC 2026 teams covered!")
