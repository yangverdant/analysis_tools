<template>
  <div class="sync-status" v-if="showSync">
    <div class="sync-overlay" v-if="syncing" @click.stop></div>
    <div class="sync-panel" :class="{ active: showPanel }">
      <div class="sync-header">
        <div class="sync-icon" :class="{ spinning: syncing }">
          <RefreshIcon />
        </div>
        <span class="sync-title">{{ syncing ? '正在同步...' : '数据同步中心' }}</span>
        <button class="close-btn" @click="closePanel" v-if="!syncing">
          <CloseIcon />
        </button>
      </div>

      <!-- 缺口报告 -->
      <div class="gap-report" v-if="gapReport && !syncing">
        <div class="gap-title">数据缺口</div>
        <div class="gap-items">
          <div class="gap-item" v-for="gap in gapItems" :key="gap.key" :class="{ warning: gap.count > 0 }">
            <span class="gap-label">{{ gap.label }}</span>
            <span class="gap-count">{{ gap.count }}</span>
          </div>
        </div>
      </div>

      <!-- 同步管道列表 -->
      <div class="sync-pipelines">
        <div class="pipeline-item" v-for="pipe in pipelines" :key="pipe.key">
          <div class="pipe-info">
            <span class="pipe-name">{{ pipe.name }}</span>
            <span class="pipe-desc">{{ pipe.desc }}</span>
          </div>
          <div class="pipe-status" v-if="pipe.status">
            <span :class="['status-tag', pipe.status]">{{ pipe.status === 'completed' ? '完成' : pipe.status === 'failed' ? '失败' : '运行中' }}</span>
          </div>
          <button class="pipe-btn" @click="runPipe(pipe)" :disabled="syncing">
            <RefreshIcon :class="{ spin: syncing && currentPipe === pipe.key }" />
          </button>
        </div>
      </div>

      <!-- 一键全量同步 -->
      <div class="sync-actions">
        <button class="sync-btn full" @click="runFullSync" :disabled="syncing">
          <RefreshIcon :class="{ spin: syncing && currentPipe === 'full' }" />
          {{ syncing && currentPipe === 'full' ? '全量同步中...' : '一键全量同步' }}
        </button>
      </div>

      <!-- 同步结果 -->
      <div class="sync-result" v-if="lastResult">
        <span :class="['result-tag', lastResult.type]">{{ lastResult.message }}</span>
      </div>
    </div>

    <!-- 紧凑状态栏 -->
    <div class="sync-bar" v-if="!showPanel" @click="openPanel">
      <RefreshIcon class="bar-icon" :class="{ spinning: syncing }" />
      <span class="sync-time" v-if="lastSyncTime">上次同步: {{ formatTime(lastSyncTime) }}</span>
      <span class="sync-indicator" :class="{ warning: needSync }">
        {{ syncing ? '同步中' : needSync ? '需要同步' : '数据最新' }}
      </span>
      <span class="gap-badge" v-if="totalGaps > 0">{{ totalGaps }}项缺失</span>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, h, defineComponent } from 'vue'
import { syncAPI } from '../api'

const createIcon = (paths) => defineComponent({
  name: 'Icon',
  setup: () => () => h('svg', {
    class: 'w-4 h-4',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': '2'
  }, paths)
})

const RefreshIcon = createIcon([
  h('path', { d: 'M23 4v6h-6' }),
  h('path', { d: 'M1 20v-6h6' }),
  h('path', { d: 'M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15' })
])

const CloseIcon = createIcon([
  h('line', { x1: '18', y1: '6', x2: '6', y2: '18' }),
  h('line', { x1: '6', y1: '6', x2: '18', y2: '18' })
])

