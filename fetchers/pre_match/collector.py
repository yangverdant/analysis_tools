"""赛前情报统一采集器

编排所有子模块:
- context_builder: 雇佣/动机/球迷/场地
- news_scanner: 伤病/阵容
- fatigue_tracker: 球员级负荷

使用:
    from fetchers.pre_match import PreMatchCollector
    collector = PreMatchCollector()
    intel = collector.collect('France', 'Ivory Coast', '2026-06-05', 'friendly')
"""

from dataclasses import dataclass, field
from typing import Optional
from fetchers.pre_match.context_builder import MatchContextBuilder, MatchContext
from fetchers.pre_match.news_scanner import PreMatchNewsScanner, PreMatchIntel
from fetchers.pre_match.fatigue_tracker import PlayerFatigueTracker, FatigueReport
from fetchers.pre_match.config import WC_HOSTS_2026


@dataclass
class PreMatchReport:
    """赛前情报完整报告"""
    home_team: str
    away_team: str
    date: str
    league: str

    # 5维度
    context: Optional[MatchContext] = None
    intel: Optional[PreMatchIntel] = None
    home_fatigue: Optional[FatigueReport] = None
    away_fatigue: Optional[FatigueReport] = None

    # 综合评估
    friendly_adjustment: dict = field(default_factory=dict)
    key_insights: list = field(default_factory=list)
    confidence: float = 0.0


