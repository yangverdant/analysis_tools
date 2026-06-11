# 窗口C：系统可用性 — FastAPI接口 + 前端日循环 + Docker部署

## 目标
让系统从"命令行工具"变为"可交互Web应用"，前端能查看日循环状态、触发采集/分析

## 当前状态
- main.py: 499行FastAPI，有leagues/matches/teams/stats/sync等路由
- api.py: 456行，另一版FastAPI（与main.py功能重叠）
- SyncStatus.vue: 557行，有gap report和同步按钮
- daily_runner.py: 112行，CLI入口
- state_machine.py: 有daily_cycle_state表持久化
- docker-compose.yml: 22行，基本配置

---

## 任务1: 日循环API路由 — 在main.py中添加

### 问题
main.py没有日循环相关的API端点。前端无法触发/查看日循环状态。

### 修改文件
`backend/app/main.py`

### 新增端点

```python
# === 日循环路由 ===

@app.get("/api/cycle/status")
async def cycle_status():
    """获取日循环当前状态"""
    # 读daily_cycle_state表
    # 返回: {date, current_node, status, last_results: {perceive: {...}, collect: {...}, ...}}

@app.post("/api/cycle/run/{mode}")
async def cycle_run(mode: str):
    """触发日循环 (mode: perceive/collect/analyze/push/clv/validate/morning/full)"""
    # 后台执行daily_runner
    # 返回: {task_id, status: "started"}

@app.get("/api/cycle/predictions")
async def cycle_predictions(date: str = None):
    """获取今日预测结果"""
    # 读lottery_analysis_reports + lottery_matches
    # 返回: [{match_id, home, away, league, prediction: {probabilities, recommended, confidence}, odds_baseline, model_vs_odds, match_profile}]

@app.get("/api/cycle/top3")
async def cycle_top3():
    """获取TOP3价值投注"""
    # 读bet_records或重新计算
    # 返回: [{home, away, selection, prob, edge, kelly, reason}]
```

### 验证
```bash
# 启动FastAPI
python -m uvicorn backend.app.main:app --port 8000

# 测试端点
curl http://localhost:8000/api/cycle/status
curl http://localhost:8000/api/cycle/predictions
curl http://localhost:8000/api/cycle/top3
```

---

## 任务2: 前端日循环面板

### 问题
前端没有日循环状态展示和手动触发入口。

### 修改文件
- 新建: `frontend/src/components/DailyCycle.vue`
- 修改: `frontend/src/App.vue` (添加tab)

### 设计
```
┌─────────────────────────────────────────────┐
│  日循环面板 — 2026-06-08                     │
├─────────────────────────────────────────────┤
│  状态: running  当前节点: push               │
│                                             │
│  [感知✓] [采集✓] [分类✓] [情报✓]           │
│  [分析✓] [推送→] [CLV] [复盘] [学习]       │
│                                             │
│  ── 今日预测 ──────────────────────────     │
│  1. 法国 vs 北爱尔兰 → 主胜 95.7%          │
│     赔率基线: 主胜89% | 模型与赔率一致      │
│  2. 荷兰 vs 乌兹别克斯坦 → 主胜 62.0%      │
│     赔率基线: 主胜80% | 模型与赔率一致      │
│  3. 秘鲁 vs 西班牙 → 客胜 57.4%            │
│     赔率基线: 无 | 无赔率对比               │
│                                             │
│  ── TOP3 价值投注 ────────────────────      │
│  1. 法国 主胜 (优势+62.7%)                  │
│  2. 荷兰 主胜 (优势+29.0%)                  │
│  3. 秘鲁 客胜 (优势+24.4%)                  │
│                                             │
│  [▶ 运行晨间] [▶ 运行全量] [↻ 刷新]       │
└─────────────────────────────────────────────┘
```

### 实现要点
1. 调`/api/cycle/status`获取状态，渲染流程节点
2. 调`/api/cycle/predictions`获取预测
3. 调`/api/cycle/top3`获取价值投注
4. 按钮触发`/api/cycle/run/{mode}`
5. 3秒轮询状态更新

### 验证
浏览器访问前端，能看到日循环面板、预测结果、TOP3推荐

---

## 任务3: Docker部署验证

### 问题
docker-compose.yml未验证，可能有路径/依赖问题。

### 修改文件
- `docker-compose.yml`
- 新建: `Dockerfile`

### Dockerfile
```dockerfile
FROM python:3.10-slim
WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码
COPY . .

# 前端构建(如果需要)
# RUN cd frontend && npm install && npm run build

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 验证
```bash
docker-compose up --build
curl http://localhost:8000/api/cycle/status
```

---

## 任务4: 清理重复的api.py

### 问题
`api.py`和`main.py`功能重叠，都是FastAPI应用。

### 方案
1. 检查api.py是否有main.py没有的功能
2. 将独有功能合并到main.py
3. api.py改为从main.py导入app（或删除）
4. 确保uvicorn启动指向main.py

### 验证
`python -m uvicorn backend.app.main:app --port 8000`能正常启动，所有端点可用

---

## 成功标准
1. `curl localhost:8000/api/cycle/status` 返回日循环状态JSON
2. `curl localhost:8000/api/cycle/predictions` 返回今日预测
3. 前端日循环面板可见、可交互
4. `docker-compose up` 能启动服务
