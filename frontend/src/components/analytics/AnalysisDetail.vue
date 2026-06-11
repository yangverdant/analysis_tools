<template>
  <div class="analysis-detail" v-if="prediction">
    <div class="detail-header">
      <h2>{{ prediction.home_team || '主队' }} vs {{ prediction.away_team || '客队' }}</h2>
      <span class="match-date">{{ prediction.match_date }}</span>
    </div>

    <!-- 赔率vs模型对比 -->
    <div class="comparison-section">
      <div class="prob-bars">
        <div class="prob-row">
          <span class="label">赔率</span>
          <div class="bar-group">
            <div class="bar odds-home" :style="{ width: oddsProbs.home_win + '%' }">
              {{ oddsProbs.home_win }}%
            </div>
            <div class="bar odds-draw" :style="{ width: oddsProbs.draw + '%' }">
              {{ oddsProbs.draw }}%
            </div>
            <div class="bar odds-away" :style="{ width: oddsProbs.away_win + '%' }">
              {{ oddsProbs.away_win }}%
            </div>
          </div>
        </div>
        <div class="prob-row">
          <span class="label">模型</span>
          <div class="bar-group">
            <div class="bar model-home" :style="{ width: modelProbs.home_win + '%' }">
              {{ modelProbs.home_win }}%
            </div>
            <div class="bar model-draw" :style="{ width: modelProbs.draw + '%' }">
              {{ modelProbs.draw }}%
            </div>
            <div class="bar model-away" :style="{ width: modelProbs.away_win + '%' }">
              {{ modelProbs.away_win }}%
            </div>
          </div>
        </div>
      </div>
      <div class="agreement-badge" :class="agreementClass">
        {{ agreementText }}
      </div>
    </div>

    <!-- 因子分解 + 准确率趋势 -->
    <div class="charts-grid">
      <FactorBreakdown :weights="currentWeights" :contributions="contributions" />
      <AccuracyTrend :days="30" />
    </div>

    <!-- 翻车归因 -->
    <div v-if="attribution" class="attribution-section">
      <h3>翻车归因</h3>
      <div class="attribution-card" :class="attribution.attribution_type">
        <div class="attr-type">{{ attributionLabel }}</div>
        <div class="attr-detail">{{ attribution.detail }}</div>
        <div v-if="attribution.actionable && attribution.suggested_action" class="attr-action">
          建议: {{ attribution.suggested_action }}
        </div>
      </div>
    </div>

    <!-- 推荐结果 -->
    <div class="recommendation-section">
      <div class="rec-card" :class="prediction.recommendation">
        <div class="rec-label">推荐</div>
        <div class="rec-value">{{ recLabel }}</div>
        <div class="rec-confidence">置信度: {{ prediction.confidence_level }}</div>
      </div>
    </div>
  </div>

  <div v-else class="no-data">
    <p>暂无分析数据</p>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { analysisAPI, trackingAPI } from '../api/index.js'
import FactorBreakdown from './FactorBreakdown.vue'
import AccuracyTrend from './AccuracyTrend.vue'

export default {
  name: 'AnalysisDetail',
  components: { FactorBreakdown, AccuracyTrend },
  props: {
    matchId: { type: String, required: true }
  },
  setup(props) {
    const prediction = ref(null)
    const attribution = ref(null)
    const contributions = ref({})

    const modelProbs = computed(() => {
      if (!prediction.value) return { home_win: 33, draw: 33, away_win: 33 }
      return {
        home_win: Math.round((prediction.value.home_win_prob || 0) * 100),
        draw: Math.round((prediction.value.draw_prob || 0) * 100),
        away_win: Math.round((prediction.value.away_win_prob || 0) * 100)
      }
    })

    const oddsProbs = computed(() => {
      if (!prediction.value?.odds) return modelProbs.value
      const o = prediction.value.odds
      if (!o.home || !o.draw || !o.away) return modelProbs.value
      const h = 1/o.home, d = 1/o.draw, a = 1/o.away, t = h+d+a
      return {
        home_win: Math.round(h/t * 100),
        draw: Math.round(d/t * 100),
        away_win: Math.round(a/t * 100)
      }
    })

    const currentWeights = computed(() => {
      if (!prediction.value?.weights) return {
        elo: 0.20, poisson: 0.25, h2h: 0.10, form: 0.15,
        home_away: 0.10, motivation: 0.10, news_factors: 0.10
      }
      try {
        return typeof prediction.value.weights === 'string'
          ? JSON.parse(prediction.value.weights)
          : prediction.value.weights
      } catch { return {} }
    })

    const agreementClass = computed(() => {
      if (!prediction.value) return ''
      return prediction.value.model_vs_odds?.agreement ? 'agree' : 'disagree'
    })

    const agreementText = computed(() => {
      if (!prediction.value) return ''
      return prediction.value.model_vs_odds?.agreement ? '模型与赔率一致' : '模型与赔率分歧'
    })

    const attributionLabel = computed(() => {
      const labels = {
        bad_luck: '运气差', close_match: '均势场',
        correction_wrong: '修正方向反', market_wrong: '市场也错', model_bias: '模型偏差'
      }
      return labels[attribution.value?.attribution_type] || attribution.value?.attribution_type
    })

    const recLabel = computed(() => {
      if (!prediction.value) return '-'
      const labels = { home_win: '主胜', draw: '平局', away_win: '客胜' }
      return labels[prediction.value.recommendation] || prediction.value.recommendation
    })

    onMounted(async () => {
      try {
        const res = await analysisAPI.getMatchPrediction(props.matchId)
        if (res) {
          prediction.value = res.final_prediction || res
        }
      } catch (e) {
        console.log('Prediction fetch failed:', e)
      }
    })

    return {
      prediction, attribution, contributions,
      modelProbs, oddsProbs, currentWeights,
      agreementClass, agreementText, attributionLabel, recLabel
    }
  }
}
</script>

