<template>
  <div class="position-view card">
    <!-- 筛选器 -->
    <div class="filters">
      <select v-model="selectedLeague" class="filter-select" @change="loadTeams">
        <option v-for="league in leagues" :key="league.league_id" :value="league.league_id">
          {{ league.name_cn || league.name }}
        </option>
      </select>
      <select v-model="selectedSeason" class="filter-select">
        <option v-for="season in seasons" :key="season" :value="season">{{ season }}</option>
      </select>
      <select v-model="selectedTeam" class="filter-select">
        <option v-for="team in teams" :key="team.team_id" :value="team.team_id">
          {{ team.name_cn || team.canonical_name }}
        </option>
      </select>
    </div>

    <!-- 站位类型标签 -->
    <div class="position-tabs">
      <button
        v-for="tab in positionTabs"
        :key="tab"
        :class="['pos-tab', { active: activePositionTab === tab }]"
        @click="activePositionTab = tab"
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
    <div v-else class="position-content">
      <!-- 球场站位图 -->
      <div class="pitch-section">
        <VerticalPitch
          title="进攻站位 (模拟)"
          color="#10b981"
          :dots="attackDots"
        />
        <VerticalPitch
          title="防守站位 (模拟)"
          color="#3b82f6"
          :dots="defenseDots"
        />
      </div>

      <!-- 右侧统计 -->
      <div class="stats-section">
        <h3 class="stats-title">阵型分析</h3>

        <!-- 当前球队 -->
        <div class="current-team">
          <h4 class="section-label">当前球队</h4>
          <div class="team-display">
            <span class="team-badge">{{ currentTeam?.name_cn || currentTeam?.canonical_name || '未选择' }}</span>
          </div>
        </div>

        <!-- 阵型分布 -->
        <div class="formation-section">
          <h4 class="section-label">常用阵型分布 (模拟)</h4>
          <div class="formation-bars">
            <div v-for="form in formations" :key="form.label" class="formation-row">
              <span class="formation-label">{{ form.label }}</span>
              <div class="formation-bar-bg">
                <div class="formation-bar" :style="{ width: form.pct + '%' }"></div>
              </div>
              <span class="formation-pct">{{ form.pct }}%</span>
            </div>
          </div>
        </div>

        <!-- 紧凑度 -->
        <div class="compact-section">
          <h4 class="section-label">阵型紧凑度 (模拟)</h4>
          <div class="compact-stats">
            <div class="compact-row">
              <span>进攻宽度</span>
              <span class="compact-val attack">31.2m</span>
            </div>
            <div class="compact-row">
              <span>防守宽度</span>
              <span class="compact-val defense">28.7m</span>
            </div>
          </div>
        </div>

        <p class="note">注：站位数据为模拟展示，真实数据需导入详细比赛事件数据</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { leagueAPI, teamAPI } from '../../api'
import VerticalPitch from './VerticalPitch.vue'

