<template>
  <div class="home-panel">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-content">
        <h1>欢迎回来，足球爱好者</h1>
        <p>今日有 {{ todayMatches.length }} 场比赛，{{ upcomingCount }} 场即将开始</p>
      </div>
      <div class="quick-actions">
        <button class="action-btn primary">
          <ActivityIcon />
          查看今日比赛
        </button>
        <button class="action-btn">
          <StarIcon />
          我的收藏
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon matches">
          <CalendarIcon />
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ todayMatches.length }}</span>
          <span class="stat-label">今日比赛</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon live">
          <RadioIcon />
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ liveMatches }}</span>
          <span class="stat-label">进行中</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon upcoming">
          <ClockIcon />
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ upcomingCount }}</span>
          <span class="stat-label">即将开始</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon favorites">
          <StarIcon />
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ favoritesCount }}</span>
          <span class="stat-label">收藏球队</span>
        </div>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-grid">
      <!-- 今日比赛 -->
      <div class="section today-matches">
        <div class="section-header">
          <h2><CalendarIcon /> 今日比赛</h2>
          <span class="badge">{{ todayMatches.length }} 场</span>
        </div>
        <div class="matches-list" v-if="todayMatches.length">
          <div class="match-card" v-for="match in todayMatches" :key="match.match_id" @click="goToMatch(match)">
            <div class="match-league">{{ match.league_cn || match.league }}</div>
            <div class="match-teams">
              <div class="team home">
                <span class="team-name">{{ match.home_team_cn || match.home_team }}</span>
              </div>
              <div class="score-box">
                <span class="score">{{ match.home_goals ?? '-' }}</span>
                <span class="vs">:</span>
                <span class="score">{{ match.away_goals ?? '-' }}</span>
              </div>
              <div class="team away">
                <span class="team-name">{{ match.away_team_cn || match.away_team }}</span>
              </div>
            </div>
            <div class="match-footer">
              <span class="match-time">{{ match.beijing_time || match.match_time || '待定' }}</span>
              <span class="match-status" :class="match.status">{{ getStatusText(match.status) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="no-data">
          <span class="icon">📭</span>
          <p>暂无今日比赛</p>
        </div>
      </div>

      <!-- 右侧栏 -->
      <div class="sidebar-right">
        <!-- 热门联赛 -->
        <div class="section leagues-section">
          <div class="section-header">
            <h2><TrophyIcon /> 热门联赛</h2>
          </div>
          <div class="leagues-list">
            <div class="league-item" v-for="league in popularLeagues" :key="league.league_id" @click="goToLeague(league.league_id)">
              <span class="league-icon">⚽</span>
              <div class="league-info">
                <span class="league-name">{{ league.name_cn || league.name }}</span>
                <span class="league-country">{{ league.country_cn || league.country }}</span>
              </div>
              <ChevronRightIcon class="arrow" />
            </div>
          </div>
        </div>

        <!-- FIFA排名 -->
        <div class="section ranking-section">
          <div class="section-header">
            <h2><GlobeIcon /> FIFA排名 TOP 5</h2>
          </div>
          <div class="ranking-list">
            <div class="ranking-item" v-for="(team, index) in fifaRankings.slice(0, 5)" :key="team.rank">
              <span class="rank" :class="'rank-' + (index + 1)">{{ team.rank }}</span>
              <span class="country">{{ team.country_cn || team.country }}</span>
              <span class="points">{{ team.points }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 即将开始的比赛 -->
    <div class="section upcoming-section">
      <div class="section-header">
        <h2><ClockIcon /> 即将开始</h2>
        <a href="#" class="view-all">查看全部 →</a>
      </div>
      <div class="upcoming-grid">
        <div class="upcoming-card" v-for="match in upcomingMatches.slice(0, 6)" :key="match.match_id">
          <div class="match-league">{{ match.league_cn || match.league }}</div>
          <div class="match-teams">
            <span class="team">{{ match.home_team_cn || match.home_team }}</span>
            <span class="vs">VS</span>
            <span class="team">{{ match.away_team_cn || match.away_team }}</span>
          </div>
          <div class="match-date">{{ formatDate(match.match_date) }}</div>
          <div class="match-odds" v-if="match.home_odds">
            <span class="odd">主{{ match.home_odds }}</span>
            <span class="odd">平{{ match.draw_odds }}</span>
            <span class="odd">客{{ match.away_odds }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, h, computed, defineComponent } from 'vue'
import { matchAPI, leagueAPI, rankingAPI } from '../api'

// 图标组件 - 使用 defineComponent 包装
const createIcon = (name, paths) => defineComponent({
  name,
  setup: () => () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, paths)
})

const CalendarIcon = createIcon('CalendarIcon', [
  h('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }),
  h('line', { x1: '16', y1: '2', x2: '16', y2: '6' }),
  h('line', { x1: '8', y1: '2', x2: '8', y2: '6' }),
  h('line', { x1: '3', y1: '10', x2: '21', y2: '10' })
])

const ActivityIcon = createIcon('ActivityIcon', [
  h('polyline', { points: '22 12 18 12 15 21 9 3 6 12 2 12' })
])

const StarIcon = createIcon('StarIcon', [
  h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' })
])

const RadioIcon = createIcon('RadioIcon', [
  h('circle', { cx: '12', cy: '12', r: '2' }),
  h('path', { d: 'M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14' })
])

const ClockIcon = createIcon('ClockIcon', [
  h('circle', { cx: '12', cy: '12', r: '10' }),
  h('polyline', { points: '12 6 12 12 16 14' })
])

const TrophyIcon = createIcon('TrophyIcon', [
  h('path', { d: 'M6 9H4.5a2.5 2.5 0 0 1 0-5H6' }),
  h('path', { d: 'M18 9h1.5a2.5 2.5 0 0 0 0-5H18' }),
  h('path', { d: 'M4 22h16' }),
  h('path', { d: 'M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22' }),
  h('path', { d: 'M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22' }),
  h('path', { d: 'M18 2H6v7a6 6 0 0 0 12 0V2Z' })
])

const GlobeIcon = createIcon('GlobeIcon', [
  h('circle', { cx: '12', cy: '12', r: '10' }),
  h('line', { x1: '2', y1: '12', x2: '22', y2: '12' }),
  h('path', { d: 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' })
])

const ChevronRightIcon = createIcon('ChevronRightIcon', [
  h('polyline', { points: '9 18 15 12 9 6' })
])

export default {
  name: 'HomePanel',
  components: { CalendarIcon, ActivityIcon, StarIcon, RadioIcon, ClockIcon, TrophyIcon, GlobeIcon, ChevronRightIcon },
  setup() {
    const todayMatches = ref([])
    const upcomingMatches = ref([])
    const popularLeagues = ref([])
    const fifaRankings = ref([])
    const loading = ref(false)

    // 计算属性
    const liveMatches = computed(() => {
      return todayMatches.value.filter(m => m.status === 'Live' || m.status === 'Today').length
    })

    const upcomingCount = computed(() => {
      return todayMatches.value.filter(m => m.status === 'Scheduled' || !m.status).length
    })

    const favoritesCount = ref(0)

    const getStatusText = (status) => {
      const statusMap = { 'Live': '进行中', 'Today': '今日', 'Finished': '已结束', 'Scheduled': '未开始' }
      return statusMap[status] || '未开始'
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`
    }

    const goToMatch = (match) => console.log('Go to match:', match)
    const goToLeague = (id) => console.log('Go to league:', id)

    const loadData = async () => {
      loading.value = true
      try {
        // 并行加载所有数据
        const [matchesRes, leaguesRes, rankingsRes] = await Promise.all([
          matchAPI.getToday(),
          leagueAPI.getLeagues(),
          rankingAPI.getFIFANational(5)
        ])

        // 今日比赛 - 按北京时间排序
        if (matchesRes.data) {
          todayMatches.value = matchesRes.data.sort((a, b) => {
            const timeA = a.beijing_time || a.match_time || ''
            const timeB = b.beijing_time || b.match_time || ''
            return timeA.localeCompare(timeB)
          })
          // 提取即将开始的比赛（未开始的取前6场）
          upcomingMatches.value = todayMatches.value
            .filter(m => m.status === 'Scheduled' || !m.status)
            .slice(0, 6)
        }

        // 热门联赛 - 只取前5个
        if (leaguesRes.data) {
          popularLeagues.value = leaguesRes.data.slice(0, 5)
        }

        // FIFA排名
        if (rankingsRes.data) {
          fifaRankings.value = rankingsRes.data.slice(0, 5)
        }
      } catch (e) {
        console.error('加载首页数据失败:', e)
      } finally {
        loading.value = false
      }
    }

    onMounted(loadData)

    return {
      todayMatches, upcomingMatches, popularLeagues, fifaRankings,
      liveMatches, upcomingCount, favoritesCount, loading,
      getStatusText, formatDate, goToMatch, goToLeague
    }
  }
}
</script>

<style scoped>
.home-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 欢迎区域 */
.welcome-section {
  background: linear-gradient(135deg, #1a2332 0%, #151922 100%);
  border-radius: 12px;
  padding: 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.welcome-content h1 {
  font-size: 24px;
  font-weight: 700;
  color: white;
  margin-bottom: 8px;
}

.welcome-content p {
  font-size: 14px;
  color: #9ca3af;
}

.quick-actions {
  display: flex;
  gap: 12px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid rgba(31, 41, 55, 0.5);
  background: rgba(255,255,255,0.05);
  color: #e5e7eb;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(255,255,255,0.1);
}

.action-btn.primary {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border: none;
  color: white;
}

.action-btn.primary:hover {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  background: #151922;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.matches { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.stat-icon.live { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.stat-icon.upcoming { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.stat-icon.favorites { background: rgba(16, 185, 129, 0.15); color: #10b981; }

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: white;
  display: block;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

/* 主内容网格 */
.main-grid {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
}

.section {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.section-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-header h2 {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-direction: row;
}

.section-header h2 svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.badge {
  font-size: 12px;
  color: #9ca3af;
  background: rgba(255,255,255,0.05);
  padding: 4px 10px;
  border-radius: 12px;
}

.view-all {
  font-size: 13px;
  color: #10b981;
  text-decoration: none;
}

/* 比赛列表 */
.matches-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.match-card {
  background: #1c222f;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.match-card:hover {
  background: #242936;
}

.match-league {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 12px;
}

.match-teams {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}

.match-teams .team {
  flex: 1;
  display: flex;
  align-items: center;
}

.match-teams .team.home {
  justify-content: flex-start;
}

.match-teams .team.away {
  justify-content: flex-end;
}

.team-name {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.score-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
}

.score {
  font-size: 18px;
  font-weight: 700;
  color: white;
}

.vs {
  color: #4b5563;
}

.match-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.match-time {
  font-size: 12px;
  color: #6b7280;
}

.match-status {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
}

.match-status.live { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.match-status.finished { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.match-status.upcoming { background: rgba(16, 185, 129, 0.15); color: #10b981; }

/* 右侧栏 */
.sidebar-right {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.leagues-list {
  padding: 8px 0;
}

.league-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.league-item:hover {
  background: rgba(255,255,255,0.02);
}

.league-icon {
  font-size: 16px;
}

.league-info {
  flex: 1;
}

.league-name {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.league-country {
  font-size: 12px;
  color: #6b7280;
}

.arrow {
  color: #4b5563;
  width: 14px;
  height: 14px;
}

/* 排名 */
.ranking-list {
  padding: 8px 0;
}

.ranking-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
}

.rank {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(255,255,255,0.05);
  color: #9ca3af;
}

.rank-1 { background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%); color: #1a1a2e; }
.rank-2 { background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%); color: #1a1a2e; }
.rank-3 { background: linear-gradient(135deg, #d97706 0%, #b45309 100%); color: #1a1a2e; }

.country {
  flex: 1;
  font-size: 14px;
  color: #e5e7eb;
}

.points {
  font-size: 12px;
  color: #6b7280;
  font-family: 'SF Mono', Monaco, monospace;
}

/* 即将开始 */
.upcoming-section {
  margin-top: 8px;
}

.upcoming-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 20px;
}

.upcoming-card {
  background: #1c222f;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.upcoming-card .match-league {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 10px;
}

.upcoming-card .match-teams {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.upcoming-card .team {
  font-size: 13px;
  font-weight: 500;
  color: #e5e7eb;
}

.upcoming-card .vs {
  font-size: 10px;
  color: #4b5563;
  padding: 2px 8px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
}

.upcoming-card .match-date {
  font-size: 12px;
  color: #6b7280;
  text-align: center;
  margin-bottom: 8px;
}

.upcoming-card .match-odds {
  display: flex;
  justify-content: center;
  gap: 6px;
}

.upcoming-card .odd {
  font-size: 10px;
  padding: 3px 6px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
  color: #9ca3af;
}

.no-data {
  text-align: center;
  padding: 24px;
  color: #6b7280;
}

.no-data .icon {
  font-size: 20px;
  display: block;
  margin-bottom: 8px;
}

.no-data p {
  font-size: 12px;
}
</style>