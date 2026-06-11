<template>
  <div class="venue-analysis">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>场地分析</h2>
        <p>主场优势、场地影响与距离计算</p>
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

    <!-- 主场表现 -->
    <div v-if="activeTab === 'home'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="homeTeamId"
          placeholder="输入球队ID"
          class="text-input"
          @keyup.enter="loadHomePerformance"
        />
        <button class="action-btn" @click="loadHomePerformance" :disabled="homeLoading">查询</button>
      </div>
      <div class="loading-state" v-if="homeLoading">
        <div class="spinner"></div>
        <p>正在加载主场表现...</p>
      </div>
      <template v-else-if="homePerformance">
        <div class="stats-grid">
          <div class="stat-card card">
            <div class="stat-label">主场比赛数</div>
            <div class="stat-value">{{ homePerformance.total_matches || homePerformance.matches || '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">主场胜率</div>
            <div class="stat-value accent">{{ homePerformance.win_rate != null ? (homePerformance.win_rate * 100).toFixed(1) + '%' : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">主场进球</div>
            <div class="stat-value">{{ homePerformance.goals_scored || homePerformance.avg_goals_scored != null ? (homePerformance.avg_goals_scored || homePerformance.goals_scored) : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">主场失球</div>
            <div class="stat-value">{{ homePerformance.goals_conceded || homePerformance.avg_goals_conceded != null ? (homePerformance.avg_goals_conceded || homePerformance.goals_conceded) : '--' }}</div>
          </div>
        </div>
        <div v-if="homePerformance.recent_matches && homePerformance.recent_matches.length" class="detail-card card">
          <h3>近期主场比赛</h3>
          <div class="match-list">
            <div v-for="(m, idx) in homePerformance.recent_matches" :key="idx" class="match-item">
              <span class="match-teams">{{ m.home_team || '--' }} vs {{ m.away_team || '--' }}</span>
              <span class="match-score">{{ m.home_score != null ? m.home_score : '--' }} : {{ m.away_score != null ? m.away_score : '--' }}</span>
              <span :class="['match-result', resultClass(m)]">{{ resultLabel(m) }}</span>
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="homeTeamId && !homeLoading" class="empty-state card">
        <p>未找到该球队主场数据</p>
      </div>
    </div>

    <!-- 场地影响 -->
    <div v-if="activeTab === 'impact'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="impactMatchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadVenueImpact"
        />
        <button class="action-btn" @click="loadVenueImpact" :disabled="impactLoading">查询</button>
      </div>
      <div class="loading-state" v-if="impactLoading">
        <div class="spinner"></div>
        <p>正在分析场地影响...</p>
      </div>
      <template v-else-if="venueImpact">
        <div class="detail-card card">
          <h3>场地影响因素</h3>
          <div class="impact-content">
            <div v-if="venueImpact.stadium || venueImpact.venue" class="impact-row">
              <span class="impact-label">比赛场地</span>
              <span class="impact-value">{{ venueImpact.stadium || venueImpact.venue }}</span>
            </div>
            <div v-if="venueImpact.altitude != null" class="impact-row">
              <span class="impact-label">海拔高度</span>
              <span class="impact-value">{{ venueImpact.altitude }}m</span>
            </div>
            <div v-if="venueImpact.pitch_type" class="impact-row">
              <span class="impact-label">草皮类型</span>
              <span class="impact-value">{{ venueImpact.pitch_type }}</span>
            </div>
            <div v-if="venueImpact.home_advantage_score != null" class="impact-row">
              <span class="impact-label">主场优势评分</span>
              <span class="impact-value accent">{{ venueImpact.home_advantage_score }}</span>
            </div>
            <div v-if="venueImpact.analysis" class="impact-analysis">
              <p>{{ venueImpact.analysis }}</p>
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="impactMatchId && !impactLoading" class="empty-state card">
        <p>未找到该比赛的场地影响数据</p>
      </div>
    </div>

    <!-- 距离计算 -->
    <div v-if="activeTab === 'distance'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="city1"
          placeholder="城市1"
          class="text-input"
        />
        <span class="input-sep">→</span>
        <input
          v-model="city2"
          placeholder="城市2"
          class="text-input"
        />
        <button class="action-btn" @click="calculateDistance" :disabled="distLoading">计算</button>
      </div>
      <div class="loading-state" v-if="distLoading">
        <div class="spinner"></div>
        <p>正在计算距离...</p>
      </div>
      <template v-else-if="distanceResult">
        <div class="result-card card">
          <div class="distance-display">
            <div class="distance-value">{{ distanceResult.distance_km != null ? distanceResult.distance_km.toFixed(1) : '--' }}</div>
            <div class="distance-unit">公里 (km)</div>
          </div>
          <div v-if="distanceResult.distance_miles != null" class="distance-sub">
            约 {{ distanceResult.distance_miles.toFixed(1) }} 英里
          </div>
          <div v-if="distanceResult.travel_time" class="distance-sub">
            预计行程时间: {{ distanceResult.travel_time }}
          </div>
        </div>
      </template>
      <div v-else-if="city1 && city2 && !distLoading" class="empty-state card">
        <p>无法计算两城市间距离</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'VenueAnalysis',
  setup() {
    const activeTab = ref('home')
    const tabs = [
      { key: 'home', label: '主场表现' },
      { key: 'impact', label: '场地影响' },
      { key: 'distance', label: '距离计算' }
    ]

    // 主场表现
    const homeTeamId = ref('')
    const homeLoading = ref(false)
    const homePerformance = ref(null)

    // 场地影响
    const impactMatchId = ref('')
    const impactLoading = ref(false)
    const venueImpact = ref(null)

    // 距离计算
    const city1 = ref('')
    const city2 = ref('')
    const distLoading = ref(false)
    const distanceResult = ref(null)

    const resultClass = (match) => {
      const hs = match.home_score
      const as = match.away_score
      if (hs == null || as == null) return ''
      if (hs > as) return 'win'
      if (hs < as) return 'loss'
      return 'draw'
    }

    const resultLabel = (match) => {
      const hs = match.home_score
      const as = match.away_score
      if (hs == null || as == null) return '--'
      if (hs > as) return '胜'
      if (hs < as) return '负'
      return '平'
    }

    const loadHomePerformance = async () => {
      if (!homeTeamId.value) return
      homeLoading.value = true
      homePerformance.value = null
      try {
        const res = await analysisAPI.getTeamHomePerformance(homeTeamId.value)
        homePerformance.value = res.data || res || null
      } catch (e) {
        console.error('加载主场表现失败:', e)
        homePerformance.value = null
      } finally {
        homeLoading.value = false
      }
    }

    const loadVenueImpact = async () => {
      if (!impactMatchId.value) return
      impactLoading.value = true
      venueImpact.value = null
      try {
        const res = await analysisAPI.getVenueImpact(impactMatchId.value)
        venueImpact.value = res.data || res || null
      } catch (e) {
        console.error('加载场地影响失败:', e)
        venueImpact.value = null
      } finally {
        impactLoading.value = false
      }
    }

    const calculateDistance = async () => {
      if (!city1.value || !city2.value) return
      distLoading.value = true
      distanceResult.value = null
      try {
        const res = await analysisAPI.calculateDistance(city1.value, city2.value)
        distanceResult.value = res.data || res || null
      } catch (e) {
        console.error('计算距离失败:', e)
        distanceResult.value = null
      } finally {
        distLoading.value = false
      }
    }

    return {
      activeTab, tabs,
      homeTeamId, homeLoading, homePerformance,
      impactMatchId, impactLoading, venueImpact,
      city1, city2, distLoading, distanceResult,
      loadHomePerformance, loadVenueImpact, calculateDistance,
      resultClass, resultLabel
    }
  }
}
</script>

<style scoped>
.venue-analysis {
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

.text-input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.text-input::placeholder {
  color: #6b7280;
}

.input-sep {
  color: #6b7280;
  font-size: 16px;
  font-weight: 600;
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

/* 比赛列表 */
.match-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.match-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.match-teams {
  font-size: 13px;
  color: #e5e7eb;
  flex: 1;
}

.match-score {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
  margin: 0 12px;
}

.match-result {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.match-result.win {
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.match-result.draw {
  color: #9ca3af;
  background: rgba(156, 163, 175, 0.1);
}

.match-result.loss {
  color: #60a5fa;
  background: rgba(96, 165, 250, 0.1);
}

/* 场地影响 */
.impact-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.impact-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.impact-label {
  font-size: 13px;
  color: #9ca3af;
}

.impact-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.impact-value.accent {
  color: #10b981;
}

.impact-analysis {
  padding: 10px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.impact-analysis p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
}

/* 距离结果 */
.result-card {
  padding: 24px 20px;
  text-align: center;
}

.distance-display {
  margin-bottom: 12px;
}

.distance-value {
  font-size: 36px;
  font-weight: 700;
  color: #10b981;
}

.distance-unit {
  font-size: 14px;
  color: #9ca3af;
  margin-top: 4px;
}

.distance-sub {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
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
}
</style>
