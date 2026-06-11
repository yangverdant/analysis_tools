# Sportradar、Opta、足球数据API对比分析

## 一、Sportradar

### 基本信息
- **官网**: https://sportradar.com
- **定位**: 专业体育数据服务商，面向B端客户
- **客户**: 体育媒体、博彩公司、体育联盟

### 数据能力

| 数据类型 | 支持情况 | 说明 |
|----------|----------|------|
| 实时比分 | ✅ | 全球覆盖，延迟<1秒 |
| xG数据 | ✅ | 高级分析数据 |
| 球员追踪 | ✅ | 实时位置数据 |
| 赔率数据 | ✅ | 50+庄家，150+市场 |
| AI预测 | ✅ | 胜率预测、比分预测 |
| 伤病名单 | ✅ | 实时更新 |
| 阵容预测 | ✅ | 赛前阵容 |

### 价格
- **Enterprise**: 定制报价，通常$1000+/月
- **博彩版**: €129+/月 (All-In计划)
- **媒体版**: €69+/月 (Advanced计划)
- **免费试用**: 有限

### 优势
1. 数据最全面、最专业
2. 实时性最强
3. xG、Pressure Index等高级数据
4. 官方合作伙伴关系

### 缺点
1. 价格昂贵
2. 需要商业合作
3. 不适合个人开发者

---

## 二、Opta (Stats Perform)

### 基本信息
- **官网**: https://statsperform.com
- **定位**: 体育数据分析公司，提供Opta数据
- **客户**: 媒体、博彩、俱乐部

### 数据能力

| 数据类型 | 支持情况 | 说明 |
|----------|----------|------|
| 实时比分 | ✅ | 全球覆盖 |
| xG数据 | ✅ | Opta xG模型 |
| 球员统计 | ✅ | 详细球员数据 |
| 比赛事件 | ✅ | 传球、射门、犯规等 |
| AI分析 | ✅ | Stats Perform AI |
| 历史数据 | ✅ | 丰富历史数据库 |

### 价格
- **Enterprise**: 定制报价
- **Opta数据订阅**: 通常€500+/月
- **API访问**: 需商务洽谈

### 优势
1. Opta xG业界认可度高
2. 数据质量可靠
3. 历史数据丰富
4. 与主流媒体合作

### 缺点
1. 价格高
2. 需商务合作
3. API文档不公开

---

## 三、API-Football (apifootball)

### 基本信息
- **官网**: https://api-football.com
- **平台**: RapidAPI / api-sports.io
- **定位**: 开发者友好的足球API

### 数据能力

| 数据类型 | 支持情况 | 说明 |
|----------|----------|------|
| 实时比分 | ✅ | 全球联赛 |
| 比赛统计 | ✅ | 射门、控球、传球等 |
| 阵容数据 | ✅ | 首发、替补 |
| 进球时间 | ✅ | goalscorer.time字段 |
| 赔率数据 | ✅ | 多庄家赔率 |
| 伤病名单 | ✅ | injuries端点 |
| 联赛覆盖 | ✅ | 900+联赛 |

### 价格 (RapidAPI)

| 计划 | 价格 | 请求量 |
|------|------|--------|
| Free | $0 | 100次/天 |
| Basic | $10/月 | 3000次/月 |
| Pro | $30/月 | 10000次/月 |
| Ultra | $60/月 | 30000次/月 |
| Mega | $100/月 | 100000次/月 |

### 优势
1. 价格亲民
2. 开发者友好
3. API文档完善
4. RapidAPI一键订阅
5. goalscorer.time提供进球时间

### 缺点
1. xG数据不完整
2. 高级分析有限
3. 实时性不如Sportradar

---

## 四、对比总结

| 维度 | Sportradar | Opta | API-Football |
|------|------------|------|--------------|
| **价格** | €129+/月 | €500+/月 | $10-100/月 |
| **xG数据** | ✅ 完整 | ✅ 完整 | ⚠️ 有限 |
| **进球时间** | ✅ | ✅ | ✅ goalscorer.time |
| **赔率数据** | ✅ 50+庄家 | ✅ | ✅ |
| **伤病名单** | ✅ | ✅ | ✅ injuries端点 |
| **实时性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **开发者友好** | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **联赛覆盖** | 全球 | 全球 | 900+联赛 |
| **适合用户** | 企业 | 企业 | 个人/小团队 |

---

## 五、推荐方案

### 对于您的项目 (football_tools)

**推荐使用**: API-Football + Sportmonks

**理由**:
1. **API-Football**: 
   - 价格亲民 ($10-30/月)
   - goalscorer.time 提供进球时间分布
   - injuries端点提供伤病数据
   - 覆盖900+联赛

2. **Sportmonks** (已配置):
   - 免费版覆盖基础数据
   - xG数据可用 (All-In计划)
   - predictions端点提供AI预测

3. **补充数据源**:
   - 直播吧/懂球帝爬虫 → 球队动态、利好坏消息
   - Odds Feed API → 赔率数据

### 数据获取策略

| 数据类型 | 数据源 | 成本 |
|----------|--------|------|
| 进球时间分布 | API-Football goalscorer | $10/月 |
| 伤病名单 | API-Football injuries | 同上 |
| xG数据 | Sportmonks All-In | €129/月 或 StatsBomb免费数据 |
| 赔率数据 | Odds Feed RapidAPI | $10/月 |
| 球队动态 | 直播吧爬虫 | 免费 |
| 比赛统计 | Sportmonks免费版 | 免费 |

---

## 六、Sportradar/Opta获取建议

如果需要更专业数据：

### Sportradar获取方式
1. 官网联系商务: https://sportradar.com/contact
2. 申请试用账号
3. 选择适合的计划 (Advanced €69/月 或 All-In €129/月)

### Opta获取方式
1. 通过Stats Perform官网联系
2. 申请Opta数据订阅
3. 通常需要商业合作洽谈

### 注意事项
- Sportradar/Opta适合商业项目
- 个人项目建议用API-Football/Sportmonks
- xG数据可继续使用StatsBomb免费数据

---

## 七、API-Football关键端点

### 进球时间分布
```
GET https://api-football-v1.p.rapidapi.com/v3/fixtures
GET https://api-football-v1.p.rapidapi.com/v3/fixtures/{fixture_id}/goalscorer

返回:
{
  "goalscorer": [
    {
      "time": "45'",        // 进球时间
      "player": "Player Name",
      "team": "Team Name",
      "type": "goal/penalty/own_goal"
    }
  ]
}
```

### 伤病名单
```
GET https://api-football-v1.p.rapidapi.com/v3/injuries
参数: league, team, player

返回:
{
  "injuries": [
    {
      "player": "Player Name",
      "team": "Team Name",
      "injury_type": "Muscle injury",
      "return_date": "2026-05-30"
    }
  ]
}
```

---

## 八、结论

**最佳方案**:
1. **主力**: API-Football ($10-30/月) + Sportmonks免费版
2. **补充**: 直播吧爬虫 + Odds Feed API
3. **xG**: StatsBomb免费数据 (已有)

**升级方案** (预算充足):
1. Sportmonks All-In (€129/月) → 完整xG + AI预测
2. 或 Sportradar All-In (€129/月) → 最专业数据