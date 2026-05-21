<template>
  <div class="league-view card">
    <!-- 筛选器 -->
    <div class="filters">
      <select v-model="selectedSeason" class="filter-select" @change="loadStandings">
        <option v-for="season in seasons" :key="season" :value="season">{{ season }}</option>
      </select>
      <select v-model="selectedLeague" class="filter-select" @change="loadStandings">
        <option v-for="league in leagues" :key="league.league_id" :value="league.league_id">
          {{ league.name_cn || league.name }}
        </option>
      </select>
    </div>

    <!-- 标签页 -->
    <div class="league-tabs">
      <button
        v-for="tab in leagueTabs"
        :key="tab"
        :class="['league-tab', { active: activeLeagueTab === tab }]"
        @click="activeLeagueTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>加载中...</span>
    </div>

    <!-- 调试信息 -->
    <div v-else-if="standings.length === 0" class="loading-state">
      <span>联赛ID: {{ selectedLeague }}, 赛季: {{ selectedSeason }}</span>
      <span>联赛数: {{ leagues.length }}, 赛季数: {{ seasons.length }}</span>
      <button @click="loadStandings" class="retry-btn">重新加载</button>
    </div>

    <!-- 内容区 -->
    <div v-else class="league-content">
      <!-- 左侧表格 -->
      <div class="table-section" v-if="activeLeagueTab === '积分榜'">
        <div class="table-header">积分榜</div>
        <div class="table-body">
          <table class="standings-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>球队</th>
                <th>场次</th>
                <th>胜</th>
                <th>平</th>
                <th>负</th>
                <th>进/失</th>
                <th>净胜球</th>
                <th class="points-col">积分</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="standings.length === 0">
                <td colspan="9" class="empty-cell">暂无数据</td>
              </tr>
              <tr v-for="(row, idx) in standings" :key="row.team_id" @click="goToTeam(row)">
                <td class="rank" :class="getRankClass(idx)">{{ row.rank || idx + 1 }}</td>
                <td class="team-cell">
                  <span class="team-name">{{ row.team_name_cn || row.team_name }}</span>
                </td>
                <td>{{ row.matches || 0 }}</td>
                <td class="win">{{ row.wins || 0 }}</td>
                <td>{{ row.draws || 0 }}</td>
                <td class="loss">{{ row.losses || 0 }}</td>
                <td class="goals">{{ row.goals_for || 0 }}/{{ row.goals_against || 0 }}</td>
                <td :class="(row.goal_diff || 0) > 0 ? 'positive' : (row.goal_diff || 0) < 0 ? 'negative' : ''">
                  {{ (row.goal_diff || 0) > 0 ? '+' : '' }}{{ row.goal_diff || 0 }}
                </td>
                <td class="points-cell">{{ row.points || 0 }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 其他榜单占位 -->
      <div class="table-section" v-else>
        <div class="table-header">{{ activeLeagueTab }}</div>
        <div class="table-body empty-body">
          <p class="empty-text">{{ activeLeagueTab }}数据开发中...</p>
        </div>
      </div>

      <!-- 右侧图表 -->
      <div class="charts-section">
        <div class="chart-card">
          <div class="chart-header">
            <h4 class="chart-title">进球数趋势</h4>
            <div class="chart-legend">
              <span class="legend-item blue">{{ topTeams[0]?.team_name_cn || '球队1' }}</span>
              <span class="legend-item red">{{ topTeams[1]?.team_name_cn || '球队2' }}</span>
              <span class="legend-item green">{{ topTeams[2]?.team_name_cn || '球队3' }}</span>
            </div>
          </div>
          <MultiLineChart
            :yMax="goalMax"
            :yLabels="goalLabels"
            :xLabels="roundLabels"
            :lines="goalLines"
          />
        </div>

        <div class="chart-card">
          <div class="chart-header">
            <h4 class="chart-title">场均得分趋势</h4>
            <div class="chart-legend">
              <span class="legend-item blue">{{ topTeams[0]?.team_name_cn || '球队1' }}</span>
              <span class="legend-item red">{{ topTeams[1]?.team_name_cn || '球队2' }}</span>
              <span class="legend-item green">{{ topTeams[2]?.team_name_cn || '球队3' }}</span>
            </div>
          </div>
          <MultiLineChart
            :yMax="scoreMax"
            :yLabels="scoreLabels"
            :xLabels="roundLabels"
            :lines="scoreLines"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { leagueAPI } from '../../api'
import MultiLineChart from './MultiLineChart.vue'

export default {
  name: 'LeagueDataView',
  components: { MultiLineChart },
  setup() {
    const router = useRouter()
    const selectedSeason = ref('')
    const selectedLeague = ref('')
    const activeLeagueTab = ref('积分榜')
    const loading = ref(false)
    const standings = ref([])
    const leagues = ref([])
    const seasons = ref([])

    const leagueTabs = ['积分榜', '射手榜', '助攻榜', '零封榜', '黄牌榜', '红牌榜']

    // 前三名球队
    const topTeams = computed(() => standings.value.slice(0, 3))

    // 图表数据 - 基于积分榜数据生成
    const goalMax = computed(() => {
      if (standings.value.length === 0) return 50
      const maxGoals = Math.max(...standings.value.map(t => t.goals_for || 0))
      return Math.ceil(maxGoals / 10) * 10 || 50
    })

    const goalLabels = computed(() => {
      const max = goalMax.value
      return [max, Math.round(max * 0.8), Math.round(max * 0.6), Math.round(max * 0.4), Math.round(max * 0.2)]
    })

    const scoreMax = 3
    const scoreLabels = [3, 2, 1]

    const roundLabels = ['1', '10', '20', '30', '38']

    // 进球趋势线 - 模拟累计进球
    const goalLines = computed(() => {
      const colors = ['#3b82f6', '#ef4444', '#10b981']
      return topTeams.value.map((team, idx) => {
        const totalGoals = team.goals_for || 50
        const matches = team.matches || 38
        const avgPerRound = totalGoals / matches
        return {
          color: colors[idx],
          data: [
            avgPerRound * 1,
            avgPerRound * 10,
            avgPerRound * 20,
            avgPerRound * 30,
            totalGoals
          ].map(v => Math.round(v))
        }
      })
    })

    // 场均得分趋势线
    const scoreLines = computed(() => {
      const colors = ['#3b82f6', '#ef4444', '#10b981']
      return topTeams.value.map((team, idx) => {
        const points = team.points || 60
        const matches = team.matches || 38
        const avgScore = points / matches
        // 模拟得分波动
        return {
          color: colors[idx],
          data: [
            avgScore * 0.9,
            avgScore * 0.95,
            avgScore,
            avgScore * 1.02,
            avgScore
          ].map(v => Math.min(3, Math.max(0, v)))
        }
      })
    })

    const loadLeagues = async () => {
      try {
        // 并行加载联赛和赛季
        const [leaguesRes, seasonsRes] = await Promise.all([
          leagueAPI.getLeagues(),
          leagueAPI.getAllSeasons()
        ])

        if (seasonsRes.data && seasonsRes.data.length) {
          seasons.value = seasonsRes.data
          selectedSeason.value = seasonsRes.data[0]
        }

        if (leaguesRes.data && leaguesRes.data.length) {
          leagues.value = leaguesRes.data
          // 默认选择英超
          const epl = leaguesRes.data.find(l => l.name === 'Premier League' || l.name_cn === '英超')
          selectedLeague.value = epl ? epl.league_id : leaguesRes.data[0].league_id
        }

        // 加载数据
        if (selectedLeague.value && selectedSeason.value) {
          await loadStandings()
        }
      } catch (e) {
        console.error('加载数据失败:', e)
      }
    }

    const loadStandings = async () => {
      if (!selectedLeague.value || !selectedSeason.value) return
      loading.value = true
      try {
        const res = await leagueAPI.getStandings(selectedLeague.value, selectedSeason.value)
        if (res.data) {
          standings.value = res.data
        }
      } catch (e) {
        console.error('加载积分榜失败:', e)
        standings.value = []
      } finally {
        loading.value = false
      }
    }

    const getRankClass = (idx) => {
      if (idx === 0) return 'champion'
      if (idx < 4) return 'cl'
      if (idx < 6) return 'el'
      return ''
    }

    const goToTeam = (row) => {
      if (row.team_id) {
        router.push({ name: 'Team', params: { id: row.team_id } })
      }
    }

    onMounted(() => {
      loadLeagues()
    })

    return {
      selectedSeason, selectedLeague, activeLeagueTab,
      seasons, leagueTabs, leagues, standings, loading,
      topTeams, goalMax, goalLabels, scoreMax, scoreLabels,
      roundLabels, goalLines, scoreLines,
      loadStandings, getRankClass, goToTeam
    }
  }
}
</script>

<style scoped>
.card {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.league-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  overflow: hidden;
  min-height: 0;
}

.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-select {
  background: #1c222f;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: white;
  outline: none;
  cursor: pointer;
}

.league-tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  margin-bottom: 16px;
  overflow-x: auto;
}

