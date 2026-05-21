<template>
  <div class="calendar-panel">
    <!-- 月份导航 -->
    <div class="calendar-header">
      <button class="nav-btn" @click="prevMonth"><ChevronLeftIcon /></button>
      <h2 class="current-month">{{ currentMonth }}</h2>
      <button class="nav-btn" @click="nextMonth"><ChevronRightIcon /></button>
      <div class="view-toggle">
        <button :class="['toggle-btn', { active: viewMode === 'month' }]" @click="viewMode = 'month'">月</button>
        <button :class="['toggle-btn', { active: viewMode === 'week' }]" @click="viewMode = 'week'">周</button>
      </div>
    </div>

    <!-- 筛选器 -->
    <div class="filters">
      <select v-model="selectedLeague" class="filter-select">
        <option value="">全部联赛</option>
        <option value="premier">英超</option>
        <option value="laliga">西甲</option>
        <option value="bundesliga">德甲</option>
        <option value="seriea">意甲</option>
        <option value="ligue1">法甲</option>
        <option value="ucl">欧冠</option>
      </select>
      <select v-model="selectedTeam" class="filter-select">
        <option value="">全部球队</option>
        <option value="mancity">曼城</option>
        <option value="arsenal">阿森纳</option>
        <option value="liverpool">利物浦</option>
      </select>
      <button class="today-btn" @click="goToToday">今天</button>
    </div>

    <!-- 日历视图 -->
    <div class="calendar-body">
      <!-- 星期标题 -->
      <div class="weekdays">
        <span v-for="day in weekdays" :key="day" class="weekday">{{ day }}</span>
      </div>

      <!-- 日期网格 -->
      <div class="days-grid">
        <div v-for="day in calendarDays" :key="day.date"
             :class="['day-cell', { 'other-month': day.otherMonth, 'today': day.isToday, 'selected': day.isSelected }]"
             @click="selectDay(day)">
          <span class="day-number">{{ day.dayNum }}</span>
          <div class="day-matches" v-if="day.matches.length">
            <div v-for="match in day.matches.slice(0, 3)" :key="match.id"
                 :class="['match-dot', match.leagueClass]"
                 :title="`${match.homeTeam} vs ${match.awayTeam}`">
            </div>
            <span v-if="day.matches.length > 3" class="more">+{{ day.matches.length - 3 }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 选中日期的比赛列表 -->
    <div class="selected-day-matches" v-if="selectedDayMatches.length">
      <div class="section-header">
        <h3>{{ selectedDayTitle }}</h3>
        <span class="match-count">{{ selectedDayMatches.length }} 场比赛</span>
      </div>
      <div class="matches-list">
        <div class="match-item" v-for="match in selectedDayMatches" :key="match.id">
          <div class="match-time">{{ match.time }}</div>
          <div class="match-league">
            <span :class="['league-badge', match.leagueClass]">{{ match.league }}</span>
          </div>
          <div class="match-teams">
            <span class="team home">{{ match.homeTeam }}</span>
            <span class="vs">VS</span>
            <span class="team away">{{ match.awayTeam }}</span>
          </div>
          <div class="match-odds" v-if="match.odds">
            <span class="odd">{{ match.odds.home }}</span>
            <span class="odd">{{ match.odds.draw }}</span>
            <span class="odd">{{ match.odds.away }}</span>
          </div>
          <button class="notify-btn" :class="{ active: match.notify }" @click="toggleNotify(match)">
            <BellIcon />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, h } from 'vue'

const ChevronLeftIcon = () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('polyline', { points: '15 18 9 12 15 6' })
])

const ChevronRightIcon = () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('polyline', { points: '9 18 15 12 9 6' })
])

