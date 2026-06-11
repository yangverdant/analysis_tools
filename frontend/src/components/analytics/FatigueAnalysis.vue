<template>
  <div class="fatigue-analysis">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>球队疲劳分析</h2>
        <p>赛程密集度与疲劳影响评估</p>
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

    <!-- Tab 1: 球队疲劳评估 -->
    <div v-if="activeTab === 'fatigue'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="fatigueTeamId"
          placeholder="输入球队ID"
          class="text-input"
          @keyup.enter="loadTeamFatigue"
        />
        <button class="action-btn" @click="loadTeamFatigue" :disabled="fatigueLoading">查询</button>
      </div>
      <div class="loading-state" v-if="fatigueLoading">
        <div class="spinner"></div>
        <p>正在获取疲劳数据...</p>
      </div>
      <template v-else-if="fatigueData">
        <div class="stats-grid">
          <div class="stat-card card">
            <div class="stat-label">疲劳指数</div>
            <div class="stat-value" :class="riskLevelClass(fatigueData.fatigue_index)">
              {{ fatigueData.fatigue_index != null ? fatigueData.fatigue_index : '--' }}
            </div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">休息天数</div>
            <div class="stat-value" :class="restDayClass(fatigueData.rest_days)">
              {{ fatigueData.rest_days != null ? fatigueData.rest_days : '--' }}
            </div>
            <div class="stat-sub">天</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">比赛负荷</div>
            <div class="stat-value accent">{{ fatigueData.match_load != null ? fatigueData.match_load : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">恢复状态</div>
            <div class="stat-value" :class="recoveryClass(fatigueData.recovery_status)">
              {{ fatigueData.recovery_status || '--' }}
            </div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">风险等级</div>
            <div class="stat-value" :class="riskLevelClass(fatigueData.risk_level)">
              {{ fatigueData.risk_level || '--' }}
            </div>
          </div>
        </div>
        <div v-if="fatigueData.analysis || fatigueData.recommendation" class="detail-card card">
          <h3>详细分析</h3>
          <div v-if="fatigueData.recommendation" class="detail-row">
            <span class="detail-label">建议</span>
            <span class="detail-value">{{ fatigueData.recommendation }}</span>
          </div>
          <div v-if="fatigueData.analysis" class="detail-block">
            <p>{{ typeof fatigueData.analysis === 'string' ? fatigueData.analysis : JSON.stringify(fatigueData.analysis) }}</p>
          </div>
        </div>
        <div v-if="fatigueData.schedule && fatigueData.schedule.length" class="detail-card card">
          <h3>近期赛程</h3>
          <div class="schedule-list">
            <div v-for="(s, idx) in fatigueData.schedule" :key="idx" class="schedule-item">
              <span class="schedule-date">{{ s.date || s.match_date || '--' }}</span>
              <span class="schedule-opponent">{{ s.opponent || s.opponent_name || '--' }}</span>
              <span v-if="s.competition || s.type" class="schedule-type">{{ s.competition || s.type }}</span>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入球队ID查询疲劳数据</p>
      </div>
    </div>

    <!-- Tab 2: 赛程密集度 -->
    <div v-if="activeTab === 'density'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="densityTeamId"
          placeholder="输入球队ID"
          class="text-input"
          @keyup.enter="loadFixtureDensity"
        />
        <input
          v-model="densityDays"
          placeholder="天数"
          class="text-input short"
          type="number"
          @keyup.enter="loadFixtureDensity"
        />
        <button class="action-btn" @click="loadFixtureDensity" :disabled="densityLoading">查询</button>
      </div>
      <div class="loading-state" v-if="densityLoading">
        <div class="spinner"></div>
        <p>正在获取赛程密集度...</p>
      </div>
      <template v-else-if="densityData">
        <div class="stats-grid">
          <div class="stat-card card">
            <div class="stat-label">比赛场次</div>
            <div class="stat-value accent">{{ densityData.match_count != null ? densityData.match_count : densityData.recent_matches != null ? densityData.recent_matches : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">平均间隔</div>
            <div class="stat-value">{{ densityData.avg_interval != null ? densityData.avg_interval + ' 天' : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">密集度指数</div>
            <div class="stat-value" :class="riskLevelClass(densityData.density_index || densityData.fatigue_index)">
              {{ densityData.density_index != null ? densityData.density_index : densityData.fatigue_index != null ? densityData.fatigue_index : '--' }}
            </div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">休息天数</div>
            <div class="stat-value" :class="restDayClass(densityData.rest_days)">{{ densityData.rest_days != null ? densityData.rest_days : '--' }} 天</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">风险等级</div>
            <div class="stat-value" :class="riskLevelClass(densityData.risk_level || densityData.fatigue_level)">
              {{ densityData.risk_level || densityData.fatigue_level || '--' }}
            </div>
          </div>
        </div>
        <div v-if="densityData.schedule && densityData.schedule.length" class="detail-card card">
          <h3>赛程列表</h3>
          <div class="schedule-list">
            <div v-for="(fix, idx) in densityData.schedule" :key="idx" class="schedule-item">
              <span class="schedule-date">{{ fix.date || fix.match_date || '--' }}</span>
              <span class="schedule-opponent">{{ fix.opponent || fix.opponent_name || fix.match || '--' }}</span>
              <span v-if="fix.competition || fix.type" class="schedule-type">{{ fix.competition || fix.type }}</span>
            </div>
          </div>
        </div>
        <div v-if="densityData.analysis" class="detail-card card">
          <h3>密集度分析</h3>
          <div class="detail-block">
            <p>{{ typeof densityData.analysis === 'string' ? densityData.analysis : JSON.stringify(densityData.analysis) }}</p>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入球队ID和天数查询赛程密集度</p>
      </div>
    </div>

    <!-- Tab 3: 疲劳影响预测 -->
    <div v-if="activeTab === 'impact'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="impactTeamId"
          placeholder="输入球队ID"
          class="text-input"
          @keyup.enter="loadFatigueImpact"
        />
        <input
          v-model="impactMatchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadFatigueImpact"
        />
        <button class="action-btn" @click="loadFatigueImpact" :disabled="impactLoading">查询</button>
      </div>
      <div class="loading-state" v-if="impactLoading">
        <div class="spinner"></div>
        <p>正在获取疲劳影响预测...</p>
      </div>
      <template v-else-if="impactData">
        <div class="stats-grid">
          <div class="stat-card card">
            <div class="stat-label">疲劳指数</div>
            <div class="stat-value" :class="riskLevelClass(impactData.fatigue_index)">
              {{ impactData.fatigue_index != null ? impactData.fatigue_index : '--' }}
            </div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">休息天数</div>
            <div class="stat-value" :class="restDayClass(impactData.rest_days)">
              {{ impactData.rest_days != null ? impactData.rest_days : '--' }}
            </div>
            <div class="stat-sub">天</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">比赛负荷</div>
            <div class="stat-value accent">{{ impactData.match_load != null ? impactData.match_load : '--' }}</div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">恢复状态</div>
            <div class="stat-value" :class="recoveryClass(impactData.recovery_status)">
              {{ impactData.recovery_status || '--' }}
            </div>
          </div>
          <div class="stat-card card">
            <div class="stat-label">风险等级</div>
            <div class="stat-value" :class="riskLevelClass(impactData.risk_level)">
              {{ impactData.risk_level || '--' }}
            </div>
          </div>
        </div>
        <div v-if="impactData.impact_analysis || impactData.analysis" class="detail-card card">
          <h3>影响分析</h3>
          <div class="detail-block">
            <p>{{ typeof (impactData.impact_analysis || impactData.analysis) === 'string' ? (impactData.impact_analysis || impactData.analysis) : JSON.stringify(impactData.impact_analysis || impactData.analysis) }}</p>
          </div>
        </div>
        <div v-if="impactData.recommendation" class="detail-card card">
          <h3>建议</h3>
          <div class="detail-row">
            <span class="detail-value">{{ impactData.recommendation }}</span>
          </div>
        </div>
        <div v-if="impactData.home_team || impactData.away_team" class="detail-card card">
          <h3>比赛双方疲劳对比</h3>
          <div class="compare-grid">
            <div v-if="impactData.home_team" class="compare-team card">
              <h4 class="team-title home">主队</h4>
              <div class="compare-stat">
                <span class="compare-label">疲劳等级</span>
                <span class="compare-value" :class="riskLevelClass(impactData.home_team.fatigue_level || impactData.home_team.fatigue_score)">
                  {{ impactData.home_team.fatigue_level || impactData.home_team.fatigue_score || '--' }}
                </span>
              </div>
              <div class="compare-stat">
                <span class="compare-label">休息天数</span>
                <span class="compare-value">{{ impactData.home_team.rest_days != null ? impactData.home_team.rest_days + '天' : '--' }}</span>
              </div>
            </div>
            <div v-if="impactData.away_team" class="compare-team card">
              <h4 class="team-title away">客队</h4>
              <div class="compare-stat">
                <span class="compare-label">疲劳等级</span>
                <span class="compare-value" :class="riskLevelClass(impactData.away_team.fatigue_level || impactData.away_team.fatigue_score)">
                  {{ impactData.away_team.fatigue_level || impactData.away_team.fatigue_score || '--' }}
                </span>
              </div>
              <div class="compare-stat">
                <span class="compare-label">休息天数</span>
                <span class="compare-value">{{ impactData.away_team.rest_days != null ? impactData.away_team.rest_days + '天' : '--' }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty-state card">
        <p>请输入球队ID和比赛ID查询疲劳影响</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'FatigueAnalysis',
  setup() {
    const activeTab = ref('fatigue')
    const tabs = [
      { key: 'fatigue', label: '球队疲劳评估' },
      { key: 'density', label: '赛程密集度' },
      { key: 'impact', label: '疲劳影响预测' }
    ]

    // Tab 1: 球队疲劳评估
    const fatigueTeamId = ref('')
    const fatigueLoading = ref(false)
    const fatigueData = ref(null)

    const loadTeamFatigue = async () => {
      if (!fatigueTeamId.value) return
      fatigueLoading.value = true
      fatigueData.value = null
      try {
        const res = await analysisAPI.getTeamFatigue(fatigueTeamId.value)
        fatigueData.value = res.data || res || null
      } catch (e) {
        console.error('获取球队疲劳数据失败:', e)
        fatigueData.value = null
      } finally {
        fatigueLoading.value = false
      }
    }

    // Tab 2: 赛程密集度
    const densityTeamId = ref('')
    const densityDays = ref(14)
    const densityLoading = ref(false)
    const densityData = ref(null)

    const loadFixtureDensity = async () => {
      if (!densityTeamId.value) return
      densityLoading.value = true
      densityData.value = null
      try {
        const days = densityDays.value || 14
        const res = await analysisAPI.getTeamFatigue(densityTeamId.value)
        densityData.value = res.data || res || null
      } catch (e) {
        console.error('获取赛程密集度失败:', e)
        densityData.value = null
      } finally {
        densityLoading.value = false
      }
    }

    // Tab 3: 疲劳影响预测
    const impactTeamId = ref('')
    const impactMatchId = ref('')
    const impactLoading = ref(false)
    const impactData = ref(null)

    const loadFatigueImpact = async () => {
      if (!impactTeamId.value || !impactMatchId.value) return
      impactLoading.value = true
      impactData.value = null
      try {
        const res = await analysisAPI.getMatchFatigue(impactMatchId.value)
        impactData.value = res.data || res || null
      } catch (e) {
        console.error('获取疲劳影响预测失败:', e)
        impactData.value = null
      } finally {
        impactLoading.value = false
      }
    }

    const riskLevelClass = (level) => {
      if (level == null) return ''
      const l = level.toString().toLowerCase()
      if (l.includes('high') || l.includes('高') || l.includes('严重')) return 'level-high'
      if (l.includes('medium') || l.includes('中') || l.includes('中等')) return 'level-medium'
      if (l.includes('low') || l.includes('低') || l.includes('轻微')) return 'level-low'
      if (!isNaN(parseFloat(l))) {
        const v = parseFloat(l)
        if (v >= 0.7) return 'level-high'
        if (v >= 0.4) return 'level-medium'
        return 'level-low'
      }
      return ''
    }

    const restDayClass = (days) => {
      if (days == null) return ''
      if (days <= 2) return 'level-high'
      if (days <= 4) return 'level-medium'
      return 'level-low'
    }

    const recoveryClass = (status) => {
      if (!status) return ''
      const s = status.toString().toLowerCase()
      if (s.includes('full') || s.includes('完全') || s.includes('good') || s.includes('良好')) return 'level-low'
      if (s.includes('partial') || s.includes('部分') || s.includes('moderate') || s.includes('一般')) return 'level-medium'
      if (s.includes('poor') || s.includes('差') || s.includes('未恢复')) return 'level-high'
      return ''
    }

    return {
      activeTab, tabs,
      fatigueTeamId, fatigueLoading, fatigueData, loadTeamFatigue,
      densityTeamId, densityDays, densityLoading, densityData, loadFixtureDensity,
      impactTeamId, impactMatchId, impactLoading, impactData, loadFatigueImpact,
      riskLevelClass, restDayClass, recoveryClass
    }
  }
}
</script>

<style scoped>
.fatigue-analysis {
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

.text-input.short {
  max-width: 120px;
  flex: none;
  width: 120px;
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

.stat-value.level-high {
  color: #ef4444;
}

.stat-value.level-medium {
  color: #f59e0b;
}

.stat-value.level-low {
  color: #10b981;
}

.stat-sub {
  font-size: 11px;
  color: #6b7280;
  margin-top: 2px;
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

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
  margin-bottom: 8px;
}

.detail-label {
  font-size: 13px;
  color: #9ca3af;
}

.detail-value {
  font-size: 13px;
  font-weight: 500;
  color: #e5e7eb;
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
}

/* 赛程列表 */
.schedule-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.schedule-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.schedule-date {
  font-size: 12px;
  color: #10b981;
  min-width: 80px;
}

.schedule-opponent {
  font-size: 13px;
  color: #e5e7eb;
  flex: 1;
}

.schedule-type {
  font-size: 11px;
  color: #6b7280;
  background: rgba(16, 185, 129, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

/* 对比网格 */
.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.compare-team {
  padding: 14px;
  background: #0a0d14;
}

.team-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.team-title.home {
  color: #10b981;
}

.team-title.away {
  color: #60a5fa;
}

.compare-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 0;
}

.compare-label {
  font-size: 12px;
  color: #9ca3af;
}

.compare-value {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
}

.compare-value.level-high {
  color: #ef4444;
}

.compare-value.level-medium {
  color: #f59e0b;
}

.compare-value.level-low {
  color: #10b981;
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
  .compare-grid {
    grid-template-columns: 1fr;
  }
  .input-row {
    flex-wrap: wrap;
  }
  .text-input.short {
    width: 100%;
    max-width: none;
  }
}
</style>
