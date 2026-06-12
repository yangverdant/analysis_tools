<template>
  <div class="lottery-value-bets">
    <div class="header">
      <h3>价值投注推荐</h3>
      <span class="subtitle">基于预测概率与赔率对比</span>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <div v-else-if="valueBets.length === 0" class="empty-state">
      <span>暂无价值投注</span>
      <p class="hint">当预测概率高于赔率隐含概率5%以上时，视为价值投注</p>
    </div>

    <div v-else class="value-bets-list">
      <!-- 高价值投注 -->
      <div v-if="highValueBets.length > 0" class="value-group high">
        <div class="group-header">
          <span class="group-label">高价值 (>10%)</span>
          <span class="group-count">{{ highValueBets.length }}个</span>
        </div>
        <div class="bets-items">
          <div v-for="bet in highValueBets" :key="bet.key" class="bet-card high">
            <div class="bet-main">
              <span class="play-type">{{ bet.play_type }}</span>
              <span class="bet-result">{{ bet.result }}</span>
              <span class="bet-value">+{{ bet.value_percent }}%</span>
            </div>
            <div class="bet-details">
              <div class="detail-row">
                <span class="detail-label">预测概率</span>
                <span class="detail-value">{{ bet.predicted_prob }}%</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">隐含概率</span>
                <span class="detail-value">{{ bet.implied_prob }}%</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">赔率</span>
                <span class="detail-value odds">{{ bet.odds }}</span>
              </div>
            </div>
            <div class="confidence-bar">
              <div class="bar-fill" :style="{ width: bet.predicted_prob + '%' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 中价值投注 -->
      <div v-if="mediumValueBets.length > 0" class="value-group medium">
        <div class="group-header">
          <span class="group-label">中价值 (5-10%)</span>
          <span class="group-count">{{ mediumValueBets.length }}个</span>
        </div>
        <div class="bets-items">
          <div v-for="bet in mediumValueBets" :key="bet.key" class="bet-card medium">
            <div class="bet-main">
              <span class="play-type">{{ bet.play_type }}</span>
              <span class="bet-result">{{ bet.result }}</span>
              <span class="bet-value">+{{ bet.value_percent }}%</span>
            </div>
            <div class="bet-details compact">
              <span>预测{{ bet.predicted_prob }}% vs 隐含{{ bet.implied_prob }}%</span>
              <span class="odds">赔率{{ bet.odds }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 价值投注说明 -->
    <div class="value-explanation">
      <h4>什么是价值投注?</h4>
      <p>
        当我们的预测概率高于赔率隐含概率时，存在"价值"。
        价值投注是长期盈利的核心策略。
      </p>
      <div class="formula">
        <span>价值 = 预测概率 - (1 / 赔率)</span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'

export default {
  name: 'LotteryValueBets',
  props: {
    matchId: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const loading = ref(false)
    const valueBets = ref([])

    const highValueBets = computed(() =>
      valueBets.value.filter(b => b.value > 0.1)
    )

    const mediumValueBets = computed(() =>
      valueBets.value.filter(b => b.value >= 0.05 && b.value <= 0.1)
    )

    const fetchValueBets = async () => {
      loading.value = true
      try {
        const response = await fetch(
          `/api/v1/lottery/value-bets/${props.matchId}`
        )
        const data = await response.json()
        if (data.success && data.value_bets) {
          valueBets.value = data.value_bets.map(bet => ({
            key: `${bet.play_type}_${bet.result}`,
            play_type: getPlayTypeLabel(bet.play_type),
            result: bet.result_display || bet.result,
            value: bet.value,
            value_percent: (bet.value * 100).toFixed(1),
            predicted_prob: (bet.predicted_prob * 100).toFixed(1),
            implied_prob: (bet.implied_prob * 100).toFixed(1),
            odds: bet.odds,
            value_rating: bet.value_rating || 'medium'
          }))
        }
      } catch (e) {
        console.error('获取价值投注失败:', e)
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

    watch(() => props.matchId, fetchValueBets, { immediate: true })

    return {
      loading,
      valueBets,
      highValueBets,
      mediumValueBets
    }
  }
}
</script>

<style scoped>
.lottery-value-bets {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header h3 {
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.subtitle {
  font-size: 12px;
  color: #6b7280;
}

.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #6b7280;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #374151;
  border-top-color: #f59e0b;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.hint {
  font-size: 12px;
  margin-top: 8px;
  text-align: center;
}

.value-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-header {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
}

.group-label {
  font-size: 13px;
  font-weight: 600;
}

.value-group.high .group-label { color: #10b981; }
.value-group.medium .group-label { color: #f59e0b; }

.group-count {
  font-size: 12px;
  color: #6b7280;
}

.bets-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bet-card {
  padding: 12px;
  border-radius: 8px;
}

.bet-card.high {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.bet-card.medium {
  background: rgba(245, 158, 11, 0.05);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.bet-main {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.play-type {
  font-size: 12px;
  color: #6b7280;
  padding: 2px 8px;
  background: rgba(255,255,255,0.1);
  border-radius: 4px;
}

.bet-result {
  font-size: 16px;
  font-weight: 700;
  color: white;
}

.bet-value {
  font-size: 14px;
  font-weight: 700;
}

.bet-card.high .bet-value { color: #10b981; }
.bet-card.medium .bet-value { color: #f59e0b; }

.bet-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.detail-label { color: #6b7280; }
.detail-value { color: white; }
.detail-value.odds { color: #10b981; }

.bet-details.compact {
  flex-direction: row;
  justify-content: space-between;
  font-size: 11px;
  color: #6b7280;
}

.bet-details.compact .odds {
  color: #10b981;
}

.confidence-bar {
  height: 4px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  margin-top: 8px;
}

.bar-fill {
  height: 100%;
  background: #10b981;
  border-radius: 2px;
}

/* 说明区域 */
.value-explanation {
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
}

.value-explanation h4 {
  font-size: 13px;
  color: white;
  margin-bottom: 8px;
}

.value-explanation p {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;
}

.formula {
  margin-top: 8px;
  padding: 8px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}
</style>