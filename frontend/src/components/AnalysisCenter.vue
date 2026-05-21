<template>
  <div class="analysis-center">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2><ActivityIcon /> 分析中心</h2>
        <p>比赛智能分析与预测 · 即将开始的比赛</p>
      </div>
    </div>

    <!-- 加载状态 -->
    <div class="loading-state" v-if="loading">
      <div class="spinner"></div>
      <p>正在分析比赛数据...</p>
    </div>

    <!-- 比赛分析列表 -->
    <div class="matches-analysis" v-else>
      <div
        class="match-analysis-card card"
        v-for="match in matchAnalysisList"
        :key="match.match_id"
        @click="goToMatchDetail(match.match_id)"
      >
        <!-- 比赛头部 -->
        <div class="match-header">
          <span class="league-tag">{{ match.league_cn || match.league }}</span>
          <span class="match-time">{{ match.match_date }} {{ match.beijing_time || match.match_time || '时间待定' }}</span>
          <span class="countdown-badge">{{ getCountdown(match.match_date, match.beijing_time || match.match_time) }}</span>
        </div>

        <!-- 球队对比 -->
        <div class="teams-row">
          <div class="team-side">
            <span class="team-name">{{ match.home_team_cn || match.home_team }}</span>
            <span class="elo-badge home">Elo {{ match.home_elo || '--' }}</span>
          </div>
          <div class="vs-box">
            <span class="vs-text">VS</span>
          </div>
          <div class="team-side away">
            <span class="team-name">{{ match.away_team_cn || match.away_team }}</span>
            <span class="elo-badge away">Elo {{ match.away_elo || '--' }}</span>
          </div>
        </div>

        <!-- 预测条 -->
        <div class="prediction-bar" v-if="match.prediction">
          <div class="pred-segment home" :style="{ width: match.prediction.home_win + '%' }">
            <span v-if="match.prediction.home_win > 15">{{ match.prediction.home_win }}%</span>
          </div>
          <div class="pred-segment draw" :style="{ width: match.prediction.draw + '%' }">
            <span v-if="match.prediction.draw > 15">{{ match.prediction.draw }}%</span>
          </div>
          <div class="pred-segment away" :style="{ width: match.prediction.away_win + '%' }">
            <span v-if="match.prediction.away_win > 15">{{ match.prediction.away_win }}%</span>
          </div>
        </div>

        <!-- 分析摘要 -->
        <div class="analysis-summary">
          <p>{{ match.summary || '分析中...' }}</p>
        </div>

        <!-- H2H简要 -->
        <div class="h2h-mini" v-if="match.h2h && match.h2h.total > 0">
          <span class="h2h-label">历史交锋:</span>
          <span class="h2h-record">
            <span class="win">{{ match.h2h.home_wins }}胜</span>
            <span class="draw">{{ match.h2h.draws }}平</span>
            <span class="loss">{{ match.h2h.away_wins }}负</span>
          </span>
        </div>

        <!-- 查看详情按钮 -->
        <div class="card-footer">
          <button class="detail-btn">
            查看详细分析
            <ChevronRightIcon />
          </button>
        </div>
      </div>

      <!-- 无数据 -->
      <div class="no-matches" v-if="!loading && matchAnalysisList.length === 0">
        <InboxIcon />
        <p>暂无该日期的比赛数据</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, h, defineComponent } from 'vue'
import { useRouter } from 'vue-router'
import { matchAPI } from '../api'

// 图标组件
const ActivityIcon = defineComponent({
  name: 'ActivityIcon',
  setup() {
    return () => h('svg', { class: 'w-4 h-4', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '22 12 18 12 15 21 9 3 6 12 2 12' })
    ])
  }
})

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
    return () => h('svg', { class: 'w-3 h-3', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '15 18 9 12 15 6' })
    ])
  }
})

const ChevronRightIcon = defineComponent({
  name: 'ChevronRightIcon',
  setup() {
    return () => h('svg', { class: 'w-3 h-3', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '9 18 15 12 9 6' })
    ])
  }
})

const InboxIcon = defineComponent({
  name: 'InboxIcon',
  setup() {
    return () => h('svg', { class: 'w-5 h-5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5' }, [
      h('polyline', { points: '22 12 16 12 14 15 10 15 8 12 2 12' }),
      h('path', { d: 'M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z' })
    ])
  }
})

