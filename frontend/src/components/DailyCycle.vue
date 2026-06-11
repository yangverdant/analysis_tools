<template>
  <div class="daily-cycle">
    <div class="cycle-header">
      <h2>日循环面板 — {{ today }}</h2>
      <span :class="['status-badge', status]">{{ statusText }}</span>
    </div>

    <!-- 流程节点 -->
    <div class="flow-nodes">
      <div v-for="node in nodes" :key="node.id"
           :class="['flow-node', nodeState(node.id)]"
           @click="runMode(node.id)">
        <div class="node-icon">{{ node.icon }}</div>
        <div class="node-label">{{ node.label }}</div>
        <div class="node-status">{{ nodeStatusText(node.id) }}</div>
      </div>
    </div>

    <!-- 今日预测 -->
    <div class="section">
      <h3>今日预测 <span class="count">{{ predictions.length }}场</span></h3>
      <div v-if="predictions.length === 0" class="empty">暂无预测</div>
      <div v-for="(p, i) in predictions" :key="i" class="prediction-card">
        <div class="pred-header">
          <span class="league">{{ p.league }}</span>
          <span class="time">{{ p.match_time ? p.match_time.substring(0, 5) : '' }}</span>
        </div>
        <div class="pred-match" @click="toggleDetail(i)" style="cursor:pointer">
          {{ p.home }} vs {{ p.away }}
          <span class="expand-icon">{{ expandedIdx === i ? '▼' : '▶' }}</span>
        </div>
        <div class="pred-result">
          <span :class="['rec-badge', p.prediction?.recommended]">
            {{ recLabel(p.prediction?.recommended) }}
          </span>
          <span class="probs">
            {{ pct(p.prediction?.home_win) }} / {{ pct(p.prediction?.draw) }} / {{ pct(p.prediction?.away_win) }}
          </span>
        </div>
        <div v-if="p.model_vs_odds" class="pred-odds">
          <span :class="['agreement', p.model_vs_odds.agreement ? 'yes' : 'no']">
            {{ p.model_vs_odds.agreement ? '与赔率一致' : '与赔率分歧' }}
          </span>
        </div>
        <!-- 6项玩法 -->
        <div v-if="p.play_predictions" class="pred-plays">
          <div v-if="p.play_predictions.top3_scores?.length" class="play-row">
            <span class="play-tag">比分</span>
            <span v-for="(s, si) in p.play_predictions.top3_scores" :key="si" class="score-mini">
              {{ s.score }} <small>{{ (s.probability * 100).toFixed(0) }}%</small>
            </span>
          </div>
          <div v-if="p.play_predictions.rqspf?.direction_cn" class="play-row">
            <span class="play-tag">让球{{ p.play_predictions.rqspf.handicap ? '(' + p.play_predictions.rqspf.handicap + ')' : '' }}</span>
            <span class="rqspf-dir">{{ p.play_predictions.rqspf.direction_cn }}</span>
          </div>
          <div v-if="p.play_predictions.over_under?.recommendation" class="play-row">
            <span class="play-tag">大小</span>
            <span class="ou-dir">{{ p.play_predictions.over_under.recommendation }}</span>
          </div>
          <div v-if="p.play_predictions.bqc?.recommendation_cn" class="play-row">
            <span class="play-tag">半全</span>
            <span class="bqc-dir">{{ p.play_predictions.bqc.recommendation_cn }}</span>
          </div>
        </div>
        <!-- 因子分解展开区 -->
        <div v-if="expandedIdx === i" class="factor-detail">
          <div v-if="p.weights_used" class="factor-section">
            <div class="factor-title">模型权重</div>
            <div v-for="(w, key) in p.weights_used" :key="key" class="factor-bar-row">
              <span class="factor-name">{{ factorLabel(key) }}</span>
              <div class="factor-bar-bg">
                <div class="factor-bar-fill" :style="{width: (w * 100) + '%'}"></div>
              </div>
              <span class="factor-val">{{ (w * 100).toFixed(0) }}%</span>
            </div>
          </div>
          <div v-if="p.model_vs_odds?.edge" class="factor-section">
            <div class="factor-title">模型 vs 赔率</div>
            <div class="edge-row">
              <span class="edge-label">主胜</span>
              <span :class="['edge-val', p.model_vs_odds.edge.home_win >= 0 ? 'pos' : 'neg']">
                {{ p.model_vs_odds.edge.home_win >= 0 ? '+' : '' }}{{ (p.model_vs_odds.edge.home_win * 100).toFixed(1) }}%
              </span>
              <span class="edge-label">平局</span>
              <span :class="['edge-val', p.model_vs_odds.edge.draw >= 0 ? 'pos' : 'neg']">
                {{ p.model_vs_odds.edge.draw >= 0 ? '+' : '' }}{{ (p.model_vs_odds.edge.draw * 100).toFixed(1) }}%
              </span>
              <span class="edge-label">客胜</span>
              <span :class="['edge-val', p.model_vs_odds.edge.away_win >= 0 ? 'pos' : 'neg']">
                {{ p.model_vs_odds.edge.away_win >= 0 ? '+' : '' }}{{ (p.model_vs_odds.edge.away_win * 100).toFixed(1) }}%
              </span>
            </div>
          </div>
          <div v-if="p.match_profile" class="factor-section">
            <div class="factor-title">赛事画像</div>
            <div class="profile-tags">
              <span class="profile-tag">{{ p.match_profile.competition_type || '-' }}</span>
              <span class="profile-tag">{{ p.match_profile.participant_type || '-' }}</span>
              <span class="profile-tag">{{ p.match_profile.format_type || '-' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- TOP3 价值投注 -->
    <div class="section">
      <h3>TOP3 价值投注</h3>
      <div v-if="top3.length === 0" class="empty">暂无推荐</div>
      <div v-for="(b, i) in top3" :key="i" class="bet-card">
        <div class="bet-rank">{{ i + 1 }}</div>
        <div class="bet-info">
          <div class="bet-match">{{ b.home }} vs {{ b.away }}</div>
          <div class="bet-detail">
            <span class="bet-sel">{{ b.selection }}</span>
            <span class="bet-prob">{{ b.prob }}%</span>
            <span :class="['bet-edge', b.edge >= 0 ? 'pos' : 'neg']">
              优势{{ b.edge >= 0 ? '+' : '' }}{{ b.edge }}%
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="actions">
      <button class="btn-primary" @click="runMode('morning')" :disabled="running">
        {{ running ? '执行中...' : '运行晨间' }}
      </button>
      <button class="btn-secondary" @click="runMode('full')" :disabled="running">
        运行全量
      </button>
      <button class="btn-ghost" @click="refresh" :disabled="running">刷新</button>
      <button class="btn-accent" @click="runBacktest" :disabled="backtestLoading">
        {{ backtestLoading ? '回测中...' : '一键回测' }}
      </button>
    </div>

    <!-- 投注ROI -->
    <div class="section" v-if="betROI">
      <h3>投注追踪</h3>
      <div class="roi-row" v-if="betROI.summary">
        <div v-for="(s, period) in betROI.summary" :key="period" class="roi-item">
          <span class="roi-period">{{ period }}</span>
          <span :class="['roi-profit', s.total_profit >= 0 ? 'pos' : 'neg']">
            {{ s.total_profit >= 0 ? '+' : '' }}{{ s.total_profit }}元
          </span>
          <span class="roi-rate">ROI {{ s.roi }}%</span>
          <span class="roi-record">{{ s.wins }}W{{ s.losses }}L</span>
        </div>
      </div>
    </div>

    <!-- 准确率趋势 -->
    <div class="section">
      <h3>准确率趋势 <span class="count">
        <button :class="['trend-btn', trendDays===7&&'active']" @click="trendDays=7;fetchTrend()">7天</button>
        <button :class="['trend-btn', trendDays===30&&'active']" @click="trendDays=30;fetchTrend()">30天</button>
      </span></h3>
      <div v-if="accuracyTrend.length === 0" class="empty">暂无验证数据</div>
      <div v-else class="trend-chart">
        <div v-for="d in accuracyTrend" :key="d.date" class="trend-col">
          <div class="trend-bar-wrap">
            <div class="trend-bar model" :style="{height: d.accuracy + '%'}" :title="'模型 ' + d.accuracy + '%'"></div>
            <div v-if="d.odds_accuracy != null" class="trend-bar odds" :style="{height: d.odds_accuracy + '%'}" :title="'赔率 ' + d.odds_accuracy + '%'"></div>
          </div>
          <div class="trend-date">{{ d.date.slice(5) }}</div>
          <div class="trend-acc">{{ d.accuracy }}%</div>
        </div>
      </div>
      <div class="trend-legend">
        <span class="legend-item"><span class="legend-dot model"></span>模型</span>
        <span class="legend-item"><span class="legend-dot odds"></span>赔率</span>
      </div>
    </div>

    <!-- 回测结果 -->
    <div class="section" v-if="backtestResult">
      <h3>回测结果 ({{ backtestResult.days }}天)</h3>
      <div class="backtest-grid">
        <div class="bt-item"><span class="bt-label">总场次</span><span class="bt-val">{{ backtestResult.total_matches }}</span></div>
        <div class="bt-item"><span class="bt-label">正确率</span><span class="bt-val">{{ backtestResult.accuracy }}%</span></div>
        <div class="bt-item"><span class="bt-label">虚拟盈亏</span><span :class="['bt-val', backtestResult.total_profit >= 0 ? 'pos' : 'neg']">{{ backtestResult.total_profit >= 0 ? '+' : '' }}{{ backtestResult.total_profit }}元</span></div>
        <div class="bt-item"><span class="bt-label">ROI</span><span :class="['bt-val', backtestResult.roi >= 0 ? 'pos' : 'neg']">{{ backtestResult.roi }}%</span></div>
      </div>
    </div>

    <!-- 调度器状态 -->
    <div class="section" v-if="schedulerJobs.length">
      <h3>定时任务</h3>
      <div v-for="job in schedulerJobs" :key="job.id" class="job-item">
        <span class="job-name">{{ job.name }}</span>
        <span class="job-next">{{ job.next_run }}</span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'

const API_BASE = '/api'

export default {
  name: 'DailyCycle',
  setup() {
    const today = new Date().toISOString().slice(0, 10)
    const status = ref('idle')
    const statusText = ref('空闲')
    const running = ref(false)
    const predictions = ref([])
    const top3 = ref([])
    const betROI = ref(null)
    const schedulerJobs = ref([])
    const expandedIdx = ref(null)
    const accuracyTrend = ref([])
    const trendDays = ref(30)
    const backtestResult = ref(null)
    const backtestLoading = ref(false)
    let pollTimer = null

    const nodes = [
      { id: 'perceive', label: '感知', icon: '📡' },
      { id: 'collect', label: '采集', icon: '📥' },
      { id: 'classify', label: '分类', icon: '🏷️' },
      { id: 'intel', label: '情报', icon: '🔍' },
      { id: 'analyze', label: '分析', icon: '🧠' },
      { id: 'push', label: '推送', icon: '📤' },
      { id: 'clv', label: 'CLV', icon: '📈' },
      { id: 'validate', label: '复盘', icon: '✅' },
      { id: 'learn', label: '学习', icon: '🔄' },
    ]

    const nodeResults = ref({})

    function nodeState(id) {
      const r = nodeResults.value[id]
      if (!r) return 'pending'
      if (r === 'running') return 'running'
      return r.success !== false ? 'done' : 'error'
    }

    function nodeStatusText(id) {
      const r = nodeResults.value[id]
      if (!r) return ''
      if (r === 'running') return '...'
      return r.success !== false ? 'OK' : 'ERR'
    }

    function recLabel(rec) {
      return { home_win: '主胜', draw: '平', away_win: '客胜' }[rec] || rec || '-'
    }

    function pct(v) {
      return v != null ? Math.round(v * 100) + '%' : '-'
    }

    function factorLabel(key) {
      const map = { odds: '赔率', elo: 'Elo', poisson: '泊松', form: '状态', motivation: '动机', friendly: '友谊赛', cup: '杯赛', other: '其他' }
      return map[key] || key
    }

    function toggleDetail(idx) {
      expandedIdx.value = expandedIdx.value === idx ? null : idx
    }

    async function fetchStatus() {
      try {
        const res = await fetch(`${API_BASE}/cycle/status`)
        const data = await res.json()
        status.value = data.status || 'idle'
        statusText.value = { idle: '空闲', running: '运行中', completed: '已完成', error: '错误' }[status.value] || status.value

        for (const n of nodes) {
          if (data[n.id]) {
            nodeResults.value[n.id] = data[n.id]
          }
        }
      } catch {}
    }

    async function fetchPredictions() {
      try {
        const res = await fetch(`${API_BASE}/cycle/predictions`)
        const data = await res.json()
        predictions.value = data.predictions || []
      } catch {}
    }

    async function fetchTop3() {
      try {
        const res = await fetch(`${API_BASE}/cycle/top3`)
        const data = await res.json()
        top3.value = data.top3 || []
      } catch {}
    }

    async function fetchBetROI() {
      try {
        const res = await fetch(`${API_BASE}/bets/roi`)
        const data = await res.json()
        if (!data.error) betROI.value = data
      } catch {}
    }

    async function fetchScheduler() {
      try {
        const res = await fetch(`${API_BASE}/scheduler/status`)
        const data = await res.json()
        if (data.jobs) {
          schedulerJobs.value = data.jobs.map(j => ({
            id: j.id,
            name: j.name || j.id,
            next_run: j.next_run_time ? new Date(j.next_run_time).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '-',
          }))
        }
      } catch {}
    }

    async function fetchTrend() {
      try {
        const res = await fetch(`${API_BASE}/accuracy_trend?days=${trendDays.value}`)
        const data = await res.json()
        accuracyTrend.value = data.daily || []
      } catch {}
    }

    async function runBacktest() {
      backtestLoading.value = true
      try {
        const res = await fetch(`${API_BASE}/backtest?days=30&stake=100`)
        const data = await res.json()
        if (!data.error) backtestResult.value = data
      } catch {}
      backtestLoading.value = false
    }

    async function runMode(mode) {
      running.value = true
      try {
        await fetch(`${API_BASE}/cycle/run/${mode}`, { method: 'POST' })
        status.value = 'running'
        statusText.value = '运行中'
        nodeResults.value[mode] = 'running'
      } catch {}
      setTimeout(() => { refresh(); running.value = false }, 3000)
    }

    async function refresh() {
      await Promise.all([fetchStatus(), fetchPredictions(), fetchTop3(), fetchBetROI(), fetchScheduler(), fetchTrend()])
    }

    onMounted(() => {
      refresh()
      pollTimer = setInterval(refresh, 30000)
    })

    onUnmounted(() => {
      if (pollTimer) clearInterval(pollTimer)
    })

    return {
      today, status, statusText, running,
      predictions, top3, betROI, schedulerJobs, nodes, nodeResults,
      nodeState, nodeStatusText, recLabel, pct, factorLabel,
      expandedIdx, toggleDetail,
      accuracyTrend, trendDays, fetchTrend,
      backtestResult, backtestLoading, runBacktest,
      runMode, refresh
    }
  }
}
</script>

<style scoped>
.daily-cycle { padding: 4px; }

.cycle-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.cycle-header h2 { font-size: 16px; color: #e5e7eb; font-weight: 600; }

.status-badge {
  font-size: 12px; padding: 2px 10px; border-radius: 9999px;
}
.status-badge.idle { background: rgba(107,114,128,0.2); color: #9ca3af; }
.status-badge.running { background: rgba(59,130,246,0.2); color: #3b82f6; }
.status-badge.completed { background: rgba(16,185,129,0.2); color: #10b981; }
.status-badge.error { background: rgba(239,68,68,0.2); color: #ef4444; }

.flow-nodes {
  display: flex; gap: 4px; margin-bottom: 20px;
  overflow-x: auto; padding-bottom: 4px;
}
.flow-node {
  display: flex; flex-direction: column; align-items: center;
  padding: 8px 10px; border-radius: 8px; min-width: 56px;
  background: #151922; border: 1px solid #1f2937; cursor: pointer;
  transition: all 0.2s;
}
.flow-node:hover { border-color: #374151; }
.flow-node.done { border-color: #10b981; background: rgba(16,185,129,0.05); }
.flow-node.running { border-color: #3b82f6; background: rgba(59,130,246,0.05); }
.flow-node.error { border-color: #ef4444; background: rgba(239,68,68,0.05); }
.node-icon { font-size: 16px; }
.node-label { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.node-status { font-size: 10px; color: #6b7280; margin-top: 1px; }
.flow-node.done .node-status { color: #10b981; }
.flow-node.error .node-status { color: #ef4444; }

.section { margin-bottom: 16px; }
.section h3 {
  font-size: 14px; color: #e5e7eb; margin-bottom: 8px;
  display: flex; align-items: center; gap: 8px;
}
.count { font-size: 12px; color: #6b7280; font-weight: 400; }
.empty { color: #6b7280; font-size: 13px; padding: 12px; text-align: center; }

.prediction-card {
  background: #151922; border: 1px solid #1f2937; border-radius: 8px;
  padding: 10px 12px; margin-bottom: 6px;
}
.pred-header {
  display: flex; justify-content: space-between; font-size: 11px; color: #6b7280;
  margin-bottom: 4px;
}
.pred-match { font-size: 14px; color: #e5e7eb; font-weight: 500; margin-bottom: 4px; }
.expand-icon { font-size: 10px; color: #6b7280; margin-left: 6px; }
.pred-result { display: flex; align-items: center; gap: 8px; }
.rec-badge {
  font-size: 12px; padding: 1px 8px; border-radius: 4px; font-weight: 600;
}
.rec-badge.home_win { background: rgba(59,130,246,0.2); color: #3b82f6; }
.rec-badge.draw { background: rgba(139,92,246,0.2); color: #8b5cf6; }
.rec-badge.away_win { background: rgba(239,68,68,0.2); color: #ef4444; }
.probs { font-size: 12px; color: #9ca3af; }
.pred-odds { margin-top: 4px; }
.agreement.yes { font-size: 11px; color: #10b981; }
.agreement.no { font-size: 11px; color: #f59e0b; }

.pred-plays { margin-top: 6px; display: flex; flex-direction: column; gap: 3px; }
.play-row { display: flex; align-items: center; gap: 6px; font-size: 11px; }
.play-tag { color: #6b7280; min-width: 32px; }
.score-mini { background: #1e293b; padding: 1px 5px; border-radius: 3px; color: #e2e8f0; font-weight: 600; }
.score-mini:first-of-type { background: rgba(59,130,246,0.2); color: #93c5fd; }
.score-mini small { color: #94a3b8; font-weight: 400; }
.rqspf-dir, .ou-dir, .bqc-dir { font-weight: 600; color: #93c5fd; }

/* 因子分解 */
.factor-detail {
  margin-top: 8px; padding-top: 8px; border-top: 1px solid #1f2937;
}
.factor-section { margin-bottom: 8px; }
.factor-title { font-size: 11px; color: #9ca3af; margin-bottom: 4px; font-weight: 600; }
.factor-bar-row { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.factor-name { font-size: 11px; color: #6b7280; min-width: 36px; }
.factor-bar-bg { flex: 1; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; }
.factor-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #10b981); border-radius: 3px; transition: width 0.3s; }
.factor-val { font-size: 10px; color: #9ca3af; min-width: 28px; text-align: right; }
.edge-row { display: flex; gap: 10px; font-size: 11px; }
.edge-label { color: #6b7280; }
.edge-val { font-weight: 600; }
.edge-val.pos { color: #10b981; }
.edge-val.neg { color: #ef4444; }
.profile-tags { display: flex; gap: 4px; }
.profile-tag {
  font-size: 10px; padding: 1px 6px; border-radius: 3px;
  background: rgba(139,92,246,0.15); color: #a78bfa;
}

.bet-card {
  display: flex; align-items: center; gap: 10px;
  background: #151922; border: 1px solid #1f2937; border-radius: 8px;
  padding: 10px 12px; margin-bottom: 6px;
}
.bet-rank {
  width: 24px; height: 24px; border-radius: 50%; display: flex;
  align-items: center; justify-content: center; font-size: 12px;
  font-weight: 700; color: white; flex-shrink: 0;
}
.bet-card:nth-child(1) .bet-rank { background: #f59e0b; }
.bet-card:nth-child(2) .bet-rank { background: #9ca3af; }
.bet-card:nth-child(3) .bet-rank { background: #b45309; }
.bet-match { font-size: 13px; color: #e5e7eb; }
.bet-detail { display: flex; gap: 8px; font-size: 12px; margin-top: 2px; }
.bet-sel { color: #10b981; font-weight: 600; }
.bet-prob { color: #9ca3af; }
.bet-edge.pos { color: #10b981; }
.bet-edge.neg { color: #ef4444; }

.actions { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.btn-primary, .btn-secondary, .btn-ghost, .btn-accent {
  padding: 8px 16px; border-radius: 6px; font-size: 13px;
  border: none; cursor: pointer; transition: all 0.2s;
}
.btn-primary { background: #10b981; color: white; }
.btn-primary:hover { background: #059669; }
.btn-primary:disabled { background: #374151; color: #6b7280; cursor: default; }
.btn-secondary { background: #1f2937; color: #e5e7eb; }
.btn-secondary:hover { background: #374151; }
.btn-secondary:disabled { color: #6b7280; cursor: default; }
.btn-ghost { background: transparent; color: #9ca3af; border: 1px solid #374151; }
.btn-ghost:hover { color: #e5e7eb; border-color: #6b7280; }
.btn-ghost:disabled { color: #374151; cursor: default; }
.btn-accent { background: rgba(139,92,246,0.2); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3); }
.btn-accent:hover { background: rgba(139,92,246,0.3); }
.btn-accent:disabled { color: #6b7280; background: rgba(107,114,128,0.1); border-color: #374151; cursor: default; }

/* ROI */
.roi-row { display: flex; gap: 8px; }
.roi-item {
  flex: 1; background: #151922; border: 1px solid #1f2937; border-radius: 6px;
  padding: 8px 10px; display: flex; flex-direction: column; gap: 2px;
}
.roi-period { font-size: 11px; color: #6b7280; }
.roi-profit { font-size: 16px; font-weight: 700; }
.roi-profit.pos { color: #4ade80; }
.roi-profit.neg { color: #f87171; }
.roi-rate { font-size: 11px; color: #9ca3af; }
.roi-record { font-size: 11px; color: #6b7280; }

/* 准确率趋势 */
.trend-btn {
  font-size: 11px; padding: 1px 8px; border-radius: 4px; border: 1px solid #374151;
  background: transparent; color: #6b7280; cursor: pointer; margin-left: 4px;
}
.trend-btn.active { background: rgba(59,130,246,0.2); color: #3b82f6; border-color: #3b82f6; }
.trend-chart {
  display: flex; align-items: flex-end; gap: 2px; height: 100px;
  padding: 4px 0; overflow-x: auto;
}
.trend-col {
  display: flex; flex-direction: column; align-items: center;
  min-width: 20px; flex-shrink: 0;
}
.trend-bar-wrap {
  display: flex; gap: 2px; align-items: flex-end; height: 80px;
}
.trend-bar {
  width: 6px; border-radius: 2px 2px 0 0; min-height: 2px;
  transition: height 0.3s;
}
.trend-bar.model { background: #3b82f6; }
.trend-bar.odds { background: #6b7280; }
.trend-date { font-size: 9px; color: #6b7280; margin-top: 2px; }
.trend-acc { font-size: 9px; color: #9ca3af; }
.trend-legend { display: flex; gap: 12px; margin-top: 4px; }
.legend-item { font-size: 11px; color: #6b7280; display: flex; align-items: center; gap: 4px; }
.legend-dot { width: 8px; height: 8px; border-radius: 2px; }
.legend-dot.model { background: #3b82f6; }
.legend-dot.odds { background: #6b7280; }

/* 回测结果 */
.backtest-grid { display: flex; gap: 8px; }
.bt-item {
  flex: 1; background: #151922; border: 1px solid #1f2937; border-radius: 6px;
  padding: 8px 10px; display: flex; flex-direction: column; gap: 2px;
}
.bt-label { font-size: 11px; color: #6b7280; }
.bt-val { font-size: 16px; font-weight: 700; color: #e5e7eb; }
.bt-val.pos { color: #4ade80; }
.bt-val.neg { color: #f87171; }

/* Scheduler jobs */
.job-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 10px; background: #151922; border: 1px solid #1f2937;
  border-radius: 6px; margin-bottom: 4px;
}
.job-name { font-size: 12px; color: #e5e7eb; }
.job-next { font-size: 11px; color: #6b7280; }
</style>