const BellIcon = () => h('svg', { class: 'w-3 h-3', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('path', { d: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9' }),
  h('path', { d: 'M13.73 21a2 2 0 0 1-3.46 0' })
])

export default {
  name: 'Calendar',
  components: { ChevronLeftIcon, ChevronRightIcon, BellIcon },
  setup() {
    const currentDate = ref(new Date())
    const selectedDate = ref(new Date())
    const viewMode = ref('month')
    const selectedLeague = ref('')
    const selectedTeam = ref('')

    const weekdays = ['日', '一', '二', '三', '四', '五', '六']
    const months = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月']

    const currentMonth = computed(() => {
      return `${currentDate.value.getFullYear()}年 ${months[currentDate.value.getMonth()]}`
    })

    // 模拟比赛数据
    const matchesData = {
      '2024-05-11': [
        { id: 1, time: '22:00', league: '英超', leagueClass: 'premier', homeTeam: '曼城', awayTeam: '阿森纳', odds: { home: 1.85, draw: 3.50, away: 4.20 }, notify: true },
        { id: 2, time: '19:30', league: '西甲', leagueClass: 'laliga', homeTeam: '皇马', awayTeam: '巴萨', odds: { home: 2.10, draw: 3.30, away: 3.40 }, notify: false },
      ],
      '2024-05-12': [
        { id: 3, time: '21:30', league: '德甲', leagueClass: 'bundesliga', homeTeam: '拜仁', awayTeam: '多特', odds: { home: 1.65, draw: 3.80, away: 5.00 }, notify: false },
        { id: 4, time: '22:00', league: '意甲', leagueClass: 'seriea', homeTeam: '尤文', awayTeam: '国米', odds: { home: 2.30, draw: 3.20, away: 3.10 }, notify: true },
      ],
      '2024-05-13': [
        { id: 5, time: '03:00', league: '法甲', leagueClass: 'ligue1', homeTeam: '巴黎', awayTeam: '马赛', odds: { home: 1.45, draw: 4.20, away: 6.50 }, notify: false },
      ],
      '2024-05-15': [
        { id: 6, time: '03:00', league: '欧冠', leagueClass: 'ucl', homeTeam: '皇马', awayTeam: '拜仁', notify: true },
      ],
    }

    const calendarDays = computed(() => {
      const year = currentDate.value.getFullYear()
      const month = currentDate.value.getMonth()
      const firstDay = new Date(year, month, 1)
      const lastDay = new Date(year, month + 1, 0)
      const days = []

      // 上个月的日期
      const firstDayOfWeek = firstDay.getDay()
      for (let i = firstDayOfWeek - 1; i >= 0; i--) {
        const date = new Date(year, month, -i)
        days.push(createDayObject(date, true))
      }

      // 当月日期
      for (let i = 1; i <= lastDay.getDate(); i++) {
        const date = new Date(year, month, i)
        days.push(createDayObject(date, false))
      }

      // 下个月的日期
      const remainingDays = 42 - days.length
      for (let i = 1; i <= remainingDays; i++) {
        const date = new Date(year, month + 1, i)
        days.push(createDayObject(date, true))
      }

      return days
    })

    const createDayObject = (date, otherMonth) => {
      const dateStr = date.toISOString().split('T')[0]
      const today = new Date()
      return {
        date: dateStr,
        dayNum: date.getDate(),
        otherMonth,
        isToday: date.toDateString() === today.toDateString(),
        isSelected: date.toDateString() === selectedDate.value.toDateString(),
        matches: matchesData[dateStr] || []
      }
    }

    const selectedDayMatches = computed(() => {
      const dateStr = selectedDate.value.toISOString().split('T')[0]
      return matchesData[dateStr] || []
    })

    const selectedDayTitle = computed(() => {
      const d = selectedDate.value
      return `${d.getMonth() + 1}月${d.getDate()}日 星期${weekdays[d.getDay()]}`
    })

    const prevMonth = () => {
      currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() - 1, 1)
    }

    const nextMonth = () => {
      currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() + 1, 1)
    }

    const goToToday = () => {
      currentDate.value = new Date()
      selectedDate.value = new Date()
    }

    const selectDay = (day) => {
      if (!day.otherMonth) {
        selectedDate.value = new Date(day.date)
      }
    }

    const toggleNotify = (match) => { match.notify = !match.notify }

    return {
      currentDate, selectedDate, viewMode, selectedLeague, selectedTeam,
      weekdays, currentMonth, calendarDays, selectedDayMatches, selectedDayTitle,
      prevMonth, nextMonth, goToToday, selectDay, toggleNotify
    }
  }
}
</script>

<style scoped>
.calendar-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 头部 */
.calendar-header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nav-btn {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #151922;
  border: 1px solid rgba(31, 41, 55, 0.5);
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-btn:hover { color: white; border-color: #374151; }

.current-month {
  font-size: 20px;
  font-weight: 700;
  color: white;
  min-width: 160px;
}

.view-toggle {
  display: flex;
  background: #151922;
  border-radius: 8px;
  padding: 4px;
  margin-left: auto;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.toggle-btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  color: #9ca3af;
  background: transparent;
  border: none;
  cursor: pointer;
}

.toggle-btn.active { background: #10b981; color: white; }

/* 筛选器 */
.filters {
  display: flex;
  gap: 12px;
}

.filter-select {
  background: #151922;
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 14px;
  color: white;
  outline: none;
  min-width: 140px;
}

.today-btn {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  padding: 10px 20px;
  font-size: 14px;
  color: #10b981;
  cursor: pointer;
  margin-left: auto;
}

/* 日历主体 */
.calendar-body {
  background: #151922;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  margin-bottom: 12px;
}

.weekday {
  text-align: center;
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  padding: 8px;
}

.days-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

.day-cell {
  aspect-ratio: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.day-cell:hover { background: rgba(255,255,255,0.05); }
.day-cell.other-month { opacity: 0.3; }
.day-cell.today { background: rgba(16, 185, 129, 0.15); }
.day-cell.selected { background: rgba(16, 185, 129, 0.25); }

.day-number {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.day-cell.today .day-number {
  color: #10b981;
  font-weight: 700;
}

.day-matches {
  display: flex;
  gap: 2px;
  flex-wrap: wrap;
  justify-content: center;
}

.match-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.match-dot.premier { background: #3b82f6; }
.match-dot.laliga { background: #f59e0b; }
.match-dot.bundesliga { background: #ef4444; }
.match-dot.seriea { background: #10b981; }
.match-dot.ligue1 { background: #8b5cf6; }
.match-dot.ucl { background: #06b6d4; }

.more {
  font-size: 9px;
  color: #6b7280;
}

/* 选中日期比赛 */
.selected-day-matches {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.section-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
}

.match-count {
  font-size: 12px;
  color: #6b7280;
}

.matches-list {
  padding: 12px;
}

.match-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: #1c222f;
  border-radius: 8px;
  margin-bottom: 8px;
}

.match-time {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  min-width: 50px;
}

.league-badge {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.league-badge.premier { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.league-badge.laliga { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.league-badge.bundesliga { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.league-badge.seriea { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.league-badge.ligue1 { background: rgba(139, 92, 246, 0.15); color: #a78bfa; }
.league-badge.ucl { background: rgba(6, 182, 212, 0.15); color: #22d3ee; }

.match-teams {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.match-teams .team {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.match-teams .vs {
  font-size: 12px;
  color: #4b5563;
}

.match-odds {
  display: flex;
  gap: 6px;
}

.odd {
  font-size: 11px;
  padding: 4px 8px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
  color: #9ca3af;
}

.notify-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(255,255,255,0.05);
  border: none;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.notify-btn.active { background: rgba(16, 185, 129, 0.15); color: #10b981; }
</style>