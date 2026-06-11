import pandas as pd
import os

# 2026年解放者杯小组赛数据
matches = []

# A组
a_group = [
    # 第1轮
    {'round': 'A_1', 'match_date': '2026-04-09', 'match_time': '08:00', 'home_team': 'Independiente Medellin', 'away_team': 'Estudiantes LP', 'home_goals': 1, 'away_goals': 1, 'home_odds': 2.53, 'draw_odds': 2.91, 'away_odds': 2.88, 'status': 'finished'},
    {'round': 'A_1', 'match_date': '2026-04-09', 'match_time': '08:30', 'home_team': 'Cusco FC', 'away_team': 'Flamengo', 'home_goals': 0, 'away_goals': 2, 'home_odds': 4.99, 'draw_odds': 3.50, 'away_odds': 1.65, 'status': 'finished'},
    # 第2轮
    {'round': 'A_2', 'match_date': '2026-04-15', 'match_time': '06:00', 'home_team': 'Estudiantes LP', 'away_team': 'Cusco FC', 'home_goals': 2, 'away_goals': 1, 'home_odds': 1.25, 'draw_odds': 5.12, 'away_odds': 10.41, 'status': 'finished'},
    {'round': 'A_2', 'match_date': '2026-04-17', 'match_time': '08:30', 'home_team': 'Flamengo', 'away_team': 'Independiente Medellin', 'home_goals': 4, 'away_goals': 1, 'home_odds': 1.24, 'draw_odds': 5.15, 'away_odds': 10.63, 'status': 'finished'},
    # 第3轮
    {'round': 'A_3', 'match_date': '2026-04-30', 'match_time': '08:30', 'home_team': 'Estudiantes LP', 'away_team': 'Flamengo', 'home_goals': 1, 'away_goals': 1, 'home_odds': 3.44, 'draw_odds': 3.01, 'away_odds': 2.14, 'status': 'finished'},
    {'round': 'A_3', 'match_date': '2026-05-01', 'match_time': '10:00', 'home_team': 'Independiente Medellin', 'away_team': 'Cusco FC', 'home_goals': 1, 'away_goals': 0, 'home_odds': 1.49, 'draw_odds': 4.22, 'away_odds': 5.50, 'status': 'finished'},
    # 第4轮
    {'round': 'A_4', 'match_date': '2026-05-07', 'match_time': '06:00', 'home_team': 'Cusco FC', 'away_team': 'Estudiantes LP', 'home_goals': 1, 'away_goals': 1, 'home_odds': 2.41, 'draw_odds': 3.18, 'away_odds': 2.76, 'status': 'finished'},
    {'round': 'A_4', 'match_date': '2026-05-08', 'match_time': '08:30', 'home_team': 'Independiente Medellin', 'away_team': 'Flamengo', 'home_goals': None, 'away_goals': None, 'home_odds': 3.95, 'draw_odds': 3.52, 'away_odds': 1.80, 'status': 'scheduled'},
    # 第5轮
    {'round': 'A_5', 'match_date': '2026-05-21', 'match_time': '08:30', 'home_team': 'Flamengo', 'away_team': 'Estudiantes LP', 'home_goals': None, 'away_goals': None, 'home_odds': 1.33, 'draw_odds': 4.27, 'away_odds': 9.30, 'status': 'scheduled'},
    {'round': 'A_5', 'match_date': '2026-05-21', 'match_time': '10:00', 'home_team': 'Cusco FC', 'away_team': 'Independiente Medellin', 'home_goals': None, 'away_goals': None, 'home_odds': 3.16, 'draw_odds': 3.14, 'away_odds': 2.18, 'status': 'scheduled'},
    # 第6轮
    {'round': 'A_6', 'match_date': '2026-05-27', 'match_time': '08:30', 'home_team': 'Flamengo', 'away_team': 'Cusco FC', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
    {'round': 'A_6', 'match_date': '2026-05-27', 'match_time': '08:30', 'home_team': 'Estudiantes LP', 'away_team': 'Independiente Medellin', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
]
matches.extend(a_group)

# B组
b_group = [
    # 第1轮
    {'round': 'B_1', 'match_date': '2026-04-08', 'match_time': '10:00', 'home_team': 'Deportes Tolima', 'away_team': 'Estudiantes de La Plata', 'home_goals': 0, 'away_goals': 0, 'home_odds': 2.18, 'draw_odds': 2.86, 'away_odds': 3.72, 'status': 'finished'},
    {'round': 'B_1', 'match_date': '2026-04-09', 'match_time': '06:00', 'home_team': 'Coquimbo Unido', 'away_team': 'Nacional', 'home_goals': 1, 'away_goals': 1, 'home_odds': 2.34, 'draw_odds': 2.94, 'away_odds': 3.08, 'status': 'finished'},
    # 第2轮
    {'round': 'B_2', 'match_date': '2026-04-15', 'match_time': '06:00', 'home_team': 'Nacional', 'away_team': 'Deportes Tolima', 'home_goals': 3, 'away_goals': 1, 'home_odds': 1.82, 'draw_odds': 3.35, 'away_odds': 4.29, 'status': 'finished'},
    {'round': 'B_2', 'match_date': '2026-04-15', 'match_time': '10:00', 'home_team': 'Estudiantes de La Plata', 'away_team': 'Coquimbo Unido', 'home_goals': 0, 'away_goals': 2, 'home_odds': 2.21, 'draw_odds': 3.15, 'away_odds': 3.18, 'status': 'finished'},
    # 第3轮
    {'round': 'B_3', 'match_date': '2026-04-29', 'match_time': '10:00', 'home_team': 'Deportes Tolima', 'away_team': 'Coquimbo Unido', 'home_goals': 3, 'away_goals': 0, 'home_odds': 2.04, 'draw_odds': 3.09, 'away_odds': 3.60, 'status': 'finished'},
    {'round': 'B_3', 'match_date': '2026-04-30', 'match_time': '10:00', 'home_team': 'Estudiantes de La Plata', 'away_team': 'Nacional', 'home_goals': 4, 'away_goals': 2, 'home_odds': 2.18, 'draw_odds': 3.10, 'away_odds': 3.27, 'status': 'finished'},
    # 第4轮
    {'round': 'B_4', 'match_date': '2026-05-07', 'match_time': '10:00', 'home_team': 'Deportes Tolima', 'away_team': 'Nacional', 'home_goals': 3, 'away_goals': 0, 'home_odds': 1.99, 'draw_odds': 3.21, 'away_odds': 3.64, 'status': 'finished'},
    {'round': 'B_4', 'match_date': '2026-05-08', 'match_time': '08:00', 'home_team': 'Coquimbo Unido', 'away_team': 'Estudiantes de La Plata', 'home_goals': 2, 'away_goals': 1, 'home_odds': 1.95, 'draw_odds': 3.20, 'away_odds': 3.76, 'status': 'finished'},
    # 第5轮
    {'round': 'B_5', 'match_date': '2026-05-20', 'match_time': '06:00', 'home_team': 'Coquimbo Unido', 'away_team': 'Deportes Tolima', 'home_goals': None, 'away_goals': None, 'home_odds': 2.32, 'draw_odds': 3.15, 'away_odds': 3.04, 'status': 'scheduled'},
    {'round': 'B_5', 'match_date': '2026-05-21', 'match_time': '06:00', 'home_team': 'Nacional', 'away_team': 'Estudiantes de La Plata', 'home_goals': None, 'away_goals': None, 'home_odds': 1.82, 'draw_odds': 3.38, 'away_odds': 4.05, 'status': 'scheduled'},
    # 第6轮
    {'round': 'B_6', 'match_date': '2026-05-27', 'match_time': '08:30', 'home_team': 'Nacional', 'away_team': 'Coquimbo Unido', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
    {'round': 'B_6', 'match_date': '2026-05-27', 'match_time': '08:30', 'home_team': 'Estudiantes de La Plata', 'away_team': 'Deportes Tolima', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
]
matches.extend(b_group)

# C组
c_group = [
    # 第1轮
    {'round': 'C_1', 'match_date': '2026-04-08', 'match_time': '06:00', 'home_team': 'Independiente Rivadavia', 'away_team': 'Bolivar', 'home_goals': 1, 'away_goals': 0, 'home_odds': 1.56, 'draw_odds': 3.82, 'away_odds': 5.50, 'status': 'finished'},
    {'round': 'C_1', 'match_date': '2026-04-08', 'match_time': '06:00', 'home_team': 'Deportivo La Guaira', 'away_team': 'Fluminense', 'home_goals': 0, 'away_goals': 0, 'home_odds': 4.75, 'draw_odds': 3.52, 'away_odds': 1.70, 'status': 'finished'},
    # 第2轮
    {'round': 'C_2', 'match_date': '2026-04-15', 'match_time': '08:00', 'home_team': 'Bolivar', 'away_team': 'Deportivo La Guaira', 'home_goals': 1, 'away_goals': 1, 'home_odds': 1.17, 'draw_odds': 6.88, 'away_odds': 13.05, 'status': 'finished'},
    {'round': 'C_2', 'match_date': '2026-04-16', 'match_time': '08:30', 'home_team': 'Fluminense', 'away_team': 'Independiente Rivadavia', 'home_goals': 1, 'away_goals': 2, 'home_odds': 1.34, 'draw_odds': 4.64, 'away_odds': 8.82, 'status': 'finished'},
    # 第3轮
    {'round': 'C_3', 'match_date': '2026-05-01', 'match_time': '06:00', 'home_team': 'Bolivar', 'away_team': 'Fluminense', 'home_goals': 2, 'away_goals': 0, 'home_odds': 1.74, 'draw_odds': 3.57, 'away_odds': 4.34, 'status': 'finished'},
    {'round': 'C_3', 'match_date': '2026-05-01', 'match_time': '06:00', 'home_team': 'Independiente Rivadavia', 'away_team': 'Deportivo La Guaira', 'home_goals': 4, 'away_goals': 1, 'home_odds': 1.50, 'draw_odds': 3.87, 'away_odds': 6.09, 'status': 'finished'},
    # 第4轮
    {'round': 'C_4', 'match_date': '2026-05-07', 'match_time': '06:00', 'home_team': 'Deportivo La Guaira', 'away_team': 'Bolivar', 'home_goals': 1, 'away_goals': 1, 'home_odds': 2.17, 'draw_odds': 3.39, 'away_odds': 2.97, 'status': 'finished'},
    {'round': 'C_4', 'match_date': '2026-05-07', 'match_time': '08:30', 'home_team': 'Independiente Rivadavia', 'away_team': 'Fluminense', 'home_goals': 1, 'away_goals': 1, 'home_odds': 2.90, 'draw_odds': 3.09, 'away_odds': 2.37, 'status': 'finished'},
    # 第5轮
    {'round': 'C_5', 'match_date': '2026-05-20', 'match_time': '06:00', 'home_team': 'Fluminense', 'away_team': 'Bolivar', 'home_goals': None, 'away_goals': None, 'home_odds': 1.25, 'draw_odds': 5.13, 'away_odds': 10.56, 'status': 'scheduled'},
    {'round': 'C_5', 'match_date': '2026-05-22', 'match_time': '06:00', 'home_team': 'Deportivo La Guaira', 'away_team': 'Independiente Rivadavia', 'home_goals': None, 'away_goals': None, 'home_odds': 5.11, 'draw_odds': 3.63, 'away_odds': 1.61, 'status': 'scheduled'},
    # 第6轮
    {'round': 'C_6', 'match_date': '2026-05-28', 'match_time': '08:30', 'home_team': 'Fluminense', 'away_team': 'Deportivo La Guaira', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
    {'round': 'C_6', 'match_date': '2026-05-28', 'match_time': '08:30', 'home_team': 'Bolivar', 'away_team': 'Independiente Rivadavia', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
]
matches.extend(c_group)

# D组
d_group = [
    # 第1轮
    {'round': 'D_1', 'match_date': '2026-04-08', 'match_time': '08:00', 'home_team': 'Barcelona SC', 'away_team': 'Cruzeiro', 'home_goals': 0, 'away_goals': 1, 'home_odds': 3.19, 'draw_odds': 3.01, 'away_odds': 2.31, 'status': 'finished'},
    {'round': 'D_1', 'match_date': '2026-04-08', 'match_time': '08:30', 'home_team': 'Universidad Catolica', 'away_team': 'Boca Juniors', 'home_goals': 1, 'away_goals': 2, 'home_odds': 3.45, 'draw_odds': 3.05, 'away_odds': 2.12, 'status': 'finished'},
    # 第2轮
    {'round': 'D_2', 'match_date': '2026-04-15', 'match_time': '08:00', 'home_team': 'Boca Juniors', 'away_team': 'Barcelona SC', 'home_goals': 3, 'away_goals': 0, 'home_odds': 1.52, 'draw_odds': 3.95, 'away_odds': 5.99, 'status': 'finished'},
    {'round': 'D_2', 'match_date': '2026-04-16', 'match_time': '06:00', 'home_team': 'Cruzeiro', 'away_team': 'Universidad Catolica', 'home_goals': 1, 'away_goals': 2, 'home_odds': 1.35, 'draw_odds': 4.65, 'away_odds': 8.06, 'status': 'finished'},
    # 第3轮
    {'round': 'D_3', 'match_date': '2026-04-29', 'match_time': '08:30', 'home_team': 'Cruzeiro', 'away_team': 'Boca Juniors', 'home_goals': 1, 'away_goals': 0, 'home_odds': 1.88, 'draw_odds': 3.21, 'away_odds': 4.06, 'status': 'finished'},
    {'round': 'D_3', 'match_date': '2026-04-30', 'match_time': '08:00', 'home_team': 'Barcelona SC', 'away_team': 'Universidad Catolica', 'home_goals': 1, 'away_goals': 2, 'home_odds': 2.08, 'draw_odds': 3.19, 'away_odds': 3.40, 'status': 'finished'},
    # 第4轮
    {'round': 'D_4', 'match_date': '2026-05-06', 'match_time': '08:00', 'home_team': 'Barcelona SC', 'away_team': 'Boca Juniors', 'home_goals': 1, 'away_goals': 0, 'home_odds': 2.88, 'draw_odds': 3.16, 'away_odds': 2.39, 'status': 'finished'},
    {'round': 'D_4', 'match_date': '2026-05-07', 'match_time': '10:00', 'home_team': 'Universidad Catolica', 'away_team': 'Cruzeiro', 'home_goals': 0, 'away_goals': 0, 'home_odds': 3.05, 'draw_odds': 3.14, 'away_odds': 2.24, 'status': 'finished'},
    # 第5轮
    {'round': 'D_5', 'match_date': '2026-05-20', 'match_time': '08:30', 'home_team': 'Boca Juniors', 'away_team': 'Cruzeiro', 'home_goals': None, 'away_goals': None, 'home_odds': 2.09, 'draw_odds': 3.11, 'away_odds': 3.38, 'status': 'scheduled'},
    {'round': 'D_5', 'match_date': '2026-05-22', 'match_time': '08:30', 'home_team': 'Universidad Catolica', 'away_team': 'Barcelona SC', 'home_goals': None, 'away_goals': None, 'home_odds': 1.74, 'draw_odds': 3.46, 'away_odds': 4.40, 'status': 'scheduled'},
    # 第6轮
    {'round': 'D_6', 'match_date': '2026-05-29', 'match_time': '08:30', 'home_team': 'Boca Juniors', 'away_team': 'Universidad Catolica', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
    {'round': 'D_6', 'match_date': '2026-05-29', 'match_time': '08:30', 'home_team': 'Cruzeiro', 'away_team': 'Barcelona SC', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
]
matches.extend(d_group)

# E组
e_group = [
    # 第1轮
    {'round': 'E_1', 'match_date': '2026-04-10', 'match_time': '08:00', 'home_team': 'Platense', 'away_team': 'Corinthians', 'home_goals': 0, 'away_goals': 2, 'home_odds': 2.93, 'draw_odds': 2.81, 'away_odds': 2.69, 'status': 'finished'},
    {'round': 'E_1', 'match_date': '2026-04-10', 'match_time': '10:00', 'home_team': 'Independiente Santa Fe', 'away_team': 'Penarol', 'home_goals': 1, 'away_goals': 1, 'home_odds': 2.45, 'draw_odds': 2.95, 'away_odds': 3.11, 'status': 'finished'},
    # 第2轮
    {'round': 'E_2', 'match_date': '2026-04-16', 'match_time': '08:30', 'home_team': 'Corinthians', 'away_team': 'Independiente Santa Fe', 'home_goals': 2, 'away_goals': 0, 'home_odds': 1.37, 'draw_odds': 4.60, 'away_odds': 7.15, 'status': 'finished'},
    {'round': 'E_2', 'match_date': '2026-04-17', 'match_time': '08:30', 'home_team': 'Penarol', 'away_team': 'Platense', 'home_goals': 1, 'away_goals': 2, 'home_odds': 1.64, 'draw_odds': 3.69, 'away_odds': 4.91, 'status': 'finished'},
    # 第3轮
    {'round': 'E_3', 'match_date': '2026-04-30', 'match_time': '06:00', 'home_team': 'Platense', 'away_team': 'Independiente Santa Fe', 'home_goals': 2, 'away_goals': 1, 'home_odds': 2.08, 'draw_odds': 3.15, 'away_odds': 3.45, 'status': 'finished'},
    {'round': 'E_3', 'match_date': '2026-05-01', 'match_time': '08:00', 'home_team': 'Corinthians', 'away_team': 'Penarol', 'home_goals': 2, 'away_goals': 0, 'home_odds': 1.58, 'draw_odds': 3.54, 'away_odds': 5.79, 'status': 'finished'},
    # 第4轮
    {'round': 'E_4', 'match_date': '2026-05-07', 'match_time': '08:30', 'home_team': 'Independiente Santa Fe', 'away_team': 'Corinthians', 'home_goals': 1, 'away_goals': 1, 'home_odds': 2.82, 'draw_odds': 3.04, 'away_odds': 2.46, 'status': 'finished'},
    {'round': 'E_4', 'match_date': '2026-05-08', 'match_time': '06:00', 'home_team': 'Platense', 'away_team': 'Penarol', 'home_goals': 1, 'away_goals': 1, 'home_odds': 2.60, 'draw_odds': 2.95, 'away_odds': 2.72, 'status': 'finished'},
    # 第5轮
    {'round': 'E_5', 'match_date': '2026-05-20', 'match_time': '08:00', 'home_team': 'Independiente Santa Fe', 'away_team': 'Platense', 'home_goals': None, 'away_goals': None, 'home_odds': 1.84, 'draw_odds': 3.39, 'away_odds': 4.05, 'status': 'scheduled'},
    {'round': 'E_5', 'match_date': '2026-05-22', 'match_time': '08:30', 'home_team': 'Penarol', 'away_team': 'Corinthians', 'home_goals': None, 'away_goals': None, 'home_odds': 2.45, 'draw_odds': 3.32, 'away_odds': 2.64, 'status': 'scheduled'},
    # 第6轮
    {'round': 'E_6', 'match_date': '2026-05-28', 'match_time': '08:30', 'home_team': 'Penarol', 'away_team': 'Independiente Santa Fe', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
    {'round': 'E_6', 'match_date': '2026-05-28', 'match_time': '08:30', 'home_team': 'Corinthians', 'away_team': 'Platense', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
]
matches.extend(e_group)

# F组
f_group = [
    # 第1轮
    {'round': 'F_1', 'match_date': '2026-04-09', 'match_time': '08:30', 'home_team': 'Junior Barranquilla', 'away_team': 'Palmeiras', 'home_goals': 1, 'away_goals': 1, 'home_odds': 3.72, 'draw_odds': 3.27, 'away_odds': 1.98, 'status': 'finished'},
    {'round': 'F_1', 'match_date': '2026-04-09', 'match_time': '10:00', 'home_team': 'Sporting Cristal', 'away_team': 'Cerro Porteno', 'home_goals': 1, 'away_goals': 0, 'home_odds': 2.47, 'draw_odds': 3.07, 'away_odds': 2.90, 'status': 'finished'},
    # 第2轮
    {'round': 'F_2', 'match_date': '2026-04-15', 'match_time': '06:00', 'home_team': 'Cerro Porteno', 'away_team': 'Junior Barranquilla', 'home_goals': 1, 'away_goals': 0, 'home_odds': 2.01, 'draw_odds': 3.31, 'away_odds': 3.60, 'status': 'finished'},
    {'round': 'F_2', 'match_date': '2026-04-17', 'match_time': '06:00', 'home_team': 'Palmeiras', 'away_team': 'Sporting Cristal', 'home_goals': 2, 'away_goals': 1, 'home_odds': 1.14, 'draw_odds': 7.19, 'away_odds': 16.13, 'status': 'finished'},
    # 第3轮
    {'round': 'F_3', 'match_date': '2026-04-29', 'match_time': '10:00', 'home_team': 'Sporting Cristal', 'away_team': 'Junior Barranquilla', 'home_goals': 2, 'away_goals': 0, 'home_odds': 2.83, 'draw_odds': 3.10, 'away_odds': 2.43, 'status': 'finished'},
    {'round': 'F_3', 'match_date': '2026-04-30', 'match_time': '08:30', 'home_team': 'Cerro Porteno', 'away_team': 'Palmeiras', 'home_goals': 1, 'away_goals': 1, 'home_odds': 4.66, 'draw_odds': 3.23, 'away_odds': 1.78, 'status': 'finished'},
    # 第4轮
    {'round': 'F_4', 'match_date': '2026-05-06', 'match_time': '06:00', 'home_team': 'Sporting Cristal', 'away_team': 'Palmeiras', 'home_goals': 0, 'away_goals': 2, 'home_odds': 4.26, 'draw_odds': 3.47, 'away_odds': 1.81, 'status': 'finished'},
    {'round': 'F_4', 'match_date': '2026-05-08', 'match_time': '10:00', 'home_team': 'Junior Barranquilla', 'away_team': 'Cerro Porteno', 'home_goals': 0, 'away_goals': 1, 'home_odds': 1.84, 'draw_odds': 3.27, 'away_odds': 4.13, 'status': 'finished'},
    # 第5轮
    {'round': 'F_5', 'match_date': '2026-05-21', 'match_time': '08:30', 'home_team': 'Palmeiras', 'away_team': 'Cerro Porteno', 'home_goals': None, 'away_goals': None, 'home_odds': 1.27, 'draw_odds': 4.84, 'away_odds': 9.95, 'status': 'scheduled'},
    {'round': 'F_5', 'match_date': '2026-05-21', 'match_time': '10:00', 'home_team': 'Junior Barranquilla', 'away_team': 'Sporting Cristal', 'home_goals': None, 'away_goals': None, 'home_odds': 1.77, 'draw_odds': 3.56, 'away_odds': 4.18, 'status': 'scheduled'},
    # 第6轮
    {'round': 'F_6', 'match_date': '2026-05-29', 'match_time': '06:00', 'home_team': 'Palmeiras', 'away_team': 'Junior Barranquilla', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
    {'round': 'F_6', 'match_date': '2026-05-29', 'match_time': '06:00', 'home_team': 'Cerro Porteno', 'away_team': 'Sporting Cristal', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
]
matches.extend(f_group)

# G组
g_group = [
    # 第1轮
    {'round': 'G_1', 'match_date': '2026-04-08', 'match_time': '08:00', 'home_team': 'Always Ready', 'away_team': 'LDU Quito', 'home_goals': 0, 'away_goals': 1, 'home_odds': 2.34, 'draw_odds': 3.38, 'away_odds': 2.72, 'status': 'finished'},
    {'round': 'G_1', 'match_date': '2026-04-09', 'match_time': '06:00', 'home_team': 'Mylar Sol', 'away_team': 'Lanus', 'home_goals': 1, 'away_goals': 0, 'home_odds': 1.92, 'draw_odds': 3.11, 'away_odds': 4.13, 'status': 'finished'},
    # 第2轮
    {'round': 'G_2', 'match_date': '2026-04-15', 'match_time': '10:00', 'home_team': 'LDU Quito', 'away_team': 'Mylar Sol', 'home_goals': 2, 'away_goals': 0, 'home_odds': 1.71, 'draw_odds': 3.60, 'away_odds': 4.64, 'status': 'finished'},
    {'round': 'G_2', 'match_date': '2026-04-17', 'match_time': '06:00', 'home_team': 'Lanus', 'away_team': 'Always Ready', 'home_goals': 1, 'away_goals': 0, 'home_odds': 1.18, 'draw_odds': 6.22, 'away_odds': 14.50, 'status': 'finished'},
    # 第3轮
    {'round': 'G_3', 'match_date': '2026-04-29', 'match_time': '06:00', 'home_team': 'Lanus', 'away_team': 'LDU Quito', 'home_goals': 1, 'away_goals': 0, 'home_odds': 1.63, 'draw_odds': 3.55, 'away_odds': 5.14, 'status': 'finished'},
    {'round': 'G_3', 'match_date': '2026-04-30', 'match_time': '06:00', 'home_team': 'Mylar Sol', 'away_team': 'Always Ready', 'home_goals': 2, 'away_goals': 0, 'home_odds': 1.22, 'draw_odds': 5.69, 'away_odds': 10.89, 'status': 'finished'},
    # 第4轮
    {'round': 'G_4', 'match_date': '2026-05-06', 'match_time': '08:30', 'home_team': 'Always Ready', 'away_team': 'Lanus', 'home_goals': 4, 'away_goals': 0, 'home_odds': 1.62, 'draw_odds': 3.76, 'away_odds': 5.11, 'status': 'finished'},
    {'round': 'G_4', 'match_date': '2026-05-08', 'match_time': '06:00', 'home_team': 'Mylar Sol', 'away_team': 'LDU Quito', 'home_goals': 2, 'away_goals': 0, 'home_odds': 1.68, 'draw_odds': 3.49, 'away_odds': 4.87, 'status': 'finished'},
    # 第5轮
    {'round': 'G_5', 'match_date': '2026-05-20', 'match_time': '08:00', 'home_team': 'Always Ready', 'away_team': 'Mylar Sol', 'home_goals': None, 'away_goals': None, 'home_odds': 1.58, 'draw_odds': 4.00, 'away_odds': 4.80, 'status': 'scheduled'},
    {'round': 'G_5', 'match_date': '2026-05-21', 'match_time': '08:30', 'home_team': 'LDU Quito', 'away_team': 'Lanus', 'home_goals': None, 'away_goals': None, 'home_odds': 1.62, 'draw_odds': 3.77, 'away_odds': 4.76, 'status': 'scheduled'},
    # 第6轮
    {'round': 'G_6', 'match_date': '2026-05-27', 'match_time': '06:00', 'home_team': 'LDU Quito', 'away_team': 'Always Ready', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
    {'round': 'G_6', 'match_date': '2026-05-27', 'match_time': '06:00', 'home_team': 'Lanus', 'away_team': 'Mylar Sol', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
]
matches.extend(g_group)

# H组
h_group = [
    # 第1轮
    {'round': 'H_1', 'match_date': '2026-04-10', 'match_time': '06:00', 'home_team': 'Universidad Central', 'away_team': 'Libertad', 'home_goals': 3, 'away_goals': 1, 'home_odds': 3.06, 'draw_odds': 3.00, 'away_odds': 2.40, 'status': 'finished'},
    {'round': 'H_1', 'match_date': '2026-04-10', 'match_time': '06:00', 'home_team': 'Rosario Central', 'away_team': 'Independiente del Valle', 'home_goals': 0, 'away_goals': 0, 'home_odds': 1.80, 'draw_odds': 3.17, 'away_odds': 4.80, 'status': 'finished'},
    # 第2轮
    {'round': 'H_2', 'match_date': '2026-04-16', 'match_time': '06:00', 'home_team': 'Libertad', 'away_team': 'Rosario Central', 'home_goals': 0, 'away_goals': 1, 'home_odds': 2.81, 'draw_odds': 3.14, 'away_odds': 2.47, 'status': 'finished'},
    {'round': 'H_2', 'match_date': '2026-04-16', 'match_time': '10:00', 'home_team': 'Independiente del Valle', 'away_team': 'Universidad Central', 'home_goals': 3, 'away_goals': 1, 'home_odds': 1.24, 'draw_odds': 5.73, 'away_odds': 9.82, 'status': 'finished'},
    # 第3轮
    {'round': 'H_3', 'match_date': '2026-04-29', 'match_time': '06:00', 'home_team': 'Libertad', 'away_team': 'Independiente del Valle', 'home_goals': 2, 'away_goals': 3, 'home_odds': 2.66, 'draw_odds': 3.26, 'away_odds': 2.46, 'status': 'finished'},
    {'round': 'H_3', 'match_date': '2026-04-29', 'match_time': '08:00', 'home_team': 'Universidad Central', 'away_team': 'Rosario Central', 'home_goals': 0, 'away_goals': 3, 'home_odds': 4.43, 'draw_odds': 3.37, 'away_odds': 1.77, 'status': 'finished'},
    # 第4轮
    {'round': 'H_4', 'match_date': '2026-05-06', 'match_time': '06:00', 'home_team': 'Rosario Central', 'away_team': 'Libertad', 'home_goals': 1, 'away_goals': 0, 'home_odds': 1.48, 'draw_odds': 4.09, 'away_odds': 6.34, 'status': 'finished'},
    {'round': 'H_4', 'match_date': '2026-05-06', 'match_time': '08:00', 'home_team': 'Universidad Central', 'away_team': 'Independiente del Valle', 'home_goals': 2, 'away_goals': 0, 'home_odds': 4.23, 'draw_odds': 3.63, 'away_odds': 1.77, 'status': 'finished'},
    # 第5轮
    {'round': 'H_5', 'match_date': '2026-05-20', 'match_time': '06:00', 'home_team': 'Rosario Central', 'away_team': 'Universidad Central', 'home_goals': None, 'away_goals': None, 'home_odds': 1.24, 'draw_odds': 5.40, 'away_odds': 10.38, 'status': 'scheduled'},
    {'round': 'H_5', 'match_date': '2026-05-20', 'match_time': '10:00', 'home_team': 'Independiente del Valle', 'away_team': 'Libertad', 'home_goals': None, 'away_goals': None, 'home_odds': 1.30, 'draw_odds': 5.09, 'away_odds': 8.13, 'status': 'scheduled'},
    # 第6轮
    {'round': 'H_6', 'match_date': '2026-05-28', 'match_time': '06:00', 'home_team': 'Independiente del Valle', 'away_team': 'Rosario Central', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
    {'round': 'H_6', 'match_date': '2026-05-28', 'match_time': '06:00', 'home_team': 'Libertad', 'away_team': 'Universidad Central', 'home_goals': None, 'away_goals': None, 'home_odds': None, 'draw_odds': None, 'away_odds': None, 'status': 'scheduled'},
]
matches.extend(h_group)

# 创建DataFrame
df = pd.DataFrame(matches)

# 添加固定字段
df['competition'] = 'libertadores'
df['season'] = '2026'
df['leg'] = ''
df['neutral'] = False

# 计算result
def calc_result(row):
    if pd.isna(row['home_goals']) or pd.isna(row['away_goals']):
        return ''
    if row['home_goals'] > row['away_goals']:
        return 'H'
    elif row['home_goals'] < row['away_goals']:
        return 'A'
    else:
        return 'D'

df['result'] = df.apply(calc_result, axis=1)

# 重排列
columns = ['competition', 'season', 'round', 'leg', 'match_date', 'match_time', 'neutral',
           'home_team', 'away_team', 'home_goals', 'away_goals', 'result',
           'home_goals_ht', 'away_goals_ht', 'result_ht',
           'home_goals_et', 'away_goals_et', 'home_penalties', 'away_penalties',
           'home_shots', 'away_shots', 'home_shots_target', 'away_shots_target',
           'home_corners', 'away_corners', 'home_fouls', 'away_fouls',
           'home_yellow', 'away_yellow', 'home_red', 'away_red',
           'referee', 'attendance', 'status', 'home_odds', 'draw_odds', 'away_odds']

# 添加缺失列
for col in columns:
    if col not in df.columns:
        df[col] = ''

df = df[columns]

# 保存
output_path = 'd:/football_tools/new_data/matches/clubs/cups/libertadores/libertadores_2026.csv'
df.to_csv(output_path, index=False)
print(f"Saved {len(df)} matches to {output_path}")