class PreMatchCollector:
    """赛前情报统一采集器"""

    def __init__(self):
        self.context_builder = MatchContextBuilder()
        self.news_scanner = PreMatchNewsScanner()
        self.fatigue_tracker = PlayerFatigueTracker()

    def collect(
        self,
        home_team: str,
        away_team: str,
        date: str,
        league: str,
        venue_city: Optional[str] = None,
        recent_form: Optional[dict] = None,
        key_players_home: Optional[list] = None,
        key_players_away: Optional[list] = None,
        team_cn_names: Optional[dict] = None,
        odds: Optional[dict] = None
    ) -> PreMatchReport:
        """采集完整赛前情报"""

        report = PreMatchReport(
            home_team=home_team,
            away_team=away_team,
            date=date,
            league=league
        )

        # 1. 比赛上下文(雇佣/动机/球迷/场地)
        try:
            report.context = self.context_builder.build_context(
                home_team, away_team, date, league,
                venue_city=venue_city,
                recent_form=recent_form
            )
        except Exception as e:
            report.context = MatchContext(
                home_team=home_team, away_team=away_team,
                date=date, league=league, friendly_type='unknown'
            )

        # 2. 新闻扫描(伤病/阵容)
        try:
            report.intel = self.news_scanner.scan_match_news(
                home_team, away_team, date,
                team_cn_names=team_cn_names
            )
        except Exception:
            # 新闻源不可用时创建空情报
            from fetchers.pre_match.news_scanner import TeamIntel
            report.intel = PreMatchIntel(
                home=TeamIntel(team_name=home_team),
                away=TeamIntel(team_name=away_team),
                confidence=0.0
            )

        # 3. 疲劳追踪(球员级)
        try:
            report.home_fatigue = self.fatigue_tracker.track_season_load(
                home_team, date, opponent=away_team,
                key_players=key_players_home
            )
        except Exception:
            report.home_fatigue = FatigueReport(team=home_team)

        try:
            report.away_fatigue = self.fatigue_tracker.track_season_load(
                away_team, date, opponent=home_team,
                key_players=key_players_away
            )
        except Exception:
            report.away_fatigue = FatigueReport(team=away_team)

        # 4. 综合评估
        report.friendly_adjustment = self._calculate_friendly_adjustment(report, odds)
        report.key_insights = self._generate_insights(report)
        report.confidence = self._assess_confidence(report)

        return report

    def _calculate_friendly_adjustment(self, report: PreMatchReport, odds: Optional[dict] = None) -> dict:
        """计算友谊赛修正值"""

        adj = {
            'home_win_adj': 0.0,
            'draw_adj': 0.0,
            'away_win_adj': 0.0,
            'friendly_type': 'not_friendly'
        }

        ctx = report.context
        if not ctx or ctx.friendly_type == 'not_friendly':
            return adj

        adj['friendly_type'] = ctx.friendly_type

        # === 赔率区间分级修正(核心!) ===
        # 赔率越低(越看好主队),友谊赛偏差越大
        is_crush = False  # 碾压场景: 排名差>50 + 赔率<1.30 → 修正减半
        if odds:
            home_odds = odds.get('home', odds.get('h', 0))
            away_odds = odds.get('away', odds.get('a', 0))
            try:
                home_odds = float(home_odds)
                away_odds = float(away_odds)
            except (ValueError, TypeError):
                home_odds = away_odds = 0

            # 检测碾压场景(仅当: 排名差>50 + 赔率<1.30 + 无球迷效应 + 无球星缺阵)
            try:
                from fetchers.fifa_ranking import get_team_ranking
                hr = get_team_ranking(report.home_team)
                ar = get_team_ranking(report.away_team)
                home_rank = hr['rank'] if isinstance(hr, dict) else 999
                away_rank = ar['rank'] if isinstance(ar, dict) else 999
                rank_diff = abs(home_rank - away_rank)
                has_fan_effect = ctx.fan_effect and ctx.fan_effect.away_fan_ratio >= 0.15
                if (home_odds < 1.30 and home_rank < away_rank and rank_diff > 50 and not has_fan_effect) or \
                   (away_odds < 1.30 and away_rank < home_rank and rank_diff > 50):
                    is_crush = True
            except:
                pass

            if home_odds > 0 and not is_crush:
                if home_odds < 1.20:
                    adj['home_win_adj'] -= 0.18
                    adj['draw_adj'] += 0.12
                    adj['away_win_adj'] += 0.06
                elif home_odds < 1.40:
                    adj['home_win_adj'] -= 0.12
                    adj['draw_adj'] += 0.08
                    adj['away_win_adj'] += 0.04
                elif home_odds < 1.80:
                    adj['home_win_adj'] -= 0.06
                    adj['draw_adj'] += 0.04
                    adj['away_win_adj'] += 0.02
                elif home_odds < 2.50:
                    adj['home_win_adj'] -= 0.04
                    adj['draw_adj'] += 0.03

                # 客赔率修正: 客队赔率6-9 → 高风险翻车区
                # 客队有一定实力(IC/Algeria赔率8-9), 强队不认真就可能平局
                # 客赔率>10(Andorra/Malta) → 太弱, 强队度假也能赢, 不额外推平局
                if away_odds > 0:
                    if 6.0 <= away_odds <= 9.5:
                        # 客队有一定实力 → 额外推平局
                        adj['draw_adj'] += 0.06
                        adj['home_win_adj'] -= 0.04
                    elif 4.0 <= away_odds < 6.0:
                        # 客队实力更强 → 更容易翻车
                        adj['draw_adj'] += 0.04
                        adj['home_win_adj'] -= 0.02

            # 客胜赔率修正(友谊赛客胜同样被高估)
            if away_odds > 0 and not is_crush:
                if away_odds < 1.80:
                    adj['away_win_adj'] -= 0.04
                    adj['draw_adj'] += 0.03
                elif away_odds < 2.50:
                    adj['away_win_adj'] -= 0.02
                    adj['draw_adj'] += 0.01

            # 碾压场景: 小幅修正(强队仍然大概率赢)
            if is_crush and home_odds > 0 and home_odds < 1.30:
                adj['home_win_adj'] -= 0.05
                adj['draw_adj'] += 0.03

        # 友谊赛基础修正: 整体向平局偏移
        if ctx.friendly_type == 'wc_warmup':
            adj['draw_adj'] += 0.05
        elif ctx.friendly_type == 'post_season':
            adj['draw_adj'] += 0.10
            adj['home_win_adj'] -= 0.08
        elif ctx.friendly_type == 'mid_season':
            adj['draw_adj'] += 0.08
            adj['home_win_adj'] -= 0.05

        # === WC vs WC规则 ===
        # 两支WC级别球队友谊赛 → 平局概率提升
        # 但仅在赔率偏斜<20%时(即双方实力接近)
        wc_teams = set(WC_HOSTS_2026) | {
            'France', 'Germany', 'Spain', 'England', 'Italy', 'Portugal',
            'Netherlands', 'Belgium', 'Croatia', 'Brazil', 'Argentina',
            'Uruguay', 'Colombia', 'Denmark', 'Switzerland', 'Austria',
            'Serbia', 'Poland', 'Sweden', 'Ukraine', 'Turkey', 'Morocco',
            'Japan', 'South Korea', 'United States', 'Mexico', 'Canada',
        }
        if report.home_team in wc_teams and report.away_team in wc_teams and not is_crush:
            # 检查赔率偏斜: 主/客赔率比值 < 1.3 才算接近
            if odds:
                try:
                    ho = float(odds.get('home', odds.get('h', 0)))
                    ao = float(odds.get('away', odds.get('a', 0)))
                    if ho > 0 and ao > 0:
                        skew = max(ho, ao) / min(ho, ao)
                        if skew < 1.3:
                            # 双方实力接近 → 大幅推平局
                            adj['draw_adj'] += 0.12
                            adj['home_win_adj'] -= 0.06
                            adj['away_win_adj'] -= 0.06
                        elif skew < 1.6:
                            # 有差距但不大 → 小幅推平局
                            adj['draw_adj'] += 0.05
                            adj['home_win_adj'] -= 0.02
                            adj['away_win_adj'] -= 0.03
                        # skew >= 1.6: 差距大,不推平局
                except:
                    pass

        # === 雇佣关系修正 ===
        if ctx.employer:
            if ctx.employer.employer == 'home':
                # 主队是雇主: 被雇方(客队)不拼命
                adj['away_win_adj'] -= 0.05
                # 雇主动机决定修正方向
                if ctx.home_motivation and ctx.home_motivation.level in ['must_win', 'high']:
                    # 雇主认真打+被雇方不拼命 → 主胜上升
                    adj['home_win_adj'] += 0.05
                elif ctx.home_motivation and ctx.home_motivation.level == 'medium':
                    # 雇主试阵 → 小幅推主胜
                    adj['home_win_adj'] += 0.02
                else:
                    # 雇主也不认真 → 推平局
                    adj['home_win_adj'] -= 0.03
                    adj['draw_adj'] += 0.05
            elif ctx.employer.employer == 'away':
                # 客队是雇主: 被雇方(主队)不拼命
                adj['home_win_adj'] -= 0.05
                if ctx.away_motivation and ctx.away_motivation.level in ['must_win', 'high']:
                    adj['away_win_adj'] += 0.05
                elif ctx.away_motivation and ctx.away_motivation.level == 'medium':
                    adj['away_win_adj'] += 0.02
                else:
                    adj['away_win_adj'] -= 0.03
                    adj['draw_adj'] += 0.05

        # 球迷效应修正
        if ctx.fan_effect:
            if ctx.fan_effect.home_advantage_level in ['weakened', 'reversed']:
                adj['home_win_adj'] -= 0.10
                adj['away_win_adj'] += 0.06
                adj['draw_adj'] += 0.04
                if ctx.fan_effect.home_advantage_level == 'reversed':
                    adj['home_win_adj'] -= 0.08
                    adj['away_win_adj'] += 0.05

        # 动机差异修正
        if ctx.home_motivation and ctx.away_motivation:
            level_score = {'must_win': 3, 'high': 2, 'medium': 1, 'low': 0, 'exhibition': -1}
            home_m = level_score.get(ctx.home_motivation.level, 1)
            away_m = level_score.get(ctx.away_motivation.level, 1)
            diff = home_m - away_m

            if diff >= 2:  # 主队动机远强于客队
                adj['home_win_adj'] += 0.08
                adj['away_win_adj'] -= 0.05
            elif diff <= -2:  # 客队动机远强于主队
                adj['home_win_adj'] -= 0.08
                adj['away_win_adj'] += 0.05
            elif diff == 0 and home_m <= 1:  # 双方都不重视
                adj['draw_adj'] += 0.08

        # 场地修正
        if ctx.venue_special and ctx.venue_special.altitude_effect in ['extreme', 'high']:
            if ctx.venue_special.is_home_familiar:
                adj['home_win_adj'] += 0.05
                adj['away_win_adj'] -= 0.05
            else:
                # 双方都不熟悉高原,减少主胜
                adj['home_win_adj'] -= 0.03
                adj['draw_adj'] += 0.03

        # 伤病修正
        if report.intel:
            if report.intel.home.impact_level == 'high':
                adj['home_win_adj'] -= 0.10
                adj['draw_adj'] += 0.05
            elif report.intel.home.impact_level == 'medium':
                adj['home_win_adj'] -= 0.05

            if report.intel.away.impact_level == 'high':
                adj['away_win_adj'] -= 0.10
                adj['draw_adj'] += 0.05
            elif report.intel.away.impact_level == 'medium':
                adj['away_win_adj'] -= 0.05

        # 疲劳修正
        if report.home_fatigue:
            fatigue_adj = self.fatigue_tracker.get_fatigue_adjustment(report.home_fatigue)
            adj['home_win_adj'] += fatigue_adj.get('home_win_adj', 0.0)
            adj['draw_adj'] += fatigue_adj.get('draw_adj', 0.0)

        if report.away_fatigue:
            fatigue_adj = self.fatigue_tracker.get_fatigue_adjustment(report.away_fatigue)
            adj['away_win_adj'] += fatigue_adj.get('home_win_adj', 0.0)
            adj['draw_adj'] += fatigue_adj.get('draw_adj', 0.0)

        return adj

    def _generate_insights(self, report: PreMatchReport) -> list:
        """生成关键洞察"""

        insights = []
        ctx = report.context

        if not ctx:
            return insights

        # 雇佣关系洞察
        if ctx.employer and ctx.employer.confidence >= 0.7:
            if ctx.employer.employer == 'home':
                insights.append(
                    f"雇佣关系: {report.home_team}花钱请{report.away_team}陪练 — "
                    f"被雇方不会拼命({ctx.employer.reason})"
                )
            elif ctx.employer.employer == 'away':
                insights.append(
                    f"雇佣关系: {report.away_team}花钱请{report.home_team}陪练 — "
                    f"被雇方不会拼命({ctx.employer.reason})"
                )

        # 球迷效应洞察
        if ctx.fan_effect and ctx.fan_effect.away_fan_ratio >= 0.15:
            insights.append(
                f"球迷效应: {ctx.fan_effect.reason} — "
                f"主场优势{'严重削弱' if ctx.fan_effect.away_fan_ratio >= 0.25 else '被削弱'}"
            )

        # 动机不对称洞察
        if ctx.home_motivation and ctx.away_motivation:
            if ctx.home_motivation.level in ['must_win', 'high'] and ctx.away_motivation.level in ['low', 'exhibition']:
                insights.append(
                    f"动机不对称: {report.home_team}必须认真打({ctx.home_motivation.reason}) vs "
                    f"{report.away_team}无所谓({ctx.away_motivation.reason})"
                )
            elif ctx.away_motivation.level in ['must_win', 'high'] and ctx.home_motivation.level in ['low', 'exhibition']:
                insights.append(
                    f"动机不对称: {report.away_team}必须认真打({ctx.away_motivation.reason}) vs "
                    f"{report.home_team}无所谓({ctx.home_motivation.reason})"
                )

        # 高原洞察
        if ctx.venue_special and ctx.venue_special.altitude_effect in ['extreme', 'high']:
            familiar = '主队适应' if ctx.venue_special.is_home_familiar else '双方不适应'
            insights.append(
                f"高原效应: 海拔{ctx.venue_special.altitude_m}m, {familiar}"
            )

        # 伤病洞察
        if report.intel:
            if report.intel.home.impact_level == 'high':
                names = ', '.join(p.name or '?' for p in report.intel.home.key_players_missing[:3])
                insights.append(f"主队伤病严重: {names}缺阵")
            if report.intel.away.impact_level == 'high':
                names = ', '.join(p.name or '?' for p in report.intel.away.key_players_missing[:3])
                insights.append(f"客队伤病严重: {names}缺阵")

        # 疲劳洞察
        if report.home_fatigue and report.home_fatigue.stars_missing:
            names = ', '.join(report.home_fatigue.stars_missing[:3])
            insights.append(f"主队疲劳: {names}大概率轮休")
        if report.away_fatigue and report.away_fatigue.stars_missing:
            names = ', '.join(report.away_fatigue.stars_missing[:3])
            insights.append(f"客队疲劳: {names}大概率轮休")

        return insights

    def _assess_confidence(self, report: PreMatchReport) -> float:
        """评估整体情报可信度"""

        score = 0.0

        # 上下文推断有依据
        if report.context and report.context.employer:
            score += report.context.employer.confidence * 0.3

        # 新闻源有数据
        if report.intel:
            score += report.intel.confidence * 0.3

        # 疲劳有数据
        if report.home_fatigue and report.home_fatigue.avg_season_games > 0:
            score += 0.2
        if report.away_fatigue and report.away_fatigue.avg_season_games > 0:
            score += 0.2

        return min(1.0, score)

    def format_report(self, report: PreMatchReport) -> str:
        """格式化输出报告"""

        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"赛前情报: {report.home_team} vs {report.away_team} ({report.date})")
        lines.append(f"赛事: {report.league}")
        lines.append(f"{'='*60}")

        if report.context:
            lines.append(f"\n友谊赛类型: {report.context.friendly_type}")
            lines.append(f"净主场优势: {report.context.home_advantage_net:+.2f}")

        if report.key_insights:
            lines.append(f"\n关键洞察:")
            for i, insight in enumerate(report.key_insights, 1):
                lines.append(f"  {i}. {insight}")

        adj = report.friendly_adjustment
        if adj.get('friendly_type') != 'not_friendly':
            lines.append(f"\n友谊赛修正:")
            lines.append(f"  主胜: {adj['home_win_adj']:+.2f}")
            lines.append(f"  平局: {adj['draw_adj']:+.2f}")
            lines.append(f"  客胜: {adj['away_win_adj']:+.2f}")

        lines.append(f"\n情报可信度: {report.confidence:.0%}")
        lines.append(f"{'='*60}")

        return '\n'.join(lines)
