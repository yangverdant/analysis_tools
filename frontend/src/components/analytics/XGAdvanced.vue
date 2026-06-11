<template>
  <div class="xg-advanced">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>高级xG分析</h2>
        <p>预期进球深度分析与趋势对比</p>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab 1: 比赛xG -->
    <div v-if="activeTab === 'match'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="matchMatchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadMatchXG"
        />
        <button class="action-btn" @click="loadMatchXG" :disabled="matchLoading">查询</button>
      </div>
      <div class="loading-state" v-if="matchLoading">
        <div class="spinner"></div>
        <p>正在加载比赛xG数据...</p>
      </div>
      <template v-else-if="matchData">
        <div class="xg-comparison card">
          <div class="xg-team home">
            <div class="xg-team-label">主队</div>
            <div class="xg-team-name">{{ matchData.home_team || matchData.home_team_name || '--' }}</div>
            <div class="xg-value">{{ matchData.home_xg != null ? Number(matchData.home_xg).toFixed(2) : '--' }}</div>
            <div class="xg-goals">实际进球: {{ matchData.home_goals != null ? matchData.home_goals : '--' }}</div>
          </div>
          <div class="xg-vs">
            <div class="xg-vs-label">xG</div>
            <div class="xg-vs-text">VS</div>
          </div>
          <div class="xg-team away">
            <div class="xg-team-label">客队</div>
            <div class="xg-team-name">{{ matchData.away_team || matchData.away_team_name || '--' }}</div>
            <div class="xg-value">{{ matchData.away_xg != null ? Number(matchData.away_xg).toFixed(2) : '--' }}</div>
            <div class="xg-goals">实际进球: {{ matchData.away_goals != null ? matchData.away_goals : '--' }}</div>
          </div>
        </div>
        <div v-if="matchData.xg_details || matchData.shots" class="detail-card card">
          <h3>xG详情</h3>
          <div class="xg-details">
            <div v-if="matchData.home_xg_open_play != null" class="detail-row">
              <span class="detail-label">主队运动战xG</span>
              <span class="detail-value">{{ Number(matchData.home_xg_open_play).toFixed(2) }}</span>
            </div>
            <div v-if="matchData.home_xg_set_piece != null" class="detail-row">
              <span class="detail-label">主队定位球xG</span>
              <span class="detail-value">{{ Number(matchData.home_xg_set_piece).toFixed(2) }}</span>
            </div>
            <div v-if="matchData.away_xg_open_play != null" class="detail-row">
              <span class="detail-label">客队运动战xG</span>
              <span class="detail-value">{{ Number(matchData.away_xg_open_play).toFixed(2) }}</span>
            </div>
            <div v-if="matchData.away_xg_set_piece != null" class="detail-row">
              <span class="detail-label">客队定位球xG</span>
              <span class="detail-value">{{ Number(matchData.away_xg_set_piece).toFixed(2) }}</span>
            </div>
          </div>
        </div>
        <div v-if="matchData.analysis" class="detail-card card">
          <h3>xG分析</h3>
          <div class="detail-block">
            <p>{{ typeof matchData.analysis === 'string' ? matchData.analysis : JSON.stringify(matchData.analysis) }}</p>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入比赛ID查询xG数据</p>
      </div>
    </div>

    <!-- Tab 2: 球队xG趋势 -->
    <div v-if="activeTab === 'trend'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="trendTeamId"
          placeholder="输入球队ID"
          class="text-input"
          @keyup.enter="loadTeamXGTrend"
        />
        <input
          v-model="trendLimit"
          placeholder="场次 (默认20)"
          class="text-input short"
          type="number"
          @keyup.enter="loadTeamXGTrend"
        />
        <button class="action-btn" @click="loadTeamXGTrend" :disabled="trendLoading">查询</button>
      </div>
      <div class="loading-state" v-if="trendLoading">
        <div class="spinner"></div>
        <p>正在加载xG趋势...</p>
      </div>
      <template v-else-if="trendData">
        <div class="stats-grid">
          <div class="stat-card card">
            <div class="stat-label">总xG</div>
            <div class="stat-value accent">{{ trendData.total_xg != null ? Number(trendData.total_xg).toFixed(2) : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">总xGA</div>
            <div class="stat-value">{{ trendData.total_xga != null ? Number(trendData.total_xga).toFixed(2) : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">xG差值</div>
            <div class="stat-value" :class="xgDiffClass(trendData.xg_diff)">{{ trendData.xg_diff != null ? Number(trendData.xg_diff).toFixed(2) : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">场均xG</div>
            <div class="stat-value accent">{{ trendData.avg_xg != null ? Number(trendData.avg_xg).toFixed(2) : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">场均xGA</div>
            <div class="stat-value">{{ trendData.avg_xga != null ? Number(trendData.avg_xga).toFixed(2) : '--' }}</div>
          </div>
        </div>
        <div v-if="trendData.recent_matches && trendData.recent_matches.length" class="detail-card card">
          <h3>近期xG走势</h3>
          <div class="xg-trend-list">
            <div v-for="(m, idx) in trendData.recent_matches" :key="idx" class="xg-trend-item">
              <span class="trend-date">{{ m.date || m.match_date || '--' }}</span>
              <span class="trend-opponent">{{ m.opponent || m.opponent_name || '--' }}</span>
              <span class="trend-xg">xG: {{ m.xg != null ? Number(m.xg).toFixed(2) : '--' }}</span>
              <span class="trend-xga">xGA: {{ m.xga != null ? Number(m.xga).toFixed(2) : '--' }}</span>
              <span v-if="m.goals != null" class="trend-goals">进球: {{ m.goals }}</span>
            </div>
          </div>
        </div>
        <div v-if="trendData.shot_types" class="detail-card card">
          <h3>射门类型分布</h3>
          <div class="shot-type-list">
            <div v-for="(val, key) in trendData.shot_types" :key="key" class="shot-type-item">
              <span class="shot-type-name">{{ key }}</span>
              <span class="shot-type-value">{{ typeof val === 'number' ? val.toFixed(2) : val }}</span>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入球队ID查询xG趋势</p>
      </div>
    </div>

    <!-- Tab 3: xG vs 实际进球 -->
    <div v-if="activeTab === 'vsactual'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="vsActualTeamId"
          placeholder="输入球队ID"
          class="text-input"
          @keyup.enter="loadXGVsActual"
        />
        <button class="action-btn" @click="loadXGVsActual" :disabled="vsActualLoading">查询</button>
      </div>
      <div class="loading-state" v-if="vsActualLoading">
        <div class="spinner"></div>
        <p>正在加载xG vs 实际进球数据...</p>
      </div>
      <template v-else-if="vsActualData">
        <div class="stats-grid">
          <div class="stat-card card">
            <div class="stat-label">总xG</div>
            <div class="stat-value accent">{{ vsActualData.total_xg != null ? Number(vsActualData.total_xg).toFixed(2) : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">实际进球</div>
            <div class="stat-value">{{ vsActualData.actual_goals != null ? vsActualData.actual_goals : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">xG差值</div>
            <div class="stat-value" :class="xgDiffClass(vsActualData.xg_diff)">
              {{ vsActualData.xg_diff != null ? Number(vsActualData.xg_diff).toFixed(2) : '--' }}
            </div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">转化率</div>
            <div class="stat-value" :class="conversionClass(vsActualData.conversion_rate)">
              {{ vsActualData.conversion_rate != null ? (vsActualData.conversion_rate * 100).toFixed(1) + '%' : '--' }}
            </div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">超额进球</div>
            <div class="stat-value" :class="xgDiffClass(vsActualData.overperformance || vsActualData.xg_diff)">
              {{ vsActualData.overperformance != null ? Number(vsActualData.overperformance).toFixed(2) : '--' }}
            </div>
          </div>
        </div>
        <div v-if="vsActualData.match_by_match && vsActualData.match_by_match.length" class="detail-card card">
          <h3>逐场对比</h3>
          <div class="match-comparison-list">
            <div v-for="(m, idx) in vsActualData.match_by_match" :key="idx" class="match-comp-item">
              <span class="comp-date">{{ m.date || m.match_date || '--' }}</span>
              <span class="comp-opponent">{{ m.opponent || m.opponent_name || '--' }}</span>
              <span class="comp-xg">xG: {{ m.xg != null ? Number(m.xg).toFixed(2) : '--' }}</span>
              <span class="comp-goals">进球: {{ m.goals != null ? m.goals : '--' }}</span>
              <span class="comp-diff" :class="xgDiffClass(m.goals != null && m.xg != null ? m.goals - m.xg : null)">
                {{ m.goals != null && m.xg != null ? (m.goals - m.xg).toFixed(2) : '--' }}
              </span>
            </div>
          </div>
        </div>
        <div v-if="vsActualData.analysis" class="detail-card card">
          <h3>分析</h3>
          <div class="detail-block">
            <p>{{ typeof vsActualData.analysis === 'string' ? vsActualData.analysis : JSON.stringify(vsActualData.analysis) }}</p>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入球队ID查询xG vs 实际进球</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'XGAdvanced',
  setup() {
    const activeTab = ref('match')
    const tabs = [
      { key: 'match', label: '比赛xG' },
      { key: 'trend', label: '球队xG趋势' },
      { key: 'vsactual', label: 'xG vs 实际进球' }
    ]

    // Tab 1: 比赛xG
    const matchMatchId = ref('')
    const matchLoading = ref(false)
    const matchData = ref(null)

    const loadMatchXG = async () => {
      if (!matchMatchId.value) return
      matchLoading.value = true
      matchData.value = null
      try {
        const res = await analysisAPI.getMatchXG(matchMatchId.value)
        matchData.value = res.data || res || null
      } catch (e) {
        console.error('加载比赛xG失败:', e)
        matchData.value = null
      } finally {
        matchLoading.value = false
      }
    }

    // Tab 2: 球队xG趋势
    const trendTeamId = ref('')
    const trendLimit = ref(20)
    const trendLoading = ref(false)
    const trendData = ref(null)

    const loadTeamXGTrend = async () => {
      if (!trendTeamId.value) return
      trendLoading.value = true
      trendData.value = null
      try {
        const limit = trendLimit.value || 20
        const res = await analysisAPI.getTeamStatsBombXG(trendTeamId.value, limit)
        trendData.value = res.data || res || null
      } catch (e) {
        console.error('加载球队xG趋势失败:', e)
        trendData.value = null
      } finally {
        trendLoading.value = false
      }
    }

    // Tab 3: xG vs 实际进球
    const vsActualTeamId = ref('')
    const vsActualLoading = ref(false)
    const vsActualData = ref(null)

    const loadXGVsActual = async () => {
      if (!vsActualTeamId.value) return
      vsActualLoading.value = true
      vsActualData.value = null
      try {
        const res = await analysisAPI.getTeamXGPerformance(vsActualTeamId.value)
        vsActualData.value = res.data || res || null
      } catch (e) {
        console.error('加载xG vs 实际进球失败:', e)
        vsActualData.value = null
      } finally {
        vsActualLoading.value = false
      }
    }

    const xgDiffClass = (diff) => {
      if (diff == null) return ''
      const num = typeof diff === 'number' ? diff : parseFloat(diff)
      if (isNaN(num)) return ''
      if (num > 0) return 'positive'
      if (num < 0) return 'negative'
      return ''
    }

    const conversionClass = (rate) => {
      if (rate == null) return ''
      if (rate >= 1.0) return 'positive'
      if (rate < 0.8) return 'negative'
      return ''
    }

    return {
      activeTab, tabs,
      matchMatchId, matchLoading, matchData, loadMatchXG,
      trendTeamId, trendLimit, trendLoading, trendData, loadTeamXGTrend,
      vsActualTeamId, vsActualLoading, vsActualData, loadXGVsActual,
      xgDiffClass, conversionClass
    }
  }
}
</script>

<style scoped>
.xg-advanced {
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

.header {
  padding: 16px 20px;
}

.header-content h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
  margin-bottom: 4px;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

.tabs {
  display: flex;
  gap: 4px;
  background: #0a0d14;
  padding: 4px;
  border-radius: 10px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.tab-btn {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #9ca3af;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: #151922;
  color: #10b981;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.tab-btn:hover:not(.active) {
  color: #e5e7eb;
}

.input-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  align-items: center;
}

.text-input {
  flex: 1;
  padding: 8px 12px;
  background: #0a0d14;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.text-input.short {
  max-width: 140px;
  flex: none;
  width: 140px;
}

.text-input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.text-input::placeholder {
  color: #6b7280;
}

.action-btn {
  padding: 8px 16px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  color: #10b981;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.action-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* xG对比 */
.xg-comparison {
  display: flex;
  align-items: center;
  padding: 24px 20px;
}

.xg-team {
  flex: 1;
  text-align: center;
}

.xg-team-label {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
}

.xg-team-name {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 8px;
}

.xg-team.home .xg-team-name {
  color: #10b981;
}

.xg-team.away .xg-team-name {
  color: #60a5fa;
}

.xg-value {
  font-size: 32px;
  font-weight: 700;
  color: #e5e7eb;
}

.xg-goals {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 6px;
}

.xg-vs {
  padding: 0 20px;
  text-align: center;
}

.xg-vs-label {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
}

.xg-vs-text {
  font-size: 14px;
  font-weight: 700;
  color: #4b5563;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.stat-card {
  padding: 14px 16px;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #e5e7eb;
}

.stat-value.accent {
  color: #10b981;
}

.stat-value.positive {
  color: #10b981;
}

.stat-value.negative {
  color: #ef4444;
}

/* 详情卡片 */
.detail-card {
  padding: 16px 20px;
}

.detail-card h3 {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.xg-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.detail-label {
  font-size: 13px;
  color: #9ca3af;
}

.detail-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.detail-block {
  padding: 10px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.detail-block p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
}

/* xG走势 */
.xg-trend-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.xg-trend-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.trend-date {
  font-size: 12px;
  color: #6b7280;
  min-width: 80px;
}

.trend-opponent {
  font-size: 13px;
  color: #e5e7eb;
  flex: 1;
}

.trend-xg {
  font-size: 12px;
  color: #10b981;
  font-weight: 500;
}

.trend-xga {
  font-size: 12px;
  color: #ef4444;
  font-weight: 500;
}

.trend-goals {
  font-size: 12px;
  color: #9ca3af;
}

/* 射门类型 */
.shot-type-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px;
}

.shot-type-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: #0a0d14;
  border-radius: 4px;
}

.shot-type-name {
  font-size: 12px;
  color: #9ca3af;
}

.shot-type-value {
  font-size: 13px;
  font-weight: 600;
  color: #10b981;
}

/* 逐场对比 */
.match-comparison-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.match-comp-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.comp-date {
  font-size: 12px;
  color: #6b7280;
  min-width: 80px;
}

.comp-opponent {
  font-size: 13px;
  color: #e5e7eb;
  flex: 1;
}

.comp-xg {
  font-size: 12px;
  color: #10b981;
  font-weight: 500;
}

.comp-goals {
  font-size: 12px;
  color: #e5e7eb;
  font-weight: 500;
}

.comp-diff {
  font-size: 12px;
  font-weight: 600;
  min-width: 50px;
  text-align: right;
}

.comp-diff.positive {
  color: #10b981;
}

.comp-diff.negative {
  color: #ef4444;
}

/* 加载/空状态 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
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

.empty-state {
  padding: 40px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
}

@media (max-width: 600px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .xg-comparison {
    flex-direction: column;
    gap: 12px;
  }
  .xg-vs {
    padding: 8px 0;
  }
  .input-row {
    flex-wrap: wrap;
  }
  .text-input.short {
    width: 100%;
    max-width: none;
  }
}
</style>
