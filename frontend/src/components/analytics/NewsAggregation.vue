<template>
  <div class="news-aggregation">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>新闻聚合</h2>
        <p>多维度足球新闻聚合与追踪</p>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab 1: 比赛新闻 -->
    <div v-if="activeTab === 'match'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="matchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadMatchNews"
        />
        <button class="action-btn" @click="loadMatchNews" :disabled="matchLoading">查询</button>
      </div>
      <div class="loading-state" v-if="matchLoading">
        <div class="spinner"></div>
        <p>正在加载比赛新闻...</p>
      </div>
      <div v-else-if="matchNews.length > 0" class="news-list">
        <div v-for="(item, idx) in matchNews" :key="idx" class="news-card card">
          <div class="news-header">
            <div class="news-source-tag" :class="sourceClass(item.source)">{{ item.source || '综合' }}</div>
            <div v-if="item.impact_level" class="impact-tag" :class="impactClass(item.impact_level)">{{ item.impact_level }}</div>
          </div>
          <div class="news-title">{{ item.title || '--' }}</div>
          <div class="news-summary" v-if="item.summary">{{ item.summary }}</div>
          <div class="news-meta">
            <span class="news-time">{{ item.date || item.published_at || item.time || '' }}</span>
            <span v-if="item.sentiment" class="news-sentiment" :class="sentimentClass(item.sentiment)">{{ item.sentiment }}</span>
            <a v-if="item.url || item.link" :href="item.url || item.link" target="_blank" class="news-link">查看原文</a>
          </div>
        </div>
      </div>
      <div v-else class="empty-state card">
        <p>请输入比赛ID查询新闻</p>
      </div>
    </div>

    <!-- Tab 2: 球队新闻 -->
    <div v-if="activeTab === 'team'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="teamId"
          placeholder="输入球队ID"
          class="text-input"
          @keyup.enter="loadTeamNews"
        />
        <button class="action-btn" @click="loadTeamNews" :disabled="teamLoading">查询</button>
      </div>
      <div class="loading-state" v-if="teamLoading">
        <div class="spinner"></div>
        <p>正在加载球队新闻...</p>
      </div>
      <div v-else-if="teamNews.length > 0" class="news-list">
        <div v-for="(item, idx) in teamNews" :key="idx" class="news-card card">
          <div class="news-header">
            <div class="news-source-tag" :class="sourceClass(item.source)">{{ item.source || '球队' }}</div>
            <div v-if="item.impact_level" class="impact-tag" :class="impactClass(item.impact_level)">{{ item.impact_level }}</div>
          </div>
          <div class="news-title">{{ item.title || '--' }}</div>
          <div class="news-summary" v-if="item.summary || item.content">{{ item.summary || item.content }}</div>
          <div class="news-meta">
            <span class="news-time">{{ item.date || item.published_at || item.time || '' }}</span>
            <span v-if="item.sentiment" class="news-sentiment" :class="sentimentClass(item.sentiment)">{{ item.sentiment }}</span>
            <a v-if="item.url || item.link" :href="item.url || item.link" target="_blank" class="news-link">查看原文</a>
          </div>
        </div>
      </div>
      <div v-else class="empty-state card">
        <p>请输入球队ID查询新闻</p>
      </div>
    </div>

    <!-- Tab 3: 联赛新闻 -->
    <div v-if="activeTab === 'league'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="leagueId"
          placeholder="输入联赛ID"
          class="text-input"
          @keyup.enter="loadLeagueNews"
        />
        <button class="action-btn" @click="loadLeagueNews" :disabled="leagueLoading">查询</button>
      </div>
      <div class="loading-state" v-if="leagueLoading">
        <div class="spinner"></div>
        <p>正在加载联赛新闻...</p>
      </div>
      <div v-else-if="leagueNews.length > 0" class="news-list">
        <div v-for="(item, idx) in leagueNews" :key="idx" class="news-card card">
          <div class="news-header">
            <div class="news-source-tag" :class="sourceClass(item.source)">{{ item.source || '联赛' }}</div>
            <div v-if="item.impact_level" class="impact-tag" :class="impactClass(item.impact_level)">{{ item.impact_level }}</div>
          </div>
          <div class="news-title">{{ item.title || '--' }}</div>
          <div class="news-summary" v-if="item.summary">{{ item.summary }}</div>
          <div class="news-meta">
            <span class="news-time">{{ item.date || item.published_at || item.time || '' }}</span>
            <span v-if="item.sentiment" class="news-sentiment" :class="sentimentClass(item.sentiment)">{{ item.sentiment }}</span>
            <a v-if="item.url || item.link" :href="item.url || item.link" target="_blank" class="news-link">查看原文</a>
          </div>
        </div>
      </div>
      <div v-else class="empty-state card">
        <p>请输入联赛ID查询新闻</p>
      </div>
    </div>

    <!-- Tab 4: 热门新闻 -->
    <div v-if="activeTab === 'hot'" class="tab-content">
      <div class="loading-state" v-if="hotLoading">
        <div class="spinner"></div>
        <p>正在加载热门新闻...</p>
      </div>
      <div v-else-if="hotNews.length > 0" class="news-list">
        <div v-for="(item, idx) in hotNews" :key="idx" class="news-card card">
          <div class="news-header">
            <div class="hot-rank" :class="rankClass(idx)">{{ idx + 1 }}</div>
            <div class="news-source-tag" :class="sourceClass(item.source)">{{ item.source || '热门' }}</div>
            <div v-if="item.impact_level" class="impact-tag" :class="impactClass(item.impact_level)">{{ item.impact_level }}</div>
          </div>
          <div class="news-title">{{ item.title || '--' }}</div>
          <div class="news-summary" v-if="item.summary || item.content">{{ item.summary || item.content }}</div>
          <div class="news-meta">
            <span class="news-time">{{ item.date || item.published_at || item.time || '' }}</span>
            <span v-if="item.sentiment" class="news-sentiment" :class="sentimentClass(item.sentiment)">{{ item.sentiment }}</span>
            <a v-if="item.url || item.link" :href="item.url || item.link" target="_blank" class="news-link">查看原文</a>
          </div>
        </div>
      </div>
      <div v-else class="empty-state card">
        <p>暂无热门新闻</p>
      </div>
    </div>

    <!-- Tab 5: 赛季综述 -->
    <div v-if="activeTab === 'season'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="seasonLeagueId"
          placeholder="联赛ID"
          class="text-input"
        />
        <input
          v-model="seasonId"
          placeholder="赛季ID"
          class="text-input"
          @keyup.enter="loadSeasonReview"
        />
        <button class="action-btn" @click="loadSeasonReview" :disabled="seasonLoading">查询</button>
      </div>
      <div class="loading-state" v-if="seasonLoading">
        <div class="spinner"></div>
        <p>正在加载赛季综述...</p>
      </div>
      <div v-else-if="seasonReview.length > 0" class="news-list">
        <div v-for="(item, idx) in seasonReview" :key="idx" class="news-card card">
          <div class="news-header">
            <div class="news-source-tag" :class="sourceClass(item.source)">{{ item.source || '综述' }}</div>
            <div v-if="item.impact_level" class="impact-tag" :class="impactClass(item.impact_level)">{{ item.impact_level }}</div>
          </div>
          <div class="news-title">{{ item.title || '--' }}</div>
          <div class="news-summary" v-if="item.summary">{{ item.summary }}</div>
          <div class="news-meta">
            <span class="news-time">{{ item.date || item.published_at || item.time || '' }}</span>
            <span v-if="item.sentiment" class="news-sentiment" :class="sentimentClass(item.sentiment)">{{ item.sentiment }}</span>
            <a v-if="item.url || item.link" :href="item.url || item.link" target="_blank" class="news-link">查看原文</a>
          </div>
        </div>
      </div>
      <div v-else class="empty-state card">
        <p>请输入联赛ID和赛季ID查询综述</p>
      </div>
    </div>

    <!-- Tab 6: 伤病新闻 -->
    <div v-if="activeTab === 'injury'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="injuryTeamId"
          placeholder="输入球队ID"
          class="text-input"
          @keyup.enter="loadInjuryNews"
        />
        <button class="action-btn" @click="loadInjuryNews" :disabled="injuryLoading">查询</button>
      </div>
      <div class="loading-state" v-if="injuryLoading">
        <div class="spinner"></div>
        <p>正在加载伤病新闻...</p>
      </div>
      <div v-else-if="injuryNews.length > 0" class="news-list">
        <div v-for="(item, idx) in injuryNews" :key="idx" class="news-card card">
          <div class="news-header">
            <div class="news-source-tag injury">伤病</div>
            <div v-if="item.impact_level" class="impact-tag" :class="impactClass(item.impact_level)">{{ item.impact_level }}</div>
          </div>
          <div class="news-title">{{ item.title || item.player_name || '--' }}</div>
          <div class="news-summary" v-if="item.summary || item.injury_type">{{ item.summary || item.injury_type }}</div>
          <div class="news-meta">
            <span class="news-time">{{ item.date || item.published_at || item.time || '' }}</span>
            <span v-if="item.sentiment" class="news-sentiment" :class="sentimentClass(item.sentiment)">{{ item.sentiment }}</span>
            <a v-if="item.url || item.link" :href="item.url || item.link" target="_blank" class="news-link">查看原文</a>
          </div>
        </div>
      </div>
      <div v-else class="empty-state card">
        <p>请输入球队ID查询伤病新闻</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'NewsAggregation',
  setup() {
    const activeTab = ref('hot')
    const tabs = [
      { key: 'match', label: '比赛新闻' },
      { key: 'team', label: '球队新闻' },
      { key: 'league', label: '联赛新闻' },
      { key: 'hot', label: '热门新闻' },
      { key: 'season', label: '赛季综述' },
      { key: 'injury', label: '伤病新闻' }
    ]

    // Tab 1: 比赛新闻
    const matchId = ref('')
    const matchLoading = ref(false)
    const matchNews = ref([])

    // Tab 2: 球队新闻
    const teamId = ref('')
    const teamLoading = ref(false)
    const teamNews = ref([])

    // Tab 3: 联赛新闻
    const leagueId = ref('')
    const leagueLoading = ref(false)
    const leagueNews = ref([])

    // Tab 4: 热门新闻
    const hotLoading = ref(false)
    const hotNews = ref([])

    // Tab 5: 赛季综述
    const seasonLeagueId = ref('')
    const seasonId = ref('')
    const seasonLoading = ref(false)
    const seasonReview = ref([])

    // Tab 6: 伤病新闻
    const injuryTeamId = ref('')
    const injuryLoading = ref(false)
    const injuryNews = ref([])

    const sourceClass = (source) => {
      if (!source) return 'default'
      const s = source.toLowerCase()
      if (s.includes('weibo') || s.includes('微博')) return 'weibo'
      if (s.includes('twitter')) return 'twitter'
      if (s.includes('hupu') || s.includes('虎扑')) return 'hupu'
      if (s.includes('zhibo8') || s.includes('直播吧')) return 'zhibo8'
      return 'default'
    }

    const impactClass = (level) => {
      if (!level) return ''
      const l = level.toString().toLowerCase()
      if (l.includes('high') || l.includes('高') || l.includes('重大')) return 'impact-high'
      if (l.includes('medium') || l.includes('中') || l.includes('中等')) return 'impact-medium'
      if (l.includes('low') || l.includes('低') || l.includes('轻微')) return 'impact-low'
      return ''
    }

    const sentimentClass = (sentiment) => {
      if (!sentiment) return ''
      const s = sentiment.toString().toLowerCase()
      if (s.includes('positive') || s.includes('正面') || s.includes('积极')) return 'sentiment-positive'
      if (s.includes('negative') || s.includes('负面') || s.includes('消极')) return 'sentiment-negative'
      if (s.includes('neutral') || s.includes('中性') || s.includes('中立')) return 'sentiment-neutral'
      return ''
    }

    const rankClass = (idx) => {
      if (idx === 0) return 'rank-1'
      if (idx === 1) return 'rank-2'
      if (idx === 2) return 'rank-3'
      return ''
    }

    const loadMatchNews = async () => {
      if (!matchId.value) return
      matchLoading.value = true
      matchNews.value = []
      try {
        const res = await analysisAPI.getMatchNews(matchId.value)
        matchNews.value = res.data || res || []
      } catch (e) {
        console.error('加载比赛新闻失败:', e)
        matchNews.value = []
      } finally {
        matchLoading.value = false
      }
    }

    const loadTeamNews = async () => {
      if (!teamId.value) return
      teamLoading.value = true
      teamNews.value = []
      try {
        const res = await analysisAPI.getTeamNews(teamId.value)
        teamNews.value = res.data || res || []
      } catch (e) {
        console.error('加载球队新闻失败:', e)
        teamNews.value = []
      } finally {
        teamLoading.value = false
      }
    }

    const loadLeagueNews = async () => {
      if (!leagueId.value) return
      leagueLoading.value = true
      leagueNews.value = []
      try {
        const res = await analysisAPI.getLeagueNews(leagueId.value)
        leagueNews.value = res.data || res || []
      } catch (e) {
        console.error('加载联赛新闻失败:', e)
        leagueNews.value = []
      } finally {
        leagueLoading.value = false
      }
    }

    const loadHotNews = async () => {
      hotLoading.value = true
      try {
        const res = await analysisAPI.getHotNews()
        hotNews.value = res.data || res || []
      } catch (e) {
        console.error('加载热门新闻失败:', e)
        hotNews.value = []
      } finally {
        hotLoading.value = false
      }
    }

    const loadSeasonReview = async () => {
      if (!seasonLeagueId.value) return
      seasonLoading.value = true
      seasonReview.value = []
      try {
        const res = await analysisAPI.getSeasonReview(seasonLeagueId.value, seasonId.value || undefined)
        seasonReview.value = res.data || res || []
      } catch (e) {
        console.error('加载赛季综述失败:', e)
        seasonReview.value = []
      } finally {
        seasonLoading.value = false
      }
    }

    const loadInjuryNews = async () => {
      if (!injuryTeamId.value) return
      injuryLoading.value = true
      injuryNews.value = []
      try {
        const res = await analysisAPI.getInjuryNews(injuryTeamId.value)
        injuryNews.value = res.data || res || []
      } catch (e) {
        console.error('加载伤病新闻失败:', e)
        injuryNews.value = []
      } finally {
        injuryLoading.value = false
      }
    }

    const switchTab = async (key) => {
      activeTab.value = key
      if (key === 'hot' && hotNews.value.length === 0) {
        await loadHotNews()
      }
    }

    onMounted(loadHotNews)

    return {
      activeTab, tabs,
      matchId, matchLoading, matchNews, loadMatchNews,
      teamId, teamLoading, teamNews, loadTeamNews,
      leagueId, leagueLoading, leagueNews, loadLeagueNews,
      hotLoading, hotNews,
      seasonLeagueId, seasonId, seasonLoading, seasonReview, loadSeasonReview,
      injuryTeamId, injuryLoading, injuryNews, loadInjuryNews,
      sourceClass, impactClass, sentimentClass, rankClass, switchTab
    }
  }
}
</script>

