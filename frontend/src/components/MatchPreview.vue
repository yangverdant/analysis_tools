<template>
  <div class="match-preview">
    <!-- 头部 -->
    <div class="header-section card">
      <div class="header-top">
        <div class="title-section">
          <h2 class="page-title">
            <CalendarIcon />
            赛事前瞻
          </h2>
          <p class="subtitle">查看今日比赛安排与实时比分</p>
        </div>
        <div class="date-nav">
          <button class="nav-btn" @click="prevDay">
            <ChevronLeftIcon />
          </button>
          <span class="current-date">{{ todayDate }}</span>
          <button class="nav-btn" @click="nextDay">
            <ChevronRightIcon />
          </button>
        </div>
      </div>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <button
          v-for="filter in filters"
          :key="filter.value"
          :class="['filter-btn', { active: activeFilter === filter.value }]"
          @click="activeFilter = filter.value"
        >
          {{ filter.label }}
          <span class="filter-count">{{ getFilterCount(filter.value) }}</span>
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <LoadingSpinner />
      <span>加载中...</span>
    </div>

    <!-- 无比赛 -->
    <div v-else-if="!filteredMatches.length" class="empty-state card">
      <CalendarIcon class="empty-icon" />
      <h3>暂无比赛</h3>
      <p>{{ todayDate }} 没有符合条件的比赛</p>
    </div>

    <!-- 比赛列表 -->
    <div v-else class="leagues-container">
      <div v-for="league in groupedMatches" :key="league.league_id" class="league-section card">
        <!-- 联赛头部 -->
        <div class="league-header">
          <div class="league-info">
            <span class="league-logo">⚽</span>
            <span class="league-name">{{ league.name_cn || league.name }}</span>
            <span class="league-country">{{ league.country_cn || league.country || '' }}</span>
          </div>
          <span class="match-count">{{ league.matches.length }} 场比赛</span>
        </div>

        <!-- 横向滚动的比赛卡片 -->
        <div class="matches-scroll">
          <div
            v-for="match in league.matches"
            :key="match.match_id"
            :class="['match-card', getStatusClass(match)]"
          >
            <!-- 状态标签 -->
            <div class="match-status-row">
              <span class="status-badge" :class="getStatusClass(match)">
                <span v-if="isLive(match)" class="pulse-dot"></span>
                {{ getStatusText(match) }}
              </span>
              <span class="match-time">{{ match.beijing_time || match.match_time }}</span>
            </div>

            <!-- 球队信息 -->
            <div class="teams-section">
              <div class="team home">
                <div class="team-logo">
                  <img :src="getTeamLogo(match.home_team, match.home_team_id)" :alt="match.home_team" />
                </div>
                <span class="team-name">{{ match.home_team_cn || match.home_team }}</span>
              </div>

              <div class="score-area">
                <template v-if="hasScore(match)">
                  <span class="score">{{ match.home_goals }}</span>
                  <span class="score-sep">-</span>
                  <span class="score">{{ match.away_goals }}</span>
                </template>
                <template v-else>
                  <span class="vs">VS</span>
                </template>
              </div>

              <div class="team away">
                <div class="team-logo">
                  <img :src="getTeamLogo(match.away_team, match.away_team_id)" :alt="match.away_team" />
                </div>
                <span class="team-name">{{ match.away_team_cn || match.away_team }}</span>
              </div>
            </div>

            <!-- 查看详情 -->
            <button class="detail-btn" @click="selectMatch(match)">
              查看详情
              <ArrowRightIcon />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 选中比赛详情弹窗 -->
    <div v-if="selectedMatch" class="modal-overlay" @click.self="selectedMatch = null">
      <div class="modal-content">
        <button class="modal-close" @click="selectedMatch = null">
          <XIcon />
        </button>

        <div class="modal-header">
          <span class="modal-league">{{ selectedMatch.league_cn || selectedMatch.league }}</span>
          <span class="modal-status" :class="getStatusClass(selectedMatch)">
            {{ getStatusText(selectedMatch) }}
          </span>
        </div>

        <div class="modal-teams">
          <div class="modal-team">
            <img :src="getTeamLogo(selectedMatch.home_team, selectedMatch.home_team_id)" class="modal-team-logo" />
            <span class="modal-team-name">{{ selectedMatch.home_team_cn || selectedMatch.home_team }}</span>
          </div>

          <div class="modal-vs-section">
            <template v-if="hasScore(selectedMatch)">
              <div class="modal-score">
                <span class="modal-score-num">{{ selectedMatch.home_goals }}</span>
                <span class="modal-score-divider">:</span>
                <span class="modal-score-num">{{ selectedMatch.away_goals }}</span>
              </div>
            </template>
            <template v-else>
              <span class="modal-vs">VS</span>
            </template>
            <span class="modal-time">{{ selectedMatch.beijing_time || selectedMatch.match_time }}</span>
          </div>

          <div class="modal-team">
            <img :src="getTeamLogo(selectedMatch.away_team, selectedMatch.away_team_id)" class="modal-team-logo" />
            <span class="modal-team-name">{{ selectedMatch.away_team_cn || selectedMatch.away_team }}</span>
          </div>
        </div>

        <div class="modal-info" v-if="selectedMatch.stadium">
          <div class="info-item">
            <MapPinIcon />
            <span>{{ selectedMatch.stadium }}</span>
          </div>
        </div>

        <!-- 预测 -->
        <div class="modal-prediction" v-if="prediction">
          <h4>赛前预测</h4>
          <div class="prediction-bars">
            <div class="prediction-bar">
              <span class="bar-label">主胜</span>
              <div class="bar-track">
                <div class="bar-fill home" :style="{ width: prediction.home_win_prob + '%' }"></div>
              </div>
              <span class="bar-value">{{ prediction.home_win_prob }}%</span>
            </div>
            <div class="prediction-bar">
              <span class="bar-label">平局</span>
              <div class="bar-track">
                <div class="bar-fill draw" :style="{ width: prediction.draw_prob + '%' }"></div>
              </div>
              <span class="bar-value">{{ prediction.draw_prob }}%</span>
            </div>
            <div class="prediction-bar">
              <span class="bar-label">客胜</span>
              <div class="bar-track">
                <div class="bar-fill away" :style="{ width: prediction.away_win_prob + '%' }"></div>
              </div>
              <span class="bar-value">{{ prediction.away_win_prob }}%</span>
            </div>
          </div>
        </div>

        <div class="modal-prediction" v-else-if="predictionLoading">
          <h4>赛前预测</h4>
          <span class="loading-text">计算中...</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, h, onMounted, watch, defineComponent } from 'vue'
