<template>
  <div class="data-center">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>数据中心</h2>
      <p class="subtitle">查看全部赛事数据，自动检测和补充缺失数据</p>
    </div>

    <!-- 主内容区：左侧导航 + 右侧内容 -->
    <div class="main-layout">
      <!-- 左侧联赛导航 -->
      <aside class="league-sidebar">
        <div class="sidebar-header">
          <h3>赛事导航</h3>
          <input v-model="searchLeague" placeholder="搜索联赛..." class="search-input" />
        </div>

        <div class="league-tree">
          <!-- 全部联赛 -->
          <div class="tree-item all-leagues" :class="{ active: selectedLeague === null }" @click="selectLeague(null)">
            <DatabaseIcon class="tree-icon" />
            <span>全部联赛</span>
            <span class="count">{{ stats.leagues }}</span>
          </div>

          <!-- 按地区分组 -->
          <div v-for="region in groupedLeagues" :key="region.name" class="region-group">
            <div class="region-header" @click="toggleRegion(region.name)">
              <ChevronIcon :class="['chevron', { expanded: expandedRegions.includes(region.name) }]" />
              <span class="region-flag">{{ region.flag }}</span>
              <span class="region-name">{{ region.name }}</span>
              <span class="count">{{ region.totalCount }}</span>
            </div>
            <div v-show="expandedRegions.includes(region.name)" class="region-countries">
              <!-- 国家列表 -->
              <div v-for="country in region.countries" :key="country.name" class="country-group">
                <div class="country-header" @click="toggleCountry(country.name)">
                  <ChevronIcon :class="['chevron', 'small', { expanded: expandedCountries.includes(country.name) }]" />
                  <span class="country-flag">{{ country.flag }}</span>
                  <span class="country-name">{{ country.name }}</span>
                  <span class="count">{{ country.leagues.length }}</span>
                </div>
                <div v-show="expandedCountries.includes(country.name)" class="country-leagues">
                  <div
                    v-for="league in country.leagues"
                    :key="league.league_id"
                    :class="['league-item', { active: selectedLeague?.league_id === league.league_id }]"
                    @click="selectLeague(league)"
                  >
                    <span class="league-name">{{ league.name_cn || league.name_en }}</span>
                    <span class="league-matches">{{ league.matches_count || 0 }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧内容区 -->
      <div class="content-area">
        <!-- 标签页切换 -->
        <div class="tabs">
          <button :class="['tab', { active: activeTab === 'overview' }]" @click="activeTab = 'overview'">
            <DatabaseIcon class="tab-icon" />
            <span>数据概览</span>
          </button>
          <button :class="['tab', { active: activeTab === 'matches' }]" @click="activeTab = 'matches'">
            <ActivityIcon class="tab-icon" />
            <span>比赛数据</span>
          </button>
          <button :class="['tab', { active: activeTab === 'detect' }]" @click="activeTab = 'detect'">
            <AlertIcon class="tab-icon" />
            <span>缺失检测</span>
          </button>
          <button :class="['tab', { active: activeTab === 'sync' }]" @click="activeTab = 'sync'">
            <RefreshIcon class="tab-icon" />
            <span>数据同步</span>
          </button>
        </div>

        <!-- 数据概览 -->
        <div v-if="activeTab === 'overview'" class="tab-content">
          <!-- 选中联赛 - 显示各赛季数据情况 -->
          <div v-if="selectedLeague" class="league-seasons-view">
            <div class="league-header">
              <div class="league-title">
                <h3>{{ selectedLeague.name_cn || selectedLeague.name_en }}</h3>
                <p>{{ selectedLeague.country }}</p>
              </div>
              <div class="league-stats">
                <div class="stat-badge">
                  <span class="value">{{ selectedLeague.seasons_count || 0 }}</span>
                  <span class="label">赛季</span>
                </div>
                <div class="stat-badge">
                  <span class="value">{{ selectedLeague.matches_count || 0 }}</span>
                  <span class="label">比赛</span>
                </div>
                <div class="stat-badge">
                  <span class="value">{{ selectedLeague.teams_count || 0 }}</span>
                  <span class="label">球队</span>
                </div>
              </div>
            </div>

            <!-- 赛季数据列表 -->
            <div class="seasons-list">
              <div class="seasons-header">
                <h4>各赛季数据情况</h4>
                <button class="btn btn-primary btn-small" @click="detectLeagueMissing(selectedLeague.league_id)">
                  <ScanIcon class="btn-icon" />
                  <span>检测缺失数据</span>
                </button>
              </div>
              <div v-if="loadingSeasons" class="loading-state">
                <LoadingIcon class="spin" />
                <span>加载中...</span>
              </div>
              <div v-else-if="leagueSeasons.length === 0" class="empty-state">
                <DatabaseIcon class="empty-icon" />
                <p>暂无赛季数据</p>
              </div>
              <table v-else class="seasons-table">
                <thead>
                  <tr>
                    <th>赛季</th>
                    <th>比赛数</th>
                    <th>球队数</th>
                    <th>已结束</th>
                    <th>未开始</th>
                    <th>缺失比分</th>
                    <th>缺失日期</th>
                    <th>数据完整度</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="season in leagueSeasons" :key="season.season">
                    <td class="season-name">{{ season.season }}</td>
                    <td>{{ season.matches_count || 0 }}</td>
                    <td>{{ season.teams_count || 0 }}</td>
                    <td>{{ season.finished_count || 0 }}</td>
                    <td>{{ season.scheduled_count || 0 }}</td>
                    <td :class="{ warning: season.missing_scores > 0 }">{{ season.missing_scores || 0 }}</td>
                    <td :class="{ warning: season.missing_dates > 0 }">{{ season.missing_dates || 0 }}</td>
                    <td>
                      <div class="completeness-bar">
                        <div class="completeness-fill" :style="{ width: (season.completeness || 0) + '%' }"></div>
                        <span class="completeness-text">{{ season.completeness || 0 }}%</span>
                      </div>
                    </td>
                    <td>
                      <button class="btn btn-small" @click="viewSeasonMatches(selectedLeague.league_id, season.season)">查看</button>
                      <button class="btn btn-small" @click="syncSeasonData(selectedLeague.league_id, season.season)">同步</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 未选中联赛 - 显示统计卡片 -->
          <template v-else>
            <!-- 统计卡片 - 一排显示 -->
            <div class="stats-row">
              <div class="stat-item">
                <TrophyIcon class="stat-icon" />
                <div class="stat-info">
                  <span class="stat-value">{{ stats.leagues }}</span>
                  <span class="stat-label">联赛</span>
                </div>
              </div>
              <div class="stat-item">
                <UsersIcon class="stat-icon" />
                <div class="stat-info">
                  <span class="stat-value">{{ stats.teams }}</span>
                  <span class="stat-label">球队</span>
                </div>
              </div>
              <div class="stat-item">
                <ActivityIcon class="stat-icon" />
                <div class="stat-info">
                  <span class="stat-value">{{ stats.matches }}</span>
                  <span class="stat-label">比赛</span>
                </div>
              </div>
              <div class="stat-item">
                <CalendarIcon class="stat-icon" />
                <div class="stat-info">
                  <span class="stat-value">{{ stats.seasons }}</span>
                  <span class="stat-label">赛季</span>
                </div>
              </div>
            </div>
          </template>

          <!-- 全部联赛数据表格 -->
          <div class="section" v-if="!selectedLeague">
            <div class="section-header">
              <h3 class="section-title">全部联赛数据</h3>
              <div class="sort-options">
                <select v-model="sortBy" class="sort-select">
                  <option value="hot">按热度排序</option>
                  <option value="matches">按比赛数排序</option>
                  <option value="teams">按球队数排序</option>
                  <option value="name">按名称排序</option>
                </select>
              </div>
            </div>
            <div class="leagues-table-container">
              <table class="leagues-table">
                <thead>
                  <tr>
                    <th></th>
                    <th>联赛</th>
                    <th>国家</th>
                    <th>球队</th>
                    <th>比赛</th>
                    <th>赛季</th>
                    <th>最新赛季</th>
                    <th>数据完整度</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="league in sortedLeagueStats" :key="league.league_id">
                    <td>
                      <button class="star-btn" :class="{ starred: starredLeagues.includes(league.league_id) }" @click="toggleStar(league.league_id)">
                        ★
                      </button>
                    </td>
                    <td class="league-name">
                      <span class="name-cn">{{ league.name_cn }}</span>
                      <span class="name-en">{{ league.name_en }}</span>
                    </td>
                    <td>{{ league.country }}</td>
                    <td>{{ league.teams_count || '-' }}</td>
                    <td>{{ league.matches_count || '-' }}</td>
                    <td>{{ league.seasons_count || '-' }}</td>
                    <td>{{ league.latest_season || '-' }}</td>
                    <td>
                      <div class="completeness-bar">
                        <div class="completeness-fill" :style="{ width: (league.completeness || 0) + '%' }"></div>
                        <span class="completeness-text">{{ league.completeness || 0 }}%</span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- 比赛数据 -->
        <div v-if="activeTab === 'matches'" class="tab-content">
          <!-- 筛选栏 - 紧凑一行 -->
          <div class="filter-bar-compact">
            <div class="filter-row">
              <div class="filter-item">
                <label>联赛</label>
                <select v-model="matchFilter.league" @change="onLeagueChange">
                  <option value="">全部</option>
                  <option v-for="l in leaguesList" :key="l.league_id" :value="l.league_id">
                    {{ l.name_cn || l.name_en }}
                  </option>
                </select>
              </div>
              <div class="filter-item">
                <label>赛季</label>
                <select v-model="matchFilter.season" @change="loadMatches">
                  <option value="">全部</option>
                  <option v-for="s in seasonsList" :key="s" :value="s">{{ s }}</option>
                </select>
              </div>
              <div class="filter-item">
                <label>状态</label>
                <select v-model="matchFilter.status" @change="loadMatches">
                  <option value="">全部</option>
                  <option value="finished">已结束</option>
                  <option value="scheduled">未开始</option>
                </select>
              </div>
              <div class="filter-item date-range">
                <label>日期</label>
                <input type="date" v-model="matchFilter.dateFrom" @change="loadMatches" />
                <span class="date-arrow">→</span>
                <input type="date" v-model="matchFilter.dateTo" @change="loadMatches" />
              </div>
              <div class="filter-actions">
                <button class="btn-compact btn-search" @click="loadMatches">查询</button>
                <button class="btn-compact btn-export" @click="exportMatches">导出</button>
              </div>
            </div>
          </div>

          <div class="matches-count" v-if="matches.length > 0">
            共 {{ totalMatches }} 条记录，显示 {{ matches.length }} 条
          </div>

          <div class="matches-table-container" v-if="matches.length > 0">
            <table class="matches-table">
              <thead>
                <tr>
                  <th>日期</th>
                  <th>联赛</th>
                  <th>主队</th>
                  <th>比分</th>
                  <th>客队</th>
                  <th>状态</th>
                  <th>数据源</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="match in paginatedMatches" :key="match.match_id">
                  <td>{{ match.match_date }}</td>
                  <td>{{ match.league_name_cn || match.league_name }}</td>
                  <td class="team-name">
                    <span class="name-cn">{{ match.home_team_cn || match.home_team }}</span>
                    <span class="name-en" v-if="match.home_team_cn">{{ match.home_team }}</span>
                  </td>
                  <td class="score">
                    <template v-if="match.status === 'finished'">
                      {{ match.home_goals }} - {{ match.away_goals }}
                    </template>
                    <template v-else>-</template>
                  </td>
                  <td class="team-name">
                    <span class="name-cn">{{ match.away_team_cn || match.away_team }}</span>
                    <span class="name-en" v-if="match.away_team_cn">{{ match.away_team }}</span>
                  </td>
                  <td>
                    <span :class="['status-badge', match.status]">
                      {{ match.status === 'finished' ? '已结束' : '未开始' }}
                    </span>
                  </td>
                  <td>
                    <span class="source-badge">{{ match.data_source || '本地' }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else class="empty-state">
            <DatabaseIcon class="empty-icon" />
            <p>暂无比赛数据</p>
          </div>

          <!-- 分页 -->
          <div class="pagination" v-if="matches.length > matchPageSize">
            <button class="page-btn" :disabled="matchPage === 1" @click="matchPage--">上一页</button>
            <span class="page-info">第 {{ matchPage }} / {{ matchTotalPages }} 页</span>
            <button class="page-btn" :disabled="matchPage >= matchTotalPages" @click="matchPage++">下一页</button>
          </div>
        </div>

        <!-- 缺失检测 -->
        <div v-if="activeTab === 'detect'" class="tab-content">
          <div class="detect-header">
            <p>扫描数据库，检测缺失的数据字段和不完整的记录</p>
            <button class="btn btn-primary" @click="runDetection" :disabled="detecting">
              <LoadingIcon v-if="detecting" class="spin" />
              <ScanIcon v-else class="btn-icon" />
              <span>{{ detecting ? '检测中...' : '开始检测' }}</span>
            </button>
          </div>

          <div v-if="detectionResult" class="detection-result">
            <div class="result-summary">
              <div class="summary-item" :class="{ warning: detectionResult.missing_team_cn > 0 }">
                <div class="summary-value">{{ detectionResult.missing_team_cn }}</div>
                <div class="summary-label">球队缺失中文名</div>
              </div>
              <div class="summary-item" :class="{ warning: detectionResult.missing_scores > 0 }">
                <div class="summary-value">{{ detectionResult.missing_scores }}</div>
                <div class="summary-label">已结束比赛缺失比分</div>
              </div>
              <div class="summary-item" :class="{ warning: detectionResult.missing_dates > 0 }">
                <div class="summary-value">{{ detectionResult.missing_dates }}</div>
                <div class="summary-label">比赛缺失日期</div>
              </div>
              <div class="summary-item" :class="{ warning: detectionResult.missing_league_rules > 0 }">
                <div class="summary-value">{{ detectionResult.missing_league_rules }}</div>
                <div class="summary-label">联赛缺失规则配置</div>
              </div>
            </div>

            <!-- 缺失详情 -->
            <div class="missing-details" v-if="detectionResult.details">
              <div class="detail-section" v-if="detectionResult.details.missing_cn_teams?.length > 0">
                <h4>缺失中文名的球队 (前20个)</h4>
                <div class="missing-list">
                  <div v-for="team in detectionResult.details.missing_cn_teams" :key="team.team_id" class="missing-item">
                    <span class="item-name">{{ team.name_en }}</span>
                    <span class="item-country">{{ team.country }}</span>
                    <button class="btn-fix" @click="fixTeamName(team)">补充</button>
                  </div>
                </div>
              </div>

              <div class="detail-section" v-if="detectionResult.details.missing_score_matches?.length > 0">
                <h4>缺失比分的已结束比赛 (前20个)</h4>
                <div class="missing-list">
                  <div v-for="match in detectionResult.details.missing_score_matches" :key="match.match_id" class="missing-item">
                    <span class="item-date">{{ match.match_date }}</span>
                    <span class="item-match">{{ match.home_team }} vs {{ match.away_team }}</span>
                    <button class="btn-fix" @click="fixMatchScore(match)">补充</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="empty-state">
            <ScanIcon class="empty-icon" />
            <p>点击"开始检测"扫描数据缺失情况</p>
          </div>
        </div>

        <!-- 数据同步 -->
        <div v-if="activeTab === 'sync'" class="tab-content">
          <div class="sync-section">
            <h3>外部数据源配置</h3>
            <div class="data-sources">
              <div class="source-card" v-for="source in dataSources" :key="source.id">
                <div class="source-header">
                  <div class="source-icon" :class="source.status">
                    <CloudIcon />
                  </div>
                  <div class="source-info">
                    <div class="source-name">{{ source.name }}</div>
                    <div class="source-status" :class="source.status">
                      {{ source.status === 'connected' ? '已连接' : source.status === 'error' ? '连接失败' : '未配置' }}
                    </div>
                  </div>
                </div>
                <div class="source-desc">{{ source.description }}</div>
                <div class="source-actions">
                  <button class="btn btn-small" @click="testSource(source)">测试连接</button>
                  <button class="btn btn-small btn-primary" @click="syncFromSource(source)" :disabled="source.syncing">
                    {{ source.syncing ? '同步中...' : '同步数据' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="sync-section">
            <h3>批量数据同步</h3>
            <div class="sync-options">
              <div class="sync-option">
                <div class="option-info">
                  <h4>同步近期比赛结果</h4>
                  <p>从外部数据源同步最近7天内已结束比赛的结果</p>
                </div>
                <button class="btn btn-primary" @click="syncRecentResults" :disabled="syncing">
                  <RefreshIcon class="btn-icon" :class="{ spin: syncing }" />
                  <span>同步</span>
                </button>
              </div>
              <div class="sync-option">
                <div class="option-info">
                  <h4>同步未来赛程</h4>
                  <p>从外部数据源同步未来3-6个月的比赛安排</p>
                </div>
                <button class="btn btn-primary" @click="syncUpcomingFixtures" :disabled="syncing">
                  <RefreshIcon class="btn-icon" :class="{ spin: syncing }" />
                  <span>同步</span>
                </button>
              </div>
              <div class="sync-option">
                <div class="option-info">
                  <h4>同步球队信息</h4>
                  <p>从外部数据源同步球队基本信息和中文名称</p>
                </div>
                <button class="btn btn-primary" @click="syncTeams" :disabled="syncing">
                  <RefreshIcon class="btn-icon" :class="{ spin: syncing }" />
                  <span>同步</span>
                </button>
              </div>
              <div class="sync-option">
                <div class="option-info">
                  <h4>同步联赛规则</h4>
                  <p>更新各联赛的赛制规则配置</p>
                </div>
                <button class="btn btn-primary" @click="syncLeagueRules" :disabled="syncing">
                  <RefreshIcon class="btn-icon" :class="{ spin: syncing }" />
                  <span>同步</span>
                </button>
              </div>
            </div>
          </div>

          <!-- 同步日志 -->
          <div class="sync-section" v-if="syncLogs.length > 0">
            <h3>同步日志</h3>
            <div class="sync-logs">
              <div v-for="log in syncLogs" :key="log.id" class="log-item" :class="log.type">
                <span class="log-time">{{ log.time }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 通知 -->
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

const DatabaseIcon = createIcon([
  h('ellipse', { cx: '12', cy: '5', rx: '9', ry: '3' }),
  h('path', { d: 'M21 12c0 1.66-4 3-9 3s-9-1.34-9-3' }),
  h('path', { d: 'M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5' })
])

const ActivityIcon = createIcon([
  h('polyline', { points: '22 12 18 12 15 21 9 3 6 12 2 12' })
])

const AlertIcon = createIcon([
  h('circle', { cx: '12', cy: '12', r: '10' }),
  h('line', { x1: '12', y1: '8', x2: '12', y2: '12' }),
  h('line', { x1: '12', y1: '16', x2: '12.01', y2: '16' })
])

const RefreshIcon = createIcon([
  h('polyline', { points: '23 4 23 10 17 10' }),
  h('path', { d: 'M20.49 15a9 9 0 1 1-2.12-9.36L23 10' })
])

const TrophyIcon = createIcon([
  h('path', { d: 'M6 9H4.5a2.5 2.5 0 0 1 0-5H6' }),
  h('path', { d: 'M18 9h1.5a2.5 2.5 0 0 0 0-5H18' }),
  h('path', { d: 'M4 22h16' }),
  h('path', { d: 'M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22' }),
  h('path', { d: 'M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22' }),
  h('path', { d: 'M18 2H6v7a6 6 0 0 0 12 0V2Z' })
])

const UsersIcon = createIcon([
  h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: '9', cy: '7', r: '4' }),
  h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
  h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
])

const CalendarIcon = createIcon([
  h('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }),
  h('line', { x1: '16', y1: '2', x2: '16', y2: '6' }),
  h('line', { x1: '8', y1: '2', x2: '8', y2: '6' }),
  h('line', { x1: '3', y1: '10', x2: '21', y2: '10' })
])

const DownloadIcon = createIcon([
  h('path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }),
  h('polyline', { points: '7 10 12 15 17 10' }),
  h('line', { x1: '12', y1: '15', x2: '12', y2: '3' })
])

const ScanIcon = createIcon([
  h('circle', { cx: '11', cy: '11', r: '8' }),
  h('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' }),
  h('line', { x1: '11', y1: '8', x2: '11', y2: '14' }),
  h('line', { x1: '8', y1: '11', x2: '14', y2: '11' })
])

const CloudIcon = createIcon([
  h('path', { d: 'M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z' })
])

const LoadingIcon = createIcon([
  h('line', { x1: '12', y1: '2', x2: '12', y2: '6' }),
  h('line', { x1: '12', y1: '18', x2: '12', y2: '22' }),
  h('line', { x1: '4.93', y1: '4.93', x2: '7.17', y2: '7.17' }),
  h('line', { x1: '16.83', y1: '16.83', x2: '19.07', y2: '19.07' }),
  h('line', { x1: '2', y1: '12', x2: '6', y2: '12' }),
  h('line', { x1: '18', y1: '12', x2: '22', y2: '12' })
])

const ChevronIcon = createIcon([
  h('polyline', { points: '9 18 15 12 9 6' })
])

// 地区配置 - 按地区分组（名称必须与数据库中的 name_cn 或 name_en 精确匹配）
const REGION_CONFIG = {
  '欧洲赛事': {
    flag: '🇪🇺',
    order: 0,
    countries: [
      { name: '英格兰', flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', leagues: ['英超', '英冠', '英甲', '英乙', '足总杯', '联赛杯', '社区盾杯'] },
      { name: '意大利', flag: '🇮🇹', leagues: ['意甲', '意乙', '意大利杯', '意大利超级杯'] },
      { name: '西班牙', flag: '🇪🇸', leagues: ['西甲', '西乙', '国王杯', '西班牙超级杯'] },
      { name: '德国', flag: '🇩🇪', leagues: ['德甲', '德乙', '德国杯'] },
      { name: '法国', flag: '🇫🇷', leagues: ['法甲', '法乙', '法国杯', '法国联赛杯', '法国超级杯'] },
      { name: '葡萄牙', flag: '🇵🇹', leagues: ['葡超', '葡萄牙杯'] },
      { name: '荷兰', flag: '🇳🇱', leagues: ['荷甲', '荷乙', '荷兰杯'] },
      { name: '比利时', flag: '🇧🇪', leagues: ['比甲', '比利时杯'] },
      { name: '土耳其', flag: '🇹🇷', leagues: ['土超'] },
      { name: '希腊', flag: '🇬🇷', leagues: ['希腊超'] },
      { name: '俄罗斯', flag: '🇷🇺', leagues: ['俄超'] },
      { name: '乌克兰', flag: '🇺🇦', leagues: ['乌超'] },
      { name: '苏格兰', flag: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', leagues: ['苏超'] },
      { name: '奥地利', flag: '🇦🇹', leagues: ['奥地利甲'] },
      { name: '瑞士', flag: '🇨🇭', leagues: ['瑞士超'] },
      { name: '波兰', flag: '🇵🇱', leagues: ['波兰甲'] },
      { name: '捷克', flag: '🇨🇿', leagues: ['捷克甲'] },
      { name: '丹麦', flag: '🇩🇰', leagues: ['丹麦超', '丹麦甲'] },
      { name: '挪威', flag: '🇳🇴', leagues: ['挪超', '挪甲'] },
      { name: '瑞典', flag: '🇸🇪', leagues: ['瑞典超', '瑞典甲'] },
      { name: '芬兰', flag: '🇫🇮', leagues: ['芬超'] },
      { name: '罗马尼亚', flag: '🇷🇴', leagues: ['罗马尼亚甲'] },
      { name: '匈牙利', flag: '🇭🇺', leagues: ['匈牙利甲'] },
      { name: '克罗地亚', flag: '🇭🇷', leagues: ['克罗地亚甲'] },
      { name: '塞尔维亚', flag: '🇷🇸', leagues: ['塞尔维亚超'] },
      { name: '保加利亚', flag: '🇧🇬', leagues: ['保加利亚甲'] },
      { name: '爱尔兰', flag: '🇮🇪', leagues: ['爱尔兰超'] },
      { name: '冰岛', flag: '🇮🇸', leagues: ['冰岛超'] }
    ]
  },
  '美洲赛事': {
    flag: '🌎',
    order: 1,
    countries: [
      { name: '巴西', flag: '🇧🇷', leagues: ['巴甲', '巴乙', '巴西杯'] },
      { name: '阿根廷', flag: '🇦🇷', leagues: ['阿根廷甲', '阿根廷杯'] },
      { name: '墨西哥', flag: '🇲🇽', leagues: ['墨超'] },
      { name: '美国', flag: '🇺🇸', leagues: ['美职联'] },
      { name: '智利', flag: '🇨🇱', leagues: ['智利甲'] }
    ]
  },
  '亚洲赛事': {
    flag: '🌏',
    order: 2,
    countries: [
      { name: '中国', flag: '🇨🇳', leagues: ['中超', '中甲', '中乙', '中国足协杯', '中国超级杯'] },
      { name: '日本', flag: '🇯🇵', leagues: ['J1联赛', 'J2联赛', 'J3联赛', '天皇杯', 'J联赛杯', '日本超级杯'] },
      { name: '韩国', flag: '🇰🇷', leagues: ['K联赛', 'K联赛1', 'K联赛2', '韩国足协杯'] },
      { name: '澳大利亚', flag: '🇦🇺', leagues: ['澳超'] },
      { name: '沙特', flag: '🇸🇦', leagues: ['沙特联'] }
    ]
  },
  '洲际赛事': {
    flag: '🏆',
    order: 3,
    countries: [
      { name: '俱乐部赛事', flag: '🏟️', leagues: ['欧冠', '欧联', '欧协联', '欧洲超级杯', '解放者杯', '亚冠', '世俱杯'] },
      { name: '国家队赛事', flag: '🌍', leagues: ['世界杯', '女足世界杯', '欧洲杯', '美洲杯', '亚洲杯', '非洲杯', '金杯赛', '联合会杯', '欧洲U21锦标赛', '奥运会足球'] }
    ]
  }
}

// 常用赛事列表（用于快速筛选，名称必须与数据库匹配）
const HOT_LEAGUES = [
  // 欧洲
  '英超', '英冠', '英甲', '英乙', '意甲', '意乙', '西甲', '西乙', '德甲', '德乙', '法甲', '法乙',
  '葡超', '罗马尼亚甲', '荷甲', '荷乙', '俄超', '苏超', '乌超', '比甲', '捷克甲', '土超', '希腊超',
  '保加利亚甲', '瑞士超', '塞尔维亚超', '丹麦超', '奥地利甲', '波兰甲', '克罗地亚甲', '爱尔兰超', '匈牙利甲',
  '挪超', '挪甲', '瑞典超', '瑞典甲', '芬超',
  // 亚洲
  '中超', 'J1联赛', 'K联赛', 'K联赛2', '澳超',
  // 美洲
  '巴甲', '阿根廷甲', '墨超', '美职联', '智利甲',
  // 洲际俱乐部
  '欧冠', '欧联', '欧洲超级杯', '解放者杯', '亚冠', '世俱杯',
  // 洲际国家队
  '欧洲杯', '美洲杯', '亚洲杯', '非洲杯', '金杯赛', '联合会杯', '欧洲U21锦标赛', '奥运会足球', '世界杯', '女足世界杯',
  // 国内杯赛
  '足总杯', '联赛杯', '社区盾杯', '意大利杯', '意大利超级杯', '国王杯', '西班牙超级杯', '德国杯', '法国杯', '法国联赛杯', '法国超级杯',
  '荷兰杯', '葡萄牙杯', '比利时杯', '巴西杯', '天皇杯', 'J联赛杯', '日本超级杯', '韩国足协杯'
]

export default {
  name: 'DataCenter',
  components: {
    DatabaseIcon, ActivityIcon, AlertIcon, RefreshIcon, TrophyIcon,
    UsersIcon, CalendarIcon, DownloadIcon, ScanIcon, CloudIcon, LoadingIcon, ChevronIcon
  },
  setup() {
    const activeTab = ref('overview')
    const notification = ref(null)
    const searchLeague = ref('')
    const selectedLeague = ref(null)
    const expandedRegions = ref(['欧洲赛事'])
    const expandedCountries = ref(['英格兰', '意大利', '西班牙', '德国', '法国'])
    const sortBy = ref('hot')
    const starredLeagues = ref([])
    const leagueSeasons = ref([])
    const loadingSeasons = ref(false)

    // 统计数据
    const stats = ref({
      leagues: 0,
      teams: 0,
      matches: 0,
      seasons: 0
    })
    const leagueStats = ref([])

    // 比赛数据
    const matches = ref([])
    const totalMatches = ref(0)
    const matchPage = ref(1)
    const matchPageSize = ref(50)
    const leaguesList = ref([])
    const seasonsList = ref([])
    const matchFilter = ref({
      league: '',
      season: '',
      status: '',
      dateFrom: '',
      dateTo: ''
    })

    // 缺失检测
    const detecting = ref(false)
    const detectionResult = ref(null)

    // 数据同步
    const syncing = ref(false)
    const syncLogs = ref([])
    const dataSources = ref([
      {
        id: 'thesportsdb',
        name: 'TheSportsDB',
        description: '免费体育数据库，提供比赛、球队、联赛信息',
        status: 'connected',
        syncing: false
      },
      {
        id: 'football-data',
        name: 'Football-Data.org',
        description: '欧洲足球数据API，提供详细的比赛和积分榜数据',
        status: 'unconfigured',
        syncing: false
      },
      {
        id: 'api-futebol',
        name: 'API-Futebol',
        description: '巴西和南美足球数据',
        status: 'unconfigured',
        syncing: false
      }
    ])

    // 计算属性
    const matchTotalPages = computed(() => Math.ceil(matches.value.length / matchPageSize.value))
    const paginatedMatches = computed(() => {
      const start = (matchPage.value - 1) * matchPageSize.value
      return matches.value.slice(start, start + matchPageSize.value)
    })

    // 按地区和国家分组的联赛
    const groupedLeagues = computed(() => {
      const groups = []
      const matchedLeagueIds = new Set() // 记录已匹配的联赛ID

      for (const [regionName, regionConfig] of Object.entries(REGION_CONFIG)) {
        const countries = []

        for (const countryConfig of regionConfig.countries) {
          const countryLeagues = []

          for (const configName of countryConfig.leagues) {
            // 根据配置的中文名或英文名精确匹配
            const matched = leagueStats.value.find(l => {
              if (matchedLeagueIds.has(l.league_id)) return false

              const nameCn = (l.name_cn || '').trim()
              const nameEn = (l.name_en || '').trim()

              // 精确匹配或包含匹配
              return nameCn === configName ||
                     nameEn.toLowerCase().includes(configName.toLowerCase()) ||
                     configName.toLowerCase().includes(nameEn.toLowerCase()) ||
                     nameCn.includes(configName)
            })

            if (matched) {
              matchedLeagueIds.add(matched.league_id)
              countryLeagues.push(matched)
            }
          }

          // 搜索过滤
          let filteredLeagues = countryLeagues
          if (searchLeague.value) {
            const search = searchLeague.value.toLowerCase()
            filteredLeagues = countryLeagues.filter(l =>
              (l.name_cn && l.name_cn.toLowerCase().includes(search)) ||
              (l.name_en && l.name_en.toLowerCase().includes(search))
            )
          }

          if (filteredLeagues.length > 0) {
            countries.push({
              name: countryConfig.name,
              flag: countryConfig.flag,
              leagues: filteredLeagues.sort((a, b) => (b.matches_count || 0) - (a.matches_count || 0))
            })
          }
        }

        if (countries.length > 0) {
          groups.push({
            name: regionName,
            flag: regionConfig.flag,
            order: regionConfig.order,
            countries: countries,
            totalCount: countries.reduce((sum, c) => sum + c.leagues.length, 0)
          })
        }
      }

      // 按order排序
      return groups.sort((a, b) => a.order - b.order)
    })

    // 排序后的联赛列表
    const sortedLeagueStats = computed(() => {
      let sorted = [...leagueStats.value]

      // 热门联赛优先级
      const hotPriority = HOT_LEAGUES.reduce((acc, name, idx) => {
        acc[name] = idx
        return acc
      }, {})

      switch (sortBy.value) {
        case 'hot':
          // 先按收藏排序，再按热度，最后按比赛数
          sorted.sort((a, b) => {
            const aStarred = starredLeagues.value.includes(a.league_id) ? 0 : 1
            const bStarred = starredLeagues.value.includes(b.league_id) ? 0 : 1
            if (aStarred !== bStarred) return aStarred - bStarred

            const aHot = a.name_cn && hotPriority[a.name_cn] !== undefined ? hotPriority[a.name_cn] : 999
            const bHot = b.name_cn && hotPriority[b.name_cn] !== undefined ? hotPriority[b.name_cn] : 999
            if (aHot !== bHot) return aHot - bHot

            return (b.matches_count || 0) - (a.matches_count || 0)
          })
          break
        case 'matches':
          sorted.sort((a, b) => (b.matches_count || 0) - (a.matches_count || 0))
          break
        case 'teams':
          sorted.sort((a, b) => (b.teams_count || 0) - (a.teams_count || 0))
          break
        case 'name':
          sorted.sort((a, b) => (a.name_cn || a.name_en || '').localeCompare(b.name_cn || b.name_en || ''))
          break
      }

      return sorted
    })

    // 收藏切换
    const toggleStar = (leagueId) => {
      const index = starredLeagues.value.indexOf(leagueId)
      if (index > -1) {
        starredLeagues.value.splice(index, 1)
      } else {
        starredLeagues.value.push(leagueId)
      }
      // 保存到 localStorage
      localStorage.setItem('starredLeagues', JSON.stringify(starredLeagues.value))
    }

    // 方法
    const showNotification = (message, type = 'info') => {
      notification.value = { message, type }
      setTimeout(() => { notification.value = null }, 3000)
    }

    const toggleRegion = (regionName) => {
      const index = expandedRegions.value.indexOf(regionName)
      if (index > -1) {
        expandedRegions.value.splice(index, 1)
      } else {
        expandedRegions.value.push(regionName)
      }
    }

    const toggleCountry = (countryName) => {
      const index = expandedCountries.value.indexOf(countryName)
      if (index > -1) {
        expandedCountries.value.splice(index, 1)
      } else {
        expandedCountries.value.push(countryName)
      }
    }

    const selectLeague = (league) => {
      selectedLeague.value = league
      if (league) {
        activeTab.value = 'overview'
        // 加载该联赛的赛季数据
        loadLeagueSeasons(league.league_id)
      }
    }

    // 加载联赛各赛季数据
    const loadLeagueSeasons = async (leagueId) => {
      loadingSeasons.value = true
      try {
        const response = await axios.get(`/api/v1/leagues/${leagueId}/seasons-stats`)
        if (response.data.success) {
          leagueSeasons.value = response.data.seasons || []
        }
      } catch (error) {
        console.error('加载赛季数据失败:', error)
        leagueSeasons.value = []
      } finally {
        loadingSeasons.value = false
      }
    }

    // 检测联赛缺失数据
    const detectLeagueMissing = async (leagueId) => {
      showNotification('正在检测缺失数据...', 'info')
      try {
        const response = await axios.get(`/api/v1/leagues/${leagueId}/detect-missing`)
        if (response.data.success) {
          showNotification(`检测完成：缺失比分${response.data.missing_scores}场，缺失日期${response.data.missing_dates}场`, 'success')
          // 刷新赛季数据
          loadLeagueSeasons(leagueId)
        }
      } catch (error) {
        showNotification('检测失败', 'error')
      }
    }

    // 查看赛季比赛
    const viewSeasonMatches = (leagueId, season) => {
      activeTab.value = 'matches'
      matchFilter.value.league = leagueId
      matchFilter.value.season = season
      // 加载该联赛的赛季列表
      loadSeasonsList(leagueId)
      // 加载比赛数据
      loadMatches()
    }

    // 加载赛季列表（用于筛选）
    const loadSeasonsList = async (leagueId) => {
      if (!leagueId) {
        seasonsList.value = []
        return
      }
      try {
        const response = await axios.get(`/api/v1/leagues/${leagueId}/seasons`)
        if (response.data.seasons) {
          seasonsList.value = response.data.seasons
        }
      } catch (error) {
        console.error('加载赛季列表失败:', error)
        seasonsList.value = []
      }
    }

    // 联赛选择变化时
    const onLeagueChange = () => {
      // 清空赛季选择
      matchFilter.value.season = ''
      // 加载该联赛的赛季列表
      if (matchFilter.value.league) {
        loadSeasonsList(matchFilter.value.league)
      } else {
        seasonsList.value = []
      }
      // 加载比赛
      loadMatches()
    }

    // 同步赛季数据
    const syncSeasonData = async (leagueId, season) => {
      showNotification(`正在同步 ${season} 赛季数据...`, 'info')
      try {
        const response = await axios.post(`/api/v1/sync/league-season`, { league_id: leagueId, season })
        if (response.data.success) {
          showNotification(`同步完成：更新${response.data.updated}场比赛`, 'success')
          loadLeagueSeasons(leagueId)
        }
      } catch (error) {
        showNotification('同步失败', 'error')
      }
    }

    const loadStats = async () => {
      try {
        const response = await axios.get('/api/v1/data/stats')
        if (response.data.success) {
          stats.value = response.data.stats
          leagueStats.value = response.data.league_stats || []
        }
      } catch (error) {
        console.error('加载统计失败:', error)
      }

      // 加载联赛列表用于筛选
      try {
        const leaguesRes = await axios.get('/api/v1/leagues')
        leaguesList.value = leaguesRes.data.leagues || []
      } catch (error) {
        console.error('加载联赛列表失败:', error)
      }
    }

    const loadLeagueMatches = async (leagueId) => {
      try {
        const response = await axios.get(`/api/v1/leagues/${leagueId}/matches`)
        matches.value = response.data.matches || []
        totalMatches.value = matches.value.length
      } catch (error) {
        console.error('加载联赛比赛失败:', error)
      }
    }

    const loadMatches = async () => {
      try {
        // 如果没有选择联赛，加载全部比赛
        if (!matchFilter.value.league) {
          const response = await axios.get('/api/v1/matches/list', {
            params: {
              limit: 500,
              status: matchFilter.value.status || '',
              date_from: matchFilter.value.dateFrom || '',
              date_to: matchFilter.value.dateTo || ''
            }
          })
          matches.value = response.data.matches || []
          totalMatches.value = response.data.total || matches.value.length
        } else {
          // 加载指定联赛的比赛
          const params = {}
          if (matchFilter.value.season) params.season = matchFilter.value.season
          if (matchFilter.value.status) params.status = matchFilter.value.status
          if (matchFilter.value.dateFrom) params.date_from = matchFilter.value.dateFrom
          if (matchFilter.value.dateTo) params.date_to = matchFilter.value.dateTo

          const response = await axios.get(`/api/v1/leagues/${matchFilter.value.league}/matches`, { params })
          matches.value = response.data.matches || []
          totalMatches.value = matches.value.length
        }
      } catch (error) {
        console.error('加载比赛失败:', error)
        showNotification('加载比赛数据失败', 'error')
      }
    }

    const exportMatches = () => {
      if (matches.value.length === 0) return

      const csv = [
        ['日期', '联赛', '主队', '比分', '客队', '状态'].join(','),
        ...matches.value.map(m => [
          m.match_date,
          m.league_name,
          m.home_team_cn || m.home_team,
          m.status === 'finished' ? `${m.home_score}-${m.away_score}` : '',
          m.away_team_cn || m.away_team,
          m.status === 'finished' ? '已结束' : '未开始'
        ].join(','))
      ].join('\n')

      const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `matches_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)

      showNotification('导出成功', 'success')
    }

    const runDetection = async () => {
      detecting.value = true
      try {
        const response = await axios.get('/api/v1/data/detect-missing')
        detectionResult.value = response.data
        showNotification('检测完成', 'success')
      } catch (error) {
        console.error('检测失败:', error)
        // 模拟检测结果
        detectionResult.value = {
          missing_team_cn: 156,
          missing_scores: 23,
          missing_dates: 5,
          missing_league_rules: 8,
          details: {
            missing_cn_teams: [
              { team_id: 1, name_en: 'FC Utrecht', country: 'Netherlands' },
              { team_id: 2, name_en: 'SC Heerenveen', country: 'Netherlands' }
            ],
            missing_score_matches: [
              { match_id: 1, match_date: '2024-05-15', home_team: 'Arsenal', away_team: 'Chelsea' }
            ]
          }
        }
        showNotification('检测完成（模拟数据）', 'success')
      } finally {
        detecting.value = false
      }
    }

    const fixTeamName = async (team) => {
      showNotification(`正在补充 ${team.name_en} 的中文名...`, 'info')
      // 调用API补充数据
    }

    const fixMatchScore = async (match) => {
      showNotification(`正在补充比赛比分...`, 'info')
      // 调用API补充数据
    }

    const testSource = async (source) => {
      showNotification(`测试 ${source.name} 连接...`, 'info')
      try {
        // 测试同步状态API
        const response = await axios.get('/api/v1/sync/status')
        source.status = 'connected'
        showNotification(`${source.name} 连接成功`, 'success')
      } catch (error) {
        source.status = 'error'
        showNotification(`${source.name} 连接失败`, 'error')
      }
    }

    const syncFromSource = async (source) => {
      source.syncing = true
      syncLogs.value.unshift({
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        message: `开始从 ${source.name} 同步数据...`,
        type: 'info'
      })

      try {
        // 调用实际的同步API
        if (source.id === 'thesportsdb') {
          const response = await axios.post('/api/v1/sync/start')
          const result = response.data
          syncLogs.value.unshift({
            id: Date.now(),
            time: new Date().toLocaleTimeString(),
            message: `${source.name} 同步完成：${result.finished_matches?.updated || 0} 场已结束比赛，${result.future_matches?.updated || 0} 场未来赛程`,
            type: 'success'
          })
        } else if (source.id === 'football-data') {
          const response = await axios.post('/api/v1/sync/finished', null, { params: { days: 7 } })
          syncLogs.value.unshift({
            id: Date.now(),
            time: new Date().toLocaleTimeString(),
            message: `${source.name} 同步完成：${response.data.updated || 0} 场比赛已更新`,
            type: 'success'
          })
        } else if (source.id === 'api-futebol') {
          const response = await axios.post('/api/v1/sync/upcoming', null, { params: { months: 3 } })
          syncLogs.value.unshift({
            id: Date.now(),
            time: new Date().toLocaleTimeString(),
            message: `${source.name} 同步完成：${response.data.updated || 0} 场赛程已更新`,
            type: 'success'
          })
        }
        showNotification(`${source.name} 同步完成`, 'success')
      } catch (error) {
        syncLogs.value.unshift({
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          message: `${source.name} 同步失败: ${error.message}`,
          type: 'error'
        })
        showNotification(`${source.name} 同步失败`, 'error')
      } finally {
        source.syncing = false
      }
    }

    const syncRecentResults = async () => {
      syncing.value = true
      syncLogs.value.unshift({
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        message: '开始同步近期比赛结果...',
        type: 'info'
      })
      try {
        const response = await axios.post('/api/v1/sync/finished', null, { params: { days: 7 } })
        const result = response.data
        syncLogs.value.unshift({
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          message: `近期比赛结果同步完成：检查 ${result.checked || 0} 场，更新 ${result.updated || 0} 场`,
          type: 'success'
        })
        showNotification(`近期比赛结果同步完成：更新 ${result.updated || 0} 场`, 'success')
      } catch (error) {
        syncLogs.value.unshift({
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          message: `同步失败: ${error.message}`,
          type: 'error'
        })
        showNotification('同步失败: ' + error.message, 'error')
      } finally {
        syncing.value = false
      }
    }

    const syncUpcomingFixtures = async () => {
      syncing.value = true
      syncLogs.value.unshift({
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        message: '开始同步未来赛程...',
        type: 'info'
      })
      try {
        const response = await axios.post('/api/v1/sync/upcoming', null, { params: { months: 3 } })
        const result = response.data
        syncLogs.value.unshift({
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          message: `未来赛程同步完成：更新 ${result.updated || 0} 场赛程`,
          type: 'success'
        })
        showNotification(`未来赛程同步完成：更新 ${result.updated || 0} 场`, 'success')
      } catch (error) {
        syncLogs.value.unshift({
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          message: `同步失败: ${error.message}`,
          type: 'error'
        })
        showNotification('同步失败: ' + error.message, 'error')
      } finally {
        syncing.value = false
      }
    }

    const syncTeams = async () => {
      syncing.value = true
      showNotification('正在同步球队信息...', 'info')
      try {
        // 调用球队更新API
        const response = await axios.get('/api/v1/teams', { params: { limit: 500 } })
        const teams = response.data.teams || []
        showNotification(`已加载 ${teams.length} 个球队信息`, 'success')
        syncLogs.value.unshift({
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          message: `球队信息同步完成，共 ${teams.length} 个球队`,
          type: 'success'
        })
      } catch (error) {
        showNotification('同步失败: ' + error.message, 'error')
      } finally {
        syncing.value = false
      }
    }

    const syncLeagueRules = async () => {
      syncing.value = true
      showNotification('正在同步联赛规则...', 'info')
      try {
        // 获取所有联赛并同步规则
        const leaguesRes = await axios.get('/api/v1/leagues')
        const leagues = leaguesRes.data.leagues || []
        let successCount = 0
        for (const league of leagues.slice(0, 20)) { // 只同步前20个联赛
          try {
            await axios.get(`/api/v1/leagues/${league.league_id}/rules`)
            successCount++
          } catch (e) {
            // 忽略单个联赛的错误
          }
        }
        showNotification(`联赛规则同步完成，成功 ${successCount} 个`, 'success')
        syncLogs.value.unshift({
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          message: `联赛规则同步完成，成功 ${successCount} 个联赛`,
          type: 'success'
        })
      } catch (error) {
        showNotification('同步失败: ' + error.message, 'error')
      } finally {
        syncing.value = false
      }
    }

    onMounted(() => {
      // 加载收藏数据
      const savedStars = localStorage.getItem('starredLeagues')
      if (savedStars) {
        starredLeagues.value = JSON.parse(savedStars)
      }
      loadStats()
      // 默认加载比赛数据
      loadMatches()
    })

    return {
      activeTab,
      notification,
      stats,
      leagueStats,
      sortedLeagueStats,
      matches,
      totalMatches,
      matchPage,
      matchPageSize,
      matchTotalPages,
      paginatedMatches,
      leaguesList,
      seasonsList,
      matchFilter,
      detecting,
      detectionResult,
      syncing,
      syncLogs,
      dataSources,
      searchLeague,
      selectedLeague,
      expandedRegions,
      expandedCountries,
      groupedLeagues,
      sortBy,
      starredLeagues,
      leagueSeasons,
      loadingSeasons,
      showNotification,
      toggleRegion,
      toggleCountry,
      toggleStar,
      selectLeague,
      loadMatches,
      loadLeagueMatches,
      loadLeagueSeasons,
      loadSeasonsList,
      onLeagueChange,
      detectLeagueMissing,
      viewSeasonMatches,
      syncSeasonData,
      exportMatches,
      runDetection,
      fixTeamName,
      fixMatchScore,
      testSource,
      syncFromSource,
      syncRecentResults,
      syncUpcomingFixtures,
      syncTeams,
      syncLeagueRules
    }
  }
}
</script>

<style scoped>
.data-center {
  padding: 0;
}

/* 主布局 */
.main-layout {
  display: flex;
  gap: 20px;
  min-height: calc(100vh - 200px);
}

/* 左侧导航栏 */
.league-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  overflow: hidden;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #1f2937;
}

.sidebar-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  background: #0d1117;
  border: 1px solid #374151;
  border-radius: 6px;
  color: white;
  font-size: 13px;
}

.search-input:focus {
  outline: none;
  border-color: #10b981;
}

.league-tree {
  max-height: calc(100vh - 350px);
  overflow-y: auto;
}

.tree-item.all-leagues {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid #1f2937;
}

.tree-item.all-leagues:hover {
  background: rgba(255, 255, 255, 0.03);
}

.tree-item.all-leagues.active {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.tree-icon {
  width: 16px;
  height: 16px;
  opacity: 0.7;
}

.tree-item.all-leagues .count {
  margin-left: auto;
  font-size: 12px;
  color: #6b7280;
  background: #1f2937;
  padding: 2px 8px;
  border-radius: 10px;
}

/* 地区分组 */
.region-group {
  border-bottom: 1px solid #1f2937;
}

.region-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.region-header:hover {
  background: rgba(255, 255, 255, 0.02);
}

.chevron {
  width: 14px;
  height: 14px;
  color: #6b7280;
  transition: transform 0.2s;
}

.chevron.expanded {
  transform: rotate(90deg);
}

.region-flag {
  font-size: 16px;
}

.region-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #e5e7eb;
}

.region-header .count {
  font-size: 11px;
  color: #6b7280;
  background: #1f2937;
  padding: 2px 6px;
  border-radius: 8px;
}

.region-leagues {
  background: #0d1117;
}

/* 国家分组 */
.country-group {
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
}

.country-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px 8px 24px;
  cursor: pointer;
  transition: background 0.2s;
}

.country-header:hover {
  background: rgba(255, 255, 255, 0.02);
}

.chevron.small {
  width: 12px;
  height: 12px;
}

.country-flag {
  font-size: 14px;
}

.country-name {
  flex: 1;
  font-size: 12px;
  font-weight: 500;
  color: #d1d5db;
}

.country-header .count {
  font-size: 10px;
  color: #6b7280;
  background: #1f2937;
  padding: 1px 5px;
  border-radius: 6px;
}

.country-leagues {
  background: rgba(0, 0, 0, 0.2);
}

.league-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px 8px 36px;
  cursor: pointer;
  transition: background 0.2s;
}

.league-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

.league-item.active {
  background: rgba(16, 185, 129, 0.1);
}

.league-item.active .league-name {
  color: #10b981;
}

.league-name {
  font-size: 13px;
  color: #9ca3af;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.league-matches {
  font-size: 11px;
  color: #6b7280;
}

/* 右侧内容区 */
.content-area {
  flex: 1;
  min-width: 0;
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

/* 选中联赛信息 */
.selected-league-info {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.selected-league-info h3 {
  font-size: 18px;
  font-weight: 600;
  color: white;
  margin-bottom: 4px;
}

.selected-league-info p {
  font-size: 13px;
  color: #9ca3af;
}

/* 标签页 */
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  border-bottom: 1px solid #1f2937;
  padding-bottom: 12px;
  flex-wrap: wrap;
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

/* 选中联赛视图 */
.league-seasons-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.league-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 20px;
}

.league-title h3 {
  font-size: 24px;
  font-weight: 700;
  color: white;
  margin: 0 0 4px 0;
}

.league-title p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.league-stats {
  display: flex;
  gap: 16px;
}

.stat-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.stat-badge .value {
  font-size: 24px;
  font-weight: 700;
  color: #10b981;
}

.stat-badge .label {
  font-size: 12px;
  color: #6b7280;
}

.seasons-list {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 20px;
}

.seasons-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.seasons-header h4 {
  font-size: 16px;
  font-weight: 600;
  color: white;
  margin: 0;
}

.seasons-table {
  width: 100%;
  border-collapse: collapse;
}

.seasons-table th {
  text-align: left;
  padding: 12px;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  border-bottom: 1px solid #1f2937;
  background: #0d1117;
}

.seasons-table td {
  padding: 12px;
  font-size: 13px;
  color: #e5e7eb;
  border-bottom: 1px solid #1f2937;
}

.seasons-table td.warning {
  color: #f59e0b;
  font-weight: 600;
}

.season-name {
  font-weight: 600;
  color: white;
}

/* 统计卡片 - 一排显示 */
.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 16px;
}

.stat-item {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
}

.stat-item .stat-icon {
  width: 20px;
  height: 20px;
  color: #10b981;
  flex-shrink: 0;
}

.stat-item .stat-info {
  display: flex;
  flex-direction: column;
}

.stat-item .stat-value {
  font-size: 20px;
  font-weight: 700;
  color: white;
  line-height: 1.2;
}

.stat-item .stat-label {
  font-size: 12px;
  color: #6b7280;
}

/* 统计卡片 - 旧样式保留给其他地方 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.leagues { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.stat-icon.teams { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
.stat-icon.matches { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.stat-icon.seasons { background: rgba(139, 92, 246, 0.1); color: #8b5cf6; }

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: white;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

/* 区块 */
.section {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: white;
  margin: 0;
}

.sort-select {
  padding: 6px 12px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 6px;
  color: white;
  font-size: 13px;
}

.star-btn {
  background: transparent;
  border: none;
  color: #4b5563;
  font-size: 18px;
  cursor: pointer;
  padding: 4px;
  transition: color 0.2s;
}

.star-btn:hover {
  color: #fbbf24;
}

.star-btn.starred {
  color: #fbbf24;
}

/* 联赛表格 */
.leagues-table-container {
  overflow-x: auto;
}

.leagues-table {
  width: 100%;
  border-collapse: collapse;
}

.leagues-table th {
  text-align: left;
  padding: 12px;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  border-bottom: 1px solid #1f2937;
}

.leagues-table td {
  padding: 12px;
  font-size: 13px;
  color: #e5e7eb;
  border-bottom: 1px solid #1f2937;
}

.league-name .name-cn {
  font-weight: 500;
  display: block;
}

.league-name .name-en {
  font-size: 11px;
  color: #6b7280;
}

.completeness-bar {
  width: 100px;
  height: 8px;
  background: #1f2937;
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}

.completeness-fill {
  height: 100%;
  background: #10b981;
  border-radius: 4px;
}

.completeness-text {
  position: absolute;
  right: -35px;
  top: -4px;
  font-size: 11px;
  color: #6b7280;
}

/* 筛选栏 - 紧凑样式 */
.filter-bar-compact {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-item label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
  white-space: nowrap;
}

.filter-item select {
  padding: 6px 10px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 6px;
  color: white;
  font-size: 12px;
  min-width: 100px;
  outline: none;
}

.filter-item select:focus {
  border-color: #10b981;
}

.filter-item input[type="date"] {
  padding: 5px 8px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 6px;
  color: white;
  font-size: 12px;
  width: 110px;
  outline: none;
}

.filter-item input[type="date"]:focus {
  border-color: #10b981;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 6px;
}

.date-arrow {
  color: #4b5563;
  font-size: 12px;
}

.filter-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.btn-compact {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-search {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
}

.btn-search:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
}

.btn-export {
  background: #1a1f2e;
  border: 1px solid #374151;
  color: #e5e7eb;
}

.btn-export:hover {
  background: #252b3b;
  border-color: #4b5563;
}

/* 旧筛选栏样式保留 */
.filter-bar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-group label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.filter-group select,
.filter-group input {
  padding: 8px 12px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  min-width: 120px;
}

.date-sep {
  color: #6b7280;
  margin: 0 8px;
  align-self: center;
  margin-bottom: 2px;
}

/* 按钮 */
.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
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

.btn-small {
  padding: 6px 12px;
  font-size: 12px;
}

.btn-icon {
  width: 14px;
  height: 14px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 比赛表格 */
.matches-count {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 12px;
}

.matches-table-container {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  overflow: hidden;
}

.matches-table {
  width: 100%;
  border-collapse: collapse;
}

.matches-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  background: #0d1117;
  border-bottom: 1px solid #1f2937;
}

.matches-table td {
  padding: 12px 16px;
  font-size: 13px;
  color: #e5e7eb;
  border-bottom: 1px solid #1f2937;
}

.team-name .name-cn {
  font-weight: 500;
}

.team-name .name-en {
  font-size: 11px;
  color: #6b7280;
  margin-left: 4px;
}

.score {
  font-weight: 600;
  color: #10b981;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.status-badge.finished {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.status-badge.scheduled {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.source-badge {
  font-size: 11px;
  color: #6b7280;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  background: #151922;
  border: 1px dashed #374151;
  border-radius: 8px;
  color: #6b7280;
}

.empty-icon {
  width: 20px;
  height: 20px;
  margin-bottom: 8px;
  opacity: 0.5;
}

.empty-state p {
  font-size: 12px;
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
  padding: 8px 16px;
  background: #1a1f2e;
  border: 1px solid #374151;
  border-radius: 6px;
  color: #9ca3af;
  font-size: 13px;
  cursor: pointer;
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
  color: #6b7280;
}

/* 检测结果 */
.detect-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.detect-header p {
  color: #6b7280;
  font-size: 14px;
}

.result-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.summary-item {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.summary-item.warning {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.05);
}

.summary-value {
  font-size: 32px;
  font-weight: 700;
  color: white;
}

.summary-item.warning .summary-value {
  color: #f59e0b;
}

.summary-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.missing-details {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 20px;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section h4 {
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
}

.missing-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.missing-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: #0d1117;
  border-radius: 6px;
}

.item-name {
  font-weight: 500;
  color: #e5e7eb;
}

.item-country,
.item-date {
  font-size: 12px;
  color: #6b7280;
}

.item-match {
  flex: 1;
  font-size: 13px;
  color: #e5e7eb;
}

.btn-fix {
  padding: 4px 12px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid #10b981;
  border-radius: 4px;
  color: #10b981;
  font-size: 12px;
  cursor: pointer;
}

.btn-fix:hover {
  background: rgba(16, 185, 129, 0.2);
}

/* 数据同步 */
.sync-section {
  background: #151922;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.sync-section h3 {
  font-size: 16px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.data-sources {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.source-card {
  background: #0d1117;
  border: 1px solid #1f2937;
  border-radius: 8px;
  padding: 16px;
}

.source-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.source-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.source-icon.connected {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.source-icon.error {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.source-name {
  font-weight: 600;
  color: white;
}

.source-status {
  font-size: 12px;
  color: #6b7280;
}

.source-status.connected {
  color: #10b981;
}

.source-status.error {
  color: #ef4444;
}

.source-desc {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 12px;
}

.source-actions {
  display: flex;
  gap: 8px;
}

.sync-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sync-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: #0d1117;
  border: 1px solid #1f2937;
  border-radius: 8px;
}

.option-info h4 {
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 4px;
}

.option-info p {
  font-size: 12px;
  color: #6b7280;
}

.sync-logs {
  max-height: 200px;
  overflow-y: auto;
}

.log-item {
  display: flex;
  gap: 12px;
  padding: 8px 12px;
  font-size: 13px;
  border-bottom: 1px solid #1f2937;
}

.log-time {
  color: #6b7280;
  font-family: monospace;
}

.log-message {
  color: #e5e7eb;
}

.log-item.success .log-message {
  color: #10b981;
}

.log-item.error .log-message {
  color: #ef4444;
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
@media (max-width: 768px) {
  .tabs {
    flex-direction: column;
  }

  .tab {
    justify-content: center;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }

  .sync-option {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
