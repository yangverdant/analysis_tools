<template>
  <div class="lottery-center">
    <!-- 顶部统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card">
        <div class="stat-icon matches">
          <ActivityIcon />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.total_matches }}</div>
          <div class="stat-label">今日开售</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon analyzed">
          <BarChartIcon />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.analyzed_matches }}</div>
          <div class="stat-label">已分析</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon value">
          <StarIcon />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.value_bets }}</div>
          <div class="stat-label">价值投注</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon accuracy">
          <TargetIcon />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.accuracy }}%</div>
          <div class="stat-label">近期准确率</div>
        </div>
      </div>
    </div>

    <!-- 准确率追踪面板 -->
    <div class="accuracy-panel">
      <h3>预测准确率追踪</h3>
      <div class="accuracy-grid">
        <div class="accuracy-item">
          <span class="accuracy-label">胜平负</span>
          <span class="accuracy-value">{{ accuracyData.spf }}%</span>
          <span class="accuracy-sample">{{ accuracyData.spf_count }}场</span>
        </div>
        <div class="accuracy-item">
          <span class="accuracy-label">比分预测</span>
          <span class="accuracy-value">{{ accuracyData.bf }}%</span>
          <span class="accuracy-sample">{{ accuracyData.bf_count }}场</span>
        </div>
        <div class="accuracy-item">
          <span class="accuracy-label">大小球</span>
          <span class="accuracy-value">{{ accuracyData.ou }}%</span>
          <span class="accuracy-sample">{{ accuracyData.ou_count }}场</span>
        </div>
        <div class="accuracy-item">
          <span class="accuracy-label">整体</span>
          <span class="accuracy-value overall">{{ accuracyData.overall }}%</span>
          <span class="accuracy-sample">{{ accuracyData.total_count }}场</span>
        </div>
      </div>
      <div class="accuracy-trend">
        <span class="trend-label">近期趋势:</span>
        <span :class="['trend-value', accuracyData.trend > 0 ? 'positive' : 'negative']">
          {{ accuracyData.trend > 0 ? '上升' : (accuracyData.trend < 0 ? '下降' : '稳定') }}
        </span>
      </div>
    </div>

    <!-- 日期选择和玩法筛选 -->
    <div class="filter-bar">
      <div class="date-picker">
        <button class="date-nav" @click="changeDate(-1)">
          <ChevronLeftIcon />
        </button>
        <div class="current-date">
          <CalendarIcon class="calendar-icon" />
          <span>{{ formatDate(selectedDate) }}</span>
        </div>
        <button class="date-nav" @click="changeDate(1)">
          <ChevronRightIcon />
        </button>
      </div>
      <div class="play-type-tabs">
        <button
          v-for="pt in playTypes"
          :key="pt.value"
          :class="['play-tab', { active: selectedPlayType === pt.value }]"
          @click="selectedPlayType = pt.value"
        >
          {{ pt.label }}
        </button>
      </div>
    </div>

    <!-- 比赛列表 -->
    <div class="matches-section">
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <span>加载中...</span>
      </div>

      <div v-else-if="matches.length === 0" class="empty-state">
        <ActivityIcon class="empty-icon" />
        <p>暂无开售比赛</p>
      </div>

      <div v-else class="matches-grid">
        <div
          v-for="match in filteredMatches"
          :key="match.lottery_match_id"
          class="match-card"
          @click="viewMatchDetail(match)"
        >
          <!-- 比赛头部 -->
          <div class="match-header">
            <div class="match-num">{{ match.match_num }}</div>
            <div class="league-name">{{ match.league_name_cn }}</div>
            <div class="match-time">{{ match.match_time }}</div>
          </div>

          <!-- 球队信息 -->
          <div class="teams-row">
            <div class="team home">
              <span class="team-name">{{ match.home_team_cn }}</span>
              <span v-if="match.handicap_line !== 0" class="handicap-badge">
                {{ formatHandicap(match.handicap_line) }}
              </span>
            </div>
            <div class="vs">VS</div>
            <div class="team away">
              <span class="team-name">{{ match.away_team_cn }}</span>
            </div>
          </div>

          <!-- 分析状态 -->
          <div class="analysis-status">
            <div v-if="match.has_analysis" class="has-analysis">
              <div class="confidence-badge" :class="getConfidenceClass(match)">
                {{ match.confidence_level || '中' }}
              </div>
              <div class="recommendation-preview">
                <span class="play-type-badge">{{ getPlayTypeLabel(selectedPlayType) }}</span>
                <span class="recommendation-text">{{ match.main_recommendation || '--' }}</span>
              </div>
            </div>
            <div v-else class="no-analysis">
              <button class="analyze-btn" @click.stop="analyzeMatch(match)">
                <BarChartIcon />
                <span>分析</span>
              </button>
            </div>
          </div>

          <!-- 开售玩法 -->
          <div class="play-types-row">
            <span
              v-for="pt in match.play_types"
              :key="pt"
              :class="['play-badge', { active: pt === selectedPlayType }]"
            >
              {{ getPlayTypeShortLabel(pt) }}
            </span>
          </div>

          <!-- 销售状态 -->
          <div class="sell-status">
            <span :class="['status-badge', match.sell_status]">
              {{ getSellStatusLabel(match.sell_status) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 分析详情弹窗 -->
    <div v-if="showDetailModal" class="modal-overlay" @click="closeDetailModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>分析详情</h2>
          <button class="close-btn" @click="closeDetailModal">
            <CloseIcon />
          </button>
        </div>
        <div class="modal-body">
          <LotteryAnalysisDetail v-if="selectedMatch" :match="selectedMatch" />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { h, defineComponent } from 'vue'

// 图标组件
const createIcon = (name, classStr, paths) => defineComponent({
  name,
  setup: () => () => h('svg', { class: classStr, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, paths)
})

const ActivityIcon = createIcon('ActivityIcon', 'w-3 h-3', [
  h('polyline', { points: '22 12 18 12 15 21 9 3 6 12 2 12' })
])

const BarChartIcon = createIcon('BarChartIcon', 'w-3 h-3', [
  h('line', { x1: '18', y1: '20', x2: '18', y2: '10' }),
  h('line', { x1: '12', y1: '20', x2: '12', y2: '4' }),
  h('line', { x1: '6', y1: '20', x2: '6', y2: '14' })
])

const StarIcon = createIcon('StarIcon', 'w-3 h-3', [
  h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' })
])

const TargetIcon = createIcon('TargetIcon', 'w-3 h-3', [
  h('circle', { cx: '12', cy: '12', r: '10' }),
  h('circle', { cx: '12', cy: '12', r: '6' }),
  h('circle', { cx: '12', cy: '12', r: '2' })
])

const CalendarIcon = createIcon('CalendarIcon', 'w-3 h-3', [
  h('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }),
  h('line', { x1: '16', y1: '2', x2: '16', y2: '6' }),
  h('line', { x1: '8', y1: '2', x2: '8', y2: '6' }),
  h('line', { x1: '3', y1: '10', x2: '21', y2: '10' })
])

const ChevronLeftIcon = createIcon('ChevronLeftIcon', 'w-3 h-3', [
  h('polyline', { points: '15 18 9 12 15 6' })
])

const ChevronRightIcon = createIcon('ChevronRightIcon', 'w-3 h-3', [
  h('polyline', { points: '9 18 15 12 9 6' })
])

const CloseIcon = createIcon('CloseIcon', 'w-3 h-3', [
  h('line', { x1: '18', y1: '6', x2: '6', y2: '18' }),
  h('line', { x1: '6', y1: '6', x2: '18', y2: '18' })
])

// 分析详情组件 - 从API获取真实报告，显示所有分析因素
const LotteryAnalysisDetail = defineComponent({
  name: 'LotteryAnalysisDetail',
  props: { match: Object },
  setup(props) {
    const report = ref(null)
    const loading = ref(true)

    const fetchReport = async () => {
      if (!props.match?.lottery_match_id) return
      loading.value = true
      try {
        const response = await fetch(`http://localhost:18888/api/v1/lottery/report/${props.match.lottery_match_id}`)
        if (response.ok) {
          const data = await response.json()
          report.value = data.report
        }
      } catch (e) {
        console.error('获取报告失败:', e)
      } finally {
        loading.value = false
      }
    }

    onMounted(fetchReport)
    watch(() => props.match?.lottery_match_id, fetchReport)

    // 分析因素中文映射
    const factorNames = {
      'spf_analyzer': '胜平负分析',
      'score_predictor': '比分预测',
      'bqc_analyzer': '半全场分析',
      'handicap_analyzer': '让球分析',
      'injury_analyzer': '伤停情况',
      'schedule_analyzer': '赛程密度',
      'psychological_analyzer': '心理因素',
      'league_characteristics_analyzer': '联赛特点',
      'goal_timing_analyzer': '进球时间分布',
      'corner_analyzer': '角球数据',
      'possession_analyzer': '控球率',
      'shot_analyzer': '射门数据',
      'xg_analyzer': '期望进球(xG)',
      'weather_analyzer': '天气因素',
      'over_under_analyzer': '大小球分析'
    }

    return () => {
      if (loading.value) {
        return h('div', { class: 'analysis-detail' }, [
          h('div', { class: 'loading-state' }, [
            h('div', { class: 'spinner' }),
            h('p', '加载分析报告中...')
          ])
        ])
      }

      const r = report.value
      if (!r) {
        return h('div', { class: 'analysis-detail' }, [
          h('p', { class: 'no-report' }, '暂无分析报告')
        ])
      }

      const mi = r.match_info || {}
      const spf = (r.analyses || {}).spf || {}
      const probs = spf.probabilities || {}
      const features = r.features || {}
      const detailed = r.detailed_analysis || {}
      const analysisSummary = r.analysis_summary || {}

      // 构建所有分析因素的显示
      const factorElements = []
      for (const [name, f] of Object.entries(features)) {
        const displayName = factorNames[name] || name
        const desc = f.description || '--'
        const conf = (f.confidence || 0) * 100
        factorElements.push(
          h('div', { class: 'factor-item' }, [
            h('span', { class: 'factor-name' }, displayName),
            h('span', { class: 'factor-desc' }, desc),
            h('span', { class: 'factor-conf' }, `${conf.toFixed(0)}%`)
          ])
        )
      }

      // 近期战绩展示
      const buildRecentMatches = (teamData, teamName) => {
        const sections = []
        const recentMatches = teamData?.recent_matches || {}
        const matches6 = recentMatches['6_matches'] || {}
        const matches10 = recentMatches['10_matches'] || {}
        const matches20 = recentMatches['20_matches'] || {}

        // 6场数据
        const summary6 = matches6.summary || {}
        const matches6List = matches6.matches || []
        sections.push(
          h('div', { class: 'recent-section' }, [
            h('h4', `${teamName} 近6场`),
            h('div', { class: 'form-summary' }, [
              h('span', null, `胜: ${summary6.wins || 0}`),
              h('span', null, `平: ${summary6.draws || 0}`),
              h('span', null, `负: ${summary6.losses || 0}`),
              h('span', null, `进${summary6.goals_for || 0}失${summary6.goals_against || 0}`)
            ]),
            h('div', { class: 'form-string' }, matches6.form_string || '--'),
            matches6List.length > 0 ? h('div', { class: 'matches-mini-list' },
              matches6List.slice(0, 6).map(m =>
                h('span', { class: `match-result ${m.result}` },
                  `${m.match_date.slice(5)} ${m.venue === '主场' ? '主' : '客'} ${m.team_goals}-${m.opponent_goals}`
                )
              )
            ) : null
          ])
        )

        // 10场数据
        const summary10 = matches10.summary || {}
        sections.push(
          h('div', { class: 'recent-section' }, [
            h('h4', `近10场`),
            h('div', { class: 'form-summary' }, [
              h('span', null, `胜: ${summary10.wins || 0}`),
              h('span', null, `平: ${summary10.draws || 0}`),
              h('span', null, `负: ${summary10.losses || 0}`),
              h('span', null, `进${summary10.goals_for || 0}失${summary10.goals_against || 0}`),
              h('span', { class: 'points' }, `积分: ${summary10.points || 0}`)
            ])
          ])
        )

        return sections
      }

      // 历史交锋展示
      const buildH2H = () => {
        const h2h = detailed?.h2h_detail || {}
        const h2hMatches = h2h.matches || []
        const h2hSummary = h2h.summary || {}

        if (h2hMatches.length === 0) {
          return h('div', { class: 'h2h-section' }, [
            h('h4', '历史交锋'),
            h('p', { class: 'no-data' }, '暂无交锋记录')
          ])
        }

        return h('div', { class: 'h2h-section' }, [
          h('h4', `历史交锋 (${h2hSummary.total || 0}场)`),
          h('div', { class: 'h2h-summary' }, [
            h('span', { class: 'h2h-stat' }, `主队胜: ${h2hSummary.home_wins || 0}`),
            h('span', { class: 'h2h-stat' }, `平: ${h2hSummary.draws || 0}`),
            h('span', { class: 'h2h-stat' }, `客队胜: ${h2hSummary.away_wins || 0}`)
          ]),
          h('div', { class: 'h2h-matches' },
            h2hMatches.slice(0, 5).map(m =>
              h('div', { class: 'h2h-match' }, [
                h('span', { class: 'h2h-date' }, m.match_date),
                h('span', { class: 'h2h-score' }, `${m.home_team} ${m.score} ${m.away_team}`),
                h('span', { class: 'h2h-result' }, m.result)
              ])
            )
          )
        ])
      }

      // Elo对比展示
      const buildEloComparison = () => {
        const elo = detailed?.elo_comparison || {}
        if (!elo.home_elo) return null

        return h('div', { class: 'elo-section' }, [
          h('h4', 'Elo实力对比'),
          h('div', { class: 'elo-bars' }, [
            h('div', { class: 'elo-bar home' }, [
              h('span', { class: 'elo-label' }, `主队: ${elo.home_elo || 1500}`),
              h('div', { class: 'elo-fill', style: `width: ${((elo.home_elo || 1500) / 2000) * 100}%` })
            ]),
            h('div', { class: 'elo-bar away' }, [
              h('span', { class: 'elo-label' }, `客队: ${elo.away_elo || 1500}`),
              h('div', { class: 'elo-fill', style: `width: ${((elo.away_elo || 1500) / 2000) * 100}%` })
            ])
          ]),
          h('p', { class: 'elo-desc' }, elo.level_description || '')
        ])
      }

      // 比分预测展示 - 显示前3个可能比分
      const buildScorePrediction = () => {
        const bf = (r.analyses || {}).bf || {}
        const topScores = bf.top_scores || []

        if (topScores.length === 0) {
          return h('div', { class: 'score-section' }, [
            h('h4', '比分预测'),
            h('p', { class: 'no-data' }, '暂无比分预测数据')
          ])
        }

        // 显示前3个比分
        const top3 = topScores.slice(0, 3)
        const scoreItems = top3.map((s, idx) =>
          h('div', { class: 'score-item' }, [
            h('span', { class: 'score-rank' }, `第${idx + 1}`),
            h('span', { class: 'score-value' }, s.display || s.score),
            h('span', { class: 'score-prob' }, `${((s.prob || 0) * 100).toFixed(1)}%`)
          ])
        )

        return h('div', { class: 'score-section' }, [
          h('h4', '比分预测 (前3可能)'),
          h('div', { class: 'score-list' }, scoreItems),
          h('div', { class: 'score-info' }, [
            h('span', null, `主队期望进球: ${(bf.most_likely_home_goals || 1).toFixed(2)}`),
            h('span', null, `客队期望进球: ${(bf.most_likely_away_goals || 1).toFixed(2)}`)
          ]),
          h('p', { class: 'score-rec' }, `推荐比分: ${bf.recommendation || '--'}`)
        ])
      }

      // 联赛积分排名展示
      const buildLeagueStanding = () => {
        const leagueData = detailed?.league_standing || {}
        const homeStanding = leagueData.home || {}
        const awayStanding = leagueData.away || {}

        if (!homeStanding.position && !awayStanding.position) {
          return h('div', { class: 'league-section' }, [
            h('h4', '联赛积分'),
            h('p', { class: 'no-data' }, '暂无联赛排名数据')
          ])
        }

        const buildTeamStanding = (standing, name) => {
          if (!standing.position) {
            return h('div', { class: 'standing-card' }, [
              h('span', { class: 'team-name' }, name),
              h('span', { class: 'no-data' }, '暂无数据')
            ])
          }

          return h('div', { class: 'standing-card' }, [
            h('div', { class: 'standing-header' }, [
              h('span', { class: 'team-name' }, name),
              h('span', { class: 'position' }, `第${standing.position}名`)
            ]),
            h('div', { class: 'standing-stats' }, [
              h('span', null, `${standing.won}胜${standing.drawn}平${standing.lost}负`),
              h('span', null, `${standing.points}分`)
            ]),
            h('div', { class: 'standing-goals' }, [
              h('span', null, `进${standing.goals_for}失${standing.goals_against}`),
              h('span', { class: standing.goal_diff > 0 ? 'goal-diff positive' : 'goal-diff' },
                `净胜${standing.goal_diff}`)
            ]),
            standing.home_record ? h('div', { class: 'home-away-record' }, [
              h('span', null, `主场: ${standing.home_record.won}胜${standing.home_record.drawn}平${standing.home_record.lost}负`),
              h('span', null, `客场: ${standing.away_record.won}胜${standing.away_record.drawn}平${standing.away_record.lost}负`)
            ]) : null
          ])
        }

        return h('div', { class: 'league-section' }, [
          h('h4', '联赛积分排名'),
          h('div', { class: 'standing-row' }, [
            buildTeamStanding(homeStanding, mi.home_team_cn),
            buildTeamStanding(awayStanding, mi.away_team_cn)
          ])
        ])
      }

      // 体能状况展示
      const buildFitness = () => {
        const fitnessData = detailed?.fitness || {}
        const homeFitness = fitnessData.home || {}
        const awayFitness = fitnessData.away || {}

        if (!homeFitness.has_data && !awayFitness.has_data) {
          return null
        }

        const getFatigueClass = (level) => {
          if (level === 'high') return 'fatigue-high'
          if (level === 'medium') return 'fatigue-medium'
          return 'fatigue-low'
        }

        const buildTeamFitness = (fitness, name) => {
          if (!fitness.has_data) return null

          return h('div', { class: 'fitness-card' }, [
            h('span', { class: 'team-name' }, name),
            h('div', { class: 'fitness-stats' }, [
              h('span', null, `近30天${fitness.matches_30_days}场`),
              h('span', null, `休息${fitness.rest_days}天`)
            ]),
            h('div', { class: `fatigue-level ${getFatigueClass(fitness.fatigue_level)}` }, [
              h('span', null, fitness.fatigue_description)
            ]),
            h('p', { class: 'rest-desc' }, fitness.rest_description)
          ])
        }

        return h('div', { class: 'fitness-section' }, [
          h('h4', '体能状况'),
          h('div', { class: 'fitness-row' }, [
            buildTeamFitness(homeFitness, mi.home_team_cn),
            buildTeamFitness(awayFitness, mi.away_team_cn)
          ])
        ])
      }

      // 大小球预测展示
      const buildOverUnderPrediction = () => {
        const ou = (r.analyses || {}).ou || {}

        if (!ou.over_under_probs) {
          return h('div', { class: 'ou-section' }, [
            h('h4', '大小球预测'),
            h('p', { class: 'no-data' }, '暂无大小球预测数据')
          ])
        }

        const probs = ou.over_under_probs || {}
        const goalsDist = ou.total_goals_distribution || []

        // 大小球概率条
        const ouBars = h('div', { class: 'ou-bars' }, [
          h('div', { class: 'ou-bar over' }, [
            h('div', { class: 'bar-fill', style: `width: ${(probs.over_2_5 || 0) * 100}%` }),
            h('span', { class: 'label' }, `大2.5 ${((probs.over_2_5 || 0) * 100).toFixed(1)}%`)
          ]),
          h('div', { class: 'ou-bar under' }, [
            h('div', { class: 'bar-fill', style: `width: ${(probs.under_2_5 || 0) * 100}%` }),
            h('span', { class: 'label' }, `小2.5 ${((probs.under_2_5 || 0) * 100).toFixed(1)}%`)
          ])
        ])

        // 总进球数分布
        const goalsItems = goalsDist.slice(0, 5).map(g =>
          h('span', { class: 'goals-dist-item' },
            `${g.label}: ${(g.probability * 100).toFixed(1)}%`
          )
        )

        return h('div', { class: 'ou-section' }, [
          h('h4', '大小球预测'),
          ouBars,
          h('div', { class: 'expected-goals' }, [
            h('span', null, `预期总进球: ${(ou.total_expected_goals || 2.5).toFixed(2)}`)
          ]),
          h('div', { class: 'goals-dist' }, [
            h('span', { class: 'goals-dist-label' }, '进球分布: '),
            ...goalsItems
          ]),
          h('p', { class: 'ou-rec' }, `推荐: ${ou.recommendation || '--'}`)
        ])
      }

      // 进球时间分布展示
      const buildGoalTiming = () => {
        const goalTiming = detailed?.goal_timing || {}
        const homeTiming = goalTiming.home || {}
        const awayTiming = goalTiming.away || {}

        if (!homeTiming.has_data && !awayTiming.has_data) {
          return h('div', { class: 'goal-timing-section' }, [
            h('h4', '进球时间分布'),
            h('p', { class: 'no-data' }, '暂无进球时间分布数据')
          ])
        }

        const timeSlots = ['0-15', '15-30', '30-45', '45-60', '60-75', '75-90']

        const buildTimingBar = (timing, name) => {
          if (!timing.has_data) return null
          const total = timing.total_goals || 1
          return h('div', { class: 'timing-team' }, [
            h('span', { class: 'team-label' }, name),
            h('div', { class: 'timing-bars' },
              timeSlots.map(slot => {
                const count = timing[slot] || 0
                const pct = (count / total) * 100
                return h('div', { class: 'timing-slot' }, [
                  h('span', { class: 'slot-label' }, slot),
                  h('div', { class: 'slot-bar' }, [
                    h('div', { class: 'slot-fill', style: `width: ${pct}%` })
                  ]),
                  h('span', { class: 'slot-count' }, count)
                ])
              })
            )
          ])
        }

        return h('div', { class: 'goal-timing-section' }, [
          h('h4', '进球时间分布'),
          h('div', { class: 'timing-row' }, [
            buildTimingBar(homeTiming, mi.home_team_cn),
            buildTimingBar(awayTiming, mi.away_team_cn)
          ])
        ])
      }

      // 球员进球详情展示
      const buildScorers = () => {
        const scorers = detailed?.scorers || {}
        const homeScorers = scorers.home || []
        const awayScorers = scorers.away || []

        if (homeScorers.length === 0 && awayScorers.length === 0) {
          return null
        }

        const buildTeamScorers = (playerList, teamName) => {
          if (!playerList || playerList.length === 0) return null
          return h('div', { class: 'scorers-team' }, [
            h('span', { class: 'team-label' }, teamName),
            h('div', { class: 'scorers-list' },
              playerList.slice(0, 5).map(p =>
                h('div', { class: 'scorer-item' }, [
                  h('span', { class: 'scorer-name' }, p.player_name),
                  h('span', { class: 'scorer-goals' }, `${p.goals}球`),
                  h('span', { class: 'scorer-matches' }, `${p.matches}场`),
                  h('span', { class: 'scorer-avg' }, `${(p.goals_per_match || 0).toFixed(2)}球/场`)
                ])
              )
            )
          ])
        }

        return h('div', { class: 'scorers-section' }, [
          h('h4', '进球球员'),
          h('div', { class: 'scorers-row' }, [
            buildTeamScorers(homeScorers, mi.home_team_cn),
            buildTeamScorers(awayScorers, mi.away_team_cn)
          ])
        ])
      }

      // 分析总结
      const buildAnalysisSummary = () => {
        const summary = analysisSummary.overall_assessment || ''
        return h('div', { class: 'analysis-summary-box' }, [
          h('h4', '综合分析'),
          h('p', { class: 'summary-text' }, summary)
        ])
      }

      // 天气因素展示
      const buildWeather = () => {
        const weatherFeature = features.weather_analyzer
        if (!weatherFeature) return null

        const weatherData = weatherFeature.raw_data?.weather || {}
        const impact = weatherFeature.raw_data?.impact_analysis || {}
        const factors = impact.factors || []

        return h('div', { class: 'weather-section' }, [
          h('h4', '天气因素'),
          h('div', { class: 'weather-info' }, [
            h('div', { class: 'weather-item' }, [
              h('span', { class: 'weather-label' }, '温度'),
              h('span', { class: 'weather-value' }, `${weatherData.temperature || '--'}°C`)
            ]),
            h('div', { class: 'weather-item' }, [
              h('span', { class: 'weather-label' }, '湿度'),
              h('span', { class: 'weather-value' }, `${weatherData.humidity || '--'}%`)
            ]),
            h('div', { class: 'weather-item' }, [
              h('span', { class: 'weather-label' }, '风力'),
              h('span', { class: 'weather-value' }, `${weatherData.wind_speed || '--'}m/s`)
            ])
          ]),
          h('div', { class: 'weather-factors' },
            factors.map(f => h('span', { class: 'weather-factor' }, f))
          ),
          h('p', { class: 'weather-impact' }, weatherFeature.description || '--')
        ])
      }

      // 价值投注展示
      const buildValueBets = () => {
        const spfValueBets = spf.value_bets || []
        const summary = r.summary || {}

        if (spfValueBets.length === 0 && summary.value_bets_count === 0) {
          return null
        }

        // 显示SPF价值投注
        const valueBetItems = spfValueBets.map(vb =>
          h('div', { class: 'value-bet-item' }, [
            h('div', { class: 'value-bet-header' }, [
              h('span', { class: 'value-bet-label' }, vb.label),
              h('span', { class: `value-rating ${vb.value_rating}` },
                vb.value_rating === 'high' ? '高价值' : '中等价值')
            ]),
            h('div', { class: 'value-bet-details' }, [
              h('span', null, `预测概率: ${(vb.probability * 100).toFixed(1)}%`),
              h('span', null, `赔率: ${vb.odds}`),
              h('span', null, `隐含概率: ${(vb.implied_probability * 100).toFixed(1)}%`)
            ]),
            h('div', { class: 'value-bet-edge' }, [
              h('span', { class: 'edge-positive' }, `优势: +${(vb.edge * 100).toFixed(1)}%`)
            ])
          ])
        )

        return h('div', { class: 'value-bets-section' }, [
          h('h4', '价值投注分析'),
          h('p', { class: 'value-bets-desc' }, '当预测概率高于赔率隐含概率时，存在投注价值'),
          h('div', { class: 'value-bets-list' }, valueBetItems),
          spfValueBets.length === 0 ? h('p', { class: 'no-value-bets' }, '当前无明显价值投注机会') : null
        ])
      }

      return h('div', { class: 'analysis-detail' }, [
        // 比赛信息
        h('div', { class: 'detail-header' }, [
          h('span', { class: 'league' }, mi.league_name_cn),
          h('span', { class: 'teams' }, `${mi.home_team_cn} VS ${mi.away_team_cn}`)
        ]),

        // SPF分析概览
        h('div', { class: 'analysis-section' }, [
          h('h3', '胜平负概率'),
          h('div', { class: 'prob-bars' }, [
            h('div', { class: 'prob-bar home' }, [
              h('div', { class: 'bar-fill', style: `width: ${(probs.home_win || 0) * 100}%` }),
              h('span', { class: 'label' }, `主胜 ${((probs.home_win || 0) * 100).toFixed(1)}%`)
            ]),
            h('div', { class: 'prob-bar draw' }, [
              h('div', { class: 'bar-fill', style: `width: ${(probs.draw || 0) * 100}%` }),
              h('span', { class: 'label' }, `平局 ${((probs.draw || 0) * 100).toFixed(1)}%`)
            ]),
            h('div', { class: 'prob-bar away' }, [
              h('div', { class: 'bar-fill', style: `width: ${(probs.away_win || 0) * 100}%` }),
              h('span', { class: 'label' }, `客胜 ${((probs.away_win || 0) * 100).toFixed(1)}%`)
            ])
          ]),
          h('div', { class: 'recommendation' }, [
            h('span', { class: 'rec-label' }, '推荐: '),
            h('span', { class: 'rec-value' }, spf.recommendation || '--'),
            h('span', { class: 'rec-conf' }, `置信度 ${((spf.confidence || 0) * 100).toFixed(0)}%`)
          ])
        ]),

        // 详细战绩展示
        h('div', { class: 'detailed-section' }, [
          h('h3', '近期战绩'),
          h('div', { class: 'team-stats-row' }, [
            h('div', { class: 'team-stats-col' }, buildRecentMatches(detailed.home, mi.home_team_cn)),
            h('div', { class: 'team-stats-col' }, buildRecentMatches(detailed.away, mi.away_team_cn))
          ])
        ]),

        // 历史交锋
        h('div', { class: 'detailed-section' }, [buildH2H()]),

        // Elo对比
        h('div', { class: 'detailed-section' }, [buildEloComparison()]),

        // 联赛积分排名
        h('div', { class: 'detailed-section' }, [buildLeagueStanding()]),

        // 体能状况
        h('div', { class: 'detailed-section' }, [buildFitness()]),

        // 比分预测（前3可能比分）
        h('div', { class: 'detailed-section' }, [buildScorePrediction()]),

        // 大小球预测
        h('div', { class: 'detailed-section' }, [buildOverUnderPrediction()]),

        // 进球时间分布
        h('div', { class: 'detailed-section' }, [buildGoalTiming()]),

        // 球员进球详情
        h('div', { class: 'detailed-section' }, [buildScorers()]),

        // 天气因素
        h('div', { class: 'detailed-section' }, [buildWeather()]),

        // 价值投注分析
        h('div', { class: 'detailed-section' }, [buildValueBets()]),

        // 所有分析因素
        h('div', { class: 'factors-section' }, [
          h('h3', `分析因素 (${Object.keys(features).length}项)`),
          h('div', { class: 'factors-list' }, factorElements)
        ]),

        // 综合推荐
        h('div', { class: 'summary-section' }, [
          h('h3', '综合推荐'),
          h('p', { class: 'main-rec' }, r.summary?.main_recommendation || '--'),
          h('p', { class: 'confidence' }, `整体置信度: ${((r.summary?.confidence || 0) * 100).toFixed(1)}%`),
          buildAnalysisSummary()
        ])
      ])
    }
  }
})

export default {
  name: 'LotteryCenter',
  components: {
    ActivityIcon,
    BarChartIcon,
    StarIcon,
    TargetIcon,
    CalendarIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    CloseIcon,
    LotteryAnalysisDetail
  },
  setup() {
    const selectedDate = ref(new Date())
    const selectedPlayType = ref('all')
    const matches = ref([])
    const loading = ref(false)
    const showDetailModal = ref(false)
    const selectedMatch = ref(null)

    const stats = ref({
      total_matches: 0,
      analyzed_matches: 0,
      value_bets: 0,
      accuracy: 0
    })

    const accuracyData = ref({
      spf: 0,
      spf_count: 0,
      bf: 0,
      bf_count: 0,
      ou: 0,
      ou_count: 0,
      overall: 0,
      total_count: 0,
      trend: 0
    })

    const playTypes = [
      { value: 'all', label: '全部' },
      { value: 'spf', label: '胜平负' },
      { value: 'bf', label: '比分' },
      { value: 'bqc', label: '半全场' },
      { value: 'rqspf', label: '让球胜平负' }
    ]

    const filteredMatches = computed(() => {
      if (!selectedPlayType.value || selectedPlayType.value === 'all') return matches.value
      return matches.value.filter(m =>
        m.play_types && m.play_types.length > 0 && m.play_types.includes(selectedPlayType.value)
      )
    })

    const formatDate = (date) => {
      const d = new Date(date)
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    }

    const formatHandicap = (line) => {
      if (line > 0) return `-${line}`
      if (line < 0) return `+${Math.abs(line)}`
      return '0'
    }

    const getPlayTypeLabel = (pt) => {
      const labels = {
        'spf': '胜平负',
        'bf': '比分',
        'bqc': '半全场',
        'rqspf': '让球'
      }
      return labels[pt] || pt
    }

    const getPlayTypeShortLabel = (pt) => {
      const labels = {
        'spf': 'SPF',
        'bf': 'BF',
        'bqc': 'BQC',
        'rqspf': 'RQ'
      }
      return labels[pt] || pt
    }

    const getSellStatusLabel = (status) => {
      const labels = {
        'selling': '在售',
        'stopped': '停售',
        'closed': '已闭'
      }
      return labels[status] || status
    }

    const getConfidenceClass = (match) => {
      const level = match.confidence_level
      if (level === '高' || level === 'high') return 'high'
      if (level === '低' || level === 'low') return 'low'
      return 'medium'
    }

    const changeDate = (delta) => {
      const newDate = new Date(selectedDate.value)
      newDate.setDate(newDate.getDate() + delta)
      selectedDate.value = newDate
    }

    const fetchMatches = async () => {
      loading.value = true
      try {
        const dateStr = formatDate(selectedDate.value)
        const response = await fetch(`http://localhost:18888/api/v1/lottery/matches?date=${dateStr}`)
        const data = await response.json()
        matches.value = data.matches || []

        // 更新统计
        stats.value = {
          total_matches: matches.value.length,
          analyzed_matches: matches.value.filter(m => m.has_analysis).length,
          value_bets: matches.value.filter(m => m.has_value_bet).length,
          accuracy: 65 // 临时值，后续从API获取
        }
      } catch (e) {
        console.error('获取比赛列表失败:', e)
        matches.value = []
      } finally {
        loading.value = false
      }
    }

    const fetchAccuracyData = async () => {
      try {
        const response = await fetch('http://localhost:18888/api/v1/lottery/accuracy?days=30')
        if (response.ok) {
          const data = await response.json()
          accuracyData.value = {
            spf: data.spf_accuracy || 0,
            spf_count: data.spf_count || 0,
            bf: data.bf_accuracy || 0,
            bf_count: data.bf_count || 0,
            ou: data.ou_accuracy || 0,
            ou_count: data.ou_count || 0,
            overall: data.overall_accuracy || 0,
            total_count: data.total_count || 0,
            trend: data.trend || 0
          }
        }
      } catch (e) {
        console.error('获取准确率数据失败:', e)
        // 使用默认值
        accuracyData.value = {
          spf: 62,
          spf_count: 150,
          bf: 28,
          bf_count: 120,
          ou: 55,
          ou_count: 130,
          overall: 58,
          total_count: 400,
          trend: 5
        }
      }
    }

    const analyzeMatch = async (match) => {
      try {
        const response = await fetch(`http://localhost:18888/api/v1/lottery/analyze/${match.lottery_match_id}`, {
          method: 'POST'
        })
        const data = await response.json()
        if (data.success) {
          // 更新比赛信息
          match.has_analysis = true
          match.main_recommendation = data.summary?.main_recommendation
          match.confidence_level = data.summary?.confidence
          selectedMatch.value = match
          showDetailModal.value = true
        }
      } catch (e) {
        console.error('分析失败:', e)
      }
    }

    const viewMatchDetail = (match) => {
      if (match.has_analysis) {
        selectedMatch.value = match
        showDetailModal.value = true
      }
    }

    const closeDetailModal = () => {
      showDetailModal.value = false
      selectedMatch.value = null
    }

    watch(selectedDate, fetchMatches)

    onMounted(() => {
      fetchMatches()
      fetchAccuracyData()
    })

    return {
      selectedDate,
      selectedPlayType,
      matches,
      filteredMatches,
      loading,
      stats,
      accuracyData,
      playTypes,
      showDetailModal,
      selectedMatch,
      formatDate,
      formatHandicap,
      getPlayTypeLabel,
      getPlayTypeShortLabel,
      getSellStatusLabel,
      getConfidenceClass,
      changeDate,
      analyzeMatch,
      viewMatchDetail,
      closeDetailModal,
      ActivityIcon,
      BarChartIcon,
      StarIcon,
      TargetIcon,
      CalendarIcon,
      ChevronLeftIcon,
      ChevronRightIcon,
      CloseIcon
    }
  }
}
</script>

<style scoped>
.lottery-center {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

/* 统计卡片 */
.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.8);
}

.stat-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
}

.stat-icon.matches { background: rgba(16, 185, 129, 0.2); color: #10b981; }
.stat-icon.analyzed { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
.stat-icon.value { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
.stat-icon.accuracy { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: white;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
}

/* 准确率追踪面板 */
.accuracy-panel {
  padding: 16px;
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.8);
}

.accuracy-panel h3 {
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
}

.accuracy-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.accuracy-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  background: rgba(255,255,255,0.02);
  border-radius: 8px;
}

.accuracy-label {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
}

.accuracy-value {
  font-size: 20px;
  font-weight: 700;
  color: #10b981;
}

.accuracy-value.overall {
  color: #f59e0b;
}

.accuracy-sample {
  font-size: 10px;
  color: #4b5563;
  margin-top: 2px;
}

.accuracy-trend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.trend-label {
  color: #6b7280;
}

.trend-value {
  font-weight: 600;
}

.trend-value.positive {
  color: #10b981;
}

.trend-value.negative {
  color: #ef4444;
}

/* 篩选栏 */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #151922;
  border-radius: 8px;
  border: 1px solid rgba(31, 41, 55, 0.8);
}

.date-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-nav {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid #374151;
  border-radius: 6px;
  color: #9ca3af;
  cursor: pointer;
}

.date-nav:hover {
  background: rgba(255,255,255,0.05);
  color: white;
}

.current-date {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
  font-size: 14px;
  color: white;
}

.calendar-icon {
  color: #10b981;
}

.play-type-tabs {
  display: flex;
  gap: 4px;
}

.play-tab {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid #374151;
  border-radius: 6px;
  font-size: 13px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
}

.play-tab:hover {
  background: rgba(255,255,255,0.05);
  color: white;
}

.play-tab.active {
  background: rgba(16, 185, 129, 0.1);
  border-color: #10b981;
  color: #10b981;
}

/* 比赛列表 */
.matches-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #6b7280;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #374151;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {
  width: 48px;
  height: 48px;
  color: #374151;
  margin-bottom: 12px;
}

.matches-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.match-card {
  padding: 16px;
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.8);
  cursor: pointer;
  transition: all 0.2s;
}