import { matchAPI, analysisAPI } from '../api'

// 图标组件
const CalendarIcon = defineComponent({
  name: 'CalendarIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }),
      h('line', { x1: '16', y1: '2', x2: '16', y2: '6' }),
      h('line', { x1: '8', y1: '2', x2: '8', y2: '6' }),
      h('line', { x1: '3', y1: '10', x2: '21', y2: '10' })
    ])
  }
})

const ChevronLeftIcon = defineComponent({
  name: 'ChevronLeftIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '15 18 9 12 15 6' })
    ])
  }
})

const ChevronRightIcon = defineComponent({
  name: 'ChevronRightIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '9 18 15 12 9 6' })
    ])
  }
})

const ClockIcon = defineComponent({
  name: 'ClockIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('circle', { cx: '12', cy: '12', r: '10' }),
      h('polyline', { points: '12 6 12 12 16 14' })
    ])
  }
})

const MapPinIcon = defineComponent({
  name: 'MapPinIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z' }),
      h('circle', { cx: '12', cy: '10', r: '3' })
    ])
  }
})

const XIcon = defineComponent({
  name: 'XIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('line', { x1: '18', y1: '6', x2: '6', y2: '18' }),
      h('line', { x1: '6', y1: '6', x2: '18', y2: '18' })
    ])
  }
})

const ArrowRightIcon = defineComponent({
  name: 'ArrowRightIcon',
  setup() {
    return () => h('svg', { class: 'w-3 h-3', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('line', { x1: '5', y1: '12', x2: '19', y2: '12' }),
      h('polyline', { points: '12 5 19 12 12 19' })
    ])
  }
})

const LoadingSpinner = defineComponent({
  name: 'LoadingSpinner',
  setup() {
    return () => h('div', { class: 'spinner' })
  }
})

