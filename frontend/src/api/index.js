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

  // 获取日期范围内的比赛
  getByDateRange: (startDate, endDate) => fetchAPI(`/matches/date-range?from_date=${startDate}&to_date=${endDate}`),

  // 获取即将开始的比赛
  getUpcoming: (days = 7) => fetchAPI(`/matches/upcoming?days=${days}`),

  // 获取比赛详情
  getMatch: (matchId) => fetchAPI(`/matches/${matchId}`),

  // 获取比赛简略分析摘要（用于首页）
  getAnalysisSummary: (matchId) => fetchAPI(`/analytics/preview/match/${matchId}`),

  // 获取比赛全面分析（用于详情页）
  getFullAnalysis: (matchId) => fetchAPI(`/analytics/predict/match/${matchId}`)
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
  getRecentFormTrend: (teamId, matchesCount = 10) => analysisAPI.getTeamForm(teamId, matchesCount),

  // ==================== 盘路分析 ====================
  // 球队赢盘率 (ATS)
  getTeamATS: (teamId, leagueId = null, seasonId = null, limit = 20) => {
    const params = new URLSearchParams({ limit })
    if (leagueId) params.append('league_id', leagueId)
    if (seasonId) params.append('season_id', seasonId)
    return fetchAPI(`/analytics/handicap/ats/${teamId}?${params}`)
  },
  // 球队大小球趋势
  getTeamOverUnder: (teamId, leagueId = null, seasonId = null, limit = 20) => {
    const params = new URLSearchParams({ limit })
    if (leagueId) params.append('league_id', leagueId)
    if (seasonId) params.append('season_id', seasonId)
    return fetchAPI(`/analytics/handicap/over-under/${teamId}?${params}`)
  },
  // 球队盘路趋势
  getTeamHandicapTrend: (teamId, lastN = 10) =>
    fetchAPI(`/analytics/handicap/trend/${teamId}?last_n=${lastN}`),
  // 比较两队盘路
  compareTeamsHandicap: (homeTeamId, awayTeamId) =>
    fetchAPI(`/analytics/handicap/compare/${homeTeamId}/${awayTeamId}`),

  // ==================== 效率分析 ====================
  // 进攻效率
  getAttackingEfficiency: (teamId, leagueId = null, seasonId = null, limit = 20) => {
    const params = new URLSearchParams({ limit })
    if (leagueId) params.append('league_id', leagueId)
    if (seasonId) params.append('season_id', seasonId)
    return fetchAPI(`/analytics/efficiency/attacking/${teamId}?${params}`)
  },
  // 防守效率
  getDefensiveEfficiency: (teamId, leagueId = null, seasonId = null, limit = 20) => {
    const params = new URLSearchParams({ limit })
    if (leagueId) params.append('league_id', leagueId)
    if (seasonId) params.append('season_id', seasonId)
    return fetchAPI(`/analytics/efficiency/defensive/${teamId}?${params}`)
  },
  // 控球效率
  getPossessionEfficiency: (teamId, leagueId = null, seasonId = null, limit = 20) => {
    const params = new URLSearchParams({ limit })
    if (leagueId) params.append('league_id', leagueId)
    if (seasonId) params.append('season_id', seasonId)
    return fetchAPI(`/analytics/efficiency/possession/${teamId}?${params}`)
  },
  // 比较两队效率
  compareTeamsEfficiency: (homeTeamId, awayTeamId, leagueId = null, seasonId = null) => {
    const params = new URLSearchParams()
    if (leagueId) params.append('league_id', leagueId)
    if (seasonId) params.append('season_id', seasonId)
    return fetchAPI(`/analytics/efficiency/compare/${homeTeamId}/${awayTeamId}?${params}`)
  },

  // ==================== 换帅效应 ====================
  // 换帅效应分析
  getManagerChangeEffect: (teamId, changeDate, matchesBefore = 10, matchesAfter = 10) =>
    fetchAPI(`/analytics/manager-change/${teamId}?change_date=${changeDate}&matches_before=${matchesBefore}&matches_after=${matchesAfter}`),
  // 最近换帅记录
  getRecentManagerChanges: (limit = 20) =>
    fetchAPI(`/analytics/manager-changes/recent?limit=${limit}`),
  // 联赛换帅效果
  getLeagueManagerChanges: (leagueId, seasonId) =>
    fetchAPI(`/analytics/manager-changes/league/${leagueId}/${seasonId}`),

  // ==================== 爆冷分析 ====================
  // 比赛爆冷潜力
  analyzeUpsetPotential: (homeTeamId, awayTeamId, leagueId = null, seasonId = null) => {
    const params = new URLSearchParams({ home_team_id: homeTeamId, away_team_id: awayTeamId })
    if (leagueId) params.append('league_id', leagueId)
    if (seasonId) params.append('season_id', seasonId)
    return fetchAPI(`/analytics/upset/analysis?${params}`)
  },
  // 扫描爆冷比赛
  scanUpsetMatches: (leagueId = null, matchDate = null, minProbability = 25) => {
    const params = new URLSearchParams({ min_probability: minProbability })
    if (leagueId) params.append('league_id', leagueId)
    if (matchDate) params.append('match_date', matchDate)
    return fetchAPI(`/analytics/upset/scan?${params}`)
  },
  // 爆冷赢球历史
  getGiantKillingHistory: (teamId, limit = 20) =>
    fetchAPI(`/analytics/upset/giant-killing/${teamId}?limit=${limit}`),

  // ==================== 赛季推理 ====================
  // 球队赛季形势
  getTeamSeasonScenario: (teamId, leagueId, seasonId) =>
    fetchAPI(`/analytics/season-scenario/${teamId}?league_id=${leagueId}&season_id=${seasonId}`),
  // 轮换风险
  getRotationRisk: (teamId, leagueId, seasonId) =>
    fetchAPI(`/analytics/rotation-risk/${teamId}?league_id=${leagueId}&season_id=${seasonId}`),
  // 6分战分析
  getSixPointerAnalysis: (homeTeamId, awayTeamId, leagueId, seasonId) =>
    fetchAPI(`/analytics/six-pointer/${homeTeamId}/${awayTeamId}?league_id=${leagueId}&season_id=${seasonId}`),
  // 争冠形势
  getTitleRace: (leagueId, seasonId) =>
    fetchAPI(`/analytics/title-race/${leagueId}/${seasonId}`),
  // 保级形势
  getRelegationBattle: (leagueId, seasonId) =>
    fetchAPI(`/analytics/relegation-battle/${leagueId}/${seasonId}`),

  // ==================== 价值投注 ====================
  // 比赛价值注
  getMatchValueBets: (matchId) =>
    fetchAPI(`/analytics/value-bet/match/${matchId}`),
  // 扫描价值注
  scanValueBets: (days = 7, minEdge = 0.05) =>
    fetchAPI(`/analytics/value-bet/scan?days=${days}&min_edge=${minEdge}`),
  // 分析价值注
  analyzeValueBets: (prediction, odds) =>
    fetchAPI('/analytics/value-bet/analyze', {
      method: 'POST',
      body: JSON.stringify({ prediction, odds })
    }),
  // 套利机会
  findArbitrage: (oddsList) =>
    fetchAPI('/analytics/value-bet/arbitrage', {
      method: 'POST',
      body: JSON.stringify({ odds_list: oddsList })
    }),
  // Kelly公式
  calculateKelly: (predictionProb, odds, fractional = 0.5) =>
    fetchAPI(`/analytics/value-bet/kelly?prediction_prob=${predictionProb}&odds=${odds}&fractional=${fractional}`),

  // ==================== 裁判分析 ====================
  getRefereeList: (limit = 50) =>
    fetchAPI(`/analytics/referee/list?limit=${limit}`),
  getRefereeStats: (refereeName) =>
    fetchAPI(`/analytics/referee/${encodeURIComponent(refereeName)}`),
  getRefereeImpact: (matchId) =>
    fetchAPI(`/analytics/referee/impact/${matchId}`),

  // ==================== 场地分析 ====================
  calculateDistance: (city1, city2) =>
    fetchAPI(`/analytics/venue/distance?city1=${encodeURIComponent(city1)}&city2=${encodeURIComponent(city2)}`),
  getVenueImpact: (matchId) =>
    fetchAPI(`/analytics/venue/impact/${matchId}`),
  getTeamHomePerformance: (teamId, recentMatches = 20) =>
    fetchAPI(`/analytics/venue/team/${teamId}/home-performance?recent_matches=${recentMatches}`),

  // ==================== 天气分析 ====================
  getCityWeather: (city) =>
    fetchAPI(`/analytics/weather/city/${encodeURIComponent(city)}`),
  getMatchWeather: (matchId) =>
    fetchAPI(`/analytics/weather/match/${matchId}`),

  // ==================== 疲劳分析(独立) ====================
  getTeamFatigue: (teamId, matchDate = null) => {
    const query = matchDate ? `?match_date=${matchDate}` : ''
    return fetchAPI(`/analytics/fatigue/team/${teamId}${query}`)
  },
  getFixtureDensity: (teamId, days = 14) =>
    fetchAPI(`/analytics/fatigue/team/${teamId}/fixture-density?days=${days}`),
  compareTeamsFatigue: (homeTeamId, awayTeamId, matchDate) =>
    fetchAPI(`/analytics/fatigue/compare?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&match_date=${matchDate}`),
  getMatchFatigue: (matchId) =>
    fetchAPI(`/analytics/fatigue/match/${matchId}`),

  // ==================== 联赛影响 ====================
  getLeagueStyle: (leagueId) =>
    fetchAPI(`/analytics/league-impact/style/${leagueId}`),
  getSeasonRules: (leagueId, seasonId) =>
    fetchAPI(`/analytics/league-impact/rules/${leagueId}/${seasonId}`),
  compareLeagueStyles: (leagueId1, leagueId2) =>
    fetchAPI(`/analytics/league-impact/compare/${leagueId1}/${leagueId2}`),
  getLeagueRankImpact: (leagueId, teamId, seasonId) =>
    fetchAPI(`/analytics/league-impact/rank/${leagueId}?team_id=${teamId}&season_id=${seasonId}`),
  getLeagueStandings: (leagueId, seasonId) =>
    fetchAPI(`/analytics/league-impact/standings/${leagueId}/${seasonId}`),
  getMatchImpact: (matchId) =>
    fetchAPI(`/analytics/league-impact/match/${matchId}`),
  getRelegationImpact: (teamId, leagueId, seasonId) =>
    fetchAPI(`/analytics/league-impact/team/${teamId}/relegation?league_id=${leagueId}&season_id=${seasonId}`),
  getTitleImpact: (teamId, leagueId, seasonId) =>
    fetchAPI(`/analytics/league-impact/team/${teamId}/title?league_id=${leagueId}&season_id=${seasonId}`),

  // ==================== ML预测 ====================
  getMLPrediction: (matchId) =>
    fetchAPI(`/analytics/ml/predict/match/${matchId}`),
  getModelComparison: (matchId) =>
    fetchAPI(`/analytics/ml/model-comparison/${matchId}`),
  getFeatureImportance: (matchId) =>
    fetchAPI(`/analytics/ml/feature-importance/${matchId}`),
  mlPredict: (homeTeamId, awayTeamId, matchDate) =>
    fetchAPI(`/analytics/ml/predict?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&match_date=${matchDate}`),
  extractFeatures: (homeTeamId, awayTeamId, matchDate) =>
    fetchAPI(`/analytics/ml/features?home_team_id=${homeTeamId}&away_team_id=${awayTeamId}&match_date=${matchDate}`),
  blendPredictions: (mlPred, eloPred, poissonPred, mlWeight = 0.35, eloWeight = 0.35, poissonWeight = 0.30) =>
    fetchAPI(`/analytics/ml/blend?ml_weight=${mlWeight}&elo_weight=${eloWeight}&poisson_weight=${poissonWeight}`, {
      method: 'POST',
      body: JSON.stringify({ ml_prediction: mlPred, elo_prediction: eloPred, poisson_prediction: poissonPred })
    }),

  // ==================== xG高级 ====================
  getMatchXG: (matchId) =>
    fetchAPI(`/analytics/xg/match/${matchId}`),
  getTeamXGTrend: (teamId, limit = 20) =>
    fetchAPI(`/analytics/xg/team/${teamId}/trend?limit=${limit}`),
  getXGVsActual: (teamId) =>
    fetchAPI(`/analytics/xg/team/${teamId}/vs-actual`),
  getTeamStatsBombXG: (teamId, limit = 20) =>
    fetchAPI(`/analytics/xg/team/${teamId}/statsbomb-stats?limit=${limit}`),
  getLeagueXGRankings: (leagueId, seasonId) =>
    fetchAPI(`/analytics/xg/league/${leagueId}/season/${seasonId}/rankings`),

  // ==================== 泊松分布高级 ====================
  getTeamGoalDistribution: (teamId, isHome = true, recentMatches = 30) =>
    fetchAPI(`/analytics/poisson/team/${teamId}/distribution?is_home=${isHome}&recent_matches=${recentMatches}`),

  // ==================== 新闻聚合 ====================
  getMatchNews: (matchId) =>
    fetchAPI(`/analytics/news/match/${matchId}`),
  getLeagueNews: (leagueId) =>
    fetchAPI(`/analytics/news/league/${leagueId}`),
  getHotNews: () =>
    fetchAPI('/analytics/news/hot'),
  getSeasonReview: (leagueId, seasonId) =>
    fetchAPI(`/analytics/news/season-review/${leagueId}/${seasonId}`),
  getInjuryNews: (teamId) =>
    fetchAPI(`/analytics/news/injury/${teamId}`),
  aggregateNews: (teamName = null) => {
    const query = teamName ? `?team_name=${encodeURIComponent(teamName)}` : ''
    return fetchAPI(`/analytics/news/aggregate${query}`)
  },
  getWeiboNews: (keyword = '足球') =>
    fetchAPI(`/analytics/news/weibo?keyword=${encodeURIComponent(keyword)}`),
  getTwitterNews: (accounts = null) => {
    const query = accounts ? `?accounts=${encodeURIComponent(accounts)}` : ''
    return fetchAPI(`/analytics/news/twitter${query}`)
  },
  getHupuNews: () => fetchAPI('/analytics/news/hupu'),
  getZhibo8News: () => fetchAPI('/analytics/news/zhibo8'),
  getTeamNews: (teamName) =>
    fetchAPI(`/analytics/news/team/${encodeURIComponent(teamName)}`),

  // ==================== 实时数据(Sofascore) ====================
  getLiveMatches: () => fetchAPI('/analytics/live/matches'),
  getUpcomingLive: (date = null) => {
    const query = date ? `?date=${date}` : ''
    return fetchAPI(`/analytics/live/upcoming${query}`)
  },
  getMatchEvents: (eventId) =>
    fetchAPI(`/analytics/live/match/${eventId}/events`),
  getMatchStatistics: (eventId) =>
    fetchAPI(`/analytics/live/match/${eventId}/statistics`),
  getPlayerRatings: (eventId) =>
    fetchAPI(`/analytics/live/match/${eventId}/ratings`),
  searchLiveTeam: (teamName) =>
    fetchAPI(`/analytics/live/team/search?team_name=${encodeURIComponent(teamName)}`),
  getTeamLiveMatches: (teamId) =>
    fetchAPI(`/analytics/live/team/${teamId}/matches`),

  // ==================== 赔率/盘口 ====================
  getUpcomingOdds: (league = null) => {
    const query = league ? `?league=${league}` : ''
    return fetchAPI(`/analytics/odds/upcoming${query}`)
  },
  getOddsLeagues: () => fetchAPI('/analytics/odds/leagues'),
  getBestOdds: (homeOdds, drawOdds, awayOdds) =>
    fetchAPI(`/analytics/odds/best?home_odds=${homeOdds}&draw_odds=${drawOdds}&away_odds=${awayOdds}`),
  getOddsApiUsage: () => fetchAPI('/analytics/odds/api-usage'),

  // ==================== 时区 ====================
  getCurrentTimes: () => fetchAPI('/analytics/time/current'),
  convertTime: (utcTime, targetCity = null) => {
    const params = new URLSearchParams({ utc_time: utcTime })
    if (targetCity) params.append('target_city', targetCity)
    return fetchAPI(`/analytics/time/convert?${params}`)
  },
  getMatchLocalTimes: (matchId) =>
    fetchAPI(`/analytics/time/match/${matchId}`),
  getTeamTimezoneInfo: (teamName) =>
    fetchAPI(`/analytics/time/team/${encodeURIComponent(teamName)}`),
  getSupportedCities: () => fetchAPI('/analytics/time/cities')
}

