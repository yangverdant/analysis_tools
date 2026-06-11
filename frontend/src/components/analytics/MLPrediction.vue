<template>
  <div class="ml-prediction">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>机器学习预测</h2>
        <p>AI模型比赛预测与特征分析</p>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab 1: 比赛预测 -->
    <div v-if="activeTab === 'prediction'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="predictionMatchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadPrediction"
        />
        <button class="action-btn" @click="loadPrediction" :disabled="predictionLoading">预测</button>
      </div>
      <div class="loading-state" v-if="predictionLoading">
        <div class="spinner"></div>
        <p>正在生成预测...</p>
      </div>
      <template v-else-if="predictionData">
        <div class="stats-grid">
          <div class="stat-card card">
            <div class="stat-label">预测结果</div>
            <div class="stat-value accent">{{ predictionData.prediction || predictionData.predicted_result || '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">置信度</div>
            <div class="stat-value" :class="confidenceClass(predictionData.confidence)">
              {{ predictionData.confidence != null ? (predictionData.confidence * 100).toFixed(1) + '%' : '--' }}
            </div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">模型名称</div>
            <div class="stat-value model-name">{{ predictionData.model_name || predictionData.model || '--' }}</div>
          </div>
        </div>
        <div v-if="predictionData.probabilities" class="detail-card card">
          <h3>概率分布</h3>
          <div class="probability-bars">
            <div class="prob-item">
              <div class="prob-header">
                <span class="prob-label">主胜</span>
                <span class="prob-value">{{ formatProb(predictionData.probabilities.home_win || predictionData.probabilities['1']) }}</span>
              </div>
              <div class="prob-bar-bg">
                <div
                  class="prob-bar home"
                  :style="{ width: probWidth(predictionData.probabilities.home_win || predictionData.probabilities['1']) }"
                ></div>
              </div>
            </div>
            <div class="prob-item">
              <div class="prob-header">
                <span class="prob-label">平局</span>
                <span class="prob-value">{{ formatProb(predictionData.probabilities.draw || predictionData.probabilities.X) }}</span>
              </div>
              <div class="prob-bar-bg">
                <div
                  class="prob-bar draw"
                  :style="{ width: probWidth(predictionData.probabilities.draw || predictionData.probabilities.X) }"
                ></div>
              </div>
            </div>
            <div class="prob-item">
              <div class="prob-header">
                <span class="prob-label">客胜</span>
                <span class="prob-value">{{ formatProb(predictionData.probabilities.away_win || predictionData.probabilities['2']) }}</span>
              </div>
              <div class="prob-bar-bg">
                <div
                  class="prob-bar away"
                  :style="{ width: probWidth(predictionData.probabilities.away_win || predictionData.probabilities['2']) }"
                ></div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="predictionData.score_prediction || predictionData.predicted_score" class="detail-card card">
          <h3>比分预测</h3>
          <div class="score-display">
            <span class="score-value">{{ predictionData.score_prediction || predictionData.predicted_score }}</span>
          </div>
        </div>
        <div v-if="predictionData.key_factors && predictionData.key_factors.length" class="detail-card card">
          <h3>关键因素</h3>
          <div class="factor-list">
            <div v-for="(f, idx) in predictionData.key_factors" :key="idx" class="factor-item">
              <span class="factor-rank">{{ idx + 1 }}</span>
              <span class="factor-text">{{ typeof f === 'string' ? f : f.name || f.factor || JSON.stringify(f) }}</span>
              <span v-if="f.weight || f.value" class="factor-weight">{{ f.weight || f.value }}</span>
            </div>
          </div>
        </div>
        <div v-if="predictionData.analysis" class="detail-card card">
          <h3>预测分析</h3>
          <div class="detail-block">
            <p>{{ typeof predictionData.analysis === 'string' ? predictionData.analysis : JSON.stringify(predictionData.analysis) }}</p>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入比赛ID进行预测</p>
      </div>
    </div>

    <!-- Tab 2: 模型对比 -->
    <div v-if="activeTab === 'comparison'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="comparisonMatchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadModelComparison"
        />
        <button class="action-btn" @click="loadModelComparison" :disabled="comparisonLoading">对比</button>
      </div>
      <div class="loading-state" v-if="comparisonLoading">
        <div class="spinner"></div>
        <p>正在对比模型...</p>
      </div>
      <template v-else-if="comparisonData">
        <div v-if="comparisonData.models && comparisonData.models.length" class="model-list">
          <div v-for="(m, idx) in comparisonData.models" :key="idx" class="model-card card">
            <div class="model-header">
              <span class="model-name">{{ m.model_name || m.name || 'Model ' + (idx + 1) }}</span>
              <span class="model-confidence" :class="confidenceClass(m.confidence || m.accuracy)">
                {{ m.confidence != null ? (m.confidence * 100).toFixed(1) + '%' : m.accuracy != null ? (m.accuracy * 100).toFixed(1) + '%' : '--' }}
              </span>
            </div>
            <div class="model-prediction">
              <span class="model-label">预测:</span>
              <span class="model-result">{{ m.prediction || m.predicted_result || '--' }}</span>
            </div>
            <div v-if="m.probabilities" class="mini-prob-bars">
              <div class="mini-prob">
                <span class="mini-label">主</span>
                <div class="mini-bar-bg"><div class="mini-bar home" :style="{ width: probWidth(m.probabilities.home_win || m.probabilities['1']) }"></div></div>
              </div>
              <div class="mini-prob">
                <span class="mini-label">平</span>
                <div class="mini-bar-bg"><div class="mini-bar draw" :style="{ width: probWidth(m.probabilities.draw || m.probabilities.X) }"></div></div>
              </div>
              <div class="mini-prob">
                <span class="mini-label">客</span>
                <div class="mini-bar-bg"><div class="mini-bar away" :style="{ width: probWidth(m.probabilities.away_win || m.probabilities['2']) }"></div></div>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="comparisonData.comparison" class="detail-card card">
          <h3>模型对比</h3>
          <div class="detail-block">
            <p>{{ typeof comparisonData.comparison === 'string' ? comparisonData.comparison : JSON.stringify(comparisonData.comparison, null, 2) }}</p>
          </div>
        </div>
        <div v-else class="detail-card card">
          <h3>模型对比结果</h3>
          <div class="detail-block">
            <p>{{ JSON.stringify(comparisonData, null, 2) }}</p>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入比赛ID对比模型</p>
      </div>
    </div>

    <!-- Tab 3: 特征分析 -->
    <div v-if="activeTab === 'features'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="featureMatchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadFeatureImportance"
        />
        <button class="action-btn" @click="loadFeatureImportance" :disabled="featureLoading">分析</button>
      </div>
      <div class="loading-state" v-if="featureLoading">
        <div class="spinner"></div>
        <p>正在分析特征重要性...</p>
      </div>
      <template v-else-if="featureData">
        <div v-if="featureData.features && featureData.features.length" class="detail-card card">
          <h3>特征重要性排名</h3>
          <div class="feature-list">
            <div v-for="(f, idx) in featureData.features" :key="idx" class="feature-item">
              <div class="feature-header">
                <span class="feature-rank">{{ idx + 1 }}</span>
                <span class="feature-name">{{ f.name || f.feature || 'Feature ' + (idx + 1) }}</span>
                <span class="feature-weight">{{ (f.weight || f.importance || f.value || 0).toFixed ? (f.weight || f.importance || f.value).toFixed(3) : f.weight || f.importance || f.value }}</span>
              </div>
              <div class="feature-bar-bg">
                <div
                  class="feature-bar"
                  :style="{ width: featureBarWidth(f.weight || f.importance || f.value) }"
                ></div>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="featureData.feature_weights && typeof featureData.feature_weights === 'object'" class="detail-card card">
          <h3>特征权重</h3>
          <div class="feature-list">
            <div v-for="(val, key) in featureData.feature_weights" :key="key" class="feature-item">
              <div class="feature-header">
                <span class="feature-name">{{ formatFeatureKey(key) }}</span>
                <span class="feature-weight">{{ typeof val === 'number' ? val.toFixed(3) : val }}</span>
              </div>
              <div class="feature-bar-bg">
                <div class="feature-bar" :style="{ width: featureBarWidth(val) }"></div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="featureData.top_features || featureData.summary" class="detail-card card">
          <h3>分析摘要</h3>
          <div v-if="featureData.top_features" class="tag-list">
            <span v-for="(f, idx) in featureData.top_features" :key="idx" class="tag">{{ typeof f === 'string' ? f : f.name || f.feature }}</span>
          </div>
          <div v-if="featureData.summary" class="detail-block">
            <p>{{ typeof featureData.summary === 'string' ? featureData.summary : JSON.stringify(featureData.summary) }}</p>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入比赛ID进行特征分析</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'MLPrediction',
  setup() {
    const activeTab = ref('prediction')
    const tabs = [
      { key: 'prediction', label: '比赛预测' },
      { key: 'comparison', label: '模型对比' },
      { key: 'features', label: '特征分析' }
    ]

    // Tab 1: 比赛预测
    const predictionMatchId = ref('')
    const predictionLoading = ref(false)
    const predictionData = ref(null)

    const loadPrediction = async () => {
      if (!predictionMatchId.value) return
      predictionLoading.value = true
      predictionData.value = null
      try {
        const res = await analysisAPI.getMLPrediction(predictionMatchId.value)
        predictionData.value = res.data || res || null
      } catch (e) {
        console.error('获取比赛预测失败:', e)
        predictionData.value = null
      } finally {
        predictionLoading.value = false
      }
    }

    // Tab 2: 模型对比
    const comparisonMatchId = ref('')
    const comparisonLoading = ref(false)
    const comparisonData = ref(null)

    const loadModelComparison = async () => {
      if (!comparisonMatchId.value) return
      comparisonLoading.value = true
      comparisonData.value = null
      try {
        const res = await analysisAPI.getModelComparison(comparisonMatchId.value)
        comparisonData.value = res.data || res || null
      } catch (e) {
        console.error('获取模型对比失败:', e)
        comparisonData.value = null
      } finally {
        comparisonLoading.value = false
      }
    }

    // Tab 3: 特征分析
    const featureMatchId = ref('')
    const featureLoading = ref(false)
    const featureData = ref(null)

    const loadFeatureImportance = async () => {
      if (!featureMatchId.value) return
      featureLoading.value = true
      featureData.value = null
      try {
        const res = await analysisAPI.getFeatureImportance(featureMatchId.value)
        featureData.value = res.data || res || null
      } catch (e) {
        console.error('获取特征重要性失败:', e)
        featureData.value = null
      } finally {
        featureLoading.value = false
      }
    }

    const formatProb = (val) => {
      if (val == null) return '--'
      return typeof val === 'number' ? (val * 100).toFixed(1) + '%' : val
    }

    const probWidth = (val) => {
      if (val == null) return '0%'
      const num = typeof val === 'number' ? val : parseFloat(val)
      return isNaN(num) ? '0%' : (num * 100) + '%'
    }

    const confidenceClass = (val) => {
      if (val == null) return ''
      const num = typeof val === 'number' ? val : parseFloat(val)
      if (isNaN(num)) return ''
      if (num >= 0.7) return 'level-low'
      if (num >= 0.4) return 'level-medium'
      return 'level-high'
    }

    const featureBarWidth = (val) => {
      if (val == null) return '0%'
      const num = typeof val === 'number' ? val : parseFloat(val)
      return isNaN(num) ? '0%' : Math.min(num * 100, 100) + '%'
    }

    const formatFeatureKey = (key) => {
      const map = {
        home_form: '主队状态',
        away_form: '客队状态',
        home_attack: '主队进攻',
        away_attack: '客队进攻',
        home_defense: '主队防守',
        away_defense: '客队防守',
        h2h: '历史交锋',
        home_xg: '主队xG',
        away_xg: '客队xG',
        home_possession: '主队控球率',
        away_possession: '客队控球率',
        fatigue: '疲劳因素',
        weather: '天气因素',
        home_advantage: '主场优势',
        league_form: '联赛表现',
        recent_goals: '近期进球',
        head_to_head: '历史交锋',
        xg_diff: 'xG差值',
        ranking_diff: '排名差'
      }
      return map[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    }

    return {
      activeTab, tabs,
      predictionMatchId, predictionLoading, predictionData, loadPrediction,
      comparisonMatchId, comparisonLoading, comparisonData, loadModelComparison,
      featureMatchId, featureLoading, featureData, loadFeatureImportance,
      formatProb, probWidth, confidenceClass, featureBarWidth, formatFeatureKey
    }
  }
}
</script>

<style scoped>
.ml-prediction {
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

.header {
  padding: 16px 20px;
}

.header-content h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
  margin-bottom: 4px;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

.tabs {
  display: flex;
  gap: 4px;
  background: #0a0d14;
  padding: 4px;
  border-radius: 10px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.tab-btn {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #9ca3af;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: #151922;
  color: #10b981;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.tab-btn:hover:not(.active) {
  color: #e5e7eb;
}

.input-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  align-items: center;
}

.text-input {
  flex: 1;
  padding: 8px 12px;
  background: #0a0d14;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.text-input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.text-input::placeholder {
  color: #6b7280;
}

.action-btn {
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

.action-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.stat-card {
  padding: 14px 16px;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #e5e7eb;
}

.stat-value.accent {
  color: #10b981;
}

.stat-value.model-name {
  font-size: 14px;
  color: #60a5fa;
}

.stat-value.level-high {
  color: #ef4444;
}

.stat-value.level-medium {
  color: #f59e0b;
}

.stat-value.level-low {
  color: #10b981;
}

/* 概率条 */
.detail-card {
  padding: 16px 20px;
}

.detail-card h3 {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.probability-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prob-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prob-header {
  display: flex;
  justify-content: space-between;
}

.prob-label {
  font-size: 13px;
  color: #9ca3af;
}

.prob-value {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
}

.prob-bar-bg {
  height: 8px;
  background: #0a0d14;
  border-radius: 4px;
  overflow: hidden;
}

.prob-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.prob-bar.home {
  background: #10b981;
}

.prob-bar.draw {
  background: #f59e0b;
}

.prob-bar.away {
  background: #60a5fa;
}

/* 比分显示 */
.score-display {
  text-align: center;
  padding: 20px;
}

.score-value {
  font-size: 32px;
  font-weight: 700;
  color: #10b981;
  letter-spacing: 4px;
}

/* 因素列表 */
.factor-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.factor-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.factor-rank {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 185, 129, 0.15);
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
  flex-shrink: 0;
}

.factor-text {
  flex: 1;
  font-size: 13px;
  color: #e5e7eb;
}

.factor-weight {
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
}

/* 模型列表 */
.model-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.model-card {
  padding: 16px;
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.model-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.model-confidence {
  font-size: 13px;
  font-weight: 600;
}

.model-confidence.level-high {
  color: #ef4444;
}

.model-confidence.level-medium {
  color: #f59e0b;
}

.model-confidence.level-low {
  color: #10b981;
}

.model-prediction {
  margin-bottom: 10px;
}

.model-label {
  font-size: 12px;
  color: #6b7280;
  margin-right: 6px;
}

.model-result {
  font-size: 13px;
  font-weight: 600;
  color: #10b981;
}

/* 迷你概率条 */
.mini-prob-bars {
  display: flex;
  gap: 12px;
}

.mini-prob {
  flex: 1;
}

.mini-label {
  font-size: 11px;
  color: #6b7280;
  display: block;
  margin-bottom: 3px;
}

.mini-bar-bg {
  height: 5px;
  background: #0a0d14;
  border-radius: 3px;
  overflow: hidden;
}

.mini-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.mini-bar.home {
  background: #10b981;
}

.mini-bar.draw {
  background: #f59e0b;
}

.mini-bar.away {
  background: #60a5fa;
}

/* 特征列表 */
.feature-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feature-item {
  padding: 6px 0;
}

.feature-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.feature-rank {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 185, 129, 0.15);
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  color: #10b981;
  margin-right: 8px;
}

.feature-name {
  font-size: 13px;
  color: #e5e7eb;
  flex: 1;
}

.feature-weight {
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
  min-width: 60px;
  text-align: right;
}

.feature-bar-bg {
  height: 6px;
  background: #0a0d14;
  border-radius: 3px;
  overflow: hidden;
}

.feature-bar {
  height: 100%;
  background: linear-gradient(90deg, #10b981, #059669);
  border-radius: 3px;
  transition: width 0.4s ease;
}

/* 标签列表 */
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  padding: 4px 12px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 20px;
  font-size: 12px;
  color: #10b981;
}

.detail-block {
  padding: 10px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.detail-block p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
  white-space: pre-wrap;
}

/* 加载/空状态 */
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

.empty-state {
  padding: 40px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
}

@media (max-width: 600px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .input-row {
    flex-wrap: wrap;
  }
  .mini-prob-bars {
    flex-direction: column;
    gap: 6px;
  }
}
</style>
