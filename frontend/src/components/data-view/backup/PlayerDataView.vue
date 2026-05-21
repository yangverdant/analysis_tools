<template>
  <div class="player-view card">
    <!-- 筛选器 -->
    <div class="filters">
      <select v-model="selectedSeason" class="filter-select">
        <option v-for="season in seasons" :key="season" :value="season">{{ season }}</option>
      </select>
      <select v-model="selectedLeague" class="filter-select" @change="loadTeams">
        <option v-for="league in leagues" :key="league.league_id" :value="league.league_id">
          {{ league.name_cn || league.name }}
        </option>
      </select>
      <div class="search-box">
        <SearchIcon />
        <input v-model="searchQuery" placeholder="搜索球队名称" />
      </div>
    </div>

    <!-- 内容区 -->
    <div class="player-content">
      <!-- 左侧球队列表 -->
      <div class="team-list">
        <div class="list-header">球队列表</div>
        <div class="list-body">
          <div v-if="loading" class="loading-item">
            <div class="mini-spinner"></div>
            <span>加载中...</span>
          </div>
          <div
            v-for="team in filteredTeams"
            :key="team.team_id"
            :class="['team-item', { active: activeTeam?.team_id === team.team_id }]"
            @click="selectTeam(team)"
          >
            <div class="team-avatar">
              <span class="team-initial">{{ getInitial(team) }}</span>
            </div>
            <div class="team-info">
              <span class="team-name">{{ team.name_cn || team.canonical_name }}</span>
              <span class="team-meta">
                <span class="dot"></span>
                {{ team.country_cn || team.country || '未知' }} · {{ team.team_type || '俱乐部' }}
              </span>
            </div>
          </div>
          <div v-if="!loading && filteredTeams.length === 0" class="empty-item">
            <p>暂无球队数据</p>
          </div>
        </div>
      </div>

      <!-- 右侧详情 -->
      <div class="team-detail">
        <!-- 详情标签 -->
        <div class="detail-tabs">
          <button
            v-for="tab in detailTabs"
            :key="tab"
            :class="['detail-tab', { active: activeDetailTab === tab }]"
            @click="activeDetailTab = tab"
          >
            {{ tab }}
          </button>
        </div>

        <!-- 球队信息 -->
        <div class="detail-body" v-if="activeTeam">
          <div class="team-header">
            <div class="team-large-avatar">
              <span class="team-large-initial">{{ getInitial(activeTeam) }}</span>
            </div>
            <div class="team-main-info">
              <h3 class="team-full-name">{{ activeTeam.name_cn || activeTeam.canonical_name }}</h3>
              <div class="team-type-country">{{ activeTeam.team_type || '俱乐部' }} / {{ activeTeam.country_cn || activeTeam.country || '未知' }}</div>
              <div class="team-extra">ID: {{ activeTeam.team_id }}</div>
            </div>
          </div>

          <!-- 核心数据 -->
          <div class="core-stats">
            <div class="core-stat-card">
              <span class="stat-label">球队ID</span>
              <span class="stat-value">{{ activeTeam.team_id }}</span>
            </div>
            <div class="core-stat-card">
              <span class="stat-label">类型</span>
              <span class="stat-value">{{ activeTeam.team_type || '俱乐部' }}</span>
            </div>
            <div class="core-stat-card">
              <span class="stat-label">国家</span>
              <span class="stat-value">{{ activeTeam.country_cn || activeTeam.country || '-' }}</span>
            </div>
            <div class="core-stat-card">
              <span class="stat-label">联赛</span>
              <span class="stat-value color-emerald">{{ getLeagueName(selectedLeague) }}</span>
            </div>
          </div>

          <!-- 提示信息 -->
          <h4 class="detail-title">数据说明</h4>
          <div class="info-box">
            <p>当前数据库暂无球员详细数据。</p>
            <p>球队基础信息已从API获取。</p>
            <p>如需球员数据，请导入球员数据源。</p>
          </div>
        </div>

        <!-- 未选择球队时的提示 -->
        <div class="detail-body empty-detail" v-else>
          <p class="empty-text">请从左侧选择一个球队查看详情</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, h, defineComponent } from 'vue'
import { leagueAPI, teamAPI } from '../../api'

const SearchIcon = defineComponent({
  name: 'SearchIcon',
  setup() {
    return () => h('svg', { class: 'w-3 h-3', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('circle', { cx: '11', cy: '11', r: '8' }),
      h('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' })
    ])
  }
})

