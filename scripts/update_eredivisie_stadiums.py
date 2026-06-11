"""
Update Eredivisie team stadium information
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')

# Stadium info for Eredivisie teams
TEAM_STADIUMS = {
    'Ajax': ('Johan Cruijff Arena', 55865, '阿贾克斯'),
    'AZ': ('AFAS Stadion', 19600, '阿尔克马尔'),
    'Feyenoord': ('De Kuip', 51117, '费耶诺德'),
    'PSV': ('Philips Stadion', 35119, '埃因霍温'),
    'Vitesse': ('GelreDome', 21000, '维特斯'),
    'Utrecht': ('Stadion Galgenwaard', 23000, '乌得勒支'),
    'Twente': ('De Grolsch Veste', 30205, '特温特'),
    'Heerenveen': ('Abe Lenstra Stadion', 26100, '海伦芬'),
    'Groningen': ('Euroborg', 22579, '格罗宁根'),
    'NAC': ('Rat Verlegh Stadion', 19000, 'NAC布雷达'),
    'Roda': ('Parkstad Limburg Stadion', 19979, '罗达JC'),
    'Willem II': ('Koning Willem II Stadion', 14600, '威廉二世'),
    'Sparta': ('Sparta-Stadion Het Kasteel', 11000, '斯巴达'),
    'Sparta Rotterdam': ('Sparta-Stadion Het Kasteel', 11000, '鹿特丹斯巴达'),
    'Go Ahead Eagles': ('De Adelaarshorst', 10200, '前进之鹰'),
    'NEC': ('Goffertstadion', 12500, 'NEC奈梅亨'),
    'Nijmegen': ('Goffertstadion', 12500, 'NEC奈梅亨'),
    'Waalwijk': ('Mandemakers Stadion', 7500, '瓦尔韦克'),
    'RKC': ('Mandemakers Stadion', 7500, 'RKC瓦尔韦克'),
    'Graafschap': ('De Vijverberg', 13500, '格拉夫沙普'),
    'Roosendaal': ('Vast & Goed Stadion', 6500, '罗斯达尔'),
    'Fortuna Sittard': ('Fortuna Sittard Stadion', 12500, '幸运薛达'),
    'Sittard': ('Fortuna Sittard Stadion', 12500, '锡塔德'),
    'Almere City': ('Yankee Stadion', 3050, '阿尔梅勒城'),
    'Excelsior': ('Van Donge & De Roo Stadion', 4400, '埃克塞尔'),
    'Venlo': ('De Koel', 8100, '芬洛'),
    'Heracles': ('Erve Asito', 13500, '大力神'),
    'Cambuur': ('Cambuurstadion', 10500, '坎布尔'),
    'Volendam': ('Kras Stadion', 6200, '沃伦丹'),
    'ADO Den Haag': ('Cars Jeans Stadion', 15000, '海牙'),
    'Zwolle': ('MAC3PARK Stadion', 14000, '兹沃勒'),
    'Emmen': ('De Oude Meerdijk', 8500, '埃门'),
    'Den Bosch': ('De Vliert', 9000, '登博斯'),
    'Dordrecht': ('GN Bouw Stadion', 4100, '多德勒支'),
    'Telstar': ('Rabobank IJmond Stadion', 3600, '泰尔斯塔'),
    'For Sittard': ('Fortuna Sittard Stadion', 12500, '福尔图娜'),
    'Go Ahead': ('De Adelaarshorst', 10200, '前进之鹰'),
    'FC Emmen': ('De Oude Meerdijk', 8500, '埃门'),
}

def update_stadiums():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    updated = 0
    for team_name, (stadium, capacity, name_cn) in TEAM_STADIUMS.items():
        cursor.execute('''
            UPDATE teams
            SET stadium = ?, stadium_capacity = ?, name_cn = ?
            WHERE name_en = ?
        ''', (stadium, capacity, name_cn, team_name))
        if cursor.rowcount > 0:
            updated += 1
            print(f'Updated: {team_name} -> {stadium} ({capacity})')

    conn.commit()
    conn.close()
    print(f'\nUpdated {updated} teams')

if __name__ == '__main__':
    update_stadiums()
