<template>
  <div class="weather-analysis">
    <!-- 头部 -->
    <div class="header card">
      <div class="header-content">
        <h2>天气分析</h2>
        <p>天气条件对比赛的影响评估</p>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 城市天气 -->
    <div v-if="activeTab === 'city'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="cityName"
          placeholder="输入城市名称"
          class="text-input"
          @keyup.enter="loadCityWeather"
        />
        <button class="action-btn" @click="loadCityWeather" :disabled="cityLoading">查询</button>
      </div>
      <div class="loading-state" v-if="cityLoading">
        <div class="spinner"></div>
        <p>正在获取天气数据...</p>
      </div>
      <template v-else-if="cityWeather">
        <div class="weather-display card">
          <div class="weather-main">
            <div class="weather-temp">
              <span class="temp-value">{{ cityWeather.temperature != null ? cityWeather.temperature : '--' }}</span>
              <span class="temp-unit">°C</span>
            </div>
            <div class="weather-desc">{{ cityWeather.conditions || cityWeather.description || cityWeather.weather || '--' }}</div>
          </div>
          <div class="weather-details">
            <div v-if="cityWeather.humidity != null" class="weather-detail">
              <span class="detail-label">湿度</span>
              <span class="detail-value">{{ cityWeather.humidity }}%</span>
            </div>
            <div v-if="cityWeather.wind_speed != null" class="weather-detail">
              <span class="detail-label">风速</span>
              <span class="detail-value">{{ cityWeather.wind_speed }} km/h</span>
            </div>
            <div v-if="cityWeather.precipitation != null" class="weather-detail">
              <span class="detail-label">降水概率</span>
              <span class="detail-value">{{ cityWeather.precipitation }}%</span>
            </div>
            <div v-if="cityWeather.visibility != null" class="weather-detail">
              <span class="detail-label">能见度</span>
              <span class="detail-value">{{ cityWeather.visibility }} km</span>
            </div>
          </div>
        </div>
        <div v-if="cityWeather.match_impact" class="detail-card card">
          <h3>比赛影响评估</h3>
          <div class="impact-content">
            <div v-if="cityWeather.match_impact.impact_level" class="impact-row">
              <span class="impact-label">影响等级</span>
              <span :class="['impact-value', impactLevelClass(cityWeather.match_impact.impact_level)]">
                {{ cityWeather.match_impact.impact_level }}
              </span>
            </div>
            <div v-if="cityWeather.match_impact.goal_impact != null" class="impact-row">
              <span class="impact-label">进球影响</span>
              <span class="impact-value">{{ cityWeather.match_impact.goal_impact }}</span>
            </div>
            <div v-if="cityWeather.match_impact.description" class="impact-analysis">
              <p>{{ cityWeather.match_impact.description }}</p>
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="cityName && !cityLoading" class="empty-state card">
        <p>未找到该城市天气数据</p>
      </div>
    </div>

    <!-- 比赛天气 -->
    <div v-if="activeTab === 'match'" class="tab-content">
      <div class="input-row card">
        <input
          v-model="matchId"
          placeholder="输入比赛ID"
          class="text-input"
          @keyup.enter="loadMatchWeather"
        />
        <button class="action-btn" @click="loadMatchWeather" :disabled="matchLoading">查询</button>
      </div>
      <div class="loading-state" v-if="matchLoading">
        <div class="spinner"></div>
        <p>正在获取比赛天气...</p>
      </div>
      <template v-else-if="matchWeather">
        <div class="weather-display card">
          <div class="weather-main">
            <div class="weather-temp">
              <span class="temp-value">{{ matchWeather.temperature != null ? matchWeather.temperature : '--' }}</span>
              <span class="temp-unit">°C</span>
            </div>
            <div class="weather-desc">{{ matchWeather.conditions || matchWeather.description || matchWeather.weather || '--' }}</div>
          </div>
          <div class="weather-details">
            <div v-if="matchWeather.humidity != null" class="weather-detail">
              <span class="detail-label">湿度</span>
              <span class="detail-value">{{ matchWeather.humidity }}%</span>
            </div>
            <div v-if="matchWeather.wind_speed != null" class="weather-detail">
              <span class="detail-label">风速</span>
              <span class="detail-value">{{ matchWeather.wind_speed }} km/h</span>
            </div>
            <div v-if="matchWeather.precipitation != null" class="weather-detail">
              <span class="detail-label">降水概率</span>
              <span class="detail-value">{{ matchWeather.precipitation }}%</span>
            </div>
          </div>
        </div>
        <div v-if="matchWeather.impact_analysis || matchWeather.match_impact" class="detail-card card">
          <h3>天气影响分析</h3>
          <div class="impact-content">
            <div v-if="matchWeather.impact_analysis" class="impact-analysis">
              <p>{{ matchWeather.impact_analysis }}</p>
            </div>
            <div v-if="matchWeather.match_impact">
              <div v-if="matchWeather.match_impact.impact_level" class="impact-row">
                <span class="impact-label">影响等级</span>
                <span :class="['impact-value', impactLevelClass(matchWeather.match_impact.impact_level)]">
                  {{ matchWeather.match_impact.impact_level }}
                </span>
              </div>
              <div v-if="matchWeather.match_impact.description" class="impact-analysis">
                <p>{{ matchWeather.match_impact.description }}</p>
              </div>
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="matchId && !matchLoading" class="empty-state card">
        <p>未找到该比赛天气数据</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { analysisAPI } from '../../api'

