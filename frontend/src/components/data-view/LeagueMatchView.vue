<template>
  <div class="league-match-view">
    <!-- 左侧：比赛列表 -->
    <div class="match-list-section">
      <div class="section-header">
        <h3>比赛列表</h3>
        <div class="header-controls">
          <select v-model="selectedRound" class="round-selector" v-if="availableRounds.length">
            <option value="all">全部轮次</option>
            <option v-for="r in availableRounds" :key="r" :value="r">第{{ r }}轮</option>
          </select>
          <span class="season-tag">{{ season }}</span>
        </div>
      </div>

      <!-- 特定轮次：平铺显示 -->
      <template v-if="selectedRound !== 'all' && roundMatches.length">
        <div class="round-info">
          <span class="round-label">第{{ selectedRound }}轮</span>
          <span class="round-stats">{{ roundFinished }}场已结束 / {{ roundUpcoming }}场未开始</span>
        </div>
        <div class="round-matches">
          <div class="match-row" v-for="match in roundMatches" :key="match.match_id">
            <span class="match-date">{{ formatDate(match.match_date) }}</span>
            <span class="match-time">{{ formatMatchTime(match) }}</span>
            <div class="match-teams">
              <span class="team home">{{ match.home_team_cn || match.home_team }}</span>
              <span class="score-box">
                <span class="score">{{ match.home_goals ?? '-' }}</span>
                <span class="divider">-</span>
                <span class="score">{{ match.away_goals ?? '-' }}</span>
              </span>
              <span class="team away">{{ match.away_team_cn || match.away_team }}</span>
            </div>
            <div class="match-odds" v-if="match.home_odds">
              <span class="odd">{{ formatOdds(match.home_odds) }}</span>
              <span class="odd">{{ formatOdds(match.draw_odds) }}</span>
              <span class="odd">{{ formatOdds(match.away_odds) }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 全部轮次：按轮次分组 -->
      <template v-else>
        <div class="match-groups" v-if="roundGroups.length">
          <div class="match-group" v-for="group in roundGroups" :key="group.round">
            <div class="group-header">
              <span class="group-round">第{{ group.round }}轮</span>
              <span class="group-stats">
                {{ group.finished }}场已结束 / {{ group.upcoming }}场未开始
              </span>
            </div>
            <div class="group-matches">
              <div class="match-row" v-for="match in group.matches" :key="match.match_id">
                <span class="match-date">{{ formatDate(match.match_date) }}</span>
                <span class="match-time">{{ formatMatchTime(match) }}</span>
                <div class="match-teams">
                  <span class="team home">{{ match.home_team_cn || match.home_team }}</span>
                  <span class="score-box">
                    <span class="score">{{ match.home_goals ?? '-' }}</span>
                    <span class="divider">-</span>
                    <span class="score">{{ match.away_goals ?? '-' }}</span>
                  </span>
                  <span class="team away">{{ match.away_team_cn || match.away_team }}</span>
                </div>
                <div class="match-odds" v-if="match.home_odds">
                  <span class="odd">{{ formatOdds(match.home_odds) }}</span>
                  <span class="odd">{{ formatOdds(match.draw_odds) }}</span>
                  <span class="odd">{{ formatOdds(match.away_odds) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="no-data">暂无比赛数据</div>
      </template>
    </div>

    <!-- 右侧：积分榜 -->
    <div class="standings-section">
      <div class="section-header">
        <h3>积分榜</h3>
      </div>
      <div class="standings-table" v-if="standings.length">
        <div class="table-header">
          <span class="col rank">#</span>
          <span class="col team">球队</span>
          <span class="col">赛</span>
          <span class="col">胜</span>
          <span class="col">平</span>
          <span class="col">负</span>
          <span class="col">进</span>
          <span class="col">失</span>
          <span class="col">净</span>
          <span class="col points">积分</span>
        </div>
        <div class="table-body">
          <div class="table-row" v-for="team in standings" :key="team.team_id"
               :class="getRowClass(team.rank)">
            <span class="col rank">{{ team.rank }}</span>
            <span class="col team">{{ team.team_name_cn || team.team_name }}</span>
            <span class="col">{{ team.matches }}</span>
            <span class="col win">{{ team.wins }}</span>
            <span class="col">{{ team.draws }}</span>
            <span class="col loss">{{ team.losses }}</span>
            <span class="col">{{ team.goals_for }}</span>
            <span class="col">{{ team.goals_against }}</span>
            <span class="col gd">{{ team.goal_diff > 0 ? '+' + team.goal_diff : team.goal_diff }}</span>
            <span class="col points">{{ team.points }}</span>
          </div>
        </div>
      </div>
      <div v-else class="no-data">暂无积分榜数据</div>

      <!-- 联赛介绍 -->
      <div class="league-info" v-if="leagueRules">
        <h4>联赛介绍</h4>
        <p class="league-name">{{ leagueRules.name }}</p>
        <p class="info-row">
          <span>{{ leagueRules.country }}</span>
          <span>·</span>
          <span>成立于{{ leagueRules.founded }}年</span>
        </p>
        <p class="info-row" v-if="leagueRules.teams">
          <span>{{ leagueRules.teams }}支球队</span>
          <span>·</span>
          <span>每队{{ leagueRules.matches_per_team }}场</span>
        </p>
        <p class="info-row" v-if="leagueRules.format_desc">
          <span>赛制: {{ leagueRules.format_desc }}</span>
        </p>
        <p class="info-row" v-if="leagueRules.relegation_spots">
          <span>降级: 后{{ leagueRules.relegation_spots }}名</span>
          <span v-if="leagueRules.champions_league_spots">·</span>
          <span v-if="leagueRules.champions_league_spots">欧冠: 前{{ leagueRules.champions_league_spots }}名</span>
        </p>
        <p class="info-row" v-if="leagueRules.var_enabled">
          <span>VAR: {{ leagueRules.var_enabled ? '启用' : '未启用' }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue'
import { leagueAPI } from '../../api'

export default {
  name: 'LeagueMatchView',
  props: {
    leagueId: { type: Number, required: true },
    season: { type: String, default: null },
    availableRounds: { type: Array, default: () => [] }
  },
  setup(props) {
    const roundGroups = ref([])
    const standings = ref([])
    const leagueRules = ref(null)
    const loading = ref(false)
    const selectedRound = ref('all')
    const roundMatches = ref([])
    const roundFinished = ref(0)
    const roundUpcoming = ref(0)
    const localRounds = ref([]) // 本地轮次列表

    const loadData = async () => {
      if (!props.leagueId) return
      loading.value = true
      try {
        // 如果父组件没有传递轮次列表，自己获取
        let roundsToUse = props.availableRounds
        if (!roundsToUse || roundsToUse.length === 0) {
          try {
            const roundsRes = await leagueAPI.getRounds(props.leagueId, props.season)
            if (roundsRes.data) {
              roundsToUse = roundsRes.data
              localRounds.value = roundsRes.data
            }
          } catch (e) {
            console.error('获取轮次列表失败:', e)
          }
        }

        // 如果选择了特定轮次，只获取该轮次
        if (selectedRound.value && selectedRound.value !== 'all') {
          const matchesRes = await leagueAPI.getMatchesByRound(props.leagueId, selectedRound.value, props.season)
          if (matchesRes.data) {
            roundMatches.value = matchesRes.data.sort((a, b) => {
              const timeA = a.beijing_time?.beijing_time || a.match_time || ''
              const timeB = b.beijing_time?.beijing_time || b.match_time || ''
              return timeA.localeCompare(timeB)
            })
            roundFinished.value = matchesRes.data.filter(m => m.home_goals !== null && m.away_goals !== null).length
            roundUpcoming.value = matchesRes.data.filter(m => m.home_goals === null || m.away_goals === null).length
          }
        } else if (roundsToUse.length) {
          // 按轮次获取所有比赛
          const groups = []
          for (const roundNum of roundsToUse) {
            try {
              const matchesRes = await leagueAPI.getMatchesByRound(props.leagueId, roundNum, props.season)
              if (matchesRes.data && matchesRes.data.length) {
                const matches = matchesRes.data.sort((a, b) => {
                  const timeA = a.beijing_time?.beijing_time || a.match_time || ''
                  const timeB = b.beijing_time?.beijing_time || b.match_time || ''
                  return timeA.localeCompare(timeB)
                })
                groups.push({
                  round: roundNum,
                  matches,
                  finished: matches.filter(m => m.home_goals !== null && m.away_goals !== null).length,
                  upcoming: matches.filter(m => m.home_goals === null || m.away_goals === null).length
                })
              }
            } catch (e) {
              console.error(`获取第${roundNum}轮数据失败:`, e)
            }
          }
          roundGroups.value = groups.sort((a, b) => b.round - a.round)
        }

        const [standingsRes, rulesRes] = await Promise.all([
          leagueAPI.getStandings(props.leagueId, props.season),
          leagueAPI.getLeagueRules(props.leagueId)
        ])

        if (standingsRes.data) standings.value = standingsRes.data
        if (rulesRes.data) leagueRules.value = rulesRes.data
      } catch (e) {
        console.error('加载联赛数据失败:', e)
      } finally {
        loading.value = false
      }
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return '-'
      const d = new Date(dateStr)
      return `${d.getMonth() + 1}/${d.getDate()}`
    }

    const formatMatchTime = (match) => {
      // 优先使用北京时间（beijing_time 可能是对象或字符串）
      let time = match.beijing_time
      if (time) {
        if (typeof time === 'object' && time.beijing_time) {
          time = time.beijing_time
        }
        if (typeof time === 'string') {
          const parts = time.split(':')
          if (parts.length >= 2) {
            return `${parts[0]}:${parts[1]}`
          }
        }
      }
      // 如果没有北京时间，使用当地时间
      time = match.match_time
      if (time && typeof time === 'string') {
        const parts = time.split(':')
        if (parts.length >= 2) {
          return `${parts[0]}:${parts[1]}`
        }
      }
      return '-'
    }

    const formatOdds = (odds) => {
      if (odds === null || odds === undefined) return '-'
      return Number(odds).toFixed(2)
    }

    const getRowClass = (rank) => {
      if (rank <= 4) return 'champions'
      if (rank <= 6) return 'europe'
      if (rank >= standings.value.length - 2) return 'relegation'
      return ''
    }

    // 监听轮次变化
    watch(selectedRound, loadData)

    watch(() => [props.leagueId, props.season], () => {
      selectedRound.value = 'all'
      loadData()
    })

    // 监听availableRounds变化，默认选择全部轮次
    watch(() => props.availableRounds, (newRounds) => {
      if (newRounds && newRounds.length && selectedRound.value !== 'all') {
        selectedRound.value = 'all'
      }
    })

    onMounted(loadData)

    return { roundGroups, standings, leagueRules, loading, selectedRound, formatDate, formatMatchTime, formatOdds, getRowClass, roundMatches, roundFinished, roundUpcoming }
  }
}
</script>

<style scoped>
.league-match-view {
  display: flex;
  gap: 24px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.match-list-section {
  flex: 1;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.standings-section {
  width: 380px;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.section-header {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.section-header h3 {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.round-selector {
  background: #1c222f;
  border: 1px solid #374151;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 11px;
  color: white;
  outline: none;
  cursor: pointer;
}

.round-selector:focus {
  border-color: #10b981;
}

.season-tag {
  font-size: 11px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.match-groups {
  padding: 8px;
}

.round-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 4px;
  margin: 8px;
}

.round-label {
  font-size: 13px;
  font-weight: 500;
  color: #10b981;
}

.round-stats {
  font-size: 11px;
  color: #6b7280;
}

.round-matches {
  padding: 8px;
}

.match-group {
  margin-bottom: 12px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 4px;
}

.group-round {
  font-size: 12px;
  font-weight: 500;
  color: #10b981;
}

.group-stats {
  font-size: 10px;
  color: #6b7280;
}

.group-matches {
  padding: 4px 0;
}

.match-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.match-row:hover {
  background: rgba(255, 255, 255, 0.03);
}

.match-date {
  width: 45px;
  font-size: 11px;
  color: #9ca3af;
  flex-shrink: 0;
}

.match-time {
  width: 45px;
  font-size: 11px;
  color: #6b7280;
  flex-shrink: 0;
}

.match-teams {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 0;
}

.team {
  font-size: 13px;
  color: #e5e7eb;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.team.home { text-align: right; }
.team.away { text-align: left; }

.score-box {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  flex-shrink: 0;
  min-width: 50px;
  justify-content: center;
}

.score {
  font-size: 13px;
  font-weight: 600;
  color: white;
  width: 16px;
  text-align: center;
}

.divider {
  color: #4b5563;
}

.match-odds {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.odd {
  font-size: 10px;
  color: #9ca3af;
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 2px;
  min-width: 36px;
  text-align: center;
}

.standings-table {
  padding: 8px;
  flex-shrink: 0;
}

.table-header, .table-row {
  display: flex;
  align-items: center;
  padding: 8px;
}

.table-header {
  font-size: 11px;
  color: #6b7280;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
}

.table-row {
  font-size: 12px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.2);
  position: relative;
}

.table-row.champions {
  background: rgba(16, 185, 129, 0.08);
  border-left: 3px solid #10b981;
}

.table-row.europe {
  background: rgba(59, 130, 246, 0.08);
  border-left: 3px solid #3b82f6;
}

.table-row.relegation {
  background: rgba(239, 68, 68, 0.08);
  border-left: 3px solid #ef4444;
}

.table-row.champions .col.rank { color: #10b981; }
.table-row.europe .col.rank { color: #3b82f6; }
.table-row.relegation .col.rank { color: #ef4444; }

.col {
  width: 32px;
  text-align: center;
  color: #9ca3af;
}

.col.rank { width: 24px; font-weight: 600; color: #d1d5db; }
.col.team { flex: 1; text-align: left; color: #e5e7eb; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col.win { color: #10b981; }
.col.loss { color: #ef4444; }
.col.gd { color: #6b7280; }
.col.points { font-weight: 600; color: white; }

.league-info {
  padding: 16px;
  border-top: 1px solid rgba(31, 41, 55, 0.5);
  flex-shrink: 0;
}

.league-info h4 {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 12px;
}

.league-name {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
  margin-bottom: 8px;
}

.info-row {
  font-size: 11px;
  color: #9ca3af;
  margin-bottom: 4px;
  display: flex;
  gap: 6px;
}

.no-data {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 12px;
  padding: 16px;
}

@media (max-width: 900px) {
  .league-match-view {
    flex-direction: column;
  }
  .standings-section {
    width: 100%;
  }
}
</style>
