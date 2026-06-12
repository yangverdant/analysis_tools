<template>
  <div class="lottery-analysis">
    <!-- 比赛信息头部 -->
    <div class="match-header">
      <div class="league-info">
        <span class="league-name">{{ match.league_name_cn }}</span>
        <span class="match-time">{{ match.match_date }} {{ match.match_time }}</span>
      </div>
      <div class="teams-info">
        <div class="team home">
          <span class="team-name">{{ match.home_team_cn }}</span>
          <span v-if="match.handicap_line !== 0" class="handicap">
            {{ formatHandicap(match.handicap_line) }}
          </span>
        </div>
        <div class="vs">VS</div>
        <div class="team away">
          <span class="team-name">{{ match.away_team_cn }}</span>
        </div>
      </div>
    </div>

    <!-- 玩法Tab切换 -->
    <div class="play-tabs">
      <button
        v-for="tab in playTabs"
        :key="tab.value"
        :class="['tab-btn', { active: activeTab === tab.value }]"
        @click="activeTab = tab.value"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>分析中...</span>
    </div>

    <!-- SPF分析结果 -->
    <div v-else-if="activeTab === 'spf' && analysis.spf" class="analysis-content">
      <SPFAnalysisView :data="analysis.spf" />
    </div>

    <!-- 比分分析结果 -->
    <div v-else-if="activeTab === 'bf' && analysis.bf" class="analysis-content">
      <ScoreAnalysisView :data="analysis.bf" />
    </div>

    <!-- 半全场分析结果 -->
    <div v-else-if="activeTab === 'bqc' && analysis.bqc" class="analysis-content">
      <BQCAnalysisView :data="analysis.bqc" />
    </div>

    <!-- 让球胜平负分析结果 -->
    <div v-else-if="activeTab === 'rqspf' && analysis.rqspf" class="analysis-content">
      <HandicapAnalysisView :data="analysis.rqspf" :handicap="match.handicap_line" />
    </div>

    <!-- 无数据提示 -->
    <div v-else class="no-data">
      <span>暂无分析数据</span>
    </div>

    <!-- 综合推荐 -->
    <div v-if="hasAnyAnalysis" class="summary-section">
      <h3>综合推荐</h3>
      <div class="recommendations">
        <div
          v-for="rec in recommendations"
          :key="rec.play_type"
          class="recommendation-card"
        >
          <span class="play-type">{{ rec.play_type_label }}</span>
          <span class="result">{{ rec.result }}</span>
          <span :class="['confidence', rec.confidence_level]">
            置信度: {{ rec.confidence }}%
          </span>
        </div>
      </div>
    </div>

    <!-- 价值投注提示 -->
    <div v-if="valueBets.length > 0" class="value-bets-section">
      <h3>价值投注</h3>
      <div class="value-bets-list">
        <div
          v-for="bet in valueBets"
          :key="bet.key"
          class="value-bet-item"
        >
          <span class="bet-type">{{ bet.play_type }}</span>
          <span class="bet-result">{{ bet.result }}</span>
          <span class="bet-value">+{{ bet.value }}%</span>
          <span class="bet-odds">赔率: {{ bet.odds }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch, h, defineComponent } from 'vue'

// SPF分析子组件
const SPFAnalysisView = defineComponent({
  name: 'SPFAnalysisView',
  props: { data: Object },
  setup(props) {
    const probs = computed(() => props.data?.final_probs || {})
    return () => h('div', { class: 'spf-view' }, [
      h('h4', { class: 'section-title' }, '胜平负概率分布'),
      h('div', { class: 'prob-bars' }, [
        ['home_win', '主胜', '#10b981'],
        ['draw', '平局', '#3b82f6'],
        ['away_win', '客胜', '#ef4444']
      ].map(([key, label, color]) =>
        h('div', { class: 'prob-bar-item', key }, [
          h('span', { class: 'prob-label' }, label),
          h('div', { class: 'prob-bar-wrapper' }, [
            h('div', {
              class: 'prob-bar',
              style: {
                width: `${(probs.value[key] || 0) * 100}%`,
                background: color
              }
            }),
            h('span', { class: 'prob-value' }, `${((probs.value[key] || 0) * 100).toFixed(1)}%`)
          ])
        ])
      )),
      props.data?.recommendation && h('div', { class: 'recommendation-box' }, [
        h('span', { class: 'rec-label' }, '推荐:'),
        h('span', { class: 'rec-result' }, props.data.recommendation.label),
        h('span', { class: 'rec-confidence' }, `(${(props.data.confidence * 100).toFixed(0)}%)`)
      ])
    ])
  }
})

