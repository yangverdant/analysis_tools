"""
Update MLS team stadium information
"""
import sqlite3

DB_PATH = 'd:/football_tools/data/football_v2.db'

# Stadium info for MLS teams
TEAM_STADIUMS = {
    'Los Angeles FC': ('Banc of California Stadium', 22000, '洛杉矶FC', 'USA'),
    'LA Galaxy': ('Dignity Health Sports Park', 27000, '洛杉矶银河', 'USA'),
    'Inter Miami CF': ('Chase Stadium', 21550, '国际迈阿密', 'USA'),
    'Minnesota United FC': ('Allianz Field', 19400, '明尼苏达联', 'USA'),
    'Atlanta United FC': ('Mercedes-Benz Stadium', 42500, '亚特兰大联', 'USA'),
    'CF Montréal': ('Saputo Stadium', 19819, '蒙特利尔', 'Canada'),
    'Columbus Crew': ('Lower.com Field', 20371, '哥伦布机员', 'USA'),
    'Chicago Fire FC': ('Soldier Field', 61500, '芝加哥火焰', 'USA'),
    'D.C. United': ('Audi Field', 20000, '华盛顿联', 'USA'),
    'Toronto FC': ('BMO Field', 30000, '多伦多FC', 'Canada'),
    'New York City FC': ('Yankee Stadium', 30323, '纽约城', 'USA'),
    'New York Red Bulls': ('Red Bull Arena', 25000, '纽约红牛', 'USA'),
    'Seattle Sounders FC': ('Lumen Field', 37722, '西雅图海湾人', 'USA'),
    'Portland Timbers': ('Providence Park', 25218, '波特兰伐木者', 'USA'),
    'Vancouver Whitecaps FC': ('BC Place', 22200, '温哥华白帽', 'Canada'),
    'Sporting Kansas City': ('Children\'s Mercy Park', 18511, '堪萨斯城竞技', 'USA'),
    'Real Salt Lake': ('America First Field', 20497, '皇家盐湖城', 'USA'),
    'Colorado Rapids': ('Dick\'s Sporting Goods Park', 18144, '科罗拉多急流', 'USA'),
    'FC Dallas': ('Toyota Stadium', 16500, '达拉斯FC', 'USA'),
    'Houston Dynamo FC': ('Shell Energy Stadium', 21000, '休斯敦迪纳摩', 'USA'),
    'San Jose Earthquakes': ('PayPal Park', 18000, '圣何塞地震', 'USA'),
    'FC Cincinnati': ('TQL Stadium', 26000, '辛辛那提FC', 'USA'),
    'Orlando City SC': ('Exploria Stadium', 25500, '奥兰多城', 'USA'),
    'New England Revolution': ('Gillette Stadium', 65878, '新英格兰革命', 'USA'),
    'Nashville SC': ('GEODIS Park', 30000, '纳什维尔', 'USA'),
    'Austin FC': ('Q2 Stadium', 20500, '奥斯汀FC', 'USA'),
    'Charlotte FC': ('Bank of America Stadium', 38000, '夏洛特', 'USA'),
    'St. Louis City SC': ('CITYPARK', 22500, '圣路易斯城', 'USA'),
    'Philadelphia Union': ('Subaru Park', 18500, '费城联合', 'USA'),
    'San Diego FC': ('Snapdragon Stadium', 23500, '圣迭戈FC', 'USA'),
}

def update_stadiums():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    updated = 0
    for team_name, (stadium, capacity, name_cn, country) in TEAM_STADIUMS.items():
        cursor.execute('''
            UPDATE teams
            SET stadium = ?, stadium_capacity = ?, name_cn = ?, country = ?
            WHERE name_en = ?
        ''', (stadium, capacity, name_cn, country, team_name))
        if cursor.rowcount > 0:
            updated += 1

    conn.commit()
    conn.close()
    print(f'Updated {updated} MLS teams')

if __name__ == '__main__':
    update_stadiums()