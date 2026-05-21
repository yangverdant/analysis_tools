<template>
  <div class="teams-panel">
    <!-- 搜索和筛选 -->
    <div class="search-section">
      <div class="search-box">
        <SearchIcon class="search-icon" />
        <input v-model="searchQuery" placeholder="搜索球队名称..." @input="handleSearch" />
      </div>
      <div class="filters">
        <select v-model="selectedType" class="filter-select">
          <option value="">全部类型</option>
          <option value="club">俱乐部</option>
          <option value="national">国家队</option>
        </select>
        <select v-model="selectedCountry" class="filter-select">
          <option value="">全部国家</option>
          <option value="england">英格兰</option>
          <option value="spain">西班牙</option>
          <option value="germany">德国</option>
          <option value="italy">意大利</option>
          <option value="france">法国</option>
        </select>
        <select v-model="selectedLeague" class="filter-select">
          <option value="">全部联赛</option>
          <option value="premier">英超</option>
          <option value="laliga">西甲</option>
          <option value="bundesliga">德甲</option>
        </select>
      </div>
    </div>

    <!-- 热门球队 -->
    <div class="section" v-if="!searchQuery">
      <div class="section-header">
        <h2><StarIcon /> 热门球队</h2>
      </div>
      <div class="hot-teams">
        <div class="hot-team-card" v-for="team in hotTeams" :key="team.id" @click="goToTeam(team.id)">
          <div class="team-logo">
            <img :src="team.logo" :alt="team.name" />
          </div>
          <div class="team-info">
            <h3 class="team-name">{{ team.name }}</h3>
            <p class="team-meta">{{ team.league }} · {{ team.country }}</p>
          </div>
          <div class="team-stats-mini">
            <span class="position" :class="getPositionClass(team.position)">{{ team.position }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 球队列表 -->
    <div class="section">
      <div class="section-header">
        <h2><UsersIcon /> 全部球队</h2>
        <span class="count">{{ filteredTeams.length }} 支球队</span>
      </div>
      <div class="teams-grid">
        <div class="team-card" v-for="team in filteredTeams" :key="team.id" @click="goToTeam(team.id)">
          <div class="card-header">
            <div class="team-logo-small">
              <img :src="team.logo" :alt="team.name" />
            </div>
            <button class="favorite-btn" :class="{ active: team.isFavorite }" @click.stop="toggleFavorite(team)">
              <StarIcon />
            </button>
          </div>
          <div class="card-body">
            <h3 class="team-name">{{ team.name }}</h3>
            <p class="team-meta">{{ team.league || team.country }}</p>
            <div class="team-badges">
              <span class="badge type" :class="team.type">{{ team.type === 'club' ? '俱乐部' : '国家队' }}</span>
              <span class="badge country">{{ team.country }}</span>
            </div>
          </div>
          <div class="card-footer">
            <div class="stat-item">
              <span class="stat-value">{{ team.matches || 0 }}</span>
              <span class="stat-label">比赛</span>
            </div>
            <div class="stat-item">
              <span class="stat-value win">{{ team.wins || 0 }}</span>
              <span class="stat-label">胜</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ team.draws || 0 }}</span>
              <span class="stat-label">平</span>
            </div>
            <div class="stat-item">
              <span class="stat-value loss">{{ team.losses || 0 }}</span>
              <span class="stat-label">负</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载更多 -->
      <div class="load-more" v-if="hasMore">
        <button class="load-more-btn" @click="loadMore">
          <RefreshIcon />
          加载更多
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, h } from 'vue'

const SearchIcon = () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('circle', { cx: '11', cy: '11', r: '8' }),
  h('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' })
])

const StarIcon = () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' })
])

const UsersIcon = () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: '9', cy: '7', r: '4' }),
  h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
  h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
])

const RefreshIcon = () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('polyline', { points: '23 4 23 10 17 10' }),
  h('polyline', { points: '1 20 1 14 7 14' }),
  h('path', { d: 'M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15' })
])

