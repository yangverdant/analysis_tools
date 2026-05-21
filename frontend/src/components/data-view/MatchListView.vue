<template>
  <div class="match-list-view">
    <!-- 轮次选择器 -->
    <div class="controls-bar">
      <select v-model="selectedRound" class="round-selector">
        <option value="all">全部轮次</option>
        <option v-for="r in rounds" :key="r" :value="r">第{{ r }}轮</option>
      </select>
      <div class="stats-info">
        <span class="stat">总计: {{ matches.length }} 场比赛</span>
        <span class="stat finished">已结束: {{ finishedCount }}</span>
        <span class="stat upcoming">未开始: {{ upcomingCount }}</span>
      </div>
    </div>

    <!-- 特定轮次：平铺显示 -->
    <template v-if="selectedRound !== 'all' && roundMatches.length">
      <div class="round-header">
        <span class="round-label">第{{ selectedRound }}轮</span>
      </div>
      <div class="matches-grid">
        <div class="match-card" v-for="match in roundMatches" :key="match.match_id">
          <div class="match-date-row">
            <span class="date">{{ formatDate(match.match_date) }}</span>
            <span class="time">{{ match.match_time || '--:--' }}</span>
          </div>
          <div class="match-teams-row">
            <span class="team home">{{ match.home_team_cn || match.home_team }}</span>
            <span class="score-box">
              <span class="score">{{ match.home_goals ?? '-' }}</span>
              <span class="sep">-</span>
              <span class="score">{{ match.away_goals ?? '-' }}</span>
            </span>
            <span class="team away">{{ match.away_team_cn || match.away_team }}</span>
          </div>
          <div class="match-odds-row" v-if="match.home_odds">
            <span class="odd-label">赔率</span>
            <span class="odd">{{ formatOdds(match.home_odds) }}</span>
            <span class="odd">{{ formatOdds(match.draw_odds) }}</span>
            <span class="odd">{{ formatOdds(match.away_odds) }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- 全部轮次：按轮次分组 -->
    <template v-else>
      <div class="round-groups" v-if="roundGroups.length">
        <div class="round-group" v-for="group in roundGroups" :key="group.round">
          <div class="group-header">
            <span class="group-round">第{{ group.round }}轮</span>
            <span class="group-stats">{{ group.finished }}场已结束 / {{ group.upcoming }}场未开始</span>
          </div>
          <div class="group-matches">
            <div class="match-row" v-for="match in group.matches" :key="match.match_id">
              <span class="match-date">{{ formatDate(match.match_date) }}</span>
              <span class="match-time">{{ match.match_time || '--:--' }}</span>
              <div class="match-teams">
                <span class="team home">{{ match.home_team_cn || match.home_team }}</span>
                <span class="score-box">
                  <span class="score">{{ match.home_goals ?? '-' }}</span>
                  <span class="sep">-</span>
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
      <div v-else class="no-data">
        <span class="no-data-icon">📭</span>
        <span class="no-data-text">暂无比赛数据</span>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'

export default {
  name: 'MatchListView',
  props: {
    leagueId: { type: Number, default: null },
    season: { type: String, default: null }
  },
  setup(props) {
    const matches = ref([])
    const rounds = ref([])
    const selectedRound = ref('all')
    const loading = ref(false)

    // 计算属性
    const finishedCount = computed(() => {
      return matches.value.filter(m => m.home_goals !== null).length
    })

    const upcomingCount = computed(() => {
      return matches.value.filter(m => m.home_goals === null).length
    })

    const roundMatches = computed(() => {
      if (selectedRound.value === 'all') return []
      return matches.value.filter(m => m.round == selectedRound.value)
    })

    const roundGroups = computed(() => {
      const groups = {}
      matches.value.forEach(m => {
        const r = m.round || 0
        if (!groups[r]) {
          groups[r] = { round: r, matches: [], finished: 0, upcoming: 0 }
        }
        groups[r].matches.push(m)
        if (m.home_goals !== null) {
          groups[r].finished++
        } else {
          groups[r].upcoming++
        }
      })
      return Object.values(groups).sort((a, b) => a.round - b.round)
    })

    // 方法
    const formatDate = (dateStr) => {
      if (!dateStr) return '--'
      const d = new Date(dateStr)
      return `${d.getMonth() + 1}/${d.getDate()}`
    }

    const formatOdds = (odds) => {
      if (!odds) return '-'
      return parseFloat(odds).toFixed(2)
    }

    const loadMatches = async () => {
      if (!props.leagueId || !props.season) return

      loading.value = true
      try {
        const res = await axios.get(`/api/v1/leagues/${props.leagueId}/matches`, {
          params: {
            season: props.season
          }
        })

        if (res.data && res.data.data) {
          matches.value = res.data.data

          // 提取轮次列表
          const roundSet = new Set()
          res.data.data.forEach(m => {
            if (m.round) roundSet.add(m.round)
          })
          rounds.value = Array.from(roundSet).sort((a, b) => a - b)
        }
      } catch (e) {
        console.error('加载比赛失败:', e)
        matches.value = []
      } finally {
        loading.value = false
      }
    }

    // 监听 props 变化 - 使用 immediate 确保初始化时也加载
    watch(() => [props.leagueId, props.season], () => {
      loadMatches()
    }, { immediate: true })

    return {
      matches,
      rounds,
      selectedRound,
      loading,
      finishedCount,
      upcomingCount,
      roundMatches,
      roundGroups,
      formatDate,
      formatOdds
    }
  }
}
</script>

<style scoped>
.match-list-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.controls-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: #151922;
  border-radius: 8px;
  border: 1px solid #1f2937;
}

