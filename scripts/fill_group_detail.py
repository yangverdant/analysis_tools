import pandas as pd
import os

# 各赛事分组配置（按年份）
configs = {
    'euro': {
        2024: {
            'groups': {
                'A': ['Germany', 'Scotland', 'Hungary', 'Switzerland'],
                'B': ['Spain', 'Croatia', 'Italy', 'Albania'],
                'C': ['Slovenia', 'Denmark', 'Serbia', 'England'],
                'D': ['Poland', 'Netherlands', 'Austria', 'France'],
                'E': ['Belgium', 'Slovakia', 'Romania', 'Ukraine'],
                'F': ['Turkey', 'Georgia', 'Portugal', 'Czech Republic']
            },
            'round_dates': {
                1: ('2024-06-14', '2024-06-18'),
                2: ('2024-06-19', '2024-06-22'),
                3: ('2024-06-23', '2024-06-26')
            }
        },
        2020: {
            'groups': {
                'A': ['Turkey', 'Italy', 'Wales', 'Switzerland'],
                'B': ['Denmark', 'Finland', 'Belgium', 'Russia'],
                'C': ['Netherlands', 'Ukraine', 'Austria', 'North Macedonia'],
                'D': ['England', 'Croatia', 'Scotland', 'Czech Republic'],
                'E': ['Spain', 'Sweden', 'Poland', 'Slovakia'],
                'F': ['Hungary', 'Portugal', 'France', 'Germany']
            },
            'round_dates': {
                1: ('2021-06-11', '2021-06-15'),
                2: ('2021-06-16', '2021-06-19'),
                3: ('2021-06-20', '2021-06-23')
            }
        },
        2016: {
            'groups': {
                'A': ['France', 'Romania', 'Albania', 'Switzerland'],
                'B': ['England', 'Russia', 'Wales', 'Slovakia'],
                'C': ['Germany', 'Ukraine', 'Poland', 'Northern Ireland'],
                'D': ['Spain', 'Czech Republic', 'Turkey', 'Croatia'],
                'E': ['Belgium', 'Italy', 'Republic of Ireland', 'Sweden'],
                'F': ['Portugal', 'Iceland', 'Austria', 'Hungary']
            },
            'round_dates': {
                1: ('2016-06-10', '2016-06-14'),
                2: ('2016-06-15', '2016-06-18'),
                3: ('2016-06-19', '2016-06-22')
            }
        }
    },
    'copa_america': {
        2024: {
            'groups': {
                'A': ['Argentina', 'Peru', 'Chile', 'Canada'],
                'B': ['Mexico', 'Ecuador', 'Venezuela', 'Jamaica'],
                'C': ['United States', 'Uruguay', 'Panama', 'Bolivia'],
                'D': ['Colombia', 'Brazil', 'Paraguay', 'Costa Rica']
            },
            'round_dates': {
                1: ('2024-06-20', '2024-06-25'),
                2: ('2024-06-26', '2024-06-30'),
                3: ('2024-07-01', '2024-07-02')
            }
        }
    }
}

def fill_group_round(df, config):
    """填充小组赛的详细 round 字段"""
    for idx, row in df.iterrows():
        if row['round'] != 'group':
            continue

        date = row['match_date']
        home = row['home_team']

        # 确定小组
        group = None
        for g, teams in config['groups'].items():
            if home in teams:
                group = g
                break

        if not group:
            continue

        # 确定轮次
        round_num = None
        for r, (start, end) in config['round_dates'].items():
            if start <= date <= end:
                round_num = r
                break

        if round_num:
            df.at[idx, 'round'] = f"{group}_{round_num}"

    return df

# 处理各赛事
for competition, years in configs.items():
    directory = f'd:/football_tools/new_data/international/{competition}'
    for year, config in years.items():
        filepath = os.path.join(directory, f'{competition}_{year}.csv')
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            df = fill_group_round(df, config)
            df.to_csv(filepath, index=False)

            round_counts = df['round'].value_counts().to_dict()
            print(f"{competition} {year}: {round_counts}")

print("\n完成!")