import pandas as pd

# ============================================================
# 2025-2026赛季四大联赛：添加缺失球队的比赛 + 更新近期轮次数据
# 北京时间 -> 当地时间转换（5月夏令时：英国-7h, 西班牙-6h, 德国-6h, 法国-6h, 意大利-6h）
# ============================================================

# ============================================================
# 西甲 La Liga - R36-R38
# 北京时间 -> 西班牙当地时间（5月夏令时-6h）
# ============================================================
la_liga_updates = [
    # R36 已结束
    {'home': 'Celta', 'away': 'Levante', 'date': '2026-05-12', 'time': '19:00', 'hg': 2, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Betis', 'away': 'Elche', 'date': '2026-05-12', 'time': '20:00', 'hg': 2, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 36},
    {'home': 'Osasuna', 'away': 'Ath Madrid', 'date': '2026-05-12', 'time': '21:30', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Espanol', 'away': 'Ath Bilbao', 'date': '2026-05-13', 'time': '19:00', 'hg': 2, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 36},
    {'home': 'Villarreal', 'away': 'Sevilla', 'date': '2026-05-13', 'time': '20:00', 'hg': 2, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Alaves', 'away': 'Barcelona', 'date': '2026-05-13', 'time': '21:30', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 36},
    {'home': 'Getafe', 'away': 'Mallorca', 'date': '2026-05-13', 'time': '21:30', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 36},
    {'home': 'Valencia', 'away': 'Vallecano', 'date': '2026-05-14', 'time': '19:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 36},
    {'home': 'Girona', 'away': 'Sociedad', 'date': '2026-05-14', 'time': '20:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 36},
    {'home': 'Real Madrid', 'away': 'Oviedo', 'date': '2026-05-14', 'time': '21:30', 'hg': 2, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 36},
    # R37 已结束
    {'home': 'Ath Bilbao', 'away': 'Celta', 'date': '2026-05-17', 'time': '19:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 37},
    {'home': 'Ath Madrid', 'away': 'Girona', 'date': '2026-05-17', 'time': '19:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 37},
    {'home': 'Elche', 'away': 'Getafe', 'date': '2026-05-17', 'time': '19:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 37},
    {'home': 'Levante', 'away': 'Mallorca', 'date': '2026-05-17', 'time': '19:00', 'hg': 2, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 37},
    {'home': 'Vallecano', 'away': 'Villarreal', 'date': '2026-05-17', 'time': '19:00', 'hg': 2, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 37},
    {'home': 'Sociedad', 'away': 'Valencia', 'date': '2026-05-17', 'time': '19:00', 'hg': 3, 'ag': 4, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Oviedo', 'away': 'Alaves', 'date': '2026-05-17', 'time': '19:00', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Osasuna', 'away': 'Espanol', 'date': '2026-05-17', 'time': '19:00', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Sevilla', 'away': 'Real Madrid', 'date': '2026-05-17', 'time': '19:00', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Barcelona', 'away': 'Betis', 'date': '2026-05-17', 'time': '21:15', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 37},
    # R38 未开赛
    {'home': 'Alaves', 'away': 'Vallecano', 'date': '2026-05-23', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Betis', 'away': 'Levante', 'date': '2026-05-23', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Celta', 'away': 'Sevilla', 'date': '2026-05-23', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Espanol', 'away': 'Sociedad', 'date': '2026-05-23', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Getafe', 'away': 'Osasuna', 'date': '2026-05-23', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Mallorca', 'away': 'Oviedo', 'date': '2026-05-23', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Real Madrid', 'away': 'Ath Bilbao', 'date': '2026-05-23', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Valencia', 'away': 'Barcelona', 'date': '2026-05-23', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Girona', 'away': 'Elche', 'date': '2026-05-24', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Villarreal', 'away': 'Ath Madrid', 'date': '2026-05-24', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
]

# ============================================================
# 意甲 Serie A - R35-R38
# 北京时间 -> 意大利当地时间（5月夏令时-6h）
# ============================================================
serie_a_updates = [
    # R35 已结束
    {'home': 'Pisa', 'away': 'Lecce', 'date': '2026-05-01', 'time': '20:45', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 35},
    {'home': 'Udinese', 'away': 'Torino', 'date': '2026-05-01', 'time': '20:45', 'hg': 2, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 35},
    {'home': 'Como', 'away': 'Napoli', 'date': '2026-05-02', 'time': '18:00', 'hg': 0, 'ag': 0, 'result': 'D', 'status': 'finished', 'round': 35},
    {'home': 'Atalanta', 'away': 'Genoa', 'date': '2026-05-02', 'time': '20:45', 'hg': 0, 'ag': 0, 'result': 'D', 'status': 'finished', 'round': 35},
    {'home': 'Bologna', 'away': 'Cagliari', 'date': '2026-05-03', 'time': '12:30', 'hg': 0, 'ag': 0, 'result': 'D', 'status': 'finished', 'round': 35},
    {'home': 'Sassuolo', 'away': 'Milan', 'date': '2026-05-03', 'time': '15:00', 'hg': 2, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 35},
    {'home': 'Juventus', 'away': 'Verona', 'date': '2026-05-03', 'time': '18:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 35},
    {'home': 'Inter', 'away': 'Parma', 'date': '2026-05-03', 'time': '20:45', 'hg': 2, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 35},
    {'home': 'Cremonese', 'away': 'Lazio', 'date': '2026-05-04', 'time': '18:30', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 35},
    {'home': 'Roma', 'away': 'Fiorentina', 'date': '2026-05-04', 'time': '20:45', 'hg': 4, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 35},
    # R36 已结束
    {'home': 'Torino', 'away': 'Sassuolo', 'date': '2026-05-08', 'time': '20:45', 'hg': 2, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 36},
    {'home': 'Cagliari', 'away': 'Udinese', 'date': '2026-05-09', 'time': '15:00', 'hg': 0, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Lazio', 'away': 'Inter', 'date': '2026-05-09', 'time': '18:00', 'hg': 0, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Lecce', 'away': 'Juventus', 'date': '2026-05-09', 'time': '20:45', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Verona', 'away': 'Como', 'date': '2026-05-09', 'time': '21:30', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Cremonese', 'away': 'Pisa', 'date': '2026-05-09', 'time': '15:00', 'hg': 3, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 36},
    {'home': 'Fiorentina', 'away': 'Genoa', 'date': '2026-05-09', 'time': '15:00', 'hg': 0, 'ag': 0, 'result': 'D', 'status': 'finished', 'round': 36},
    {'home': 'Parma', 'away': 'Roma', 'date': '2026-05-10', 'time': '18:00', 'hg': 2, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Milan', 'away': 'Atalanta', 'date': '2026-05-10', 'time': '20:45', 'hg': 2, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 36},
    {'home': 'Napoli', 'away': 'Bologna', 'date': '2026-05-10', 'time': '20:45', 'hg': 2, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 36},
    # R37 已结束
    {'home': 'Como', 'away': 'Parma', 'date': '2026-05-17', 'time': '12:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 37},
    {'home': 'Genoa', 'away': 'Milan', 'date': '2026-05-17', 'time': '12:00', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Juventus', 'away': 'Fiorentina', 'date': '2026-05-17', 'time': '12:00', 'hg': 0, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Pisa', 'away': 'Napoli', 'date': '2026-05-17', 'time': '12:00', 'hg': 0, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Roma', 'away': 'Lazio', 'date': '2026-05-17', 'time': '12:00', 'hg': 2, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 37},
    {'home': 'Inter', 'away': 'Verona', 'date': '2026-05-17', 'time': '15:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 37},
    {'home': 'Atalanta', 'away': 'Bologna', 'date': '2026-05-17', 'time': '18:00', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Cagliari', 'away': 'Torino', 'date': '2026-05-17', 'time': '20:45', 'hg': 2, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 37},
    {'home': 'Sassuolo', 'away': 'Lecce', 'date': '2026-05-17', 'time': '20:45', 'hg': 2, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 37},
    {'home': 'Udinese', 'away': 'Cremonese', 'date': '2026-05-17', 'time': '20:45', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 37},
    # R38 未开赛
    {'home': 'Fiorentina', 'away': 'Atalanta', 'date': '2026-05-22', 'time': '20:45', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Bologna', 'away': 'Inter', 'date': '2026-05-23', 'time': '18:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Lazio', 'away': 'Pisa', 'date': '2026-05-23', 'time': '20:45', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Parma', 'away': 'Sassuolo', 'date': '2026-05-23', 'time': '15:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Napoli', 'away': 'Udinese', 'date': '2026-05-24', 'time': '18:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Cremonese', 'away': 'Como', 'date': '2026-05-24', 'time': '20:45', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Lecce', 'away': 'Genoa', 'date': '2026-05-24', 'time': '20:45', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Milan', 'away': 'Cagliari', 'date': '2026-05-24', 'time': '20:45', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Verona', 'away': 'Roma', 'date': '2026-05-24', 'time': '20:45', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
    {'home': 'Torino', 'away': 'Juventus', 'date': '2026-05-24', 'time': '20:45', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 38},
]

# ============================================================
# 德甲 Bundesliga - R32-R34
# 北京时间 -> 德国当地时间（5月夏令时-6h）
# ============================================================
bundesliga_updates = [
    # R32 已结束
    {'home': 'Bayern Munich', 'away': 'Heidenheim', 'date': '2026-05-02', 'time': '15:30', 'hg': 3, 'ag': 3, 'result': 'D', 'status': 'finished', 'round': 32},
    {'home': 'Ein Frankfurt', 'away': 'Hamburg', 'date': '2026-05-02', 'time': '15:30', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 32},
    {'home': 'Werder Bremen', 'away': 'Augsburg', 'date': '2026-05-02', 'time': '15:30', 'hg': 1, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 32},
    {'home': 'Union Berlin', 'away': 'Koln', 'date': '2026-05-02', 'time': '15:30', 'hg': 2, 'ag': 2, 'result': 'D', 'status': 'finished', 'round': 32},
    {'home': 'Hoffenheim', 'away': 'Stuttgart', 'date': '2026-05-02', 'time': '15:30', 'hg': 3, 'ag': 3, 'result': 'D', 'status': 'finished', 'round': 32},
    {'home': 'Leverkusen', 'away': 'RB Leipzig', 'date': '2026-05-02', 'time': '18:30', 'hg': 4, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 32},
    {'home': 'St Pauli', 'away': 'Mainz', 'date': '2026-05-03', 'time': '15:30', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 32},
    {'home': "M'gladbach", 'away': 'Dortmund', 'date': '2026-05-03', 'time': '17:30', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 32},
    {'home': 'Freiburg', 'away': 'Wolfsburg', 'date': '2026-05-03', 'time': '19:30', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 32},
    # R33 已结束
    {'home': 'Dortmund', 'away': 'Ein Frankfurt', 'date': '2026-05-08', 'time': '20:30', 'hg': 3, 'ag': 2, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'RB Leipzig', 'away': 'St Pauli', 'date': '2026-05-09', 'time': '15:30', 'hg': 2, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Stuttgart', 'away': 'Leverkusen', 'date': '2026-05-09', 'time': '15:30', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Augsburg', 'away': "M'gladbach", 'date': '2026-05-09', 'time': '15:30', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Hoffenheim', 'away': 'Werder Bremen', 'date': '2026-05-09', 'time': '15:30', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Wolfsburg', 'away': 'Bayern Munich', 'date': '2026-05-09', 'time': '18:30', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 33},
    {'home': 'Hamburg', 'away': 'Freiburg', 'date': '2026-05-09', 'time': '15:30', 'hg': 3, 'ag': 2, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Koln', 'away': 'Heidenheim', 'date': '2026-05-09', 'time': '17:30', 'hg': 1, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 33},
    {'home': 'Mainz', 'away': 'Union Berlin', 'date': '2026-05-10', 'time': '19:30', 'hg': 1, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 33},
    # R34 已结束
    {'home': 'Bayern Munich', 'away': 'Koln', 'date': '2026-05-16', 'time': '15:30', 'hg': 5, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 34},
    {'home': 'Leverkusen', 'away': 'Hamburg', 'date': '2026-05-16', 'time': '15:30', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 34},
    {'home': 'Ein Frankfurt', 'away': 'Stuttgart', 'date': '2026-05-16', 'time': '15:30', 'hg': 2, 'ag': 2, 'result': 'D', 'status': 'finished', 'round': 34},
    {'home': 'Freiburg', 'away': 'RB Leipzig', 'date': '2026-05-16', 'time': '15:30', 'hg': 4, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 34},
    {'home': 'Werder Bremen', 'away': 'Dortmund', 'date': '2026-05-16', 'time': '15:30', 'hg': 0, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 34},
    {'home': "M'gladbach", 'away': 'Hoffenheim', 'date': '2026-05-16', 'time': '15:30', 'hg': 4, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 34},
    {'home': 'Union Berlin', 'away': 'Augsburg', 'date': '2026-05-16', 'time': '15:30', 'hg': 4, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 34},
    {'home': 'St Pauli', 'away': 'Wolfsburg', 'date': '2026-05-16', 'time': '15:30', 'hg': 1, 'ag': 3, 'result': 'A', 'status': 'finished', 'round': 34},
    {'home': 'Heidenheim', 'away': 'Mainz', 'date': '2026-05-16', 'time': '15:30', 'hg': 0, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 34},
]

# ============================================================
# 法甲 Ligue 1 - R32-R34
# 北京时间 -> 法国当地时间（5月夏令时-6h）
# ============================================================
ligue_1_updates = [
    # R32 已结束
    {'home': 'Nantes', 'away': 'Marseille', 'date': '2026-05-02', 'time': '15:00', 'hg': 3, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 32},
    {'home': 'Paris SG', 'away': 'Lorient', 'date': '2026-05-02', 'time': '17:00', 'hg': 2, 'ag': 2, 'result': 'D', 'status': 'finished', 'round': 32},
    {'home': 'Metz', 'away': 'Monaco', 'date': '2026-05-02', 'time': '19:00', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 32},
    {'home': 'Nice', 'away': 'Lens', 'date': '2026-05-02', 'time': '21:05', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 32},
    {'home': 'Lille', 'away': 'Le Havre', 'date': '2026-05-03', 'time': '15:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 32},
    {'home': 'Strasbourg', 'away': 'Toulouse', 'date': '2026-05-03', 'time': '17:15', 'hg': 1, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 32},
    {'home': 'Paris FC', 'away': 'Brest', 'date': '2026-05-03', 'time': '17:15', 'hg': 4, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 32},
    {'home': 'Auxerre', 'away': 'Angers', 'date': '2026-05-03', 'time': '17:15', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 32},
    {'home': 'Lyon', 'away': 'Rennes', 'date': '2026-05-03', 'time': '20:45', 'hg': 4, 'ag': 2, 'result': 'H', 'status': 'finished', 'round': 32},
    # R33 已结束
    {'home': 'Lens', 'away': 'Nantes', 'date': '2026-05-08', 'time': '20:45', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Paris SG', 'away': 'Brest', 'date': '2026-05-10', 'time': '21:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Le Havre', 'away': 'Marseille', 'date': '2026-05-10', 'time': '21:00', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 33},
    {'home': 'Toulouse', 'away': 'Lyon', 'date': '2026-05-10', 'time': '21:00', 'hg': 2, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Auxerre', 'away': 'Nice', 'date': '2026-05-10', 'time': '21:00', 'hg': 2, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Rennes', 'away': 'Paris FC', 'date': '2026-05-10', 'time': '21:00', 'hg': 2, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 33},
    {'home': 'Metz', 'away': 'Lorient', 'date': '2026-05-10', 'time': '21:00', 'hg': 0, 'ag': 4, 'result': 'A', 'status': 'finished', 'round': 33},
    {'home': 'Angers', 'away': 'Strasbourg', 'date': '2026-05-10', 'time': '21:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 33},
    {'home': 'Monaco', 'away': 'Lille', 'date': '2026-05-10', 'time': '21:00', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished', 'round': 33},
    # R34 部分已结束
    {'home': 'Lorient', 'away': 'Le Havre', 'date': '2026-05-17', 'time': '21:00', 'hg': 0, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 34},
    {'home': 'Nantes', 'away': 'Toulouse', 'date': '2026-05-17', 'time': '21:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled', 'round': 34},
    {'home': 'Lille', 'away': 'Auxerre', 'date': '2026-05-17', 'time': '21:00', 'hg': 0, 'ag': 2, 'result': 'A', 'status': 'finished', 'round': 34},
    {'home': 'Nice', 'away': 'Metz', 'date': '2026-05-17', 'time': '21:00', 'hg': 0, 'ag': 0, 'result': 'D', 'status': 'finished', 'round': 34},
    {'home': 'Brest', 'away': 'Angers', 'date': '2026-05-17', 'time': '21:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished', 'round': 34},
    {'home': 'Paris FC', 'away': 'Paris SG', 'date': '2026-05-17', 'time': '21:00', 'hg': 2, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 34},
    {'home': 'Marseille', 'away': 'Rennes', 'date': '2026-05-17', 'time': '21:00', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished', 'round': 34},
    {'home': 'Strasbourg', 'away': 'Monaco', 'date': '2026-05-17', 'time': '21:00', 'hg': 5, 'ag': 4, 'result': 'H', 'status': 'finished', 'round': 34},
    {'home': 'Lyon', 'away': 'Lens', 'date': '2026-05-17', 'time': '21:00', 'hg': 0, 'ag': 4, 'result': 'A', 'status': 'finished', 'round': 34},
]

# ============================================================
# 处理每个联赛
# ============================================================

league_configs = {
    'la_liga': {
        'path': 'd:/football_tools/new_data/matches/clubs/leagues/la_liga/la_liga_2025-2026.csv',
        'division': 'la_liga',
        'updates': la_liga_updates,
    },
    'bundesliga': {
        'path': 'd:/football_tools/new_data/matches/clubs/leagues/bundesliga/bundesliga_2025-2026.csv',
        'division': 'bundesliga',
        'updates': bundesliga_updates,
    },
    'serie_a': {
        'path': 'd:/football_tools/new_data/matches/clubs/leagues/serie_a/serie_a_2025-2026.csv',
        'division': 'serie_a',
        'updates': serie_a_updates,
    },
    'ligue_1': {
        'path': 'd:/football_tools/new_data/matches/clubs/leagues/ligue_1/ligue_1_2025-2026.csv',
        'division': 'ligue_1',
        'updates': ligue_1_updates,
    },
}

for league_name, config in league_configs.items():
    print(f'\n{"="*60}')
    print(f'Processing {league_name}')
    print(f'{"="*60}')

    df = pd.read_csv(config['path'])
    print(f'Before: {len(df)} rows')

    # 1. Update/add match data
    updated = 0
    added = 0
    for u in config['updates']:
        mask = (df['home_team'] == u['home']) & (df['away_team'] == u['away'])
        if mask.any():
            idx = df[mask].index[0]
            df.loc[idx, 'match_date'] = u['date']
            df.loc[idx, 'match_time'] = u['time']
            df.loc[idx, 'home_goals'] = u['hg']
            df.loc[idx, 'away_goals'] = u['ag']
            df.loc[idx, 'result'] = u['result']
            df.loc[idx, 'status'] = u['status']
            df.loc[idx, 'round_num'] = u['round']
            updated += 1
        else:
            new_row = {
                'season': '2025-2026',
                'match_date': u['date'],
                'match_time': u['time'],
                'round_num': u['round'],
                'division': config['division'],
                'home_team': u['home'],
                'away_team': u['away'],
                'home_goals': u['hg'],
                'away_goals': u['ag'],
                'result': u['result'],
                'status': u['status'],
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            added += 1

    print(f'Updated: {updated}, Added: {added}')

    # 2. Sort by date
    df = df.sort_values('match_date').reset_index(drop=True)

    # 3. Fill round_num using team count method (only for rows without round_num)
    team_count = {}
    for idx, row in df.iterrows():
        home = row['home_team']
        away = row['away_team']
        team_count[home] = team_count.get(home, 0) + 1
        team_count[away] = team_count.get(away, 0) + 1
        if pd.isna(row['round_num']) or row['round_num'] == 0:
            df.loc[idx, 'round_num'] = team_count[home]

    # 4. Save
    df.to_csv(config['path'], index=False)

    # 5. Verify
    teams = sorted(set(df['home_team'].unique()) | set(df['away_team'].unique()))
    per_round = len(teams) // 2
    max_round = int(df['round_num'].max())
    finished = len(df[df['status'] == 'finished'])
    scheduled = len(df[df['status'] == 'scheduled'])

    print(f'\nAfter: {len(df)} rows, {len(teams)} teams')
    print(f'Finished: {finished}, Scheduled: {scheduled}')
    print(f'Per round: {per_round}, Max round: {max_round}')

    wrong_rounds = []
    for r in range(1, max_round + 1):
        count = len(df[df['round_num'] == r])
        if count != per_round:
            wrong_rounds.append(f'R{r}:{count}')

    if wrong_rounds:
        print(f'Uneven rounds: {wrong_rounds[:20]}')
    else:
        print('All rounds even OK')

    # Show last few rounds
    for r in range(max(1, max_round - 2), max_round + 1):
        round_df = df[df['round_num'] == r]
        print(f'\nR{r} ({len(round_df)} matches):')
        for _, row in round_df.iterrows():
            hg = int(row['home_goals']) if pd.notna(row['home_goals']) else ''
            ag = int(row['away_goals']) if pd.notna(row['away_goals']) else ''
            score = f'{hg}-{ag}' if hg != '' else 'vs'
            print(f"  {row['match_date']} {row['match_time']} {row['home_team']} {score} {row['away_team']} {row['status']}")