.round-selector {
  padding: 8px 12px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 6px;
  color: white;
  font-size: 13px;
}

.stats-info {
  display: flex;
  gap: 12px;
}

.stat {
  font-size: 12px;
  color: #9ca3af;
}

.stat.finished {
  color: #10b981;
}

.stat.upcoming {
  color: #f59e0b;
}

.round-header {
  padding: 8px 16px;
  background: rgba(16, 185, 129, 0.1);
  border-radius: 6px;
}

.round-label {
  font-size: 14px;
  font-weight: 600;
  color: #10b981;
}

.matches-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.match-card {
  padding: 12px 16px;
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 8px;
}

.match-date-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.date {
  font-size: 12px;
  color: #6b7280;
}

.time {
  font-size: 12px;
  color: #9ca3af;
}

.match-teams-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.team {
  font-size: 13px;
  color: white;
  font-weight: 500;
}

.team.home {
  text-align: left;
}

.team.away {
  text-align: right;
}

.score-box {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #1a1f2e;
  border-radius: 4px;
}

.score {
  font-size: 14px;
  font-weight: 700;
  color: #10b981;
}

.sep {
  color: #6b7280;
}

.match-odds-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #1f2937;
}

.odd-label {
  font-size: 11px;
  color: #6b7280;
}

.odd {
  font-size: 12px;
  color: #f59e0b;
}

/* 按轮次分组样式 */
.round-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.round-group {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 8px;
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: rgba(16, 185, 129, 0.05);
  border-bottom: 1px solid #1f2937;
}

.group-round {
  font-size: 14px;
  font-weight: 600;
  color: #10b981;
}

.group-stats {
  font-size: 12px;
  color: #9ca3af;
}

.group-matches {
  padding: 8px;
}

.match-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  transition: background 0.2s;
}

.match-row:hover {
  background: rgba(255, 255, 255, 0.03);
}

.match-date {
  font-size: 12px;
  color: #6b7280;
  width: 40px;
}

.match-time {
  font-size: 12px;
  color: #9ca3af;
  width: 50px;
}

.match-teams {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.match-odds {
  display: flex;
  gap: 6px;
}

.no-data {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #6b7280;
}

.no-data-icon {
  font-size: 20px;
  margin-bottom: 8px;
}

.no-data-text {
  font-size: 12px;
}

@media (max-width: 600px) {
  .controls-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .matches-grid {
    grid-template-columns: 1fr;
  }

  .match-row {
    flex-wrap: wrap;
  }

  .match-teams {
    order: -1;
    width: 100%;
    justify-content: center;
  }
}
</style>