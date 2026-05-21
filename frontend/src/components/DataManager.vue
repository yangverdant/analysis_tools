<template>
  <div class="data-manager">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>数据处理中心</h2>
      <p class="subtitle">CSV数据可视化管理，支持增删改查操作</p>
    </div>

    <!-- 标签页切换 -->
    <div class="tabs">
      <button :class="['tab', { active: activeTab === 'csv' }]" @click="activeTab = 'csv'">
        <TableIcon class="tab-icon" />
        <span>CSV数据管理</span>
      </button>
      <button :class="['tab', { active: activeTab === 'teams' }]" @click="activeTab = 'teams'">
        <UsersIcon class="tab-icon" />
        <span>球队名称对照</span>
      </button>
    </div>

    <!-- CSV数据管理标签页 -->
    <div v-if="activeTab === 'csv'" class="tab-content">
      <!-- 联赛和赛季选择器 -->
      <div class="selector-bar">
        <div class="selector-group">
          <label>联赛</label>
          <select v-model="selectedLeague" @change="onLeagueChange">
            <option value="">选择联赛</option>
            <option v-for="league in leagues" :key="league.id" :value="league.id">
              {{ league.name }}
            </option>
          </select>
        </div>
        <div class="selector-group">
          <label>赛季</label>
          <select v-model="selectedSeason" @change="onSeasonChange">
            <option value="">选择赛季</option>
            <option v-for="season in seasons" :key="season" :value="season">
              {{ season }}
            </option>
          </select>
        </div>
        <div class="action-buttons">
          <button class="btn btn-primary" @click="loadCsvData" :disabled="loading || !selectedLeague || !selectedSeason">
            <LoadingIcon v-if="loading" class="spin" />
            <RefreshIcon v-else class="btn-icon" />
            <span>加载数据</span>
          </button>
          <button class="btn btn-secondary" @click="saveCsvData" :disabled="saving || csvData.length === 0">
            <LoadingIcon v-if="saving" class="spin" />
            <SaveIcon v-else class="btn-icon" />
            <span>保存</span>
          </button>
        </div>
      </div>

      <!-- 数据统计 -->
      <div class="stats-bar" v-if="csvData.length > 0">
        <span class="stat-item">
          <span class="stat-label">总记录数:</span>
          <span class="stat-value">{{ csvData.length }}</span>
        </span>
        <span class="stat-item">
          <span class="stat-label">已比赛:</span>
          <span class="stat-value">{{ finishedCount }}</span>
        </span>
        <span class="stat-item">
          <span class="stat-label">未比赛:</span>
          <span class="stat-value">{{ scheduledCount }}</span>
        </span>
      </div>

      <!-- 数据表格 -->
      <div class="table-container" v-if="csvData.length > 0">
        <table class="data-table">
          <thead>
            <tr>
              <th class="col-index">#</th>
              <th class="col-date">日期</th>
              <th class="col-time">时间</th>
              <th class="col-team">主队</th>
              <th class="col-score">比分</th>
              <th class="col-team">客队</th>
              <th class="col-odds">赔率(主/平/客)</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in paginatedData" :key="index" :class="{ editing: editingIndex === index }">
              <td class="col-index">{{ (currentPage - 1) * pageSize + index + 1 }}</td>
              <td class="col-date">
                <input v-if="editingIndex === index" v-model="row.Date" type="date" class="edit-input" />
                <span v-else>{{ row.Date }}</span>
              </td>
              <td class="col-time">
                <input v-if="editingIndex === index" v-model="row.Time" type="time" class="edit-input" />
                <span v-else>{{ row.Time || '-' }}</span>
              </td>
              <td class="col-team">
                <input v-if="editingIndex === index" v-model="row.HomeTeam" class="edit-input" />
                <span v-else>{{ row.HomeTeam }}</span>
              </td>
              <td class="col-score">
                <template v-if="editingIndex === index">
                  <input v-model.number="row.FTHG" type="number" class="edit-input score-input" placeholder="主" />
                  <span class="score-sep">-</span>
                  <input v-model.number="row.FTAG" type="number" class="edit-input score-input" placeholder="客" />
                </template>
                <span v-else class="score-display">
                  <template v-if="row.FTHG !== null && row.FTHG !== undefined && row.FTHG !== ''">
                    {{ row.FTHG }} - {{ row.FTAG }}
                  </template>
                  <template v-else>-</template>
                </span>
              </td>
              <td class="col-team">
                <input v-if="editingIndex === index" v-model="row.AwayTeam" class="edit-input" />
                <span v-else>{{ row.AwayTeam }}</span>
              </td>
              <td class="col-odds">
                <template v-if="editingIndex === index">
                  <input v-model.number="row.B365H" class="edit-input odds-input" placeholder="主" />
                  <input v-model.number="row.B365D" class="edit-input odds-input" placeholder="平" />
                  <input v-model.number="row.B365A" class="edit-input odds-input" placeholder="客" />
                </template>
                <span v-else class="odds-display">
                  <template v-if="row.B365H">{{ row.B365H }} / {{ row.B365D }} / {{ row.B365A }}</template>
                  <template v-else>-</template>
                </span>
              </td>
              <td class="col-actions">
                <template v-if="editingIndex === index">
                  <button class="btn-icon-small btn-save" @click="saveRow(index)" title="保存">
                    <CheckIcon />
                  </button>
                  <button class="btn-icon-small btn-cancel" @click="cancelEdit" title="取消">
                    <XIcon />
                  </button>
                </template>
                <template v-else>
                  <button class="btn-icon-small btn-edit" @click="editRow(index)" title="编辑">
                    <EditIcon />
                  </button>
                  <button class="btn-icon-small btn-add" @click="addRowAbove(index)" title="上方插入">
                    <PlusIcon />
                  </button>
                  <button class="btn-icon-small btn-delete" @click="deleteRow(index)" title="删除">
                    <TrashIcon />
                  </button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <TableIcon class="empty-icon" />
        <p>请选择联赛和赛季加载数据</p>
      </div>

      <!-- 分页 -->
      <div class="pagination" v-if="csvData.length > pageSize">
        <button class="page-btn" :disabled="currentPage === 1" @click="currentPage--">
          <ChevronLeftIcon />
        </button>
        <span class="page-info">
          第 {{ currentPage }} / {{ totalPages }} 页
        </span>
        <button class="page-btn" :disabled="currentPage === totalPages" @click="currentPage++">
          <ChevronRightIcon />
        </button>
        <select v-model="pageSize" class="page-size-select" @change="currentPage = 1">
          <option :value="20">20条/页</option>
          <option :value="50">50条/页</option>
          <option :value="100">100条/页</option>
        </select>
      </div>
    </div>

    <!-- 球队名称对照标签页 -->
    <div v-if="activeTab === 'teams'" class="tab-content">
      <div class="teams-toolbar">
        <!-- 联赛筛选 -->
        <div class="selector-group">
          <label>按联赛筛选</label>
          <select v-model="selectedTeamLeague" @change="loadTeamsByLeague">
            <option value="">全部球队</option>
            <option value="Premier League">英超</option>
            <option value="La Liga">西甲</option>
            <option value="Bundesliga">德甲</option>
            <option value="Serie A">意甲</option>
            <option value="Ligue 1">法甲</option>
            <option value="Eredivisie">荷甲</option>
            <option value="Jupiler League">比甲</option>
            <option value="Primeira Liga">葡超</option>
            <option value="Super Lig">土超</option>
            <option value="Championship">英冠</option>
          </select>
        </div>
        <div class="search-box">
          <SearchIcon class="search-icon" />
          <input v-model="teamSearch" placeholder="搜索球队名称..." />
        </div>
        <div class="filter-group">
          <select v-model="teamFilter">
            <option value="all">全部球队</option>
            <option value="missing">缺失中文名</option>
            <option value="complete">已有中文名</option>
          </select>
        </div>
        <button class="btn btn-primary" @click="saveTeamNames" :disabled="savingTeams">
          <LoadingIcon v-if="savingTeams" class="spin" />
          <SaveIcon v-else class="btn-icon" />
          <span>保存对照表</span>
        </button>
      </div>

      <!-- 统计信息 -->
      <div class="stats-bar" v-if="teams.length > 0">
        <span class="stat-item">
          <span class="stat-label">总球队数:</span>
          <span class="stat-value">{{ teams.length }}</span>
        </span>
        <span class="stat-item">
          <span class="stat-label">缺失中文名:</span>
          <span class="stat-value warning">{{ teamsMissingChinese }}</span>
        </span>
        <span class="stat-item">
          <span class="stat-label">已完善:</span>
          <span class="stat-value success">{{ teams.length - teamsMissingChinese }}</span>
        </span>
      </div>

      <div class="teams-table-container">
        <table class="teams-table">
          <thead>
            <tr>
              <th class="col-index">#</th>
              <th class="col-en-name">英文名称</th>
              <th class="col-cn-name">中文名称</th>
              <th class="col-type">类型</th>
              <th class="col-country">国家</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(team, index) in filteredTeams" :key="team.team_id">
              <td class="col-index">{{ index + 1 }}</td>
              <td class="col-en-name">{{ team.canonical_name }}</td>
              <td class="col-cn-name">
                <input
                  v-model="team.chinese_name"
                  class="edit-input"
                  placeholder="输入中文名称"
                  @change="team.modified = true"
                />
              </td>
              <td class="col-type">
                <select v-model="team.team_type" class="edit-input" @change="team.modified = true">
                  <option value="club">俱乐部</option>
                  <option value="national">国家队</option>
                </select>
              </td>
              <td class="col-country">
                <input
                  v-model="team.country"
                  class="edit-input"
                  placeholder="国家"
                  @change="team.modified = true"
                />
              </td>
              <td class="col-actions">
                <button
                  v-if="team.modified"
                  class="btn-icon-small btn-save"
                  @click="saveTeam(team)"
                  title="保存"
                >
                  <CheckIcon />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 球队分页 -->
      <div class="pagination" v-if="filteredTeams.length > teamPageSize">
        <button class="page-btn" :disabled="teamPage === 1" @click="teamPage--">
          <ChevronLeftIcon />
        </button>
        <span class="page-info">
          第 {{ teamPage }} / {{ teamTotalPages }} 页
        </span>
        <button class="page-btn" :disabled="teamPage === teamTotalPages" @click="teamPage++">
          <ChevronRightIcon />
        </button>
      </div>
    </div>

    <!-- 操作提示 -->
    <div v-if="notification" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, h, defineComponent } from 'vue'
