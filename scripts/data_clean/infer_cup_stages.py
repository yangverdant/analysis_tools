"""
改进版：根据比赛日期和球队数量推断杯赛阶段
"""
import os
import csv
import pandas as pd
from datetime import datetime
from collections import defaultdict

# 杯赛阶段定义（按时间顺序）
CUP_STAGES = {
    'fa_cup': {
        'stages': [
            ('qualifying', 1),      # 预选赛 (8月)
            ('first_round', 2),     # 第一轮 (11月)
            ('second_round', 3),    # 第二轮 (12月)
            ('third_round', 4),     # 第三轮 (1月)
            ('fourth_round', 5),    # 第四轮 (1月底)
            ('fifth_round', 6),     # 第五轮 (2月)
            ('quarterfinal', 7),    # 八强 (3月)
            ('semifinal', 8),       # 半决赛 (4月)
            ('final', 9),           # 决赛 (5月)
        ],
        'teams_per_stage': {
            'qualifying': 80,       # 预选赛约80场
            'first_round': 40,      # 第一轮40场
            'second_round': 20,     # 第二轮20场
            'third_round': 32,      # 第三轮32场(英超球队加入)
            'fourth_round': 16,     # 第四轮16场
            'fifth_round': 8,       # 第五轮8场
            'quarterfinal': 4,      # 八强4场
            'semifinal': 2,         # 半决赛2场
            'final': 1,             # 决赛1场
        }
    },
    'england_league_cup': {
        'stages': [
            ('first_round', 1),     # 第一轮 (8月)
            ('second_round', 2),    # 第二轮 (9月)
            ('third_round', 3),     # 第三轮 (9月)
            ('fourth_round', 4),    # 第四轮 (10月)
            ('fifth_round', 5),     # 第五轮 (12月)
            ('quarterfinal', 6),    # 八强 (1月)
            ('semifinal', 7),       # 半决赛 (1月, 两回合)
            ('final', 8),           # 决赛 (2月)
        ]
    },
    'champions_league': {
        'stages': [
            ('qualifying', 1),      # 资格赛 (7-8月)
            ('playoff', 2),         # 附加赛 (8月)
            ('league_phase', 3),    # 联赛阶段 (9月-1月)
            ('playoff_round', 4),   # 附加赛轮 (2月)
            ('round_of_16', 5),     # 16强 (2-3月)
            ('quarterfinal', 6),    # 八强 (4月)
            ('semifinal', 7),       # 半决赛 (4-5月)
            ('final', 8),           # 决赛 (5-6月)
        ]
    },
    'europa_league': {
        'stages': [
            ('qualifying', 1),
            ('playoff', 2),
            ('league_phase', 3),
            ('playoff_round', 4),
            ('round_of_16', 5),
            ('quarterfinal', 6),
            ('semifinal', 7),
            ('final', 8),
        ]
    },
    'conference_league': {
        'stages': [
            ('qualifying', 1),
            ('playoff', 2),
            ('league_phase', 3),
            ('playoff_round', 4),
            ('round_of_16', 5),
            ('quarterfinal', 6),
            ('semifinal', 7),
            ('final', 8),
        ]
    },
    'dfb_pokal': {
        'stages': [
            ('first_round', 1),     # 第一轮 (8月)
            ('second_round', 2),    # 第二轮 (10-11月)
            ('round_of_16', 3),     # 16强 (12月-1月)
            ('quarterfinal', 4),    # 八强 (2月)
            ('semifinal', 5),       # 半决赛 (4月)
            ('final', 6),           # 决赛 (5月)
        ]
    },
    'copa_del_rey': {
        'stages': [
            ('first_round', 1),
            ('second_round', 2),
            ('third_round', 3),
            ('round_of_32', 4),
            ('round_of_16', 5),
            ('quarterfinal', 6),
            ('semifinal', 7),
            ('final', 8),
        ]
    },
    'italy_cup': {
        'stages': [
            ('first_round', 1),
            ('second_round', 2),
            ('third_round', 3),
            ('fourth_round', 4),
            ('round_of_16', 5),
            ('quarterfinal', 6),
            ('semifinal', 7),
            ('final', 8),
        ]
    },
    'coupe_de_france': {
        'stages': [
            ('regional', 1),
            ('round_of_64', 2),
            ('round_of_32', 3),
            ('round_of_16', 4),
            ('quarterfinal', 5),
            ('semifinal', 6),
            ('final', 7),
        ]
    },
    'austria_cup': {
        'stages': [
            ('first_round', 1),
            ('second_round', 2),
            ('round_of_16', 3),
            ('quarterfinal', 4),
            ('semifinal', 5),
            ('final', 6),
        ]
    }
}