export default {
  name: 'PlayerDataView',
  components: { SearchIcon },
  setup() {
    const selectedSeason = ref('2025-2026')
    const selectedLeague = ref('')
    const searchQuery = ref('')
    const activeTeam = ref(null)
    const activeDetailTab = ref('总览')
    const loading = ref(false)
    const teams = ref([])
    const leagues = ref([])

    const seasons = ['2025-2026', '2024-2025', '2023-2024', '2022-2023', '2021-2022', '2020-2021', '2019-2020', '2018-2019', '2017-2018', '2016-2017', '2015-2016', '2014-2015', '2013-2014', '2012-2013', '2011-2012', '2010-2011', '2009-2010', '2008-2009', '2007-2008', '2006-2007', '2005-2006', '2004-2005', '2003-2004', '2002-2003', '2001-2002', '2000-2001']
    const detailTabs = ['总览', '进攻', '传球', '防守', '纪律']

    const filteredTeams = computed(() => {
      if (!searchQuery.value) return teams.value
      const q = searchQuery.value.toLowerCase()
      return teams.value.filter(t =>
        (t.name_cn || t.canonical_name || '').toLowerCase().includes(q) ||
        (t.canonical_name || '').toLowerCase().includes(q)
      )
    })

    const loadLeagues = async () => {
      try {
        const res = await leagueAPI.getLeagues()
        if (res.data) {
          leagues.value = res.data
          if (res.data.length && !selectedLeague.value) {
            const epl = res.data.find(l => l.name === 'Premier League' || l.name_cn === '英超')
            selectedLeague.value = epl ? epl.league_id : res.data[0].league_id
            await loadTeams()
          }
        }
      } catch (e) {
        console.error('加载联赛失败:', e)
      }
    }

    const loadTeams = async () => {
      if (!selectedLeague.value) return
      loading.value = true
      try {
        const res = await teamAPI.getTeams({ league_id: selectedLeague.value })
        if (res.data) {
          teams.value = res.data
          if (res.data.length) {
            activeTeam.value = res.data[0]
          }
        }
      } catch (e) {
        console.error('加载球队失败:', e)
        teams.value = []
      } finally {
        loading.value = false
      }
    }

    const selectTeam = (team) => {
      activeTeam.value = team
    }

    const getInitial = (team) => {
      const name = team.name_cn || team.canonical_name || ''
      return name.charAt(0).toUpperCase()
    }

    const getLeagueName = (leagueId) => {
      const league = leagues.value.find(l => l.league_id === leagueId)
      return league ? (league.name_cn || league.name) : ''
    }

    onMounted(() => {
      loadLeagues()
    })

    return {
      selectedSeason, selectedLeague, searchQuery,
      seasons, leagues,
      activeTeam, activeDetailTab, detailTabs,
      loading, teams, filteredTeams,
      loadTeams, selectTeam, getInitial, getLeagueName
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

.player-view {
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

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-box svg {
  position: absolute;
  left: 10px;
  color: #6b7280;
  width: 12px;
  height: 12px;
}

.search-box input {
  background: #1c222f;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 6px 10px 6px 32px;
  font-size: 12px;
  color: white;
  outline: none;
  width: 180px;
}

.search-box input:focus {
  border-color: #10b981;
}

.player-content {
  flex: 1;
  display: flex;
  gap: 24px;
  min-height: 0;
}

.team-list {
  width: 256px;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  padding: 12px 16px;
  background: #151922;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  font-size: 14px;
  font-weight: 500;
  color: #d1d5db;
}

.list-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.loading-item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: #6b7280;
  font-size: 12px;
}

.mini-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #374151;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-item {
  padding: 20px;
  text-align: center;
  color: #6b7280;
  font-size: 12px;
}

.team-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  border: 1px solid transparent;
}

.team-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.team-item.active {
  background: #1c222f;
  border-color: #374151;
}

.team-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.team-initial {
  font-size: 16px;
  font-weight: 700;
  color: white;
}

.team-info {
  display: flex;
  flex-direction: column;
}

.team-name {
  font-size: 14px;
  color: #e5e7eb;
}

.team-meta {
  font-size: 10px;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(16, 185, 129, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.dot::after {
  content: '';
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #10b981;
}

.team-detail {
  flex: 1;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-tabs {
  display: flex;
  gap: 24px;
  padding: 16px 24px 0;
  background: #151922;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.detail-tab {
  font-size: 14px;
  color: #9ca3af;
  background: transparent;
  border: none;
  padding: 0 0 12px 0;
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.detail-tab:hover {
  color: #e5e7eb;
}

.detail-tab.active {
  color: #10b981;
  font-weight: 500;
}

.detail-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: #10b981;
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
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

.team-header {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 32px;
}

.team-large-avatar {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.team-large-initial {
  font-size: 32px;
  font-weight: 700;
  color: white;
}

.team-main-info {
  flex: 1;
}

.team-full-name {
  font-size: 22px;
  font-weight: 700;
  color: white;
  margin-bottom: 4px;
}

.team-type-country {
  font-size: 14px;
  color: #9ca3af;
}

.team-extra {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.core-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.core-stat-card {
  background: #151922;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: white;
}

.stat-value.color-emerald {
  color: #10b981;
}

.detail-title {
  font-size: 14px;
  font-weight: 500;
  color: #d1d5db;
  margin-bottom: 16px;
}

.info-box {
  background: #151922;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  padding: 16px;
}

.info-box p {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 8px;
}

.info-box p:last-child {
  margin-bottom: 0;
}

/* 移动端 */
@media (max-width: 900px) {
  .player-content {
    flex-direction: column;
  }

  .team-list {
    width: 100%;
    max-height: 200px;
  }

  .core-stats {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .player-view {
    padding: 12px 16px;
  }

  .filters {
    gap: 8px;
  }

  .search-box input {
    width: 140px;
  }

  .detail-tabs {
    gap: 16px;
    padding: 12px 16px 0;
    overflow-x: auto;
  }

  .detail-tab {
    font-size: 13px;
    white-space: nowrap;
  }

  .detail-body {
    padding: 16px;
  }

  .team-header {
    flex-wrap: wrap;
  }

  .team-large-avatar {
    width: 60px;
    height: 60px;
  }

  .team-large-initial {
    font-size: 24px;
  }

  .team-full-name {
    font-size: 18px;
  }

  .core-stats {
    gap: 8px;
  }

  .core-stat-card {
    padding: 12px;
  }

  .stat-value {
    font-size: 16px;
  }
}
</style>