export default {
  name: 'Teams',
  components: { SearchIcon, StarIcon, UsersIcon, RefreshIcon },
  setup() {
    const searchQuery = ref('')
    const selectedType = ref('')
    const selectedCountry = ref('')
    const selectedLeague = ref('')
    const hasMore = ref(true)

    const hotTeams = ref([
      { id: 1, name: '曼城', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/1200px-Manchester_City_FC_badge.svg.png', league: '英超', country: '英格兰', position: 1 },
      { id: 2, name: '阿森纳', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png', league: '英超', country: '英格兰', position: 2 },
      { id: 3, name: '皇马', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png', league: '西甲', country: '西班牙', position: 1 },
      { id: 4, name: '拜仁', logo: 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/FC_Bayern_M%C3%BCnchen_logo_%282017%29.svg/1200px-FC_Bayern_M%C3%BCnchen_logo_%282017%29.svg.png', league: '德甲', country: '德国', position: 1 },
      { id: 5, name: '巴黎圣日耳曼', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/a/a7/Paris_Saint-Germain_F.C..svg/1200px-Paris_Saint-Germain_F.C..svg.png', league: '法甲', country: '法国', position: 1 },
      { id: 6, name: '国际米兰', logo: 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/FC_Internazionale_Milano_2021.svg/1200px-FC_Internazionale_Milano_2021.svg.png', league: '意甲', country: '意大利', position: 1 },
    ])

    const allTeams = ref([
      { id: 1, name: '曼城', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/1200px-Manchester_City_FC_badge.svg.png', type: 'club', country: '英格兰', league: '英超', matches: 35, wins: 25, draws: 7, losses: 3, isFavorite: true },
      { id: 2, name: '阿森纳', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png', type: 'club', country: '英格兰', league: '英超', matches: 35, wins: 25, draws: 5, losses: 5, isFavorite: true },
      { id: 3, name: '利物浦', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/0/0c/Liverpool_FC.svg/1200px-Liverpool_FC.svg.png', type: 'club', country: '英格兰', league: '英超', matches: 35, wins: 22, draws: 8, losses: 5, isFavorite: false },
      { id: 4, name: '皇马', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png', type: 'club', country: '西班牙', league: '西甲', matches: 34, wins: 26, draws: 6, losses: 2, isFavorite: true },
      { id: 5, name: '巴萨', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/4/47/FC_Barcelona_%28crest%29.svg/1200px-FC_Barcelona_%28crest%29.svg.png', type: 'club', country: '西班牙', league: '西甲', matches: 34, wins: 24, draws: 7, losses: 3, isFavorite: false },
      { id: 6, name: '拜仁', logo: 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/FC_Bayern_M%C3%BCnchen_logo_%282017%29.svg/1200px-FC_Bayern_M%C3%BCnchen_logo_%282017%29.svg.png', type: 'club', country: '德国', league: '德甲', matches: 32, wins: 23, draws: 5, losses: 4, isFavorite: false },
      { id: 7, name: '多特蒙德', logo: 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Borussia_Dortmund_logo.svg/1200px-Borussia_Dortmund_logo.svg.png', type: 'club', country: '德国', league: '德甲', matches: 32, wins: 20, draws: 7, losses: 5, isFavorite: false },
      { id: 8, name: '尤文图斯', logo: 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Juventus_FC_2017_icon_%28black%29.svg/1200px-Juventus_FC_2017_icon_%28black%29.svg.png', type: 'club', country: '意大利', league: '意甲', matches: 34, wins: 18, draws: 12, losses: 4, isFavorite: false },
      { id: 9, name: '阿根廷', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/ca/Flag_of_Argentina.svg/1200px-Flag_of_Argentina.svg.png', type: 'national', country: '阿根廷', matches: 15, wins: 12, draws: 2, losses: 1, isFavorite: false },
      { id: 10, name: '法国', logo: 'https://upload.wikimedia.org/wikipedia/en/thumb/c/c3/Flag_of_France.svg/1200px-Flag_of_France.svg.png', type: 'national', country: '法国', matches: 14, wins: 10, draws: 3, losses: 1, isFavorite: false },
    ])

    const filteredTeams = computed(() => {
      return allTeams.value.filter(team => {
        if (searchQuery.value && !team.name.toLowerCase().includes(searchQuery.value.toLowerCase())) return false
        if (selectedType.value && team.type !== selectedType.value) return false
        if (selectedCountry.value && team.country !== selectedCountry.value) return false
        if (selectedLeague.value && team.league !== selectedLeague.value) return false
        return true
      })
    })

    const getPositionClass = (pos) => pos <= 4 ? 'champions' : pos <= 6 ? 'europa' : ''

    const handleSearch = () => {}

    const toggleFavorite = (team) => { team.isFavorite = !team.isFavorite }

    const goToTeam = (id) => console.log('Go to team:', id)

    const loadMore = () => { hasMore.value = false }

    return {
      searchQuery, selectedType, selectedCountry, selectedLeague, hasMore,
      hotTeams, allTeams, filteredTeams,
      getPositionClass, handleSearch, toggleFavorite, goToTeam, loadMore
    }
  }
}
</script>

<style scoped>
.teams-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 搜索区域 */
.search-section {
  display: flex;
  gap: 16px;
  align-items: center;
}

.search-box {
  position: relative;
  flex: 1;
  max-width: 400px;
}

.search-box .search-icon {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  color: #6b7280;
}

.search-box input {
  width: 100%;
  background: #151922;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 12px;
  padding: 14px 16px 14px 48px;
  font-size: 14px;
  color: white;
  outline: none;
}

.search-box input:focus { border-color: #10b981; }

.filters {
  display: flex;
  gap: 12px;
}

.filter-select {
  background: #151922;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 14px;
  color: white;
  outline: none;
  min-width: 120px;
}

/* 区块 */
.section {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.section-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-header h2 {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  display: flex;
  align-items: center;
  gap: 8px;
}

.count {
  font-size: 13px;
  color: #6b7280;
}

/* 热门球队 */
.hot-teams {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  padding: 16px;
}

.hot-team-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  background: #1c222f;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.hot-team-card:hover {
  transform: translateY(-2px);
  background: #242936;
}

.hot-team-card .team-logo {
  width: 56px;
  height: 56px;
  margin-bottom: 12px;
}

.hot-team-card .team-logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.hot-team-card .team-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.hot-team-card .team-meta {
  font-size: 11px;
  color: #6b7280;
}

.position {
  margin-top: 8px;
  padding: 3px 10px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255,255,255,0.05);
  color: #9ca3af;
}

.position.champions { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.position.europa { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }

/* 球队网格 */
.teams-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  padding: 20px;
}

.team-card {
  background: #1c222f;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.team-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px;
}

.team-logo-small {
  width: 48px;
  height: 48px;
}

.team-logo-small img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.favorite-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255,255,255,0.05);
  border: none;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.favorite-btn.active { color: #fbbf24; }

.card-body {
  padding: 0 16px 16px;
}

.team-card .team-name {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.team-card .team-meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 12px;
}

.team-badges {
  display: flex;
  gap: 8px;
}

.badge {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.badge.type { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.badge.type.national { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.badge.country { background: rgba(255,255,255,0.05); color: #9ca3af; }

.card-footer {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-top: 1px solid rgba(31, 41, 55, 0.5);
  padding: 12px 16px;
  background: rgba(0,0,0,0.2);
}

.stat-item {
  text-align: center;
}

.stat-item .stat-value {
  display: block;
  font-size: 16px;
  font-weight: 700;
  color: #e5e7eb;
}

.stat-item .stat-value.win { color: #10b981; }
.stat-item .stat-value.loss { color: #ef4444; }

.stat-item .stat-label {
  font-size: 10px;
  color: #6b7280;
}

/* 加载更多 */
.load-more {
  padding: 20px;
  text-align: center;
}

.load-more-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  color: #10b981;
  font-size: 14px;
  cursor: pointer;
}
</style>