.league-tabs::-webkit-scrollbar {
  height: 0;
}

.league-tab {
  font-size: 14px;
  color: #9ca3af;
  background: transparent;
  border: none;
  padding: 0 0 10px 0;
  cursor: pointer;
  position: relative;
  white-space: nowrap;
  transition: color 0.2s;
}

.league-tab:hover {
  color: #e5e7eb;
}

.league-tab.active {
  color: #10b981;
  font-weight: 500;
}

.league-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: #10b981;
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #6b7280;
}

.retry-btn {
  background: #10b981;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 12px;
  cursor: pointer;
  margin-top: 8px;
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

.league-content {
  flex: 1;
  display: flex;
  gap: 24px;
  min-height: 0;
}

.table-section {
  flex: 3;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.table-header {
  padding: 16px;
  background: #151922;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.table-body {
  flex: 1;
  overflow-y: auto;
}

.empty-body {
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-cell {
  padding: 40px;
  text-align: center;
  color: #6b7280;
}

.empty-text {
  color: #6b7280;
  font-size: 14px;
}

.standings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.standings-table th {
  background: #0a0d14;
  padding: 12px 16px;
  text-align: left;
  font-size: 11px;
  font-weight: 400;
  color: #6b7280;
  position: sticky;
  top: 0;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.standings-table th:first-child {
  width: 60px;
  text-align: center;
}

.standings-table td:first-child {
  text-align: center;
}

.standings-table td {
  padding: 12px 16px;
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
  font-weight: 600;
  color: #e5e7eb;
  text-align: center;
  padding: 4px 8px;
}

.rank.champion {
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  color: #1a1a2e;
  border-radius: 6px;
}

.rank.cl {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
  border-radius: 6px;
}

.rank.el {
  background: rgba(249, 115, 22, 0.2);
  color: #f97316;
  border-radius: 6px;
}

.team-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.team-name {
  color: #e5e7eb;
  font-weight: 500;
}

.win { color: #10b981; }
.loss { color: #ef4444; }
.positive { color: #10b981; }
.negative { color: #ef4444; }
.goals { color: #6b7280; }

.points-col, .points-cell {
  color: white;
  font-weight: 600;
}

.charts-section {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
}

.chart-card {
  flex: 1;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  padding: 20px;
  display: flex;
  flex-direction: column;
  min-height: 220px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-title {
  font-size: 14px;
  font-weight: 500;
  color: #d1d5db;
}

.chart-legend {
  display: flex;
  gap: 12px;
  font-size: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #6b7280;
}

.legend-item::before {
  content: '';
  width: 8px;
  height: 2px;
  border-radius: 1px;
}

.legend-item.blue::before { background: #3b82f6; }
.legend-item.red::before { background: #ef4444; }
.legend-item.green::before { background: #10b981; }

/* 移动端 */
@media (max-width: 900px) {
  .league-content {
    flex-direction: column;
  }

  .charts-section {
    flex-direction: row;
  }
}

@media (max-width: 600px) {
  .league-view {
    padding: 12px 16px;
  }

  .league-tabs {
    gap: 16px;
  }

  .league-tab {
    font-size: 13px;
  }

  .standings-table th,
  .standings-table td {
    padding: 10px 12px;
    font-size: 11px;
  }

  .charts-section {
    flex-direction: column;
  }

  .chart-card {
    padding: 16px;
    min-height: 180px;
  }
}
</style>