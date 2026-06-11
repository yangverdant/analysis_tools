<template>
  <div class="team-page">
    <!-- 球队信息头部 -->
    <section class="team-header">
      <div class="team-info">
        <h1>{{ team?.team_name_cn || team?.canonical_name || '加载中...' }}</h1>
        <p>{{ team?.country_cn || team?.country }} | {{ team?.team_type === 'national' ? '国家队' : '俱乐部' }}</p>
      </div>
    </section>

    <!-- 统计卡片 -->
    <section class="stats-section">
      <div class="stat-card">
        <div class="stat-value">{{ stats?.total_matches || 0 }}</div>
        <div class="stat-label">总比赛</div>
      </div>
      <div class="stat-card win">
        <div class="stat-value">{{ stats?.wins || 0 }}</div>
        <div class="stat-label">胜</div>
      </div>
      <div class="stat-card draw">
        <div class="stat-value">{{ stats?.draws || 0 }}</div>
        <div class="stat-label">平</div>
      </div>
      <div class="stat-card loss">
        <div class="stat-value">{{ stats?.losses || 0 }}</div>
        <div class="stat-label">负</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats?.goals_for || 0 }}</div>
        <div class="stat-label">进球</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats?.goals_against || 0 }}</div>
        <div class="stat-label">失球</div>
      </div>
    </section>

    <!-- 主内容区域 -->
    <div class="main-content">
      <!-- 左侧：近期状态和赛程 -->
      <div class="left-panel">
        <!-- 近期状态 -->
        <section class="section card">
          <div class="section-header">
            <h2><span class="icon">📊</span> 近期状态</h2>
            <span class="sub-title">最近10场</span>
          </div>
          <div class="form-display">
            <div class="form-string">
              <span v-for="(r, i) in (form?.form_string || '').split('')" :key="i"
                    class="form-badge" :class="getFormClass(r)">{{ r }}</span>
              <span v-if="!form?.form_string" class="no-data-text">暂无数据</span>
            </div>
            <div class="form-stats" v-if="form">
              <div class="stat-row">
                <span class="win">{{ form.wins || 0 }}胜</span>
                <span class="draw">{{ form.draws || 0 }}平</span>
                <span class="loss">{{ form.losses || 0 }}负</span>
              </div>
              <div class="goals-row">
                <span>进球: {{ form.goals_for || 0 }}</span>
                <span>失球: {{ form.goals_against || 0 }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 赛程密集度 -->
        <section class="section card">
          <div class="section-header">
            <h2><span class="icon">📅</span> 赛程密集度</h2>
            <span class="sub-title">未来14天</span>
          </div>
          <div class="schedule-info">
            <div class="intensity-badge" :class="schedule?.intensity">
              <span class="icon">{{ getIntensityIcon(schedule?.intensity) }}</span>
              {{ getIntensityText(schedule?.intensity) }}
            </div>
            <p class="matches-count">未来14天: {{ schedule?.matches_in_period || 0 }} 场比赛</p>
            <div class="fixtures-list" v-if="schedule?.fixtures?.length">
              <div class="fixture-item" v-for="(f, i) in schedule.fixtures" :key="i">
                <span class="date">{{ f.match_date }}</span>
                <span class="teams">{{ f.home_team_cn || f.home_team }} vs {{ f.away_team_cn || f.away_team }}</span>
                <span class="competition">{{ f.competition }}</span>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- 右侧：历史战绩 -->
      <section class="section card history-section">
        <div class="section-header">
          <h2><span class="icon">📜</span> 历史战绩</h2>
          <span class="sub-title">最近30场</span>
        </div>
        <div class="matches-list">
          <div class="match-row" v-for="match in matches" :key="match.match_id">
            <div class="match-info">
              <span class="match-date">{{ match.match_date }}</span>
              <span class="match-league">{{ match.league_cn || match.league }}</span>
            </div>
            <div class="match-content">
              <span class="teams">
                {{ match.home_team_cn || match.home_team }} {{ match.home_goals ?? '-' }} - {{ match.away_goals ?? '-' }} {{ match.away_team_cn || match.away_team }}
              </span>
            </div>
            <span class="result-badge" :class="getResultClass(match.team_result)">{{ match.team_result }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { teamAPI } from '../api'

export default {
  name: 'TeamPage',
  setup() {
    const route = useRoute()

    const team = ref(null)
    const stats = ref(null)
    const form = ref(null)
    const schedule = ref(null)
    const matches = ref([])

    const getFormClass = (result) => {
      const classes = { 'W': 'win', 'D': 'draw', 'L': 'loss' }
      return classes[result] || ''
    }

    const getIntensityIcon = (intensity) => {
      const icons = { 'high': '🔴', 'medium': '🟡', 'low': '🟢' }
      return icons[intensity] || '⚪'
    }

    const getIntensityText = (intensity) => {
      const texts = { 'high': '高强度', 'medium': '中等', 'low': '轻松' }
      return texts[intensity] || '未知'
    }

    const getResultClass = (result) => {
      const classes = { 'W': 'win', 'D': 'draw', 'L': 'loss' }
      return classes[result] || ''
    }

    const loadData = async () => {
      const teamId = route.params.id

      try {
        const teamData = await teamAPI.getTeam(teamId)
        if (teamData.data) {
          team.value = teamData.data
          stats.value = teamData.data.stats
        }

        const formData = await teamAPI.getForm(teamId, 10)
        if (formData.data) form.value = formData.data

        const scheduleData = await teamAPI.getSchedule(teamId, 14)
        if (scheduleData.data) schedule.value = scheduleData.data

        const matchesData = await teamAPI.getMatches(teamId, 30)
        if (matchesData.data) matches.value = matchesData.data

      } catch (error) {
        console.error('加载数据失败:', error)
      }
    }

    onMounted(loadData)

    return {
      team,
      stats,
      form,
      schedule,
      matches,
      getFormClass,
      getIntensityIcon,
      getIntensityText,
      getResultClass
    }
  }
}
</script>

<style scoped>
.team-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 头部样式 */
.team-header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white;
  border-radius: 12px;
  padding: 32px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.team-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
  font-weight: 700;
}

.team-header p {
  opacity: 0.7;
  font-size: 14px;
  color: #9ca3af;
}

/* 统计卡片 */
.stats-section {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}

.stat-card {
  background: #151922;
  border-radius: 10px;
  padding: 20px;
  text-align: center;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #f3f4f6;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

.stat-card.win .stat-value { color: #10b981; }
.stat-card.draw .stat-value { color: #9ca3af; }
.stat-card.loss .stat-value { color: #ef4444; }

/* 主内容区域 */
.main-content {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 24px;
}

/* 卡片样式 */
.card {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.section {
  margin-bottom: 0;
}

.section-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-header h2 {
  font-size: 14px;
  font-weight: 600;
  color: #f3f4f6;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-header h2 .icon {
  font-size: 16px;
}

.sub-title {
  font-size: 12px;
  color: #6b7280;
  background: rgba(255,255,255,0.05);
  padding: 4px 10px;
  border-radius: 10px;
}

/* 近期状态 */
.form-display {
  padding: 20px;
}

.form-string {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.form-badge {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-weight: 700;
  font-size: 14px;
}

.form-badge.win {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.form-badge.draw {
  background: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
  border: 1px solid rgba(107, 114, 128, 0.3);
}

.form-badge.loss {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.no-data-text {
  color: #6b7280;
  font-size: 14px;
}

.form-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-row {
  display: flex;
  gap: 16px;
  font-size: 14px;
  font-weight: 500;
}

.stat-row .win { color: #10b981; }
.stat-row .draw { color: #9ca3af; }
.stat-row .loss { color: #ef4444; }

.goals-row {
  display: flex;
  gap: 20px;
  color: #6b7280;
  font-size: 13px;
}

/* 赛程密集度 */
.schedule-info {
  padding: 20px;
}

.intensity-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}

.intensity-badge.high {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.intensity-badge.medium {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.intensity-badge.low {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.matches-count {
  color: #9ca3af;
  font-size: 14px;
  margin-bottom: 12px;
}

.fixtures-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fixture-item {
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
  font-size: 13px;
}

.fixture-item .date {
  color: #6b7280;
  min-width: 90px;
}

.fixture-item .teams {
  flex: 1;
  color: #e5e7eb;
}

.fixture-item .competition {
  color: #6b7280;
  font-size: 12px;
}

/* 历史战绩 */
.history-section {
  display: flex;
  flex-direction: column;
}

.matches-list {
  flex: 1;
  overflow-y: auto;
  max-height: 500px;
}

.match-row {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
  gap: 16px;
}

.match-row:hover {
  background: rgba(255,255,255,0.02);
}

.match-info {
  min-width: 180px;
}

.match-date {
  color: #6b7280;
  font-size: 12px;
  display: block;
}

.match-league {
  color: #4b5563;
  font-size: 11px;
}

.match-content {
  flex: 1;
}

.teams {
  font-weight: 500;
  color: #e5e7eb;
  font-size: 14px;
}

.result-badge {
  padding: 4px 12px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 12px;
}

.result-badge.win {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.result-badge.draw {
  background: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
}

.result-badge.loss {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

/* 响应式 */
@media (max-width: 1024px) {
  .stats-section {
    grid-template-columns: repeat(3, 1fr);
  }

  .main-content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .stats-section {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
