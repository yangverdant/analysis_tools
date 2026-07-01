<template>
  <section class="wc-panel">
    <div class="wc-head">
      <div>
        <div class="wc-kicker">FIFA World Cup 2026</div>
        <h2>{{ t.title }}</h2>
      </div>
      <div class="wc-actions">
        <label class="wc-live-toggle">
          <input type="checkbox" v-model="liveMode" @change="loadContext" />
          <span>{{ t.liveSource }}</span>
        </label>
        <button class="wc-refresh" @click="loadContext" :disabled="loading">
          {{ loading ? t.refreshing : t.refresh }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="wc-loading">{{ t.loading }}</div>
    <div v-else-if="error" class="wc-error">{{ error }}</div>

    <template v-else-if="context">
      <div class="wc-status">
        <span>{{ sourceLabel }}</span>
        <span>{{ summary.finished }} / {{ summary.total }} {{ t.finishedMatches }}</span>
        <span>{{ tournamentText }}</span>
        <span v-if="assignmentStatusText">{{ assignmentStatusText }}</span>
      </div>

      <div class="wc-rule-strip">
        <div class="wc-rule-item">
          <b>{{ rules.teams_count }}</b>
          <span>{{ t.teams }}</span>
        </div>
        <div class="wc-rule-item">
          <b>{{ rules.group_count }}</b>
          <span>{{ t.groups }}</span>
        </div>
        <div class="wc-rule-item">
          <b>{{ t.topTwo }}</b>
          <span>{{ t.directAdvance }}</span>
        </div>
        <div class="wc-rule-item">
          <b>8</b>
          <span>{{ t.bestThird }}</span>
        </div>
        <div class="wc-rule-item wide">
          <b>{{ t.roundOf32 }}</b>
          <span>{{ t.knockoutRule }}</span>
        </div>
      </div>

      <div class="wc-section-title collapsible" @click="groupSectionOpen = !groupSectionOpen">
        <h3>{{ t.groupShapeTitle }} <span class="collapse-indicator">{{ groupSectionOpen ? '▾' : '▸' }}</span></h3>
        <span>{{ t.groupShapeNote }}</span>
      </div>
      <div class="wc-collapsible-body" :class="{ collapsed: !groupSectionOpen }">
        <div class="wc-groups-grid">
        <article v-for="group in groupsList" :key="group.group" class="wc-group-card">
          <div class="wc-group-top">
            <strong>{{ group.name }}</strong>
            <span title="每队小组赛3场，本组4队共6场">本组已赛 {{ group.matches_finished }}/{{ group.matches_total }}场</span>
          </div>
          <table class="wc-table">
            <thead>
              <tr>
                <th>{{ t.rank }}</th>
                <th>{{ t.team }}</th>
                <th>{{ t.played }}</th>
                <th>{{ t.goalDiff }}</th>
                <th>{{ t.points }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="team in group.standings" :key="team.team_id || team.team_name" :class="zoneClass(team)">
                <td>{{ team.position }}</td>
                <td class="team-cell"><span>{{ displayTeam(team) }}</span></td>
                <td>{{ team.played }}</td>
                <td>{{ signed(team.goal_diff) }}</td>
                <td><b>{{ team.points }}</b></td>
              </tr>
              <tr v-if="!group.standings.length" class="empty-row">
                <td colspan="5">{{ t.noTeams }}</td>
              </tr>
            </tbody>
          </table>
        </article>
        </div>
      </div>

      <div class="wc-section-title collapsible" @click="thirdSectionOpen = !thirdSectionOpen">
        <h3>{{ t.thirdTitle }} <span class="collapse-indicator">{{ thirdSectionOpen ? '▾' : '▸' }}</span></h3>
        <span>{{ t.thirdNote }}</span>
      </div>
      <div class="wc-collapsible-body" :class="{ collapsed: !thirdSectionOpen }">
      <div class="wc-third-table-wrap">
        <table class="wc-third-table">
          <thead>
            <tr>
              <th>{{ t.thirdRank }}</th>
              <th>{{ t.group }}</th>
              <th>{{ t.team }}</th>
              <th>{{ t.played }}</th>
              <th>{{ t.goalDiff }}</th>
              <th>{{ t.goalsFor }}</th>
              <th>{{ t.points }}</th>
              <th>{{ t.status }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in thirdRows" :key="row.group" :class="row.third_rank <= 8 ? 'advance' : 'out'">
              <td>{{ row.third_rank }}</td>
              <td>{{ row.group }}</td>
              <td class="team-cell"><span>{{ displayTeam(row) }}</span></td>
              <td>{{ row.played }}</td>
              <td>{{ signed(row.goal_diff) }}</td>
              <td>{{ row.goals_for }}</td>
              <td><b>{{ row.points }}</b></td>
              <td>{{ row.third_rank <= 8 ? t.advanceZone : t.chasing }}</td>
            </tr>
          </tbody>
        </table>
        </div>
      </div>

      <div class="wc-section-title collapsible" @click="knockoutSectionOpen = !knockoutSectionOpen">
        <h3>{{ t.knockoutTitle }} <span class="collapse-indicator">{{ knockoutSectionOpen ? '▾' : '▸' }}</span></h3>
        <span>{{ t.knockoutNote }}</span>
      </div>
      <div class="wc-collapsible-body" :class="{ collapsed: !knockoutSectionOpen }">
      <div class="wc-bracket-wrap">
        <div v-if="bracketGraph" class="wc-bracket-map">
          <div class="wc-path-side left" :style="bracketSideStyle">
            <svg class="wc-path-lines" :viewBox="bracketViewBox" preserveAspectRatio="none" aria-hidden="true">
              <path v-for="line in bracketLines(bracketGraph.left)" :key="line.key" :d="line.d" />
            </svg>
            <article
              v-for="node in orderedNodes(bracketGraph.left)"
              :key="`left-${node.match_number}`"
              class="wc-path-node"
              tabindex="0"
              :style="nodeStyle(node)"
            >
              <BracketNode
                :node="node"
                :t="t"
                :stage-label="stageLabel"
                :short-date="shortDate"
                :participant-title="participantTitle"
                :participant-meta="participantMeta"
                :participant-state-label="participantStateLabel"
                :candidate-rows="candidateRows"
                :display-team="displayTeam"
                :signed="signed"
                :is-locked="isLocked"
              />
            </article>
          </div>

          <div class="wc-path-center">
            <article v-if="bracketGraph.final" class="wc-final-node" tabindex="0">
              <div class="wc-final-title">{{ t.final }}</div>
              <BracketNode
                :node="bracketGraph.final"
                :t="t"
                :stage-label="stageLabel"
                :short-date="shortDate"
                :participant-title="participantTitle"
                :participant-meta="participantMeta"
                :participant-state-label="participantStateLabel"
                :candidate-rows="candidateRows"
                :display-team="displayTeam"
                :signed="signed"
                :is-locked="isLocked"
                compact
              />
            </article>
            <article v-if="bracketGraph.third_place" class="wc-third-node" tabindex="0">
              <div class="wc-final-title">{{ t.thirdPlace }}</div>
              <BracketNode
                :node="bracketGraph.third_place"
                :t="t"
                :stage-label="stageLabel"
                :short-date="shortDate"
                :participant-title="participantTitle"
                :participant-meta="participantMeta"
                :participant-state-label="participantStateLabel"
                :candidate-rows="candidateRows"
                :display-team="displayTeam"
                :signed="signed"
                :is-locked="isLocked"
                compact
              />
            </article>
          </div>

          <div class="wc-path-side right" :style="bracketSideStyle">
            <svg class="wc-path-lines" :viewBox="bracketViewBox" preserveAspectRatio="none" aria-hidden="true">
              <path v-for="line in bracketLines(bracketGraph.right)" :key="line.key" :d="line.d" />
            </svg>
            <article
              v-for="node in orderedNodes(bracketGraph.right)"
              :key="`right-${node.match_number}`"
              class="wc-path-node"
              tabindex="0"
              :style="nodeStyle(node)"
            >
              <BracketNode
                :node="node"
                :t="t"
                :stage-label="stageLabel"
                :short-date="shortDate"
                :participant-title="participantTitle"
                :participant-meta="participantMeta"
                :participant-state-label="participantStateLabel"
                :candidate-rows="candidateRows"
                :display-team="displayTeam"
                :signed="signed"
                :is-locked="isLocked"
              />
            </article>
          </div>
        </div>
        <div v-else class="wc-bracket-empty">{{ t.noData || '暂无淘汰赛数据' }}</div>
      </div>
      </div>
    </template>
  </section>
</template>

<script>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { worldCupAPI } from '../api'

const BracketNode = defineComponent({
  name: 'BracketNode',
  props: {
    node: { type: Object, required: true },
    t: { type: Object, required: true },
    stageLabel: { type: Function, required: true },
    shortDate: { type: Function, required: true },
    participantTitle: { type: Function, required: true },
    participantMeta: { type: Function, required: true },
    participantStateLabel: { type: Function, required: true },
    candidateRows: { type: Function, required: true },
    displayTeam: { type: Function, required: true },
    signed: { type: Function, required: true },
    isLocked: { type: Function, required: true },
    compact: { type: Boolean, default: false },
  },
  setup(props) {
    const participants = props.node.participants || []
    const p1 = participants[0] || {}
    const p2 = participants[1] || {}
    const team1 = props.participantTitle(p1)
    const team2 = props.participantTitle(p2)
    const state1 = props.participantStateLabel(p1)
    const state2 = props.participantStateLabel(p2)
    const meta1 = props.participantMeta(p1)
    const meta2 = props.participantMeta(p2)
    const rows1 = props.candidateRows(p1)
    const rows2 = props.candidateRows(p2)
    const city = props.node.city || ''
    const locked1 = props.isLocked(p1)
    const locked2 = props.isLocked(p2)

    // "确定 墨西哥 vs 苏格兰 暂定" — P1状态在前，P2状态在后
    const vsChildren = [
      state1 ? h('span', { class: 'wc-vs-s' + (locked1 ? ' locked' : '') }, state1) : null,
      h('span', { class: 'wc-vs-t' + (p1.resolved ? ' r' : '') + (locked1 ? ' locked' : '') }, team1),
      ' vs ',
      h('span', { class: 'wc-vs-t' + (p2.resolved ? ' r' : '') + (locked2 ? ' locked' : '') }, team2),
      state2 ? h('span', { class: 'wc-vs-s' + (locked2 ? ' locked' : '') }, state2) : null,
    ]

    return () => h('div', { class: 'wc-node-inner' }, [
      h('div', { class: 'wc-node-head' }, [
        h('b', null, `M${props.node.match_number} · ${props.shortDate(props.node.date)}`),
      ]),
      city ? h('div', { class: 'wc-node-city' }, city) : null,
      h('div', { class: 'wc-vs-line' }, vsChildren),
      h('div', { class: 'wc-hover-detail' }, [
        h('div', { class: 'wc-hd-stage' }, props.stageLabel(props.node.stage)),
        meta1 ? h('div', { class: 'wc-hd-row' }, [
          h('span', { class: 'wc-hd-name' }, team1), h('span', { class: 'wc-hd-meta' }, meta1),
        ]) : null,
        rows1.length ? h('div', { class: 'wc-hd-cands' }, rows1.map((row) =>
          h('span', { class: 'wc-hd-cand', key: `${p1.slot}-${row.group}` },
            `${row.group}组第三: ${props.displayTeam(row)} (${row.played || 0}场·${row.points || 0}分·净${props.signed(row.goal_diff)})`)
        )) : null,
        meta2 ? h('div', { class: 'wc-hd-row' }, [
          h('span', { class: 'wc-hd-name' }, team2), h('span', { class: 'wc-hd-meta' }, meta2),
        ]) : null,
        rows2.length ? h('div', { class: 'wc-hd-cands' }, rows2.map((row) =>
          h('span', { class: 'wc-hd-cand', key: `${p2.slot}-${row.group}` },
            `${row.group}组第三: ${props.displayTeam(row)} (${row.played || 0}场·${row.points || 0}分·净${props.signed(row.goal_diff)})`)
        )) : null,
      ]),
    ])
  },
})

export default {
  name: 'WorldCupContext',
  components: { BracketNode },
  setup() {
    const context = ref(null)
    const loading = ref(false)
    const error = ref('')
    const liveMode = ref(true)
    const groupSectionOpen = ref(false)
    const thirdSectionOpen = ref(true)
    const knockoutSectionOpen = ref(true)
    const t = {
      title: '世界杯小组与晋级视图',
      liveSource: '实时源',
      refreshing: '刷新中',
      refresh: '刷新',
      loading: '正在加载世界杯上下文...',
      finishedMatches: '场已结束',
      teams: '参赛队',
      groups: '小组',
      topTwo: '前 2',
      directAdvance: '直接晋级',
      bestThird: '最佳第三',
      roundOf32: '32 强',
      knockoutRule: '淘汰赛加时与点球决胜',
      groupShapeTitle: '12 个小组实时形势',
      groupShapeNote: '绿色为直接晋级区，橙色为第三名池',
      rank: '名',
      team: '队',
      played: '赛',
      goalDiff: '净',
      points: '分',
      noTeams: '暂无球队',
      thirdTitle: '小组第三排名',
      thirdNote: '前 8 名进入 32 强，末轮时这里最关键',
      thirdRank: '第三排名',
      group: '小组',
      goalsFor: '进球',
      status: '状态',
      advanceZone: '晋级区',
      chasing: '待追赶',
      knockoutTitle: '淘汰赛路径',
      knockoutNote: '第三名槽位会按当前第三名排名和组合表先显示暂定队，最终以官方落位为准',
      loadFailed: '世界杯上下文加载失败',
      liveApi: '数据源：实时 API',
      localCache: '数据源：本地缓存',
      to: '至',
      round16: '16 强',
      quarterfinals: '1/4 决赛',
      semifinals: '半决赛',
      thirdPlace: '三四名',
      final: '决赛',
      official: '官方',
      finalized: '确定',
      advanced: '晋级',
      projected: '暂列',
      tentative: '暂定',
      candidate: '候选',
      pending: '待定',
      notStarted: '未开',
    }

    const NODE_WIDTH = 160
    const NODE_HEIGHT = 48
    const COLUMN_STEP = 190
    const ROW_STEP = 64
    const BOARD_WIDTH = NODE_WIDTH + COLUMN_STEP * 3
    const BOARD_HEIGHT = NODE_HEIGHT + ROW_STEP * 14 + 44

    const loadContext = async () => {
      loading.value = true
      error.value = ''
      try {
        const data = await worldCupAPI.getContext({ live: liveMode.value })
        if (data.detail) throw new Error(data.detail)
        context.value = data
      } catch (e) {
        error.value = e.message || t.loadFailed
      } finally {
        loading.value = false
      }
    }

    onMounted(loadContext)

    const rules = computed(() => context.value?.rules || {})
    const summary = computed(() => context.value?.matches_summary || { total: 0, finished: 0 })
    const groupsList = computed(() => Object.values(context.value?.groups || {}))
    const thirdRows = computed(() => context.value?.third_place_table?.rows || [])
    const bracketGraph = computed(() => context.value?.knockout?.bracket_graph || null)
    const thirdAssignment = computed(() => context.value?.knockout?.third_place_assignment || {})
    const assignmentStatusText = computed(() => {
      const key = thirdAssignment.value?.assignment_key
      return key ? `第三落位：${key} · 固定规则` : ''
    })
    const bracketSideStyle = computed(() => ({ width: `${BOARD_WIDTH}px`, height: `${BOARD_HEIGHT}px` }))
    const bracketViewBox = computed(() => `0 0 ${BOARD_WIDTH} ${BOARD_HEIGHT}`)
    const sourceLabel = computed(() => {
      const status = context.value?.data_status || {}
      return status.mode === 'live_api' ? t.liveApi : t.localCache
    })
    const tournamentText = computed(() => {
      const tournament = context.value?.tournament || {}
      return `${tournament.start_date || ''} ${t.to} ${tournament.end_date || ''}`
    })
    const signed = (value) => Number(value || 0) > 0 ? `+${value}` : String(value || 0)
    const zoneClass = (team) => {
      if (team.position <= 2) return 'direct'
      if (team.position === 3) return 'third'
      return 'outside'
    }
    const displayTeam = (team) => team?.team_name_cn || team?.name_cn || team?.team_name || team?.name || team?.team_full_name || ''
    const stageLabel = (stage) => {
      const map = {
        round_of_32: t.roundOf32,
        round_of_16: t.round16,
        quarterfinals: t.quarterfinals,
        semifinals: t.semifinals,
        third_place: t.thirdPlace,
        final: t.final,
      }
      return map[stage] || stage || ''
    }
    const shortDate = (date) => String(date || '').slice(5)
    const nodeStyle = (node) => ({
      left: `${((node.column || 1) - 1) * COLUMN_STEP}px`,
      top: `${((node.row || 1) - 1) * ROW_STEP + 8}px`,
      width: `${NODE_WIDTH}px`,
      minHeight: `${NODE_HEIGHT}px`,
    })
    const orderedNodes = (sideGraph) => (sideGraph?.nodes || []).slice().sort((a, b) => (a.column - b.column) || (a.row - b.row) || (a.match_number - b.match_number))
    const bracketLines = (sideGraph) => {
      const nodes = sideGraph?.nodes || []
      const byMatch = new Map(nodes.map(node => [node.match_number, node]))
      const lines = []
      nodes.forEach((parent) => {
        ;(parent.children || []).forEach((childMatch) => {
          const child = byMatch.get(childMatch)
          if (!child) return
          const childLeft = ((child.column || 1) - 1) * COLUMN_STEP
          const parentLeft = ((parent.column || 1) - 1) * COLUMN_STEP
          const parentIsRight = parentLeft > childLeft
          const startX = childLeft + (parentIsRight ? NODE_WIDTH : 0)
          const endX = parentLeft + (parentIsRight ? 0 : NODE_WIDTH)
          const startY = ((child.row || 1) - 1) * ROW_STEP + 8 + NODE_HEIGHT / 2
          const endY = ((parent.row || 1) - 1) * ROW_STEP + 8 + NODE_HEIGHT / 2
          const midX = (startX + endX) / 2
          lines.push({ key: `${child.match_number}-${parent.match_number}`, d: `M ${startX} ${startY} H ${midX} V ${endY} H ${endX}` })
        })
      })
      return lines
    }
    const participantTitle = (participant) => {
      if (participant?.resolved && participant?.team) return displayTeam(participant.team)
      return participant?.display_name || participant?.slot_label || ''
    }
    const participantMeta = (participant) => {
      const team = participant?.team
      if (!team) return ''
      const parts = []
      if (team.group && team.position) {
        parts.push(`${team.group}${team.position}`)
      } else if (team.group) {
        parts.push(`${team.group}组`)
      } else if (team.position) {
        parts.push(`第${team.position}`)
      }
      if (team.third_rank) parts.push(`第三#${team.third_rank}`)
      if (team.played !== undefined) parts.push(`${team.played}场`)
      if (team.points !== undefined) parts.push(`${team.points}分`)
      if (team.goal_diff !== undefined) parts.push(`净${signed(team.goal_diff)}`)
      return parts.join(' · ')
    }
    const participantStateLabel = (participant) => {
      const status = participant?.status || ''
      if (status === 'official_match_team') return t.official
      if (status === 'resolved_from_previous_match_result') return t.advanced
      if (status === 'final_third_place_assignment') return t.finalized
      if (status === 'projected_third_place_assignment') return t.tentative
      if (status === 'locked_group_position') return t.finalized
      if (status === 'projected_from_current_table') return ''
      if (status === 'conditional_third_place_slot') return t.candidate
      if (status === 'unresolved_group_not_started') return t.notStarted
      return ''
    }
    const candidateRows = (participant) => {
      if (participant?.status === 'projected_third_place_assignment' || participant?.status === 'final_third_place_assignment') return []
      const current = participant?.currently_advancing_candidate_rows || []
      const all = participant?.candidate_rows || []
      return (current.length ? current : all).slice(0, 5)
    }
    const isLocked = (participant) => {
      const s = participant?.status || ''
      return s === 'locked_group_position' || s === 'resolved_from_previous_match_result'
    }

    return {
      context,
      t,
      loading,
      error,
      liveMode,
      loadContext,
      rules,
      summary,
      groupsList,
      thirdRows,
      bracketGraph,
      thirdAssignment,
      assignmentStatusText,
      bracketSideStyle,
      bracketViewBox,
      sourceLabel,
      tournamentText,
      signed,
      zoneClass,
      displayTeam,
      stageLabel,
      shortDate,
      nodeStyle,
      orderedNodes,
      bracketLines,
      participantTitle,
      participantMeta,
      participantStateLabel,
      candidateRows,
      isLocked,
    }
  },
}
</script>

<style scoped>
.wc-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: #e5e7eb;
}
.wc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.wc-kicker {
  color: #38bdf8;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.wc-head h2 {
  margin: 2px 0 0;
  font-size: 22px;
  letter-spacing: 0;
}
.wc-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.wc-live-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #a7f3d0;
  font-size: 13px;
}
.wc-refresh {
  border: 1px solid rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.12);
  color: #e0f2fe;
  border-radius: 6px;
  padding: 7px 12px;
  cursor: pointer;
}
.wc-refresh:disabled {
  opacity: 0.55;
  cursor: wait;
}
.wc-loading,
.wc-error {
  padding: 16px;
  border-radius: 6px;
  background: #1e1e2e;
  border: 1px solid #2a2a3a;
}
.wc-error {
  color: #fecaca;
  border-color: rgba(239, 68, 68, 0.45);
}
.wc-status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.wc-status span {
  padding: 5px 8px;
  border-radius: 6px;
  background: #1e293b;
  color: #cbd5e1;
  font-size: 12px;
}
.wc-rule-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 8px;
}
.wc-rule-item {
  min-height: 72px;
  border-radius: 8px;
  background: #111827;
  border: 1px solid #263244;
  padding: 12px;
}
.wc-rule-item b {
  display: block;
  color: #facc15;
  font-size: 22px;
  line-height: 1.1;
}
.wc-rule-item span {
  display: block;
  margin-top: 6px;
  color: #94a3b8;
  font-size: 12px;
}
.wc-section-title {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
}
.wc-collapsible-body {
  overflow: hidden;
  max-height: 2000px;
  transition: max-height 0.35s ease, opacity 0.25s ease;
  opacity: 1;
}
.wc-collapsible-body.collapsed {
  max-height: 0;
  opacity: 0;
  pointer-events: none;
}

