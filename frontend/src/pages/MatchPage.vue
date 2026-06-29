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
    <div v-else>
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
                <div v-if="analysis.odds_analysis.has_odds">
                  <div class="odds-grid">
                    <div class="odds-item"><span class="type">主胜</span><span class="odds">{{ analysis.odds_analysis.home_odds }}</span><span class="implied">{{ analysis.odds_analysis.home_implied }}%</span></div>
                    <div class="odds-item"><span class="type">平局</span><span class="odds">{{ analysis.odds_analysis.draw_odds }}</span><span class="implied">{{ analysis.odds_analysis.draw_implied }}%</span></div>
                    <div class="odds-item"><span class="type">客胜</span><span class="odds">{{ analysis.odds_analysis.away_odds }}</span><span class="implied">{{ analysis.odds_analysis.away_implied }}%</span></div>
                  </div>
                  <div class="value-bets" v-if="analysis.odds_analysis.value_bets?.length">
                    <span class="vb-label">价值投注</span>
                    <div class="vb-list"><span v-for="(v, i) in analysis.odds_analysis.value_bets.slice(0, 2)" :key="i" class="vb-item">{{ v.type }} +{{ v.value }}%</span></div>
                  </div>
                </div>
                <div v-else>
                  <div class="est-odds"><span class="est-label">模型估算赔率</span><div class="est-grid"><span>主胜 {{ analysis.odds_analysis.estimated_home_odds }}</span><span>平局 {{ analysis.odds_analysis.estimated_draw_odds }}</span><span>客胜 {{ analysis.odds_analysis.estimated_away_odds }}</span></div></div>
                </div>
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

          <!-- 天气数据 -->
          <section class="section-block" v-if="analysis.weather">
            <div class="section-title"><CloudIcon /><span>比赛天气</span></div>
            <div class="weather-content">
              <div class="weather-main">
                <div class="weather-temp">
                  <span class="temp-value">{{ analysis.weather.temperature }}°C</span>
                  <span class="temp-desc">{{ analysis.weather.weather_description }}</span>
                </div>
                <div class="weather-details">
                  <div class="w-item"><span class="w-label">湿度</span><span class="w-value">{{ analysis.weather.humidity }}%</span></div>
                  <div class="w-item"><span class="w-label">风速</span><span class="w-value">{{ analysis.weather.wind_speed }} m/s</span></div>
                </div>
              </div>
              <div class="weather-impact" v-if="analysis.weather.impact">
                <div class="impact-title">天气影响</div>
                <div class="impact-factors">
                  <div class="impact-item">
                    <span class="i-label">进球</span>
                    <span class="i-value" :class="analysis.weather.impact.goal_factor < 1 ? 'negative' : ''">{{ (analysis.weather.impact.goal_factor * 100).toFixed(0) }}%</span>
                  </div>
                  <div class="impact-item">
                    <span class="i-label">体能</span>
                    <span class="i-value" :class="analysis.weather.impact.stamina_factor < 1 ? 'negative' : ''">{{ (analysis.weather.impact.stamina_factor * 100).toFixed(0) }}%</span>
                  </div>
                  <div class="impact-item">
                    <span class="i-label">传球</span>
                    <span class="i-value" :class="analysis.weather.impact.pass_factor < 1 ? 'negative' : ''">{{ (analysis.weather.impact.pass_factor * 100).toFixed(0) }}%</span>
                  </div>
                </div>
                <div class="impact-desc" v-if="analysis.weather.impact.description?.length">
                  <span v-for="(desc, i) in analysis.weather.impact.description.slice(0, 2)" :key="i">{{ desc }}</span>
                </div>
              </div>
            </div>
          </section>

          <!-- 价值投注 -->
          <section class="section-block" v-if="analysis.value_bets && analysis.value_bets.value_bets?.length">
            <div class="section-title"><DiamondIcon /><span>价值投注</span></div>
            <div class="value-bet-content">
              <div class="vb-header" v-if="analysis.value_bets.odds">
                <span class="vb-label">市场赔率</span>
                <div class="vb-odds">
                  <span>主{{ analysis.value_bets.odds.home }}</span>
                  <span>平{{ analysis.value_bets.odds.draw }}</span>
                  <span>客{{ analysis.value_bets.odds.away }}</span>
                </div>
              </div>
              <div class="vb-list">
                <div v-for="(vb, i) in analysis.value_bets.value_bets" :key="i" class="vb-item" :class="vb.value_rating">
                  <div class="vb-market">{{ vb.market === 'home_win' ? '主胜' : vb.market === 'draw' ? '平局' : '客胜' }}</div>
                  <div class="vb-stats">
                    <div class="vb-stat">
                      <span class="s-label">预测</span>
                      <span class="s-value">{{ vb.prediction_prob }}%</span>
                    </div>
                    <div class="vb-stat">
                      <span class="s-label">隐含</span>
                      <span class="s-value">{{ vb.implied_prob }}%</span>
                    </div>
                    <div class="vb-stat highlight">
                      <span class="s-label">优势</span>
                      <span class="s-value">+{{ vb.edge }}%</span>
                    </div>
                    <div class="vb-stat">
                      <span class="s-label">Kelly</span>
                      <span class="s-value">{{ vb.kelly_fraction }}%</span>
                    </div>
                  </div>
                  <div class="vb-rating" :class="vb.value_rating">
                    {{ vb.value_rating === 'high' ? '高价值' : vb.value_rating === 'medium' ? '中等价值' : '低价值' }}
                  </div>
                </div>
              </div>
              <div class="vb-summary" v-if="analysis.value_bets.summary">{{ analysis.value_bets.summary }}</div>
            </div>
          </section>
        </div>
      </div>
      <div class="analysis-grid">
        <div class="analysis-group-title"><TargetIcon /><span>进攻分析</span></div>
        <section class="section-block" v-if="advData.xg">
        <div class="section-title"><TargetIcon /><span>xG分析</span></div>
        <div class="cards-row">
          <div class="card" v-if="advData.xg.simple_xg">
            <div class="card-header"><h4>基础 xG</h4></div>
            <div class="card-body">
              <div class="compare-cards">
                <div class="compare-card">
                  <div class="compare-header">主队</div>
                  <div class="elo-num home" style="font-size:22px">{{ advData.xg.simple_xg.home?.toFixed(2) || '-' }}</div>
                </div>
                <div class="vs-divider">xG</div>
                <div class="compare-card">
                  <div class="compare-header">客队</div>
                  <div class="elo-num away" style="font-size:22px">{{ advData.xg.simple_xg.away?.toFixed(2) || '-' }}</div>
                </div>
              </div>
            </div>
          </div>
          <div class="card" v-if="advData.xg.statsbomb_xg">
            <div class="card-header"><h4>StatsBomb xG</h4></div>
            <div class="card-body">
              <div class="compare-cards">
                <div class="compare-card">
                  <div class="compare-header">主队</div>
                  <div class="elo-num home" style="font-size:22px">{{ advData.xg.statsbomb_xg.home_xg?.toFixed(2) || '-' }}</div>
                </div>
                <div class="vs-divider">xG</div>
                <div class="compare-card">
                  <div class="compare-header">客队</div>
                  <div class="elo-num away" style="font-size:22px">{{ advData.xg.statsbomb_xg.away_xg?.toFixed(2) || '-' }}</div>
                </div>
              </div>
              <div class="form-pts" v-if="advData.xg.statsbomb_xg.shots_count">射门 {{ advData.xg.statsbomb_xg.shots_count }} 次</div>
            </div>
          </div>
        </div>
        <div v-if="advData.xg.comparison" class="info-grid" style="padding:10px">
          <div class="info-item"><span class="info-label">主队超/低于xG</span><span class="info-value" :class="advData.xg.comparison.home_diff > 0 ? 'home' : ''">{{ advData.xg.comparison.home_diff?.toFixed(2) }}</span></div>
          <div class="info-item"><span class="info-label">客队超/低于xG</span><span class="info-value" :class="advData.xg.comparison.away_diff > 0 ? 'away' : ''">{{ advData.xg.comparison.away_diff?.toFixed(2) }}</span></div>
        </div>
      </section>

        <!-- 体能影响 -->
        <div class="analysis-group-title"><FlameIcon /><span>体能影响</span></div>
      <!-- 疲劳对比 -->
      <section class="section-block" v-if="advData.fatigue">
        <div class="section-title"><RestIcon /><span>疲劳对比</span></div>
        <div class="compare-cards">
          <div class="compare-card">
            <div class="compare-header">{{ analysis.match?.home_team_cn || '主队' }}</div>
            <div class="compare-body">
              <div class="rest-num">{{ advData.fatigue.home_team?.rest_days ?? '-' }}<span class="unit">天</span></div>
              <div class="form-pts">7天{{ advData.fatigue.home_team?.matches_7days ?? 0 }}场 · 14天{{ advData.fatigue.home_team?.matches_14days ?? 0 }}场</div>
              <span class="impact-badge" :class="advData.fatigue.home_team?.fatigue_level">{{ advData.fatigue.home_team?.fatigue_level }}</span>
            </div>
          </div>
          <div class="vs-divider">{{ advData.fatigue.comparison?.advantage === 'home' ? '主队优' : advData.fatigue.comparison?.advantage === 'away' ? '客队优' : '持平' }}</div>
          <div class="compare-card">
            <div class="compare-header">{{ analysis.match?.away_team_cn || '客队' }}</div>
            <div class="compare-body">
              <div class="rest-num">{{ advData.fatigue.away_team?.rest_days ?? '-' }}<span class="unit">天</span></div>
              <div class="form-pts">7天{{ advData.fatigue.away_team?.matches_7days ?? 0 }}场 · 14天{{ advData.fatigue.away_team?.matches_14days ?? 0 }}场</div>
              <span class="impact-badge" :class="advData.fatigue.away_team?.fatigue_level">{{ advData.fatigue.away_team?.fatigue_level }}</span>
            </div>
          </div>
        </div>
        <div v-if="advData.fatigue.impact_on_prediction" class="info-grid" style="padding:10px">
          <div class="info-item"><span class="info-label">疲劳净影响</span><span class="info-value">{{ advData.fatigue.impact_on_prediction.net_effect?.toFixed(2) }}</span></div>
          <div class="info-item" v-if="advData.fatigue.comparison?.description"><span class="info-label">评估</span><span class="info-value">{{ advData.fatigue.comparison.description }}</span></div>
        </div>
      </section>

        <!-- 环境因素 -->
        <div class="analysis-group-title"><AlertIcon /><span>环境因素</span></div>
      <!-- 裁判影响 -->
      <section class="section-block" v-if="advData.referee && advData.referee.has_data">
        <div class="section-title"><AlertIcon /><span>裁判影响</span></div>
        <div class="info-grid" style="padding:12px">
          <div class="info-item"><span class="info-label">裁判</span><span class="info-value accent">{{ advData.referee.referee }}</span></div>
          <div class="info-item" v-if="advData.referee.overall_stats"><span class="info-label">执法场次</span><span class="info-value">{{ advData.referee.overall_stats.matches }}</span></div>
          <div class="info-item" v-if="advData.referee.overall_stats"><span class="info-label">场均黄牌</span><span class="info-value">{{ advData.referee.overall_stats.avg_yellow?.toFixed(1) }}</span></div>
          <div class="info-item" v-if="advData.referee.overall_stats"><span class="info-label">主胜率</span><span class="info-value home">{{ (advData.referee.overall_stats.home_win_rate * 100)?.toFixed(1) }}%</span></div>
          <div class="info-item" v-if="advData.referee.overall_stats"><span class="info-label">判罚风格</span><span class="info-value">{{ advData.referee.overall_stats.strictness }}</span></div>
          <div class="info-item" v-if="advData.referee.overall_stats"><span class="info-label">主场倾向</span><span class="info-value">{{ (advData.referee.overall_stats.home_bias * 100)?.toFixed(1) }}%</span></div>
        </div>
        <div v-if="advData.referee.impact" class="info-grid" style="padding:10px;border-top:1px solid rgba(31,41,55,0.3)">
          <div class="info-item" v-if="advData.referee.impact.strictness_impact"><span class="info-label">判罚影响</span><span class="info-value">{{ advData.referee.impact.strictness_impact.description }}</span></div>
          <div class="info-item" v-if="advData.referee.impact.home_bias_impact"><span class="info-label">主场偏向</span><span class="info-value">{{ advData.referee.impact.home_bias_impact.description }}</span></div>
        </div>
        <div v-if="advData.referee.summary" style="padding:10px;border-top:1px solid rgba(31,41,55,0.3);font-size:12px;color:#9ca3af">{{ advData.referee.summary }}</div>
      </section>

      <!-- 场地影响 -->
      <section class="section-block" v-if="advData.venue">
        <div class="section-title"><HomeIcon /><span>场地影响</span></div>
        <div class="info-grid" style="padding:12px">
          <div class="info-item" v-if="advData.venue.venue"><span class="info-label">球场</span><span class="info-value accent">{{ advData.venue.venue }}</span></div>
          <div class="info-item" v-if="advData.venue.altitude_impact"><span class="info-label">海拔</span><span class="info-value">{{ advData.venue.altitude_impact.altitude }}m</span></div>
          <div class="info-item" v-if="advData.venue.altitude_impact"><span class="info-label">海拔影响</span><span class="info-value" :class="advData.venue.altitude_impact.level === 'extreme' ? 'negative' : ''">{{ advData.venue.altitude_impact.level }}</span></div>
          <div class="info-item" v-if="advData.venue.travel_impact"><span class="info-label">旅途疲劳</span><span class="info-value">{{ advData.venue.travel_impact.level }}</span></div>
          <div class="info-item" v-if="advData.venue.distance"><span class="info-label">距离</span><span class="info-value">{{ Math.round(advData.venue.distance) }} km</span></div>
          <div class="info-item"><span class="info-label">主场优势</span><span class="info-value accent">{{ (advData.venue.overall_home_advantage * 100)?.toFixed(1) }}%</span></div>
        </div>
        <div v-if="advData.venue.home_record" class="compare-cards" style="padding:10px;border-top:1px solid rgba(31,41,55,0.3)">
          <div class="compare-card">
            <div class="compare-header">主场战绩</div>
            <div class="compare-body">
              <div class="form-numbers"><span class="win">{{ advData.venue.home_record.wins }}</span><span class="draw">{{ advData.venue.home_record.draws }}</span><span class="loss">{{ (advData.venue.home_record.matches - advData.venue.home_record.wins - advData.venue.home_record.draws) || 0 }}</span></div>
              <div class="form-pts">胜率 {{ (advData.venue.home_record.win_rate * 100)?.toFixed(1) }}%</div>
            </div>
          </div>
        </div>
        <div v-if="advData.venue.summary" style="padding:10px;border-top:1px solid rgba(31,41,55,0.3);font-size:12px;color:#9ca3af">{{ advData.venue.summary }}</div>
      </section>

      <!-- 联赛影响 -->
      <section class="section-block" v-if="advData.leagueImpact">
        <div class="section-title"><StarIcon /><span>联赛积分影响</span></div>
        <div class="scenarios-grid" v-if="advData.leagueImpact.scenarios">
          <div class="scenario-item">
            <div class="scenario-header">主胜</div>
            <div class="scenario-body" v-if="advData.leagueImpact.scenarios.home_win">
              <div class="scenario-row"><span class="s-label">主队</span><span class="s-value home">#{{ advData.leagueImpact.scenarios.home_win.home_rank }} {{ advData.leagueImpact.scenarios.home_win.home_rank_change > 0 ? '(↑' + advData.leagueImpact.scenarios.home_win.home_rank_change + ')' : advData.leagueImpact.scenarios.home_win.home_rank_change < 0 ? '(↓' + Math.abs(advData.leagueImpact.scenarios.home_win.home_rank_change) + ')' : '' }}</span></div>
              <div class="scenario-row"><span class="s-label">客队</span><span class="s-value away">#{{ advData.leagueImpact.scenarios.home_win.away_rank }} {{ advData.leagueImpact.scenarios.home_win.away_rank_change < 0 ? '(↑' + Math.abs(advData.leagueImpact.scenarios.home_win.away_rank_change) + ')' : advData.leagueImpact.scenarios.home_win.away_rank_change > 0 ? '(↓' + advData.leagueImpact.scenarios.home_win.away_rank_change + ')' : '' }}</span></div>
            </div>
          </div>
          <div class="scenario-item">
            <div class="scenario-header">平局</div>
            <div class="scenario-body" v-if="advData.leagueImpact.scenarios.draw">
              <div class="scenario-row"><span class="s-label">主队</span><span class="s-value home">#{{ advData.leagueImpact.scenarios.draw.home_rank }}</span></div>
              <div class="scenario-row"><span class="s-label">客队</span><span class="s-value away">#{{ advData.leagueImpact.scenarios.draw.away_rank }}</span></div>
            </div>
          </div>
          <div class="scenario-item">
            <div class="scenario-header">客胜</div>
            <div class="scenario-body" v-if="advData.leagueImpact.scenarios.away_win">
              <div class="scenario-row"><span class="s-label">主队</span><span class="s-value home">#{{ advData.leagueImpact.scenarios.away_win.home_rank }}</span></div>
              <div class="scenario-row"><span class="s-label">客队</span><span class="s-value away">#{{ advData.leagueImpact.scenarios.away_win.away_rank }}</span></div>
            </div>
          </div>
        </div>
        <div v-if="advData.leagueImpact.impact_analysis" class="info-grid" style="padding:10px;border-top:1px solid rgba(31,41,55,0.3)">
          <div class="info-item" v-if="advData.leagueImpact.impact_analysis.home_team"><span class="info-label">主队保级风险</span><span class="info-value" :class="advData.leagueImpact.impact_analysis.home_team.relegation_risk?.level === 'critical' ? 'negative' : ''">{{ advData.leagueImpact.impact_analysis.home_team.relegation_risk?.level }}</span></div>
          <div class="info-item" v-if="advData.leagueImpact.impact_analysis.home_team"><span class="info-label">主队争冠</span><span class="info-value">{{ advData.leagueImpact.impact_analysis.home_team.title_risk?.level }}</span></div>
          <div class="info-item" v-if="advData.leagueImpact.impact_analysis.away_team"><span class="info-label">客队保级风险</span><span class="info-value" :class="advData.leagueImpact.impact_analysis.away_team.relegation_risk?.level === 'critical' ? 'negative' : ''">{{ advData.leagueImpact.impact_analysis.away_team.relegation_risk?.level }}</span></div>
          <div class="info-item" v-if="advData.leagueImpact.impact_analysis.away_team"><span class="info-label">客队争冠</span><span class="info-value">{{ advData.leagueImpact.impact_analysis.away_team.title_risk?.level }}</span></div>
        </div>
        <div v-if="advData.leagueImpact.summary" style="padding:10px;border-top:1px solid rgba(31,41,55,0.3);font-size:12px;color:#9ca3af">{{ advData.leagueImpact.summary }}</div>
      </section>

      <!-- 时区转换 -->
      <section class="section-block analysis-full" v-if="advData.timezone">
        <div class="section-title"><ClockIcon /><span>时区转换</span></div>
        <div class="info-grid" style="padding:12px">
          <div class="info-item"><span class="info-label">UTC时间</span><span class="info-value">{{ advData.timezone.utc_time }}</span></div>
          <div class="info-item" v-if="advData.timezone.home_team_local"><span class="info-label">主队本地</span><span class="info-value home">{{ advData.timezone.home_team_local.display }}</span></div>
          <div class="info-item" v-if="advData.timezone.away_team_local"><span class="info-label">客队本地</span><span class="info-value away">{{ advData.timezone.away_team_local.display }}</span></div>
        </div>
        <div v-if="advData.timezone.major_cities?.length" class="h2h-recent" style="padding:10px;border-top:1px solid rgba(31,41,55,0.3)">
          <div class="h2h-row" v-for="city in advData.timezone.major_cities" :key="city.city">
            <span class="date">{{ city.city }}</span>
            <span class="teams">{{ city.timezone }}</span>
            <span class="result accent">{{ city.display }}</span>
          </div>
        </div>
      </section>

      <!-- API天气数据 -->
      <section class="section-block" v-if="advData.weather && !analysis.weather">
        <div class="section-title"><CloudIcon /><span>比赛天气</span></div>
        <div class="weather-content">
          <div class="weather-main">
            <div class="weather-temp">
              <span class="temp-value">{{ advData.weather.temperature }}°C</span>
              <span class="temp-desc">{{ advData.weather.weather_description }}</span>
            </div>
            <div class="weather-details">
              <div class="w-item"><span class="w-label">湿度</span><span class="w-value">{{ advData.weather.humidity }}%</span></div>
              <div class="w-item"><span class="w-label">风速</span><span class="w-value">{{ advData.weather.wind_speed }} m/s</span></div>
            </div>
          </div>
          <div class="weather-impact" v-if="advData.weather.impact">
            <div class="impact-title">天气影响</div>
            <div class="impact-factors">
              <div class="impact-item">
                <span class="i-label">进球</span>
                <span class="i-value" :class="advData.weather.impact.goal_factor < 1 ? 'negative' : ''">{{ (advData.weather.impact.goal_factor * 100).toFixed(0) }}%</span>
              </div>
              <div class="impact-item">
                <span class="i-label">体能</span>
                <span class="i-value" :class="advData.weather.impact.stamina_factor < 1 ? 'negative' : ''">{{ (advData.weather.impact.stamina_factor * 100).toFixed(0) }}%</span>
              </div>
              <div class="impact-item">
                <span class="i-label">传球</span>
                <span class="i-value" :class="advData.weather.impact.pass_factor < 1 ? 'negative' : ''">{{ (advData.weather.impact.pass_factor * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div class="impact-desc" v-if="advData.weather.impact.description?.length">
              <span v-for="(desc, i) in advData.weather.impact.description.slice(0, 2)" :key="i">{{ desc }}</span>
            </div>
          </div>
        </div>
      </section>

        <!-- 前瞻汇总 -->
        <div class="analysis-group-title"><FileTextIcon /><span>前瞻汇总</span></div>
      <!-- 比赛前瞻 -->
      <section class="section-block" v-if="advData.preview">
        <div class="section-title"><InfoIcon /><span>比赛前瞻</span></div>
        <div class="preview-content">
          <div v-if="advData.preview.key_factors?.length" class="preview-factors">
            <div class="factor-item" v-for="(factor, i) in advData.preview.key_factors.slice(0, 6)" :key="i">
              <span class="factor-label">{{ factor.name || factor.factor }}</span>
              <span class="factor-impact" :class="factor.impact === 'positive' ? 'positive' : factor.impact === 'negative' ? 'negative' : 'neutral'">{{ factor.description || factor.impact }}</span>
            </div>
          </div>
          <div v-if="advData.preview.home_advantage" class="info-grid" style="padding:10px;border-top:1px solid rgba(31,41,55,0.3)">
            <div class="info-item"><span class="info-label">主场优势</span><span class="info-value accent">{{ (advData.preview.home_advantage * 100).toFixed(1) }}%</span></div>
          </div>
          <div v-if="advData.preview.summary" class="preview-summary">{{ advData.preview.summary }}</div>
          <div v-if="advData.preview.recommendation" class="preview-rec">
            <span class="rec-label">建议</span>
            <span class="rec-value">{{ advData.preview.recommendation }}</span>
          </div>
        </div>
      </section>


        <!-- AI预测 -->
        <div class="analysis-group-title"><BrainIcon /><span>AI预测</span></div>
      <!-- ML预测 -->
        <section class="section-block" v-if="advData.ml">
          <div class="section-title"><BrainIcon /><span>ML深度预测</span></div>
        <div class="ml-content">
          <div class="ml-probs" v-if="advData.ml.probabilities">
            <div class="ml-prob-item">
              <span class="ml-label">主胜</span>
              <div class="ml-prob-bar"><div class="ml-bar home" :style="{ width: (advData.ml.probabilities.home_win * 100) + '%' }"></div></div>
              <span class="ml-pct">{{ (advData.ml.probabilities.home_win * 100).toFixed(1) }}%</span>
            </div>
            <div class="ml-prob-item">
              <span class="ml-label">平局</span>
              <div class="ml-prob-bar"><div class="ml-bar draw" :style="{ width: (advData.ml.probabilities.draw * 100) + '%' }"></div></div>
              <span class="ml-pct">{{ (advData.ml.probabilities.draw * 100).toFixed(1) }}%</span>
            </div>
            <div class="ml-prob-item">
              <span class="ml-label">客胜</span>
              <div class="ml-prob-bar"><div class="ml-bar away" :style="{ width: (advData.ml.probabilities.away_win * 100) + '%' }"></div></div>
              <span class="ml-pct">{{ (advData.ml.probabilities.away_win * 100).toFixed(1) }}%</span>
            </div>
          </div>
          <div class="ml-meta" v-if="advData.ml.model_info">
            <span class="ml-meta-item">模型: {{ advData.ml.model_info.model_type || 'XGBoost' }}</span>
            <span class="ml-meta-item" v-if="advData.ml.model_info.accuracy">准确率: {{ (advData.ml.model_info.accuracy * 100).toFixed(1) }}%</span>
            <span class="ml-meta-item" v-if="advData.ml.model_info.cv_score">CV: {{ (advData.ml.model_info.cv_score * 100).toFixed(1) }}%</span>
          </div>
          <div class="ml-prediction" v-if="advData.ml.predicted_result">
            <span class="ml-pred-label">预测结果</span>
            <span class="ml-pred-value">{{ advData.ml.predicted_result === 'H' ? '主胜' : advData.ml.predicted_result === 'D' ? '平局' : '客胜' }}</span>
            <span class="ml-confidence" v-if="advData.ml.confidence">置信度 {{ (advData.ml.confidence * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </section>

      <!-- 模型对比 -->
      <section class="section-block" v-if="advData.modelComp && advData.modelComp.models">
        <div class="section-title"><LayersIcon /><span>多模型对比</span></div>
        <div class="model-comp-content">
          <div class="model-table">
            <div class="model-header">
              <span>模型</span><span>主胜</span><span>平局</span><span>客胜</span><span>预测</span>
            </div>
            <div class="model-row" v-for="(m, i) in advData.modelComp.models" :key="i">
              <span class="model-name">{{ m.name || m.model_type }}</span>
              <span class="model-prob">{{ (m.home_win * 100).toFixed(1) }}%</span>
              <span class="model-prob">{{ (m.draw * 100).toFixed(1) }}%</span>
              <span class="model-prob">{{ (m.away_win * 100).toFixed(1) }}%</span>
              <span class="model-pred" :class="m.predicted === 'H' ? 'home' : m.predicted === 'A' ? 'away' : 'draw'">{{ m.predicted === 'H' ? '主胜' : m.predicted === 'D' ? '平局' : '客胜' }}</span>
            </div>
          </div>
          <div class="model-consensus" v-if="advData.modelComp.consensus">
            <span class="consensus-label">综合共识</span>
            <span class="consensus-value">{{ advData.modelComp.consensus }}</span>
          </div>
        </div>
      </section>

      <!-- 特征重要性 -->
      <section class="section-block" v-if="advData.features && advData.features.top_features?.length">
        <div class="section-title"><BarIcon /><span>关键特征分析</span></div>
        <div class="features-content">
          <div class="feature-bar-item" v-for="(f, i) in advData.features.top_features.slice(0, 8)" :key="i">
            <span class="feature-name">{{ f.name || f.feature }}</span>
            <div class="feature-bar-wrap">
              <div class="feature-bar" :style="{ width: (f.importance * 100) + '%' }"></div>
            </div>
            <span class="feature-val">{{ (f.importance * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </section>

      <!-- 让球分析 -->
      <section class="section-block" v-if="advData.handicap">
        <div class="section-title"><TargetIcon /><span>让球深度分析</span></div>
        <div class="handicap-content">
          <div class="hc-main" v-if="advData.handicap.recommended_handicap != null">
            <div class="hc-line">
              <span class="hc-label">推荐盘口</span>
              <span class="hc-value">{{ advData.handicap.recommended_handicap > 0 ? '+' + advData.handicap.recommended_handicap : advData.handicap.recommended_handicap }}</span>
            </div>
            <div class="hc-line" v-if="advData.handicap.fair_odds">
              <span class="hc-label">公平赔率</span>
              <span class="hc-value">{{ advData.handicap.fair_odds }}</span>
            </div>
          </div>
          <div class="hc-scenarios" v-if="advData.handicap.scenarios?.length">
            <div class="hc-scenario" v-for="(s, i) in advData.handicap.scenarios" :key="i">
              <span class="sc-line">盘口 {{ s.handicap != null ? (s.handicap > 0 ? '+' + s.handicap : s.handicap) : '-' }}</span>
              <span class="sc-prob">主{{ (s.home_prob * 100).toFixed(1) }}%</span>
              <span class="sc-prob">客{{ (s.away_prob * 100).toFixed(1) }}%</span>
            </div>
          </div>
          <div class="hc-summary" v-if="advData.handicap.summary">{{ advData.handicap.summary }}</div>
        </div>
      </section>

      <!-- 效率对比 -->
      <section class="section-block" v-if="advData.efficiency">
        <div class="section-title"><ZapIcon /><span>攻防效率对比</span></div>
        <div class="efficiency-content">
          <div class="eff-compare" v-if="advData.efficiency.comparison">
            <div class="eff-category" v-for="(cat, name) in advData.efficiency.comparison" :key="name">
              <span class="eff-cat-name">{{ name }}</span>
              <div class="eff-bars">
                <div class="eff-bar-row">
                  <span class="eff-team">主</span>
                  <div class="eff-bar-wrap"><div class="eff-bar home" :style="{ width: Math.min(cat.home * 100, 100) + '%' }"></div></div>
                  <span class="eff-val">{{ (cat.home * 100).toFixed(1) }}</span>
                </div>
                <div class="eff-bar-row">
                  <span class="eff-team">客</span>
                  <div class="eff-bar-wrap"><div class="eff-bar away" :style="{ width: Math.min(cat.away * 100, 100) + '%' }"></div></div>
                  <span class="eff-val">{{ (cat.away * 100).toFixed(1) }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="eff-summary" v-if="advData.efficiency.summary">{{ advData.efficiency.summary }}</div>
        </div>
      </section>

      <!-- 爆冷分析 -->
      <section class="section-block" v-if="advData.upset">
        <div class="section-title"><AlertIcon /><span>爆冷可能性分析</span></div>
        <div class="upset-content">
          <div class="upset-score" v-if="advData.upset.upset_probability != null">
            <span class="upset-label">爆冷概率</span>
            <div class="upset-bar-wrap">
              <div class="upset-bar" :class="advData.upset.upset_probability > 0.3 ? 'high' : advData.upset.upset_probability > 0.15 ? 'medium' : 'low'" :style="{ width: (advData.upset.upset_probability * 100) + '%' }"></div>
            </div>
            <span class="upset-pct">{{ (advData.upset.upset_probability * 100).toFixed(1) }}%</span>
          </div>
          <div class="upset-factors" v-if="advData.upset.factors?.length">
            <div class="upset-factor" v-for="(f, i) in advData.upset.factors.slice(0, 5)" :key="i">
              <span class="uf-name">{{ f.name || f.factor }}</span>
              <span class="uf-impact" :class="f.impact === 'positive' ? 'positive' : f.impact === 'negative' ? 'negative' : 'neutral'">{{ f.description || f.value }}</span>
            </div>
          </div>
          <div class="upset-historical" v-if="advData.upset.historical_upsets">
            <span class="uh-label">历史爆冷率</span>
            <span class="uh-value">{{ (advData.upset.historical_upsets.rate * 100).toFixed(1) }}% ({{ advData.upset.historical_upsets.count }}次)</span>
          </div>
          <div class="upset-assessment" v-if="advData.upset.assessment">{{ advData.upset.assessment }}</div>
        </div>
      </section>


      <!-- 比赛背景 -->
      <div class="analysis-group-title"><FlameIcon /><span>比赛背景</span></div>
      <!-- 六分之战 -->
      <section class="section-block" v-if="advData.sixPointer">
        <div class="section-title"><FlameIcon /><span>六分之战分析</span></div>
        <div class="sixptr-content">
          <div class="sixptr-main" v-if="advData.sixPointer.is_six_pointer != null">
            <span class="sixptr-badge" :class="advData.sixPointer.is_six_pointer ? 'yes' : 'no'">{{ advData.sixPointer.is_six_pointer ? '六分之战' : '非六分之战' }}</span>
            <span class="sixptr-desc" v-if="advData.sixPointer.description">{{ advData.sixPointer.description }}</span>
          </div>
          <div class="sixptr-scenarios" v-if="advData.sixPointer.scenarios">
            <div class="sp-scenario" v-if="advData.sixPointer.scenarios.home_win">
              <span class="sp-result home">主胜</span>
              <span class="sp-impact">{{ advData.sixPointer.scenarios.home_win.impact || advData.sixPointer.scenarios.home_win.description }}</span>
            </div>
            <div class="sp-scenario" v-if="advData.sixPointer.scenarios.draw">
              <span class="sp-result draw">平局</span>
              <span class="sp-impact">{{ advData.sixPointer.scenarios.draw.impact || advData.sixPointer.scenarios.draw.description }}</span>
            </div>
            <div class="sp-scenario" v-if="advData.sixPointer.scenarios.away_win">
              <span class="sp-result away">客胜</span>
              <span class="sp-impact">{{ advData.sixPointer.scenarios.away_win.impact || advData.sixPointer.scenarios.away_win.description }}</span>
            </div>
          </div>
          <div class="sixptr-motivation" v-if="advData.sixPointer.motivation_comparison">
            <div class="sp-mot-item"><span class="sp-mot-label">主队战意</span><span class="sp-mot-val home">{{ advData.sixPointer.motivation_comparison.home }}</span></div>
            <div class="sp-mot-item"><span class="sp-mot-label">客队战意</span><span class="sp-mot-val away">{{ advData.sixPointer.motivation_comparison.away }}</span></div>
          </div>
        </div>
      </section>

      <!-- 战意对比 -->
      <section class="section-block" v-if="advData.motivation && !advData.sixPointer">
        <div class="section-title"><FlameIcon /><span>战意对比</span></div>
        <div class="motivation-content">
          <div class="mot-compare" v-if="advData.motivation.comparison">
            <div class="mot-side home">
              <span class="mot-team">{{ analysis.match?.home_team_cn || '主队' }}</span>
              <span class="mot-score" :class="advData.motivation.comparison.home_level">{{ advData.motivation.comparison.home_score || advData.motivation.comparison.home }}</span>
              <span class="mot-reason" v-if="advData.motivation.comparison.home_reason">{{ advData.motivation.comparison.home_reason }}</span>
            </div>
            <div class="mot-side away">
              <span class="mot-team">{{ analysis.match?.away_team_cn || '客队' }}</span>
              <span class="mot-score" :class="advData.motivation.comparison.away_level">{{ advData.motivation.comparison.away_score || advData.motivation.comparison.away }}</span>
              <span class="mot-reason" v-if="advData.motivation.comparison.away_reason">{{ advData.motivation.comparison.away_reason }}</span>
            </div>
          </div>
          <div class="mot-summary" v-if="advData.motivation.summary">{{ advData.motivation.summary }}</div>
        </div>
      </section>

      <!-- H2H模式分析 -->
      <section class="section-block" v-if="advData.h2hPatterns && (advData.h2hPatterns.patterns?.length || advData.h2hPatterns.scoring_trends)">
        <div class="section-title"><GitBranchIcon /><span>交锋模式深度分析</span></div>
        <div class="h2h-patterns-content">
          <div class="hp-trends" v-if="advData.h2hPatterns.scoring_trends">
            <div class="hp-trend-item" v-if="advData.h2hPatterns.scoring_trends.avg_total_goals != null">
              <span class="hp-label">场均总进球</span><span class="hp-value">{{ advData.h2hPatterns.scoring_trends.avg_total_goals.toFixed(2) }}</span>
            </div>
            <div class="hp-trend-item" v-if="advData.h2hPatterns.scoring_trends.avg_home_goals != null">
              <span class="hp-label">主队场均</span><span class="hp-value home">{{ advData.h2hPatterns.scoring_trends.avg_home_goals.toFixed(2) }}</span>
            </div>
            <div class="hp-trend-item" v-if="advData.h2hPatterns.scoring_trends.avg_away_goals != null">
              <span class="hp-label">客队场均</span><span class="hp-value away">{{ advData.h2hPatterns.scoring_trends.avg_away_goals.toFixed(2) }}</span>
            </div>
            <div class="hp-trend-item" v-if="advData.h2hPatterns.scoring_trends.btts_rate != null">
              <span class="hp-label">双方进球率</span><span class="hp-value">{{ (advData.h2hPatterns.scoring_trends.btts_rate * 100).toFixed(0) }}%</span>
            </div>
            <div class="hp-trend-item" v-if="advData.h2hPatterns.scoring_trends.over25_rate != null">
              <span class="hp-label">大2.5球率</span><span class="hp-value accent">{{ (advData.h2hPatterns.scoring_trends.over25_rate * 100).toFixed(0) }}%</span>
            </div>
          </div>
          <div class="hp-patterns" v-if="advData.h2hPatterns.patterns?.length">
            <div class="hp-pattern" v-for="(p, i) in advData.h2hPatterns.patterns.slice(0, 5)" :key="i">
              <span class="hpat-name">{{ p.name || p.pattern }}</span>
              <span class="hpat-desc">{{ p.description || p.detail }}</span>
            </div>
          </div>
          <div class="hp-dominance" v-if="advData.h2hPatterns.dominance">
            <span class="hp-dom-label">主导方</span>
            <span class="hp-dom-value" :class="advData.h2hPatterns.dominance === 'home' ? 'home' : advData.h2hPatterns.dominance === 'away' ? 'away' : ''">{{ advData.h2hPatterns.dominance === 'home' ? '主队压制' : advData.h2hPatterns.dominance === 'away' ? '客队压制' : '势均力敌' }}</span>
          </div>
        </div>
      </section>

      <!-- 泊松分布进球预测 -->
      <section class="section-block" v-if="advData.poissonHome || advData.poissonAway">
        <div class="section-title"><TrendingIcon /><span>泊松分布进球预测</span></div>
        <div class="poisson-content">
          <div class="pois-params">
            <div class="pois-param" v-if="advData.poissonHome">
              <span class="pois-team">{{ analysis.match?.home_team_cn || '主队' }}</span>
              <span class="pois-lambda">λ = {{ advData.poissonHome.lambda?.toFixed(2) || advData.poissonHome.expected_goals?.toFixed(2) }}</span>
              <span class="pois-exp">期望 {{ advData.poissonHome.expected_goals?.toFixed(2) || '-' }} 球</span>
            </div>
            <div class="pois-param away" v-if="advData.poissonAway">
              <span class="pois-team">{{ analysis.match?.away_team_cn || '客队' }}</span>
              <span class="pois-lambda">λ = {{ advData.poissonAway.lambda?.toFixed(2) || advData.poissonAway.expected_goals?.toFixed(2) }}</span>
              <span class="pois-exp">期望 {{ advData.poissonAway.expected_goals?.toFixed(2) || '-' }} 球</span>
            </div>
          </div>
          <div class="pois-dist">
            <div class="pois-row" v-if="advData.poissonHome?.distribution">
              <span class="pois-row-label">主队进球</span>
              <div class="pois-bars">
                <div class="pois-bar-item" v-for="(p, g) in advData.poissonHome.distribution.slice(0, 6)" :key="g">
                  <div class="pois-bar home" :style="{ height: (p * 200) + '%' }"></div>
                  <span class="pois-g">{{ g }}</span>
                  <span class="pois-p">{{ (p * 100).toFixed(1) }}%</span>
                </div>
              </div>
            </div>
            <div class="pois-row" v-if="advData.poissonAway?.distribution">
              <span class="pois-row-label">客队进球</span>
              <div class="pois-bars">
                <div class="pois-bar-item" v-for="(p, g) in advData.poissonAway.distribution.slice(0, 6)" :key="g">
                  <div class="pois-bar away" :style="{ height: (p * 200) + '%' }"></div>
                  <span class="pois-g">{{ g }}</span>
                  <span class="pois-p">{{ (p * 100).toFixed(1) }}%</span>
                </div>
              </div>
            </div>
          </div>
          <div class="pois-scoreline" v-if="advData.poissonHome?.distribution && advData.poissonAway?.distribution">
            <span class="pois-sl-label">最可能比分</span>
            <div class="pois-scores">
              <span v-for="(s, i) in getTopScorelines(advData.poissonHome.distribution, advData.poissonAway.distribution, 4)" :key="i" class="pois-score">
                {{ s.score }} <small>{{ (s.prob * 100).toFixed(1) }}%</small>
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- 赛季走势分析 -->
      <section class="section-block" v-if="advData.seasonScenarioHome || advData.seasonScenarioAway">
        <div class="section-title"><TrendingIcon /><span>赛季走势分析</span></div>
        <div class="season-scenario-content">
          <div class="ss-grid">
            <div class="ss-side" v-if="advData.seasonScenarioHome">
              <div class="ss-team">{{ analysis.match?.home_team_cn || '主队' }}</div>
              <div class="ss-items">
                <div class="ss-item" v-if="advData.seasonScenarioHome.current_position"><span class="ss-label">当前排名</span><span class="ss-val">#{{ advData.seasonScenarioHome.current_position }}</span></div>
                <div class="ss-item" v-if="advData.seasonScenarioHome.points"><span class="ss-label">积分</span><span class="ss-val">{{ advData.seasonScenarioHome.points }}</span></div>
                <div class="ss-item" v-if="advData.seasonScenarioHome.form_trend"><span class="ss-label">走势</span><span class="ss-val" :class="advData.seasonScenarioHome.form_trend === 'up' ? 'positive' : advData.seasonScenarioHome.form_trend === 'down' ? 'negative' : ''">{{ advData.seasonScenarioHome.form_trend === 'up' ? '上升' : advData.seasonScenarioHome.form_trend === 'down' ? '下降' : '平稳' }}</span></div>
                <div class="ss-item" v-if="advData.seasonScenarioHome.target"><span class="ss-label">目标</span><span class="ss-val accent">{{ advData.seasonScenarioHome.target }}</span></div>
                <div class="ss-item" v-if="advData.seasonScenarioHome.remain_fixtures"><span class="ss-label">剩余场次</span><span class="ss-val">{{ advData.seasonScenarioHome.remain_fixtures }}</span></div>
              </div>
              <div class="ss-desc" v-if="advData.seasonScenarioHome.description">{{ advData.seasonScenarioHome.description }}</div>
            </div>
            <div class="ss-side" v-if="advData.seasonScenarioAway">
              <div class="ss-team away">{{ analysis.match?.away_team_cn || '客队' }}</div>
              <div class="ss-items">
                <div class="ss-item" v-if="advData.seasonScenarioAway.current_position"><span class="ss-label">当前排名</span><span class="ss-val">#{{ advData.seasonScenarioAway.current_position }}</span></div>
                <div class="ss-item" v-if="advData.seasonScenarioAway.points"><span class="ss-label">积分</span><span class="ss-val">{{ advData.seasonScenarioAway.points }}</span></div>
                <div class="ss-item" v-if="advData.seasonScenarioAway.form_trend"><span class="ss-label">走势</span><span class="ss-val" :class="advData.seasonScenarioAway.form_trend === 'up' ? 'positive' : advData.seasonScenarioAway.form_trend === 'down' ? 'negative' : ''">{{ advData.seasonScenarioAway.form_trend === 'up' ? '上升' : advData.seasonScenarioAway.form_trend === 'down' ? '下降' : '平稳' }}</span></div>
                <div class="ss-item" v-if="advData.seasonScenarioAway.target"><span class="ss-label">目标</span><span class="ss-val accent">{{ advData.seasonScenarioAway.target }}</span></div>
                <div class="ss-item" v-if="advData.seasonScenarioAway.remain_fixtures"><span class="ss-label">剩余场次</span><span class="ss-val">{{ advData.seasonScenarioAway.remain_fixtures }}</span></div>
              </div>
              <div class="ss-desc" v-if="advData.seasonScenarioAway.description">{{ advData.seasonScenarioAway.description }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 轮换风险 -->
      <section class="section-block" v-if="advData.rotationRiskHome || advData.rotationRiskAway">
        <div class="section-title"><RefreshIcon /><span>轮换风险评估</span></div>
        <div class="rotation-content">
          <div class="rot-grid">
            <div class="rot-side" v-if="advData.rotationRiskHome">
              <span class="rot-team">{{ analysis.match?.home_team_cn || '主队' }}</span>
              <span class="rot-risk" :class="advData.rotationRiskHome.risk_level">{{ advData.rotationRiskHome.risk_level === 'high' ? '高风险' : advData.rotationRiskHome.risk_level === 'medium' ? '中风险' : '低风险' }}</span>
              <span class="rot-prob" v-if="advData.rotationRiskHome.rotation_probability">轮换概率 {{ (advData.rotationRiskHome.rotation_probability * 100).toFixed(0) }}%</span>
              <div class="rot-reasons" v-if="advData.rotationRiskHome.factors?.length">
                <span v-for="(f, i) in advData.rotationRiskHome.factors.slice(0, 3)" :key="i" class="rot-reason">{{ f }}</span>
              </div>
            </div>
            <div class="rot-side" v-if="advData.rotationRiskAway">
              <span class="rot-team away">{{ analysis.match?.away_team_cn || '客队' }}</span>
              <span class="rot-risk" :class="advData.rotationRiskAway.risk_level">{{ advData.rotationRiskAway.risk_level === 'high' ? '高风险' : advData.rotationRiskAway.risk_level === 'medium' ? '中风险' : '低风险' }}</span>
              <span class="rot-prob" v-if="advData.rotationRiskAway.rotation_probability">轮换概率 {{ (advData.rotationRiskAway.rotation_probability * 100).toFixed(0) }}%</span>
              <div class="rot-reasons" v-if="advData.rotationRiskAway.factors?.length">
                <span v-for="(f, i) in advData.rotationRiskAway.factors.slice(0, 3)" :key="i" class="rot-reason">{{ f }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 换帅效应 -->
      <section class="section-block" v-if="(advData.managerChangeHome && advData.managerChangeHome.has_change) || (advData.managerChangeAway && advData.managerChangeAway.has_change)">
        <div class="section-title"><UserIcon /><span>换帅效应</span></div>
        <div class="manager-change-content">
          <div class="mc-side" v-if="advData.managerChangeHome && advData.managerChangeHome.has_change">
            <div class="mc-team">{{ analysis.match?.home_team_cn || '主队' }}</div>
            <div class="mc-info">
              <span class="mc-date">{{ advData.managerChangeHome.change_date }}</span>
              <span class="mc-coaches">{{ advData.managerChangeHome.old_coach }} → {{ advData.managerChangeHome.new_coach }}</span>
            </div>
            <div class="mc-bounce" v-if="advData.managerChangeHome.effect">
              <span class="mc-bounce-label">新帅效应</span>
              <span class="mc-bounce-val" :class="advData.managerChangeHome.effect.trend?.includes('improvement') ? 'positive' : advData.managerChangeHome.effect.trend?.includes('decline') ? 'negative' : ''">{{ advData.managerChangeHome.effect.trend === 'significant_improvement' ? '显著提升' : advData.managerChangeHome.effect.trend === 'moderate_improvement' ? '中等提升' : advData.managerChangeHome.effect.trend === 'stable' ? '基本稳定' : advData.managerChangeHome.effect.trend === 'moderate_decline' ? '中等下滑' : '显著下滑' }}</span>
            </div>
          </div>
          <div class="mc-side" v-if="advData.managerChangeAway && advData.managerChangeAway.has_change">
            <div class="mc-team away">{{ analysis.match?.away_team_cn || '客队' }}</div>
            <div class="mc-info">
              <span class="mc-date">{{ advData.managerChangeAway.change_date }}</span>
              <span class="mc-coaches">{{ advData.managerChangeAway.old_coach }} → {{ advData.managerChangeAway.new_coach }}</span>
            </div>
            <div class="mc-bounce" v-if="advData.managerChangeAway.effect">
              <span class="mc-bounce-label">新帅效应</span>
              <span class="mc-bounce-val" :class="advData.managerChangeAway.effect.trend?.includes('improvement') ? 'positive' : advData.managerChangeAway.effect.trend?.includes('decline') ? 'negative' : ''">{{ advData.managerChangeAway.effect.trend === 'significant_improvement' ? '显著提升' : advData.managerChangeAway.effect.trend === 'moderate_improvement' ? '中等提升' : advData.managerChangeAway.effect.trend === 'stable' ? '基本稳定' : advData.managerChangeAway.effect.trend === 'moderate_decline' ? '中等下滑' : '显著下滑' }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 阵容分析 -->
      <section class="section-block" v-if="advData.squadHome || advData.squadAway">
        <div class="section-title"><UsersIcon /><span>阵容分析</span></div>
        <div class="squad-content">
          <div class="sq-grid">
            <div class="sq-side" v-if="advData.squadHome">
              <div class="sq-team">{{ analysis.match?.home_team_cn || '主队' }}</div>
              <div class="sq-stats">
                <div class="sq-stat" v-if="advData.squadHome.squad_value"><span class="sq-label">阵容价值</span><span class="sq-val">€{{ advData.squadHome.squad_value }}</span></div>
                <div class="sq-stat" v-if="advData.squadHome.avg_age"><span class="sq-label">平均年龄</span><span class="sq-val">{{ advData.squadHome.avg_age }}</span></div>
                <div class="sq-stat" v-if="advData.squadHome.injuries != null"><span class="sq-label">伤停</span><span class="sq-val" :class="advData.squadHome.injuries > 3 ? 'negative' : ''">{{ advData.squadHome.injuries }}人</span></div>
                <div class="sq-stat" v-if="advData.squadHome.key_players_missing"><span class="sq-label">核心缺阵</span><span class="sq-val negative">{{ advData.squadHome.key_players_missing }}</span></div>
              </div>
              <div class="sq-players" v-if="advData.squadHome.missing_players?.length">
                <span class="sq-mp" v-for="(p, i) in advData.squadHome.missing_players.slice(0, 4)" :key="i">{{ p.name || p }}</span>
              </div>
            </div>
            <div class="sq-side" v-if="advData.squadAway">
              <div class="sq-team away">{{ analysis.match?.away_team_cn || '客队' }}</div>
              <div class="sq-stats">
                <div class="sq-stat" v-if="advData.squadAway.squad_value"><span class="sq-label">阵容价值</span><span class="sq-val">€{{ advData.squadAway.squad_value }}</span></div>
                <div class="sq-stat" v-if="advData.squadAway.avg_age"><span class="sq-label">平均年龄</span><span class="sq-val">{{ advData.squadAway.avg_age }}</span></div>
                <div class="sq-stat" v-if="advData.squadAway.injuries != null"><span class="sq-label">伤停</span><span class="sq-val" :class="advData.squadAway.injuries > 3 ? 'negative' : ''">{{ advData.squadAway.injuries }}人</span></div>
                <div class="sq-stat" v-if="advData.squadAway.key_players_missing"><span class="sq-label">核心缺阵</span><span class="sq-val negative">{{ advData.squadAway.key_players_missing }}</span></div>
              </div>
              <div class="sq-players" v-if="advData.squadAway.missing_players?.length">
                <span class="sq-mp" v-for="(p, i) in advData.squadAway.missing_players.slice(0, 4)" :key="i">{{ p.name || p }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 比赛相关新闻 -->
      <section class="section-block" v-if="advData.matchNews && (advData.matchNews.home_news?.length || advData.matchNews.away_news?.length)">
        <div class="section-title"><FileTextIcon /><span>相关新闻动态</span></div>
        <div class="match-news-content">
          <div class="mn-section" v-if="advData.matchNews.home_news?.length">
            <div class="mn-team-label">{{ analysis.match?.home_team_cn || '主队' }}</div>
            <div class="mn-item" v-for="(n, i) in advData.matchNews.home_news.slice(0, 3)" :key="'h'+i">
              <span class="mn-title">{{ n.title }}</span>
              <span class="mn-date">{{ n.date || n.published }}</span>
            </div>
          </div>
          <div class="mn-section" v-if="advData.matchNews.away_news?.length">
            <div class="mn-team-label away">{{ analysis.match?.away_team_cn || '客队' }}</div>
            <div class="mn-item" v-for="(n, i) in advData.matchNews.away_news.slice(0, 3)" :key="'a'+i">
              <span class="mn-title">{{ n.title }}</span>
              <span class="mn-date">{{ n.date || n.published }}</span>
            </div>
          </div>
        </div>
      </section>
    </div><!-- /analysis-grid -->
    </div><!-- /v-else -->
  </div><!-- /match-page -->
</template>

<script>
import { ref, computed, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { matchAPI, analysisAPI } from '../api'

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
const CloudIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z' })])
const DiamondIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M2.7 10.3a2.41 2.41 0 0 0 0 3.41l7.59 7.59a2.41 2.41 0 0 0 3.41 0l7.59-7.59a2.41 2.41 0 0 0 0-3.41l-7.59-7.59a2.41 2.41 0 0 0-3.41 0z' })])
const LayersIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('polygon', { points: '12 2 2 7 12 12 22 7 12 2' }), h('polyline', { points: '2 17 12 22 22 17' }), h('polyline', { points: '2 12 12 17 22 12' })])
const BarIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('line', { x1: '18', y1: '20', x2: '18', y2: '10' }), h('line', { x1: '12', y1: '20', x2: '12', y2: '4' }), h('line', { x1: '6', y1: '20', x2: '6', y2: '14' })])
const ZapIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('polygon', { points: '13 2 3 14 12 14 11 22 21 10 12 10 13 2' })])
const FlameIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z' })])
const GitBranchIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('line', { x1: '6', y1: '3', x2: '6', y2: '15' }), h('circle', { cx: '18', cy: '6', r: '3' }), h('circle', { cx: '6', cy: '18', r: '3' }), h('path', { d: 'M18 9a9 9 0 0 1-9 9' })])
const FileTextIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' }), h('polyline', { points: '14 2 14 8 20 8' }), h('line', { x1: '16', y1: '13', x2: '8', y2: '13' }), h('line', { x1: '16', y1: '17', x2: '8', y2: '17' }), h('polyline', { points: '10 9 9 9 8 9' })])
const RefreshIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('polyline', { points: '23 4 23 10 17 10' }), h('path', { d: 'M20.49 15a9 9 0 1 1-2.12-9.36L23 10' })])
const UserIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2' }), h('circle', { cx: '12', cy: '7', r: '4' })])
const UsersIcon = () => h('svg', { class: 'icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }), h('circle', { cx: '9', cy: '7', r: '4' }), h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }), h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })])

export default {
  name: 'MatchPage',
  components: { BrainIcon, TrendingIcon, HomeIcon, SwordsIcon, TargetIcon, DollarIcon, StarIcon, AlertIcon, CalendarIcon, FireIcon, InfoIcon, ClockIcon, HalfIcon, NewsIcon, RestIcon, ArrowLeftIcon, CloudIcon, DiamondIcon, LayersIcon, BarIcon, ZapIcon, FlameIcon, GitBranchIcon, FileTextIcon, RefreshIcon, UserIcon, UsersIcon },
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
        const matchId = route.params.id

        // 并行获取比赛详情和综合分析
        const matchRes = await matchAPI.getMatch(matchId).catch(e => {
          error.value = '加载比赛数据失败: ' + (e.message || '未知错误')
          return null
        })
        const analysisRes = await matchAPI.getFullAnalysis(matchId).catch(() => null)

        // 同时加载高级分析模块数据
        loadAdvData(matchId)

        if (analysisRes?.error) {
          error.value = analysisRes.error
          return
        }

        const matchData = matchRes?.data || {}
        const data = analysisRes || {}

        // 解析综合分析API的嵌套结构
        const finalPred = data.final_prediction || {}
        const probs = finalPred.probabilities || {}
        const expectedScore = finalPred.expected_score || {}
        const mostLikelyScores = finalPred.most_likely_scores || []
        const overUnder = finalPred.over_under_2_5 || {}

        const eloPred = (data.base_prediction || {}).elo || {}
        const h2hData = data.h2h_analysis || {}
        const formData = data.form_comparison || {}
        const haData = data.home_away_analysis || {}

        // 构建比分预测
        let scorePrediction = null
        if (mostLikelyScores.length > 0) {
          const top = mostLikelyScores[0]
          const scoreParts = top.score ? top.score.split('-') : ['0', '0']
          const homeG = parseInt(scoreParts[0]) || 0
          const awayG = parseInt(scoreParts[1]) || 0
          const resultLabel = homeG > awayG ? '主胜' : homeG < awayG ? '客胜' : '平局'
          scorePrediction = {
            most_likely: { home: homeG, away: awayG, result: resultLabel },
            possible_scores: mostLikelyScores.slice(1, 4).map(s => {
              const p = s.score ? s.score.split('-') : ['0', '0']
              return { home: parseInt(p[0]) || 0, away: parseInt(p[1]) || 0, probability: s.probability }
            })
          }
        }

        // 从后端返回的form_comparison中提取home/away数据
        // formData结构: { last6: {team1_form, team2_form, comparison}, last10: {...}, last20: {...} }
        const buildPeriodData = (periodData) => ({
          wins: periodData?.wins || 0,
          draws: periodData?.draws || 0,
          losses: periodData?.losses || 0,
          goals_for: periodData?.goals_for || 0,
          goals_against: periodData?.goals_against || 0,
          matches: periodData?.matches || 0,
          form_score: periodData?.form_score || 0,
          points_per_game: periodData?.points_per_game || 0
        })
        const homeFormByPeriod = {
          last6: buildPeriodData(formData.last6?.team1_form),
          last10: buildPeriodData(formData.last10?.team1_form),
          last20: buildPeriodData(formData.last20?.team1_form)
        }
        const awayFormByPeriod = {
          last6: buildPeriodData(formData.last6?.team2_form),
          last10: buildPeriodData(formData.last10?.team2_form),
          last20: buildPeriodData(formData.last20?.team2_form)
        }

        // 构建主客场表现数据
        // home_away_analysis现在是: { last6: {home_team, away_team}, last10: {...}, last20: {...} }
        const buildHARecord = (record) => {
          if (!record) return {}
          return {
            wins: record.wins || 0,
            draws: record.draws || 0,
            losses: record.losses || 0,
            goals_for: record.goals_scored || record.goals_for || 0,
            goals_against: record.goals_conceded || record.goals_against || 0,
            matches: record.matches || 0,
            win_rate: record.win_rate || 0,
            points_per_game: record.points_per_game || 0
          }
        }
        // 从home_away_analysis提取各时段的主队主场、客队客场数据
        const homeHomeByPeriod = {
          last6: buildHARecord(haData.last6?.home_team?.home),
          last10: buildHARecord(haData.last10?.home_team?.home),
          last20: buildHARecord(haData.last20?.home_team?.home)
        }
        const awayAwayByPeriod = {
          last6: buildHARecord(haData.last6?.away_team?.away),
          last10: buildHARecord(haData.last10?.away_team?.away),
          last20: buildHARecord(haData.last20?.away_team?.away)
        }

        // 构建H2H比赛列表
        const h2hMatches = (h2hData.matches || []).map(m => ({
          match_id: m.match_id,
          match_date: m.match_date,
          home_team: m.home_team,
          away_team: m.away_team,
          home_team_cn: m.home_team_cn,
          away_team_cn: m.away_team_cn,
          home_goals: m.home_goals,
          away_goals: m.away_goals
        }))

        // 构建大小球数据
        let overUnderData = null
        if (overUnder) {
          const overProb = overUnder.over || overUnder.probability || 0
          const underProb = overUnder.under || (1 - overProb)
          overUnderData = {
            predicted_total_goals: ((expectedScore.home || 0) + (expectedScore.away || 0)).toFixed(1),
            over_2_5_prob: Math.round(overProb * 100),
            under_2_5_prob: Math.round(underProb * 100),
            recommendation: overProb > 0.5 ? '大2.5' : '小2.5'
          }
        }

        analysis.value = {
          // 比赛基本信息
          match: {
            match_id: matchId,
            match_date: matchData.match_date || data.match_date,
            match_time: matchData.match_time,
            beijing_time: matchData.beijing_time,
            home_team_id: matchData.home_team_id || data.home_team_id,
            away_team_id: matchData.away_team_id || data.away_team_id,
            home_team: matchData.home_team,
            away_team: matchData.away_team,
            home_team_cn: matchData.home_team_cn || matchData.home_team,
            away_team_cn: matchData.away_team_cn || matchData.away_team,
            league: matchData.league,
            league_cn: matchData.league_cn || matchData.league,
            league_id: matchData.league_id || data.league_id,
            season_id: matchData.season_id || data.season_id,
            home_goals: matchData.home_goals,
            away_goals: matchData.away_goals
          },
          // Elo
          elo: {
            home: Math.round(eloPred.home_elo || 0),
            away: Math.round(eloPred.away_elo || 0),
            diff: Math.round(eloPred.elo_diff || 0)
          },
          // 预测
          prediction: {
            home_win_prob: Math.round((probs.home_win || 0) * 100),
            draw_prob: Math.round((probs.draw || 0) * 100),
            away_win_prob: Math.round((probs.away_win || 0) * 100),
            predicted_home_goals: expectedScore.home || 0,
            predicted_away_goals: expectedScore.away || 0
          },
          // 比分预测
          score_prediction: scorePrediction,
          // 近期战绩
          form: {
            home: homeFormByPeriod,
            away: awayFormByPeriod
          },
          // 主客场表现
          home_away: {
            home_at_home: homeHomeByPeriod,
            away_at_away: awayAwayByPeriod
          },
          // H2H交锋
          h2h: {
            stats: h2hData.total_matches > 0 ? {
              home_wins: (h2hData.overall_record || {}).team1_wins || 0,
              draws: (h2hData.overall_record || {}).draws || 0,
              away_wins: (h2hData.overall_record || {}).team2_wins || 0
            } : null,
            matches: h2hMatches
          },
          // 心理压制
          psychology: (h2hData.psychological_advantage || {}).description
            ? { description: h2hData.psychological_advantage.description }
            : null,
          // 敌对关系
          rivalry: data.rivalry_analysis || null,
          // 大小球
          over_under: overUnderData,
          // 报告摘要
          report: data.report || ''
        }
      } catch (e) {
        console.error('加载分析数据失败:', e)
        error.value = '加载分析数据失败'
      } finally {
        loading.value = false
      }
    }

    onMounted(loadAnalysis)
    // 高级分析模块 - 页面加载时并行获取
    const advData = ref({})

    const loadAdvData = async (matchId) => {
      // 从analysis中获取team IDs和league/season信息
      const match = analysis.value.match || {}
      const homeId = match.home_team_id
      const awayId = match.away_team_id
      const leagueId = match.league_id
      const seasonId = match.season_id
      const matchDate = match.match_date

      // 基于matchId的端点
      const matchEndpoints = {
        xg: () => analysisAPI.getMatchXG(matchId),
        fatigue: () => analysisAPI.getMatchFatigue(matchId),
        referee: () => analysisAPI.getRefereeImpact(matchId),
        venue: () => analysisAPI.getVenueImpact(matchId),
        leagueImpact: () => analysisAPI.getMatchImpact(matchId),
        timezone: () => analysisAPI.getMatchLocalTimes(matchId),
        valueBets: () => analysisAPI.getMatchValueBets(matchId),
        preview: () => analysisAPI.getMatchPreview(matchId),
        weather: () => analysisAPI.getMatchWeather(matchId),
        ml: () => analysisAPI.getMLPrediction(matchId),
        modelComp: () => analysisAPI.getModelComparison(matchId),
        features: () => analysisAPI.getFeatureImportance(matchId),
        matchNews: () => analysisAPI.getMatchNews(matchId)
      }

      // 基于teamIds的端点（需要两个队伍ID）
      const teamEndpoints = {}
      if (homeId && awayId) {
        teamEndpoints.handicap = () => analysisAPI.compareTeamsHandicap(homeId, awayId)
        teamEndpoints.efficiency = () => analysisAPI.compareTeamsEfficiency(homeId, awayId, leagueId, seasonId)
        teamEndpoints.upset = () => analysisAPI.analyzeUpsetPotential(homeId, awayId, leagueId, seasonId)
        teamEndpoints.h2hPatterns = () => analysisAPI.getH2HPatterns(homeId, awayId)
        teamEndpoints.motivation = () => analysisAPI.compareTeamsMotivation(homeId, awayId, leagueId, seasonId)
        teamEndpoints.factors = () => analysisAPI.compareTeamsFactors(homeId, awayId)
        teamEndpoints.sixPointer = () => analysisAPI.getSixPointerAnalysis(homeId, awayId, leagueId, seasonId)
        teamEndpoints.poissonHome = () => analysisAPI.getTeamGoalDistribution(homeId, true)
        teamEndpoints.poissonAway = () => analysisAPI.getTeamGoalDistribution(awayId, false)
        teamEndpoints.rotationRiskHome = () => analysisAPI.getRotationRisk(homeId, leagueId, seasonId)
        teamEndpoints.rotationRiskAway = () => analysisAPI.getRotationRisk(awayId, leagueId, seasonId)
        teamEndpoints.seasonScenarioHome = () => analysisAPI.getTeamSeasonScenario(homeId, leagueId, seasonId)
        teamEndpoints.seasonScenarioAway = () => analysisAPI.getTeamSeasonScenario(awayId, leagueId, seasonId)
        teamEndpoints.managerChangeHome = () => analysisAPI.getManagerChangeEffect(homeId, matchDate).catch(() => null)
        teamEndpoints.managerChangeAway = () => analysisAPI.getManagerChangeEffect(awayId, matchDate).catch(() => null)
        teamEndpoints.squadHome = () => Promise.resolve(null)
        teamEndpoints.squadAway = () => Promise.resolve(null)
      }

      const results = {}
      const allEndpoints = { ...matchEndpoints, ...teamEndpoints }
      const promises = Object.entries(allEndpoints).map(async ([key, fn]) => {
        try { results[key] = await fn() } catch (e) { console.warn(`分析模块 ${key} 加载失败:`, e.message) }
      })
      await Promise.all(promises)
      advData.value = results
    }

    // 泊松分布比分计算
    const getTopScorelines = (homeDist, awayDist, count = 4) => {
      if (!homeDist?.length || !awayDist?.length) return []
      const scores = []
      for (let h = 0; h < Math.min(homeDist.length, 5); h++) {
        for (let a = 0; a < Math.min(awayDist.length, 5); a++) {
          scores.push({ score: `${h}-${a}`, prob: homeDist[h] * awayDist[a] })
        }
      }
      scores.sort((a, b) => b.prob - a.prob)
      return scores.slice(0, count)
    }

    return { loading, error, analysis, matchStatus, statusText, goToTeam, goBack, selectedPeriod, homeForm, awayForm, homeHomeStats, awayAwayStats, avgPoints, advData, getTopScorelines }
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

/* 高级分析网格 */
.analysis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 4px; }
.analysis-grid .section-block { grid-column: auto; }
.analysis-group-title { grid-column: 1 / -1; display: flex; align-items: center; gap: 8px; padding: 8px 4px; font-size: 14px; font-weight: 700; color: #10b981; border-bottom: 1px solid rgba(16, 185, 129, 0.2); margin-bottom: -4px; }
.analysis-group-title .icon { width: 16px; height: 16px; }
.analysis-full { grid-column: 1 / -1; }

/* 区域块 */
.section-block { background: #151922; border-radius: 10px; border: 1px solid rgba(31, 41, 55, 0.5); overflow: hidden; }
.section-title { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: rgba(255,255,255,0.02); border-bottom: 1px solid rgba(31, 41, 55, 0.5); font-size: 14px; font-weight: 600; color: #e5e7eb; }
.section-title .icon { width: 16px; height: 16px; color: #10b981; }

/* 卡片行布局 */
.cards-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: rgba(31, 41, 55, 0.3); }
.cards-row .card { background: #151922; border-bottom: none; }

/* 三场景单行布局 */
.scenarios-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 10px; }
.scenario-item { background: rgba(255,255,255,0.02); border-radius: 8px; text-align: center; }
.scenario-header { font-size: 13px; font-weight: 600; color: #e5e7eb; padding: 8px; background: rgba(255,255,255,0.01); border-radius: 8px 8px 0 0; }
.scenario-body { padding: 8px; }
.scenario-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; margin-bottom: 2px; }
.scenario-row .s-label { font-size: 11px; color: #6b7280; }
.scenario-row .s-value { font-size: 12px; font-weight: 600; }
.scenario-row .s-value.home { color: #10b981; }
.scenario-row .s-value.away { color: #60a5fa; }

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
.info-value.home { color: #10b981; }
.info-value.away { color: #60a5fa; }
.info-value.accent { color: #fbbf24; }
.info-value.negative { color: #ef4444; }

/* 疲劳影响标签 */
.impact-badge { font-size: 11px; padding: 3px 10px; border-radius: 10px; font-weight: 500; display: inline-block; }
.impact-badge.low { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.impact-badge.medium { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.impact-badge.high { background: rgba(239, 68, 68, 0.15); color: #ef4444; }

/* 比赛前瞻 */
.preview-content { padding: 12px; }
.preview-factors { display: flex; flex-direction: column; gap: 6px; }
.factor-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.factor-label { font-size: 13px; color: #e5e7eb; font-weight: 500; }
.factor-impact { font-size: 12px; font-weight: 500; }
.factor-impact.positive { color: #10b981; }
.factor-impact.negative { color: #ef4444; }
.factor-impact.neutral { color: #9ca3af; }
.preview-summary { padding: 10px; margin-top: 8px; background: rgba(255,255,255,0.02); border-radius: 6px; font-size: 12px; color: #9ca3af; line-height: 1.5; border-top: 1px solid rgba(31, 41, 55, 0.3); }
.preview-rec { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 8px; background: rgba(16, 185, 129, 0.1); border-radius: 6px; margin-top: 6px; border-top: 1px solid rgba(31, 41, 55, 0.3); }

/* 价值投注 */
.value-bet-content { padding: 12px; }
.vb-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: rgba(255,255,255,0.02); border-radius: 6px; margin-bottom: 10px; }
.vb-label { font-size: 12px; color: #6b7280; }
.vb-odds { display: flex; gap: 12px; font-size: 13px; color: #e5e7eb; font-weight: 500; }
.vb-list { display: flex; flex-direction: column; gap: 8px; }
.vb-item { padding: 10px 12px; background: rgba(255,255,255,0.02); border-radius: 8px; border-left: 3px solid transparent; }
.vb-item.high { border-left-color: #10b981; background: rgba(16, 185, 129, 0.05); }
.vb-item.medium { border-left-color: #fbbf24; background: rgba(251, 191, 36, 0.05); }
.vb-item.low { border-left-color: #6b7280; }
.vb-market { font-size: 13px; font-weight: 600; color: #e5e7eb; margin-bottom: 6px; }
.vb-stats { display: flex; gap: 16px; flex-wrap: wrap; }
.vb-stat { display: flex; flex-direction: column; gap: 2px; }
.vb-stat .s-label { font-size: 10px; color: #6b7280; }
.vb-stat .s-value { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.vb-stat.highlight .s-value { color: #10b981; }
.vb-rating { display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; margin-top: 6px; }
.vb-rating.high { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.vb-rating.medium { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.vb-rating.low { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.vb-summary { font-size: 12px; color: #9ca3af; padding: 8px 10px; margin-top: 8px; border-top: 1px solid rgba(31, 41, 55, 0.3); line-height: 1.4; }

/* 天气数据 */
.weather-content { padding: 12px; }
.weather-main { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
.temp-value { font-size: 28px; font-weight: 700; color: #e5e7eb; }
.temp-desc { font-size: 13px; color: #9ca3af; display: block; }
.weather-details { display: flex; flex-direction: column; gap: 6px; }
.w-item { display: flex; align-items: center; gap: 8px; }
.w-label { font-size: 11px; color: #6b7280; }
.w-value { font-size: 13px; color: #e5e7eb; font-weight: 500; }
.weather-impact { padding: 10px; background: rgba(255,255,255,0.02); border-radius: 6px; border-top: 1px solid rgba(31, 41, 55, 0.3); margin-top: 8px; }
.impact-title { font-size: 12px; color: #e5e7eb; font-weight: 600; margin-bottom: 8px; }
.impact-factors { display: flex; gap: 16px; flex-wrap: wrap; }
.impact-item { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.impact-item .i-label { font-size: 10px; color: #6b7280; }
.impact-item .i-value { font-size: 14px; font-weight: 600; color: #10b981; }
.impact-item .i-value.negative { color: #ef4444; }
.impact-desc { display: flex; flex-direction: column; gap: 3px; margin-top: 8px; font-size: 11px; color: #9ca3af; }

/* ML深度预测 */
.ml-content { padding: 12px; }
.ml-probs { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.ml-prob-item { display: flex; align-items: center; gap: 8px; }
.ml-label { font-size: 12px; color: #9ca3af; width: 32px; }
.ml-prob-bar { flex: 1; height: 16px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; }
.ml-bar { height: 100%; border-radius: 4px; transition: width 0.3s; }
.ml-bar.home { background: linear-gradient(90deg, #10b981, #059669); }
.ml-bar.draw { background: #4b5563; }
.ml-bar.away { background: linear-gradient(90deg, #3b82f6, #2563eb); }
.ml-pct { font-size: 12px; font-weight: 600; color: #e5e7eb; width: 48px; text-align: right; }
.ml-meta { display: flex; gap: 12px; flex-wrap: wrap; padding: 8px 10px; background: rgba(255,255,255,0.02); border-radius: 6px; margin-bottom: 8px; }
.ml-meta-item { font-size: 11px; color: #9ca3af; }
.ml-prediction { display: flex; align-items: center; gap: 10px; padding: 10px; background: rgba(16, 185, 129, 0.08); border-radius: 6px; border: 1px solid rgba(16, 185, 129, 0.2); }
.ml-pred-label { font-size: 12px; color: #9ca3af; }
.ml-pred-value { font-size: 16px; font-weight: 700; color: #10b981; }
.ml-confidence { font-size: 12px; color: #fbbf24; margin-left: auto; }

/* 多模型对比 */
.model-comp-content { padding: 12px; }
.model-table { display: flex; flex-direction: column; gap: 2px; }
.model-header { display: grid; grid-template-columns: 1.2fr 0.7fr 0.7fr 0.7fr 0.7fr; gap: 4px; padding: 6px 10px; font-size: 11px; color: #6b7280; border-bottom: 1px solid rgba(31,41,55,0.3); }
.model-row { display: grid; grid-template-columns: 1.2fr 0.7fr 0.7fr 0.7fr 0.7fr; gap: 4px; padding: 6px 10px; font-size: 12px; background: rgba(255,255,255,0.02); border-radius: 4px; }
.model-name { color: #e5e7eb; font-weight: 500; }
.model-prob { color: #9ca3af; }
.model-pred { font-weight: 600; }
.model-pred.home { color: #10b981; }
.model-pred.draw { color: #9ca3af; }
.model-pred.away { color: #60a5fa; }
.model-consensus { display: flex; align-items: center; gap: 8px; padding: 8px 10px; margin-top: 6px; background: rgba(16, 185, 129, 0.08); border-radius: 6px; }
.consensus-label { font-size: 12px; color: #9ca3af; }
.consensus-value { font-size: 13px; font-weight: 600; color: #10b981; }

/* 特征重要性 */
.features-content { padding: 12px; display: flex; flex-direction: column; gap: 6px; }
.feature-bar-item { display: flex; align-items: center; gap: 8px; }
.feature-name { font-size: 12px; color: #9ca3af; width: 80px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }
.feature-bar-wrap { flex: 1; height: 10px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden; }
.feature-bar { height: 100%; background: linear-gradient(90deg, #10b981, #059669); border-radius: 3px; }
.feature-val { font-size: 11px; color: #e5e7eb; font-weight: 500; width: 40px; text-align: right; }

/* 让球分析 */
.handicap-content { padding: 12px; }
.hc-main { display: flex; gap: 20px; margin-bottom: 10px; }
.hc-line { display: flex; align-items: center; gap: 6px; }
.hc-label { font-size: 12px; color: #6b7280; }
.hc-value { font-size: 18px; font-weight: 700; color: #fbbf24; }
.hc-scenarios { display: flex; flex-direction: column; gap: 4px; }
.hc-scenario { display: flex; align-items: center; gap: 12px; padding: 6px 10px; background: rgba(255,255,255,0.02); border-radius: 4px; font-size: 12px; }
.sc-line { color: #e5e7eb; font-weight: 500; min-width: 70px; }
.sc-prob { color: #9ca3af; }
.hc-summary { font-size: 12px; color: #9ca3af; padding: 8px 10px; margin-top: 8px; border-top: 1px solid rgba(31,41,55,0.3); line-height: 1.4; }

/* 效率对比 */
.efficiency-content { padding: 12px; }
.eff-compare { display: flex; flex-direction: column; gap: 12px; }
.eff-category { }
.eff-cat-name { font-size: 12px; color: #e5e7eb; font-weight: 600; margin-bottom: 4px; }
.eff-bars { display: flex; flex-direction: column; gap: 3px; }
.eff-bar-row { display: flex; align-items: center; gap: 6px; }
.eff-team { font-size: 10px; color: #6b7280; width: 18px; }
.eff-bar-wrap { flex: 1; height: 8px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden; }
.eff-bar { height: 100%; border-radius: 3px; }
.eff-bar.home { background: #10b981; }
.eff-bar.away { background: #3b82f6; }
.eff-val { font-size: 11px; color: #e5e7eb; width: 36px; text-align: right; }
.eff-summary { font-size: 12px; color: #9ca3af; padding: 8px 10px; margin-top: 8px; border-top: 1px solid rgba(31,41,55,0.3); line-height: 1.4; }

/* 爆冷分析 */
.upset-content { padding: 12px; }
.upset-score { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.upset-label { font-size: 12px; color: #9ca3af; }
.upset-bar-wrap { flex: 1; height: 16px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; }
.upset-bar { height: 100%; border-radius: 4px; transition: width 0.3s; }
.upset-bar.high { background: linear-gradient(90deg, #ef4444, #dc2626); }
.upset-bar.medium { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.upset-bar.low { background: linear-gradient(90deg, #10b981, #059669); }
.upset-pct { font-size: 14px; font-weight: 700; color: #e5e7eb; }
.upset-factors { display: flex; flex-direction: column; gap: 4px; }
.upset-factor { display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: rgba(255,255,255,0.02); border-radius: 4px; }
.uf-name { font-size: 12px; color: #e5e7eb; }
.uf-impact { font-size: 11px; font-weight: 500; }
.uf-impact.positive { color: #ef4444; }
.uf-impact.negative { color: #10b981; }
.uf-impact.neutral { color: #9ca3af; }
.upset-historical { display: flex; align-items: center; gap: 8px; padding: 8px 10px; margin-top: 6px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.uh-label { font-size: 12px; color: #6b7280; }
.uh-value { font-size: 13px; color: #e5e7eb; font-weight: 500; }
.upset-assessment { font-size: 12px; color: #9ca3af; padding: 8px 10px; margin-top: 6px; border-top: 1px solid rgba(31,41,55,0.3); line-height: 1.4; }

/* 六分之战 */
.sixptr-content { padding: 12px; }
.sixptr-main { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.sixptr-badge { font-size: 13px; font-weight: 700; padding: 4px 12px; border-radius: 6px; }
.sixptr-badge.yes { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.sixptr-badge.no { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.sixptr-desc { font-size: 12px; color: #9ca3af; }
.sixptr-scenarios { display: flex; flex-direction: column; gap: 4px; }
.sp-scenario { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: rgba(255,255,255,0.02); border-radius: 4px; }
.sp-result { font-size: 12px; font-weight: 600; min-width: 40px; }
.sp-result.home { color: #10b981; }
.sp-result.draw { color: #9ca3af; }
.sp-result.away { color: #60a5fa; }
.sp-impact { font-size: 12px; color: #9ca3af; }
.sixptr-motivation { display: flex; gap: 20px; margin-top: 10px; padding: 8px 10px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.sp-mot-item { display: flex; align-items: center; gap: 6px; }
.sp-mot-label { font-size: 12px; color: #6b7280; }
.sp-mot-val { font-size: 13px; font-weight: 600; }
.sp-mot-val.home { color: #10b981; }
.sp-mot-val.away { color: #60a5fa; }

/* 战意对比 */
.motivation-content { padding: 12px; }
.mot-compare { display: flex; gap: 20px; }
.mot-side { flex: 1; display: flex; flex-direction: column; gap: 4px; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.mot-side.away { align-items: flex-end; }
.mot-team { font-size: 13px; color: #e5e7eb; font-weight: 600; }
.mot-score { font-size: 16px; font-weight: 700; color: #fbbf24; }
.mot-reason { font-size: 11px; color: #9ca3af; }
.mot-summary { font-size: 12px; color: #9ca3af; padding: 8px 10px; margin-top: 8px; border-top: 1px solid rgba(31,41,55,0.3); line-height: 1.4; }

/* H2H模式分析 */
.h2h-patterns-content { padding: 12px; }
.hp-trends { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.hp-trend-item { display: flex; align-items: center; gap: 6px; padding: 4px 10px; background: rgba(255,255,255,0.03); border-radius: 4px; }
.hp-label { font-size: 11px; color: #6b7280; }
.hp-value { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.hp-value.home { color: #10b981; }
.hp-value.away { color: #60a5fa; }
.hp-value.accent { color: #fbbf24; }
.hp-patterns { display: flex; flex-direction: column; gap: 4px; }
.hp-pattern { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: rgba(255,255,255,0.02); border-radius: 4px; }
.hpat-name { font-size: 12px; color: #e5e7eb; font-weight: 500; min-width: 70px; }
.hpat-desc { font-size: 12px; color: #9ca3af; }
.hp-dominance { display: flex; align-items: center; gap: 8px; padding: 8px 10px; margin-top: 8px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.hp-dom-label { font-size: 12px; color: #6b7280; }
.hp-dom-value { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.hp-dom-value.home { color: #10b981; }
.hp-dom-value.away { color: #60a5fa; }

/* 泊松分布 */
.poisson-content { padding: 12px; }
.pois-params { display: flex; gap: 20px; margin-bottom: 12px; }
.pois-param { display: flex; flex-direction: column; gap: 2px; flex: 1; padding: 8px 10px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.pois-param.away { align-items: flex-end; }
.pois-team { font-size: 12px; color: #e5e7eb; font-weight: 500; }
.pois-lambda { font-size: 18px; font-weight: 700; color: #fbbf24; }
.pois-exp { font-size: 11px; color: #9ca3af; }
.pois-dist { display: flex; flex-direction: column; gap: 10px; margin-bottom: 10px; }
.pois-row { display: flex; align-items: flex-end; gap: 8px; }
.pois-row-label { font-size: 11px; color: #6b7280; width: 50px; writing-mode: vertical-lr; text-align: center; }
.pois-bars { display: flex; align-items: flex-end; gap: 4px; flex: 1; height: 60px; }
.pois-bar-item { display: flex; flex-direction: column; align-items: center; gap: 2px; flex: 1; height: 100%; justify-content: flex-end; }
.pois-bar { width: 100%; border-radius: 3px 3px 0 0; min-height: 2px; transition: height 0.3s; }
.pois-bar.home { background: #10b981; }
.pois-bar.away { background: #3b82f6; }
.pois-g { font-size: 10px; color: #6b7280; }
.pois-p { font-size: 9px; color: #9ca3af; }
.pois-scoreline { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: rgba(16, 185, 129, 0.08); border-radius: 6px; flex-wrap: wrap; }
.pois-sl-label { font-size: 12px; color: #9ca3af; }
.pois-scores { display: flex; gap: 8px; flex-wrap: wrap; }
.pois-score { font-size: 13px; font-weight: 600; color: #e5e7eb; padding: 2px 8px; background: rgba(255,255,255,0.05); border-radius: 4px; }
.pois-score small { font-size: 10px; color: #fbbf24; font-weight: 400; }

/* 比赛新闻 */
.match-news-content { padding: 12px; display: flex; flex-direction: column; gap: 12px; }
.mn-section { }
.mn-team-label { font-size: 12px; font-weight: 600; color: #10b981; margin-bottom: 4px; padding-left: 4px; border-left: 2px solid #10b981; }
.mn-team-label.away { color: #60a5fa; border-left-color: #60a5fa; }
.mn-item { display: flex; flex-direction: column; gap: 2px; padding: 6px 10px; background: rgba(255,255,255,0.02); border-radius: 4px; }
.mn-title { font-size: 12px; color: #e5e7eb; line-height: 1.4; }
.mn-date { font-size: 10px; color: #6b7280; }

/* 赛季走势 */
.season-scenario-content { padding: 12px; }
.ss-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.ss-side { display: flex; flex-direction: column; gap: 6px; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 8px; }
.ss-team { font-size: 13px; font-weight: 600; color: #10b981; }
.ss-team.away { color: #60a5fa; }
.ss-items { display: flex; flex-wrap: wrap; gap: 6px; }
.ss-item { display: flex; align-items: center; gap: 4px; }
.ss-label { font-size: 11px; color: #6b7280; }
.ss-val { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.ss-val.positive { color: #10b981; }
.ss-val.negative { color: #ef4444; }
.ss-val.accent { color: #fbbf24; }
.ss-desc { font-size: 11px; color: #9ca3af; line-height: 1.4; }

/* 轮换风险 */
.rotation-content { padding: 12px; }
.rot-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.rot-side { display: flex; flex-direction: column; gap: 6px; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 8px; }
.rot-team { font-size: 13px; font-weight: 600; color: #10b981; }
.rot-team.away { color: #60a5fa; }
.rot-risk { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 4px; width: fit-content; }
.rot-risk.high { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.rot-risk.medium { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.rot-risk.low { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.rot-prob { font-size: 11px; color: #9ca3af; }
.rot-reasons { display: flex; flex-direction: column; gap: 2px; }
.rot-reason { font-size: 11px; color: #9ca3af; padding-left: 8px; border-left: 2px solid rgba(31,41,55,0.5); }

/* 换帅效应 */
.manager-change-content { padding: 12px; display: flex; flex-direction: column; gap: 12px; }
.mc-side { display: flex; flex-direction: column; gap: 6px; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 8px; border-left: 3px solid #f59e0b; }
.mc-team { font-size: 13px; font-weight: 600; color: #10b981; }
.mc-team.away { color: #60a5fa; }
.mc-info { display: flex; gap: 12px; font-size: 12px; color: #9ca3af; }
.mc-coaches { color: #e5e7eb; font-weight: 500; }
.mc-bounce { display: flex; align-items: center; gap: 8px; }
.mc-bounce-label { font-size: 12px; color: #6b7280; }
.mc-bounce-val { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.mc-bounce-val.positive { color: #10b981; }
.mc-bounce-val.negative { color: #ef4444; }

/* 阵容分析 */
.squad-content { padding: 12px; }
.sq-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.sq-side { display: flex; flex-direction: column; gap: 6px; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 8px; }
.sq-team { font-size: 13px; font-weight: 600; color: #10b981; }
.sq-team.away { color: #60a5fa; }
.sq-stats { display: flex; flex-wrap: wrap; gap: 6px; }
.sq-stat { display: flex; align-items: center; gap: 4px; }
.sq-label { font-size: 11px; color: #6b7280; }
.sq-val { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.sq-val.negative { color: #ef4444; }
.sq-players { display: flex; flex-wrap: wrap; gap: 4px; }
.sq-mp { font-size: 10px; color: #fbbf24; background: rgba(251, 191, 36, 0.1); padding: 2px 6px; border-radius: 3px; }

/* 天气数据 */
.weather-content { padding: 12px; }
.weather-main { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.weather-temp { display: flex; flex-direction: column; align-items: center; }
.temp-value { font-size: 24px; font-weight: 700; color: #fbbf24; }
.temp-desc { font-size: 12px; color: #9ca3af; margin-top: 4px; }
.weather-details { display: flex; gap: 16px; }
.w-item { display: flex; flex-direction: column; align-items: center; }
.w-label { font-size: 11px; color: #6b7280; }
.w-value { font-size: 14px; font-weight: 600; color: #e5e7eb; }
.weather-impact { padding: 10px; background: rgba(255,255,255,0.02); border-radius: 8px; }
.impact-title { font-size: 12px; font-weight: 600; color: #9ca3af; margin-bottom: 8px; text-align: center; }
.impact-factors { display: flex; justify-content: center; gap: 12px; margin-bottom: 8px; }
.impact-item { display: flex; flex-direction: column; align-items: center; padding: 6px 12px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.i-label { font-size: 10px; color: #6b7280; }
.i-value { font-size: 14px; font-weight: 600; color: #10b981; }
.i-value.negative { color: #ef4444; }
.impact-desc { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: #9ca3af; text-align: center; }

/* 价值投注 */
.value-bet-content { padding: 12px; }
.vb-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 8px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.vb-header .vb-label { font-size: 11px; color: #6b7280; }
.vb-odds { display: flex; gap: 12px; font-size: 13px; color: #fbbf24; font-weight: 600; }
.vb-list { display: flex; flex-direction: column; gap: 8px; }
.vb-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(255,255,255,0.02); border-radius: 8px; border-left: 3px solid #6b7280; }
.vb-item.high { border-left-color: #10b981; background: rgba(16, 185, 129, 0.1); }
.vb-item.medium { border-left-color: #fbbf24; background: rgba(251, 191, 36, 0.1); }
.vb-item.low { border-left-color: #60a5fa; }
.vb-market { font-size: 14px; font-weight: 600; color: #e5e7eb; }
.vb-stats { display: flex; gap: 12px; }
.vb-stat { display: flex; flex-direction: column; align-items: center; }
.vb-stat .s-label { font-size: 10px; color: #6b7280; }
.vb-stat .s-value { font-size: 12px; font-weight: 600; color: #e5e7eb; }
.vb-stat.highlight .s-value { color: #10b981; }
.vb-rating { font-size: 11px; padding: 4px 10px; border-radius: 10px; }
.vb-rating.high { background: rgba(16, 185, 129, 0.2); color: #10b981; }
.vb-rating.medium { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
.vb-rating.low { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.vb-summary { margin-top: 10px; padding: 8px; background: rgba(16, 185, 129, 0.1); border-radius: 6px; font-size: 12px; color: #10b981; text-align: center; }

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
  .ss-grid { grid-template-columns: 1fr; }
  .rot-grid { grid-template-columns: 1fr; }
  .sq-grid { grid-template-columns: 1fr; }
  .pois-params { flex-direction: column; gap: 8px; }
  .analysis-grid { grid-template-columns: 1fr; }
}
</style>
