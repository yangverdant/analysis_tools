"""
天气因素分析器 (Weather Analyzer)

分析因素:
1. 比赛场地天气情况
2. 温度影响
3. 降水影响
4. 风力影响
5. 天气对比赛风格的适配度
"""

from typing import Dict, Any, Optional
import sqlite3
import logging

from ..base import (
    FeatureExtractor, ExtractionContext, ExtractionResult,
    FeatureCategory
)
from ...schemas.lottery import PlayType

logger = logging.getLogger(__name__)


class WeatherAnalyzer(FeatureExtractor):
    """
    天气因素分析器

    评估天气对比赛结果的影响
    """

    def __init__(self, db_path: str, config: Dict = None):
        super().__init__(db_path, config or {})
        self._weight = 0.03  # 天气因素权重较低

    @property
    def name(self) -> str:
        return "weather_analyzer"

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.CONTEXT

    @property
    def play_type(self) -> PlayType:
        return PlayType.SPF

    def get_required_data(self) -> list:
        return ['home_team_id', 'away_team_id', 'match_date']

    def initialize(self):
        pass

    def validate_context(self, context: ExtractionContext) -> bool:
        return context.home_team_id is not None and context.away_team_id is not None

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行天气分析"""

        cursor = context.db_conn.cursor()

        # 尝试获取比赛地点的天气信息
        weather_data = self._get_match_weather(cursor, context)

        # 分析天气影响
        impact = self._analyze_weather_impact(weather_data)

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=impact['overall_impact'],
            raw_data={
                'weather': weather_data,
                'impact_analysis': impact,
                'has_data': weather_data.get('has_data', False)
            },
            confidence=impact['confidence'],
            impact_direction=impact['direction'],
            description=impact['description']
        )

    def _get_match_weather(self, cursor, context: ExtractionContext) -> Dict:
        """获取比赛天气信息"""

        # 尝试从match_details表获取天气信息
        try:
            cursor.execute("""
                SELECT city, stadium
                FROM match_details
                WHERE match_id = (
                    SELECT match_id FROM matches
                    WHERE (home_team_id = ? OR away_team_id = ?)
                      AND match_date = ?
                    LIMIT 1
                )
            """, (context.home_team_id, context.home_team_id, context.match_date))

            row = cursor.fetchone()
            if row:
                city = row['city'] if row else None
                stadium = row['stadium'] if row else None
            else:
                city = None
                stadium = None

        except Exception as e:
            logger.debug(f"Could not get match location: {e}")
            city = None
            stadium = None

        # 尝试从球队信息获取主场城市
        if not city:
            try:
                cursor.execute("""
                    SELECT city FROM teams WHERE team_id = ?
                """, (context.home_team_id,))
                row = cursor.fetchone()
                city = row['city'] if row else None
            except:
                city = None

        # 如果没有实际天气数据，返回模拟数据（实际应用中应接入天气API）
        # 这里基于季节和地区给出估计值
        weather = self._estimate_weather(context.match_date, city)

        weather['city'] = city
        weather['stadium'] = stadium
        weather['has_data'] = city is not None

        return weather

    def _estimate_weather(self, match_date: str, city: str) -> Dict:
        """根据日期和城市估计天气（简化版）"""

        # 解析月份
        try:
            month = int(match_date.split('-')[1])
        except:
            month = 1

        # 根据月份估计温度（北半球）
        if month in [12, 1, 2]:
            temp_estimate = 5  # 冬季
            season = 'winter'
        elif month in [3, 4, 5]:
            temp_estimate = 15  # 春季
            season = 'spring'
        elif month in [6, 7, 8]:
            temp_estimate = 28  # 夏季
            season = 'summer'
        else:
            temp_estimate = 18  # 秋季
            season = 'autumn'

        # 日本J联赛的天气特点
        if city:
            city_lower = city.lower() if city else ''
            # 沿海城市湿度较高
            if any(c in city_lower for c in ['osaka', 'tokyo', 'yokohama', 'kobe']):
                humidity = 70
            else:
                humidity = 60
        else:
            humidity = 65

        return {
            'temperature': temp_estimate,
            'humidity': humidity,
            'precipitation': 0,  # 假设无降水
            'wind_speed': 5,  # 假设微风
            'season': season,
            'is_artificial': True  # 标记为估计数据
        }

    def _analyze_weather_impact(self, weather: Dict) -> Dict:
        """分析天气对比赛的影响"""

        temp = weather.get('temperature', 20)
        humidity = weather.get('humidity', 60)
        precipitation = weather.get('precipitation', 0)
        wind = weather.get('wind_speed', 5)

        impacts = []

        # 温度影响
        temp_impact = 0.0
        if temp < 5:
            temp_impact = -0.1
            impacts.append('低温影响技术发挥')
        elif temp > 30:
            temp_impact = -0.1
            impacts.append('高温影响体能')
        else:
            temp_impact = 0.0
            impacts.append('温度适宜')

        # 降水影响
        rain_impact = 0.0
        if precipitation > 10:
            rain_impact = -0.15
            impacts.append('大雨影响比赛节奏')
        elif precipitation > 0:
            rain_impact = -0.05
            impacts.append('小雨可能影响场地')
        else:
            impacts.append('无降水')

        # 风力影响
        wind_impact = 0.0
        if wind > 15:
            wind_impact = -0.1
            impacts.append('大风影响长传和射门')
        elif wind > 10:
            wind_impact = -0.05
            impacts.append('微风影响有限')
        else:
            impacts.append('风力适中')

        # 综合影响
        overall = temp_impact + rain_impact + wind_impact

        # 计算置信度
        if weather.get('is_artificial'):
            confidence = 0.3  # 估计数据，置信度较低
        else:
            confidence = 0.7

        # 影响方向
        if overall < -0.1:
            direction = 'negative'
            desc_suffix = '，不利于技术流球队'
        elif overall < 0:
            direction = 'slight_negative'
            desc_suffix = '，略微影响比赛'
        else:
            direction = 'neutral'
            desc_suffix = '，天气条件良好'

        description = f"温度{temp}°C, 湿度{humidity}%{desc_suffix}"

        return {
            'overall_impact': overall,
            'temp_impact': temp_impact,
            'rain_impact': rain_impact,
            'wind_impact': wind_impact,
            'confidence': confidence,
            'direction': direction,
            'description': description,
            'factors': impacts
        }
