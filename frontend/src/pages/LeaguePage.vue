<template>
  <div class="league-page">
    <!-- 联赛信息头部 -->
    <section class="league-header">
      <div class="league-info">
        <h1>{{ league?.name_cn || league?.name || '加载中...' }}</h1>
        <p>{{ league?.country_cn || league?.country }} | {{ league?.tier ? `第${league.tier}级别` : '杯赛' }}</p>
      </div>
      <!-- 赛季选择器 -->
      <div class="season-selector">
        <select v-model="selectedSeason" @change="loadData">
          <option v-for="s in seasons" :key="s" :value="s">{{ formatSeason(s) }}</option>
        </select>
      </div>
    </section>

    <!-- 主内容区域：左侧比赛 + 右侧积分榜 -->
    <section class="main-content">
      <!-- 左侧：最新一轮比赛 -->
      <div class="matches-panel card">
        <div class="panel-header">
          <h2>
            <span class="icon">📅</span>
            {{ currentRound ? `第 ${currentRound} 轮` : '最新比赛' }}
          </h2>
          <span class="match-count">{{ roundMatches.length }} 场</span>
        </div>
        <div class="matches-list" v-if="roundMatches.length">
          <div class="match-row" v-for="match in roundMatches" :key="match.match_id">
            <div class="match-time-info">
              <span class="beijing-time">{{ match.beijing_time || match.match_time || '' }}</span>
              <span class="time-label" v-if="match.beijing_time">北京时间</span>
            </div>
            <div class="match-content">
              <span class="team home">{{ match.home_team_cn || match.home_team }}</span>
              <span class="score" :class="getScoreClass(match)">
                <span class="home-score">{{ match.home_goals ?? '-' }}</span>
                <span class="separator">-</span>
                <span class="away-score">{{ match.away_goals ?? '-' }}</span>
              </span>
              <span class="team away">{{ match.away_team_cn || match.away_team }}</span>
            </div>
            <div class="match-odds" v-if="match.home_odds">
              <span class="odd" :class="{ 'hit': isHomeWin(match) }">{{ match.home_odds }}</span>
              <span class="odd" :class="{ 'hit': isDraw(match) }">{{ match.draw_odds }}</span>
              <span class="odd" :class="{ 'hit': isAwayWin(match) }">{{ match.away_odds }}</span>
            </div>
          </div>
        </div>
        <div v-else class="no-data">
          <span class="icon">📭</span>
          <p>暂无比赛数据</p>
        </div>
      </div>

      <!-- 右侧：积分榜 -->
      <div class="standings-panel card">
        <div class="panel-header">
          <h2>
            <span class="icon">🏆</span>
            积分榜
          </h2>
          <span class="team-count">{{ standings.length }} 队</span>
        </div>
        <div class="standings-wrapper">
          <table class="standings-table">
            <thead>
              <tr>
                <th class="rank-col">#</th>
                <th class="team-col">球队</th>
                <th>场</th>
                <th>胜</th>
                <th>平</th>
                <th>负</th>
                <th>进</th>
                <th>失</th>
                <th>净</th>
                <th class="points-col">积分</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="team in standings" :key="team.team_id" @click="goToTeam(team.team_id)">
                <td class="rank">
                  <span class="rank-badge" :class="getRankClass(team.rank)">{{ team.rank }}</span>
                </td>
                <td class="team-name">{{ team.team_name_cn || team.team_name }}</td>
                <td>{{ team.matches }}</td>
                <td class="win">{{ team.wins }}</td>
                <td>{{ team.draws }}</td>
                <td class="loss">{{ team.losses }}</td>
                <td>{{ team.goals_for }}</td>
                <td>{{ team.goals_against }}</td>
                <td :class="team.goal_diff > 0 ? 'positive' : team.goal_diff < 0 ? 'negative' : ''">
                  {{ team.goal_diff > 0 ? '+' : '' }}{{ team.goal_diff }}
                </td>
                <td class="points">{{ team.points }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { leagueAPI } from '../api'

export default {
  name: 'LeaguePage',
  setup() {
    const route = useRoute()
    const router = useRouter()

    const league = ref(null)
    const seasons = ref([])
    const selectedSeason = ref(null)
    const standings = ref([])
    const roundMatches = ref([])
    const currentRound = ref(null)

    const formatSeason = (s) => {
      const year = parseInt(s)
      if (isNaN(year)) return s
      return `${year}-${(year + 1).toString().slice(-2)}赛季`
    }

    const formatMatchDate = (dateStr) => {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      const month = date.getMonth() + 1
      const day = date.getDate()
      const hours = date.getHours().toString().padStart(2, '0')
      const minutes = date.getMinutes().toString().padStart(2, '0')
      return `${month}/${day} ${hours}:${minutes}`
    }

    const isHomeWin = (match) => match.home_goals > match.away_goals
    const isDraw = (match) => match.home_goals === match.away_goals
    const isAwayWin = (match) => match.away_goals > match.home_goals

    const getScoreClass = (match) => {
      if (match.home_goals === null || match.away_goals === null) return ''
      if (isHomeWin(match)) return 'home-win'
      if (isAwayWin(match)) return 'away-win'
      return 'draw'
    }

    const getRankClass = (rank) => {
      if (rank <= 4) return 'champions'
      if (rank <= 6) return 'europa'
      if (rank >= 18) return 'relegation'
      return ''
    }

    const loadData = async () => {
      const leagueId = route.params.id

      try {
        // 1. 加载联赛信息
        const leagueData = await leagueAPI.getLeague(leagueId)
        if (leagueData.data) league.value = leagueData.data

        // 2. 加载赛季列表
        const seasonsData = await leagueAPI.getSeasons(leagueId)
        if (seasonsData.data && seasonsData.data.length) {
          seasons.value = seasonsData.data
          if (!selectedSeason.value) {
            selectedSeason.value = seasonsData.data[0]
          }
        }

        // 3. 确保season有值后再加载数据
        const season = selectedSeason.value || seasons.value[0]
        console.log('加载数据, leagueId:', leagueId, 'season:', season)

        // 4. 加载积分榜
        const standingsData = await leagueAPI.getStandings(leagueId, season)
        console.log('积分榜数据:', standingsData)
        if (standingsData.data) {
          standings.value = standingsData.data
          console.log('积分榜球队数:', standings.value.length)
        }

        // 5. 加载最新一轮比赛
        const roundData = await leagueAPI.getLatestRound(leagueId, season)
        console.log('比赛数据:', roundData)
        if (roundData.data) {
          roundMatches.value = roundData.data.matches || roundData.data
          currentRound.value = roundData.data.round || null
          console.log('比赛数量:', roundMatches.value.length)
        }

      } catch (error) {
        console.error('加载数据失败:', error)
      }
    }

    const goToTeam = (teamId) => {
      router.push({ name: 'Team', params: { id: teamId } })
    }

    onMounted(loadData)

    return {
      league,
      seasons,
      selectedSeason,
      standings,
      roundMatches,
      currentRound,
      formatSeason,
      formatMatchDate,
      isHomeWin,
      isDraw,
      isAwayWin,
      getScoreClass,
      getRankClass,
      loadData,
      goToTeam
    }
  }
}
</script>

<style scoped>
.league-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 头部样式 */
.league-header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white;
  border-radius: 12px;
  padding: 24px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.league-header h1 {
  font-size: 26px;
  margin-bottom: 6px;
  font-weight: 700;
}

.league-header p {
  opacity: 0.7;
  font-size: 14px;
  color: #9ca3af;
}

.season-selector select {
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid #374151;
  background: #1c222f;
  color: white;
  font-size: 14px;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s;
}

.season-selector select:hover {
  border-color: #10b981;
}

.season-selector select:focus {
  border-color: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
}

/* 主内容区域 */
.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

/* 卡片样式 */
.card {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  overflow: hidden;
}

.panel-header {
  background: #1c222f;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-header h2 {
  font-size: 15px;
  font-weight: 600;
  color: #f3f4f6;
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-header h2 .icon {
  font-size: 16px;
}

.match-count, .team-count {
  font-size: 12px;
  color: #6b7280;
  background: rgba(255,255,255,0.05);
  padding: 4px 10px;
  border-radius: 12px;
}

/* 比赛列表 */
.matches-list {
  max-height: 520px;
  overflow-y: auto;
}

.match-row {
  display: flex;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
  gap: 16px;
  transition: background 0.2s;
}

.match-row:hover {
  background: rgba(255, 255, 255, 0.02);
}

.match-row:last-child {
  border-bottom: none;
}

.match-date {
  font-size: 12px;
  color: #6b7280;
  min-width: 65px;
  font-family: 'SF Mono', Monaco, monospace;
}

.match-time-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 70px;
}

.beijing-time {
  font-size: 13px;
  font-weight: 600;
  color: #10b981;
  font-family: 'SF Mono', Monaco, monospace;
}

.time-label {
  font-size: 10px;
  color: #6b7280;
}

.match-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.team {
  font-weight: 500;
  font-size: 14px;
  color: #e5e7eb;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.team.home {
  text-align: right;
  flex: 1;
}

.team.away {
  text-align: left;
  flex: 1;
}

.score {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  font-size: 16px;
  min-width: 55px;
  justify-content: center;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(255,255,255,0.03);
}

.score.home-win {
  background: rgba(16, 185, 129, 0.1);
}

.score.home-win .home-score {
  color: #10b981;
}

.score.away-win {
  background: rgba(59, 130, 246, 0.1);
}

.score.away-win .away-score {
  color: #3b82f6;
}

.score.draw {
  background: rgba(107, 114, 128, 0.1);
}

.separator {
  color: #4b5563;
}

.match-odds {
  display: flex;
  gap: 6px;
}

.odd {
  font-size: 11px;
  padding: 3px 8px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
  color: #6b7280;
  font-family: 'SF Mono', Monaco, monospace;
}

.odd.hit {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  font-weight: 600;
}

/* 积分榜 */
.standings-wrapper {
  max-height: 520px;
  overflow-y: auto;
}

.standings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.standings-table th {
  background: #1c222f;
  padding: 12px 8px;
  text-align: center;
  font-size: 11px;
  color: #6b7280;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  position: sticky;
  top: 0;
}

.standings-table th.rank-col,
.standings-table th.team-col {
  text-align: left;
  padding-left: 20px;
}

.standings-table th.points-col {
  text-align: center;
  padding-right: 20px;
}

.standings-table td {
  padding: 12px 8px;
  text-align: center;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
  color: #9ca3af;
}

.standings-table tr:hover {
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
}

.standings-table tr:hover td {
  color: #e5e7eb;
}

.rank {
  padding-left: 20px;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 12px;
  background: rgba(255,255,255,0.05);
  color: #9ca3af;
}

.rank-badge.champions {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.rank-badge.europa {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.rank-badge.relegation {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.team-name {
  text-align: left;
  font-weight: 500;
  color: #e5e7eb;
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.win {
  color: #10b981 !important;
}

.loss {
  color: #ef4444 !important;
}

.positive {
  color: #10b981 !important;
}

.negative {
  color: #ef4444 !important;
}

.points {
  font-weight: 700;
  color: #f3f4f6 !important;
  background: rgba(255,255,255,0.02);
  padding-right: 20px !important;
}

.no-data {
  text-align: center;
  padding: 60px 20px;
  color: #6b7280;
}

.no-data .icon {
  font-size: 48px;
  display: block;
  margin-bottom: 16px;
  opacity: 0.5;
}

.no-data p {
  font-size: 14px;
}

/* 响应式 */
@media (max-width: 1024px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .league-header {
    flex-direction: column;
    gap: 16px;
    text-align: center;
  }
}
</style>
