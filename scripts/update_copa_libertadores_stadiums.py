"""
Update Copa Libertadores team stadium information
"""
import sqlite3

DB_PATH = 'd:/football_tools/data/football_v2.db'

# Stadium info for Copa Libertadores 2025 teams
TEAM_STADIUMS = {
    # Venezuela
    'Monagas SC': ('Estadio Monumental de Maturín', 52000, '莫纳加斯', 'Venezuela'),
    'Carabobo FC': ('Estadio Misael Delgado Duque', 12000, '卡拉沃博', 'Venezuela'),
    'Universidad Central de Venezuela FC': ('Estadio Olímpico de Caracas', 24000, '委内瑞拉中央大学', 'Venezuela'),

    # Uruguay
    'Defensor SC': ('Estadio Luis Franzini', 16000, '防卫者体育', 'Uruguay'),

    # Paraguay
    'Club Nacional': ('Estadio Defensores del Chaco', 36000, '国民俱乐部', 'Paraguay'),
    'Olimpia Asuncion': ('Estadio Manuel Ferreira', 28000, '奥林匹亚', 'Paraguay'),

    # Peru
    'Club Alianza Lima': ('Estadio Alejandro Villanueva', 35000, '利马联盟', 'Peru'),
    'FBC Melgar': ('Estadio Garcilaso de la Vega', 45000, '梅尔加', 'Peru'),

    # Bolivia
    'CD Blooming': ('Estadio Ramón Tahuichi Aguilera', 38000, '布洛明', 'Bolivia'),
    'Club The Strongest': ('Estadio Hernando Siles', 42000, '最强者', 'Bolivia'),

    # Ecuador
    'CSCyD El Nacional': ('Estadio Olímpico Atahualpa', 35000, '国民', 'Ecuador'),
    'LDU de Quito': ('Estadio Rodrigo Paz Delgado', 41000, '基多大学', 'Ecuador'),

    # Chile
    'CD Iquique': ('Estadio Municipal de Iquique', 15000, '伊基克', 'Chile'),
    'CD Nublense': ('Estadio Municipal de Chillán', 10000, '纽布伦斯', 'Chile'),
    'CSD Colo-Colo': ('Estadio Monumental David Arellano', 47000, '科洛科洛', 'Chile'),

    # Colombia
    'Independiente Santa Fe': ('Estadio El Campín', 36000, '圣塔菲独立', 'Colombia'),
    'CDC Atlético Nacional': ('Estadio Atanasio Girardot', 40000, '国民竞技', 'Colombia'),

    # Argentina
    'CA Boca Juniors': ('La Bombonera', 54000, '博卡青年', 'Argentina'),
    'CA River Plate': ('Estadio Monumental', 70000, '河床', 'Argentina'),
    'Racing Club': ('Estadio Presidente Perón', 51000, '竞技俱乐部', 'Argentina'),
    'CA Estudiantes de La Plata': ('Estadio Jorge Luis Hirschi', 53000, '拉普拉塔大学生', 'Argentina'),
    'CA Rosario Central': ('Estadio Gigante de Arroyito', 42000, '罗萨里奥中央', 'Argentina'),

    # Brazil
    'EC Bahia': ('Estadio Fonte Nova', 50000, '巴伊亚', 'Brazil'),
    'CR Flamengo': ('Estadio Maracanã', 78000, '弗拉门戈', 'Brazil'),
    'CR Vasco da Gama': ('Estadio São Januário', 24000, '瓦斯科达伽马', 'Brazil'),
    'SC Corinthians Paulista': ('Estadio Neo Química Arena', 49000, '科林蒂安', 'Brazil'),
    'São Paulo FC': ('Estadio Morumbi', 66000, '圣保罗', 'Brazil'),
    'Botafogo FR': ('Estadio Nilton Santos', 46000, '博塔弗戈', 'Brazil'),
    'Grêmio FBPA': ('Estadio Arena do Grêmio', 55000, '格雷米奥', 'Brazil'),
    'Internacional': ('Estadio Beira-Rio', 51000, '国际队', 'Brazil'),
    'Fortaleza EC': ('Estadio Castelão', 60000, '福塔莱萨', 'Brazil'),
    'Athletico Paranaense': ('Estadio Arena da Baixada', 42000, '巴拉纳竞技', 'Brazil'),
    'Atlético Mineiro': ('Estadio Mineirão', 62000, '米内罗竞技', 'Brazil'),
    'Palmeiras': ('Estadio Allianz Parque', 43000, '帕尔梅拉斯', 'Brazil'),
    'Fluminense FC': ('Estadio Maracanã', 78000, '弗鲁米嫩塞', 'Brazil'),
    'Cruzeiro EC': ('Estadio Mineirão', 62000, '克鲁塞罗', 'Brazil'),
    'Red Bull Bragantino': ('Estadio Nabi Abi Chedid', 17000, '布拉甘蒂诺', 'Brazil'),
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
        else:
            # Try to find by partial match
            cursor.execute('''
                UPDATE teams
                SET stadium = ?, stadium_capacity = ?, name_cn = ?, country = ?
                WHERE name_en LIKE ?
            ''', (stadium, capacity, name_cn, country, f'%{team_name.split()[0]}%'))
            if cursor.rowcount > 0:
                updated += 1

    conn.commit()
    conn.close()
    print(f'Updated {updated} teams')

if __name__ == '__main__':
    update_stadiums()