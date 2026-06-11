<template>
  <div class="accuracy-trend">
    <h3>准确率趋势</h3>
    <div class="chart-container">
      <svg :width="chartWidth" :height="chartHeight" class="trend-chart">
        <!-- 网格线 -->
        <line v-for="i in 5" :key="'grid-'+i"
              :x1="padding" :y1="padding + (i-1) * (chartHeight - 2*padding) / 4"
              :x2="chartWidth - padding" :y2="padding + (i-1) * (chartHeight - 2*padding) / 4"
              stroke="#1f2937" stroke-width="1"/>
        <!-- Y轴标签 -->
        <text v-for="i in 5" :key="'ylabel-'+i"
              :x="padding - 8" :y="padding + (i-1) * (chartHeight - 2*padding) / 4 + 4"
              fill="#6b7280" font-size="10" text-anchor="end">
          {{ (100 - (i-1) * 25) }}%
        </text>
        <!-- 模型准确率折线 -->
        <polyline :points="modelLinePoints" fill="none" stroke="#10b981" stroke-width="2"/>
        <!-- 赔率基线折线 -->
        <polyline :points="oddsLinePoints" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4"/>
        <!-- 数据点 -->
        <circle v-for="(pt, i) in modelPoints" :key="'mp-'+i" :cx="pt.x" :cy="pt.y"
                r="3" fill="#10b981" @mouseenter="hovered = i" @mouseleave="hovered = -1"/>
        <circle v-for="(pt, i) in oddsPoints" :key="'op-'+i" :cx="pt.x" :cy="pt.y"
                r="3" fill="#f59e0b"/>
        <!-- 悬浮提示 -->
        <g v-if="hovered >= 0 && modelPoints[hovered]">
          <rect :x="modelPoints[hovered].x - 40" :y="modelPoints[hovered].y - 30"
                width="80" height="22" rx="4" fill="#1f2937" stroke="#374151"/>
          <text :x="modelPoints[hovered].x" :y="modelPoints[hovered].y - 16"
                fill="#e5e7eb" font-size="10" text-anchor="middle">
            {{ modelPoints[hovered].label }}: {{ modelPoints[hovered].value }}%
          </text>
        </g>
      </svg>
    </div>
    <div class="stats-row">
      <span class="stat-item model">7天: {{ accuracy7d }}%</span>
      <span class="stat-item model">30天: {{ accuracy30d }}%</span>
      <span class="stat-item odds">赔率基线: {{ oddsBaseline }}%</span>
    </div>
    <div class="legend">
      <span class="legend-item"><span class="dot model"></span>模型</span>
      <span class="legend-item"><span class="dot odds"></span>赔率基线</span>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { trackingAPI } from '../api/index.js'

export default {
  name: 'AccuracyTrend',
  props: {
    days: { type: Number, default: 30 }
  },
  setup(props) {
    const trendData = ref([])
    const accuracy7d = ref(0)
    const accuracy30d = ref(0)
    const oddsBaseline = ref(0)
    const hovered = ref(-1)
    const chartWidth = 500
    const chartHeight = 200
    const padding = 40

    const modelPoints = computed(() => {
      if (!trendData.value.length) return []
      const data = trendData.value.slice(-props.days)
      const step = (chartWidth - 2 * padding) / Math.max(data.length - 1, 1)
      return data.map((d, i) => ({
        x: padding + i * step,
        y: padding + (1 - (d.accuracy || 0) / 100) * (chartHeight - 2 * padding),
        value: d.accuracy || 0,
        label: d.date || ''
      }))
    })

    const oddsPoints = computed(() => {
      if (!trendData.value.length) return []
      const data = trendData.value.slice(-props.days)
      const step = (chartWidth - 2 * padding) / Math.max(data.length - 1, 1)
      const baseline = oddsBaseline.value / 100
      return data.map((d, i) => ({
        x: padding + i * step,
        y: padding + (1 - baseline) * (chartHeight - 2 * padding)
      }))
    })

    const modelLinePoints = computed(() => modelPoints.value.map(p => `${p.x},${p.y}`).join(' '))
    const oddsLinePoints = computed(() => oddsPoints.value.map(p => `${p.x},${p.y}`).join(' '))

    onMounted(async () => {
      try {
        const res = await trackingAPI.getAccuracy(null, props.days)
        if (res && res.daily_trend) {
          trendData.value = res.daily_trend
          accuracy7d.value = res.daily_trend.slice(-7).reduce((s, d) => s + d.accuracy, 0) / Math.max(res.daily_trend.slice(-7).length, 1)
          accuracy30d.value = res.result_accuracy || 0
          oddsBaseline.value = 48 // 经验值
        }
      } catch (e) {
        console.log('Accuracy trend fetch failed:', e)
      }
    })

    return {
      trendData, accuracy7d, accuracy30d, oddsBaseline,
      hovered, chartWidth, chartHeight, padding,
      modelPoints, oddsPoints, modelLinePoints, oddsLinePoints
    }
  }
}
</script>

<style scoped>
.accuracy-trend {
  background: #151922;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #1f2937;
}
h3 { font-size: 14px; color: #e5e7eb; margin-bottom: 12px; }
.chart-container { overflow-x: auto; }
.trend-chart { display: block; }
.stats-row {
  display: flex; gap: 16px; margin-top: 12px; font-size: 13px;
}
.stat-item.model { color: #10b981; }
.stat-item.odds { color: #f59e0b; }
.legend { display: flex; gap: 16px; margin-top: 8px; font-size: 12px; color: #9ca3af; }
.legend-item { display: flex; align-items: center; gap: 4px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.model { background: #10b981; }
.dot.odds { background: #f59e0b; }
</style>
