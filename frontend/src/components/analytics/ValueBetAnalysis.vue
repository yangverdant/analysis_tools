<template>
  <div class="value-bet-analysis">
    <!-- Header -->
    <div class="header card">
      <div class="header-content">
        <h2>
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          价值投注
        </h2>
        <p>价值注扫描、套利机会、Kelly公式</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs-bar card">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'scan' }"
        @click="activeTab = 'scan'"
      >
        <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        价值注扫描
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'arbitrage' }"
        @click="activeTab = 'arbitrage'"
      >
        <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        套利分析
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'kelly' }"
        @click="activeTab = 'kelly'"
      >
        <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
        Kelly公式
      </button>
    </div>

    <!-- Tab: Value Bet Scan -->
    <div class="tab-content" v-if="activeTab === 'scan'">
      <div class="scan-controls card">
        <div class="control-group">
          <label>扫描天数</label>
          <span class="control-value">7 天</span>
        </div>
        <div class="control-group">
          <label>最小Edge</label>
          <span class="control-value">5%</span>
        </div>
        <button class="action-btn" @click="loadValueBets" :disabled="scanLoading">
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
          {{ scanLoading ? '扫描中...' : '扫描价值注' }}
        </button>
      </div>

      <!-- Loading -->
      <div class="loading-state" v-if="scanLoading">
        <div class="spinner"></div>
        <p>正在扫描价值注...</p>
      </div>

      <!-- Value Bets List -->
      <div class="value-bets-list" v-else-if="valueBets.length">
        <div
          class="value-bet-card card"
          v-for="(bet, index) in valueBets"
          :key="index"
        >
          <div class="bet-header">
            <span class="match-name">{{ bet.match }}</span>
            <span class="market-tag">{{ bet.market }}</span>
          </div>
          <div class="bet-probs">
            <div class="prob-item">
              <span class="prob-label">预测概率</span>
              <span class="prob-value predicted">{{ (bet.predicted_prob * 100).toFixed(1) }}%</span>
            </div>
            <div class="prob-item">
              <span class="prob-label">隐含概率</span>
              <span class="prob-value implied">{{ (bet.implied_prob * 100).toFixed(1) }}%</span>
            </div>
            <div class="prob-item">
              <span class="prob-label">Edge</span>
              <span class="prob-value edge" :class="getEdgeClass(bet.edge)">
                {{ (bet.edge * 100).toFixed(1) }}%
              </span>
            </div>
          </div>
          <div class="bet-recommendation">
            <span class="rec-label">建议</span>
            <span class="rec-value">{{ bet.recommendation }}</span>
          </div>
          <div class="bet-confidence">
            <span class="confidence-label">置信度</span>
            <div class="confidence-bar">
              <div
                class="confidence-fill"
                :style="{ width: (bet.confidence * 100) + '%' }"
                :class="getConfidenceClass(bet.confidence)"
              ></div>
            </div>
            <span class="confidence-value">{{ (bet.confidence * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <!-- No Data -->
      <div class="no-data card" v-else-if="scanLoaded && !valueBets.length">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
          <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
        </svg>
        <p>暂无价值注数据，点击扫描按钮开始</p>
      </div>
    </div>

    <!-- Tab: Arbitrage -->
    <div class="tab-content" v-if="activeTab === 'arbitrage'">
      <div class="arbitrage-form card">
        <h3>套利机会检测</h3>
        <p class="form-desc">输入三个赛果的赔率，检测是否存在套利空间</p>
        <div class="odds-inputs">
          <div class="input-group">
            <label>主胜赔率</label>
            <input
              type="number"
              v-model.number="arbForm.home_odds"
              placeholder="如 2.10"
              step="0.01"
              min="1.01"
            />
          </div>
          <div class="input-group">
            <label>平局赔率</label>
            <input
              type="number"
              v-model.number="arbForm.draw_odds"
              placeholder="如 3.40"
              step="0.01"
              min="1.01"
            />
          </div>
          <div class="input-group">
            <label>客胜赔率</label>
            <input
              type="number"
              v-model.number="arbForm.away_odds"
              placeholder="如 3.80"
              step="0.01"
              min="1.01"
            />
          </div>
        </div>
        <button
          class="action-btn"
          @click="analyzeArbitrage"
          :disabled="arbLoading || !arbForm.home_odds || !arbForm.draw_odds || !arbForm.away_odds"
        >
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          {{ arbLoading ? '分析中...' : '检测套利' }}
        </button>
      </div>

      <!-- Arbitrage Result -->
      <div class="arb-result card" v-if="arbResult">
        <div class="arb-status" :class="arbResult.is_arbitrage ? 'positive' : 'negative'">
          <svg v-if="arbResult.is_arbitrage" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="status-icon">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="status-icon">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          <span>{{ arbResult.is_arbitrage ? '存在套利机会' : '无套利机会' }}</span>
        </div>

        <template v-if="arbResult.is_arbitrage">
          <div class="arb-metrics">
            <div class="metric-item">
              <span class="metric-label">利润率</span>
              <span class="metric-value profit">{{ (arbResult.profit_pct * 100).toFixed(2) }}%</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">总回报率</span>
              <span class="metric-value">{{ (arbResult.total_return * 100).toFixed(2) }}%</span>
            </div>
          </div>
          <div class="optimal-stakes" v-if="arbResult.optimal_stakes">
            <h4>最优投注分配</h4>
            <div class="stakes-grid">
              <div class="stake-item">
                <span class="stake-label">主胜</span>
                <span class="stake-value">{{ (arbResult.optimal_stakes.home * 100).toFixed(1) }}%</span>
              </div>
              <div class="stake-item">
                <span class="stake-label">平局</span>
                <span class="stake-value">{{ (arbResult.optimal_stakes.draw * 100).toFixed(1) }}%</span>
              </div>
              <div class="stake-item">
                <span class="stake-label">客胜</span>
                <span class="stake-value">{{ (arbResult.optimal_stakes.away * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </template>

        <div class="arb-info" v-else>
          <p>当前赔率组合不存在套利空间。隐含概率总和需小于100%才存在套利机会。</p>
          <div class="implied-sum">
            <span class="implied-label">隐含概率总和:</span>
            <span class="implied-value">
              {{ (1 / arbForm.home_odds + 1 / arbForm.draw_odds + 1 / arbForm.away_odds).toFixed(4) }}
              ({{ ((1 / arbForm.home_odds + 1 / arbForm.draw_odds + 1 / arbForm.away_odds) * 100).toFixed(2) }}%)
            </span>
          </div>
        </div>
      </div>

      <!-- No Result -->
      <div class="no-data card" v-else>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
          <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
        </svg>
        <p>输入赔率后点击检测按钮</p>
      </div>
    </div>

    <!-- Tab: Kelly -->
    <div class="tab-content" v-if="activeTab === 'kelly'">
      <div class="kelly-form card">
        <h3>Kelly公式计算</h3>
        <p class="form-desc">根据预测概率和赔率计算最优投注比例</p>
        <div class="kelly-inputs">
          <div class="input-group">
            <label>预测概率</label>
            <input
              type="number"
              v-model.number="kellyForm.prediction_prob"
              placeholder="如 0.55"
              step="0.01"
              min="0"
              max="1"
            />
            <span class="input-hint">0~1之间，如0.55表示55%</span>
          </div>
          <div class="input-group">
            <label>赔率</label>
            <input
              type="number"
              v-model.number="kellyForm.odds"
              placeholder="如 2.00"
              step="0.01"
              min="1.01"
            />
            <span class="input-hint">小数赔率，如2.00</span>
          </div>
          <div class="input-group">
            <label>Fractional Kelly</label>
            <input
              type="number"
              v-model.number="kellyForm.fractional"
              placeholder="如 0.5"
              step="0.1"
              min="0.1"
              max="1"
            />
            <span class="input-hint">保守系数，0.5为半Kelly</span>
          </div>
        </div>
        <button
          class="action-btn"
          @click="calculateKelly"
          :disabled="kellyLoading || !kellyForm.prediction_prob || !kellyForm.odds"
        >
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          {{ kellyLoading ? '计算中...' : '计算Kelly' }}
        </button>
      </div>

      <!-- Kelly Result -->
      <div class="kelly-result card" v-if="kellyResult">
        <h3>计算结果</h3>
        <div class="kelly-metrics">
          <div class="kelly-metric">
            <span class="metric-label">Full Kelly</span>
            <span class="metric-value" :class="kellyResult.full_kelly > 0 ? 'positive' : 'negative'">
              {{ (kellyResult.full_kelly * 100).toFixed(2) }}%
            </span>
          </div>
          <div class="kelly-metric">
            <span class="metric-label">Fractional Kelly</span>
            <span class="metric-value accent">
              {{ (kellyResult.fractional_kelly * 100).toFixed(2) }}%
            </span>
          </div>
          <div class="kelly-metric">
            <span class="metric-label">期望值 (EV)</span>
            <span class="metric-value" :class="kellyResult.expected_value > 0 ? 'positive' : 'negative'">
              {{ kellyResult.expected_value.toFixed(4) }}
            </span>
          </div>
          <div class="kelly-metric">
            <span class="metric-label">建议投注</span>
            <span class="metric-value accent">
              {{ (kellyResult.recommended_stake * 100).toFixed(2) }}%
            </span>
          </div>
        </div>

        <div class="kelly-visual">
          <div class="kelly-bar-container">
            <div class="kelly-bar-label">Full Kelly</div>
            <div class="kelly-bar">
              <div
                class="kelly-bar-fill full"
                :style="{ width: Math.min(Math.abs(kellyResult.full_kelly) * 500, 100) + '%' }"
              ></div>
            </div>
            <div class="kelly-bar-value">{{ (kellyResult.full_kelly * 100).toFixed(2) }}%</div>
          </div>
          <div class="kelly-bar-container">
            <div class="kelly-bar-label">Fractional</div>
            <div class="kelly-bar">
              <div
                class="kelly-bar-fill fractional"
                :style="{ width: Math.min(Math.abs(kellyResult.fractional_kelly) * 500, 100) + '%' }"
              ></div>
            </div>
            <div class="kelly-bar-value">{{ (kellyResult.fractional_kelly * 100).toFixed(2) }}%</div>
          </div>
        </div>

        <div class="kelly-note" v-if="kellyResult.full_kelly <= 0">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="note-icon">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>Kelly值为负，表示此投注不具备正期望值，建议不投注</span>
        </div>
      </div>

      <!-- No Result -->
      <div class="no-data card" v-else>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
          <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
        </svg>
        <p>输入参数后点击计算按钮</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'ValueBetAnalysis',
  setup() {
    const activeTab = ref('scan')

    // Value Bet Scan
    const scanLoading = ref(false)
    const scanLoaded = ref(false)
    const valueBets = ref([])

    const loadValueBets = async () => {
      scanLoading.value = true
      try {
        const res = await analysisAPI.scanValueBets(7, 0.05)
        valueBets.value = res.data || res.value_bets || []
        scanLoaded.value = true
      } catch (e) {
        console.error('扫描价值注失败:', e)
        valueBets.value = []
        scanLoaded.value = true
      } finally {
        scanLoading.value = false
      }
    }

    const getEdgeClass = (edge) => {
      if (edge >= 0.15) return 'high'
      if (edge >= 0.10) return 'medium'
      return 'low'
    }

    const getConfidenceClass = (confidence) => {
      if (confidence >= 0.8) return 'high'
      if (confidence >= 0.6) return 'medium'
      return 'low'
    }

    // Arbitrage
    const arbLoading = ref(false)
    const arbResult = ref(null)
    const arbForm = reactive({
      home_odds: null,
      draw_odds: null,
      away_odds: null
    })

    const analyzeArbitrage = async () => {
      if (!arbForm.home_odds || !arbForm.draw_odds || !arbForm.away_odds) return
      arbLoading.value = true
      try {
        const res = await analysisAPI.findArbitrage([
          arbForm.home_odds,
          arbForm.draw_odds,
          arbForm.away_odds
        ])
        arbResult.value = res.data || res
      } catch (e) {
        console.error('套利分析失败:', e)
        arbResult.value = null
      } finally {
        arbLoading.value = false
      }
    }

    // Kelly
    const kellyLoading = ref(false)
    const kellyResult = ref(null)
    const kellyForm = reactive({
      prediction_prob: null,
      odds: null,
      fractional: 0.5
    })

    const calculateKelly = async () => {
      if (!kellyForm.prediction_prob || !kellyForm.odds) return
      kellyLoading.value = true
      try {
        const res = await analysisAPI.calculateKelly(
          kellyForm.prediction_prob,
          kellyForm.odds,
          kellyForm.fractional
        )
        kellyResult.value = res.data || res
      } catch (e) {
        console.error('Kelly计算失败:', e)
        kellyResult.value = null
      } finally {
        kellyLoading.value = false
      }
    }

    return {
      activeTab,
      // Scan
      scanLoading,
      scanLoaded,
      valueBets,
      loadValueBets,
      getEdgeClass,
      getConfidenceClass,
      // Arbitrage
      arbLoading,
      arbResult,
      arbForm,
      analyzeArbitrage,
      // Kelly
      kellyLoading,
      kellyResult,
      kellyForm,
      calculateKelly
    }
  }
}
</script>

<style scoped>
.value-bet-analysis {
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
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.header-content h2 .icon {
  width: 18px;
  height: 18px;
  color: #10b981;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

/* Tabs */
.tabs-bar {
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
  padding: 10px 16px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  color: #9ca3af;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(16, 185, 129, 0.05);
  color: #e5e7eb;
}

.tab-btn.active {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
  color: #10b981;
}

.tab-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

/* Tab Content */
.tab-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Action Button */
.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 20px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  color: #10b981;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon {
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

/* Scan Controls */
.scan-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  flex-wrap: wrap;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-group label {
  font-size: 12px;
  color: #9ca3af;
}

.control-value {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 10px;
  border-radius: 4px;
}

/* Value Bets List */
.value-bets-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.value-bet-card {
  padding: 16px;
  transition: all 0.2s;
}

.value-bet-card:hover {
  border-color: rgba(16, 185, 129, 0.3);
  background: #1a1f2e;
}

.bet-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.match-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.market-tag {
  font-size: 11px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 3px 8px;
  border-radius: 4px;
}

.bet-probs {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.prob-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px;
  background: #1c222f;
  border-radius: 6px;
}

.prob-label {
  font-size: 11px;
  color: #6b7280;
}

.prob-value {
  font-size: 14px;
  font-weight: 700;
}

.prob-value.predicted {
  color: #10b981;
}

.prob-value.implied {
  color: #9ca3af;
}

.prob-value.edge.high {
  color: #f59e0b;
}

.prob-value.edge.medium {
  color: #10b981;
}

.prob-value.edge.low {
  color: #6b7280;
}

.bet-recommendation {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #1c222f;
  border-radius: 6px;
}

.rec-label {
  font-size: 11px;
  color: #6b7280;
}

.rec-value {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
}

.bet-confidence {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-label {
  font-size: 11px;
  color: #6b7280;
  min-width: 40px;
}

.confidence-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 3px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.confidence-fill.high {
  background: linear-gradient(90deg, #10b981, #059669);
}

.confidence-fill.medium {
  background: linear-gradient(90deg, #f59e0b, #d97706);
}

.confidence-fill.low {
  background: linear-gradient(90deg, #6b7280, #4b5563);
}

.confidence-value {
  font-size: 12px;
  font-weight: 600;
  color: #e5e7eb;
  min-width: 36px;
  text-align: right;
}

/* No Data */
.no-data {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #6b7280;
}

.no-data svg {
  width: 20px;
  height: 20px;
  margin-bottom: 8px;
}

.no-data p {
  font-size: 13px;
}

/* Arbitrage Form */
.arbitrage-form {
  padding: 20px;
}

.arbitrage-form h3 {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.form-desc {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 16px;
}

.odds-inputs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-group label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.input-group input {
  padding: 8px 12px;
  background: #1c222f;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 6px;
  color: #e5e7eb;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.input-group input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.input-group input::placeholder {
  color: #4b5563;
}

.input-hint {
  font-size: 11px;
  color: #4b5563;
}

/* Arbitrage Result */
.arb-result {
  padding: 20px;
}

.arb-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-weight: 600;
}

.arb-status.positive {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.arb-status.negative {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.status-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.arb-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: #1c222f;
  border-radius: 6px;
}

.metric-label {
  font-size: 11px;
  color: #6b7280;
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  color: #e5e7eb;
}

.metric-value.profit {
  color: #10b981;
}

.optimal-stakes h4 {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 10px;
}

.stakes-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.stake-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px;
  background: #1c222f;
  border-radius: 6px;
}

.stake-label {
  font-size: 11px;
  color: #6b7280;
}

.stake-value {
  font-size: 16px;
  font-weight: 700;
  color: #10b981;
}

.arb-info p {
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 10px;
}

.implied-sum {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #1c222f;
  border-radius: 6px;
}

.implied-label {
  font-size: 12px;
  color: #6b7280;
}

.implied-value {
  font-size: 13px;
  font-weight: 600;
  color: #ef4444;
}

/* Kelly Form */
.kelly-form {
  padding: 20px;
}

.kelly-form h3 {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.kelly-inputs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

/* Kelly Result */
.kelly-result {
  padding: 20px;
}

.kelly-result h3 {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 16px;
}

.kelly-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.kelly-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: #1c222f;
  border-radius: 6px;
}

.kelly-metric .metric-label {
  font-size: 11px;
  color: #6b7280;
}

.kelly-metric .metric-value {
  font-size: 18px;
  font-weight: 700;
}

.kelly-metric .metric-value.positive {
  color: #10b981;
}

.kelly-metric .metric-value.negative {
  color: #ef4444;
}

.kelly-metric .metric-value.accent {
  color: #10b981;
}

/* Kelly Visual */
.kelly-visual {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.kelly-bar-container {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kelly-bar-label {
  font-size: 12px;
  color: #9ca3af;
  min-width: 60px;
}

.kelly-bar {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  overflow: hidden;
}

.kelly-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.kelly-bar-fill.full {
  background: linear-gradient(90deg, #10b981, #059669);
}

.kelly-bar-fill.fractional {
  background: linear-gradient(90deg, #3b82f6, #2563eb);
}

.kelly-bar-value {
  font-size: 12px;
  font-weight: 600;
  color: #e5e7eb;
  min-width: 56px;
  text-align: right;
}

/* Kelly Note */
.kelly-note {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: 6px;
  font-size: 12px;
  color: #f59e0b;
}

.note-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

/* Responsive */
@media (max-width: 600px) {
  .tabs-bar {
    flex-wrap: wrap;
  }

  .tab-btn {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    padding: 8px 10px;
  }

  .odds-inputs,
  .kelly-inputs {
    grid-template-columns: 1fr;
  }

  .arb-metrics,
  .kelly-metrics {
    grid-template-columns: 1fr;
  }

  .stakes-grid {
    grid-template-columns: 1fr;
  }

  .scan-controls {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