// 比分分析子组件
const ScoreAnalysisView = defineComponent({
  name: 'ScoreAnalysisView',
  props: { data: Object },
  setup(props) {
    const topScores = computed(() => props.data?.top_scores || [])
    return () => h('div', { class: 'score-view' }, [
      h('h4', { class: 'section-title' }, '比分概率TOP5'),
      h('div', { class: 'score-table' }, [
        h('div', { class: 'score-header' }, [
          h('span', '比分'),
          h('span', '概率'),
          h('span', '结果')
        ]),
        topScores.value.slice(0, 5).map((s, i) =>
          h('div', { class: 'score-row', key: i }, [
            h('span', { class: 'score-value' }, s.display),
            h('span', { class: 'score-prob' }, `${(s.prob * 100).toFixed(1)}%`),
            h('span', { class: 'score-result' }, getPlayTypeLabel(s.result_type))
          ])
        )
      ])
    ])
  }
})

// 半全场分析子组件
const BQCAnalysisView = defineComponent({
  name: 'BQCAnalysisView',
  props: { data: Object },
  setup(props) {
    const topBqc = computed(() => props.data?.top_bqc || [])
    return () => h('div', { class: 'bqc-view' }, [
      h('h4', { class: 'section-title' }, '半全场概率TOP3'),
      h('div', { class: 'bqc-grid' }, topBqc.slice(0, 3).map((b, i) =>
        h('div', { class: 'bqc-item', key: i }, [
          h('span', { class: 'bqc-code' }, b.bqc),
          h('span', { class: 'bqc-display' }, b.display),
          h('span', { class: 'bqc-prob' }, `${(b.prob * 100).toFixed(1)}%`)
        ])
      ))
    ])
  }
})

// 让球分析子组件
const HandicapAnalysisView = defineComponent({
  name: 'HandicapAnalysisView',
  props: { data: Object, handicap: Number },
  setup(props) {
    const adjusted = computed(() => props.data?.adjusted_distribution || {})
    const original = computed(() => props.data?.original_distribution || {})
    const formatHandicap = (line) => {
      if (line > 0) return `主队让${line}球`
      if (line < 0) return `主队受让${Math.abs(line)}球`
      return '平手盘'
    }
    return () => h('div', { class: 'handicap-view' }, [
      h('h4', { class: 'section-title' }, [
        '让球分析 - ',
        h('span', { class: 'handicap-line' }, formatHandicap(props.handicap))
      ]),
      h('div', { class: 'comparison' }, [
        h('div', { class: 'prob-col' }, [
          h('h5', '原始概率'),
          h('div', { class: 'prob-list' }, [
            h('div', { class: 'prob-item' }, [
              h('span', '主胜'),
              h('span', `${((original.value.home_win || 0) * 100).toFixed(1)}%`)
            ]),
            h('div', { class: 'prob-item' }, [
              h('span', '平局'),
              h('span', `${((original.value.draw || 0) * 100).toFixed(1)}%`)
            ]),
            h('div', { class: 'prob-item' }, [
              h('span', '客胜'),
              h('span', `${((original.value.away_win || 0) * 100).toFixed(1)}%`)
            ])
          ])
        ]),
        h('div', { class: 'prob-col adjusted' }, [
          h('h5', '让球后概率'),
          h('div', { class: 'prob-list' }, [
            h('div', { class: 'prob-item' }, [
              h('span', '主胜'),
              h('span', `${((adjusted.value.home_win || 0) * 100).toFixed(1)}%`)
            ]),
            h('div', { class: 'prob-item' }, [
              h('span', '平局'),
              h('span', `${((adjusted.value.draw || 0) * 100).toFixed(1)}%`)
            ]),
            h('div', { class: 'prob-item' }, [
              h('span', '客胜'),
              h('span', `${((adjusted.value.away_win || 0) * 100).toFixed(1)}%`)
            ])
          ])
        ])
      ])
    ])
  }
})

