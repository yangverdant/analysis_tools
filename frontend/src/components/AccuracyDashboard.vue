<template>
  <div class="accuracy-dashboard">
    <!-- 闭环流程概览 -->
    <div class="cycle-overview">
      <div class="cycle-step" :class="{ active: currentStep === 'predict' }">
        <div class="step-icon">🎯</div>
        <div class="step-label">预测</div>
        <div class="step-desc">记录预测结果</div>
      </div>
      <div class="cycle-arrow">→</div>
      <div class="cycle-step" :class="{ active: currentStep === 'validate' }">
        <div class="step-icon">✅</div>
        <div class="step-label">验证</div>
        <div class="step-desc">对比实际赛果</div>
      </div>
      <div class="cycle-arrow">→</div>
      <div class="cycle-step" :class="{ active: currentStep === 'optimize' }">
        <div class="step-icon">🔧</div>
        <div class="step-label">优化</div>
        <div class="step-desc">调整分析权重</div>
      </div>
      <div class="cycle-arrow">→</div>
      <div class="cycle-step" :class="{ active: currentStep === 'predict' }">
        <div class="step-icon">🔄</div>
        <div class="step-label">迭代</div>
        <div class="step-desc">下次更准</div>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
      <button class="btn-primary" @click="runFullCycle" :disabled="loading">
        <span v-if="loading" class="spinner"></span>
        {{ loading ? '执行中...' : '执行完整闭环学习' }}
      </button>
      <button class="btn-secondary" @click="validatePredictions" :disabled="loading">验证赛果</button>
      <button class="btn-secondary" @click="logUpcoming" :disabled="loading">记录新预测</button>
      <button class="btn-secondary" @click="optimizeWeights" :disabled="loading">优化权重</button>
      <button class="btn-secondary" @click="runBacktest" :disabled="loading">回测收益</button>
      <button class="btn-secondary" @click="runWarmup" :disabled="loading">热启动校准</button>
      <span class="model-version" v-if="activeVersion">当前模型: {{ activeVersion }}</span>
    </div>

    <!-- 执行结果提示 -->
    <div v-if="cycleResult" class="cycle-result" :class="{ error: cycleResult.error }">
      <div v-for="(step, i) in cycleResult.steps" :key="i" class="step-result">
        <span class="step-status" :class="step.status">{{ stepStatusText(step) }}</span>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-value">{{ metrics.result_accuracy ?? '--' }}%</div>
        <div class="metric-label">胜平负准确率</div>
        <div class="metric-sub">共 {{ metrics.total || 0 }} 场验证</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{{ metrics.over_under_accuracy ?? '--' }}%</div>
        <div class="metric-label">大小球准确率</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{{ metrics.btts_accuracy ?? '--' }}%</div>
        <div class="metric-label">进球数准确率</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{{ metrics.avg_brier_score ?? '--' }}</div>
        <div class="metric-label">Brier Score</div>
        <div class="metric-sub">越低越好，0=完美</div>
      </div>
    </div>

    <!-- Oddsfe赔率基线 (229K) -->
    <div class="section" v-if="oddsfeBacktest">
      <h3>Pinnacle赔率基线 ({{ oddsfeBacktest.processed?.toLocaleString() }}场)</h3>
      <div class="baseline-grid">
        <div class="baseline-card">
          <div class="bl-value">{{ oddsfeBacktest.total?.accuracy }}%</div>
          <div class="bl-label">赔率argmax准确率</div>
        </div>
        <div class="baseline-card">
          <div class="bl-value">{{ oddsfeBacktest.total?.draw_rate }}%</div>
          <div class="bl-label">实际平局率</div>
        </div>
      </div>
      <div class="bucket-table" v-if="oddsfeBacktest.by_bucket">
        <div class="bucket-row header">
          <span>赔率区间</span><span>场次</span><span>准确率</span><span>平局率</span>
        </div>
        <div v-for="(info, bucket) in oddsfeBacktest.by_bucket" :key="bucket" class="bucket-row">
          <span class="bucket-name">{{ bucket }}</span>
          <span>{{ info.count?.toLocaleString() }}</span>
          <span :class="accuracyClass(info.accuracy)">{{ info.accuracy }}%</span>
          <span>{{ info.draw_rate }}%</span>
        </div>
      </div>
    </div>

    <!-- 维度准确率 -->
    <div class="section" v-if="dimensionAccuracy">
      <h3>各分析维度准确率</h3>
      <p class="section-desc">每个子分析器的方向预测与实际赛果的对齐率</p>
      <div class="dimension-grid">
        <div v-for="(info, dim) in dimensionAccuracy.dimensions" :key="dim" class="dimension-item">
          <div class="dim-header">
            <span class="dim-name">{{ dimensionLabel(dim) }}</span>
            <span class="dim-accuracy" :class="accuracyClass(info.accuracy)">
              {{ info.accuracy !== null ? info.accuracy + '%' : '--' }}
            </span>
          </div>
          <div class="dim-bar">
            <div class="dim-bar-fill" :style="{ width: barWidth(info.accuracy) }"
                 :class="accuracyClass(info.accuracy)"></div>
          </div>
          <div class="dim-detail">
            {{ info.aligned }}/{{ info.total }} 对齐
            <span v-if="!info.sufficient_data" class="insufficient">数据不足</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 按置信度分组 -->
    <div class="section" v-if="metrics.by_confidence && Object.keys(metrics.by_confidence).length">
      <h3>按置信度分组</h3>
      <div class="confidence-grid">
        <div v-for="(info, level) in metrics.by_confidence" :key="level" class="confidence-item">
          <div class="conf-level" :class="level">{{ confidenceLabel(level) }}</div>
          <div class="conf-stats">
            <span class="conf-accuracy">{{ info.accuracy }}%</span>
            <span class="conf-detail">{{ info.correct }}/{{ info.total }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 翻车归因 -->
    <div class="section" v-if="attributionStats && attributionStats.length">
      <h3>翻车归因分析</h3>
      <p class="section-desc">预测失败的原因分类统计</p>
      <div class="attribution-grid">
        <div v-for="attr in attributionStats" :key="attr.level" class="attribution-item">
          <div class="attr-header">
            <span class="attr-level" :class="attr.level">{{ attributionLabel(attr.level) }}</span>
            <span class="attr-count">{{ attr.count }}场</span>
          </div>
          <div class="attr-bar">
            <div class="attr-bar-fill" :class="attr.level" :style="{ width: attr.barWidth }"></div>
          </div>
          <div class="attr-pct">{{ attr.percentage }}%</div>
        </div>
      </div>
    </div>

    <!-- 准确率趋势 -->
    <div class="section" v-if="accuracyTrend.length">
      <h3>准确率趋势</h3>
      <div class="trend-chart">
        <div v-for="day in accuracyTrend" :key="day.date" class="trend-bar-group">
          <div class="trend-bar" :class="{ positive: day.accuracy >= 50, negative: day.accuracy < 50 }"
               :style="{ height: Math.max(day.accuracy, 5) + '%' }"
               :title="`${day.date}: ${day.accuracy}% (${day.correct}/${day.total})`">
          </div>
          <div class="trend-date">{{ day.date.slice(5) }}</div>
          <div class="trend-pct">{{ day.accuracy }}%</div>
        </div>
      </div>
    </div>

    <!-- 权重历史 -->
    <div class="section" v-if="weightHistory.length">
      <h3>权重版本历史</h3>
      <div class="weight-table">
        <table>
          <thead>
            <tr>
              <th>版本</th>
              <th>Elo</th>
              <th>Poisson</th>
              <th>H2H</th>
              <th>Form</th>
              <th>主客</th>
              <th>动机</th>
              <th>新闻</th>
              <th>样本</th>
              <th>准确率</th>
              <th>Brier</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in weightHistory" :key="w.version" :class="{ active: w.is_active }">
              <td class="version-cell">{{ w.version }} <span v-if="w.is_active" class="active-badge">当前</span></td>
              <td>{{ (w.elo_weight * 100).toFixed(1) }}%</td>
              <td>{{ (w.poisson_weight * 100).toFixed(1) }}%</td>
              <td>{{ (w.h2h_weight * 100).toFixed(1) }}%</td>
              <td>{{ (w.form_weight * 100).toFixed(1) }}%</td>
              <td>{{ (w.home_away_weight * 100).toFixed(1) }}%</td>
              <td>{{ (w.motivation_weight * 100).toFixed(1) }}%</td>
              <td>{{ (w.news_factors_weight * 100).toFixed(1) }}%</td>
              <td>{{ w.sample_size }}</td>
              <td>{{ w.accuracy_rate ?? '--' }}%</td>
              <td>{{ w.brier_score_avg ?? '--' }}</td>
              <td>
                <button v-if="!w.is_active" class="btn-small" @click="rollbackWeights(w.version)"
                        :disabled="loading">回滚</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 回测收益面板 -->
    <div class="section" v-if="backtestResult">
      <h3>回测收益报告</h3>
      <div v-if="backtestResult.error" class="backtest-error">{{ backtestResult.error }}</div>
      <div v-else-if="backtestResult.empty" class="backtest-empty">无回测数据</div>
      <template v-else>
        <div class="backtest-summary">
          <div class="bt-card">
            <div class="bt-value" :class="backtestResult.summary.roi >= 0 ? 'positive' : 'negative'">
              {{ backtestResult.summary.roi >= 0 ? '+' : '' }}{{ backtestResult.summary.roi?.toFixed(1) }}%
            </div>
            <div class="bt-label">ROI</div>
          </div>
          <div class="bt-card">
            <div class="bt-value">{{ backtestResult.summary.total_matches }}场</div>
            <div class="bt-label">总场次</div>
          </div>
          <div class="bt-card">
            <div class="bt-value">{{ (backtestResult.summary.win_rate * 100)?.toFixed(1) }}%</div>
            <div class="bt-label">胜率</div>
          </div>
          <div class="bt-card">
            <div class="bt-value" :class="backtestResult.summary.total_profit >= 0 ? 'positive' : 'negative'">
              {{ backtestResult.summary.total_profit >= 0 ? '+' : '' }}{{ backtestResult.summary.total_profit?.toFixed(0) }}元
            </div>
            <div class="bt-label">总盈亏</div>
          </div>
        </div>
        <div class="backtest-detail" v-if="backtestResult.per_match?.length">
          <table>
            <thead>
              <tr>
                <th>比赛</th>
                <th>推荐</th>
                <th>实际</th>
                <th>赔率</th>
                <th>投注</th>
                <th>盈亏</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in backtestResult.per_match" :key="m.match_id">
                <td>{{ m.home_name || '主' }} vs {{ m.away_name || '客' }}</td>
                <td>{{ resultLabel(m.predicted_result) }}</td>
                <td>{{ resultLabel(m.actual_result) }}</td>
                <td>{{ m.odds_used?.toFixed(2) }}</td>
                <td>{{ m.stake?.toFixed(0) }}元</td>
                <td :class="m.profit >= 0 ? 'positive' : 'negative'">
                  {{ m.profit >= 0 ? '+' : '' }}{{ m.profit?.toFixed(0) }}元
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <!-- 赔率校准面板 -->
    <div class="section" v-if="calibration && Object.keys(calibration).length">
      <h3>赔率校准 (229K历史数据)</h3>
      <div class="calibration-grid">
        <div v-for="(stats, bucket) in calibration" :key="bucket" class="cal-item">
          <div class="cal-bucket">{{ bucket }}</div>
          <div class="cal-accuracy">{{ (stats.accuracy * 100).toFixed(1) }}%</div>
          <div class="cal-draw">平局率 {{ (stats.draw_rate * 100).toFixed(1) }}%</div>
          <div class="cal-samples">{{ stats.sample_size }}场</div>
        </div>
      </div>
    </div>

    <!-- 热启动结果 -->
    <div class="section" v-if="warmupResult">
      <h3>热启动校准结果</h3>
      <div v-if="warmupResult.error" class="backtest-error">{{ warmupResult.error }}</div>
      <template v-else>
        <div class="backtest-summary">
          <div class="bt-card">
            <div class="bt-value">{{ (warmupResult.odds_accuracy * 100).toFixed(1) }}%</div>
            <div class="bt-label">赔率基线准确率</div>
          </div>
          <div class="bt-card">
            <div class="bt-value">{{ warmupResult.sample_size?.toLocaleString() }}</div>
            <div class="bt-label">校准样本</div>
          </div>
          <div class="bt-card">
            <div class="bt-value">{{ warmupResult.mode }}</div>
            <div class="bt-label">推荐模式</div>
          </div>
        </div>
      </template>
    </div>

    <!-- 投注ROI -->
    <div class="section" v-if="betROI">
      <h3>投注追踪 <button class="btn-tiny" @click="settleBets" :disabled="loading">结算</button></h3>
      <div class="roi-grid" v-if="betROI.summary">
        <div v-for="(stats, period) in betROI.summary" :key="period" class="roi-card">
          <div class="roi-period">{{ period }}</div>
          <div class="roi-value" :class="stats.total_profit >= 0 ? 'positive' : 'negative'">
            {{ stats.total_profit >= 0 ? '+' : '' }}{{ stats.total_profit }}元
          </div>
          <div class="roi-detail">
            ROI {{ stats.roi }}% | {{ stats.wins }}胜{{ stats.losses }}负
            <span v-if="stats.pending > 0" class="pending-count">({{ stats.pending }}待结算)</span>
          </div>
          <div class="roi-stake">投注{{ stats.total_stake }}元</div>
        </div>
      </div>
      <div class="bet-list" v-if="betROI.recent && betROI.recent.length">
        <div v-for="bet in betROI.recent.slice(0, 10)" :key="bet.id" class="bet-item">
          <span class="bet-match">{{ bet.home_team_cn || '主' }} vs {{ bet.away_team_cn || '客' }}</span>
          <span class="bet-sel">{{ { '3': '主胜', '1': '平', '0': '客胜' }[bet.selection] || bet.selection }}</span>
          <span class="bet-odds">@{{ bet.odds?.toFixed(2) }}</span>
          <span :class="['bet-result', bet.result]">{{ { 'win': '赢', 'lose': '输', 'pending': '待' }[bet.result] }}</span>
          <span class="bet-profit" :class="bet.profit >= 0 ? 'positive' : 'negative'">
            {{ bet.result !== 'pending' ? (bet.profit >= 0 ? '+' : '') + bet.profit?.toFixed(0) + '元' : '-' }}
          </span>
        </div>
      </div>
    </div>

    <!-- 待验证列表 -->
    <div class="section" v-if="pendingValidations.length">
      <h3>待验证预测 ({{ pendingValidations.length }})</h3>
      <div class="pending-list">
        <div v-for="p in pendingValidations.slice(0, 20)" :key="p.match_id" class="pending-item">
          <div class="pending-match">
            <span class="team">{{ p.home_name || '主队' }}</span>
            <span class="vs">vs</span>
            <span class="team">{{ p.away_name || '客队' }}</span>
          </div>
          <div class="pending-info">
            <span class="predicted">预测: {{ resultLabel(p.predicted_result) }}</span>
            <span class="actual">实际: {{ p.home_goals }}-{{ p.away_goals }}</span>
          </div>
        </div>
        <div v-if="pendingValidations.length > 20" class="more">
          还有 {{ pendingValidations.length - 20 }} 条...
        </div>
      </div>
    </div>

    <!-- 无数据提示 -->
    <div v-if="!metrics.total && !loading" class="empty-state">
      <div class="empty-icon">📊</div>
      <div class="empty-text">暂无验证数据</div>
      <div class="empty-hint">点击"执行完整闭环学习"开始收集预测数据</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { trackingAPI } from '../api'

const loading = ref(false)
const currentStep = ref('')
const metrics = ref({})
const dimensionAccuracy = ref(null)
const weightHistory = ref([])
const pendingValidations = ref([])
const activeVersion = ref('')
const cycleResult = ref(null)
const backtestResult = ref(null)
const attributionStats = ref([])
const accuracyTrend = ref([])
const warmupResult = ref(null)
const calibration = ref(null)
const betROI = ref(null)
const oddsfeBacktest = ref(null)

onMounted(() => {
  loadAll()
})

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([
      loadMetrics(),
      loadDimensionAccuracy(),
      loadWeightHistory(),
      loadPendingValidations(),
      loadAttributionStats(),
      loadAccuracyTrend(),
      loadCalibration(),
      loadBetROI(),
      loadOddsfeBacktest()
    ])
  } finally {
    loading.value = false
  }
}

