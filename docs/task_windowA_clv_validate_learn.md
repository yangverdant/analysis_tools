# 窗口A：日循环闭环 — CLV + 复盘 + 学习

## 目标
让日循环形成完整闭环：晨间(已通) → 14:00 CLV → 次日复盘 → 参数学习

## 当前状态
- clv_update.py: 189行，已有实现但调sporttery采赔率（不可用），需改用oddsfe
- validate.py: 169行，已有翻车归因5级逻辑，但sync_results可能拿不到数据
- learn.py: 333行，已有场景准确率+回测+调参，但依赖validate的输出
- daily_runner.py: 已接入clv_update/validate/learn节点
- state_machine.py: 已有9个节点

---

## 任务1: 修复clv_update — 用oddsfe替代sporttery赔率

### 问题
clv_update.py第28行调用`sync.sync_daily_matches()`走sporttery采集赔率，但sporttery赔率API返回567错误。

### 修改文件
`backend/app/core/clv_update.py`

### 修改方案
1. 将第46-50行的`sync.sync_daily_matches()`替换为oddsfe赔率采集
2. 复用`collect.py`的`_fetch_and_save_oddsfe_odds()`逻辑
3. 流程：
   - 获取今日未开赛比赛（已有）
   - 调oddsfe获取最新赔率（替换sync.sync_daily_matches）
   - 写入lottery_odds(snapshot_type='midday')（已有）
   - 对比opening vs midday检测CLV信号（已有）

### 具体代码
```python
# 替换第46-50行
# 旧: sync_result = sync.sync_daily_matches(match_date)
# 新:
from backend.app.core.collect import _fetch_and_save_oddsfe_odds
from datetime import date as date_cls
odds_result = _fetch_and_save_oddsfe_odds(db_path, match_date if isinstance(match_date, date_cls) else date_cls.today())
```

注意：`_fetch_and_save_oddsfe_odds`写入的是`snapshot_type='opening'`，CLV需要改为`snapshot_type='midday'`。两种方案：
- **方案A（推荐）**: 修改`_fetch_and_save_oddsfe_odds`接受snapshot_type参数，默认'opening'
- **方案B**: CLV自己写赔率入库逻辑，不复用collect的函数

### 验证
```bash
python -c "
import sys; sys.path.insert(0, 'd:/football_tools')
from backend.app.core.clv_update import clv_update
result = clv_update(db_path='d:/football_tools/data/football_v2.db')
print(result)
"
```

---

## 任务2: 修复validate — 结果获取 + 预测验证

### 问题
1. `sync_results()`调`crawl_results_sync()`，但sporttery结果API可能返回空
2. validate需要`lottery_results`表有数据，目前该表为空
3. `ValidationService`可能未实现

### 修改文件
`backend/app/core/validate.py`

### 修改方案
1. 检查`ValidationService`是否可用，不可用则直接在validate.py内实现验证逻辑
2. 添加oddsfe结果获取作为备选数据源
3. 验证逻辑：从`lottery_analysis_reports`取预测，从`lottery_results`取实际结果，对比计算准确率

### 验证核心逻辑
```python
def _validate_single(prediction, result):
    """验证单场预测"""
    pred_rec = prediction['recommended']  # home_win/draw/away_win
    actual = result['spf_result']         # 3/1/0

    result_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    pred_result = result_map.get(pred_rec, '')

    correct = (pred_result == actual)

    # 翻车归因
    attribution = _attribute_error(prediction, result, correct)

    return {
        'correct': correct,
        'predicted': pred_result,
        'actual': actual,
        'attribution': attribution,
    }
```

### 验证
```bash
# 先模拟插入一条结果
python -c "
import sqlite3
conn = sqlite3.connect('d:/football_tools/data/football_v2.db')
conn.execute('INSERT OR REPLACE INTO lottery_results (lottery_match_id, home_goals_ft, away_goals_ft, spf_result) VALUES (\"202606081201\", 3, 0, \"3\")')
conn.commit(); conn.close()
"
# 然后运行validate
python -c "
import sys; sys.path.insert(0, 'd:/football_tools')
from backend.app.core.validate import validate
result = validate({}, 'd:/football_tools/data/football_v2.db')
print(result)
"
```

---

## 任务3: 验证learn闭环

### 问题
learn.py依赖validate写入的`lottery_validation`表，需要validate先跑通。

### 修改文件
`backend/app/core/learn.py`（可能只需小修）

### 修改方案
1. validate跑通后，检查learn是否能正确读取validation数据
2. 确认`compute_scene_accuracy()`和`_backtest()`函数能正确执行
3. 确认参数调整能写入`model_params_history`表

### 验证
```bash
python -c "
import sys; sys.path.insert(0, 'd:/football_tools')
from backend.app.core.learn import learn
result = learn(db_path='d:/football_tools/data/football_v2.db')
print(result)
"
```

---

## 任务4: 集成测试 — 完整日循环

### 验证步骤
1. 清除今日测试数据
2. 运行`daily_runner --mode full`（perceive→collect→classify→intel→analyze→push→clv_update）
3. 模拟插入比赛结果
4. 运行`daily_runner --mode validate`
5. 运行`daily_runner --mode learn`
6. 检查`lottery_validation`和`model_params_history`表有数据

### 成功标准
- full模式跑完无报错
- lottery_validation有翻车归因记录
- model_params_history有参数调整记录（或"无需调整"记录）
