<template>
  <div class="upset-analysis">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2><ZapIcon /> 爆冷分析</h2>
        <p>识别爆冷潜力、强弱对比、巨人杀手</p>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="tabs">
      <button :class="['tab', { active: activeTab === 'match' }]" @click="activeTab = 'match'">
        <TargetIcon class="tab-icon" />
        <span>比赛爆冷分析</span>
      </button>
      <button :class="['tab', { active: activeTab === 'scan' }]" @click="activeTab = 'scan'">
        <ScanIcon class="tab-icon" />
        <span>爆冷扫描</span>
      </button>
      <button :class="['tab', { active: activeTab === 'giant' }]" @click="activeTab = 'giant'">
        <SwordIcon class="tab-icon" />
        <span>巨人杀手榜</span>
      </button>
    </div>

    <!-- 比赛爆冷分析 -->
    <div v-if="activeTab === 'match'" class="tab-content">
      <div class="input-card card">
        <h3>选择对阵双方</h3>
        <div class="team-inputs">
          <div class="input-group">
            <label>主队 ID</label>
            <input v-model="matchInput.homeId" type="number" placeholder="输入主队ID" />
          </div>
          <div class="vs-label">VS</div>
          <div class="input-group">
            <label>客队 ID</label>
            <input v-model="matchInput.awayId" type="number" placeholder="输入客队ID" />
          </div>
        </div>
        <button class="btn btn-primary" @click="analyzeMatch" :disabled="matchLoading">
          <LoadingIcon v-if="matchLoading" class="spin" />
          <ZapIcon v-else class="btn-icon" />
          <span>{{ matchLoading ? '分析中...' : '分析爆冷潜力' }}</span>
        </button>
      </div>

      <!-- 加载状态 -->
      <div v-if="matchLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在分析爆冷潜力...</p>
      </div>

      <!-- 分析结果 -->
      <div v-else-if="matchResult" class="result-area">
        <!-- 爆冷概率总览 -->
        <div class="overview-card card">
          <div class="overview-header">
            <h3>爆冷潜力评估</h3>
            <span :class="['upset-badge', matchResult.upset_level]">
              {{ getUpsetLevelText(matchResult.upset_level) }}
            </span>
          </div>
          <div class="probability-display">
            <div class="prob-circle" :style="{ '--prob': matchResult.upset_probability }">
              <span class="prob-value">{{ matchResult.upset_probability }}%</span>
              <span class="prob-label">爆冷概率</span>
            </div>
            <div class="overview-info">
              <div class="info-row">
                <span class="info-label">爆冷潜力</span>
                <span :class="['info-value', matchResult.is_upset_potential ? 'positive' : 'negative']">
                  {{ matchResult.is_upset_potential ? '有爆冷风险' : '暂无爆冷迹象' }}
                </span>
              </div>
              <div class="info-row">
                <span class="info-label">爆冷等级</span>
                <span class="info-value">{{ matchResult.upset_level || '--' }}</span>
              </div>
              <div class="info-row" v-if="matchResult.upset_factors">
                <span class="info-label">爆冷因素数</span>
                <span class="info-value accent">{{ matchResult.upset_factors.upset_factor_count || 0 }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 实力对比 -->
        <div class="strength-card card" v-if="matchResult.strength_analysis">
          <h3>实力对比</h3>
          <div class="strength-bars">
            <div class="strength-row">
              <div class="team-label home">
                <span class="team-tag">主队</span>
                <span class="elo-val">Elo {{ matchResult.strength_analysis.home_elo }}</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill home" :style="{ width: getEloWidth(matchResult.strength_analysis.home_elo, matchResult.strength_analysis.away_elo) + '%' }"></div>
              </div>
            </div>
            <div class="strength-row">
              <div class="team-label away">
                <span class="team-tag">客队</span>
                <span class="elo-val">Elo {{ matchResult.strength_analysis.away_elo }}</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill away" :style="{ width: getEloWidth(matchResult.strength_analysis.away_elo, matchResult.strength_analysis.home_elo) + '%' }"></div>
              </div>
            </div>
          </div>
          <div class="strength-details">
            <div class="detail-item">
              <span class="detail-label">Elo差值</span>
              <span class="detail-value">{{ matchResult.strength_analysis.elo_diff }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">热门方</span>
              <span class="detail-value accent">{{ matchResult.strength_analysis.favorite || '--' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">冷门方</span>
              <span class="detail-value warn">{{ matchResult.strength_analysis.underdog || '--' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">实力差距</span>
              <span class="detail-value">{{ matchResult.strength_analysis.strength_gap || '--' }}</span>
            </div>
          </div>
        </div>

        <!-- 联赛排名 -->
        <div class="position-card card" v-if="matchResult.league_position">
          <h3>联赛排名</h3>
          <div class="position-compare">
            <div class="pos-side home">
              <span class="pos-label">主队排名</span>
              <span class="pos-value">{{ matchResult.league_position.home_rank || '--' }}</span>
            </div>
            <div class="pos-divider"></div>
            <div class="pos-side away">
              <span class="pos-label">客队排名</span>
              <span class="pos-value">{{ matchResult.league_position.away_rank || '--' }}</span>
            </div>
          </div>
        </div>

        <!-- 近期状态 -->
        <div class="form-card card" v-if="matchResult.recent_form">
          <h3>近期状态</h3>
          <div class="form-compare">
            <div class="form-side home">
              <span class="form-label">主队近况</span>
              <span class="form-value">{{ matchResult.recent_form.home_form || '--' }}</span>
            </div>
            <div class="form-side away">
              <span class="form-label">客队近况</span>
              <span class="form-value">{{ matchResult.recent_form.away_form || '--' }}</span>
            </div>
          </div>
        </div>

        <!-- 爆冷因素 -->
        <div class="factors-card card" v-if="matchResult.upset_factors && matchResult.upset_factors.key_factors">
          <h3>爆冷因素</h3>
          <div class="factors-list">
            <div class="factor-item" v-for="(factor, idx) in matchResult.upset_factors.key_factors" :key="idx">
              <span class="factor-index">{{ idx + 1 }}</span>
              <span class="factor-text">{{ factor }}</span>
            </div>
          </div>
          <div class="factors-summary" v-if="matchResult.upset_factors.upset_factor_count">
            共 <span class="accent">{{ matchResult.upset_factors.upset_factor_count }}</span> 个爆冷因素
          </div>
        </div>
      </div>

      <!-- 无数据提示 -->
      <div v-else-if="!matchLoading" class="empty-state">
        <TargetIcon class="empty-icon" />
        <p>输入球队ID，分析比赛爆冷潜力</p>
      </div>
    </div>

    <!-- 爆冷扫描 -->
    <div v-if="activeTab === 'scan'" class="tab-content">
      <div class="scan-header">
        <p>扫描近期具有爆冷潜力的比赛</p>
        <button class="btn btn-primary" @click="scanUpsets" :disabled="scanLoading">
          <LoadingIcon v-if="scanLoading" class="spin" />
          <ScanIcon v-else class="btn-icon" />
          <span>{{ scanLoading ? '扫描中...' : '开始扫描' }}</span>
        </button>
      </div>

      <!-- 加载状态 -->
      <div v-if="scanLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在扫描爆冷比赛...</p>
      </div>

      <!-- 扫描结果 -->
      <div v-else-if="scanResults.length > 0" class="scan-results">
        <div class="results-count">共发现 <span class="accent">{{ scanResults.length }}</span> 场爆冷潜力比赛</div>
        <div class="match-list">
          <div class="match-item card" v-for="match in sortedScanResults" :key="match.match_id || (match.home_team + match.away_team)">
            <div class="match-top">
              <span class="league-tag" v-if="match.league">{{ match.league }}</span>
              <span class="date-tag" v-if="match.match_date">{{ match.match_date }}</span>
              <span :class="['upset-badge small', match.upset_level]">
                {{ getUpsetLevelText(match.upset_level) }}
              </span>
            </div>
            <div class="match-teams">
              <span class="team home">{{ match.home_team || match.home_team_cn || '主队' }}</span>
              <span class="vs">VS</span>
              <span class="team away">{{ match.away_team || match.away_team_cn || '客队' }}</span>
            </div>
            <div class="match-bottom">
              <div class="prob-bar-container">
                <div class="prob-bar" :style="{ width: match.upset_probability + '%' }"></div>
                <span class="prob-text">{{ match.upset_probability }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 无数据 -->
      <div v-else class="empty-state">
        <ScanIcon class="empty-icon" />
        <p>点击扫描，发现近期爆冷潜力比赛</p>
      </div>
    </div>

    <!-- 巨人杀手榜 -->
    <div v-if="activeTab === 'giant'" class="tab-content">
      <div class="input-card card">
        <h3>查询巨人杀手</h3>
        <div class="giant-input">
          <div class="input-group">
            <label>球队 ID</label>
            <input v-model="giantInput.teamId" type="number" placeholder="输入球队ID" />
          </div>
          <button class="btn btn-primary" @click="loadGiantKilling" :disabled="giantLoading">
            <LoadingIcon v-if="giantLoading" class="spin" />
            <SwordIcon v-else class="btn-icon" />
            <span>{{ giantLoading ? '查询中...' : '查询巨人杀手' }}</span>
          </button>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="giantLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在查询巨人杀手记录...</p>
      </div>

      <!-- 巨人杀手结果 -->
      <div v-else-if="giantResult" class="giant-result">
        <!-- 统计概览 -->
        <div class="giant-stats card">
          <h3>巨人杀手统计</h3>
          <div class="stats-grid">
            <div class="stat-box">
              <span class="stat-value accent">{{ giantResult.giant_killing_count || 0 }}</span>
              <span class="stat-label">爆冷赢球次数</span>
            </div>
            <div class="stat-box">
              <span class="stat-value warn">{{ giantResult.upset_win_rate || '0%' }}</span>
              <span class="stat-label">爆冷胜率</span>
            </div>
          </div>
        </div>

        <!-- 爆冷赢球列表 -->
        <div class="giant-list card" v-if="giantResult.upset_wins && giantResult.upset_wins.length > 0">
          <h3>爆冷赢球记录</h3>
          <div class="win-item" v-for="(win, idx) in giantResult.upset_wins" :key="idx">
            <div class="win-top">
              <span class="win-index">{{ idx + 1 }}</span>
              <span class="win-date">{{ win.match_date || '--' }}</span>
              <span class="win-league" v-if="win.league">{{ win.league }}</span>
            </div>
            <div class="win-teams">
              <span class="win-team">{{ win.home_team || win.home_team_cn || '--' }}</span>
              <span class="win-score">{{ win.home_goals }} - {{ win.away_goals }}</span>
              <span class="win-team">{{ win.away_team || win.away_team_cn || '--' }}</span>
            </div>
            <div class="win-detail" v-if="win.opponent_elo">
              对手Elo: <span class="accent">{{ win.opponent_elo }}</span>
              <span v-if="win.elo_diff"> (差值: {{ win.elo_diff }})</span>
            </div>
          </div>
        </div>

        <!-- 无爆冷记录 -->
        <div v-else class="empty-state">
          <SwordIcon class="empty-icon" />
          <p>暂无爆冷赢球记录</p>
        </div>
      </div>

      <!-- 无数据提示 -->
      <div v-else-if="!giantLoading" class="empty-state">
        <SwordIcon class="empty-icon" />
        <p>输入球队ID，查询巨人杀手记录</p>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-toast">
      {{ error }}
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, h, defineComponent } from 'vue'
import { analysisAPI } from '../../api'

// 图标组件
const createIcon = (paths) => defineComponent({
  setup: () => () => h('svg', { class: 'w-4 h-4', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, paths)
})

const ZapIcon = createIcon([
  h('polygon', { points: '13 2 3 14 12 14 11 22 21 10 12 10 13 2' })
])

const TargetIcon = createIcon([
  h('circle', { cx: '12', cy: '12', r: '10' }),
  h('circle', { cx: '12', cy: '12', r: '6' }),
  h('circle', { cx: '12', cy: '12', r: '2' })
])

const ScanIcon = createIcon([
  h('circle', { cx: '11', cy: '11', r: '8' }),
  h('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' }),
  h('line', { x1: '11', y1: '8', x2: '11', y2: '14' }),
  h('line', { x1: '8', y1: '11', x2: '14', y2: '11' })
])

const SwordIcon = createIcon([
  h('path', { d: 'M14.5 17.5L3 6V3h3l11.5 11.5' }),
  h('path', { d: 'M13 19l6-6' }),
  h('path', { d: 'M16 16l4 4' }),
  h('path', { d: 'M19 21l2-2' })
])

const LoadingIcon = createIcon([
  h('line', { x1: '12', y1: '2', x2: '12', y2: '6' }),
  h('line', { x1: '12', y1: '18', x2: '12', y2: '22' }),
  h('line', { x1: '4.93', y1: '4.93', x2: '7.17', y2: '7.17' }),
  h('line', { x1: '16.83', y1: '16.83', x2: '19.07', y2: '19.07' }),
  h('line', { x1: '2', y1: '12', x2: '6', y2: '12' }),
  h('line', { x1: '18', y1: '12', x2: '22', y2: '12' })
])

export default {
  name: 'UpsetAnalysis',
  components: { ZapIcon, TargetIcon, ScanIcon, SwordIcon, LoadingIcon },
  setup() {
    const activeTab = ref('match')
    const error = ref(null)

    // 比赛爆冷分析
    const matchInput = ref({ homeId: '', awayId: '' })
    const matchLoading = ref(false)
    const matchResult = ref(null)

    // 爆冷扫描
    const scanLoading = ref(false)
    const scanResults = ref([])

    // 巨人杀手
    const giantInput = ref({ teamId: '' })
    const giantLoading = ref(false)
    const giantResult = ref(null)

    // 扫描结果按爆冷概率排序
    const sortedScanResults = computed(() => {
      return [...scanResults.value].sort((a, b) => (b.upset_probability || 0) - (a.upset_probability || 0))
    })

    // 爆冷等级文本
    const getUpsetLevelText = (level) => {
      const map = {
        'very_high': '极高',
        'high': '高',
        'medium': '中',
        'low': '低',
        'very_low': '极低'
      }
      return map[level] || level || '--'
    }

    // Elo条宽度计算
    const getEloWidth = (elo1, elo2) => {
      if (!elo1 || !elo2) return 50
      const total = elo1 + elo2
      return Math.max(10, Math.min(90, (elo1 / total) * 100))
    }

    // 比赛爆冷分析
    const analyzeMatch = async () => {
      if (!matchInput.value.homeId || !matchInput.value.awayId) {
        error.value = '请输入主队和客队ID'
        setTimeout(() => { error.value = null }, 3000)
        return
      }
      matchLoading.value = true
      matchResult.value = null
      error.value = null
      try {
        const res = await analysisAPI.analyzeUpsetPotential(
          matchInput.value.homeId,
          matchInput.value.awayId
        )
        matchResult.value = res.data || res
      } catch (e) {
        console.error('爆冷分析失败:', e)
        error.value = '分析失败，请检查球队ID是否正确'
        setTimeout(() => { error.value = null }, 3000)
      } finally {
        matchLoading.value = false
      }
    }

    // 爆冷扫描
    const scanUpsets = async () => {
      scanLoading.value = true
      scanResults.value = []
      error.value = null
      try {
        const res = await analysisAPI.scanUpsetMatches(null, null, 25)
        scanResults.value = res.data || res.upset_matches || res || []
      } catch (e) {
        console.error('爆冷扫描失败:', e)
        error.value = '扫描失败，请稍后重试'
        setTimeout(() => { error.value = null }, 3000)
      } finally {
        scanLoading.value = false
      }
    }

    // 巨人杀手查询
    const loadGiantKilling = async () => {
      if (!giantInput.value.teamId) {
        error.value = '请输入球队ID'
        setTimeout(() => { error.value = null }, 3000)
        return
      }
      giantLoading.value = true
      giantResult.value = null
      error.value = null
      try {
        const res = await analysisAPI.getGiantKillingHistory(giantInput.value.teamId)
        giantResult.value = res.data || res
      } catch (e) {
        console.error('巨人杀手查询失败:', e)
        error.value = '查询失败，请检查球队ID是否正确'
        setTimeout(() => { error.value = null }, 3000)
      } finally {
        giantLoading.value = false
      }
    }

    return {
      activeTab,
      error,
      matchInput,
      matchLoading,
      matchResult,
      scanLoading,
      scanResults,
      sortedScanResults,
      giantInput,
      giantLoading,
      giantResult,
      getUpsetLevelText,
      getEloWidth,
      analyzeMatch,
      scanUpsets,
      loadGiantKilling
    }
  }
}
</script>

<style scoped>
.upset-analysis {
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

/* 头部 */
.header {
  padding: 16px 20px;
}

.header-content h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.header-content h2 svg {
  width: 18px;
  height: 18px;
  color: #10b981;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

/* 标签页 */
.tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid #1f2937;
  padding-bottom: 12px;
  flex-wrap: wrap;
}

.tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: transparent;
  border: 1px solid #374151;
  border-radius: 8px;
  color: #9ca3af;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #e5e7eb;
}

.tab.active {
  background: rgba(16, 185, 129, 0.1);
  border-color: #10b981;
  color: #10b981;
}

.tab-icon {
  width: 16px;
  height: 16px;
}

/* 输入卡片 */
.input-card {
  padding: 20px;
}

.input-card h3 {
  font-size: 15px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.team-inputs {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 16px;
}

.vs-label {
  font-size: 14px;
  font-weight: 700;
  color: #4b5563;
  padding-bottom: 8px;
}

.input-group {
  flex: 1;
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
  width: 100%;
  padding: 8px 12px;
  background: #0d1117;
  border: 1px solid #374151;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.input-group input:focus {
  border-color: #10b981;
}

.input-group input::placeholder {
  color: #4b5563;
}

.giant-input {
  display: flex;
  align-items: flex-end;
  gap: 16px;
}

.giant-input .input-group {
  max-width: 240px;
}

/* 按钮 */
.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-icon {
  width: 14px;
  height: 14px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 加载状态 */
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

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background: #151922;
  border: 1px dashed #374151;
  border-radius: 12px;
  color: #6b7280;
}

.empty-icon {
  width: 24px;
  height: 24px;
  margin-bottom: 10px;
  opacity: 0.4;
}

.empty-state p {
  font-size: 13px;
}

/* 结果区域 */
.result-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 爆冷概率总览 */
.overview-card {
  padding: 20px;
}

.overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.overview-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: white;
}

.upset-badge {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.upset-badge.very_high {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.upset-badge.high {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.upset-badge.medium {
  background: rgba(234, 179, 8, 0.15);
  color: #eab308;
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.upset-badge.low {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.upset-badge.very_low {
  background: rgba(107, 114, 128, 0.15);
  color: #6b7280;
  border: 1px solid rgba(107, 114, 128, 0.3);
}

.upset-badge.small {
  padding: 2px 8px;
  font-size: 11px;
}

.probability-display {
  display: flex;
  align-items: center;
  gap: 32px;
}

.prob-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: conic-gradient(#10b981 0deg, #10b981 calc(var(--prob) * 3.6deg), #1f2937 calc(var(--prob) * 3.6deg));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  flex-shrink: 0;
}

.prob-circle::before {
  content: '';
  position: absolute;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: #151922;
}

.prob-value {
  position: relative;
  z-index: 1;
  font-size: 24px;
  font-weight: 700;
  color: #10b981;
}

.prob-label {
  position: relative;
  z-index: 1;
  font-size: 11px;
  color: #6b7280;
}

.overview-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0d1117;
  border-radius: 6px;
}

.info-label {
  font-size: 13px;
  color: #9ca3af;
}

.info-value {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
}

.info-value.positive {
  color: #f59e0b;
}

.info-value.negative {
  color: #10b981;
}

.info-value.accent {
  color: #10b981;
}

.info-value.warn {
  color: #f59e0b;
}

/* 实力对比 */
.strength-card {
  padding: 20px;
}

.strength-card h3 {
  font-size: 15px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.strength-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.strength-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.team-label {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 140px;
}

.team-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.team-label.home .team-tag {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.team-label.away .team-tag {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.elo-val {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.bar-track {
  flex: 1;
  height: 8px;
  background: #1f2937;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.bar-fill.home {
  background: linear-gradient(90deg, #10b981, #059669);
}

.bar-fill.away {
  background: linear-gradient(90deg, #3b82f6, #2563eb);
}

.strength-details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
}

.detail-item {
  padding: 10px 12px;
  background: #0d1117;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 11px;
  color: #6b7280;
}

.detail-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.detail-value.accent {
  color: #10b981;
}

/* 联赛排名 */
.position-card {
  padding: 20px;
}

.position-card h3 {
  font-size: 15px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.position-compare {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
}

.pos-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex: 1;
  padding: 16px;
  background: #0d1117;
  border-radius: 8px;
}

.pos-label {
  font-size: 12px;
  color: #9ca3af;
}

.pos-value {
  font-size: 28px;
  font-weight: 700;
  color: #10b981;
}

.pos-divider {
  width: 2px;
  height: 48px;
  background: #1f2937;
  border-radius: 1px;
}

/* 近期状态 */
.form-card {
  padding: 20px;
}

.form-card h3 {
  font-size: 15px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.form-compare {
  display: flex;
  gap: 16px;
}

.form-side {
  flex: 1;
  padding: 12px;
  background: #0d1117;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 12px;
  color: #9ca3af;
}

.form-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

/* 爆冷因素 */
.factors-card {
  padding: 20px;
}

.factors-card h3 {
  font-size: 15px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.factors-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.factor-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: #0d1117;
  border-radius: 6px;
  border-left: 3px solid #f59e0b;
}

.factor-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.factor-text {
  font-size: 13px;
  color: #e5e7eb;
  line-height: 1.5;
}

.factors-summary {
  font-size: 12px;
  color: #6b7280;
  text-align: right;
}

/* 扫描头部 */
.scan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.scan-header p {
  font-size: 13px;
  color: #9ca3af;
}

.scan-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.results-count {
  font-size: 13px;
  color: #9ca3af;
}

.accent {
  color: #10b981;
  font-weight: 600;
}

.warn {
  color: #f59e0b;
}

/* 比赛列表 */
.match-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.match-item {
  padding: 16px;
  transition: border-color 0.2s;
}

.match-item:hover {
  border-color: rgba(16, 185, 129, 0.3);
}

.match-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.league-tag {
  font-size: 11px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 3px 8px;
  border-radius: 4px;
}

.date-tag {
  font-size: 11px;
  color: #6b7280;
}

.match-teams {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 12px;
}

.match-teams .team {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  flex: 1;
  text-align: center;
}

.match-teams .team.home {
  text-align: right;
}

.match-teams .team.away {
  text-align: left;
}

.match-teams .vs {
  font-size: 12px;
  color: #4b5563;
  font-weight: 600;
}

.match-bottom {
  display: flex;
  align-items: center;
}

.prob-bar-container {
  flex: 1;
  height: 20px;
  background: #1f2937;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.prob-bar {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #ef4444);
  border-radius: 4px;
  transition: width 0.5s ease;
  min-width: 2px;
}

.prob-text {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

/* 巨人杀手结果 */
.giant-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.giant-stats {
  padding: 20px;
}

.giant-stats h3 {
  font-size: 15px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.stat-box {
  padding: 16px;
  background: #0d1117;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: white;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
}

/* 爆冷赢球列表 */
.giant-list {
  padding: 20px;
}

.giant-list h3 {
  font-size: 15px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.win-item {
  padding: 12px;
  background: #0d1117;
  border-radius: 6px;
  border-left: 3px solid #10b981;
  margin-bottom: 8px;
}

.win-item:last-child {
  margin-bottom: 0;
}

.win-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.win-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.win-date {
  font-size: 12px;
  color: #6b7280;
}

.win-league {
  font-size: 11px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 2px 6px;
  border-radius: 3px;
}

.win-teams {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 6px;
}

.win-team {
  font-size: 13px;
  font-weight: 500;
  color: #e5e7eb;
  flex: 1;
  text-align: center;
}

.win-team:first-child {
  text-align: right;
}

.win-team:last-child {
  text-align: left;
}

.win-score {
  font-size: 14px;
  font-weight: 700;
  color: #10b981;
  min-width: 48px;
  text-align: center;
}

.win-detail {
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}

/* 错误提示 */
.error-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  border-radius: 8px;
  background: #ef4444;
  color: white;
  font-size: 14px;
  font-weight: 500;
  z-index: 1000;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* 响应式 */
@media (max-width: 600px) {
  .team-inputs {
    flex-direction: column;
    align-items: stretch;
  }

  .vs-label {
    text-align: center;
  }

  .giant-input {
    flex-direction: column;
    align-items: stretch;
  }

  .giant-input .input-group {
    max-width: none;
  }

  .probability-display {
    flex-direction: column;
    align-items: center;
  }

  .overview-info {
    width: 100%;
  }

  .position-compare {
    gap: 12px;
  }

  .form-compare {
    flex-direction: column;
  }

  .tabs {
    flex-direction: column;
  }

  .tab {
    justify-content: center;
  }
}
</style>
