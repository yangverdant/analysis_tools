import pandas as pd
import os

# 欧洲杯配置（简化版，按日期范围判断阶段）
euro_configs = {
    2000: {
        'teams': 16,
        'group_dates': ('2000-06-10', '2000-06-21'),
        'ko_dates': {
            'QF': ('2000-06-24', '2000-06-25'),
            'SF': ('2000-06-28', '2000-06-29'),
            'F': ('2000-07-02', '2000-07-02')
        }
    },
    2004: {
        'teams': 16,
        'group_dates': ('2004-06-12', '2004-06-23'),
        'ko_dates': {
            'QF': ('2004-06-24', '2004-06-27'),
            'SF': ('2004-06-30', '2004-07-01'),
            'F': ('2004-07-04', '2004-07-04')
        }
    },
    2008: {
        'teams': 16,
        'group_dates': ('2008-06-07', '2008-06-18'),
        'ko_dates': {
            'QF': ('2008-06-19', '2008-06-22'),
            'SF': ('2008-06-25', '2008-06-26'),
            'F': ('2008-06-29', '2008-06-29')
        }
    },
    2012: {
        'teams': 16,
        'group_dates': ('2012-06-08', '2012-06-19'),
        'ko_dates': {
            'QF': ('2012-06-21', '2012-06-24'),
            'SF': ('2012-06-27', '2012-06-28'),
            'F': ('2012-07-01', '2012-07-01')
        }
    },
    2016: {
        'teams': 24,
        'group_dates': ('2016-06-10', '2016-06-22'),
        'ko_dates': {
            'R16': ('2016-06-25', '2016-06-27'),
            'QF': ('2016-06-30', '2016-07-03'),
            'SF': ('2016-07-06', '2016-07-07'),
            'F': ('2016-07-10', '2016-07-10')
        }
    },
    2020: {
        'teams': 24,
        'group_dates': ('2021-06-11', '2021-06-23'),
        'ko_dates': {
            'R16': ('2021-06-26', '2021-06-29'),
            'QF': ('2021-07-02', '2021-07-03'),
            'SF': ('2021-07-06', '2021-07-07'),
            'F': ('2021-07-11', '2021-07-11')
        }
    },
    2024: {
        'teams': 24,
        'group_dates': ('2024-06-14', '2024-06-26'),
        'ko_dates': {
            'R16': ('2024-06-29', '2024-07-02'),
            'QF': ('2024-07-05', '2024-07-06'),
            'SF': ('2024-07-09', '2024-07-10'),
            'F': ('2024-07-14', '2024-07-14')
        }
    }
}

def get_round_value(row, config):
    date = row['match_date']

    # 检查淘汰赛
    for ko_round, (start, end) in config['ko_dates'].items():
        if start <= date <= end:
            return ko_round

    # 小组赛暂时返回空，需要更详细的分组数据
    group_start, group_end = config['group_dates']
    if group_start <= date <= group_end:
        return 'group'

    return ''

# 处理各届欧洲杯
euro_dir = 'd:/football_tools/new_data/international/euro'
for year, config in euro_configs.items():
    filepath = os.path.join(euro_dir, f'euro_{year}.csv')
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        df['round'] = df.apply(lambda r: get_round_value(r, config), axis=1)
        df.to_csv(filepath, index=False)

        round_counts = df['round'].value_counts().to_dict()
        print(f"{year}年欧洲杯: {round_counts}")

print("\n完成!")
