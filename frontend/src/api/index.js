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

function buildQuery(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) {
      value.forEach(item => {
        if (item !== undefined && item !== null && item !== '') {
          query.append(key, item)
        }
      })
      return
    }
    query.append(key, value)
  })
  const text = query.toString()
  return text ? `?${text}` : ''
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
  getStatus: () => fetchAPI('/cycle/status'),

  // 获取今日预测
  getPredictions: (date = null) => {
    const query = date ? `?date=${date}` : ''
    return fetchAPI(`/cycle/predictions${query}`)
  },

  // 获取TOP3价值投注
  getTop3: () => fetchAPI('/cycle/top3'),

  // 手动触发日循环
  run: (mode) => fetchAPI(`/cycle/run/${mode}`, { method: 'POST' }),

  // 获取调度器状态
  getSchedulerStatus: () => fetch('/api/scheduler/status').then(r => r.json()),

  // 暂停自动调度
  pauseScheduler: () => fetch('/api/scheduler/pause', { method: 'POST' }).then(r => r.json()),

  // 恢复自动调度
  resumeScheduler: () => fetch('/api/scheduler/resume', { method: 'POST' }).then(r => r.json()),

  // 立即触发调度任务
  runSchedulerJob: (jobId) => fetch(`/api/scheduler/run/${jobId}`, { method: 'POST' }).then(r => r.json()),
}

// 投注ROI相关
export const betsAPI = {
  // 获取ROI统计
  getROI: () => fetchAPI('/bets/roi'),

  // 手动结算
  settle: () => fetchAPI('/bets/settle', { method: 'POST' }),
}

// 回测相关
export const backtestAPI = {
  // 运行回测
  run: (days = 30, stake = 100) => fetchAPI(`/backtest?days=${days}&stake=${stake}`),

  // oddsfe回测结果
  getOddsfeResults: () => fetchAPI('/oddsfe-backtest'),
}

// 准确率趋势
export const accuracyTrendAPI = {
  get: (days = 30) => fetchAPI(`/accuracy_trend?days=${days}`),
}

// 用户设置与收藏
export const userAPI = {
  // 设置
  getSettings: () => fetchAPI('/user/settings'),
  saveSettings: (settings) => fetchAPI('/user/settings', {
    method: 'POST',
    body: JSON.stringify({ settings })
  }),
  // 收藏
  getFavorites: (itemType = null) => {
    const query = itemType ? `?item_type=${itemType}` : ''
    return fetchAPI(`/user/favorites${query}`)
  },
  addFavorite: (itemType, itemId, itemName = '', extra = {}) => fetchAPI('/user/favorites', {
    method: 'POST',
    body: JSON.stringify({ item_type: itemType, item_id: String(itemId), item_name: itemName, extra })
  }),
  removeFavorite: (itemType, itemId) => fetchAPI(`/user/favorites/${itemType}/${itemId}`, { method: 'DELETE' }),
  // 联赛白名单管控
  getLeaguesCatalog: () => fetchAPI('/user/leagues-catalog'),
  getVisibleLeagues: () => fetchAPI('/user/visible-leagues'),
}

