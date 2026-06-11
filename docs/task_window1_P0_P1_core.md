# 窗口1: P0 阻塞项 + P1 日循环核心

## 任务目标
让日循环跑起来：6:00感知→7:00采集→9:00分析→次日复盘，端到端跑通。

---

## Step 1: 修复 team_names.py 国家队映射 (0.5天)

**文件:** `fetchers/common/team_names.py` 第160-176行

**Bug:** `normalize_team_name("日本")` → "日本" 而非 "Japan"

**原因:** 第164行 `if en_name in _standard_to_info` — 国家队不在team_aliases.json(只有5大联赛俱乐部)，所以中文→英文反向映射永远不会建立。

**修复:**
```python
# 找到第160-176行，当前代码:
    # 4. 补充 team_chinese_names.json 的反向映射 (中→英)
    chinese = _load_chinese_names()
    for en_name, cn_name in chinese.items():
        # 如果英文名是已知标准名，把中文名加入索引
        if en_name in _standard_to_info:
            cn_key = cn_name.lower()
            if cn_key not in _name_to_standard:
                _name_to_standard[cn_key] = en_name
                if cn_name not in _standard_to_all_names.get(en_name, []):
                    _standard_to_all_names.setdefault(en_name, [en_name]).append(cn_name)
        # 如果中文名指向某个已知标准名
        elif en_name.lower() in _name_to_standard:
            standard = _name_to_standard[en_name.lower()]
            cn_key = cn_name.lower()
            if cn_key not in _name_to_standard:
                _name_to_standard[cn_key] = standard

# 替换为:
    # 4. 补充 team_chinese_names.json 的反向映射 (中→英)
    chinese = _load_chinese_names()
    for en_name, cn_name in chinese.items():
        cn_key = cn_name.lower()
        # 【关键修复】直接建立中文→英文映射（不论英文名是否已知标准名）
        if cn_key not in _name_to_standard:
            _name_to_standard[cn_key] = en_name
        # 原有逻辑: 如果英文名是已知标准名，补充别名
        if en_name in _standard_to_info:
            if cn_name not in _standard_to_all_names.get(en_name, []):
                _standard_to_all_names.setdefault(en_name, [en_name]).append(cn_name)
        elif en_name.lower() in _name_to_standard:
            standard = _name_to_standard[en_name.lower()]
            if cn_key not in _name_to_standard:
                _name_to_standard[cn_key] = standard
```

**验证:**
```python
from fetchers.common.team_names import normalize_team_name
assert normalize_team_name("日本") == "Japan"
assert normalize_team_name("巴西") == "Brazil"
assert normalize_team_name("韩国") == "Korea Republic"
assert normalize_team_name("英格兰") == "England"
assert normalize_team_name("阿森纳") == "Arsenal"  # 俱乐部不受影响
```

---

## Step 2: 修复 sync_service.py sync_odds + sync_results (1天)

**文件:** `backend/app/lottery/services/sync_service.py`

### 2a: sync_daily_matches() 加赔率入库

当前sync_daily_matches()第71-106行，比赛入库了但赔率没入库。

在第100行 `if self.match_dao.insert(match_data):` 之后，加入赔率入库逻辑:

```python
                # DAO 入库
                if self.match_dao.insert(match_data):
                    saved_count += 1

                    # 【新增】赔率入库
                    odds_data = self._extract_odds(raw_match)  # 复用已有的提取逻辑
                    if odds_data:
                        for play_type, odds in odds_data.items():
                            self.odds_dao.insert(
                                lottery_match_id=raw_match['lottery_match_id'],
                                play_type=play_type,
                                odds_data=odds
                            )
```

注意: `_extract_odds()` 方法可能在LotteryCrawlerSync中而不是SyncService中。如果不存在，需要从raw_match的odds字段中提取。检查lottery_crawler.py的_extract_odds()方法，确认返回格式。

### 2b: sync_results() 实现结果入库

当前第133-158行，爬取了结果但没写入lottery_results(TODO)。