// 同步相关
export const syncAPI = {
  // 检查是否需要同步
  checkNeeded: () => fetchAPI('/sync/check'),

  // 获取同步状态
  getStatus: () => fetchAPI('/sync/status'),

  // 获取数据缺口报告
  getGapReport: () => fetchAPI('/sync/gap-report'),

  // 同步国家中文名
  syncCountryCN: () => fetchAPI('/sync/country-cn', { method: 'POST' }),

  // 同步联赛规则
  syncLeagueRules: () => fetchAPI('/sync/league-rules', { method: 'POST' }),

  // AI翻译球员中文名
  syncPlayerCN: (limit = 200) => fetchAPI(`/sync/player-cn?limit=${limit}`, { method: 'POST' }),

  // AI翻译联赛中文名
  syncLeagueCN: (limit = 200) => fetchAPI(`/sync/league-cn?limit=${limit}`, { method: 'POST' }),

  // API获取球队中文名（非AI）
  syncTeamCNApi: (limit = 500) => fetchAPI(`/sync/team-cn-api?limit=${limit}`, { method: 'POST' }),

  // API获取联赛中文名（非AI）
  syncLeagueCNApi: (limit = 200) => fetchAPI(`/sync/league-cn-api?limit=${limit}`, { method: 'POST' }),

  // 修复比赛season_id
  fixSeasonIds: () => fetchAPI('/sync/fix-season-ids', { method: 'POST' }),

  // 同步已结束比赛结果
  syncFinished: (days = 7) => fetchAPI(`/sync/events?days=${days}`, { method: 'POST' }),

  // 同步未来赛程
  syncUpcoming: () => fetchAPI('/sync/future', { method: 'POST' }),

  // 完整同步
  fullSync: () => fetchAPI('/sync/full', { method: 'POST' }),

  // 查询同步任务进度
  getProgress: (taskName) => fetchAPI(`/sync/progress/${taskName}`),

  // 列出所有同步任务
  listTasks: () => fetchAPI('/sync/tasks')
}

