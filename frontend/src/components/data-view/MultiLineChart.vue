<template>
  <div class="multi-line-chart">
    <svg viewBox="0 0 100 40" class="chart-svg">
      <!-- Y轴网格线 -->
      <g v-for="(val, i) in yLabels" :key="'y-' + i">
        <line
          :x1="0"
          :y1="40 - (val / yMax) * 40"
          :x2="100"
          :y2="40 - (val / yMax) * 40"
          stroke="#1f2937"
          stroke-width="0.5"
        />
        <text
          x="-2"
          :y="40 - (val / yMax) * 40 + 1"
          fill="#6b7280"
          font-size="3"
          text-anchor="end"
        >{{ val }}</text>
      </g>

      <!-- X轴标签 -->
      <text
        v-for="(label, i) in xLabels"
        :key="'x-' + i"
        :x="(i / (xLabels.length - 1)) * 100"
        y="46"
        fill="#6b7280"
        font-size="3"
        text-anchor="middle"
      >{{ label }}</text>

      <!-- 数据线 -->
      <g v-for="(line, idx) in lines" :key="'line-' + idx">
        <polyline
          :points="getPoints(line.data)"
          fill="none"
          :stroke="line.color"
          stroke-width="0.8"
          stroke-linejoin="round"
        />
        <circle
          v-for="(val, i) in line.data"
          :key="'c-' + idx + '-' + i"
          :cx="(i / (line.data.length - 1)) * 100"
          :cy="40 - (val / yMax) * 40"
          r="0.8"
          :fill="line.color"
        />
      </g>
    </svg>
  </div>
</template>

<script>
export default {
  name: 'MultiLineChart',
  props: {
    yMax: { type: Number, default: 5 },
    yLabels: { type: Array, default: () => [] },
    xLabels: { type: Array, default: () => [] },
    lines: { type: Array, default: () => [] }
  },
  setup(props) {
    const getPoints = (data) => {
      return data.map((val, i) => {
        const x = (i / (data.length - 1)) * 100
        const y = 40 - (val / props.yMax) * 40
        return `${x},${y}`
      }).join(' ')
    }

    return { getPoints }
  }
}
</script>

<style scoped>
.multi-line-chart {
  width: 100%;
  height: 100%;
  padding: 8px 16px 24px 16px;
}

.chart-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}
</style>