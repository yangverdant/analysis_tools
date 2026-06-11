<template>
  <div class="league-impact">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>联赛影响</h2>
        <p>积分形势、比赛影响与争冠保级分析</p>
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

    <!-- 积分榜 -->
    <div v-if="activeTab === 'standings'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="leagueId"
          placeholder="联赛ID"
          class="text-input"
        />
        <input
          v-model="seasonId"
          placeholder="赛季ID"
          class="text-input"
        />
        <button class="action-btn" @click="loadStandings" :disabled="standingsLoading">查询</button>
      </div>
      <div class="loading-state" v-if="standingsLoading">
        <div class="spinner"></div>
        <p>正在加载积分榜...</p>
      </div>
      <div v-else-if="standings.length > 0" class="data-table-wrap card">
        <table class="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>球队</th>
              <th>场次</th>
              <th>胜</th>
              <th>平</th>
              <th>负</th>
              <th>进球</th>
              <th>失球</th>
              <th>净胜球</th>
              <th>积分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(team, idx) in standings" :key="idx">
              <td :class="['rank-cell', rankClass(idx)]">{{ idx + 1 }}</td>
              <td class="name-cell">{{ team.team_name || team.name || '--' }}</td>
              <td>{{ team.played || team.matches || '--' }}</td>
              <td>{{ team.won || team.wins || '--' }}</td>
              <td>{{ team.drawn || team.draws || '--' }}</td>
              <td>{{ team.lost || team.losses || '--' }}</td>
              <td>{{ team.goals_for || team.gf || '--' }}</td>
              <td>{{ team.goals_against || team.ga || '--' }}</td>
              <td>{{ team.goal_difference || team.gd || '--' }}</td>
              <td class="points-cell">{{ team.points || '--' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="leagueId && seasonId && !standingsLoading" class="empty-state card">
        <p>未找到积分榜数据</p>
      </div>
    </div>

    <!-- 比赛影响 -->
    <div v-if="activeTab === 'impact'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="impactMatchId"
          placeholder="比赛ID"
          class="text-input"
          @keyup.enter="loadMatchImpact"
        />
        <button class="action-btn" @click="loadMatchImpact" :disabled="impactLoading">查询</button>
      </div>
      <div class="loading-state" v-if="impactLoading">
        <div class="spinner"></div>
        <p>正在分析比赛影响...</p>
      </div>
      <template v-else-if="matchImpact">
        <div class="outcomes-grid">
          <div class="outcome-card card home-win">
            <div class="outcome-title">主队胜</div>
            <div v-if="matchImpact.home_win" class="outcome-content">
              <div v-if="matchImpact.home_win.home_team" class="outcome-team">
                <span class="outcome-label">主队排名变化</span>
                <span class="outcome-value">{{ matchImpact.home_win.home_team.rank_change || '--' }}</span>
              </div>
              <div v-if="matchImpact.home_win.away_team" class="outcome-team">
                <span class="outcome-label">客队排名变化</span>
                <span class="outcome-value">{{ matchImpact.home_win.away_team.rank_change || '--' }}</span>
              </div>
            </div>
          </div>
          <div class="outcome-card card draw">
            <div class="outcome-title">平局</div>
            <div v-if="matchImpact.draw" class="outcome-content">
              <div v-if="matchImpact.draw.home_team" class="outcome-team">
                <span class="outcome-label">主队排名变化</span>
                <span class="outcome-value">{{ matchImpact.draw.home_team.rank_change || '--' }}</span>
              </div>
              <div v-if="matchImpact.draw.away_team" class="outcome-team">
                <span class="outcome-label">客队排名变化</span>
                <span class="outcome-value">{{ matchImpact.draw.away_team.rank_change || '--' }}</span>
              </div>
            </div>
          </div>
          <div class="outcome-card card away-win">
            <div class="outcome-title">客队胜</div>
            <div v-if="matchImpact.away_win" class="outcome-content">
              <div v-if="matchImpact.away_win.home_team" class="outcome-team">
                <span class="outcome-label">主队排名变化</span>
                <span class="outcome-value">{{ matchImpact.away_win.home_team.rank_change || '--' }}</span>
              </div>
              <div v-if="matchImpact.away_win.away_team" class="outcome-team">
                <span class="outcome-label">客队排名变化</span>
                <span class="outcome-value">{{ matchImpact.away_win.away_team.rank_change || '--' }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="matchImpact.analysis" class="detail-card card">
          <h3>影响分析</h3>
          <p>{{ matchImpact.analysis }}</p>
        </div>
      </template>
      <div v-else-if="impactMatchId && !impactLoading" class="empty-state card">
        <p>未找到该比赛影响数据</p>
      </div>
    </div>

    <!-- 降级分析 -->
    <div v-if="activeTab === 'relegation'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="relegationTeamId"
          placeholder="球队ID"
          class="text-input"
        />
        <input
          v-model="relegationLeagueId"
          placeholder="联赛ID"
          class="text-input"
        />
        <input
          v-model="relegationSeasonId"
          placeholder="赛季ID"
          class="text-input"
        />
        <button class="action-btn" @click="loadRelegationImpact" :disabled="relegationLoading">查询</button>
      </div>
      <div class="loading-state" v-if="relegationLoading">
        <div class="spinner"></div>
        <p>正在分析降级形势...</p>
      </div>
      <template v-else-if="relegationImpact">
        <div class="detail-card card">
          <h3>降级风险分析</h3>
          <div class="impact-content">
            <div v-if="relegationImpact.current_position != null" class="impact-row">
              <span class="impact-label">当前排名</span>
              <span class="impact-value">{{ relegationImpact.current_position }}</span>
            </div>
            <div v-if="relegationImpact.relegation_probability != null" class="impact-row">
              <span class="impact-label">降级概率</span>
              <span class="impact-value" :class="probClass(relegationImpact.relegation_probability)">{{ (relegationImpact.relegation_probability * 100).toFixed(1) }}%</span>
            </div>
            <div v-if="relegationImpact.points_to_safety != null" class="impact-row">
              <span class="impact-label">距安全区</span>
              <span class="impact-value accent">{{ relegationImpact.points_to_safety }}分</span>
            </div>
            <div v-if="relegationImpact.analysis" class="impact-analysis">
              <p>{{ relegationImpact.analysis }}</p>
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="relegationTeamId && !relegationLoading" class="empty-state card">
        <p>未找到降级分析数据</p>
      </div>
    </div>

    <!-- 争冠分析 -->
    <div v-if="activeTab === 'title'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="titleTeamId"
          placeholder="球队ID"
          class="text-input"
        />
        <input
          v-model="titleLeagueId"
          placeholder="联赛ID"
          class="text-input"
        />
        <input
          v-model="titleSeasonId"
          placeholder="赛季ID"
          class="text-input"
        />
        <button class="action-btn" @click="loadTitleImpact" :disabled="titleLoading">查询</button>
      </div>
      <div class="loading-state" v-if="titleLoading">
        <div class="spinner"></div>
        <p>正在分析争冠形势...</p>
      </div>
      <template v-else-if="titleImpact">
        <div class="detail-card card">
          <h3>争冠形势分析</h3>
          <div class="impact-content">
            <div v-if="titleImpact.current_position != null" class="impact-row">
              <span class="impact-label">当前排名</span>
              <span class="impact-value">{{ titleImpact.current_position }}</span>
            </div>
            <div v-if="titleImpact.title_probability != null" class="impact-row">
              <span class="impact-label">夺冠概率</span>
              <span class="impact-value accent">{{ (titleImpact.title_probability * 100).toFixed(1) }}%</span>
            </div>
            <div v-if="titleImpact.points_behind_leader != null" class="impact-row">
              <span class="impact-label">落后榜首</span>
              <span class="impact-value">{{ titleImpact.points_behind_leader }}分</span>
            </div>
            <div v-if="titleImpact.analysis" class="impact-analysis">
              <p>{{ titleImpact.analysis }}</p>
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="titleTeamId && !titleLoading" class="empty-state card">
        <p>未找到争冠分析数据</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'LeagueImpactAnalysis',
  setup() {
    const activeTab = ref('standings')
    const tabs = [
      { key: 'standings', label: '积分榜' },
      { key: 'impact', label: '比赛影响' },
      { key: 'relegation', label: '降级分析' },
      { key: 'title', label: '争冠分析' }
    ]

    // 积分榜
    const leagueId = ref('')
    const seasonId = ref('')
    const standingsLoading = ref(false)
    const standings = ref([])

    // 比赛影响
    const impactMatchId = ref('')
    const impactLoading = ref(false)
    const matchImpact = ref(null)

    // 降级分析
    const relegationTeamId = ref('')
    const relegationLeagueId = ref('')
    const relegationSeasonId = ref('')
    const relegationLoading = ref(false)
    const relegationImpact = ref(null)

    // 争冠分析
    const titleTeamId = ref('')
    const titleLeagueId = ref('')
    const titleSeasonId = ref('')
    const titleLoading = ref(false)
    const titleImpact = ref(null)

    const rankClass = (idx) => {
      if (idx < 4) return 'rank-top'
      if (idx >= 17) return 'rank-bottom'
      return ''
    }

    const probClass = (prob) => {
      if (prob >= 0.5) return 'prob-high'
      if (prob >= 0.2) return 'prob-medium'
      return 'prob-low'
    }

    const loadStandings = async () => {
      if (!leagueId.value || !seasonId.value) return
      standingsLoading.value = true
      standings.value = []
      try {
        const res = await analysisAPI.getLeagueStandings(leagueId.value, seasonId.value)
        standings.value = res.data || res || []
      } catch (e) {
        console.error('加载积分榜失败:', e)
        standings.value = []
      } finally {
        standingsLoading.value = false
      }
    }

    const loadMatchImpact = async () => {
      if (!impactMatchId.value) return
      impactLoading.value = true
      matchImpact.value = null
      try {
        const res = await analysisAPI.getMatchImpact(impactMatchId.value)
        matchImpact.value = res.data || res || null
      } catch (e) {
        console.error('加载比赛影响失败:', e)
        matchImpact.value = null
      } finally {
        impactLoading.value = false
      }
    }

    const loadRelegationImpact = async () => {
      if (!relegationTeamId.value || !relegationLeagueId.value || !relegationSeasonId.value) return
      relegationLoading.value = true
      relegationImpact.value = null
      try {
        const res = await analysisAPI.getRelegationImpact(relegationTeamId.value, relegationLeagueId.value, relegationSeasonId.value)
        relegationImpact.value = res.data || res || null
      } catch (e) {
        console.error('加载降级分析失败:', e)
        relegationImpact.value = null
      } finally {
        relegationLoading.value = false
      }
    }

    const loadTitleImpact = async () => {
      if (!titleTeamId.value || !titleLeagueId.value || !titleSeasonId.value) return
      titleLoading.value = true
      titleImpact.value = null
      try {
        const res = await analysisAPI.getTitleImpact(titleTeamId.value, titleLeagueId.value, titleSeasonId.value)
        titleImpact.value = res.data || res || null
      } catch (e) {
        console.error('加载争冠分析失败:', e)
        titleImpact.value = null
      } finally {
        titleLoading.value = false
      }
    }

    return {
      activeTab, tabs,
      leagueId, seasonId, standingsLoading, standings,
      impactMatchId, impactLoading, matchImpact,
      relegationTeamId, relegationLeagueId, relegationSeasonId, relegationLoading, relegationImpact,
      titleTeamId, titleLeagueId, titleSeasonId, titleLoading, titleImpact,
      loadStandings, loadMatchImpact, loadRelegationImpact, loadTitleImpact,
      rankClass, probClass
    }
  }
}
</script>

<style scoped>
.league-impact {
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

/* 数据表格 */
.data-table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  padding: 10px 12px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  white-space: nowrap;
}

.data-table td {
  padding: 10px 12px;
  font-size: 13px;
  color: #e5e7eb;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
}

.rank-cell {
  font-weight: 600;
  text-align: center;
}

.rank-cell.rank-top {
  color: #10b981;
}

.rank-cell.rank-bottom {
  color: #ef4444;
}

.name-cell {
  color: #e5e7eb;
  font-weight: 500;
}

.points-cell {
  font-weight: 700;
  color: #10b981;
}

/* 结果模拟 */
.outcomes-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.outcome-card {
  padding: 16px;
}

.outcome-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.home-win .outcome-title {
  color: #10b981;
}

.draw .outcome-title {
  color: #9ca3af;
}

.away-win .outcome-title {
  color: #60a5fa;
}

.outcome-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.outcome-team {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  background: #0a0d14;
  border-radius: 4px;
}

.outcome-label {
  font-size: 12px;
  color: #9ca3af;
}

.outcome-value {
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
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

.impact-value.prob-high {
  color: #ef4444;
}

.impact-value.prob-medium {
  color: #f59e0b;
}

.impact-value.prob-low {
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
  .outcomes-grid {
    grid-template-columns: 1fr;
  }

  .input-row {
    flex-wrap: wrap;
  }
}
</style>
