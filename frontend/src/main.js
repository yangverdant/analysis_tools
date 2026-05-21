import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'

// 使用组件导航，不再需要路由
const routes = [
  { path: '/', name: 'Home', component: App },
  { path: '/team/:id', name: 'Team', component: () => import('./pages/TeamPage.vue') },
  { path: '/league/:id', name: 'League', component: () => import('./pages/LeaguePage.vue') },
  { path: '/match/:id', name: 'Match', component: () => import('./pages/MatchPage.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.use(ElementPlus)
app.mount('#app')
