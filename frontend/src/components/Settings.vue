<template>
  <div class="settings-panel">
    <div class="settings-grid">
      <!-- 个人设置 -->
      <div class="settings-section card">
        <div class="section-header">
          <h2><UserIcon /> 个人设置</h2>
        </div>
        <div class="settings-list">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">用户名</span>
              <span class="setting-desc">设置您的显示名称</span>
            </div>
            <input type="text" v-model="settings.username" class="setting-input" />
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">邮箱</span>
              <span class="setting-desc">用于接收通知和找回密码</span>
            </div>
            <input type="email" v-model="settings.email" class="setting-input" />
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">语言</span>
              <span class="setting-desc">界面显示语言</span>
            </div>
            <select v-model="settings.language" class="setting-select">
              <option value="zh-CN">简体中文</option>
              <option value="en-US">English</option>
            </select>
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">时区</span>
              <span class="setting-desc">比赛时间显示时区</span>
            </div>
            <select v-model="settings.timezone" class="setting-select">
              <option value="Asia/Shanghai">北京时间 (UTC+8)</option>
              <option value="Europe/London">伦敦时间 (UTC+0)</option>
              <option value="America/New_York">纽约时间 (UTC-5)</option>
            </select>
          </div>
        </div>
      </div>

      <!-- 外观设置 -->
      <div class="settings-section card">
        <div class="section-header">
          <h2><PaletteIcon /> 外观设置</h2>
        </div>
        <div class="settings-list">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">深色模式</span>
              <span class="setting-desc">使用深色主题减少眼睛疲劳</span>
            </div>
            <div class="toggle-switch" :class="{ active: settings.darkMode }" @click="settings.darkMode = !settings.darkMode">
              <div class="toggle-knob"></div>
            </div>
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">主题色</span>
              <span class="setting-desc">选择您喜欢的主题颜色</span>
            </div>
            <div class="color-options">
              <div v-for="color in themeColors" :key="color.value"
                   :class="['color-option', { active: settings.themeColor === color.value }]"
                   :style="{ background: color.value }"
                   @click="settings.themeColor = color.value">
              </div>
            </div>
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">紧凑模式</span>
              <span class="setting-desc">减少界面间距，显示更多内容</span>
            </div>
            <div class="toggle-switch" :class="{ active: settings.compactMode }" @click="settings.compactMode = !settings.compactMode">
              <div class="toggle-knob"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 通知设置 -->
      <div class="settings-section card">
        <div class="section-header">
          <h2><BellIcon /> 通知设置</h2>
        </div>
        <div class="settings-list">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">比赛提醒</span>
              <span class="setting-desc">收藏球队比赛开始前提醒</span>
            </div>
            <div class="toggle-switch" :class="{ active: settings.matchNotify }" @click="settings.matchNotify = !settings.matchNotify">
              <div class="toggle-knob"></div>
            </div>
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">比分推送</span>
              <span class="setting-desc">实时推送关注比赛的比分变化</span>
            </div>
            <div class="toggle-switch" :class="{ active: settings.scoreNotify }" @click="settings.scoreNotify = !settings.scoreNotify">
              <div class="toggle-knob"></div>
            </div>
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">提前提醒时间</span>
              <span class="setting-desc">比赛开始前多久提醒</span>
            </div>
            <select v-model="settings.notifyBefore" class="setting-select">
              <option value="15">15分钟</option>
              <option value="30">30分钟</option>
              <option value="60">1小时</option>
              <option value="120">2小时</option>
            </select>
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">邮件通知</span>
              <span class="setting-desc">接收每周赛事预告邮件</span>
            </div>
            <div class="toggle-switch" :class="{ active: settings.emailNotify }" @click="settings.emailNotify = !settings.emailNotify">
              <div class="toggle-knob"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 数据设置 -->
      <div class="settings-section card">
        <div class="section-header">
          <h2><DatabaseIcon /> 数据设置</h2>
        </div>
        <div class="settings-list">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">默认联赛</span>
              <span class="setting-desc">首页默认显示的联赛</span>
            </div>
            <select v-model="settings.defaultLeague" class="setting-select">
              <option value="premier">英超</option>
              <option value="laliga">西甲</option>
              <option value="bundesliga">德甲</option>
              <option value="seriea">意甲</option>
              <option value="ligue1">法甲</option>
            </select>
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">赔率格式</span>
              <span class="setting-desc">赔率显示格式</span>
            </div>
            <select v-model="settings.oddsFormat" class="setting-select">
              <option value="decimal">小数 (1.85)</option>
              <option value="fractional">分数 (5/4)</option>
              <option value="american">美式 (-120)</option>
            </select>
          </div>
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">清除缓存</span>
              <span class="setting-desc">清除本地缓存数据</span>
            </div>
            <button class="action-btn danger" @click="clearCache">清除</button>
          </div>
        </div>
      </div>

      <!-- 关于 -->
      <div class="settings-section card">
        <div class="section-header">
          <h2><InfoIcon /> 关于</h2>
        </div>
        <div class="about-content">
          <div class="about-item">
            <span class="about-label">版本</span>
            <span class="about-value">v1.0.0</span>
          </div>
          <div class="about-item">
            <span class="about-label">数据来源</span>
            <span class="about-value">football-data.co.uk, FIFA, StatsBomb</span>
          </div>
          <div class="about-links">
            <a href="#" class="link">使用条款</a>
            <a href="#" class="link">隐私政策</a>
            <a href="#" class="link">联系我们</a>
          </div>
        </div>
      </div>
    </div>

    <!-- 保存按钮 -->
    <div class="save-bar">
      <button class="save-btn" @click="saveSettings">
        <CheckIcon />
        保存设置
      </button>
      <button class="reset-btn" @click="resetSettings">恢复默认</button>
    </div>
  </div>
