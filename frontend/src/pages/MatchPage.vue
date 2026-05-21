<template>
  <div class="match-page">
    <!-- 返回按钮 -->
    <div class="back-header">
      <button class="back-btn" @click="goBack">
        <ArrowLeftIcon />
        <span>返回分析中心</span>
      </button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>加载比赛分析数据...</p>
    </div>

    <!-- 比赛不存在 -->
    <div v-else-if="error" class="error-state">
      <span class="icon">❌</span>
      <p>{{ error }}</p>
    </div>

    <!-- 比赛详情 -->
    <template v-else>
      <!-- 比赛头部 -->
      <section class="match-header">
        <div class="league-info">
          <span class="league-name">{{ analysis.match?.league_cn || analysis.match?.league }}</span>
          <span class="match-date">{{ analysis.match?.match_date }}</span>
        </div>
        <div class="match-teams">
          <div class="team home" @click="goToTeam(analysis.match?.home_team_id)">
            <span class="team-name">{{ analysis.match?.home_team_cn || analysis.match?.home_team }}</span>
            <span class="elo-tag home">Elo {{ analysis.elo?.home || '--' }}</span>
          </div>
          <div class="score-section">
            <div class="scores">
              <span class="score">{{ analysis.match?.home_goals ?? '-' }}</span>
              <span class="separator">:</span>
              <span class="score">{{ analysis.match?.away_goals ?? '-' }}</span>
            </div>
            <div class="vs-info">
              <span class="vs-text">VS</span>
              <span class="match-time" v-if="analysis.match?.beijing_time">{{ analysis.match?.beijing_time }}</span>
              <span class="match-time" v-else-if="analysis.match?.match_time">{{ analysis.match?.match_time }}</span>
            </div>
            <div class="status" :class="matchStatus">{{ statusText }}</div>
          </div>
          <div class="team away" @click="goToTeam(analysis.match?.away_team_id)">
            <span class="team-name">{{ analysis.match?.away_team_cn || analysis.match?.away_team }}</span>
            <span class="elo-tag away">Elo {{ analysis.elo?.away || '--' }}</span>
          </div>
        </div>
      </section>

      <!-- 时间段选择器 -->
      <div class="period-selector">
        <button v-for="p in ['last6', 'last10', 'last20']" :key="p"
                :class="['period-btn', { active: selectedPeriod === p }]"
                @click="selectedPeriod = p">
          {{ p === 'last6' ? '近6场' : p === 'last10' ? '近10场' : '近20场' }}
        </button>
      </div>

      <!-- 两列大布局 -->
      <div class="two-columns">
        <!-- 左列 -->
        <div class="column">
          <!-- AI预测分析 -->
          <section class="section-block">
            <div class="section-title"><BrainIcon /><span>AI预测分析</span></div>
            <div class="cards-row" v-if="analysis.prediction">
              <div class="card">
                <div class="card-header"><h4>赛果预测</h4></div>
                <div class="card-body">
                  <div class="prediction-bars">
                    <div class="pred-row">
                      <span class="label">主胜</span>
                      <div class="bar-container"><div class="bar home" :style="{ width: analysis.prediction.home_win_prob + '%' }"></div></div>
                      <span class="value">{{ analysis.prediction.home_win_prob }}%</span>
                    </div>
                    <div class="pred-row">
                      <span class="label">平局</span>
                      <div class="bar-container"><div class="bar draw" :style="{ width: analysis.prediction.draw_prob + '%' }"></div></div>
                      <span class="value">{{ analysis.prediction.draw_prob }}%</span>
                    </div>
                    <div class="pred-row">
                      <span class="label">客胜</span>
                      <div class="bar-container"><div class="bar away" :style="{ width: analysis.prediction.away_win_prob + '%' }"></div></div>
                      <span class="value">{{ analysis.prediction.away_win_prob }}%</span>
                    </div>
                  </div>
                  <div class="predicted-score">
                    <span>预测比分</span>
                    <b>{{ analysis.prediction.predicted_home_goals }} - {{ analysis.prediction.predicted_away_goals }}</b>
                  </div>
                </div>
              </div>
              <div class="card" v-if="analysis.score_prediction">
                <div class="card-header"><h4>比分预测</h4></div>
                <div class="card-body">
                  <div class="most-likely">
                    <span class="score-big">{{ analysis.score_prediction.most_likely?.home }} - {{ analysis.score_prediction.most_likely?.away }}</span>
                    <span class="result-tag" :class="analysis.score_prediction.most_likely?.result === '主胜' ? 'home-win' : analysis.score_prediction.most_likely?.result === '客胜' ? 'away-win' : 'draw'">
                      {{ analysis.score_prediction.most_likely?.result }}
                    </span>
                  </div>
                  <div class="other-scores" v-if="analysis.score_prediction.possible_scores?.length > 1">
                    <span class="small-label">其他可能</span>
                    <div class="score-chips">
                      <span v-for="(s, i) in analysis.score_prediction.possible_scores?.slice(1, 4)" :key="i" class="chip">
                        {{ s.home }}-{{ s.away }} <small>{{ s.probability }}%</small>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- 近期战绩对比（左右对比） -->
          <section class="section-block">
            <div class="section-title"><TrendingIcon /><span>近期战绩</span></div>
            <div class="compare-cards">
              <div class="compare-card">
                <div class="compare-header">{{ analysis.match?.home_team_cn || '主队' }}</div>
                <div class="compare-body">
                  <div class="form-numbers"><span class="win">{{ homeForm?.wins || 0 }}</span><span class="draw">{{ homeForm?.draws || 0 }}</span><span class="loss">{{ homeForm?.losses || 0 }}</span></div>
                  <div class="form-labels"><span>胜</span><span>平</span><span>负</span></div>
                  <div class="form-goals">进{{ homeForm?.goals_for || 0 }} / 失{{ homeForm?.goals_against || 0 }}</div>
                  <div class="form-pts">场均{{ avgPoints(homeForm) }}分</div>
                </div>
              </div>
              <div class="vs-divider">VS</div>
              <div class="compare-card">
                <div class="compare-header">{{ analysis.match?.away_team_cn || '客队' }}</div>
                <div class="compare-body">
                  <div class="form-numbers"><span class="win">{{ awayForm?.wins || 0 }}</span><span class="draw">{{ awayForm?.draws || 0 }}</span><span class="loss">{{ awayForm?.losses || 0 }}</span></div>
                  <div class="form-labels"><span>胜</span><span>平</span><span>负</span></div>
                  <div class="form-goals">进{{ awayForm?.goals_for || 0 }} / 失{{ awayForm?.goals_against || 0 }}</div>
                  <div class="form-pts">场均{{ avgPoints(awayForm) }}分</div>
                </div>
              </div>
            </div>
          </section>

          <!-- 主客场表现（左右对比） -->
          <section class="section-block">
            <div class="section-title"><HomeIcon /><span>主客场表现</span></div>
            <div class="compare-cards">
              <div class="compare-card">
                <div class="compare-header">{{ analysis.match?.home_team_cn || '主队' }} 主场</div>
                <div class="compare-body">
                  <div class="form-numbers"><span class="win">{{ homeHomeStats?.wins || 0 }}</span><span class="draw">{{ homeHomeStats?.draws || 0 }}</span><span class="loss">{{ homeHomeStats?.losses || 0 }}</span></div>
                  <div class="form-labels"><span>胜</span><span>平</span><span>负</span></div>
                  <div class="form-goals">进{{ homeHomeStats?.goals_for || 0 }} / 失{{ homeHomeStats?.goals_against || 0 }}</div>
                  <div class="form-pts">场均{{ avgPoints(homeHomeStats) }}分</div>
                </div>
              </div>
              <div class="vs-divider">VS</div>
              <div class="compare-card">
                <div class="compare-header">{{ analysis.match?.away_team_cn || '客队' }} 客场</div>
                <div class="compare-body">
                  <div class="form-numbers"><span class="win">{{ awayAwayStats?.wins || 0 }}</span><span class="draw">{{ awayAwayStats?.draws || 0 }}</span><span class="loss">{{ awayAwayStats?.losses || 0 }}</span></div>
                  <div class="form-labels"><span>胜</span><span>平</span><span>负</span></div>
                  <div class="form-goals">进{{ awayAwayStats?.goals_for || 0 }} / 失{{ awayAwayStats?.goals_against || 0 }}</div>
                  <div class="form-pts">场均{{ avgPoints(awayAwayStats) }}分</div>
                </div>
              </div>
            </div>
          </section>

          <!-- 半场战绩（左右对比） -->
          <section class="section-block" v-if="analysis.ht_stats">
            <div class="section-title"><HalfIcon /><span>半场战绩</span></div>
            <div class="compare-cards">
              <div class="compare-card">
                <div class="compare-header">{{ analysis.match?.home_team_cn || '主队' }}</div>
                <div class="compare-body">
                  <div class="form-numbers"><span class="win">{{ analysis.ht_stats?.home?.wins || 0 }}</span><span class="draw">{{ analysis.ht_stats?.home?.draws || 0 }}</span><span class="loss">{{ analysis.ht_stats?.home?.losses || 0 }}</span></div>
                  <div class="form-labels"><span>胜</span><span>平</span><span>负</span></div>
                </div>
              </div>
              <div class="vs-divider">VS</div>
              <div class="compare-card">
                <div class="compare-header">{{ analysis.match?.away_team_cn || '客队' }}</div>
                <div class="compare-body">
                  <div class="form-numbers"><span class="win">{{ analysis.ht_stats?.away?.wins || 0 }}</span><span class="draw">{{ analysis.ht_stats?.away?.draws || 0 }}</span><span class="loss">{{ analysis.ht_stats?.away?.losses || 0 }}</span></div>
                  <div class="form-labels"><span>胜</span><span>平</span><span>负</span></div>
                </div>
              </div>
            </div>
          </section>

          <!-- 进球时间分布 -->
          <section class="section-block" v-if="analysis.goal_timing">
            <div class="section-title"><ClockIcon /><span>进球时间分布</span></div>
            <div class="timing-simple">
              <div class="timing-header">
                <span class="t-team">{{ analysis.match?.home_team_cn || '主队' }}</span>
                <span class="t-team">{{ analysis.match?.away_team_cn || '客队' }}</span>
              </div>
              <div class="timing-periods-row">
                <div class="t-period" v-for="(p, idx) in ['0-15','16-30','31-45','46-60','61-75','76-90']" :key="idx">
                  <span class="p-label">{{ p }}'</span>
                  <span class="p-home">{{ (analysis.goal_timing?.home?.by_period || [0,0,0,0,0,0])[idx] || 0 }}</span>
                  <span class="p-away">{{ (analysis.goal_timing?.away?.by_period || [0,0,0,0,0,0])[idx] || 0 }}</span>
                </div>
              </div>
            </div>
          </section>

          <!-- 进攻与大小球 -->
          <section class="section-block" v-if="analysis.attack_efficiency || analysis.over_under">
            <div class="section-title"><TargetIcon /><span>进攻与大小球</span></div>
            <div class="cards-row">
              <div class="card" v-if="analysis.attack_efficiency">
                <div class="card-header"><h4>进攻效率</h4></div>
                <div class="card-body">
                  <div class="eff-compare"><span class="eff-label">进攻:</span><span class="eff-value">{{ analysis.attack_efficiency.attack_comparison }}</span></div>
                  <div class="eff-compare"><span class="eff-label">防守:</span><span class="eff-value">{{ analysis.attack_efficiency.defense_comparison }}</span></div>
                  <div class="eff-teams">
                    <div class="eff-team"><span class="name">主</span><span class="stat">{{ analysis.attack_efficiency.home?.avg_goals }}球/场</span></div>
                    <div class="eff-team"><span class="name">客</span><span class="stat">{{ analysis.attack_efficiency.away?.avg_goals }}球/场</span></div>
                  </div>
                </div>
              </div>
              <div class="card" v-if="analysis.over_under">
                <div class="card-header"><h4>大小球</h4></div>
                <div class="card-body">
                  <div class="ou-pred"><span class="ou-label">预测总进球</span><span class="ou-value">{{ analysis.over_under.predicted_total_goals }} 球</span></div>
                  <div class="ou-bars">
                    <div class="ou-row"><span>大2.5</span><div class="bar-container"><div class="bar over" :style="{ width: analysis.over_under.over_2_5_prob + '%' }"></div></div><span>{{ analysis.over_under.over_2_5_prob }}%</span></div>
                    <div class="ou-row"><span>小2.5</span><div class="bar-container"><div class="bar under" :style="{ width: analysis.over_under.under_2_5_prob + '%' }"></div></div><span>{{ analysis.over_under.under_2_5_prob }}%</span></div>
                  </div>
                  <div class="ou-rec"><span class="rec-label">推荐:</span><span class="rec-value">{{ analysis.over_under.recommendation }}</span></div>
                </div>
              </div>
            </div>
          </section>

          <!-- 球队动态 -->
          <section class="section-block" v-if="analysis.team_news && (analysis.team_news.home?.length || analysis.team_news.away?.length)">
            <div class="section-title"><NewsIcon /><span>球队动态</span></div>
            <div class="news-grid">
              <div class="news-col" v-if="analysis.team_news?.home?.length">
                <div class="news-team">{{ analysis.match?.home_team_cn || '主队' }}</div>
                <div class="news-list">
                  <div v-for="(news, i) in analysis.team_news.home.slice(0, 3)" :key="i" class="news-item" :class="news.impact">
                    <span class="news-icon">{{ news.impact === 'positive' ? '✓' : news.impact === 'negative' ? '✗' : '○' }}</span>
                    <span class="news-text">{{ news.text }}</span>
                  </div>
                </div>
              </div>
              <div class="news-col" v-if="analysis.team_news?.away?.length">
                <div class="news-team">{{ analysis.match?.away_team_cn || '客队' }}</div>
                <div class="news-list">
                  <div v-for="(news, i) in analysis.team_news.away.slice(0, 3)" :key="i" class="news-item" :class="news.impact">
                    <span class="news-icon">{{ news.impact === 'positive' ? '✓' : news.impact === 'negative' ? '✗' : '○' }}</span>
                    <span class="news-text">{{ news.text }}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- 右列 -->
        <div class="column">
          <!-- Elo实力对比 -->
          <section class="section-block">
            <div class="section-title"><StarIcon /><span>Elo实力</span></div>
            <div class="elo-compare">
              <div class="elo-side home">
                <span class="elo-num">{{ analysis.elo?.home || '--' }}</span>
                <span class="elo-team">{{ analysis.match?.home_team_cn || '主队' }}</span>
              </div>
              <div class="elo-vs">VS</div>
              <div class="elo-side away">
                <span class="elo-num">{{ analysis.elo?.away || '--' }}</span>
                <span class="elo-team">{{ analysis.match?.away_team_cn || '客队' }}</span>
              </div>
            </div>
            <div class="elo-hint" v-if="analysis.elo?.diff">{{ analysis.elo.diff > 50 ? '主队明显占优' : analysis.elo.diff < -50 ? '客队明显占优' : '实力接近' }}</div>
          </section>

          <!-- 历史交锋 -->
          <section class="section-block">
            <div class="section-title"><SwordsIcon /><span>历史交锋</span></div>
            <div class="h2h-summary" v-if="analysis.h2h?.stats">
              <div class="h2h-item home-win"><b>{{ analysis.h2h.stats.home_wins }}</b><span>主胜</span></div>
              <div class="h2h-item draw"><b>{{ analysis.h2h.stats.draws }}</b><span>平局</span></div>
              <div class="h2h-item away-win"><b>{{ analysis.h2h.stats.away_wins }}</b><span>客胜</span></div>
            </div>
            <div class="h2h-recent" v-if="analysis.h2h?.matches?.length">
              <div class="h2h-row" v-for="game in analysis.h2h.matches.slice(0, 5)" :key="game.match_id">
                <span class="date">{{ game.match_date }}</span>
                <span class="teams">{{ game.home_team_cn || game.home_team }} vs {{ game.away_team_cn || game.away_team }}</span>
                <span class="result">{{ game.home_goals }}-{{ game.away_goals }}</span>
              </div>
            </div>
            <div v-else class="no-data">暂无交锋记录</div>
            <!-- 心理压制 -->
            <div class="psychology-section" v-if="analysis.psychology">
              <div class="psy-title">心理压制</div>
              <p class="psy-desc">{{ analysis.psychology.description }}</p>
            </div>
          </section>

          <!-- 敌对关系 -->
          <section class="section-block" v-if="analysis.rivalry">
            <div class="section-title"><FireIcon /><span>敌对关系</span></div>
            <div class="rivalry-content">
              <div class="rivalry-level" :class="analysis.rivalry.level === '普通' ? '' : 'hot'">{{ analysis.rivalry.level }}</div>
              <p class="rivalry-desc">{{ analysis.rivalry.description }}</p>
              <div class="rivalry-indicators" v-if="analysis.rivalry.indicators?.length">
                <span v-for="(ind, i) in analysis.rivalry.indicators" :key="i" class="indicator-tag">{{ ind }}</span>
              </div>
            </div>
          </section>

          <!-- 关键理由 -->
          <section class="section-block" v-if="analysis.critical_reasons">
            <div class="section-title"><AlertIcon /><span>关键理由</span></div>
            <div class="reasons-grid">
              <div class="reason-col">
                <div class="reason-team">{{ analysis.match?.home_team_cn || '主队' }}</div>
                <div class="reasons-list">
                  <div v-for="(r, i) in [...(analysis.critical_reasons.home?.must_win || []), ...(analysis.critical_reasons.home?.must_not_lose || [])]" :key="i" class="reason-item must">
                    <span class="reason-icon">!</span><span>{{ r }}</span>
                  </div>
                  <div v-for="(r, i) in (analysis.critical_reasons.home?.can_afford_loss || [])" :key="'a'+i" class="reason-item can">
                    <span class="reason-icon">○</span><span>{{ r }}</span>
                  </div>
                  <div v-if="!analysis.critical_reasons.home?.must_win?.length && !analysis.critical_reasons.home?.must_not_lose?.length && !analysis.critical_reasons.home?.can_afford_loss?.length" class="no-reason">暂无特殊压力</div>
                </div>
              </div>
              <div class="reason-col">
                <div class="reason-team">{{ analysis.match?.away_team_cn || '客队' }}</div>
                <div class="reasons-list">
                  <div v-for="(r, i) in [...(analysis.critical_reasons.away?.must_win || []), ...(analysis.critical_reasons.away?.must_not_lose || [])]" :key="i" class="reason-item must">
                    <span class="reason-icon">!</span><span>{{ r }}</span>
                  </div>
                  <div v-for="(r, i) in (analysis.critical_reasons.away?.can_afford_loss || [])" :key="'a'+i" class="reason-item can">
                    <span class="reason-icon">○</span><span>{{ r }}</span>
                  </div>
                  <div v-if="!analysis.critical_reasons.away?.must_win?.length && !analysis.critical_reasons.away?.must_not_lose?.length && !analysis.critical_reasons.away?.can_afford_loss?.length" class="no-reason">暂无特殊压力</div>
                </div>
              </div>
            </div>
          </section>

          <!-- 未来赛程 -->
          <section class="section-block" v-if="analysis.future_fixtures">
            <div class="section-title"><CalendarIcon /><span>未来赛程</span></div>
            <div class="fixtures-grid">
              <div class="fixture-col">
                <div class="fixture-team">{{ analysis.match?.home_team_cn || '主队' }}</div>
                <div class="fixtures-list" v-if="analysis.future_fixtures.home_next?.length">
                  <div v-for="(f, i) in analysis.future_fixtures.home_next.slice(0, 3)" :key="i" class="fixture-item">
                    <span class="f-date">{{ f.date }}</span>
                    <span class="f-venue" :class="f.venue === '主场' ? 'home' : 'away'">{{ f.venue }}</span>
                    <span class="f-opponent">vs {{ f.opponent_cn || f.opponent }}</span>
                  </div>
                </div>
                <div v-else class="no-data">暂无</div>
              </div>
              <div class="fixture-col">
                <div class="fixture-team">{{ analysis.match?.away_team_cn || '客队' }}</div>
                <div class="fixtures-list" v-if="analysis.future_fixtures.away_next?.length">
                  <div v-for="(f, i) in analysis.future_fixtures.away_next.slice(0, 3)" :key="i" class="fixture-item">
                    <span class="f-date">{{ f.date }}</span>
                    <span class="f-venue" :class="f.venue === '主场' ? 'home' : 'away'">{{ f.venue }}</span>
                    <span class="f-opponent">vs {{ f.opponent_cn || f.opponent }}</span>
                  </div>
                </div>
                <div v-else class="no-data">暂无</div>
              </div>
            </div>
          </section>

          <!-- 休息天数（左右对比） -->
          <section class="section-block" v-if="analysis.rest_days">
            <div class="section-title"><RestIcon /><span>休息天数</span></div>
            <div class="compare-cards">
              <div class="compare-card">
                <div class="compare-header">{{ analysis.match?.home_team_cn || '主队' }}</div>
                <div class="compare-body">
                  <div class="rest-num">{{ analysis.rest_days.home ?? '-' }}<span class="unit">天</span></div>
                </div>
              </div>
              <div class="vs-divider" v-if="analysis.rest_days.diff">{{ analysis.rest_days.diff > 0 ? '主队多' + analysis.rest_days.diff + '天' : analysis.rest_days.diff < 0 ? '客队多' + Math.abs(analysis.rest_days.diff) + '天' : '相同' }}</div>
              <div class="vs-divider" v-else>-</div>
              <div class="compare-card">
                <div class="compare-header">{{ analysis.match?.away_team_cn || '客队' }}</div>
                <div class="compare-body">
                  <div class="rest-num">{{ analysis.rest_days.away ?? '-' }}<span class="unit">天</span></div>
                </div>
              </div>
            </div>
          </section>

          <!-- 投注分析 -->
          <section class="section-block" v-if="analysis.betting_analysis || analysis.odds_analysis">
            <div class="section-title"><DollarIcon /><span>投注分析</span></div>
            <div class="card" v-if="analysis.betting_analysis">
              <div class="card-header"><h4>胜平负概率</h4></div>
              <div class="card-body">
                <div class="prob-bars">
                  <div class="prob-row home"><span class="label">主胜</span><div class="bar-container"><div class="bar" :style="{ width: analysis.betting_analysis.home_win_prob + '%' }"></div></div><span class="value">{{ analysis.betting_analysis.home_win_prob }}%</span></div>
                  <div class="prob-row draw"><span class="label">平局</span><div class="bar-container"><div class="bar" :style="{ width: analysis.betting_analysis.draw_prob + '%' }"></div></div><span class="value">{{ analysis.betting_analysis.draw_prob }}%</span></div>
                  <div class="prob-row away"><span class="label">客胜</span><div class="bar-container"><div class="bar" :style="{ width: analysis.betting_analysis.away_win_prob + '%' }"></div></div><span class="value">{{ analysis.betting_analysis.away_win_prob }}%</span></div>
                </div>
                <div class="bet-recs" v-if="analysis.betting_analysis.recommendations?.length">
                  <span class="rec-label">建议</span>
                  <div class="rec-chips">
                    <span v-for="(r, i) in analysis.betting_analysis.recommendations.slice(0, 3)" :key="i" class="rec-chip" :class="r.confidence === '高' ? 'high' : ''">{{ r.type }} {{ r.prob }}%</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="card" v-if="analysis.odds_analysis">
              <div class="card-header"><h4>赔率分析</h4></div>
              <div class="card-body">
                <template v-if="analysis.odds_analysis.has_odds">
                  <div class="odds-grid">
                    <div class="odds-item"><span class="type">主胜</span><span class="odds">{{ analysis.odds_analysis.home_odds }}</span><span class="implied">{{ analysis.odds_analysis.home_implied }}%</span></div>
                    <div class="odds-item"><span class="type">平局</span><span class="odds">{{ analysis.odds_analysis.draw_odds }}</span><span class="implied">{{ analysis.odds_analysis.draw_implied }}%</span></div>
                    <div class="odds-item"><span class="type">客胜</span><span class="odds">{{ analysis.odds_analysis.away_odds }}</span><span class="implied">{{ analysis.odds_analysis.away_implied }}%</span></div>
                  </div>
                  <div class="value-bets" v-if="analysis.odds_analysis.value_bets?.length">
                    <span class="vb-label">价值投注</span>
                    <div class="vb-list"><span v-for="(v, i) in analysis.odds_analysis.value_bets.slice(0, 2)" :key="i" class="vb-item">{{ v.type }} +{{ v.value }}%</span></div>
                  </div>
                </template>
                <template v-else>
                  <div class="est-odds"><span class="est-label">模型估算赔率</span><div class="est-grid"><span>主胜 {{ analysis.odds_analysis.estimated_home_odds }}</span><span>平局 {{ analysis.odds_analysis.estimated_draw_odds }}</span><span>客胜 {{ analysis.odds_analysis.estimated_away_odds }}</span></div></div>
                </template>
              </div>
            </div>
          </section>

          <!-- 比赛重要性 & 近期走势 -->
          <section class="section-block" v-if="analysis.match_importance || analysis.recent_trend">
            <div class="section-title"><InfoIcon /><span>其他信息</span></div>
            <div class="info-grid">
              <div class="info-item" v-if="analysis.match_importance">
                <span class="info-label">比赛重要性</span>
                <span class="info-value">{{ analysis.match_importance.importance }}</span>
              </div>
              <div class="info-item" v-if="analysis.recent_trend">
                <span class="info-label">近期走势</span>
                <span class="info-value">主{{ analysis.recent_trend.home?.last10?.form }} / 客{{ analysis.recent_trend.away?.last10?.form }}</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { matchAPI } from '../api'

const BrainIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.54' }), h('path', { d: 'M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.54' })])
const TrendingIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('polyline', { points: '23 6 13.5 15.5 8.5 10.5 1 18' }), h('polyline', { points: '17 6 23 6 23 12' })])
const HomeIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z' }), h('polyline', { points: '9 22 9 12 15 12 15 22' })])
const SwordsIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('polyline', { points: '14.5 17.5 3 6 3 3 6 3 17.5 14.5' }), h('line', { x1: '13', y1: '19', x2: '19', y2: '13' }), h('line', { x1: '16', y1: '16', x2: '20', y2: '20' })])
const TargetIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('circle', { cx: '12', cy: '12', r: '10' }), h('circle', { cx: '12', cy: '12', r: '6' }), h('circle', { cx: '12', cy: '12', r: '2' })])
const DollarIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('line', { x1: '12', y1: '1', x2: '12', y2: '23' }), h('path', { d: 'M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6' })])
const StarIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' })])
const AlertIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z' }), h('line', { x1: '12', y1: '9', x2: '12', y2: '13' }), h('line', { x1: '12', y1: '17', x2: '12.01', y2: '17' })])
const CalendarIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }), h('line', { x1: '16', y1: '2', x2: '16', y2: '6' }), h('line', { x1: '8', y1: '2', x2: '8', y2: '6' }), h('line', { x1: '3', y1: '10', x2: '21', y2: '10' })])
const FireIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z' })])
const InfoIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('circle', { cx: '12', cy: '12', r: '10' }), h('line', { x1: '12', y1: '16', x2: '12', y2: '12' }), h('line', { x1: '12', y1: '8', x2: '12.01', y2: '8' })])
const ClockIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('circle', { cx: '12', cy: '12', r: '10' }), h('polyline', { points: '12 6 12 12 16 14' })])
const HalfIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2', ry: '2' }), h('line', { x1: '12', y1: '3', x2: '12', y2: '21' })])
const NewsIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M19 20H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1m2 13a2 2 0 0 1-2-2V7m2 13a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2' })])
const RestIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M5 12h14' }), h('path', { d: 'M12 5v14' })])
const ArrowLeftIcon = () => h('svg', { class: 'icon-sm', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('line', { x1: '19', y1: '12', x2: '5', y2: '12' }), h('polyline', { points: '12 19 5 12 12 5' })])

