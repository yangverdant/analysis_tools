"""
定时采集调度服务
7x24小时持续采集各类数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Callable
import schedule

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'scheduled_collector.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ScheduledCollector:
    """定时采集调度器"""

    def __init__(self):
        self.tasks = {}
        self.running = False
        self._register_tasks()

    def _register_tasks(self):
        """注册采集任务"""

        # 每分钟任务
        self.tasks['every_minute'] = {
            'interval': 1,
            'unit': 'minutes',
            'tasks': [
                ('live_odds', self._collect_live_odds),
                ('live_scores', self._collect_live_scores),
            ]
        }

        # 每10分钟任务
        self.tasks['every_10_minutes'] = {
            'interval': 10,
            'unit': 'minutes',
            'tasks': [
                ('injury_update', self._collect_injuries),
            ]
        }

        # 每小时任务
        self.tasks['every_hour'] = {
            'interval': 1,
            'unit': 'hours',
            'tasks': [
                ('news_aggregate', self._collect_news),
                ('social_monitor', self._monitor_social),
            ]
        }

        # 每6小时任务
        self.tasks['every_6_hours'] = {
            'interval': 6,
            'unit': 'hours',
            'tasks': [
                ('team_value', self._update_team_values),
                ('form_update', self._update_team_form),
            ]
        }

        # 每天任务
        self.tasks['every_day'] = {
            'interval': 1,
            'unit': 'days',
            'time': '06:00',
            'tasks': [
                ('fifa_ranking', self._update_fifa_rankings),
                ('h2h_update', self._update_h2h_records),
                ('chemistry_update', self._update_chemistry),
            ]
        }

        # 每周任务
        self.tasks['every_week'] = {
            'interval': 1,
            'unit': 'weeks',
            'tasks': [
                ('db_backup', self._backup_database),
                ('cleanup_old_data', self._cleanup_old_data),
            ]
        }

    # ==================== 采集任务实现 ====================

    def _collect_live_odds(self):
        """采集实时赔率"""
        try:
            from fetchers.odds_feed_api.oddsfe_realtime_refresh import main as refresh_odds
            logger.info("开始采集实时赔率...")
            # refresh_odds()
            logger.info("实时赔率采集完成")
        except Exception as e:
            logger.error(f"实时赔率采集失败: {e}")

    def _collect_live_scores(self):
        """采集实时比分"""
        try:
            from fetchers.apifootball.get_data import get_livescores
            logger.info("开始采集实时比分...")
            scores = get_livescores()
            logger.info(f"实时比分采集完成: {len(scores)}场")
        except Exception as e:
            logger.error(f"实时比分采集失败: {e}")

    def _collect_injuries(self):
        """采集伤病信息"""
        try:
            from backend.scripts.national_team_collector import NationalTeamCollector
            logger.info("开始采集伤病信息...")
            collector = NationalTeamCollector()
            # 从apifootball获取伤病
            # injuries = ...
            # collector.save_injuries_from_apifootball(injuries)
            logger.info("伤病信息采集完成")
        except Exception as e:
            logger.error(f"伤病信息采集失败: {e}")

    def _collect_news(self):
        """采集新闻"""
        try:
            from backend.scripts.news_aggregator import NewsAggregator
            logger.info("开始采集新闻...")
            aggregator = NewsAggregator()
            count = aggregator.collect_all()
            logger.info(f"新闻采集完成: {count}条")
        except Exception as e:
            logger.error(f"新闻采集失败: {e}")

    def _monitor_social(self):
        """监控社交媒体"""
        try:
            logger.info("开始社交媒体监控...")
            # TODO: 实现社交媒体监控
            logger.info("社交媒体监控完成")
        except Exception as e:
            logger.error(f"社交媒体监控失败: {e}")

    def _update_team_values(self):
        """更新球队身价"""
        try:
            logger.info("开始更新球队身价...")
            # TODO: 从transfermarkt获取身价
            logger.info("球队身价更新完成")
        except Exception as e:
            logger.error(f"球队身价更新失败: {e}")

    def _update_team_form(self):
        """更新球队form"""
        try:
            from backend.scripts.national_team_collector import NationalTeamCollector
            logger.info("开始更新球队form...")
            collector = NationalTeamCollector()
            # TODO: 更新form数据
            logger.info("球队form更新完成")
        except Exception as e:
            logger.error(f"球队form更新失败: {e}")

    def _update_fifa_rankings(self):
        """更新FIFA排名"""
        try:
            from backend.scripts.national_team_collector import NationalTeamCollector
            logger.info("开始更新FIFA排名...")
            collector = NationalTeamCollector()
            collector.import_fifa_rankings()
            logger.info("FIFA排名更新完成")
        except Exception as e:
            logger.error(f"FIFA排名更新失败: {e}")

    def _update_h2h_records(self):
        """更新H2H记录"""
        try:
            logger.info("开始更新H2H记录...")
            # TODO: 更新H2H
            logger.info("H2H记录更新完成")
        except Exception as e:
            logger.error(f"H2H记录更新失败: {e}")

    def _update_chemistry(self):
        """更新阵容磨合度"""
        try:
            from backend.scripts.chemistry_calculator import ChemistryCalculator
            logger.info("开始更新阵容磨合度...")
            # TODO: 更新磨合度
            logger.info("阵容磨合度更新完成")
        except Exception as e:
            logger.error(f"阵容磨合度更新失败: {e}")

    def _backup_database(self):
        """备份数据库"""
        try:
            import shutil
            logger.info("开始备份数据库...")
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                   'data', 'football_v2.db')
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            backup_root = os.environ.get(
                'FOOTBALL_BACKUP_DIR',
                os.path.abspath(os.path.join(project_root, '..', 'football_backups'))
            )
            backup_path = os.path.join(
                backup_root,
                'scheduled_db',
                f'football_v2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
            )

            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy(db_path, backup_path)
            logger.info(f"数据库备份完成: {backup_path}")
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")

    def _cleanup_old_data(self):
        """清理过期数据"""
        try:
            logger.info("开始清理过期数据...")
            # TODO: 清理90天前的详细数据
            logger.info("过期数据清理完成")
        except Exception as e:
            logger.error(f"过期数据清理失败: {e}")

    # ==================== 调度器 ====================

    def setup_schedule(self):
        """设置调度"""
        schedule.clear()

        # 每分钟
        for name, func in self.tasks['every_minute']['tasks']:
            schedule.every(1).minutes.do(func).tag(name)
            logger.info(f"注册任务: {name} (每分钟)")

        # 每10分钟
        for name, func in self.tasks['every_10_minutes']['tasks']:
            schedule.every(10).minutes.do(func).tag(name)
            logger.info(f"注册任务: {name} (每10分钟)")

        # 每小时
        for name, func in self.tasks['every_hour']['tasks']:
            schedule.every(1).hours.do(func).tag(name)
            logger.info(f"注册任务: {name} (每小时)")

        # 每6小时
        for name, func in self.tasks['every_6_hours']['tasks']:
            schedule.every(6).hours.do(func).tag(name)
            logger.info(f"注册任务: {name} (每6小时)")

        # 每天
        for name, func in self.tasks['every_day']['tasks']:
            schedule.every().day.at('06:00').do(func).tag(name)
            logger.info(f"注册任务: {name} (每天06:00)")

        # 每周
        for name, func in self.tasks['every_week']['tasks']:
            schedule.every().monday.at('03:00').do(func).tag(name)
            logger.info(f"注册任务: {name} (每周一03:00)")

    def run(self):
        """运行调度器"""
        logger.info("=" * 60)
        logger.info("定时采集调度服务启动")
        logger.info("=" * 60)

        self.setup_schedule()
        self.running = True

        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except KeyboardInterrupt:
                logger.info("收到停止信号，正在退出...")
                self.running = False
            except Exception as e:
                logger.error(f"调度器异常: {e}")
                time.sleep(60)

    def stop(self):
        """停止调度器"""
        self.running = False
        schedule.clear()

    def run_once(self, task_name: str):
        """执行单个任务"""
        for task_group in self.tasks.values():
            for name, func in task_group['tasks']:
                if name == task_name:
                    logger.info(f"执行任务: {task_name}")
                    try:
                        func()
                        logger.info(f"任务完成: {task_name}")
                    except Exception as e:
                        logger.error(f"任务失败 {task_name}: {e}")
                    return
        logger.warning(f"任务不存在: {task_name}")

    def list_tasks(self):
        """列出所有任务"""
        print("\n已注册的采集任务:")
        print("-" * 50)

        for group_name, group in self.tasks.items():
            print(f"\n[{group_name}]")
            for name, _ in group['tasks']:
                print(f"  - {name}")

        print("-" * 50)


class WorldCupMatchCollector:
    """世界杯比赛专项采集器"""

    def __init__(self):
        self.collector = None

    def collect_match_intelligence(self, home_team: str, away_team: str,
                                   match_date: str, match_time: str = None):
        """
        采集单场比赛的完整情报
        """
        from backend.scripts.national_team_collector import NationalTeamCollector
        from backend.scripts.news_aggregator import NewsAggregator
        from backend.scripts.chemistry_calculator import ChemistryCalculator

        logger.info(f"采集比赛情报: {home_team} vs {away_team} ({match_date})")

        intelligence = {
            'match': {
                'home_team': home_team,
                'away_team': away_team,
                'date': match_date,
                'time': match_time
            },
            'fifa_ranking': {},
            'team_value': {},
            'h2h': [],
            'form': {},
            'injuries': [],
            'news': [],
            'chemistry': {}
        }

        # 1. FIFA排名
        # TODO: 从数据库查询

        # 2. 球队身价
        # TODO: 从数据库查询

        # 3. H2H记录
        # TODO: 从数据库查询

        # 4. 近期form
        # TODO: 从数据库查询

        # 5. 伤病信息
        # TODO: 从数据库查询

        # 6. 相关新闻
        aggregator = NewsAggregator()
        home_news = aggregator.get_team_news(home_team, days=7)
        away_news = aggregator.get_team_news(away_team, days=7)
        intelligence['news'] = {
            'home': home_news[:10],
            'away': away_news[:10]
        }

        # 7. 舆论情感
        home_sentiment = aggregator.get_team_sentiment(home_team)
        away_sentiment = aggregator.get_team_sentiment(away_team)
        intelligence['sentiment'] = {
            'home': home_sentiment,
            'away': away_sentiment
        }

        logger.info(f"比赛情报采集完成")
        return intelligence


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='定时采集调度服务')
    parser.add_argument('--run', action='store_true', help='启动调度服务')
    parser.add_argument('--list', action='store_true', help='列出所有任务')
    parser.add_argument('--once', type=str, help='执行单个任务')
    parser.add_argument('--match', type=str, help='采集单场比赛情报 (格式: 主队,客队,日期)')

    args = parser.parse_args()

    service = ScheduledCollector()

    if args.run:
        service.run()

    if args.list:
        service.list_tasks()

    if args.once:
        service.run_once(args.once)

    if args.match:
        parts = args.match.split(',')
        if len(parts) >= 3:
            wc = WorldCupMatchCollector()
            intel = wc.collect_match_intelligence(parts[0], parts[1], parts[2])
            print(json.dumps(intel, ensure_ascii=False, indent=2, default=str))

    if not any([args.run, args.list, args.once, args.match]):
        print("定时采集调度服务")
        print("用法:")
        print("  python scheduled_integrated_collector.py --run           # 启动服务")
        print("  python scheduled_integrated_collector.py --list          # 列出任务")
        print("  python scheduled_integrated_collector.py --once news     # 执行单个任务")
        print("  python scheduled_integrated_collector.py --match 'Argentina,France,2026-06-15'")