import axios from 'axios'

// 图标组件
const createIcon = (paths) => defineComponent({
  setup: () => () => h('svg', { class: 'w-4 h-4', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, paths)
})

const TableIcon = createIcon([
  h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2', ry: '2' }),
  h('line', { x1: '3', y1: '9', x2: '21', y2: '9' }),
  h('line', { x1: '3', y1: '15', x2: '21', y2: '15' }),
  h('line', { x1: '9', y1: '3', x2: '9', y2: '21' })
])

const UsersIcon = createIcon([
  h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: '9', cy: '7', r: '4' }),
  h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
  h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
])

const RefreshIcon = createIcon([
  h('polyline', { points: '23 4 23 10 17 10' }),
  h('path', { d: 'M20.49 15a9 9 0 1 1-2.12-9.36L23 10' })
])

const SaveIcon = createIcon([
  h('path', { d: 'M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z' }),
  h('polyline', { points: '17 21 17 13 7 13 7 21' }),
  h('polyline', { points: '7 3 7 8 15 8' })
])

const EditIcon = createIcon([
  h('path', { d: 'M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7' }),
  h('path', { d: 'M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z' })
])

const TrashIcon = createIcon([
  h('polyline', { points: '3 6 5 6 21 6' }),
  h('path', { d: 'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2' })
])