替换为:
```python
    def sync_results(self, match_date: date = None) -> Dict:
        """同步开奖结果"""
        if match_date is None:
            match_date = date.today()

        raw_results = self.crawler.crawl_results_sync(match_date)

        if not raw_results:
            return {
                'success': False,
                'date': str(match_date),
                'results': 0
            }

        saved = 0
        for result in raw_results:
            try:
                # 解析结果
                result_data = {
                    'lottery_match_id': result.get('lottery_match_id') or result.get('matchId'),
                    'home_goals_ft': result.get('homeScore'),
                    'away_goals_ft': result.get('awayScore'),
                    'home_goals_ht': result.get('homeScoreHt'),
                    'away_goals_ht': result.get('awayScoreHt'),
                    'spf_result': result.get('spfResult'),
                    'bf_result': result.get('bfResult'),
                    'bqc_result': result.get('bqcResult'),
                    'rqspf_result': result.get('rqspfResult'),
                }
                self.result_dao.insert(result_data)
                saved += 1
            except Exception as e:
                logger.error(f"Save result error: {e}")

        # 更新sell_status
        self.match_dao.update_sell_status(match_date, 'finished')

        return {
            'success': True,
            'date': str(match_date),
            'saved': saved
        }
```

**需要新建 ResultDAO** — 见Step 4。

---

## Step 3: DB Schema变更 (0.5天)

**文件:** 创建 `scripts/migrate_db.py`

```python
"""数据库Schema迁移脚本"""
import sqlite3
import sys

DB_PATH = 'data/football_v2.db'

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. lottery_matches 加 oddsfe_event_id
    try:
        cursor.execute("ALTER TABLE lottery_matches ADD COLUMN oddsfe_event_id TEXT")
        print("✓ lottery_matches +oddsfe_event_id")
    except: print("- lottery_matches oddsfe_event_id already exists")

    # 2. lottery_odds 加 snapshot_type
    try:
        cursor.execute("ALTER TABLE lottery_odds ADD COLUMN snapshot_type TEXT DEFAULT 'current'")
        print("✓ lottery_odds +snapshot_type")
    except: print("- lottery_odds snapshot_type already exists")

    # 3. lottery_validation 加归因字段
    for col, typ in [('attribution', 'TEXT'), ('attribution_detail', 'TEXT'),
                     ('scenario_type', 'TEXT'), ('actionable', 'INTEGER DEFAULT 0')]:
        try:
            cursor.execute(f"ALTER TABLE lottery_validation ADD COLUMN {col} {typ}")
            print(f"✓ lottery_validation +{col}")
        except: print(f"- lottery_validation {col} already exists")

    # 4. 新建 daily_cycle_state 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_cycle_state (
            date TEXT PRIMARY KEY,
            current_node TEXT NOT NULL,
            perceive_result TEXT,
            collect_result TEXT,
            intel_result TEXT,
            classify_result TEXT,
            analyze_result TEXT,
            push_result TEXT,
            clv_result TEXT,
            validate_result TEXT,
            learn_result TEXT,
            status TEXT DEFAULT 'running',
            error_message TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✓ daily_cycle_state table")

    # 5. 新建 model_accuracy 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_accuracy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_type TEXT NOT NULL,
            odds_tier TEXT,
            participant_type TEXT DEFAULT 'club',
            total_matches INTEGER DEFAULT 0,
            model_accuracy REAL,
            odds_baseline_accuracy REAL,
            model_brier REAL,
            odds_brier REAL,
            period TEXT,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✓ model_accuracy table")

    # 6. 新建 bet_records 表 (投资回报追踪)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bet_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER,
            lottery_match_id TEXT,
            play_type TEXT,
            selection TEXT,
            odds REAL,
            stake REAL DEFAULT 0,
            result TEXT,
            payout REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prediction_id) REFERENCES lottery_predictions(prediction_id)
        )
    """)
    print("✓ bet_records table")

    # 7. data_source_health 初始化
    cursor.execute("""
        INSERT OR IGNORE INTO data_source_health (source_name, source_category, status)
        VALUES
            ('sporttery', 'lottery', 'unknown'),
            ('oddsfe', 'odds', 'unknown'),
            ('apifootball', 'injury', 'unknown'),
            ('fifa', 'ranking', 'unknown'),
            ('football_data_uk', 'historical', 'unknown')
    """)
    print("✓ data_source_health initialized")

    # 8. leagues表 competition_type 细分
    cursor.execute("""
        UPDATE leagues SET competition_type = 'qualifier'
        WHERE name_en LIKE '%qualif%' OR name_cn LIKE '%预选赛%'
    """)
    cursor.execute("""
        UPDATE leagues SET competition_type = 'nations_league'
        WHERE name_en LIKE '%nations league%' OR name_cn LIKE '%国联%'
    """)
    cursor.execute("""
        UPDATE leagues SET competition_type = 'olympic'
        WHERE name_en LIKE '%olympic%' OR name_cn LIKE '%奥运%'
    """)
    print("✓ leagues competition_type refined")

    # 9. model_accuracy 加 participant_type 维度(俱乐部 vs 国家队分线统计)
    # 已在CREATE TABLE中加入participant_type字段

    conn.commit()
    conn.close()
    print("\n迁移完成!")

if __name__ == '__main__':
    migrate()
```

