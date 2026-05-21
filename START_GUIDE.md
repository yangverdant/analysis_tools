# 足球数据分析可视化平台 - 启动指南

## 项目完成状态

✅ 所有核心功能已完成

---

## 一、项目结构

```
football_tools/
├── data/                           # 数据目录
│   ├── football_unified.db         # 统一数据库 (530,286场比赛)
│   ├── linkage/                    # 关联数据
│   └── fifa_rankings/              # FIFA排名数据
│
├── backend/                        # FastAPI后端
│   ├── app/main.py                 # API服务
│   ├── run.py                      # 启动脚本
│   └ requirements.txt
│
├── frontend/                       # Vue前端
│   ├── src/pages/                  # 页面组件
│   ├── src/api/                    # API调用
│   ├── package.json
│   └── vite.config.js
│
├── football_analysis_techniques/   # 技术文档
│   ├── README.md                   # 技术全景
│   ├── python_stack.md             # Python技术栈
│   ├── advanced_metrics.md         # 高级指标(xG/Elo等)
│   ├── prediction_models.md        # 预测模型
│   ├── visualization.md            # 可视化技术
│   └── ...
│
├── build_team_mapping.py           # 球队名称映射
├── build_database.py               # 数据库构建
│
├── ARCHITECTURE_DESIGN.md          # 系统架构设计
├── FEATURE_DESIGN.md               # 功能设计文档
└── DATA_LINKAGE_DESIGN.md          # 数据关联设计
```

---

## 二、数据统计

| 数据类型 | 数量 |
|----------|------|
| 球队 | 1,883 |
| 比赛 | 530,286 |
| 联赛 | 74 |
| FIFA国家队排名 | 2,160 条 |
| FIFA俱乐部排名 | 360 条 |

---

## 三、启动步骤

### 1. 启动后端API

```bash
cd d:/football_tools/backend
pip install -r requirements.txt
python run.py
```

访问: http://localhost:8000/docs (API文档)

### 2. 启动前端

```bash
cd d:/football_tools/frontend
npm install
npm run dev
```

访问: http://localhost:3000

---

## 四、API端点

### 数据查询
- `/api/v1/leagues` - 联赛列表
- `/api/v1/leagues/{id}/standings` - 积分榜
- `/api/v1/teams/{id}` - 球队详情
- `/api/v1/teams/{id}/matches` - 历史战绩
- `/api/v1/teams/{id}/form` - 近期状态
- `/api/v1/teams/{id}/schedule` - 赛程密集度
- `/api/v1/matches/today` - 今日比赛
- `/api/v1/matches/upcoming` - 即将开始的比赛
- `/api/v1/rankings/fifa/national` - FIFA国家队排名
- `/api/v1/rankings/fifa/club` - FIFA俱乐部排名

### 分析功能
- `/api/v1/analytics/head-to-head` - 交锋分析
- `/api/v1/analytics/search` - 球队搜索

---

## 五、页面功能

### 首页
- 今日比赛展示
- 即将开始的比赛
- 热门联赛入口
- FIFA排名TOP 10

### 联赛页
- 积分榜表格
- 近期比赛列表
- 点击球队进入球队详情

### 球队页
- 球队基本信息
- 统计数据卡片
- 近期状态(最近10场)
- 赛程密集度分析
- 历史战绩列表

### 分析页
- 球队搜索
- 交锋分析(两队历史对战)

---

## 六、后续扩展

可继续添加的功能:

1. **比赛预测API** - 使用xG/Elo模型预测比赛结果
2. **球员数据** - 导入球员统计数据
3. **教练数据** - 导入教练执教历史
4. **图表可视化** - 使用ECharts添加更多图表
5. **轮换建议** - 基于赛程密集度给出轮换建议
6. **多赛事分析** - 分析球队在不同赛事的表现

---

## 七、技术文档

详细技术说明见 `football_analysis_techniques/` 目录:

- [README.md](football_analysis_techniques/README.md) - 技术全景
- [advanced_metrics.md](football_analysis_techniques/advanced_metrics.md) - xG/Elo/VAEP等指标
- [prediction_models.md](football_analysis_techniques/prediction_models.md) - Poisson/Dixon-Coles/ML预测模型
- [visualization.md](football_analysis_techniques/visualization.md) - mplsoccer可视化
- [tactical_analysis.md](football_analysis_techniques/tactical_analysis.md) - 战术分析技术

---

*项目完成时间: 2024年5月17日*