<style scoped>
.news-aggregation {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
}

.card {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.header {
  padding: 16px 20px;
}

.header-content h2 {
  font-size: 18px;
  font-weight: 700;
  color: white;
  margin-bottom: 4px;
}

.header-content p {
  font-size: 12px;
  color: #6b7280;
}

.tabs {
  display: flex;
  gap: 4px;
  background: #0a0d14;
  padding: 4px;
  border-radius: 10px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  overflow-x: auto;
}

.tab-btn {
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #9ca3af;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.tab-btn.active {
  background: #151922;
  color: #10b981;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.tab-btn:hover:not(.active) {
  color: #e5e7eb;
}

.input-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  align-items: center;
}

.text-input {
  flex: 1;
  padding: 8px 12px;
  background: #0a0d14;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.text-input:focus {
  border-color: rgba(16, 185, 129, 0.5);
}

.text-input::placeholder {
  color: #6b7280;
}

.action-btn {
  padding: 8px 16px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  color: #10b981;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.action-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 新闻列表 */
.news-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.news-card {
  padding: 14px 16px;
  transition: all 0.2s;
}

.news-card:hover {
  border-color: rgba(16, 185, 129, 0.3);
  background: #1a1f2e;
}

.news-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.news-source-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-block;
}

.news-source-tag.default {
  color: #9ca3af;
  background: rgba(156, 163, 175, 0.1);
}

