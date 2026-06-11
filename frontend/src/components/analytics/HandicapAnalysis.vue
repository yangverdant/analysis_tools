<template>
  <div class="handicap-analysis">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2><TrendingIcon /> 盘路分析</h2>
        <p>赢盘率(ATS)、大小球趋势、盘路走势</p>
      </div>
    </div>

    <!-- 球队选择 -->
    <div class="team-selector card" v-if="activeTab !== 'compare'">
      <div class="selector-row">
        <label class="selector-label">
          <SearchIcon />
          球队ID
        </label>
        <div class="selector-input-group">
          <input
            v-model="teamId"
            type="text"
            class="team-input"
            placeholder="输入球队ID，如 529"
            @keyup.enter="loadData"
          />
          <button class="search-btn" @click="loadData" :disabled="!teamId || loading">
            <SearchIcon />
            查询
          </button>
        </div>
      </div>
    </div>

    <!-- 标签切换 -->
    <div class="tabs card">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="switchTab(tab.key)"
      >
        <component :is="tab.icon" />
        {{ tab.label }}
      </button>
    </div>

    <!-- 加载状态 -->
    <div class="loading-state" v-if="loading">
      <div class="spinner"></div>
      <p>正在加载盘路数据...</p>
    </div>

    <!-- 错误提示 -->
    <div class="error-state" v-if="error">
      <AlertIcon />
      <p>{{ error }}</p>
    </div>

    <!-- ATS赢盘率 -->
    <div class="tab-content" v-if="!loading && !error && activeTab === 'ats' && atsData">
      <div class="stats-grid">
        <div class="stat-card card">
          <div class="stat-label">总场次</div>
          <div class="stat-value">{{ atsData.total_matches || 0 }}</div>
        </div>
        <div class="stat-card card highlight-green">
          <div class="stat-label">赢盘</div>
          <div class="stat-value">{{ atsData.ats_wins || 0 }}</div>
        </div>
        <div class="stat-card card highlight-red">
          <div class="stat-label">输盘</div>
          <div class="stat-value">{{ atsData.ats_losses || 0 }}</div>
        </div>
        <div class="stat-card card highlight-gray">
          <div class="stat-label">走盘</div>
          <div class="stat-value">{{ atsData.ats_pushes || 0 }}</div>
        </div>
      </div>

      <!-- 赢盘率 -->
      <div class="rate-section card">
        <div class="rate-header">
          <span class="rate-title">赢盘率 (ATS Rate)</span>
          <span class="rate-value" :class="getAtsRateClass(atsData.ats_rate)">
            {{ formatPercent(atsData.ats_rate) }}
          </span>
        </div>
        <div class="rate-bar">
          <div
            class="rate-bar-fill"
            :style="{ width: formatPercent(atsData.ats_rate) }"
            :class="getAtsRateClass(atsData.ats_rate)"
          ></div>
        </div>
      </div>

      <!-- 主客场赢盘率 -->
      <div class="home-away-grid">
        <div class="home-away-card card">
          <div class="ha-label">主场赢盘</div>
          <div class="ha-stats" v-if="atsData.home_ats">
            <div class="ha-record">
              <span class="win">{{ atsData.home_ats.wins || 0 }}赢</span>
              <span class="loss">{{ atsData.home_ats.losses || 0 }}输</span>
              <span class="push">{{ atsData.home_ats.pushes || 0 }}走</span>
            </div>
            <div class="ha-rate" :class="getAtsRateClass(atsData.home_ats.rate)">
              {{ formatPercent(atsData.home_ats.rate) }}
            </div>
          </div>
          <div class="ha-stats" v-else>
            <span class="no-data">暂无数据</span>
          </div>
        </div>
        <div class="home-away-card card">
          <div class="ha-label">客场赢盘</div>
          <div class="ha-stats" v-if="atsData.away_ats">
            <div class="ha-record">
              <span class="win">{{ atsData.away_ats.wins || 0 }}赢</span>
              <span class="loss">{{ atsData.away_ats.losses || 0 }}输</span>
              <span class="push">{{ atsData.away_ats.pushes || 0 }}走</span>
            </div>
            <div class="ha-rate" :class="getAtsRateClass(atsData.away_ats.rate)">
              {{ formatPercent(atsData.away_ats.rate) }}
            </div>
          </div>
          <div class="ha-stats" v-else>
            <span class="no-data">暂无数据</span>
          </div>
        </div>
      </div>

      <!-- 按盘口类型 -->
      <div class="handicap-type-section card" v-if="atsData.by_handicap_type && Object.keys(atsData.by_handicap_type).length">
        <h3 class="section-title">
          <BarChartIcon />
          按盘口类型统计
        </h3>
        <div class="handicap-type-list">
          <div
            class="handicap-type-row"
            v-for="(stats, type) in atsData.by_handicap_type"
            :key="type"
          >
            <div class="ht-type">{{ type }}</div>
            <div class="ht-record">
              <span class="win">{{ stats.wins || 0 }}赢</span>
              <span class="loss">{{ stats.losses || 0 }}输</span>
              <span class="push">{{ stats.pushes || 0 }}走</span>
            </div>
            <div class="ht-rate-bar">
              <div class="ht-rate-fill" :style="{ width: formatPercent(stats.rate) }" :class="getAtsRateClass(stats.rate)"></div>
            </div>
            <div class="ht-rate" :class="getAtsRateClass(stats.rate)">{{ formatPercent(stats.rate) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 大小球趋势 -->
    <div class="tab-content" v-if="!loading && !error && activeTab === 'overunder' && ouData">
      <div class="stats-grid">
        <div class="stat-card card">
          <div class="stat-label">总场次</div>
          <div class="stat-value">{{ ouData.total_matches || 0 }}</div>
        </div>
        <div class="stat-card card highlight-green">
          <div class="stat-label">大球</div>
          <div class="stat-value">{{ ouData.over_count || 0 }}</div>
        </div>
        <div class="stat-card card highlight-red">
          <div class="stat-label">小球</div>
          <div class="stat-value">{{ ouData.under_count || 0 }}</div>
        </div>
        <div class="stat-card card highlight-gray">
          <div class="stat-label">走盘</div>
          <div class="stat-value">{{ ouData.push_count || 0 }}</div>
        </div>
      </div>

      <!-- 大球率 -->
      <div class="rate-section card">
        <div class="rate-header">
          <span class="rate-title">大球率</span>
          <span class="rate-value" :class="getOuRateClass(ouData.over_rate)">
            {{ formatPercent(ouData.over_rate) }}
          </span>
        </div>
        <div class="rate-bar">
          <div
            class="rate-bar-fill"
            :style="{ width: formatPercent(ouData.over_rate) }"
            :class="getOuRateClass(ouData.over_rate)"
          ></div>
        </div>
      </div>

      <!-- 主客场大小球 -->
      <div class="home-away-grid" v-if="ouData.home_over_under || ouData.away_over_under">
        <div class="home-away-card card" v-if="ouData.home_over_under">
          <div class="ha-label">主场大小球</div>
          <div class="ha-stats">
            <div class="ha-record">
              <span class="over">大{{ ouData.home_over_under.over || 0 }}</span>
              <span class="under">小{{ ouData.home_over_under.under || 0 }}</span>
              <span class="push">走{{ ouData.home_over_under.push || 0 }}</span>
            </div>
            <div class="ha-rate" :class="getOuRateClass(ouData.home_over_under.over_rate)">
              {{ formatPercent(ouData.home_over_under.over_rate) }}
            </div>
          </div>
        </div>
        <div class="home-away-card card" v-if="ouData.away_over_under">
          <div class="ha-label">客场大小球</div>
          <div class="ha-stats">
            <div class="ha-record">
              <span class="over">大{{ ouData.away_over_under.over || 0 }}</span>
              <span class="under">小{{ ouData.away_over_under.under || 0 }}</span>
              <span class="push">走{{ ouData.away_over_under.push || 0 }}</span>
            </div>
            <div class="ha-rate" :class="getOuRateClass(ouData.away_over_under.over_rate)">
              {{ formatPercent(ouData.away_over_under.over_rate) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 常见盘口线 -->
      <div class="line-section card" v-if="ouData.by_line && Object.keys(ouData.by_line).length">
        <h3 class="section-title">
          <BarChartIcon />
          按盘口线统计
        </h3>
        <div class="line-list">
          <div
            class="line-row"
            v-for="(stats, line) in ouData.by_line"
            :key="line"
          >
            <div class="line-value">{{ line }}</div>
            <div class="line-record">
              <span class="over">大{{ stats.over || 0 }}</span>
              <span class="under">小{{ stats.under || 0 }}</span>
            </div>
            <div class="line-rate-bar">
              <div class="line-rate-fill" :style="{ width: formatPercent(stats.over_rate) }" :class="getOuRateClass(stats.over_rate)"></div>
            </div>
            <div class="line-rate" :class="getOuRateClass(stats.over_rate)">{{ formatPercent(stats.over_rate) }}</div>
          </div>
        </div>
      </div>

      <!-- 平均进球 -->
      <div class="avg-goals-grid" v-if="ouData.avg_total_goals != null">
        <div class="avg-card card">
          <div class="avg-label">场均总进球</div>
          <div class="avg-value">{{ (ouData.avg_total_goals || 0).toFixed(2) }}</div>
        </div>
        <div class="avg-card card" v-if="ouData.avg_home_goals != null">
          <div class="avg-label">主场场均进球</div>
          <div class="avg-value">{{ (ouData.avg_home_goals || 0).toFixed(2) }}</div>
        </div>
        <div class="avg-card card" v-if="ouData.avg_away_goals != null">
          <div class="avg-label">客场场均进球</div>
          <div class="avg-value">{{ (ouData.avg_away_goals || 0).toFixed(2) }}</div>
        </div>
      </div>
    </div>

    <!-- 盘路走势 -->
    <div class="tab-content" v-if="!loading && !error && activeTab === 'trend' && trendData">
      <!-- 当前连续 -->
      <div class="streak-card card" v-if="trendData.current_streak">
        <div class="streak-header">
          <span class="streak-label">当前连续</span>
          <span class="streak-badge" :class="getStreakClass(trendData.current_streak)">
            {{ trendData.current_streak.type === 'win' ? '赢盘' : trendData.current_streak.type === 'loss' ? '输盘' : '走盘' }}
            {{ trendData.current_streak.count }}场
          </span>
        </div>
      </div>

      <!-- 走势字符串 -->
      <div class="trend-string-card card" v-if="trendData.trend_string">
        <h3 class="section-title">
          <TrendingIcon />
          近期盘路走势
        </h3>
        <div class="trend-dots">
          <span
            v-for="(item, idx) in parseTrendString(trendData.trend_string)"
            :key="idx"
            :class="['trend-dot', item.type]"
            :title="item.label"
          >
            {{ item.symbol }}
          </span>
        </div>
        <div class="trend-legend">
          <span class="legend-item"><span class="legend-dot win"></span> 赢盘</span>
          <span class="legend-item"><span class="legend-dot loss"></span> 输盘</span>
          <span class="legend-item"><span class="legend-dot push"></span> 走盘</span>
        </div>
      </div>

      <!-- 走势详情列表 -->
      <div class="trend-list card" v-if="trendData.matches && trendData.matches.length">
        <h3 class="section-title">
          <ListIcon />
          盘路明细
        </h3>
        <div class="trend-table">
          <div class="trend-table-header">
            <span class="th-date">日期</span>
            <span class="th-opponent">对手</span>
            <span class="th-handicap">盘口</span>
            <span class="th-score">比分</span>
            <span class="th-result">结果</span>
          </div>
          <div
            class="trend-table-row"
            v-for="(match, idx) in trendData.matches"
            :key="idx"
          >
            <span class="td-date">{{ match.date || '--' }}</span>
            <span class="td-opponent">{{ match.opponent || '--' }}</span>
            <span class="td-handicap">{{ match.handicap || '--' }}</span>
            <span class="td-score">{{ match.score || '--' }}</span>
            <span :class="['td-result', match.result]">{{ getResultLabel(match.result) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 两队对比 -->
    <div class="tab-content" v-if="!loading && !error && activeTab === 'compare'">
      <div class="compare-selectors card">
        <div class="compare-selector-group">
          <label class="selector-label">
            <HomeIcon />
            主队ID
          </label>
          <input
            v-model="homeTeamId"
            type="text"
            class="team-input"
            placeholder="主队ID"
            @keyup.enter="loadCompareData"
          />
        </div>
        <div class="compare-vs">VS</div>
        <div class="compare-selector-group">
          <label class="selector-label">
            <AwayIcon />
            客队ID
          </label>
          <input
            v-model="awayTeamId"
            type="text"
            class="team-input"
            placeholder="客队ID"
            @keyup.enter="loadCompareData"
          />
        </div>
        <button class="search-btn" @click="loadCompareData" :disabled="!homeTeamId || !awayTeamId || loading">
          <SearchIcon />
          对比
        </button>
      </div>

      <div v-if="compareData" class="compare-results">
        <!-- ATS对比 -->
        <div class="compare-section card" v-if="compareData.ats_comparison">
          <h3 class="section-title">
            <BarChartIcon />
            赢盘率对比
          </h3>
          <div class="compare-bars">
            <div class="compare-row">
              <span class="compare-team home">主队</span>
              <div class="compare-bar-track">
                <div
                  class="compare-bar-fill home"
                  :style="{ width: formatPercent(compareData.ats_comparison.home_ats_rate) }"
                ></div>
              </div>
              <span class="compare-rate" :class="getAtsRateClass(compareData.ats_comparison.home_ats_rate)">
                {{ formatPercent(compareData.ats_comparison.home_ats_rate) }}
              </span>
            </div>
            <div class="compare-row">
              <span class="compare-team away">客队</span>
              <div class="compare-bar-track">
                <div
                  class="compare-bar-fill away"
                  :style="{ width: formatPercent(compareData.ats_comparison.away_ats_rate) }"
                ></div>
              </div>
              <span class="compare-rate" :class="getAtsRateClass(compareData.ats_comparison.away_ats_rate)">
                {{ formatPercent(compareData.ats_comparison.away_ats_rate) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 大小球对比 -->
        <div class="compare-section card" v-if="compareData.over_under_comparison">
          <h3 class="section-title">
            <BarChartIcon />
            大球率对比
          </h3>
          <div class="compare-bars">
            <div class="compare-row">
              <span class="compare-team home">主队</span>
              <div class="compare-bar-track">
                <div
                  class="compare-bar-fill home"
                  :style="{ width: formatPercent(compareData.over_under_comparison.home_over_rate) }"
                ></div>
              </div>
              <span class="compare-rate" :class="getOuRateClass(compareData.over_under_comparison.home_over_rate)">
                {{ formatPercent(compareData.over_under_comparison.home_over_rate) }}
              </span>
            </div>
            <div class="compare-row">
              <span class="compare-team away">客队</span>
              <div class="compare-bar-track">
                <div
                  class="compare-bar-fill away"
                  :style="{ width: formatPercent(compareData.over_under_comparison.away_over_rate) }"
                ></div>
              </div>
              <span class="compare-rate" :class="getOuRateClass(compareData.over_under_comparison.away_over_rate)">
                {{ formatPercent(compareData.over_under_comparison.away_over_rate) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 走势对比 -->
        <div class="compare-section card" v-if="compareData.trend_comparison">
          <h3 class="section-title">
            <TrendingIcon />
            近期走势对比
          </h3>
          <div class="compare-trends">
            <div class="compare-trend-row">
              <span class="compare-team home">主队</span>
              <div class="trend-dots small">
                <span
                  v-for="(item, idx) in parseTrendString(compareData.trend_comparison.home_trend)"
                  :key="'h' + idx"
                  :class="['trend-dot', item.type]"
                >{{ item.symbol }}</span>
              </div>
            </div>
            <div class="compare-trend-row">
              <span class="compare-team away">客队</span>
              <div class="trend-dots small">
                <span
                  v-for="(item, idx) in parseTrendString(compareData.trend_comparison.away_trend)"
                  :key="'a' + idx"
                  :class="['trend-dot', item.type]"
                >{{ item.symbol }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 综合建议 -->
        <div class="compare-summary card" v-if="compareData.summary">
          <h3 class="section-title">
            <LightbulbIcon />
            综合分析
          </h3>
          <p class="summary-text">{{ compareData.summary }}</p>
        </div>
      </div>
    </div>

    <!-- 无数据提示 -->
    <div class="no-data card" v-if="!loading && !error && !hasData">
      <InboxIcon />
      <p>请输入球队ID查询盘路数据</p>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, h, defineComponent } from 'vue'
import { analysisAPI } from '../../api'

// 图标组件
const TrendingIcon = defineComponent({
  name: 'TrendingIcon',
  setup() {
    return () => h('svg', { class: 'w-4 h-4', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('polyline', { points: '23 6 13.5 15.5 8.5 10.5 1 18' }),
      h('polyline', { points: '17 6 23 6 23 12' })
    ])
  }
})

const SearchIcon = defineComponent({
  name: 'SearchIcon',
  setup() {
    return () => h('svg', { class: 'w-4 h-4', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('circle', { cx: '11', cy: '11', r: '8' }),
      h('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' })
    ])
  }
})

const BarChartIcon = defineComponent({
  name: 'BarChartIcon',
  setup() {
    return () => h('svg', { class: 'w-4 h-4', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('line', { x1: '12', y1: '20', x2: '12', y2: '10' }),
      h('line', { x1: '18', y1: '20', x2: '18', y2: '4' }),
      h('line', { x1: '6', y1: '20', x2: '6', y2: '16' })
    ])
  }
})

const ListIcon = defineComponent({
  name: 'ListIcon',
  setup() {
    return () => h('svg', { class: 'w-4 h-4', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('line', { x1: '8', y1: '6', x2: '21', y2: '6' }),
      h('line', { x1: '8', y1: '12', x2: '21', y2: '12' }),
      h('line', { x1: '8', y1: '18', x2: '21', y2: '18' }),
      h('line', { x1: '3', y1: '6', x2: '3.01', y2: '6' }),
      h('line', { x1: '3', y1: '12', x2: '3.01', y2: '12' }),
      h('line', { x1: '3', y1: '18', x2: '3.01', y2: '18' })
    ])
  }
})

const AlertIcon = defineComponent({
  name: 'AlertIcon',
  setup() {
    return () => h('svg', { class: 'w-5 h-5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('circle', { cx: '12', cy: '12', r: '10' }),
      h('line', { x1: '12', y1: '8', x2: '12', y2: '12' }),
      h('line', { x1: '12', y1: '16', x2: '12.01', y2: '16' })
    ])
  }
})

const InboxIcon = defineComponent({
  name: 'InboxIcon',
  setup() {
    return () => h('svg', { class: 'w-5 h-5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5' }, [
      h('polyline', { points: '22 12 16 12 14 15 10 15 8 12 2 12' }),
      h('path', { d: 'M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z' })
    ])
  }
})

const HomeIcon = defineComponent({
  name: 'HomeIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z' }),
      h('polyline', { points: '9 22 9 12 15 12 15 22' })
    ])
  }
})

const AwayIcon = defineComponent({
  name: 'AwayIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2', ry: '2' }),
      h('line', { x1: '9', y1: '3', x2: '9', y2: '21' })
    ])
  }
})

