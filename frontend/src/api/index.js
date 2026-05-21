// API基础配置
const API_BASE = '/api/v1'

// API请求封装
async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  })
  return response.json()
}

// 联赛相关
export const leagueAPI = {
  // 获取联赛列表
  getLeagues: () => fetchAPI('/leagues'),

  // 获取联赛详情
  getLeague: (id) => fetchAPI(`/leagues/${id}`),

  // 获取联赛可用赛季
  getSeasons: (leagueId) => fetchAPI(`/leagues/${leagueId}/seasons`),

  // 获取联赛某赛季轮次列表
  getRounds: (leagueId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/leagues/${leagueId}/rounds${query}`)
  },

  // 获取某轮次比赛
  getMatchesByRound: (leagueId, roundNum, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/leagues/${leagueId}/matches/by-round/${roundNum}${query}`)
  },

  // 获取所有可用赛季
  getAllSeasons: () => fetchAPI('/seasons'),

  // 获取积分榜
  getStandings: (leagueId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/leagues/${leagueId}/standings${query}`)
  },

  // 获取比赛列表
  getMatches: (leagueId, limit = 50, season = null) => {
    const params = new URLSearchParams({ limit })
    if (season) params.append('season', season)
    return fetchAPI(`/leagues/${leagueId}/matches?${params}`)
  },

  // 获取最新一轮比赛
  getLatestRound: (leagueId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/leagues/${leagueId}/matches/latest-round${query}`)
  },

  // 获取按日期分组的比赛
  getMatchesGrouped: (leagueId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/leagues/${leagueId}/matches/grouped${query}`)
  },

  // 获取球员统计
  getPlayerStats: (leagueId, season = null, statType = 'goals') => {
    const params = new URLSearchParams()
    if (season) params.append('season', season)
    params.append('stat_type', statType)
    return fetchAPI(`/leagues/${leagueId}/player-stats?${params}`)
  },

  // 获取联赛规则
  getLeagueRules: (leagueId) => fetchAPI(`/leagues/${leagueId}/rules`),

  // 获取联赛某赛季球队列表（含主教练、阵型）
  getLeagueTeamsSeason: (leagueId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/leagues/${leagueId}/teams-season${query}`)
  },

  // 杯赛专用API
  // 获取杯赛赛季列表
  getCupSeasons: (leagueId) => fetchAPI(`/cups/${leagueId}/seasons`),

  // 获取杯赛阶段列表
  getCupStages: (leagueId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/cups/${leagueId}/stages${query}`)
  },

  // 获取杯赛比赛数据
  getCupMatches: (leagueId, season = null, stage = null) => {
    const params = new URLSearchParams()
    if (season) params.append('season', season)
    if (stage) params.append('stage', stage)
    return fetchAPI(`/cups/${leagueId}/matches?${params}`)
  },

  // 获取杯赛小组赛数据
  getCupGroups: (leagueId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/cups/${leagueId}/groups${query}`)
  },

  // 获取杯赛淘汰赛数据
  getCupKnockout: (leagueId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/cups/${leagueId}/knockout${query}`)
  }
}

// 球队赛季相关
export const teamSeasonAPI = {
  // 获取球队某赛季信息
  getTeamSeasonInfo: (teamId, season = null) => {
    const query = season ? `?season=${season}` : ''
    return fetchAPI(`/teams/${teamId}/season-info${query}`)
  }
}

// 球队相关
export const teamAPI = {
  // 获取球队列表
  getTeams: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return fetchAPI(`/teams?${query}`)
  },

  // 获取球队详情
  getTeam: (id) => fetchAPI(`/teams/${id}`),

  // 获取球队比赛
  getMatches: (teamId, limit = 50) => fetchAPI(`/teams/${teamId}/matches?limit=${limit}`),

  // 获取球队状态
  getForm: (teamId, matches = 10) => fetchAPI(`/teams/${teamId}/form?matches=${matches}`),

  // 获取赛程密集度
  getSchedule: (teamId, days = 14) => fetchAPI(`/teams/${teamId}/schedule?days=${days}`)
}

// 比赛相关
export const matchAPI = {
  // 获取今日比赛
  getToday: () => fetchAPI('/matches/today'),

  // 获取指定日期的比赛
  getByDate: (date) => fetchAPI(`/matches/date/${date}`),

  // 获取即将开始的比赛
  getUpcoming: (days = 7) => fetchAPI(`/matches/upcoming?days=${days}`),

  // 获取比赛详情
  getMatch: (matchId) => fetchAPI(`/matches/${matchId}`),

  // 获取比赛简略分析摘要（用于首页）
  getAnalysisSummary: (matchId) => fetchAPI(`/matches/${matchId}/analysis-summary`),

  // 获取比赛全面分析（用于详情页）
  getFullAnalysis: (matchId) => fetchAPI(`/matches/${matchId}/full-analysis`)
}

// 排名相关
export const rankingAPI = {
  // FIFA国家队排名
  getFIFANational: (limit = 50) => fetchAPI(`/rankings/fifa/national?limit=${limit}`),

  // FIFA俱乐部排名
  getFIFAClub: (limit = 50) => fetchAPI(`/rankings/fifa/club?limit=${limit}`)
}

// 分析相关
export const analysisAPI = {
  // Elo评分
  getTeamElo: (teamId, includeHistory = false) => {
    const query = includeHistory ? '?include_history=true' : ''
    return fetchAPI(`/analytics/elo/${teamId}${query}`)
  },

  // Elo排名列表
  getEloRankings: (leagueId = null, limit = 50) => {
    const params = new URLSearchParams()
    if (leagueId) params.append('league_id', leagueId)
    params.append('limit', limit)
    return fetchAPI(`/analytics/elo/rankings?${params}`)
  },

  // Elo预测比赛
  getEloPrediction: (homeTeamId, awayTeamId) =>
    fetchAPI(`/analytics/elo/prediction?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}`),

  // xG预期进球
  getXGPrediction: (homeTeamId, awayTeamId, recentMatches = 10) =>
    fetchAPI(`/analytics/xg/prediction?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&recent_matches=${recentMatches}`),

  // 球队xG表现
  getTeamXGPerformance: (teamId, recentMatches = 20) =>
    fetchAPI(`/analytics/xg/team/${teamId}/performance?recent_matches=${recentMatches}`),

  // Poisson预测
  getPoissonPrediction: (homeTeamId, awayTeamId, recentMatches = 20) =>
    fetchAPI(`/analytics/poisson/prediction?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&recent_matches=${recentMatches}`),

  // 特定比分概率
  getCorrectScoreProbability: (homeTeamId, awayTeamId, homeGoals, awayGoals) =>
    fetchAPI(`/analytics/poisson/correct-score?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&home_goals=${homeGoals}&away_goals=${awayGoals}`),

  // 交锋记录分析
  getH2HAnalysis: (team1Id, team2Id, limit = 20) =>
    fetchAPI(`/analytics/h2h/analysis?team1_id=${team1Id}&team2_id=${team2Id}&limit=${limit}`),

  // 交锋常见比分
  getH2HPatterns: (team1Id, team2Id) =>
    fetchAPI(`/analytics/h2h/patterns?team1_id=${team1Id}&team2_id=${team2Id}`),

  // 球队近期状态
  getTeamForm: (teamId, recentMatches = 10) =>
    fetchAPI(`/analytics/form/team/${teamId}?recent_matches=${recentMatches}`),

  // 比较两队状态
  compareTeamsForm: (team1Id, team2Id, recentMatches = 10) =>
    fetchAPI(`/analytics/form/compare?team1_id=${team1Id}&team2_id=${team2Id}&recent_matches=${recentMatches}`),

  // 主客场表现
  getHomeAwayPerformance: (teamId, recentMatches = 20) =>
    fetchAPI(`/analytics/home-away/team/${teamId}?recent_matches=${recentMatches}`),

  // 联赛主场优势统计
  getLeagueHomeAdvantage: (leagueId, seasonId = null) => {
    const query = seasonId ? `?season_id=${seasonId}` : ''
    return fetchAPI(`/analytics/home-away/league/${leagueId}${query}`)
  },

  // 球队动机分析
  getTeamMotivation: (teamId, leagueId, seasonId) =>
    fetchAPI(`/analytics/motivation/team/${teamId}?league_id=${leagueId}&season_id=${seasonId}`),

  // 比较两队动机
  compareTeamsMotivation: (homeTeamId, awayTeamId, leagueId, seasonId) =>
    fetchAPI(`/analytics/motivation/compare?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&league_id=${leagueId}&season_id=${seasonId}`),

  // 疲劳因素分析
  getFatigueAnalysis: (homeTeamId, awayTeamId, matchDate) =>
    fetchAPI(`/analytics/motivation/fatigue?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&match_date=${matchDate}`),

  // 比赛重要性分析（为什么需要赢、不能输的理由）
  getMatchImportance: (homeTeamId, awayTeamId, leagueId, seasonId, matchDate = null) => {
    const params = new URLSearchParams()
    params.append('home_team_id', homeTeamId)
    params.append('away_team_id', awayTeamId)
    params.append('league_id', leagueId)
    params.append('season_id', seasonId)
    if (matchDate) params.append('match_date', matchDate)
    return fetchAPI(`/analytics/importance?${params}`)
  },

  // 球队利好利空因素
  getTeamFactors: (teamId, days = 30) =>
    fetchAPI(`/analytics/factors/team/${teamId}?days=${days}`),

  // 比较两队利好利空
  compareTeamsFactors: (homeTeamId, awayTeamId, days = 30) =>
    fetchAPI(`/analytics/factors/compare?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&days=${days}`),

  // 球员状态汇总
  getTeamPlayerStatus: (teamId) =>
    fetchAPI(`/analytics/factors/team/${teamId}/player-status`),

  // 综合预测（整合所有维度）
  getComprehensivePrediction: (homeTeamId, awayTeamId, leagueId = null, seasonId = null, matchDate = null) => {
    const params = new URLSearchParams()
    params.append('home_team_id', homeTeamId)
    params.append('away_team_id', awayTeamId)
    if (leagueId) params.append('league_id', leagueId)
    if (seasonId) params.append('season_id', seasonId)
    if (matchDate) params.append('match_date', matchDate)
    return fetchAPI(`/analytics/predict/comprehensive?${params}`)
  },

  // 快速预测
  getQuickPrediction: (homeTeamId, awayTeamId) =>
    fetchAPI(`/analytics/predict/quick?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}`),

  // 根据比赛ID预测
  getMatchPrediction: (matchId) =>
    fetchAPI(`/analytics/predict/match/${matchId}`),

  // 比赛前瞻报告
  getMatchPreview: (matchId) =>
    fetchAPI(`/analytics/preview/match/${matchId}`),

  // 批量预测
  batchPrediction: (matches) =>
    fetchAPI('/analytics/predict/batch', {
      method: 'POST',
      body: JSON.stringify(matches)
    }),

  // 旧接口兼容
  getHeadToHead: (team1Id, team2Id) => analysisAPI.getH2HAnalysis(team1Id, team2Id),
  searchTeams: (q) => fetchAPI(`/analytics/search?q=${encodeURIComponent(q)}`),
  predictMatch: (homeTeamId, awayTeamId) => analysisAPI.getQuickPrediction(homeTeamId, awayTeamId),
  getXGAnalysis: (homeTeamId, awayTeamId) => analysisAPI.getXGPrediction(homeTeamId, awayTeamId),
  compareTeams: (team1Id, team2Id) => analysisAPI.compareTeamsForm(team1Id, team2Id),
  getMatchContext: (homeTeamId, awayTeamId, leagueId = null, matchDate = null) => {
    let query = `home_team_id=${homeTeamId}&away_team_id=${awayTeamId}`
    if (leagueId) query += `&league_id=${leagueId}`
    if (matchDate) query += `&match_date=${matchDate}`
    return fetchAPI(`/analytics/match-context?${query}`)
  },
  getRestDays: (homeTeamId, awayTeamId, matchDate = null) => {
    let query = `home_team_id=${homeTeamId}&away_team_id=${awayTeamId}`
    if (matchDate) query += `&match_date=${matchDate}`
    return fetchAPI(`/analytics/rest-days?${query}`)
  },
  getSeasonSituation: (teamId, leagueId) => fetchAPI(`/analytics/season-situation?team_id=${teamId}&league_id=${leagueId}`),
  getFullAnalysis: (homeTeamId, awayTeamId, leagueId = null, matchDate = null) =>
    analysisAPI.getComprehensivePrediction(homeTeamId, awayTeamId, leagueId, null, matchDate),
  getH2HPsychology: (team1Id, team2Id) => analysisAPI.getH2HAnalysis(team1Id, team2Id),
  getMatchImportance: (homeTeamId, awayTeamId, leagueId, matchDate = null) => {
    let query = `home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&league_id=${leagueId}`
    if (matchDate) query += `&match_date=${matchDate}`
    return fetchAPI(`/analytics/match-importance?${query}`)
  },
  getRecentFormTrend: (teamId, matchesCount = 10) => analysisAPI.getTeamForm(teamId, matchesCount)
}

// 同步相关
export const syncAPI = {
  // 检查是否需要同步
  checkNeeded: () => fetchAPI('/sync/check-needed'),

  // 获取同步状态
  getStatus: () => fetchAPI('/sync/status'),

  // 同步已结束比赛结果
  syncFinished: (days = 7) => fetchAPI(`/sync/finished?days=${days}`, { method: 'POST' }),

  // 同步未来赛程
  syncUpcoming: (months = 3) => fetchAPI(`/sync/upcoming?months=${months}`, { method: 'POST' }),

  // 完整同步
  fullSync: () => fetchAPI('/sync/full', { method: 'POST' })
}