export default {
  name: 'MatchPage',
  components: { BrainIcon, TrendingIcon, HomeIcon, SwordsIcon, TargetIcon, DollarIcon, StarIcon, AlertIcon, CalendarIcon, FireIcon, InfoIcon, ClockIcon, HalfIcon, NewsIcon, RestIcon, ArrowLeftIcon },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const loading = ref(true)
    const error = ref(null)
    const analysis = ref({})
    const selectedPeriod = ref('last10')

    const goBack = () => router.push('/')
    const matchStatus = computed(() => analysis.value.match?.home_goals === null ? 'upcoming' : 'finished')
    const statusText = computed(() => analysis.value.match?.home_goals === null ? '未开始' : '已结束')
    const goToTeam = (teamId) => { if (teamId) router.push(`/team/${teamId}`) }

    // 根据选择的时间段获取数据 - 联动更新
    const homeForm = computed(() => analysis.value.form?.home?.[selectedPeriod.value])
    const awayForm = computed(() => analysis.value.form?.away?.[selectedPeriod.value])
    const homeHomeStats = computed(() => analysis.value.home_away?.home_at_home?.[selectedPeriod.value])
    const awayAwayStats = computed(() => analysis.value.home_away?.away_at_away?.[selectedPeriod.value])

    const avgPoints = (stats) => {
      if (!stats || !stats.matches) return '0.00'
      const pts = ((stats.wins || 0) * 3 + (stats.draws || 0)) / stats.matches
      return pts.toFixed(2)
    }

    const loadAnalysis = async () => {
      try {
        loading.value = true
        const data = await matchAPI.getFullAnalysis(route.params.id)
        if (data.error) error.value = data.error
        else analysis.value = data.data || {}
      } catch (e) {
        error.value = '加载分析数据失败'
      } finally {
        loading.value = false
      }
    }

    onMounted(loadAnalysis)
    return { loading, error, analysis, matchStatus, statusText, goToTeam, goBack, selectedPeriod, homeForm, awayForm, homeHomeStats, awayAwayStats, avgPoints }
  }
}
</script>

