<template>
  <div class="live-data">
    <!-- Header Card -->
    <div class="header-card">
      <h2 class="header-title">实时数据</h2>
      <p class="header-desc">实时比赛数据、事件追踪与球员评分</p>
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
      <!-- 实时比赛 -->
      <div v-if="activeTab === 'live'" class="tab-panel">
        <div v-if="loading.live" class="loading-state">
          <div class="spinner"></div>
          <span>加载实时比赛中...</span>
        </div>
        <div v-else-if="error.live" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.live }}</span>
          <button class="retry-btn" @click="fetchLiveMatches">重试</button>
        </div>
        <div v-else-if="liveMatches.length === 0" class="empty-state">
          <span>暂无正在进行的比赛</span>
        </div>
        <div v-else class="match-list">
          <div v-for="match in liveMatches" :key="match.id || match.fixture?.id" class="match-card">
            <div class="match-header">
              <span class="match-league">{{ match.league?.name || '未知联赛' }}</span>
              <span class="match-time live-indicator">
                <span class="pulse-dot"></span>
                {{ match.fixture?.status?.elapsed ? `${match.fixture.status.elapsed}'` : '进行中' }}
              </span>
            </div>
            <div class="match-body">
              <div class="team-row">
                <span class="team-name">{{ match.teams?.home?.name || '主队' }}</span>
                <span class="team-score">{{ match.goals?.home ?? '-' }}</span>
              </div>
              <div class="team-row">
                <span class="team-name">{{ match.teams?.away?.name || '客队' }}</span>
                <span class="team-score">{{ match.goals?.away ?? '-' }}</span>
              </div>
            </div>
            <div class="match-footer">
              <span class="match-date">{{ formatTime(match.fixture?.date) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 即将开赛 -->
      <div v-if="activeTab === 'upcoming'" class="tab-panel">
        <div v-if="loading.upcoming" class="loading-state">
          <div class="spinner"></div>
          <span>加载即将开赛的比赛...</span>
        </div>
        <div v-else-if="error.upcoming" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.upcoming }}</span>
          <button class="retry-btn" @click="fetchUpcoming">重试</button>
        </div>
        <div v-else-if="upcomingMatches.length === 0" class="empty-state">
          <span>暂无即将开赛的比赛</span>
        </div>
        <div v-else class="match-list">
          <div v-for="match in upcomingMatches" :key="match.id || match.fixture?.id" class="match-card upcoming">
            <div class="match-header">
              <span class="match-league">{{ match.league?.name || '未知联赛' }}</span>
              <span class="match-time upcoming-tag">即将开赛</span>
            </div>
            <div class="match-body">
              <div class="team-row">
                <span class="team-name">{{ match.teams?.home?.name || '主队' }}</span>
                <span class="team-score">-</span>
              </div>
              <div class="team-row">
                <span class="team-name">{{ match.teams?.away?.name || '客队' }}</span>
                <span class="team-score">-</span>
              </div>
            </div>
            <div class="match-footer">
              <span class="match-date">{{ formatTime(match.fixture?.date) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 比赛事件 -->
      <div v-if="activeTab === 'events'" class="tab-panel">
        <div class="input-row">
          <label class="input-label">比赛 ID</label>
          <input
            v-model="eventId"
            type="number"
            class="input-field"
            placeholder="请输入比赛ID"
            @keyup.enter="fetchEvents"
          />
          <button class="action-btn" @click="fetchEvents" :disabled="!eventId">查询事件</button>
        </div>
        <div v-if="loading.events" class="loading-state">
          <div class="spinner"></div>
          <span>加载比赛事件...</span>
        </div>
        <div v-else-if="error.events" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.events }}</span>
        </div>
        <div v-else-if="events.length === 0 && eventsFetched" class="empty-state">
          <span>暂无比赛事件数据</span>
        </div>
        <div v-else-if="events.length > 0" class="event-timeline">
          <div
            v-for="(event, index) in events"
            :key="index"
            :class="['event-item', `event-${event.type?.toLowerCase()}`]"
          >
            <div class="event-time-badge">
              {{ event.time?.elapsed ?? '?' }}'
            </div>
            <div class="event-details">
              <span :class="['event-type-badge', `type-${event.type?.toLowerCase()}`]">
                {{ getEventTypeLabel(event.type) }}
              </span>
              <span class="event-player">{{ event.player?.name || '未知球员' }}</span>
              <span class="event-team">{{ event.team?.name || '' }}</span>
              <span v-if="event.detail" class="event-detail">{{ event.detail }}</span>
              <span v-if="event.assist?.name" class="event-assist">助攻: {{ event.assist.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 比赛统计 -->
      <div v-if="activeTab === 'statistics'" class="tab-panel">
        <div class="input-row">
          <label class="input-label">比赛 ID</label>
          <input
            v-model="statsEventId"
            type="number"
            class="input-field"
            placeholder="请输入比赛ID"
            @keyup.enter="fetchStatistics"
          />
          <button class="action-btn" @click="fetchStatistics" :disabled="!statsEventId">查询统计</button>
        </div>
        <div v-if="loading.statistics" class="loading-state">
          <div class="spinner"></div>
          <span>加载比赛统计...</span>
        </div>
        <div v-else-if="error.statistics" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.statistics }}</span>
        </div>
        <div v-else-if="statistics.length === 0 && statsFetched" class="empty-state">
          <span>暂无比赛统计数据</span>
        </div>
        <div v-else-if="statistics.length > 0" class="stats-comparison">
          <div v-if="statTeams.home || statTeams.away" class="stats-teams-header">
            <span class="stats-team-name">{{ statTeams.home || '主队' }}</span>
            <span class="stats-vs">VS</span>
            <span class="stats-team-name">{{ statTeams.away || '客队' }}</span>
          </div>
          <div v-for="(stat, index) in statistics" :key="index" class="stat-row">
            <span class="stat-value-home">{{ stat.home ?? '-' }}</span>
            <div class="stat-bar-container">
              <div class="stat-label">{{ stat.type || stat.label }}</div>
              <div class="stat-bar">
                <div
                  class="stat-bar-fill home"
                  :style="{ width: getBarWidth(stat.home, stat.away) + '%' }"
                ></div>
                <div
                  class="stat-bar-fill away"
                  :style="{ width: getBarWidth(stat.away, stat.home) + '%' }"
                ></div>
              </div>
            </div>
            <span class="stat-value-away">{{ stat.away ?? '-' }}</span>
          </div>
        </div>
      </div>

      <!-- 球员评分 -->
      <div v-if="activeTab === 'ratings'" class="tab-panel">
        <div class="input-row">
          <label class="input-label">比赛 ID</label>
          <input
            v-model="ratingsEventId"
            type="number"
            class="input-field"
            placeholder="请输入比赛ID"
            @keyup.enter="fetchRatings"
          />
          <button class="action-btn" @click="fetchRatings" :disabled="!ratingsEventId">查询评分</button>
        </div>
        <div v-if="loading.ratings" class="loading-state">
          <div class="spinner"></div>
          <span>加载球员评分...</span>
        </div>
        <div v-else-if="error.ratings" class="error-state">
          <span class="error-icon">!</span>
          <span>{{ error.ratings }}</span>
        </div>
        <div v-else-if="playerRatings.length === 0 && ratingsFetched" class="empty-state">
          <span>暂无球员评分数据</span>
        </div>
        <div v-else-if="playerRatings.length > 0" class="ratings-container">
          <div v-for="teamRatings in playerRatings" :key="teamRatings.team?.id || teamRatings.team?.name" class="ratings-team-group">
            <h3 class="ratings-team-title">{{ teamRatings.team?.name || '球队' }}</h3>
            <div class="ratings-table">
              <div class="ratings-table-header">
                <span class="col-player">球员</span>
                <span class="col-pos">位置</span>
                <span class="col-rating">评分</span>
              </div>
              <div
                v-for="player in teamRatings.players || []"
                :key="player.player?.id || player.player?.name"
                class="ratings-table-row"
              >
                <span class="col-player">{{ player.player?.name || '未知' }}</span>
                <span class="col-pos">{{ player.games?.position || '-' }}</span>
                <span :class="['col-rating', getRatingClass(player.games?.rating)]">
                  {{ player.games?.rating ? Number(player.games.rating).toFixed(1) : '-' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { analysisAPI } from '../../api'

const tabs = [
  { key: 'live', label: '实时比赛' },
  { key: 'upcoming', label: '即将开赛' },
  { key: 'events', label: '比赛事件' },
  { key: 'statistics', label: '比赛统计' },
  { key: 'ratings', label: '球员评分' }
]

const activeTab = ref('live')
const loading = reactive({
  live: false,
  upcoming: false,
  events: false,
  statistics: false,
  ratings: false
})
const error = reactive({
  live: '',
  upcoming: '',
  events: '',
  statistics: '',
  ratings: ''
})

// Data
const liveMatches = ref([])
const upcomingMatches = ref([])
const eventId = ref('')
const events = ref([])
const eventsFetched = ref(false)
const statsEventId = ref('')
const statistics = ref([])
const statTeams = reactive({ home: '', away: '' })
const statsFetched = ref(false)
const ratingsEventId = ref('')
const playerRatings = ref([])
const ratingsFetched = ref(false)

// Tab switch
function switchTab(key) {
  activeTab.value = key
  if (key === 'live' && liveMatches.value.length === 0) fetchLiveMatches()
  if (key === 'upcoming' && upcomingMatches.value.length === 0) fetchUpcoming()
}

// Fetch live matches
async function fetchLiveMatches() {
  loading.live = true
  error.live = ''
  try {
    const res = await analysisAPI.getLiveMatches()
    liveMatches.value = res?.data || res || []
  } catch (e) {
    error.live = e?.response?.data?.message || e?.message || '获取实时比赛失败'
  } finally {
    loading.live = false
  }
}

// Fetch upcoming
async function fetchUpcoming() {
  loading.upcoming = true
  error.upcoming = ''
  try {
    const res = await analysisAPI.getUpcomingLive()
    upcomingMatches.value = res?.data || res || []
  } catch (e) {
    error.upcoming = e?.response?.data?.message || e?.message || '获取即将开赛数据失败'
  } finally {
    loading.upcoming = false
  }
}

// Fetch events
async function fetchEvents() {
  if (!eventId.value) return
  loading.events = true
  error.events = ''
  eventsFetched.value = false
  try {
    const res = await analysisAPI.getMatchEvents(eventId.value)
    events.value = res?.data || res || []
    eventsFetched.value = true
  } catch (e) {
    error.events = e?.response?.data?.message || e?.message || '获取比赛事件失败'
    eventsFetched.value = true
  } finally {
    loading.events = false
  }
}

// Fetch statistics
async function fetchStatistics() {
  if (!statsEventId.value) return
  loading.statistics = true
  error.statistics = ''
  statsFetched.value = false
  try {
    const res = await analysisAPI.getMatchStatistics(statsEventId.value)
    const data = res?.data || res || []
    if (Array.isArray(data) && data.length > 0) {
      const first = data[0]
      statTeams.home = first?.team?.name || ''
      if (data.length > 1) {
        statTeams.away = data[1]?.team?.name || ''
        statistics.value = (first?.statistics || []).map((s, i) => ({
          type: s.type,
          home: s.value,
          away: data[1]?.statistics?.[i]?.value
        }))
      } else {
        statistics.value = (first?.statistics || []).map(s => ({
          type: s.type,
          home: s.value,
          away: '-'
        }))
      }
    } else {
      statistics.value = data
    }
    statsFetched.value = true
  } catch (e) {
    error.statistics = e?.response?.data?.message || e?.message || '获取比赛统计失败'
    statsFetched.value = true
  } finally {
    loading.statistics = false
  }
}

// Fetch ratings
async function fetchRatings() {
  if (!ratingsEventId.value) return
  loading.ratings = true
  error.ratings = ''
  ratingsFetched.value = false
  try {
    const res = await analysisAPI.getPlayerRatings(ratingsEventId.value)
    playerRatings.value = res?.data || res || []
    ratingsFetched.value = true
  } catch (e) {
    error.ratings = e?.response?.data?.message || e?.message || '获取球员评分失败'
    ratingsFetched.value = true
  } finally {
    loading.ratings = false
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

function getEventTypeLabel(type) {
  const map = { Goal: '进球', Card: '卡片', subst: '换人', Var: 'VAR' }
  return map[type] || type || '事件'
}

function getBarWidth(val, oppositeVal) {
  const num = parseFloat(val)
  const opp = parseFloat(oppositeVal)
  if (isNaN(num) || (isNaN(num) && isNaN(opp))) return 50
  if (isNaN(opp) || opp === 0) return num > 0 ? 100 : 0
  const total = num + opp
  if (total === 0) return 50
  return (num / total) * 100
}

function getRatingClass(rating) {
  const r = Number(rating)
  if (isNaN(r)) return ''
  if (r >= 8) return 'rating-excellent'
  if (r >= 7) return 'rating-good'
  if (r >= 6) return 'rating-average'
  return 'rating-poor'
}

// Initial fetch
fetchLiveMatches()
</script>

<style scoped>
.live-data {
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

/* Input Row */
.input-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  background: #151922;
  padding: 16px;
  border-radius: 10px;
  border: 1px solid #1e293b;
}

.input-label {
  font-size: 13px;
  color: #9ca3af;
  white-space: nowrap;
  font-weight: 500;
}

.input-field {
  flex: 1;
  max-width: 240px;
  padding: 8px 14px;
  background: #0a0d14;
  border: 1px solid #1e293b;
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.input-field:focus {
  border-color: #10b981;
}

.input-field::placeholder {
  color: #4b5563;
}

.action-btn {
  padding: 8px 20px;
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

/* Match List */
.match-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.match-card {
  background: #151922;
  border-radius: 10px;
  border: 1px solid #1e293b;
  overflow: hidden;
  transition: border-color 0.2s;
}

.match-card:hover {
  border-color: #10b981;
}

.match-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: rgba(16, 185, 129, 0.05);
  border-bottom: 1px solid #1e293b;
}

.match-league {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.match-time {
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 5px;
}

.live-indicator {
  color: #10b981;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  animation: pulse 1.5s ease infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.upcoming-tag {
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.12);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.match-body {
  padding: 12px 14px;
}

.team-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.team-name {
  font-size: 14px;
  color: #e5e7eb;
}

.team-score {
  font-size: 18px;
  font-weight: 700;
  color: #10b981;
  min-width: 24px;
  text-align: right;
}

.match-footer {
  padding: 8px 14px;
  border-top: 1px solid #1e293b;
}

.match-date {
  font-size: 12px;
  color: #6b7280;
}

/* Event Timeline */
.event-timeline {
  position: relative;
  padding-left: 20px;
}

.event-timeline::before {
  content: '';
  position: absolute;
  left: 22px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #1e293b;
}

.event-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 12px 16px;
  margin-bottom: 8px;
  background: #151922;
  border-radius: 10px;
  border: 1px solid #1e293b;
  position: relative;
}

.event-item::before {
  content: '';
  position: absolute;
  left: -22px;
  top: 18px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #1e293b;
  border: 2px solid #10b981;
}

.event-goal::before {
  background: #10b981;
  border-color: #10b981;
}

.event-card::before {
  background: #fbbf24;
  border-color: #fbbf24;
}

.event-subst::before {
  background: #60a5fa;
  border-color: #60a5fa;
}

.event-time-badge {
  min-width: 36px;
  padding: 4px 8px;
  background: #0a0d14;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
  text-align: center;
}

.event-details {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.event-type-badge {
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.type-goal {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.type-card {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.type-subst {
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
}

.type-var {
  background: rgba(167, 139, 250, 0.15);
  color: #a78bfa;
}

.event-player {
  font-size: 14px;
  color: #e5e7eb;
  font-weight: 500;
}

.event-team {
  font-size: 12px;
  color: #6b7280;
}

.event-detail {
  font-size: 12px;
  color: #9ca3af;
}

.event-assist {
  font-size: 12px;
  color: #10b981;
}

/* Stats Comparison */
.stats-teams-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #151922;
  border-radius: 10px 10px 0 0;
  border: 1px solid #1e293b;
  border-bottom: none;
  margin-bottom: 0;
}

.stats-team-name {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  flex: 1;
}

.stats-team-name:last-child {
  text-align: right;
}

.stats-vs {
  font-size: 13px;
  color: #6b7280;
  font-weight: 600;
  padding: 0 16px;
}

.stat-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: #151922;
  border-left: 1px solid #1e293b;
  border-right: 1px solid #1e293b;
}

.stat-row:last-child {
  border-bottom: 1px solid #1e293b;
  border-radius: 0 0 10px 10px;
}

.stat-value-home,
.stat-value-away {
  min-width: 48px;
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
  text-align: center;
}

.stat-bar-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}

.stat-bar {
  display: flex;
  height: 6px;
  background: #0a0d14;
  border-radius: 3px;
  overflow: hidden;
}

.stat-bar-fill {
  height: 100%;
  transition: width 0.4s ease;
  border-radius: 3px;
}

.stat-bar-fill.home {
  background: #10b981;
  margin-right: 1px;
}

.stat-bar-fill.away {
  background: #60a5fa;
}

/* Ratings */
.ratings-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.ratings-team-group {
  background: #151922;
  border-radius: 10px;
  border: 1px solid #1e293b;
  overflow: hidden;
}

.ratings-team-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  padding: 12px 16px;
  margin: 0;
  background: rgba(16, 185, 129, 0.05);
  border-bottom: 1px solid #1e293b;
}

.ratings-table-header,
.ratings-table-row {
  display: flex;
  padding: 8px 16px;
  align-items: center;
}

.ratings-table-header {
  border-bottom: 1px solid #1e293b;
  font-size: 12px;
  color: #6b7280;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.ratings-table-row {
  border-bottom: 1px solid rgba(30, 41, 59, 0.5);
  transition: background 0.15s;
}

.ratings-table-row:hover {
  background: rgba(16, 185, 129, 0.04);
}

.ratings-table-row:last-child {
  border-bottom: none;
}

.col-player {
  flex: 2;
  font-size: 13px;
  color: #e5e7eb;
}

.col-pos {
  flex: 1;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}

.col-rating {
  flex: 1;
  font-size: 14px;
  font-weight: 700;
  text-align: right;
}

.rating-excellent {
  color: #10b981;
}

.rating-good {
  color: #60a5fa;
}

.rating-average {
  color: #fbbf24;
}

.rating-poor {
  color: #f87171;
}
</style>