const LightbulbIcon = defineComponent({
  name: 'LightbulbIcon',
  setup() {
    return () => h('svg', { class: 'w-4 h-4', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M9 18h6' }),
      h('path', { d: 'M10 22h4' }),
      h('path', { d: 'M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z' })
    ])
  }
})

const tabs = [
  { key: 'ats', label: 'ATS赢盘率', icon: BarChartIcon },
  { key: 'overunder', label: '大小球趋势', icon: TrendingIcon },
  { key: 'trend', label: '盘路走势', icon: TrendingIcon },
  { key: 'compare', label: '两队对比', icon: BarChartIcon }
]

export default {
  name: 'HandicapAnalysis',
  components: { TrendingIcon, SearchIcon, BarChartIcon, ListIcon, AlertIcon, InboxIcon, HomeIcon, AwayIcon, LightbulbIcon },
  setup() {
    const teamId = ref('')
    const homeTeamId = ref('')
    const awayTeamId = ref('')
    const activeTab = ref('ats')
    const loading = ref(false)
    const error = ref('')

    const atsData = ref(null)
    const ouData = ref(null)
    const trendData = ref(null)
    const compareData = ref(null)

    const hasData = computed(() => {
      if (activeTab.value === 'ats') return !!atsData.value
      if (activeTab.value === 'overunder') return !!ouData.value
      if (activeTab.value === 'trend') return !!trendData.value
      if (activeTab.value === 'compare') return !!compareData.value
      return false
    })

    const formatPercent = (val) => {
      if (val == null) return '0%'
      const num = typeof val === 'string' ? parseFloat(val) : val
      if (isNaN(num)) return '0%'
      return Math.round(num * 100) + '%'
    }

    const getAtsRateClass = (rate) => {
      if (rate == null) return ''
      const num = typeof rate === 'string' ? parseFloat(rate) : rate
      if (num >= 0.55) return 'rate-high'
      if (num >= 0.45) return 'rate-mid'
      return 'rate-low'
    }

    const getOuRateClass = (rate) => {
      if (rate == null) return ''
      const num = typeof rate === 'string' ? parseFloat(rate) : rate
      if (num >= 0.55) return 'rate-over'
      if (num <= 0.45) return 'rate-under'
      return 'rate-mid'
    }

    const getStreakClass = (streak) => {
      if (!streak) return ''
      if (streak.type === 'win') return 'streak-win'
      if (streak.type === 'loss') return 'streak-loss'
      return 'streak-push'
    }

    const parseTrendString = (str) => {
      if (!str) return []
      return str.split('').map(ch => {
        if (ch === 'W' || ch === 'w') return { type: 'win', symbol: 'W', label: '赢盘' }
        if (ch === 'L' || ch === 'l') return { type: 'loss', symbol: 'L', label: '输盘' }
        if (ch === 'P' || ch === 'p' || ch === 'D' || ch === 'd') return { type: 'push', symbol: 'P', label: '走盘' }
        return { type: 'other', symbol: ch, label: ch }
      })
    }

    const getResultLabel = (result) => {
      if (result === 'win' || result === 'W') return '赢'
      if (result === 'loss' || result === 'L') return '输'
      if (result === 'push' || result === 'P' || result === 'draw') return '走'
      return result || '--'
    }

    const switchTab = (key) => {
      activeTab.value = key
      error.value = ''
    }

    const loadData = async () => {
      if (!teamId.value) return
      loading.value = true
      error.value = ''

      try {
        if (activeTab.value === 'ats') {
          const res = await analysisAPI.getTeamATS(teamId.value)
          atsData.value = res.ats_summary || res.data || res
        } else if (activeTab.value === 'overunder') {
          const res = await analysisAPI.getTeamOverUnder(teamId.value)
          ouData.value = res.over_under_summary || res.data || res
        } else if (activeTab.value === 'trend') {
          const res = await analysisAPI.getTeamHandicapTrend(teamId.value)
          trendData.value = res.data || res
        }
      } catch (e) {
        console.error('加载盘路数据失败:', e)
        error.value = '加载数据失败，请检查球队ID是否正确'
      } finally {
        loading.value = false
      }
    }

    const loadCompareData = async () => {
      if (!homeTeamId.value || !awayTeamId.value) return
      loading.value = true
      error.value = ''

      try {
        const res = await analysisAPI.compareTeamsHandicap(homeTeamId.value, awayTeamId.value)
        compareData.value = res.data || res
      } catch (e) {
        console.error('加载对比数据失败:', e)
        error.value = '加载对比数据失败，请检查球队ID是否正确'
      } finally {
        loading.value = false
      }
    }

    return {
      teamId,
      homeTeamId,
      awayTeamId,
      activeTab,
      tabs,
      loading,
      error,
      atsData,
      ouData,
      trendData,
      compareData,
      hasData,
      formatPercent,
      getAtsRateClass,
      getOuRateClass,
      getStreakClass,
      parseTrendString,
      getResultLabel,
      switchTab,
      loadData,
      loadCompareData
    }
  }
}
</script>

