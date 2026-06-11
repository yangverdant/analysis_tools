<template>
  <div class="lottery-accuracy">
    <div class="header">
      <h3>预测准确率追踪</h3>
      <div class="period-selector">
        <button
          v-for="p in periods"
          :key="p.value"
          :class="['period-btn', { active: selectedPeriod === p.value }]"
          @click="selectedPeriod = p.value"
        >
          {{ p.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <div v-else class="accuracy-content">
      <!-- 总体准确率卡片 -->
      <div class="overview-cards">
        <div class="overview-card">
          <span class="card-value">{{ stats.total_predictions }}</span>
          <span class="card-label">总预测数</span>
        </div>
        <div class="overview-card highlight">
          <span class="card-value">{{ stats.overall_accuracy }}%</span>
          <span class="card-label">总体准确率</span>
        </div>
        <div class="overview-card">
          <span class="card-value">{{ stats.avg_brier_score }}</span>
          <span class="card-label">平均Brier分数</span>
        </div>
      </div>

      <!-- 各玩法准确率 -->
      <div class="play-type-accuracy">
        <h4>各玩法准确率</h4>
        <div class="accuracy-bars">
          <div v-for="pt in playTypeStats" :key="pt.play_type" class="accuracy-bar-item">
            <div class="bar-header">
              <span class="play-type-label">{{ pt.label }}</span>
              <span class="accuracy-value">{{ pt.accuracy }}%</span>
            </div>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: pt.accuracy + '%' }"
                :class="getAccuracyClass(pt.accuracy)"
              ></div>
            </div>
            <div class="bar-footer">
              <span>{{ pt.correct }}/{{ pt.total }}正确</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 按置信度分组 -->
      <div class="confidence-breakdown">
        <h4>按置信度分组</h4>
        <div class="confidence-grid">
          <div v-for="cb in confidenceBreakdown" :key="cb.level" class="confidence-item">
            <span :class="['confidence-level', cb.level]">{{ cb.label }}</span>
            <div class="confidence-stats">
              <span class="stat">{{ cb.accuracy }}%</span>
              <span class="count">({{ cb.count }}次)</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 趋势图 -->
      <div class="trend-section">
        <h4>准确率趋势</h4>
        <div class="trend-chart">
          <div class="chart-placeholder">
            <div v-for="(point, i) in trendData" :key="i" class="trend-bar">
              <div
                class="bar"
                :style="{ height: point.accuracy + '%' }"
                :class="getAccuracyClass(point.accuracy)"
              ></div>
              <span class="label">{{ point.date }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 最近验证记录 -->
      <div class="recent-validations">
        <h4>最近验证记录</h4>
        <div class="validation-list">
          <div v-for="v in recentValidations" :key="v.id" class="validation-item">
            <div class="validation-header">
              <span class="match-info">{{ v.home_team }} vs {{ v.away_team }}</span>
              <span :class="['result-badge', v.is_correct ? 'correct' : 'incorrect']">
                {{ v.is_correct ? '正确' : '错误' }}
              </span>
            </div>
            <div class="validation-details">
              <span>预测: {{ v.predicted }} | 实际: {{ v.actual }}</span>
              <span class="confidence-tag">置信度: {{ v.confidence }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'

export default {
  name: 'LotteryAccuracy',
  setup() {
    const loading = ref(false)
    const selectedPeriod = ref(30)

    const periods = [
      { value: 7, label: '近7天' },
      { value: 30, label: '近30天' },
      { value: 90, label: '近90天' }
    ]

    const stats = ref({
      total_predictions: 0,
      overall_accuracy: 0,
      avg_brier_score: '-'
    })

    const playTypeStats = ref([
      { play_type: 'spf', label: '胜平负', accuracy: 0, correct: 0, total: 0 },
      { play_type: 'bf', label: '比分', accuracy: 0, correct: 0, total: 0 },
      { play_type: 'bqc', label: '半全场', accuracy: 0, correct: 0, total: 0 },
      { play_type: 'rqspf', label: '让球胜平负', accuracy: 0, correct: 0, total: 0 }
    ])

    const confidenceBreakdown = ref([
      { level: 'high', label: '高置信度', accuracy: 0, count: 0 },
      { level: 'medium', label: '中置信度', accuracy: 0, count: 0 },
      { level: 'low', label: '低置信度', accuracy: 0, count: 0 }
    ])

    const trendData = ref([])
    const recentValidations = ref([])

    const getAccuracyClass = (acc) => {
      if (acc >= 60) return 'high'
      if (acc >= 40) return 'medium'
      return 'low'
    }

    const fetchAccuracy = async () => {
      loading.value = true
      try {
        const response = await fetch(
          `http://localhost:18888/api/v1/lottery/accuracy?days=${selectedPeriod.value}`
        )
        const data = await response.json()
        if (data.success) {
          stats.value = {
            total_predictions: data.total_predictions || 0,
            overall_accuracy: data.overall_accuracy || 0,
            avg_brier_score: data.avg_brier_score?.toFixed(3) || '-'
          }

          if (data.by_play_type) {
            playTypeStats.value = data.by_play_type.map(pt => ({
              play_type: pt.play_type,
              label: getPlayTypeLabel(pt.play_type),
              accuracy: pt.accuracy || 0,
              correct: pt.correct || 0,
              total: pt.total || 0
            }))
          }

          if (data.by_confidence) {
            confidenceBreakdown.value = data.by_confidence.map(cb => ({
              level: cb.confidence_level,
              label: getConfidenceLabel(cb.confidence_level),
              accuracy: cb.accuracy || 0,
              count: cb.count || 0
            }))
          }

          trendData.value = data.trend || []
          recentValidations.value = data.recent || []
        }
      } catch (e) {
        console.error('获取准确率失败:', e)
      } finally {
        loading.value = false
      }
    }

    const getPlayTypeLabel = (type) => {
      const labels = {
        'spf': '胜平负',
        'bf': '比分',
        'bqc': '半全场',
        'rqspf': '让球胜平负'
      }
      return labels[type] || type
    }

    const getConfidenceLabel = (level) => {
      const labels = { 'high': '高置信度', 'medium': '中置信度', 'low': '低置信度' }
      return labels[level] || level
    }

    watch(selectedPeriod, fetchAccuracy)
    onMounted(fetchAccuracy)

    return {
      loading,
      selectedPeriod,
      periods,
      stats,
      playTypeStats,
      confidenceBreakdown,
      trendData,
      recentValidations,
      getAccuracyClass
    }
  }
}
</script>

<style scoped>
.lottery-accuracy {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h3 {
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.period-selector {
  display: flex;
  gap: 4px;
}

.period-btn {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid #374151;
  border-radius: 4px;
  font-size: 12px;
  color: #9ca3af;
  cursor: pointer;
}

.period-btn.active {
  background: #10b981;
  border-color: #10b981;
  color: white;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 40px;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #374151;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 概览卡片 */
.overview-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.overview-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
}

.overview-card.highlight {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.card-value {
  font-size: 28px;
  font-weight: 700;
  color: white;
}

.overview-card.highlight .card-value {
  color: #10b981;
}

.card-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

/* 各玩法准确率 */
.play-type-accuracy {
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
}

.play-type-accuracy h4 {
  font-size: 14px;
  color: white;
  margin-bottom: 12px;
}

.accuracy-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.accuracy-bar-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bar-header {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.play-type-label { color: #9ca3af; }
.accuracy-value { color: white; font-weight: 600; }

.bar-track {
  height: 8px;
  background: rgba(255,255,255,0.1);
  border-radius: 4px;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.bar-fill.high { background: #10b981; }
.bar-fill.medium { background: #f59e0b; }
.bar-fill.low { background: #ef4444; }

.bar-footer {
  font-size: 11px;
  color: #6b7280;
}

/* 置信度分组 */
.confidence-breakdown {
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
}

.confidence-breakdown h4 {
  font-size: 14px;
  color: white;
  margin-bottom: 12px;
}

.confidence-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.confidence-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
}

.confidence-level {
  font-size: 12px;
  font-weight: 600;
}

.confidence-level.high { color: #10b981; }
.confidence-level.medium { color: #f59e0b; }
.confidence-level.low { color: #ef4444; }

.confidence-stats {
  display: flex;
  gap: 4px;
}

.stat {
  font-size: 16px;
  font-weight: 700;
  color: white;
}

.count {
  font-size: 12px;
  color: #6b7280;
}

/* 趋势图 */
.trend-section {
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
}

.trend-section h4 {
  font-size: 14px;
  color: white;
  margin-bottom: 12px;
}

.chart-placeholder {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  height: 100px;
  padding-top: 20px;
}

.trend-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.trend-bar .bar {
  width: 80%;
  min-height: 4px;
  border-radius: 2px;
  transition: height 0.3s;
}

.trend-bar .label {
  font-size: 10px;
  color: #6b7280;
  margin-top: 4px;
}

/* 最近验证记录 */
.recent-validations {
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
}

.recent-validations h4 {
  font-size: 14px;
  color: white;
  margin-bottom: 12px;
}

.validation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.validation-item {
  padding: 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
}

.validation-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.match-info {
  font-size: 13px;
  color: white;
}

.result-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}

.result-badge.correct {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.result-badge.incorrect {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.validation-details {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #6b7280;
}

.confidence-tag {
  color: #9ca3af;
}
</style>