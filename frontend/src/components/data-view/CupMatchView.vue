<template>
  <div class="cup-view">
    <!-- 头部导航区域 -->
    <header class="cup-header">
      <div class="header-content">
        <div class="header-left">
          <div class="trophy-badge">🏆</div>
          <div class="title-section">
            <h1 class="cup-title">{{ cupInfo?.name || '杯赛' }}</h1>
            <h2 class="cup-subtitle">{{ season }} 赛季</h2>
          </div>
        </div>
        <div class="header-right">
          <span class="update-time">🕐 {{ totalMatches }} 场比赛</span>
        </div>
      </div>
    </header>

    <!-- 模块切换 Tab -->
    <div class="module-tabs">
      <button
        v-for="mod in modules"
        :key="mod.key"
        :class="['module-tab', { active: currentModule === mod.key }]"
        @click="currentModule = mod.key"
      >
        {{ mod.label }}
        <span class="tab-indicator" v-if="currentModule === mod.key"></span>
      </button>
    </div>

    <!-- 主体内容区 -->
    <main class="cup-main">
      <!-- 模块1: 小组赛分组 -->
      <section v-if="currentModule === 'group'" class="section">
        <div class="groups-grid" v-if="groupStandings.length">
          <div class="group-card" v-for="group in groupStandings" :key="group.name">
            <div class="group-header">
              <span class="group-name">{{ group.name }}组</span>
              <span class="group-cols">
                <span class="col">场次</span>
                <span class="col wide">胜 平 负</span>
                <span class="col">进/失</span>
                <span class="col">积分</span>
              </span>
            </div>
            <div class="group-body">
              <div class="team-row" v-for="(team, idx) in group.teams" :key="team.team_name" :class="{ qualified: idx < 2 }">
                <div class="team-info">
                  <span class="rank" :class="getRankClass(idx)">{{ idx + 1 }}</span>
                  <span class="team-flag" :style="getTeamColor(team.team_name)"></span>
                  <span class="team-name">{{ team.team_name_cn || team.team_name }}</span>
                </div>
                <div class="team-stats">
                  <span class="stat">{{ team.matches }}</span>
                  <span class="stat wide">{{ team.wins }} {{ team.draws }} {{ team.losses }}</span>
                  <span class="stat">{{ team.goals_for }}/{{ team.goals_against }}</span>
                  <span class="stat pts">{{ team.points }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="legend" v-if="groupStandings.length">
          <span class="legend-item"><span class="dot green"></span> 晋级淘汰赛</span>
          <span class="legend-item"><span class="dot gray"></span> 淘汰出局</span>
        </div>

        <div class="empty-state" v-else>
          <span class="empty-icon">📊</span>
          <span class="empty-text">暂无小组赛数据</span>
        </div>
      </section>

      <!-- 模块2: 晋级之路 (淘汰赛) -->
      <section v-if="currentModule === 'knockout'" class="section">
        <div class="bracket-wrapper" v-if="knockoutByRound.length">
          <!-- 背景装饰渐变 -->
          <div class="bracket-bg-gradient"></div>

          <div class="bracket-container">
            <div class="bracket-rounds">

              <!-- 左侧 (R16 -> QF -> SF) -->
              <div class="bracket-side left">
                <div class="bracket-round" v-for="(round, idx) in leftRounds" :key="round.stage">
                  <div class="round-label">{{ round.name }}</div>
                  <div class="round-matches" :style="{ gap: getGap(idx) }">
                    <div class="bracket-match" v-for="match in round.matches" :key="match.match_id" :class="{ completed: isMatchCompleted(match) }">
                      <div class="match-date">{{ formatDate(match.match_date) }}</div>
                      <div class="match-team" :class="{ winner: isHomeWinner(match) }">
                        <span class="team-flag">{{ getFlag(match.home_team) }}</span>
                        <span class="team-name">{{ match.home_team_cn || getShortName(match.home_team) }}</span>
                        <span class="team-score">{{ match.home_goals ?? '-' }}</span>
                      </div>
                      <div class="match-divider"></div>
                      <div class="match-team" :class="{ winner: isAwayWinner(match) }">
                        <span class="team-flag">{{ getFlag(match.away_team) }}</span>
                        <span class="team-name">{{ match.away_team_cn || getShortName(match.away_team) }}</span>
                        <span class="team-score">{{ match.away_goals ?? '-' }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 中间奖杯和决赛 -->
              <div class="bracket-center">
                <div class="trophy-glow">🏆</div>
                <div class="final-match" v-if="finalMatch" :class="{ completed: isMatchCompleted(finalMatch) }">
                  <div class="final-label">决赛</div>
                  <div class="match-team" :class="{ winner: isHomeWinner(finalMatch) }">
                    <span class="team-flag">{{ getFlag(finalMatch.home_team) }}</span>
                    <span class="team-name">{{ finalMatch.home_team_cn || getShortName(finalMatch.home_team) }}</span>
                    <span class="team-score">{{ finalMatch.home_goals ?? '-' }}</span>
                  </div>
                  <div class="match-divider"></div>
                  <div class="match-team" :class="{ winner: isAwayWinner(finalMatch) }">
                    <span class="team-flag">{{ getFlag(finalMatch.away_team) }}</span>
                    <span class="team-name">{{ finalMatch.away_team_cn || getShortName(finalMatch.away_team) }}</span>
                    <span class="team-score">{{ finalMatch.away_goals ?? '-' }}</span>
                  </div>
                  <div class="final-date">{{ formatDate(finalMatch.match_date) }}</div>
                </div>
              </div>

              <!-- 右侧 (SF <- QF <- R16) - 反向排列 -->
              <div class="bracket-side right">
                <div class="bracket-round" v-for="(round, idx) in rightRounds" :key="round.stage">
                  <div class="round-label">{{ round.name }}</div>
                  <div class="round-matches" :style="{ gap: getGap(idx) }">
                    <div class="bracket-match" v-for="match in round.matches" :key="match.match_id" :class="{ completed: isMatchCompleted(match) }">
                      <div class="match-date">{{ formatDate(match.match_date) }}</div>
                      <div class="match-team" :class="{ winner: isHomeWinner(match) }">
                        <span class="team-flag">{{ getFlag(match.home_team) }}</span>
                        <span class="team-name">{{ match.home_team_cn || getShortName(match.home_team) }}</span>
                        <span class="team-score">{{ match.home_goals ?? '-' }}</span>
                      </div>
                      <div class="match-divider"></div>
                      <div class="match-team" :class="{ winner: isAwayWinner(match) }">
                        <span class="team-flag">{{ getFlag(match.away_team) }}</span>
                        <span class="team-name">{{ match.away_team_cn || getShortName(match.away_team) }}</span>
                        <span class="team-score">{{ match.away_goals ?? '-' }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

        <div class="empty-state" v-else>
          <span class="empty-icon">⚔️</span>
          <span class="empty-text">暂无淘汰赛数据</span>
        </div>
      </section>

      <!-- 模块3: 比赛列表 -->
      <section v-if="currentModule === 'matches'" class="section">
        <div class="match-list-header">
          <div class="header-left">
            <span class="title-bar"></span>
            <h3>比赛列表</h3>
            <div class="list-tabs">
              <button
                v-for="tab in listTabs"
                :key="tab.key"
                :class="['list-tab', { active: activeListTab === tab.key }]"
                @click="activeListTab = tab.key"
              >
                {{ tab.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="match-list-container" v-if="matchesByDate.length">
          <div class="date-block" v-for="group in matchesByDate" :key="group.date">
            <div class="date-header">{{ formatFullDate(group.date) }}</div>
            <div class="date-matches">
              <div class="match-row" v-for="match in group.matches" :key="match.match_id">
                <div class="match-time">{{ match.match_time || '--:--' }}</div>
                <div class="match-stage">{{ getStageName(match.stage) }}</div>
                <div class="match-teams">
                  <div class="team-side home">
                    <span class="team-name">{{ match.home_team_cn || match.home_team }}</span>
                    <span class="team-flag">{{ getFlag(match.home_team) }}</span>
                  </div>
                  <div class="score-box">
                    <span class="score">{{ match.home_goals ?? '-' }}</span>
                    <span class="sep">-</span>
                    <span class="score">{{ match.away_goals ?? '-' }}</span>
                  </div>
                  <div class="team-side away">
                    <span class="team-flag">{{ getFlag(match.away_team) }}</span>
                    <span class="team-name">{{ match.away_team_cn || match.away_team }}</span>
                  </div>
                </div>
                <div class="match-status" :class="{ finished: match.home_goals !== null }">
                  {{ match.home_goals !== null ? '已结束' : '未开始' }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="empty-state" v-else>
          <span class="empty-icon">📋</span>
          <span class="empty-text">暂无比赛数据</span>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue'
import { leagueAPI } from '../../api'

const STAGE_NAMES = {
  'qualifying': '预选赛',
  'playoff': '附加赛',
  'group': '小组赛',
  'league_phase': '联赛阶段',
  'round_of_32': '32强',
  'round_of_16': '1/8决赛',
  'quarterfinal': '1/4决赛',
  'semifinal': '半决赛',
  'final': '决赛',
  'first_round': '第一轮',
  'second_round': '第二轮',
  'third_round': '第三轮',
  'fourth_round': '第四轮',
  'fifth_round': '第五轮',
  'sixth_round': '第六轮'
}

const KNOCKOUT_ORDER = [
  'round_of_32', 'round_of_16', 'quarterfinal', 'semifinal', 'final',
  'first_round', 'second_round', 'third_round', 'fourth_round', 'fifth_round', 'sixth_round'
]

export default {
  name: 'CupMatchView',
  props: {
    leagueId: { type: Number, required: true },
    season: { type: String, default: null }
  },
  setup(props) {
    const currentModule = ref('group')
    const activeListTab = ref('all')
    const allMatches = ref([])
    const cupInfo = ref(null)

    const modules = [
      { key: 'group', label: '小组赛分组' },
      { key: 'knockout', label: '晋级之路 (淘汰赛)' },
      { key: 'matches', label: '比赛列表' }
    ]

    const listTabs = [
      { key: 'all', label: '全部' },
      { key: 'group', label: '小组赛' },
      { key: 'knockout', label: '淘汰赛' }
    ]

    // 小组赛积分榜
    const groupStandings = computed(() => {
      const groupMatches = allMatches.value.filter(m =>
        m.stage === 'group' || m.stage === 'league_phase'
      )
      if (!groupMatches.length) return []

      const groups = {}
      groupMatches.forEach(match => {
        const groupName = match.group_name || 'A'
        if (!groups[groupName]) groups[groupName] = {}

        const homeTeam = match.home_team
        const awayTeam = match.away_team

        if (!groups[groupName][homeTeam]) {
          groups[groupName][homeTeam] = createTeamStats(match, 'home')
        }
        if (!groups[groupName][awayTeam]) {
          groups[groupName][awayTeam] = createTeamStats(match, 'away')
        }

        if (match.home_goals !== null && match.away_goals !== null) {
          updateTeamStats(groups[groupName][homeTeam], match.home_goals, match.away_goals, true)
          updateTeamStats(groups[groupName][awayTeam], match.away_goals, match.home_goals, false)
        }
      })

      return Object.entries(groups).map(([name, teams]) => ({
        name,
        teams: Object.values(teams)
          .map(t => ({ ...t, goal_diff: t.goals_for - t.goals_against }))
          .sort((a, b) => b.points - a.points || b.goal_diff - a.goal_diff)
      })).sort((a, b) => a.name.localeCompare(b.name))
    })

    // 淘汰赛按轮次分组
    const knockoutByRound = computed(() => {
      const rounds = {}
      allMatches.value
        .filter(m => KNOCKOUT_ORDER.includes(m.stage))
        .forEach(m => {
          if (!rounds[m.stage]) {
            rounds[m.stage] = {
              name: STAGE_NAMES[m.stage] || m.stage,
              stage: m.stage,
              matches: []
            }
          }
          rounds[m.stage].matches.push(m)
        })

      return Object.values(rounds).sort((a, b) => {
        return KNOCKOUT_ORDER.indexOf(a.stage) - KNOCKOUT_ORDER.indexOf(b.stage)
      })
    })

    // 决赛
    const finalMatch = computed(() => {
      const finals = knockoutByRound.value.find(r => r.stage === 'final')
      return finals?.matches?.[0] || null
    })

    // 左侧轮次 (不含决赛，取前3轮)
    const leftRounds = computed(() => {
      return knockoutByRound.value.filter(r => r.stage !== 'final').slice(0, 3)
    })

    // 右侧轮次 (取后3轮)
    const rightRounds = computed(() => {
      const nonFinal = knockoutByRound.value.filter(r => r.stage !== 'final')
      return nonFinal.slice(3, 6)
    })

    // 按日期分组
    const matchesByDate = computed(() => {
      let matches = allMatches.value

      if (activeListTab.value === 'group') {
        matches = matches.filter(m => m.stage === 'group' || m.stage === 'league_phase')
      } else if (activeListTab.value === 'knockout') {
        matches = matches.filter(m => KNOCKOUT_ORDER.includes(m.stage))
      }

      const groups = {}
      matches.forEach(m => {
        const date = m.match_date || 'unknown'
        if (!groups[date]) groups[date] = []
        groups[date].push(m)
      })
      return Object.entries(groups)
        .sort((a, b) => b[0].localeCompare(a[0]))
        .map(([date, matches]) => ({ date, matches }))
    })

    const totalMatches = computed(() => allMatches.value.length)

    // 辅助函数
    const createTeamStats = (match, side) => ({
      team_id: side === 'home' ? match.home_team_id : match.away_team_id,
      team_name: side === 'home' ? match.home_team : match.away_team,
      team_name_cn: side === 'home' ? match.home_team_cn : match.away_team_cn,
      matches: 0, wins: 0, draws: 0, losses: 0,
      goals_for: 0, goals_against: 0, points: 0
    })

    const updateTeamStats = (team, gf, ga, isHome) => {
      team.matches++
      team.goals_for += gf
      team.goals_against += ga
      if (gf > ga) { team.wins++; team.points += 3 }
      else if (gf < ga) { team.losses++ }
      else { team.draws++; team.points++ }
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return '-'
      const d = new Date(dateStr)
      return `${d.getMonth() + 1}/${d.getDate()}`
    }

    const formatFullDate = (dateStr) => {
      if (!dateStr || dateStr === 'unknown') return '日期未知'
      const d = new Date(dateStr)
      const month = d.getMonth() + 1
      const day = d.getDate()
      const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
      return `${month}月${day}日 ${weekDays[d.getDay()]}`
    }

    const getShortName = (name) => {
      if (!name) return 'TBD'
      return name.replace(/\s*\(.*?\)/, '').substring(0, 10)
    }

    const getStageName = (stage) => STAGE_NAMES[stage] || stage || '比赛'

    const getFlag = (teamName) => {
      if (!teamName) return '🏳️'
      const flags = {
        'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'France': '🇫🇷', 'Germany': '🇩🇪', 'Spain': '🇪🇸',
        'Italy': '🇮🇹', 'Brazil': '🇧🇷', 'Argentina': '🇦🇷', 'Portugal': '🇵🇹',
        'Netherlands': '🇳🇱', 'Belgium': '🇧🇪', 'Croatia': '🇭🇷', 'Morocco': '🇲🇦',
        'Japan': '🇯🇵', 'Korea': '🇰🇷', 'USA': '🇺🇸', 'Mexico': '🇲🇽',
        'Australia': '🇦🇺', 'Senegal': '🇸🇳', 'Poland': '🇵🇱', 'Switzerland': '🇨🇭',
        'Serbia': '🇷🇸', 'Denmark': '🇩🇰', 'Tunisia': '🇹🇳', 'Uruguay': '🇺🇾',
        'Ghana': '🇬🇭', 'Canada': '🇨🇦', 'Qatar': '🇶🇦', 'Wales': '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
        'Iran': '🇮🇷', 'Saudi Arabia': '🇸🇦', 'Costa Rica': '🇨🇷', 'Cameroon': '🇨🇲',
        'Ecuador': '🇪🇨', 'China': '🇨🇳'
      }
      return flags[teamName] || '🏳️'
    }

    const isMatchCompleted = (m) => m.home_goals !== null
    const isHomeWinner = (m) => m.home_goals !== null && m.home_goals > m.away_goals
    const isAwayWinner = (m) => m.home_goals !== null && m.away_goals > m.home_goals

    const getRankClass = (idx) => {
      if (idx === 0) return 'first'
      if (idx === 1) return 'second'
      return ''
    }

    const getTeamColor = (teamName) => {
      const colors = [
        'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
        'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
        'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
        'linear-gradient(135deg, #ec4899 0%, #db2777 100%)',
        'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)',
        'linear-gradient(135deg, #84cc16 0%, #65a30d 100%)'
      ]
      const idx = teamName.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length
      return { background: colors[idx] }
    }

    const getGap = (idx) => {
      // 越往后，间距越大（模拟对阵树的间距）
      const gaps = ['24px', '48px', '96px']
      return gaps[idx] || '24px'
    }

    const loadData = async () => {
      if (!props.leagueId) return
      try {
        const [matchesRes, groupsRes, knockoutRes] = await Promise.all([
          leagueAPI.getCupMatches(props.leagueId, props.season),
          leagueAPI.getCupGroups(props.leagueId, props.season),
          leagueAPI.getCupKnockout(props.leagueId, props.season)
        ])

        const allMatchesData = matchesRes.data || []
        const groupMatchesData = groupsRes.data?.matches || []
        const knockoutData = knockoutRes.data || []

        const matchMap = new Map()
        allMatchesData.forEach(m => matchMap.set(m.match_id, m))
        groupMatchesData.forEach(m => matchMap.set(m.match_id, m))

        if (Array.isArray(knockoutData)) {
          knockoutData.forEach(round => {
            if (round.matches && Array.isArray(round.matches)) {
              round.matches.forEach(m => matchMap.set(m.match_id, m))
            }
          })
        }

        allMatches.value = Array.from(matchMap.values())

        if (matchesRes.league_cn) {
          cupInfo.value = { name: matchesRes.league_cn }
        }
      } catch (e) {
        console.error('加载杯赛数据失败:', e)
      }
    }

    watch(() => [props.leagueId, props.season], loadData)
    onMounted(loadData)

    return {
      currentModule, activeListTab, modules, listTabs, allMatches, cupInfo,
      groupStandings, knockoutByRound, finalMatch, leftRounds, rightRounds,
      matchesByDate, totalMatches,
      formatDate, formatFullDate, getShortName, getStageName, getFlag,
      isMatchCompleted, isHomeWinner, isAwayWinner,
      getRankClass, getTeamColor, getGap
    }
  }
}
</script>

<style scoped>
.cup-view {
  min-height: 100%;
  background: #070d19;
}

/* 头部 */
.cup-header {
  background: #0b1324;
  border-bottom: 1px solid #1e2e4a;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.header-content {
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 24px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.trophy-badge {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #f59e0b 0%, #b45309 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
}

.cup-title {
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(to right, #fff, #cbd5e1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0;
}

.cup-subtitle {
  font-size: 13px;
  color: #38bdf8;
  margin: 0;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.update-time {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #94a3b8;
}

/* 模块切换 */
.module-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 32px;
  padding: 0 24px;
  border-bottom: 1px solid #1e2e4a;
  background: #0b1324;
}

.module-tab {
  position: relative;
  padding: 16px 0;
  font-size: 16px;
  font-weight: 700;
  color: #64748b;
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s;
}

.module-tab:hover { color: #cbd5e1; }
.module-tab.active { color: #fff; }

.tab-indicator {
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 3px;
  background: #38bdf8;
  border-radius: 2px 2px 0 0;
  box-shadow: 0 0 8px rgba(56, 189, 248, 0.6);
}

/* 主内容 */
.cup-main {
  max-width: 1600px;
  margin: 0 auto;
  padding: 24px;
}

.section {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ========== 小组赛样式 ========== */
.groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.group-card {
  background: #121c2f;
  border-radius: 8px;
  border: 1px solid #1e2e4a;
  overflow: hidden;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.group-card:hover {
  border-color: #3a86ff;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #1a263c;
  border-bottom: 1px solid #1e2e4a;
}

.group-name {
  font-size: 14px;
  font-weight: 700;
  color: #e2e8f0;
}

.group-cols {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: #64748b;
}

.col { width: 32px; text-align: center; }
.col.wide { width: 64px; }

.group-body { padding: 8px; }

.team-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  transition: background 0.2s;
  cursor: pointer;
}

.team-row:hover { background: #1e2e4a; }
.team-row.qualified { background: rgba(16, 185, 129, 0.08); }

.team-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rank {
  width: 16px;
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.rank.first, .rank.second { color: #10b981; }

.team-flag {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  flex-shrink: 0;
}

.team-name {
  font-size: 13px;
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
}

.team-row:hover .team-name { color: #fff; }

.team-stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #94a3b8;
}

.stat { width: 32px; text-align: center; }
.stat.wide { width: 64px; letter-spacing: 2px; }
.stat.pts { color: #38bdf8; font-weight: 700; }

.legend {
  display: flex;
  gap: 24px;
  font-size: 12px;
  color: #94a3b8;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.green { background: #10b981; }
.dot.gray { background: #475569; }

/* ========== 淘汰赛样式 - 完全按照参考代码 ========== */
.bracket-wrapper {
  background: #0b1324;
  border: 1px solid #1e2e4a;
  border-radius: 12px;
  padding: 16px;
  overflow-x: auto;
  position: relative;
}

/* 背景装饰渐变 */
.bracket-bg-gradient {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, rgba(30, 58, 138, 0.2) 0%, transparent 70%);
  pointer-events: none;
}

.bracket-container {
  position: relative;
  z-index: 10;
}

.bracket-rounds {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-width: 900px;
  padding: 24px 8px;
}

.bracket-side {
  display: flex;
  gap: 32px;
  align-items: center;
}

.bracket-side.left {
  flex-direction: row;
}

.bracket-side.right {
  flex-direction: row-reverse;
}

.bracket-round {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.round-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 12px;
  text-align: center;
  position: absolute;
  top: -32px;
  width: 100%;
}

.bracket-round {
  position: relative;
}

.round-matches {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
}

/* 淘汰赛比赛卡片 - 关键样式 */
.bracket-match {
  background: #121c2f;
  border: 1px solid #1e2e4a;
  border-radius: 6px;
  padding: 8px 10px;
  width: 140px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  transition: border-color 0.2s;
  position: relative;
  z-index: 10;
}

.bracket-match:hover {
  border-color: #38bdf8;
}

.bracket-match.completed {
  border-color: rgba(16, 185, 129, 0.3);
}

.match-date {
  font-size: 10px;
  color: #64748b;
  margin-bottom: 6px;
}

.match-team {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 4px;
}

.match-team.winner { background: rgba(16, 185, 129, 0.1); }

.match-team .team-flag {
  font-size: 14px;
  width: auto;
  height: auto;
  background: none;
}

.match-team .team-name {
  flex: 1;
  font-size: 12px;
  color: #94a3b8;
  max-width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.match-team.winner .team-name {
  color: #fff;
  font-weight: 500;
}

.match-team .team-score {
  font-size: 14px;
  font-weight: 700;
  color: #64748b;
  min-width: 20px;
  text-align: right;
}

.match-team.winner .team-score { color: #38bdf8; }

.match-divider {
  height: 1px;
  background: #1e2e4a;
  margin: 2px 0;
}

/* 中间奖杯和决赛 */
.bracket-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  position: relative;
  z-index: 20;
  transform: scale(1.1);
}

.trophy-glow {
  width: 96px;
  height: 96px;
  margin-bottom: 16px;
  border-radius: 50%;
  background: linear-gradient(to bottom, rgba(245, 158, 11, 0.2) 0%, transparent 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 56px;
  filter: drop-shadow(0 0 20px rgba(245, 158, 11, 0.5));
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.final-match {
  background: linear-gradient(135deg, #1a1710 0%, #121c2f 100%);
  border: 2px solid #f59e0b;
  border-radius: 6px;
  padding: 10px;
  width: 160px;
}

.final-label {
  font-size: 12px;
  font-weight: 700;
  color: #f59e0b;
  text-align: center;
  margin-bottom: 8px;
}

.final-date {
  font-size: 10px;
  color: #94a3b8;
  text-align: center;
  margin-top: 6px;
}

/* ========== 比赛列表样式 ========== */
.match-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.match-list-header .header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-bar {
  width: 4px;
  height: 20px;
  background: #38bdf8;
  border-radius: 2px;
}

.match-list-header h3 {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  margin: 0;
}

.list-tabs {
  display: flex;
  background: #121c2f;
  border-radius: 20px;
  border: 1px solid #1e2e4a;
  padding: 3px;
  margin-left: 16px;
}

.list-tab {
  padding: 6px 16px;
  font-size: 13px;
  color: #94a3b8;
  background: none;
  border: none;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.list-tab:hover { color: #e2e8f0; }
.list-tab.active {
  background: #38bdf8;
  color: #fff;
  box-shadow: 0 2px 8px rgba(56, 189, 248, 0.3);
}

.match-list-container {
  background: #0b1324;
  border: 1px solid #1e2e4a;
  border-radius: 12px;
  overflow: hidden;
}

.date-block {
  border-bottom: 1px solid #1e2e4a;
}

.date-block:last-child { border-bottom: none; }

.date-header {
  padding: 12px 16px;
  background: rgba(16, 185, 129, 0.1);
  font-size: 14px;
  font-weight: 600;
  color: #10b981;
}

.date-matches { padding: 8px; }

.match-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  transition: background 0.2s;
  cursor: pointer;
}

.match-row:hover { background: #121c2f; }

.match-time {
  width: 60px;
  font-size: 13px;
  color: #cbd5e1;
  font-weight: 500;
}

.match-stage {
  width: 80px;
  font-size: 12px;
  color: #64748b;
}

.match-teams {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.team-side {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 120px;
}

.team-side.home { justify-content: flex-end; }
.team-side.away { justify-content: flex-start; }

.team-side .team-flag {
  font-size: 20px;
  width: auto;
  height: auto;
  background: none;
}

.team-side .team-name {
  font-size: 14px;
  color: #e2e8f0;
  font-weight: 500;
}

.score-box {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: #1a263c;
  border: 1px solid #1e2e4a;
  border-radius: 24px;
  min-width: 80px;
  justify-content: center;
}

.score-box .score {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
}

.score-box .sep { color: #475569; }

.match-status {
  width: 60px;
  text-align: right;
  font-size: 12px;
  color: #64748b;
}

.match-status.finished { color: #10b981; }

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.empty-icon {
  font-size: 20px;
  margin-bottom: 8px;
  opacity: 0.5;
}

.empty-text {
  font-size: 12px;
  color: #64748b;
}

/* 响应式 */
@media (max-width: 768px) {
  .groups-grid { grid-template-columns: 1fr; }
  .bracket-rounds { flex-direction: column; }
  .bracket-side { flex-direction: column; }
  .bracket-side.right { flex-direction: column; }
  .module-tabs { gap: 16px; padding: 0 16px; }
  .module-tab { font-size: 14px; padding: 12px 0; }
  .cup-main { padding: 16px; }
}
</style>