<style scoped>
.handicap-analysis {
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

/* 头部 */
.header {
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  white-space: nowrap;
}

.header-content h2 svg {
  width: 18px;
  height: 18px;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

/* 球队选择 */
.team-selector {
  padding: 16px 20px;
}

.selector-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.selector-label {
  font-size: 13px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.selector-label svg {
  width: 14px;
  height: 14px;
}

.selector-input-group {
  display: flex;
  gap: 8px;
  flex: 1;
}

.team-input {
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

.team-input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.team-input::placeholder {
  color: #4b5563;
}

.search-btn {
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

.search-btn svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.search-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
}

.search-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* 标签切换 */
.tabs {
  display: flex;
  padding: 4px;
  gap: 4px;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 8px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  color: #6b7280;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.tab-btn:hover {
  color: #9ca3af;
  background: rgba(255, 255, 255, 0.03);
}

.tab-btn.active {
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
}

/* 加载状态 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
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

/* 错误提示 */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #ef4444;
  gap: 8px;
}

.error-state svg {
  width: 20px;
  height: 20px;
}

.error-state p {
  font-size: 13px;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card {
  padding: 16px;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #e5e7eb;
}

.stat-card.highlight-green .stat-value {
  color: #10b981;
}

.stat-card.highlight-red .stat-value {
  color: #ef4444;
}

.stat-card.highlight-gray .stat-value {
  color: #9ca3af;
}

/* 赢盘率条 */
.rate-section {
  padding: 16px 20px;
}

.rate-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.rate-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.rate-value {
  font-size: 18px;
  font-weight: 700;
}

.rate-bar {
  height: 8px;
  background: rgba(31, 41, 55, 0.5);
  border-radius: 4px;
  overflow: hidden;
}

.rate-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.rate-high, .rate-bar-fill.rate-high {
  color: #10b981;
  background: #10b981;
}

.rate-mid, .rate-bar-fill.rate-mid {
  color: #f59e0b;
  background: #f59e0b;
}

.rate-low, .rate-bar-fill.rate-low {
  color: #ef4444;
  background: #ef4444;
}

.rate-over, .rate-bar-fill.rate-over {
  color: #10b981;
  background: #10b981;
}

.rate-under, .rate-bar-fill.rate-under {
  color: #3b82f6;
  background: #3b82f6;
}

/* 主客场 */
.home-away-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.home-away-card {
  padding: 16px;
}

.ha-label {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 10px;
}

.ha-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ha-record {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.ha-record .win, .ha-record .over { color: #10b981; }
.ha-record .loss, .ha-record .under { color: #ef4444; }
.ha-record .push { color: #9ca3af; }

.ha-rate {
  font-size: 18px;
  font-weight: 700;
}

.no-data {
  font-size: 12px;
  color: #4b5563;
}

/* 盘口类型 */
.handicap-type-section,
.line-section {
  padding: 16px 20px;
}

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
}

.handicap-type-list,
.line-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.handicap-type-row,
.line-row {
  display: grid;
  grid-template-columns: 60px 100px 1fr 50px;
  align-items: center;
  gap: 10px;
}

.ht-type,
.line-value {
  font-size: 13px;
  font-weight: 600;
  color: #10b981;
}

.ht-record,
.line-record {
  display: flex;
  gap: 6px;
  font-size: 12px;
}

.ht-record .win, .line-record .over { color: #10b981; }
.ht-record .loss, .line-record .under { color: #ef4444; }
.ht-record .push { color: #9ca3af; }

.ht-rate-bar,
.line-rate-bar {
  height: 6px;
  background: rgba(31, 41, 55, 0.5);
  border-radius: 3px;
  overflow: hidden;
}

.ht-rate-fill,
.line-rate-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.ht-rate,
.line-rate {
  font-size: 12px;
  font-weight: 600;
  text-align: right;
}

/* 平均进球 */
.avg-goals-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.avg-card {
  padding: 16px;
  text-align: center;
}

.avg-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}

.avg-value {
  font-size: 20px;
  font-weight: 700;
  color: #f59e0b;
}

/* 连续 */
.streak-card {
  padding: 16px 20px;
}

.streak-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.streak-label {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.streak-badge {
  font-size: 14px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 6px;
}

.streak-win {
  color: #10b981;
  background: rgba(16, 185, 129, 0.15);
}

.streak-loss {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.15);
}

.streak-push {
  color: #9ca3af;
  background: rgba(156, 163, 175, 0.15);
}

/* 走势字符串 */
.trend-string-card {
  padding: 16px 20px;
}

.trend-dots {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.trend-dots.small {
  gap: 4px;
}

.trend-dot {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
}

.trend-dots.small .trend-dot {
  width: 22px;
  height: 22px;
  font-size: 10px;
  border-radius: 4px;
}

.trend-dot.win {
  color: #10b981;
  background: rgba(16, 185, 129, 0.15);
}

.trend-dot.loss {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.15);
}

.trend-dot.push {
  color: #9ca3af;
  background: rgba(156, 163, 175, 0.15);
}

.trend-dot.other {
  color: #4b5563;
  background: rgba(75, 85, 99, 0.15);
}

.trend-legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #6b7280;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.legend-dot.win { background: #10b981; }
.legend-dot.loss { background: #ef4444; }
.legend-dot.push { background: #9ca3af; }

/* 走势表格 */
.trend-list {
  padding: 16px 20px;
}

.trend-table {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trend-table-header {
  display: grid;
  grid-template-columns: 80px 1fr 60px 60px 50px;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  font-size: 11px;
  color: #6b7280;
  font-weight: 600;
}

.trend-table-row {
  display: grid;
  grid-template-columns: 80px 1fr 60px 60px 50px;
  gap: 8px;
  padding: 8px 0;
  font-size: 12px;
  color: #9ca3af;
  border-bottom: 1px solid rgba(31, 41, 55, 0.2);
}

.trend-table-row:last-child {
  border-bottom: none;
}

.td-result {
  font-weight: 600;
}

.td-result.win { color: #10b981; }
.td-result.loss { color: #ef4444; }
.td-result.push { color: #9ca3af; }

/* 两队对比 */
.compare-selectors {
  padding: 16px 20px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.compare-selector-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.compare-vs {
  font-size: 14px;
  font-weight: 700;
  color: #4b5563;
  padding-bottom: 8px;
}

.compare-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.compare-section {
  padding: 16px 20px;
}

.compare-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.compare-row {
  display: grid;
  grid-template-columns: 50px 1fr 50px;
  align-items: center;
  gap: 10px;
}

.compare-team {
  font-size: 12px;
  font-weight: 600;
}

.compare-team.home { color: #10b981; }
.compare-team.away { color: #60a5fa; }

.compare-bar-track {
  height: 8px;
  background: rgba(31, 41, 55, 0.5);
  border-radius: 4px;
  overflow: hidden;
}

.compare-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.compare-bar-fill.home { background: #10b981; }
.compare-bar-fill.away { background: #3b82f6; }

.compare-rate {
  font-size: 13px;
  font-weight: 700;
  text-align: right;
}

.compare-trends {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.compare-trend-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.compare-summary {
  padding: 16px 20px;
}

.summary-text {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
}

/* 无数据 */
.no-data {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #6b7280;
}

.no-data svg {
  width: 20px;
  height: 20px;
}

.no-data p {
  margin-top: 10px;
  font-size: 13px;
}

/* 响应式 */
@media (max-width: 600px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .home-away-grid {
    grid-template-columns: 1fr;
  }

  .avg-goals-grid {
    grid-template-columns: 1fr;
  }

  .compare-selectors {
    flex-direction: column;
    align-items: stretch;
  }

  .compare-vs {
    text-align: center;
    padding: 0;
  }

  .handicap-type-row,
  .line-row {
    grid-template-columns: 50px 80px 1fr 40px;
    gap: 6px;
  }

  .trend-table-header,
  .trend-table-row {
    grid-template-columns: 70px 1fr 50px 50px 40px;
    gap: 4px;
  }

  .tabs {
    flex-wrap: wrap;
  }

  .tab-btn {
    font-size: 12px;
    padding: 8px 6px;
  }
}
</style>
