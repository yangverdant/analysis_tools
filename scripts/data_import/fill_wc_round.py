import pandas as pd
import os

# 各届世界杯分组和日期
wc_configs = {
    2002: {
        'groups': {
            'A': ['France', 'Senegal', 'Uruguay', 'Denmark'],
            'B': ['Spain', 'Slovenia', 'Paraguay', 'South Africa'],
            'C': ['Brazil', 'Turkey', 'China PR', 'Costa Rica'],
            'D': ['South Korea', 'Poland', 'United States', 'Portugal'],
            'E': ['Germany', 'Saudi Arabia', 'Republic of Ireland', 'Cameroon'],
            'F': ['Argentina', 'Nigeria', 'England', 'Sweden'],
            'G': ['Italy', 'Ecuador', 'Croatia', 'Mexico'],
            'H': ['Japan', 'Belgium', 'Russia', 'Tunisia']
        },
        'round_dates': {
            1: ('2002-05-31', '2002-06-05'),
            2: ('2002-06-06', '2002-06-11'),
            3: ('2002-06-11', '2002-06-14')
        },
        'ko_dates': {
            'R16': ('2002-06-15', '2002-06-18'),
            'QF': ('2002-06-21', '2002-06-22'),
            'SF': ('2002-06-25', '2002-06-26'),
            '3RD': ('2002-06-29', '2002-06-29'),
            'F': ('2002-06-30', '2002-06-30')
        }
    },
    2006: {
        'groups': {
            'A': ['Germany', 'Costa Rica', 'Poland', 'Ecuador'],
            'B': ['England', 'Paraguay', 'Trinidad and Tobago', 'Sweden'],
            'C': ['Argentina', 'Ivory Coast', 'Serbia and Montenegro', 'Netherlands'],
            'D': ['Mexico', 'Iran', 'Angola', 'Portugal'],
            'E': ['Italy', 'Ghana', 'United States', 'Czech Republic'],
            'F': ['Brazil', 'Croatia', 'Australia', 'Japan'],
            'G': ['France', 'Switzerland', 'South Korea', 'Togo'],
            'H': ['Spain', 'Ukraine', 'Tunisia', 'Saudi Arabia']
        },
        'round_dates': {
            1: ('2006-06-09', '2006-06-14'),
            2: ('2006-06-15', '2006-06-20'),
            3: ('2006-06-20', '2006-06-23')
        },
        'ko_dates': {
            'R16': ('2006-06-24', '2006-06-27'),
            'QF': ('2006-06-30', '2006-07-01'),
            'SF': ('2006-07-04', '2006-07-05'),
            '3RD': ('2006-07-08', '2006-07-08'),
            'F': ('2006-07-09', '2006-07-09')
        }
    },
    2010: {
        'groups': {
            'A': ['South Africa', 'Mexico', 'Uruguay', 'France'],
            'B': ['Argentina', 'Nigeria', 'South Korea', 'Greece'],
            'C': ['England', 'United States', 'Algeria', 'Slovenia'],
            'D': ['Germany', 'Australia', 'Serbia', 'Ghana'],
            'E': ['Netherlands', 'Denmark', 'Japan', 'Cameroon'],
            'F': ['Italy', 'Paraguay', 'New Zealand', 'Slovakia'],
            'G': ['Brazil', 'North Korea', 'Ivory Coast', 'Portugal'],
            'H': ['Spain', 'Switzerland', 'Honduras', 'Chile']
        },
        'round_dates': {
            1: ('2010-06-11', '2010-06-16'),
            2: ('2010-06-17', '2010-06-22'),
            3: ('2010-06-22', '2010-06-25')
        },
        'ko_dates': {
            'R16': ('2010-06-26', '2010-06-29'),
            'QF': ('2010-07-02', '2010-07-03'),
            'SF': ('2010-07-06', '2010-07-07'),
            '3RD': ('2010-07-10', '2010-07-10'),
            'F': ('2010-07-11', '2010-07-11')
        }
    },
    2014: {
        'groups': {
            'A': ['Brazil', 'Mexico', 'Croatia', 'Cameroon'],
            'B': ['Netherlands', 'Chile', 'Spain', 'Australia'],
            'C': ['Colombia', 'Greece', 'Ivory Coast', 'Japan'],
            'D': ['Costa Rica', 'Uruguay', 'Italy', 'England'],
            'E': ['France', 'Switzerland', 'Ecuador', 'Honduras'],
            'F': ['Argentina', 'Nigeria', 'Bosnia and Herzegovina', 'Iran'],
            'G': ['Germany', 'United States', 'Portugal', 'Ghana'],
            'H': ['Belgium', 'Algeria', 'Russia', 'South Korea']
        },
        'round_dates': {
            1: ('2014-06-12', '2014-06-17'),
            2: ('2014-06-18', '2014-06-23'),
            3: ('2014-06-23', '2014-06-26')
        },
        'ko_dates': {
            'R16': ('2014-06-28', '2014-07-01'),
            'QF': ('2014-07-04', '2014-07-05'),
            'SF': ('2014-07-08', '2014-07-09'),
            '3RD': ('2014-07-12', '2014-07-12'),
            'F': ('2014-07-13', '2014-07-13')
        }
    },
    2018: {
        'groups': {
            'A': ['Russia', 'Saudi Arabia', 'Egypt', 'Uruguay'],
            'B': ['Portugal', 'Spain', 'Morocco', 'Iran'],
            'C': ['France', 'Australia', 'Peru', 'Denmark'],
            'D': ['Argentina', 'Iceland', 'Croatia', 'Nigeria'],
            'E': ['Brazil', 'Switzerland', 'Costa Rica', 'Serbia'],
            'F': ['Germany', 'Mexico', 'Sweden', 'South Korea'],
            'G': ['Belgium', 'Panama', 'Tunisia', 'England'],
            'H': ['Poland', 'Senegal', 'Colombia', 'Japan']
        },
        'round_dates': {
            1: ('2018-06-14', '2018-06-19'),
            2: ('2018-06-20', '2018-06-25'),
            3: ('2018-06-25', '2018-06-28')
        },
        'ko_dates': {
            'R16': ('2018-06-30', '2018-07-03'),
            'QF': ('2018-07-06', '2018-07-07'),
            'SF': ('2018-07-10', '2018-07-11'),
            '3RD': ('2018-07-14', '2018-07-14'),
            'F': ('2018-07-15', '2018-07-15')
        }
    },
    2022: {
        'groups': {
            'A': ['Qatar', 'Ecuador', 'Senegal', 'Netherlands'],
            'B': ['England', 'Iran', 'United States', 'Wales'],
            'C': ['Argentina', 'Saudi Arabia', 'Mexico', 'Poland'],
            'D': ['France', 'Australia', 'Denmark', 'Tunisia'],
            'E': ['Spain', 'Costa Rica', 'Germany', 'Japan'],
            'F': ['Belgium', 'Canada', 'Morocco', 'Croatia'],
            'G': ['Brazil', 'Serbia', 'Switzerland', 'Cameroon'],
            'H': ['Portugal', 'Ghana', 'Uruguay', 'South Korea']
        },
        'round_dates': {
            1: ('2022-11-20', '2022-11-24'),
            2: ('2022-11-25', '2022-11-28'),
            3: ('2022-11-29', '2022-12-02')
        },
        'ko_dates': {
            'R16': ('2022-12-03', '2022-12-06'),
            'QF': ('2022-12-09', '2022-12-10'),
            'SF': ('2022-12-13', '2022-12-14'),
            '3RD': ('2022-12-17', '2022-12-17'),
            'F': ('2022-12-18', '2022-12-18')
        }
    }
}

def get_round_value(row, config):
    date = row['match_date']
    home = row['home_team']

    # 检查淘汰赛
    for ko_round, (start, end) in config['ko_dates'].items():
        if start <= date <= end:
            return ko_round

    # 检查小组赛
    for round_num, (start, end) in config['round_dates'].items():
        if start <= date <= end:
            for group, teams in config['groups'].items():
                if home in teams:
                    return f"{group}_{round_num}"

    return ''

# 处理各届世界杯
wc_dir = 'd:/football_tools/new_data/international/world_cup'
for year, config in wc_configs.items():
    filepath = os.path.join(wc_dir, f'world_cup_{year}.csv')
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        df['round'] = df.apply(lambda r: get_round_value(r, config), axis=1)
        df.to_csv(filepath, index=False)

        round_counts = df['round'].value_counts().to_dict()
        print(f"{year}年世界杯: {round_counts}")

print("\n完成!")