export default {
  name: 'AnalysisCenter',
  components: { ActivityIcon, CalendarIcon, ChevronLeftIcon, ChevronRightIcon, InboxIcon },
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const matchAnalysisList = ref([])

    // 计算比赛倒计时
    const getCountdown = (matchDate, matchTime) => {
      if (!matchDate) return ''

      // 构造比赛时间
      const timeStr = matchTime || '00:00'
      const matchDateTime = new Date(`${matchDate}T${timeStr}`)
      const now = new Date()

      const diffMs = matchDateTime - now
      if (diffMs <= 0) return '已开始'

      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
      const diffHours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
      const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60))

      if (diffDays > 0) {
        return `${diffDays}天后`
      } else if (diffHours > 0) {
        return `${diffHours}小时后`
      } else {
        return `${diffMinutes}分钟后`
      }
    }

    const loadAnalysis = async () => {
      loading.value = true
      try {
        // 获取即将开始的比赛（未开始的比赛）
        const matchesRes = await matchAPI.getUpcoming(30)  // 获取30天内即将开始的比赛
        if (matchesRes.data) {
          const matches = matchesRes.data

          // 并行获取每场比赛的分析摘要
          const analysisPromises = matches.map(async (match) => {
            try {
              const analysisRes = await matchAPI.getAnalysisSummary(match.match_id)
              if (analysisRes.data) {
                return {
                  ...match,
                  ...analysisRes.data
                }
              }
              return match
            } catch (e) {
              console.error(`获取比赛${match.match_id}分析失败:`, e)
              return match
            }
          })

          matchAnalysisList.value = await Promise.all(analysisPromises)

          // 按比赛日期和时间排序
          matchAnalysisList.value.sort((a, b) => {
            const dateA = a.match_date || ''
            const dateB = b.match_date || ''
            if (dateA !== dateB) return dateA.localeCompare(dateB)
            const timeA = a.beijing_time || a.match_time || ''
            const timeB = b.beijing_time || b.match_time || ''
            return timeA.localeCompare(timeB)
          })
        }
      } catch (e) {
        console.error('加载分析数据失败:', e)
      } finally {
        loading.value = false
      }
    }

    const goToMatchDetail = (matchId) => {
      router.push(`/match/${matchId}`)
    }

    onMounted(loadAnalysis)

    return {
      loading,
      matchAnalysisList,
      goToMatchDetail,
      getCountdown
    }
  }
}
</script>

<style scoped>
.analysis-center {
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
.header {
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  white-space: nowrap;
}

.header-content h2 svg {
  width: 18px;
  height: 18px;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

.date-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 6px 12px;
  border-radius: 6px;
}

.date-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 6px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-btn:hover {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
  color: #10b981;
}

.nav-btn svg {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.current-date {
  font-size: 13px;
  font-weight: 500;
  color: #e5e7eb;
  min-width: 90px;
  text-align: center;
}

/* 加载状态 */
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

/* 比赛分析卡片 */
.matches-analysis {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  padding: 0 4px;
}

.match-analysis-card {
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.match-analysis-card:hover {
  border-color: rgba(16, 185, 129, 0.3);
  background: #1a1f2e;
}

.match-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.league-tag {
  font-size: 11px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 3px 8px;
  border-radius: 4px;
}

.match-time {
  font-size: 12px;
  color: #6b7280;
}

.countdown-badge {
  font-size: 11px;
  font-weight: 600;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  padding: 3px 8px;
  border-radius: 4px;
  margin-left: auto;
}

/* 球队对比 */
.teams-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.team-side {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.team-side.away {
  align-items: flex-end;
}

.team-name {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
}

.elo-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  width: fit-content;
}

.elo-badge.home {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.elo-badge.away {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.vs-box {
  padding: 0 16px;
}

.vs-text {
  font-size: 12px;
  color: #4b5563;
  font-weight: 600;
}

/* 预测条 */
.prediction-bar {
  display: flex;
  height: 24px;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 12px;
}

.pred-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: white;
  transition: width 0.3s;
}

.pred-segment.home {
  background: linear-gradient(90deg, #10b981, #059669);
}

.pred-segment.draw {
  background: #4b5563;
}

.pred-segment.away {
  background: linear-gradient(90deg, #3b82f6, #2563eb);
}

/* 分析摘要 */
.analysis-summary {
  padding: 10px 12px;
  background: #1c222f;
  border-radius: 6px;
  margin-bottom: 10px;
}

.analysis-summary p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.5;
}

/* H2H简要 */
.h2h-mini {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 12px;
}

.h2h-label {
  color: #6b7280;
}

.h2h-record {
  display: flex;
  gap: 6px;
}

.h2h-record .win { color: #10b981; }
.h2h-record .draw { color: #9ca3af; }
.h2h-record .loss { color: #60a5fa; }

/* 卡片底部 */
.card-footer {
  border-top: 1px solid rgba(31, 41, 55, 0.5);
  padding-top: 12px;
  margin-top: 4px;
}

.detail-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 6px;
  color: #10b981;
  font-size: 13px;
  font-weight: 500;
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

/* 无数据 */
.no-matches {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: #6b7280;
}

.no-matches svg {
  width: 16px;
  height: 16px;
}

.no-matches p {
  margin-top: 8px;
  font-size: 12px;
}

/* 响应式 */
@media (max-width: 600px) {
  .header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .team-name {
    font-size: 14px;
  }

  .vs-box {
    padding: 0 10px;
  }
}
</style>