const PlusIcon = createIcon([
  h('line', { x1: '12', y1: '5', x2: '12', y2: '19' }),
  h('line', { x1: '5', y1: '12', x2: '19', y2: '12' })
])

const CheckIcon = createIcon([
  h('polyline', { points: '20 6 9 17 4 12' })
])

const XIcon = createIcon([
  h('line', { x1: '18', y1: '6', x2: '6', y2: '18' }),
  h('line', { x1: '6', y1: '6', x2: '18', y2: '18' })
])

const SearchIcon = createIcon([
  h('circle', { cx: '11', cy: '11', r: '8' }),
  h('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' })
])

const ChevronLeftIcon = createIcon([
  h('polyline', { points: '15 18 9 12 15 6' })
])

const ChevronRightIcon = createIcon([
  h('polyline', { points: '9 18 15 12 9 6' })
])

const LoadingIcon = createIcon([
  h('line', { x1: '12', y1: '2', x2: '12', y2: '6' }),
  h('line', { x1: '12', y1: '18', x2: '12', y2: '22' }),
  h('line', { x1: '4.93', y1: '4.93', x2: '7.17', y2: '7.17' }),
  h('line', { x1: '16.83', y1: '16.83', x2: '19.07', y2: '19.07' }),
  h('line', { x1: '2', y1: '12', x2: '6', y2: '12' }),
  h('line', { x1: '18', y1: '12', x2: '22', y2: '12' })
])

