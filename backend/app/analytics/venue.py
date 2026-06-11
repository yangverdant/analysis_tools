"""
球场/场地影响分析模块

功能:
1. 球场信息获取 (名称、容量、草皮类型)
2. 主场优势强度计算
3. 客队旅行距离估算
4. 球场历史战绩分析
5. 场地条件对比赛的影响

数据来源:
- matches.venue, matches.venue_city
- teams.stadium
- 地理位置数据
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import math


@dataclass
class VenueInfo:
    """球场信息"""
    venue_name: str
    city: str
    capacity: int
    surface: str  # grass, artificial
    altitude: int  # 海拔(米)
    latitude: float
    longitude: float


class VenueAnalyzer:
    """球场分析器"""

    # 知名球场信息 (预设数据)
    VENUE_DATABASE = {
        # 英超
        'Old Trafford': {'city': 'Manchester', 'capacity': 74310, 'altitude': 50},
        'Anfield': {'city': 'Liverpool', 'capacity': 54074, 'altitude': 20},
        'Stamford Bridge': {'city': 'London', 'capacity': 40341, 'altitude': 10},
        'Emirates Stadium': {'city': 'London', 'capacity': 60704, 'altitude': 15},
        'Etihad Stadium': {'city': 'Manchester', 'capacity': 55097, 'altitude': 40},
        'Tottenham Hotspur Stadium': {'city': 'London', 'capacity': 62850, 'altitude': 15},
        'St James\' Park': {'city': 'Newcastle', 'capacity': 52305, 'altitude': 30},
        'Villa Park': {'city': 'Birmingham', 'capacity': 42682, 'altitude': 50},
        'Goodison Park': {'city': 'Liverpool', 'capacity': 39572, 'altitude': 25},
        'Selhurst Park': {'city': 'London', 'capacity': 25486, 'altitude': 20},
        'Craven Cottage': {'city': 'London', 'capacity': 24500, 'altitude': 5},
        'Bramall Lane': {'city': 'Sheffield', 'capacity': 32702, 'altitude': 60},
        'Molineux Stadium': {'city': 'Wolverhampton', 'capacity': 31750, 'altitude': 70},
        'The American Express Community Stadium': {'city': 'Brighton', 'capacity': 31872, 'altitude': 10},
        'Vitality Stadium': {'city': 'Bournemouth', 'capacity': 12000, 'altitude': 5},

        # 西甲
        'Santiago Bernabéu': {'city': 'Madrid', 'capacity': 83186, 'altitude': 650},
        'Camp Nou': {'city': 'Barcelona', 'capacity': 99354, 'altitude': 30},
        'Wanda Metropolitano': {'city': 'Madrid', 'capacity': 70460, 'altitude': 600},
        'San Siro': {'city': 'Milan', 'capacity': 80018, 'altitude': 120},
        'Allianz Arena': {'city': 'Munich', 'capacity': 75024, 'altitude': 520},
        'Signal Iduna Park': {'city': 'Dortmund', 'capacity': 81365, 'altitude': 100},
        'Parc des Princes': {'city': 'Paris', 'capacity': 47929, 'altitude': 35},
        'Johan Cruijff ArenA': {'city': 'Amsterdam', 'capacity': 55500, 'altitude': -2},

        # 高海拔球场
        'Estadio Hernando Siles': {'city': 'La Paz', 'capacity': 42000, 'altitude': 3637},
        'Estadio Monumental': {'city': 'Quito', 'capacity': 55104, 'altitude': 2800},
        'Estadio Atahualpa': {'city': 'Quito', 'capacity': 35724, 'altitude': 2800},
    }

    # 城市坐标 (用于计算旅行距离)
    CITY_COORDINATES = {
        'London': (51.5074, -0.1278),
        'Manchester': (53.4808, -2.2426),
        'Liverpool': (53.4084, -2.9916),
        'Birmingham': (52.4862, -1.8904),
        'Leeds': (53.8008, -1.5491),
        'Newcastle': (54.9783, -1.6178),
        'Sheffield': (53.3811, -1.4701),
        'Brighton': (50.8225, -0.1372),
        'Southampton': (50.9097, -1.4044),
        'Bournemouth': (50.7205, -1.8805),
        'Wolverhampton': (52.5870, -2.1288),
        'Norwich': (52.6309, 1.2974),
        'Leicester': (52.6369, -1.1398),
        'Madrid': (40.4168, -3.7038),
        'Barcelona': (41.3851, 2.1734),
        'Milan': (45.4642, 9.1900),
        'Munich': (48.1351, 11.5820),
        'Dortmund': (51.5136, 7.4653),
        'Paris': (48.8566, 2.3522),
        'Amsterdam': (52.3676, 4.9041),
        'Berlin': (52.5200, 13.4050),
        'Rome': (41.9028, 12.4964),
        'Turin': (45.0703, 7.6869),
        'Naples': (40.8518, 14.2681),
        'Lisbon': (38.7223, -9.1393),
        'Porto': (41.1579, -8.6291),
        'Glasgow': (55.8642, -4.2518),
        'Edinburgh': (55.9533, -3.1883),
        'Sunderland': (54.9069, -1.3838),
    }

    # 海拔影响阈值
    ALTITUDE_HIGH = 1500  # 高海拔
    ALTITUDE_VERY_HIGH = 2500  # 极高海拔

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_venue_info(self, venue_name: str) -> Optional[VenueInfo]:
        """获取球场信息"""
        # 查找预设数据
        if venue_name in self.VENUE_DATABASE:
            data = self.VENUE_DATABASE[venue_name]
            return VenueInfo(
                venue_name=venue_name,
                city=data.get('city', ''),
                capacity=data.get('capacity', 0),
                surface=data.get('surface', 'grass'),
                altitude=data.get('altitude', 0),
                latitude=0,
                longitude=0
            )
        return None

    def calculate_distance(self, city1: str, city2: str) -> float:
        """
        计算两城市间的直线距离(公里)

        使用Haversine公式
        """
        if city1 not in self.CITY_COORDINATES or city2 not in self.CITY_COORDINATES:
            return 0

        lat1, lon1 = self.CITY_COORDINATES[city1]
        lat2, lon2 = self.CITY_COORDINATES[city2]

        # Haversine公式
        R = 6371  # 地球半径(公里)

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return round(R * c, 1)

    def calculate_altitude_impact(self, altitude: int) -> Dict:
        """
        计算海拔对比赛的影响

        高海拔对客队影响更大，尤其是海平面来的球队
        """
        if altitude >= self.ALTITUDE_VERY_HIGH:
            return {
                'level': 'extreme',
                'altitude': altitude,
                'home_advantage_factor': 1.15,  # 主队优势+15%
                'stamina_impact': -0.15,  # 客队体能-15%
                'description': f'极高海拔({altitude}m): 客队严重不适'
            }
        elif altitude >= self.ALTITUDE_HIGH:
            return {
                'level': 'high',
                'altitude': altitude,
                'home_advantage_factor': 1.08,
                'stamina_impact': -0.08,
                'description': f'高海拔({altitude}m): 客队需要适应'
            }
        else:
            return {
                'level': 'normal',
                'altitude': altitude,
                'home_advantage_factor': 1.0,
                'stamina_impact': 0,
                'description': '海拔正常'
            }

    def calculate_travel_impact(self, distance: float) -> Dict:
        """
        计算旅行距离对客队的影响

        长途旅行导致疲劳，影响表现
        """
        if distance >= 3000:
            return {
                'level': 'extreme',
                'distance': distance,
                'fatigue_factor': -0.12,
                'description': f'长途旅行({distance:.0f}km): 严重疲劳'
            }
        elif distance >= 1500:
            return {
                'level': 'high',
                'distance': distance,
                'fatigue_factor': -0.08,
                'description': f'中长途旅行({distance:.0f}km): 明显疲劳'
            }
        elif distance >= 500:
            return {
                'level': 'moderate',
                'distance': distance,
                'fatigue_factor': -0.04,
                'description': f'中程旅行({distance:.0f}km): 轻微疲劳'
            }
        else:
            return {
                'level': 'low',
                'distance': distance,
                'fatigue_factor': 0,
                'description': f'短途旅行({distance:.0f}km): 影响小'
            }

    def analyze_venue_advantage(
        self,
        home_team_id: int,
        away_team_id: int,
        venue_name: str = None,
        venue_city: str = None,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析主场优势

        整合海拔、旅行距离、历史战绩等因素
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取球队城市
        cursor.execute("SELECT stadium FROM teams WHERE team_id = ?", (home_team_id,))
        home_team = cursor.fetchone()
        home_city = venue_city or (home_team['stadium'] if home_team else '')

        cursor.execute("SELECT stadium FROM teams WHERE team_id = ?", (away_team_id,))
        away_team = cursor.fetchone()
        away_city = away_team['stadium'] if away_team else ''

        result = {
            'venue': venue_name,
            'home_city': home_city,
            'away_city': away_city,
            'factors': []
        }

        # 1. 海拔影响
        venue_info = self.get_venue_info(venue_name) if venue_name else None
        if venue_info and venue_info.altitude > 0:
            altitude_impact = self.calculate_altitude_impact(venue_info.altitude)
            result['altitude_impact'] = altitude_impact
            if altitude_impact['level'] != 'normal':
                result['factors'].append(altitude_impact['description'])

        # 2. 旅行距离
        if home_city and away_city:
            distance = self.calculate_distance(home_city, away_city)
            travel_impact = self.calculate_travel_impact(distance)
            result['travel_impact'] = travel_impact
            result['distance'] = distance
            if travel_impact['level'] != 'low':
                result['factors'].append(travel_impact['description'])

        # 3. 球场容量影响
        if venue_info and venue_info.capacity > 50000:
            result['capacity_factor'] = {
                'capacity': venue_info.capacity,
                'atmosphere': 'strong',
                'home_advantage_bonus': 0.03
            }
            result['factors'].append(f'大球场({venue_info.capacity}人): 氛围热烈')

        # 4. 历史主场战绩
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws
            FROM matches
            WHERE home_team_id = ?
            AND home_goals IS NOT NULL
            LIMIT 20
        """, (home_team_id,))

        home_record = cursor.fetchone()
        if home_record and home_record['matches'] > 0:
            win_rate = home_record['wins'] / home_record['matches']
            result['home_record'] = {
                'matches': home_record['matches'],
                'wins': home_record['wins'],
                'draws': home_record['draws'],
                'win_rate': round(win_rate, 3)
            }

            if win_rate > 0.65:
                result['factors'].append(f'主场强势(胜率{win_rate*100:.0f}%)')
            elif win_rate < 0.35:
                result['factors'].append(f'主场弱势(胜率{win_rate*100:.0f}%)')

        # 计算综合主场优势系数
        total_factor = 1.0
        if 'altitude_impact' in result:
            total_factor += (result['altitude_impact']['home_advantage_factor'] - 1)
        if 'travel_impact' in result:
            total_factor -= result['travel_impact']['fatigue_factor']
        if 'capacity_factor' in result:
            total_factor += result['capacity_factor']['home_advantage_bonus']

        result['overall_home_advantage'] = round(total_factor, 3)
        result['summary'] = '，'.join(result['factors']) if result['factors'] else '主场优势正常'

        return result

    def get_team_home_performance(
        self,
        team_id: int,
        recent_matches: int = 20,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """获取球队主场表现统计"""
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                SUM(home_goals) as goals_for,
                SUM(away_goals) as goals_against,
                AVG(home_goals) as avg_goals
            FROM (
                SELECT * FROM matches
                WHERE home_team_id = ?
                AND home_goals IS NOT NULL
                ORDER BY match_date DESC
                LIMIT ?
            )
        """, (team_id, recent_matches))

        stats = cursor.fetchone()

        if not stats or stats['matches'] == 0:
            return {'matches': 0}

        return {
            'matches': stats['matches'],
            'wins': stats['wins'] or 0,
            'draws': stats['draws'] or 0,
            'losses': stats['matches'] - (stats['wins'] or 0) - (stats['draws'] or 0),
            'goals_for': stats['goals_for'] or 0,
            'goals_against': stats['goals_against'] or 0,
            'avg_goals': round(stats['avg_goals'] or 0, 2),
            'win_rate': round((stats['wins'] or 0) / stats['matches'], 3),
            'points_per_game': round(((stats['wins'] or 0) * 3 + (stats['draws'] or 0)) / stats['matches'], 2)
        }


def main():
    """测试球场分析"""
    db_path = r"d:\football_tools\data\football_v2.db"
    analyzer = VenueAnalyzer(db_path)

    print("球场分析测试")
    print("=" * 60)

    # 测试距离计算
    print("\n[城市距离计算]")
    cities = [('London', 'Manchester'), ('London', 'Madrid'), ('Madrid', 'Barcelona')]
    for c1, c2 in cities:
        dist = analyzer.calculate_distance(c1, c2)
        print(f"  {c1} -> {c2}: {dist} km")

    # 测试海拔影响
    print("\n[海拔影响分析]")
    altitudes = [100, 1500, 2500, 3600]
    for alt in altitudes:
        impact = analyzer.calculate_altitude_impact(alt)
        print(f"  {alt}m: {impact['description']}")


if __name__ == "__main__":
    main()
