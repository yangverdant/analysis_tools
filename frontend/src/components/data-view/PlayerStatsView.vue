<template>
  <div class="player-stats-view">
    <!-- 统计类型标签 -->
    <div class="stat-tabs">
      <button
        v-for="tab in statTabs"
        :key="tab.key"
        :class="['stat-tab', { active: activeStat === tab.key }]"
        @click="activeStat = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 球员列表 -->
    <div class="player-table">
      <div class="table-header">
        <span class="col rank">#</span>
        <span class="col player">球员</span>
        <span class="col team">球队</span>
        <span class="col pos">位置</span>
        <span class="col">出场</span>
        <span class="col" v-if="activeStat !== 'minute'">{{ statLabel }}</span>
        <span class="col" v-if="activeStat === 'goals'">点球</span>
        <span class="col" v-if="activeStat === 'cards'">黄/红</span>
        <span class="col" v-if="activeStat === 'minute'">首发</span>
        <span class="col" v-if="activeStat === 'minute'">分钟</span>
      </div>
      <div class="table-body" v-if="players.length">
        <div class="table-row" v-for="player in players" :key="player.rank">
          <span class="col rank" :class="'rank-' + Math.min(player.rank, 3)">{{ player.rank }}</span>
          <span class="col player">
            <span class="player-name">{{ player.player_cn || player.player }}</span>
            <span class="player-nation" v-if="player.nation_cn">{{ player.nation_cn }}</span>
          </span>
          <span class="col team">{{ player.team_cn || player.team }}</span>
          <span class="col pos">{{ formatPosition(player.position) }}</span>
          <span class="col">{{ player.matches }}</span>
          <span class="col stat-value" v-if="activeStat !== 'minute'">{{ getStatValue(player) }}</span>
          <span class="col" v-if="activeStat === 'goals'">{{ player.penalties || 0 }}</span>
          <span class="col cards" v-if="activeStat === 'cards'">
            <span class="yellow">{{ player.yellow_cards }}</span>/<span class="red">{{ player.red_cards }}</span>
          </span>
          <span class="col" v-if="activeStat === 'minute'">{{ player.starts }}</span>
          <span class="col" v-if="activeStat === 'minute'">{{ player.minutes }}</span>
        </div>
      </div>
      <div v-else class="no-data">暂无球员数据</div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue'
import { leagueAPI } from '../../api'

export default {
  name: 'PlayerStatsView',
  props: {
    leagueId: { type: Number, required: true },
    season: { type: String, default: null }
  },
  setup(props) {
    const players = ref([])
    const activeStat = ref('goals')
    const loading = ref(false)

    const statTabs = [
      { key: 'goals', label: '射手榜' },
      { key: 'assists', label: '助攻榜' },
      { key: 'cards', label: '红黄牌' },
      { key: 'minute', label: '出场时间' }
    ]

    const statLabel = computed(() => {
      const tab = statTabs.find(t => t.key === activeStat.value)
      if (tab) {
        if (tab.key === 'goals') return '进球'
        if (tab.key === 'assists') return '助攻'
        if (tab.key === 'cards') return '黄牌'
      }
      return ''
    })

    const loadData = async () => {
      if (!props.leagueId) return
      loading.value = true
      try {
        const res = await leagueAPI.getPlayerStats(props.leagueId, props.season, activeStat.value)
        if (res.data) players.value = res.data
      } catch (e) {
        console.error('加载球员数据失败:', e)
        players.value = []
      } finally {
        loading.value = false
      }
    }

    const getStatValue = (player) => {
      if (activeStat.value === 'goals') return player.goals
      if (activeStat.value === 'assists') return player.assists
      if (activeStat.value === 'cards') return player.yellow_cards
      return ''
    }

    const formatPosition = (pos) => {
      if (!pos) return '-'
      const map = { 'GK': '门将', 'DF': '后卫', 'MF': '中场', 'FW': '前锋' }
      return map[pos] || pos
    }

    watch(() => [props.leagueId, props.season, activeStat], loadData)
    onMounted(loadData)

    return { players, activeStat, statTabs, statLabel, loading, getStatValue, formatPosition }
  }
}
</script>

<style scoped>
.player-stats-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.stat-tabs {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.stat-tab {
  font-size: 14px;
  color: #9ca3af;
  background: transparent;
  border: none;
  padding: 0 0 8px 0;
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.stat-tab:hover { color: #e5e7eb; }
.stat-tab.active { color: #10b981; font-weight: 500; }
.stat-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: #10b981;
}

.player-table {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.table-header, .table-row {
  display: flex;
  align-items: center;
  padding: 10px 16px;
}

.table-header {
  font-size: 11px;
  color: #6b7280;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
}

.table-body {
  flex: 1;
  overflow-y: auto;
}

.table-row {
  font-size: 12px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.2);
  transition: background 0.2s;
}

.table-row:hover { background: rgba(255, 255, 255, 0.03); }

.col {
  text-align: center;
  color: #9ca3af;
}

.col.rank {
  width: 32px;
  font-weight: 600;
  color: #d1d5db;
}

.col.rank-1 { color: #fbbf24; }
.col.rank-2 { color: #9ca3af; }
.col.rank-3 { color: #d97706; }

.col.player {
  flex: 1;
  text-align: left;
  display: flex;
  flex-direction: column;
}

.player-name {
  color: #e5e7eb;
  font-weight: 500;
}

.player-nation {
  font-size: 10px;
  color: #6b7280;
}

.col.team {
  width: 100px;
  text-align: left;
  color: #d1d5db;
}

.col.pos {
  width: 40px;
}

.col.stat-value {
  font-weight: 600;
  color: #10b981;
}

.col.cards .yellow { color: #fbbf24; }
.col.cards .red { color: #ef4444; }

.no-data {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 12px;
}
</style>