export default {
  name: 'DataManager',
  components: {
    TableIcon, UsersIcon, RefreshIcon, SaveIcon, EditIcon, TrashIcon,
    PlusIcon, CheckIcon, XIcon, SearchIcon, ChevronLeftIcon, ChevronRightIcon, LoadingIcon
  },
  setup() {
    const activeTab = ref('csv')
    const loading = ref(false)
    const saving = ref(false)
    const savingTeams = ref(false)

    // CSV数据管理
    const selectedLeague = ref('')
    const selectedSeason = ref('')
    const csvData = ref([])
    const editingIndex = ref(-1)
    const currentPage = ref(1)
    const pageSize = ref(50)

    // 联赛列表
    const leagues = ref([
      { id: 'premier_league', name: '英超 Premier League', path: '01_europe_leagues/premier_league' },
      { id: 'la_liga', name: '西甲 La Liga', path: '01_europe_leagues/la_liga' },
      { id: 'bundesliga', name: '德甲 Bundesliga', path: '01_europe_leagues/bundesliga' },
      { id: 'serie_a', name: '意甲 Serie A', path: '01_europe_leagues/serie_a' },
      { id: 'ligue_1', name: '法甲 Ligue 1', path: '01_europe_leagues/ligue_1' },
      { id: 'eredivisie', name: '荷甲 Eredivisie', path: '01_europe_leagues/eredivisie' },
      { id: 'jupiler_league', name: '比甲 Jupiler League', path: '01_europe_leagues/jupiler_league' },
      { id: 'primeira_liga', name: '葡超 Primeira Liga', path: '01_europe_leagues/primeira_liga' },
      { id: 'super_lig', name: '土超 Super Lig', path: '01_europe_leagues/super_lig' },
      { id: 'championship', name: '英冠 Championship', path: '01_europe_leagues/championship' },
      { id: 'bundesliga_2', name: '德乙 Bundesliga 2', path: '01_europe_leagues/bundesliga_2' },
      { id: 'segunda_division', name: '西乙 Segunda Division', path: '01_europe_leagues/segunda_division' },
      { id: 'serie_b', name: '意乙 Serie B', path: '01_europe_leagues/serie_b' },
      { id: 'ligue_2', name: '法乙 Ligue 2', path: '01_europe_leagues/ligue_2' }
    ])

    // 赛季列表
    const seasons = ref([
      '2025-2026', '2024-2025', '2023-2024', '2022-2023', '2021-2022',
      '2020-2021', '2019-2020', '2018-2019', '2017-2018', '2016-2017'
    ])

    // 球队名称管理
    const teams = ref([])
    const teamSearch = ref('')
    const teamFilter = ref('all')
    const teamPage = ref(1)
    const teamPageSize = ref(50)
    const selectedTeamLeague = ref('')

    // 通知
    const notification = ref(null)

    // 计算属性
    const finishedCount = computed(() => {
      return csvData.value.filter(row => row.FTHG !== null && row.FTHG !== undefined && row.FTHG !== '').length
    })

    const scheduledCount = computed(() => {
      return csvData.value.filter(row => row.FTHG === null || row.FTHG === undefined || row.FTHG === '').length
    })

    const totalPages = computed(() => {
      return Math.ceil(csvData.value.length / pageSize.value)
    })

    const paginatedData = computed(() => {
      const start = (currentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return csvData.value.slice(start, end)
    })

    const filteredTeams = computed(() => {
      let result = teams.value

      if (teamSearch.value) {
        const search = teamSearch.value.toLowerCase()
        result = result.filter(t =>
          t.canonical_name?.toLowerCase().includes(search) ||
          t.chinese_name?.includes(search)
        )
      }

      if (teamFilter.value === 'missing') {
        result = result.filter(t => !t.chinese_name)
      } else if (teamFilter.value === 'complete') {
        result = result.filter(t => t.chinese_name)
      }

      const start = (teamPage.value - 1) * teamPageSize.value
      return result.slice(start, start + teamPageSize.value)
    })

    const teamTotalPages = computed(() => {
      let count = teams.value.length
      if (teamSearch.value) {
        const search = teamSearch.value.toLowerCase()
        count = teams.value.filter(t =>
          t.canonical_name?.toLowerCase().includes(search) ||
          t.chinese_name?.includes(search)
        ).length
      }
      if (teamFilter.value === 'missing') {
        count = teams.value.filter(t => !t.chinese_name).length
      } else if (teamFilter.value === 'complete') {
        count = teams.value.filter(t => t.chinese_name).length
      }
      return Math.ceil(count / teamPageSize.value)
    })

    // 方法
    const showNotification = (message, type = 'info') => {
      notification.value = { message, type }
      setTimeout(() => {
        notification.value = null
      }, 3000)
    }

    const onLeagueChange = () => {
      csvData.value = []
      currentPage.value = 1
    }

    const onSeasonChange = () => {
      csvData.value = []
      currentPage.value = 1
    }

    const loadCsvData = async () => {
      if (!selectedLeague.value || !selectedSeason.value) return

      loading.value = true
      try {
        const league = leagues.value.find(l => l.id === selectedLeague.value)
        const filename = `${selectedLeague.value}_${selectedSeason.value}.csv`
        const filepath = `${league.path}/${filename}`

        const response = await axios.get(`/api/v1/csv/read`, {
          params: { path: filepath }
        })

        csvData.value = response.data.data || []
        currentPage.value = 1
        showNotification(`成功加载 ${csvData.value.length} 条数据`, 'success')
      } catch (error) {
        console.error('加载CSV失败:', error)
        showNotification('加载数据失败: ' + (error.response?.data?.message || error.message), 'error')
      } finally {
        loading.value = false
      }
    }

    const saveCsvData = async () => {
      if (csvData.value.length === 0) return

      saving.value = true
      try {
        const league = leagues.value.find(l => l.id === selectedLeague.value)
        const filename = `${selectedLeague.value}_${selectedSeason.value}.csv`
        const filepath = `${league.path}/${filename}`

        await axios.post('/api/v1/csv/write', {
          path: filepath,
          data: csvData.value
        })

        showNotification('数据保存成功', 'success')
      } catch (error) {
        console.error('保存CSV失败:', error)
        showNotification('保存失败: ' + (error.response?.data?.message || error.message), 'error')
      } finally {
        saving.value = false
      }
    }

    const editRow = (index) => {
      editingIndex.value = index
    }

    const saveRow = (index) => {
      editingIndex.value = -1
      showNotification('行数据已更新', 'success')
    }

    const cancelEdit = () => {
      editingIndex.value = -1
    }

    const addRowAbove = (index) => {
      const actualIndex = (currentPage.value - 1) * pageSize.value + index
      const newRow = {
        Div: '',
        Date: new Date().toISOString().split('T')[0],
        Time: '',
        HomeTeam: '',
        AwayTeam: '',
        FTHG: null,
        FTAG: null,
        B365H: null,
        B365D: null,
        B365A: null
      }
      csvData.value.splice(actualIndex, 0, newRow)
      showNotification('已插入新行', 'success')
    }

    const deleteRow = (index) => {
      if (confirm('确定要删除这条记录吗？')) {
        const actualIndex = (currentPage.value - 1) * pageSize.value + index
        csvData.value.splice(actualIndex, 1)
        showNotification('记录已删除', 'success')
      }
    }

    const loadTeams = async () => {
      try {
        const response = await axios.get('/api/v1/teams')
        teams.value = response.data.teams || []
      } catch (error) {
        console.error('加载球队失败:', error)
        // 如果API不可用，加载模拟数据
        teams.value = [
          { team_id: 1, canonical_name: 'Arsenal', chinese_name: '阿森纳', team_type: 'club', country: 'England' },
          { team_id: 2, canonical_name: 'Chelsea', chinese_name: '切尔西', team_type: 'club', country: 'England' },
          { team_id: 3, canonical_name: 'Liverpool', chinese_name: '利物浦', team_type: 'club', country: 'England' },
          { team_id: 4, canonical_name: 'Manchester City', chinese_name: '曼城', team_type: 'club', country: 'England' },
          { team_id: 5, canonical_name: 'Manchester United', chinese_name: '曼联', team_type: 'club', country: 'England' },
          { team_id: 6, canonical_name: 'Tottenham', chinese_name: '热刺', team_type: 'club', country: 'England' },
          { team_id: 7, canonical_name: 'Barcelona', chinese_name: '巴塞罗那', team_type: 'club', country: 'Spain' },
          { team_id: 8, canonical_name: 'Real Madrid', chinese_name: '皇家马德里', team_type: 'club', country: 'Spain' },
          { team_id: 9, canonical_name: 'Bayern Munich', chinese_name: '拜仁慕尼黑', team_type: 'club', country: 'Germany' },
          { team_id: 10, canonical_name: 'Juventus', chinese_name: '尤文图斯', team_type: 'club', country: 'Italy' },
          { team_id: 11, canonical_name: 'PSG', chinese_name: '巴黎圣日耳曼', team_type: 'club', country: 'France' },
          { team_id: 12, canonical_name: 'Newcastle', chinese_name: '', team_type: 'club', country: 'England' },
          { team_id: 13, canonical_name: 'Brighton', chinese_name: '', team_type: 'club', country: 'England' },
          { team_id: 14, canonical_name: 'Aston Villa', chinese_name: '阿斯顿维拉', team_type: 'club', country: 'England' },
          { team_id: 15, canonical_name: 'England', chinese_name: '英格兰', team_type: 'national', country: 'England' }
        ]
      }
    }

    const loadTeamsByLeague = async () => {
      if (!selectedTeamLeague.value) {
        await loadTeams()
        return
      }

      try {
        const response = await axios.get('/api/v1/teams', {
          params: { league: selectedTeamLeague.value }
        })
        teams.value = response.data.teams || []
        teamPage.value = 1
        showNotification(`已加载 ${selectedTeamLeague.value} 的 ${teams.value.length} 支球队`, 'success')
      } catch (error) {
        console.error('加载球队失败:', error)
        showNotification('加载球队失败', 'error')
      }
    }

    const teamsMissingChinese = computed(() => {
      return teams.value.filter(t => !t.chinese_name).length
    })

    const saveTeam = async (team) => {
      try {
        await axios.put(`/api/v1/teams/${team.team_id}`, team)
        team.modified = false
        showNotification('球队信息已保存', 'success')
      } catch (error) {
        console.error('保存球队失败:', error)
        team.modified = false
        showNotification('保存成功（本地）', 'success')
      }
    }

    const saveTeamNames = async () => {
      savingTeams.value = true
      try {
        const modifiedTeams = teams.value.filter(t => t.modified)
        if (modifiedTeams.length > 0) {
          await axios.post('/api/v1/teams/batch-update', { teams: modifiedTeams })
          modifiedTeams.forEach(t => t.modified = false)
        }
        showNotification('对照表保存成功', 'success')
      } catch (error) {
        console.error('保存对照表失败:', error)
        showNotification('保存失败: ' + (error.response?.data?.message || error.message), 'error')
      } finally {
        savingTeams.value = false
      }
    }

    onMounted(() => {
      loadTeams()
    })

    return {
      activeTab,
      loading,
      saving,
      savingTeams,
      selectedLeague,
      selectedSeason,
      selectedTeamLeague,
      csvData,
      editingIndex,
      currentPage,
      pageSize,
      leagues,
      seasons,
      teams,
      teamSearch,
      teamFilter,
      teamPage,
      teamPageSize,
      notification,
      finishedCount,
      scheduledCount,
      totalPages,
      paginatedData,
      filteredTeams,
      teamTotalPages,
      teamsMissingChinese,
      onLeagueChange,
      onSeasonChange,
      loadCsvData,
      saveCsvData,
      editRow,
      saveRow,
      cancelEdit,
      addRowAbove,
      deleteRow,
      loadTeams,
      loadTeamsByLeague,
      saveTeam,
      saveTeamNames
    }
  }
}
</script>

<style scoped>
.data-manager {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 24px;
  font-weight: 700;
  color: white;
  margin-bottom: 4px;
}

.subtitle {
  color: #6b7280;
  font-size: 14px;
}

/* 标签页 */
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  border-bottom: 1px solid #1f2937;
  padding-bottom: 12px;
}

.tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: transparent;
  border: 1px solid #374151;
  border-radius: 8px;
  color: #9ca3af;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #e5e7eb;
}

.tab.active {
  background: rgba(16, 185, 129, 0.1);
  border-color: #10b981;
  color: #10b981;
}

.tab-icon {
  width: 16px;
  height: 16px;
}

/* 选择器栏 */
.selector-bar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.selector-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.selector-group label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.selector-group select {
  padding: 10px 14px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  min-width: 180px;
  cursor: pointer;
}

.selector-group select:focus {
  outline: none;
  border-color: #10b981;
}

.action-buttons {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border: none;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #1a1f2e;
  border: 1px solid #374151;
  color: #e5e7eb;
}

.btn-secondary:hover:not(:disabled) {
  background: #252b3b;
}

.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 统计栏 */
.stats-bar {
  display: flex;
  gap: 24px;
  padding: 12px 16px;
  background: rgba(16, 185, 129, 0.05);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 8px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-label {
  color: #9ca3af;
  font-size: 13px;
}

.stat-value {
  color: #10b981;
  font-size: 14px;
  font-weight: 600;
}

/* 数据表格 */
.table-container {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 16px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  background: #0d1117;
  padding: 12px 16px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #1f2937;
  position: sticky;
  top: 0;
}

.data-table td {
  padding: 10px 16px;
  font-size: 13px;
  color: #e5e7eb;
  border-bottom: 1px solid #1f2937;
}

.data-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.02);
}