export default {
  name: 'SyncStatus',
  components: { RefreshIcon, CloseIcon },
  setup() {
    const showSync = ref(true)
    const showPanel = ref(false)
    const syncing = ref(false)
    const currentPipe = ref(null)
    const lastSyncTime = ref(null)
    const needSync = ref(false)
    const gapReport = ref(null)
    const lastResult = ref(null)
    const pipeStatuses = ref({})

    const pipelines = computed(() => [
      { key: 'country_cn', name: '国家中文名', desc: '从linkage文件同步', status: pipeStatuses.value['country_cn'] },
      { key: 'league_rules', name: '联赛规则', desc: '自动推断赛制规则', status: pipeStatuses.value['league_rules'] },
      { key: 'player_cn', name: '球员中文名', desc: 'DeepSeek AI翻译', status: pipeStatuses.value['player_cn'] },
      { key: 'league_cn', name: '联赛中文名', desc: 'DeepSeek AI翻译', status: pipeStatuses.value['league_cn'] },
      { key: 'fix_season_ids', name: '赛季关联', desc: '修复比赛season_id', status: pipeStatuses.value['fix_season_ids'] },
      { key: 'match_results', name: '比赛结果', desc: 'API-Football同步', status: pipeStatuses.value['match_results'] },
      { key: 'future_matches', name: '未来赛程', desc: '同步即将开始的比赛', status: pipeStatuses.value['future_matches'] }
    ])

    const gapItems = computed(() => {
      if (!gapReport.value) return []
      const g = gapReport.value
      return [
        { key: 'team_cn', label: '球队缺中文名', count: g.missing_team_cn || 0 },
        { key: 'player_cn', label: '球员缺中文名', count: g.missing_player_cn || 0 },
        { key: 'league_cn', label: '联赛缺中文名', count: g.missing_league_cn || 0 },
        { key: 'country_cn', label: '国家缺中文名', count: g.missing_country_cn || 0 },
        { key: 'league_rules', label: '联赛缺规则', count: g.missing_league_rules || 0 },
        { key: 'match_scores', label: '比赛缺比分', count: g.missing_match_scores || 0 }
      ]
    })

    const totalGaps = computed(() => gapItems.value.reduce((sum, g) => sum + g.count, 0))

    const formatTime = (time) => {
      if (!time) return ''
      const date = new Date(time)
      const now = new Date()
      const diff = now - date
      if (diff < 60000) return '刚刚'
      if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
      return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    }

    const loadGapReport = async () => {
      try {
        const res = await syncAPI.getGapReport()
        if (res.success && res.gaps) {
          gapReport.value = res.gaps
          needSync.value = totalGaps.value > 0
        }
      } catch (e) {
        console.error('加载缺口报告失败:', e)
      }
    }

    const pollProgress = async (taskName) => {
      const poll = async () => {
        try {
          const res = await syncAPI.getProgress(taskName)
          if (res.status === 'completed' || res.status === 'failed') {
            pipeStatuses.value[taskName] = res.status
            if (res.status === 'completed') {
              lastResult.value = { type: 'success', message: `${taskName} 完成` }
            } else {
              lastResult.value = { type: 'error', message: `${taskName} 失败: ${res.error || ''}` }
            }
            syncing.value = false
            currentPipe.value = null
            lastSyncTime.value = new Date().toISOString()
            localStorage.setItem('lastSyncTime', lastSyncTime.value)
            loadGapReport()
            return
          }
        } catch (e) { /* ignore */ }
        setTimeout(poll, 2000)
      }
      setTimeout(poll, 1500)
    }

    const runPipe = async (pipe) => {
      syncing.value = true
      currentPipe.value = pipe.key
      lastResult.value = null
      try {
        const apiMap = {
          country_cn: () => syncAPI.syncCountryCN(),
          league_rules: () => syncAPI.syncLeagueRules(),
          player_cn: () => syncAPI.syncPlayerCN(200),
          league_cn: () => syncAPI.syncLeagueCN(200),
          fix_season_ids: () => syncAPI.fixSeasonIds(),
          match_results: () => syncAPI.syncFinished(),
          future_matches: () => syncAPI.syncUpcoming()
        }
        const fn = apiMap[pipe.key]
        if (fn) {
          await fn()
          pollProgress(pipe.key)
        }
      } catch (e) {
        syncing.value = false
        currentPipe.value = null
        lastResult.value = { type: 'error', message: `${pipe.name} 启动失败: ${e.message}` }
      }
    }

    const runFullSync = async () => {
      syncing.value = true
      currentPipe.value = 'full'
      lastResult.value = null
      try {
        await syncAPI.fullSync()
        pollProgress('full_sync')
      } catch (e) {
        syncing.value = false
        currentPipe.value = null
        lastResult.value = { type: 'error', message: `全量同步启动失败: ${e.message}` }
      }
    }

    const openPanel = () => { showPanel.value = true }
    const closePanel = () => { showPanel.value = false }

    onMounted(async () => {
      const savedTime = localStorage.getItem('lastSyncTime')
      if (savedTime) lastSyncTime.value = savedTime
      await loadGapReport()
      // 如果有缺口，自动显示
      if (totalGaps.value > 0) {
        needSync.value = true
      }
    })

    return {
      showSync, showPanel, syncing, currentPipe, lastSyncTime, needSync,
      gapReport, lastResult, pipelines, gapItems, totalGaps,
      formatTime, runPipe, runFullSync, openPanel, closePanel
    }
  }
}
</script>