export default {
  name: 'MatchPreview',
  components: {
    CalendarIcon, ChevronLeftIcon, ChevronRightIcon, ClockIcon, MapPinIcon, XIcon, ArrowRightIcon, LoadingSpinner
  },
  setup() {
    const loading = ref(false)
    const matches = ref([])
    const selectedMatch = ref(null)
    const prediction = ref(null)
    const predictionLoading = ref(false)
    const currentDate = ref(new Date())
    const activeFilter = ref('all')

    const filters = [
      { label: '全部比赛', value: 'all' },
      { label: '进行中', value: 'live' },
      { label: '未开始', value: 'upcoming' },
      { label: '已结束', value: 'finished' }
    ]

    const todayDate = computed(() => {
      const d = currentDate.value
      return `${d.getMonth() + 1}月${d.getDate()}日 星期${'日一二三四五六'[d.getDay()]}`
    })

    const isLive = (match) => {
      return match.status === 'Live' || match.status === 'Today'
    }

    const isFinished = (match) => {
      return match.status === 'Finished'
    }

    const isUpcoming = (match) => {
      return match.status === 'Scheduled' || !match.status
    }

    const hasScore = (match) => {
      return match.status === 'Finished' || match.home_goals !== null
    }

    const getFilterCount = (filter) => {
      if (filter === 'all') return matches.value.length
      if (filter === 'live') return matches.value.filter(m => isLive(m)).length
      if (filter === 'finished') return matches.value.filter(m => isFinished(m)).length
      if (filter === 'upcoming') return matches.value.filter(m => isUpcoming(m)).length
      return 0
    }

    const filteredMatches = computed(() => {
      let result = matches.value

      // 按状态筛选
      if (activeFilter.value === 'live') result = matches.value.filter(m => isLive(m))
      else if (activeFilter.value === 'finished') result = matches.value.filter(m => isFinished(m))
      else if (activeFilter.value === 'upcoming') result = matches.value.filter(m => isUpcoming(m))

      // 按时间排序
      return result.sort((a, b) => {
        const timeA = a.beijing_time || a.match_time || ''
        const timeB = b.beijing_time || b.match_time || ''
        return timeA.localeCompare(timeB)
      })
    })

    const groupedMatches = computed(() => {
      // 按联赛分组
      const groups = {}
      for (const match of filteredMatches.value) {
        const key = match.league_id || match.league
        if (!groups[key]) {
          groups[key] = {
            league_id: match.league_id,
            name: match.league,
            name_cn: match.league_cn,
            country: match.league_country,
            country_cn: match.league_country_cn,
            matches: []
          }
        }
        groups[key].matches.push(match)
      }
      return Object.values(groups)
    })

    const formatDate = (date) => {
      const d = date instanceof Date ? date : new Date(date)
      return d.toISOString().split('T')[0]
    }

    const loadMatches = async () => {
      loading.value = true
      try {
        // 根据当前选择的日期加载比赛
        const dateStr = formatDate(currentDate.value)
        const res = await matchAPI.getByDate(dateStr)
        matches.value = res.data || []
      } catch (e) {
        console.error('加载比赛失败:', e)
        matches.value = []
      } finally {
        loading.value = false
      }
    }

    const prevDay = () => {
      const d = new Date(currentDate.value)
      d.setDate(d.getDate() - 1)
      currentDate.value = d
    }

    const nextDay = () => {
      const d = new Date(currentDate.value)
      d.setDate(d.getDate() + 1)
      currentDate.value = d
    }

    const selectMatch = async (match) => {
      selectedMatch.value = match
      prediction.value = null
      predictionLoading.value = true

      try {
        if (match.home_team_id && match.away_team_id) {
          const res = await analysisAPI.predictMatch(match.home_team_id, match.away_team_id)
          prediction.value = res.data
        }
      } catch (e) {
        console.error('加载预测失败:', e)
      } finally {
        predictionLoading.value = false
      }
    }

    const getStatusClass = (match) => {
      if (isFinished(match)) return 'status-finished'
      if (isLive(match)) return 'status-live'
      return 'status-upcoming'
    }

    const getStatusText = (match) => {
      if (isFinished(match)) return '已结束'
      if (match.status === 'Live') return '进行中'
      if (match.status === 'Today') return '今日'
      return '未开始'
    }

    const getTeamLogo = (name, id) => {
      return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=random&color=fff&size=64`
    }

    watch(currentDate, loadMatches)

    onMounted(loadMatches)

    return {
      loading, matches, selectedMatch, prediction, predictionLoading,
      currentDate, todayDate, activeFilter, filters, filteredMatches, groupedMatches,
      prevDay, nextDay, selectMatch, getStatusClass, getStatusText, getTeamLogo,
      isLive, isFinished, isUpcoming, hasScore, getFilterCount
    }
  }
}
</script>

<style scoped>
.match-preview {
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

/* 头部 */
.header-section {
  padding: 16px 20px;
}

.header-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.title-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 700;
  color: white;
}

.page-title svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.subtitle {
  font-size: 12px;
  color: #6b7280;
}

.date-nav {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #1c222f;
  border: 1px solid #374151;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.nav-btn:hover {
  background: #242936;
  color: white;
}

.current-date {
  font-size: 14px;
  color: #e5e7eb;
  font-weight: 500;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  padding-bottom: 16px;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  background: transparent;
  border: 1px solid rgba(31, 41, 55, 0.5);
  color: #9ca3af;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #e5e7eb;
}

.filter-btn.active {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
  color: #10b981;
}

.filter-count {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
}

.filter-btn.active .filter-count {
  background: rgba(16, 185, 129, 0.2);
}

/* 加载状态 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px;
  color: #6b7280;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #374151;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: #6b7280;
}

.empty-icon {
  width: 24px;
  height: 24px;
  opacity: 0.5;
}

/* 联赛分组 */
.leagues-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.league-section {
  overflow: hidden;
}

.league-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: #1c222f;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.league-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.league-logo {
  font-size: 18px;
}

.league-name {
  font-size: 15px;
  font-weight: 600;
  color: white;
}

.league-country {
  font-size: 12px;
  color: #6b7280;
  margin-left: 4px;
}

.match-count {
  font-size: 12px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 4px 10px;
  border-radius: 12px;
}

/* 横向滚动的比赛卡片 */
.matches-scroll {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #374151 transparent;
}

.matches-scroll::-webkit-scrollbar {
  height: 6px;
}

.matches-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.matches-scroll::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 3px;
}

.match-card {
  min-width: 240px;
  max-width: 280px;
  flex-shrink: 0;
  background: #1c222f;
  border-radius: 10px;
  padding: 14px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.match-card.status-live {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.05);
}

/* 状态行 */
.match-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  background: #f87171;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-live {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.status-finished {
  background: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
}

.status-upcoming {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.match-time {
  font-size: 12px;
  color: #6b7280;
}

/* 球队区域 */
.teams-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.team {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.team-logo {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.team-logo img {
  width: 32px;
  height: 32px;
  object-fit: contain;
}

.team-name {
  font-size: 12px;
  font-weight: 500;
  color: #e5e7eb;
  text-align: center;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.score-area {
  display: flex;
  align-items: center;
  gap: 4px;
}

.score {
  font-size: 18px;
  font-weight: 700;
  color: white;
}

.score-sep {
  color: #6b7280;
  font-size: 14px;
}

.vs {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

/* 查看详情按钮 */
.detail-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 6px;
  color: #10b981;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.detail-btn svg {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.detail-btn:hover {
  background: rgba(16, 185, 129, 0.2);
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: #151922;
  border-radius: 16px;
  width: 100%;
  max-width: 480px;
  padding: 24px;
  position: relative;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.modal-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  border: none;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.modal-league {
  font-size: 14px;
  color: #6b7280;
}

.modal-status {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
}

.modal-teams {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.modal-team {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.modal-team-logo {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.05);
  padding: 8px;
}

.modal-team-name {
  font-size: 16px;
  font-weight: 600;
  color: white;
  text-align: center;
}

.modal-score {
  display: flex;
  align-items: center;
  gap: 12px;
}

.modal-score-num {
  font-size: 32px;
  font-weight: 900;
  color: white;
}

.modal-score-divider {
  font-size: 24px;
  color: #6b7280;
}

.modal-vs-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.modal-vs {
  font-size: 18px;
  font-weight: 700;
  color: #6b7280;
}

.modal-time {
  font-size: 13px;
  color: #10b981;
  font-weight: 500;
}

.modal-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: #1c222f;
  border-radius: 10px;
  margin-bottom: 20px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #9ca3af;
}

.info-item svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.modal-prediction {
  padding: 16px;
  background: #1c222f;
  border-radius: 10px;
}

.modal-prediction h4 {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 16px;
}

.prediction-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.prediction-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bar-label {
  width: 40px;
  font-size: 13px;
  color: #9ca3af;
}

.bar-track {
  flex: 1;
  height: 8px;
  background: #374151;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.bar-fill.home { background: #10b981; }
.bar-fill.draw { background: #6b7280; }
.bar-fill.away { background: #3b82f6; }

.bar-value {
  width: 40px;
  font-size: 13px;
  font-weight: 600;
  color: white;
  text-align: right;
}

.loading-text {
  color: #6b7280;
  font-size: 13px;
}

@media (max-width: 600px) {
  .header-section {
    padding: 12px 16px;
  }

  .header-top {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .date-nav {
    justify-content: center;
  }

  .filter-bar {
    flex-wrap: wrap;
    gap: 6px;
  }

  .filter-btn {
    padding: 6px 10px;
    font-size: 12px;
  }

  .matches-scroll {
    padding: 12px 16px;
  }

  .match-card {
    min-width: 200px;
  }

  .modal-teams {
    flex-direction: column;
    gap: 16px;
  }

  .modal-score {
    order: -1;
  }
}
</style>