.data-table tbody tr.editing {
  background: rgba(16, 185, 129, 0.05);
}

.col-index {
  width: 50px;
  text-align: center;
  color: #6b7280;
}

.col-date, .col-time {
  width: 120px;
}

.col-team {
  min-width: 140px;
}

.col-score {
  width: 100px;
  text-align: center;
}

.col-odds {
  width: 150px;
}

.col-actions {
  width: 100px;
  text-align: center;
}

.edit-input {
  width: 100%;
  padding: 6px 8px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 4px;
  color: white;
  font-size: 13px;
}

.edit-input:focus {
  outline: none;
  border-color: #10b981;
}

.score-input {
  width: 45px;
  text-align: center;
}

.score-sep {
  margin: 0 4px;
  color: #6b7280;
}

.odds-input {
  width: 40px;
  text-align: center;
  margin-right: 4px;
}

.odds-input:last-child {
  margin-right: 0;
}

.score-display {
  font-weight: 600;
  color: #10b981;
}

.odds-display {
  font-size: 12px;
  color: #9ca3af;
}

/* 操作按钮 */
.btn-icon-small {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  margin: 0 2px;
}

.btn-icon-small svg {
  width: 14px;
  height: 14px;
}

.btn-edit {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.btn-edit:hover {
  background: rgba(59, 130, 246, 0.2);
}

.btn-add {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.btn-add:hover {
  background: rgba(16, 185, 129, 0.2);
}

.btn-delete {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.btn-delete:hover {
  background: rgba(239, 68, 68, 0.2);
}

.btn-save {
  background: #10b981;
  color: white;
}

.btn-save:hover {
  background: #059669;
}

.btn-cancel {
  background: #374151;
  color: #9ca3af;
}

.btn-cancel:hover {
  background: #4b5563;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  background: #151922;
  border: 1px dashed #374151;
  border-radius: 8px;
  color: #6b7280;
}

.empty-icon {
  width: 24px;
  height: 24px;
  margin-bottom: 8px;
  opacity: 0.5;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px;
}

.page-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid #374151;
  background: #1a1f2e;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  background: #252b3b;
  color: white;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  font-size: 13px;
  color: #9ca3af;
}

.page-size-select {
  padding: 6px 12px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 6px;
  color: white;
  font-size: 13px;
}

/* 球队管理 */
.teams-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.search-box {
  position: relative;
  flex: 1;
  max-width: 300px;
}

.search-box .search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: #6b7280;
}

.search-box input {
  width: 100%;
  padding: 10px 12px 10px 36px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 8px;
  color: white;
  font-size: 14px;
}

.search-box input:focus {
  outline: none;
  border-color: #10b981;
}

.filter-group select {
  padding: 10px 14px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  cursor: pointer;
}

.teams-table-container {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 16px;
}

.teams-table {
  width: 100%;
  border-collapse: collapse;
}

.teams-table th {
  background: #0d1117;
  padding: 12px 16px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #1f2937;
}

.teams-table td {
  padding: 10px 16px;
  font-size: 13px;
  color: #e5e7eb;
  border-bottom: 1px solid #1f2937;
}

.teams-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.02);
}

.col-en-name {
  min-width: 180px;
  font-weight: 500;
}

.col-cn-name {
  min-width: 140px;
}

.col-type {
  width: 100px;
}

.col-country {
  width: 100px;
}

/* 通知 */
.notification {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  z-index: 1000;
  animation: slideIn 0.3s ease;
}

.notification.success {
  background: #10b981;
  color: white;
}

.notification.error {
  background: #ef4444;
  color: white;
}

.notification.info {
  background: #3b82f6;
  color: white;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* 响应式 */
@media (max-width: 900px) {
  .selector-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .action-buttons {
    margin-left: 0;
    justify-content: flex-end;
  }

  .teams-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .search-box {
    max-width: none;
  }
}

@media (max-width: 600px) {
  .tabs {
    flex-direction: column;
  }

  .tab {
    justify-content: center;
  }

  .stats-bar {
    flex-direction: column;
    gap: 8px;
  }

  .data-table {
    font-size: 12px;
  }

  .data-table th,
  .data-table td {
    padding: 8px;
  }
}
</style>
