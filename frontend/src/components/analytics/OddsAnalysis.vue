<template>
  <div class="odds-analysis">
    <!-- Header Card -->
    <div class="header-card">
      <h2 class="header-title">赔率分析</h2>
      <p class="header-desc">即时赔率对比、最佳赔率计算与API用量查询</p>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Content Area -->
    <div class="content-area">
      <!-- 即时赔率 -->
      <div v-if="activeTab === 'upcoming'" class="tab-panel">
        <div v-if="loading.upcoming" class="loading-state">
          <div class="spinner"></div>
          <span>加载即时赔率...</span>
        </div>
        <div v-else-if="error.upcoming" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.upcoming }}</span>
          <button class="retry-btn" @click="fetchUpcomingOdds">重试</button>
        </div>
        <div v-else-if="upcomingOdds.length === 0" class="empty-state">
          <span>暂无即时赔率数据</span>
        </div>
        <div v-else class="odds-table-wrapper">
          <table class="odds-table">
            <thead>
              <tr>
                <th>联赛</th>
                <th>比赛</th>
                <th>时间</th>
                <th>主胜</th>
                <th>平局</th>
                <th>客胜</th>
                <th>赔率来源</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in upcomingOdds" :key="item.id || item.fixture?.id">
                <td class="td-league">{{ item.league?.name || '-' }}</td>
                <td class="td-match">
                  {{ item.teams?.home?.name || '?' }} vs {{ item.teams?.away?.name || '?' }}
                </td>
                <td class="td-time">{{ formatTime(item.fixture?.date) }}</td>
                <td class="td-odds home-odds">{{ formatOdds(getOddsValue(item, 'home')) }}</td>
                <td class="td-odds draw-odds">{{ formatOdds(getOddsValue(item, 'draw')) }}</td>
                <td class="td-odds away-odds">{{ formatOdds(getOddsValue(item, 'away')) }}</td>
                <td class="td-bookmaker">{{ getBookmaker(item) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 最佳赔率 -->
      <div v-if="activeTab === 'best'" class="tab-panel">
        <div class="best-odds-form">
          <h3 class="form-title">输入赔率计算最佳市场</h3>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">主胜赔率</label>
              <input
                v-model.number="bestHome"
                type="number"
                step="0.01"
                min="1"
                class="form-input"
                placeholder="如 2.10"
              />
            </div>
            <div class="form-group">
              <label class="form-label">平局赔率</label>
              <input
                v-model.number="bestDraw"
                type="number"
                step="0.01"
                min="1"
                class="form-input"
                placeholder="如 3.40"
              />
            </div>
            <div class="form-group">
              <label class="form-label">客胜赔率</label>
              <input
                v-model.number="bestAway"
                type="number"
                step="0.01"
                min="1"
                class="form-input"
                placeholder="如 3.60"
              />
            </div>
          </div>
          <button class="action-btn" @click="fetchBestOdds" :disabled="!canCalcBest">
            计算最佳赔率
          </button>
        </div>

        <div v-if="loading.best" class="loading-state">
          <div class="spinner"></div>
          <span>计算最佳赔率...</span>
        </div>
        <div v-else-if="error.best" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.best }}</span>
        </div>
        <div v-else-if="bestOddsResult" class="best-odds-result">
          <div class="result-grid">
            <div class="result-card primary">
              <span class="result-label">最佳市场</span>
              <span class="result-value highlight">{{ bestOddsResult.best_market || '-' }}</span>
            </div>
            <div class="result-card">
              <span class="result-label">返还率</span>
              <span class="result-value">{{ formatPercent(bestOddsResult.payout) }}</span>
            </div>
          </div>
          <div v-if="bestOddsResult.implied_probabilities" class="implied-section">
            <h4 class="section-subtitle">隐含概率</h4>
            <div class="implied-grid">
              <div class="implied-item">
                <span class="implied-label">主胜</span>
                <div class="implied-bar-container">
                  <div
                    class="implied-bar home"
                    :style="{ width: getImpliedWidth(bestOddsResult.implied_probabilities.home) + '%' }"
                  ></div>
                </div>
                <span class="implied-value">{{ formatPercent(bestOddsResult.implied_probabilities.home) }}</span>
              </div>
              <div class="implied-item">
                <span class="implied-label">平局</span>
                <div class="implied-bar-container">
                  <div
                    class="implied-bar draw"
                    :style="{ width: getImpliedWidth(bestOddsResult.implied_probabilities.draw) + '%' }"
                  ></div>
                </div>
                <span class="implied-value">{{ formatPercent(bestOddsResult.implied_probabilities.draw) }}</span>
              </div>
              <div class="implied-item">
                <span class="implied-label">客胜</span>
                <div class="implied-bar-container">
                  <div
                    class="implied-bar away"
                    :style="{ width: getImpliedWidth(bestOddsResult.implied_probabilities.away) + '%' }"
                  ></div>
                </div>
                <span class="implied-value">{{ formatPercent(bestOddsResult.implied_probabilities.away) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 赔率联赛 -->
      <div v-if="activeTab === 'leagues'" class="tab-panel">
        <div v-if="loading.leagues" class="loading-state">
          <div class="spinner"></div>
          <span>加载可用联赛...</span>
        </div>
        <div v-else-if="error.leagues" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.leagues }}</span>
          <button class="retry-btn" @click="fetchLeagues">重试</button>
        </div>
        <div v-else-if="oddsLeagues.length === 0" class="empty-state">
          <span>暂无可用的赔率联赛数据</span>
        </div>
        <div v-else class="leagues-grid">
          <div v-for="league in oddsLeagues" :key="league.id || league.key" class="league-card">
            <div class="league-icon">
              <img v-if="league.logo" :src="league.logo" :alt="league.name" class="league-logo" />
              <span v-else class="league-fallback">{{ getInitial(league.name) }}</span>
            </div>
            <div class="league-info">
              <span class="league-name">{{ league.name || '未知联赛' }}</span>
              <span class="league-country">{{ league.country || '' }}</span>
            </div>
            <span v-if="league.flag" class="league-flag">{{ league.flag }}</span>
          </div>
        </div>
      </div>

      <!-- API用量 -->
      <div v-if="activeTab === 'usage'" class="tab-panel">
        <div v-if="loading.usage" class="loading-state">
          <div class="spinner"></div>
          <span>加载API用量...</span>
        </div>
        <div v-else-if="error.usage" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.usage }}</span>
          <button class="retry-btn" @click="fetchUsage">重试</button>
        </div>
        <div v-else-if="!apiUsage" class="empty-state">
          <span>暂无API用量数据</span>
        </div>
        <div v-else class="usage-container">
          <div class="usage-overview">
            <div class="usage-card">
              <span class="usage-label">今日请求</span>
              <span class="usage-value">{{ apiUsage.requests?.today ?? apiUsage.current ?? '-' }}</span>
            </div>
            <div class="usage-card">
              <span class="usage-label">每日限额</span>
              <span class="usage-value">{{ apiUsage.requests?.limit ?? apiUsage.limit ?? '-' }}</span>
            </div>
            <div class="usage-card">
              <span class="usage-label">剩余次数</span>
              <span class="usage-value highlight">{{ getRemaining() }}</span>
            </div>
          </div>
          <div class="usage-bar-section">
            <div class="usage-bar-header">
              <span class="usage-bar-label">用量进度</span>
              <span class="usage-bar-percent">{{ getUsagePercent() }}%</span>
            </div>
            <div class="usage-bar">
              <div
                class="usage-bar-fill"
                :class="{ warning: getUsagePercent() > 80, danger: getUsagePercent() > 95 }"
                :style="{ width: Math.min(getUsagePercent(), 100) + '%' }"
              ></div>
            </div>
          </div>
          <div v-if="apiUsage.requests" class="usage-detail-grid">
            <div class="detail-item">
              <span class="detail-label">昨日请求</span>
              <span class="detail-value">{{ apiUsage.requests.yesterday ?? '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">本月请求</span>
              <span class="detail-value">{{ apiUsage.requests.month ?? '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">总请求</span>
              <span class="detail-value">{{ apiUsage.requests.total ?? '-' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { analysisAPI } from '../../api'

const tabs = [
  { key: 'upcoming', label: '即时赔率' },
  { key: 'best', label: '最佳赔率' },
  { key: 'leagues', label: '赔率联赛' },
  { key: 'usage', label: 'API用量' }
]

const activeTab = ref('upcoming')
const loading = reactive({
  upcoming: false,
  best: false,
  leagues: false,
  usage: false
})
const error = reactive({
  upcoming: '',
  best: '',
  leagues: '',
  usage: ''
})

// Data
const upcomingOdds = ref([])
const bestHome = ref(null)
const bestDraw = ref(null)
const bestAway = ref(null)
const bestOddsResult = ref(null)
const oddsLeagues = ref([])
const apiUsage = ref(null)

// Computed
const canCalcBest = computed(() => {
  return bestHome.value > 0 && bestDraw.value > 0 && bestAway.value > 0
})

// Tab switch
function switchTab(key) {
  activeTab.value = key
  if (key === 'upcoming' && upcomingOdds.value.length === 0) fetchUpcomingOdds()
  if (key === 'leagues' && oddsLeagues.value.length === 0) fetchLeagues()
  if (key === 'usage' && !apiUsage.value) fetchUsage()
}

// Fetch upcoming odds
async function fetchUpcomingOdds() {
  loading.upcoming = true
  error.upcoming = ''
  try {
    const res = await analysisAPI.getUpcomingOdds()
    upcomingOdds.value = res?.data || res || []
  } catch (e) {
    error.upcoming = e?.response?.data?.message || e?.message || '获取即时赔率失败'
  } finally {
    loading.upcoming = false
  }
}

// Fetch best odds
async function fetchBestOdds() {
  if (!canCalcBest.value) return
  loading.best = true
  error.best = ''
  try {
    const res = await analysisAPI.getBestOdds(bestHome.value, bestDraw.value, bestAway.value)
    bestOddsResult.value = res?.data || res || null
  } catch (e) {
    error.best = e?.response?.data?.message || e?.message || '计算最佳赔率失败'
  } finally {
    loading.best = false
  }
}

// Fetch leagues
async function fetchLeagues() {
  loading.leagues = true
  error.leagues = ''
  try {
    const res = await analysisAPI.getOddsLeagues()
    oddsLeagues.value = res?.data || res || []
  } catch (e) {
    error.leagues = e?.response?.data?.message || e?.message || '获取赔率联赛失败'
  } finally {
    loading.leagues = false
  }
}

// Fetch usage
async function fetchUsage() {
  loading.usage = true
  error.usage = ''
  try {
    const res = await analysisAPI.getOddsApiUsage()
    apiUsage.value = res?.data || res || null
  } catch (e) {
    error.usage = e?.response?.data?.message || e?.message || '获取API用量失败'
  } finally {
    loading.usage = false
  }
}

// Helpers
function formatTime(dateStr) {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr
  }
}

function formatOdds(val) {
  if (val === null || val === undefined || val === '-') return '-'
  const num = Number(val)
  if (isNaN(num)) return val
  return num.toFixed(2)
}

function formatPercent(val) {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  if (isNaN(num)) return val
  return (num * 100).toFixed(1) + '%'
}

function getOddsValue(item, type) {
  const bets = item?.bookmakers?.[0]?.bets
  if (!bets || bets.length === 0) return '-'
  const matchBet = bets.find(b => b.name === 'Match Winner' || b.name === '1X2' || b.name === 'Match Result')
  if (!matchBet) return '-'
  const values = matchBet.values
  if (!values) return '-'
  if (type === 'home') return values.Home || values.home || values['1'] || '-'
  if (type === 'draw') return values.Draw || values.draw || values.X || '-'
  if (type === 'away') return values.Away || values.away || values['2'] || '-'
  return '-'
}

function getBookmaker(item) {
  return item?.bookmakers?.[0]?.name || '-'
}

function getInitial(name) {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

function getImpliedWidth(prob) {
  if (!prob) return 0
  return Math.min(Number(prob) * 100, 100)
}

function getRemaining() {
  if (!apiUsage.value) return '-'
  const today = apiUsage.value.requests?.today ?? apiUsage.value.current ?? 0
  const limit = apiUsage.value.requests?.limit ?? apiUsage.value.limit ?? 0
  if (limit === 0) return '-'
  return Math.max(limit - today, 0)
}

function getUsagePercent() {
  if (!apiUsage.value) return 0
  const today = apiUsage.value.requests?.today ?? apiUsage.value.current ?? 0
  const limit = apiUsage.value.requests?.limit ?? apiUsage.value.limit ?? 0
  if (limit === 0) return 0
  return Math.round((today / limit) * 100)
}

// Initial fetch
fetchUpcomingOdds()
</script>

<style scoped>
.odds-analysis {
  padding: 0;
}

/* Header Card */
.header-card {
  background: #151922;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  border: 1px solid #1e293b;
}

.header-title {
  font-size: 22px;
  font-weight: 700;
  color: #e5e7eb;
  margin: 0 0 6px 0;
}

.header-desc {
  font-size: 14px;
  color: #9ca3af;
  margin: 0;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: #151922;
  border-radius: 10px;
  padding: 4px;
  border: 1px solid #1e293b;
}

.tab-btn {
  flex: 1;
  padding: 10px 12px;
  background: transparent;
  border: none;
  color: #9ca3af;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: #e5e7eb;
  background: rgba(16, 185, 129, 0.08);
}

.tab-btn.active {
  background: #10b981;
  color: #0a0d14;
  font-weight: 600;
}

/* Content Area */
.content-area {
  min-height: 300px;
}

.tab-panel {
  animation: fadeIn 0.25s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Loading / Error / Empty */
.loading-state,
.error-state,
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 20px;
  color: #9ca3af;
  font-size: 14px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #1e293b;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  flex-direction: column;
  color: #f87171;
}

.error-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}

.retry-btn {
  margin-top: 8px;
  padding: 6px 16px;
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.retry-btn:hover {
  background: rgba(248, 113, 113, 0.25);
}

/* Odds Table */
.odds-table-wrapper {
  overflow-x: auto;
  border-radius: 10px;
  border: 1px solid #1e293b;
}

.odds-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.odds-table thead {
  background: rgba(16, 185, 129, 0.06);
}

.odds-table th {
  padding: 12px 14px;
  text-align: left;
  color: #9ca3af;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #1e293b;
  white-space: nowrap;
}

.odds-table td {
  padding: 10px 14px;
  color: #e5e7eb;
  border-bottom: 1px solid rgba(30, 41, 59, 0.5);
  white-space: nowrap;
}

.odds-table tbody tr:hover {
  background: rgba(16, 185, 129, 0.04);
}

.odds-table tbody tr:last-child td {
  border-bottom: none;
}

.td-league {
  color: #9ca3af;
  font-size: 12px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.td-match {
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.td-time {
  color: #6b7280;
  font-size: 12px;
}

.td-odds {
  font-weight: 700;
  font-size: 14px;
  text-align: center;
}

.home-odds {
  color: #10b981;
}

.draw-odds {
  color: #fbbf24;
}

.away-odds {
  color: #60a5fa;
}

.td-bookmaker {
  color: #9ca3af;
  font-size: 12px;
}

/* Best Odds Form */
.best-odds-form {
  background: #151922;
  border-radius: 10px;
  padding: 20px;
  border: 1px solid #1e293b;
  margin-bottom: 20px;
}

.form-title {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  margin: 0 0 16px 0;
}

.form-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.form-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.form-input {
  padding: 10px 14px;
  background: #0a0d14;
  border: 1px solid #1e293b;
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
  width: 100%;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: #10b981;
}

.form-input::placeholder {
  color: #4b5563;
}

.action-btn {
  padding: 10px 24px;
  background: #10b981;
  color: #0a0d14;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: #059669;
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Best Odds Result */
.best-odds-result {
  animation: fadeIn 0.3s ease;
}

.result-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}

.result-card {
  background: #151922;
  border-radius: 10px;
  padding: 20px;
  border: 1px solid #1e293b;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-card.primary {
  border-color: rgba(16, 185, 129, 0.3);
  background: rgba(16, 185, 129, 0.05);
}

.result-label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.result-value {
  font-size: 22px;
  font-weight: 700;
  color: #e5e7eb;
}

.result-value.highlight {
  color: #10b981;
}

/* Implied Probabilities */
.implied-section {
  background: #151922;
  border-radius: 10px;
  padding: 20px;
  border: 1px solid #1e293b;
}

.section-subtitle {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin: 0 0 16px 0;
}

.implied-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.implied-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.implied-label {
  min-width: 40px;
  font-size: 13px;
  color: #9ca3af;
  font-weight: 500;
}

.implied-bar-container {
  flex: 1;
  height: 8px;
  background: #0a0d14;
  border-radius: 4px;
  overflow: hidden;
}

.implied-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.implied-bar.home {
  background: #10b981;
}

.implied-bar.draw {
  background: #fbbf24;
}

.implied-bar.away {
  background: #60a5fa;
}

.implied-value {
  min-width: 56px;
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
  text-align: right;
}

/* Leagues Grid */
.leagues-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
}

.league-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #151922;
  border-radius: 10px;
  border: 1px solid #1e293b;
  transition: border-color 0.2s;
}

.league-card:hover {
  border-color: #10b981;
}

.league-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #0a0d14;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

.league-logo {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.league-fallback {
  font-size: 16px;
  font-weight: 700;
  color: #10b981;
}

.league-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.league-name {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.league-country {
  font-size: 12px;
  color: #6b7280;
}

.league-flag {
  font-size: 18px;
}

/* API Usage */
.usage-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.usage-overview {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.usage-card {
  background: #151922;
  border-radius: 10px;
  padding: 20px;
  border: 1px solid #1e293b;
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: center;
}

.usage-label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.usage-value {
  font-size: 28px;
  font-weight: 700;
  color: #e5e7eb;
}

.usage-value.highlight {
  color: #10b981;
}

.usage-bar-section {
  background: #151922;
  border-radius: 10px;
  padding: 16px 20px;
  border: 1px solid #1e293b;
}

.usage-bar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.usage-bar-label {
  font-size: 13px;
  color: #9ca3af;
  font-weight: 500;
}

.usage-bar-percent {
  font-size: 14px;
  font-weight: 700;
  color: #e5e7eb;
}

.usage-bar {
  height: 10px;
  background: #0a0d14;
  border-radius: 5px;
  overflow: hidden;
}

.usage-bar-fill {
  height: 100%;
  background: #10b981;
  border-radius: 5px;
  transition: width 0.5s ease;
}

.usage-bar-fill.warning {
  background: #fbbf24;
}

.usage-bar-fill.danger {
  background: #f87171;
}

.usage-detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.detail-item {
  background: #151922;
  border-radius: 10px;
  padding: 14px 16px;
  border: 1px solid #1e293b;
  display: flex;
  justify-content: space-between;
  align-items: center;
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
</style>
