"""
体彩官网爬虫

数据源: webapi.sporttery.cn
- 比赛列表: /gateway/jc/football/getMatchCalculatorV1.qry
- 开奖结果: /gateway/jc/football/getMatchResultV1.qry

注意: 需要逆向分析API接口
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

logger = logging.getLogger(__name__)


class CrawlerStatus(str, Enum):
    """爬虫状态"""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class CrawlerResult:
    """爬虫结果"""
    success: bool
    data: List[Any] = field(default_factory=list)
    error: Optional[str] = None
    count: int = 0
    duration: float = 0.0


class LotteryCrawler:
    """
    体彩官网爬虫

    使用方式:
        crawler = LotteryCrawler()
        result = await crawler.crawl_matches(date.today())
        if result.success:
            matches = result.data
    """

    BASE_URL = "https://webapi.sporttery.cn"

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.status = CrawlerStatus.IDLE
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0

    @property
    def name(self) -> str:
        return "lottery_official"

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self._get_headers()
            )
        return self._session

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.sporttery.cn/',
            'Origin': 'https://www.sporttery.cn',
        }

    def _rate_limit(self, interval: float = 3.0):
        """请求限流"""
        import time
        elapsed = time.time() - self._last_request_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_time = time.time()

    async def _request(
        self,
        url: str,
        method: str = 'GET',
        params: Dict = None,
        data: Dict = None
    ) -> str:
        """发送请求"""
        session = await self._get_session()

        try:
            self._rate_limit()

            if method == 'GET':
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    return await response.text()
            else:
                async with session.post(url, params=params, data=data) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    return await response.text()
        except Exception as e:
            raise Exception(f"Request failed: {e}")

    async def crawl_matches(
        self,
        match_date: date = None,
        play_type: str = None
    ) -> CrawlerResult:
        """
        爬取开售比赛

        Args:
            match_date: 比赛日期，默认今天
            play_type: 玩法类型 (spf/bf/bqc)

        Returns:
            CrawlerResult: 爬取结果
        """
        if match_date is None:
            match_date = date.today()

        self.status = CrawlerStatus.RUNNING
        start_time = datetime.now()

        try:
            # 构建请求参数
            params = {
                'sellStatus': 'on',
                'date': match_date.strftime('%Y-%m-%d')
            }

            # 发送请求
            url = f"{self.BASE_URL}/gateway/jc/football/getMatchCalculatorV1.qry"
            logger.info(f"Crawling matches from: {url}")

            response = await self._request(url, params=params)

            # 解析响应
            matches = self.parse_matches(response)

            duration = (datetime.now() - start_time).total_seconds()
            self.status = CrawlerStatus.SUCCESS

            logger.info(f"Crawled {len(matches)} matches in {duration:.2f}s")

            return CrawlerResult(
                success=True,
                data=matches,
                count=len(matches),
                duration=duration
            )

        except Exception as e:
            self.status = CrawlerStatus.ERROR
            logger.error(f"Crawl matches failed: {e}")
            return CrawlerResult(
                success=False,
                data=[],
                error=str(e)
            )

    async def crawl_odds(
        self,
        lottery_match_id: str,
        play_type: str = 'spf'
    ) -> CrawlerResult:
        """
        爬取赔率

        Args:
            lottery_match_id: 体彩比赛ID
            play_type: 玩法类型
        """
        try:
            params = {
                'matchId': lottery_match_id,
                'playType': play_type
            }

            url = f"{self.BASE_URL}/gateway/jc/football/getOddsV1.qry"
            response = await self._request(url, params=params)

            odds = self.parse_odds(response, play_type)

            return CrawlerResult(
                success=True,
                data=odds,
                count=len(odds)
            )

        except Exception as e:
            logger.error(f"Crawl odds failed: {e}")
            return CrawlerResult(
                success=False,
                data=[],
                error=str(e)
            )

    async def crawl_results(
        self,
        match_date: date = None
    ) -> CrawlerResult:
        """
        爬取开奖结果

        Args:
            match_date: 比赛日期，默认今天
        """
        if match_date is None:
            match_date = date.today()

        try:
            params = {
                'date': match_date.strftime('%Y-%m-%d')
            }

            url = f"{self.BASE_URL}/gateway/jc/football/getMatchResultV1.qry"
            response = await self._request(url, params=params)

            results = self.parse_results(response)

            return CrawlerResult(
                success=True,
                data=results,
                count=len(results)
            )

        except Exception as e:
            logger.error(f"Crawl results failed: {e}")
            return CrawlerResult(
                success=False,
                data=[],
                error=str(e)
            )

    def parse_matches(self, response: str) -> List[Dict]:
        """
        解析比赛列表

        实际数据结构:
        {
            "success": true,
            "value": {
                "matchInfoList": [
                    {
                        "businessDate": "2026-05-24",
                        "subMatchList": [
                            {
                                "matchNum": "7001",
                                "homeTeamAllName": "水户蜀葵",
                                "awayTeamAllName": "川崎前锋",
                                "leagueAbbName": "日职",
                                "matchTime": "13:00:00",
                                "handicapLine": 0,
                                "oddsData": {
                                    "spf": {"h": "2.15", "d": "3.20", "a": "3.05"},
                                    "rqspf": {"h": "1.85", "d": "3.50", "a": "4.20"}
                                }
                            }
                        ]
                    }
                ]
            }
        }
        """
        matches = []

        try:
            data = json.loads(response)

            # 检查success状态
            if not data.get('success'):
                logger.warning("API returned success=false")
                return matches

            value = data.get('value', {})
            if not value:
                logger.warning("No value in response")
                return matches

            # 获取matchInfoList
            match_info_list = value.get('matchInfoList', [])

            for date_info in match_info_list:
                business_date = date_info.get('businessDate', '')
                sub_matches = date_info.get('subMatchList', [])

                for item in sub_matches:
                    # 构建比赛ID
                    match_num = item.get('matchNum', '')
                    lottery_match_id = f"{business_date.replace('-', '')}{match_num}"

                    match = {
                        'lottery_match_id': lottery_match_id,
                        'match_num': match_num,
                        'home_team_cn': item.get('homeTeamAllName') or item.get('homeTeamAbbName', ''),
                        'away_team_cn': item.get('awayTeamAllName') or item.get('awayTeamAbbName', ''),
                        'league_name_cn': item.get('leagueAbbName') or item.get('leagueName', ''),
                        'match_date': business_date,
                        'match_time': item.get('matchTime', '').split('.')[0] if item.get('matchTime') else '',
                        'beijing_time': item.get('beijingTime', ''),
                        'sell_status': 'selling' if item.get('sellStatus') == 'on' else 'selling',  # 默认在售
                        'sell_end_time': item.get('sellEndTime', ''),
                        'play_types': self._parse_play_types(item),
                        'handicap_line': float(item.get('handicapLine', 0) or 0),
                        'home_team_id': item.get('homeTeamId'),
                        'away_team_id': item.get('awayTeamId'),
                        'odds_data': self._extract_odds(item)
                    }
                    matches.append(match)

            logger.info(f"Parsed {len(matches)} matches")

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Parse error: {e}")

        return matches

    def _extract_odds(self, item: Dict) -> Dict:
        """提取赔率数据

        新API格式(2026.06): 独立字段 had/hhad/crs/hafu/ttg
        旧API格式: oddsData嵌套对象(保留兼容)
        """
        result = {}

        # 新格式: had = SPF
        had = item.get('had', {})
        if had:
            result['spf'] = {
                '3': float(had.get('h', 0) or 0),
                '1': float(had.get('d', 0) or 0),
                '0': float(had.get('a', 0) or 0)
            }

        # 新格式: hhad = RQSPF (让球胜平负)
        hhad = item.get('hhad', {})
        if hhad:
            result['rqspf'] = {
                '3': float(hhad.get('h', 0) or 0),
                '1': float(hhad.get('d', 0) or 0),
                '0': float(hhad.get('a', 0) or 0),
                'goal_line': hhad.get('goalLine', ''),
            }

        # 新格式: crs = BF (比分)
        crs = item.get('crs', {})
        if crs:
            result['bf'] = {k: v for k, v in crs.items()
                           if not k.endswith('f') and k not in ('goalLine', 'goalLineValue', 'updateDate', 'updateTime')}

        # 新格式: hafu = BQC (半全场)
        hafu = item.get('hafu', {})
        if hafu:
            result['bqc'] = {k: v for k, v in hafu.items()
                            if not k.endswith('f') and k not in ('goalLine', 'goalLineValue', 'updateDate', 'updateTime', 'id')}

        # 新格式: ttg = 总进球
        ttg = item.get('ttg', {})
        if ttg:
            result['ttg'] = {k: v for k, v in ttg.items()
                            if not k.endswith('f') and k not in ('goalLine', 'goalLineValue', 'updateDate', 'updateTime')}

        # 旧格式兼容: oddsData嵌套
        odds_data = item.get('oddsData', {})
        if odds_data and not result:
            spf = odds_data.get('spf', {})
            if spf:
                result['spf'] = {
                    '3': float(spf.get('h', 0) or 0),
                    '1': float(spf.get('d', 0) or 0),
                    '0': float(spf.get('a', 0) or 0)
                }
            rqspf = odds_data.get('rqspf', {})
            if rqspf:
                result['rqspf'] = {
                    '3': float(rqspf.get('h', 0) or 0),
                    '1': float(rqspf.get('d', 0) or 0),
                    '0': float(rqspf.get('a', 0) or 0)
                }
            bf = odds_data.get('bf', {})
            if bf:
                result['bf'] = bf
            bqc = odds_data.get('bqc', {})
            if bqc:
                result['bqc'] = bqc

        return result

    def parse_odds(self, response: str, play_type: str) -> List[Dict]:
        """解析赔率"""
        odds_list = []

        try:
            data = json.loads(response)
            odds_data = data.get('value', {}).get('oddsInfo', [])

            for item in odds_data:
                odds = {
                    'play_type': play_type,
                    'odds_data': item
                }
                odds_list.append(odds)

        except Exception as e:
            logger.error(f"Parse odds error: {e}")

        return odds_list

    def parse_results(self, response: str) -> List[Dict]:
        """解析开奖结果"""
        results = []

        try:
            data = json.loads(response)
            result_list = data.get('value', {}).get('matchResult', [])

            for item in result_list:
                result = {
                    'lottery_match_id': item.get('matchId'),
                    'home_goals_ft': item.get('homeScore'),
                    'away_goals_ft': item.get('awayScore'),
                    'home_goals_ht': item.get('homeScoreHt'),
                    'away_goals_ht': item.get('awayScoreHt'),
                    'spf_result': item.get('spfResult'),
                    'bf_result': item.get('bfResult'),
                    'bqc_result': item.get('bqcResult'),
                    'rqspf_result': item.get('rqspfResult'),
                    'draw_time': item.get('drawTime')
                }
                results.append(result)

        except Exception as e:
            logger.error(f"Parse results error: {e}")

        return results

    def _parse_play_types(self, item: Dict) -> List[str]:
        """解析开售玩法"""
        play_types = []

        # 根据字段判断开售玩法
        if item.get('spfStatus') == 'on':
            play_types.append('spf')
        if item.get('bfStatus') == 'on':
            play_types.append('bf')
        if item.get('bqcStatus') == 'on':
            play_types.append('bqc')
        if item.get('rqspfStatus') == 'on':
            play_types.append('rqspf')

        return play_types

    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# 同步版本 (用于简单场景)
class LotteryCrawlerSync:
    """
    体彩官网爬虫 (同步版本)

    使用方式:
        crawler = LotteryCrawlerSync()
        matches = crawler.crawl_matches_sync()
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._async_crawler = LotteryCrawler(config)

    def crawl_matches_sync(self, match_date: date = None) -> Dict:
        """同步爬取比赛"""
        import requests
        import urllib3
        urllib3.disable_warnings()

        if match_date is None:
            match_date = date.today()

        url = f"{LotteryCrawler.BASE_URL}/gateway/jc/football/getMatchCalculatorV1.qry"
        params = {
            'sellStatus': 'on',
            'date': match_date.strftime('%Y-%m-%d')
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.sporttery.cn/'
        }

        # 创建session并禁用代理
        session = requests.Session()
        session.trust_env = False  # 禁用环境变量代理

        try:
            response = session.get(url, params=params, headers=headers, timeout=30, verify=False)
            response.raise_for_status()

            matches = self._async_crawler.parse_matches(response.text)

            return {
                'success': True,
                'data': matches,
                'count': len(matches)
            }

        except Exception as e:
            logger.error(f"Sync crawl failed: {e}")
            return {
                'success': False,
                'data': [],
                'error': str(e),
                'count': 0
            }

    def crawl_results_sync(self, match_date: date = None) -> List[Dict]:
        """同步爬取开奖结果"""
        import requests

        if match_date is None:
            match_date = date.today()

        url = f"{LotteryCrawler.BASE_URL}/gateway/jc/football/getMatchResultV1.qry"
        params = {
            'date': match_date.strftime('%Y-%m-%d')
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.sporttery.cn/'
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            return self._async_crawler.parse_results(response.text)

        except Exception as e:
            logger.error(f"Sync crawl results failed: {e}")
            return []