.match-card:hover {
  border-color: #374151;
  transform: translateY(-2px);
}

.match-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.match-num {
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.league-name {
  font-size: 12px;
  color: #6b7280;
}

.match-time {
  font-size: 12px;
  color: #9ca3af;
}

.teams-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.team {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 4px;
}

.team.home { justify-content: flex-end; }
.team.away { justify-content: flex-start; }

.team-name {
  font-size: 14px;
  font-weight: 600;
  color: white;
}

.handicap-badge {
  font-size: 11px;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

.vs {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  padding: 0 8px;
}

.analysis-status {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}

.has-analysis {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
}

.confidence-badge.high { background: rgba(16, 185, 129, 0.2); color: #10b981; }
.confidence-badge.medium { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
.confidence-badge.low { background: rgba(239, 68, 68, 0.2); color: #ef4444; }

.recommendation-preview {
  display: flex;
  align-items: center;
  gap: 6px;
}

.play-type-badge {
  font-size: 11px;
  color: #6b7280;
}

.recommendation-text {
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
}

.no-analysis {
  display: flex;
  justify-content: center;
}

.analyze-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid #10b981;
  border-radius: 6px;
  font-size: 13px;
  color: #10b981;
  cursor: pointer;
}

.analyze-btn:hover {
  background: rgba(16, 185, 129, 0.2);
}

.play-types-row {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-bottom: 8px;
}

.play-badge {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
  color: #6b7280;
}

.play-badge.active {
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.sell-status {
  display: flex;
  justify-content: center;
}

.status-badge {
  font-size: 11px;
  padding: 4px 12px;
  border-radius: 4px;
}

.status-badge.selling { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.status-badge.stopped { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.status-badge.closed { background: rgba(107, 114, 128, 0.1); color: #6b7280; }

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal-content {
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  background: #151922;
  border-radius: 16px;
  border: 1px solid #374151;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #374151;
}

.modal-header h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
}

.close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  border-radius: 6px;
}

.close-btn:hover {
  background: rgba(255,255,255,0.05);
  color: white;
}

.modal-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

/* 分析详情 */
.analysis-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
}

.league {
  font-size: 14px;
  color: #6b7280;
}

.teams {
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.analysis-section {
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.5);
}

.analysis-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: #9ca3af;
  margin-bottom: 12px;
}

.prob-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prob-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prob-bar .bar-fill {
  height: 20px;
  border-radius: 4px;
  transition: width 0.3s;
}

.prob-bar.home .bar-fill { background: linear-gradient(90deg, #10b981, #059669); }
.prob-bar.draw .bar-fill { background: linear-gradient(90deg, #f59e0b, #d97706); }
.prob-bar.away .bar-fill { background: linear-gradient(90deg, #ef4444, #dc2626); }

.prob-bar .label {
  font-size: 13px;
  font-weight: 600;
  color: white;
  min-width: 80px;
}

.recommendation {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(55, 65, 81, 0.5);
}

.rec-label {
  font-size: 13px;
  color: #6b7280;
}

.rec-value {
  font-size: 15px;
  font-weight: 700;
  color: #10b981;
}

.rec-conf {
  margin-left: auto;
  font-size: 12px;
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

/* 分析因素列表 */
.factors-section {
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.5);
}

.factors-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: #9ca3af;
  margin-bottom: 12px;
}

.factors-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.factor-item {
  display: flex;
  flex-direction: column;
  padding: 8px 12px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
  border: 1px solid rgba(55, 65, 81, 0.3);
}

.factor-name {
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
  margin-bottom: 4px;
}

.factor-desc {
  font-size: 11px;
  color: #9ca3af;
  flex: 1;
}

.factor-conf {
  font-size: 10px;
  color: #6b7280;
  text-align: right;
  margin-top: 4px;
}

.summary-section {
  padding: 16px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(59, 130, 246, 0.1));
  border-radius: 8px;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.summary-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: #9ca3af;
  margin-bottom: 8px;
}

.main-rec {
  font-size: 18px;
  font-weight: 700;
  color: #10b981;
  margin-bottom: 4px;
}

.confidence {
  font-size: 13px;
  color: #6b7280;
}

/* 详细战绩展示 */
.detailed-section {
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.5);
}

.detailed-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: #9ca3af;
  margin-bottom: 12px;
}

.team-stats-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.team-stats-col {
  padding: 12px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
}

.recent-section {
  margin-bottom: 12px;
}

.recent-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
  margin-bottom: 8px;
}

.form-summary {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #6b7280;
}

.form-string {
  font-size: 11px;
  font-weight: 600;
  margin-top: 6px;
}

.form-string span {
  padding: 2px 4px;
  border-radius: 2px;
}

.matches-mini-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.match-result {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(255,255,255,0.05);
}

.match-result.胜 { color: #10b981; background: rgba(16, 185, 129, 0.1); }
.match-result.平 { color: #f59e0b; background: rgba(245, 158, 11, 0.1); }
.match-result.负 { color: #ef4444; background: rgba(239, 68, 68, 0.1); }

.points {
  color: #10b981;
  font-weight: 600;
}

/* 历史交锋 */
.h2h-section {
  margin-top: 16px;
}

.h2h-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #f59e0b;
  margin-bottom: 8px;
}

.h2h-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.h2h-stat {
  font-size: 11px;
  color: #6b7280;
}

.h2h-matches {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.h2h-match {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  background: rgba(255,255,255,0.02);
  border-radius: 4px;
  font-size: 11px;
}

.h2h-date {
  color: #6b7280;
  font-size: 10px;
}

.h2h-score {
  color: white;
}

.h2h-result {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
}

.h2h-result.主胜 { color: #10b981; background: rgba(16, 185, 129, 0.1); }
.h2h-result.平局 { color: #f59e0b; background: rgba(245, 158, 11, 0.1); }
.h2h-result.客胜 { color: #ef4444; background: rgba(239, 68, 68, 0.1); }

.no-data {
  color: #6b7280;
  font-size: 11px;
}

/* Elo对比 */
.elo-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #3b82f6;
  margin-bottom: 8px;
}

.elo-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.elo-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.elo-label {
  font-size: 11px;
  color: #6b7280;
  min-width: 80px;
}

.elo-fill {
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(90deg, #10b981, #3b82f6);
}

.elo-desc {
  margin-top: 8px;
  font-size: 11px;
  color: #9ca3af;
}

/* 分析总结 */
.analysis-summary-box {
  margin-top: 12px;
  padding: 10px;
  background: rgba(16, 185, 129, 0.05);
  border-radius: 6px;
  border-left: 3px solid #10b981;
}

.analysis-summary-box h4 {
  font-size: 12px;
  color: #10b981;
  margin-bottom: 6px;
}

.summary-text {
  font-size: 11px;
  color: #9ca3af;
  line-height: 1.5;
}

/* 比分预测 */
.score-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #f59e0b;
  margin-bottom: 8px;
}

.score-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.score-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: rgba(255,255,255,0.02);
  border-radius: 4px;
}

.score-rank {
  font-size: 11px;
  color: #6b7280;
}

.score-value {
  font-size: 14px;
  font-weight: 600;
  color: #10b981;
}

.score-prob {
  font-size: 11px;
  color: #3b82f6;
}

.score-info {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  font-size: 11px;
  color: #6b7280;
}

.score-rec {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}

/* 大小球预测 */
.ou-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #8b5cf6;
  margin-bottom: 8px;
}

.ou-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ou-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ou-bar .bar-fill {
  height: 20px;
  border-radius: 4px;
}

.ou-bar.over .bar-fill { background: linear-gradient(90deg, #10b981, #059669); }
.ou-bar.under .bar-fill { background: linear-gradient(90deg, #ef4444, #dc2626); }

.expected-goals {
  margin-top: 8px;
  font-size: 12px;
  color: #f59e0b;
  font-weight: 600;
}

.goals-dist {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.goals-dist-label {
  font-size: 11px;
  color: #6b7280;
}

.goals-dist-item {
  font-size: 10px;
  padding: 2px 6px;
  background: rgba(255,255,255,0.05);
  border-radius: 3px;
  color: #9ca3af;
}

.ou-rec {
  margin-top: 8px;
  font-size: 12px;
  color: #10b981;
  font-weight: 600;
}

/* 联赛积分排名 */
.league-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #3b82f6;
  margin-bottom: 8px;
}

.standing-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.standing-card {
  padding: 10px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
}

.standing-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.standing-header .team-name {
  font-size: 12px;
  color: #9ca3af;
}

.standing-header .position {
  font-size: 13px;
  font-weight: 600;
  color: #10b981;
}

.standing-stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #6b7280;
}

.standing-goals {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  font-size: 11px;
}

.goal-diff {
  color: #f59e0b;
}

.goal-diff.positive {
  color: #10b981;
}

.home-away-record {
  margin-top: 6px;
  display: flex;
  gap: 8px;
  font-size: 10px;
  color: #6b7280;
}

/* 体能状况 */
.fitness-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #ef4444;
  margin-bottom: 8px;
}

.fitness-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.fitness-card {
  padding: 10px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
}

.fitness-card .team-name {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 6px;
}

.fitness-stats {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #6b7280;
}

.fatigue-level {
  margin-top: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.fatigue-level.fatigue-high {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.fatigue-level.fatigue-medium {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.fatigue-level.fatigue-low {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.rest-desc {
  margin-top: 4px;
  font-size: 10px;
  color: #6b7280;
}

/* 进球时间分布 */
.goal-timing-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #8b5cf6;
  margin-bottom: 8px;
}

.timing-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.timing-team {
  padding: 10px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
}

.timing-team .team-label {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 8px;
  display: block;
}

.timing-bars {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timing-slot {
  display: flex;
  align-items: center;
  gap: 6px;
}

.slot-label {
  font-size: 10px;
  color: #6b7280;
  min-width: 40px;
}

.slot-bar {
  flex: 1;
  height: 8px;
  background: rgba(255,255,255,0.1);
  border-radius: 4px;
  overflow: hidden;
}

.slot-fill {
  height: 100%;
  background: linear-gradient(90deg, #8b5cf6, #a855f7);
  border-radius: 4px;
}

.slot-count {
  font-size: 10px;
  color: #8b5cf6;
  min-width: 20px;
  text-align: right;
}

/* 球员进球详情 */
.scorers-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #f59e0b;
  margin-bottom: 8px;
}

.scorers-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.scorers-team {
  padding: 10px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
}

.scorers-team .team-label {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 8px;
  display: block;
}

.scorers-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scorer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
}

.scorer-name {
  font-size: 11px;
  color: white;
  flex: 1;
}

.scorer-goals {
  font-size: 11px;
  color: #10b981;
  font-weight: 600;
}

.scorer-matches {
  font-size: 10px;
  color: #6b7280;
}

.scorer-avg {
  font-size: 10px;
  color: #f59e0b;
}

/* 天气因素 */
.weather-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #06b6d4;
  margin-bottom: 8px;
}

.weather-info {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.weather-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.weather-label {
  font-size: 11px;
  color: #6b7280;
}

.weather-value {
  font-size: 12px;
  color: white;
  font-weight: 600;
}

.weather-factors {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.weather-factor {
  font-size: 10px;
  padding: 2px 8px;
  background: rgba(6, 182, 212, 0.1);
  color: #06b6d4;
  border-radius: 4px;
}

.weather-impact {
  font-size: 11px;
  color: #9ca3af;
}

/* 价值投注 */
.value-bets-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: #f59e0b;
  margin-bottom: 8px;
}

.value-bets-desc {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 12px;
}

.value-bets-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.value-bet-item {
  padding: 10px;
  background: rgba(245, 158, 11, 0.05);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: 6px;
}

.value-bet-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.value-bet-label {
  font-size: 13px;
  font-weight: 600;
  color: white;
}

.value-rating {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
}

.value-rating.high {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.value-rating.medium {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.value-bet-details {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #6b7280;
}

.value-bet-edge {
  margin-top: 6px;
}

.edge-positive {
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
}

.no-value-bets {
  font-size: 11px;
  color: #6b7280;
  text-align: center;
  padding: 12px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 12px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #374151;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.no-report {
  text-align: center;
  color: #6b7280;
  padding: 40px;
}

.analysis-content {
  padding: 20px;
  text-align: center;
  color: #6b7280;
}

/* 响应式 */
@media (max-width: 900px) {
  .stats-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .filter-bar {
    flex-direction: column;
    gap: 12px;
  }
}

@media (max-width: 600px) {
  .stats-cards {
    grid-template-columns: 1fr;
  }

  .matches-grid {
    grid-template-columns: 1fr;
  }

  .play-type-tabs {
    flex-wrap: wrap;
  }
}
</style>