async function loadMetrics() {
  try {
    const data = await trackingAPI.getAccuracy(null, 90)
    metrics.value = data
  } catch (e) {
    console.error('加载准确率失败:', e)
  }
}

async function loadDimensionAccuracy() {
  try {
    const data = await trackingAPI.getDimensionAccuracy()
    dimensionAccuracy.value = data
  } catch (e) {
    console.error('加载维度准确率失败:', e)
  }
}

async function loadWeightHistory() {
  try {
    const data = await trackingAPI.getWeightHistory()
    weightHistory.value = data.history || []
    const active = weightHistory.value.find(w => w.is_active)
    if (active) activeVersion.value = active.version
  } catch (e) {
    console.error('加载权重历史失败:', e)
  }
}

async function loadPendingValidations() {
  try {
    const data = await trackingAPI.getPendingValidations()
    pendingValidations.value = data.pending || []
  } catch (e) {
    console.error('加载待验证列表失败:', e)
  }
}

async function runFullCycle() {
  loading.value = true
  currentStep.value = 'validate'
  cycleResult.value = null
  try {
    const data = await trackingAPI.runFullCycle()
    cycleResult.value = data
    await loadAll()
  } catch (e) {
    cycleResult.value = { error: true, steps: [{ step: 'error', status: 'error', error: e.message }] }
  } finally {
    loading.value = false
    currentStep.value = ''
  }
}

