# Pressure Index 和实时比赛追踪实现方案

## 一、Pressure Index (压力指数)

### 方案对比

| 方案 | 成本 | 数据质量 | 实现难度 |
|------|------|----------|----------|
| Sportmonks All-In | €249/月 | 最高 | 简单 |
| StatsBomb 360 | 按需定价 | 高 | 中等 |
| **自建模型** | **免费** | 中等 | 中等 |

### 推荐：自建压力指数模型

基于已有数据计算压力指数：

```python
class PressureIndexCalculator:
    """压力指数计算器"""

    def calculate_match_pressure(
        self,
        match_events: Dict,
        minute: int,
        is_home: bool
    ) -> float:
        """
        计算比赛压力指数 (0-100)

        因素：
        1. 比分差异 (权重30%)
        2. 比赛时间 (权重25%)
        3. 控球率劣势 (权重20%)
        4. 射门威胁 (权重15%)
        5. 犯规/黄牌 (权重10%)
        """
        # 比分压力
        score_diff = match_events['my_score'] - match_events['opponent_score']
        if score_diff < 0:
            score_pressure = min(abs(score_diff) * 25, 50)
        else:
            score_pressure = 0

        # 时间压力 (越接近终场压力越大)
        time_pressure = (minute / 90) * 30

        # 控球压力
        possession = match_events.get('possession', 50)
        possession_pressure = max(0, (50 - possession) * 0.4)

        # 射门压力
        shots_conceded = match_events.get('shots_conceded', 0)
        shots_pressure = min(shots_conceded * 2, 15)

        # 纪律压力
        cards = match_events.get('cards', 0)
        discipline_pressure = min(cards * 3, 10)

        total = (score_pressure + time_pressure +
                possession_pressure + shots_pressure +
                discipline_pressure)

        return min(total, 100)
```

---

## 二、实时比赛追踪

### 方案对比

| 方案 | 成本 | 延迟 | 数据丰富度 |
|------|------|------|-----------|
| Sportmonks Inplay | €99/月 | <1秒 | 高 |
| API-Football | €10/月 | 1-5秒 | 中 |
| **爬虫方案** | **免费** | 5-30秒 | 中高 |

### 推荐：爬虫 + The Odds API组合

#### 1. 爬虫目标

| 网站 | 数据 | 难度 |
|------|------|------|
| **FlashScore** | 比分、事件、统计 | 中 |
| **直播吧** | 比分、事件、文字直播 | 低 |
| **懂球帝** | 比分、事件、阵容 | 低 |

#### 2. 实现架构

```
┌─────────────────────────────────────────────┐
│              实时追踪系统                     │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────┐    ┌──────────┐    ┌────────┐│
│  │ 爬虫服务  │───▶│ 事件处理 │───▶│ WebSocket││
│  │ (轮询)   │    │ (解析)   │    │ (推送) ││
│  └──────────┘    └──────────┘    └────────┘│
│       │                               │     │
│       ▼                               ▼     │
│  ┌──────────┐                    ┌────────┐│
│  │ 数据存储  │                    │ 前端   ││
│  │ (SQLite) │                    │ (Vue) ││
│  └──────────┘                    └────────┘│
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ The Odds API (滚球赔率变化)           │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

#### 3. 爬虫代码示例

```python
class LiveMatchTracker:
    """实时比赛追踪器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.active_matches = {}

    async def track_match(self, match_id: str, callback):
        """
        追踪比赛实时数据

        Args:
            match_id: 比赛ID
            callback: 事件回调函数
        """
        while match_id in self.active_matches:
            try:
                # 获取实时数据
                data = await self.fetch_live_data(match_id)

                # 检测事件变化
                events = self.detect_new_events(data)

                # 回调通知
                for event in events:
                    await callback(event)

                # 等待下一次轮询
                await asyncio.sleep(10)

            except Exception as e:
                print(f"追踪错误: {e}")
                await asyncio.sleep(30)

    async def fetch_live_data(self, match_id: str) -> Dict:
        """从直播网站获取数据"""
        # 实现具体的爬虫逻辑
        pass

    def detect_new_events(self, data: Dict) -> List[Dict]:
        """检测新事件"""
        events = []

        # 检测进球
        # 检测红黄牌
        # 检测换人
        # 检测比分变化

        return events
```

---

## 三、推荐实施顺序

### 第一阶段：基础功能（免费）
1. ✅ The Odds API 集成（已完成）
2. 自建压力指数模型
3. 基础爬虫框架

### 第二阶段：增强功能（低成本）
1. API-Football Livescores（€10/月）
2. 实时事件推送
3. 前端实时更新

### 第三阶段：专业功能（高成本）
1. Sportmonks All-In（€249/月）
2. Pressure Index API
3. 完整实时追踪

---

## 四、当前已实现

| 功能 | 状态 | 说明 |
|------|------|------|
| The Odds API | ✅ | 实时赔率获取 |
| 赔率分析 | ✅ | 隐含概率、最佳赔率 |
| 赔率同步 | ✅ | 保存到数据库 |

## 五、待实现

| 功能 | 优先级 | 预计时间 |
|------|--------|----------|
| 压力指数模型 | P1 | 2小时 |
| 爬虫框架 | P2 | 4小时 |
| WebSocket推送 | P3 | 4小时 |
| 前端实时更新 | P3 | 2小时 |
