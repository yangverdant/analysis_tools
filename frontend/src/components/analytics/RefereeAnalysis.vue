<template>
  <div class="referee-analysis">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>裁判分析</h2>
        <p>裁判执法风格与比赛影响分析</p>
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

    <!-- 裁判列表 -->
    <div v-if="activeTab === 'list'" class="tab-content">
      <div class="loading-state" v-if="listLoading">
        <div class="spinner"></div>
        <p>正在加载裁判列表...</p>
      </div>
      <div v-else-if="refereeList.length > 0" class="data-table-wrap card">
        <table class="data-table">
          <thead>
            <tr>
              <th>裁判姓名</th>
              <th>执法场次</th>
              <th>场均出牌</th>
              <th>主场胜率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(ref, idx) in refereeList" :key="idx" @click="selectReferee(ref.name || ref.referee_name)">
              <td class="name-cell">{{ ref.name || ref.referee_name }}</td>
              <td>{{ ref.matches || ref.total_matches || '--' }}</td>
              <td>{{ ref.avg_cards != null ? ref.avg_cards.toFixed(2) : '--' }}</td>
              <td>{{ ref.home_win_rate != null ? (ref.home_win_rate * 100).toFixed(1) + '%' : '--' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state card">
        <p>暂无裁判数据</p>
      </div>
    </div>

    <!-- 裁判详情 -->
    <div v-if="activeTab === 'detail'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="refereeName"
          placeholder="输入裁判姓名"
          class="text-input"
          @keyup.enter="loadRefereeStats"
        />
        <button class="action-btn" @click="loadRefereeStats" :disabled="detailLoading">查询</button>
      </div>
      <div class="loading-state" v-if="detailLoading">
        <div class="spinner"></div>
        <p>正在加载裁判详情...</p>
      </div>
      <template v-else-if="refereeStats">
        <div class="stats-grid">
          <div class="stat-card card">
            <div class="stat-label">执法场次</div>
            <div class="stat-value">{{ refereeStats.total_matches || refereeStats.matches || '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">场均黄牌</div>
            <div class="stat-value">{{ refereeStats.avg_yellow_cards != null ? refereeStats.avg_yellow_cards.toFixed(2) : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">场均红牌</div>
            <div class="stat-value">{{ refereeStats.avg_red_cards != null ? refereeStats.avg_red_cards.toFixed(2) : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">主场胜率</div>
            <div class="stat-value accent">{{ refereeStats.home_win_rate != null ? (refereeStats.home_win_rate * 100).toFixed(1) + '%' : '--' }}</div>
          </div>
        </div>
        <div v-if="refereeStats.style_analysis" class="detail-card card">
          <h3>执法风格</h3>
          <p>{{ refereeStats.style_analysis }}</p>
        </div>
        <div v-if="refereeStats.card_trends && refereeStats.card_trends.length" class="detail-card card">
          <h3>出牌趋势</h3>
          <div class="trend-list">
            <div v-for="(trend, idx) in refereeStats.card_trends" :key="idx" class="trend-item">
              <span class="trend-label">{{ trend.season || trend.period || `第${idx + 1}期` }}</span>
              <span class="trend-value">黄牌 {{ trend.yellow_cards || trend.yellows || '--' }} / 红牌 {{ trend.red_cards || trend.reds || '--' }}</span>
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="refereeName && !detailLoading" class="empty-state card">
        <p>未找到该裁判数据</p>
      </div>
    </div>

    <!-- 比赛裁判影响 -->
    <div v-if="activeTab === 'impact'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="impactMatchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadRefereeImpact"
        />
        <button class="action-btn" @click="loadRefereeImpact" :disabled="impactLoading">查询</button>
      </div>
      <div class="loading-state" v-if="impactLoading">
        <div class="spinner"></div>
        <p>正在分析裁判影响...</p>
      </div>
      <template v-else-if="refereeImpact">
        <div class="detail-card card">
          <h3>裁判影响分析</h3>
          <div class="impact-content">
            <div v-if="refereeImpact.referee_name" class="impact-row">
              <span class="impact-label">执法裁判</span>
              <span class="impact-value">{{ refereeImpact.referee_name }}</span>
            </div>
            <div v-if="refereeImpact.impact_score != null" class="impact-row">
              <span class="impact-label">影响评分</span>
              <span class="impact-value accent">{{ refereeImpact.impact_score }}</span>
            </div>
            <div v-if="refereeImpact.analysis" class="impact-analysis">
              <p>{{ refereeImpact.analysis }}</p>
            </div>
            <div v-if="refereeImpact.card_prediction" class="impact-row">
              <span class="impact-label">出牌预测</span>
              <span class="impact-value">{{ refereeImpact.card_prediction }}</span>
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="impactMatchId && !impactLoading" class="empty-state card">
        <p>未找到该比赛的裁判影响数据</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'RefereeAnalysis',
  setup() {
    const activeTab = ref('list')
    const tabs = [
      { key: 'list', label: '裁判列表' },
      { key: 'detail', label: '裁判详情' },
      { key: 'impact', label: '比赛裁判影响' }
    ]

    // 裁判列表
    const listLoading = ref(false)
    const refereeList = ref([])

    // 裁判详情
    const refereeName = ref('')
    const detailLoading = ref(false)
    const refereeStats = ref(null)

    // 裁判影响
    const impactMatchId = ref('')
    const impactLoading = ref(false)
    const refereeImpact = ref(null)

    const loadRefereeList = async () => {
      listLoading.value = true
      try {
        const res = await analysisAPI.getRefereeList(50)
        refereeList.value = res.data || res || []
      } catch (e) {
        console.error('加载裁判列表失败:', e)
        refereeList.value = []
      } finally {
        listLoading.value = false
      }
    }

    const selectReferee = (name) => {
      if (name) {
        refereeName.value = name
        activeTab.value = 'detail'
        loadRefereeStats()
      }
    }

    const loadRefereeStats = async () => {
      if (!refereeName.value) return
      detailLoading.value = true
      refereeStats.value = null
      try {
        const res = await analysisAPI.getRefereeStats(refereeName.value)
        refereeStats.value = res.data || res || null
      } catch (e) {
        console.error('加载裁判详情失败:', e)
        refereeStats.value = null
      } finally {
        detailLoading.value = false
      }
    }

    const loadRefereeImpact = async () => {
      if (!impactMatchId.value) return
      impactLoading.value = true
      refereeImpact.value = null
      try {
        const res = await analysisAPI.getRefereeImpact(impactMatchId.value)
        refereeImpact.value = res.data || res || null
      } catch (e) {
        console.error('加载裁判影响失败:', e)
        refereeImpact.value = null
      } finally {
        impactLoading.value = false
      }
    }

    onMounted(loadRefereeList)

    return {
      activeTab, tabs,
      listLoading, refereeList,
      refereeName, detailLoading, refereeStats,
      impactMatchId, impactLoading, refereeImpact,
      loadRefereeList, selectReferee, loadRefereeStats, loadRefereeImpact
    }
  }
}
</script>

<style scoped>
.referee-analysis {
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

/* 标签页 */
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

/* 输入行 */
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

/* 数据表格 */
.data-table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  padding: 10px 14px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  white-space: nowrap;
}

.data-table td {
  padding: 10px 14px;
  font-size: 13px;
  color: #e5e7eb;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
}

.data-table tr:hover td {
  background: rgba(16, 185, 129, 0.05);
  cursor: pointer;
}

.name-cell {
  color: #10b981;
  font-weight: 500;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
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

/* 详情卡片 */
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

.detail-card p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
}

/* 趋势列表 */
.trend-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trend-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.trend-label {
  font-size: 13px;
  color: #e5e7eb;
  font-weight: 500;
}

.trend-value {
  font-size: 12px;
  color: #9ca3af;
}

/* 影响分析 */
.impact-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.impact-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.impact-label {
  font-size: 13px;
  color: #9ca3af;
}

.impact-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.impact-value.accent {
  color: #10b981;
}

.impact-analysis {
  padding: 10px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.impact-analysis p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
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
}
</style>