<style scoped>
.analysis-detail { padding: 16px; }
.detail-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.detail-header h2 { font-size: 18px; color: #e5e7eb; }
.match-date { font-size: 13px; color: #6b7280; }

.comparison-section {
  background: #151922; border-radius: 8px; padding: 16px;
  border: 1px solid #1f2937; margin-bottom: 16px;
}
.prob-bars { display: flex; flex-direction: column; gap: 8px; }
.prob-row { display: flex; align-items: center; gap: 8px; }
.prob-row .label { width: 36px; font-size: 12px; color: #9ca3af; }
.bar-group { display: flex; flex: 1; height: 24px; border-radius: 4px; overflow: hidden; }
.bar { display: flex; align-items: center; justify-content: center; font-size: 10px; color: white; min-width: 20px; }
.bar.odds-home, .bar.model-home { background: #3b82f6; }
.bar.odds-draw, .bar.model-draw { background: #8b5cf6; }
.bar.odds-away, .bar.model-away { background: #ef4444; }
.bar.model-home { background: rgba(59,130,246,0.7); }
.bar.model-draw { background: rgba(139,92,246,0.7); }
.bar.model-away { background: rgba(239,68,68,0.7); }

.agreement-badge {
  margin-top: 12px; text-align: center; font-size: 12px;
  padding: 4px 12px; border-radius: 9999px; display: inline-block;
}
.agreement-badge.agree { background: rgba(16,185,129,0.1); color: #10b981; }
.agreement-badge.disagree { background: rgba(245,158,11,0.1); color: #f59e0b; }

.charts-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;
}
@media (max-width: 768px) { .charts-grid { grid-template-columns: 1fr; } }

.attribution-section {
  background: #151922; border-radius: 8px; padding: 16px;
  border: 1px solid #1f2937; margin-bottom: 16px;
}
.attribution-section h3 { font-size: 14px; color: #e5e7eb; margin-bottom: 12px; }
.attribution-card { padding: 12px; border-radius: 6px; border-left: 4px solid; }
.attribution-card.bad_luck { border-color: #6b7280; background: rgba(107,114,128,0.1); }
.attribution-card.close_match { border-color: #f59e0b; background: rgba(245,158,11,0.1); }
.attribution-card.correction_wrong { border-color: #ef4444; background: rgba(239,68,68,0.1); }
.attribution-card.market_wrong { border-color: #8b5cf6; background: rgba(139,92,246,0.1); }
.attribution-card.model_bias { border-color: #3b82f6; background: rgba(59,130,246,0.1); }
.attr-type { font-size: 14px; font-weight: 600; color: #e5e7eb; margin-bottom: 4px; }
.attr-detail { font-size: 13px; color: #9ca3af; }
.attr-action { font-size: 12px; color: #10b981; margin-top: 8px; }

.recommendation-section { display: flex; justify-content: center; }
.rec-card {
  text-align: center; padding: 20px 40px; border-radius: 8px;
  background: #151922; border: 1px solid #1f2937;
}
.rec-card.home_win { border-color: #3b82f6; }
.rec-card.draw { border-color: #8b5cf6; }
.rec-card.away_win { border-color: #ef4444; }
.rec-label { font-size: 12px; color: #6b7280; }
.rec-value { font-size: 24px; font-weight: 700; color: #e5e7eb; }
.rec-confidence { font-size: 12px; color: #9ca3af; margin-top: 4px; }

.no-data { text-align: center; color: #6b7280; padding: 40px; }
</style>