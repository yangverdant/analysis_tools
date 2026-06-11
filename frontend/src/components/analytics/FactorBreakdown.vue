<template>
  <div class="factor-breakdown">
    <h3>因子贡献分解</h3>
    <div class="chart-container">
      <svg :width="200" :height="200" class="pie-chart">
        <!-- 饼图扇形 -->
        <path v-for="(slice, i) in slices" :key="i"
              :d="slice.path" :fill="slice.color" stroke="#151922" stroke-width="2"/>
        <!-- 标签 -->
        <text v-for="(label, i) in labelPositions" :key="'l-'+i"
              :x="label.x" :y="label.y" fill="#e5e7eb" font-size="11" text-anchor="middle">
          {{ label.name }} {{ label.value }}%
        </text>
      </svg>
    </div>
    <!-- 详细列表 -->
    <div class="factor-list">
      <div v-for="factor in factors" :key="factor.name" class="factor-row">
        <span class="factor-name">{{ factor.name }}</span>
        <span class="factor-direction">{{ factor.direction }}</span>
        <span class="factor-contribution">{{ factor.contribution }}</span>
        <span :class="['factor-aligned', factor.aligned ? 'yes' : 'no']">
          {{ factor.aligned ? '正确' : '偏离' }}
        </span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'

const FACTOR_COLORS = {
  elo: '#3b82f6', poisson: '#8b5cf6', h2h: '#f59e0b',
  form: '#10b981', home_away: '#ef4444', motivation: '#06b6d4',
  news_factors: '#6b7280'
}

const FACTOR_NAMES = {
  elo: 'Elo', poisson: 'Poisson', h2h: '交锋',
  form: '近期', home_away: '主客', motivation: '动机',
  news_factors: '情报'
}

export default {
  name: 'FactorBreakdown',
  props: {
    weights: { type: Object, default: () => ({
      elo: 0.20, poisson: 0.25, h2h: 0.10, form: 0.15,
      home_away: 0.10, motivation: 0.10, news_factors: 0.10
    })},
    contributions: { type: Object, default: () => {} }
  },
  setup(props) {
    const factors = ref([])

    const slices = computed(() => {
      const weights = props.weights
      const total = Object.values(weights).reduce((s, v) => s + v, 0)
      const cx = 100, cy = 100, r = 80
      let angle = -90 // 从顶部开始

      return Object.entries(weights).map(([key, value]) => {
        const pct = value / total * 100
        const angleDelta = pct / 100 * 360
        const startAngle = angle
        const endAngle = angle + angleDelta

        const x1 = cx + r * Math.cos(startAngle * Math.PI / 180)
        const y1 = cy + r * Math.sin(startAngle * Math.PI / 180)
        const x2 = cx + r * Math.cos(endAngle * Math.PI / 180)
        const y2 = cy + r * Math.sin(endAngle * Math.PI / 180)

        const largeArc = angleDelta > 180 ? 1 : 0

        const path = pct > 0
          ? `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${largeArc} 1 ${x2},${y2} Z`
          : ''

        angle = endAngle
        return { path, color: FACTOR_COLORS[key] || '#6b7280' }
      })
    })

    const labelPositions = computed(() => {
      const weights = props.weights
      const total = Object.values(weights).reduce((s, v) => s + v, 0)
      const cx = 100, cy = 100, r = 110
      let angle = -90

      return Object.entries(weights).map(([key, value]) => {
        const pct = Math.round(value / total * 100)
        const midAngle = angle + (pct / 100 * 360) / 2
        const x = cx + r * Math.cos(midAngle * Math.PI / 180)
        const y = cy + r * Math.sin(midAngle * Math.PI / 180)
        angle += pct / 100 * 360
        return { name: FACTOR_NAMES[key] || key, value: pct, x, y }
      })
    })

    onMounted(() => {
      // 将权重转为因子列表
      const weights = props.weights
      const contribs = props.contributions || {}
      factors.value = Object.entries(weights).map(([key, value]) => ({
        name: FACTOR_NAMES[key] || key,
        direction: contribs[key]?.direction || '-',
        contribution: Math.round(value * 100) + '%',
        aligned: contribs[key]?.aligned ?? null
      }))
    })

    return { factors, slices, labelPositions }
  }
}
</script>

<style scoped>
.factor-breakdown {
  background: #151922;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #1f2937;
}
h3 { font-size: 14px; color: #e5e7eb; margin-bottom: 12px; }
.chart-container { display: flex; justify-content: center; margin-bottom: 12px; }
.factor-list { font-size: 12px; }
.factor-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 0; border-bottom: 1px solid rgba(31,41,55,0.3);
}
.factor-name { color: #e5e7eb; min-width: 60px; }
.factor-direction { color: #9ca3af; min-width: 80px; }
.factor-contribution { color: #10b981; }
.factor-aligned.yes { color: #10b981; }
.factor-aligned.no { color: #ef4444; }
</style>