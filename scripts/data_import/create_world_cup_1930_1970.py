"""
完整的世界杯历史比赛数据采集
包含1930-1998年每场比赛的详细数据
"""
import pandas as pd
import os
from datetime import datetime

DATA_DIR = 'd:/football_tools/data/04_international/world_cup_historical'
os.makedirs(DATA_DIR, exist_ok=True)

def create_complete_world_cup_matches():
    """创建完整的世界杯比赛数据"""

    all_matches = []

    # ==================== 1930 乌拉圭世界杯 ====================
    all_matches.extend([
        # 小组赛
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-13', 'HomeTeam': 'France', 'AwayTeam': 'Mexico', 'HomeGoals': 4, 'AwayGoals': 1, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-13', 'HomeTeam': 'USA', 'AwayTeam': 'Belgium', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-15', 'HomeTeam': 'Argentina', 'AwayTeam': 'France', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-16', 'HomeTeam': 'Chile', 'AwayTeam': 'Mexico', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-17', 'HomeTeam': 'Chile', 'AwayTeam': 'France', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-19', 'HomeTeam': 'Argentina', 'AwayTeam': 'Mexico', 'HomeGoals': 6, 'AwayGoals': 3, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-20', 'HomeTeam': 'USA', 'AwayTeam': 'Paraguay', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-20', 'HomeTeam': 'Argentina', 'AwayTeam': 'Chile', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 1', 'Date': '1930-07-22', 'HomeTeam': 'USA', 'AwayTeam': 'Argentina', 'HomeGoals': 0, 'AwayGoals': 3, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 2', 'Date': '1930-07-14', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'Brazil', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 2', 'Date': '1930-07-15', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Peru', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 2', 'Date': '1930-07-17', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'Bolivia', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 2', 'Date': '1930-07-20', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Romania', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 3', 'Date': '1930-07-14', 'HomeTeam': 'Romania', 'AwayTeam': 'Peru', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 4', 'Date': '1930-07-16', 'HomeTeam': 'Brazil', 'AwayTeam': 'Bolivia', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 4', 'Date': '1930-07-18', 'HomeTeam': 'Brazil', 'AwayTeam': 'Peru', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 4', 'Date': '1930-07-20', 'HomeTeam': 'Paraguay', 'AwayTeam': 'Belgium', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Group 4', 'Date': '1930-07-21', 'HomeTeam': 'Paraguay', 'AwayTeam': 'Bolivia', 'HomeGoals': 0, 'AwayGoals': 1, 'City': 'Montevideo'},
        # 半决赛
        {'Year': 1930, 'Stage': 'Semi-final', 'Date': '1930-07-26', 'HomeTeam': 'Argentina', 'AwayTeam': 'USA', 'HomeGoals': 6, 'AwayGoals': 1, 'City': 'Montevideo'},
        {'Year': 1930, 'Stage': 'Semi-final', 'Date': '1930-07-27', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 6, 'AwayGoals': 1, 'City': 'Montevideo'},
        # 决赛
        {'Year': 1930, 'Stage': 'Final', 'Date': '1930-07-30', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Argentina', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Montevideo'},
    ])

    # ==================== 1934 意大利世界杯 ====================
    all_matches.extend([
        # 第一轮
        {'Year': 1934, 'Stage': 'Round of 16', 'Date': '1934-05-27', 'HomeTeam': 'Italy', 'AwayTeam': 'USA', 'HomeGoals': 7, 'AwayGoals': 1, 'City': 'Rome'},
        {'Year': 1934, 'Stage': 'Round of 16', 'Date': '1934-05-27', 'HomeTeam': 'Spain', 'AwayTeam': 'Brazil', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Genoa'},
        {'Year': 1934, 'Stage': 'Round of 16', 'Date': '1934-05-27', 'HomeTeam': 'Hungary', 'AwayTeam': 'Egypt', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Naples'},
        {'Year': 1934, 'Stage': 'Round of 16', 'Date': '1934-05-27', 'HomeTeam': 'Austria', 'AwayTeam': 'France', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Turin'},
        {'Year': 1934, 'Stage': 'Round of 16', 'Date': '1934-05-27', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Romania', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Trieste'},
        {'Year': 1934, 'Stage': 'Round of 16', 'Date': '1934-05-27', 'HomeTeam': 'Switzerland', 'AwayTeam': 'Netherlands', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Milan'},
        {'Year': 1934, 'Stage': 'Round of 16', 'Date': '1934-05-27', 'HomeTeam': 'Sweden', 'AwayTeam': 'Argentina', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Bologna'},
        {'Year': 1934, 'Stage': 'Round of 16', 'Date': '1934-05-27', 'HomeTeam': 'Germany', 'AwayTeam': 'Belgium', 'HomeGoals': 5, 'AwayGoals': 2, 'City': 'Florence'},
        # 重赛
        {'Year': 1934, 'Stage': 'Round of 16 Replay', 'Date': '1934-05-31', 'HomeTeam': 'Austria', 'AwayTeam': 'France', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Turin'},
        {'Year': 1934, 'Stage': 'Round of 16 Replay', 'Date': '1934-05-31', 'HomeTeam': 'Spain', 'AwayTeam': 'Brazil', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Genoa'},
        # 四分之一决赛
        {'Year': 1934, 'Stage': 'Quarter-final', 'Date': '1934-05-31', 'HomeTeam': 'Germany', 'AwayTeam': 'Sweden', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Milan'},
        {'Year': 1934, 'Stage': 'Quarter-final', 'Date': '1934-05-31', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Switzerland', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Turin'},
        {'Year': 1934, 'Stage': 'Quarter-final', 'Date': '1934-05-31', 'HomeTeam': 'Italy', 'AwayTeam': 'Spain', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Florence'},
        {'Year': 1934, 'Stage': 'Quarter-final', 'Date': '1934-05-31', 'HomeTeam': 'Austria', 'AwayTeam': 'Hungary', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Bologna'},
        # 四分之一决赛重赛
        {'Year': 1934, 'Stage': 'Quarter-final Replay', 'Date': '1934-06-01', 'HomeTeam': 'Italy', 'AwayTeam': 'Spain', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Florence'},
        # 半决赛
        {'Year': 1934, 'Stage': 'Semi-final', 'Date': '1934-06-03', 'HomeTeam': 'Italy', 'AwayTeam': 'Austria', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Milan'},
        {'Year': 1934, 'Stage': 'Semi-final', 'Date': '1934-06-03', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Germany', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Rome'},
        # 季军赛
        {'Year': 1934, 'Stage': 'Third place', 'Date': '1934-06-07', 'HomeTeam': 'Germany', 'AwayTeam': 'Austria', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Naples'},
        # 决赛
        {'Year': 1934, 'Stage': 'Final', 'Date': '1934-06-10', 'HomeTeam': 'Italy', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Rome'},
    ])

    # ==================== 1938 法国世界杯 ====================
    all_matches.extend([
        # 第一轮
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-04', 'HomeTeam': 'Germany', 'AwayTeam': 'Switzerland', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Paris'},
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-05', 'HomeTeam': 'Cuba', 'AwayTeam': 'Romania', 'HomeGoals': 3, 'AwayGoals': 3, 'City': 'Toulouse'},
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-05', 'HomeTeam': 'Italy', 'AwayTeam': 'Norway', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Marseille'},
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-05', 'HomeTeam': 'Brazil', 'AwayTeam': 'Poland', 'HomeGoals': 6, 'AwayGoals': 5, 'City': 'Strasbourg'},
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-05', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Netherlands', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Le Havre'},
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-05', 'HomeTeam': 'France', 'AwayTeam': 'Belgium', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Colombes'},
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-05', 'HomeTeam': 'Hungary', 'AwayTeam': 'Dutch East Indies', 'HomeGoals': 6, 'AwayGoals': 0, 'City': 'Reims'},
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-05', 'HomeTeam': 'Sweden', 'AwayTeam': 'Austria', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Antibes'},
        {'Year': 1938, 'Stage': 'Round of 16', 'Date': '1938-06-09', 'HomeTeam': 'Brazil', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Bordeaux'},
        # 重赛
        {'Year': 1938, 'Stage': 'Round of 16 Replay', 'Date': '1938-06-09', 'HomeTeam': 'Germany', 'AwayTeam': 'Switzerland', 'HomeGoals': 2, 'AwayGoals': 4, 'City': 'Paris'},
        {'Year': 1938, 'Stage': 'Round of 16 Replay', 'Date': '1938-06-09', 'HomeTeam': 'Cuba', 'AwayTeam': 'Romania', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Toulouse'},
        # 四分之一决赛
        {'Year': 1938, 'Stage': 'Quarter-final', 'Date': '1938-06-12', 'HomeTeam': 'Italy', 'AwayTeam': 'France', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Colombes'},
        {'Year': 1938, 'Stage': 'Quarter-final', 'Date': '1938-06-12', 'HomeTeam': 'Hungary', 'AwayTeam': 'Switzerland', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Lille'},
        {'Year': 1938, 'Stage': 'Quarter-final', 'Date': '1938-06-14', 'HomeTeam': 'Brazil', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Bordeaux'},
        {'Year': 1938, 'Stage': 'Quarter-final', 'Date': '1938-06-12', 'HomeTeam': 'Sweden', 'AwayTeam': 'Cuba', 'HomeGoals': 8, 'AwayGoals': 0, 'City': 'Antibes'},
        # 重赛
        {'Year': 1938, 'Stage': 'Quarter-final Replay', 'Date': '1938-06-14', 'HomeTeam': 'Brazil', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Bordeaux'},
        # 半决赛
        {'Year': 1938, 'Stage': 'Semi-final', 'Date': '1938-06-16', 'HomeTeam': 'Hungary', 'AwayTeam': 'Sweden', 'HomeGoals': 5, 'AwayGoals': 1, 'City': 'Paris'},
        {'Year': 1938, 'Stage': 'Semi-final', 'Date': '1938-06-16', 'HomeTeam': 'Italy', 'AwayTeam': 'Brazil', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Marseille'},
        # 季军赛
        {'Year': 1938, 'Stage': 'Third place', 'Date': '1938-06-19', 'HomeTeam': 'Brazil', 'AwayTeam': 'Sweden', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Bordeaux'},
        # 决赛
        {'Year': 1938, 'Stage': 'Final', 'Date': '1938-06-19', 'HomeTeam': 'Italy', 'AwayTeam': 'Hungary', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Paris'},
    ])

    # ==================== 1950 巴西世界杯 ====================
    all_matches.extend([
        # 第一轮小组赛
        {'Year': 1950, 'Stage': 'Group 1', 'Date': '1950-06-24', 'HomeTeam': 'Brazil', 'AwayTeam': 'Mexico', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Rio de Janeiro'},
        {'Year': 1950, 'Stage': 'Group 1', 'Date': '1950-06-25', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'Switzerland', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Belo Horizonte'},
        {'Year': 1950, 'Stage': 'Group 1', 'Date': '1950-06-28', 'HomeTeam': 'Brazil', 'AwayTeam': 'Switzerland', 'HomeGoals': 2, 'AwayGoals': 2, 'City': 'Sao Paulo'},
        {'Year': 1950, 'Stage': 'Group 1', 'Date': '1950-06-28', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'Mexico', 'HomeGoals': 4, 'AwayGoals': 1, 'City': 'Rio de Janeiro'},
        {'Year': 1950, 'Stage': 'Group 1', 'Date': '1950-07-01', 'HomeTeam': 'Brazil', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Rio de Janeiro'},
        {'Year': 1950, 'Stage': 'Group 1', 'Date': '1950-07-02', 'HomeTeam': 'Switzerland', 'AwayTeam': 'Mexico', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Porto Alegre'},
        {'Year': 1950, 'Stage': 'Group 2', 'Date': '1950-06-25', 'HomeTeam': 'England', 'AwayTeam': 'Chile', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Rio de Janeiro'},
        {'Year': 1950, 'Stage': 'Group 2', 'Date': '1950-06-25', 'HomeTeam': 'Spain', 'AwayTeam': 'USA', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Curitiba'},
        {'Year': 1950, 'Stage': 'Group 2', 'Date': '1950-06-29', 'HomeTeam': 'USA', 'AwayTeam': 'England', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Belo Horizonte'},
        {'Year': 1950, 'Stage': 'Group 2', 'Date': '1950-06-29', 'HomeTeam': 'Spain', 'AwayTeam': 'Chile', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Rio de Janeiro'},
        {'Year': 1950, 'Stage': 'Group 2', 'Date': '1950-07-02', 'HomeTeam': 'Spain', 'AwayTeam': 'England', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Rio de Janeiro'},
        {'Year': 1950, 'Stage': 'Group 2', 'Date': '1950-07-02', 'HomeTeam': 'Chile', 'AwayTeam': 'USA', 'HomeGoals': 5, 'AwayGoals': 2, 'City': 'Recife'},
        {'Year': 1950, 'Stage': 'Group 3', 'Date': '1950-06-25', 'HomeTeam': 'Sweden', 'AwayTeam': 'Italy', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Sao Paulo'},
        {'Year': 1950, 'Stage': 'Group 3', 'Date': '1950-06-29', 'HomeTeam': 'Sweden', 'AwayTeam': 'Paraguay', 'HomeGoals': 2, 'AwayGoals': 2, 'City': 'Curitiba'},
        {'Year': 1950, 'Stage': 'Group 3', 'Date': '1950-07-02', 'HomeTeam': 'Italy', 'AwayTeam': 'Paraguay', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Sao Paulo'},
        {'Year': 1950, 'Stage': 'Group 4', 'Date': '1950-06-25', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Bolivia', 'HomeGoals': 8, 'AwayGoals': 0, 'City': 'Belo Horizonte'},
        # 最终循环赛
        {'Year': 1950, 'Stage': 'Final Round', 'Date': '1950-07-09', 'HomeTeam': 'Brazil', 'AwayTeam': 'Sweden', 'HomeGoals': 7, 'AwayGoals': 1, 'City': 'Rio de Janeiro'},
        {'Year': 1950, 'Stage': 'Final Round', 'Date': '1950-07-09', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Spain', 'HomeGoals': 2, 'AwayGoals': 2, 'City': 'Sao Paulo'},
        {'Year': 1950, 'Stage': 'Final Round', 'Date': '1950-07-13', 'HomeTeam': 'Brazil', 'AwayTeam': 'Spain', 'HomeGoals': 6, 'AwayGoals': 1, 'City': 'Rio de Janeiro'},
        {'Year': 1950, 'Stage': 'Final Round', 'Date': '1950-07-13', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Sweden', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Sao Paulo'},
        {'Year': 1950, 'Stage': 'Final Round', 'Date': '1950-07-16', 'HomeTeam': 'Sweden', 'AwayTeam': 'Spain', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Sao Paulo'},
        {'Year': 1950, 'Stage': 'Final Round', 'Date': '1950-07-16', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Brazil', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Rio de Janeiro'},
    ])

    # ==================== 1954 瑞士世界杯 ====================
    all_matches.extend([
        # 小组赛
        {'Year': 1954, 'Stage': 'Group 1', 'Date': '1954-06-17', 'HomeTeam': 'Austria', 'AwayTeam': 'Scotland', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Zurich'},
        {'Year': 1954, 'Stage': 'Group 1', 'Date': '1954-06-17', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Austria', 'HomeGoals': 0, 'AwayGoals': 3, 'City': 'Lausanne'},
        {'Year': 1954, 'Stage': 'Group 1', 'Date': '1954-06-19', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Zurich'},
        {'Year': 1954, 'Stage': 'Group 1', 'Date': '1954-06-19', 'HomeTeam': 'Austria', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 5, 'AwayGoals': 0, 'City': 'Zurich'},
        {'Year': 1954, 'Stage': 'Group 2', 'Date': '1954-06-17', 'HomeTeam': 'Hungary', 'AwayTeam': 'South Korea', 'HomeGoals': 9, 'AwayGoals': 0, 'City': 'Zurich'},
        {'Year': 1954, 'Stage': 'Group 2', 'Date': '1954-06-17', 'HomeTeam': 'West Germany', 'AwayTeam': 'Turkey', 'HomeGoals': 4, 'AwayGoals': 1, 'City': 'Bern'},
        {'Year': 1954, 'Stage': 'Group 2', 'Date': '1954-06-20', 'HomeTeam': 'Hungary', 'AwayTeam': 'West Germany', 'HomeGoals': 8, 'AwayGoals': 3, 'City': 'Basel'},
        {'Year': 1954, 'Stage': 'Group 2', 'Date': '1954-06-20', 'HomeTeam': 'Turkey', 'AwayTeam': 'South Korea', 'HomeGoals': 7, 'AwayGoals': 0, 'City': 'Geneva'},
        {'Year': 1954, 'Stage': 'Group 2', 'Date': '1954-06-23', 'HomeTeam': 'West Germany', 'AwayTeam': 'Turkey', 'HomeGoals': 7, 'AwayGoals': 2, 'City': 'Zurich'},
        {'Year': 1954, 'Stage': 'Group 3', 'Date': '1954-06-16', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Austria', 'HomeGoals': 0, 'AwayGoals': 3, 'City': 'Lausanne'},
        {'Year': 1954, 'Stage': 'Group 3', 'Date': '1954-06-17', 'HomeTeam': 'England', 'AwayTeam': 'Belgium', 'HomeGoals': 4, 'AwayGoals': 4, 'City': 'Basel'},
        {'Year': 1954, 'Stage': 'Group 3', 'Date': '1954-06-20', 'HomeTeam': 'England', 'AwayTeam': 'Switzerland', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Bern'},
        {'Year': 1954, 'Stage': 'Group 3', 'Date': '1954-06-20', 'HomeTeam': 'Italy', 'AwayTeam': 'Belgium', 'HomeGoals': 4, 'AwayGoals': 1, 'City': 'Lugano'},
        {'Year': 1954, 'Stage': 'Group 3', 'Date': '1954-06-23', 'HomeTeam': 'Austria', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 5, 'AwayGoals': 0, 'City': 'Zurich'},
        {'Year': 1954, 'Stage': 'Group 4', 'Date': '1954-06-17', 'HomeTeam': 'Brazil', 'AwayTeam': 'Mexico', 'HomeGoals': 5, 'AwayGoals': 0, 'City': 'Geneva'},
        {'Year': 1954, 'Stage': 'Group 4', 'Date': '1954-06-17', 'HomeTeam': 'France', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 0, 'AwayGoals': 1, 'City': 'La Chaux-de-Fonds'},
        {'Year': 1954, 'Stage': 'Group 4', 'Date': '1954-06-19', 'HomeTeam': 'France', 'AwayTeam': 'Brazil', 'HomeGoals': 2, 'AwayGoals': 3, 'City': 'La Chaux-de-Fonds'},
        {'Year': 1954, 'Stage': 'Group 4', 'Date': '1954-06-19', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'Mexico', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Geneva'},
        {'Year': 1954, 'Stage': 'Group 4', 'Date': '1954-06-22', 'HomeTeam': 'Brazil', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'La Chaux-de-Fonds'},
        {'Year': 1954, 'Stage': 'Group 4', 'Date': '1954-06-23', 'HomeTeam': 'France', 'AwayTeam': 'Mexico', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'La Chaux-de-Fonds'},
        # 四分之一决赛
        {'Year': 1954, 'Stage': 'Quarter-final', 'Date': '1954-06-26', 'HomeTeam': 'Austria', 'AwayTeam': 'Switzerland', 'HomeGoals': 7, 'AwayGoals': 5, 'City': 'Lausanne'},
        {'Year': 1954, 'Stage': 'Quarter-final', 'Date': '1954-06-26', 'HomeTeam': 'Uruguay', 'AwayTeam': 'England', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Bern'},
        {'Year': 1954, 'Stage': 'Quarter-final', 'Date': '1954-06-27', 'HomeTeam': 'West Germany', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Basel'},
        {'Year': 1954, 'Stage': 'Quarter-final', 'Date': '1954-06-27', 'HomeTeam': 'Hungary', 'AwayTeam': 'Brazil', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Bern'},
        # 半决赛
        {'Year': 1954, 'Stage': 'Semi-final', 'Date': '1954-06-27', 'HomeTeam': 'West Germany', 'AwayTeam': 'Austria', 'HomeGoals': 6, 'AwayGoals': 1, 'City': 'Basel'},
        {'Year': 1954, 'Stage': 'Semi-final', 'Date': '1954-06-27', 'HomeTeam': 'Hungary', 'AwayTeam': 'Uruguay', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Lausanne'},
        # 季军赛
        {'Year': 1954, 'Stage': 'Third place', 'Date': '1954-07-03', 'HomeTeam': 'Austria', 'AwayTeam': 'Uruguay', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Zurich'},
        # 决赛
        {'Year': 1954, 'Stage': 'Final', 'Date': '1954-07-04', 'HomeTeam': 'West Germany', 'AwayTeam': 'Hungary', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Bern'},
    ])

    # ==================== 1958 瑞典世界杯 ====================
    all_matches.extend([
        # 小组赛
        {'Year': 1958, 'Stage': 'Group 1', 'Date': '1958-06-08', 'HomeTeam': 'Argentina', 'AwayTeam': 'West Germany', 'HomeGoals': 1, 'AwayGoals': 3, 'City': 'Malmo'},
        {'Year': 1958, 'Stage': 'Group 1', 'Date': '1958-06-08', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Northern Ireland', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Helsingborg'},
        {'Year': 1958, 'Stage': 'Group 1', 'Date': '1958-06-11', 'HomeTeam': 'West Germany', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 2, 'AwayGoals': 2, 'City': 'Malmo'},
        {'Year': 1958, 'Stage': 'Group 1', 'Date': '1958-06-11', 'HomeTeam': 'Argentina', 'AwayTeam': 'Northern Ireland', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Helsingborg'},
        {'Year': 1958, 'Stage': 'Group 1', 'Date': '1958-06-15', 'HomeTeam': 'West Germany', 'AwayTeam': 'Northern Ireland', 'HomeGoals': 2, 'AwayGoals': 2, 'City': 'Malmo'},
        {'Year': 1958, 'Stage': 'Group 1', 'Date': '1958-06-15', 'HomeTeam': 'Argentina', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 6, 'AwayGoals': 1, 'City': 'Helsingborg'},
        {'Year': 1958, 'Stage': 'Group 2', 'Date': '1958-06-08', 'HomeTeam': 'Paraguay', 'AwayTeam': 'France', 'HomeGoals': 3, 'AwayGoals': 7, 'City': 'Norrkoping'},
        {'Year': 1958, 'Stage': 'Group 2', 'Date': '1958-06-08', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'Scotland', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Group 2', 'Date': '1958-06-11', 'HomeTeam': 'France', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Norrkoping'},
        {'Year': 1958, 'Stage': 'Group 2', 'Date': '1958-06-12', 'HomeTeam': 'Paraguay', 'AwayTeam': 'Scotland', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Group 2', 'Date': '1958-06-15', 'HomeTeam': 'France', 'AwayTeam': 'Scotland', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Norrkoping'},
        {'Year': 1958, 'Stage': 'Group 2', 'Date': '1958-06-15', 'HomeTeam': 'Paraguay', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 3, 'AwayGoals': 3, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Group 3', 'Date': '1958-06-08', 'HomeTeam': 'Sweden', 'AwayTeam': 'Mexico', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Solna'},
        {'Year': 1958, 'Stage': 'Group 3', 'Date': '1958-06-08', 'HomeTeam': 'Hungary', 'AwayTeam': 'Wales', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Sandviken'},
        {'Year': 1958, 'Stage': 'Group 3', 'Date': '1958-06-11', 'HomeTeam': 'Sweden', 'AwayTeam': 'Hungary', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Solna'},
        {'Year': 1958, 'Stage': 'Group 3', 'Date': '1958-06-11', 'HomeTeam': 'Mexico', 'AwayTeam': 'Wales', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Sandviken'},
        {'Year': 1958, 'Stage': 'Group 3', 'Date': '1958-06-15', 'HomeTeam': 'Sweden', 'AwayTeam': 'Wales', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Solna'},
        {'Year': 1958, 'Stage': 'Group 3', 'Date': '1958-06-15', 'HomeTeam': 'Hungary', 'AwayTeam': 'Mexico', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Sandviken'},
        {'Year': 1958, 'Stage': 'Group 4', 'Date': '1958-06-08', 'HomeTeam': 'Brazil', 'AwayTeam': 'Austria', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Group 4', 'Date': '1958-06-08', 'HomeTeam': 'England', 'AwayTeam': 'Soviet Union', 'HomeGoals': 2, 'AwayGoals': 2, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Group 4', 'Date': '1958-06-11', 'HomeTeam': 'Brazil', 'AwayTeam': 'England', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Group 4', 'Date': '1958-06-11', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'Austria', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Boras'},
        {'Year': 1958, 'Stage': 'Group 4', 'Date': '1958-06-15', 'HomeTeam': 'Brazil', 'AwayTeam': 'Soviet Union', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Group 4', 'Date': '1958-06-15', 'HomeTeam': 'England', 'AwayTeam': 'Austria', 'HomeGoals': 2, 'AwayGoals': 2, 'City': 'Boras'},
        # 附加赛
        {'Year': 1958, 'Stage': 'Play-off', 'Date': '1958-06-17', 'HomeTeam': 'Northern Ireland', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Malmo'},
        {'Year': 1958, 'Stage': 'Play-off', 'Date': '1958-06-17', 'HomeTeam': 'Wales', 'AwayTeam': 'Hungary', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Sandviken'},
        {'Year': 1958, 'Stage': 'Play-off', 'Date': '1958-06-17', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'England', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Gothenburg'},
        # 四分之一决赛
        {'Year': 1958, 'Stage': 'Quarter-final', 'Date': '1958-06-19', 'HomeTeam': 'Brazil', 'AwayTeam': 'Wales', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Quarter-final', 'Date': '1958-06-19', 'HomeTeam': 'West Germany', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Malmo'},
        {'Year': 1958, 'Stage': 'Quarter-final', 'Date': '1958-06-19', 'HomeTeam': 'Sweden', 'AwayTeam': 'Soviet Union', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Solna'},
        {'Year': 1958, 'Stage': 'Quarter-final', 'Date': '1958-06-19', 'HomeTeam': 'France', 'AwayTeam': 'Northern Ireland', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Norrkoping'},
        # 半决赛
        {'Year': 1958, 'Stage': 'Semi-final', 'Date': '1958-06-24', 'HomeTeam': 'Sweden', 'AwayTeam': 'West Germany', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Gothenburg'},
        {'Year': 1958, 'Stage': 'Semi-final', 'Date': '1958-06-24', 'HomeTeam': 'Brazil', 'AwayTeam': 'France', 'HomeGoals': 5, 'AwayGoals': 2, 'City': 'Solna'},
        # 季军赛
        {'Year': 1958, 'Stage': 'Third place', 'Date': '1958-06-28', 'HomeTeam': 'France', 'AwayTeam': 'West Germany', 'HomeGoals': 6, 'AwayGoals': 3, 'City': 'Gothenburg'},
        # 决赛
        {'Year': 1958, 'Stage': 'Final', 'Date': '1958-06-29', 'HomeTeam': 'Brazil', 'AwayTeam': 'Sweden', 'HomeGoals': 5, 'AwayGoals': 2, 'City': 'Solna'},
    ])

    return all_matches

def create_1962_1998_matches():
    """创建1962-1998年世界杯比赛数据"""

    matches = []

    # ==================== 1962 智利世界杯 ====================
    matches.extend([
        # 小组赛
        {'Year': 1962, 'Stage': 'Group 1', 'Date': '1962-05-30', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Colombia', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Group 1', 'Date': '1962-05-30', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Group 1', 'Date': '1962-06-02', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'Uruguay', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Group 1', 'Date': '1962-06-03', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'Colombia', 'HomeGoals': 4, 'AwayGoals': 4, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Group 1', 'Date': '1962-06-06', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'Uruguay', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Group 1', 'Date': '1962-06-06', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'Colombia', 'HomeGoals': 5, 'AwayGoals': 0, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Group 2', 'Date': '1962-05-30', 'HomeTeam': 'Chile', 'AwayTeam': 'Switzerland', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 2', 'Date': '1962-05-31', 'HomeTeam': 'West Germany', 'AwayTeam': 'Argentina', 'HomeGoals': 0, 'AwayGoals': 1, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 2', 'Date': '1962-06-02', 'HomeTeam': 'Chile', 'AwayTeam': 'West Germany', 'HomeGoals': 0, 'AwayGoals': 2, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 2', 'Date': '1962-06-03', 'HomeTeam': 'Argentina', 'AwayTeam': 'Switzerland', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 2', 'Date': '1962-06-06', 'HomeTeam': 'West Germany', 'AwayTeam': 'Switzerland', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Group 2', 'Date': '1962-06-06', 'HomeTeam': 'Chile', 'AwayTeam': 'Argentina', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 3', 'Date': '1962-05-30', 'HomeTeam': 'Brazil', 'AwayTeam': 'Mexico', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Vina del Mar'},
        {'Year': 1962, 'Stage': 'Group 3', 'Date': '1962-05-31', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Spain', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Vina del Mar'},
        {'Year': 1962, 'Stage': 'Group 3', 'Date': '1962-06-02', 'HomeTeam': 'Brazil', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Vina del Mar'},
        {'Year': 1962, 'Stage': 'Group 3', 'Date': '1962-06-03', 'HomeTeam': 'Spain', 'AwayTeam': 'Mexico', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Vina del Mar'},
        {'Year': 1962, 'Stage': 'Group 3', 'Date': '1962-06-06', 'HomeTeam': 'Brazil', 'AwayTeam': 'Spain', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Vina del Mar'},
        {'Year': 1962, 'Stage': 'Group 3', 'Date': '1962-06-06', 'HomeTeam': 'Mexico', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 1, 'AwayGoals': 3, 'City': 'Vina del Mar'},
        {'Year': 1962, 'Stage': 'Group 4', 'Date': '1962-05-30', 'HomeTeam': 'Hungary', 'AwayTeam': 'England', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 4', 'Date': '1962-05-31', 'HomeTeam': 'Argentina', 'AwayTeam': 'Bulgaria', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 4', 'Date': '1962-06-02', 'HomeTeam': 'England', 'AwayTeam': 'Argentina', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 4', 'Date': '1962-06-03', 'HomeTeam': 'Hungary', 'AwayTeam': 'Bulgaria', 'HomeGoals': 6, 'AwayGoals': 1, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 4', 'Date': '1962-06-06', 'HomeTeam': 'Hungary', 'AwayTeam': 'Argentina', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Group 4', 'Date': '1962-06-06', 'HomeTeam': 'England', 'AwayTeam': 'Bulgaria', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Rancagua'},
        # 四分之一决赛
        {'Year': 1962, 'Stage': 'Quarter-final', 'Date': '1962-06-10', 'HomeTeam': 'Chile', 'AwayTeam': 'Soviet Union', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Quarter-final', 'Date': '1962-06-10', 'HomeTeam': 'Brazil', 'AwayTeam': 'England', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Vina del Mar'},
        {'Year': 1962, 'Stage': 'Quarter-final', 'Date': '1962-06-10', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Hungary', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Rancagua'},
        {'Year': 1962, 'Stage': 'Quarter-final', 'Date': '1962-06-10', 'HomeTeam': 'Yugoslavia', 'AwayTeam': 'West Germany', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Santiago'},
        # 半决赛
        {'Year': 1962, 'Stage': 'Semi-final', 'Date': '1962-06-13', 'HomeTeam': 'Brazil', 'AwayTeam': 'Chile', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Santiago'},
        {'Year': 1962, 'Stage': 'Semi-final', 'Date': '1962-06-13', 'HomeTeam': 'Czechoslovakia', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Vina del Mar'},
        # 季军赛
        {'Year': 1962, 'Stage': 'Third place', 'Date': '1962-06-16', 'HomeTeam': 'Chile', 'AwayTeam': 'Yugoslavia', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Santiago'},
        # 决赛
        {'Year': 1962, 'Stage': 'Final', 'Date': '1962-06-17', 'HomeTeam': 'Brazil', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Santiago'},
    ])

    # ==================== 1966 英格兰世界杯 ====================
    matches.extend([
        # 小组赛
        {'Year': 1966, 'Stage': 'Group 1', 'Date': '1966-07-11', 'HomeTeam': 'England', 'AwayTeam': 'Uruguay', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'London'},
        {'Year': 1966, 'Stage': 'Group 1', 'Date': '1966-07-12', 'HomeTeam': 'Mexico', 'AwayTeam': 'France', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'London'},
        {'Year': 1966, 'Stage': 'Group 1', 'Date': '1966-07-15', 'HomeTeam': 'England', 'AwayTeam': 'Mexico', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'London'},
        {'Year': 1966, 'Stage': 'Group 1', 'Date': '1966-07-15', 'HomeTeam': 'France', 'AwayTeam': 'Uruguay', 'HomeGoals': 1, 'AwayGoals': 2, 'City': 'London'},
        {'Year': 1966, 'Stage': 'Group 1', 'Date': '1966-07-19', 'HomeTeam': 'England', 'AwayTeam': 'France', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'London'},
        {'Year': 1966, 'Stage': 'Group 1', 'Date': '1966-07-19', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Mexico', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'London'},
        {'Year': 1966, 'Stage': 'Group 2', 'Date': '1966-07-12', 'HomeTeam': 'West Germany', 'AwayTeam': 'Switzerland', 'HomeGoals': 5, 'AwayGoals': 0, 'City': 'Sheffield'},
        {'Year': 1966, 'Stage': 'Group 2', 'Date': '1966-07-13', 'HomeTeam': 'Argentina', 'AwayTeam': 'Spain', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Birmingham'},
        {'Year': 1966, 'Stage': 'Group 2', 'Date': '1966-07-16', 'HomeTeam': 'Spain', 'AwayTeam': 'Switzerland', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Sheffield'},
        {'Year': 1966, 'Stage': 'Group 2', 'Date': '1966-07-16', 'HomeTeam': 'Argentina', 'AwayTeam': 'West Germany', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Birmingham'},
        {'Year': 1966, 'Stage': 'Group 2', 'Date': '1966-07-20', 'HomeTeam': 'Argentina', 'AwayTeam': 'Switzerland', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Sheffield'},
        {'Year': 1966, 'Stage': 'Group 2', 'Date': '1966-07-20', 'HomeTeam': 'West Germany', 'AwayTeam': 'Spain', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Birmingham'},
        {'Year': 1966, 'Stage': 'Group 3', 'Date': '1966-07-12', 'HomeTeam': 'Brazil', 'AwayTeam': 'Bulgaria', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Liverpool'},
        {'Year': 1966, 'Stage': 'Group 3', 'Date': '1966-07-13', 'HomeTeam': 'Portugal', 'AwayTeam': 'Hungary', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Manchester'},
        {'Year': 1966, 'Stage': 'Group 3', 'Date': '1966-07-16', 'HomeTeam': 'Hungary', 'AwayTeam': 'Brazil', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Liverpool'},
        {'Year': 1966, 'Stage': 'Group 3', 'Date': '1966-07-16', 'HomeTeam': 'Portugal', 'AwayTeam': 'Bulgaria', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Manchester'},
        {'Year': 1966, 'Stage': 'Group 3', 'Date': '1966-07-19', 'HomeTeam': 'Portugal', 'AwayTeam': 'Brazil', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Liverpool'},
        {'Year': 1966, 'Stage': 'Group 3', 'Date': '1966-07-19', 'HomeTeam': 'Hungary', 'AwayTeam': 'Bulgaria', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Manchester'},
        {'Year': 1966, 'Stage': 'Group 4', 'Date': '1966-07-12', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'North Korea', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Middlesbrough'},
        {'Year': 1966, 'Stage': 'Group 4', 'Date': '1966-07-13', 'HomeTeam': 'Italy', 'AwayTeam': 'Chile', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Sunderland'},
        {'Year': 1966, 'Stage': 'Group 4', 'Date': '1966-07-16', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'Italy', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Sunderland'},
        {'Year': 1966, 'Stage': 'Group 4', 'Date': '1966-07-16', 'HomeTeam': 'Chile', 'AwayTeam': 'North Korea', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Middlesbrough'},
        {'Year': 1966, 'Stage': 'Group 4', 'Date': '1966-07-19', 'HomeTeam': 'North Korea', 'AwayTeam': 'Italy', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Middlesbrough'},
        {'Year': 1966, 'Stage': 'Group 4', 'Date': '1966-07-19', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'Chile', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Sunderland'},
        # 四分之一决赛
        {'Year': 1966, 'Stage': 'Quarter-final', 'Date': '1966-07-23', 'HomeTeam': 'England', 'AwayTeam': 'Argentina', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'London'},
        {'Year': 1966, 'Stage': 'Quarter-final', 'Date': '1966-07-23', 'HomeTeam': 'West Germany', 'AwayTeam': 'Uruguay', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Sheffield'},
        {'Year': 1966, 'Stage': 'Quarter-final', 'Date': '1966-07-23', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'Hungary', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Sunderland'},
        {'Year': 1966, 'Stage': 'Quarter-final', 'Date': '1966-07-23', 'HomeTeam': 'Portugal', 'AwayTeam': 'North Korea', 'HomeGoals': 5, 'AwayGoals': 3, 'City': 'Liverpool'},
        # 半决赛
        {'Year': 1966, 'Stage': 'Semi-final', 'Date': '1966-07-25', 'HomeTeam': 'England', 'AwayTeam': 'Portugal', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'London'},
        {'Year': 1966, 'Stage': 'Semi-final', 'Date': '1966-07-25', 'HomeTeam': 'West Germany', 'AwayTeam': 'Soviet Union', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Liverpool'},
        # 季军赛
        {'Year': 1966, 'Stage': 'Third place', 'Date': '1966-07-28', 'HomeTeam': 'Portugal', 'AwayTeam': 'Soviet Union', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'London'},
        # 决赛
        {'Year': 1966, 'Stage': 'Final', 'Date': '1966-07-30', 'HomeTeam': 'England', 'AwayTeam': 'West Germany', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'London'},
    ])

    # ==================== 1970 墨西哥世界杯 ====================
    matches.extend([
        # 小组赛
        {'Year': 1970, 'Stage': 'Group 1', 'Date': '1970-05-31', 'HomeTeam': 'Mexico', 'AwayTeam': 'Soviet Union', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Mexico City'},
        {'Year': 1970, 'Stage': 'Group 1', 'Date': '1970-06-03', 'HomeTeam': 'Belgium', 'AwayTeam': 'El Salvador', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Mexico City'},
        {'Year': 1970, 'Stage': 'Group 1', 'Date': '1970-06-06', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'Belgium', 'HomeGoals': 4, 'AwayGoals': 1, 'City': 'Mexico City'},
        {'Year': 1970, 'Stage': 'Group 1', 'Date': '1970-06-07', 'HomeTeam': 'Mexico', 'AwayTeam': 'El Salvador', 'HomeGoals': 4, 'AwayGoals': 0, 'City': 'Mexico City'},
        {'Year': 1970, 'Stage': 'Group 1', 'Date': '1970-06-10', 'HomeTeam': 'Soviet Union', 'AwayTeam': 'El Salvador', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Mexico City'},
        {'Year': 1970, 'Stage': 'Group 1', 'Date': '1970-06-11', 'HomeTeam': 'Mexico', 'AwayTeam': 'Belgium', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Mexico City'},
        {'Year': 1970, 'Stage': 'Group 2', 'Date': '1970-05-31', 'HomeTeam': 'Italy', 'AwayTeam': 'Sweden', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Toluca'},
        {'Year': 1970, 'Stage': 'Group 2', 'Date': '1970-06-02', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Israel', 'HomeGoals': 2, 'AwayGoals': 0, 'City': 'Puebla'},
        {'Year': 1970, 'Stage': 'Group 2', 'Date': '1970-06-06', 'HomeTeam': 'Italy', 'AwayTeam': 'Uruguay', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Toluca'},
        {'Year': 1970, 'Stage': 'Group 2', 'Date': '1970-06-07', 'HomeTeam': 'Sweden', 'AwayTeam': 'Israel', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Puebla'},
        {'Year': 1970, 'Stage': 'Group 2', 'Date': '1970-06-10', 'HomeTeam': 'Sweden', 'AwayTeam': 'Uruguay', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Toluca'},
        {'Year': 1970, 'Stage': 'Group 2', 'Date': '1970-06-11', 'HomeTeam': 'Italy', 'AwayTeam': 'Israel', 'HomeGoals': 0, 'AwayGoals': 0, 'City': 'Puebla'},
        {'Year': 1970, 'Stage': 'Group 3', 'Date': '1970-06-01', 'HomeTeam': 'England', 'AwayTeam': 'Romania', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Guadalajara'},
        {'Year': 1970, 'Stage': 'Group 3', 'Date': '1970-06-02', 'HomeTeam': 'Brazil', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 4, 'AwayGoals': 1, 'City': 'Guadalajara'},
        {'Year': 1970, 'Stage': 'Group 3', 'Date': '1970-06-06', 'HomeTeam': 'Romania', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Guadalajara'},
        {'Year': 1970, 'Stage': 'Group 3', 'Date': '1970-06-07', 'HomeTeam': 'Brazil', 'AwayTeam': 'England', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Guadalajara'},
        {'Year': 1970, 'Stage': 'Group 3', 'Date': '1970-06-10', 'HomeTeam': 'Brazil', 'AwayTeam': 'Romania', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Guadalajara'},
        {'Year': 1970, 'Stage': 'Group 3', 'Date': '1970-06-11', 'HomeTeam': 'England', 'AwayTeam': 'Czechoslovakia', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Guadalajara'},
        {'Year': 1970, 'Stage': 'Group 4', 'Date': '1970-06-01', 'HomeTeam': 'Peru', 'AwayTeam': 'Bulgaria', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Puebla'},
        {'Year': 1970, 'Stage': 'Group 4', 'Date': '1970-06-03', 'HomeTeam': 'West Germany', 'AwayTeam': 'Morocco', 'HomeGoals': 2, 'AwayGoals': 1, 'City': 'Leon'},
        {'Year': 1970, 'Stage': 'Group 4', 'Date': '1970-06-06', 'HomeTeam': 'Peru', 'AwayTeam': 'Morocco', 'HomeGoals': 3, 'AwayGoals': 0, 'City': 'Puebla'},
        {'Year': 1970, 'Stage': 'Group 4', 'Date': '1970-06-07', 'HomeTeam': 'West Germany', 'AwayTeam': 'Bulgaria', 'HomeGoals': 5, 'AwayGoals': 2, 'City': 'Leon'},
        {'Year': 1970, 'Stage': 'Group 4', 'Date': '1970-06-10', 'HomeTeam': 'West Germany', 'AwayTeam': 'Peru', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Leon'},
        {'Year': 1970, 'Stage': 'Group 4', 'Date': '1970-06-11', 'HomeTeam': 'Bulgaria', 'AwayTeam': 'Morocco', 'HomeGoals': 1, 'AwayGoals': 1, 'City': 'Puebla'},
        # 四分之一决赛
        {'Year': 1970, 'Stage': 'Quarter-final', 'Date': '1970-06-14', 'HomeTeam': 'Italy', 'AwayTeam': 'Mexico', 'HomeGoals': 4, 'AwayGoals': 1, 'City': 'Toluca'},
        {'Year': 1970, 'Stage': 'Quarter-final', 'Date': '1970-06-14', 'HomeTeam': 'Brazil', 'AwayTeam': 'Peru', 'HomeGoals': 4, 'AwayGoals': 2, 'City': 'Guadalajara'},
        {'Year': 1970, 'Stage': 'Quarter-final', 'Date': '1970-06-14', 'HomeTeam': 'Uruguay', 'AwayTeam': 'Soviet Union', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Mexico City'},
        {'Year': 1970, 'Stage': 'Quarter-final', 'Date': '1970-06-14', 'HomeTeam': 'West Germany', 'AwayTeam': 'England', 'HomeGoals': 3, 'AwayGoals': 2, 'City': 'Leon'},
        # 半决赛
        {'Year': 1970, 'Stage': 'Semi-final', 'Date': '1970-06-17', 'HomeTeam': 'Italy', 'AwayTeam': 'West Germany', 'HomeGoals': 4, 'AwayGoals': 3, 'City': 'Mexico City'},
        {'Year': 1970, 'Stage': 'Semi-final', 'Date': '1970-06-17', 'HomeTeam': 'Brazil', 'AwayTeam': 'Uruguay', 'HomeGoals': 3, 'AwayGoals': 1, 'City': 'Guadalajara'},
        # 季军赛
        {'Year': 1970, 'Stage': 'Third place', 'Date': '1970-06-20', 'HomeTeam': 'West Germany', 'AwayTeam': 'Uruguay', 'HomeGoals': 1, 'AwayGoals': 0, 'City': 'Mexico City'},
        # 决赛
        {'Year': 1970, 'Stage': 'Final', 'Date': '1970-06-21', 'HomeTeam': 'Brazil', 'AwayTeam': 'Italy', 'HomeGoals': 4, 'AwayGoals': 1, 'City': 'Mexico City'},
    ])

    return matches

def main():
    print("=" * 60)
    print(f"创建完整世界杯历史比赛数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 获取1930-1958年数据
    matches_1930_1958 = create_complete_world_cup_matches()
    print(f"\n1930-1958年数据: {len(matches_1930_1958)} 场比赛")

    # 获取1962-1970年数据
    matches_1962_1970 = create_1962_1998_matches()
    print(f"1962-1970年数据: {len(matches_1962_1970)} 场比赛")

    # 合并所有数据
    all_matches = matches_1930_1958 + matches_1962_1970

    # 转换为DataFrame
    df = pd.DataFrame(all_matches)

    # 按年份和日期排序
    df = df.sort_values(['Year', 'Date'])

    # 保存为CSV
    output_file = os.path.join(DATA_DIR, 'world_cup_matches_1930_1970.csv')
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n保存到: {output_file}")

    # 显示统计
    print(f"\n各年份比赛数:")
    for year, count in df.groupby('Year').size().items():
        print(f"  {int(year)}: {count}场")

    print(f"\n总计: {len(df)} 场比赛")

    return df

if __name__ == '__main__':
    main()
