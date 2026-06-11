<template>
  <div class="lottery-odds">
    <div class="odds-header">
      <h3>赔率信息</h3>
      <span class="update-time" v-if="lastUpdate">
        更新于: {{ formatTime(lastUpdate) }}
      </span>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <div v-else-if="!hasOdds" class="no-odds">
      <span>暂无赔率数据</span>
    </div>

    <div v-else class="odds-grid">
      <!-- SPF赔率 -->
      <div v-if="odds.spf" class="odds-section">
        <h4>胜平负</h4>
        <div class="odds-row">
          <div class="odds-item">
            <span class="result-label">主胜(3)</span>
            <span class="odds-value">{{ odds.spf['3'] || '-' }}</span>
          </div>
          <div class="odds-item">
            <span class="result-label">平局(1)</span>
            <span class="odds-value">{{ odds.spf['1'] || '-' }}</span>
          </div>
          <div class="odds-item">
            <span class="result-label">客胜(0)</span>
            <span class="odds-value">{{ odds.spf['0'] || '-' }}</span>
          </div>
        </div>
        <div class="implied-probs">
          <span class="prob-item" v-for="(p, k) in getImpliedProbs(odds.spf)" :key="k">
            {{ k }}: {{ p }}%
          </span>
        </div>
      </div>

      <!-- RQSPF赔率 -->
      <div v-if="odds.rqspf" class="odds-section">
        <h4>让球胜平负 <span class="handicap-badge">{{ formatHandicap(handicap) }}</span></h4>
        <div class="odds-row">
          <div class="odds-item">
            <span class="result-label">主胜(3)</span>
            <span class="odds-value">{{ odds.rqspf['3'] || '-' }}</span>
          </div>
          <div class="odds-item">
            <span class="result-label">平局(1)</span>
            <span class="odds-value">{{ odds.rqspf['1'] || '-' }}</span>
          </div>
          <div class="odds-item">
            <span class="result-label">客胜(0)</span>
            <span class="odds-value">{{ odds.rqspf['0'] || '-' }}</span>
          </div>
        </div>
      </div>

      <!-- 比分赔率 -->
      <div v-if="odds.bf" class="odds-section">
        <h4>比分</h4>
        <div class="bf-grid">
          <div class="bf-group">
            <span class="group-title">主胜比分</span>
            <div class="bf-items">
              <div v-for="s in homeWinScores" :key="s" class="bf-item">
                <span class="score">{{ formatScore(s) }}</span>
                <span class="odds-value small">{{ odds.bf[s] || '-' }}</span>
              </div>
            </div>
          </div>
          <div class="bf-group">
            <span class="group-title">平局比分</span>
            <div class="bf-items">
              <div v-for="s in drawScores" :key="s" class="bf-item">
                <span class="score">{{ formatScore(s) }}</span>
                <span class="odds-value small">{{ odds.bf[s] || '-' }}</span>
              </div>
            </div>
          </div>
          <div class="bf-group">
            <span class="group-title">客胜比分</span>
            <div class="bf-items">
              <div v-for="s in awayWinScores" :key="s" class="bf-item">
                <span class="score">{{ formatScore(s) }}</span>
                <span class="odds-value small">{{ odds.bf[s] || '-' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- BQC赔率 -->
      <div v-if="odds.bqc" class="odds-section">
        <h4>半全场</h4>
        <div class="bqc-grid">
          <div v-for="code in bqcCodes" :key="code" class="bqc-item">
            <span class="bqc-code">{{ code }}</span>
            <span class="bqc-display">{{ formatBQC(code) }}</span>
            <span class="odds-value">{{ odds.bqc[code] || '-' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 赔率变动 -->
    <div v-if="oddsMovement && oddsMovement.length > 0" class="movement-section">
      <h4>赔率变动</h4>
      <div class="movement-chart">
        <div v-for="(m, i) in oddsMovement" :key="i" class="movement-item">
          <span class="time">{{ formatTime(m.time) }}</span>
          <span class="change" :class="m.direction">{{ m.change > 0 ? '+' : '' }}{{ m.change }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'

export default {
  name: 'LotteryOdds',
  props: {
    matchId: {
      type: String,
      required: true
    },
    handicap: {
      type: Number,
      default: 0
    }
  },
  setup(props) {
    const loading = ref(false)
    const lastUpdate = ref(null)
    const odds = ref({
      spf: null,
      rqspf: null,
      bf: null,
      bqc: null
    })
    const oddsMovement = ref([])

    const homeWinScores = ['10', '20', '21', '30', '31', '32', '40', '41', '42', '50']
    const drawScores = ['00', '11', '22', '33']
    const awayWinScores = ['01', '02', '12', '03', '13', '23', '04', '14', '24', '05']
    const bqcCodes = ['33', '31', '30', '13', '11', '10', '03', '01', '00']

    const hasOdds = computed(() => {
      return odds.value.spf || odds.value.rqspf || odds.value.bf || odds.value.bqc
    })

    const formatTime = (time) => {
      if (!time) return ''
      const d = new Date(time)
      return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
    }

    const formatHandicap = (line) => {
      if (line > 0) return `主让${line}球`
      if (line < 0) return `客让${Math.abs(line)}球`
      return '平手'
    }

    const formatScore = (s) => {
      if (s.length === 2) return `${s[0]}:${s[1]}`
      return s
    }

    const formatBQC = (code) => {
      const ht = { '3': '主胜', '1': '平', '0': '客胜' }
      const ft = { '3': '主胜', '1': '平', '0': '客胜' }
      return `${ht[code[0]]}+${ft[code[1]]}`
    }

    const getImpliedProbs = (oddsData) => {
      if (!oddsData) return {}
      const probs = {}
      const labels = { '3': '主胜', '1': '平局', '0': '客胜' }
      for (const [k, v] of Object.entries(oddsData)) {
        if (v && v > 1) {
          probs[labels[k] || k] = (100 / v).toFixed(1)
        }
      }
      return probs
    }

    const fetchOdds = async () => {
      loading.value = true
      try {
        const response = await fetch(
          `http://localhost:18888/api/v1/lottery/odds/${props.matchId}`
        )
        const data = await response.json()
        if (data.success) {
          odds.value = {
            spf: data.odds?.spf || null,
            rqspf: data.odds?.rqspf || null,
            bf: data.odds?.bf || null,
            bqc: data.odds?.bqc || null
          }
          lastUpdate.value = data.updated_at
        }
      } catch (e) {
        console.error('获取赔率失败:', e)
      } finally {
        loading.value = false
      }
    }

    watch(() => props.matchId, fetchOdds, { immediate: true })

    return {
      loading,
      lastUpdate,
      odds,
      oddsMovement,
      hasOdds,
      homeWinScores,
      drawScores,
      awayWinScores,
      bqcCodes,
      formatTime,
      formatHandicap,
      formatScore,
      formatBQC,
      getImpliedProbs
    }
  }
}
</script>

<style scoped>
.lottery-odds {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.odds-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.odds-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.update-time {
  font-size: 12px;
  color: #6b7280;
}

.loading-state, .no-odds {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #6b7280;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #374151;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.odds-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.odds-section {
  padding: 16px;
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
}

.odds-section h4 {
  font-size: 14px;
  color: white;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.handicap-badge {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
  border-radius: 4px;
}

.odds-row {
  display: flex;
  gap: 12px;
}

.odds-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
}

.result-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.odds-value {
  font-size: 20px;
  font-weight: 700;
  color: #10b981;
}

.odds-value.small {
  font-size: 14px;
}

.implied-probs {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 8px;
  font-size: 11px;
  color: #6b7280;
}

/* 比分赔率网格 */
.bf-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.bf-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-title {
  font-size: 12px;
  color: #6b7280;
}

.bf-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bf-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 8px;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
}

.score {
  font-size: 12px;
  color: white;
}

/* 半全场赔率网格 */
.bqc-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.bqc-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
}

.bqc-code {
  font-size: 14px;
  font-weight: 700;
  color: #10b981;
}

.bqc-display {
  font-size: 10px;
  color: #6b7280;
  margin: 2px 0;
}

/* 赔率变动 */
.movement-section {
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
}

.movement-section h4 {
  font-size: 13px;
  color: white;
  margin-bottom: 8px;
}

.movement-chart {
  display: flex;
  gap: 8px;
  overflow-x: auto;
}

.movement-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px;
  background: rgba(255,255,255,0.05);
  border-radius: 4px;
  min-width: 60px;
}

.time {
  font-size: 10px;
  color: #6b7280;
}

.change {
  font-size: 12px;
  font-weight: 600;
}

.change.up { color: #10b981; }
.change.down { color: #ef4444; }
</style>