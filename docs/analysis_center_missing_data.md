# 分析中心数据缺失分析

**分析日期**: 2026-05-21

---

## 当前分析模块一览

| 模块 | 数据来源 | 当前状态 | 缺失内容 |
|------|----------|----------|----------|
| AI预测分析 | 综合计算 | ✅ 可用 | - |
| 近期战绩 | matches表 | ✅ 可用 | - |
| 主客场表现 | matches表 | ✅ 可用 | - |
| 半场战绩 | matches表 | ⚠️ 数据少 | 需补充半场比分 |
| 进球时间分布 | statsbomb_shots | ⚠️ team_id缺失 | 需填充team_id |
| 进攻与大小球 | 综合计算 | ✅ 可用 | - |
| **球队动态** | team_news表 | ⚠️ 数据少 | **需获取实时资讯** |
| Elo实力 | elo_ratings | ✅ 可用 | - |
| 历史交锋 | matches表 | ✅ 可用 | - |
| 敌对关系 | 计算 | ✅ 可用 | - |
| 关键理由 | 计算 | ✅ 可用 | - |
| 未来赛程 | matches表 | ✅ 可用 | - |
| 休息天数 | 计算 | ✅ 可用 | - |
| 投注分析 | match_odds | ⚠️ 数据少 | 需补充赔率 |

---

## 重点缺失：球队动态（利好/坏消息）

### 数据库表结构

**team_news 表** (已有20条示例数据):
```sql
- news_id, team_id, title, content
- news_type: injury/return/form/transfer/coach/suspension
- category: positive/negative
- impact_level: 1-5 (影响程度)
- impact_type: key_player_injury/star_player_return/winning_streak等
- affected_players: 受影响球员
- news_date, source, verified
```

**player_status 表** (已有1000条数据):
```sql
- player_id, team_id, status
- status: available/injured/suspended/doubtful
- injury_type, injury_severity, expected_return
- suspension_reason, suspension_matches
- appearance_probability: 出场概率
- team_impact_score: 对球队影响评分
```

### 当前问题

1. **team_news 数据量少**: 只有20条手动添加的示例数据
2. **数据来源缺失**: 没有自动获取资讯的渠道
3. **实时性差**: 无法获取最新的伤病、停赛、转会消息

---

## 利好/坏消息数据获取方案

### 方案一：体育资讯API（推荐）

#### 1. apifootball API
- **端点**: `/news/` - 获取足球新闻
- **数据**: 球队新闻、伤病更新、转会消息
- **成本**: 免费额度有限，付费约$10/月

#### 2. Sportmonks API
- **端点**: `/news/` - 新闻资讯
- **数据**: 伤病、停赛、转会新闻
- **成本**: 免费版有限，付费约€9/月起

#### 3. football-data.org API
- **端点**: 无专门新闻端点，但有球员状态
- **数据**: 球员伤病状态
- **成本**: 免费版可用

### 方案二：爬虫抓取（推荐）

#### 1. 直播吧 (zhibo8.cc)
- **网址**: https://www.zhibo8.cc
- **数据**: 伤病新闻、赛前资讯、球队动态
- **优点**: 更新及时、内容丰富
- **爬取内容**:
  - 球队新闻页: `/zuqiu/{team_name}.htm`
  - 伤病汇总: 每日伤病更新
  - 赛前新闻: 比赛前瞻、阵容预测

#### 2. 懂球帝 (dongqiudi.com)
- **网址**: https://www.dongqiudi.com
- **数据**: 球队动态、球员伤病、转会消息
- **优点**: 内容专业、分类清晰
- **爬取内容**:
  - 球队主页: `/team/{team_id}.html`
  - 伤病名单: `/injury`
  - 转会新闻: `/transfer`

#### 3. 官方数据源
- **英超官网**: https://www.premierleague.com/injuries
- **西甲官网**: https://www.laliga.com/injuries
- **德甲官网**: https://www.bundesliga.com/injuries
- **优点**: 数据权威、准确
- **缺点**: 需要逐个联赛爬取

### 方案三：第三方数据服务

#### 1. Transfermarkt
- **网址**: https://www.transfermarkt.com
- **数据**: 球员身价、转会、伤病
- **爬取**: 球队阵容页的伤病标记

#### 2. SofaScore
- **网址**: https://www.sofascore.com
- **数据**: 球员出场概率、伤病状态
- **API**: 有非官方API可调用

---

## 推荐实施方案

### 第一阶段：爬虫抓取（低成本）

1. **懂球帝爬虫** - 获取球队动态、伤病消息
   - 优先级：⭐⭐⭐⭐⭐
   - 数据质量：高
   - 实施难度：中等

2. **直播吧爬虫** - 获取赛前资讯、阵容预测
   - 优先级：⭐⭐⭐⭐
   - 数据质量：高
   - 实施难度：中等

3. **官方伤病名单** - 获取权威伤病数据
   - 优先级：⭐⭐⭐
   - 数据质量：最高
   - 实施难度：较高（需逐联赛）

### 第二阶段：API补充（稳定可靠）

1. **apifootball news端点** - 补充新闻数据
2. **Sportmonks** - 补充球员状态

---

## 数据类型与来源对照

| 数据类型 | 最佳来源 | 备选来源 |
|----------|----------|----------|
| **伤病消息** | 懂球帝、官方 | apifootball |
| **停赛信息** | 官方、懂球帝 | Sportmonks |
| **转会新闻** | 懂球帝、Transfermarkt | apifootball |
| **主帅变动** | 懂球帝、直播吧 | apifootball |
| **球队状态** | 直播吧赛前分析 | 计算推断 |
| **阵容预测** | 直播吧、懂球帝 | apifootball |
| **出场概率** | SofaScore | player_status表 |

---

## 实施建议

1. **优先开发懂球帝爬虫**
   - 数据最全面、更新最及时
   - 可获取：伤病、停赛、转会、主帅变动

2. **补充直播吧赛前资讯**
   - 获取：阵容预测、比赛前瞻

3. **定时更新机制**
   - 每日更新伤病名单
   - 比赛前2小时更新阵容预测
   - 实时抓取重大新闻

4. **数据入库流程**
   ```
   爬虫抓取 → NLP分类 → 影响评分 → 入库team_news
   ```

---

## 其他缺失数据

| 数据 | 缺失原因 | 解决方案 |
|------|----------|----------|
| **xG数据** | StatsBomb team_id未填充 | 运行脚本填充team_id |
| **进球时间** | statsbomb_shots.team_id为NULL | 同上 |
| **赔率数据** | match_odds数据少 | 集成Odds Feed API |
| **半场比分** | 部分比赛缺失 | apifootball获取 |

---

## 下一步行动

1. [ ] 开发懂球帝爬虫，获取球队动态
2. [ ] 开发直播吧爬虫，获取赛前资讯
3. [ ] 填充statsbomb_shots的team_id字段
4. [ ] 集成Odds Feed API获取赔率
5. [ ] 建立定时更新机制