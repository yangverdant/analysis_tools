<template>
  <div class="data-view">
    <!-- 头部 -->
    <div class="data-header card">
      <div class="header-top">
        <div class="title-section">
          <h2 class="title">
            <DatabaseIcon />
            数据查看
          </h2>
          <p class="subtitle">查看球队、球员、比赛和联赛的详细数据统计</p>
        </div>
      </div>

      <!-- 类型选择器 -->
      <div class="type-selector">
        <button
          v-for="t in types"
          :key="t.key"
          :class="['type-btn', { active: selectedType === t.key }]"
          @click="selectedType = t.key"
        >
          {{ t.label }}
        </button>
      </div>

      <!-- 联赛选择器 -->
      <div class="league-selectors">
        <select v-model="selectedRegion" class="selector region-select">
          <option v-for="region in regions" :key="region.key" :value="region.key">{{ region.label }}</option>
        </select>
        <select v-model="selectedLeague" class="selector league-select">
          <option v-for="league in filteredLeagues" :key="league.league_id" :value="league.league_id">
            {{ league.name_cn || league.name_en }}
          </option>
        </select>
        <select v-model="selectedSeason" class="selector season-select">
          <option v-for="season in availableSeasons" :key="season" :value="season">{{ season }}</option>
        </select>
      </div>

      <!-- 子标签页 - 只在联赛时显示 -->
      <div class="sub-tabs" v-if="selectedType === 'league'">
        <button
          v-for="tab in subTabs"
          :key="tab"
          :class="['sub-tab', { active: activeSubTab === tab }]"
          @click="activeSubTab = tab"
        >
          {{ tab }}
        </button>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="tab-content">
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <LoadingIcon />
        <span>加载中...</span>
      </div>

      <!-- 未选择联赛提示 -->
      <div v-else-if="!selectedLeague" class="empty-state">
        <DatabaseIcon />
        <p>请选择一个联赛查看数据</p>
      </div>

      <!-- 杯赛视图 -->
      <CupMatchView v-else-if="selectedType === 'cup'" :league-id="selectedLeague" :season="selectedSeason" />

      <!-- 联赛视图 -->
      <template v-else>
        <LeagueMatchView v-if="activeSubTab === '积分榜'" :league-id="selectedLeague" :season="selectedSeason" :available-rounds="availableRounds" />
        <MatchListView v-else-if="activeSubTab === '比赛列表'" :league-id="selectedLeague" :season="selectedSeason" />
        <PlayerStatsView v-else :league-id="selectedLeague" :season="selectedSeason" />
      </template>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, h, defineComponent } from 'vue'
import { leagueAPI } from '../api'
import LeagueMatchView from './data-view/LeagueMatchView.vue'
import CupMatchView from './data-view/CupMatchView.vue'
import PlayerStatsView from './data-view/PlayerStatsView.vue'
import MatchListView from './data-view/MatchListView.vue'

const DatabaseIcon = defineComponent({
  name: 'DatabaseIcon',
  setup() {
    return () => h('svg', { class: 'w-3 h-3 text-emerald-400', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('ellipse', { cx: '12', cy: '5', rx: '9', ry: '3' }),
      h('path', { d: 'M21 12c0 1.66-4 3-9 3s-9-1.34-9-3' }),
      h('path', { d: 'M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5' })
    ])
  }
})

const LoadingIcon = defineComponent({
  name: 'LoadingIcon',
  setup() {
    return () => h('svg', { class: 'w-5 h-5 animate-spin', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('line', { x1: '12', y1: '2', x2: '12', y2: '6' }),
      h('line', { x1: '12', y1: '18', x2: '12', y2: '22' }),
      h('line', { x1: '4.93', y1: '4.93', x2: '7.17', y2: '7.17' }),
      h('line', { x1: '16.83', y1: '16.83', x2: '19.07', y2: '19.07' }),
      h('line', { x1: '2', y1: '12', x2: '6', y2: '12' }),
      h('line', { x1: '18', y1: '12', x2: '22', y2: '12' })
    ])
  }
})

// 类型分类
const TYPES = [
  { key: 'league', label: '联赛' },
  { key: 'cup', label: '杯赛' }
]

// 地区分类
const REGIONS = [
  { key: 'europe', label: '欧洲', countries: ['England', 'Spain', 'Germany', 'Italy', 'France', 'Netherlands', 'Portugal', 'Belgium', 'Austria', 'Switzerland', 'Turkey', 'Greece', 'Poland', 'Czech Republic', 'Denmark', 'Sweden', 'Norway', 'Finland', 'Croatia', 'Hungary', 'Romania', 'Russia', 'Ukraine', 'Scotland', 'Slovakia'] },
  { key: 'southamerica', label: '南美洲', countries: ['Brazil', 'Argentina', 'South America'] },
  { key: 'asia', label: '亚洲', countries: ['China', 'Japan', 'South Korea', 'Saudi Arabia', 'Australia', 'Asia'] },
  { key: 'international', label: '国际赛事', countries: ['Europe', 'World', 'Africa', 'North America', 'Mexico', 'USA', 'Egypt', 'Unknown'] }
]