.news-source-tag.weibo {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}

.news-source-tag.twitter {
  color: #60a5fa;
  background: rgba(96, 165, 250, 0.1);
}

.news-source-tag.hupu {
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.news-source-tag.zhibo8 {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.news-source-tag.injury {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

/* 影响等级标签 */
.impact-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.impact-tag.impact-high {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.impact-tag.impact-medium {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}

.impact-tag.impact-low {
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

/* 热度排名 */
.hot-rank {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  color: #6b7280;
  background: #0a0d14;
  flex-shrink: 0;
}

.hot-rank.rank-1 {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.15);
}

.hot-rank.rank-2 {
  color: #9ca3af;
  background: rgba(156, 163, 175, 0.15);
}

.hot-rank.rank-3 {
  color: #b45309;
  background: rgba(180, 83, 9, 0.15);
}

.news-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  line-height: 1.4;
  margin-bottom: 6px;
}

.news-summary {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.5;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.news-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.news-time {
  font-size: 12px;
  color: #6b7280;
}

/* 情感标签 */
.news-sentiment {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 3px;
}

.news-sentiment.sentiment-positive {
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.news-sentiment.sentiment-negative {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.news-sentiment.sentiment-neutral {
  color: #9ca3af;
  background: rgba(156, 163, 175, 0.1);
}

.news-link {
  font-size: 12px;
  color: #10b981;
  text-decoration: none;
  transition: color 0.2s;
}

.news-link:hover {
  color: #34d399;
}

/* 加载/空状态 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: #6b7280;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(16, 185, 129, 0.2);
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  padding: 40px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
}

@media (max-width: 600px) {
  .tabs {
    flex-wrap: nowrap;
  }
  .input-row {
    flex-wrap: wrap;
  }
}
</style>
