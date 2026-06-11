<template>
  <div class="efficiency-analysis">
    <!-- Header -->
    <div class="header card">
      <div class="header-content">
        <h2><ZapIcon /> 效率分析</h2>
        <p>进攻效率、防守效率、控球效率分析</p>
      </div>
    </div>

    <!-- Team selector -->
    <div class="selector-row card">
      <div class="selector-group">
        <label class="selector-label">
          <SearchIcon /> 球队ID
        </label>
        <div class="selector-input-wrap">
          <input
            v-model="teamId"
            type="text"
            class="selector-input"
            placeholder="输入球队ID，如 33"
            @keyup.enter="loadData"
          />
          <button class="query-btn" @click="loadData" :disabled="!teamId || loading">
            <RefreshIcon /> 查询
          </button>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs card">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <component :is="tab.icon" />
        {{ tab.label }}
      </button>
    </div>

    <!-- Loading -->
    <div class="loading-state" v-if="loading">
      <div class="spinner"></div>
      <p>正在加载效率数据...</p>
    </div>

    <!-- Error -->
    <div class="error-state" v-else-if="error">
      <AlertIcon />
      <p>{{ error }}</p>
    </div>

    <!-- Attack tab -->
    <div class="tab-content" v-else-if="activeTab === 'attack' && attackData">
      <div class="summary-card card">
        <h3 class="section-title"><TrendingUpIcon /> 进攻效率概览</h3>
        <div class="stat-grid">
          <div class="stat-item">
            <span class="stat-label">分析场次</span>
            <span class="stat-value">{{ attackData.attacking_summary?.matches_analyzed ?? '--' }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">效率评分</span>
            <span class="stat-value highlight">{{ formatRating(attackData.attacking_summary?.efficiency_rating) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">联赛排名</span>
            <span class="stat-value accent">{{ attackData.attacking_summary?.league_rank ?? '--' }}</span>
          </div>
        </div>
      </div>
      <div class="detail-card card" v-if="attackData.attacking_summary?.avg_stats">
        <h3 class="section-title"><BarChartIcon /> 平均进攻数据</h3>
        <div class="stat-grid">
          <div class="stat-item" v-for="(val, key) in attackData.attacking_summary.avg_stats" :key="key">
            <span class="stat-label">{{ formatStatKey(key) }}</span>
            <span class="stat-value">{{ typeof val === 'number' ? val.toFixed(2) : val }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Defense tab -->
    <div class="tab-content" v-else-if="activeTab === 'defense' && defenseData">
      <div class="summary-card card">
        <h3 class="section-title"><ShieldIcon /> 防守效率概览</h3>
        <div class="stat-grid">
          <div class="stat-item">
            <span class="stat-label">分析场次</span>
            <span class="stat-value">{{ defenseData.defensive_summary?.matches_analyzed ?? '--' }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">效率评分</span>
            <span class="stat-value highlight">{{ formatRating(defenseData.defensive_summary?.efficiency_rating) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">联赛排名</span>
            <span class="stat-value accent">{{ defenseData.defensive_summary?.league_rank ?? '--' }}</span>
          </div>
        </div>
      </div>
      <div class="detail-card card" v-if="defenseData.defensive_summary?.avg_stats">
        <h3 class="section-title"><BarChartIcon /> 平均防守数据</h3>
        <div class="stat-grid">
          <div class="stat-item" v-for="(val, key) in defenseData.defensive_summary.avg_stats" :key="key">
            <span class="stat-label">{{ formatStatKey(key) }}</span>
            <span class="stat-value">{{ typeof val === 'number' ? val.toFixed(2) : val }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Possession tab -->
    <div class="tab-content" v-else-if="activeTab === 'possession' && possessionData">
      <div class="summary-card card">
        <h3 class="section-title"><PieChartIcon /> 控球效率概览</h3>
        <div class="stat-grid">
          <div class="stat-item">
            <span class="stat-label">分析场次</span>
            <span class="stat-value">{{ possessionData.possession_summary?.matches_analyzed ?? '--' }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">效率评分</span>
            <span class="stat-value highlight">{{ formatRating(possessionData.possession_summary?.efficiency_rating) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">控球风格</span>
            <span class="stat-value accent">{{ possessionData.possession_summary?.possession_style ?? '--' }}</span>
          </div>
        </div>
      </div>
      <div class="detail-card card" v-if="possessionData.possession_summary?.avg_stats">
        <h3 class="section-title"><BarChartIcon /> 平均控球数据</h3>
        <div class="stat-grid">
          <div class="stat-item" v-for="(val, key) in possessionData.possession_summary.avg_stats" :key="key">
            <span class="stat-label">{{ formatStatKey(key) }}</span>
            <span class="stat-value">{{ typeof val === 'number' ? val.toFixed(2) : val }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Compare tab -->
    <div class="tab-content" v-else-if="activeTab === 'compare'">
      <div class="compare-selectors card">
        <div class="selector-group">
          <label class="selector-label"><HomeIcon /> 主队ID</label>
          <input
            v-model="homeTeamId"
            type="text"
            class="selector-input"
            placeholder="主队ID"
          />
        </div>
        <div class="vs-divider">VS</div>
        <div class="selector-group">
          <label class="selector-label"><AwayIcon /> 客队ID</label>
          <input
            v-model="awayTeamId"
            type="text"
            class="selector-input"
            placeholder="客队ID"
          />
        </div>
        <button class="query-btn compare-btn" @click="loadCompare" :disabled="!homeTeamId || !awayTeamId || compareLoading">
          <RefreshIcon /> 对比
        </button>
      </div>

      <div class="loading-state" v-if="compareLoading">
        <div class="spinner"></div>
        <p>正在对比效率数据...</p>
      </div>

      <div class="error-state" v-else-if="compareError">
        <AlertIcon />
        <p>{{ compareError }}</p>
      </div>

      <template v-else-if="compareData">
        <div class="summary-card card">
          <h3 class="section-title"><GitCompareIcon /> 效率对比</h3>
          <div class="compare-grid">
            <div class="compare-item">
              <span class="compare-label">进攻优势</span>
              <span class="compare-value" :class="compareData.attacking_edge > 0 ? 'home-adv' : compareData.attacking_edge < 0 ? 'away-adv' : ''">
                {{ compareData.attacking_edge > 0 ? '主队' : compareData.attacking_edge < 0 ? '客队' : '持平' }}
                <span class="edge-num" v-if="compareData.attacking_edge !== 0">({{ Math.abs(compareData.attacking_edge).toFixed(2) }})</span>
              </span>
            </div>
            <div class="compare-item">
              <span class="compare-label">防守优势</span>
              <span class="compare-value" :class="compareData.defensive_edge > 0 ? 'home-adv' : compareData.defensive_edge < 0 ? 'away-adv' : ''">
                {{ compareData.defensive_edge > 0 ? '主队' : compareData.defensive_edge < 0 ? '客队' : '持平' }}
                <span class="edge-num" v-if="compareData.defensive_edge !== 0">({{ Math.abs(compareData.defensive_edge).toFixed(2) }})</span>
              </span>
            </div>
          </div>
        </div>
        <div class="detail-card card" v-if="compareData.comparison_details">
          <h3 class="section-title"><BarChartIcon /> 详细对比</h3>
          <div class="stat-grid">
            <div class="stat-item" v-for="(val, key) in compareData.comparison_details" :key="key">
              <span class="stat-label">{{ formatStatKey(key) }}</span>
              <span class="stat-value">{{ typeof val === 'number' ? val.toFixed(2) : val }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- No data placeholder -->
    <div class="no-data" v-else-if="!loading && !error && activeTab !== 'compare'">
      <InboxIcon />
      <p>请输入球队ID并点击查询</p>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, h, defineComponent } from 'vue'
import { analysisAPI } from '../../api'

// Inline SVG icons
const ZapIcon = defineComponent({
  name: 'ZapIcon',
  setup() {
    return () => h('svg', { class: 'icon-sm', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polygon', { points: '13 2 3 14 12 14 11 22 21 10 12 10 13 2' })
    ])
  }
})

const SearchIcon = defineComponent({
  name: 'SearchIcon',
  setup() {
    return () => h('svg', { class: 'icon-xs', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('circle', { cx: '11', cy: '11', r: '8' }),
      h('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' })
    ])
  }
})

const RefreshIcon = defineComponent({
  name: 'RefreshIcon',
  setup() {
    return () => h('svg', { class: 'icon-xs', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '23 4 23 10 17 10' }),
      h('polyline', { points: '1 20 1 14 7 14' }),
      h('path', { d: 'M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15' })
    ])
  }
})

const TrendingUpIcon = defineComponent({
  name: 'TrendingUpIcon',
  setup() {
    return () => h('svg', { class: 'icon-sm', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '23 6 13.5 15.5 8.5 10.5 1 18' }),
      h('polyline', { points: '17 6 23 6 23 12' })
    ])
  }
})

const ShieldIcon = defineComponent({
  name: 'ShieldIcon',
  setup() {
    return () => h('svg', { class: 'icon-sm', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' })
    ])
  }
})

const PieChartIcon = defineComponent({
  name: 'PieChartIcon',
  setup() {
    return () => h('svg', { class: 'icon-sm', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M21.21 15.89A10 10 0 1 1 8 2.83' }),
      h('path', { d: 'M22 12A10 10 0 0 0 12 2v10z' })
    ])
  }
})

const BarChartIcon = defineComponent({
  name: 'BarChartIcon',
  setup() {
    return () => h('svg', { class: 'icon-sm', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('line', { x1: '12', y1: '20', x2: '12', y2: '10' }),
      h('line', { x1: '18', y1: '20', x2: '18', y2: '4' }),
      h('line', { x1: '6', y1: '20', x2: '6', y2: '16' })
    ])
  }
})

const GitCompareIcon = defineComponent({
  name: 'GitCompareIcon',
  setup() {
    return () => h('svg', { class: 'icon-sm', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('circle', { cx: '18', cy: '18', r: '3' }),
      h('circle', { cx: '6', cy: '6', r: '3' }),
      h('path', { d: 'M13 6h3a2 2 0 0 1 2 2v7' }),
      h('path', { d: 'M11 18H8a2 2 0 0 1-2-2V9' })
    ])
  }
})

const HomeIcon = defineComponent({
  name: 'HomeIcon',
  setup() {
    return () => h('svg', { class: 'icon-xs', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z' }),
      h('polyline', { points: '9 22 9 12 15 12 15 22' })
    ])
  }
})

const AwayIcon = defineComponent({
  name: 'AwayIcon',
  setup() {
    return () => h('svg', { class: 'icon-xs', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2', ry: '2' }),
      h('line', { x1: '9', y1: '3', x2: '9', y2: '21' })
    ])
  }
})

const AlertIcon = defineComponent({
  name: 'AlertIcon',
  setup() {
    return () => h('svg', { class: 'icon-md', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('circle', { cx: '12', cy: '12', r: '10' }),
      h('line', { x1: '12', y1: '8', x2: '12', y2: '12' }),
      h('line', { x1: '12', y1: '16', x2: '12.01', y2: '16' })
    ])
  }
})

const InboxIcon = defineComponent({
  name: 'InboxIcon',
  setup() {
    return () => h('svg', { class: 'icon-md', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5' }, [
      h('polyline', { points: '22 12 16 12 14 15 10 15 8 12 2 12' }),
      h('path', { d: 'M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z' })
    ])
  }
})

const SwordIcon = defineComponent({
  name: 'SwordIcon',
  setup() {
    return () => h('svg', { class: 'icon-xs', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '23 6 13.5 15.5 8.5 10.5 1 18' }),
      h('polyline', { points: '17 6 23 6 23 12' })
    ])
  }
})

const ShieldHalfIcon = defineComponent({
  name: 'ShieldHalfIcon',
  setup() {
    return () => h('svg', { class: 'icon-xs', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' }),
      h('line', { x1: '12', y1: '2', x2: '12', y2: '22' })
    ])
  }
})

const CircleDotIcon = defineComponent({
  name: 'CircleDotIcon',
  setup() {
    return () => h('svg', { class: 'icon-xs', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('circle', { cx: '12', cy: '12', r: '10' }),
      h('circle', { cx: '12', cy: '12', r: '4' })
    ])
  }
})

const UsersIcon = defineComponent({
  name: 'UsersIcon',
  setup() {
    return () => h('svg', { class: 'icon-xs', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
      h('circle', { cx: '9', cy: '7', r: '4' }),
      h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
      h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
    ])
  }
})

export default {
  name: 'EfficiencyAnalysis',
  components: {
    ZapIcon, SearchIcon, RefreshIcon, TrendingUpIcon, ShieldIcon,
    PieChartIcon, BarChartIcon, GitCompareIcon, HomeIcon, AwayIcon,
    AlertIcon, InboxIcon, SwordIcon, ShieldHalfIcon, CircleDotIcon, UsersIcon
  },
  setup() {
    const teamId = ref('')
    const activeTab = ref('attack')
    const loading = ref(false)
    const error = ref(null)

    const attackData = ref(null)
    const defenseData = ref(null)
    const possessionData = ref(null)

    const homeTeamId = ref('')
    const awayTeamId = ref('')
    const compareLoading = ref(false)
    const compareError = ref(null)
    const compareData = ref(null)

    const tabs = [
      { key: 'attack', label: '进攻效率', icon: SwordIcon },
      { key: 'defense', label: '防守效率', icon: ShieldHalfIcon },
      { key: 'possession', label: '控球效率', icon: CircleDotIcon },
      { key: 'compare', label: '两队对比', icon: UsersIcon }
    ]

    const formatRating = (rating) => {
      if (rating == null) return '--'
      return typeof rating === 'number' ? rating.toFixed(2) : rating
    }

    const formatStatKey = (key) => {
      const map = {
        avg_goals: '场均进球',
        avg_shots: '场均射门',
        avg_shots_on_target: '场均射正',
        avg_shot_accuracy: '射正率',
        avg_xg: '场均xG',
        avg_goals_conceded: '场均失球',
        avg_shots_conceded: '场均被射门',
        avg_shots_on_target_conceded: '场均被射正',
        avg_possession: '场均控球率',
        avg_pass_accuracy: '传球成功率',
        avg_chances_created: '场均创造机会',
        avg_tackles: '场均抢断',
        avg_interceptions: '场均拦截',
        avg_clearances: '场均解围',
        conversion_rate: '转化率',
        defensive_actions: '防守动作',
        possession_retention: '控球保持率',
        progressive_passes: '向前传球',
        pressing_success: '逼抢成功率',
        build_up_efficiency: '组织效率'
      }
      return map[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    }

    const switchTab = (key) => {
      activeTab.value = key
      if (key !== 'compare' && teamId.value && !loading.value) {
        const dataMap = { attack: attackData, defense: defenseData, possession: possessionData }
        if (!dataMap[key].value) {
          loadData()
        }
      }
    }

    const loadData = async () => {
      if (!teamId.value) return
      loading.value = true
      error.value = null

      try {
        const promises = []

        if (!attackData.value || activeTab.value === 'attack') {
          promises.push(
            analysisAPI.getAttackingEfficiency(teamId.value)
              .then(res => { attackData.value = res.data || res })
              .catch(e => { console.error('进攻效率加载失败:', e) })
          )
        }
        if (!defenseData.value || activeTab.value === 'defense') {
          promises.push(
            analysisAPI.getDefensiveEfficiency(teamId.value)
              .then(res => { defenseData.value = res.data || res })
              .catch(e => { console.error('防守效率加载失败:', e) })
          )
        }
        if (!possessionData.value || activeTab.value === 'possession') {
          promises.push(
            analysisAPI.getPossessionEfficiency(teamId.value)
              .then(res => { possessionData.value = res.data || res })
              .catch(e => { console.error('控球效率加载失败:', e) })
          )
        }

        await Promise.all(promises)

        const dataMap = { attack: attackData, defense: defenseData, possession: possessionData }
        if (activeTab.value !== 'compare' && !dataMap[activeTab.value].value) {
          error.value = '未能获取效率数据，请检查球队ID'
        }
      } catch (e) {
        console.error('加载效率数据失败:', e)
        error.value = '加载失败: ' + (e.message || '未知错误')
      } finally {
        loading.value = false
      }
    }

    const loadCompare = async () => {
      if (!homeTeamId.value || !awayTeamId.value) return
      compareLoading.value = true
      compareError.value = null
      compareData.value = null

      try {
        const res = await analysisAPI.compareTeamsEfficiency(homeTeamId.value, awayTeamId.value)
        compareData.value = res.data || res
      } catch (e) {
        console.error('对比效率加载失败:', e)
        compareError.value = '对比失败: ' + (e.message || '未知错误')
      } finally {
        compareLoading.value = false
      }
    }

    return {
      teamId,
      activeTab,
      tabs,
      loading,
      error,
      attackData,
      defenseData,
      possessionData,
      homeTeamId,
      awayTeamId,
      compareLoading,
      compareError,
      compareData,
      formatRating,
      formatStatKey,
      switchTab,
      loadData,
      loadCompare
    }
  }
}
</script>

<style scoped>
.efficiency-analysis {
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

/* Header */
.header {
  padding: 16px 20px;
}

.header-content h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

/* Icons */
.icon-sm {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.icon-xs {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.icon-md {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* Selector */
.selector-row {
  padding: 14px 20px;
}

.selector-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.selector-label {
  font-size: 12px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 6px;
}

.selector-input-wrap {
  display: flex;
  gap: 8px;
}

.selector-input {
  flex: 1;
  padding: 8px 12px;
  background: #0a0d14;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.selector-input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.selector-input::placeholder {
  color: #4b5563;
}

.query-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  color: #10b981;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.query-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
}

.query-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Tabs */
.tabs {
  display: flex;
  padding: 4px;
  gap: 2px;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: #6b7280;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: #9ca3af;
  background: rgba(255, 255, 255, 0.03);
}

.tab-btn.active {
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.tab-btn svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
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

/* Error */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: #ef4444;
  gap: 8px;
}

.error-state p {
  font-size: 13px;
}

/* No data */
.no-data {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #4b5563;
  gap: 8px;
}

.no-data p {
  font-size: 13px;
}

/* Tab content */
.tab-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Section title */
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.section-title svg {
  width: 16px;
  height: 16px;
  color: #10b981;
  flex-shrink: 0;
}

/* Summary card */
.summary-card {
  padding: 16px 20px;
}

/* Detail card */
.detail-card {
  padding: 16px 20px;
}

/* Stat grid */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.stat-label {
  font-size: 11px;
  color: #6b7280;
}

.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: #e5e7eb;
}

.stat-value.highlight {
  color: #10b981;
}

.stat-value.accent {
  color: #60a5fa;
}

/* Compare selectors */
.compare-selectors {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 20px;
}

.compare-selectors .selector-group {
  flex: 1;
}

.compare-selectors .selector-input {
  width: 100%;
}

.vs-divider {
  font-size: 13px;
  font-weight: 700;
  color: #4b5563;
  padding-bottom: 10px;
}

.compare-btn {
  margin-bottom: 0;
  align-self: flex-end;
}

/* Compare grid */
.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.compare-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  background: #0a0d14;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.3);
}

.compare-label {
  font-size: 11px;
  color: #6b7280;
}

.compare-value {
  font-size: 15px;
  font-weight: 600;
  color: #9ca3af;
}

.compare-value.home-adv {
  color: #10b981;
}

.compare-value.away-adv {
  color: #60a5fa;
}

.edge-num {
  font-size: 12px;
  font-weight: 400;
  opacity: 0.8;
}

/* Responsive */
@media (max-width: 600px) {
  .compare-selectors {
    flex-direction: column;
    align-items: stretch;
  }

  .vs-divider {
    text-align: center;
    padding: 4px 0;
  }

  .compare-btn {
    align-self: stretch;
    justify-content: center;
  }

  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .compare-grid {
    grid-template-columns: 1fr;
  }

  .tabs {
    flex-wrap: wrap;
  }

  .tab-btn {
    flex: 1 1 45%;
  }
}
</style>