// 预测追踪与闭环学习
export const trackingAPI = {
  // 获取准确率指标
  getAccuracy: (modelVersion = null, days = 30) => {
    const params = new URLSearchParams({ days })
    if (modelVersion) params.append('model_version', modelVersion)
    return fetchAPI(`/analytics/tracking/accuracy?${params}`)
  },

  // 获取待验证预测
  getPendingValidations: () => fetchAPI('/analytics/tracking/pending-validations'),

  // 验证已结束比赛的预测
  validatePredictions: () => fetchAPI('/analytics/tracking/validate', { method: 'POST' }),

  // 批量验证
  validateBatch: (matchIds) =>
    fetchAPI('/analytics/tracking/validate-batch', {
      method: 'POST',
      body: JSON.stringify(matchIds)
    }),

  // 记录单场比赛预测
  logPrediction: (matchId) => fetchAPI(`/analytics/tracking/log/${matchId}`, { method: 'POST' }),

  // 批量记录即将开始的比赛预测
  logUpcoming: (days = 7) => fetchAPI(`/analytics/tracking/log-upcoming?days=${days}`, { method: 'POST' }),

  // 获取各维度准确率
  getDimensionAccuracy: (modelVersion = null) => {
    const query = modelVersion ? `?model_version=${modelVersion}` : ''
    return fetchAPI(`/analytics/tracking/dimension-accuracy${query}`)
  },

  // 优化权重
  optimizeWeights: (force = false) => fetchAPI(`/analytics/tracking/optimize-weights?force=${force}`, { method: 'POST' }),

  // 获取权重历史
  getWeightHistory: () => fetchAPI('/analytics/tracking/weight-history'),

  // 回滚权重
  rollbackWeights: (version) => fetchAPI(`/analytics/tracking/rollback-weights?version=${version}`, { method: 'POST' }),

  // 执行完整闭环学习周期
  runFullCycle: () => fetchAPI('/analytics/tracking/run-full-cycle', { method: 'POST' })
}

