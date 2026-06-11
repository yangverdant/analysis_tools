"""赛前新闻扫描器 — 伤病/阵容/赛前发布情报"""

import re
from dataclasses import dataclass, field
from typing import Optional
from fetchers.pre_match.config import INJURY_KEYWORDS_EN, KEY_PLAYER_KEYWORDS


@dataclass
class PlayerStatus:
    """球员状态"""
    name: str
    status: str  # 'injured' / 'doubtful' / 'rested' / 'returning'
    impact: str  # 'high' / 'medium' / 'low'
    detail: str  # 原文描述


@dataclass
class TeamIntel:
    """单队情报"""
    team_name: str
    key_players_missing: list = field(default_factory=list)   # PlayerStatus
    key_players_returning: list = field(default_factory=list)  # PlayerStatus
    injury_count: int = 0
    impact_level: str = 'low'  # 'high' / 'medium' / 'low'
    news_summary: str = ''


@dataclass
class PreMatchIntel:
    """赛前情报汇总"""
    home: TeamIntel
    away: TeamIntel
    confidence: float = 0.0  # 情报可信度


class PreMatchNewsScanner:
    """赛前新闻扫描器"""

    def __init__(self):
        self.injury_keywords = INJURY_KEYWORDS_EN
        self.key_player_keywords = KEY_PLAYER_KEYWORDS

    def scan_match_news(
        self,
        home_team: str,
        away_team: str,
        date: str,
        team_cn_names: Optional[dict] = None
    ) -> PreMatchIntel:
        """扫描比赛相关新闻,提取伤病/阵容情报"""

        # 获取新闻源
        all_news = self._fetch_news_sources()

        # 按队名过滤
        home_names = self._get_team_names(home_team, team_cn_names)
        away_names = self._get_team_names(away_team, team_cn_names)

        home_news = self._filter_by_team(all_news, home_names)
        away_news = self._filter_by_team(all_news, away_names)

        # 提取情报
        home_intel = self._extract_team_intel(home_team, home_news)
        away_intel = self._extract_team_intel(away_team, away_news)

        # 计算可信度
        total_news = len(home_news) + len(away_news)
        confidence = min(1.0, total_news / 10)  # 10条新闻=满可信度

        return PreMatchIntel(
            home=home_intel,
            away=away_intel,
            confidence=confidence
        )

    def _fetch_news_sources(self) -> list:
        """从多个新闻源获取新闻"""

        all_news = []

        # 源1: zhibo8
        try:
            from fetchers.zhibo8.get_news import get_news as get_zhibo8_news
            zhibo8_news = get_zhibo8_news(100)
            if zhibo8_news:
                for item in zhibo8_news:
                    all_news.append({
                        'title': item.get('title', ''),
                        'content': item.get('content', '') or item.get('desc', ''),
                        'type': item.get('type', ''),
                        'source': 'zhibo8'
                    })
        except Exception:
            pass

        # 源2: dongqiudi
        try:
            from fetchers.dongqiudi.get_news import get_news as get_dongqiudi_news
            dqd_news = get_dongqiudi_news(50)
            if dqd_news:
                for item in dqd_news:
                    all_news.append({
                        'title': item.get('title', ''),
                        'content': item.get('content', '') or item.get('summary', ''),
                        'type': item.get('category', ''),
                        'source': 'dongqiudi'
                    })
        except Exception:
            pass

        return all_news

    def _get_team_names(self, team_en: str, cn_names: Optional[dict] = None) -> list:
        """获取球队所有可能的名称(英文+中文别名)"""

        names = [team_en.lower()]

        # 常见缩写/别名
        aliases = {
            'England': ['england', '三狮军团', '英格兰'],
            'France': ['france', '高卢雄鸡', '法国'],
            'Germany': ['germany', '德意志', '德国'],
            'Spain': ['spain', '斗牛士', '西班牙'],
            'Netherlands': ['netherlands', 'holland', 'dutch', '橙衣军团', '荷兰'],
            'Italy': ['italy', '蓝衣军团', '意大利'],
            'Portugal': ['portugal', '葡萄牙'],
            'Brazil': ['brazil', '巴西', '桑巴军团'],
            'Argentina': ['argentina', '阿根廷', '潘帕斯雄鹰'],
            'Mexico': ['mexico', '墨西哥'],
            'Japan': ['japan', '日本'],
            'South Korea': ['south korea', 'korea republic', '韩国'],
            'Morocco': ['morocco', '摩洛哥'],
            'Algeria': ['algeria', '阿尔及利亚'],
            'Turkey': ['turkey', 'türkiye', '土耳其'],
            'Serbia': ['serbia', '塞尔维亚'],
            'Croatia': ['croatia', '克罗地亚'],
            'Sweden': ['sweden', '瑞典'],
            'Denmark': ['denmark', '丹麦'],
            'Norway': ['norway', '挪威'],
            'Ivory Coast': ['ivory coast', "cote d'ivoire", '科特迪瓦'],
            'Nigeria': ['nigeria', '尼日利亚'],
            'Ghana': ['ghana', '加纳'],
            'Colombia': ['colombia', '哥伦比亚'],
            'Ecuador': ['ecuador', '厄瓜多尔'],
            'Peru': ['peru', '秘鲁'],
            'Bolivia': ['bolivia', '玻利维亚'],
            'Greece': ['greece', '希腊'],
            'Congo': ['congo', '刚果'],
            'DR Congo': ['dr congo', 'democratic republic congo', '刚果民主'],
        }

        if team_en in aliases:
            names.extend(aliases[team_en])

        # 用户提供的中文别名
        if cn_names and team_en in cn_names:
            names.append(cn_names[team_en].lower())

        return names

    def _filter_by_team(self, news: list, team_names: list) -> list:
        """按队名过滤新闻"""

        filtered = []
        for item in news:
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()
            if any(name in text for name in team_names):
                filtered.append(item)
        return filtered

    def _extract_team_intel(self, team: str, news: list) -> TeamIntel:
        """从新闻中提取球队情报"""

        intel = TeamIntel(team_name=team)
        injury_pattern = re.compile('|'.join(self.injury_keywords), re.IGNORECASE)
        key_player_pattern = re.compile('|'.join(self.key_player_keywords), re.IGNORECASE)

        for item in news:
            title = item.get('title', '')
            content = item.get('content', '')

            # 伤病检测
            if injury_pattern.search(title) or injury_pattern.search(content):
                intel.injury_count += 1

                # 判断是否核心球员
                is_key = bool(key_player_pattern.search(title) or key_player_pattern.search(content))
                impact = 'high' if is_key else 'medium'

                # 提取球员名(简单启发式)
                player_name = self._extract_player_name(title, content, team)

                # 判断状态
                status = self._classify_injury_status(title, content)

                if status in ('injured', 'doubtful', 'rested'):
                    ps = PlayerStatus(
                        name=player_name,
                        status=status,
                        impact=impact,
                        detail=title
                    )
                    if is_key:
                        intel.key_players_missing.append(ps)
                elif status == 'returning':
                    ps = PlayerStatus(
                        name=player_name,
                        status='returning',
                        impact=impact,
                        detail=title
                    )
                    intel.key_players_returning.append(ps)

        # 综合影响级别
        key_missing = len(intel.key_players_missing)
        if key_missing >= 2:
            intel.impact_level = 'high'
        elif key_missing == 1:
            intel.impact_level = 'medium'
        elif intel.injury_count >= 3:
            intel.impact_level = 'medium'
        else:
            intel.impact_level = 'low'

        # 生成摘要
        parts = []
        if intel.key_players_missing:
            names = ', '.join(p.name or '未知球员' for p in intel.key_players_missing)
            parts.append(f'核心缺阵: {names}')
        if intel.key_players_returning:
            names = ', '.join(p.name or '未知球员' for p in intel.key_players_returning)
            parts.append(f'核心回归: {names}')
        if intel.injury_count:
            parts.append(f'伤病总计: {intel.injury_count}人')
        intel.news_summary = '; '.join(parts) if parts else '无重大情报'

        return intel

    def _extract_player_name(self, title: str, content: str, team: str) -> str:
        """从标题/内容中提取球员名(简单启发式)"""

        # 常见格式: "Mbappe injured" / "姆巴佩因伤缺阵"
        # 尝试提取伤病关键词前的单词
        text = f"{title} {content}"

        for kw in self.injury_keywords:
            idx = text.lower().find(kw.lower())
            if idx > 0:
                # 取关键词前1-3个词作为球员名
                before = text[:idx].strip()
                words = before.split()
                if words:
                    candidate = words[-1].strip(' ,.，。')
                    if len(candidate) > 2:  # 太短不像名字
                        return candidate
        return ''

    def _classify_injury_status(self, title: str, content: str) -> str:
        """分类伤病状态"""

        text = f"{title} {content}".lower()

        if any(kw in text for kw in ['returning', 'returns', 'back', '回归', '复出', '伤愈']):
            return 'returning'
        if any(kw in text for kw in ['ruled out', 'misses out', 'not in squad', '缺阵', '缺席', '无法出战']):
            return 'injured'
        if any(kw in text for kw in ['rested', '轮休', '休息']):
            return 'rested'
        if any(kw in text for kw in ['doubtful', 'doubt', '出战成疑', '不确定']):
            return 'doubtful'

        return 'injured'  # 默认归为伤病
