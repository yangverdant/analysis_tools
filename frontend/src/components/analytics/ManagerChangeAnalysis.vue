<template>
  <div class="manager-change-analysis">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          换帅效应
        </h2>
        <p>换帅前后表现对比、新帅效应评估</p>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="tabs card">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'effect' }"
        @click="activeTab = 'effect'"
      >换帅效应分析</button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'recent' }"
        @click="activeTab = 'recent'"
      >最近换帅</button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'league' }"
        @click="activeTab = 'league'"
      >联赛换帅</button>
    </div>

    <!-- 换帅效应分析 -->
    <div v-if="activeTab === 'effect'" class="tab-content">
      <!-- 输入区 -->
      <div class="input-card card">
        <div class="input-row">
          <div class="input-group">
            <label>球队 ID</label>
            <input
              v-model="effectForm.teamId"
              type="number"
              placeholder="输入球队ID"
            />
          </div>
          <div class="input-group">
            <label>换帅日期</label>
            <input
              v-model="effectForm.changeDate"
              type="date"
            />
          </div>
          <button class="query-btn" @click="loadEffectAnalysis" :disabled="effectLoading">
            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            {{ effectLoading ? '分析中...' : '分析' }}
          </button>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="effectLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在分析换帅效应...</p>
      </div>

      <!-- 分析结果 -->
      <template v-if="effectData && !effectLoading">
        <!-- 前后对比 -->
        <div class="compare-section">
          <div class="compare-card card before">
            <div class="compare-header">
              <span class="compare-tag before-tag">换帅前</span>
            </div>
            <div class="stat-grid">
              <div class="stat-item">
                <span class="stat-label">胜/平/负</span>
                <span class="stat-value">{{ effectData.before?.wins ?? '--' }}/{{ effectData.before?.draws ?? '--' }}/{{ effectData.before?.losses ?? '--' }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">胜率</span>
                <span class="stat-value">{{ formatPercent(effectData.before?.win_rate) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">场均积分</span>
                <span class="stat-value">{{ effectData.before?.points_per_match?.toFixed(2) ?? '--' }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">场均进球</span>
                <span class="stat-value">{{ effectData.before?.goals_per_match?.toFixed(2) ?? '--' }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">零封率</span>
                <span class="stat-value">{{ formatPercent(effectData.before?.clean_sheet_rate) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">近期状态</span>
                <span class="stat-value form-text">{{ effectData.before?.form ?? '--' }}</span>
              </div>
            </div>
          </div>

          <div class="compare-divider">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </div>

          <div class="compare-card card after">
            <div class="compare-header">
              <span class="compare-tag after-tag">换帅后</span>
            </div>
            <div class="stat-grid">
              <div class="stat-item">
                <span class="stat-label">胜/平/负</span>
                <span class="stat-value">{{ effectData.after?.wins ?? '--' }}/{{ effectData.after?.draws ?? '--' }}/{{ effectData.after?.losses ?? '--' }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">胜率</span>
                <span class="stat-value">{{ formatPercent(effectData.after?.win_rate) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">场均积分</span>
                <span class="stat-value">{{ effectData.after?.points_per_match?.toFixed(2) ?? '--' }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">场均进球</span>
                <span class="stat-value">{{ effectData.after?.goals_per_match?.toFixed(2) ?? '--' }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">零封率</span>
                <span class="stat-value">{{ formatPercent(effectData.after?.clean_sheet_rate) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">近期状态</span>
                <span class="stat-value form-text">{{ effectData.after?.form ?? '--' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 变化指标 -->
        <div class="improvement-card card">
          <h3 class="section-title">变化指标</h3>
          <div class="improvement-grid">
            <div class="improve-item">
              <span class="improve-label">场均积分变化</span>
              <span class="improve-value" :class="changeClass(effectData.improvement?.points_per_match_change)">
                {{ formatChange(effectData.improvement?.points_per_match_change) }}
              </span>
            </div>
            <div class="improve-item">
              <span class="improve-label">胜率变化</span>
              <span class="improve-value" :class="changeClass(effectData.improvement?.win_rate_change)">
                {{ formatChange(effectData.improvement?.win_rate_change, true) }}
              </span>
            </div>
            <div class="improve-item">
              <span class="improve-label">场均进球变化</span>
              <span class="improve-value" :class="changeClass(effectData.improvement?.goals_per_match_change)">
                {{ formatChange(effectData.improvement?.goals_per_match_change) }}
              </span>
            </div>
            <div class="improve-item">
              <span class="improve-label">改善评分</span>
              <span class="improve-value score">{{ effectData.improvement?.improvement_score?.toFixed(1) ?? '--' }}</span>
            </div>
            <div class="improve-item full-width">
              <span class="improve-label">趋势</span>
              <span class="improve-value trend" :class="effectData.improvement?.trend">
                {{ trendLabel(effectData.improvement?.trend) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 新帅反弹效应 -->
        <div class="bounce-card card" v-if="effectData.manager_bounce">
          <h3 class="section-title">新帅反弹效应</h3>
          <div class="bounce-content">
            <div class="bounce-indicator" :class="{ active: effectData.manager_bounce.has_bounce }">
              <svg v-if="effectData.manager_bounce.has_bounce" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
                <polyline points="17 6 23 6 23 12" />
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
                <polyline points="17 18 23 18 23 12" />
              </svg>
              <span>{{ effectData.manager_bounce.has_bounce ? '存在反弹效应' : '无明显反弹' }}</span>
            </div>
            <div class="bounce-detail" v-if="effectData.manager_bounce.has_bounce">
              <div class="bounce-strength">
                <span class="detail-label">反弹强度</span>
                <div class="strength-bar">
                  <div
                    class="strength-fill"
                    :style="{ width: Math.min((effectData.manager_bounce.strength || 0) * 100, 100) + '%' }"
                  ></div>
                </div>
                <span class="strength-value">{{ ((effectData.manager_bounce.strength || 0) * 100).toFixed(0) }}%</span>
              </div>
              <p class="bounce-desc">{{ effectData.manager_bounce.description }}</p>
            </div>
          </div>
        </div>
      </template>

      <!-- 无数据 -->
      <div v-if="!effectData && !effectLoading && effectSearched" class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <p>未找到换帅效应数据，请检查球队ID和换帅日期</p>
      </div>
    </div>

    <!-- 最近换帅 -->
    <div v-if="activeTab === 'recent'" class="tab-content">
      <!-- 加载状态 -->
      <div v-if="recentLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在加载最近换帅记录...</p>
      </div>

      <!-- 换帅列表 -->
      <div v-if="recentData && !recentLoading" class="recent-list">
        <div
          class="recent-item card"
          v-for="(item, idx) in recentData"
          :key="idx"
        >
          <div class="recent-top">
            <span class="team-name">{{ item.team_name }}</span>
            <span class="change-date">{{ item.change_date }}</span>
          </div>
          <div class="coach-change">
            <span class="coach old-coach">{{ item.old_coach_name || '未知' }}</span>
            <svg class="arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
            <span class="coach new-coach">{{ item.new_coach_name || '未知' }}</span>
          </div>
          <div class="recent-meta">
            <span class="change-type-badge" :class="item.change_type">{{ changeTypeLabel(item.change_type) }}</span>
            <span v-if="item.effect?.improvement" class="effect-badge" :class="effectClass(item.effect.improvement)">
              {{ effectLabel(item.effect.improvement) }}
            </span>
          </div>
          <div class="recent-bounce" v-if="item.manager_bounce">
            <span class="bounce-tag" :class="{ active: item.manager_bounce.has_bounce }">
              {{ item.manager_bounce.has_bounce ? '反弹效应' : '无反弹' }}
            </span>
            <span v-if="item.manager_bounce.has_bounce && item.manager_bounce.strength" class="bounce-strength-mini">
              强度 {{ (item.manager_bounce.strength * 100).toFixed(0) }}%
            </span>
          </div>
        </div>

        <div v-if="recentData.length === 0" class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p>暂无最近换帅记录</p>
        </div>
      </div>
    </div>

    <!-- 联赛换帅 -->
    <div v-if="activeTab === 'league'" class="tab-content">
      <!-- 输入区 -->
      <div class="input-card card">
        <div class="input-row">
          <div class="input-group">
            <label>联赛 ID</label>
            <input
              v-model="leagueForm.leagueId"
              type="number"
              placeholder="输入联赛ID"
            />
          </div>
          <div class="input-group">
            <label>赛季 ID</label>
            <input
              v-model="leagueForm.seasonId"
              type="number"
              placeholder="输入赛季ID"
            />
          </div>
          <button class="query-btn" @click="loadLeagueChanges" :disabled="leagueLoading">
            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            {{ leagueLoading ? '查询中...' : '查询' }}
          </button>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="leagueLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在加载联赛换帅数据...</p>
      </div>

      <!-- 联赛统计 -->
      <template v-if="leagueData && !leagueLoading">
        <div class="league-stats card">
          <h3 class="section-title">联赛换帅概览</h3>
          <div class="stats-overview">
            <div class="overview-item">
              <span class="overview-value">{{ leagueData.total_changes ?? 0 }}</span>
              <span class="overview-label">总换帅次数</span>
            </div>
            <div class="overview-item positive">
              <span class="overview-value">{{ leagueData.positive_changes ?? 0 }}</span>
              <span class="overview-label">正面效果</span>
            </div>
            <div class="overview-item negative">
              <span class="overview-value">{{ leagueData.negative_changes ?? 0 }}</span>
              <span class="overview-label">负面效果</span>
            </div>
            <div class="overview-item">
              <span class="overview-value accent">{{ formatPercent(leagueData.success_rate) }}</span>
              <span class="overview-label">成功率</span>
            </div>
          </div>
        </div>

        <!-- 分析列表 -->
        <div class="league-analyses" v-if="leagueData.analyses && leagueData.analyses.length > 0">
          <div
            class="analysis-item card"
            v-for="(item, idx) in leagueData.analyses"
            :key="idx"
          >
            <div class="analysis-top">
              <span class="team-name">{{ item.team_name }}</span>
              <span class="change-date">{{ item.change_date }}</span>
            </div>
            <div class="coach-change">
              <span class="coach old-coach">{{ item.old_coach_name || '未知' }}</span>
              <svg class="arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
              <span class="coach new-coach">{{ item.new_coach_name || '未知' }}</span>
            </div>
            <div class="analysis-metrics" v-if="item.improvement">
              <div class="metric">
                <span class="metric-label">场均积分变化</span>
                <span class="metric-value" :class="changeClass(item.improvement.points_per_match_change)">
                  {{ formatChange(item.improvement.points_per_match_change) }}
                </span>
              </div>
              <div class="metric">
                <span class="metric-label">胜率变化</span>
                <span class="metric-value" :class="changeClass(item.improvement.win_rate_change)">
                  {{ formatChange(item.improvement.win_rate_change, true) }}
                </span>
              </div>
              <div class="metric">
                <span class="metric-label">改善评分</span>
                <span class="metric-value score">{{ item.improvement.improvement_score?.toFixed(1) ?? '--' }}</span>
              </div>
            </div>
            <div class="analysis-bounce" v-if="item.manager_bounce">
              <span class="bounce-tag" :class="{ active: item.manager_bounce.has_bounce }">
                {{ item.manager_bounce.has_bounce ? '反弹效应' : '无反弹' }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="!leagueData.analyses || leagueData.analyses.length === 0" class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p>该联赛本赛季暂无换帅记录</p>
        </div>
      </template>

      <!-- 无数据 -->
      <div v-if="!leagueData && !leagueLoading && leagueSearched" class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <p>未找到联赛换帅数据，请检查联赛ID和赛季ID</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, watch } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'ManagerChangeAnalysis',
  setup() {
    const activeTab = ref('effect')

    // 换帅效应分析
    const effectForm = reactive({ teamId: '', changeDate: '' })
    const effectLoading = ref(false)
    const effectData = ref(null)
    const effectSearched = ref(false)

    const loadEffectAnalysis = async () => {
      if (!effectForm.teamId || !effectForm.changeDate) return
      effectLoading.value = true
      effectSearched.value = true
      try {
        const res = await analysisAPI.getManagerChangeEffect(effectForm.teamId, effectForm.changeDate)
        effectData.value = res.data || res
      } catch (e) {
        console.error('换帅效应分析失败:', e)
        effectData.value = null
      } finally {
        effectLoading.value = false
      }
    }

    // 最近换帅
    const recentLoading = ref(false)
    const recentData = ref(null)

    const loadRecentChanges = async () => {
      recentLoading.value = true
      try {
        const res = await analysisAPI.getRecentManagerChanges(20)
        recentData.value = res.data || res || []
      } catch (e) {
        console.error('加载最近换帅记录失败:', e)
        recentData.value = []
      } finally {
        recentLoading.value = false
      }
    }

    // 联赛换帅
    const leagueForm = reactive({ leagueId: '', seasonId: '' })
    const leagueLoading = ref(false)
    const leagueData = ref(null)
    const leagueSearched = ref(false)

    const loadLeagueChanges = async () => {
      if (!leagueForm.leagueId || !leagueForm.seasonId) return
      leagueLoading.value = true
      leagueSearched.value = true
      try {
        const res = await analysisAPI.getLeagueManagerChanges(leagueForm.leagueId, leagueForm.seasonId)
        leagueData.value = res.data || res
      } catch (e) {
        console.error('联赛换帅查询失败:', e)
        leagueData.value = null
      } finally {
        leagueLoading.value = false
      }
    }

    // 切换到最近换帅tab时自动加载
    watch(activeTab, (tab) => {
      if (tab === 'recent' && !recentData.value) {
        loadRecentChanges()
      }
    })

    // 格式化工具
    const formatPercent = (val) => {
      if (val == null) return '--'
      return (val * 100).toFixed(1) + '%'
    }

    const formatChange = (val, isPercent = false) => {
      if (val == null) return '--'
      const prefix = val > 0 ? '+' : ''
      return isPercent ? prefix + (val * 100).toFixed(1) + '%' : prefix + val.toFixed(2)
    }

    const changeClass = (val) => {
      if (val == null) return ''
      return val > 0 ? 'positive' : val < 0 ? 'negative' : 'neutral'
    }

    const trendLabel = (trend) => {
      const map = { improving: '改善中', declining: '下滑中', stable: '稳定', mixed: '波动' }
      return map[trend] || trend || '--'
    }

    const changeTypeLabel = (type) => {
      const map = { fired: '解雇', resigned: '辞职', mutual: '协商', appointed: '任命', interim: '临时' }
      return map[type] || type || '换帅'
    }

    const effectClass = (improvement) => {
      if (!improvement) return ''
      const score = improvement.improvement_score || 0
      return score > 0 ? 'positive' : score < 0 ? 'negative' : 'neutral'
    }

    const effectLabel = (improvement) => {
      if (!improvement) return '--'
      const score = improvement.improvement_score || 0
      return score > 0.3 ? '效果显著' : score > 0 ? '略有改善' : score > -0.3 ? '效果一般' : '效果不佳'
    }

    return {
      activeTab,
      effectForm,
      effectLoading,
      effectData,
      effectSearched,
      loadEffectAnalysis,
      recentLoading,
      recentData,
      leagueForm,
      leagueLoading,
      leagueData,
      leagueSearched,
      loadLeagueChanges,
      formatPercent,
      formatChange,
      changeClass,
      trendLabel,
      changeTypeLabel,
      effectClass,
      effectLabel
    }
  }
}
</script>

<style scoped>
.manager-change-analysis {
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
  color: #e5e7eb;
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
  color: #9ca3af;
}

/* 标签页 */
.tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
}

.tab-btn {
  flex: 1;
  padding: 10px 16px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: #9ca3af;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: #e5e7eb;
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  font-weight: 600;
}

/* 输入区 */
.input-card {
  padding: 16px 20px;
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
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
  padding: 8px 12px;
  background: #0a0d14;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.input-group input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.input-group input::placeholder {
  color: #4b5563;
}

.query-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  color: #10b981;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.query-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
}

.query-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.query-btn .btn-icon {
  width: 14px;
  height: 14px;
}

/* 加载状态 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: #9ca3af;
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

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #6b7280;
}

.empty-state svg {
  width: 32px;
  height: 32px;
  margin-bottom: 8px;
}

.empty-state p {
  font-size: 13px;
}

/* 前后对比 */
.compare-section {
  display: flex;
  gap: 12px;
  align-items: stretch;
}

.compare-card {
  flex: 1;
  padding: 16px;
}

.compare-header {
  margin-bottom: 12px;
}

.compare-tag {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 6px;
}

.compare-tag.before-tag {
  background: rgba(107, 114, 128, 0.2);
  color: #9ca3af;
}

.compare-tag.after-tag {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.compare-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4b5563;
  flex-shrink: 0;
}

.compare-divider svg {
  width: 20px;
  height: 20px;
}

.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: #6b7280;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.stat-value.form-text {
  font-size: 13px;
  letter-spacing: 2px;
  font-family: monospace;
}

/* 变化指标 */
.improvement-card {
  padding: 16px 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.improvement-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.improve-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 8px;
}

.improve-item.full-width {
  grid-column: 1 / -1;
}

.improve-label {
  font-size: 12px;
  color: #9ca3af;
}

.improve-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.improve-value.positive {
  color: #10b981;
}

.improve-value.negative {
  color: #ef4444;
}

.improve-value.neutral {
  color: #9ca3af;
}

.improve-value.score {
  color: #10b981;
}

.improve-value.trend {
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.improve-value.trend.improving {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.improve-value.trend.declining {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.improve-value.trend.stable {
  background: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
}

.improve-value.trend.mixed {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

/* 新帅反弹效应 */
.bounce-card {
  padding: 16px 20px;
}

.bounce-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.bounce-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #6b7280;
}

.bounce-indicator.active {
  color: #10b981;
}

.bounce-indicator svg {
  width: 20px;
  height: 20px;
}

.bounce-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: #0a0d14;
  border-radius: 8px;
}

.bounce-strength {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-label {
  font-size: 12px;
  color: #9ca3af;
  min-width: 60px;
}

.strength-bar {
  flex: 1;
  height: 6px;
  background: rgba(31, 41, 55, 0.8);
  border-radius: 3px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  background: linear-gradient(90deg, #10b981, #059669);
  border-radius: 3px;
  transition: width 0.3s;
}

.strength-value {
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
  min-width: 36px;
  text-align: right;
}

.bounce-desc {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.5;
  margin: 0;
}

/* 最近换帅列表 */
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.recent-item {
  padding: 14px 16px;
  transition: border-color 0.2s;
}

.recent-item:hover {
  border-color: rgba(16, 185, 129, 0.3);
}

.recent-top,
.analysis-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.team-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.change-date {
  font-size: 12px;
  color: #6b7280;
}

.coach-change {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.coach {
  font-size: 13px;
  font-weight: 500;
}

.coach.old-coach {
  color: #9ca3af;
}

.coach.new-coach {
  color: #10b981;
}

.arrow-icon {
  width: 14px;
  height: 14px;
  color: #4b5563;
  flex-shrink: 0;
}

.recent-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.change-type-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(107, 114, 128, 0.2);
  color: #9ca3af;
}

.change-type-badge.fired {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.change-type-badge.resigned {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.change-type-badge.mutual {
  background: rgba(107, 114, 128, 0.2);
  color: #9ca3af;
}

.change-type-badge.appointed {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.change-type-badge.interim {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.effect-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
}

.effect-badge.positive {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.effect-badge.negative {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.effect-badge.neutral {
  background: rgba(107, 114, 128, 0.2);
  color: #9ca3af;
}

.recent-bounce {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bounce-tag {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(107, 114, 128, 0.2);
  color: #6b7280;
}

.bounce-tag.active {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.bounce-strength-mini {
  font-size: 11px;
  color: #10b981;
}

/* 联赛换帅 */
.league-stats {
  padding: 16px 20px;
}

.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.overview-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px;
  background: #0a0d14;
  border-radius: 8px;
}

.overview-value {
  font-size: 20px;
  font-weight: 700;
  color: #e5e7eb;
}

.overview-value.accent {
  color: #10b981;
}

.overview-item.positive .overview-value {
  color: #10b981;
}

.overview-item.negative .overview-value {
  color: #ef4444;
}

.overview-label {
  font-size: 11px;
  color: #9ca3af;
}

/* 联赛分析列表 */
.league-analyses {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.analysis-item {
  padding: 14px 16px;
  transition: border-color 0.2s;
}

.analysis-item:hover {
  border-color: rgba(16, 185, 129, 0.3);
}

.analysis-metrics {
  display: flex;
  gap: 16px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(31, 41, 55, 0.3);
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: 11px;
  color: #6b7280;
}

.metric-value {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
}

.metric-value.positive {
  color: #10b981;
}

.metric-value.negative {
  color: #ef4444;
}

.metric-value.neutral {
  color: #9ca3af;
}

.metric-value.score {
  color: #10b981;
}

.analysis-bounce {
  margin-top: 8px;
}

/* 响应式 */
@media (max-width: 700px) {
  .compare-section {
    flex-direction: column;
  }

  .compare-divider {
    transform: rotate(90deg);
    padding: 4px 0;
  }

  .input-row {
    flex-direction: column;
  }

  .stats-overview {
    grid-template-columns: repeat(2, 1fr);
  }

  .improvement-grid {
    grid-template-columns: 1fr;
  }

  .analysis-metrics {
    flex-wrap: wrap;
    gap: 10px;
  }
}
</style>