// 日循环相关
export const cycleAPI = {
  // 获取日循环状态
  getStatus: () => fetch('/api/cycle/status').then(r => r.json()),

  // 获取今日预测
  getPredictions: (date = null) => {
    const query = date ? `?date=${date}` : ''
    return fetch(`/api/cycle/predictions${query}`).then(r => r.json())
  },

  // 获取TOP3价值投注
  getTop3: () => fetch('/api/cycle/top3').then(r => r.json()),

  // 手动触发日循环
  run: (mode) => fetch(`/api/cycle/run/${mode}`, { method: 'POST' }).then(r => r.json()),

  // 获取调度器状态
  getSchedulerStatus: () => fetch('/api/scheduler/status').then(r => r.json()),
}

// 投注ROI相关
export const betsAPI = {
  // 获取ROI统计
  getROI: () => fetch('/api/bets/roi').then(r => r.json()),

  // 手动结算
  settle: () => fetch('/api/bets/settle', { method: 'POST' }).then(r => r.json()),
}

// 回测相关
export const backtestAPI = {
  // 运行回测
  run: (days = 30, stake = 100) => fetch(`/api/backtest?days=${days}&stake=${stake}`).then(r => r.json()),

  // oddsfe回测结果
  getOddsfeResults: () => fetch('/api/oddsfe-backtest').then(r => r.json()),
}

// 准确率趋势
export const accuracyTrendAPI = {
  get: (days = 30) => fetch(`/api/accuracy_trend?days=${days}`).then(r => r.json()),
}