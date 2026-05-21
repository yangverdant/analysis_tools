<template>
  <div class="favorites-panel">
    <!-- 标签页 -->
    <div class="tabs-header">
      <button :class="['tab', { active: activeTab === 'teams' }]" @click="activeTab = 'teams'">
        <UsersIcon /> 收藏球队
      </button>
      <button :class="['tab', { active: activeTab === 'leagues' }]" @click="activeTab = 'leagues'">
        <TrophyIcon /> 收藏联赛
      </button>
      <button :class="['tab', { active: activeTab === 'matches' }]" @click="activeTab = 'matches'">
        <CalendarIcon /> 关注比赛
      </button>
    </div>

    <!-- 收藏球队 -->
    <div v-if="activeTab === 'teams'" class="content-section">
      <div class="teams-grid">
        <div class="team-card" v-for="team in favoriteTeams" :key="team.id">
          <div class="team-header">
            <div class="team-logo">
              <img :src="team.logo" :alt="team.name" />
            </div>
            <button class="remove-btn" @click="removeFavorite('team', team.id)">
              <XIcon />
            </button>
          </div>
          <div class="team-info">
            <h3 class="team-name">{{ team.name }}</h3>
            <p class="team-meta">{{ team.league }} · {{ team.country }}</p>
          </div>
          <div class="team-stats">
            <div class="stat">
              <span class="value">{{ team.form }}</span>
              <span class="label">近5场</span>
            </div>
            <div class="stat">
              <span class="value">{{ team.position }}</span>
              <span class="label">排名</span>
            </div>
            <div class="stat">
              <span class="value">{{ team.points }}</span>
              <span class="label">积分</span>
            </div>
          </div>
          <div class="team-form">
            <span v-for="(r, i) in team.recentForm" :key="i" :class="['form-badge', r]">{{ r }}</span>
          </div>
          <button class="view-btn" @click="goToTeam(team.id)">查看详情</button>
        </div>
      </div>

      <!-- 添加收藏 -->
      <div class="add-favorite" @click="showAddModal = true">
        <PlusIcon />
        <span>添加收藏球队</span>
      </div>
    </div>

    <!-- 收藏联赛 -->
    <div v-if="activeTab === 'leagues'" class="content-section">
      <div class="leagues-grid">
        <div class="league-card" v-for="league in favoriteLeagues" :key="league.id">
          <div class="league-header">
            <span class="league-icon">⚽</span>
            <button class="remove-btn" @click="removeFavorite('league', league.id)">
              <XIcon />
            </button>
          </div>
          <div class="league-info">
            <h3 class="league-name">{{ league.name }}</h3>
            <p class="league-country">{{ league.country }}</p>
          </div>
          <div class="league-stats">
            <div class="stat">
              <span class="value">{{ league.teams }}</span>
              <span class="label">球队</span>
            </div>
            <div class="stat">
              <span class="value">{{ league.matches }}</span>
              <span class="label">比赛</span>
            </div>
          </div>
          <button class="view-btn" @click="goToLeague(league.id)">查看积分榜</button>
        </div>
      </div>
    </div>

    <!-- 关注比赛 -->
    <div v-if="activeTab === 'matches'" class="content-section">
      <div class="matches-list">
        <div class="match-item" v-for="match in followedMatches" :key="match.id">
          <div class="match-date">
            <span class="day">{{ match.day }}</span>
            <span class="time">{{ match.time }}</span>
          </div>
          <div class="match-content">
            <div class="match-league">{{ match.league }}</div>
            <div class="match-teams">
              <span class="team home">{{ match.homeTeam }}</span>
              <span class="vs">VS</span>
              <span class="team away">{{ match.awayTeam }}</span>
            </div>
          </div>
          <div class="match-actions">
            <button class="notify-btn" :class="{ active: match.notify }" @click="toggleNotify(match)">
              <BellIcon />
            </button>
            <button class="remove-btn small" @click="removeFavorite('match', match.id)">
              <XIcon />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="isEmpty" class="empty-state">
      <StarIcon class="empty-icon" />
      <h3>暂无收藏</h3>
      <p>点击球队或联赛页面的收藏按钮，将它们添加到这里</p>
    </div>
  </div>