// 辅助函数
function getPlayTypeLabel(type) {
  const labels = { 'home_win': '主胜', 'draw': '平局', 'away_win': '客胜' }
  return labels[type] || type
}

export default {
  name: 'LotteryAnalysis',
  components: {
    SPFAnalysisView,
    ScoreAnalysisView,
    BQCAnalysisView,
    HandicapAnalysisView
  },
  props: {
    match: {
      type: Object,
      required: true
    },
    analysisData: {
      type: Object,
      default: null
    }
  },
  setup(props) {
    const activeTab = ref('spf')
    const loading = ref(false)
    const analysis = ref({
      spf: null,
      bf: null,
      bqc: null,
      rqspf: null
    })

    const playTabs = [
      { value: 'spf', label: '胜平负' },
      { value: 'bf', label: '比分' },
      { value: 'bqc', label: '半全场' },
      { value: 'rqspf', label: '让球胜平负' }
    ]

    const formatHandicap = (line) => {
      if (line > 0) return `-${line}`
      if (line < 0) return `+${Math.abs(line)}`
      return '0'
    }

    const hasAnyAnalysis = computed(() => {
      return analysis.value.spf || analysis.value.bf ||
             analysis.value.bqc || analysis.value.rqspf
    })

    const recommendations = computed(() => {
      const recs = []
      if (analysis.value.spf?.recommendation) {
        recs.push({
          play_type: 'spf',
          play_type_label: '胜平负',
          result: analysis.value.spf.recommendation.label,
          confidence: (analysis.value.spf.confidence * 100).toFixed(0),
          confidence_level: getConfidenceLevel(analysis.value.spf.confidence)
        })
      }
      if (analysis.value.bf?.top_scores?.[0]) {
        recs.push({
          play_type: 'bf',
          play_type_label: '比分',
          result: analysis.value.bf.top_scores[0].display,
          confidence: (analysis.value.bf.top_scores[0].prob * 100).toFixed(0),
          confidence_level: getConfidenceLevel(analysis.value.bf.top_scores[0].prob)
        })
      }
      if (analysis.value.bqc?.top_bqc?.[0]) {
        recs.push({
          play_type: 'bqc',
          play_type_label: '半全场',
          result: analysis.value.bqc.top_bqc[0].display,
          confidence: (analysis.value.bqc.top_bqc[0].prob * 100).toFixed(0),
          confidence_level: getConfidenceLevel(analysis.value.bqc.top_bqc[0].prob)
        })
      }
      return recs
    })

    const valueBets = computed(() => {
      const bets = []
      // 从各分析结果中提取价值投注
      if (analysis.value.bf?.value_bets) {
        analysis.value.bf.value_bets.forEach(vb => {
          bets.push({
            key: `bf_${vb.score}`,
            play_type: '比分',
            result: vb.score_display,
            value: (vb.value * 100).toFixed(1),
            odds: vb.odds
          })
        })
      }
      if (analysis.value.bqc?.value_bets) {
        analysis.value.bqc.value_bets.forEach(vb => {
          bets.push({
            key: `bqc_${vb.bqc}`,
            play_type: '半全场',
            result: vb.bqc_display,
            value: (vb.value * 100).toFixed(1),
            odds: vb.odds
          })
        })
      }
      return bets
    })

    const getConfidenceLevel = (conf) => {
      if (conf >= 0.6) return 'high'
      if (conf >= 0.35) return 'medium'
      return 'low'
    }

    const fetchAnalysis = async () => {
      if (props.analysisData) {
        analysis.value = props.analysisData
        return
      }

      loading.value = true
      try {
        const response = await fetch(
          `/api/v1/lottery/report/${props.match.lottery_match_id}`
        )
        const data = await response.json()
        if (data.success) {
          analysis.value = {
            spf: data.spf_analysis,
            bf: data.bf_analysis,
            bqc: data.bqc_analysis,
            rqspf: data.rqspf_analysis
          }
        }
      } catch (e) {
        console.error('获取分析失败:', e)
      } finally {
        loading.value = false
      }
    }

    watch(() => props.match, fetchAnalysis, { immediate: true })

    return {
      activeTab,
      loading,
      analysis,
      playTabs,
      formatHandicap,
      hasAnyAnalysis,
      recommendations,
      valueBets
    }
  }
}
</script>

