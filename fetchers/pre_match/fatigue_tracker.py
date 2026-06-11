"""球员疲劳追踪器 — 赛季负荷+球星缺阵"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from fetchers.pre_match.config import FATIGUE_THRESHOLDS


@dataclass
class PlayerFatigue:
    """球员疲劳状态"""
    name: str
    season_games: int  # 赛季出场数
    fatigue_level: str  # 'critical' / 'high' / 'moderate' / 'low'
    likely_rest: bool  # 大概率轮休
    reason: str  # 理由
    cl_final: bool = False  # 刚打完欧冠决赛
    nt_tournament: bool = False  # 国家队大赛


@dataclass
class FatigueReport:
    """球队疲劳报告"""
    team: str
    team_fatigue_level: str = 'low'  # 'critical' / 'high' / 'moderate' / 'low'
    key_players_status: list = field(default_factory=list)  # PlayerFatigue
    stars_missing: list = field(default_factory=list)  # 大概率不上场的球星
    load_diff: float = 0.0  # 主队vs客队赛季负荷差(正=主队更累)
    avg_season_games: float = 0.0
    cl_final_players: int = 0  # 欧冠决赛球员数
    wc_window: bool = False  # 是否在WC前临界窗口


class PlayerFatigueTracker:
    """球员疲劳追踪器"""

    def __init__(self):
        self.thresholds = FATIGUE_THRESHOLDS

    def track_season_load(
        self,
        team: str,
        date: str,
        opponent: Optional[str] = None,
        key_players: Optional[list] = None
    ) -> FatigueReport:
        """追踪球队赛季负荷"""

        report = FatigueReport(team=team)

        # 1. 检查是否在WC前临界窗口
        report.wc_window = self._is_wc_window(date)

        # 2. 从DB获取赛季比赛密度
        team_games = self._get_team_season_games(team, date)
        report.avg_season_games = team_games

        # 3. 获取关键球员负荷
        if key_players:
            for player_info in key_players:
                pf = self._assess_player_fatigue(player_info, date, team_games)
                report.key_players_status.append(pf)
                if pf.likely_rest:
                    report.stars_missing.append(pf.name)

        # 4. 检查欧冠决赛球员
        report.cl_final_players = self._count_cl_final_players(
            report.key_players_status
        )

        # 5. 计算球队疲劳级别
        report.team_fatigue_level = self._calculate_team_fatigue(
            team_games, report.cl_final_players, report.wc_window
        )

        # 6. 计算负荷差(需要对手数据)
        if opponent:
            opp_games = self._get_team_season_games(opponent, date)
            report.load_diff = team_games - opp_games

        return report

    def _is_wc_window(self, date: str) -> bool:
        """检查是否在世界杯前临界窗口"""

        # 2026世界杯6月11日开赛
        wc_start = datetime(2026, 6, 11)
        try:
            match_date = datetime.strptime(date, '%Y-%m-%d')
            days_before = (wc_start - match_date).days
            return 0 < days_before <= self.thresholds['wc_days_before']
        except:
            return False

    def _get_team_season_games(self, team: str, date: str) -> int:
        """从DB获取球队赛季比赛数"""

        try:
            from fetchers.storage.db import get_db
            db = get_db()
            cursor = db.cursor()

            # 赛季开始约8月1日
            try:
                match_date = datetime.strptime(date, '%Y-%m-%d')
                season_start = f"{match_date.year - 1}-08-01"
                if match_date.month >= 8:
                    season_start = f"{match_date.year}-08-01"
            except:
                season_start = '2025-08-01'

            cursor.execute("""
                SELECT COUNT(*) FROM matches
                WHERE (home_team = ? OR away_team = ?)
                AND date >= ? AND date <= ?
            """, (team, team, season_start, date))

            result = cursor.fetchone()
            return result[0] if result else 0
        except:
            # DB不可用时用启发式估算
            # 联赛38场 + 杯赛10-15场 + 欧冠13场(进决赛)
            return 0  # 返回0表示未知

    def _assess_player_fatigue(
        self,
        player_info: dict,
        date: str,
        team_games: int
    ) -> PlayerFatigue:
        """评估单个球员疲劳"""

        name = player_info.get('name', 'Unknown')
        season_games = player_info.get('season_games', team_games)
        cl_final = player_info.get('cl_final', False)
        nt_tournament = player_info.get('nt_tournament', False)

        # 疲劳等级计算
        fatigue_score = 0

        if season_games >= self.thresholds['games_critical']:
            fatigue_score += 3
        elif season_games >= self.thresholds['games_high']:
            fatigue_score += 2
        elif season_games >= self.thresholds['games_moderate']:
            fatigue_score += 1

        if cl_final:
            fatigue_score += self.thresholds['cl_final_penalty']

        if nt_tournament:
            fatigue_score += self.thresholds['nt_semi_penalty']

        # WC窗口加成
        if self._is_wc_window(date):
            fatigue_score += 1

        # 映射到级别
        if fatigue_score >= 5:
            level = 'critical'
        elif fatigue_score >= 3:
            level = 'high'
        elif fatigue_score >= 2:
            level = 'moderate'
        else:
            level = 'low'

        # 是否大概率轮休
        likely_rest = fatigue_score >= 4 or (cl_final and self._is_wc_window(date))

        # 理由
        reasons = []
        if season_games >= self.thresholds['games_high']:
            reasons.append(f'赛季{season_games}场')
        if cl_final:
            reasons.append('刚打完欧冠决赛')
        if nt_tournament:
            reasons.append('国家队大赛')
        if self._is_wc_window(date):
            reasons.append('WC前临界窗口')

        return PlayerFatigue(
            name=name,
            season_games=season_games,
            fatigue_level=level,
            likely_rest=likely_rest,
            reason=', '.join(reasons) if reasons else '正常负荷',
            cl_final=cl_final,
            nt_tournament=nt_tournament
        )

    def _count_cl_final_players(self, players: list) -> int:
        """统计欧冠决赛球员数"""
        return sum(1 for p in players if p.cl_final)

    def _calculate_team_fatigue(
        self,
        team_games: int,
        cl_final_players: int,
        wc_window: bool
    ) -> str:
        """计算球队整体疲劳级别"""

        score = 0

        if team_games >= self.thresholds['games_critical']:
            score += 3
        elif team_games >= self.thresholds['games_high']:
            score += 2
        elif team_games >= self.thresholds['games_moderate']:
            score += 1

        # 欧冠决赛球员影响
        if cl_final_players >= 3:
            score += 2
        elif cl_final_players >= 1:
            score += 1

        # WC窗口
        if wc_window:
            score += 1

        if score >= 5:
            return 'critical'
        elif score >= 3:
            return 'high'
        elif score >= 2:
            return 'moderate'
        else:
            return 'low'

    def get_fatigue_adjustment(self, report: FatigueReport) -> dict:
        """根据疲劳报告生成预测修正值"""

        adjustments = {
            'home_win_adj': 0.0,
            'draw_adj': 0.0,
            'away_win_adj': 0.0,
            'reason': ''
        }

        level_map = {
            'critical': -0.15,
            'high': -0.10,
            'moderate': -0.05,
            'low': 0.0
        }

        # 球星缺阵修正
        stars_missing_count = len(report.stars_missing)
        if stars_missing_count >= 3:
            adjustments['home_win_adj'] = -0.15
            adjustments['draw_adj'] = 0.05
            adjustments['reason'] = f'{stars_missing_count}名核心缺阵'
        elif stars_missing_count >= 1:
            adjustments['home_win_adj'] = -0.08
            adjustments['draw_adj'] = 0.03
            adjustments['reason'] = f'{stars_missing_count}名核心缺阵'

        # 整体疲劳修正
        fatigue_adj = level_map.get(report.team_fatigue_level, 0.0)
        adjustments['home_win_adj'] += fatigue_adj
        if fatigue_adj < 0:
            adjustments['draw_adj'] += abs(fatigue_adj) * 0.3

        # 负荷差修正
        if report.load_diff > 10:
            adjustments['home_win_adj'] -= 0.05
            adjustments['reason'] += f'; 负荷差{report.load_diff:.0f}场'

        return adjustments