</template>

<script>
import { ref, computed, h, defineComponent } from 'vue'

// 图标组件
const UsersIcon = defineComponent({
  name: 'UsersIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
      h('circle', { cx: '9', cy: '7', r: '4' }),
      h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
      h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
    ])
  }
})

const TrophyIcon = defineComponent({
  name: 'TrophyIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M6 9H4.5a2.5 2.5 0 0 1 0-5H6' }),
      h('path', { d: 'M18 9h1.5a2.5 2.5 0 0 0 0-5H18' }),
      h('path', { d: 'M4 22h16' }),
      h('path', { d: 'M18 2H6v7a6 6 0 0 0 12 0V2Z' })
    ])
  }
})

const CalendarIcon = defineComponent({
  name: 'CalendarIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }),
      h('line', { x1: '16', y1: '2', x2: '16', y2: '6' }),
      h('line', { x1: '8', y1: '2', x2: '8', y2: '6' }),
      h('line', { x1: '3', y1: '10', x2: '21', y2: '10' })
    ])
  }
})

const StarIcon = defineComponent({
  name: 'StarIcon',
  setup() {
    return () => h('svg', { class: 'w-8 h-8', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5' }, [
      h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' })
    ])
  }
})

const XIcon = defineComponent({
  name: 'XIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('line', { x1: '18', y1: '6', x2: '6', y2: '18' }),
      h('line', { x1: '6', y1: '6', x2: '18', y2: '18' })
    ])
  }
})

const PlusIcon = defineComponent({
  name: 'PlusIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('line', { x1: '12', y1: '5', x2: '12', y2: '19' }),
      h('line', { x1: '5', y1: '12', x2: '19', y2: '12' })
    ])
  }
})

const BellIcon = defineComponent({
  name: 'BellIcon',
  setup() {
    return () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
      h('path', { d: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9' }),
      h('path', { d: 'M13.73 21a2 2 0 0 1-3.46 0' })
    ])
  }
})