export default {
  name: 'PositionDataView',
  components: { VerticalPitch },
  setup() {
    const selectedLeague = ref('')
    const selectedSeason = ref('2025-2026')
    const selectedTeam = ref('')
    const loading = ref(false)
    const teams = ref([])
    const leagues = ref([])

    const seasons = ['2025-2026', '2024-2025', '2023-2024', '2022-2023', '2021-2022', '2020-2021', '2019-2020', '2018-2019', '2017-2018', '2016-2017', '2015-2016', '2014-2015', '2013-2014', '2012-2013', '2011-2012', '2010-2011', '2009-2010', '2008-2009', '2007-2008', '2006-2007', '2005-2006', '2004-2005', '2003-2004', '2002-2003', '2001-2002', '2000-2001']
    const positionTabs = ['总体站位', '进攻站位', '防守站位', '定位球站位']
    const activePositionTab = ref('总体站位')

    const currentTeam = computed(() => teams.value.find(t => t.team_id === selectedTeam.value))

    // 模拟站位数据
    const attackDots = [
      { num: 1, x: 50, y: 90 },
      { num: 2, x: 80, y: 70 },
      { num: 3, x: 20, y: 70 },
      { num: 4, x: 65, y: 75 },
      { num: 5, x: 35, y: 75 },
      { num: 6, x: 60, y: 55 },
      { num: 7, x: 40, y: 55 },
      { num: 8, x: 85, y: 35 },
      { num: 9, x: 15, y: 35 },
      { num: 10, x: 50, y: 40 },
      { num: 11, x: 50, y: 15 },
    ]

    const defenseDots = [
      { num: 1, x: 50, y: 88 },
      { num: 2, x: 85, y: 65 },
      { num: 3, x: 15, y: 65 },
      { num: 4, x: 60, y: 70 },
      { num: 5, x: 40, y: 70 },
      { num: 6, x: 70, y: 50 },
      { num: 7, x: 30, y: 50 },
      { num: 8, x: 80, y: 30 },
      { num: 9, x: 20, y: 30 },
      { num: 10, x: 50, y: 45 },
      { num: 11, x: 50, y: 25 },
    ]

    const formations = [
      { label: '4-2-3-1', pct: 62 },
      { label: '4-3-3', pct: 25 },
      { label: '3-2-4-1', pct: 8 },
      { label: '4-4-2', pct: 5 },
    ]

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
          if (res.data.length && !selectedTeam.value) {
            selectedTeam.value = res.data[0].team_id
          }
        }
      } catch (e) {
        console.error('加载球队失败:', e)
        teams.value = []
      } finally {
        loading.value = false
      }
    }

    onMounted(() => {
      loadLeagues()
    })

    return {
      selectedLeague, selectedSeason, selectedTeam,
      seasons, leagues, teams, loading,
      positionTabs, activePositionTab,
      currentTeam, attackDots, defenseDots,
      formations, loadTeams
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

.position-view {
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

.position-tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  margin-bottom: 16px;
}

.pos-tab {
  font-size: 14px;
  color: #9ca3af;
  background: transparent;
  border: none;
  padding: 0 0 10px 0;
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.pos-tab:hover {
  color: #e5e7eb;
}

.pos-tab.active {
  color: #10b981;
  font-weight: 500;
}

.pos-tab.active::after {
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

.position-content {
  flex: 1;
  display: flex;
  gap: 24px;
  min-height: 0;
  overflow: hidden;
}

.pitch-section {
  flex: 2;
  display: flex;
  gap: 32px;
  padding-right: 24px;
  border-right: 1px solid rgba(31, 41, 55, 0.5);
  overflow-y: auto;
}

.stats-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding-left: 24px;
}

.stats-title {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
  margin-bottom: 24px;
}

.section-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 16px;
}

.current-team {
  margin-bottom: 24px;
}

.team-display {
  display: flex;
  align-items: center;
}

.team-badge {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
}

.formation-section {
  margin-bottom: 32px;
}

.formation-bars {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.formation-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.formation-label {
  width: 64px;
  font-size: 12px;
  color: #d1d5db;
}

.formation-bar-bg {
  flex: 1;
  height: 6px;
  background: #1f2937;
  border-radius: 3px;
  overflow: hidden;
}

.formation-bar {
  height: 100%;
  background: #10b981;
  border-radius: 3px;
  transition: width 0.3s;
}

.formation-pct {
  width: 32px;
  font-size: 12px;
  color: #9ca3af;
  text-align: right;
}

.compact-section {
  margin-bottom: auto;
}

.compact-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.compact-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  font-size: 14px;
  color: #d1d5db;
}

.compact-val {
  font-family: monospace;
  font-weight: 600;
}

.compact-val.attack {
  color: #10b981;
}

.compact-val.defense {
  color: #3b82f6;
}

.note {
  margin-top: auto;
  padding-top: 16px;
  font-size: 10px;
  color: #4b5563;
}

/* 移动端 */
@media (max-width: 900px) {
  .position-content {
    flex-direction: column;
  }

  .pitch-section {
    flex: none;
    flex-direction: column;
    gap: 16px;
    padding-right: 0;
    border-right: none;
    border-bottom: 1px solid rgba(31, 41, 55, 0.5);
    padding-bottom: 16px;
    overflow-y: visible;
  }

  .stats-section {
    padding-left: 0;
    padding-top: 16px;
  }
}

@media (max-width: 600px) {
  .position-view {
    padding: 12px 16px;
  }

  .filters {
    gap: 8px;
  }

  .filter-select {
    padding: 6px 10px;
    font-size: 11px;
  }

  .position-tabs {
    gap: 16px;
    overflow-x: auto;
  }

  .pos-tab {
    font-size: 13px;
    white-space: nowrap;
  }
}
</style>