**运行:** `python scripts/migrate_db.py`

---

## Step 4: data_access 层拆DAO (2天)

**目录:** `backend/app/data_access/`

### 4a: database.py — 连接管理

```python
"""数据库连接管理"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent.parent / 'data' / 'football_v2.db'

def get_connection(db_path: str = None) -> sqlite3.Connection:
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
```

### 4b: result_dao.py — 新建ResultDAO

```python
"""lottery_results DAO"""
from typing import Dict, List, Optional
import sqlite3

class ResultDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def insert(self, result: Dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO lottery_results
                (lottery_match_id, home_goals_ft, away_goals_ft,
                 home_goals_ht, away_goals_ht,
                 spf_result, bf_result, bqc_result, rqspf_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['lottery_match_id'],
                result.get('home_goals_ft'), result.get('away_goals_ft'),
                result.get('home_goals_ht'), result.get('away_goals_ht'),
                result.get('spf_result'), result.get('bf_result'),
                result.get('bqc_result'), result.get('rqspf_result')
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"ResultDAO insert error: {e}")
            return False
        finally:
            conn.close()

    def find_by_date(self, match_date: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("""
                SELECT lr.* FROM lottery_results lr
                JOIN lottery_matches lm ON lr.lottery_match_id = lm.lottery_match_id
                WHERE lm.match_date = ?
            """, (match_date,))
            return [dict(row) for row in conn.fetchall()]
        finally:
            conn.close()
```

### 4c: 其他DAO从lottery_dao.py迁移

把 `backend/app/lottery/dao/lottery_dao.py` 中的5个DAO类按表拆分:
- match_dao.py → LotteryMatchDAO
- odds_dao.py → LotteryOddsDAO
- prediction_dao.py → PredictionDAO
- validation_dao.py → ValidationDAO
- health_dao.py → DataSourceHealthDAO (新增)
- cycle_dao.py → CycleStateDAO (新增)

**原文件保留**，改为从data_access导入(兼容性):
```python
# backend/app/lottery/dao/lottery_dao.py
from backend.app.data_access.match_dao import LotteryMatchDAO
from backend.app.data_access.odds_dao import LotteryOddsDAO
# ...
```

---

## Step 5: 工作流状态机 + daily_runner (2天)

### 5a: state_machine.py

**文件:** `backend/app/core/state_machine.py`

```python
"""轻量日循环工作流引擎"""
import logging
from typing import Callable, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class CycleState:
    date: str
    current_node: str = 'perceive'
    status: str = 'running'
    results: Dict = field(default_factory=dict)
    error: Optional[str] = None

class DailyCycleStateMachine:
    NODES = ['perceive', 'collect', 'intel', 'classify',
             'analyze', 'push', 'clv_update', 'validate', 'learn']

    TRANSITIONS = {
        'perceive': {'normal': 'collect', 'validate_yesterday': 'validate',
                     'circuit_break': 'collect', 'warmup': 'collect'},
        'collect': 'intel',
        'intel': 'classify',
        'classify': 'analyze',
        'analyze': 'push',
        'push': 'done_morning',      # 上午完成，等14:00
        'clv_update': 'done_day',     # 14:00完成，等次日
        'validate': 'learn',
        'learn': 'collect',           # 闭环
    }

    def __init__(self, node_handlers: Dict[str, Callable], cycle_dao):
        self.handlers = node_handlers
        self.cycle_dao = cycle_dao

    def run_node(self, state: CycleState, node: str) -> dict:
        handler = self.handlers.get(node)
        if not handler:
            raise ValueError(f"No handler for node: {node}")
        return handler(state)

    def get_next(self, current: str, result: dict) -> str:
        transition = self.TRANSITIONS.get(current, {})
        if isinstance(transition, dict):
            route = result.get('route', 'normal')
            return transition.get(route, transition.get('normal', 'done'))
        return transition

    def run_cycle(self, state: CycleState, stop_at: str = None) -> CycleState:
        while state.status == 'running':
            try:
                result = self.run_node(state, state.current_node)
                state.results[state.current_node] = result

                next_node = self.get_next(state.current_node, result)
                if next_node.startswith('done'):
                    state.status = next_node
                    break

                state.current_node = next_node
                self.cycle_dao.save(state)

                if stop_at and state.current_node == stop_at:
                    break

            except Exception as e:
                state.status = 'failed'
                state.error = str(e)
                self.cycle_dao.save(state)
                logger.error(f"Cycle failed at {state.current_node}: {e}")
                break

        return state
```