export default {
  name: 'Favorites',
  components: { UsersIcon, TrophyIcon, CalendarIcon, StarIcon, XIcon, PlusIcon, BellIcon },
  setup() {
    const activeTab = ref('teams')
    const showAddModal = ref(false)

    const favoriteTeams = ref([
      { id: 1, name: '曼城', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/1200px-Manchester_City_FC_badge.svg.png', league: '英超', country: '英格兰', form: '4胜1平', position: 1, points: 82, recentForm: ['W', 'W', 'W', 'D', 'W'] },
      { id: 2, name: '阿森纳', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png', league: '英超', country: '英格兰', form: '3胜1平1负', position: 2, points: 80, recentForm: ['W', 'W', 'D', 'L', 'W'] },
      { id: 3, name: '皇马', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png', league: '西甲', country: '西班牙', form: '5胜', position: 1, points: 88, recentForm: ['W', 'W', 'W', 'W', 'W'] },
    ])

    const favoriteLeagues = ref([
      { id: 1, name: '英超', country: '英格兰', teams: 20, matches: 380 },
      { id: 2, name: '西甲', country: '西班牙', teams: 20, matches: 380 },
      { id: 3, name: '欧冠', country: '欧洲', teams: 32, matches: 125 },
    ])

    const followedMatches = ref([
      { id: 1, day: '今天', time: '22:00', league: '英超', homeTeam: '曼城', awayTeam: '阿森纳', notify: true },
      { id: 2, day: '明天', time: '21:30', league: '德甲', homeTeam: '拜仁', awayTeam: '多特', notify: false },
      { id: 3, day: '周日', time: '03:00', league: '西甲', homeTeam: '皇马', awayTeam: '巴萨', notify: true },
    ])

    const isEmpty = computed(() => {
      if (activeTab.value === 'teams') return favoriteTeams.value.length === 0
      if (activeTab.value === 'leagues') return favoriteLeagues.value.length === 0
      return followedMatches.value.length === 0
    })

    const removeFavorite = (type, id) => {
      if (type === 'team') favoriteTeams.value = favoriteTeams.value.filter(t => t.id !== id)
      if (type === 'league') favoriteLeagues.value = favoriteLeagues.value.filter(l => l.id !== id)
      if (type === 'match') followedMatches.value = followedMatches.value.filter(m => m.id !== id)
    }

    const toggleNotify = (match) => { match.notify = !match.notify }
    const goToTeam = (id) => console.log('Go to team:', id)
    const goToLeague = (id) => console.log('Go to league:', id)

    return {
      activeTab, showAddModal, favoriteTeams, favoriteLeagues, followedMatches,
      isEmpty, removeFavorite, toggleNotify, goToTeam, goToLeague
    }
  }
}
</script>

<style scoped>
.favorites-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.tabs-header {
  display: flex;
  gap: 0;
  background: #151922;
  border-radius: 12px;
  padding: 4px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #9ca3af;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.tab svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.tab:hover { color: #e5e7eb; }

.tab.active {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 球队卡片 */
.teams-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.team-card {
  background: #151922;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.team-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.team-logo {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: rgba(255,255,255,0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.team-logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.remove-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: rgba(239, 68, 68, 0.1);
  border: none;
  color: #f87171;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.remove-btn:hover { background: rgba(239, 68, 68, 0.2); }
.remove-btn.small { width: 32px; height: 32px; }

.team-name {
  font-size: 16px;
  font-weight: 600;
  color: white;
  margin-bottom: 4px;
}

.team-meta {
  font-size: 12px;
  color: #6b7280;
}

.team-stats {
  display: flex;
  gap: 16px;
  margin: 16px 0;
  padding: 12px 0;
  border-top: 1px solid rgba(31, 41, 55, 0.5);
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.stat {
  flex: 1;
  text-align: center;
}

.stat .value {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #e5e7eb;
}

.stat .label {
  font-size: 11px;
  color: #6b7280;
}

.team-form {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
}

.form-badge {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
}

.form-badge.W { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.form-badge.D { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.form-badge.L { background: rgba(239, 68, 68, 0.15); color: #ef4444; }

.view-btn {
  width: 100%;
  padding: 10px;
  border-radius: 8px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #10b981;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.view-btn:hover { background: rgba(16, 185, 129, 0.2); }

/* 联赛卡片 */
.leagues-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.league-card {
  background: #151922;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.league-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.league-icon {
  font-size: 40px;
}

.league-name {
  font-size: 16px;
  font-weight: 600;
  color: white;
  margin-bottom: 4px;
}

.league-country {
  font-size: 12px;
  color: #6b7280;
}

.league-stats {
  display: flex;
  gap: 24px;
  margin: 16px 0;
}

/* 比赛列表 */
.matches-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.match-item {
  display: flex;
  align-items: center;
  gap: 20px;
  background: #151922;
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.match-date {
  text-align: center;
  min-width: 60px;
}

.match-date .day {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #10b981;
}

.match-date .time {
  font-size: 12px;
  color: #6b7280;
}

.match-content {
  flex: 1;
}

.match-league {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 6px;
}

.match-teams {
  display: flex;
  align-items: center;
  gap: 12px;
}

.match-teams .team {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.match-teams .vs {
  font-size: 12px;
  color: #4b5563;
}

.match-actions {
  display: flex;
  gap: 8px;
}

.notify-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(255,255,255,0.05);
  border: none;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.notify-btn.active { background: rgba(16, 185, 129, 0.15); color: #10b981; }

/* 添加收藏 */
.add-favorite {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  background: #151922;
  border: 2px dashed rgba(31, 41, 55, 0.5);
  border-radius: 12px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
}

.add-favorite:hover {
  border-color: #10b981;
  color: #10b981;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #6b7280;
}

.empty-icon {
  margin-bottom: 8px;
  opacity: 0.3;
  width: 24px;
  height: 24px;
}

.empty-state h3 {
  font-size: 14px;
  color: #9ca3af;
  margin-bottom: 4px;
}

.empty-state p {
  font-size: 12px;
}
</style>