export default {
  name: 'WeatherAnalysis',
  setup() {
    const activeTab = ref('city')
    const tabs = [
      { key: 'city', label: '城市天气' },
      { key: 'match', label: '比赛天气' }
    ]

    // 城市天气
    const cityName = ref('')
    const cityLoading = ref(false)
    const cityWeather = ref(null)

    // 比赛天气
    const matchId = ref('')
    const matchLoading = ref(false)
    const matchWeather = ref(null)

    const impactLevelClass = (level) => {
      if (!level) return ''
      const l = level.toString().toLowerCase()
      if (l.includes('high') || l.includes('高')) return 'level-high'
      if (l.includes('medium') || l.includes('中')) return 'level-medium'
      if (l.includes('low') || l.includes('低')) return 'level-low'
      return ''
    }

    const loadCityWeather = async () => {
      if (!cityName.value) return
      cityLoading.value = true
      cityWeather.value = null
      try {
        const res = await analysisAPI.getCityWeather(cityName.value)
        cityWeather.value = res.data || res || null
      } catch (e) {
        console.error('获取城市天气失败:', e)
        cityWeather.value = null
      } finally {
        cityLoading.value = false
      }
    }

    const loadMatchWeather = async () => {
      if (!matchId.value) return
      matchLoading.value = true
      matchWeather.value = null
      try {
        const res = await analysisAPI.getMatchWeather(matchId.value)
        matchWeather.value = res.data || res || null
      } catch (e) {
        console.error('获取比赛天气失败:', e)
        matchWeather.value = null
      } finally {
        matchLoading.value = false
      }
    }

    return {
      activeTab, tabs,
      cityName, cityLoading, cityWeather,
      matchId, matchLoading, matchWeather,
      loadCityWeather, loadMatchWeather, impactLevelClass
    }
  }
}
</script>

<style scoped>
.weather-analysis {
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
}

.tab-btn {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #9ca3af;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
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

/* 天气展示 */
.weather-display {
  padding: 24px 20px;
}

.weather-main {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 16px;
}

.weather-temp {
  display: flex;
  align-items: flex-start;
}

.temp-value {
  font-size: 42px;
  font-weight: 700;
  color: #e5e7eb;
  line-height: 1;
}

.temp-unit {
  font-size: 18px;
  color: #9ca3af;
  margin-top: 4px;
  margin-left: 2px;
}

.weather-desc {
  font-size: 16px;
  color: #10b981;
  font-weight: 500;
}

.weather-details {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.weather-detail {
  padding: 10px 12px;
  background: #0a0d14;
  border-radius: 8px;
}

.detail-label {
  display: block;
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 16px;
  font-weight: 600;
  color: #e5e7eb;
}

/* 详情卡片 */
.detail-card {
  padding: 16px 20px;
}

.detail-card h3 {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.impact-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.impact-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.impact-label {
  font-size: 13px;
  color: #9ca3af;
}

.impact-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.impact-value.level-high {
  color: #ef4444;
}

.impact-value.level-medium {
  color: #f59e0b;
}

.impact-value.level-low {
  color: #10b981;
}

.impact-analysis {
  padding: 10px 12px;
  background: #0a0d14;
  border-radius: 6px;
}

.impact-analysis p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
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
  .weather-main {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>