<style scoped>
.match-page { display: flex; flex-direction: column; gap: 12px; max-width: 1100px; margin: 0 auto; }

.back-header { margin-bottom: 4px; }
.back-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; color: #10b981; font-size: 13px; cursor: pointer; }
.back-btn:hover { background: rgba(16, 185, 129, 0.2); }
.icon-sm { width: 12px; height: 12px; }

.loading, .error-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; color: #6b7280; }
.spinner { width: 32px; height: 32px; border: 3px solid rgba(16, 185, 129, 0.2); border-top-color: #10b981; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 12px; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 比赛头部 */
.match-header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 12px; padding: 16px; border: 1px solid rgba(31, 41, 55, 0.5); }
.league-info { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.league-name { color: #10b981; font-weight: 600; font-size: 15px; }
.match-date { color: #6b7280; font-size: 13px; }
.match-teams { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.team { flex: 1; text-align: center; cursor: pointer; padding: 10px; border-radius: 8px; transition: background 0.2s; }
.team:hover { background: rgba(255,255,255,0.05); }
.team-name { font-size: 18px; font-weight: 600; color: #f3f4f6; display: block; margin-bottom: 4px; }
.elo-tag { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
.elo-tag.home { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.elo-tag.away { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.score-section { text-align: center; }
.scores { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 4px; }
.score { font-size: 28px; font-weight: 700; color: #f3f4f6; min-width: 36px; }
.separator { font-size: 20px; color: #4b5563; }
.vs-info { display: flex; flex-direction: column; align-items: center; gap: 2px; margin-bottom: 4px; }
.vs-text { font-size: 12px; color: #6b7280; font-weight: 600; }
.match-time { font-size: 13px; color: #10b981; font-weight: 500; }
.status { font-size: 11px; padding: 3px 10px; border-radius: 10px; display: inline-block; }
.status.finished { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.status.upcoming { background: rgba(16, 185, 129, 0.15); color: #10b981; }

/* 时间段选择器 */
.period-selector { display: flex; gap: 8px; justify-content: center; margin-bottom: 8px; }
.period-btn { padding: 8px 20px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; color: #9ca3af; font-size: 13px; cursor: pointer; transition: all 0.2s; }
.period-btn:hover { background: rgba(255,255,255,0.1); }
.period-btn.active { background: rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.5); color: #10b981; font-weight: 600; }

/* 两列大布局 */
.two-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.column { display: flex; flex-direction: column; gap: 12px; }

/* 区域块 */
.section-block { background: #151922; border-radius: 10px; border: 1px solid rgba(31, 41, 55, 0.5); overflow: hidden; }
.section-title { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: rgba(255,255,255,0.02); border-bottom: 1px solid rgba(31, 41, 55, 0.5); font-size: 14px; font-weight: 600; color: #e5e7eb; }
.section-title .icon { width: 16px; height: 16px; color: #10b981; }

/* 卡片行布局 */
.cards-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: rgba(31, 41, 55, 0.3); }
.cards-row .card { background: #151922; border-bottom: none; }

/* 卡片 */
.card { border-bottom: 1px solid rgba(31, 41, 55, 0.3); }
.card:last-child { border-bottom: none; }
.card-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: rgba(255,255,255,0.01); }
.card-header h4 { font-size: 12px; font-weight: 600; color: #9ca3af; }
.card-body { padding: 10px 12px; }

/* 对比卡片（左右对比） */
.compare-cards { display: grid; grid-template-columns: 1fr auto 1fr; gap: 8px; padding: 10px; }
.compare-card { background: rgba(255,255,255,0.02); border-radius: 8px; padding: 10px; text-align: center; }
.compare-header { font-size: 13px; font-weight: 600; color: #e5e7eb; margin-bottom: 8px; }
.compare-body { text-align: center; }
.vs-divider { display: flex; align-items: center; justify-content: center; font-size: 11px; color: #10b981; font-weight: 500; min-width: 60px; text-align: center; }

/* 战绩数字 */
.form-numbers { display: flex; justify-content: center; gap: 16px; margin-bottom: 4px; }
.form-numbers span { font-size: 24px; font-weight: 700; }
.form-numbers .win { color: #10b981; }
.form-numbers .draw { color: #9ca3af; }
.form-numbers .loss { color: #ef4444; }
.form-labels { display: flex; justify-content: center; gap: 22px; font-size: 12px; color: #6b7280; margin-bottom: 6px; }
.form-goals { font-size: 12px; color: #9ca3af; margin-bottom: 2px; }
.form-pts { font-size: 11px; color: #10b981; }

/* 休息天数 */
.rest-num { font-size: 28px; font-weight: 700; color: #e5e7eb; }
.rest-num .unit { font-size: 14px; color: #6b7280; margin-left: 2px; }

/* 预测条 */
.prediction-bars { margin-bottom: 8px; }
.pred-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.pred-row .label { min-width: 32px; font-size: 12px; color: #6b7280; }
.bar-container { flex: 1; height: 6px; background: #1c222f; border-radius: 3px; overflow: hidden; }
.bar { height: 100%; border-radius: 3px; }
.bar.home, .bar.over { background: linear-gradient(90deg, #10b981, #059669); }
.bar.draw { background: #4b5563; }
.bar.away, .bar.under { background: linear-gradient(90deg, #3b82f6, #2563eb); }
.pred-row .value { min-width: 32px; font-size: 12px; font-weight: 600; color: #e5e7eb; text-align: right; }
.predicted-score { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 6px; background: rgba(16, 185, 129, 0.1); border-radius: 6px; font-size: 12px; color: #6b7280; }
.predicted-score b { font-size: 16px; color: #10b981; }

/* 比分预测 */
.most-likely { text-align: center; padding: 8px; background: rgba(16, 185, 129, 0.1); border-radius: 8px; margin-bottom: 6px; }
.score-big { display: block; font-size: 22px; font-weight: 700; color: #10b981; margin-bottom: 4px; }
.result-tag { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.result-tag.home-win { background: rgba(16, 185, 129, 0.2); color: #10b981; }
.result-tag.away-win { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.result-tag.draw { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }
.small-label { display: block; font-size: 10px; color: #6b7280; margin-bottom: 4px; }
.score-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip { font-size: 10px; padding: 3px 6px; background: rgba(255,255,255,0.05); border-radius: 4px; color: #e5e7eb; }
.chip small { color: #6b7280; margin-left: 2px; }

/* Elo对比 */
.elo-compare { display: flex; align-items: center; justify-content: center; gap: 20px; padding: 16px; }
.elo-side { text-align: center; }
.elo-num { display: block; font-size: 28px; font-weight: 700; }
.elo-side.home .elo-num { color: #10b981; }
.elo-side.away .elo-num { color: #60a5fa; }
.elo-team { font-size: 12px; color: #9ca3af; }
.elo-vs { font-size: 13px; color: #4b5563; font-weight: 600; }
.elo-hint { text-align: center; font-size: 12px; color: #6b7280; padding: 8px; border-top: 1px solid rgba(31, 41, 55, 0.3); }

/* 历史交锋 */
.h2h-summary { display: flex; gap: 8px; padding: 10px; }
.h2h-item { flex: 1; text-align: center; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.h2h-item b { display: block; font-size: 22px; }
.h2h-item span { font-size: 11px; color: #6b7280; }
.h2h-item.home-win b { color: #10b981; }
.h2h-item.draw b { color: #9ca3af; }
.h2h-item.away-win b { color: #60a5fa; }
.h2h-recent { font-size: 11px; padding: 0 10px 10px; }
.h2h-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid rgba(31, 41, 55, 0.3); color: #6b7280; }
.h2h-row:last-child { border-bottom: none; }
.h2h-row .date { min-width: 70px; }
.h2h-row .teams { flex: 1; margin: 0 8px; color: #9ca3af; }
.h2h-row .result { color: #e5e7eb; font-weight: 500; min-width: 30px; text-align: right; }
.no-data { text-align: center; padding: 12px; color: #6b7280; font-size: 12px; }

/* 心理压制 */
.psychology-section { padding: 10px; border-top: 1px solid rgba(31, 41, 55, 0.3); }
.psy-title { font-size: 12px; font-weight: 600; color: #9ca3af; margin-bottom: 6px; }
.psy-desc { font-size: 12px; color: #e5e7eb; text-align: center; }

/* 敌对关系 */
.rivalry-content { padding: 12px; text-align: center; }
.rivalry-level { font-size: 18px; font-weight: 600; color: #e5e7eb; margin-bottom: 6px; }
.rivalry-level.hot { color: #ef4444; }
.rivalry-desc { font-size: 12px; color: #6b7280; margin-bottom: 8px; }
.rivalry-indicators { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
.indicator-tag { font-size: 11px; padding: 4px 10px; background: rgba(239, 68, 68, 0.15); color: #ef4444; border-radius: 12px; }

/* 关键理由 */
.reasons-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: rgba(31, 41, 55, 0.3); }
.reason-col { background: #151922; padding: 10px; }
.reason-team { font-size: 13px; font-weight: 600; color: #e5e7eb; margin-bottom: 8px; text-align: center; }
.reasons-list { display: flex; flex-direction: column; gap: 4px; }
.reason-item { display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: rgba(255,255,255,0.02); border-radius: 4px; font-size: 11px; color: #e5e7eb; }
.reason-item.must { border-left: 2px solid #ef4444; }
.reason-item.can { border-left: 2px solid #6b7280; }
.reason-icon { font-size: 10px; font-weight: 700; }
.reason-item.must .reason-icon { color: #ef4444; }
.reason-item.can .reason-icon { color: #6b7280; }
.no-reason { text-align: center; padding: 8px; color: #6b7280; font-size: 11px; }

/* 未来赛程 */
.fixtures-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: rgba(31, 41, 55, 0.3); }
.fixture-col { background: #151922; padding: 10px; }
.fixture-team { font-size: 13px; font-weight: 600; color: #e5e7eb; margin-bottom: 8px; text-align: center; }
.fixtures-list { display: flex; flex-direction: column; gap: 4px; }
.fixture-item { display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: rgba(255,255,255,0.02); border-radius: 4px; font-size: 11px; }
.f-date { color: #6b7280; min-width: 65px; }
.f-venue { padding: 2px 6px; border-radius: 4px; font-size: 10px; }
.f-venue.home { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.f-venue.away { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.f-opponent { color: #e5e7eb; }

/* 进球时间分布 - 简洁版 */
.timing-simple { padding: 10px; }
.timing-header { display: flex; justify-content: space-between; margin-bottom: 8px; padding: 0 10px; }
.t-team { font-size: 12px; font-weight: 600; color: #e5e7eb; }
.timing-periods-row { display: flex; gap: 4px; }
.t-period { flex: 1; text-align: center; padding: 8px 4px; background: rgba(255,255,255,0.02); border-radius: 4px; }
.p-label { display: block; font-size: 10px; color: #6b7280; margin-bottom: 6px; }
.p-home { display: block; font-size: 14px; font-weight: 600; color: #10b981; margin-bottom: 2px; }
.p-away { display: block; font-size: 14px; font-weight: 600; color: #60a5fa; }

/* 球队动态 */
.news-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: rgba(31, 41, 55, 0.3); }
.news-col { background: #151922; padding: 10px; }
.news-team { font-size: 13px; font-weight: 600; color: #e5e7eb; margin-bottom: 8px; text-align: center; }
.news-list { display: flex; flex-direction: column; gap: 4px; }
.news-item { display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: rgba(255,255,255,0.02); border-radius: 4px; font-size: 11px; }
.news-item.positive { border-left: 2px solid #10b981; }
.news-item.negative { border-left: 2px solid #ef4444; }
.news-item.neutral { border-left: 2px solid #6b7280; }
.news-icon { font-size: 10px; }
.news-item.positive .news-icon { color: #10b981; }
.news-item.negative .news-icon { color: #ef4444; }
.news-item.neutral .news-icon { color: #6b7280; }
.news-text { color: #e5e7eb; }

/* 进攻效率 */
.eff-compare { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; font-size: 11px; }
.eff-label { color: #6b7280; }
.eff-value { color: #e5e7eb; font-weight: 500; }
.eff-teams { display: flex; gap: 8px; margin-top: 6px; }
.eff-team { flex: 1; text-align: center; padding: 6px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.eff-team .name { display: block; font-size: 11px; color: #6b7280; margin-bottom: 2px; }
.eff-team .stat { font-size: 13px; font-weight: 600; color: #e5e7eb; }

/* 大小球 */
.ou-pred { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.ou-label { font-size: 11px; color: #6b7280; }
.ou-value { font-size: 16px; font-weight: 700; color: #fbbf24; }
.ou-bars { margin-bottom: 6px; }
.ou-row { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; font-size: 11px; color: #6b7280; }
.ou-row .bar-container { height: 4px; }
.ou-rec { display: flex; align-items: center; gap: 6px; font-size: 11px; }
.rec-label { color: #6b7280; }
.rec-value { color: #10b981; font-weight: 600; }

/* 概率条 */
.prob-bars { margin-bottom: 6px; }
.prob-row { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.prob-row .label { min-width: 32px; font-size: 11px; color: #6b7280; }
.prob-row .bar-container { height: 5px; }
.prob-row .bar { height: 100%; border-radius: 3px; }
.prob-row.home .bar { background: linear-gradient(90deg, #10b981, #059669); }
.prob-row.draw .bar { background: #4b5563; }
.prob-row.away .bar { background: linear-gradient(90deg, #3b82f6, #2563eb); }
.prob-row .value { min-width: 28px; font-size: 11px; font-weight: 600; color: #e5e7eb; text-align: right; }
.bet-recs { margin-top: 6px; }
.bet-recs .rec-label { display: block; font-size: 10px; color: #6b7280; margin-bottom: 4px; }
.rec-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.rec-chip { font-size: 10px; padding: 3px 6px; background: rgba(255,255,255,0.05); border-radius: 4px; color: #9ca3af; }
.rec-chip.high { background: rgba(16, 185, 129, 0.15); color: #10b981; }

/* 赔率 */
.odds-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 6px; }
.odds-item { text-align: center; padding: 8px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.odds-item .type { display: block; font-size: 10px; color: #6b7280; margin-bottom: 2px; }
.odds-item .odds { display: block; font-size: 18px; font-weight: 700; color: #fbbf24; margin-bottom: 2px; }
.odds-item .implied { font-size: 9px; color: #6b7280; }
.value-bets { padding: 8px; background: rgba(16, 185, 129, 0.1); border-radius: 6px; }
.vb-label { display: block; font-size: 10px; color: #10b981; margin-bottom: 4px; }
.vb-list { display: flex; gap: 6px; }
.vb-item { font-size: 11px; padding: 3px 6px; background: rgba(16, 185, 129, 0.2); border-radius: 4px; color: #10b981; }
.est-odds { text-align: center; }
.est-label { display: block; font-size: 10px; color: #6b7280; margin-bottom: 6px; }
.est-grid { display: flex; justify-content: center; gap: 12px; font-size: 12px; color: #fbbf24; }

/* 其他信息 */
.info-grid { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px; }
.info-item { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: rgba(255,255,255,0.02); border-radius: 6px; font-size: 12px; }
.info-label { color: #6b7280; }
.info-value { color: #e5e7eb; font-weight: 500; }

/* 响应式 */
@media (max-width: 900px) {
  .two-columns { grid-template-columns: 1fr; }
  .match-teams { flex-direction: column; gap: 10px; }
  .team { width: 100%; }
  .compare-cards { grid-template-columns: 1fr; }
  .vs-divider { display: none; }
  .cards-row { grid-template-columns: 1fr; }
  .reasons-grid { grid-template-columns: 1fr; }
  .fixtures-grid { grid-template-columns: 1fr; }
  .news-grid { grid-template-columns: 1fr; }
}
</style>