export default {
  name: 'DataView',
  components: { DatabaseIcon, LeagueMatchView, CupMatchView, PlayerStatsView, MatchListView, LoadingIcon },
  setup() {
    const selectedType = ref('league')
    const types = TYPES
    const activeSubTab = ref('积分榜')
    const subTabs = ['积分榜', '比赛列表', '球员数据']
    const loading = ref(true)

    const selectedRegion = ref('europe')
    const selectedLeague = ref(null)
    const selectedSeason = ref(null)
    const leagues = ref([])
    const availableSeasons = ref([])
    const availableRounds = ref([])

    const regions = REGIONS

    // 根据类型和地区筛选联赛
    const filteredLeagues = computed(() => {
      const region = REGIONS.find(r => r.key === selectedRegion.value)
      if (!region) return leagues.value

            return leagues.value.filter(l => {
        const matchRegion = region.countries.includes(l.country)
        if (selectedType.value === 'cup') {
          return matchRegion && (l.competition_type === 'cup' || l.competition_type === 'international' || l.competition_type === 'continental_cup' || l.competition_type === 'domestic_cup')
        } else {
          return matchRegion && l.competition_type === 'league'
        }
      }).sort((a, b) => (a.tier || 99) - (b.tier || 99))
    })

    // 加载联赛列表
    const loadLeagues = async () => {
      loading.value = true
      try {
        const res = await leagueAPI.getLeagues()
        if (res.data) {
          leagues.value = res.data
          // 根据类型选择默认联赛
          selectDefaultLeague()
        }
      } catch (e) {
        console.error('加载联赛失败:', e)
      } finally {
        loading.value = false
      }
    }

    // 选择默认联赛
    const selectDefaultLeague = () => {
      if (filteredLeagues.value.length) {
        selectedLeague.value = filteredLeagues.value[0].league_id
      } else {
        selectedLeague.value = null
      }
    }

    // 加载联赛可用赛季
    const loadSeasons = async (leagueId) => {
      if (!leagueId) return
      try {
        const res = await leagueAPI.getSeasons(leagueId)
        if (res.data && res.data.length) {
          availableSeasons.value = res.data
          selectedSeason.value = res.data[0]
        }
      } catch (e) {
        console.error('加载赛季失败:', e)
        availableSeasons.value = []
      }
    }

    // 加载轮次列表
    const loadRounds = async (leagueId, season) => {
      if (!leagueId || !season) return
      try {
        const res = await leagueAPI.getRounds(leagueId, season)
        if (res.data) {
          availableRounds.value = res.data
        }
      } catch (e) {
        console.error('加载轮次失败:', e)
        availableRounds.value = []
      }
    }

    // 监听类型变化
    watch(selectedType, () => {
      selectDefaultLeague()
    })

    // 监听地区变化
    watch(selectedRegion, () => {
      selectDefaultLeague()
    })

    // 监听联赛变化
    watch(selectedLeague, (newVal) => {
      if (newVal) {
        loadSeasons(newVal)
      }
    })

    // 监听赛季变化
    watch(selectedSeason, (newVal) => {
      if (newVal && selectedLeague.value) {
        loadRounds(selectedLeague.value, newVal)
      }
    })

    // 初始化加载
    onMounted(async () => {
      await loadLeagues()
      if (selectedLeague.value) {
        await loadSeasons(selectedLeague.value)
        if (selectedSeason.value) {
          await loadRounds(selectedLeague.value, selectedSeason.value)
        }
      }
    })

    return {
      selectedType, types, activeSubTab, subTabs,
      selectedRegion, selectedLeague, selectedSeason,
      leagues, filteredLeagues, availableSeasons, availableRounds, regions
    }
  }
}
</script>

<style scoped>
.data-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  overflow-y: auto;
  max-width: 1200px;
  margin: 0 auto;
}

.card {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.data-header {
  padding: 16px 20px;
  flex-shrink: 0;
}

.header-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 16px;
}

.title-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title {
  font-size: 18px;
  font-weight: 700;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.subtitle {
  font-size: 12px;
  color: #6b7280;
}

.type-selector {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.type-btn {
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  background: #1c222f;
  border: 1px solid #374151;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.type-btn:hover {
  color: #e5e7eb;
  border-color: #4b5563;
}

.type-btn.active {
  color: white;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border-color: #10b981;
}

.league-selectors {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.selector {
  background: #1c222f;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: white;
  outline: none;
  cursor: pointer;
}

.selector:focus {
  border-color: #10b981;
}

.region-select {
  min-width: 100px;
}

.league-select {
  min-width: 160px;
}

.season-select {
  min-width: 120px;
}

.sub-tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  overflow-x: auto;
}

.sub-tabs::-webkit-scrollbar {
  height: 0;
}

.sub-tab {
  font-size: 14px;
  color: #9ca3af;
  background: transparent;
  border: none;
  padding: 0 0 12px 0;
  cursor: pointer;
  position: relative;
  white-space: nowrap;
  transition: color 0.2s;
}

.sub-tab:hover {
  color: #e5e7eb;
}

.sub-tab.active {
  color: #10b981;
  font-weight: 500;
}

.sub-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: #10b981;
}

.tab-content {
  flex-shrink: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  color: #6b7280;
  background: #151922;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.empty-state svg {
  width: 16px;
  height: 16px;
  margin-bottom: 8px;
}

.empty-state p {
  font-size: 13px;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  color: #6b7280;
  font-size: 13px;
}

@media (max-width: 600px) {
  .data-header {
    padding: 12px 16px;
  }

  .header-top {
    flex-wrap: wrap;
  }

  .title {
    font-size: 16px;
  }

  .subtitle {
    font-size: 11px;
  }

  .type-selector {
    flex-wrap: wrap;
  }

  .type-btn {
    padding: 5px 12px;
    font-size: 12px;
  }

  .league-selectors {
    gap: 8px;
  }

  .selector {
    padding: 6px 10px;
    font-size: 11px;
  }

  .sub-tabs {
    gap: 16px;
  }

  .sub-tab {
    font-size: 13px;
  }
}
</style>