async function validatePredictions() {
  loading.value = true
  try {
    const data = await trackingAPI.validatePredictions()
    alert(`验证完成: ${data.validated_count} 场比赛`)
    await loadAll()
  } catch (e) {
    alert('验证失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function logUpcoming() {
  loading.value = true
  try {
    const data = await trackingAPI.logUpcoming(7)
    alert(`已记录: ${data.logged} 场, 失败: ${data.errors} 场`)
    await loadAll()
  } catch (e) {
    alert('记录失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function optimizeWeights() {
  loading.value = true
  try {
    const data = await trackingAPI.optimizeWeights()
    if (data.success) {
      alert(`权重优化成功: ${data.old_version} → ${data.new_version}`)
    } else {
      alert(`优化跳过: ${data.reason}`)
    }
    await loadAll()
  } catch (e) {
    alert('优化失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function rollbackWeights(version) {
  if (!confirm(`确认回滚到版本 ${version}?`)) return
  loading.value = true
  try {
    const data = await trackingAPI.rollbackWeights(version)
    if (data.success) {
      alert(`已回滚到 ${version}`)
      await loadAll()
    }
  } catch (e) {
    alert('回滚失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function loadAttributionStats() {
  try {
    const resp = await fetch('/api/validation/attribution')
    const data = await resp.json()
    if (data.stats) {
      attributionStats.value = data.stats
    }
  } catch (e) {
    // Silently fail — attribution data is optional
  }
}

async function loadAccuracyTrend() {
  try {
    const resp = await fetch('/api/validation/trend?days=30')
    const data = await resp.json()
    if (data.trend) {
      accuracyTrend.value = data.trend
    }
  } catch (e) {
    // Silently fail
  }
}

function attributionLabel(level) {
  const labels = {
    bad_luck: '运气差',
    close_match: '势均力敌',
    correction_wrong: '修正方向错',
    market_wrong: '市场信号错',
    intel_missing: '情报缺失'
  }
  return labels[level] || level
}

function dimensionLabel(dim) {
  const labels = {
    elo: 'Elo评级', poisson: '泊松模型', h2h: '历史交锋',
    form: '近期状态', home_away: '主客场', motivation: '比赛动机',
    news_factors: '新闻因素'
  }
  return labels[dim] || dim
}

function confidenceLabel(level) {
  const labels = { high: '高', medium: '中', low: '低' }
  return labels[level] || level
}

function resultLabel(result) {
  const labels = { home_win: '主胜', draw: '平', away_win: '客胜', '3': '主胜', '1': '平', '0': '客胜' }
  return labels[result] || result
}

function accuracyClass(accuracy) {
  if (accuracy === null || accuracy === undefined) return 'unknown'
  if (accuracy >= 55) return 'good'
  if (accuracy >= 45) return 'neutral'
  return 'bad'
}

function barWidth(accuracy) {
  if (accuracy === null || accuracy === undefined) return '50%'
  return Math.min(Math.max(accuracy, 5), 100) + '%'
}

function stepStatusText(step) {
  const names = { validate: '验证赛果', optimize: '优化权重', log_new_predictions: '记录新预测', error: '执行出错' }
  return `${names[step.step] || step.step}: ${step.status === 'success' ? '成功' : step.status === 'skipped' ? '跳过' : '失败'}`
}

async function runBacktest() {
  loading.value = true
  try {
    const resp = await fetch('/api/backtest?days=30&stake=100')
    const data = await resp.json()
    if (data.error) {
      backtestResult.value = { error: data.error }
    } else if (data.summary && data.summary.total_matches > 0) {
      backtestResult.value = data
    } else {
      backtestResult.value = { empty: true }
    }
  } catch (e) {
    backtestResult.value = { error: e.message }
  } finally {
    loading.value = false
  }
}

async function runWarmup() {
  loading.value = true
  try {
    const resp = await fetch('/api/warmup', { method: 'POST' })
    const data = await resp.json()
    warmupResult.value = data
    if (data.odds_calibration) {
      calibration.value = data.odds_calibration
    }
    loadAll()
  } catch (e) {
    warmupResult.value = { error: e.message }
  } finally {
    loading.value = false
  }
}

async function loadCalibration() {
  try {
    const resp = await fetch('/api/warmup/status')
    const data = await resp.json()
    if (data.calibration && Object.keys(data.calibration).length) {
      calibration.value = data.calibration
    }
  } catch (e) {
    // Silently fail
  }
}

async function loadBetROI() {
  try {
    const resp = await fetch('/api/bets/roi')
    const data = await resp.json()
    if (!data.error) {
      betROI.value = data
    }
  } catch (e) {
    // Silently fail
  }
}

async function loadOddsfeBacktest() {
  try {
    const resp = await fetch('/api/oddsfe-backtest')
    const data = await resp.json()
    if (!data.error) {
      oddsfeBacktest.value = data
    }
  } catch (e) {
    // Silently fail
  }
}

async function settleBets() {
  loading.value = true
  try {
    const resp = await fetch('/api/bets/settle', { method: 'POST' })
    const data = await resp.json()
    await loadBetROI()
  } catch (e) {
    // Silently fail
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.accuracy-dashboard {
  padding: 16px;
}

/* 闭环流程概览 */
.cycle-overview {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 20px;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 12px;
  margin-bottom: 20px;
}
.cycle-step {
  text-align: center;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(255,255,255,0.05);
  min-width: 80px;
  transition: all 0.3s;
}
.cycle-step.active {
  background: rgba(64, 156, 255, 0.2);
  box-shadow: 0 0 12px rgba(64, 156, 255, 0.3);
}
.step-icon { font-size: 24px; margin-bottom: 4px; }
.step-label { font-size: 14px; font-weight: 600; color: #e0e0e0; }
.step-desc { font-size: 11px; color: #888; margin-top: 2px; }
.cycle-arrow { font-size: 20px; color: #555; }

/* 操作栏 */
.action-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.btn-primary {
  padding: 8px 20px;
  background: linear-gradient(135deg, #409cff, #6366f1);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  padding: 6px 14px;
  background: rgba(255,255,255,0.08);
  color: #ccc;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-secondary:hover:not(:disabled) { background: rgba(255,255,255,0.15); }
.btn-small {
  padding: 2px 8px;
  background: rgba(255,255,255,0.08);
  color: #aaa;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
}
.btn-small:hover:not(:disabled) { background: rgba(255,255,255,0.15); }
.model-version {
  font-size: 12px;
  color: #888;
  margin-left: auto;
  background: rgba(255,255,255,0.05);
  padding: 4px 10px;
  border-radius: 4px;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top: 2px solid white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 执行结果 */
.cycle-result {
  padding: 12px;
  background: rgba(64, 156, 255, 0.1);
  border: 1px solid rgba(64, 156, 255, 0.2);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
}
.cycle-result.error {
  background: rgba(255, 80, 80, 0.1);
  border-color: rgba(255, 80, 80, 0.2);
}
.step-result { padding: 2px 0; }
.step-status.success { color: #4ade80; }
.step-status.skipped { color: #fbbf24; }
.step-status.error { color: #f87171; }

/* 核心指标 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.metric-card {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}
.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: #409cff;
}
.metric-label {
  font-size: 13px;
  color: #aaa;
  margin-top: 4px;
}
.metric-sub {
  font-size: 11px;
  color: #666;
  margin-top: 2px;
}

/* 维度准确率 */
.section {
  margin-bottom: 24px;
}
.section h3 {
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 4px;
}
.section-desc {
  font-size: 12px;
  color: #777;
  margin-bottom: 12px;
}
.dimension-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.dimension-item {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 12px;
}
.dim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.dim-name { font-size: 13px; color: #ccc; font-weight: 500; }
.dim-accuracy { font-size: 14px; font-weight: 700; }
.dim-accuracy.good { color: #4ade80; }
.dim-accuracy.neutral { color: #fbbf24; }
.dim-accuracy.bad { color: #f87171; }
.dim-accuracy.unknown { color: #666; }
.dim-bar {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}
.dim-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s;
}
.dim-bar-fill.good { background: #4ade80; }
.dim-bar-fill.neutral { background: #fbbf24; }
.dim-bar-fill.bad { background: #f87171; }
.dim-bar-fill.unknown { background: #555; }
.dim-detail { font-size: 11px; color: #666; }
.insufficient { color: #f59e0b; margin-left: 6px; }

/* 按置信度 */
.confidence-grid {
  display: flex;
  gap: 12px;
}
.confidence-item {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 12px 16px;
  text-align: center;
  min-width: 100px;
}
.conf-level {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}
.conf-level.high { color: #4ade80; }
.conf-level.medium { color: #fbbf24; }
.conf-level.low { color: #f87171; }
.conf-accuracy { font-size: 20px; font-weight: 700; color: #e0e0e0; }
.conf-detail { font-size: 12px; color: #777; }

/* 权重表 */
.weight-table {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
th, td {
  padding: 8px 10px;
  text-align: center;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
th {
  color: #888;
  font-weight: 500;
  font-size: 11px;
}
td { color: #bbb; }
tr.active {
  background: rgba(64, 156, 255, 0.08);
}
.version-cell { font-weight: 600; color: #ddd; white-space: nowrap; }
.active-badge {
  font-size: 10px;
  background: #409cff;
  color: white;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 4px;
  font-weight: 400;
}

/* 翻车归因 */
.attribution-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}
.attribution-item {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 10px;
}
.attr-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.attr-level { font-size: 13px; font-weight: 600; }
.attr-level.bad_luck { color: #888; }
.attr-level.close_match { color: #fbbf24; }
.attr-level.correction_wrong { color: #f87171; }
.attr-level.market_wrong { color: #60a5fa; }
.attr-level.intel_missing { color: #a78bfa; }
.attr-count { font-size: 14px; font-weight: 700; color: #ddd; }
.attr-bar {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}
.attr-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s;
}
.attr-bar-fill.bad_luck { background: #888; }
.attr-bar-fill.close_match { background: #fbbf24; }
.attr-bar-fill.correction_wrong { background: #f87171; }
.attr-bar-fill.market_wrong { background: #60a5fa; }
.attr-bar-fill.intel_missing { background: #a78bfa; }
.attr-pct { font-size: 11px; color: #666; }

/* 准确率趋势 */
.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 120px;
  padding: 8px 0;
}
.trend-bar-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 0;
}
.trend-bar {
  width: 100%;
  max-width: 30px;
  border-radius: 3px 3px 0 0;
  transition: height 0.5s;
}
.trend-bar.positive { background: #4ade80; }
.trend-bar.negative { background: #f87171; }
.trend-date { font-size: 10px; color: #666; margin-top: 2px; }
.trend-pct { font-size: 10px; color: #888; }

/* 待验证 */
.pending-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}
.pending-item {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 6px;
  padding: 10px;
}
.pending-match {
  font-size: 13px;
  color: #ddd;
  margin-bottom: 4px;
}
.pending-match .vs { color: #666; margin: 0 6px; }
.pending-info {
  font-size: 11px;
  color: #888;
}
.predicted { margin-right: 12px; }
.actual { color: #4ade80; }
.more { font-size: 12px; color: #666; text-align: center; padding: 8px; }

/* 无数据 */
.empty-state {
  text-align: center;
  padding: 40px;
  color: #666;
}
.empty-icon { font-size: 48px; margin-bottom: 8px; }
.empty-text { font-size: 16px; color: #888; margin-bottom: 4px; }
.empty-hint { font-size: 13px; }

/* 回测面板 */
.backtest-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.bt-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}
.bt-value {
  font-size: 20px;
  font-weight: 700;
  color: #e0e0e0;
}
.bt-value.positive { color: #4ade80; }
.bt-value.negative { color: #f87171; }
.bt-label { font-size: 12px; color: #888; margin-top: 2px; }
.backtest-error { color: #f87171; font-size: 13px; }
.backtest-empty { color: #888; font-size: 13px; }
.backtest-detail { overflow-x: auto; }

/* 赔率校准 */
.calibration-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}
.cal-item {
  background: #1a2332;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}
.cal-bucket { font-size: 13px; color: #94a3b8; margin-bottom: 4px; }
.cal-accuracy { font-size: 20px; font-weight: 700; color: #22d3ee; }
.cal-draw { font-size: 11px; color: #fbbf24; margin-top: 2px; }
.cal-samples { font-size: 11px; color: #64748b; margin-top: 2px; }
@media (max-width: 768px) {
  .calibration-grid { grid-template-columns: repeat(3, 1fr); }
}

/* 投注ROI */
.roi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.roi-card {
  background: #1a2332;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}
.roi-period { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.roi-value { font-size: 22px; font-weight: 700; }
.roi-value.positive { color: #4ade80; }
.roi-value.negative { color: #f87171; }
.roi-detail { font-size: 11px; color: #cbd5e1; margin-top: 4px; }
.roi-stake { font-size: 11px; color: #64748b; margin-top: 2px; }
.pending-count { color: #fbbf24; }
.bet-list { display: flex; flex-direction: column; gap: 4px; }
.bet-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #0f172a;
  border-radius: 6px;
  font-size: 12px;
}
.bet-match { flex: 1; color: #e2e8f0; }
.bet-sel { color: #94a3b8; }
.bet-odds { color: #64748b; }
.bet-result { font-weight: 600; width: 20px; text-align: center; }
.bet-result.win { color: #4ade80; }
.bet-result.lose { color: #f87171; }
.bet-result.pending { color: #fbbf24; }
.bet-profit { width: 50px; text-align: right; }
.bet-profit.positive { color: #4ade80; }
.bet-profit.negative { color: #f87171; }
.btn-tiny {
  font-size: 11px;
  padding: 2px 8px;
  background: #334155;
  border: 1px solid #475569;
  border-radius: 4px;
  color: #e2e8f0;
  cursor: pointer;
  margin-left: 8px;
}
.btn-tiny:hover { background: #475569; }

/* Oddsfe baseline */
.baseline-grid {
  display: grid; grid-template-columns: repeat(2, 1fr);
  gap: 10px; margin-bottom: 12px;
}
.baseline-card {
  background: #1a2332; border-radius: 8px; padding: 12px; text-align: center;
}
.bl-value { font-size: 22px; font-weight: 700; color: #e2e8f0; }
.bl-label { font-size: 11px; color: #94a3b8; margin-top: 4px; }
.bucket-table { font-size: 12px; }
.bucket-row {
  display: grid; grid-template-columns: 80px 1fr 1fr 1fr;
  gap: 4px; padding: 6px 8px; border-radius: 4px;
}
.bucket-row.header { color: #64748b; font-weight: 600; }
.bucket-row:not(.header) { background: #0f172a; margin-bottom: 2px; }
.bucket-name { color: #94a3b8; font-family: monospace; }

@media (max-width: 768px) {
  .roi-grid { grid-template-columns: 1fr; }
}
.positive { color: #4ade80; }
.negative { color: #f87171; }

@media (max-width: 768px) {
  .metrics-grid { grid-template-columns: repeat(2, 1fr); }
  .dimension-grid { grid-template-columns: repeat(2, 1fr); }
  .confidence-grid { flex-wrap: wrap; }
  .backtest-summary { grid-template-columns: repeat(2, 1fr); }
}
</style>