// 体彩分析相关
export const lotteryAPI = {
  // 获取准确率
  getAccuracy: (days = 30) => fetchAPI(`/lottery/accuracy?days=${days}`),

  // 单场分析
  analyzeMatch: (lotteryMatchId, force = true) => fetchAPI(`/lottery/analyze/${lotteryMatchId}?force=${force}&sync=true`, { method: 'POST' }),

  // 批量分析
  analyzeBatch: (date = null, matchIds = null, force = true) => {
    const body = {}
    if (date) body.date = date
    if (matchIds) body.match_ids = matchIds
    return fetchAPI(`/lottery/analyze-batch?force=${force}`, {
      method: 'POST',
      body: JSON.stringify(body)
    })
  },

  // 复盘数据
  getReview: (days = 30, playType = null, correct = null) => {
    const params = new URLSearchParams({ days })
    if (playType) params.append('play_type', playType)
    if (correct !== null) params.append('correct', correct)
    return fetchAPI(`/lottery/review?${params}`)
  },

  // 健康检查
  getHealth: () => fetchAPI('/lottery/health'),

  // 数据完整度
  getDataCompleteness: (date = null) =>
    fetchAPI(`/lottery/data-completeness${buildQuery({ date })}`),

  getDataCompletenessRange: ({ startDate, endDate, limitPerDay = 200 } = {}) =>
    fetchAPI(`/lottery/data-completeness/range${buildQuery({
      start_date: startDate,
      end_date: endDate,
      limit_per_day: limitPerDay,
    })}`),

  getAutomationAudit: ({
    dateFrom = null,
    dateTo = null,
    recentHours = 24,
    staleRunningHours = 6,
    duplicateThreshold = 10,
  } = {}) => fetchAPI(`/lottery/automation-audit${buildQuery({
    date_from: dateFrom,
    date_to: dateTo,
    recent_hours: recentHours,
    stale_running_hours: staleRunningHours,
    duplicate_threshold: duplicateThreshold,
  })}`),

  getAutomationDashboard: ({
    dateFrom = null,
    dateTo = null,
    league = '世界杯',
    recentHours = 24,
  } = {}) => fetchAPI(`/lottery/automation-dashboard${buildQuery({
    date_from: dateFrom,
    date_to: dateTo,
    league,
    recent_hours: recentHours,
  })}`),

  getAutomationControl: () => fetchAPI('/lottery/automation-control'),

  startAutomationControl: ({
    runNow = true,
    workers = 3,
    historicalDates = 1,
    maxEvents = 6,
    maxAnalysis = 10,
    maxIntelligence = 6,
    maxValidationDates = 1,
    fetchLiveOu = true,
    networkIntelligence = true,
    includeLearning = true,
  } = {}) => fetchAPI(`/lottery/automation-control/start${buildQuery({
    run_now: runNow,
    workers,
    historical_dates: historicalDates,
    max_events: maxEvents,
    max_analysis: maxAnalysis,
    max_intelligence: maxIntelligence,
    max_validation_dates: maxValidationDates,
    fetch_live_ou: fetchLiveOu,
    network_intelligence: networkIntelligence,
    include_learning: includeLearning,
  })}`, { method: 'POST' }),

  pauseAutomationControl: () => fetchAPI('/lottery/automation-control/pause', { method: 'POST' }),

  stopAutomationControl: () => fetchAPI('/lottery/automation-control/stop', { method: 'POST' }),

  runAutomationCenter: ({
    mode = 'mixed',
    dateFrom = null,
    dateTo = null,
    league = '世界杯',
    historicalDates = 1,
    workers = 3,
    taskTimeout = 300,
    maxEvents = 6,
    maxAnalysis = 10,
    maxIntelligence = 6,
    maxValidationDates = 1,
    fetchLiveOu = true,
    networkIntelligence = true,
    includeLearning = true,
    forceAnalysis = false,
    forceValidation = false,
    forceLearning = false,
    dryRun = false,
    background = true,
  } = {}) => fetchAPI(`/lottery/automation-center/run${buildQuery({
    mode,
    date_from: dateFrom,
    date_to: dateTo,
    league,
    historical_dates: historicalDates,
    workers,
    task_timeout: taskTimeout,
    max_events: maxEvents,
    max_analysis: maxAnalysis,
    max_intelligence: maxIntelligence,
    max_validation_dates: maxValidationDates,
    fetch_live_ou: fetchLiveOu,
    network_intelligence: networkIntelligence,
    include_learning: includeLearning,
    force_analysis: forceAnalysis,
    force_validation: forceValidation,
    force_learning: forceLearning,
    dry_run: dryRun,
    background,
  })}`, { method: 'POST' }),

  retryAutomationFailures: ({
    runId,
    background = true,
    workers = 2,
    taskKey = null,
    taskIndex = null,
  } = {}) => fetchAPI(`/lottery/automation-center/retry-failed${buildQuery({
    run_id: runId,
    task_key: taskKey,
    task_index: taskIndex,
    background,
    workers,
  })}`, { method: 'POST' }),

  // oddsfe赛果/半场证据补齐
  syncEventDetails: ({
    dateFrom = null,
    dateTo = null,
    background = false,
    dryRun = false,
    fetchSchedule = false,
    includeScheduleOnly = true,
    maxEvents = 4,
    batches = 3,
    batchGapSeconds = 2,
    schedulePaddingDays = 1,
  } = {}) => fetchAPI(`/lottery/sync-oddsfe-event-details${buildQuery({
    date_from: dateFrom,
    date_to: dateTo,
    background,
    dry_run: dryRun,
    fetch_schedule: fetchSchedule,
    include_schedule_only: includeScheduleOnly,
    max_events: maxEvents,
    batches,
    batch_gap_seconds: batchGapSeconds,
    schedule_padding_days: schedulePaddingDays,
  })}`, { method: 'POST' }),

  // 赔率数据
  syncOddsfeOuLines: ({
    dateFrom = null,
    dateTo = null,
    days = 21,
    background = true,
    dryRun = false,
    fetchLive = true,
    maxEvents = 8,
    reanalyze = false,
  } = {}) => fetchAPI(`/lottery/sync-oddsfe-ou-lines${buildQuery({
    date_from: dateFrom,
    date_to: dateTo,
    days,
    background,
    dry_run: dryRun,
    fetch_live: fetchLive,
    max_events: maxEvents,
    reanalyze,
  })}`, { method: 'POST' }),

  getOdds: (lotteryMatchId) => fetchAPI(`/lottery/odds/${lotteryMatchId}`),

  // 手动修正/录入赛果（带后端审计）
  correctResult: (lotteryMatchId, payload) => fetchAPI(`/lottery/results/${encodeURIComponent(lotteryMatchId)}/correct`, {
    method: 'POST',
    body: JSON.stringify(payload || {})
  }),

  refreshResult: (lotteryMatchId, { overwrite = true } = {}) =>
    fetchAPI(`/lottery/results/${encodeURIComponent(lotteryMatchId)}/refresh${buildQuery({ overwrite })}`, { method: 'POST' }),

  getResultCorrections: (lotteryMatchId) =>
    fetchAPI(`/lottery/results/${encodeURIComponent(lotteryMatchId)}/corrections`),

  // 预测报告
  getPrediction: (lotteryMatchId) => fetchAPI(`/lottery/prediction/${lotteryMatchId}`),

  // 今日比赛列表
  getMatches: (date = null) => {
    const query = date ? `?date=${date}` : ''
    return fetchAPI(`/lottery/matches${query}`)
  },

  // 模型版本+权重+gate
  getModelStatus: () => fetchAPI('/lottery/model-status'),

  // 重分析变更历史
  getReanalysisChanges: (lotteryMatchId) => fetchAPI(`/lottery/reanalysis-changes/${lotteryMatchId}`),

  // 准确率趋势
  getAccuracyTrend: ({ days = 30, playType = null, granularity = 'day' } = {}) =>
    fetchAPI(`/lottery/accuracy-trend${buildQuery({ days, play_type: playType, granularity })}`),

  // 模型基线对比
  getBaselineComparison: ({ playType = 'spf', days = 30 } = {}) =>
    fetchAPI(`/lottery/baseline-comparison${buildQuery({ play_type: playType, days })}`),

  // 时间分割基线对比(train/validation/test)
  getTimeSplitComparison: ({ playType = 'spf', totalDays = 90 } = {}) =>
    fetchAPI(`/lottery/time-split-comparison${buildQuery({ play_type: playType, total_days: totalDays })}`),

  // 按赛事类型基线对比
  getCompetitionSplitComparison: ({ playType = 'spf', days = 90 } = {}) =>
    fetchAPI(`/lottery/competition-split-comparison${buildQuery({ play_type: playType, days })}`),

  // 综合验证指标(Brier + calibration + market diff + leakage)
  getValidationMetrics: (days = 30) =>
    fetchAPI(`/lottery/validation-metrics${buildQuery({ days })}`),

  // 错误归因产生的数据需求
  getNextDataRequirements: ({ status = 'pending', limit = 50 } = {}) =>
    fetchAPI(`/lottery/next-data-requirements${buildQuery({ status, limit })}`),

  // 比赛脚本(方向轴/边界轴/进球轴/BTTS/半场节奏)
  getMatchScript: (lotteryMatchId) => fetchAPI(`/lottery/match-script/${lotteryMatchId}`),

  // 置信度分层准确率(settlement grade + enriched BF metrics)
  getAccuracyByTier: (days = 30) => fetchAPI(`/lottery/accuracy-by-tier${buildQuery({ days })}`),
}