<style scoped>
.sync-status {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 1000;
}

.sync-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #1a2332;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.sync-bar:hover {
  background: #1f2937;
}

.bar-icon {
  width: 14px;
  height: 14px;
  color: #6b7280;
  flex-shrink: 0;
}

.bar-icon.spinning {
  animation: spin 1s linear infinite;
  color: #10b981;
}

.sync-time {
  font-size: 11px;
  color: #6b7280;
}

.sync-indicator {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.sync-indicator.warning {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.gap-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  font-weight: 500;
}

.sync-panel {
  background: #1a2332;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 12px;
  padding: 16px;
  width: 340px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.sync-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.sync-icon {
  color: #6b7280;
  flex-shrink: 0;
}

.sync-icon.spinning {
  animation: spin 1s linear infinite;
  color: #10b981;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.sync-title {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
  flex: 1;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 6px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e5e7eb;
}

/* 缺口报告 */
.gap-report {
  margin-bottom: 12px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
}

.gap-title {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 6px;
  font-weight: 500;
}

.gap-items {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}

.gap-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 6px;
  border-radius: 3px;
  font-size: 11px;
}

.gap-item.warning .gap-count {
  color: #fbbf24;
  font-weight: 600;
}

.gap-label {
  color: #9ca3af;
}

.gap-count {
  color: #6b7280;
}

/* 同步管道 */
.sync-pipelines {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
  max-height: 260px;
  overflow-y: auto;
}

.pipeline-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.pipeline-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

.pipe-info {
  flex: 1;
  min-width: 0;
}

.pipe-name {
  font-size: 12px;
  color: #e5e7eb;
  font-weight: 500;
  display: block;
}

.pipe-desc {
  font-size: 10px;
  color: #6b7280;
  display: block;
}

.pipe-status {
  flex-shrink: 0;
}

.status-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 500;
}

.status-tag.completed {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.status-tag.failed {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.status-tag.running {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.pipe-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 4px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.pipe-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.1);
  border-color: #10b981;
  color: #10b981;
}

.pipe-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* 全量同步按钮 */
.sync-actions {
  margin-bottom: 8px;
}

.sync-btn.full {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.sync-btn.full:hover:not(:disabled) {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
}

.sync-btn.full:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 结果提示 */
.sync-result {
  text-align: center;
  padding: 4px;
}

.result-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 8px;
}

.result-tag.success {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.result-tag.error {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.sync-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.2);
  z-index: -1;
}
</style>
