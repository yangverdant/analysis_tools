"""
定时任务 - 自动更新球队动态数据

功能:
1. 每日更新新闻资讯
2. 每日更新伤病名单
3. 比赛前更新阵容预测
4. 更新球员状态

使用:
    python scheduled_crawler.py [--type news|injury|lineup|all]
"""

import sys
import os
import argparse
from datetime import datetime

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from team_news_crawler import TeamNewsCrawler
from comprehensive_news_crawler import ComprehensiveNewsCrawler
from prematch_crawler import PreMatchCrawler


def run_news_crawler(db_path: str):
    """运行新闻爬虫"""
    print("\n" + "=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 新闻爬虫启动")
    print("=" * 60)

    crawler = TeamNewsCrawler(db_path)
    news = crawler.crawl_zhibo8_news()

    if news:
        saved = crawler.save_news_to_db(news)
        print(f"保存 {saved} 条新闻")
        return saved
    return 0


def run_injury_crawler(db_path: str):
    """运行伤病爬虫"""
    print("\n" + "=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 伤病爬虫启动")
    print("=" * 60)

    crawler = PreMatchCrawler(db_path)

    total_saved = 0

    # 英超伤病
    print("\n[1] 英超伤病名单...")
    pl_injuries = crawler.crawl_premier_league_injuries()
    if pl_injuries:
        saved = crawler.save_injuries_to_db(pl_injuries)
        print(f"保存 {saved} 条英超伤病信息")
        total_saved += saved

    # 西甲伤病
    print("\n[2] 西甲伤病名单...")
    laliga_injuries = crawler.crawl_laliga_injuries()
    if laliga_injuries:
        saved = crawler.save_injuries_to_db(laliga_injuries)
        print(f"保存 {saved} 条西甲伤病信息")
        total_saved += saved

    return total_saved


def run_lineup_crawler(db_path: str):
    """运行阵容预测爬虫"""
    print("\n" + "=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 阵容预测爬虫启动")
    print("=" * 60)

    crawler = PreMatchCrawler(db_path)

    # 今日比赛
    print("\n[1] 今日比赛列表...")
    matches = crawler.crawl_zhibo8_today_matches()
    print(f"获取 {len(matches)} 场比赛")

    # 阵容预测
    print("\n[2] 阵容预测...")
    lineups = crawler.crawl_188bifen_lineups()
    if lineups:
        saved = crawler.save_lineups_to_db(lineups)
        print(f"保存 {saved} 场阵容预测")
        return saved

    return 0


def run_all_crawlers(db_path: str):
    """运行所有爬虫"""
    print("\n" + "=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 全部爬虫启动")
    print("=" * 60)

    total = 0

    # 1. 新闻
    total += run_news_crawler(db_path)

    # 2. 伤病
    total += run_injury_crawler(db_path)

    # 3. 阵容
    total += run_lineup_crawler(db_path)

    print(f"\n总计保存 {total} 条数据")
    return total


def main():
    parser = argparse.ArgumentParser(description='球队动态数据爬虫')
    parser.add_argument('--type', choices=['news', 'injury', 'lineup', 'all'],
                       default='all', help='爬虫类型')
    parser.add_argument('--db', default=r'd:\football_tools\data\football_v2.db',
                       help='数据库路径')

    args = parser.parse_args()

    db_path = args.db

    if args.type == 'news':
        run_news_crawler(db_path)
    elif args.type == 'injury':
        run_injury_crawler(db_path)
    elif args.type == 'lineup':
        run_lineup_crawler(db_path)
    else:
        run_all_crawlers(db_path)


if __name__ == "__main__":
    main()
