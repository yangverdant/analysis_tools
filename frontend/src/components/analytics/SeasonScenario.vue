<template>
  <div class="season-scenario">
    <!-- Header -->
    <div class="header card">
      <div class="header-content">
        <h2>
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M2 20h20" /><path d="M5 20V8l7-5 7 5v12" /><path d="M9 20v-6h6v6" />
          </svg>
          赛季推理
        </h2>
        <p>积分形势、争冠保级、轮换风险、6分战分析</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs card">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab: 赛季形势 -->
    <div v-if="activeTab === 'scenario'" class="tab-content">
      <div class="input-row card">
        <div class="input-group">
          <label>球队 ID</label>
          <input v-model="scenarioInput.teamId" type="number" placeholder="如 42" />
        </div>
        <div class="input-group">
          <label>联赛 ID</label>
          <input v-model="scenarioInput.leagueId" type="number" placeholder="如 39" />
        </div>
        <div class="input-group">
          <label>赛季 ID</label>
          <input v-model="scenarioInput.seasonId" type="number" placeholder="如 2024" />
        </div>
        <button class="query-btn" @click="loadScenario" :disabled="scenarioLoading">
          {{ scenarioLoading ? '分析中...' : '分析' }}
        </button>
      </div>

      <div v-if="scenarioLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在分析赛季形势...</p>
      </div>

      <template v-if="scenarioData && !scenarioLoading">
        <!-- Current Status -->
        <div class="card section-card" v-if="scenarioData.current_status">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
              <path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            当前状态
          </h3>
          <div class="status-grid">
            <div class="status-item highlight">
              <span class="status-label">球队</span>
              <span class="status-value name">{{ scenarioData.current_status.team_name || '--' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">排名</span>
              <span class="status-value">{{ scenarioData.current_status.position || '--' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">积分</span>
              <span class="status-value accent">{{ scenarioData.current_status.points || 0 }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">已赛</span>
              <span class="status-value">{{ scenarioData.current_status.played || 0 }}</span>
            </div>
            <div class="status-item win">
              <span class="status-label">胜</span>
              <span class="status-value">{{ scenarioData.current_status.won || 0 }}</span>
            </div>
            <div class="status-item draw">
              <span class="status-label">平</span>
              <span class="status-value">{{ scenarioData.current_status.drawn || 0 }}</span>
            </div>
            <div class="status-item loss">
              <span class="status-label">负</span>
              <span class="status-value">{{ scenarioData.current_status.lost || 0 }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">净胜球</span>
              <span class="status-value" :class="scenarioData.current_status.goal_diff > 0 ? 'positive' : scenarioData.current_status.goal_diff < 0 ? 'negative' : ''">
                {{ scenarioData.current_status.goal_diff > 0 ? '+' : '' }}{{ scenarioData.current_status.goal_diff || 0 }}
              </span>
            </div>
          </div>
        </div>

        <!-- Season Progress -->
        <div class="card section-card" v-if="scenarioData.season_progress">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
            </svg>
            赛季进度
          </h3>
          <div class="progress-info">
            <div class="progress-stats">
              <div class="progress-stat">
                <span class="progress-label">总轮次</span>
                <span class="progress-value">{{ scenarioData.season_progress.total_rounds || 0 }}</span>
              </div>
              <div class="progress-stat">
                <span class="progress-label">已完赛</span>
                <span class="progress-value">{{ scenarioData.season_progress.played || 0 }}</span>
              </div>
              <div class="progress-stat">
                <span class="progress-label">剩余</span>
                <span class="progress-value">{{ scenarioData.season_progress.remaining || 0 }}</span>
              </div>
            </div>
            <div class="progress-bar-wrap">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: (scenarioData.season_progress.progress_pct || 0) + '%' }"></div>
              </div>
              <span class="progress-pct">{{ (scenarioData.season_progress.progress_pct || 0).toFixed(1) }}%</span>
            </div>
          </div>
        </div>

        <!-- Points Projection -->
        <div class="card section-card" v-if="scenarioData.points_projection">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            积分预测
          </h3>
          <div class="projection-grid">
            <div class="projection-item current">
              <span class="proj-label">当前积分</span>
              <span class="proj-value">{{ scenarioData.points_projection.current || 0 }}</span>
            </div>
            <div class="projection-item max">
              <span class="proj-label">理论最高</span>
              <span class="proj-value">{{ scenarioData.points_projection.max_possible || 0 }}</span>
            </div>
            <div class="projection-item min">
              <span class="proj-label">理论最低</span>
              <span class="proj-value">{{ scenarioData.points_projection.min_possible || 0 }}</span>
            </div>
            <div class="projection-item realistic">
              <span class="proj-label">现实最高</span>
              <span class="proj-value">{{ scenarioData.points_projection.realistic_max || 0 }}</span>
            </div>
            <div class="projection-item avg">
              <span class="proj-label">平均预测</span>
              <span class="proj-value">{{ scenarioData.points_projection.avg_projection || 0 }}</span>
            </div>
          </div>
        </div>

        <!-- Zone Gaps -->
        <div class="card section-card" v-if="scenarioData.zone_gaps">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
            </svg>
            区域差距
          </h3>
          <div class="zone-grid">
            <div class="zone-item" v-for="(zone, key) in scenarioData.zone_gaps" :key="key" :class="zone.status">
              <div class="zone-header">
                <span class="zone-name">{{ getZoneLabel(key) }}</span>
                <span class="zone-status-badge" :class="zone.status">{{ getZoneStatusLabel(zone.status) }}</span>
              </div>
              <div class="zone-gap" v-if="zone.gap !== undefined">
                差距: <span :class="zone.gap > 0 ? 'negative' : 'positive'">{{ zone.gap > 0 ? '+' : '' }}{{ zone.gap }}</span> 分
              </div>
              <div class="zone-desc" v-if="zone.description">{{ zone.description }}</div>
            </div>
          </div>
        </div>

        <!-- Motivation Assessment -->
        <div class="card section-card" v-if="scenarioData.motivation_assessment">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
            战意评估
          </h3>
          <div class="motivation-block" :class="scenarioData.motivation_assessment.level">
            <div class="motivation-level">
              <span class="level-badge" :class="scenarioData.motivation_assessment.level">
                {{ getMotivationLabel(scenarioData.motivation_assessment.level) }}
              </span>
            </div>
            <div class="motivation-desc" v-if="scenarioData.motivation_assessment.description">
              {{ scenarioData.motivation_assessment.description }}
            </div>
            <div class="motivation-details">
              <div class="detail-row" v-if="scenarioData.motivation_assessment.rotation_risk">
                <span class="detail-label">轮换风险</span>
                <span class="detail-value" :class="scenarioData.motivation_assessment.rotation_risk">
                  {{ getRiskLabel(scenarioData.motivation_assessment.rotation_risk) }}
                </span>
              </div>
              <div class="detail-row" v-if="scenarioData.motivation_assessment.key_factor">
                <span class="detail-label">关键因素</span>
                <span class="detail-value">{{ scenarioData.motivation_assessment.key_factor }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Clinch Analysis -->
        <div class="card section-card" v-if="scenarioData.clinch_analysis">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            提前判定
          </h3>
          <div class="clinch-grid">
            <div class="clinch-item" :class="scenarioData.clinch_analysis.can_clinch_title ? 'yes' : 'no'">
              <span class="clinch-label">可提前夺冠</span>
              <span class="clinch-value">{{ scenarioData.clinch_analysis.can_clinch_title ? '是' : '否' }}</span>
            </div>
            <div class="clinch-item" :class="scenarioData.clinch_analysis.can_be_relegated ? 'danger' : 'safe'">
              <span class="clinch-label">可能降级</span>
              <span class="clinch-value">{{ scenarioData.clinch_analysis.can_be_relegated ? '是' : '否' }}</span>
            </div>
            <div class="clinch-item" :class="scenarioData.clinch_analysis.can_clinch_europe ? 'yes' : 'no'">
              <span class="clinch-label">可锁定欧战</span>
              <span class="clinch-value">{{ scenarioData.clinch_analysis.can_clinch_europe ? '是' : '否' }}</span>
            </div>
          </div>
        </div>
      </template>

      <div v-if="scenarioError" class="error-state card">
        <p>{{ scenarioError }}</p>
      </div>
    </div>

    <!-- Tab: 轮换风险 -->
    <div v-if="activeTab === 'rotation'" class="tab-content">
      <div class="input-row card">
        <div class="input-group">
          <label>球队 ID</label>
          <input v-model="rotationInput.teamId" type="number" placeholder="如 42" />
        </div>
        <div class="input-group">
          <label>联赛 ID</label>
          <input v-model="rotationInput.leagueId" type="number" placeholder="如 39" />
        </div>
        <div class="input-group">
          <label>赛季 ID</label>
          <input v-model="rotationInput.seasonId" type="number" placeholder="如 2024" />
        </div>
        <button class="query-btn" @click="loadRotation" :disabled="rotationLoading">
          {{ rotationLoading ? '分析中...' : '分析' }}
        </button>
      </div>

      <div v-if="rotationLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在分析轮换风险...</p>
      </div>

      <template v-if="rotationData && !rotationLoading">
        <!-- Motivation -->
        <div class="card section-card" v-if="rotationData.motivation">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
            战意状态
          </h3>
          <div class="rotation-motivation" :class="rotationData.motivation.level">
            <span class="level-badge" :class="rotationData.motivation.level">
              {{ getMotivationLabel(rotationData.motivation.level) }}
            </span>
            <p class="motivation-desc" v-if="rotationData.motivation.description">
              {{ rotationData.motivation.description }}
            </p>
          </div>
        </div>

        <!-- Upcoming Matches -->
        <div class="card section-card" v-if="rotationData.upcoming_matches && rotationData.upcoming_matches.length">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            近期赛程
          </h3>
          <div class="upcoming-list">
            <div class="upcoming-item" v-for="(m, i) in rotationData.upcoming_matches" :key="i">
              <span class="upcoming-date">{{ m.match_date || m.date || '--' }}</span>
              <span class="upcoming-opponent">{{ m.opponent || m.opponent_name || '--' }}</span>
              <span class="upcoming-league" v-if="m.league || m.competition">{{ m.league || m.competition }}</span>
              <span class="upcoming-home" :class="m.is_home ? 'home' : 'away'">{{ m.is_home ? '主' : '客' }}</span>
            </div>
          </div>
        </div>

        <!-- Rotation Analysis -->
        <div class="card section-card" v-if="rotationData.rotation_analysis">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            轮换分析
          </h3>
          <div class="rotation-analysis">
            <div class="rotation-prob-row">
              <span class="rotation-label">轮换概率</span>
              <div class="rotation-prob-bar">
                <div class="rotation-prob-fill" :style="{ width: (rotationData.rotation_analysis.rotation_probability || 0) + '%' }"></div>
              </div>
              <span class="rotation-prob-value">{{ (rotationData.rotation_analysis.rotation_probability || 0) }}%</span>
            </div>
            <div class="rotation-detail" v-if="rotationData.rotation_analysis.reason">
              <span class="detail-label">原因</span>
              <span class="detail-value">{{ rotationData.rotation_analysis.reason }}</span>
            </div>
            <div class="rotation-detail" v-if="rotationData.rotation_analysis.save_for_next">
              <span class="detail-label">为下场留力</span>
              <span class="detail-value">{{ rotationData.rotation_analysis.save_for_next }}</span>
            </div>
            <div class="rotation-detail" v-if="rotationData.rotation_analysis.schedule_congestion">
              <span class="detail-label">赛程密集度</span>
              <span class="detail-value" :class="rotationData.rotation_analysis.schedule_congestion">
                {{ getCongestionLabel(rotationData.rotation_analysis.schedule_congestion) }}
              </span>
            </div>
          </div>
        </div>
      </template>

      <div v-if="rotationError" class="error-state card">
        <p>{{ rotationError }}</p>
      </div>
    </div>

    <!-- Tab: 6分战 -->
    <div v-if="activeTab === 'sixpointer'" class="tab-content">
      <div class="input-row card">
        <div class="input-group">
          <label>主队 ID</label>
          <input v-model="sixPointerInput.homeId" type="number" placeholder="如 42" />
        </div>
        <div class="input-group">
          <label>客队 ID</label>
          <input v-model="sixPointerInput.awayId" type="number" placeholder="如 33" />
        </div>
        <div class="input-group">
          <label>联赛 ID</label>
          <input v-model="sixPointerInput.leagueId" type="number" placeholder="如 39" />
        </div>
        <div class="input-group">
          <label>赛季 ID</label>
          <input v-model="sixPointerInput.seasonId" type="number" placeholder="如 2024" />
        </div>
        <button class="query-btn" @click="loadSixPointer" :disabled="sixPointerLoading">
          {{ sixPointerLoading ? '分析中...' : '分析' }}
        </button>
      </div>

      <div v-if="sixPointerLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在分析6分战...</p>
      </div>

      <template v-if="sixPointerData && !sixPointerLoading">
        <!-- Competition Type -->
        <div class="card section-card">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            比赛性质
          </h3>
          <div class="six-pointer-nature">
            <div class="nature-row">
              <span class="nature-label">竞争类型</span>
              <span class="nature-value">{{ sixPointerData.competition_type || '--' }}</span>
            </div>
            <div class="nature-row">
              <span class="nature-label">是否6分战</span>
              <span class="nature-value" :class="sixPointerData.is_six_pointer ? 'accent' : ''">
                {{ sixPointerData.is_six_pointer ? '是' : '否' }}
              </span>
            </div>
            <div class="nature-row" v-if="sixPointerData.points_gap !== undefined">
              <span class="nature-label">积分差距</span>
              <span class="nature-value">{{ sixPointerData.points_gap }} 分</span>
            </div>
          </div>
        </div>

        <!-- Simulations -->
        <div class="card section-card" v-if="sixPointerData.simulations">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            结果模拟
          </h3>
          <div class="simulation-grid">
            <div class="sim-card home-win" v-if="sixPointerData.simulations.home_win">
              <div class="sim-title">主胜</div>
              <div class="sim-impact" v-if="sixPointerData.simulations.home_win.impact">
                积分变化: {{ sixPointerData.simulations.home_win.impact }}
              </div>
              <div class="sim-desc" v-if="sixPointerData.simulations.home_win.description">
                {{ sixPointerData.simulations.home_win.description }}
              </div>
            </div>
            <div class="sim-card draw-result" v-if="sixPointerData.simulations.draw">
              <div class="sim-title">平局</div>
              <div class="sim-impact" v-if="sixPointerData.simulations.draw.impact">
                积分变化: {{ sixPointerData.simulations.draw.impact }}
              </div>
              <div class="sim-desc" v-if="sixPointerData.simulations.draw.description">
                {{ sixPointerData.simulations.draw.description }}
              </div>
            </div>
            <div class="sim-card away-win" v-if="sixPointerData.simulations.away_win">
              <div class="sim-title">客胜</div>
              <div class="sim-impact" v-if="sixPointerData.simulations.away_win.impact">
                积分变化: {{ sixPointerData.simulations.away_win.impact }}
              </div>
              <div class="sim-desc" v-if="sixPointerData.simulations.away_win.description">
                {{ sixPointerData.simulations.away_win.description }}
              </div>
            </div>
          </div>
        </div>

        <!-- Match Significance -->
        <div class="card section-card" v-if="sixPointerData.match_significance">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
            </svg>
            比赛意义
          </h3>
          <div class="significance-content">
            <p>{{ sixPointerData.match_significance }}</p>
          </div>
        </div>
      </template>

      <div v-if="sixPointerError" class="error-state card">
        <p>{{ sixPointerError }}</p>
      </div>
    </div>

    <!-- Tab: 争冠形势 -->
    <div v-if="activeTab === 'titlerace'" class="tab-content">
      <div class="input-row card">
        <div class="input-group">
          <label>联赛 ID</label>
          <input v-model="titleRaceInput.leagueId" type="number" placeholder="如 39" />
        </div>
        <div class="input-group">
          <label>赛季 ID</label>
          <input v-model="titleRaceInput.seasonId" type="number" placeholder="如 2024" />
        </div>
        <button class="query-btn" @click="loadTitleRace" :disabled="titleRaceLoading">
          {{ titleRaceLoading ? '分析中...' : '分析' }}
        </button>
      </div>

      <div v-if="titleRaceLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在分析争冠形势...</p>
      </div>

      <template v-if="titleRaceData && !titleRaceLoading">
        <!-- Leader -->
        <div class="card section-card" v-if="titleRaceData.leader">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="8" r="7" /><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88" />
            </svg>
            领头羊
          </h3>
          <div class="leader-info">
            <div class="leader-name">{{ titleRaceData.leader.team_name || '--' }}</div>
            <div class="leader-stats">
              <span class="leader-stat">积分: <strong>{{ titleRaceData.leader.points || 0 }}</strong></span>
              <span class="leader-stat">已赛: {{ titleRaceData.leader.played || 0 }}</span>
              <span class="leader-stat">净胜球: {{ titleRaceData.leader.goal_diff || 0 }}</span>
            </div>
          </div>
        </div>

        <!-- Title Race Teams -->
        <div class="card section-card" v-if="titleRaceData.title_race_teams && titleRaceData.title_race_teams.length">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            争冠集团
          </h3>
          <div class="race-teams-list">
            <div class="race-team-item" v-for="(team, i) in titleRaceData.title_race_teams" :key="i">
              <div class="race-team-rank">{{ i + 1 }}</div>
              <div class="race-team-info">
                <div class="race-team-name">{{ team.team_name || '--' }}</div>
                <div class="race-team-stats">
                  <span>积分 {{ team.points || 0 }}</span>
                  <span>落后 <span class="gap-value">{{ team.gap_to_leader || 0 }}</span> 分</span>
                  <span>剩余 {{ team.remaining || 0 }} 轮</span>
                  <span>理论最高 {{ team.max_possible || 0 }}</span>
                </div>
                <div class="race-team-chances">
                  <span class="chance-label" :class="team.can_catch_leader ? 'yes' : 'no'">
                    {{ team.can_catch_leader ? '可追上' : '无法追上' }}
                  </span>
                  <span class="probability" v-if="team.title_probability !== undefined">
                    夺冠概率: {{ (team.title_probability * 100).toFixed(1) }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Race Status -->
        <div class="card section-card">
          <div class="race-status-grid">
            <div class="race-status-item" v-if="titleRaceData.is_clinched !== undefined">
              <span class="rs-label">已锁定冠军</span>
              <span class="rs-value" :class="titleRaceData.is_clinched ? 'accent' : ''">
                {{ titleRaceData.is_clinched ? '是' : '否' }}
              </span>
            </div>
            <div class="race-status-item" v-if="titleRaceData.race_intensity">
              <span class="rs-label">争冠激烈度</span>
              <span class="rs-value" :class="titleRaceData.race_intensity">
                {{ getIntensityLabel(titleRaceData.race_intensity) }}
              </span>
            </div>
          </div>
        </div>
      </template>

      <div v-if="titleRaceError" class="error-state card">
        <p>{{ titleRaceError }}</p>
      </div>
    </div>

    <!-- Tab: 保级形势 -->
    <div v-if="activeTab === 'relegation'" class="tab-content">
      <div class="input-row card">
        <div class="input-group">
          <label>联赛 ID</label>
          <input v-model="relegationInput.leagueId" type="number" placeholder="如 39" />
        </div>
        <div class="input-group">
          <label>赛季 ID</label>
          <input v-model="relegationInput.seasonId" type="number" placeholder="如 2024" />
        </div>
        <button class="query-btn" @click="loadRelegation" :disabled="relegationLoading">
          {{ relegationLoading ? '分析中...' : '分析' }}
        </button>
      </div>

      <div v-if="relegationLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在分析保级形势...</p>
      </div>

      <template v-if="relegationData && !relegationLoading">
        <!-- Safety Line -->
        <div class="card section-card" v-if="relegationData.safety_line">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            安全线
          </h3>
          <div class="safety-line-info">
            <span class="safety-points">{{ relegationData.safety_line.points || relegationData.safety_line }} 分</span>
            <span class="safety-desc" v-if="relegationData.safety_line.description">
              {{ relegationData.safety_line.description }}
            </span>
          </div>
        </div>

        <!-- Relegation Teams -->
        <div class="card section-card" v-if="relegationData.relegation_teams && relegationData.relegation_teams.length">
          <h3 class="section-title">
            <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
              <polyline points="17 6 23 6 23 12" />
            </svg>
            保级球队
          </h3>
          <div class="relegation-teams-list">
            <div class="relegation-team-item" v-for="(team, i) in relegationData.relegation_teams" :key="i"
              :class="{ 'in-zone': team.in_relegation_zone }">
              <div class="rel-team-rank" :class="team.in_relegation_zone ? 'danger' : 'warning'">
                {{ team.position || i + 1 }}
              </div>
              <div class="rel-team-info">
                <div class="rel-team-name">{{ team.team_name || '--' }}</div>
                <div class="rel-team-stats">
                  <span>积分 {{ team.points || 0 }}</span>
                  <span>距安全线 <span class="gap-value" :class="team.gap_to_safety > 0 ? 'negative' : 'positive'">
                    {{ team.gap_to_safety > 0 ? '+' : '' }}{{ team.gap_to_safety || 0 }}
                  </span> 分</span>
                </div>
                <div class="rel-team-chances">
                  <span class="chance-label" :class="team.can_escape ? 'yes' : 'no'">
                    {{ team.can_escape ? '可保级' : '形势严峻' }}
                  </span>
                  <span class="escape-condition" v-if="team.escape_condition">
                    条件: {{ team.escape_condition }}
                  </span>
                  <span class="probability" v-if="team.survival_probability !== undefined">
                    保级概率: {{ (team.survival_probability * 100).toFixed(1) }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Battle Intensity -->
        <div class="card section-card" v-if="relegationData.battle_intensity">
          <div class="battle-intensity">
            <span class="bi-label">保级激烈度</span>
            <span class="bi-value" :class="relegationData.battle_intensity">
              {{ getIntensityLabel(relegationData.battle_intensity) }}
            </span>
          </div>
        </div>
      </template>

      <div v-if="relegationError" class="error-state card">
        <p>{{ relegationError }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'SeasonScenario',
  setup() {
    const activeTab = ref('scenario')

    const tabs = [
      { key: 'scenario', label: '赛季形势' },
      { key: 'rotation', label: '轮换风险' },
      { key: 'sixpointer', label: '6分战' },
      { key: 'titlerace', label: '争冠形势' },
      { key: 'relegation', label: '保级形势' }
    ]

    // --- Scenario ---
    const scenarioInput = ref({ teamId: '', leagueId: '', seasonId: '' })
    const scenarioData = ref(null)
    const scenarioLoading = ref(false)
    const scenarioError = ref('')

    const loadScenario = async () => {
      const { teamId, leagueId, seasonId } = scenarioInput.value
      if (!teamId || !leagueId || !seasonId) {
        scenarioError.value = '请填写球队ID、联赛ID和赛季ID'
        return
      }
      scenarioLoading.value = true
      scenarioError.value = ''
      scenarioData.value = null
      try {
        const res = await analysisAPI.getTeamSeasonScenario(teamId, leagueId, seasonId)
        scenarioData.value = res.data || res
      } catch (e) {
        scenarioError.value = '获取赛季形势数据失败: ' + (e.message || e)
      } finally {
        scenarioLoading.value = false
      }
    }

    // --- Rotation ---
    const rotationInput = ref({ teamId: '', leagueId: '', seasonId: '' })
    const rotationData = ref(null)
    const rotationLoading = ref(false)
    const rotationError = ref('')

    const loadRotation = async () => {
      const { teamId, leagueId, seasonId } = rotationInput.value
      if (!teamId || !leagueId || !seasonId) {
        rotationError.value = '请填写球队ID、联赛ID和赛季ID'
        return
      }
      rotationLoading.value = true
      rotationError.value = ''
      rotationData.value = null
      try {
        const res = await analysisAPI.getRotationRisk(teamId, leagueId, seasonId)
        rotationData.value = res.data || res
      } catch (e) {
        rotationError.value = '获取轮换风险数据失败: ' + (e.message || e)
      } finally {
        rotationLoading.value = false
      }
    }

    // --- Six Pointer ---
    const sixPointerInput = ref({ homeId: '', awayId: '', leagueId: '', seasonId: '' })
    const sixPointerData = ref(null)
    const sixPointerLoading = ref(false)
    const sixPointerError = ref('')

    const loadSixPointer = async () => {
      const { homeId, awayId, leagueId, seasonId } = sixPointerInput.value
      if (!homeId || !awayId || !leagueId || !seasonId) {
        sixPointerError.value = '请填写主队ID、客队ID、联赛ID和赛季ID'
        return
      }
      sixPointerLoading.value = true
      sixPointerError.value = ''
      sixPointerData.value = null
      try {
        const res = await analysisAPI.getSixPointerAnalysis(homeId, awayId, leagueId, seasonId)
        sixPointerData.value = res.data || res
      } catch (e) {
        sixPointerError.value = '获取6分战数据失败: ' + (e.message || e)
      } finally {
        sixPointerLoading.value = false
      }
    }

    // --- Title Race ---
    const titleRaceInput = ref({ leagueId: '', seasonId: '' })
    const titleRaceData = ref(null)
    const titleRaceLoading = ref(false)
    const titleRaceError = ref('')

    const loadTitleRace = async () => {
      const { leagueId, seasonId } = titleRaceInput.value
      if (!leagueId || !seasonId) {
        titleRaceError.value = '请填写联赛ID和赛季ID'
        return
      }
      titleRaceLoading.value = true
      titleRaceError.value = ''
      titleRaceData.value = null
      try {
        const res = await analysisAPI.getTitleRace(leagueId, seasonId)
        titleRaceData.value = res.data || res
      } catch (e) {
        titleRaceError.value = '获取争冠形势数据失败: ' + (e.message || e)
      } finally {
        titleRaceLoading.value = false
      }
    }

    // --- Relegation ---
    const relegationInput = ref({ leagueId: '', seasonId: '' })
    const relegationData = ref(null)
    const relegationLoading = ref(false)
    const relegationError = ref('')

    const loadRelegation = async () => {
      const { leagueId, seasonId } = relegationInput.value
      if (!leagueId || !seasonId) {
        relegationError.value = '请填写联赛ID和赛季ID'
        return
      }
      relegationLoading.value = true
      relegationError.value = ''
      relegationData.value = null
      try {
        const res = await analysisAPI.getRelegationBattle(leagueId, seasonId)
        relegationData.value = res.data || res
      } catch (e) {
        relegationError.value = '获取保级形势数据失败: ' + (e.message || e)
      } finally {
        relegationLoading.value = false
      }
    }

    // --- Helpers ---
    const getZoneLabel = (key) => {
      const map = {
        champion_league: '欧冠区',
        europa_league: '欧联区',
        relegation: '降级区',
        mid_table: '中游区'
      }
      return map[key] || key
    }

    const getZoneStatusLabel = (status) => {
      const map = {
        in: '已进入',
        above: '高于',
        below: '低于',
        safe: '安全',
        danger: '危险',
        out: '已出局'
      }
      return map[status] || status || '--'
    }

    const getMotivationLabel = (level) => {
      const map = {
        desperate: '必须拿分',
        high: '战意强烈',
        normal: '正常',
        low: '无欲无求',
        very_high: '战意极强',
        medium: '中等'
      }
      return map[level] || level || '--'
    }

    const getRiskLabel = (risk) => {
      const map = {
        high: '高风险',
        medium: '中等风险',
        low: '低风险',
        very_high: '极高风险',
        very_low: '极低风险'
      }
      return map[risk] || risk || '--'
    }

    const getCongestionLabel = (level) => {
      const map = {
        very_high: '极高',
        high: '高',
        medium: '中等',
        low: '低'
      }
      return map[level] || level || '--'
    }

    const getIntensityLabel = (intensity) => {
      const map = {
        very_high: '极高',
        high: '高',
        medium: '中等',
        low: '低',
        intense: '激烈',
        moderate: '一般',
        mild: '平淡'
      }
      return map[intensity] || intensity || '--'
    }

    return {
      activeTab,
      tabs,
      // Scenario
      scenarioInput, scenarioData, scenarioLoading, scenarioError, loadScenario,
      // Rotation
      rotationInput, rotationData, rotationLoading, rotationError, loadRotation,
      // Six Pointer
      sixPointerInput, sixPointerData, sixPointerLoading, sixPointerError, loadSixPointer,
      // Title Race
      titleRaceInput, titleRaceData, titleRaceLoading, titleRaceError, loadTitleRace,
      // Relegation
      relegationInput, relegationData, relegationLoading, relegationError, loadRelegation,
      // Helpers
      getZoneLabel, getZoneStatusLabel, getMotivationLabel, getRiskLabel,
      getCongestionLabel, getIntensityLabel
    }
  }
}
</script>

<style scoped>
.season-scenario {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
}

.card {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

/* Header */
.header {
  padding: 16px 20px;
}

.header-content h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.header-content h2 .icon {
  width: 18px;
  height: 18px;
  color: #10b981;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 4px;
  padding: 6px;
  overflow-x: auto;
}

.tab-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #9ca3af;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.tab-btn:hover {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.tab-btn.active {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  font-weight: 600;
}

/* Input Row */
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 16px 20px;
  flex-wrap: wrap;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 120px;
}

.input-group label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.input-group input {
  padding: 8px 12px;
  background: #0a0d14;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 6px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.input-group input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.input-group input::placeholder {
  color: #4b5563;
}

.query-btn {
  padding: 8px 20px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 6px;
  color: #10b981;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.query-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
}

.query-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #6b7280;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(16, 185, 129, 0.2);
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Error */
.error-state {
  padding: 16px 20px;
  color: #ef4444;
  font-size: 13px;
  background: rgba(239, 68, 68, 0.05);
  border-color: rgba(239, 68, 68, 0.2);
}

/* Section Card */
.section-card {
  padding: 16px 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.section-icon {
  width: 16px;
  height: 16px;
  color: #10b981;
  flex-shrink: 0;
}

/* Status Grid */
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 10px;
}

.status-item {
  background: #0a0d14;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.status-item.highlight {
  grid-column: span 2;
}

.status-item.win {
  border-left: 3px solid #10b981;
}

.status-item.draw {
  border-left: 3px solid #f59e0b;
}

.status-item.loss {
  border-left: 3px solid #ef4444;
}

.status-label {
  font-size: 11px;
  color: #6b7280;
}

.status-value {
  font-size: 16px;
  font-weight: 700;
  color: #e5e7eb;
}

.status-value.name {
  font-size: 15px;
}

.status-value.accent {
  color: #10b981;
}

.status-value.positive {
  color: #10b981;
}

.status-value.negative {
  color: #ef4444;
}

/* Progress */
.progress-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-stats {
  display: flex;
  gap: 20px;
}

.progress-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.progress-label {
  font-size: 11px;
  color: #6b7280;
}

.progress-value {
  font-size: 18px;
  font-weight: 700;
  color: #e5e7eb;
}

.progress-bar-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: #0a0d14;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #10b981, #059669);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-pct {
  font-size: 13px;
  font-weight: 600;
  color: #10b981;
  min-width: 48px;
  text-align: right;
}

/* Projection Grid */
.projection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
}

.projection-item {
  background: #0a0d14;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.projection-item.current {
  border-left: 3px solid #10b981;
}

.projection-item.max {
  border-left: 3px solid #3b82f6;
}

.projection-item.min {
  border-left: 3px solid #ef4444;
}

.projection-item.realistic {
  border-left: 3px solid #8b5cf6;
}

.projection-item.avg {
  border-left: 3px solid #f59e0b;
}

.proj-label {
  font-size: 11px;
  color: #6b7280;
}

.proj-value {
  font-size: 20px;
  font-weight: 700;
  color: #e5e7eb;
}

/* Zone Grid */
.zone-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}

.zone-item {
  background: #0a0d14;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.zone-item.in,
.zone-item.safe {
  border-left: 3px solid #10b981;
}

.zone-item.above {
  border-left: 3px solid #3b82f6;
}

.zone-item.below,
.zone-item.danger {
  border-left: 3px solid #ef4444;
}

.zone-item.out {
  border-left: 3px solid #6b7280;
}

.zone-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.zone-name {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
}

.zone-status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.zone-status-badge.in,
.zone-status-badge.safe {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.zone-status-badge.above {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.zone-status-badge.below,
.zone-status-badge.danger {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.zone-status-badge.out {
  background: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
}

.zone-gap {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 4px;
}

.zone-gap .positive {
  color: #10b981;
}

.zone-gap .negative {
  color: #ef4444;
}

.zone-desc {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
}

/* Motivation Block */
.motivation-block {
  background: #0a0d14;
  border-radius: 8px;
  padding: 14px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.motivation-block.desperate,
.motivation-block.very_high {
  border-left: 3px solid #ef4444;
}

.motivation-block.high {
  border-left: 3px solid #10b981;
}

.motivation-block.normal,
.motivation-block.medium {
  border-left: 3px solid #3b82f6;
}

.motivation-block.low {
  border-left: 3px solid #6b7280;
}

.motivation-level {
  margin-bottom: 8px;
}

.level-badge {
  font-size: 13px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 6px;
}

.level-badge.desperate,
.level-badge.very_high {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.level-badge.high {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.level-badge.normal,
.level-badge.medium {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.level-badge.low {
  background: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
}

.motivation-desc {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.5;
  margin-bottom: 10px;
}

.motivation-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.detail-label {
  color: #6b7280;
}

.detail-value {
  color: #e5e7eb;
  font-weight: 500;
}

.detail-value.high {
  color: #ef4444;
}

.detail-value.medium {
  color: #f59e0b;
}

.detail-value.low {
  color: #10b981;
}

.detail-value.very_high {
  color: #ef4444;
}

/* Clinch Grid */
.clinch-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.clinch-item {
  background: #0a0d14;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: center;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.clinch-item.yes {
  border-color: rgba(16, 185, 129, 0.3);
}

.clinch-item.no {
  border-color: rgba(107, 114, 128, 0.2);
}

.clinch-item.danger {
  border-color: rgba(239, 68, 68, 0.3);
}

.clinch-item.safe {
  border-color: rgba(16, 185, 129, 0.3);
}

.clinch-label {
  font-size: 11px;
  color: #6b7280;
}

.clinch-value {
  font-size: 16px;
  font-weight: 700;
}

.clinch-item.yes .clinch-value {
  color: #10b981;
}

.clinch-item.no .clinch-value {
  color: #9ca3af;
}

.clinch-item.danger .clinch-value {
  color: #ef4444;
}

.clinch-item.safe .clinch-value {
  color: #10b981;
}

/* Rotation Tab */
.rotation-motivation {
  background: #0a0d14;
  border-radius: 8px;
  padding: 14px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.rotation-motivation.desperate,
.rotation-motivation.very_high {
  border-left: 3px solid #ef4444;
}

.rotation-motivation.high {
  border-left: 3px solid #10b981;
}

.rotation-motivation.normal,
.rotation-motivation.medium {
  border-left: 3px solid #3b82f6;
}

.rotation-motivation.low {
  border-left: 3px solid #6b7280;
}

/* Upcoming List */
.upcoming-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.upcoming-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.upcoming-date {
  color: #6b7280;
  min-width: 80px;
}

.upcoming-opponent {
  flex: 1;
  color: #e5e7eb;
  font-weight: 500;
}

.upcoming-league {
  color: #6b7280;
  font-size: 11px;
}

.upcoming-home {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.upcoming-home.home {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.upcoming-home.away {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

/* Rotation Analysis */
.rotation-analysis {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rotation-prob-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rotation-label {
  font-size: 12px;
  color: #6b7280;
  min-width: 60px;
}

.rotation-prob-bar {
  flex: 1;
  height: 8px;
  background: #0a0d14;
  border-radius: 4px;
  overflow: hidden;
}

.rotation-prob-fill {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #ef4444);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.rotation-prob-value {
  font-size: 13px;
  font-weight: 600;
  color: #f59e0b;
  min-width: 40px;
  text-align: right;
}

.rotation-detail {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  padding: 6px 0;
  border-top: 1px solid rgba(31, 41, 55, 0.3);
}

.rotation-detail .detail-label {
  color: #6b7280;
}

.rotation-detail .detail-value {
  color: #e5e7eb;
  font-weight: 500;
}

.rotation-detail .detail-value.high,
.rotation-detail .detail-value.very_high {
  color: #ef4444;
}

.rotation-detail .detail-value.medium {
  color: #f59e0b;
}

.rotation-detail .detail-value.low {
  color: #10b981;
}

/* Six Pointer */
.six-pointer-nature {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nature-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.nature-label {
  font-size: 12px;
  color: #6b7280;
}

.nature-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.nature-value.accent {
  color: #10b981;
}

/* Simulation Grid */
.simulation-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.sim-card {
  background: #0a0d14;
  border-radius: 8px;
  padding: 14px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.sim-card.home-win {
  border-top: 3px solid #10b981;
}

.sim-card.draw-result {
  border-top: 3px solid #f59e0b;
}

.sim-card.away-win {
  border-top: 3px solid #3b82f6;
}

.sim-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 8px;
}

.sim-impact {
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 6px;
}

.sim-desc {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
}

/* Significance */
.significance-content {
  padding: 12px;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.significance-content p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
}

/* Title Race */
.leader-info {
  background: #0a0d14;
  border-radius: 8px;
  padding: 14px;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.leader-name {
  font-size: 16px;
  font-weight: 700;
  color: #10b981;
  margin-bottom: 8px;
}

.leader-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #9ca3af;
}

.leader-stat strong {
  color: #e5e7eb;
}

/* Race Teams List */
.race-teams-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.race-team-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.race-team-rank {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.race-team-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.race-team-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.race-team-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #9ca3af;
}

.gap-value {
  color: #f59e0b;
  font-weight: 600;
}

.race-team-chances {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 12px;
}

.chance-label {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.chance-label.yes {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.chance-label.no {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.probability {
  color: #9ca3af;
}

/* Race Status */
.race-status-grid {
  display: flex;
  gap: 20px;
}

.race-status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rs-label {
  font-size: 12px;
  color: #6b7280;
}

.rs-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.rs-value.accent {
  color: #10b981;
}

.rs-value.high,
.rs-value.very_high,
.rs-value.intense {
  color: #ef4444;
}

.rs-value.medium,
.rs-value.moderate {
  color: #f59e0b;
}

.rs-value.low,
.rs-value.mild {
  color: #10b981;
}

/* Relegation */
.safety-line-info {
  background: #0a0d14;
  border-radius: 8px;
  padding: 14px;
  border: 1px solid rgba(16, 185, 129, 0.2);
  display: flex;
  align-items: center;
  gap: 12px;
}

.safety-points {
  font-size: 24px;
  font-weight: 700;
  color: #10b981;
}

.safety-desc {
  font-size: 13px;
  color: #9ca3af;
}

/* Relegation Teams List */
.relegation-teams-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.relegation-team-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.relegation-team-item.in-zone {
  border-color: rgba(239, 68, 68, 0.3);
}

.rel-team-rank {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.rel-team-rank.danger {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.rel-team-rank.warning {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.rel-team-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rel-team-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.rel-team-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #9ca3af;
}

.rel-team-stats .gap-value.positive {
  color: #10b981;
}

.rel-team-stats .gap-value.negative {
  color: #ef4444;
}

.rel-team-chances {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  flex-wrap: wrap;
}

.escape-condition {
  color: #9ca3af;
}

/* Battle Intensity */
.battle-intensity {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bi-label {
  font-size: 12px;
  color: #6b7280;
}

.bi-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.bi-value.high,
.bi-value.very_high,
.bi-value.intense {
  color: #ef4444;
}

.bi-value.medium,
.bi-value.moderate {
  color: #f59e0b;
}

.bi-value.low,
.bi-value.mild {
  color: #10b981;
}

/* Responsive */
@media (max-width: 600px) {
  .input-row {
    flex-direction: column;
    align-items: stretch;
  }

  .input-group {
    min-width: unset;
  }

  .status-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .projection-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .zone-grid {
    grid-template-columns: 1fr;
  }

  .clinch-grid {
    grid-template-columns: 1fr;
  }

  .simulation-grid {
    grid-template-columns: 1fr;
  }

  .leader-stats {
    flex-wrap: wrap;
  }

  .race-team-stats {
    flex-wrap: wrap;
  }
}
</style>
