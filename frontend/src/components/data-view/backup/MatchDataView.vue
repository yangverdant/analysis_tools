<template>
  <div class="match-view card">
    <!-- 筛选器 -->
    <div class="filters">
      <select v-model="selectedLeague" class="filter-select" @change="loadMatches">
        <option v-for="league in leagues" :key="league.league_id" :value="league.league_id">
          {{ league.name_cn || league.name }}
        </option>
      </select>
      <select v-model="selectedSeason" class="filter-select" @change="loadMatches">
        <option v-for="season in seasons" :key="season" :value="season">{{ season }}</option>
      </select>
    </div>

    <!-- 标签页 -->
    <div class="match-tabs">
      <button
        v-for="tab in matchTabs"
        :key="tab"
        :class="['match-tab', { active: activeMatchTab === tab }]"
        @click="activeMatchTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>加载中...</span>
    </div>

    <!-- 内容区 -->
    <div v-else class="match-content">
      <!-- 比赛列表 -->
      <div class="match-list">
        <div class="list-header">比赛列表</div>
        <div class="list-body">
          <div v-if="matches.length === 0" class="empty-state">
            <p>暂无比赛数据</p>
          </div>
          <div
            v-for="match in matches"
            :key="match.match_id"
            :class="['match-item', { selected: selectedMatch?.match_id === match.match_id }]"
            @click="selectMatch(match)"
          >
            <div class="match-date">{{ formatDate(match.match_date) }}</div>
            <div class="match-teams">
              <span class="team-name home">{{ match.home_team_cn || match.home_team }}</span>
              <span class="match-score">
                <span :class="getScoreClass(match, 'home')">{{ match.home_goals ?? '-' }}</span>
                <span class="divider">-</span>
                <span :class="getScoreClass(match, 'away')">{{ match.away_goals ?? '-' }}</span>
              </span>
              <span class="team-name away">{{ match.away_team_cn || match.away_team }}</span>
            </div>
            <div class="match-time">{{ match.beijing_time || match.match_time || '' }}</div>
          </div>
        </div>
      </div>

      <!-- 比赛详情 -->
      <div class="match-detail" v-if="selectedMatch">
        <!-- 比分板 -->
        <div class="scoreboard">
          <div class="match-league">{{ getLeagueName(selectedLeague) }}</div>
          <div class="teams-score">
            <div class="team-side">
              <span class="team-name">{{ selectedMatch.home_team_cn || selectedMatch.home_team }}</span>
            </div>
            <div class="score-display">
              {{ selectedMatch.home_goals ?? 0 }} - {{ selectedMatch.away_goals ?? 0 }}
            </div>
            <div class="team-side">
              <span class="team-name">{{ selectedMatch.away_team_cn || selectedMatch.away_team }}</span>
            </div>
          </div>
          <div class="match-info">
            <p>{{ selectedMatch.match_date }} {{ selectedMatch.beijing_time || selectedMatch.match_time }}</p>
          </div>
        </div>

        <!-- 数据对比 -->
        <div class="stats-compare">
          <h4 class="compare-title">比赛信息</h4>
          <div class="compare-info">
            <div class="info-row">
              <span class="info-label">比赛ID</span>
              <span class="info-value">{{ selectedMatch.match_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">主队</span>
              <span class="info-value">{{ selectedMatch.home_team_cn || selectedMatch.home_team }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">客队</span>
              <span class="info-value">{{ selectedMatch.away_team_cn || selectedMatch.away_team }}</span>
            </div>
            <div class="info-row" v-if="selectedMatch.home_odds">
              <span class="info-label">赔率(主/平/客)</span>
              <span class="info-value">{{ selectedMatch.home_odds }} / {{ selectedMatch.draw_odds }} / {{ selectedMatch.away_odds }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 未选择比赛时的提示 -->
      <div class="match-detail empty-detail" v-else>
        <p class="empty-text">请从左侧选择一场比赛查看详情</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { leagueAPI } from '../../api'

export default {
  name: 'MatchDataView',
  setup() {
    const selectedLeague = ref('')
    const selectedSeason = ref('2025-2026')
    const selectedMatch = ref(null)
    const activeMatchTab = ref('比赛概况')
    const loading = ref(false)
    const matches = ref([])
    const leagues = ref([])

    const seasons = ['2025-2026', '2024-2025', '2023-2024', '2022-2023', '2021-2022', '2020-2021', '2019-2020', '2018-2019', '2017-2018', '2016-2017', '2015-2016', '2014-2015', '2013-2014', '2012-2013', '2011-2012', '2010-2011', '2009-2010', '2008-2009', '2007-2008', '2006-2007', '2005-2006', '2004-2005', '2003-2004', '2002-2003', '2001-2002', '2000-2001']
    const matchTabs = ['比赛概况', '球队数据对比', '球员数据', '事件时间线']

    const loadLeagues = async () => {
      try {
        const res = await leagueAPI.getLeagues()
        if (res.data) {
          leagues.value = res.data
          if (res.data.length && !selectedLeague.value) {
            const epl = res.data.find(l => l.name === 'Premier League' || l.name_cn === '英超')
            selectedLeague.value = epl ? epl.league_id : res.data[0].league_id
            await loadMatches()
          }
        }
      } catch (e) {
        console.error('加载联赛失败:', e)
      }
    }

    const loadMatches = async () => {
      if (!selectedLeague.value) return
      loading.value = true
      try {
        const res = await leagueAPI.getMatches(selectedLeague.value, 100, selectedSeason.value)
        if (res.data) {
          matches.value = res.data
          if (res.data.length) {
            selectedMatch.value = res.data[0]
          }
        }
      } catch (e) {
        console.error('加载比赛失败:', e)
        matches.value = []
      } finally {
        loading.value = false
      }
    }

    const selectMatch = (match) => {
      selectedMatch.value = match
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return '-'
      const d = new Date(dateStr)
      return `${d.getMonth() + 1}/${d.getDate()}`
    }

    const getScoreClass = (match, side) => {
      if (match.home_goals === null || match.away_goals === null) return ''
      if (match.home_goals === match.away_goals) return 'draw'
      if (side === 'home') return match.home_goals > match.away_goals ? 'win' : 'loss'
      return match.away_goals > match.home_goals ? 'win' : 'loss'
    }

    const getLeagueName = (leagueId) => {
      const league = leagues.value.find(l => l.league_id === leagueId)
      return league ? (league.name_cn || league.name) : ''
    }

    onMounted(() => {
      loadLeagues()
    })

    return {
      selectedLeague, selectedSeason, selectedMatch, activeMatchTab,
      loading, matches, leagues,
      seasons, matchTabs,
      loadMatches, selectMatch, formatDate, getScoreClass, getLeagueName
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

.match-view {
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
  flex-wrap: wrap;
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

.match-tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  margin-bottom: 16px;
}

.match-tab {
  font-size: 14px;
  color: #9ca3af;
  background: transparent;
  border: none;
  padding: 0 0 10px 0;
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.match-tab:hover {
  color: #e5e7eb;
}

.match-tab.active {
  color: #10b981;
  font-weight: 500;
}

.match-tab.active::after {
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

.match-content {
  flex: 1;
  display: flex;
  gap: 24px;
  min-height: 0;
}

.match-list {
  width: 320px;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  padding: 16px;
  background: #151922;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.list-body {
  flex: 1;
  overflow-y: auto;
}

.empty-state {
  padding: 40px;
  text-align: center;
  color: #6b7280;
}

.match-item {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
  cursor: pointer;
  transition: background 0.2s;
}

.match-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.match-item.selected {
  background: rgba(16, 185, 129, 0.1);
  border-left: 3px solid #10b981;
}

.match-date {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 6px;
}

.match-teams {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.team-name {
  font-size: 13px;
  color: #e5e7eb;
  font-weight: 500;
}

.team-name.home {
  text-align: left;
}

.team-name.away {
  text-align: right;
}

.match-score {
  display: flex;
  align-items: center;
  gap: 4px;
}

.match-score span {
  min-width: 20px;
  text-align: center;
  font-weight: 600;
  font-size: 13px;
}

.match-score .win {
  color: #10b981;
}

.match-score .loss {
  color: #ef4444;
}

.match-score .draw {
  color: #9ca3af;
}

.divider {
  color: #4b5563;
}

.match-time {
  font-size: 11px;
  color: #6b7280;
  margin-top: 4px;
}

.match-detail {
  flex: 1;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.empty-detail {
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-text {
  color: #6b7280;
  font-size: 14px;
}

.scoreboard {
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.match-league {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 16px;
}

.teams-score {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  max-width: 400px;
  margin-bottom: 16px;
}

.team-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.score-display {
  font-size: 32px;
  font-weight: 900;
  color: white;
  padding: 0 16px;
}

.match-info {
  font-size: 12px;
  color: #6b7280;
  text-align: center;
}

.stats-compare {
  flex: 1;
  padding: 24px;
}

.compare-title {
  font-size: 14px;
  font-weight: 500;
  color: #d1d5db;
  margin-bottom: 16px;
}

.compare-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
}

.info-label {
  font-size: 12px;
  color: #6b7280;
}

.info-value {
  font-size: 12px;
  color: #e5e7eb;
  font-weight: 500;
}

/* 移动端 */
@media (max-width: 900px) {
  .match-content {
    flex-direction: column;
  }

  .match-list {
    width: 100%;
    max-height: 300px;
  }
}

@media (max-width: 600px) {
  .match-view {
    padding: 12px 16px;
  }

  .match-tabs {
    gap: 16px;
    overflow-x: auto;
  }

  .match-tab {
    font-size: 13px;
    white-space: nowrap;
  }

  .match-list {
    max-height: 200px;
  }

  .scoreboard {
    padding: 16px;
  }

  .score-display {
    font-size: 24px;
  }

  .stats-compare {
    padding: 16px;
  }
}
</style>