### 5b: daily_runner.py

**文件:** `backend/app/core/daily_runner.py`

```python
"""日循环入口 — APScheduler调度 + 状态机驱动"""
import argparse
import logging
from datetime import datetime

from .state_machine import DailyCycleStateMachine, CycleState
from .perceive import perceive
from .collect import collect
from .intel import intel
from .classify import classify
from .analyze import analyze
from .push import push
from .clv_update import clv_update
from .validate import validate
from .learn import learn

logger = logging.getLogger(__name__)

DB_PATH = 'data/football_v2.db'

def get_handlers():
    return {
        'perceive': perceive,
        'collect': collect,
        'intel': intel,
        'classify': classify,
        'analyze': analyze,
        'push': push,
        'clv_update': clv_update,
        'validate': validate,
        'learn': learn,
    }

def run_mode(mode: str):
    """按模式运行"""
    from backend.app.data_access.cycle_dao import CycleStateDAO
    dao = CycleStateDAO(DB_PATH)

    today = datetime.now().strftime('%Y-%m-%d')
    state = dao.load(today) or CycleState(date=today)

    handlers = get_handlers()
    machine = DailyCycleStateMachine(handlers, dao)

    if mode == 'perceive':
        result = perceive(state)
        print(f"自感知完成: {result}")
    elif mode == 'collect':
        state.current_node = 'collect'
        machine.run_cycle(state, stop_at='classify')
    elif mode == 'analyze':
        state.current_node = 'analyze'
        machine.run_cycle(state, stop_at='push')
    elif mode == 'validate':
        state.current_node = 'validate'
        machine.run_cycle(state, stop_at='learn')
    elif mode == 'morning':
        # 完整上午流程: perceive → collect → ... → push
        machine.run_cycle(state, stop_at='push')
    elif mode == 'full':
        machine.run_cycle(state)
    else:
        print(f"Unknown mode: {mode}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='perceive',
                       choices=['perceive', 'collect', 'analyze', 'validate', 'morning', 'full'])
    args = parser.parse_args()
    run_mode(args.mode)
```

---

## Step 6: perceive.py (1天)

**文件:** `backend/app/core/perceive.py`

核心逻辑见plan文件6:00自感知节。关键要点:
- 冷启动检测 → 触发热启动(oddsfe 8492场历史回测)
- 熔断检测 → 模型准确率 < 赔率基线 → 返回circuit_break路由
- 昨日未完成检查 → 路由到validate
- 输出DailyStatus写入daily_cycle_state

**热启动实现:**
```python
def run_warmup() -> dict:
    """用oddsfe历史数据做离线回测"""
    # 1. 查oddsfe历史友谊赛(8492场)
    # 2. 纯赔率: 1/odds归一化 → argmax → 准确率
    # 3. ComprehensiveAnalyzer: 同样8492场 → 准确率
    # 4. 返回对比结果
    # 这部分可以用oddsfe数据直接SQL查询，不需要跑完整分析
```

---

## Step 7: collect.py (1天)

**文件:** `backend/app/core/collect.py`

核心逻辑见plan文件7:00采集节。关键要点:
- 轮询检测开售(非固定7:00)
- 队名映射(依赖Step 1修复)
- 赔率入库lottery_odds(snapshot_type='opening')
- sell_status更新
- data_source_health更新

---

## Step 8: validate.py + push.py (1.5天)

### validate.py
- 调用sync_results(Step 2修复后)
- 写入lottery_results
- 调ValidationService.validate_match()
- 翻车归因(5级: bad_luck/close_match/correction_wrong/market_wrong/intel_missing)
- 写入lottery_validation(含attribution)

### push.py
- 汇总今日预测
- TOP3价值投注(按Kelly排序)
- 自然语言理由(不用术语)
- 投资回报追踪(bet_records表)
- 推送渠道: 初期只写日志

---

## 验证清单

- [ ] `normalize_team_name("日本")` == "Japan"
- [ ] sync_daily_matches()入库后lottery_odds有数据
- [ ] sync_results()入库后lottery_results有数据
- [ ] `python scripts/migrate_db.py` 无报错
- [ ] `python -m backend.app.core.daily_runner --mode perceive` 不报错
- [ ] 日循环跑完一天，daily_cycle_state.status != 'failed'
- [ ] 推送内容有TOP3价值投注+自然语言理由