export const worldCupAPI = {
  health: () => fetchAPI('/world-cup/2026/health'),
  getContext: ({ live = true, includeMatches = false } = {}) =>
    fetchAPI(`/world-cup/2026/context${buildQuery({ live, include_matches: includeMatches })}`),
  getRules: () => fetchAPI('/world-cup/2026/rules'),
  getGroups: ({ live = true } = {}) =>
    fetchAPI(`/world-cup/2026/groups${buildQuery({ live })}`),
  getKnockout: ({ live = true } = {}) =>
    fetchAPI(`/world-cup/2026/knockout${buildQuery({ live })}`),
  getMatches: ({ live = true } = {}) =>
    fetchAPI(`/world-cup/2026/matches${buildQuery({ live })}`),
  getMatchContext: (matchId, { live = true } = {}) =>
    fetchAPI(`/world-cup/2026/match/${encodeURIComponent(matchId)}/context${buildQuery({ live })}`),
}

// 情报中枢相关
export const intelligenceAPI = {
  health: () => fetchAPI('/intelligence/health'),
  sourceHealth: () => fetchAPI('/intelligence/source-health'),

  getRequirements: (analysisView = 'world_cup') =>
    fetchAPI(`/intelligence/requirements/${analysisView}`),

  generateJobs: ({ date = null, source = 'lottery' } = {}) =>
    fetchAPI(`/intelligence/jobs/generate${buildQuery({ date, source })}`, { method: 'POST' }),

  runDaily: ({
    date = null,
    includeExternal = false,
    collectors = null,
    network = true,
    force = false,
  } = {}) =>
    fetchAPI(`/intelligence/run-daily${buildQuery({
      date,
      include_external: includeExternal,
      collectors,
      network,
      force,
    })}`, { method: 'POST' }),

  startRun: ({
    date = null,
    includeExternal = false,
    collectors = null,
    network = true,
    force = false,
    background = true,
  } = {}) =>
    fetchAPI(`/intelligence/runs${buildQuery({
      date,
      include_external: includeExternal,
      collectors,
      network,
      force,
      background,
    })}`, { method: 'POST' }),

  backfillFinished: ({
    startDate = null,
    endDate = null,
    includeExternal = true,
    collectors = null,
    network = false,
    force = false,
    playType = 'spf',
    limit = 200,
    background = false,
  } = {}) =>
    fetchAPI(`/intelligence/backfill-finished${buildQuery({
      start_date: startDate,
      end_date: endDate,
      include_external: includeExternal,
      collectors,
      network,
      force,
      play_type: playType,
      limit,
      background,
    })}`, { method: 'POST' }),

  listRuns: (limit = 50) =>
    fetchAPI(`/intelligence/runs${buildQuery({ limit })}`),

  getRun: (runId) =>
    fetchAPI(`/intelligence/runs/${encodeURIComponent(runId)}`),

  listJobs: ({ date = null, status = null, limit = 100 } = {}) =>
    fetchAPI(`/intelligence/jobs${buildQuery({ date, status, limit })}`),

  getJob: (jobId) =>
    fetchAPI(`/intelligence/jobs/${encodeURIComponent(jobId)}`),

  getPackage: (jobId) =>
    fetchAPI(`/intelligence/jobs/${encodeURIComponent(jobId)}/package`),

  collectBuiltin: (jobId, force = false) =>
    fetchAPI(`/intelligence/jobs/${encodeURIComponent(jobId)}/collect/builtin${buildQuery({ force })}`, { method: 'POST' }),

  collectExternal: (jobId, {
    collectors = null,
    network = true,
    force = false,
  } = {}) =>
    fetchAPI(`/intelligence/jobs/${encodeURIComponent(jobId)}/collect/external${buildQuery({
      collectors,
      network,
      force,
    })}`, { method: 'POST' }),

  buildPackage: (jobId) =>
    fetchAPI(`/intelligence/jobs/${encodeURIComponent(jobId)}/package`, { method: 'POST' }),

  listReviews: ({ jobId = null, limit = 100 } = {}) =>
    fetchAPI(`/intelligence/reviews${buildQuery({ job_id: jobId, limit })}`),

  autoReview: ({ date = null, playType = 'spf' } = {}) =>
    fetchAPI(`/intelligence/reviews/auto${buildQuery({ date, play_type: playType })}`, { method: 'POST' }),

  getTrainingSamples: ({
    limit = 200,
    onlySettled = true,
    attribution = null,
    includeRawPackage = false,
  } = {}) =>
    fetchAPI(`/intelligence/training-samples${buildQuery({
      limit,
      only_settled: onlySettled,
      attribution,
      include_raw_package: includeRawPackage,
    })}`),

  getTrainingSummary: ({
    startDate = null,
    endDate = null,
    limit = 10000,
  } = {}) =>
    fetchAPI(`/intelligence/training-summary${buildQuery({
      start_date: startDate,
      end_date: endDate,
      limit,
    })}`),

  exportTrainingSamples: ({
    limit = 10000,
    onlySettled = true,
    attribution = null,
    includeRawPackage = false,
  } = {}) =>
    fetchAPI(`/intelligence/training-samples/export${buildQuery({
      limit,
      only_settled: onlySettled,
      attribution,
      include_raw_package: includeRawPackage,
    })}`, { method: 'POST' }),
}
