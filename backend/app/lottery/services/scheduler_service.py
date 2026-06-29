"""
调度服务 - 定时任务管理

串联调度层和服务层:
- 定时触发 SyncService 同步数据
- 定时触发 AnalysisService 生成分析
- 定时触发 ValidationService 验证结果
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    调度服务

    定时任务:
    08:00 - 同步当日比赛数据
    09:00 - 生成待分析比赛的分析报告
    14:00 - 更新最新赔率
    02:00 - 验证昨日预测结果
    03:00 - 优化模型权重
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._scheduler = None
        self._task_status: Dict[str, Dict] = {}

    def start(self):
        """启动调度器"""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            self._scheduler = AsyncIOScheduler()

            # 注册定时任务
            self._scheduler.add_job(
                self._task_sync_matches,
                CronTrigger(hour=8, minute=0),
                id='sync_matches',
                name='同步体彩比赛',
                replace_existing=True
            )

            self._scheduler.add_job(
                self._task_generate_analysis,
                CronTrigger(hour=9, minute=0),
                id='generate_analysis',
                name='生成分析报告',
                replace_existing=True
            )

            self._scheduler.add_job(
                self._task_validate_results,
                CronTrigger(hour=2, minute=0),
                id='validate_results',
                name='验证预测结果',
                replace_existing=True
            )

            self._scheduler.start()
            logger.info("Scheduler started with 3 tasks")

        except ImportError:
            logger.warning("APScheduler not installed, scheduler disabled")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")

    def stop(self):
        """停止调度器"""
        if self._scheduler:
            self._scheduler.shutdown()
            logger.info("Scheduler stopped")

    async def _task_sync_matches(self):
        """任务: 同步比赛数据"""
        task_id = 'sync_matches'
        self._update_task_status(task_id, 'running')

        try:
            from .sync_service import LotterySyncService

            service = LotterySyncService(self.db_path)
            result = service.sync_daily_matches(
                bridge_oddsfe=False,
                trigger_source='scheduler_fast_sporttery',
            )
            service.close()

            self._update_task_status(task_id, 'success', result)
            logger.info(f"Sync matches completed: {result}")

        except Exception as e:
            self._update_task_status(task_id, 'error', {'error': str(e)})
            logger.error(f"Sync matches failed: {e}")

    async def _task_generate_analysis(self):
        """任务: 生成分析报告"""
        task_id = 'generate_analysis'
        self._update_task_status(task_id, 'running')

        try:
            from .analysis_service import AnalysisService
            from ..dao.lottery_dao import LotteryMatchDAO

            # 获取待分析比赛
            match_dao = LotteryMatchDAO(self.db_path)
            pending_matches = match_dao.find_pending_analysis()

            if not pending_matches:
                self._update_task_status(task_id, 'success', {'analyzed': 0})
                return

            # 批量分析
            analysis_service = AnalysisService(self.db_path)

            analyzed = 0
            errors = []

            for match in pending_matches[:20]:  # 最多分析20场
                try:
                    analysis_service.analyze_match(match['lottery_match_id'])
                    analyzed += 1
                except Exception as e:
                    errors.append(str(e))

            self._update_task_status(task_id, 'success', {
                'analyzed': analyzed,
                'errors': errors
            })
            logger.info(f"Analysis completed: {analyzed} matches")

        except Exception as e:
            self._update_task_status(task_id, 'error', {'error': str(e)})
            logger.error(f"Analysis failed: {e}")

    async def _task_validate_results(self):
        """任务: 验证预测结果"""
        task_id = 'validate_results'
        self._update_task_status(task_id, 'running')

        try:
            from ..closed_loop.validation_service import ValidationService
            from ..closed_loop.weight_optimizer import WeightOptimizer
            from datetime import date, timedelta

            # 获取昨日日期
            yesterday = date.today() - timedelta(days=1)

            # 执行验证
            validation_service = ValidationService(self.db_path)
            result = validation_service.validate_date_range(yesterday, yesterday)

            # 执行权重优化
            optimizer = WeightOptimizer(self.db_path)
            optimization = optimizer.optimize_weights(days=30)

            self._update_task_status(task_id, 'success', {
                'validated': result.get('total_matches', 0),
                'validation_result': result,
                'optimization': optimization
            })
            logger.info(f"Validation completed: {result.get('total_matches', 0)} matches validated")

        except Exception as e:
            self._update_task_status(task_id, 'error', {'error': str(e)})
            logger.error(f"Validation failed: {e}")

    def _update_task_status(self, task_id: str, status: str, result: Dict = None):
        """更新任务状态"""
        self._task_status[task_id] = {
            'status': status,
            'result': result,
            'updated_at': datetime.now().isoformat()
        }

    def get_task_status(self) -> Dict:
        """获取所有任务状态"""
        return self._task_status

    def get_jobs(self) -> List[Dict]:
        """获取所有任务"""
        if not self._scheduler:
            return []

        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None
            })
        return jobs

    async def run_task_now(self, task_id: str) -> Dict:
        """立即执行任务"""
        task_map = {
            'sync_matches': self._task_sync_matches,
            'generate_analysis': self._task_generate_analysis,
            'validate_results': self._task_validate_results
        }

        if task_id not in task_map:
            return {'error': f'Task not found: {task_id}'}

        await task_map[task_id]()
        return {'success': True, 'task': task_id}
