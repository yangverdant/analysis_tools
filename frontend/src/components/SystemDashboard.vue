<template>
  <section class="dashboard">
    <div class="dash-head">
      <div>
        <div class="dash-kicker">System Cockpit</div>
        <h2>系统驾驶舱</h2>
      </div>
      <div class="dash-actions">
        <button class="dash-refresh" @click="loadAll" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="loading && !dashboardData" class="dash-loading">加载中...</div>
    <div v-else-if="error" class="dash-error">{{ error }}</div>

    <template v-else>
      <!-- 标签页 -->
      <div class="dash-tabs">
        <button v-for="tab in tabs" :key="tab.key"
                :class="['dash-tab', { active: activeTab === tab.key }]"
                @click="activeTab = tab.key">
          {{ tab.label }}
          <span v-if="tab.badge" class="tab-badge" :class="tab.badgeClass">{{ tab.badge }}</span>
        </button>
      </div>

      <!-- 实时运转 -->
      <div v-if="activeTab === 'live'" class="tab-panel">
        <div class="panel-grid">
          <div class="status-strip">
            <div v-for="card in liveCards" :key="card.key" :class="['status-card', card.state]">
              <div class="card-label">{{ card.label }}</div>
              <div class="card-value">{{ card.value }}</div>
              <div class="card-sub" v-if="card.sub">{{ card.sub }}</div>
            </div>
          </div>

          <div class="panel-card">
            <h3>日循环当前节点</h3>
            <div class="cycle-flow">
              <div v-for="(node, i) in cycleNodes" :key="node.name"
                   :class="['cycle-node', { active: node.active, done: node.done }]">
                <div class="cycle-dot"></div>
                <div class="cycle-label">{{ node.label }}</div>
                <div class="cycle-time" v-if="node.time">{{ node.time }}</div>
              </div>
            </div>
          </div>

          <div class="panel-card">
            <h3>定时任务</h3>
            <div class="jobs-list">
              <div v-for="job in schedulerJobs" :key="job.id" class="job-row">
                <div class="job-name">{{ job.name }}</div>
                <div class="job-next">{{ job.next_run || '未调度' }}</div>
              </div>
              <div v-if="!schedulerJobs.length" class="empty">无定时任务</div>
            </div>
          </div>

          <div class="panel-card wide">
            <h3>最近24h任务执行</h3>
            <div class="timeline" v-if="timeline.length">
              <div v-for="evt in timeline" :key="evt.id" :class="['tl-item', evt.status]">
                <div class="tl-time">{{ evt.time }}</div>
                <div class="tl-dot"></div>
                <div class="tl-content">
                  <div class="tl-title">{{ evt.name }}</div>
                  <div class="tl-meta" v-if="evt.duration">{{ evt.duration }}s · {{ evt.status }}</div>
                </div>
              </div>
            </div>
            <div v-else class="empty">无执行记录</div>
          </div>

          <div class="panel-card wide" v-if="latestAgentReport">
            <h3>🤖 最近AI分析师早报</h3>
            <div class="agent-report" v-html="renderMarkdown(latestAgentReport)"></div>
          </div>
        </div>
      </div>

      <!-- 模型表现 -->
      <div v-if="activeTab === 'model'" class="tab-panel">
        <div class="panel-grid">
          <div class="panel-card wide">
            <h3>30天准确率走势</h3>
            <div class="chart-wrap" v-if="accuracyTrend.length">
              <MultiLineChart
                :lines="accuracyLines"
                :yMax="100"
                :yLabels="[0, 25, 50, 75, 100]"
                :xLabels="accuracyXLabels"
                :height="240"
              />
            </div>
            <div v-else class="empty">暂无趋势数据</div>
          </div>

          <div class="panel-card">
            <h3>各玩法准确率 vs 目标</h3>
            <div class="targets-list">
              <div v-for="t in playTargets" :key="t.play_type" class="target-row">
                <div class="target-name">{{ t.play_type.toUpperCase() }}</div>
                <div class="target-bar-wrap">
                  <div class="target-bar" :style="{ width: t.current_pct + '%' }" :class="t.met ? 'met' : 'gap'"></div>
                  <div class="target-line" :style="{ left: t.target_pct + '%' }"></div>
                </div>
                <div class="target-val">{{ (t.current * 100).toFixed(1) }}% / {{ (t.target * 100).toFixed(0) }}%</div>
              </div>
            </div>
          </div>

          <div class="panel-card">
            <h3>当前模型版本</h3>
            <div class="model-version">{{ modelVersion }}</div>
            <div class="model-acc">30天准确率 {{ (currentAccuracy * 100).toFixed(1) }}%</div>
            <div class="model-weights" v-if="activeWeights">
              <div v-for="(v, k) in activeWeights" :key="k" class="weight-row">
                <span class="w-name">{{ k }}</span>
                <span class="w-val">{{ (v * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 学习进度 -->
      <div v-if="activeTab === 'learning'" class="tab-panel">
        <div class="panel-grid">
          <div class="panel-card wide">
            <h3>最近参数变更</h3>
            <div class="changes-list" v-if="learningHistory.length">
              <div v-for="c in learningHistory" :key="c.id" class="change-row">
                <div class="chg-time">{{ (c.changed_at || '').slice(0, 16) }}</div>
                <div class="chg-param">{{ c.param_name }}</div>
                <div class="chg-val">{{ c.old_value }} → {{ c.new_value }}</div>
                <div class="chg-reason">{{ (c.change_reason || '').slice(0, 60) }}</div>
              </div>
            </div>
            <div v-else class="empty">暂无学习记录</div>
          </div>

          <div class="panel-card">
            <h3>熔断事件</h3>
            <div class="circuit-list" v-if="circuitEvents.length">
              <div v-for="c in circuitEvents" :key="c.id" class="circuit-row">
                <div class="cb-scene">{{ c.scene }} / {{ c.participant_type }}</div>
                <div class="cb-reason">{{ (c.change_reason || '').slice(0, 50) }}</div>
              </div>
            </div>
            <div v-else class="empty">无熔断</div>
          </div>

          <div class="panel-card wide">
            <h3>场景×玩法准确率热力图</h3>
            <div class="heatmap-wrap" v-if="sceneAccuracy.length">
              <div class="heatmap-table">
                <div class="heatmap-row heatmap-header">
                  <div class="hm-cell hm-label">场景 / 玩法</div>
                  <div class="hm-cell" v-for="p in playTypes" :key="p">{{ p }}</div>
                  <div class="hm-cell hm-total">整体</div>
                </div>
                <div v-for="sc in sceneAccuracy" :key="sc.scenario" class="heatmap-row">
                  <div class="hm-cell hm-label">{{ scenarioLabel(sc.scenario) }}</div>
                  <div v-for="p in playTypes" :key="p" class="hm-cell" :class="heatClass(sc, p)">
                    {{ heatValue(sc, p) }}
                  </div>
                  <div class="hm-cell hm-total">{{ sc.overall_accuracy?.toFixed(1) }}%</div>
                </div>
              </div>
              <div class="heatmap-legend">
                <span class="leg-item"><span class="leg-dot strong"></span>强项(≥基线+5pp)</span>
                <span class="leg-item"><span class="leg-dot normal"></span>正常</span>
                <span class="leg-item"><span class="leg-dot weak"></span>弱项(≤基线-5pp)</span>
                <span class="leg-item leg-baseline">基线 {{ baseline }}%</span>
              </div>
            </div>
            <div v-else class="empty">暂无场景准确率数据</div>
          </div>

          <div class="panel-card">
            <h3>发现的场景偏差</h3>
            <div class="segments-list" v-if="discoveredSegments.length">
              <div v-for="s in discoveredSegments" :key="s.key" class="segment-row">
                <div class="seg-key">{{ s.key }}</div>
                <div class="seg-gap" :class="s.gap > 0.08 ? 'high' : ''">gap {{ (s.gap * 100).toFixed(1) }}pp</div>
                <div class="seg-sample">{{ s.sample }}场</div>
              </div>
            </div>
            <div v-else class="empty">暂无发现</div>
          </div>
        </div>
      </div>

      <!-- 投注ROI -->
      <div v-if="activeTab === 'roi'" class="tab-panel">
        <div class="panel-grid">
          <div class="panel-card wide">
            <h3>ROI走势</h3>
            <div class="chart-wrap" v-if="roiTrend.length">
              <MultiLineChart
                :lines="roiLines"
                :yMax="roiYMax"
                :yLabels="roiYLabels"
                :xLabels="roiXLabels"
                :height="240"
              />
            </div>
            <div v-else class="empty">暂无ROI数据</div>
          </div>

          <div class="panel-card">
            <h3>ROI概况</h3>
            <div class="roi-grid" v-if="roiSummary">
              <div class="roi-item">
                <div class="roi-label">7天</div>
                <div class="roi-val" :class="roiSummary.roi_7d >= 0 ? 'pos' : 'neg'">{{ roiSummary.roi_7d?.toFixed(1) }}%</div>
              </div>
              <div class="roi-item">
                <div class="roi-label">30天</div>
                <div class="roi-val" :class="roiSummary.roi_30d >= 0 ? 'pos' : 'neg'">{{ roiSummary.roi_30d?.toFixed(1) }}%</div>
              </div>
              <div class="roi-item">
                <div class="roi-label">全部</div>
                <div class="roi-val" :class="roiSummary.roi_all >= 0 ? 'pos' : 'neg'">{{ roiSummary.roi_all?.toFixed(1) }}%</div>
              </div>
            </div>
          </div>

          <div class="panel-card">
            <h3>止损状态</h3>
            <div class="stoploss-box" :class="stopLossActive ? 'active' : 'safe'">
              <div class="sl-status">{{ stopLossActive ? '止损激活' : '正常' }}</div>
              <div class="sl-detail" v-if="stopLossDetail">{{ stopLossDetail }}</div>
            </div>
          </div>

          <div class="panel-card wide">
            <h3>近期投注记录</h3>
            <div class="bets-list" v-if="recentBets.length">
              <div v-for="b in recentBets" :key="b.id" class="bet-row" :class="b.result">
                <div class="bet-match">{{ b.home }} vs {{ b.away }}</div>
                <div class="bet-sel">{{ b.play_type }} · {{ b.selection }}</div>
                <div class="bet-odds">@{{ b.odds }}</div>
                <div class="bet-result">{{ b.result }}</div>
                <div class="bet-profit" :class="b.profit >= 0 ? 'pos' : 'neg'">{{ b.profit >= 0 ? '+' : '' }}{{ b.profit?.toFixed(0) }}</div>
              </div>
            </div>
            <div v-else class="empty">暂无投注记录</div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import MultiLineChart from './data-view/MultiLineChart.vue'

const loading = ref(false)
const error = ref('')
const activeTab = ref('live')
const dashboardData = ref(null)
const modelStatus = ref(null)
const schedulerData = ref(null)
const timeline = ref([])
const learningHistory = ref([])
const roiTrend = ref([])
const roiSummary = ref(null)
const recentBets = ref([])
const discoveredSegments = ref([])
const pushHistory = ref([])
const sceneAccuracy = ref([])
const baseline = ref(0)
const playTypes = ['spf', 'rqspf', 'ou', 'bqc', 'bf']

const tabs = computed(() => [
  { key: 'live', label: '实时运转', badge: liveCards.value.find(c => c.key === 'running')?.value || '', badgeClass: 'run' },
  { key: 'model', label: '模型表现' },
  { key: 'learning', label: '学习进度' },
  { key: 'roi', label: '投注ROI' },
])

const liveCards = computed(() => {
  const d = dashboardData.value || {}
  const s = d.status || {}
  return [
    { key: 'health', label: '系统健康', value: s.health || 'ok', state: s.health === 'ok' ? 'success' : 'failed' },
    { key: 'running', label: '正在执行', value: s.running_count || 0, state: 'running' },
    { key: 'failures', label: '近24h失败', value: s.recent_failure_count || 0, state: (s.recent_failure_count || 0) > 0 ? 'failed' : 'success' },
    { key: 'automation', label: '自动化', value: s.automation_enabled ? '开启' : '关闭', state: s.automation_enabled ? 'success' : 'planned' },
    { key: 'learning', label: '学习锁', value: s.learning_locked ? '锁定' : '空闲', state: s.learning_locked ? 'running' : 'planned' },
  ]
})

const cycleNodes = computed(() => {
  const nodes = [
    { name: 'perceive', label: '感知', time: '06:00' },
    { name: 'collect', label: '采集', time: '07:00' },
    { name: 'intel', label: '情报', time: '08:00' },
    { name: 'classify', label: '分类', time: '08:30' },
    { name: 'analyze', label: '分析', time: '09:00' },
    { name: 'push', label: '推送', time: '09:30' },
    { name: 'clv', label: 'CLV', time: '14:00' },
    { name: 'validate', label: '验证', time: '次日' },
    { name: 'learn', label: '学习', time: '次日' },
  ]
  const hour = new Date().getHours()
  return nodes.map(n => {
    const h = parseInt(n.time === '次日' ? '24' : n.time.split(':')[0])
    return { ...n, done: hour > h, active: hour === h }
  })
})

const schedulerJobs = computed(() => schedulerData.value?.jobs || [])

const modelVersion = computed(() => modelStatus.value?.model_version || '-')
const currentAccuracy = computed(() => modelStatus.value?.current_accuracy_30d || 0)
const activeWeights = computed(() => modelStatus.value?.active_weights)
const playTargets = computed(() => {
  const t = modelStatus.value?.play_accuracy_targets || {}
  return Object.entries(t).map(([k, v]) => ({
    play_type: k,
    current: v.current || 0,
    target: v.target || 0,
    current_pct: (v.current || 0) * 100,
    target_pct: (v.target || 0) * 100,
    met: v.met,
  }))
})

const accuracyTrendData = ref([])
const accuracyTrend = computed(() => accuracyTrendData.value)

const circuitEvents = computed(() => {
  return (learningHistory.value || []).filter(c => (c.change_reason || '').includes('熔断'))
})

const stopLossActive = computed(() => {
  return recentBets.value.length > 0 && roiSummary.value?.roi_7d < -30
})

const stopLossDetail = computed(() => {
  if (!stopLossActive.value) return '近7天ROI未触及-30%止损线'
  return `近7天ROI ${roiSummary.value?.roi_7d?.toFixed(1)}%，已激活止损`
})

const latestAgentReport = computed(() => {
  if (!pushHistory.value.length) return ''
  const latest = pushHistory.value[0]
  return latest.agent_report_text || ''
})

// 准确率趋势图适配
const accuracyLines = computed(() => {
  if (!accuracyTrend.value.length) return []
  return [{
    data: accuracyTrend.value.map(p => p.accuracy || 0),
    color: '#10b981'
  }]
})
const accuracyXLabels = computed(() => {
  return accuracyTrend.value.map(p => (p.period || '').slice(5))
})

// ROI趋势图适配
const roiLines = computed(() => {
  if (!roiTrend.value.length) return []
  return [
    { data: roiTrend.value.map(p => p.roi || 0), color: '#3b82f6' },
    { data: roiTrend.value.map(p => p.cum_roi || 0), color: '#f59e0b' }
  ]
})
const roiYMax = computed(() => {
  if (!roiTrend.value.length) return 100
  const vals = roiTrend.value.flatMap(p => [p.roi || 0, p.cum_roi || 0])
  const max = Math.max(...vals, 50)
  const min = Math.min(...vals, -50)
  return Math.max(Math.abs(max), Math.abs(min), 50)
})
const roiYLabels = computed(() => {
  const m = roiYMax.value
  return [Math.round(-m), Math.round(-m/2), 0, Math.round(m/2), Math.round(m)]
})
const roiXLabels = computed(() => {
  return roiTrend.value.map(p => (p.date || '').slice(5))
})

const renderMarkdown = (text) => {
  if (!text) return ''
  // 简单Markdown渲染
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/\n/g, '<br>')
}

const scenarioLabel = (sc) => {
  const map = { friendly_intl: '友谊赛', international_cup: '国际杯赛', league: '联赛' }
  return map[sc] || sc
}

const _playInScenario = (sc, p) => {
  if (!sc || !sc.plays) return null
  return sc.plays.find(x => x.play_type === p) || null
}

const heatClass = (sc, p) => {
  const play = _playInScenario(sc, p)
  if (!play) return 'hm-empty'
  return 'hm-' + (play.status || 'normal')
}

const heatValue = (sc, p) => {
  const play = _playInScenario(sc, p)
  if (!play) return '—'
  return play.accuracy?.toFixed(1) + '%'
}

const loadAll = async () => {
  loading.value = true
  error.value = ''
  try {
    const [dash, model, sched, tl, lh, rt, bets, segs, ph, sa, at] = await Promise.all([
      fetch('/api/v1/lottery/automation-dashboard').then(r => r.json()),
      fetch('/api/v1/lottery/model-status').then(r => r.json()),
      fetch('/api/scheduler/status').then(r => r.json()),
      fetch('/api/v1/lottery/automation-timeline?hours=24').then(r => r.json()).catch(() => ({ events: [] })),
      fetch('/api/v1/lottery/learning-history?limit=20').then(r => r.json()).catch(() => ({ changes: [] })),
      fetch('/api/v1/lottery/roi-trend?days=30').then(r => r.json()).catch(() => ({ trend: [] })),
      fetch('/api/v1/lottery/roi').then(r => r.json()).catch(() => ({})),
      fetch('/api/v1/lottery/discovered-segments').then(r => r.json()).catch(() => ({ segments: [] })),
      fetch('/api/v1/lottery/push-history?limit=3').then(r => r.json()).catch(() => ({ history: [] })),
      fetch('/api/v1/lottery/scene-accuracy?days=30').then(r => r.json()).catch(() => ({ scenarios: [] })),
      fetch('/api/v1/lottery/accuracy-trend?days=30').then(r => r.json()).catch(() => ({ trend: [] })),
    ])
    dashboardData.value = dash
    modelStatus.value = model
    schedulerData.value = sched
    timeline.value = tl.events || []
    learningHistory.value = lh.changes || []
    roiTrend.value = rt.trend || []
    roiSummary.value = bets.summary || bets
    recentBets.value = bets.recent_bets || []
    discoveredSegments.value = segs.segments || []
    pushHistory.value = ph.history || []
    sceneAccuracy.value = sa.scenarios || []
    baseline.value = sa.baseline || 0
    accuracyTrendData.value = at.trend || []
  } catch (e) {
    error.value = '加载失败: ' + e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.dashboard { padding: 16px; max-width: 1400px; margin: 0 auto; }
.dash-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.dash-kicker { font-size: 11px; color: #64748b; letter-spacing: 1px; text-transform: uppercase; }
.dash-head h2 { margin: 4px 0 0; font-size: 24px; }
.dash-refresh { padding: 8px 16px; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.dash-refresh:disabled { opacity: 0.5; }
.dash-loading, .dash-error { padding: 40px; text-align: center; color: #64748b; }
.dash-error { color: #ef4444; }

.dash-tabs { display: flex; gap: 4px; border-bottom: 1px solid #1e293b; margin-bottom: 20px; }
.dash-tab { padding: 10px 16px; background: none; border: none; color: #94a3b8; cursor: pointer; border-bottom: 2px solid transparent; font-size: 14px; position: relative; }
.dash-tab.active { color: #3b82f6; border-bottom-color: #3b82f6; }
.tab-badge { display: inline-block; margin-left: 6px; padding: 1px 6px; border-radius: 8px; font-size: 10px; background: #334155; color: #cbd5e1; }
.tab-badge.run { background: #065f46; color: #6ee7b7; }

.panel-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
.panel-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 16px; }
.panel-card.wide { grid-column: span 2; }
.panel-card h3 { margin: 0 0 12px; font-size: 14px; color: #e2e8f0; }

.status-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin-bottom: 16px; grid-column: span 2; }
.status-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; }
.status-card.success { border-color: #065f46; }
.status-card.failed { border-color: #7f1d1d; }
.status-card.running { border-color: #1e40af; }
.status-card.planned { border-color: #334155; }
.card-label { font-size: 11px; color: #94a3b8; }
.card-value { font-size: 22px; font-weight: 600; color: #e2e8f0; margin-top: 4px; }
.card-sub { font-size: 11px; color: #64748b; margin-top: 2px; }

.cycle-flow { display: flex; flex-wrap: wrap; gap: 8px; }
.cycle-node { display: flex; flex-direction: column; align-items: center; padding: 8px; border-radius: 6px; min-width: 60px; position: relative; }
.cycle-node.done { opacity: 0.5; }
.cycle-node.active { background: #1e3a8a; }
.cycle-dot { width: 10px; height: 10px; border-radius: 50%; background: #334155; margin-bottom: 4px; }
.cycle-node.done .cycle-dot { background: #065f46; }
.cycle-node.active .cycle-dot { background: #3b82f6; box-shadow: 0 0 8px #3b82f6; }
.cycle-label { font-size: 11px; color: #cbd5e1; }
.cycle-time { font-size: 10px; color: #64748b; }

.jobs-list { display: flex; flex-direction: column; gap: 8px; }
.job-row { display: flex; justify-content: space-between; padding: 8px; background: #1e293b; border-radius: 4px; font-size: 12px; }
.job-name { color: #e2e8f0; }
.job-next { color: #94a3b8; }

.timeline { position: relative; padding-left: 16px; max-height: 400px; overflow-y: auto; }
.timeline::before { content: ''; position: absolute; left: 7px; top: 0; bottom: 0; width: 1px; background: #334155; }
.tl-item { position: relative; padding: 8px 0 8px 16px; }
.tl-time { position: absolute; left: -50px; top: 10px; font-size: 10px; color: #64748b; width: 48px; text-align: right; }
.tl-dot { position: absolute; left: -5px; top: 12px; width: 8px; height: 8px; border-radius: 50%; background: #3b82f6; }
.tl-item.failed .tl-dot { background: #ef4444; }
.tl-item.completed .tl-dot { background: #10b981; }
.tl-content { display: inline-block; }
.tl-title { font-size: 13px; color: #e2e8f0; }
.tl-meta { font-size: 11px; color: #64748b; }

.targets-list { display: flex; flex-direction: column; gap: 10px; }
.target-row { display: grid; grid-template-columns: 50px 1fr 90px; align-items: center; gap: 8px; font-size: 12px; }
.target-name { color: #94a3b8; }
.target-bar-wrap { position: relative; height: 8px; background: #1e293b; border-radius: 4px; }
.target-bar { height: 100%; border-radius: 4px; }
.target-bar.met { background: #10b981; }
.target-bar.gap { background: #f59e0b; }
.target-line { position: absolute; top: -2px; bottom: -2px; width: 2px; background: #ef4444; }
.target-val { color: #e2e8f0; font-size: 11px; text-align: right; }

.model-version { font-family: monospace; font-size: 12px; color: #3b82f6; word-break: break-all; }
.model-acc { font-size: 18px; color: #e2e8f0; margin: 8px 0; }
.model-weights { display: flex; flex-direction: column; gap: 4px; }
.weight-row { display: flex; justify-content: space-between; font-size: 11px; }
.w-name { color: #94a3b8; }
.w-val { color: #e2e8f0; }

.changes-list { display: flex; flex-direction: column; gap: 8px; max-height: 500px; overflow-y: auto; }
.change-row { display: grid; grid-template-columns: 90px 1fr 1fr; gap: 8px; padding: 8px; background: #1e293b; border-radius: 4px; font-size: 11px; }
.chg-time { color: #64748b; }
.chg-param { color: #3b82f6; font-family: monospace; }
.chg-val { color: #e2e8f0; }
.chg-reason { grid-column: span 3; color: #94a3b8; font-size: 10px; }

.circuit-list { display: flex; flex-direction: column; gap: 6px; }
.circuit-row { padding: 8px; background: #7f1d1d33; border-left: 3px solid #ef4444; border-radius: 4px; font-size: 11px; }
.cb-scene { color: #fca5a5; font-weight: 500; }
.cb-reason { color: #94a3b8; margin-top: 2px; }

.segments-list { display: flex; flex-direction: column; gap: 6px; }
.segment-row { display: grid; grid-template-columns: 1fr 70px 50px; gap: 8px; padding: 8px; background: #1e293b; border-radius: 4px; font-size: 11px; align-items: center; }
.seg-key { color: #e2e8f0; font-family: monospace; }
.seg-gap { color: #f59e0b; text-align: right; }
.seg-gap.high { color: #ef4444; }
.seg-sample { color: #64748b; text-align: right; }

.roi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.roi-item { text-align: center; padding: 12px; background: #1e293b; border-radius: 6px; }
.roi-label { font-size: 11px; color: #94a3b8; }
.roi-val { font-size: 20px; font-weight: 600; margin-top: 4px; }
.roi-val.pos { color: #10b981; }
.roi-val.neg { color: #ef4444; }

.stoploss-box { padding: 16px; border-radius: 8px; text-align: center; }
.stoploss-box.safe { background: #065f4633; }
.stoploss-box.active { background: #7f1d1d33; }
.sl-status { font-size: 18px; font-weight: 600; }
.stoploss-box.safe .sl-status { color: #10b981; }
.stoploss-box.active .sl-status { color: #ef4444; }
.sl-detail { font-size: 11px; color: #94a3b8; margin-top: 4px; }

.bets-list { display: flex; flex-direction: column; gap: 6px; max-height: 400px; overflow-y: auto; }
.bet-row { display: grid; grid-template-columns: 1fr 1fr 50px 60px 50px; gap: 8px; padding: 8px; background: #1e293b; border-radius: 4px; font-size: 11px; align-items: center; }
.bet-row.win { border-left: 3px solid #10b981; }
.bet-row.lose { border-left: 3px solid #ef4444; }
.bet-match { color: #e2e8f0; }
.bet-sel { color: #94a3b8; }
.bet-odds { color: #64748b; }
.bet-result { color: #cbd5e1; }
.bet-profit { text-align: right; font-weight: 600; }
.bet-profit.pos { color: #10b981; }
.bet-profit.neg { color: #ef4444; }

.empty { text-align: center; padding: 24px; color: #64748b; font-size: 12px; }
.chart-wrap { background: #1e293b; border-radius: 6px; padding: 8px; }

.agent-report { font-size: 13px; line-height: 1.6; color: #cbd5e1; max-height: 400px; overflow-y: auto; }
.agent-report :deep(h3) { color: #3b82f6; margin: 12px 0 6px; font-size: 14px; }
.agent-report :deep(h4) { color: #60a5fa; margin: 10px 0 4px; font-size: 13px; }
.agent-report :deep(strong) { color: #e2e8f0; }
.agent-report :deep(blockquote) { border-left: 3px solid #f59e0b; padding-left: 8px; color: #fbbf24; margin: 4px 0; }

/* 场景准确率热力图 */
.heatmap-wrap { display: flex; flex-direction: column; gap: 10px; }
.heatmap-table { display: flex; flex-direction: column; gap: 2px; font-size: 11px; }
.heatmap-row { display: grid; grid-template-columns: 100px repeat(5, 1fr) 70px; gap: 2px; }
.heatmap-header { font-weight: 600; color: #9ca3af; }
.heatmap-header .hm-cell { background: transparent; padding: 4px; text-align: center; }
.hm-cell { padding: 8px 4px; text-align: center; border-radius: 3px; background: #1e293b; color: #e2e8f0; }
.hm-cell.hm-label { text-align: left; font-weight: 500; color: #cbd5e1; background: transparent; }
.hm-cell.hm-total { font-weight: 600; background: #0f172a; color: #94a3b8; }
.hm-cell.hm-empty { background: #0f172a; color: #475569; }
.hm-cell.hm-strong { background: rgba(16, 185, 129, 0.25); color: #6ee7b7; font-weight: 600; }
.hm-cell.hm-normal { background: rgba(100, 116, 139, 0.2); color: #cbd5e1; }
.hm-cell.hm-weak { background: rgba(239, 68, 68, 0.25); color: #fca5a5; font-weight: 600; }
.heatmap-legend { display: flex; gap: 14px; font-size: 11px; color: #9ca3af; flex-wrap: wrap; }
.leg-item { display: flex; align-items: center; gap: 4px; }
.leg-dot { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.leg-dot.strong { background: rgba(16, 185, 129, 0.6); }
.leg-dot.normal { background: rgba(100, 116, 139, 0.5); }
.leg-dot.weak { background: rgba(239, 68, 68, 0.6); }
.leg-baseline { margin-left: auto; color: #6b7280; }
</style>
