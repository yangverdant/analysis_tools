"""
世界城市时间转换模块

功能:
1. 世界主要城市时区数据库
2. 比赛时间转换到当地时区
3. 球队主场城市时间
4. 多时区时间显示

支持:
- 自动检测城市时区
- 夏令时处理
- 比赛时间本地化
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pytz
from zoneinfo import ZoneInfo


@dataclass
class CityTimezone:
    """城市时区信息"""
    city: str
    country: str
    timezone: str
    utc_offset: str
    dst: bool  # 是否使用夏令时


class WorldTimeConverter:
    """世界城市时间转换器"""

    # 世界主要足球城市时区数据库
    CITIES = {
        # 英超
        'London': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Arsenal', 'Chelsea', 'Tottenham', 'West Ham', 'Fulham', 'Brentford', 'Crystal Palace']},
        'Manchester': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Manchester United', 'Manchester City']},
        'Liverpool': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Liverpool', 'Everton']},
        'Birmingham': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Aston Villa']},
        'Newcastle': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Newcastle']},
        'Leicester': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Leicester']},
        'Leeds': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Leeds']},
        'Southampton': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Southampton']},
        'Brighton': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Brighton']},
        'Wolverhampton': {'timezone': 'Europe/London', 'country': 'UK', 'teams': ['Wolves']},

        # 西甲
        'Madrid': {'timezone': 'Europe/Madrid', 'country': 'Spain', 'teams': ['Real Madrid', 'Atletico Madrid', 'Getafe', 'Rayo Vallecano', 'Leganes']},
        'Barcelona': {'timezone': 'Europe/Madrid', 'country': 'Spain', 'teams': ['Barcelona', 'Espanyol', 'Girona']},
        'Seville': {'timezone': 'Europe/Madrid', 'country': 'Spain', 'teams': ['Sevilla', 'Real Betis']},
        'Valencia': {'timezone': 'Europe/Madrid', 'country': 'Spain', 'teams': ['Valencia', 'Villarreal', 'Levante']},
        'Bilbao': {'timezone': 'Europe/Madrid', 'country': 'Spain', 'teams': ['Athletic Bilbao']},
        'San Sebastian': {'timezone': 'Europe/Madrid', 'country': 'Spain', 'teams': ['Real Sociedad']},

        # 德甲
        'Munich': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Bayern Munich']},
        'Dortmund': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Borussia Dortmund']},
        'Leverkusen': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Bayer Leverkusen']},
        'Leipzig': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['RB Leipzig']},
        'Frankfurt': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Eintracht Frankfurt']},
        'Stuttgart': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Stuttgart']},
        'Hamburg': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Hamburg']},
        'Berlin': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Hertha Berlin', 'Union Berlin']},
        'Wolfsburg': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Wolfsburg']},
        'Monchengladbach': {'timezone': 'Europe/Berlin', 'country': 'Germany', 'teams': ['Borussia Monchengladbach']},

        # 意甲
        'Milan': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['AC Milan', 'Inter Milan']},
        'Turin': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['Juventus', 'Torino']},
        'Rome': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['Roma', 'Lazio']},
        'Naples': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['Napoli']},
        'Florence': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['Fiorentina']},
        'Bologna': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['Bologna']},
        'Genoa': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['Genoa', 'Sampdoria']},
        'Verona': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['Hellas Verona']},
        'Bergamo': {'timezone': 'Europe/Rome', 'country': 'Italy', 'teams': ['Atalanta']},

        # 法甲
        'Paris': {'timezone': 'Europe/Paris', 'country': 'France', 'teams': ['Paris Saint-Germain']},
        'Marseille': {'timezone': 'Europe/Paris', 'country': 'France', 'teams': ['Marseille']},
        'Lyon': {'timezone': 'Europe/Paris', 'country': 'France', 'teams': ['Lyon']},
        'Lille': {'timezone': 'Europe/Paris', 'country': 'France', 'teams': ['Lille']},
        'Nice': {'timezone': 'Europe/Paris', 'country': 'France', 'teams': ['Nice']},
        'Monaco': {'timezone': 'Europe/Paris', 'country': 'France', 'teams': ['Monaco']},
        'Toulouse': {'timezone': 'Europe/Paris', 'country': 'France', 'teams': ['Toulouse']},
        'Bordeaux': {'timezone': 'Europe/Paris', 'country': 'France', 'teams': ['Bordeaux']},

        # 葡超
        'Lisbon': {'timezone': 'Europe/Lisbon', 'country': 'Portugal', 'teams': ['Benfica', 'Sporting Lisbon']},
        'Porto': {'timezone': 'Europe/Lisbon', 'country': 'Portugal', 'teams': ['Porto']},

        # 荷甲
        'Amsterdam': {'timezone': 'Europe/Amsterdam', 'country': 'Netherlands', 'teams': ['Ajax', 'AZ Alkmaar']},
        'Rotterdam': {'timezone': 'Europe/Amsterdam', 'country': 'Netherlands', 'teams': ['Feyenoord', 'Sparta Rotterdam']},
        'Eindhoven': {'timezone': 'Europe/Amsterdam', 'country': 'Netherlands', 'teams': ['PSV Eindhoven']},

        # 比利时
        'Brussels': {'timezone': 'Europe/Brussels', 'country': 'Belgium', 'teams': ['Anderlecht']},
        'Bruges': {'timezone': 'Europe/Brussels', 'country': 'Belgium', 'teams': ['Club Brugge']},

        # 苏格兰
        'Glasgow': {'timezone': 'Europe/London', 'country': 'Scotland', 'teams': ['Celtic', 'Rangers']},
        'Edinburgh': {'timezone': 'Europe/London', 'country': 'Scotland', 'teams': ['Hearts', 'Hibernian']},

        # 土耳其
        'Istanbul': {'timezone': 'Europe/Istanbul', 'country': 'Turkey', 'teams': ['Galatasaray', 'Fenerbahce', 'Besiktas']},

        # 希腊
        'Athens': {'timezone': 'Europe/Athens', 'country': 'Greece', 'teams': ['Olympiacos', 'Panathinaikos', 'AEK Athens']},

        # 俄罗斯
        'Moscow': {'timezone': 'Europe/Moscow', 'country': 'Russia', 'teams': ['CSKA Moscow', 'Spartak Moscow', 'Lokomotiv Moscow', 'Zenit']},

        # 乌克兰
        'Kyiv': {'timezone': 'Europe/Kiev', 'country': 'Ukraine', 'teams': ['Dynamo Kyiv', 'Shakhtar Donetsk']},

        # 波兰
        'Warsaw': {'timezone': 'Europe/Warsaw', 'country': 'Poland', 'teams': ['Legia Warsaw']},

        # 奥地利
        'Vienna': {'timezone': 'Europe/Vienna', 'country': 'Austria', 'teams': ['Rapid Vienna', 'Austria Vienna']},
        'Salzburg': {'timezone': 'Europe/Vienna', 'country': 'Austria', 'teams': ['Red Bull Salzburg']},

        # 瑞士
        'Zurich': {'timezone': 'Europe/Zurich', 'country': 'Switzerland', 'teams': ['FC Zurich', 'Grasshopper']},
        'Basel': {'timezone': 'Europe/Zurich', 'country': 'Switzerland', 'teams': ['Basel']},
        'Geneva': {'timezone': 'Europe/Zurich', 'country': 'Switzerland', 'teams': ['Servette']},

        # 捷克
        'Prague': {'timezone': 'Europe/Prague', 'country': 'Czech Republic', 'teams': ['Sparta Prague', 'Slavia Prague']},

        # 美洲
        'New York': {'timezone': 'America/New_York', 'country': 'USA', 'teams': ['New York City FC', 'New York Red Bulls']},
        'Los Angeles': {'timezone': 'America/Los_Angeles', 'country': 'USA', 'teams': ['LA Galaxy', 'Los Angeles FC']},
        'Miami': {'timezone': 'America/New_York', 'country': 'USA', 'teams': ['Inter Miami']},
        'Mexico City': {'timezone': 'America/Mexico_City', 'country': 'Mexico', 'teams': ['Club America', 'Chivas']},
        'Buenos Aires': {'timezone': 'America/Argentina/Buenos_Aires', 'country': 'Argentina', 'teams': ['Boca Juniors', 'River Plate']},
        'Rio de Janeiro': {'timezone': 'America/Sao_Paulo', 'country': 'Brazil', 'teams': ['Flamengo', 'Fluminense', 'Vasco']},
        'Sao Paulo': {'timezone': 'America/Sao_Paulo', 'country': 'Brazil', 'teams': ['Sao Paulo', 'Corinthians', 'Palmeiras', 'Santos']},
        'Belo Horizonte': {'timezone': 'America/Sao_Paulo', 'country': 'Brazil', 'teams': ['Atletico Mineiro', 'Cruzeiro']},
        'Lima': {'timezone': 'America/Lima', 'country': 'Peru', 'teams': ['Alianza Lima', 'Universitario']},
        'Bogota': {'timezone': 'America/Bogota', 'country': 'Colombia', 'teams': ['Millonarios', 'Atletico Nacional']},

        # 亚洲
        'Tokyo': {'timezone': 'Asia/Tokyo', 'country': 'Japan', 'teams': ['Tokyo', 'Kawasaki Frontale', 'Yokohama F. Marinos']},
        'Osaka': {'timezone': 'Asia/Tokyo', 'country': 'Japan', 'teams': ['Cerezo Osaka', 'Gamba Osaka']},
        'Seoul': {'timezone': 'Asia/Seoul', 'country': 'South Korea', 'teams': ['FC Seoul', 'Suwon Samsung']},
        'Shanghai': {'timezone': 'Asia/Shanghai', 'country': 'China', 'teams': ['Shanghai Shenhua', 'Shanghai Port']},
        'Beijing': {'timezone': 'Asia/Shanghai', 'country': 'China', 'teams': ['Beijing Guoan']},
        'Guangzhou': {'timezone': 'Asia/Shanghai', 'country': 'China', 'teams': ['Guangzhou Evergrande']},
        'Hong Kong': {'timezone': 'Asia/Hong_Kong', 'country': 'Hong Kong', 'teams': ['Kitchee', 'Eastern AA']},
        'Singapore': {'timezone': 'Asia/Singapore', 'country': 'Singapore', 'teams': ['Lion City Sailors']},
        'Bangkok': {'timezone': 'Asia/Bangkok', 'country': 'Thailand', 'teams': ['Buriram United']},
        'Kuala Lumpur': {'timezone': 'Asia/Kuala_Lumpur', 'country': 'Malaysia', 'teams': ['Johor Darul Ta\'zim']},
        'Jakarta': {'timezone': 'Asia/Jakarta', 'country': 'Indonesia', 'teams': ['Persib', 'Persija']},
        'Mumbai': {'timezone': 'Asia/Kolkata', 'country': 'India', 'teams': ['Mumbai City', 'ATK Mohun Bagan']},
        'Riyadh': {'timezone': 'Asia/Riyadh', 'country': 'Saudi Arabia', 'teams': ['Al Hilal', 'Al Nassr', 'Al Ittihad']},
        'Jeddah': {'timezone': 'Asia/Riyadh', 'country': 'Saudi Arabia', 'teams': ['Al Ahli']},
        'Dubai': {'timezone': 'Asia/Dubai', 'country': 'UAE', 'teams': ['Al Ain', 'Al Wahda']},
        'Doha': {'timezone': 'Asia/Qatar', 'country': 'Qatar', 'teams': ['Al Sadd', 'Al Duhail']},
        'Tehran': {'timezone': 'Asia/Tehran', 'country': 'Iran', 'teams': ['Persepolis', 'Esteghlal']},

        # 大洋洲
        'Sydney': {'timezone': 'Australia/Sydney', 'country': 'Australia', 'teams': ['Sydney FC', 'Western Sydney Wanderers']},
        'Melbourne': {'timezone': 'Australia/Melbourne', 'country': 'Australia', 'teams': ['Melbourne City', 'Melbourne Victory']},
        'Auckland': {'timezone': 'Pacific/Auckland', 'country': 'New Zealand', 'teams': ['Auckland City']},

        # 非洲
        'Cairo': {'timezone': 'Africa/Cairo', 'country': 'Egypt', 'teams': ['Al Ahly', 'Zamalek']},
        'Casablanca': {'timezone': 'Africa/Casablanca', 'country': 'Morocco', 'teams': ['Wydad', 'Raja']},
        'Johannesburg': {'timezone': 'Africa/Johannesburg', 'country': 'South Africa', 'teams': ['Kaizer Chiefs', 'Orlando Pirates']},
        'Lagos': {'timezone': 'Africa/Lagos', 'country': 'Nigeria', 'teams': ['Enyimba']},
    }

    # 球队到城市的映射
    TEAM_TO_CITY = {}
    for city, info in CITIES.items():
        for team in info.get('teams', []):
            TEAM_TO_CITY[team.lower()] = city

    def __init__(self, db_path: str = None):
        self.db_path = db_path

    def get_city_timezone(self, city: str) -> Optional[str]:
        """
        获取城市时区

        Args:
            city: 城市名称

        Returns:
            时区字符串 (如 'Europe/London')
        """
        city_info = self.CITIES.get(city)
        if city_info:
            return city_info['timezone']
        return None

    def get_team_timezone(self, team_name: str) -> Optional[str]:
        """
        获取球队主场城市时区

        Args:
            team_name: 球队名称

        Returns:
            时区字符串
        """
        city = self.TEAM_TO_CITY.get(team_name.lower())
        if city:
            return self.CITIES[city]['timezone']
        return None

    def get_team_city(self, team_name: str) -> Optional[str]:
        """
        获取球队所在城市

        Args:
            team_name: 球队名称

        Returns:
            城市名称
        """
        return self.TEAM_TO_CITY.get(team_name.lower())

    def convert_time(
        self,
        utc_time: datetime,
        target_timezone: str
    ) -> datetime:
        """
        将UTC时间转换为目标时区时间

        Args:
            utc_time: UTC时间
            target_timezone: 目标时区 (如 'Europe/London')

        Returns:
            目标时区的本地时间
        """
        try:
            # 确保UTC时间有时区信息
            if utc_time.tzinfo is None:
                utc_time = pytz.utc.localize(utc_time)

            # 转换到目标时区
            target_tz = pytz.timezone(target_timezone)
            local_time = utc_time.astimezone(target_tz)
            return local_time
        except Exception as e:
            print(f"时间转换失败: {e}")
            return utc_time

    def convert_to_multiple_timezones(
        self,
        utc_time: datetime,
        timezones: List[str]
    ) -> Dict[str, datetime]:
        """
        将UTC时间转换为多个时区时间

        Args:
            utc_time: UTC时间
            timezones: 时区列表

        Returns:
            各时区的本地时间字典
        """
        result = {}
        for tz in timezones:
            try:
                local_time = self.convert_time(utc_time, tz)
                result[tz] = local_time
            except:
                continue
        return result

    def get_match_local_times(
        self,
        utc_time: datetime,
        home_team: str,
        away_team: str
    ) -> Dict:
        """
        获取比赛在双方主场城市的本地时间

        Args:
            utc_time: UTC比赛时间
            home_team: 主队名称
            away_team: 客队名称

        Returns:
            包含各时区时间的字典
        """
        result = {
            'utc': utc_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'home_team': home_team,
            'away_team': away_team,
        }

        # 主队本地时间
        home_tz = self.get_team_timezone(home_team)
        if home_tz:
            home_city = self.get_team_city(home_team)
            home_time = self.convert_time(utc_time, home_tz)
            result['home_local'] = {
                'city': home_city,
                'timezone': home_tz,
                'time': home_time.strftime('%Y-%m-%d %H:%M:%S'),
                'display': home_time.strftime('%H:%M') + f' ({home_city})'
            }

        # 客队本地时间
        away_tz = self.get_team_timezone(away_team)
        if away_tz:
            away_city = self.get_team_city(away_team)
            away_time = self.convert_time(utc_time, away_tz)
            result['away_local'] = {
                'city': away_city,
                'timezone': away_tz,
                'time': away_time.strftime('%Y-%m-%d %H:%M:%S'),
                'display': away_time.strftime('%H:%M') + f' ({away_city})'
            }

        # 主要观看地区时间
        major_timezones = [
            ('Beijing/Shanghai', 'Asia/Shanghai'),
            ('London', 'Europe/London'),
            ('New York', 'America/New_York'),
            ('Los Angeles', 'America/Los_Angeles'),
            ('Tokyo', 'Asia/Tokyo'),
            ('Sydney', 'Australia/Sydney'),
        ]

        result['major_cities'] = []
        for city_name, tz in major_timezones:
            try:
                local_time = self.convert_time(utc_time, tz)
                result['major_cities'].append({
                    'city': city_name,
                    'timezone': tz,
                    'time': local_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'display': local_time.strftime('%H:%M')
                })
            except:
                continue

        return result

    def get_current_times(self, cities: List[str] = None) -> Dict[str, Dict]:
        """
        获取多个城市的当前时间

        Args:
            cities: 城市列表，默认返回主要城市

        Returns:
            各城市当前时间
        """
        if cities is None:
            # 默认返回主要足球城市
            cities = [
                'London', 'Madrid', 'Barcelona', 'Munich', 'Milan',
                'Paris', 'Lisbon', 'Amsterdam', 'Istanbul', 'Athens',
                'Moscow', 'New York', 'Los Angeles', 'Tokyo', 'Sydney',
                'Shanghai', 'Beijing', 'Hong Kong', 'Singapore', 'Riyadh'
            ]

        now_utc = datetime.now(pytz.utc)
        result = {}

        for city in cities:
            tz = self.get_city_timezone(city)
            if tz:
                try:
                    local_time = self.convert_time(now_utc, tz)
                    city_info = self.CITIES.get(city, {})
                    result[city] = {
                        'timezone': tz,
                        'country': city_info.get('country', ''),
                        'time': local_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'display': local_time.strftime('%H:%M'),
                        'date': local_time.strftime('%Y-%m-%d'),
                        'weekday': local_time.strftime('%A'),
                        'is_dst': local_time.dst() != timedelta(0) if local_time.dst() else False
                    }
                except:
                    continue

        return result

    def get_timezone_offset(self, timezone_str: str, dt: datetime = None) -> str:
        """
        获取时区偏移量

        Args:
            timezone_str: 时区字符串
            dt: 日期时间，默认当前时间

        Returns:
            偏移量字符串 (如 '+08:00')
        """
        if dt is None:
            dt = datetime.now(pytz.utc)

        try:
            tz = pytz.timezone(timezone_str)
            local_time = dt.astimezone(tz)
            offset = local_time.strftime('%z')
            # 格式化: +0800 -> +08:00
            return offset[:3] + ':' + offset[3:]
        except:
            return '+00:00'

    def search_city(self, query: str) -> List[Dict]:
        """
        搜索城市

        Args:
            query: 搜索关键词

        Returns:
            匹配的城市列表
        """
        query = query.lower()
        results = []

        for city, info in self.CITIES.items():
            if query in city.lower() or query in info.get('country', '').lower():
                tz = info['timezone']
                offset = self.get_timezone_offset(tz)
                results.append({
                    'city': city,
                    'country': info['country'],
                    'timezone': tz,
                    'utc_offset': offset,
                    'teams': info.get('teams', [])
                })

        return results

    def get_all_cities(self) -> List[Dict]:
        """
        获取所有城市列表

        Returns:
            城市列表
        """
        results = []
        for city, info in self.CITIES.items():
            tz = info['timezone']
            offset = self.get_timezone_offset(tz)
            results.append({
                'city': city,
                'country': info['country'],
                'timezone': tz,
                'utc_offset': offset,
                'teams': info.get('teams', [])
            })
        return results


def main():
    """测试世界时间转换器"""
    converter = WorldTimeConverter()

    print("世界城市时间转换器测试")
    print("=" * 60)

    # 测试当前时间
    print("\n[主要城市当前时间]")
    times = converter.get_current_times()
    for city, info in list(times.items())[:10]:
        print(f"  {city}: {info['display']} ({info['timezone']})")

    # 测试比赛时间转换
    print("\n[比赛时间转换示例]")
    from datetime import datetime
    import pytz

    # 假设一场英超比赛 UTC 15:00 开始
    utc_time = datetime(2024, 5, 20, 15, 0, 0, tzinfo=pytz.utc)
    match_times = converter.get_match_local_times(utc_time, 'Arsenal', 'Chelsea')

    print(f"  UTC时间: {match_times['utc']}")
    if 'home_local' in match_times:
        print(f"  主队时间: {match_times['home_local']['display']}")
    if 'away_local' in match_times:
        print(f"  客队时间: {match_times['away_local']['display']}")

    print("\n[主要城市观看时间]")
    for city_info in match_times.get('major_cities', []):
        print(f"  {city_info['city']}: {city_info['display']}")

    # 测试城市搜索
    print("\n[搜索城市: London]")
    results = converter.search_city('London')
    for r in results:
        print(f"  {r['city']}, {r['country']} ({r['utc_offset']})")

    # 测试球队时区
    print("\n[球队时区查询]")
    teams = ['Real Madrid', 'Bayern Munich', 'AC Milan', 'Paris Saint-Germain', 'Barcelona']
    for team in teams:
        tz = converter.get_team_timezone(team)
        city = converter.get_team_city(team)
        if tz:
            offset = converter.get_timezone_offset(tz)
            print(f"  {team}: {city} ({tz}, UTC{offset})")


if __name__ == "__main__":
    main()