def infer_stage_by_date_and_count(df, cup_name):
    """根据日期和比赛数量推断阶段"""
    if cup_name not in CUP_STAGES:
        return df

    stages_info = CUP_STAGES[cup_name]['stages']

    # 按日期分组
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df.sort_values('Date')

    # 按日期分组，每组算一个阶段
    date_groups = df.groupby(df['Date'].dt.date)

    # 根据每个日期的比赛数量推断阶段
    total_dates = len(date_groups)
    stage_idx = 0

    for date, group in date_groups:
        match_count = len(group)

        # 根据比赛数量匹配阶段
        if cup_name == 'fa_cup':
            if match_count >= 40:
                stage_name = 'qualifying'
            elif match_count >= 32:
                stage_name = 'third_round'
            elif match_count >= 16:
                stage_name = 'fourth_round'
            elif match_count >= 8:
                stage_name = 'fifth_round'
            elif match_count >= 4:
                stage_name = 'quarterfinal'
            elif match_count >= 2:
                stage_name = 'semifinal'
            elif match_count == 1:
                stage_name = 'final'
            else:
                stage_name = 'unknown'
        elif cup_name == 'champions_league':
            # 欧冠联赛阶段每天有多场比赛
            if match_count >= 8:
                stage_name = 'league_phase'
            elif match_count >= 4:
                stage_name = 'quarterfinal'
            elif match_count >= 2:
                stage_name = 'semifinal'
            elif match_count == 1:
                stage_name = 'final'
            else:
                stage_name = 'knockout'
        else:
            # 通用逻辑：按比赛数量递减推断阶段
            if stage_idx < len(stages_info):
                stage_name = stages_info[stage_idx][0]
            else:
                stage_name = 'unknown'

        # 更新Stage
        df.loc[group.index, 'Stage'] = stage_name

        # 查找阶段顺序
        for s_name, s_order in stages_info:
            if s_name == stage_name:
                df.loc[group.index, 'StageOrder'] = s_order
                break

        stage_idx += 1

    return df

def process_cup_with_stage_inference(input_path, output_path, cup_name):
    """处理单个杯赛文件，推断阶段"""
    try:
        df = pd.read_csv(input_path, encoding='utf-8')
    except:
        try:
            df = pd.read_csv(input_path, encoding='latin-1')
        except:
            return

    if df.empty:
        return

    # 推断阶段
    df = infer_stage_by_date_and_count(df, cup_name)

    # 保存
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"处理 {os.path.basename(input_path)}: {len(df)} 条记录")

def main():
    base_path = 'd:/football_tools/data/cups_standardized'

    cup_names = {
        'fa_cup': 'fa_cup',
        'england_league_cup': 'england_league_cup',
        'champions_league': 'champions_league',
        'europa_league': 'europa_league',
        'conference_league': 'conference_league',
        'dfb_pokal': 'dfb_pokal',
        'copa_del_rey': 'copa_del_rey',
        'italy_cup': 'italy_cup',
        'coupe_de_france': 'coupe_de_france',
        'austria_cup': 'austria_cup',
    }

    for dir_name, cup_name in cup_names.items():
        cup_dir = os.path.join(base_path, dir_name)
        if not os.path.exists(cup_dir):
            continue

        for filename in os.listdir(cup_dir):
            if filename.endswith('.csv'):
                input_path = os.path.join(cup_dir, filename)
                process_cup_with_stage_inference(input_path, input_path, cup_name)

    print("\n阶段推断完成!")

if __name__ == '__main__':
    main()
