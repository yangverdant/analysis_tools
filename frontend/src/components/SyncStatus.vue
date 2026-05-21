<template>
  <div class="sync-status" v-if="showSync">
    <div class="sync-overlay" v-if="syncing"></div>
    <div class="sync-panel" :class="{ active: syncing }">
      <div class="sync-header">
        <div class="sync-icon" :class="{ spinning: syncing }">
          <RefreshIcon />
        </div>
        <span class="sync-title">{{ syncing ? '正在同步数据...' : '数据同步' }}</span>
      </div>

      <div class="sync-content" v-if="syncResult">
        <div class="sync-result" v-if="syncResult.finished_matches">
          <span class="label">已结束比赛:</span>
          <span class="value">{{ syncResult.finished_matches.updated || 0 }} 场更新</span>
        </div>
        <div class="sync-result" v-if="syncResult.upcoming_fixtures">
          <span class="label">未来赛程:</span>
          <span class="value">{{ syncResult.upcoming_fixtures.saved || 0 }} 场新增</span>
        </div>
      </div>

      <div class="sync-actions">
        <button class="sync-btn" @click="doFullSync" :disabled="syncing">
          <RefreshIcon />
          {{ syncing ? '同步中...' : '立即同步' }}
        </button>
        <button class="close-btn" @click="closePanel" v-if="!syncing">
          <CloseIcon />
        </button>
      </div>
    </div>

    <!-- 紧凑状态栏 -->
    <div class="sync-bar" v-if="!showPanel && lastSyncTime" @click="showPanel = true">
      <span class="sync-time">上次同步: {{ formatTime(lastSyncTime) }}</span>
      <span class="sync-indicator" :class="{ warning: needSync }">
        {{ needSync ? '需要同步' : '数据最新' }}
      </span>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed, h, defineComponent } from 'vue'
import { syncAPI } from '../api'

// 图标组件
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
    const showSync = ref(false)
    const showPanel = ref(false)
    const syncing = ref(false)
    const syncResult = ref(null)
    const lastSyncTime = ref(null)
    const needSync = ref(false)

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

    const checkSyncNeeded = async () => {
      try {
        const result = await syncAPI.checkNeeded()
        needSync.value = result.sync_recommended || false
        return result
      } catch (e) {
        console.error('检查同步状态失败:', e)
        return null
      }
    }

    const doFullSync = async () => {
      syncing.value = true
      syncResult.value = null

      try {
        const result = await syncAPI.fullSync()
        syncResult.value = result
        lastSyncTime.value = new Date().toISOString()
        needSync.value = false

        // 保存最后同步时间到localStorage
        localStorage.setItem('lastSyncTime', lastSyncTime.value)

        // 同步完成后刷新页面数据
        setTimeout(() => {
          window.location.reload()
        }, 2000)
      } catch (e) {
        console.error('同步失败:', e)
        syncResult.value = { error: e.message }
      } finally {
        syncing.value = false
      }
    }

    const closePanel = () => {
      showPanel.value = false
    }

    // 自动同步检查
    const autoSync = async () => {
      // 检查上次同步时间
      const savedTime = localStorage.getItem('lastSyncTime')
      if (savedTime) {
        lastSyncTime.value = savedTime
        const diff = Date.now() - new Date(savedTime).getTime()

        // 如果超过1小时没同步，显示同步提示
        if (diff > 3600000) {
          showSync.value = true
          needSync.value = true
        }
      }

      // 检查是否需要同步
      const status = await checkSyncNeeded()
      if (status && status.need_update_results > 0) {
        showSync.value = true
        needSync.value = true

        // 如果有需要更新的比赛，自动同步
        if (status.need_update_results > 5) {
          await doFullSync()
        }
      }
    }

    onMounted(() => {
      autoSync()
    })

    return {
      showSync,
      showPanel,
      syncing,
      syncResult,
      lastSyncTime,
      needSync,
      formatTime,
      doFullSync,
      closePanel
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
  gap: 12px;
  padding: 8px 16px;
  background: #1a2332;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.sync-bar:hover {
  background: #1f2937;
}

.sync-time {
  font-size: 12px;
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

.sync-panel {
  background: #1a2332;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 12px;
  padding: 16px;
  min-width: 280px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.sync-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.sync-icon {
  color: #6b7280;
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
}

.sync-content {
  margin-bottom: 12px;
}

.sync-result {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.sync-result:last-child {
  border-bottom: none;
}

.sync-result .label {
  font-size: 13px;
  color: #6b7280;
}

.sync-result .value {
  font-size: 13px;
  color: #10b981;
  font-weight: 500;
}

.sync-actions {
  display: flex;
  gap: 8px;
}

.sync-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
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

.sync-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
}

.sync-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e5e7eb;
}

.sync-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: -1;
}
</style>