.wc-section-title.collapsible {
  cursor: pointer;
  user-select: none;
}
.wc-section-title.collapsible:hover h3 {
  color: #60a5fa;
}
.wc-section-title h3 {
  margin: 0;
  font-size: 18px;
}
.collapse-indicator {
  font-size: 14px;
  margin-left: 6px;
  opacity: 0.6;
}
.wc-section-title span {
  color: #94a3b8;
  font-size: 12px;
}
.wc-groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 10px;
}
.wc-group-card {
  border-radius: 8px;
  background: #151927;
  border: 1px solid #273449;
  overflow: hidden;
}
.wc-group-top {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  background: #1e293b;
}
.wc-group-top strong {
  color: #f8fafc;
}
.wc-group-top span {
  color: #94a3b8;
  font-size: 12px;
}
.wc-table,
.wc-third-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.wc-table th,
.wc-table td,
.wc-third-table th,
.wc-third-table td {
  padding: 7px 6px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  font-size: 12px;
  text-align: center;
}
.wc-table th,
.wc-third-table th {
  color: #94a3b8;
  font-weight: 600;
}
.team-cell {
  text-align: left !important;
  overflow: hidden;
}
.team-cell span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wc-table tr.direct td {
  background: rgba(16, 185, 129, 0.10);
}
.wc-table tr.third td {
  background: rgba(245, 158, 11, 0.10);
}
.wc-table tr.outside td {
  color: #94a3b8;
}
.empty-row td {
  color: #64748b;
}
.wc-third-table-wrap {
  overflow-x: auto;
  border-radius: 8px;
  border: 1px solid #273449;
  background: #111827;
}
.wc-third-table th:nth-child(3),
.wc-third-table td:nth-child(3) {
  width: 190px;
}
.wc-third-table tr.advance td {
  background: rgba(20, 184, 166, 0.10);
}
.wc-third-table tr.out td {
  color: #94a3b8;
}
.wc-bracket-map {
  display: grid;
  grid-template-columns: max-content 180px max-content;
  gap: 8px;
  overflow-x: auto;
  border-radius: 8px;
  border: 1px solid #273449;
  background: #0f1724;
  padding: 10px;
}
.wc-path-side {
  position: relative;
  flex: 0 0 auto;
}
.wc-path-lines {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.wc-path-lines path {
  fill: none;
  stroke: rgba(203, 213, 225, 0.58);
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}
.wc-path-node {
  position: absolute;
  z-index: 1;
  box-sizing: border-box;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: #172033;
  padding: 4px 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  overflow: visible;
  cursor: default;
}
.wc-node-inner {
  display: flex;
  flex-direction: column;
  gap: 3px;
  align-items: center;
  text-align: center;
}
.wc-node-head {
  color: #e2e8f0;
  font-size: 10px;
}
.wc-node-head b {
  display: inline-flex;
  align-items: center;
  border-radius: 3px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: #334155;
  color: #f8fafc;
  font-size: 9px;
  padding: 0 5px;
  white-space: nowrap;
}
.wc-node-city {
  color: #64748b;
  font-size: 9px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-left: 4px;
}

/* VS line and hover detail styles moved to unscoped <style> block below */
.wc-path-center {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 14px;
}
.wc-final-node,
.wc-third-node {
  border-radius: 8px;
  border: 1px solid rgba(250, 204, 21, 0.36);
  background: #172033;
  padding: 10px;
}
.wc-final-node {
  min-height: 0;
  box-shadow: 0 0 0 1px rgba(250, 204, 21, 0.08), 0 6px 16px rgba(0, 0, 0, 0.2);
}
.wc-third-node {
  border-color: rgba(148, 163, 184, 0.28);
}
.wc-final-title {
  margin-bottom: 8px;
  color: #facc15;
  font-size: 13px;
  font-weight: 800;
  text-align: center;
}
@media (max-width: 760px) {
  .wc-head,
  .wc-section-title {
    align-items: flex-start;
    flex-direction: column;
  }
  .wc-actions {
    width: 100%;
    justify-content: space-between;
  }
  .wc-rule-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .wc-rule-item.wide {
    grid-column: span 2;
  }
  .wc-bracket-map {
    display: flex;
    flex-direction: column;
    overflow-x: visible;
    padding: 10px;
  }
  .wc-path-side {
    width: auto !important;
    height: auto !important;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .wc-path-lines {
    display: none;
  }
  .wc-path-node {
    position: static;
    width: auto !important;
    min-height: 0 !important;
    cursor: pointer;
  }
  /* Mobile: tap to show detail */
  .wc-hover-detail {
    display: none;
  }
  .wc-path-node:focus-within .wc-hover-detail,
  .wc-path-node:active .wc-hover-detail,
  .wc-final-node:focus-within .wc-hover-detail,
  .wc-final-node:active .wc-hover-detail,
  .wc-third-node:focus-within .wc-hover-detail,
  .wc-third-node:active .wc-hover-detail {
    display: flex;
  }
  .wc-path-center {
    order: -1;
  }
  .wc-final-node,
  .wc-third-node {
    min-height: 0;
  }
}
</style>

<style>
/* BracketNode styles — must be unscoped because BracketNode uses h() render */
.wc-vs-line {
  font-size: 12px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #94a3b8;
  text-align: left;
}
.wc-vs-t {
  color: #f8fafc;
  font-weight: 600;
}
.wc-vs-t.r {
  color: #5eead4;
}
.wc-vs-t.locked {
  color: #5eead4;
  text-shadow: 0 0 6px rgba(94, 234, 212, 0.4);
}
.wc-vs-s.locked {
  background: rgba(94, 234, 212, 0.18);
  color: #5eead4;
}
.wc-vs-s {
  display: inline;
  border-radius: 3px;
  background: rgba(250, 204, 21, 0.15);
  color: #facc15;
  font-size: 9px;
  font-weight: 600;
  padding: 0 3px;
  margin-left: 2px;
  vertical-align: middle;
  line-height: 14px;
}
.wc-hover-detail {
  display: none;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 9px;
  line-height: 1.4;
}
.wc-path-node:hover .wc-hover-detail,
.wc-final-node:hover .wc-hover-detail,
.wc-third-node:hover .wc-hover-detail {
  display: flex;
}
.wc-hd-stage {
  color: #94a3b8;
  font-weight: 600;
}
.wc-hd-row {
  display: flex;
  gap: 4px;
  align-items: baseline;
}
.wc-hd-name {
  color: #e2e8f0;
  font-weight: 600;
  white-space: nowrap;
}
.wc-hd-meta {
  color: #64748b;
}
.wc-hd-cands {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding-left: 8px;
}
.wc-hd-cand {
  color: #94a3b8;
}
@media (max-width: 760px) {
  .wc-path-node:focus-within .wc-hover-detail,
  .wc-path-node:active .wc-hover-detail,
  .wc-final-node:focus-within .wc-hover-detail,
  .wc-final-node:active .wc-hover-detail,
  .wc-third-node:focus-within .wc-hover-detail,
  .wc-third-node:active .wc-hover-detail {
    display: flex;
  }
  .wc-vs-line {
    font-size: 14px;
    white-space: normal;
  }
}
</style>
