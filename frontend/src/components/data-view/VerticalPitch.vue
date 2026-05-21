<template>
  <div class="vertical-pitch">
    <div class="pitch-title">{{ title }}</div>
    <div class="pitch">
      <!-- 球场线条 -->
      <div class="pitch-lines">
        <div class="half-line"></div>
        <div class="center-circle"></div>
        <div class="penalty-area top"></div>
        <div class="penalty-area bottom"></div>
        <div class="goal-area top"></div>
        <div class="goal-area bottom"></div>
      </div>
      <!-- 球员点 -->
      <div
        v-for="(dot, i) in dots"
        :key="i"
        class="player-dot"
        :style="{ left: dot.x + '%', top: dot.y + '%', backgroundColor: color }"
      >
        {{ dot.num }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'VerticalPitch',
  props: {
    title: String,
    color: { type: String, default: '#10b981' },
    dots: { type: Array, default: () => [] }
  }
}
</script>

<style scoped>
.vertical-pitch {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pitch-title {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 12px;
}

.pitch {
  width: 100%;
  max-width: 220px;
  aspect-ratio: 2 / 3;
  background: #0c1a11;
  border: 1px solid #374151;
  position: relative;
  overflow: hidden;
  border-radius: 4px;
}

.pitch-lines {
  position: absolute;
  inset: 0;
  opacity: 0.2;
  pointer-events: none;
}

.half-line {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: white;
}

.center-circle {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 64px;
  height: 64px;
  border: 1px solid white;
  border-radius: 50%;
}

.penalty-area {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: 96px;
  height: 48px;
  border: 1px solid white;
}

.penalty-area.top {
  top: 0;
  border-top: none;
}

.penalty-area.bottom {
  bottom: 0;
  border-bottom: none;
}

.goal-area {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 16px;
  border: 1px solid white;
}

.goal-area.top {
  top: 0;
  border-top: none;
}

.goal-area.bottom {
  bottom: 0;
  border-bottom: none;
}

.player-dot {
  position: absolute;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 500;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
  transform: translate(-50%, -50%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  transition: transform 0.2s;
}

.player-dot:hover {
  transform: translate(-50%, -50%) scale(1.1);
}
</style>