<style scoped>
.lottery-analysis {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.match-header {
  padding: 16px;
  background: rgba(255,255,255,0.05);
  border-radius: 12px;
}

.league-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.league-name {
  font-size: 14px;
  color: #10b981;
  font-weight: 600;
}

.match-time {
  font-size: 12px;
  color: #6b7280;
}

.teams-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.team {
  text-align: center;
}

.team-name {
  font-size: 18px;
  font-weight: 700;
  color: white;
}

.handicap {
  display: block;
  font-size: 12px;
  color: #f59e0b;
  margin-top: 4px;
}

.vs {
  font-size: 14px;
  font-weight: 600;
  color: #6b7280;
}

.play-tabs {
  display: flex;
  gap: 8px;
  padding: 4px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
}

.tab-btn {
  flex: 1;
  padding: 10px 16px;
  background: transparent;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(255,255,255,0.05);
  color: white;
}

.tab-btn.active {
  background: #10b981;
  color: white;
}

.analysis-content {
  min-height: 200px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
}

/* SPF分析样式 */
.prob-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.prob-bar-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.prob-label {
  width: 50px;
  font-size: 13px;
  color: #9ca3af;
}

.prob-bar-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.prob-bar {
  height: 24px;
  border-radius: 4px;
  transition: width 0.3s;
}

.prob-value {
  font-size: 13px;
  font-weight: 600;
  color: white;
  min-width: 50px;
}

.recommendation-box {
  margin-top: 16px;
  padding: 12px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid #10b981;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.rec-label { color: #9ca3af; }
.rec-result { color: #10b981; font-weight: 700; }
.rec-confidence { color: #6b7280; font-size: 12px; }

/* 比分分析样式 */
.score-table {
  border: 1px solid #374151;
  border-radius: 8px;
  overflow: hidden;
}

.score-header, .score-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  padding: 10px 12px;
}

.score-header {
  background: rgba(255,255,255,0.05);
  font-size: 12px;
  color: #6b7280;
}

.score-row {
  border-top: 1px solid #374151;
}

.score-value {
  font-weight: 600;
  color: white;
}

.score-prob {
  color: #10b981;
}

.score-result {
  font-size: 12px;
  color: #9ca3af;
}

/* 半全场样式 */
.bqc-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.bqc-item {
  padding: 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
  text-align: center;
}

.bqc-code {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #10b981;
}

.bqc-display {
  display: block;
  font-size: 11px;
  color: #9ca3af;
  margin: 4px 0;
}

.bqc-prob {
  font-size: 14px;
  font-weight: 600;
  color: white;
}

/* 让球分析样式 */
.comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.prob-col {
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
}

.prob-col.adjusted {
  background: rgba(16, 185, 129, 0.05);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.prob-col h5 {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.prob-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.prob-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.prob-item span:first-child { color: #9ca3af; }
.prob-item span:last-child { color: white; font-weight: 500; }

.handicap-line {
  color: #f59e0b;
}

/* 综合推荐 */
.summary-section {
  padding: 16px;
  background: rgba(255,255,255,0.05);
  border-radius: 12px;
}

.summary-section h3 {
  font-size: 14px;
  color: white;
  margin-bottom: 12px;
}

.recommendations {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.recommendation-card {
  display: flex;
  flex-direction: column;
  padding: 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
  min-width: 120px;
}

.play-type {
  font-size: 12px;
  color: #6b7280;
}

.result {
  font-size: 16px;
  font-weight: 700;
  color: white;
  margin: 4px 0;
}

.confidence {
  font-size: 11px;
}

.confidence.high { color: #10b981; }
.confidence.medium { color: #3b82f6; }
.confidence.low { color: #ef4444; }

/* 价值投注 */
.value-bets-section {
  padding: 16px;
  background: rgba(245, 158, 11, 0.05);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 12px;
}

.value-bets-section h3 {
  font-size: 14px;
  color: #f59e0b;
  margin-bottom: 12px;
}

.value-bets-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.value-bet-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
}

.bet-type {
  font-size: 12px;
  color: #6b7280;
}

.bet-result {
  font-weight: 600;
  color: white;
}

.bet-value {
  color: #10b981;
  font-weight: 700;
}

.bet-odds {
  font-size: 12px;
  color: #9ca3af;
  margin-left: auto;
}

/* 加载状态 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #6b7280;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #374151;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #6b7280;
}
</style>