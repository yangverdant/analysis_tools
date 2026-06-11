<template>
  <div class="app-layout">
    <!-- 移动端遮罩 -->
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false"></div>

    <!-- 侧边栏 -->
    <aside :class="['sidebar', { open: sidebarOpen }]">
      <div class="sidebar-logo">
        <div class="logo-icon">
          <svg viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor" opacity="0.2"/>
            <path d="M8 12l4-4 4 4M12 16V8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <span class="logo-text">足球分析系统</span>
        <button class="close-btn" @click="sidebarOpen = false">
          <CloseIcon />
        </button>
      </div>

      <nav class="sidebar-nav">
        <a v-for="item in navItems" :key="item.label"
           :class="['nav-item', { active: currentPage === item.label }]"
           @click="selectPage(item.label)">
          <component :is="item.icon" />
          <span>{{ item.label }}</span>
        </a>
      </nav>

      <div class="sidebar-footer">
        <div class="theme-toggle">
          <MoonIcon />
          <span>夜间模式</span>
          <div class="toggle-switch">
            <div class="toggle-knob"></div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-area">
      <!-- 顶部栏 -->
      <header class="top-bar">
        <button class="menu-btn" @click="sidebarOpen = true">
          <MenuIcon />
        </button>
        <h1 class="page-title">{{ currentPage }}</h1>
        <div class="top-actions">
          <div class="search-box">
            <SearchIcon class="search-icon" />
            <input v-model="searchQuery" placeholder="搜索球队、球员、赛事" @keyup.enter="handleSearch" />
          </div>
          <button class="icon-btn">
            <BellIcon />
            <span class="notification-dot"></span>
          </button>
          <div class="user-avatar">
            <img src="https://i.pravatar.cc/100?img=11" alt="User" />
          </div>
        </div>
      </header>

      <!-- 内容区 -->
      <div class="content-area">
        <!-- 路由视图 - 用于详情页面 -->
        <router-view v-if="$route.path.startsWith('/match/') || $route.path.startsWith('/team/') || $route.path.startsWith('/league/') || $route.path.startsWith('/analysis/')"></router-view>

        <!-- 主页面组件切换 -->
        <HomePanel v-else-if="currentPage === '首页'" />
        <DailyCycle v-else-if="currentPage === '日循环'" />
        <MatchPreview v-else-if="currentPage === '赛事前瞻'" />
        <DataView v-else-if="currentPage === '数据查看'" />
        <AnalysisCenter v-else-if="currentPage === '分析中心'" />
        <LotteryCenter v-else-if="currentPage === '体彩中心'" />
        <DataCenter v-else-if="currentPage === '数据中心'" />
        <Favorites v-else-if="currentPage === '我的收藏'" />
        <Calendar v-else-if="currentPage === '比赛日历'" />
        <Teams v-else-if="currentPage === '球队库'" />
        <Settings v-else-if="currentPage === '设置'" />

        <!-- 开发中的页面 -->
        <div v-else class="coming-soon">
          <ActivityIcon class="icon" />
          <p>{{ currentPage }} 页面开发中...</p>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
