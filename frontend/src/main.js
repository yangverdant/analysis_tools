import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'

// 分析模块路由
const routes = [
  { path: '/', name: 'Home', component: App },
  { path: '/team/:id', name: 'Team', component: () => import('./pages/TeamPage.vue') },
  { path: '/league/:id', name: 'League', component: () => import('./pages/LeaguePage.vue') },
  { path: '/match/:id', name: 'Match', component: () => import('./pages/MatchPage.vue') },
  // 分析子页面
  { path: '/analysis/handicap', name: 'HandicapAnalysis', component: () => import('./components/analytics/HandicapAnalysis.vue') },
  { path: '/analysis/efficiency', name: 'EfficiencyAnalysis', component: () => import('./components/analytics/EfficiencyAnalysis.vue') },
  { path: '/analysis/manager-change', name: 'ManagerChangeAnalysis', component: () => import('./components/analytics/ManagerChangeAnalysis.vue') },
  { path: '/analysis/upset', name: 'UpsetAnalysis', component: () => import('./components/analytics/UpsetAnalysis.vue') },
  { path: '/analysis/season-scenario', name: 'SeasonScenario', component: () => import('./components/analytics/SeasonScenario.vue') },
  { path: '/analysis/value-bet', name: 'ValueBetAnalysis', component: () => import('./components/analytics/ValueBetAnalysis.vue') },
  { path: '/analysis/referee', name: 'RefereeAnalysis', component: () => import('./components/analytics/RefereeAnalysis.vue') },
  { path: '/analysis/venue', name: 'VenueAnalysis', component: () => import('./components/analytics/VenueAnalysis.vue') },
  { path: '/analysis/weather', name: 'WeatherAnalysis', component: () => import('./components/analytics/WeatherAnalysis.vue') },
  { path: '/analysis/fatigue', name: 'FatigueAnalysis', component: () => import('./components/analytics/FatigueAnalysis.vue') },
  { path: '/analysis/league-impact', name: 'LeagueImpactAnalysis', component: () => import('./components/analytics/LeagueImpactAnalysis.vue') },
  { path: '/analysis/ml-prediction', name: 'MLPrediction', component: () => import('./components/analytics/MLPrediction.vue') },
  { path: '/analysis/xg-advanced', name: 'XGAdvanced', component: () => import('./components/analytics/XGAdvanced.vue') },
  { path: '/analysis/news', name: 'NewsAggregation', component: () => import('./components/analytics/NewsAggregation.vue') },
  { path: '/analysis/live', name: 'LiveData', component: () => import('./components/analytics/LiveData.vue') },
  { path: '/analysis/odds', name: 'OddsAnalysis', component: () => import('./components/analytics/OddsAnalysis.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.use(ElementPlus)
app.mount('#app')
