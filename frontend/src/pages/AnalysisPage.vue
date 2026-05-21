<template>
  <div class="analysis-page">
    <!-- 搜索区域 -->
    <section class="search-section">
      <h2>球队搜索与分析</h2>
      <div class="search-box">
        <input
          v-model="searchQuery"
          placeholder="输入球队名称..."
          @keyup.enter="searchTeams"
        />
        <button @click="searchTeams">搜索</button>
      </div>
    </section>

    <!-- 搜索结果 -->
    <section class="results-section" v-if="searchResults.length">
      <h3>搜索结果</h3>
      <div class="teams-grid">
        <div class="team-card" v-for="team in searchResults" :key="team.team_id" @click="selectTeam(team)">
          <div class="team-name">{{ team.name_cn || team.canonical_name }}</div>
          <div class="team-info">{{ team.country_cn || team.country }} | {{ team.team_type === 'national' ? '国家队' : '俱乐部' }}</div>
        </div>
      </div>
    </section>

    <!-- 球队对比分析 -->
    <section class="compare-section">
      <h2>球队对比分析</h2>
      <div class="compare-form">
        <div class="team-select-box">
          <label>主队</label>
          <div class="selected-team" v-if="selectedTeam1">
            <span class="team-badge home">{{ selectedTeam1.name_cn || selectedTeam1.canonical_name }}</span>
            <button class="remove-btn" @click="clearTeam1">&times;</button>
          </div>
          <input v-else v-model="team1Search" placeholder="搜索主队..." @input="searchTeam1" />
          <div class="search-dropdown" v-if="team1Results.length && !selectedTeam1">
            <div class="dropdown-item" v-for="team in team1Results" :key="team.team_id" @click="selectTeam1(team)">
              {{ team.name_cn || team.canonical_name }}
            </div>
          </div>
        </div>

        <div class="vs-badge">VS</div>

        <div class="team-select-box">
          <label>客队</label>
          <div class="selected-team" v-if="selectedTeam2">
            <span class="team-badge away">{{ selectedTeam2.name_cn || selectedTeam2.canonical_name }}</span>
            <button class="remove-btn" @click="clearTeam2">&times;</button>
          </div>
          <input v-else v-model="team2Search" placeholder="搜索客队..." @input="searchTeam2" />
          <div class="search-dropdown" v-if="team2Results.length && !selectedTeam2">
            <div class="dropdown-item" v-for="team in team2Results" :key="team.team_id" @click="selectTeam2(team)">
              {{ team.name_cn || team.canonical_name }}
            </div>
          </div>
        </div>

        <button class="analyze-btn" @click="analyzeComparison" :disabled="!selectedTeam1 || !selectedTeam2">
          开始分析
        </button>
      </div>
    </section>

    <!-- 对比结果 -->
    <section class="comparison-results" v-if="comparisonData">
      <h2>分析结果</h2>

      <!-- Elo对比 -->
      <div class="elo-comparison">
        <h3>Elo 评分对比</h3>
        <div v-if="comparisonData.team1.elo && comparisonData.team2.elo" class="elo-bars">
          <div class="elo-bar-container">
            <div class="elo-label">{{ comparisonData.team1.name_cn }}</div>
            <div class="elo-bar">
              <div class="elo-fill team1" :style="{ width: eloBarWidth(comparisonData.team1.elo, comparisonData.team2.elo) + '%' }"></div>
            </div>
            <div class="elo-value">{{ comparisonData.team1.elo }}</div>
          </div>
          <div class="elo-bar-container">
            <div class="elo-label">{{ comparisonData.team2.name_cn }}</div>
            <div class="elo-bar">
              <div class="elo-fill team2" :style="{ width: eloBarWidth(comparisonData.team2.elo, comparisonData.team1.elo) + '%' }"></div>
            </div>
            <div class="elo-value">{{ comparisonData.team2.elo }}</div>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无Elo数据支撑</div>
        <div class="elo-diff" v-if="comparisonData.elo_diff">
          Elo 差距: <span :class="{ positive: comparisonData.elo_diff > 0, negative: comparisonData.elo_diff < 0 }">
            {{ comparisonData.elo_diff > 0 ? '+' : '' }}{{ comparisonData.elo_diff }}
          </span>
        </div>
      </div>

      <!-- 近期状态对比 -->
      <div class="form-comparison">
        <h3>近期状态 (最近10场)</h3>
        <div v-if="comparisonData.team1.form?.matches > 0 || comparisonData.team2.form?.matches > 0" class="form-grid">
          <div class="form-column">
            <h4>{{ comparisonData.team1.name_cn }}</h4>
            <div class="form-stats" v-if="comparisonData.team1.form?.matches > 0">
              <div class="stat-row">
                <span class="stat-label">胜</span>
                <span class="stat-value win">{{ comparisonData.team1.form.wins || 0 }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">平</span>
                <span class="stat-value draw">{{ comparisonData.team1.form.draws || 0 }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">负</span>
                <span class="stat-value loss">{{ comparisonData.team1.form.losses || 0 }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">进球</span>
                <span class="stat-value">{{ comparisonData.team1.form.goals_for || 0 }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">失球</span>
                <span class="stat-value">{{ comparisonData.team1.form.goals_against || 0 }}</span>
              </div>
            </div>
            <div v-else class="no-data-tip">暂无状态数据</div>
          </div>
          <div class="form-column">
            <h4>{{ comparisonData.team2.name_cn }}</h4>
            <div class="form-stats" v-if="comparisonData.team2.form?.matches > 0">
              <div class="stat-row">
                <span class="stat-label">胜</span>
                <span class="stat-value win">{{ comparisonData.team2.form.wins || 0 }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">平</span>
                <span class="stat-value draw">{{ comparisonData.team2.form.draws || 0 }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">负</span>
                <span class="stat-value loss">{{ comparisonData.team2.form.losses || 0 }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">进球</span>
                <span class="stat-value">{{ comparisonData.team2.form.goals_for || 0 }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">失球</span>
                <span class="stat-value">{{ comparisonData.team2.form.goals_against || 0 }}</span>
              </div>
            </div>
            <div v-else class="no-data-tip">暂无状态数据</div>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无近期状态数据支撑</div>
      </div>

      <!-- 比赛预测 -->
      <div class="prediction-section">
        <h3>比赛预测</h3>
        <div v-if="comparisonData.prediction?.home_win_prob" class="prediction-bars">
          <div class="prediction-bar">
            <div class="pred-label">主胜</div>
            <div class="pred-bar">
              <div class="pred-fill home" :style="{ width: comparisonData.prediction.home_win_prob + '%' }"></div>
            </div>
            <div class="pred-value">{{ comparisonData.prediction.home_win_prob }}%</div>
          </div>
          <div class="prediction-bar">
            <div class="pred-label">平局</div>
            <div class="pred-bar">
              <div class="pred-fill draw" :style="{ width: comparisonData.prediction.draw_prob + '%' }"></div>
            </div>
            <div class="pred-value">{{ comparisonData.prediction.draw_prob }}%</div>
          </div>
          <div class="prediction-bar">
            <div class="pred-label">客胜</div>
            <div class="pred-bar">
              <div class="pred-fill away" :style="{ width: comparisonData.prediction.away_win_prob + '%' }"></div>
            </div>
            <div class="pred-value">{{ comparisonData.prediction.away_win_prob }}%</div>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无预测数据支撑</div>
        <div class="xg-prediction" v-if="comparisonData.prediction?.predicted_home_goals">
          <span>预期比分: {{ comparisonData.prediction.predicted_home_goals }} - {{ comparisonData.prediction.predicted_away_goals }}</span>
        </div>
      </div>

      <!-- 交锋记录 -->
      <div class="h2h-section" v-if="h2hData">
        <h3>历史交锋</h3>
        <div v-if="h2hData.total_matches > 0" class="h2h-stats">
          <div class="h2h-stat">
            <div class="h2h-value">{{ h2hData.team1_wins }}</div>
            <div class="h2h-label">{{ comparisonData.team1.name_cn }}胜</div>
          </div>
          <div class="h2h-stat">
            <div class="h2h-value">{{ h2hData.draws }}</div>
            <div class="h2h-label">平局</div>
          </div>
          <div class="h2h-stat">
            <div class="h2h-value">{{ h2hData.team2_wins }}</div>
            <div class="h2h-label">{{ comparisonData.team2.name_cn }}胜</div>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无历史交锋数据</div>
        <div class="h2h-matches" v-if="h2hData.matches?.length">
          <div class="match-item" v-for="match in h2hData.matches.slice(0, 10)" :key="match.match_id">
            <span class="date">{{ match.match_date }}</span>
            <span class="teams">{{ match.home_team_cn || match.home_team }} {{ match.home_goals }} - {{ match.away_goals }} {{ match.away_team_cn || match.away_team }}</span>
            <span class="league">{{ match.league }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 比赛背景分析 -->
    <section class="context-section" v-if="contextData">
      <h2>比赛背景分析</h2>

      <!-- 轮换风险提示 -->
      <div class="rotation-risk-section">
        <h3>轮换/放水风险分析</h3>
        <div v-if="contextData.home_team?.rotation_risk || contextData.away_team?.rotation_risk" class="risk-grid">
          <div class="risk-card" :class="contextData.home_team?.rotation_risk">
            <h4>{{ contextData.home_team?.name_cn }}</h4>
            <div class="risk-level">{{ getRiskLabel(contextData.home_team?.rotation_risk) }}</div>
            <div class="risk-reasons" v-if="contextData.home_team?.rotation_reasons?.length">
              <div class="reason" v-for="(reason, i) in contextData.home_team.rotation_reasons" :key="i">
                {{ reason }}
              </div>
            </div>
          </div>
          <div class="risk-card" :class="contextData.away_team?.rotation_risk">
            <h4>{{ contextData.away_team?.name_cn }}</h4>
            <div class="risk-level">{{ getRiskLabel(contextData.away_team?.rotation_risk) }}</div>
            <div class="risk-reasons" v-if="contextData.away_team?.rotation_reasons?.length">
              <div class="reason" v-for="(reason, i) in contextData.away_team.rotation_reasons" :key="i">
                {{ reason }}
              </div>
            </div>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无轮换风险分析数据</div>
      </div>

      <!-- 球队动机分析 -->
      <div class="motivation-section">
        <h3>球队战意分析</h3>
        <div v-if="contextData.home_team?.motivation || contextData.away_team?.motivation" class="motivation-grid">
          <div class="motivation-card" :class="contextData.home_team?.motivation?.motivation">
            <h4>{{ contextData.home_team?.name_cn }}</h4>
            <div class="motivation-level">{{ getMotivationLabel(contextData.home_team?.motivation?.motivation) }}</div>
            <div class="motivation-info" v-if="contextData.home_team?.motivation">
              <div class="info-row" v-if="contextData.home_team.motivation.position">
                <span>排名:</span>
                <span>{{ contextData.home_team.motivation.position }} / {{ contextData.home_team.motivation.total_teams }}</span>
              </div>
              <div class="info-row" v-if="contextData.home_team.motivation.points">
                <span>积分:</span>
                <span>{{ contextData.home_team.motivation.points }}</span>
              </div>
              <div class="reasons" v-if="contextData.home_team.motivation.reasons?.length">
                <div class="reason" v-for="(reason, i) in contextData.home_team.motivation.reasons" :key="i">
                  {{ reason }}
                </div>
              </div>
            </div>
          </div>
          <div class="motivation-card" :class="contextData.away_team?.motivation?.motivation">
            <h4>{{ contextData.away_team?.name_cn }}</h4>
            <div class="motivation-level">{{ getMotivationLabel(contextData.away_team?.motivation?.motivation) }}</div>
            <div class="motivation-info" v-if="contextData.away_team?.motivation">
              <div class="info-row" v-if="contextData.away_team.motivation.position">
                <span>排名:</span>
                <span>{{ contextData.away_team.motivation.position }} / {{ contextData.away_team.motivation.total_teams }}</span>
              </div>
              <div class="info-row" v-if="contextData.away_team.motivation.points">
                <span>积分:</span>
                <span>{{ contextData.away_team.motivation.points }}</span>
              </div>
              <div class="reasons" v-if="contextData.away_team.motivation.reasons?.length">
                <div class="reason" v-for="(reason, i) in contextData.away_team.motivation.reasons" :key="i">
                  {{ reason }}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无球队战意分析数据</div>
      </div>

      <!-- 赛程密集度 -->
      <div class="schedule-section">
        <h3>赛程密集度</h3>
        <div v-if="contextData.home_team?.schedule || contextData.away_team?.schedule" class="schedule-grid">
          <div class="schedule-card">
            <h4>{{ contextData.home_team?.name_cn }}</h4>
            <div class="intensity-value">{{ contextData.home_team?.schedule?.intensity || 0 }} 场/14天</div>
            <div class="upcoming-list" v-if="contextData.home_team?.schedule?.upcoming_fixtures?.length">
              <div class="upcoming-item" v-for="(f, i) in contextData.home_team.schedule.upcoming_fixtures.slice(0, 3)" :key="i">
                <span class="date">{{ f.match_date }}</span>
                <span class="vs">{{ f.home_team }} vs {{ f.away_team }}</span>
              </div>
            </div>
            <div v-else class="no-data-tip-small">暂无赛程数据</div>
          </div>
          <div class="schedule-card">
            <h4>{{ contextData.away_team?.name_cn }}</h4>
            <div class="intensity-value">{{ contextData.away_team?.schedule?.intensity || 0 }} 场/14天</div>
            <div class="upcoming-list" v-if="contextData.away_team?.schedule?.upcoming_fixtures?.length">
              <div class="upcoming-item" v-for="(f, i) in contextData.away_team.schedule.upcoming_fixtures.slice(0, 3)" :key="i">
                <span class="date">{{ f.match_date }}</span>
                <span class="vs">{{ f.home_team }} vs {{ f.away_team }}</span>
              </div>
            </div>
            <div v-else class="no-data-tip-small">暂无赛程数据</div>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无赛程密集度数据</div>
      </div>

      <!-- 分析总结 -->
      <div class="analysis-summary" v-if="contextData.analysis_summary?.length">
        <h3>分析总结</h3>
        <div class="summary-list">
          <div class="summary-item" v-for="(item, i) in contextData.analysis_summary" :key="i">
            <span class="bullet">•</span>
            <span>{{ item }}</span>
          </div>
        </div>
      </div>
      <div v-else class="no-data-section">
        <h3>分析总结</h3>
        <div class="no-data-tip">暂无分析总结数据</div>
      </div>
    </section>

    <!-- 比赛重要性分析 -->
    <section class="importance-section" v-if="importanceData">
      <h2>比赛重要性分析</h2>
      <p class="importance-subtitle">为什么需要赢？不能输的理由是什么？</p>

      <!-- 比赛性质 -->
      <div class="match-nature" v-if="importanceData.is_direct_competition?.is_direct_competition">
        <div class="nature-badge" :class="importanceData.importance_level">
          {{ getImportanceLabel(importanceData.importance_level) }}
        </div>
        <div class="competition-type" v-if="importanceData.is_direct_competition?.competition_type">
          {{ getCompetitionTypeLabel(importanceData.is_direct_competition.competition_type) }}
        </div>
      </div>

      <!-- 主队分析 -->
      <div class="team-importance-card">
        <h3>{{ comparisonData?.team1?.name_cn || '主队' }} - 为什么需要赢？</h3>
        <div v-if="importanceData.home_analysis?.reasons_to_win?.length" class="reasons-list">
          <div class="reason-item win" v-for="(reason, i) in importanceData.home_analysis.reasons_to_win" :key="i">
            <span class="urgency-badge" :class="reason.urgency">{{ getUrgencyLabel(reason.urgency) }}</span>
            <span class="reason-text">{{ reason.description }}</span>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无必须赢的理由分析</div>

        <h4>不能输的理由</h4>
        <div v-if="importanceData.home_analysis?.reasons_not_to_lose?.length" class="reasons-list">
          <div class="reason-item lose" v-for="(reason, i) in importanceData.home_analysis.reasons_not_to_lose" :key="i">
            <span class="urgency-badge" :class="reason.urgency">{{ getUrgencyLabel(reason.urgency) }}</span>
            <span class="reason-text">{{ reason.description }}</span>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无不能输的理由分析</div>

        <div class="pressure-indicator">
          <span class="pressure-label">压力等级:</span>
          <span class="pressure-value" :class="importanceData.home_analysis?.pressure_level">
            {{ getPressureLabel(importanceData.home_analysis?.pressure_level) }}
          </span>
          <span class="pressure-score">({{ importanceData.home_analysis?.pressure_score || 0 }}分)</span>
        </div>

        <!-- 未来赛程影响 -->
        <div v-if="importanceData.home_analysis?.upcoming_impact?.has_upcoming" class="upcoming-fixtures">
          <h4>未来赛程影响</h4>
          <div class="schedule-intensity">
            <span class="intensity-label">赛程密集度:</span>
            <span class="intensity-value" :class="importanceData.home_analysis.upcoming_impact.intensity">
              {{ getIntensityLabel(importanceData.home_analysis.upcoming_impact.intensity) }}
              ({{ importanceData.home_analysis.upcoming_impact.fixtures_count }}场/14天)
            </span>
          </div>
          <div v-if="importanceData.home_analysis.upcoming_impact.rotation_risk !== 'low'" class="rotation-warning">
            <span class="warning-icon">⚠️</span>
            <span>轮换风险: {{ getRotationRiskLabel(importanceData.home_analysis.upcoming_impact.rotation_risk) }}</span>
          </div>
          <div v-if="importanceData.home_analysis.upcoming_impact.important_fixtures?.length" class="important-upcoming">
            <div class="upcoming-label">重要比赛:</div>
            <div class="upcoming-list">
              <div class="upcoming-match" v-for="(f, i) in importanceData.home_analysis.upcoming_impact.important_fixtures.slice(0, 3)" :key="i">
                <span class="days-away">{{ f.days_until }}天后</span>
                <span class="vs-opponent">vs {{ f.opponent_name }}</span>
                <span class="fixture-league">({{ f.league_name }})</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 客队分析 -->
      <div class="team-importance-card">
        <h3>{{ comparisonData?.team2?.name_cn || '客队' }} - 为什么需要赢？</h3>
        <div v-if="importanceData.away_analysis?.reasons_to_win?.length" class="reasons-list">
          <div class="reason-item win" v-for="(reason, i) in importanceData.away_analysis.reasons_to_win" :key="i">
            <span class="urgency-badge" :class="reason.urgency">{{ getUrgencyLabel(reason.urgency) }}</span>
            <span class="reason-text">{{ reason.description }}</span>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无必须赢的理由分析</div>

        <h4>不能输的理由</h4>
        <div v-if="importanceData.away_analysis?.reasons_not_to_lose?.length" class="reasons-list">
          <div class="reason-item lose" v-for="(reason, i) in importanceData.away_analysis.reasons_not_to_lose" :key="i">
            <span class="urgency-badge" :class="reason.urgency">{{ getUrgencyLabel(reason.urgency) }}</span>
            <span class="reason-text">{{ reason.description }}</span>
          </div>
        </div>
        <div v-else class="no-data-tip">暂无不能输的理由分析</div>

        <div class="pressure-indicator">
          <span class="pressure-label">压力等级:</span>
          <span class="pressure-value" :class="importanceData.away_analysis?.pressure_level">
            {{ getPressureLabel(importanceData.away_analysis?.pressure_level) }}
          </span>
          <span class="pressure-score">({{ importanceData.away_analysis?.pressure_score || 0 }}分)</span>
        </div>

        <!-- 未来赛程影响 -->
        <div v-if="importanceData.away_analysis?.upcoming_impact?.has_upcoming" class="upcoming-fixtures">
          <h4>未来赛程影响</h4>
          <div class="schedule-intensity">
            <span class="intensity-label">赛程密集度:</span>
            <span class="intensity-value" :class="importanceData.away_analysis.upcoming_impact.intensity">
              {{ getIntensityLabel(importanceData.away_analysis.upcoming_impact.intensity) }}
              ({{ importanceData.away_analysis.upcoming_impact.fixtures_count }}场/14天)
            </span>
          </div>
          <div v-if="importanceData.away_analysis.upcoming_impact.rotation_risk !== 'low'" class="rotation-warning">
            <span class="warning-icon">⚠️</span>
            <span>轮换风险: {{ getRotationRiskLabel(importanceData.away_analysis.upcoming_impact.rotation_risk) }}</span>
          </div>
          <div v-if="importanceData.away_analysis.upcoming_impact.important_fixtures?.length" class="important-upcoming">
            <div class="upcoming-label">重要比赛:</div>
            <div class="upcoming-list">
              <div class="upcoming-match" v-for="(f, i) in importanceData.away_analysis.upcoming_impact.important_fixtures.slice(0, 3)" :key="i">
                <span class="days-away">{{ f.days_until }}天后</span>
                <span class="vs-opponent">vs {{ f.opponent_name }}</span>
                <span class="fixture-league">({{ f.league_name }})</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 综合摘要 -->
      <div class="importance-summary" v-if="importanceData.summary">
        <h3>综合分析</h3>
        <div class="summary-content">
          {{ importanceData.summary }}
        </div>
      </div>
    </section>
    <section class="importance-section" v-else-if="selectedTeam1 && selectedTeam2">
      <h2>比赛重要性分析</h2>
      <div class="no-data-tip">暂无比赛重要性分析数据，请选择联赛和赛季信息</div>
    </section>

    <!-- 分析技术说明 -->
    <section class="tech-section">
      <h2>分析技术</h2>
      <div class="tech-grid">
        <div class="tech-card">
          <h4>xG分析</h4>
          <p>预期进球模型，基于历史数据评估球队进攻和防守能力</p>
        </div>
        <div class="tech-card">
          <h4>Elo评分</h4>
          <p>动态实力评估系统，根据比赛结果实时更新球队评分</p>
        </div>
        <div class="tech-card">
          <h4>战意分析</h4>
          <p>根据排名、保级压力、争冠形势判断球队比赛动机</p>
        </div>
        <div class="tech-card">
          <h4>轮换风险</h4>
          <p>分析赛程密集度、重要比赛临近等因素判断轮换可能性</p>
        </div>
        <div class="tech-card">
          <h4>赛季形势</h4>
          <p>判断球队是否提前夺冠、提前保级或无欲无求</p>
        </div>
        <div class="tech-card">
          <h4>休息分析</h4>
          <p>计算距离上一场比赛的休息天数，评估体能状况</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { analysisAPI } from '../api'

export default {
  name: 'AnalysisPage',
  setup() {
    const route = useRoute()
    const router = useRouter()

    const searchQuery = ref('')
    const searchResults = ref([])

    const team1Search = ref('')
    const team2Search = ref('')
    const team1Results = ref([])
    const team2Results = ref([])
    const selectedTeam1 = ref(null)
    const selectedTeam2 = ref(null)

    const comparisonData = ref(null)
    const h2hData = ref(null)
    const contextData = ref(null)
    const importanceData = ref(null)

    let searchTimeout = null

    const searchTeams = async () => {
      if (!searchQuery.value.trim()) return

      try {
        const data = await analysisAPI.searchTeams(searchQuery.value)
        if (data.data) searchResults.value = data.data
      } catch (error) {
        console.error('搜索失败:', error)
      }
    }

    const searchTeam1 = async () => {
      if (searchTimeout) clearTimeout(searchTimeout)
      if (!team1Search.value.trim()) {
        team1Results.value = []
        return
      }

      searchTimeout = setTimeout(async () => {
        try {
          const data = await analysisAPI.searchTeams(team1Search.value)
          if (data.data) team1Results.value = data.data
        } catch (error) {
          console.error('搜索失败:', error)
        }
      }, 300)
    }

    const searchTeam2 = async () => {
      if (searchTimeout) clearTimeout(searchTimeout)
      if (!team2Search.value.trim()) {
        team2Results.value = []
        return
      }

      searchTimeout = setTimeout(async () => {
        try {
          const data = await analysisAPI.searchTeams(team2Search.value)
          if (data.data) team2Results.value = data.data
        } catch (error) {
          console.error('搜索失败:', error)
        }
      }, 300)
    }

    const selectTeam1 = (team) => {
      selectedTeam1.value = team
      team1Search.value = ''
      team1Results.value = []
    }

    const selectTeam2 = (team) => {
      selectedTeam2.value = team
      team2Search.value = ''
      team2Results.value = []
    }

    const clearTeam1 = () => {
      selectedTeam1.value = null
      importanceData.value = null
    }

    const clearTeam2 = () => {
      selectedTeam2.value = null
      importanceData.value = null
    }

    const selectTeam = (team) => {
      if (!selectedTeam1.value) {
        selectTeam1(team)
      } else if (!selectedTeam2.value) {
        selectTeam2(team)
      }
    }

    const analyzeComparison = async () => {
      if (!selectedTeam1.value || !selectedTeam2.value) return

      try {
        // 获取对比数据
        const compareData = await analysisAPI.compareTeams(selectedTeam1.value.team_id, selectedTeam2.value.team_id)
        if (compareData.data) comparisonData.value = compareData.data

        // 获取交锋记录
        const h2hDataRes = await analysisAPI.getHeadToHead(selectedTeam1.value.team_id, selectedTeam2.value.team_id)
        if (h2hDataRes.data) h2hData.value = h2hDataRes.data

        // 获取比赛背景分析
        const contextDataRes = await analysisAPI.getMatchContext(selectedTeam1.value.team_id, selectedTeam2.value.team_id)
        if (contextDataRes.data) contextData.value = contextDataRes.data

        // 获取比赛重要性分析（需要league_id和season_id）
        // 从交锋记录中获取最近的联赛和赛季信息
        if (h2hData.value?.matches?.length > 0) {
          const latestMatch = h2hData.value.matches[0]
          const leagueId = latestMatch.league_id || latestMatch.league
          const seasonId = latestMatch.season_id || latestMatch.season
          const matchDate = latestMatch.match_date || latestMatch.date

          if (leagueId && seasonId) {
            try {
              const importanceRes = await analysisAPI.getMatchImportance(
                selectedTeam1.value.team_id,
                selectedTeam2.value.team_id,
                leagueId,
                seasonId,
                matchDate
              )
              if (importanceRes) importanceData.value = importanceRes
            } catch (e) {
              console.warn('比赛重要性分析暂无数据:', e)
              importanceData.value = null
            }
          }
        }
      } catch (error) {
        console.error('分析失败:', error)
      }
    }

    const eloBarWidth = (elo1, elo2) => {
      const maxElo = Math.max(elo1, elo2)
      const minElo = Math.min(elo1, elo2)
      return ((elo1 - minElo) / (maxElo - minElo + 1)) * 50 + 50
    }

    const getRiskLabel = (risk) => {
      const labels = {
        low: '低风险',
        medium: '中等风险',
        high: '高风险'
      }
      return labels[risk] || '未知'
    }

    const getMotivationLabel = (motivation) => {
      const labels = {
        desperate: '必须拿分',
        high: '战意强烈',
        normal: '正常',
        low: '无欲无求',
        unknown: '未知'
      }
      return labels[motivation] || '未知'
    }

    const getImportanceLabel = (level) => {
      const labels = {
        critical: '关键战役',
        high: '重要比赛',
        medium: '普通比赛',
        low: '无关紧要'
      }
      return labels[level] || '未知'
    }

    const getCompetitionTypeLabel = (type) => {
      const labels = {
        title_race: '争冠关键战',
        european_race: '欧战资格争夺',
        relegation_battle: '保级生死战',
        position_race: '排名争夺战'
      }
      return labels[type] || ''
    }

    const getUrgencyLabel = (urgency) => {
      const labels = {
        critical: '至关重要',
        high: '非常重要',
        medium: '较为重要',
        low: '一般'
      }
      return labels[urgency] || ''
    }

    const getPressureLabel = (level) => {
      const labels = {
        critical: '极高压力',
        high: '高压力',
        medium: '中等压力',
        low: '低压力'
      }
      return labels[level] || '未知'
    }

    const getIntensityLabel = (intensity) => {
      const labels = {
        very_high: '极高',
        high: '高',
        medium: '中等',
        low: '低'
      }
      return labels[intensity] || '未知'
    }

    const getRotationRiskLabel = (risk) => {
      const labels = {
        high: '高风险（可能轮换）',
        medium: '中等风险',
        low: '低风险'
      }
      return labels[risk] || '未知'
    }

    const goToTeam = (teamId) => {
      router.push({ name: 'Team', params: { id: teamId } })
    }

    // 从URL参数加载搜索
    onMounted(() => {
      if (route.query.q) {
        searchQuery.value = route.query.q
        searchTeams()
      }
    })

    return {
      searchQuery,
      searchResults,
      team1Search,
      team2Search,
      team1Results,
      team2Results,
      selectedTeam1,
      selectedTeam2,
      comparisonData,
      h2hData,
      contextData,
      importanceData,
      searchTeams,
      searchTeam1,
      searchTeam2,
      selectTeam1,
      selectTeam2,
      selectTeam,
      analyzeComparison,
      eloBarWidth,
      getRiskLabel,
      getMotivationLabel,
      getImportanceLabel,
      getCompetitionTypeLabel,
      getUrgencyLabel,
      getPressureLabel,
      goToTeam
    }
  }
}
</script>

<style scoped>
.analysis-page {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.search-section, .results-section, .compare-section, .comparison-results, .context-section, .tech-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.search-section h2, .compare-section h2, .tech-section h2, .comparison-results h2, .context-section h2 {
  margin-bottom: 15px;
}

.search-box {
  display: flex;
  gap: 10px;
}

.search-box input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.search-box button {
  padding: 10px 20px;
  background: #1a1a2e;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.teams-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 15px;
}

.team-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 15px;
  cursor: pointer;
  transition: transform 0.2s;
}

.team-card:hover {
  transform: translateY(-2px);
}

.team-name {
  font-weight: bold;
  margin-bottom: 5px;
}

.team-info {
  font-size: 12px;
  color: #888;
}

.compare-form {
  display: flex;
  gap: 15px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.team-select-box {
  flex: 1;
  min-width: 200px;
  position: relative;
}

.team-select-box label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.team-select-box input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.selected-team {
  display: flex;
  align-items: center;
  gap: 10px;
}

.team-badge {
  background: #1a1a2e;
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
}

.team-badge.home {
  background: #3498db;
}

.team-badge.away {
  background: #e74c3c;
}

.remove-btn {
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  cursor: pointer;
}

.search-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 10;
}

.dropdown-item {
  padding: 10px;
  cursor: pointer;
}

.dropdown-item:hover {
  background: #f5f7fa;
}

.vs-badge {
  font-size: 24px;
  font-weight: bold;
  color: #888;
  align-self: center;
}

.analyze-btn {
  padding: 12px 24px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.analyze-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

/* Elo对比 */
.elo-comparison {
  margin-bottom: 30px;
}

.elo-bars {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.elo-bar-container {
  display: flex;
  align-items: center;
  gap: 15px;
}

.elo-label {
  min-width: 150px;
  font-weight: 500;
}

.elo-bar {
  flex: 1;
  height: 24px;
  background: #f0f0f0;
  border-radius: 12px;
  overflow: hidden;
}

.elo-fill {
  height: 100%;
  border-radius: 12px;
  transition: width 0.5s ease;
}

.elo-fill.team1 {
  background: linear-gradient(90deg, #3498db, #2980b9);
}

.elo-fill.team2 {
  background: linear-gradient(90deg, #e74c3c, #c0392b);
}

.elo-value {
  min-width: 60px;
  text-align: right;
  font-weight: bold;
  font-size: 18px;
}

.elo-diff {
  text-align: center;
  margin-top: 10px;
  font-size: 14px;
}

.elo-diff .positive {
  color: #27ae60;
}

.elo-diff .negative {
  color: #e74c3c;
}

/* 近期状态 */
.form-comparison {
  margin-bottom: 30px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30px;
}

.form-column h4 {
  margin-bottom: 15px;
  text-align: center;
}

.form-stats {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stat-value {
  font-weight: bold;
}

.stat-value.win {
  color: #27ae60;
}

.stat-value.draw {
  color: #f39c12;
}

.stat-value.loss {
  color: #e74c3c;
}

/* 预测 */
.prediction-section {
  margin-bottom: 30px;
}

.prediction-bars {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.prediction-bar {
  display: flex;
  align-items: center;
  gap: 15px;
}

.pred-label {
  min-width: 60px;
}

.pred-bar {
  flex: 1;
  height: 20px;
  background: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
}

.pred-fill {
  height: 100%;
  border-radius: 10px;
  transition: width 0.5s ease;
}

.pred-fill.home {
  background: linear-gradient(90deg, #3498db, #2980b9);
}

.pred-fill.draw {
  background: linear-gradient(90deg, #f39c12, #e67e22);
}

.pred-fill.away {
  background: linear-gradient(90deg, #e74c3c, #c0392b);
}

.pred-value {
  min-width: 50px;
  text-align: right;
  font-weight: bold;
}

.xg-prediction {
  text-align: center;
  margin-top: 15px;
  font-size: 18px;
  font-weight: 500;
}

/* 交锋记录 */
.h2h-section {
  margin-bottom: 30px;
}

.h2h-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.h2h-stat {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.h2h-value {
  font-size: 32px;
  font-weight: bold;
  color: #1a1a2e;
}

.h2h-label {
  font-size: 14px;
  color: #888;
  margin-top: 5px;
}

.h2h-matches {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.match-item {
  display: flex;
  gap: 15px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.match-item .date {
  color: #888;
  min-width: 100px;
}

.match-item .teams {
  flex: 1;
}

.match-item .league {
  color: #888;
  font-size: 12px;
}

/* 轮换风险 */
.rotation-risk-section {
  margin-bottom: 30px;
}

.risk-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.risk-card {
  padding: 20px;
  border-radius: 8px;
  background: #f5f7fa;
}

.risk-card.low {
  border-left: 4px solid #27ae60;
}

.risk-card.medium {
  border-left: 4px solid #f39c12;
}

.risk-card.high {
  border-left: 4px solid #e74c3c;
}

.risk-card h4 {
  margin-bottom: 10px;
}

.risk-level {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 10px;
}

.risk-card.low .risk-level {
  color: #27ae60;
}

.risk-card.medium .risk-level {
  color: #f39c12;
}

.risk-card.high .risk-level {
  color: #e74c3c;
}

.risk-reasons .reason {
  padding: 5px 0;
  font-size: 14px;
  color: #666;
}

/* 动机分析 */
.motivation-section {
  margin-bottom: 30px;
}

.motivation-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.motivation-card {
  padding: 20px;
  border-radius: 8px;
  background: #f5f7fa;
}

.motivation-card.desperate {
  border-left: 4px solid #e74c3c;
  background: #fff5f5;
}

.motivation-card.high {
  border-left: 4px solid #27ae60;
}

.motivation-card.normal {
  border-left: 4px solid #3498db;
}

.motivation-card.low {
  border-left: 4px solid #95a5a6;
  background: #f8f9fa;
}

.motivation-card h4 {
  margin-bottom: 10px;
}

.motivation-level {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 10px;
}

.motivation-card.desperate .motivation-level {
  color: #e74c3c;
}

.motivation-card.high .motivation-level {
  color: #27ae60;
}

.motivation-card.normal .motivation-level {
  color: #3498db;
}

.motivation-card.low .motivation-level {
  color: #95a5a6;
}

.motivation-info .info-row {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  font-size: 14px;
}

.motivation-info .reasons {
  margin-top: 10px;
}

.motivation-info .reason {
  padding: 3px 0;
  font-size: 13px;
  color: #666;
}

/* 赛程密集度 */
.schedule-section {
  margin-bottom: 30px;
}

.schedule-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.schedule-card {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.schedule-card h4 {
  margin-bottom: 10px;
}

.intensity-value {
  font-size: 24px;
  font-weight: bold;
  color: #1a1a2e;
  margin-bottom: 15px;
}

.upcoming-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upcoming-item {
  display: flex;
  gap: 10px;
  font-size: 13px;
}

.upcoming-item .date {
  color: #888;
  min-width: 80px;
}

/* 分析总结 */
.analysis-summary {
  background: #e8f4fd;
  border-radius: 8px;
  padding: 20px;
}

.analysis-summary h3 {
  margin-bottom: 15px;
  color: #2980b9;
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.summary-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.summary-item .bullet {
  color: #2980b9;
  font-weight: bold;
}

/* 技术卡片 */
.tech-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
}

.tech-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white;
  border-radius: 8px;
  padding: 20px;
}

.tech-card h4 {
  margin-bottom: 10px;
}

.tech-card p {
  font-size: 14px;
  opacity: 0.8;
}

/* 无数据提示样式 */
.no-data-tip {
  padding: 20px;
  text-align: center;
  color: #888;
  font-size: 14px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px dashed #ddd;
}

.no-data-tip-small {
  padding: 10px;
  text-align: center;
  color: #888;
  font-size: 12px;
  background: #f0f0f0;
  border-radius: 4px;
}

.no-data-section {
  margin-bottom: 30px;
}

.no-data-section h3 {
  margin-bottom: 15px;
}

@media (max-width: 768px) {
  .form-grid, .risk-grid, .motivation-grid, .schedule-grid {
    grid-template-columns: 1fr;
  }

  .tech-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .compare-form {
    flex-direction: column;
  }

  .team-select-box {
    width: 100%;
  }
}

/* 比赛重要性分析 */
.importance-section {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 24px;
}

.importance-section h2 {
  margin-bottom: 8px;
}

.importance-subtitle {
  color: #666;
  margin-bottom: 20px;
}

.match-nature {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
}

.nature-badge {
  padding: 8px 16px;
  border-radius: 20px;
  font-weight: bold;
  font-size: 14px;
}

.nature-badge.critical {
  background: #e74c3c;
  color: white;
}

.nature-badge.high {
  background: #f39c12;
  color: white;
}

.nature-badge.medium {
  background: #3498db;
  color: white;
}

.nature-badge.low {
  background: #95a5a6;
  color: white;
}

.competition-type {
  font-size: 14px;
  color: #666;
}

.team-importance-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.team-importance-card h3 {
  margin-bottom: 15px;
  color: #2c3e50;
}

.team-importance-card h4 {
  margin: 20px 0 10px;
  color: #666;
  font-size: 14px;
}

.reasons-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reason-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border-radius: 6px;
}

.reason-item.win {
  background: #e8f5e9;
  border-left: 3px solid #27ae60;
}

.reason-item.lose {
  background: #ffebee;
  border-left: 3px solid #e74c3c;
}

.urgency-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: bold;
  white-space: nowrap;
}

.urgency-badge.critical {
  background: #e74c3c;
  color: white;
}

.urgency-badge.high {
  background: #f39c12;
  color: white;
}

.urgency-badge.medium {
  background: #3498db;
  color: white;
}

.urgency-badge.low {
  background: #95a5a6;
  color: white;
}

.reason-text {
  flex: 1;
  font-size: 14px;
  color: #333;
}

.pressure-indicator {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #eee;
  display: flex;
  align-items: center;
  gap: 10px;
}

.pressure-label {
  font-size: 14px;
  color: #666;
}

.pressure-value {
  font-weight: bold;
  font-size: 14px;
}

.pressure-value.critical {
  color: #e74c3c;
}

.pressure-value.high {
  color: #f39c12;
}

.pressure-value.medium {
  color: #3498db;
}

.pressure-value.low {
  color: #95a5a6;
}

.pressure-score {
  font-size: 12px;
  color: #888;
}

.importance-summary {
  background: white;
  border-radius: 8px;
  padding: 20px;
  white-space: pre-line;
  line-height: 1.8;
  color: #333;
}

.upcoming-fixtures {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #eee;
}

.upcoming-fixtures h4 {
  margin: 0 0 12px 0;
  color: #2c3e50;
  font-size: 14px;
}

.schedule-intensity {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.intensity-label {
  font-size: 13px;
  color: #666;
}

.intensity-value {
  font-weight: bold;
  font-size: 13px;
}

.intensity-value.very_high {
  color: #e74c3c;
}

.intensity-value.high {
  color: #f39c12;
}

.intensity-value.medium {
  color: #3498db;
}

.intensity-value.low {
  color: #27ae60;
}

.rotation-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fff3e0;
  border-radius: 6px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #e65100;
}

.warning-icon {
  font-size: 16px;
}

.important-upcoming {
  margin-top: 10px;
}

.upcoming-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.upcoming-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.upcoming-match {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 13px;
}

.days-away {
  color: #e74c3c;
  font-weight: bold;
  min-width: 60px;
}

.vs-opponent {
  color: #333;
}

.fixture-league {
  color: #888;
  font-size: 12px;
}

.importance-summary h3 {
  margin-bottom: 15px;
  color: #2c3e50;
}

.summary-content {
  font-size: 14px;
}
</style>