import { ref, h, defineComponent, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import MatchPreview from './components/MatchPreview.vue'
import DataView from './components/DataView.vue'
import AnalysisCenter from './components/AnalysisCenter.vue'
import Favorites from './components/Favorites.vue'
import Calendar from './components/Calendar.vue'
import Teams from './components/Teams.vue'
import Settings from './components/Settings.vue'
import HomePanel from './components/HomePanel.vue'
import DailyCycle from './components/DailyCycle.vue'
import DataCenter from './components/DataCenter.vue'
import LotteryCenter from './components/LotteryCenter.vue'

// 图标组件 - 使用 defineComponent 包装
const createIcon = (name, classStr, paths) => defineComponent({
  name,
  setup: () => () => h('svg', { class: classStr, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, paths)
})

const HomeIcon = createIcon('HomeIcon', 'w-3 h-3', [
  h('path', { d: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z' }),
  h('polyline', { points: '9 22 9 12 15 12 15 22' })
])

const ActivityIcon = createIcon('ActivityIcon', 'w-3 h-3', [
  h('polyline', { points: '22 12 18 12 15 21 9 3 6 12 2 12' })
])

const DatabaseIcon = createIcon('DatabaseIcon', 'w-3 h-3', [
  h('ellipse', { cx: '12', cy: '5', rx: '9', ry: '3' }),
  h('path', { d: 'M21 12c0 1.66-4 3-9 3s-9-1.34-9-3' }),
  h('path', { d: 'M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5' })
])

const BarChartIcon = createIcon('BarChartIcon', 'w-3 h-3', [
  h('line', { x1: '18', y1: '20', x2: '18', y2: '10' }),
  h('line', { x1: '12', y1: '20', x2: '12', y2: '4' }),
  h('line', { x1: '6', y1: '20', x2: '6', y2: '14' })
])

const StarIcon = createIcon('StarIcon', 'w-3 h-3', [
  h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' })
])

const CalendarIcon = createIcon('CalendarIcon', 'w-3 h-3', [
  h('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }),
  h('line', { x1: '16', y1: '2', x2: '16', y2: '6' }),
  h('line', { x1: '8', y1: '2', x2: '8', y2: '6' }),
  h('line', { x1: '3', y1: '10', x2: '21', y2: '10' })
])

const UsersIcon = createIcon('UsersIcon', 'w-3 h-3', [
  h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: '9', cy: '7', r: '4' }),
  h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
  h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
])

const SettingsIcon = createIcon('SettingsIcon', 'w-3 h-3', [
  h('circle', { cx: '12', cy: '12', r: '3' }),
  h('path', { d: 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z' })
])

const LotteryIcon = createIcon('LotteryIcon', 'w-3 h-3', [
  h('circle', { cx: '12', cy: '12', r: '10' }),
  h('path', { d: 'M12 6v6l4 2' }),
  h('path', { d: 'M8 14h8' })
])

const SearchIcon = defineComponent({
  name: 'SearchIcon',
  setup: () => () => h('svg', { class: 'w-3 h-3', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('circle', { cx: '11', cy: '11', r: '8' }),
    h('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' })
  ])
})

const BellIcon = createIcon('BellIcon', 'w-3.5 h-3.5', [
  h('path', { d: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9' }),
  h('path', { d: 'M13.73 21a2 2 0 0 1-3.46 0' })
])

const MoonIcon = createIcon('MoonIcon', 'w-3.5 h-3.5', [
  h('path', { d: 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z' })
])

const MenuIcon = createIcon('MenuIcon', 'w-3.5 h-3.5', [
  h('line', { x1: '3', y1: '12', x2: '21', y2: '12' }),
  h('line', { x1: '3', y1: '6', x2: '21', y2: '6' }),
  h('line', { x1: '3', y1: '18', x2: '21', y2: '18' })
])

const CloseIcon = createIcon('CloseIcon', 'w-3.5 h-3.5', [
  h('line', { x1: '18', y1: '6', x2: '6', y2: '18' }),
  h('line', { x1: '6', y1: '6', x2: '18', y2: '18' })
])

// 占位组件 - 不再需要，已全部实现

export default {
  name: 'App',
  components: {
    MatchPreview,
    DataView,
    AnalysisCenter,
    Favorites,
    Calendar,
    Teams,
    Settings,
    HomePanel,
    DailyCycle,
    DataCenter,
    LotteryCenter,
    HomeIcon,
    ActivityIcon,
    DatabaseIcon,
    BarChartIcon,
    StarIcon,
    CalendarIcon,
    UsersIcon,
    SettingsIcon,
    LotteryIcon,
    SearchIcon,
    BellIcon,
    MoonIcon,
    MenuIcon,
    CloseIcon
  },
  setup() {
    const router = useRouter()
    const currentPage = ref('体彩中心')
    const searchQuery = ref('')
    const sidebarOpen = ref(false)
    const syncStatus = ref(null)

    const navItems = [
      { icon: 'HomeIcon', label: '首页' },
      { icon: 'ActivityIcon', label: '日循环' },
      { icon: 'ActivityIcon', label: '赛事前瞻' },
      { icon: 'LotteryIcon', label: '体彩中心' },
      { icon: 'DatabaseIcon', label: '数据查看' },
      { icon: 'BarChartIcon', label: '分析中心' },
      { icon: 'DatabaseIcon', label: '数据中心' },
      { icon: 'StarIcon', label: '我的收藏' },
      { icon: 'CalendarIcon', label: '比赛日历' },
      { icon: 'UsersIcon', label: '球队库' },
      { icon: 'SettingsIcon', label: '设置' }
    ]

    // 页面加载时自动同步数据
    const startAutoSync = async () => {
      try {
        syncStatus.value = { status: 'syncing', message: '正在同步数据...' }
        const response = await fetch('http://localhost:18888/api/v1/sync/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        const data = await response.json()
        if (data.success) {
          syncStatus.value = { status: 'done', message: `同步完成：更新${data.finished_matches?.updated || 0}场，新增${data.future_matches?.inserted || 0}场` }
          // 3秒后清除状态
          setTimeout(() => { syncStatus.value = null }, 3000)
        } else {
          syncStatus.value = { status: 'error', message: '同步失败' }
          setTimeout(() => { syncStatus.value = null }, 3000)
        }
      } catch (e) {
        console.log('同步服务未启动:', e)
        syncStatus.value = null
      }
    }

    // 组件挂载时启动同步
    onMounted(() => {
      startAutoSync()
    })

    const handleSearch = () => {
      if (searchQuery.value.trim()) {
        router.push({ name: 'Analysis', query: { q: searchQuery.value } })
      }
    }

    const selectPage = (label) => {
      currentPage.value = label
      sidebarOpen.value = false
      // 切换菜单时返回首页路由，清除详情页
      if (router.currentRoute.value.path !== '/') {
        router.push('/')
      }
    }

    return {
      currentPage,
      searchQuery,
      sidebarOpen,
      navItems,
      syncStatus,
      handleSearch,
      selectPage,
      SearchIcon,
      BellIcon,
      MoonIcon,
      MenuIcon,
      CloseIcon,
      ActivityIcon
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  width: 100%;
  overflow: hidden;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: #0a0d14;
  color: #e2e8f0;
}

.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

/* 移动端遮罩 */
.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
  display: none;
}

/* 侧边栏 */
.sidebar {
  width: 200px;
  min-width: 200px;
  max-width: 200px;
  height: 100%;
  background: #0d1117;
  border-right: 1px solid #1f2937;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-logo {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.close-btn {
  display: none;
  background: transparent;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  padding: 4px;
  margin-left: auto;
  border-radius: 6px;
}

.close-btn:hover {
  background: rgba(255,255,255,0.05);
  color: white;
}

.logo-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid rgba(255,255,255,0.1);
}

.logo-icon svg {
  width: 14px;
  height: 14px;
  color: white;
}

.logo-text {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: white;
}

.sidebar-nav {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  color: #9ca3af;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 2px;
}

.nav-item svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.nav-item:hover {
  background: rgba(255,255,255,0.05);
  color: #e5e7eb;
}

.nav-item.active {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.sidebar-footer {
  padding: 16px;
  flex-shrink: 0;
  border-top: 1px solid rgba(31, 41, 55, 0.5);
}

.theme-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 9999px;
  border: 1px solid rgba(31, 41, 55, 0.5);
  font-size: 13px;
  color: #9ca3af;
  cursor: pointer;
}

.theme-toggle svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.toggle-switch {
  width: 32px;
  height: 16px;
  background: #374151;
  border-radius: 9999px;
  position: relative;
  margin-left: auto;
}

.toggle-knob {
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  position: absolute;
  right: 2px;
  top: 2px;
}

/* 主区域 */
.main-area {
  flex: 1;
  min-width: 0;
  width: calc(100% - 200px);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 顶部栏 */
.top-bar {
  height: 56px;
  min-height: 56px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #1f2937;
  background: #0d1117;
  flex-shrink: 0;
  gap: 12px;
}

.menu-btn {
  display: none;
  background: transparent;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
}

.menu-btn:hover {
  background: rgba(255,255,255,0.05);
  color: white;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: white;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-box .search-icon {
  position: absolute;
  left: 12px;
  color: #6b7280;
  width: 12px;
  height: 12px;
}

.search-box input {
  background: #151922;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 9999px;
  padding: 8px 12px 8px 36px;
  width: 240px;
  max-width: 240px;
  font-size: 13px;
  color: white;
  outline: none;
  transition: border-color 0.2s;
}

.search-box input:focus {
  border-color: #10b981;
}

.search-box input::placeholder {
  color: #6b7280;
}

.icon-btn {
  position: relative;
  background: #151922;
  border: 1px solid rgba(31, 41, 55, 0.8);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover {
  color: white;
  border-color: #374151;
}

.notification-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  background: #ef4444;
  border-radius: 50%;
  border: 2px solid #0d1117;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 2px solid #374151;
  cursor: pointer;
  transition: border-color 0.2s;
}

.user-avatar:hover {
  border-color: #6b7280;
}

.user-avatar img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}

/* 内容区 */
.content-area {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
  height: calc(100% - 56px);
}

.coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #6b7280;
  border: 2px dashed #374151;
  border-radius: 12px;
  background: rgba(21, 25, 34, 0.5);
}

.coming-soon .icon {
  width: 48px;
  height: 48px;
  margin-bottom: 16px;
  color: #374151;
}

/* 滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: #1a1a2e;
}

::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #4b5563;
}

/* 响应式布局 */
/* 平板端 - 侧边栏变为抽屉模式 */
@media (max-width: 900px) {
  .sidebar-overlay {
    display: block;
  }

  .sidebar {
    position: fixed;
    left: -280px;
    top: 0;
    width: 260px;
    min-width: 260px;
    max-width: 260px;
    transition: left 0.3s ease;
    box-shadow: none;
    z-index: 100;
  }

  .sidebar.open {
    left: 0;
    box-shadow: 4px 0 20px rgba(0, 0, 0, 0.5);
  }

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .main-area {
    width: 100%;
  }

  .menu-btn {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .search-box {
    display: none;
  }

  .page-title {
    font-size: 16px;
  }
}

/* 手机端 */
@media (max-width: 600px) {
  .top-bar {
    padding: 0 12px;
  }

  .content-area {
    padding: 12px;
  }

  .top-actions {
    gap: 8px;
  }

  .user-avatar {
    width: 32px;
    height: 32px;
  }

  .icon-btn {
    width: 36px;
    height: 36px;
  }

  .sidebar {
    width: 260px;
    min-width: 260px;
    max-width: 260px;
  }
}
</style>
