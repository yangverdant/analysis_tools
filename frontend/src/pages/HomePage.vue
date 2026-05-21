<template>
  <div class="home-page">
    <!-- 今日比赛 -->
    <section class="section">
      <div class="section-header">
        <h2><span class="icon">📅</span> 今日比赛</h2>
        <span class="badge">{{ todayMatches.length }} 场</span>
        <span class="date-info" v-if="currentDate">{{ currentDate }}</span>
      </div>
      <div class="matches-grid" v-if="todayMatches.length">
        <div class="match-card" v-for="match in todayMatches" :key="match.match_id">
          <div class="match-league">{{ match.league_cn || match.league }}</div>
          <div class="match-teams">
            <div class="team-side">
              <span class="team-name">{{ match.home_team_cn || match.home_team }}</span>
            </div>
            <div class="score-box">
              <span class="score">{{ match.home_goals ?? '-' }}</span>
              <span class="vs">:</span>
              <span class="score">{{ match.away_goals ?? '-' }}</span>
            </div>
            <div class="team-side">
              <span class="team-name">{{ match.away_team_cn || match.away_team }}</span>
            </div>
          </div>
          <div class="match-time">
            <span class="beijing-time">{{ match.beijing_time || match.match_time || '待定' }}</span>
            <span class="time-label" v-if="match.beijing_time && match.beijing_time !== match.local_time">北京时间</span>
          </div>
        </div>
      </div>
      <div v-else class="no-data">
        <span class="icon">📭</span>
        <p>暂无今日比赛</p>
      </div>
    </section>

    <!-- 即将开始的比赛 -->
    <section class="section">
      <div class="section-header">
        <h2><span class="icon">⏰</span> 即将开始</h2>
        <span class="badge">{{ upcomingMatches.length }} 场</span>
      </div>
      <div class="matches-grid upcoming-grid" v-if="upcomingMatches.length">
        <div class="match-card upcoming" v-for="match in upcomingMatches" :key="match.match_id">
          <div class="match-league">{{ match.league_cn || match.league }}</div>
          <div class="match-teams">
            <span class="team-name">{{ match.home_team_cn || match.home_team }}</span>
            <span class="vs-text">VS</span>
            <span class="team-name">{{ match.away_team_cn || match.away_team }}</span>
          </div>
          <div class="match-date">{{ match.match_date }}</div>
          <div class="match-time-info" v-if="match.beijing_time">
            <span class="beijing-time">{{ match.beijing_time }}</span>
            <span class="time-label">北京时间</span>
            <span class="local-time" v-if="match.beijing_time !== match.local_time">({{ match.local_time }} 当地)</span>
          </div>
          <div class="match-odds" v-if="match.home_odds">
            <span class="odd">主 {{ match.home_odds }}</span>
            <span class="odd">平 {{ match.draw_odds }}</span>
            <span class="odd">客 {{ match.away_odds }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 热门联赛 -->
    <section class="section">
      <div class="section-header">
        <h2><span class="icon">🏆</span> 热门联赛</h2>
      </div>
      <div class="leagues-grid">
        <div class="league-card" v-for="league in popularLeagues" :key="league.league_id" @click="goToLeague(league.league_id)">
          <div class="league-icon">⚽</div>
          <div class="league-info">
            <div class="league-name">{{ league.name_cn || league.name }}</div>
            <div class="league-country">{{ league.country_cn || league.country }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- FIFA排名 -->
    <section class="section rankings-section">
      <div class="ranking-card card">
        <div class="card-header">
          <h3><span class="icon">🌍</span> FIFA国家队排名</h3>
          <span class="top-badge">TOP 10</span>
        </div>
        <div class="ranking-list">
          <div class="ranking-row" v-for="team in fifaNationalRankings.slice(0, 10)" :key="team.rank">
            <span class="rank" :class="getRankStyle(team.rank)">{{ team.rank }}</span>
            <span class="country">{{ team.country_cn || team.country }}</span>
            <span class="points">{{ team.points }}分</span>
          </div>
        </div>
      </div>
      <div class="ranking-card card">
        <div class="card-header">
          <h3><span class="icon">🏟️</span> FIFA俱乐部排名</h3>
          <span class="top-badge">TOP 10</span>
        </div>
        <div class="ranking-list">
          <div class="ranking-row" v-for="club in fifaClubRankings.slice(0, 10)" :key="club.rank">
            <span class="rank" :class="getRankStyle(club.rank)">{{ club.rank }}</span>
            <span class="country">{{ club.club_cn || club.club }}</span>
            <span class="points">{{ club.points }}分</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { matchAPI, leagueAPI, rankingAPI } from '../api'

export default {
  name: 'HomePage',
  setup() {
    const router = useRouter()

    const todayMatches = ref([])
    const upcomingMatches = ref([])
    const leagues = ref([])
    const fifaNationalRankings = ref([])
    const fifaClubRankings = ref([])
    const popularLeagues = ref([])
    const currentDate = ref('')

    const getRankStyle = (rank) => {
      if (rank === 1) return 'gold'
      if (rank === 2) return 'silver'
      if (rank === 3) return 'bronze'
      return ''
    }

    const loadData = async () => {
      try {
        const todayData = await matchAPI.getToday()
        if (todayData.data) {
          todayMatches.value = todayData.data
          currentDate.value = todayData.current_date || ''
        }

        const upcomingData = await matchAPI.getUpcoming(7)
        if (upcomingData.data) upcomingMatches.value = upcomingData.data

        const leaguesData = await leagueAPI.getLeagues()
        if (leaguesData.data) {
          leagues.value = leaguesData.data
          popularLeagues.value = leaguesData.data.filter(l =>
            ['Premier League', 'Bundesliga', 'La Liga', 'Serie A', 'Ligue 1'].includes(l.name)
          )
        }

        const nationalData = await rankingAPI.getFIFANational(10)
        if (nationalData.data) fifaNationalRankings.value = nationalData.data

        const clubData = await rankingAPI.getFIFAClub(10)
        if (clubData.data) fifaClubRankings.value = clubData.data

      } catch (error) {
        console.error('加载数据失败:', error)
      }
    }

    const goToLeague = (leagueId) => {
      router.push({ name: 'League', params: { id: leagueId } })
    }

    onMounted(loadData)

    return {
      todayMatches,
      upcomingMatches,
      leagues,
      popularLeagues,
      fifaNationalRankings,
      fifaClubRankings,
      currentDate,
      goToLeague,
      getRankStyle
    }
  }
}
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section {
  background: #151922;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: #f3f4f6;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-header h2 .icon {
  font-size: 14px;
}

.badge {
  font-size: 12px;
  color: #9ca3af;
  background: rgba(255,255,255,0.05);
  padding: 4px 12px;
  border-radius: 12px;
}

.date-info {
  font-size: 12px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 4px 12px;
  border-radius: 12px;
}

/* 比赛卡片 */
.matches-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.match-card {
  background: #1c222f;
  border-radius: 10px;
  padding: 16px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  transition: transform 0.2s, box-shadow 0.2s;
}

.match-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}

.match-card.upcoming {
  border-color: rgba(16, 185, 129, 0.3);
  background: linear-gradient(135deg, #1c222f 0%, rgba(16, 185, 129, 0.05) 100%);
}

.match-league {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 12px;
}

.match-teams {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.team-side {
  flex: 1;
}

.team-name {
  font-weight: 500;
  font-size: 14px;
  color: #e5e7eb;
}

.score-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
}

.score {
  font-size: 18px;
  font-weight: 700;
  color: #f3f4f6;
}

.vs {
  color: #4b5563;
  font-size: 14px;
}

.vs-text {
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
}

.match-time, .match-date {
  font-size: 12px;
  color: #6b7280;
}

.match-time-info {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

.beijing-time {
  font-size: 14px;
  font-weight: 600;
  color: #10b981;
}

.time-label {
  font-size: 10px;
  color: #6b7280;
  background: rgba(16, 185, 129, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

.local-time {
  font-size: 11px;
  color: #6b7280;
}

.match-odds {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.odd {
  font-size: 11px;
  padding: 4px 10px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
  color: #9ca3af;
}

/* 联赛卡片 */
.leagues-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}

.league-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.league-card:hover {
  transform: translateY(-2px);
  border-color: rgba(16, 185, 129, 0.3);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}

.league-icon {
  font-size: 14px;
}

.league-name {
  font-weight: 500;
  color: #f3f4f6;
  font-size: 13px;
}

.league-country {
  font-size: 11px;
  color: #6b7280;
  margin-top: 1px;
}

/* 排名区域 */
.rankings-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  background: transparent;
  border: none;
  padding: 0;
}

.ranking-card {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #f3f4f6;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header h3 .icon {
  font-size: 14px;
}

.top-badge {
  font-size: 10px;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.ranking-list {
  padding: 8px 0;
}

.ranking-row {
  display: flex;
  align-items: center;
  padding: 10px 20px;
  transition: background 0.2s;
}

.ranking-row:hover {
  background: rgba(255,255,255,0.02);
}

.rank {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-weight: 700;
  font-size: 12px;
  background: rgba(255,255,255,0.05);
  color: #9ca3af;
  margin-right: 12px;
}

.rank.gold {
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  color: #1a1a2e;
}

.rank.silver {
  background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%);
  color: #1a1a2e;
}

.rank.bronze {
  background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
  color: #1a1a2e;
}

.country {
  flex: 1;
  font-size: 14px;
  color: #e5e7eb;
}

.points {
  font-size: 12px;
  color: #6b7280;
  font-family: 'SF Mono', Monaco, monospace;
}

.no-data {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.no-data .icon {
  font-size: 32px;
  display: block;
  margin-bottom: 12px;
  opacity: 0.5;
}

/* 响应式 */
@media (max-width: 900px) {
  .rankings-section {
    grid-template-columns: 1fr;
  }

  .matches-grid {
    grid-template-columns: 1fr;
  }
}
</style>