</template>

<script>
import { ref, reactive, h, defineComponent } from 'vue'

const createIcon = (name, paths) => defineComponent({
  name,
  setup: () => () => h('svg', { class: 'w-3.5 h-3.5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, paths)
})

const UserIcon = createIcon('UserIcon', [
  h('path', { d: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: '12', cy: '7', r: '4' })
])

const PaletteIcon = createIcon('PaletteIcon', [
  h('circle', { cx: '13.5', cy: '6.5', r: '.5' }),
  h('circle', { cx: '17.5', cy: '10.5', r: '.5' }),
  h('circle', { cx: '8.5', cy: '7.5', r: '.5' }),
  h('circle', { cx: '6.5', cy: '12.5', r: '.5' }),
  h('path', { d: 'M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.555C21.965 6.012 17.461 2 12 2z' })
])

const BellIcon = createIcon('BellIcon', [
  h('path', { d: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9' }),
  h('path', { d: 'M13.73 21a2 2 0 0 1-3.46 0' })
])

const DatabaseIcon = createIcon('DatabaseIcon', [
  h('ellipse', { cx: '12', cy: '5', rx: '9', ry: '3' }),
  h('path', { d: 'M21 12c0 1.66-4 3-9 3s-9-1.34-9-3' }),
  h('path', { d: 'M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5' })
])

const InfoIcon = createIcon('InfoIcon', [
  h('circle', { cx: '12', cy: '12', r: '10' }),
  h('line', { x1: '12', y1: '16', x2: '12', y2: '12' }),
  h('line', { x1: '12', y1: '8', x2: '12.01', y2: '8' })
])

const CheckIcon = createIcon('CheckIcon', [
  h('polyline', { points: '20 6 9 17 4 12' })
])

export default {
  name: 'Settings',
  components: { UserIcon, PaletteIcon, BellIcon, DatabaseIcon, InfoIcon, CheckIcon },
  setup() {
    const settings = reactive({
      username: '足球爱好者',
      email: 'user@example.com',
      language: 'zh-CN',
      timezone: 'Asia/Shanghai',
      darkMode: true,
      themeColor: '#10b981',
      compactMode: false,
      matchNotify: true,
      scoreNotify: true,
      notifyBefore: '30',
      emailNotify: false,
      defaultLeague: 'premier',
      oddsFormat: 'decimal'
    })

    const themeColors = [
      { name: '绿色', value: '#10b981' },
      { name: '蓝色', value: '#3b82f6' },
      { name: '紫色', value: '#8b5cf6' },
      { name: '红色', value: '#ef4444' },
      { name: '橙色', value: '#f59e0b' },
      { name: '青色', value: '#06b6d4' },
    ]

    const saveSettings = () => {
      localStorage.setItem('settings', JSON.stringify(settings))
      alert('设置已保存')
    }

    const resetSettings = () => {
      if (confirm('确定要恢复默认设置吗？')) {
        Object.assign(settings, {
          username: '足球爱好者',
          email: 'user@example.com',
          language: 'zh-CN',
          timezone: 'Asia/Shanghai',
          darkMode: true,
          themeColor: '#10b981',
          compactMode: false,
          matchNotify: true,
          scoreNotify: true,
          notifyBefore: '30',
          emailNotify: false,
          defaultLeague: 'premier',
          oddsFormat: 'decimal'
        })
      }
    }

    const clearCache = () => {
      if (confirm('确定要清除缓存吗？')) {
        localStorage.clear()
        alert('缓存已清除')
      }
    }

    return { settings, themeColors, saveSettings, resetSettings, clearCache }
  }
}
</script>

<style scoped>
.settings-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}

.settings-section {
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.section-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.5);
}

.section-header h2 {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-header h2 svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.settings-list {
  padding: 8px 0;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
}

.setting-item:last-child { border-bottom: none; }

.setting-info {
  flex: 1;
}

.setting-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.setting-desc {
  font-size: 12px;
  color: #6b7280;
}

.setting-input {
  background: #1c222f;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  color: white;
  outline: none;
  width: 200px;
}

.setting-input:focus { border-color: #10b981; }

.setting-select {
  background: #1c222f;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  color: white;
  outline: none;
  min-width: 160px;
}

.toggle-switch {
  width: 48px;
  height: 24px;
  background: #374151;
  border-radius: 12px;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
}

.toggle-switch.active { background: #10b981; }

.toggle-knob {
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  position: absolute;
  top: 2px;
  left: 2px;
  transition: left 0.2s;
}

.toggle-switch.active .toggle-knob { left: 26px; }

.color-options {
  display: flex;
  gap: 8px;
}

.color-option {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: transform 0.2s;
}

.color-option:hover { transform: scale(1.1); }

.color-option.active { border-color: white; }

.action-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.action-btn.danger {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.action-btn.danger:hover { background: rgba(239, 68, 68, 0.25); }

.about-content {
  padding: 20px;
}

.about-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid rgba(31, 41, 55, 0.3);
}

.about-label {
  font-size: 14px;
  color: #6b7280;
}

.about-value {
  font-size: 14px;
  color: #e5e7eb;
}

.about-links {
  display: flex;
  gap: 24px;
  margin-top: 16px;
}

.link {
  font-size: 13px;
  color: #10b981;
  text-decoration: none;
}

.link:hover { text-decoration: underline; }

.save-bar {
  display: flex;
  gap: 16px;
  justify-content: flex-end;
  padding: 20px;
  background: #151922;
  border-radius: 12px;
  border: 1px solid rgba(31, 41, 55, 0.5);
}

.save-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.reset-btn {
  padding: 12px 24px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(31, 41, 55, 0.5);
  border-radius: 8px;
  color: #9ca3af;
  font-size: 14px;
  cursor: pointer;
}
</style>