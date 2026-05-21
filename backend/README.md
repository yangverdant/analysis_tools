# 足球数据分析后端

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务器
python run.py
```

## API文档

启动后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API端点

### 联赛
- `GET /api/v1/leagues` - 联赛列表
- `GET /api/v1/leagues/{league_id}/standings` - 积分榜
- `GET /api/v1/leagues/{league_id}/matches` - 比赛列表

### 球队
- `GET /api/v1/teams` - 球队列表
- `GET /api/v1/teams/{team_id}` - 球队详情
- `GET /api/v1/teams/{team_id}/matches` - 历史战绩
- `GET /api/v1/teams/{team_id}/form` - 近期状态
- `GET /api/v1/teams/{team_id}/schedule` - 赛程密集度

### 比赛
- `GET /api/v1/matches/today` - 今日比赛
- `GET /api/v1/matches/upcoming` - 即将开始的比赛

### 排名
- `GET /api/v1/rankings/fifa/national` - FIFA国家队排名
- `GET /api/v1/rankings/fifa/club` - FIFA俱乐部排名

### 分析
- `GET /api/v1/analytics/head-to-head` - 交锋记录
- `GET /api/v1/analytics/search` - 搜索球队