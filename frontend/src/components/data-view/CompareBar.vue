<template>
  <div class="compare-bar">
    <span class="bar-value left">{{ stat.left }}{{ stat.isPercent ? '%' : '' }}</span>
    <div class="bar-container">
      <div class="bar-left-wrap">
        <div class="bar-left" :style="{ width: leftWidth + '%' }" :class="stat.leftColor || 'emerald'"></div>
      </div>
      <span class="bar-label">{{ stat.label }}</span>
      <div class="bar-right-wrap">
        <div class="bar-right" :style="{ width: rightWidth + '%' }" :class="stat.rightColor || 'blue'"></div>
      </div>
    </div>
    <span class="bar-value right">{{ stat.right }}{{ stat.isPercent ? '%' : '' }}</span>
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'CompareBar',
  props: {
    stat: Object
  },
  setup(props) {
    const leftWidth = computed(() => {
      if (props.stat.isPercent) return props.stat.left
      return (props.stat.left / props.stat.max) * 100
    })

    const rightWidth = computed(() => {
      if (props.stat.isPercent) return props.stat.right
      return (props.stat.right / props.stat.max) * 100
    })

    return { leftWidth, rightWidth }
  }
}
</script>

<style scoped>
.compare-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 12px;
}

.bar-value {
  width: 32px;
  font-weight: 500;
  color: #d1d5db;
}

.bar-value.left {
  text-align: right;
}

.bar-container {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 16px;
}

.bar-left-wrap, .bar-right-wrap {
  flex: 1;
  height: 6px;
  background: #1f2937;
  border-radius: 3px;
  overflow: hidden;
}

.bar-left-wrap {
  display: flex;
  justify-content: flex-end;
}

.bar-left, .bar-right {
  height: 100%;
  border-radius: 3px;
}

.bar-left.emerald { background: #10b981; }
.bar-left.yellow { background: #facc15; }
.bar-right.blue { background: #3b82f6; }
.bar-right.yellow { background: #facc15; }

.bar-label {
  width: 64px;
  text-align: center;
  color: #6b7280;
  font-size: 12px;
}
</style>