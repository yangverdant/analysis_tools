<template>

  <div class="lottery-center">

    <!-- 顶部统计卡片 -->

    <div class="stats-cards">

      <div class="stat-card">

        <div class="stat-icon matches">

          <ActivityIcon />

        </div>

        <div class="stat-content">

          <div class="stat-value">{{ stats.total_matches }}</div>

          <div class="stat-label">今日开售</div>

        </div>

      </div>

      <div class="stat-card">

        <div class="stat-icon analyzed">

          <BarChartIcon />

        </div>

        <div class="stat-content">

          <div class="stat-value">{{ stats.analyzed_matches }}</div>

          <div class="stat-label">已分析</div>

        </div>

      </div>

      <div class="stat-card">

        <div class="stat-icon value">

          <StarIcon />

        </div>

        <div class="stat-content">

          <div class="stat-value">{{ stats.value_bets }}</div>

          <div class="stat-label">价值投注</div>

        </div>

      </div>

      <div class="stat-card">

        <div class="stat-icon accuracy">

          <TargetIcon />

        </div>

        <div class="stat-content">

          <div class="stat-value">{{ stats.accuracy }}%</div>

          <div class="stat-label">近期准确率</div>

        </div>

      </div>

    </div>

    <!-- Tab切换 -->
    <div class="tab-bar">
      <button :class="['tab-btn', activeTab === 'worldCup' ? 'active' : '']" @click="activeTab = 'worldCup'">&#19990;&#30028;&#26479;</button>
      <button :class="['tab-btn', activeTab === 'matches' ? 'active' : '']" @click="activeTab = 'matches'">比赛</button>
      <button :class="['tab-btn', activeTab === 'review' ? 'active' : '']" @click="activeTab = 'review'; fetchReview()">复盘</button>
      <button :class="['tab-btn', activeTab === 'health' ? 'active' : '']" @click="activeTab = 'health'; fetchHealth()">健康</button>
    </div>

    <!-- 复盘视图 -->
    <WorldCupContext v-if="activeTab === 'worldCup'" />

    <div v-if="activeTab === 'review'" class="review-section">
      <div class="review-filter">
        <select v-model="reviewPlayType" @change="fetchReview()">
          <option value="">全部玩法</option>
          <option value="spf">胜平负</option>
          <option value="ou">大小球</option>
          <option value="bf">比分</option>
          <option value="bqc">半全场</option>
          <option value="rqspf">让球</option>
        </select>
        <select v-model="reviewCorrect" @change="fetchReview()">
          <option value="">全部</option>
          <option value="true">仅正确</option>
          <option value="false">仅错误</option>
        </select>
        <div class="review-summary">
          <span>共 {{ reviewSummary.total }}条</span>
          <span>准确率 {{ reviewSummary.accuracy }}%</span>
        </div>
      </div>
      <div v-if="reviewInsights && reviewInsights.summary" class="review-insights">
        <div class="review-insight-cards">
          <div class="review-insight-card">
            <span>复盘覆盖</span>
            <b>{{ reviewInsights.summary.reasoned_rate || 0 }}%</b>
            <small>{{ reviewInsights.summary.reasoned || 0 }}/{{ reviewInsights.summary.total || 0 }}</small>
          </div>
          <div class="review-insight-card danger">
            <span>高置信错</span>
            <b>{{ reviewInsights.summary.high_confidence_errors || 0 }}</b>
            <small>需要重点复核</small>
          </div>
          <div class="review-insight-card warn">
            <span>赔率分歧错</span>
            <b>{{ reviewInsights.summary.market_divergence_errors || 0 }}</b>
            <small>权重需校准</small>
          </div>
          <div class="review-insight-card info">
            <span>情报弱错</span>
            <b>{{ reviewInsights.summary.low_intelligence_errors || 0 }}</b>
            <small>采集需补强</small>
          </div>
        </div>
        <div class="review-insight-grid">
          <div class="review-insight-panel">
            <div class="review-insight-title">玩法表现</div>
            <div v-for="item in (reviewInsights.by_play_type || []).slice(0, 5)" :key="item.play_type" class="review-insight-row">
              <span>{{ playTypeLabel(item.play_type) }}</span>
              <b>{{ item.accuracy }}%</b>
              <small>{{ item.correct }}/{{ item.total }}</small>
            </div>
          </div>
          <div class="review-insight-panel">
            <div class="review-insight-title">错误标签</div>
            <div v-for="item in (reviewInsights.wrong_tags || []).slice(0, 6)" :key="item.key" class="review-insight-row">
              <span>{{ reviewTagLabel(item.key) }}</span>
              <b>{{ item.count }}</b>
              <small>{{ item.rate }}%</small>
            </div>
          </div>
          <div class="review-insight-panel">
            <div class="review-insight-title">下一步动作</div>
            <div v-for="item in (reviewInsights.action_items || []).slice(0, 6)" :key="item.key" class="review-insight-row">
              <span>{{ actionItemLabel(item.key) }}</span>
              <b>{{ item.count }}</b>
              <small>{{ item.rate }}%</small>
            </div>
          </div>
        </div>
        <div v-if="reviewInsights.high_confidence_errors && reviewInsights.high_confidence_errors.length" class="review-error-strip">
          <div class="review-insight-title">高置信错误样例</div>
          <div class="review-error-chips">
            <span v-for="item in reviewInsights.high_confidence_errors.slice(0, 4)" :key="item.review_id" :title="item.reason_text">
              {{ item.home_team }} vs {{ item.away_team }} · {{ playTypeLabel(item.play_type) }}
            </span>
          </div>
        </div>
      </div>
      <div v-if="reviewLoading" class="loading-state"><div class="spinner"></div><span>加载中...</span></div>
      <div v-else-if="reviewRecords.length === 0" class="empty-state"><p>暂无复盘数据</p></div>
      <div v-else class="review-list">
        <div v-for="r in reviewRecords" :key="r.id" class="review-row" :class="{ 'correct': r.is_correct, 'wrong': !r.is_correct }">
          <div class="review-main">
            <span class="review-play-type">{{ playTypeLabel(r.play_type) }}</span>
            <span class="review-teams">{{ r.home_team }} vs {{ r.away_team }}</span>
            <span class="review-pred">{{ r.predicted }}</span>
            <span class="review-actual">实际: {{ r.actual }}</span>
            <span :class="['review-result', r.is_correct ? 'ok' : 'fail']">{{ r.is_correct ? '正确' : '错误' }}</span>
          </div>
          <div class="review-meta">
            <span>{{ r.match_date }}</span>
            <span>{{ r.league }}</span>
            <span v-if="r.attribution" class="review-attr">{{ r.attribution }}</span>
            <span v-if="r.confidence" class="review-conf">置信{{ r.confidence }}%</span>
          </div>
          <div v-if="r.reason_text" class="review-reason">{{ r.reason_text }}</div>
          <div v-if="r.learning_tags && r.learning_tags.length" class="review-tags">
            <span v-for="tag in r.learning_tags.slice(0, 5)" :key="tag">{{ reviewTagLabel(tag) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 健康视图 -->
    <div v-if="activeTab === 'health'" class="health-section">
      <div v-if="healthLoading" class="loading-state"><div class="spinner"></div><span>加载中...</span></div>
      <div v-else-if="healthData" class="health-grid">
        <div class="health-card">
          <div class="health-label">今日比赛</div>
          <div class="health-value">{{ healthData.today_matches }}场</div>
          <div class="health-sub">有赔率: {{ healthData.today_with_odds }} / 已分析: {{ healthData.today_analyzed }}</div>
        </div>
        <div class="health-card">
          <div class="health-label">最后采集</div>
          <div class="health-value">{{ healthData.last_collection || '无' }}</div>
        </div>
        <div class="health-card">
          <div class="health-label">最后分析</div>
          <div class="health-value">{{ healthData.last_analysis || '无' }}</div>
        </div>
        <div class="health-card">
          <div class="health-label">验证记录</div>
          <div class="health-value">{{ healthData.total_validations }}条</div>
          <div class="health-sub">
            <span v-for="(count, pt) in healthData.validation_by_type" :key="pt">{{ playTypeLabel(pt) }}: {{ count }} </span>
          </div>
        </div>
        <div class="health-card">
          <div class="health-label">O/U数据新鲜度</div>
          <div class="health-value">{{ healthData.ou_fresh_count }}场近24h</div>
        </div>
      </div>
      <div v-if="schedulerData" class="auto-loop-panel">
        <div class="auto-loop-head">
          <div>
            <h3>自动闭环</h3>
            <span>{{ schedulerStateText }}</span>
          </div>
          <div class="auto-loop-actions">
            <button v-if="latestAutomationCenterFailedCount" class="range-refresh-btn primary" @click="retryAutomationFailures" :disabled="schedulerTriggering">重试失败{{ latestAutomationCenterFailedCount }}</button>
            <button v-if="automationControlEnabled" class="range-refresh-btn" @click="stopAutomationControl" :disabled="schedulerTriggering">停止中控</button>
            <button v-if="schedulerData.running && !schedulerData.paused" class="range-refresh-btn pause" @click="pauseScheduler" :disabled="schedulerTriggering">暂停自动</button>
            <button v-else class="range-refresh-btn primary" @click="resumeScheduler" :disabled="schedulerTriggering">启动自动</button>
            <button class="range-refresh-btn" @click="triggerSchedulerJob('rolling_collection')" :disabled="schedulerTriggering">立即滚动</button>
            <button class="range-refresh-btn primary" @click="triggerAutomationCenter" :disabled="schedulerTriggering">并发中控</button>
            <button class="range-refresh-btn" @click="triggerSchedulerJob('historical_backfill')" :disabled="schedulerTriggering">立即补历史</button>
            <button class="range-refresh-btn" @click="triggerSchedulerJob('intelligence_gap_fill')" :disabled="schedulerTriggering">补情报</button>
            <button class="range-refresh-btn" @click="syncOddsfeOuLines" :disabled="ouLineSyncing">补真实O/U盘</button>
            <button class="range-refresh-btn" @click="triggerSchedulerJob('validate_cycle')" :disabled="schedulerTriggering">复盘验证</button>
            <button class="range-refresh-btn primary" @click="runAutoGapFill" :disabled="autoGapRunning">自动补齐</button>
          </div>
        </div>
        <div v-if="schedulerTriggerResult" :class="['auto-loop-trigger', schedulerTriggerResult.error ? 'bad' : 'ok']">
          {{ schedulerTriggerResult.message }}
        </div>
        <div v-if="ouLineSyncResult" :class="['auto-loop-trigger', ouLineSyncResult.error ? 'bad' : 'ok']">
          {{ ouLineSyncResult.message }}
        </div>
        <div v-if="autoGapResult" :class="['auto-loop-trigger', autoGapResult.error ? 'bad' : 'ok']">
          {{ autoGapResult.message }}
        </div>
        <div v-if="automationDashboardData" class="automation-dashboard-strip">
          <div v-for="card in automationDashboardCards" :key="card.key" :class="['automation-dashboard-card', card.state]">
            <span>{{ card.label }}</span>
            <b>{{ card.value }}</b>
            <small>{{ card.detail }}</small>
          </div>
        </div>
        <div class="automation-status-strip">
          <div v-for="card in automationStatusCards" :key="card.key" :class="['automation-status-card', card.state]">
            <span>{{ card.label }}</span>
            <b>{{ card.value }}</b>
            <small>{{ card.detail }}</small>
          </div>
        </div>
        <div v-if="modelStatusData" class="mc-model-strip">
          <div class="mc-model-tag">
            <span class="mc-model-label">模型版本</span>
            <span class="mc-model-ver">{{ modelStatusData.model_version }}</span>
          </div>
          <div class="mc-model-tag">
            <span class="mc-model-label">30日准确率</span>
            <span class="mc-model-acc">{{ (modelStatusData.current_accuracy_30d * 100).toFixed(1) }}%</span>
          </div>
          <div v-if="modelStatusData.gate" class="mc-model-tag">
            <span class="mc-model-label">Gate</span>
            <span class="mc-model-gate">ON</span>
          </div>
          <div v-if="modelStatusData.recent_changes?.length" class="mc-model-changes">
            <span class="mc-model-label">最近变更</span>
            <span>{{ modelStatusData.recent_changes.length }}项</span>
          </div>
          <div v-if="modelStatusData.play_accuracy_targets" class="mc-model-targets">
            <span class="mc-model-label">玩法达标</span>
            <span v-for="(pt, key) in modelStatusData.play_accuracy_targets" :key="key" :class="['mc-target-dot', pt.met ? 'met' : 'miss']" :title="`${key}: ${(pt.current*100).toFixed(1)}% / 目标${(pt.target*100).toFixed(0)}% (${pt.gap_pp > 0 ? '+' : ''}${pt.gap_pp}pp)`">
              {{ key }}
            </span>
          </div>
        </div>
        <!-- Accuracy trend mini chart -->
        <div v-if="accuracyTrendData.length > 2" class="mc-trend-section">
          <div class="mc-trend-header">
            <span class="mc-trend-title">准确率趋势</span>
            <div class="mc-trend-toggle">
              <button :class="['mc-trend-btn', accuracyTrendGranularity === 'day' ? 'active' : '']" @click="accuracyTrendGranularity = 'day'; fetchAccuracyTrend()">日</button>
              <button :class="['mc-trend-btn', accuracyTrendGranularity === 'week' ? 'active' : '']" @click="accuracyTrendGranularity = 'week'; fetchAccuracyTrend()">周</button>
            </div>
          </div>
          <div class="mc-trend-chart">
            <div v-for="item in accuracyTrendData" :key="item.period" class="mc-trend-bar-wrap" :title="`${item.period}: ${item.accuracy}% (${item.correct}/${item.total})`">
              <div class="mc-trend-bar" :style="{ height: Math.max(2, item.accuracy) + '%' }" :class="item.accuracy >= 52 ? 'good' : item.accuracy >= 45 ? 'ok' : 'low'"></div>
            </div>
          </div>
          <div class="mc-trend-axis">
            <span>{{ accuracyTrendData[0]?.period?.slice(5) }}</span>
            <span>{{ accuracyTrendData[Math.floor(accuracyTrendData.length / 2)]?.period?.slice(5) }}</span>
            <span>{{ accuracyTrendData[accuracyTrendData.length - 1]?.period?.slice(5) }}</span>
          </div>
        </div>
        <div class="auto-loop-section-title compact">
          <b>自动效果</b>
          <span>最近30天复盘、当前缺口和卡住任务合并看</span>
        </div>
        <div class="automation-effect-grid">
          <div v-for="card in automationEffectCards" :key="card.key" :class="['automation-effect-card', card.state]">
            <span>{{ card.label }}</span>
            <b>{{ card.value }}</b>
            <small>{{ card.detail }}</small>
          </div>
        </div>
        <div class="auto-loop-section-title">
          <b>下一次调度</b>
          <span>后台服务不关闭，就会按窗口持续采集、分析、复盘和补历史</span>
        </div>
        <div class="auto-loop-grid">
          <div v-for="job in schedulerCoreJobs" :key="job.id" :class="['auto-loop-job', job.state]">
            <b>{{ job.next }}</b>
            <span>{{ job.label }}</span>
            <small>{{ job.detail }}</small>
          </div>
        </div>
        <div v-if="latestPipelineRun" class="pipeline-run-card">
          <div class="pipeline-run-head">
            <div>
              <b>{{ schedulerRunLabel(latestPipelineRun) }}</b>
              <span>{{ latestPipelineRun.started_at }} · {{ latestPipelineRun.status }}</span>
            </div>
            <small>{{ latestPipelineRun.match_date || latestPipelineRun.summary?.date || '-' }}</small>
          </div>
          <div class="pipeline-steps">
            <div v-for="step in pipelineStepCards" :key="step.key" :class="['pipeline-step', step.state]">
              <span>{{ step.label }}</span>
              <b>{{ step.value }}</b>
              <small>{{ step.detail }}</small>
            </div>
          </div>
        </div>
        <div v-if="automationTimelineRuns.length" class="auto-loop-runs">
          <div class="auto-loop-section-title compact">
            <b>后台任务时间线</b>
            <span>最近采集、自动补齐、学习刷新都会留痕</span>
          </div>
          <div v-for="run in automationTimelineRuns" :key="run.run_id" :class="['auto-loop-run', runStatusClass(run.status)]">
            <span>{{ schedulerRunLabel(run) }}</span>
            <b>{{ runStatusLabel(run.status) }}</b>
            <em>{{ triggerSourceLabel(run.trigger_source) }}</em>
            <small :title="autoRunSummaryText(run)">{{ formatRunTime(run.started_at) }} · {{ runWindowText(run) }} · {{ autoRunSummaryText(run) }}</small>
          </div>
        </div>
        <div v-if="latestAutomationCenterRun" class="automation-center-panel">
          <div class="auto-loop-section-title compact">
            <b>并发中控明细</b>
            <span>{{ automationCenterBrief }}</span>
          </div>
          <div class="automation-center-grid">
            <div v-for="row in automationCenterTaskRows" :key="row.key" :class="['automation-center-row', row.state]">
              <div class="automation-center-row-head">
                <b>{{ row.label }}</b>
                <span>{{ row.date }}</span>
                <em>{{ row.status }}</em>
                <button
                  v-if="row.state === 'failed'"
                  class="automation-row-retry"
                  @click.stop="retryAutomationTask(row)"
                  :disabled="schedulerTriggering"
                >重试</button>
              </div>
              <p :title="row.summary">{{ row.summary }}</p>
              <small v-if="row.detail" :title="row.detail">{{ row.detail }}</small>
            </div>
          </div>
        </div>
        <div v-if="latestAutoRun" class="auto-loop-latest">
          <span>最新：{{ schedulerRunLabel(latestAutoRun) }}</span>
          <span>{{ triggerSourceLabel(latestAutoRun.trigger_source) }}</span>
          <span>{{ runWindowText(latestAutoRun) }}</span>
          <span>{{ autoRunSummaryText(latestAutoRun) }}</span>
        </div>
      </div>
      <div v-if="automationAuditData" class="automation-audit-panel">
        <div class="automation-audit-head">
          <div>
            <h3>自动化体检</h3>
            <span>{{ automationAuditData.generated_at }} · 近{{ automationAuditData.window?.recent_hours || 24 }}小时</span>
          </div>
          <b :class="['automation-audit-status', auditFindings.length ? 'warn' : 'ok']">
            {{ auditFindings.length ? `${auditFindings.length}项风险` : '正常' }}
          </b>
        </div>
        <div class="automation-audit-summary">
          <div :class="{ warn: auditSeverityCounts.high > 0 }">
            <b>{{ auditSeverityCounts.high }}</b>
            <span>高风险</span>
          </div>
          <div :class="{ warn: Number(automationAuditData.completeness?.summary?.missing_total || 0) > 0 }">
            <b>{{ automationAuditData.completeness?.summary?.missing_total || 0 }}</b>
            <span>窗口缺口</span>
          </div>
          <div :class="{ warn: (automationAuditData.collection_runs?.stale_running || []).length > 0 }">
            <b>{{ (automationAuditData.collection_runs?.stale_running || []).length }}</b>
            <span>卡住任务</span>
          </div>
          <div :class="{ warn: Number(automationAuditData.analysis_reports?.active_duplicate_report_rows || 0) > 0 }">
            <b>{{ automationAuditData.analysis_reports?.active_duplicate_report_rows || 0 }}</b>
            <span>活跃重复报告</span>
          </div>
          <div :class="{ warn: Number(automationAuditData.analysis_reports?.recent_active_duplicate_rows || 0) > 0 }">
            <b>{{ automationAuditData.analysis_reports?.recent_active_duplicate_rows || 0 }}</b>
            <span>近期活跃重复</span>
          </div>
          <div>
            <b>{{ auditMb(automationAuditData.db?.free_mb) }}</b>
            <span>库可复用空间</span>
          </div>
        </div>
        <div v-if="auditFindings.length" class="automation-audit-findings">
          <div v-for="item in auditFindings" :key="item.code" :class="['automation-audit-finding', item.severity]">
            <b>{{ auditSeverityLabel(item.severity) }}</b>
            <span>{{ item.message }}</span>
          </div>
        </div>
        <div v-if="auditTopDuplicates.length" class="automation-dup-list">
          <div class="automation-dup-title">{{ auditDuplicateTitle }}</div>
          <div v-for="row in auditTopDuplicates" :key="row.lottery_match_id" class="automation-dup-row">
            <b>{{ row.lottery_match_id }}</b>
            <span>{{ row.report_count }}份</span>
            <small>最新 {{ row.latest_report_at || '-' }}</small>
          </div>
        </div>
      </div>
      <div v-if="healthRangeData" class="range-health-panel">
        <div class="range-health-head">
          <div>
            <h3>世界杯数据完整性</h3>
            <span>{{ healthRangeData.range?.start_date }} 至 {{ healthRangeData.range?.end_date }}</span>
          </div>
          <button class="range-refresh-btn" @click="fetchHealth" :disabled="healthLoading">刷新</button>
        </div>
        <div class="range-health-summary">
          <div>
            <b>{{ healthRangeData.summary?.total || 0 }}</b>
            <span>比赛</span>
          </div>
          <div>
            <b>{{ healthRangeData.summary?.complete_dates || 0 }}/{{ healthRangeData.summary?.dates || 0 }}</b>
            <span>完整日期</span>
          </div>
          <div :class="{ warn: (healthRangeData.summary?.missing_total || 0) > 0 }">
            <b>{{ healthRangeData.summary?.missing_total || 0 }}</b>
            <span>缺口</span>
          </div>
          <div :class="{ warn: (healthRangeData.summary?.missing_ou_line || 0) > 0 }">
            <b>{{ healthRangeData.summary?.missing_ou_line || 0 }}</b>
            <span>缺真实O/U盘</span>
          </div>
          <div>
            <b>{{ healthRangeData.summary?.missing_intelligence || 0 }}</b>
            <span>缺情报</span>
          </div>
          <div>
            <b>{{ healthRangeData.summary?.missing_analysis || 0 }}</b>
            <span>缺分析</span>
          </div>
          <div>
            <b>{{ healthRangeData.summary?.missing_validation || 0 }}</b>
            <span>待复盘</span>
          </div>
          <div>
            <b>{{ healthRangeData.summary?.missing_post_review || 0 }}</b>
            <span>待沉淀</span>
          </div>
          <div>
            <b>{{ healthRangeData.summary?.schedule_fallback || 0 }}</b>
            <span>赛程占位</span>
          </div>
        </div>
        <div v-if="gapPlanItems.length" class="gap-plan-grid">
          <div v-for="item in gapPlanItems" :key="item.action" :class="['gap-plan-card', gapActionState(item)]">
            <div class="gap-plan-top">
              <b>{{ item.label }}</b>
              <span>{{ item.count }}项</span>
            </div>
            <small>{{ item.detail }}</small>
            <em>自动任务：{{ item.auto_job }}</em>
            <div v-if="item.examples?.length" class="gap-plan-examples">
              <span v-for="example in item.examples.slice(0, 3)" :key="`${item.action}-${example.lottery_match_id}`" :title="gapExampleTitle(example)">
                {{ gapExampleShort(example) }}
              </span>
            </div>
          </div>
        </div>
        <div class="range-table-wrap">
          <table class="range-health-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>场</th>
                <th>赔率</th>
                <th>真实O/U盘</th>
                <th>赛果</th>
                <th>半场</th>
                <th>分析</th>
                <th>情报</th>
                <th>证据</th>
                <th>复盘</th>
                <th>沉淀</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="day in healthRangeData.days || []" :key="day.date" :class="{ complete: day.complete, problem: !day.complete }">
                <td>{{ day.date }}</td>
                <td>{{ day.summary?.total || 0 }}</td>
                <td>{{ completenessCell(day.summary, 'with_odds', 'missing_odds') }}</td>
                <td>{{ completenessCell(day.summary, 'with_ou_line', 'missing_ou_line') }}</td>
                <td>{{ completenessCell(day.summary, 'with_score', 'missing_score') }}</td>
                <td>{{ completenessCell(day.summary, 'with_half_score', 'missing_half_score') }}</td>
                <td>{{ completenessCell(day.summary, 'with_analysis', 'missing_analysis') }}</td>
                <td>{{ completenessCell(day.summary, 'with_intelligence', 'missing_intelligence') }}</td>
                <td>{{ completenessCell(day.summary, 'with_event_cache', 'missing_event_cache') }}</td>
                <td>{{ completenessCell(day.summary, 'with_validation', 'missing_validation') }}</td>
                <td>{{ completenessCell(day.summary, 'with_post_review', 'missing_post_review') }}</td>
                <td><span :class="['range-status', day.complete ? 'ok' : 'warn']">{{ day.complete ? '完整' : '待补齐' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 比赛视图(默认) -->
    <div v-if="activeTab === 'matches'">

    <!-- 准确率追踪面板 -->

    <div class="accuracy-panel">

      <h3>预测准确率追踪</h3>

      <div class="accuracy-grid">

        <div class="accuracy-item">

          <span class="accuracy-label">胜平负</span>

          <span class="accuracy-value">{{ accuracyValue(accuracyData.spf, accuracyData.spf_count) }}</span>

          <span class="accuracy-sample">{{ accuracySample(accuracyData.spf_count) }}</span>

        </div>

        <div class="accuracy-item">

          <span class="accuracy-label">比分预测</span>

          <span class="accuracy-value">{{ accuracyValue(accuracyData.bf, accuracyData.bf_count) }}</span>

          <span class="accuracy-sample">{{ accuracySample(accuracyData.bf_count) }}</span>

        </div>

        <div class="accuracy-item">

          <span class="accuracy-label">让球胜平负</span>

          <span class="accuracy-value">{{ accuracyValue(accuracyData.rqspf, accuracyData.rqspf_count) }}</span>

          <span class="accuracy-sample">{{ accuracySample(accuracyData.rqspf_count) }}</span>

        </div>

        <div class="accuracy-item">

          <span class="accuracy-label">半全场</span>

          <span class="accuracy-value">{{ accuracyValue(accuracyData.bqc, accuracyData.bqc_count) }}</span>

          <span class="accuracy-sample">{{ accuracySample(accuracyData.bqc_count) }}</span>

        </div>

        <div class="accuracy-item">

          <span class="accuracy-label">大小球</span>

          <span class="accuracy-value">{{ accuracyValue(accuracyData.ou, accuracyData.ou_count) }}</span>

          <span class="accuracy-sample">{{ accuracySample(accuracyData.ou_count) }}</span>

        </div>

        <div class="accuracy-item">

          <span class="accuracy-label">整体</span>

          <span class="accuracy-value overall">{{ accuracyValue(accuracyData.overall, accuracyData.total_count) }}</span>

          <span class="accuracy-sample">{{ accuracySample(accuracyData.total_count) }}</span>

        </div>

      </div>

      <div class="accuracy-trend">

        <span class="trend-label">近期趋势:</span>

        <span :class="['trend-value', trendClass(accuracyData.trend)]">

          {{ accuracyData.trend > 0 ? '上升' : (accuracyData.trend < 0 ? '下降' : '稳定') }}

        </span>

      </div>

    </div>



    <!-- 日期选择、玩法筛选、采集按钮 -->

    <div class="filter-bar">

      <div class="date-picker">

        <button class="date-nav" @click="changeDate(-1)">

          <ChevronLeftIcon />

        </button>

        <div class="current-date">

          <CalendarIcon class="calendar-icon" />

          <span>{{ formatDate(selectedDate) }}</span>

        </div>

        <button class="date-nav" @click="changeDate(1)">

          <ChevronRightIcon />

        </button>

      </div>

      <div class="sync-area">
        <button class="sync-btn result-sync-btn" :disabled="resultSyncing" @click="syncEventDetails">

          <span>{{ resultSyncing ? '赛果补齐中...' : '赛果补齐' }}</span>

        </button>

        <div class="result-sync-controls">
          <label>
            <span>每批</span>
            <select v-model.number="eventSyncMaxEvents" :disabled="resultSyncing">
              <option :value="2">2</option>
              <option :value="4">4</option>
              <option :value="8">8</option>
              <option :value="12">12</option>
            </select>
          </label>
          <label>
            <span>批数</span>
            <select v-model.number="eventSyncBatches" :disabled="resultSyncing">
              <option :value="1">1</option>
              <option :value="3">3</option>
              <option :value="5">5</option>
              <option :value="8">8</option>
            </select>
          </label>
          <label>
            <span>间隔</span>
            <select v-model.number="eventSyncGap" :disabled="resultSyncing">
              <option :value="0">0s</option>
              <option :value="2">2s</option>
              <option :value="5">5s</option>
              <option :value="10">10s</option>
            </select>
          </label>
        </div>

        <div v-if="resultSyncResult" class="sync-result">
          <span v-if="!resultSyncResult.error" class="sync-ok">{{ resultSyncResult.skipped ? '已有补齐任务' : '赛果补齐完成' }}</span>
          <span v-else class="sync-fail">{{ resultSyncResult.error }}</span>
          <span>{{ resultSyncResult.batches }}批</span>
          <span>{{ resultSyncResult.fetched }}个event</span>
          <span v-if="resultSyncResult.remaining != null" class="sync-status">剩余{{ resultSyncResult.remaining }}</span>
        </div>

      </div>

    </div>



    <!-- 比赛列表 -->

    <div class="matches-section">

      <div v-if="matches.length" class="data-health-strip">
        <div class="data-health-metrics">
          <span>缺赔率 {{ completenessSummary.missingOdds }}</span>
          <span>缺真实O/U盘 {{ completenessSummary.missingOuLine }}</span>
          <span>缺赛果 {{ completenessSummary.missingScore }}</span>
          <span>缺半场 {{ completenessSummary.missingHalf }}</span>
          <span>未分析 {{ completenessSummary.missingAnalysis }}</span>
          <span>缺情报 {{ completenessSummary.missingIntel }}</span>
        </div>
        <button :class="['missing-toggle', showIncompleteOnly ? 'active' : '']" @click="showIncompleteOnly = !showIncompleteOnly">
          {{ showIncompleteOnly ? '显示全部' : '只看缺失' }}
        </button>
      </div>

      <div v-if="loading" class="loading-state">

        <div class="spinner"></div>

        <span>加载中...</span>

      </div>



      <div v-else-if="matches.length === 0" class="empty-state">

        <ActivityIcon class="empty-icon" />

        <p>暂无开售比赛</p>

      </div>



      <div v-else class="matches-grid">

        <div

          v-for="match in filteredMatches"

          :key="match.lottery_match_id"

          class="match-card"

          @click="viewMatchDetail(match)"

        >

          <!-- 卡片头部：编号 + 联赛 + 时间 -->

          <div class="mc-header">

            <span class="mc-num">{{ match.match_num }}</span>

            <span class="mc-league">{{ match.league_name_cn }}</span>

            <span class="mc-time">{{ formatMatchTime(match) }}</span>

          </div>



          <!-- 球队 + 比分 -->

          <div class="mc-teams">

            <div class="mc-team-col">

              <span v-if="getHandicapLabel(match)" class="mc-hcp-badge">{{ getHandicapLabel(match) }}</span>
              <span class="mc-team-name home">{{ match.home_team_cn }}</span>

              <span v-if="match.spf_odds" class="mc-odds-line">

                <span class="mc-odds-val">{{ match.spf_odds["3"] }}</span>

                <span class="mc-odds-sep">/</span>

                <span class="mc-odds-val">{{ match.spf_odds["1"] }}</span>

                <span class="mc-odds-sep">/</span>

                <span class="mc-odds-val">{{ match.spf_odds["0"] }}</span>

              </span>

            </div>

            <div class="mc-score-col">

              <template v-if="match.match_status === 'finished' && match.home_goals_ft != null">

                <span class="mc-score">{{ match.home_goals_ft }}-{{ match.away_goals_ft }}</span>
                <span v-if="match.home_goals_ht != null && match.away_goals_ht != null" class="mc-ht-score">
                  {{ match.home_goals_ht }}-{{ match.away_goals_ht }}
                  {{ (match.home_goals_ft - match.home_goals_ht) }}-{{ (match.away_goals_ft - match.away_goals_ht) }}
                </span>
                <span v-else class="mc-ft-tag">FT</span>

              </template>

              <template v-else>

                <span v-if="getHandicapLabel(match)" class="mc-hcp">{{ getHandicapLabel(match) }}</span>

                <span v-else class="mc-vs">VS</span>

              </template>

            </div>

            <div class="mc-team-col away">

              <span class="mc-team-name away">{{ match.away_team_cn }}</span>

              <span v-if="match.rqspf_odds" class="mc-odds-line">

                <span class="mc-odds-label">让</span>

                <span class="mc-odds-val">{{ match.rqspf_odds["3"] }}</span>

                <span class="mc-odds-sep">/</span>

                <span class="mc-odds-val">{{ match.rqspf_odds["1"] }}</span>

                <span class="mc-odds-sep">/</span>

                <span class="mc-odds-val">{{ match.rqspf_odds["0"] }}</span>

              </span>

            </div>

          </div>



          <!-- 预测 + 赛果 紧凑表格 -->

          <div v-if="!match.is_schedule_fallback && (match.has_analysis || match.match_status === 'finished')" class="mc-pred-grid">

            <div class="mc-pred-row">

              <span class="mc-pred-type">胜平负</span>

              <span class="mc-pred-val blue">{{ spfCardRecommendation(match) }}</span>

              <span v-if="match.match_status === 'finished' && match.spf_result" class="mc-pred-arrow">→</span>

              <span v-else class="mc-pred-spacer"></span>

              <span v-if="match.match_status === 'finished' && match.spf_result" :class="['mc-pred-val', 'tag', samePrediction(spfCardRecommendation(match), match.spf_result) ? 'ok' : 'no']">

                {{ match.spf_result }}

              </span>

              <span v-else class="mc-pred-conf" :class="match.confidence_tier || match.confidence_level">{{ confidenceTierLabel(match) }}</span>

            </div>

            <div class="mc-pred-row">

              <span class="mc-pred-type">让球胜平负</span>

              <span class="mc-pred-val blue">{{ rqspfCardRecommendation(match) }}</span>

              <span v-if="match.match_status === 'finished' && match.rqspf_result" class="mc-pred-arrow">→</span>

              <span v-else class="mc-pred-spacer"></span>

              <span v-if="match.match_status === 'finished' && match.rqspf_result" :class="['mc-pred-val', 'tag', samePrediction(rqspfCardRecommendation(match), match.rqspf_result) ? 'ok' : 'no']">{{ match.rqspf_result }}</span>

              <span v-else class="mc-pred-spacer"></span>

            </div>

            <div class="mc-pred-row">

              <span class="mc-pred-type">半全场</span>

              <span class="mc-pred-val blue">{{ bqcCardRecommendation(match) }}</span>

              <span v-if="match.match_status === 'finished' && match.bqc_result" class="mc-pred-arrow">→</span>

              <span v-else class="mc-pred-spacer"></span>

              <span v-if="match.match_status === 'finished' && match.bqc_result" :class="['mc-pred-val', 'tag', samePrediction(bqcCardRecommendation(match), match.bqc_result) ? 'ok' : 'no']">{{ match.bqc_result }}</span>

              <span v-else class="mc-pred-spacer"></span>

            </div>

            <div class="mc-pred-row">

              <span class="mc-pred-type">大小球</span>

              <span class="mc-pred-val blue">{{ formatOuDisplay(ouCardRecommendation(match)) }}</span>

              <span v-if="match.match_status === 'finished' && match.ou_result" class="mc-pred-arrow">→</span>

              <span v-else class="mc-pred-spacer"></span>

              <span v-if="match.match_status === 'finished' && match.ou_result" :class="['mc-pred-val', 'tag', sameOuOutcome(ouCardRecommendation(match), match.ou_result) ? 'ok' : 'no']">{{ formatOuDisplay(match.ou_result) }}</span>

              <span v-else class="mc-pred-spacer"></span>

            </div>

          </div>

          <div v-else-if="!match.is_schedule_fallback" class="no-analysis">

            <button class="analyze-btn" @click.stop="analyzeMatch(match)">

              <BarChartIcon />

              <span>分析</span>

            </button>

          </div>

          <!-- 情报证据状态：服务体彩中心主流程，不作为独立入口 -->
          <div v-if="!match.is_schedule_fallback && getMatchIntelligence(match)" :class="['mc-intel-strip', getIntelligenceClass(match)]">
            <span class="mc-intel-main">{{ intelligenceCoverageLabel(getMatchIntelligence(match)) }}</span>
            <span class="mc-intel-sub">{{ intelligenceMissingLabel(getMatchIntelligence(match)) }}</span>
          </div>
          <div v-else-if="!match.is_schedule_fallback && intelligenceAvailable && !intelligenceLoading" class="mc-intel-strip missing">
            <span class="mc-intel-main">未建情报包</span>
            <span class="mc-intel-sub">待补齐</span>
          </div>

          <!-- Source health for intelligence requirements -->
          <div v-if="intelSourceHealth.length > 0" class="mc-source-health">
            <span v-for="sh in intelSourceHealth" :key="sh.key" :class="['mc-sh-dot', sh.status]" :title="sh.detail">
              {{ sh.label }}
            </span>
          </div>



          <!-- 销售状态 -->

          <div class="sell-status">

            <span :class="['status-badge', match.match_status || match.sell_status]">

              {{ getSellStatusLabel(match.match_status || match.sell_status) }}

            </span>

            <span v-if="match.is_schedule_fallback" class="source-badge schedule">赛程</span>
            <span v-if="match.score_source === 'oddsfe_event_api'" class="source-badge oddsfe">oddsfe赛果</span>
            <span v-if="match.score_source === 'oddsfe_event_cache'" class="source-badge oddsfe">oddsfe缓存</span>
            <span v-if="match.score_source === 'oddsfe_schedule_cache'" class="source-badge schedule">赛程比分</span>
            <span
              v-for="item in dataCompleteness(match)"
              :key="item.key"
              :class="['source-badge', 'quality-badge', item.status]"
            >{{ item.label }}</span>
            <button
              v-if="canRefreshResult(match)"
              class="result-refresh-btn"
              :disabled="Boolean(resultRefreshingById[String(match.lottery_match_id)])"
              @click.stop="refreshMatchResult(match)"
            >
              {{ resultRefreshingById[String(match.lottery_match_id)] ? '刷新中' : '刷新赛果' }}
            </button>
            <button
              v-if="canCorrectResult(match)"
              class="result-correct-btn"
              @click.stop="openResultCorrection(match)"
            >
              异常纠错
            </button>

          </div>

        </div>

      </div>

    </div>

    </div><!-- end matches tab -->



    <!-- 分析详情弹窗 -->

    <div v-if="showDetailModal" class="modal-overlay" @click="closeDetailModal">

      <div class="modal-content" @click.stop>

        <div class="modal-header">

          <h2>分析详情</h2>

          <button class="close-btn" @click="closeDetailModal">

            <CloseIcon />

          </button>

        </div>

        <div class="modal-body">

          <LotteryAnalysisDetail v-if="selectedMatch" :match="selectedMatch" :source-health="sourceHealthData" />

        </div>

      </div>

    </div>

    <div v-if="showResultCorrectionModal" class="modal-overlay" @click="closeResultCorrection">

      <form class="result-correction-modal" @submit.prevent="submitResultCorrection" @click.stop>

        <div class="modal-header">

          <h2>{{ resultCorrectionMatch?.home_team_cn }} vs {{ resultCorrectionMatch?.away_team_cn }}</h2>

          <button type="button" class="close-btn" @click="closeResultCorrection">

            <CloseIcon />

          </button>

        </div>

        <div class="result-correction-body">

          <div class="result-correction-title">仅在数据源赛果仍然错误时使用；系统会保留修正审计，并触发后续复盘重算</div>

          <div class="result-score-grid">

            <label>
              <span>主队全场</span>
              <input v-model="resultCorrectionForm.home_goals_ft" type="number" min="0" required />
            </label>

            <label>
              <span>客队全场</span>
              <input v-model="resultCorrectionForm.away_goals_ft" type="number" min="0" required />
            </label>

            <label>
              <span>主队半场</span>
              <input v-model="resultCorrectionForm.home_goals_ht" type="number" min="0" />
            </label>

            <label>
              <span>客队半场</span>
              <input v-model="resultCorrectionForm.away_goals_ht" type="number" min="0" />
            </label>

          </div>

          <label class="result-reason-field">
            <span>原因</span>
            <textarea v-model="resultCorrectionForm.reason" rows="3" placeholder="例如：oddsfe赛果源错误，按官方比分修正"></textarea>
          </label>

          <div v-if="resultCorrectionError" class="result-correction-error">{{ resultCorrectionError }}</div>

        </div>

        <div class="result-correction-actions">

          <button type="button" class="secondary-btn" @click="closeResultCorrection">取消</button>

          <button type="submit" class="primary-btn" :disabled="resultCorrectionSaving">
            {{ resultCorrectionSaving ? '保存中...' : '保存修正' }}
          </button>

        </div>

      </form>

    </div>

  </div>

</template>



<script>

import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

import { h, defineComponent } from 'vue'

import { userAPI, intelligenceAPI, lotteryAPI, cycleAPI } from '../api'
import WorldCupContext from './WorldCupContext.vue'



// 图标组件

const createIcon = (name, classStr, paths) => defineComponent({

  name,

  setup: () => () => h('svg', { class: classStr, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, paths)

})



const ActivityIcon = createIcon('ActivityIcon', 'w-3 h-3', [

  h('polyline', { points: '22 12 18 12 15 21 9 3 6 12 2 12' })

])



const BarChartIcon = createIcon('BarChartIcon', 'w-3 h-3', [

  h('line', { x1: '18', y1: '20', x2: '18', y2: '10' }),

  h('line', { x1: '12', y1: '20', x2: '12', y2: '4' }),

  h('line', { x1: '6', y1: '20', x2: '6', y2: '14' })

])



const StarIcon = createIcon('StarIcon', 'w-3 h-3', [

  h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' })

])



const TargetIcon = createIcon('TargetIcon', 'w-3 h-3', [

  h('circle', { cx: '12', cy: '12', r: '10' }),

  h('circle', { cx: '12', cy: '12', r: '6' }),

  h('circle', { cx: '12', cy: '12', r: '2' })

])



const CalendarIcon = createIcon('CalendarIcon', 'w-3 h-3', [

  h('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }),

  h('line', { x1: '16', y1: '2', x2: '16', y2: '6' }),

  h('line', { x1: '8', y1: '2', x2: '8', y2: '6' }),

  h('line', { x1: '3', y1: '10', x2: '21', y2: '10' })

])



const ChevronLeftIcon = createIcon('ChevronLeftIcon', 'w-3 h-3', [

  h('polyline', { points: '15 18 9 12 15 6' })

])



const ChevronRightIcon = createIcon('ChevronRightIcon', 'w-3 h-3', [

  h('polyline', { points: '9 18 15 12 9 6' })

])



const CloseIcon = createIcon('CloseIcon', 'w-3 h-3', [

  h('line', { x1: '18', y1: '6', x2: '6', y2: '18' }),

  h('line', { x1: '6', y1: '6', x2: '18', y2: '18' })

])



const RefreshIcon = createIcon('RefreshIcon', 'w-3 h-3', [

  h('polyline', { points: '23 4 23 10 17 10' }),

  h('polyline', { points: '1 20 1 14 7 14' }),

  h('path', { d: 'M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15' })

])



const REQUIREMENT_LABELS = {
  base_info: '基础信息',
  odds_1x2: '胜平负赔率',
  market_movement: '盘口变化',
  recent_form: '近期状态',
  team_news: '球队新闻',
  injuries_suspensions: '伤停停赛',
  expected_lineup: '预计首发',
  weather: '天气场地',
  data_quality: '数据质量',
  fifa_ranking: 'FIFA排名',
  elo_rating: 'ELO强度',
  tournament_context: '赛事语境',
  travel_fatigue: '旅途疲劳',
  major_tournament_experience: '大赛经验',
  standings_context: '积分形势',
  home_away_profile: '主客画像',
  schedule_congestion: '赛程密度'
}

const requirementLabel = (key) => REQUIREMENT_LABELS[key] || key



// 分析详情组件 — 5大模块：比赛信息 / AI推荐 / 概率分析 / 玩法推荐 / 分析因子+AI解释

const LotteryAnalysisDetail = defineComponent({
  name: 'LotteryAnalysisDetail',
  props: { match: Object, sourceHealth: Object },
  setup(props) {
    const report = ref(null)
    const loading = ref(true)
    const showFactors = ref(false)
    const intelligencePackage = ref(null)
    const intelligencePackageLoading = ref(false)
    const reanalysisChanges = ref([])
    const reanalysisLoading = ref(false)
    const matchScript = ref(null)
    const matchScriptLoading = ref(false)

    const fetchReport = async () => {
      if (!props.match?.lottery_match_id) return
      // Prefer inline report from analyzeMatch (avoids extra API call)
      if (props.match._report?._learning) {
        report.value = props.match._report
        loading.value = false
        return
      }
      loading.value = true
      try {
        const response = await fetch(`/api/v1/lottery/report/${props.match.lottery_match_id}`)
        if (response.ok) {
          const data = await response.json()
          const loadedReport = data.report || {}
          if (data.learning && typeof loadedReport === 'object') {
            loadedReport._learning = data.learning
          }
          report.value = loadedReport
          props.match._report = loadedReport
        }
      } catch (e) {
        console.error('获取报告失败:', e)
      } finally {
        loading.value = false
      }
    }

    const fetchIntelligencePackage = async () => {
      const jobId = props.match?._intelligenceJob?.job_id
      if (props.match?._intelPackage) {
        intelligencePackage.value = props.match._intelPackage
        return
      }
      if (!jobId) {
        intelligencePackage.value = null
        return
      }
      intelligencePackageLoading.value = true
      try {
        const data = await intelligenceAPI.getPackage(jobId)
        if (data.detail) throw new Error(data.detail)
        intelligencePackage.value = data
        props.match._intelPackage = data
      } catch (e) {
        console.warn('获取情报包失败:', e)
        intelligencePackage.value = null
      } finally {
        intelligencePackageLoading.value = false
      }
    }

    onMounted(fetchReport)
    watch(() => props.match?.lottery_match_id, fetchReport)
    onMounted(fetchIntelligencePackage)
    watch(() => props.match?._intelligenceJob?.job_id, fetchIntelligencePackage)

    const fetchReanalysisChanges = async () => {
      const mid = props.match?.lottery_match_id
      if (!mid) return
      reanalysisLoading.value = true
      try {
        const data = await lotteryAPI.getReanalysisChanges(mid)
        reanalysisChanges.value = Array.isArray(data?.changes) ? data.changes : []
      } catch (e) {
        reanalysisChanges.value = []
      } finally {
        reanalysisLoading.value = false
      }
    }
    onMounted(fetchReanalysisChanges)
    watch(() => props.match?.lottery_match_id, fetchReanalysisChanges)

    const fetchMatchScript = async () => {
      const mid = props.match?.lottery_match_id
      if (!mid) return
      matchScriptLoading.value = true
      try {
        const data = await lotteryAPI.getMatchScript(mid)
        matchScript.value = data?.success ? data.match_script : null
      } catch (e) {
        matchScript.value = null
      } finally {
        matchScriptLoading.value = false
      }
    }
    onMounted(fetchMatchScript)
    watch(() => props.match?.lottery_match_id, fetchMatchScript)

    const RL = { 'home_win': '主胜', 'draw': '平局', 'away_win': '客胜', '3': '主胜', '1': '平局', '0': '客胜' }
    const BQC = {
      '33': '胜胜', '31': '胜平', '30': '胜负',
      '13': '平胜', '11': '平平', '10': '平负',
      '03': '负胜', '01': '负平', '00': '负负',
      'hh': '胜胜', 'hd': '胜平', 'ha': '胜负',
      'dh': '平胜', 'dd': '平平', 'da': '平负',
      'ah': '负胜', 'ad': '负平', 'aa': '负负'
    }
    const COMP = { 'league': '联赛', 'friendly': '友谊赛', 'domestic_cup': '国内杯赛', 'continental_cup': '洲际杯赛', 'qualifier': '预选赛', 'nations_league': '欧国联', 'tournament_intl': '国际赛事', 'international_cup': '国际杯赛' }
    const WT_CN = { 'odds': '赔率模型', 'elo': 'ELO评分', 'poisson': 'Poisson', 'form': '近期状态', 'motivation': '动机', 'friendly': '友谊赛修正', 'cup': '杯赛修正', 'home_away': '主客场', 'other': '其他' }
    const WT_COLOR = { 'odds': '#10b981', 'elo': '#3b82f6', 'poisson': '#8b5cf6', 'form': '#f59e0b', 'motivation': '#ef4444', 'friendly': '#f59e0b', 'cup': '#f59e0b', 'home_away': '#3b82f6', 'market_movement': '#22c55e', 'travel_fatigue': '#0ea5e9', 'major_tournament_experience': '#f97316', 'other': '#6b7280' }
    const PLAY_CN = { spf: '胜平负', rqspf: '让球胜平负', ou: '大小球', bf: '比分', bqc: '半全场' }
    const ATTR_CN = {
      bad_luck: '低概率事件',
      close_match: '势均力敌',
      correction_wrong: '修正偏差',
      market_wrong: '市场信号偏差',
      intel_missing: '情报缺口'
    }
    const resultLabel = (value, playType = '') => {
      const text = value == null ? '' : String(value)
      if (playType === 'rqspf') {
        const rq = { home_win: '让胜', draw: '让平', away_win: '让负', '3': '让胜', '1': '让平', '0': '让负', 主胜: '让胜', 平局: '让平', 客胜: '让负' }
        return rq[text] || text || '--'
      }
      return RL[text] || BQC[text] || text || '--'
    }
    const pressureReasonLabel = (value) => ({
      missing_standing: '缺少实时积分',
      opening_round_positioning: '首轮定位阶段',
      win_can_push_direct_qualification: '赢球可推动直接晋级',
      needs_points_before_final_round: '末轮前需要抢分',
      group_shape_still_open: '小组形势仍开放',
      protect_or_improve_draw_position: '保护或提升落位',
      third_place_and_goal_difference_pressure: '第三名与净胜球压力',
      must_win_or_chase_margin: '必须赢球或追净胜球',
      live_world_cup_group_pressure_context: '实时小组压力',
      no_directional_group_pressure_edge: '小组压力差异不明显'
    }[value] || value || '晋级压力')
    const attributionLabel = (value) => ATTR_CN[value] || value || ''
    const reviewTagLabel = (tag) => {
      const text = String(tag || '')
      const direct = {
        'result:correct': '命中',
        'result:wrong': '未命中',
        'market:aligned': '赔率一致',
        'market:diverged': '赔率分歧',
        'intel:fallback_used': '兜底情报',
        'intel:low_confidence': '低置信情报',
        'context:world_cup': '世界杯语境'
      }
      if (direct[text]) return direct[text]
      if (text.startsWith('play:')) return PLAY_CN[text.slice(5)] || text.slice(5)
      if (text.startsWith('confidence:')) return `置信${text.slice(11)}`
      if (text.startsWith('world_cup:matchday_')) return `小组第${text.split('_').pop()}轮`
      if (text.startsWith('scenario:')) return text.slice(9)
      if (text.startsWith('pressure:')) {
        const raw = text.slice(9)
        const [side, ...rest] = raw.split('_')
        const sideLabel = side === 'home' ? '主队' : side === 'away' ? '客队' : ''
        return [sideLabel, pressureReasonLabel(rest.join('_') || raw)].filter(Boolean).join(' ')
      }
      return text
    }
    const gapLabel = (value, digits = 2) => {
      const n = Number(value)
      if (!Number.isFinite(n)) return ''
      return Math.abs(n) >= 1 ? n.toFixed(1).replace(/\.0$/, '') : n.toFixed(digits).replace(/0+$/, '').replace(/\.$/, '')
    }
    const playReferenceLabel = (profile = {}, fallback = '') => {
      return profile.reference_label || profile.risk_label || fallback || ''
    }
    const rqspfGateText = (data = {}) => {
      const gate = data.handicap_margin_gate_adjustment || data.consistency_gate_adjustment || {}
      const boundary = data.boundary_profile || {}
      if (!gate.source && !boundary.gate_override_direction) return ''
      const to = gate.to || boundary.gate_override_cn || data.recommendation_cn || ''
      const from = gate.from || data.unconditional_recommendation_cn || data.pre_handicap_margin_gate_direction || ''
      const reasonLabel = {
        positive_tail_cover: '强队净胜尾部更集中',
        negative_tail_cover: '受让方被穿盘风险更高',
        exact_margin_weak: '正好赢盘边界支撑不足',
        rqspf_impossible_under_trusted_spf: '与胜平负主轴冲突后校正',
        rqspf_impossible_under_bqc_axis: '与半全场终局方向冲突后校正',
        rqspf_margin_boundary: '让球边界回测'
      }[gate.reason] || gate.reason || '让球边界回测'
      const selectedProbability = Number(gate.selected_probability ?? boundary.gate_override_probability)
      const probabilityText = Number.isFinite(selectedProbability) && selectedProbability > 0
        ? `，覆盖概率${Math.round(selectedProbability * 100)}%`
        : ''
      const requirement = gate.margin_requirement || data.margin_requirement || ''
      const move = from && to && from !== to ? `${from} → ${to}` : to
      return `门禁覆盖：${move || '让球方向'}；${reasonLabel}${probabilityText}${requirement ? `；${requirement}` : ''}`
    }
    const playDerivationSummary = (playType, data = {}, fallback = {}) => {
      const gateText = playType === 'rqspf' ? rqspfGateText(data) : ''
      if (data.derivation?.summary) {
        const baseSummary = data.derivation.summary
        return gateText && !baseSummary.includes('门禁覆盖') ? `${baseSummary}；${gateText}` : baseSummary
      }
      const direction = fallback.direction || '胜平负方向'
      const ouText = fallback.ouText || '进球区间'
      let summary = ''
      if (playType === 'spf') summary = `主轴方向：${direction}`
      if (playType === 'ou') summary = `进球区间：${ouText}`
      if (playType === 'rqspf') summary = `由${direction}方向叠加让球线推导净胜球区间`
      if (playType === 'bqc') summary = `由${direction}方向和${ouText}推导半场路径`
      if (playType === 'bf') summary = `由${direction}方向 + ${ouText}推导比分落点`
      if (playType === 'rqspf' && gateText) return summary ? `${summary}；${gateText}` : gateText
      if (summary) return summary
      return ''
    }
    const similarReasonTags = (reasons = {}) => {
      const tags = []
      const add = (ok, text) => {
        if (ok && text && !tags.includes(text)) tags.push(text)
      }
      add(reasons.same_world_cup_context, '世界杯')
      add(!reasons.same_world_cup_context && reasons.same_category, '同赛事')
      add(reasons.same_prediction, '同预测')
      add(reasons.same_odds_rec, '同赔率')
      add(reasons.same_spf_direction, '同方向')
      add(reasons.same_market_bucket, '同市场')
      add(reasons.same_ou_direction, '同大小球')
      add(reasons.same_wc_pressure_pair, '同压力')
      add(reasons.wc_matchday_gap === 0, '同轮次')
      add(reasons.wc_matchday_gap === 1, '邻轮次')
      const handicapGap = Number(reasons.handicap_gap)
      add(Number.isFinite(handicapGap) && handicapGap <= 0.25, '同盘口')
      add(Number.isFinite(handicapGap) && handicapGap > 0.25 && handicapGap <= 1, '盘口±' + gapLabel(handicapGap, 1))
      const probGap = Number(reasons.probability_distance)
      add(Number.isFinite(probGap) && probGap <= 0.08, '模型近')
      add(Number.isFinite(probGap) && probGap > 0.08 && probGap <= 0.14, '模型较近')
      const oddsGap = Number(reasons.odds_probability_distance)
      add(Number.isFinite(oddsGap) && oddsGap <= 0.06, '赔率近')
      add(Number.isFinite(oddsGap) && oddsGap > 0.06 && oddsGap <= 0.12, '赔率较近')
      const totalGap = Number(reasons.expected_total_gap)
      add(Number.isFinite(totalGap) && totalGap <= 0.35, '总球近')
      const intelGap = Number(reasons.intel_completeness_gap)
      add(Number.isFinite(intelGap) && intelGap <= 10, '情报近')
      add((reasons.shared_missing_required || []).length > 0, '缺口相似')
      return tags.slice(0, 6)
    }
    const similarReasonTitle = (reasons = {}) => {
      const lines = []
      if (reasons.same_world_cup_context) lines.push('世界杯语境相同')
      if (reasons.same_category) lines.push('赛事类别相同')
      if (reasons.same_prediction) lines.push('模型预测方向一致')
      if (reasons.same_odds_rec) lines.push('赔率方向一致')
      if (reasons.same_spf_direction) lines.push('胜平负方向一致')
      if (reasons.same_ou_direction) lines.push('大小球方向一致')
      if (reasons.same_wc_pressure_pair) lines.push('小组压力组合相近')
      if (reasons.wc_matchday_gap != null) lines.push('世界杯轮次差: ' + reasons.wc_matchday_gap)
      if (reasons.handicap_gap != null) lines.push('盘口差: ' + gapLabel(reasons.handicap_gap, 2))
      if (reasons.probability_distance != null) lines.push('模型概率距离: ' + gapLabel(reasons.probability_distance, 4))
      if (reasons.odds_probability_distance != null) lines.push('赔率隐含概率距离: ' + gapLabel(reasons.odds_probability_distance, 4))
      if (reasons.expected_total_gap != null) lines.push('预期总进球差: ' + gapLabel(reasons.expected_total_gap, 2))
      const componentScores = reasons.component_scores || {}
      const scoreText = Object.entries(componentScores)
        .map(([key, value]) => key + ':' + gapLabel(value, 2))
        .join(' / ')
      if (scoreText) lines.push('分项: ' + scoreText)
      return lines.join('\n')
    }

    const similarCaseTeamsText = (item = {}) => {
      const home = item.home_team || ''
      const away = item.away_team || ''
      if (!home || !away) return item.similar_match_key || ''
      const scoreText = item.score || (
        item.home_goals_ft != null && item.away_goals_ft != null
          ? item.home_goals_ft + ':' + item.away_goals_ft
          : ''
      )
      return scoreText ? `${home} ${scoreText} ${away}` : `${home} vs ${away}`
    }

    const fmtNumber = (value, digits = 1) => {
      const n = Number(value)
      if (!Number.isFinite(n)) return '--'
      return n.toFixed(digits).replace(/\.0$/, '')
    }
    const fmtOdds = (value) => {
      const n = Number(value)
      if (!Number.isFinite(n)) return '--'
      return n >= 10 ? n.toFixed(1).replace(/\.0$/, '') : n.toFixed(2).replace(/0$/, '').replace(/\.$/, '')
    }
    const PLAY_TYPE_LABELS = { spf: '胜平负', rqspf: '让球胜平负', bf: '比分', bqc: '半全场', ttg: '总进球' }
    const movementText = (movement) => {
      if (!movement) return ''
      const play = PLAY_TYPE_LABELS[movement.play_type] || movement.play_type || '赔率'
      const label = movement.label || movement.key || ''
      return play + ' ' + label + ' ' + fmtOdds(movement.opening) + '→' + fmtOdds(movement.latest)
    }
    const summarizeMarketArtifact = (artifact) => {
      const payload = artifact?.payload || {}
      if (!payload.source_rows) return null
      const movements = payload.significant_movements || []
      const preferred = movements.filter(item => ['spf', 'rqspf'].includes(item.play_type))
      const top = (preferred.length ? preferred : movements).slice(0, 3)
      const primary = top[0]
      const summary = primary
        ? movementText(primary)
        : (payload.has_comparable_snapshots ? '开盘/即时盘可比，暂无明显方向变化' : '盘口快照不足，暂不能判断变化')
      const detail = top.length > 1 ? top.map(movementText).join('；') : summary
      return {
        key: 'market_movement',
        title: '盘口变化',
        value: payload.has_movement ? '有变化' : '平稳',
        summary,
        detail,
        confidence: artifact.confidence,
        color: '#22c55e',
        factorDetail: { label: '盘口变化', value: summary, color: '#22c55e' },
        explanation: '盘口变化已按真实开盘/即时盘快照计算：' + summary + '。'
      }
    }
    const summarizeTravelArtifact = (artifact, homeName, awayName) => {
      const payload = artifact?.payload || {}
      const home = payload.home || {}
      const away = payload.away || {}
      if (home.rest_days == null && away.rest_days == null) return null
      const homeRest = home.rest_days == null ? '--' : fmtNumber(home.rest_days, 1) + '天'
      const awayRest = away.rest_days == null ? '--' : fmtNumber(away.rest_days, 1) + '天'
      const delta = payload.comparison?.rest_hours_delta_home_minus_away
      const deltaText = delta == null ? '' : '，差' + fmtNumber(Math.abs(delta) / 24, 1) + '天'
      const shortSide = payload.comparison?.short_rest_side
      const homeRestNum = Number(home.rest_days)
      const awayRestNum = Number(away.rest_days)
      const bothLongGap = Number.isFinite(homeRestNum) && Number.isFinite(awayRestNum) && homeRestNum > 21 && awayRestNum > 21
      const pressureText = shortSide === 'both' ? '双方短休' : shortSide === 'home' ? homeName + '短休' : shortSide === 'away' ? awayName + '短休' : bothLongGap ? '长间隔样本' : '无短休'
      const summary = homeName + '间隔' + homeRest + ' / ' + awayName + '间隔' + awayRest + deltaText
      const title = bothLongGap ? '赛前间隔' : '休息赛程'
      const explanation = bothLongGap
        ? '这里是数据库可追溯上一场到本场的间隔，只作为赛程节奏参考，不直接等同于真实体能优势：' + summary + '。'
        : '赛程疲劳按真实赛程计算，重点关注短休和连续作战：' + summary + '。'
      return {
        key: 'travel_fatigue',
        title,
        value: pressureText,
        summary,
        detail: (payload.gaps || []).length ? summary + '；缺口：' + payload.gaps.slice(0, 2).join('；') : summary,
        confidence: artifact.confidence,
        color: '#0ea5e9',
        factorDetail: { label: title, value: summary, color: '#0ea5e9' },
        explanation
      }
    }
    const summarizeExperienceArtifact = (artifact, homeName, awayName) => {
      const payload = artifact?.payload || {}
      const homeDb = payload.home?.db || {}
      const awayDb = payload.away?.db || {}
      const homeMajor = Number(homeDb.major_matches || 0)
      const awayMajor = Number(awayDb.major_matches || 0)
      const homeWorldCup = Number(homeDb.world_cup_matches || 0)
      const awayWorldCup = Number(awayDb.world_cup_matches || 0)
      if (!homeMajor && !awayMajor && !homeWorldCup && !awayWorldCup) return null
      const majorDelta = homeMajor - awayMajor
      const leader = Math.abs(majorDelta) < 3 ? '接近' : majorDelta > 0 ? homeName + '更足' : awayName + '更足'
      const summary = '大赛 ' + homeName + homeMajor + '场 / ' + awayName + awayMajor + '场；世界杯 ' + homeWorldCup + '/' + awayWorldCup + '场'
      return {
        key: 'major_tournament_experience',
        title: '大赛经验',
        value: leader,
        summary,
        detail: summary,
        confidence: artifact.confidence,
        color: '#f97316',
        factorDetail: { label: '大赛经验', value: summary, color: '#f97316' },
        explanation: '大赛经验来自已结束历史比赛统计：' + summary + '。'
      }
    }

    // Derive BQC recommendation from SPF prediction when BQC data is missing
    const deriveBQC = (fp, ppBqc, anBqc) => {
      if (ppBqc?.recommendation || ppBqc?.recommendation_cn || ppBqc?.direction) return ppBqc
      if (anBqc?.recommendation || anBqc?.direction) return anBqc
      // Derive from final_prediction: if predicting home_win → likely hh, draw → dd, away_win → aa
      const dir = fp?.predicted_result
      if (!dir) return null
      const bqcDir = { 'home_win': 'hh', '3': 'hh', 'draw': 'dd', '1': 'dd', 'away_win': 'aa', '0': 'aa' }[dir]
      if (!bqcDir) return null
      return { direction: bqcDir, recommendation_cn: BQC[bqcDir], derived: true }
    }

    // Derive O/U data when missing from play_predictions
    const deriveOU = (ppOu, anOu, xgA, fp) => {
      if (ppOu?.recommendation) return ppOu
      if (anOu?.recommendation) return anOu
      // Derive from xG: if total xG > 2.5, recommend over
      const totalXg = (xgA?.home_xg || 0) + (xgA?.away_xg || 0)
      const expTotal = fp?.expected_score ? (fp.expected_score.home || 0) + (fp.expected_score.away || 0) : totalXg
      if (expTotal <= 0) return null
      const overProb = Math.min(0.85, Math.max(0.25, 0.5 + (expTotal - 2.5) * 0.3))
      return {
        recommendation: overProb >= 0.5 ? '大2.5' : '小2.5',
        over_2_5: overProb,
        under_2_5: 1 - overProb,
        line: 2.5,
        diagnostics: {
          line: 2.5,
          expected_total: expTotal,
          model_side: overProb >= 0.5 ? 'over' : 'under',
          over_line_probability: overProb,
          under_line_probability: 1 - overProb,
          conflict_level: 'unknown',
          flags: ['缺少真实大小球盘时由预期总进球兜底'],
          summary: '兜底估算：预期总进球' + fmtNumber(expTotal, 2)
        },
        derived: true
      }
    }

    const genExplanationLines = (r, homeTeam, awayTeam) => {
      const lines = []
      const fp = r.final_prediction || {}
      const mvo = r.model_vs_odds || {}
      const xg = r.xg_analysis || {}
      const form = r.form_comparison || {}
      const motivation = r.motivation_analysis || {}
      const h2h = r.h2h_analysis || {}
      const rec = RL[fp.predicted_result] || fp.predicted_result

      if (xg.home_xg && xg.away_xg) {
        lines.push(homeTeam + '预期进球' + xg.home_xg.toFixed(1) + '，' + awayTeam + '预期进球' + xg.away_xg.toFixed(1) + '。')
      }
      const t1f = form.last6?.team1_form || form.last6?.home || form.last6?.home_team || {}
      const t2f = form.last6?.team2_form || form.last6?.away || form.last6?.away_team || {}
      if (t1f.form_score && t2f.form_score) {
        const diff = t1f.form_score - t2f.form_score
        if (diff > 20) lines.push(homeTeam + '近期状态明显占优(状态分' + t1f.form_score + ')。')
        else if (diff < -20) lines.push(awayTeam + '近期状态明显占优(状态分' + t2f.form_score + ')。')
        else lines.push('双方近期状态接近(' + homeTeam + t1f.form_score + ' vs ' + awayTeam + t2f.form_score + ')。')
      }
      if (h2h.total_matches > 0) {
        const hr = h2h.overall_record || {}
        lines.push('历史交锋' + h2h.total_matches + '场：' + (hr.team1_wins || hr.home_wins || 0) + '胜' + (hr.draws || 0) + '平' + (hr.team2_wins || hr.away_wins || 0) + '负。')
      }
      const hm = motivation.home_motivation || {}
      const am = motivation.away_motivation || {}
      if (hm.motivation_type && am.motivation_type) {
        if (hm.motivation_level === 'high' && am.motivation_level !== 'high') lines.push(homeTeam + '战意更强。')
        else if (am.motivation_level === 'high' && hm.motivation_level !== 'high') lines.push(awayTeam + '战意更强。')
      }
      if (mvo.agreement === true) {
        lines.push('赔率走势与模型判断一致，推荐' + rec + '可信度较高。')
      } else if (mvo.agreement === false) {
        lines.push('模型与赔率方向分歧，需注意风险。')
      }
      return lines
    }

    return () => {
      if (loading.value) {
        return h('div', { class: 'analysis-detail' }, [
          h('div', { class: 'ad-loading' }, [h('div', { class: 'spinner' }), h('span', '分析中...')])
        ])
      }

      const r = report.value
      if (!r) return h('div', { class: 'analysis-detail' }, [h('p', { class: 'ad-empty' }, '暂无分析报告')])

      // Support two report formats:
      // 1. core/analyze.py: final_prediction, play_predictions, odds_baseline, etc.
      // 2. analysis_service: analyses.spf, analyses.ou, analyses.bqc, etc.
      const analyses = r.analyses || {}
      const fp = r.final_prediction || {}
      const probs = fp.probabilities || {}
      const pp = r.play_predictions || {}
      const oddsBL = r.odds_baseline || {}
      const mvo = r.model_vs_odds || {}
      const motivation = r.motivation_analysis || {}
      const formComp = r.form_comparison || {}
      const h2h = r.h2h_analysis || {}
      const xgA = r.xg_analysis || {}
      const mp = r.match_profile || {}
      const weightsUsed = r.weights_used || {}
      const weights = weightsUsed.weights || {}
      const adjustments = r.adjustments || []
      const provenance = r.factor_breakdown?.provenance || {}

      const homeTeam = props.match?.home_team_cn || r.match_info?.home_team_cn || r.home_team_cn || '主队'
      const awayTeam = props.match?.away_team_cn || r.match_info?.away_team_cn || r.away_team_cn || '客队'
      const leagueName = props.match?.league_name_cn || r.match_info?.league_name_cn || r.league_name_cn || ''
      const compLabel = COMP[mp.competition_type] || mp.competition_type || ''

      // SPF probabilities: play_predictions format or analyses format
      const spfP = pp.spf?.probabilities || analyses.spf?.probabilities || probs
      const homeP = spfP.home_win || spfP['3'] || 0
      const drawP = spfP.draw || spfP['1'] || 0
      const awayP = spfP.away_win || spfP['0'] || 0
      const oH = oddsBL.home_win || 0, oD = oddsBL.draw || 0, oA = oddsBL.away_win || 0

      const rec = RL[fp.predicted_result] || analyses.spf?.recommendation || fp.predicted_result || '--'
      const confLevel = fp.confidence_level || analyses.spf?.confidence_level || 'low'
      const confPct = fp.confidence ? Math.round(fp.confidence * 100) : analyses.spf?.confidence ? Math.round(analyses.spf.confidence * 100) : 0
      const confColor = { high: '#10b981', medium: '#f59e0b', low: '#6b7280' }[confLevel]
      const confCN = { high: '强烈推荐', medium: '谨慎推荐', low: '仅供参考' }[confLevel]
      const stars = confLevel === 'high' ? 5 : confLevel === 'medium' ? 3 : 1

      const expScore = fp.expected_score || {}
      const matchTime = props.match?.beijing_time || props.match?.match_time || r.match_info?.match_time || ''

      // O/U data: play_predictions format or analyses.ou format
      const ouData = pp.ou || pp.over_under || analyses.ou || {}

      // Odds consistency (model vs odds agreement percentage)
      // Also check match-level spf_odds when report lacks odds_baseline
      const matchOdds = props.match?.spf_odds || {}
      const effectiveOddsH = oH || (matchOdds['3'] ? 1 / matchOdds['3'] : 0)
      const effectiveOddsD = oD || (matchOdds['1'] ? 1 / matchOdds['1'] : 0)
      const effectiveOddsA = oA || (matchOdds['0'] ? 1 / matchOdds['0'] : 0)
      const mvoAgreement = mvo.agreement
      const hasOddsData = effectiveOddsH > 0 || effectiveOddsD > 0 || effectiveOddsA > 0
      const oddsConsPct = mvoAgreement === true ? 96 : mvoAgreement === false ? 35 : (hasOddsData ? 70 : 0)
      const oddsConsText = mvoAgreement === true ? '高一致' : mvoAgreement === false ? '有分歧' : (hasOddsData ? '基本一致' : '暂无赔率')

      const intelEnvelope = props.match?._intelPackage || intelligencePackage.value
      const intelPackage = intelEnvelope?.package || {}
      const intelSummary = intelPackage.summary || intelEnvelope?.package_summary || {}
      const intelligenceAdjustment = r.intelligence_adjustment || {}
      const guardEvidence = r.analysis_guard?.evidence || {}
      const guardLowConfidence = Array.isArray(guardEvidence.low_confidence_critical) ? guardEvidence.low_confidence_critical : []
      const intelMissing = intelEnvelope?.missing_required || intelSummary.missing_required || guardEvidence.missing_required || guardEvidence.missing_critical || []
      const intelCompleteness = Math.round(Number(intelEnvelope?.completeness ?? intelSummary.completeness ?? intelligenceAdjustment.package_completeness ?? guardEvidence.package_completeness ?? 0))
      const intelStrict = Math.round(Number(intelEnvelope?.strict_completeness ?? intelSummary.strict_completeness ?? intelligenceAdjustment.strict_completeness ?? guardEvidence.strict_completeness ?? 0))
      const intelAverage = Number(intelSummary.average_confidence ?? props.match?._intelligenceJob?.average_confidence ?? intelligenceAdjustment.average_confidence ?? guardEvidence.average_confidence ?? 0)
      const intelAveragePct = intelAverage > 1 ? Math.round(intelAverage) : Math.round(intelAverage * 100)
      const intelArtifacts = intelPackage.artifacts || {}
      const intelRequirements = intelPackage.requirements || []
      const intelNextActions = intelPackage.next_actions || []
      const packageFallback = intelRequirements.filter(req => req.required && req.status === 'fallback_used').map(req => req.key)
      const guardFallback = guardLowConfidence.map(item => item.key).filter(Boolean)
      const intelFallback = packageFallback.length ? packageFallback : guardFallback
      const hasReportEvidence = Boolean(
        intelligenceAdjustment.package_completeness !== undefined ||
        intelligenceAdjustment.strict_completeness !== undefined ||
        guardEvidence.package_completeness !== undefined ||
        guardEvidence.strict_completeness !== undefined
      )
      const artifactPriority = ['tournament_context', 'odds_1x2', 'market_movement', 'travel_fatigue', 'major_tournament_experience', 'injuries_suspensions', 'expected_lineup', 'weather', 'team_news', 'recent_form', 'elo_rating', 'fifa_ranking', 'data_quality', 'base_info']
      const seenArtifactKeys = new Set()
      const intelArtifactRows = [
        ...artifactPriority.filter(key => intelArtifacts[key]).map(key => [key, intelArtifacts[key]]),
        ...Object.entries(intelArtifacts).filter(([key]) => !artifactPriority.includes(key))
      ].filter(([key]) => {
        if (seenArtifactKeys.has(key)) return false
        seenArtifactKeys.add(key)
        return true
      }).slice(0, 10)
      const learning = r._learning || r.learning || {}
      const learningSummary = learning.summary || {}
      const learningFeature = learning.feature_snapshot || null
      const learningQuality = learning.context_snapshot?.data_quality || {}
      const learningReviews = learning.reviews || []
      const similarCases = learning.similar_cases || []

      // ===== Section 1: Match Header with glow =====
      const section1 = h('div', { class: 'ad-sec ad-sec-header' }, [
        h('div', { class: 'ad-h-info' }, [
          leagueName ? h('span', null, leagueName) : null,
          compLabel ? h('span', { class: 'ad-h-comp' }, compLabel) : null,
          matchTime ? h('span', null, matchTime) : null
        ].filter(Boolean)),
        h('div', { class: 'ad-header-teams' }, [
          h('div', { class: 'ad-h-team' }, [
            h('div', { class: 'ad-h-name home' }, homeTeam),
            xgA.home_xg ? h('div', { class: 'ad-h-xg' }, 'xG ' + xgA.home_xg.toFixed(1)) : null
          ]),
          h('div', { class: 'ad-h-vs' }, 'VS'),
          h('div', { class: 'ad-h-team' }, [
            h('div', { class: 'ad-h-name away' }, awayTeam),
            xgA.away_xg ? h('div', { class: 'ad-h-xg' }, 'xG ' + xgA.away_xg.toFixed(1)) : null
          ])
        ]),
        h('div', { class: 'ad-h-glow-line' })
      ])

      // ===== Section 2: AI Recommend + Confidence + Odds Consistency (3-col) =====
      const svgCircle = (pct, color) => {
        const r2 = 28, c = 2 * Math.PI * r2, offset = c * (1 - pct / 100)
        return h('svg', { class: 'ad-conf-svg' }, [
          h('circle', { cx: 32, cy: 32, r: r2, stroke: '#1f2937', 'stroke-width': 6, fill: 'transparent' }),
          h('circle', { cx: 32, cy: 32, r: r2, stroke: color, 'stroke-width': 6, fill: 'transparent',
            'stroke-dasharray': c, 'stroke-dashoffset': offset, 'stroke-linecap': 'round' })
        ])
      }

      const section2 = h('div', { class: 'ad-sec ad-sec-recommend' }, [
        h('div', { class: 'ad-sec-label' }, [
          h('span', { class: 'ad-sec-icon green' }, '●'),
          h('span', null, ' AI推荐')
        ]),
        h('div', { class: 'ad-rec-grid' }, [
          // Left: main recommendation
          h('div', { class: 'ad-rec-main' }, [
            h('div', { class: 'ad-rec-box' }, [
              h('span', { class: 'ad-rec-text', style: 'color:' + confColor }, rec),
              h('span', { class: 'ad-rec-badge', style: 'background:' + confColor + '20;color:' + confColor + ';border:1px solid ' + confColor + '40' }, confCN)
            ]),
            h('div', { class: 'ad-rec-stars' }, Array.from({ length: 5 }, (_, i) =>
              h('span', { class: 'ad-star ' + (i < stars ? 'on' : 'off') }, '★')
            ))
          ]),
          // Middle: confidence circle
          h('div', { class: 'ad-rec-conf' }, [
            h('span', { class: 'ad-conf-label' }, '信心指数'),
            h('div', { class: 'ad-conf-circle' }, [
              svgCircle(confPct, confColor),
              h('div', { class: 'ad-conf-num' }, confPct + '%')
            ])
          ]),
          // Right: odds consistency
          h('div', { class: 'ad-rec-cons' }, [
            h('span', { class: 'ad-conf-label' }, '赔率一致性'),
            h('div', { class: 'ad-cons-pct', style: 'color:' + (oddsConsPct > 70 ? '#10b981' : oddsConsPct > 50 ? '#f59e0b' : '#ef4444') }, oddsConsPct + '%'),
            h('div', { class: 'ad-cons-text', style: 'color:' + (oddsConsPct > 70 ? '#10b981' : oddsConsPct > 50 ? '#f59e0b' : '#ef4444') }, oddsConsText)
          ])
        ])
      ])

      const completenessRow = props.match?._dataCompleteness || {}
      const dataItems = [
        { label: '\u8d54\u7387', ok: completenessRow.has_odds ?? Boolean(props.match?.spf_odds || props.match?.rqspf_odds), detail: props.match?.spf_odds ? '\u80dc\u5e73\u8d1f' : '\u5f85\u91c7\u96c6' },
        { label: '\u771f\u5b9eO/U\u76d8', ok: completenessRow.has_ou_line ?? false, detail: completenessRow.has_ou_line ? '\u5df2\u540c\u6b65' : '\u5f85\u8865\u9f50' },
        { label: '\u8d5b\u679c', ok: completenessRow.has_score ?? (props.match?.home_goals_ft != null && props.match?.away_goals_ft != null), detail: props.match?.home_goals_ft != null ? props.match.home_goals_ft + '-' + props.match.away_goals_ft : '\u5f85\u8d5b\u679c' },
        { label: '\u534a\u573a', ok: completenessRow.has_half_score ?? (props.match?.home_goals_ht != null && props.match?.away_goals_ht != null), detail: props.match?.home_goals_ht != null ? props.match.home_goals_ht + '-' + props.match.away_goals_ht : '\u5f85\u534a\u573a' },
        { label: '\u5206\u6790', ok: completenessRow.has_analysis ?? Boolean(props.match?.has_analysis), detail: props.match?.has_analysis ? '\u5df2\u751f\u6210' : '\u5f85\u5206\u6790' },
        { label: '\u60c5\u62a5', ok: completenessRow.has_intelligence ?? Boolean(props.match?._intelligenceJob || intelEnvelope), detail: intelEnvelope || props.match?._intelligenceJob ? '\u5df2\u5efa\u5305' : '\u5f85\u8865\u9f50' }
      ]
      const dataMissing = dataItems.filter(item => !item.ok).length
      const sourceTags = [
        props.match?.is_schedule_fallback ? '\u8d5b\u7a0b\u5360\u4f4d' : null,
        props.match?.score_source === 'oddsfe_event_api' ? 'oddsfe\u8d5b\u679c' : null,
        props.match?.score_source === 'oddsfe_event_cache' ? 'oddsfe\u7f13\u5b58' : null,
        props.match?.score_source === 'oddsfe_schedule_cache' ? '\u8d5b\u7a0b\u6bd4\u5206' : null,
      ].filter(Boolean)
      const sectionDataStatus = h('div', { class: 'ad-sec ad-data-status ' + (dataMissing ? 'warn' : 'ready') }, [
        h('div', { class: 'ad-sec-label' }, [
          h('span', { class: 'ad-sec-icon blue' }, '\u25cf'),
          h('span', null, ' \u6570\u636e\u72b6\u6001'),
          h('small', { class: 'ad-data-summary' }, dataMissing ? '\u7f3a' + dataMissing + '\u9879' : '\u5df2\u9f50\u5907')
        ]),
        h('div', { class: 'ad-data-grid' }, dataItems.map(item =>
          h('div', { class: 'ad-data-item ' + (item.ok ? 'ok' : 'missing') }, [
            h('span', null, item.label),
            h('b', null, item.ok ? '\u5df2\u6709' : '\u7f3a\u5931'),
            h('small', null, item.detail)
          ])
        )),
        sourceTags.length ? h('div', { class: 'ad-data-sources' }, sourceTags.map(tag => h('em', null, tag))) : null
      ])

      const evidenceTone = intelMissing.length > 0 ? 'risk' : (intelStrict >= 80 ? 'ready' : 'partial')
      const sectionEvidence = h('div', { class: 'ad-sec ad-evidence ' + evidenceTone }, [
        h('div', { class: 'ad-sec-label' }, [
          h('span', { class: 'ad-sec-icon green' }, '●'),
          h('span', null, ' 情报证据')
        ]),
        intelligencePackageLoading.value ? h('div', { class: 'ad-ev-empty' }, '情报包加载中...') : null,
        (!intelligencePackageLoading.value && !props.match?._intelligenceJob && !intelEnvelope && !hasReportEvidence) ? h('div', { class: 'ad-ev-empty' }, '未建情报包：点击上方“情报补齐”或等待后台定时采集。') : null,
        (props.match?._intelligenceJob || intelEnvelope || hasReportEvidence) ? h('div', { class: 'ad-ev-grid' }, [
          h('div', { class: 'ad-ev-metric' }, [h('span', '证据覆盖'), h('b', intelCompleteness + '%')]),
          h('div', { class: 'ad-ev-metric' }, [h('span', '严格覆盖'), h('b', intelStrict + '%')]),
          h('div', { class: 'ad-ev-metric' }, [h('span', '平均置信'), h('b', (intelAveragePct || 0) + '%')])
        ]) : null,
        intelMissing.length > 0 ? h('div', { class: 'ad-ev-line warn' }, [
          h('span', { class: 'ad-ev-label' }, '缺失关键项'),
          h('span', null, intelMissing.map(requirementLabel).slice(0, 6).join(' / '))
        ]) : null,
        intelFallback.length > 0 ? h('div', { class: 'ad-ev-line fallback' }, [
          h('span', { class: 'ad-ev-label' }, '兜底证据'),
          h('span', null, intelFallback.map(requirementLabel).slice(0, 6).join(' / '))
        ]) : null,
        intelArtifactRows.length > 0 ? h('div', { class: 'ad-ev-artifacts' }, intelArtifactRows.map(([key, artifact]) =>
          h('div', { class: 'ad-ev-artifact' }, [
            h('span', { class: 'ad-ev-artifact-key' }, requirementLabel(key)),
            h('span', { class: 'ad-ev-artifact-src' }, artifact.source || 'unknown'),
            h('span', { class: 'ad-ev-artifact-conf' }, Math.round(Number(artifact.confidence || 0) * 100) + '%'),
            (artifact.payload?.lineup_confidence_tier) ? h('span', { class: 'ad-ev-artifact-tier' }, artifact.payload.lineup_confidence_label || artifact.payload.lineup_confidence_tier) : null
          ])
        )) : null,
        intelNextActions.length > 0 ? h('div', { class: 'ad-ev-actions' }, [
          h('span', { class: 'ad-ev-label' }, '下一步'),
          h('div', { class: 'ad-ev-action-list' }, intelNextActions.slice(0, 4).map(item => {
            const reqKey = item.key
            const channels = (props.sourceHealth?.requirements || {})[reqKey] || []
            const channelLabel = { news_aggregator: 'zhibo8', apifootball_match_detail: 'apifootball', api_sports_injuries: 'api-sports', bifen188_lineups: 'bifen188', weather_fetcher: 'wttr.in', fifa_ranking_fetcher: 'FIFA排名' }
            const nextChannel = channels.length > 0 ? channels.sort((a, b) => (a.priority || 99) - (b.priority || 99))[0] : null
            const actionText = nextChannel ? `${channelLabel[nextChannel.channel] || nextChannel.channel}(P${nextChannel.priority})` : '无可用源'
            const healthTag = nextChannel?.health_status === 'healthy' ? '✓' : nextChannel?.health_status === 'degraded' ? '△' : nextChannel?.health_status === 'error' ? '✗' : '?'
            return h('div', { class: 'ad-ev-action-item' }, [
              h('span', { class: 'ad-ev-action-key' }, requirementLabel(reqKey)),
              h('span', { class: 'ad-ev-action-src' }, actionText),
              h('span', { class: ['ad-ev-action-health', nextChannel?.health_status || 'unknown'].join(' ') }, healthTag)
            ])
          }))
        ]) : null
      ])

      const intelInsightCards = [
        summarizeMarketArtifact(intelArtifacts.market_movement),
        summarizeTravelArtifact(intelArtifacts.travel_fatigue, homeTeam, awayTeam),
        summarizeExperienceArtifact(intelArtifacts.major_tournament_experience, homeTeam, awayTeam)
      ].filter(Boolean)
      const adjustmentDelta = intelligenceAdjustment.probability_delta || {}
      const appliedAdjustmentFactors = (intelligenceAdjustment.factors || []).filter(item => item.applied)
      const deltaPct = (value) => {
        const n = Number(value || 0)
        if (!Number.isFinite(n) || Math.abs(n) < 0.0005) return '0%'
        return (n > 0 ? '+' : '') + (n * 100).toFixed(1).replace(/\.0$/, '') + '%'
      }
      const deltaClass = (value) => Number(value || 0) > 0 ? 'pos' : Number(value || 0) < 0 ? 'neg' : 'flat'
      const adjustmentTitle = appliedAdjustmentFactors
        .map(item => (item.title || requirementLabel(item.key)) + '：' + Object.entries(item.delta || {}).map(([k, v]) => k + ' ' + deltaPct(v)).join(' / '))
        .join('\n')
      const adjustmentCard = intelligenceAdjustment.applied ? h('div', {
        class: 'ad-intel-adjust-card',
        title: adjustmentTitle || '真实情报已进入本场概率修正'
      }, [
        h('div', { class: 'ad-intel-adjust-head' }, [
          h('span', null, '已进入模型'),
          h('b', null, appliedAdjustmentFactors.length + '项')
        ]),
        h('div', { class: 'ad-intel-deltas' }, [
          h('div', { class: 'ad-intel-delta ' + deltaClass(adjustmentDelta.home_win) }, [
            h('span', null, '主胜'),
            h('b', null, deltaPct(adjustmentDelta.home_win))
          ]),
          h('div', { class: 'ad-intel-delta ' + deltaClass(adjustmentDelta.draw) }, [
            h('span', null, '平局'),
            h('b', null, deltaPct(adjustmentDelta.draw))
          ]),
          h('div', { class: 'ad-intel-delta ' + deltaClass(adjustmentDelta.away_win) }, [
            h('span', null, '客胜'),
            h('b', null, deltaPct(adjustmentDelta.away_win))
          ])
        ]),
        h('p', null, appliedAdjustmentFactors.map(item => item.title || requirementLabel(item.key)).join(' / ') || '情报修正已应用')
      ]) : null
      const sectionIntelFactors = (intelInsightCards.length > 0 || adjustmentCard) ? h('div', { class: 'ad-sec ad-intel-factors' }, [
        h('div', { class: 'ad-sec-label' }, [
          h('span', { class: 'ad-sec-icon green' }, '●'),
          h('span', null, ' 情报分析面')
        ]),
        h('div', { class: 'ad-intel-grid' }, [
          adjustmentCard,
          ...intelInsightCards.map(item =>
          h('div', { class: 'ad-intel-card', title: item.detail || item.summary, style: 'border-left-color:' + item.color }, [
            h('div', { class: 'ad-intel-head' }, [
              h('span', { class: 'ad-intel-title' }, item.title),
              h('span', { class: 'ad-intel-conf' }, Math.round(Number(item.confidence || 0) * 100) + '%')
            ]),
            h('b', { style: 'color:' + item.color }, item.value),
            h('p', null, item.summary)
          ])
        )].filter(Boolean))
      ]) : null

      const wc = r.world_cup_context || r.competition_context?.world_cup_2026 || {}
      const wcGroup = wc.group || {}
      const wcStage = wc.group_stage_context || {}
      const wcTeams = wc.teams || {}
      const wcHome = wcTeams.home || {}
      const wcAway = wcTeams.away || {}
      const wcPressure = wc.pressure || {}
      const wcHomePressure = wcPressure.home || {}
      const wcAwayPressure = wcPressure.away || {}
      const wcSlots = wc.knockout_path_context?.potential_round_of_32_slots || []
      const wcNotes = wcPressure.notes || []
      const hasWcContext = Boolean(wc.match || wcGroup.group || wcStage.group)
      const wcHomePlayed = Number(wcHome.played ?? 0)
      const wcAwayPlayed = Number(wcAway.played ?? 0)
      const wcDataStatus = wc.data_status || {}
      const wcSourceLabel = wcDataStatus.mode === 'live_api' ? '实时积分' : wc.context_freshness === 'cached_live_snapshot' ? '缓存实时积分' : '本地赛程'
      const wcTeamPlayedLabel = wcHomePlayed === wcAwayPlayed
        ? wcHomePlayed + '/3场'
        : '主' + wcHomePlayed + '/3 · 客' + wcAwayPlayed + '/3'
      const wcGroupPlayedLabel = (wcStage.group_matches_finished ?? wcGroup.matches_finished ?? 0) + '/' + (wcStage.group_matches_total ?? wcGroup.matches_total ?? 6) + '场'
      const pressureLabel = (level) => ({
        very_high: '极高',
        high: '高',
        medium: '中',
        low: '低',
        unknown: '未知'
      }[level] || level || '未知')
      const qualificationLabel = (value) => ({
        direct_round_of_32: '直接晋级区',
        third_place_pool: '第三名池',
        outside_current_cut: '暂在淘汰区',
        best_third_advancing: '最佳第三晋级区',
        third_place_outside_cut: '第三名淘汰区',
        third_place_unresolved: '第三名未定',
        not_started: '未开赛',
        unknown: '未知'
      }[value] || value || '未知')
      const teamStanding = (row, fallbackName, pressure) => h('div', { class: 'ad-wc-team' }, [
        h('div', { class: 'ad-wc-team-line' }, [
          h('div', { class: 'ad-wc-team-name' }, row.team_name_cn || row.team_name || fallbackName),
          h('strong', { class: 'ad-wc-points' }, (row.points ?? 0) + '分')
        ]),
        h('div', { class: 'ad-wc-team-meta' }, [
          h('span', null, (row.position ? (wcGroup.group || wcStage.group || '-') + row.position : '排名未定')),
          h('span', null, (row.played ?? 0) + '/3场'),
          h('span', null, '净' + ((Number(row.goal_diff || 0) > 0 ? '+' : '') + (row.goal_diff ?? 0))),
          h('span', { class: 'ad-wc-qual' }, qualificationLabel(row.qualification))
        ]),
        h('div', { class: 'ad-wc-pressure ' + (pressure.level || 'unknown') }, [
          h('span', null, pressureReasonLabel(pressure.reason)),
          h('b', null, pressureLabel(pressure.level))
        ])
      ])
      const slotLabel = (slot) => {
        const pos = slot.finish_position === 1 ? '小组第一' : slot.finish_position === 2 ? '小组第二' : '小组第三'
        const opponent = slot.opponent_resolution?.team?.team_name_cn || slot.opponent_resolution?.team?.name_cn || slot.opponent_slot_label || '对手待定'
        return pos + ' -> M' + slot.match_number + ' vs ' + opponent
      }
      const pathSlots = [1, 2, 3]
        .map(pos => wcSlots.find(slot => slot.finish_position === pos))
        .filter(Boolean)
      const sectionWorldCup = hasWcContext ? h('div', { class: 'ad-sec ad-wc-context' }, [
        h('div', { class: 'ad-sec-label ad-wc-label' }, [
          h('span', null, [
            h('span', { class: 'ad-sec-icon orange' }, '●'),
            h('span', null, ' 世界杯小组形势')
          ]),
          h('small', { class: 'ad-wc-source' }, wcSourceLabel)
        ]),
        h('div', { class: 'ad-wc-top' }, [
          h('div', { class: 'ad-wc-pill' }, [
            h('span', null, '小组'),
            h('b', null, (wcGroup.group || wcStage.group || '-') + '组')
          ]),
          h('div', { class: 'ad-wc-pill' }, [
            h('span', null, '轮次'),
            h('b', null, '第' + (wcStage.matchday || '?') + '/3轮')
          ]),
          h('div', { class: 'ad-wc-pill', title: '每队小组赛共3场；本组4队合计6场，目前本组已赛' + wcGroupPlayedLabel }, [
            h('span', null, '进度'),
            h('b', null, wcGroupPlayedLabel)
          ])
        ]),
        h('div', { class: 'ad-wc-teams' }, [
          teamStanding(wcHome, homeTeam, wcHomePressure),
          teamStanding(wcAway, awayTeam, wcAwayPressure)
        ]),
        wcNotes.length > 0 ? h('div', { class: 'ad-wc-notes' }, wcNotes.slice(0, 3).map(note =>
          h('div', { class: 'ad-wc-note' }, note)
        )) : null,
        pathSlots.length ? h('div', { class: 'ad-wc-sub ad-wc-path' }, [
          h('div', { class: 'ad-wc-sub-title' }, '本组潜在 32 强落位'),
          h('div', { class: 'ad-wc-path-grid' }, pathSlots.map(slot =>
            h('div', { class: 'ad-wc-slot' }, [
              h('span', null, slotLabel(slot)),
              h('small', null, [slot.city, slot.date].filter(Boolean).join(' · '))
            ])
          ))
        ]) : null,
        wcStage.remaining_fixtures?.length ? h('div', { class: 'ad-wc-sub' }, [
          h('div', { class: 'ad-wc-sub-title' }, '同组关键余赛'),
          h('div', { class: 'ad-wc-fixtures' }, wcStage.remaining_fixtures.slice(0, 2).map(f =>
            h('div', { class: 'ad-wc-fixture' }, [
              h('span', null, '第' + (f.matchday || '?') + '轮'),
              h('b', null, (f.home_team_cn || f.home_team || '-') + ' vs ' + (f.away_team_cn || f.away_team || '-')),
              h('span', null, (f.date || '').slice(5) + (f.time ? ' ' + f.time : ''))
            ])
          ))
        ]) : null
      ]) : null

      // ===== Section 3: Probability Analysis (stacked single bar) =====
      // Support both play_predictions and analyses.ou formats
      const ouProbs = ouData.over_under_probs || {}
      const homePct = Math.round(homeP * 100)
      const drawPct = Math.round(drawP * 100)
      const awayPct = Math.round(awayP * 100)

      // O/U 2.5 probability from analyses.ou or play_predictions
      const ou25 = ouProbs['over_2.5'] || ouData.over_2_5 || 0

      const section3 = h('div', { class: 'ad-sec' }, [
        h('div', { class: 'ad-sec-label' }, [
          h('span', { class: 'ad-sec-icon blue' }, '●'),
          h('span', null, ' 概率分析')
        ]),
        // Labels row
        h('div', { class: 'ad-prob-labels' }, [
          h('span', { class: 'ad-prob-lbl home' }, '主胜'),
          h('span', { class: 'ad-prob-lbl draw' }, '平局'),
          h('span', { class: 'ad-prob-lbl away' }, '客胜')
        ]),
        // Single stacked bar
        h('div', { class: 'ad-prob-bar' }, [
          h('div', { class: 'ad-prob-seg home', style: 'width:' + homePct + '%' }),
          h('div', { class: 'ad-prob-seg draw', style: 'width:' + drawPct + '%' }),
          h('div', { class: 'ad-prob-seg away', style: 'width:' + awayPct + '%' })
        ]),
        // Values row
        h('div', { class: 'ad-prob-values' }, [
          h('span', { class: 'ad-prob-val home' }, homePct + '%'),
          h('span', { class: 'ad-prob-val draw' }, drawPct + '%'),
          h('span', { class: 'ad-prob-val away' }, awayPct + '%')
        ]),
        // Odds implied comparison — use match-level spf_odds when report lacks odds_baseline
        (effectiveOddsH || effectiveOddsD || effectiveOddsA) ? h('div', { class: 'ad-prob-implied' }, [
          h('div', { class: 'ad-prob-compare' }, [
            h('span', null, '赔率隐含：'),
            h('span', { class: 'ad-pci home' }, '主' + Math.round(effectiveOddsH * 100) + '%'),
            h('span', { class: 'ad-pci draw' }, '平' + Math.round(effectiveOddsD * 100) + '%'),
            h('span', { class: 'ad-pci away' }, '客' + Math.round(effectiveOddsA * 100) + '%')
          ]),
          h('div', { class: 'ad-prob-diff' }, (() => {
            const diffs = []
            const homeDiff = Math.round(homeP * 100 - effectiveOddsH * 100)
            const drawDiff = Math.round(drawP * 100 - effectiveOddsD * 100)
            const awayDiff = Math.round(awayP * 100 - effectiveOddsA * 100)
            if (Math.abs(homeDiff) >= 3) diffs.push((homeDiff > 0 ? '主+' : '主') + homeDiff + '%')
            if (Math.abs(drawDiff) >= 3) diffs.push((drawDiff > 0 ? '平+' : '平') + drawDiff + '%')
            if (Math.abs(awayDiff) >= 3) diffs.push((awayDiff > 0 ? '客+' : '客') + awayDiff + '%')
            return diffs.length ? '模型偏差: ' + diffs.join(' / ') : ''
          })())
        ]) : null
      ])

      // ===== Section 4: Expected Goals + Score Predictions (2-col) =====
      const top3 = pp.top3_scores || fp.most_likely_scores || analyses.bf?.top_scores || []
      const spfPred = fp.predicted_result || analyses.spf?.recommendation || ''
      const directionText = RL[spfPred] || rec || '胜平负方向'
      const ouDerived = deriveOU(pp.ou || pp.over_under, analyses.ou, xgA, fp)
      const ouAxisText = ouDerived?.recommendation || (ouDerived?.line || ouDerived?.best_line ? (ouDerived.line || ouDerived.best_line) + '球' : '进球区间')
      const rqspfData = pp.rqspf || analyses.rqspf || {}
      const bqcData = deriveBQC(fp, pp.bqc, analyses.bqc)
      const scoreDeriveText = top3.length > 0
        ? (top3[0]?.derivation?.summary || playDerivationSummary('bf', top3[0] || {}, { direction: directionText, ouText: ouAxisText }))
        : ''
      const ouDiag = ouDerived?.diagnostics || {}
      const scoreAxisNote = ouDerived?.score_axis_note || ouDerived?.score_distribution_note || ''
      const scoreDeriveDisplay = [scoreDeriveText, scoreAxisNote].filter(Boolean).join('；')
      const scoreNearLineText = (ouDiag.score_cluster_near_line || []).length
        ? '盘口附近比分：' + ouDiag.score_cluster_near_line.slice(0, 3).join(' / ')
        : ''
      const percentLabel = (value) => {
        const n = Number(value)
        if (!Number.isFinite(n)) return '--'
        return Math.round((n > 1 ? n : n * 100)) + '%'
      }
      const ouSideLabel = (side) => side === 'over' ? '大球' : side === 'under' ? '小球' : '未定'
      const buildOuDiagnosticChips = (diag = {}) => {
        if (!diag || Object.keys(diag).length === 0) return []
        const chips = []
        const goalAxis = diag.goal_axis || {}
        if (goalAxis.side_cn || goalAxis.side) chips.push({ label: '进球轴', value: goalAxis.side_cn || ouSideLabel(goalAxis.side) })
        if (goalAxis.confidence_level) chips.push({ label: '可信度', value: ({ high: '高', medium: '中', low: '低' }[goalAxis.confidence_level] || goalAxis.confidence_level), warn: goalAxis.confidence_level === 'low' })
        if (diag.line != null) chips.push({ label: '盘口', value: fmtNumber(diag.line, 2) })
        if (diag.expected_total != null) chips.push({ label: '预期', value: fmtNumber(diag.expected_total, 2) })
        if (diag.over_line_probability != null) chips.push({ label: '大于盘口', value: percentLabel(diag.over_line_probability) })
        if (diag.model_side) chips.push({ label: '模型', value: ouSideLabel(diag.model_side) })
        if (diag.market_side && diag.market_side !== diag.model_side) chips.push({ label: '市场', value: ouSideLabel(diag.market_side), warn: true })
        if (goalAxis.attack_defense_profile?.home_score_signal != null && goalAxis.attack_defense_profile?.away_score_signal != null) {
          chips.push({ label: '攻防', value: percentLabel(goalAxis.attack_defense_profile.home_score_signal) + '/' + percentLabel(goalAxis.attack_defense_profile.away_score_signal) })
        }
        if (goalAxis.historical_line_signal?.sample_size) {
          const hist = goalAxis.historical_line_signal
          const sideText = hist.support_side ? ouSideLabel(hist.support_side) : '样本'
          chips.push({ label: '历史盘', value: sideText + ' ' + hist.sample_size + '场', warn: Number(hist.edge_rate || 0) >= 0.4 })
        }
        if (goalAxis.historical_similarity_signal?.sample_size) {
          const sim = goalAxis.historical_similarity_signal
          const rate = sim.same_prediction_hit_rate ?? sim.hit_rate
          const rateText = rate != null ? ' · ' + percentLabel(rate) : ''
          const sideText = sim.support_side ? ouSideLabel(sim.support_side) : '样本'
          chips.push({
            label: '相似盘',
            value: sideText + ' ' + sim.sample_size + '场' + rateText,
            warn: goalAxis.side && sim.support_side && goalAxis.side !== sim.support_side
          })
        }
        ;(diag.volatility_reasons || []).slice(0, 2).forEach(text => chips.push({ label: '谨慎', value: text, warn: true }))
        ;((goalAxis.sensitivity || {}).reasons || []).slice(0, 1).forEach(text => chips.push({ label: '风险', value: text, warn: true }))
        ;(diag.score_cluster_near_line || []).slice(0, 2).forEach(text => chips.push({ label: '落点', value: text }))
        return chips
      }

      const section4 = h('div', { class: 'ad-row-2col' }, [
        // Left: expected goals
        expScore.home != null ? h('div', { class: 'ad-sec' }, [
          h('div', { class: 'ad-sec-label' }, [
            h('span', { class: 'ad-sec-icon blue' }, '●'),
            h('span', null, ' 预测进球')
          ]),
          h('div', { class: 'ad-xg-row' }, [
            h('div', { class: 'ad-xg-col' }, [
              h('span', { class: 'ad-xg-team' }, homeTeam),
              h('span', { class: 'ad-xg-val home' }, expScore.home.toFixed(1)),
              h('div', { class: 'ad-xg-dots' }, Array.from({ length: 5 }, (_, i) =>
                h('span', { class: 'ad-xg-dot ' + (i < Math.floor(expScore.home) ? 'home on' : i < Math.ceil(expScore.home) && (expScore.home - Math.floor(expScore.home)) >= 0.4 ? 'home half' : 'off') }, '●')
              ))
            ]),
            h('div', { class: 'ad-xg-vs' }, 'VS'),
            h('div', { class: 'ad-xg-col' }, [
              h('span', { class: 'ad-xg-team' }, awayTeam),
              h('span', { class: 'ad-xg-val away' }, expScore.away.toFixed(1)),
              h('div', { class: 'ad-xg-dots' }, Array.from({ length: 5 }, (_, i) =>
                h('span', { class: 'ad-xg-dot ' + (i < Math.floor(expScore.away) ? 'away on' : i < Math.ceil(expScore.away) && (expScore.away - Math.floor(expScore.away)) >= 0.4 ? 'away half' : 'off') }, '●')
              ))
            ])
          ])
        ]) : null,
        // Right: top scores
        top3.length > 0 ? h('div', { class: 'ad-sec' }, [
          h('div', { class: 'ad-sec-label' }, [
            h('span', { class: 'ad-sec-icon purple' }, '●'),
            h('span', null, ' 推荐比分')
          ]),
          h('div', { class: 'ad-sc-row' }, top3.slice(0, 3).map((s, i) => {
            const sc = s.score || (s.home_goals + '-' + s.away_goals)
            const pct = Math.round((s.probability || s.prob || 0) * (s.probability > 1 ? 1 : 100))
            return h('div', { class: 'ad-sc-card ' + (i === 0 ? 'top' : '') }, [
              h('div', { class: 'ad-sc-rank' }, String(i + 1)),
              h('div', { class: 'ad-sc-label' }, '比分'),
              h('div', { class: 'ad-sc-score' }, sc),
              h('div', { class: 'ad-sc-pct' }, pct + '%')
            ])
          })),
          scoreDeriveDisplay ? h('div', { class: 'ad-sc-derive', title: [scoreDeriveDisplay, scoreNearLineText].filter(Boolean).join('；') }, scoreDeriveDisplay) : null
        ]) : null
      ])

      const derivationRows = [
        pp.spf ? { name: '胜平负', data: pp.spf, fallback: { direction: directionText } } : null,
        ouDerived ? { name: '大小球', data: ouDerived, fallback: { ouText: ouAxisText } } : null,
        rqspfData ? { name: '让球胜平负', data: rqspfData, fallback: { direction: directionText } } : null,
        bqcData ? { name: '半全场', data: bqcData, fallback: { direction: directionText, ouText: ouAxisText } } : null,
        top3.length > 0 ? { name: '比分', data: top3[0], fallback: { direction: directionText, ouText: ouAxisText } } : null
      ].filter(Boolean).map(row => ({
        ...row,
        label: playReferenceLabel(row.data?.risk_profile, row.name === '胜平负' ? '主判断轴' : row.name === '大小球' ? '进球区间轴' : '条件推导'),
        summary: playDerivationSummary(row.name === '比分' ? 'bf' : row.name === '让球胜平负' ? 'rqspf' : row.name === '半全场' ? 'bqc' : row.name === '大小球' ? 'ou' : 'spf', row.data || {}, row.fallback || {}),
        formula: row.data?.derivation?.formula || '',
        gateText: row.name === '让球胜平负' ? rqspfGateText(row.data || {}) : '',
        diagnostics: row.name === '大小球'
          ? { ...(row.data?.diagnostics || row.data?.derivation?.conditions || {}), goal_axis: row.data?.goal_axis || null }
          : {}
      }))

      const sectionDerivation = derivationRows.length > 0 ? h('div', { class: 'ad-sec ad-derive-sec' }, [
        h('div', { class: 'ad-sec-label' }, [
          h('span', { class: 'ad-sec-icon green' }, '●'),
          h('span', null, ' 玩法联动推导')
        ]),
        h('div', { class: 'ad-derive-axis' }, [
          h('span', null, '主轴'),
          h('b', null, directionText),
          h('span', null, '进球区间'),
          h('b', null, ouAxisText)
        ]),
        h('div', { class: 'ad-derive-list' }, derivationRows.map(row =>
          h('div', { class: 'ad-derive-row', title: [row.summary, row.formula].filter(Boolean).join(' | ') }, [
            h('span', { class: 'ad-derive-name' }, row.name),
            h('span', { class: 'ad-derive-label' }, row.label),
            h('p', null, row.summary),
            row.gateText ? h('div', { class: 'ad-derive-gate', title: row.gateText }, row.gateText) : null,
            row.name === '大小球' && buildOuDiagnosticChips(row.diagnostics).length
              ? h('div', { class: 'ad-ou-diag ' + (row.diagnostics.conflict_level || '') }, buildOuDiagnosticChips(row.diagnostics).map(chip =>
                h('span', { class: chip.warn ? 'warn' : '' }, [
                  h('small', null, chip.label),
                  h('b', null, chip.value)
                ])
              ))
              : null
          ])
        ))
      ]) : null

      // ===== Section 5: Play Recommendations (horizontal scroll cards) =====
      const playItems = []
      // SPF
      // SPF — diamond with W/D/L indicator
      // Derive from final_prediction, analyses.spf, or recommendation text
      const spfIcon = spfPred === 'home_win' || spfPred === '3' || spfPred === '主胜' ? '胜' : spfPred === 'away_win' || spfPred === '0' || spfPred === '客胜' ? '负' : '平'
      playItems.push({ name: '胜平负', icon: '◆', subIcon: spfIcon, colorClass: 'orange', rec: rec, prob: Math.max(homeP, drawP, awayP), probLabel: RL[spfPred] || analyses.spf?.recommendation || '', stars: stars, referenceLabel: playReferenceLabel(pp.spf?.risk_profile, '主判断轴'), deriveText: playDerivationSummary('spf', pp.spf, { direction: directionText }) })

      // RQSPF: support both play_predictions and analyses format
      const handicapLine = rqspfData.handicap || rqspfData.handicap_line || props.match?.handicap_line || 0
      if (rqspfData.direction || rqspfData.recommendation || handicapLine) {
        const rqDir = rqspfData.direction || ''
        const rqLabel = { '3': '让胜', '1': '让平', '0': '让负', 'home_win': '让胜', 'draw': '让平', 'away_win': '让负' }[rqDir] || rqDir
        const hc = Math.abs(handicapLine)
        // Use goal_line from rqspf_odds for correct direction display
        const goalLine = props.match?.rqspf_odds?.goal_line
        const handicapLabel = goalLine ? String(goalLine).trim() : (handicapLine > 0 ? '-' + hc : handicapLine < 0 ? '+' + hc : '0')
        // If no direction from analysis, derive from SPF prediction
        const derivedLabel = rqDir ? rqLabel : (fp.predicted_result === 'home_win' || fp.predicted_result === '3' ? '让胜' : fp.predicted_result === 'away_win' || fp.predicted_result === '0' ? '让负' : '让平')
        const rqMaxP = rqspfData.probabilities || rqspfData.adjusted_probs || {}
        const rqMaxPVal = Math.max(...Object.values(rqMaxP).map(v => typeof v === 'number' ? v : 0))
        const hcDir = derivedLabel.includes('让胜') ? '←' : derivedLabel.includes('让负') ? '→' : '↔'
        playItems.push({ name: '让球', icon: hcDir, subIcon: handicapLabel, colorClass: 'green', rec: derivedLabel, prob: rqMaxPVal || Math.max(homeP, awayP), probLabel: derivedLabel, stars: rqMaxPVal >= 0.62 ? 4 : 3, referenceLabel: playReferenceLabel(rqspfData.risk_profile, '条件推导'), deriveText: playDerivationSummary('rqspf', rqspfData, { direction: directionText }) })
      }

      // BQC: use derived data when play_predictions has none
      if (bqcData) {
        const bqcRec = bqcData.recommendation_cn || BQC[bqcData.direction] || bqcData.recommendation || '--'
        const bqcProb = bqcData.probability || bqcData.prob || (bqcData.derived ? Math.max(homeP, drawP, awayP) : 0)
        playItems.push({ name: '半全场', icon: '⇥', subIcon: '半→全', colorClass: 'blue', rec: bqcRec, prob: bqcProb, probLabel: bqcRec, stars: 2, referenceLabel: playReferenceLabel(bqcData.risk_profile, '路径推导'), deriveText: playDerivationSummary('bqc', bqcData, { direction: directionText, ouText: ouAxisText }) })
      }

      // Over/Under: use derived data when play_predictions has none
      if (ouDerived) {
        const ouRec = ouDerived.recommendation || '--'
        const bestLineProbs = ouDerived.best_line_probs || {}
        const ouBestProb = Math.max(Number(bestLineProbs.over || 0), Number(bestLineProbs.under || 0))
        let ou25 = Number(ouDerived.over_2_5 || 0)
        const ouProb = ouBestProb || ou25
        const ouPct = ouProb > 0 ? Math.round(ouProb * 100) : 0
        ou25 = ouProb
        const ouLine = ouDerived.line || ouDerived.best_line || 2.5
        const ouIcon = ouRec.includes('大') || ouRec.includes('Over') ? '⬆' : ouRec.includes('小') || ouRec.includes('Under') ? '⬇' : '⇕'
        // Don't duplicate the line number if ouRec already contains it (e.g. "小3.75")
        const hasLineInRec = /\d/.test(ouRec)
        const recDisplay = hasLineInRec ? ouRec : ouRec + ' ' + ouLine
        const ouConflict = ouDerived.diagnostics?.conflict_level
        const ouVolatile = (ouDerived.diagnostics?.volatility_reasons || []).length > 0
        const baseOuStars = ouPct >= 60 ? 4 : ouPct >= 45 ? 3 : 2
        const ouStars = ouConflict === 'high' ? Math.min(baseOuStars, 2) : (ouConflict === 'medium' || ouVolatile) ? Math.min(baseOuStars, 3) : baseOuStars
        playItems.push({ name: '大小球', icon: ouIcon, subIcon: ouLine + '球', colorClass: 'purple', rec: recDisplay, prob: ou25, probLabel: ouRec, stars: ouStars, referenceLabel: playReferenceLabel(ouDerived.risk_profile, '进球区间轴'), deriveText: playDerivationSummary('ou', ouDerived, { ouText: recDisplay }) })
      }

      const section5 = playItems.length > 0 ? h('div', { class: 'ad-sec' }, [
        h('div', { class: 'ad-sec-label' }, [
          h('span', { class: 'ad-sec-icon purple' }, '●'),
          h('span', null, ' 玩法推荐')
        ]),
        h('div', { class: 'ad-play-scroll' }, playItems.map(p =>
          h('div', { class: 'ad-play-card ' + p.colorClass }, [
            h('div', { class: 'ad-pc-head' }, [
              h('span', { class: 'ad-pc-icon' }, p.icon),
              h('span', { class: 'ad-pc-name' }, p.name),
              p.subIcon ? h('span', { class: 'ad-pc-sub' }, p.subIcon) : null
            ]),
            h('div', { class: 'ad-pc-rec' }, p.rec),
            p.prob > 0 ? h('div', { class: 'ad-pc-pct' }, Math.round(p.prob * 100) + '%') : null,
            h('div', { class: 'ad-pc-stars' }, Array.from({ length: 5 }, (_, i) =>
              h('span', { class: 'ad-pc-star ' + (i < p.stars ? 'on' : 'off') }, '★')
            ))
          ])
        ))
      ]) : null

      // ===== Section 6: Analysis Factors + AI Interpretation (2-col) =====
      const explanationLines = genExplanationLines(r, homeTeam, awayTeam)
      intelInsightCards.forEach(item => {
        if (item.explanation) explanationLines.push(item.explanation)
      })

      // Build factor list from weights, or derive from report data if weights empty
      let factorEntries = Object.entries(weights)
      if (factorEntries.length === 0) {
        // Derive factors from available report data
        const derivedFactors = {}
        if (oH > 0 || oD > 0 || oA > 0) derivedFactors['odds'] = 0.25
        if (xgA.home_xg || xgA.away_xg) derivedFactors['poisson'] = 0.20
        if (formComp.last6 || r.form_comparison) derivedFactors['form'] = 0.15
        if (h2h.total_matches) derivedFactors['h2h'] = 0.10
        if (mp.is_home_advantage !== undefined || mp.home_away) derivedFactors['home_away'] = 0.10
        const hm = motivation.home_motivation || {}, am = motivation.away_motivation || {}
        if (hm.motivation_type || am.motivation_type) derivedFactors['motivation'] = 0.10
        if (mp.competition_type === 'friendly') derivedFactors['friendly'] = 0.05
        if (mp.competition_type && ['domestic_cup', 'continental_cup', 'qualifier'].includes(mp.competition_type)) derivedFactors['cup'] = 0.05
        if (intelArtifacts.market_movement) derivedFactors['market_movement'] = 0.08
        if (intelArtifacts.travel_fatigue) derivedFactors['travel_fatigue'] = 0.07
        if (intelArtifacts.major_tournament_experience) derivedFactors['major_tournament_experience'] = 0.07
        // Normalize
        const total = Object.values(derivedFactors).reduce((a, b) => a + b, 0)
        if (total > 0) {
          for (const k of Object.keys(derivedFactors)) derivedFactors[k] = derivedFactors[k] / total
        }
        factorEntries = Object.entries(derivedFactors)
      }
      // If still empty, show a minimal set
      if (factorEntries.length === 0) {
        factorEntries = [['odds', 0.25], ['elo', 0.20], ['form', 0.15], ['home_away', 0.10], ['motivation', 0.10], ['poisson', 0.10], ['h2h', 0.05], ['other', 0.05]]
      }

      // Build factor detail cards for the left column
      const factorDetails = []
      if (formComp.last6) {
        const hf = formComp.last6?.team1_form || formComp.last6?.home || {}
        const af = formComp.last6?.team2_form || formComp.last6?.away || {}
        factorDetails.push({ label: '近期状态', value: (hf.wins || 0) + '胜' + (hf.draws || 0) + '平' + (hf.losses || 0) + '负', color: '#f59e0b' })
      }
      if (h2h.total_matches > 0) {
        const hr = h2h.overall_record || {}
        factorDetails.push({ label: '历史交锋', value: h2h.total_matches + '场: ' + (hr.home_wins || hr.team1_wins || 0) + '胜' + (hr.draws || 0) + '平' + (hr.away_wins || hr.team2_wins || 0) + '负', color: '#3b82f6' })
      }
      {
        const hm = motivation.home_motivation || {}, am = motivation.away_motivation || {}
        if (hm.motivation_type || am.motivation_type) {
          const hml = hm.motivation_level === 'high' ? '强' : hm.motivation_level === 'medium' ? '中' : '弱'
          const aml = am.motivation_level === 'high' ? '强' : am.motivation_level === 'medium' ? '中' : '弱'
          factorDetails.push({ label: '比赛动机', value: homeTeam + hml + ' / ' + awayTeam + aml, color: '#ef4444' })
        }
      }
      if (mp.is_home_advantage !== false) {
        factorDetails.push({ label: '主客场', value: homeTeam + '主场', color: '#3b82f6' })
      }
      intelInsightCards.forEach(item => {
        if (item.factorDetail) factorDetails.push(item.factorDetail)
      })

      const section6 = h('div', { class: 'ad-sec ad-sec-factors' }, [
        // Left: factor bars + detail cards
        h('div', { class: 'ad-fact-left' }, [
          h('div', { class: 'ad-sec-label' }, [
            h('span', { class: 'ad-sec-icon blue' }, '●'),
            h('span', null, ' 分析因子')
          ]),
          h('div', { class: 'ad-fact-list' }, factorEntries.map(([k, v]) =>
            h('div', { class: 'ad-fact-row' }, [
              h('span', { class: 'ad-fact-name' }, WT_CN[k] || k),
              h('div', { class: 'ad-fact-track' }, [
                h('div', { class: 'ad-fact-fill', style: 'width:' + Math.round(v * 100) + '%;background:' + (WT_COLOR[k] || '#3b82f6') })
              ]),
              h('span', { class: 'ad-fact-pct' }, Math.round(v * 100) + '%')
            ])
          )),
          // Factor detail cards
          factorDetails.length > 0 ? h('div', { class: 'ad-fact-details' }, factorDetails.map(fd =>
            h('div', { class: 'ad-fd-item', style: 'border-left-color:' + fd.color }, [
              h('span', { class: 'ad-fd-label', style: 'color:' + fd.color }, fd.label),
              h('span', { class: 'ad-fd-value' }, fd.value)
            ])
          )) : null,
          // Evidence provenance — source, confidence, fallback/stale badges
          Object.keys(provenance).length > 0 ? h('div', { class: 'ad-prov-sec' }, [
            h('div', { class: 'ad-prov-title' }, '证据溯源'),
            h('div', { class: 'ad-prov-grid' }, factorEntries.filter(([k]) => provenance[k]).map(([k]) => {
              const p = provenance[k]
              const srcLabel = { elo_history: 'Elo', matches_history: '历史', lottery_odds: '赔率', classify_rules: '分类', intelligence: '情报', sporttery: '体彩', oddsfe: 'OddsFe', apifootball: 'API-FB', api_sports: 'API-SP' }[p.source] || p.source
              const badges = []
              if (p.fallback) badges.push(h('span', { class: 'ad-prov-badge fallback' }, '兜底'))
              if (p.stale) badges.push(h('span', { class: 'ad-prov-badge stale' }, '过期'))
              const confPct = p.confidence != null ? Math.round(p.confidence * 100) + '%' : ''
              return h('div', { class: 'ad-prov-row' }, [
                h('span', { class: 'ad-prov-factor' }, WT_CN[k] || k),
                h('span', { class: 'ad-prov-src' }, srcLabel),
                confPct ? h('span', { class: 'ad-prov-conf' }, confPct) : null,
                ...badges,
                p.captured_at ? h('span', { class: 'ad-prov-time' }, p.captured_at.slice(5, 16)) : null
              ])
            }))
          ]) : null
        ]),
        // Right: AI interpretation
        h('div', { class: 'ad-fact-right' }, [
          h('div', { class: 'ad-sec-label' }, [
            h('span', { class: 'ad-sec-icon blue' }, '●'),
            h('span', null, ' AI分析解读')
          ]),
          h('ul', { class: 'ad-ai-list' }, explanationLines.map(line =>
            h('li', { class: 'ad-ai-item' }, [
              h('span', { class: 'ad-ai-check' }, '✓'),
              h('span', null, line)
            ])
          )),
          h('div', { class: 'ad-ai-conclusion' }, [
            h('span', null, '综合以上因素，AI推荐：'),
            h('span', { class: 'ad-ai-result', style: 'color:' + confColor }, rec)
          ]),
          // Collapsible adjustments
          adjustments.filter(a => a.description || a.reason).length > 0 ? h('div', { class: 'ad-adj-sec' }, [
            h('div', { class: 'ad-adj-toggle', onClick: () => { showFactors.value = !showFactors.value } }, [
              h('span', null, '修正详情'),
              h('span', { class: 'ad-toggle-arrow' }, showFactors.value ? '▲' : '▼')
            ]),
            showFactors.value ? h('div', { class: 'ad-adj-list' },
              adjustments.filter(a => a.description || a.reason).map(a =>
                h('div', { class: 'ad-adj-item' }, [
                  h('span', { class: 'ad-adj-tag' }, a.type || a.adjustment_type || ''),
                  h('span', { class: 'ad-adj-txt' }, a.description || a.reason || '')
                ])
              )
            ) : null
          ]) : null
        ])
      ])

      const sectionLearning = (learningFeature || learningReviews.length > 0 || similarCases.length > 0)
        ? h('div', { class: 'ad-sec ad-learning' }, [
          h('div', { class: 'ad-sec-label' }, [
            h('span', { class: 'ad-sec-icon green' }, '●'),
            h('span', null, ' 历史学习')
          ]),
          h('div', { class: 'ad-learn-metrics' }, [
            h('div', { class: 'ad-learn-metric' }, [
              h('span', null, '特征快照'),
              h('b', null, learningFeature?.snapshot_time ? learningFeature.snapshot_time.slice(5, 16) : '--')
            ]),
            h('div', { class: 'ad-learn-metric' }, [
              h('span', null, '赛后复盘'),
              h('b', null, (learningSummary.review_total ?? learningReviews.length ?? 0) + '条')
            ]),
            h('div', { class: 'ad-learn-metric' }, [
              h('span', null, '相似命中'),
              h('b', null, learningSummary.similar_accuracy != null ? learningSummary.similar_accuracy + '%' : '--')
            ]),
            h('div', { class: 'ad-learn-metric' }, [
              h('span', null, '数据质量'),
              h('b', null, Object.values(learningQuality).filter(Boolean).length + '/' + Object.keys(learningQuality).length)
            ])
          ]),
          similarCases.length > 0 ? h('div', { class: 'ad-learn-block' }, [
            h('div', { class: 'ad-learn-title' }, '相似历史案例'),
            h('div', { class: 'ad-sim-list' }, similarCases.slice(0, 4).map(item => {
              const teams = similarCaseTeamsText(item)
              const reasons = item.reasons || {}
              const reasonTags = similarReasonTags(reasons)
              const title = similarReasonTitle(reasons)
              return h('div', { class: 'ad-sim-row', title }, [
                h('div', { class: 'ad-sim-main' }, [
                  h('b', null, teams),
                  h('span', null, [item.match_date, item.league].filter(Boolean).join(' · ') || '历史样本'),
                  reasonTags.length > 0 ? h('div', { class: 'ad-sim-tags' }, reasonTags.map(tag =>
                    h('span', { class: 'ad-sim-tag' }, tag)
                  )) : null
                ]),
                h('div', { class: 'ad-sim-side' }, [
                  h('span', { class: 'ad-sim-score' }, Math.round(Number(item.similarity_score || 0) * 100) + '%'),
                  h('span', { class: ['ad-sim-result', item.is_correct === false ? 'bad' : item.is_correct === true ? 'ok' : ''].join(' ') },
                    resultLabel(item.predicted_result, item.play_type) + ' -> ' + resultLabel(item.actual_result, item.play_type))
                ])
              ])
            }))
          ]) : null,
          learningReviews.length > 0 ? h('div', { class: 'ad-learn-block' }, [
            h('div', { class: 'ad-learn-title' }, '本场赛后复盘'),
            h('div', { class: 'ad-review-mini-list' }, learningReviews.slice(0, 5).map(item =>
              h('div', { class: ['ad-review-mini', item.is_correct === false ? 'bad' : item.is_correct === true ? 'ok' : ''].join(' '), title: item.reason_text || '' }, [
                h('span', { class: 'ad-review-play' }, PLAY_CN[item.play_type] || item.play_type || '玩法'),
                h('span', null, resultLabel(item.predicted_result, item.play_type) + ' -> ' + resultLabel(item.actual_result, item.play_type)),
                h('b', null, item.is_correct ? '正确' : item.is_correct === false ? '错误' : '待定'),
                item.attribution ? h('small', null, attributionLabel(item.attribution)) : null,
                item.next_data_requirements && item.next_data_requirements.length > 0 ? h('div', { class: 'ad-review-next-data' }, [
                  h('span', { class: 'ad-review-next-label' }, '需补:'),
                  ...item.next_data_requirements.slice(0, 3).map(req =>
                    h('span', { class: 'ad-review-next-ch' }, req.channel || req.requirement_key || '')
                  )
                ]) : null,
                item.reason_text ? h('p', { class: 'ad-review-reason' }, item.reason_text) : null,
                item.learning_tags && item.learning_tags.length ? h('div', { class: 'ad-review-tags' }, item.learning_tags.slice(0, 4).map(tag =>
                  h('em', null, reviewTagLabel(tag))
                )) : null
              ])
            ))
          ]) : null
        ])
        : null

      // Match script section
      const ms = matchScript.value
      const matchScriptSection = ms
        ? h('div', { class: 'ad-sec ad-match-script' }, [
            h('div', { class: 'ad-sec-label' }, [
              h('span', { class: 'ad-sec-icon blue' }, '●'),
              h('span', null, ' 比赛脚本'),
              ms.is_consistent === false ? h('span', { class: 'ms-warning' }, ' ⚠矛盾') : null
            ]),
            h('div', { class: 'ms-grid' }, [
              ms.direction_axis ? h('div', { class: 'ms-axis' }, [
                h('div', { class: 'ms-axis-label' }, '方向'),
                h('div', { class: 'ms-axis-value' }, ms.direction_axis.label || ms.direction_axis.side),
                ms.direction_axis.edge != null ? h('div', { class: 'ms-axis-detail' }, `优势${(ms.direction_axis.edge * 100).toFixed(0)}pp`) : null
              ]) : null,
              ms.margin_axis ? h('div', { class: 'ms-axis' }, [
                h('div', { class: 'ms-axis-label' }, '边界'),
                h('div', { class: 'ms-axis-value' }, ms.margin_axis.label || ms.margin_axis.margin)
              ]) : null,
              ms.goal_axis ? h('div', { class: 'ms-axis' }, [
                h('div', { class: 'ms-axis-label' }, '进球'),
                h('div', { class: 'ms-axis-value' }, (ms.goal_axis.label || ms.goal_axis.zone) + (ms.goal_axis.side ? ` (${ms.goal_axis.side === 'over' ? '大' : '小'})` : '')),
                ms.goal_axis.line_gap != null ? h('div', { class: 'ms-axis-detail' }, `距盘${ms.goal_axis.line_gap > 0 ? '+' : ''}${ms.goal_axis.line_gap.toFixed(2)}`) : null
              ]) : null,
              ms.btts_axis ? h('div', { class: 'ms-axis' }, [
                h('div', { class: 'ms-axis-label' }, 'BTTS'),
                h('div', { class: 'ms-axis-value' }, ms.btts_axis.label || ms.btts_axis.btts)
              ]) : null,
              ms.first_half_axis ? h('div', { class: 'ms-axis' }, [
                h('div', { class: 'ms-axis-label' }, '半场'),
                h('div', { class: 'ms-axis-value' }, ms.first_half_axis.label || ms.first_half_axis.tempo)
              ]) : null,
              ms.uncertainty ? h('div', { class: 'ms-axis' }, [
                h('div', { class: 'ms-axis-label' }, '不确定性'),
                h('div', { class: ['ms-axis-value', `ms-unc-${ms.uncertainty.level}`].join(' ') }, ms.uncertainty.label || ms.uncertainty.level)
              ]) : null
            ].filter(Boolean)),
            ms.contradictions && ms.contradictions.length > 0 ? h('div', { class: 'ms-contradictions' }, [
              h('div', { class: 'ms-contr-title' }, '矛盾项:'),
              ...ms.contradictions.map(c => h('div', { class: 'ms-contr-item' }, [
                h('span', { class: 'ms-contr-sev' }, c.severity === 'high' ? '●' : '○'),
                h('span', null, c.description || c.type)
              ]))
            ]) : null,
            ms.key_drivers && ms.key_drivers.length > 0 ? h('div', { class: 'ms-drivers' }, [
              h('span', { class: 'ms-drivers-label' }, '驱动: '),
              ...ms.key_drivers.map(d => h('span', { class: 'ms-driver-tag' }, { market_aligned: '市场一致', market_diverged: '市场分歧', elo_fifa: 'ELO/FIFA', recent_form: '近期状态', intelligence: '情报', attack_defense_profile: '攻防画像', model_odds_disagreement: '模型分歧', competition_context: '赛事语境', draw_calibration: '平局校准', odds_only: '仅赔率' }[d] || d))
            ]) : null
          ])
        : null

      // Reanalysis history section
      const reanalysisSection = reanalysisChanges.value.length > 0
        ? h('div', { class: 'ad-sec ad-reanalysis' }, [
          h('div', { class: 'ad-sec-label' }, [
            h('span', { class: 'ad-sec-icon green' }, '●'),
            h('span', null, ' 重分析历史')
          ]),
          h('div', { class: 'ad-reanalysis-list' }, reanalysisChanges.value.map(change => {
            const changes = Array.isArray(change.prediction_changes) ? change.prediction_changes : []
            const before = change.before_prediction_summary || {}
            const after = change.after_prediction_summary || {}
            const triggerMap = {
              post_learning: '学习后重算', gap_filled: '缺口补数据后重算', manual: '手动重算',
              auto_gap_post_learning: '学习后自动重算', automation_center_future_reanalysis: '自动化重算',
              evidence_signature_reanalysis: '证据签名重算', football_data_squad_probe: '阵容探测重算',
              identity_source_cleanup_20260626: '数据源清理重算', live_injury_news_probe_reanalysis: '伤停探测重算',
              local_bqc_axis_refresh_future_future_reanalysis: '半全场轴刷新',
              local_model_refresh_after_rqspf_score_axis_future_reanalysis: '让球比分轴刷新',
              local_reanalysis_change_table_smoke: '烟雾测试', local_rqspf_boundary_refresh_future_future_reanalysis: '让球边界刷新',
              manual_after_channel_registry_ou_fix: 'O/U渠道修复重算', manual_after_odds_fallback_fix: '赔率兜底修复重算',
              manual_post_learning_future_reanalysis: '手动学习后重算', restore_squad_evidence: '阵容证据恢复',
              spf_schema_normalization_20260626: '胜平负格式规范化', squad_cache_0627: '阵容缓存刷新',
            }
            const trigger = triggerMap[change.trigger_source] || change.trigger_source || '重分析'
            const time = change.created_at ? change.created_at.slice(5, 16) : ''
            const settled = change.settled_at
            const validation = change.validation || {}
            const validated = validation.correct != null
            const validatedOk = validation.correct === true
            return h('div', { class: 'ad-reanalysis-item' }, [
              h('div', { class: 'ad-reanalysis-header' }, [
                h('span', { class: 'ad-reanalysis-trigger' }, trigger),
                h('span', { class: 'ad-reanalysis-time' }, time),
                change.prediction_changed ? h('span', { class: 'ad-reanalysis-badge changed' }, '推荐变化') : h('span', { class: 'ad-reanalysis-badge unchanged' }, '无变化'),
                settled ? h('span', { class: ['ad-reanalysis-settled', validated ? (validatedOk ? 'ok' : 'bad') : ''].join(' ') }, validated ? (validatedOk ? '命中' : '未中') : '已结算') : null
              ]),
              changes.length > 0 ? h('div', { class: 'ad-reanalysis-changes' }, changes.slice(0, 4).map(c =>
                h('div', { class: 'ad-reanalysis-diff' }, [
                  h('span', { class: 'ad-reanalysis-label' }, c.label || ''),
                  h('span', { class: 'ad-reanalysis-before' }, c.before ?? '--'),
                  h('span', { class: 'ad-reanalysis-arrow' }, '→'),
                  h('span', { class: 'ad-reanalysis-after' }, c.after ?? '--')
                ])
              )) : null,
              (before.recommendation && after.recommendation) ? h('div', { class: 'ad-reanalysis-summary' }, [
                h('span', null, '推荐: '),
                h('span', { class: 'ad-reanalysis-before' }, resultLabel(before.recommendation)),
                h('span', { class: 'ad-reanalysis-arrow' }, '→'),
                h('span', { class: 'ad-reanalysis-after' }, resultLabel(after.recommendation))
              ]) : null
            ])
          }))
        ])
        : null

      // Bottom disclaimer
      const disclaimer = h('div', { class: 'ad-disclaimer' }, 'ℹ 以上分析仅供参考，请理性投注')

      return h('div', { class: 'analysis-detail' }, [section1, section2, sectionDataStatus, sectionEvidence, sectionIntelFactors, sectionWorldCup, section3, section4, sectionDerivation, section5, section6, sectionLearning, matchScriptSection, reanalysisSection, disclaimer])
    }
  }
})



export default {

  name: 'LotteryCenter',

  components: {

    ActivityIcon,

    BarChartIcon,

    StarIcon,

    TargetIcon,

    CalendarIcon,

    ChevronLeftIcon,

    ChevronRightIcon,

    CloseIcon,

    RefreshIcon,

    WorldCupContext,

    LotteryAnalysisDetail

  },

  setup() {

    const selectedDate = ref(new Date())

    const matches = ref([])
    const showIncompleteOnly = ref(false)

    const loading = ref(false)

    const showDetailModal = ref(false)

    const selectedMatch = ref(null)

    const visibleLeagueIds = ref(null) // null = show all, Set = only those

    // 通用超时fetch
    const fetchWithTimeout = (url, options = {}, timeoutMs = 120000) => {
      const controller = new AbortController()
      const id = setTimeout(() => controller.abort(), timeoutMs)
      return fetch(url, { ...options, signal: controller.signal })
        .then(r => { clearTimeout(id); return r })
        .catch(e => { clearTimeout(id); throw e })
    }


    const loadVisibleLeagues = async () => {

      try {

        const res = await userAPI.getVisibleLeagues()

        const leagues = res.leagues || res.data || res || []

        if (leagues.length > 0) {

          visibleLeagueIds.value = new Set(leagues.map(l => String(l.league_id)))

        } else {

          visibleLeagueIds.value = null

        }

      } catch (e) {

        visibleLeagueIds.value = null

      }

    }



    const stats = ref({

      total_matches: 0,

      analyzed_matches: 0,

      value_bets: 0,

      accuracy: 0

    })



    const accuracyData = ref({

      spf: 0,

      spf_count: 0,

      bf: 0,

      bf_count: 0,

      ou: 0,

      ou_count: 0,

      bqc: 0,

      bqc_count: 0,

      rqspf: 0,

      rqspf_count: 0,

      overall: 0,

      total_count: 0,

      trend: 0

    })

    // Tab state
    const activeTab = ref('matches')

    // Review state
    const reviewRecords = ref([])
    const reviewLoading = ref(false)
    const reviewPlayType = ref('')
    const reviewCorrect = ref('')
    const reviewSummary = ref({ total: 0, accuracy: 0 })
    const reviewInsights = ref(null)

    // Health state
    const healthData = ref(null)
    const healthRangeData = ref(null)
    const automationAuditData = ref(null)
    const automationDashboardData = ref(null)
    const automationControlData = ref(null)
    const healthLoading = ref(false)
    const schedulerData = ref(null)
    const schedulerTriggering = ref(false)
    const schedulerTriggerResult = ref(null)

    // 情报层状态：体彩中心只展示证据质量，不把情报中枢作为主入口
    const intelligenceJobsByLottery = ref({})
    const intelligenceLoading = ref(false)
    const intelligenceAvailable = ref(true)
    const resultSyncing = ref(false)
    const resultSyncResult = ref(null)
    const ouLineSyncing = ref(false)
    const ouLineSyncResult = ref(null)
    const autoGapRunning = ref(false)
    const autoGapResult = ref(null)
    const eventSyncMaxEvents = ref(4)
    const eventSyncBatches = ref(3)
    const eventSyncGap = ref(2)
    const dataCompletenessState = ref(null)
    const dataCompletenessByMatch = ref({})
    const showResultCorrectionModal = ref(false)
    const resultCorrectionMatch = ref(null)
    const resultCorrectionSaving = ref(false)
    const resultCorrectionError = ref('')
    const resultRefreshingById = ref({})
    const resultCorrectionForm = ref({
      home_goals_ft: '',
      away_goals_ft: '',
      home_goals_ht: '',
      away_goals_ht: '',
      reason: '',
    })

    const playTypeLabel = (pt) => {
      const labels = { spf: '胜平负', ou: '大小球', bf: '比分', bqc: '半全场', rqspf: '让球胜平负' }
      return labels[pt] || pt
    }

    const pressureReasonLabel = (value) => ({
      missing_standing: '缺少实时积分',
      opening_round_positioning: '首轮定位阶段',
      win_can_push_direct_qualification: '赢球可推动直接晋级',
      needs_points_before_final_round: '末轮前需要抢分',
      group_shape_still_open: '小组形势仍开放',
      protect_or_improve_draw_position: '保护或提升落位',
      third_place_and_goal_difference_pressure: '第三名与净胜球压力',
      must_win_or_chase_margin: '必须赢球或追净胜球',
      live_world_cup_group_pressure_context: '实时小组压力',
      no_directional_group_pressure_edge: '小组压力差异不明显'
    }[value] || value || '晋级压力')

    const reviewTagLabel = (tag) => {
      const text = String(tag || '')
      const direct = {
        'result:correct': '命中',
        'result:wrong': '未命中',
        'market:aligned': '赔率一致',
        'market:diverged': '赔率分歧',
        'intel:fallback_used': '兜底情报',
        'intel:low_confidence': '低置信情报',
        'context:world_cup': '世界杯语境'
      }
      if (direct[text]) return direct[text]
      if (text.startsWith('play:')) return playTypeLabel(text.slice(5))
      if (text.startsWith('confidence:')) return `置信${text.slice(11)}`
      if (text.startsWith('world_cup:matchday_')) return `小组第${text.split('_').pop()}轮`
      if (text.startsWith('scenario:')) return text.slice(9)
      if (text.startsWith('pressure:')) {
        const raw = text.slice(9)
        const [side, ...rest] = raw.split('_')
        const sideLabel = side === 'home' ? '主队' : side === 'away' ? '客队' : ''
        return [sideLabel, pressureReasonLabel(rest.join('_') || raw)].filter(Boolean).join(' ')
      }
      return text
    }

    const actionItemLabel = (item) => {
      const labels = {
        keep_as_positive_case: '保留正样本',
        mark_low_confidence_positive: '低置信命中复核',
        review_high_confidence_error: '复核高置信错误',
        review_market_divergence_weight: '校准赔率分歧权重',
        improve_low_confidence_intelligence: '补强低置信情报',
        separate_derivative_play_risk: '拆分衍生玩法风险'
      }
      return labels[item] || item || '--'
    }

    const accuracyValue = (value, count) => {
      if (!count) return '--'
      const numeric = Number(value || 0)
      return `${numeric.toFixed(1).replace(/\.0$/, '')}%`
    }

    const accuracySample = (count) => {
      const n = Number(count || 0)
      return n > 0 ? `${n}场` : '样本不足'
    }

    const trendClass = (trend) => {
      const n = Number(trend || 0)
      if (n > 0) return 'positive'
      if (n < 0) return 'negative'
      return ''
    }

    const trendText = (trend) => {
      const n = Number(trend || 0)
      if (n > 0) return '上升'
      if (n < 0) return '下降'
      return '稳定'
    }

    const applyAccuracyPayload = (data = {}) => {
      accuracyData.value = {
        spf: data.spf_accuracy || 0,
        spf_count: data.spf_count || 0,
        bf: data.bf_accuracy || 0,
        bf_count: data.bf_count || 0,
        ou: data.ou_accuracy || 0,
        ou_count: data.ou_count || 0,
        bqc: data.bqc_accuracy || 0,
        bqc_count: data.bqc_count || 0,
        rqspf: data.rqspf_accuracy || 0,
        rqspf_count: data.rqspf_count || 0,
        overall: data.overall_accuracy || 0,
        total_count: data.total_count || 0,
        trend: data.trend || 0
      }
      stats.value.accuracy = data.overall_accuracy || 0
    }

    const effectPercentState = (value, count, good = 55, warn = 45) => {
      const n = Number(value || 0)
      const sample = Number(count || 0)
      if (sample < 20) return 'planned'
      if (n >= good) return 'success'
      if (n >= warn) return 'running'
      return 'failed'
    }

    const weightedAccuracy = (...items) => {
      let total = 0
      let weighted = 0
      items.forEach(([value, count]) => {
        const sample = Number(count || 0)
        if (sample <= 0) return
        total += sample
        weighted += Number(value || 0) * sample
      })
      return total > 0 ? weighted / total : 0
    }

    const fetchReview = async () => {
      reviewLoading.value = true
      try {
        const params = new URLSearchParams({ days: '30' })
        const insightParams = new URLSearchParams({ days: '30' })
        if (reviewPlayType.value) params.append('play_type', reviewPlayType.value)
        if (reviewPlayType.value) insightParams.append('play_type', reviewPlayType.value)
        if (reviewCorrect.value) params.append('correct', reviewCorrect.value)
        const [res, insightRes] = await Promise.all([
          fetch(`/api/v1/lottery/review?${params}`).then(r => r.json()),
          fetch(`/api/v1/lottery/review/insights?${insightParams}`).then(r => r.json())
        ])
        reviewRecords.value = res.records || []
        reviewSummary.value = res.summary || { total: 0, accuracy: 0 }
        reviewInsights.value = insightRes || null
      } catch (e) {
        console.error('复盘加载失败:', e)
      } finally {
        reviewLoading.value = false
      }
    }

    const fetchHealth = async () => {
      healthLoading.value = true
      try {
        const auditWindow = automationAuditWindow()
        const [healthRes, rangeRes, schedulerRes, auditRes, dashboardRes, reviewInsightRes, accuracyRes] = await Promise.all([
          lotteryAPI.getHealth(),
          lotteryAPI.getDataCompletenessRange({
            startDate: auditWindow.startDate,
            endDate: auditWindow.endDate,
            limitPerDay: 250,
          }),
          cycleAPI.getSchedulerStatus(),
          lotteryAPI.getAutomationAudit({
            dateFrom: auditWindow.startDate,
            dateTo: auditWindow.endDate,
            recentHours: 24,
          }).catch(e => ({ detail: e.message || 'automation audit failed' })),
          lotteryAPI.getAutomationDashboard({
            dateFrom: auditWindow.startDate,
            dateTo: auditWindow.endDate,
            league: '世界杯',
            recentHours: 24,
          }).catch(e => ({ detail: e.message || 'automation dashboard failed' })),
          fetch('/api/v1/lottery/review/insights?days=30').then(r => r.json()).catch(e => ({ detail: e.message || 'review insight failed' })),
          fetch('/api/v1/lottery/accuracy?days=30').then(r => r.ok ? r.json() : null).catch(() => null),
        ])
        healthData.value = healthRes.health || null
        healthRangeData.value = rangeRes.detail ? null : rangeRes
        schedulerData.value = schedulerRes.detail ? null : schedulerRes
        automationDashboardData.value = dashboardRes.detail ? null : dashboardRes
        automationControlData.value = automationDashboardData.value?.control || schedulerData.value?.automation_control || null
        if (schedulerData.value) {
          schedulerData.value = {
            ...schedulerData.value,
            scheduler_paused: Boolean(schedulerData.value.paused),
            paused: Boolean(schedulerData.value.paused) || automationControlData.value?.enabled === false,
          }
        }
        automationAuditData.value = automationDashboardData.value?.audit || (auditRes.detail ? null : auditRes)
        reviewInsights.value = reviewInsightRes.detail ? reviewInsights.value : reviewInsightRes
        if (accuracyRes) applyAccuracyPayload(accuracyRes)
      } catch (e) {
        console.error('健康检查失败:', e)
        healthRangeData.value = null
        schedulerData.value = null
        automationAuditData.value = null
        automationDashboardData.value = null
        automationControlData.value = null
      } finally {
        healthLoading.value = false
      }
    }

    let healthRefreshTimer = null
    const stopHealthAutoRefresh = () => {
      if (healthRefreshTimer) {
        clearInterval(healthRefreshTimer)
        healthRefreshTimer = null
      }
    }
    const startHealthAutoRefresh = () => {
      stopHealthAutoRefresh()
      healthRefreshTimer = setInterval(() => {
        if (activeTab.value === 'health' && !healthLoading.value) {
          fetchHealth()
        }
      }, 20000)
    }

    const latestAutoRun = computed(() => {
      const runs = schedulerData.value?.auto_loop?.collection_runs || []
      return runs.length ? runs[0] : null
    })

    const autoLoopRuns = computed(() => schedulerData.value?.auto_loop?.collection_runs || [])

    const runStatusLabel = (status) => {
      const labels = {
        success: '成功',
        completed: '完成',
        running: '运行中',
        failed: '失败',
        error: '异常',
        stale_failed: '超时失败',
        pending: '等待',
      }
      return labels[status] || status || '未知'
    }

    const runStatusClass = (status) => {
      if (status === 'success' || status === 'completed') return 'success'
      if (status === 'running') return 'running'
      if (status === 'failed' || status === 'error' || status === 'stale_failed') return 'failed'
      return 'planned'
    }

    const formatRunTime = (value) => {
      if (!value) return '--'
      const text = String(value).replace('T', ' ')
      return text.length >= 16 ? text.slice(5, 16) : text
    }

    const triggerSourceLabel = (source) => {
      const labels = {
        scheduler_rolling_collection: '滚动流水线',
        scheduler_rolling_auto_gap: '滚动自动补齐',
        scheduler_historical_backfill: '历史流水线',
        scheduler_historical_auto_gap: '历史自动补齐',
        scheduler_intelligence_gap_fill: '情报缺口',
        scheduler_learning_refresh: '学习刷新',
        scheduler_validate_cycle: '复盘验证',
        scheduler_automation_center: '并发中控',
        manual_automation_center_api: '并发中控',
        manual_automation_center_script: '脚本中控',
        manual_auto_gap_fill_api: '手动自动补齐',
        background_auto_gap_fill_api: '手动后台补齐',
        manual_api: '手动触发',
        background_api: '后台触发',
      }
      return labels[source] || source || '-'
    }

    const runWindowText = (run) => {
      const s = run?.summary || {}
      const start = s.date_from || s.start_date || s.range?.start_date
      const end = s.date_to || s.end_date || s.range?.end_date
      if (start && end && start !== end) return `${start}~${end}`
      return run?.match_date || s.date || start || end || '-'
    }

    const latestRunBy = (predicate) => autoLoopRuns.value.find(predicate) || null

    const activeRuns = computed(() => autoLoopRuns.value.filter(run => run.status === 'running'))
    const automationControl = computed(() =>
      automationDashboardData.value?.control || schedulerData.value?.automation_control || automationControlData.value || null
    )
    const automationControlEnabled = computed(() => automationControl.value?.enabled !== false)

    const schedulerStateText = computed(() => {
      if (!schedulerData.value?.running) return '调度器未运行'
      if (schedulerData.value?.paused) return '自动已暂停，可手动启动后继续'
      if (activeRuns.value.length) return `自动中，${activeRuns.value.length} 个任务正在执行`
      return '自动中，当前空闲'
    })

    const latestRollingAutoGapRun = computed(() => latestRunBy(run =>
      run.run_type === 'auto_gap_fill' && run.trigger_source === 'scheduler_rolling_auto_gap'
    ))

    const latestHistoricalAutoGapRun = computed(() => latestRunBy(run =>
      run.run_type === 'auto_gap_fill' && run.trigger_source === 'scheduler_historical_auto_gap'
    ))

    const latestModelGateRun = computed(() => autoLoopRuns.value.find(run => run.summary?.model_gate) || null)
    const latestModelGate = computed(() => latestModelGateRun.value?.summary?.model_gate || null)
    const modelGateDecisionLabel = gate => {
      if (!gate) return '等待回测'
      if (gate.decision === 'pass') return '通过'
      if (gate.decision === 'warn') return '警告'
      return '失败'
    }
    const modelGateRollbackLabel = gate => {
      if (!gate || gate.decision !== 'fail') return ''
      if (gate.rollback_success === true) return ' · 已回滚'
      if (gate.rollback_failed) return ' · 回滚失败'
      return ' · 待回滚'
    }

    const auditMissingTotal = computed(() => Number(automationAuditData.value?.completeness?.summary?.missing_total || 0))

    const predictionConsistencyFromRun = (run) => {
      const payload = run?.summary?.payload || run?.summary || {}
      const consistency = payload.prediction_consistency || payload.post_prediction_consistency || null
      if (!consistency) return null
      return {
        run,
        consistency,
        hardIssues: Number(payload.hard_prediction_issues ?? payload.post_prediction_hard_issues ?? consistency.hard_issues ?? 0),
        parseErrors: Number(payload.prediction_parse_errors ?? payload.post_prediction_parse_errors ?? consistency.parse_errors ?? 0),
        reportsChecked: Number(consistency.reports_checked || 0),
      }
    }

    const latestPredictionConsistency = computed(() => {
      const dashboardRuns = Array.isArray(automationDashboardData.value?.recent_runs)
        ? automationDashboardData.value.recent_runs
        : []
      const candidates = [...dashboardRuns, ...autoLoopRuns.value]
      for (const run of candidates) {
        const item = predictionConsistencyFromRun(run)
        if (item) return item
      }
      return null
    })

    const automationTaskStableKey = (item, index = 0) => {
      const task = item?.task || {}
      return item?.source_task_key || `${Number(task.wave || 99)}:${task.kind || ''}:${task.date_from || ''}:${task.date_to || task.date_from || ''}`
    }

    const automationFailureBacklog = computed(() => {
      const dashboardRuns = Array.isArray(automationDashboardData.value?.recent_runs)
        ? automationDashboardData.value.recent_runs
        : []
      const seenRunIds = new Set()
      const runs = [...autoLoopRuns.value, ...dashboardRuns]
        .filter(run => {
          if (!['automation_center', 'automation_retry'].includes(run?.run_type)) return false
          const runId = run.run_id || `${run.run_type}-${run.started_at || ''}`
          if (seenRunIds.has(runId)) return false
          seenRunIds.add(runId)
          return true
        })
        .sort((a, b) => String(b?.started_at || '').localeCompare(String(a?.started_at || '')))

      const latestByTask = new Map()
      runs.forEach(run => {
        const tasks = Array.isArray(run?.summary?.tasks) ? run.summary.tasks : []
        tasks.forEach((item, index) => {
          const key = automationTaskStableKey(item, index)
          if (!key || latestByTask.has(key)) return
          const task = item.task || {}
          const payload = item.payload || {}
          const failed = item.success === false || payload.success === false
          latestByTask.set(key, {
            key,
            taskKey: key,
            taskIndex: Number.isInteger(item.source_task_index) ? item.source_task_index : index,
            failed,
            kind: task.kind || '',
            label: automationTaskKindLabel(task.kind),
            date: task.date_from === task.date_to ? task.date_from : `${task.date_from || '-'}~${task.date_to || '-'}`,
            runId: run.run_id,
            runLabel: schedulerRunLabel(run),
            reason: item.error || payload.error || item.reason || payload.reason || '',
          })
        })
      })
      return Array.from(latestByTask.values()).filter(item => item.failed).slice(0, 8)
    })

const futureReanalysisExampleText = (run, persistedChanges = []) => {
      const examples = Array.isArray(persistedChanges) && persistedChanges.length
        ? persistedChanges
        : (Array.isArray(run?.summary?.changed_examples) ? run.summary.changed_examples : [])
      if (!examples.length) return ''
      return examples.slice(0, 2).map(row => {
        const changes = Array.isArray(row.prediction_changes) ? row.prediction_changes : []
        const changeText = changes.slice(0, 2).map(item => `${item.label}${item.before}→${item.after}`).join('、')
        return `${row.match || row.lottery_match_id}${changeText ? `：${changeText}` : ''}`
      }).join('；')
    }

    const futureReanalysisWaitText = summary => {
      const wait = summary?.learning_wait
      const waited = Number(wait?.waited_seconds || 0)
      if (!wait || !Number.isFinite(waited) || waited <= 0) return ''
      return wait.proceeded_with_running_learning
        ? ` · 等学习${waited}s后继续`
        : ` · 等学习${waited}s`
    }

    const automationDashboardCards = computed(() => {
      const dashboard = automationDashboardData.value || {}
      const status = dashboard.status || {}
      const control = dashboard.control || automationControl.value || {}
      const accuracy = dashboard.accuracy || {}
      const window = dashboard.window || {}
      const futureRun = dashboard.latest_future_reanalysis || {}
      const futureSummary = futureRun.summary || {}
      const persistedChanges = Array.isArray(dashboard.recent_reanalysis_changes) ? dashboard.recent_reanalysis_changes : []
      const futureChanged = Number(futureSummary.prediction_changed || 0)
      const futureSaved = Number(futureSummary.change_rows_saved || 0)
      const futureFailed = Number(futureSummary.failed || 0)
      const futureExamples = futureReanalysisExampleText(futureRun, persistedChanges)
      const health = status.health || 'unknown'
      const healthLabel = health === 'ok' ? '正常' : (health === 'warn' ? '关注' : (health === 'bad' ? '异常' : '未知'))
      const healthState = health === 'ok' ? 'success' : (health === 'warn' ? 'running' : (health === 'bad' ? 'failed' : 'planned'))
      const controlEnabled = control.enabled !== false
      const automationLocked = Boolean(status.automation_locked || dashboard.automation_lock?.locked)
      const predictionConsistency = latestPredictionConsistency.value
      const predictionConsistencyBad = predictionConsistency && (predictionConsistency.hardIssues > 0 || predictionConsistency.parseErrors > 0)
      const predictionIssueText = predictionConsistency ? issueCountsText(predictionConsistency.consistency?.issue_counts, 3) : ''
      const failureBacklog = automationFailureBacklog.value
      const failureBacklogText = failureBacklog.slice(0, 2).map(item => `${item.label} ${item.date}`).join(' / ')
      return [
        {
          key: 'health',
          label: '中控健康',
          value: healthLabel,
          detail: `${window.date_from || '-'}~${window.date_to || '-'} · ${window.league || '全部'}`,
          state: healthState,
        },
        {
          key: 'automation_control',
          label: '中控自动',
          value: control.state_label || (controlEnabled ? '自动中' : '已暂停'),
          detail: `workers ${control.config?.workers || 3} · 历史${control.config?.historical_dates ?? 1}天 · ${control.config?.network_intelligence === false ? '本地情报' : '联网情报'}`,
          state: controlEnabled ? 'success' : 'planned',
        },
        {
          key: 'automation_lock',
          label: '中控锁',
          value: automationLocked ? '运行中' : '空闲',
          detail: dashboard.automation_lock?.stale ? '锁已过期，下次会自动清理' : (dashboard.automation_lock?.holder?.created_at_text || '没有并发占用'),
          state: automationLocked ? 'running' : 'success',
        },
        {
          key: 'prediction_consistency',
          label: '预测一致性',
          value: predictionConsistency ? `${predictionConsistency.hardIssues} 硬错` : '未审计',
          detail: predictionConsistency
            ? `${formatRunTime(predictionConsistency.run?.finished_at || predictionConsistency.run?.started_at)} · 报告${predictionConsistency.reportsChecked} · 解析错${predictionConsistency.parseErrors}`
            : '等待审计任务或门禁复审',
          state: predictionConsistency ? (predictionConsistencyBad ? 'failed' : 'success') : 'planned',
        },
        ...(predictionIssueText ? [{
          key: 'prediction_issue_counts',
          label: '硬错分类',
          value: predictionIssueText,
          detail: '预测一致性审计分类',
          state: predictionConsistencyBad ? 'failed' : 'success',
        }] : []),
        ...(failureBacklog.length ? [{
          key: 'automation_failure_backlog',
          label: '未解决失败',
          value: `${failureBacklog.length} 个`,
          detail: failureBacklogText || '等待单任务重试',
          state: 'failed',
        }] : []),
        {
          key: 'running',
          label: '正在执行',
          value: `${Number(status.running_count || 0)} 个`,
          detail: Number(status.recent_failure_count || 0) > 0 ? `近24h失败 ${status.recent_failure_count}` : '后台空闲或正常轮转',
          state: Number(status.running_count || 0) > 0 ? 'running' : 'planned',
        },
        {
          key: 'missing',
          label: '当前缺口',
          value: `${Number(status.missing_total || 0)} 项`,
          detail: Number(status.stale_running_count || 0) > 0 ? `卡住 ${status.stale_running_count}` : `体检问题 ${Number(status.finding_count || 0)}`,
          state: Number(status.missing_total || 0) > 0 || Number(status.stale_running_count || 0) > 0 ? 'failed' : 'success',
        },
        {
          key: 'accuracy',
          label: '窗口命中',
          value: accuracy.total ? `${Number(accuracy.accuracy || 0)}%` : '--',
          detail: accuracy.total ? `${Number(accuracy.correct || 0)}/${Number(accuracy.total || 0)} 已复盘玩法` : '等待已结束比赛',
          state: effectPercentState(accuracy.accuracy, accuracy.total, 58, 48),
        },
        {
          key: 'future_reanalysis',
          label: '未来刷新',
          value: futureRun.run_id ? `${Number(futureSummary.analyzed || 0)}/${Number(futureSummary.targets || 0)} 场` : '无记录',
          detail: futureRun.run_id
            ? `${formatRunTime(futureRun.finished_at || futureRun.started_at)} · 新报告${Number(futureSummary.changed_reports || 0)} · 推荐变化${futureChanged} · 留痕${futureSaved || persistedChanges.length}${futureReanalysisWaitText(futureSummary)}${futureExamples ? ` · ${futureExamples}` : ''}`
            : '等待学习后重算',
          state: futureFailed > 0 ? 'failed' : (futureRun.status === 'running' ? 'running' : (futureRun.run_id ? (futureChanged > 0 ? 'running' : 'success') : 'planned')),
        },
        {
          key: 'learning_lock',
          label: '学习写库',
          value: status.learning_locked ? '运行中' : '空闲',
          detail: status.learning_lock_stale ? '锁可能过期，需巡检' : (status.learning_locked ? '复盘/相似案例刷新中' : '可接受新任务'),
          state: status.learning_lock_stale ? 'failed' : (status.learning_locked ? 'running' : 'success'),
        },
      ]
    })

    const automationStatusCards = computed(() => {
      const schedulerRunning = !!schedulerData.value?.running
      const schedulerPaused = !!schedulerData.value?.paused
      const rollingRun = latestRollingAutoGapRun.value
      const historicalRun = latestHistoricalAutoGapRun.value
      const pending = Number(schedulerData.value?.auto_loop?.revalidation_pending || 0)
      const baseData = baselineComparisonData.value
      const baseModelAcc = baseData?.model_vs_market?.model_accuracy
      const baseMarketAcc = baseData?.model_vs_market?.market_accuracy
      const beatsMarket = baseData?.model_vs_market?.beats_market
      return [
        {
          key: 'scheduler',
          label: '调度器',
          value: schedulerPaused ? '已暂停' : (schedulerRunning ? '自动中' : '未运行'),
          detail: `${(schedulerData.value?.jobs || []).length} 个计划任务`,
          state: schedulerPaused ? 'planned' : (schedulerRunning ? 'success' : 'failed'),
        },
        {
          key: 'active_runs',
          label: '正在执行',
          value: `${activeRuns.value.length} 个`,
          detail: activeRuns.value.length ? activeRuns.value.map(run => schedulerRunLabel(run)).join(' / ') : '当前空闲',
          state: activeRuns.value.length ? 'running' : 'planned',
        },
        {
          key: 'model_gate',
          label: '模型门禁',
          value: modelGateDecisionLabel(latestModelGate.value),
          detail: latestModelGate.value
            ? `${formatRunTime(latestModelGateRun.value?.started_at)} · Δ${latestModelGate.value.overall_delta_pp ?? 0}pp · 硬矛盾${latestModelGate.value.hard_issues ?? 0}${modelGateRollbackLabel(latestModelGate.value)}`
            : '强制重分析后自动评估',
          state: latestModelGate.value
            ? (latestModelGate.value.decision === 'pass' ? 'success' : latestModelGate.value.decision === 'warn' ? 'running' : 'failed')
            : 'planned',
        },
        {
          key: 'rolling_gap',
          label: '滚动自动补齐',
          value: rollingRun ? runStatusLabel(rollingRun.status) : '无记录',
          detail: rollingRun ? `${formatRunTime(rollingRun.started_at)} · ${autoRunSummaryText(rollingRun)}` : '等待首次运行',
          state: rollingRun ? runStatusClass(rollingRun.status) : 'planned',
        },
        {
          key: 'historical_gap',
          label: '历史自动补齐',
          value: historicalRun ? runStatusLabel(historicalRun.status) : '无记录',
          detail: historicalRun ? `${formatRunTime(historicalRun.started_at)} · ${autoRunSummaryText(historicalRun)}` : '等待首次运行',
          state: historicalRun ? runStatusClass(historicalRun.status) : 'planned',
        },
        {
          key: 'audit_missing',
          label: '窗口缺口',
          value: `${auditMissingTotal.value} 项`,
          detail: automationAuditData.value ? `${automationAuditData.value.window?.date_from || ''}~${automationAuditData.value.window?.date_to || ''}` : '等待体检',
          state: auditMissingTotal.value > 0 ? 'failed' : 'success',
        },
        {
          key: 'revalidation',
          label: '复盘队列',
          value: `${pending} 条`,
          detail: pending > 0 ? '等待验证落库' : '无待处理',
          state: pending > 0 ? 'running' : 'success',
        },
        {
          key: 'baseline_vs_market',
          label: '模型 vs 市场',
          value: baseModelAcc != null ? `${(baseModelAcc * 100).toFixed(1)}%` : '--',
          detail: baseModelAcc != null && baseMarketAcc != null
            ? `市场${(baseMarketAcc * 100).toFixed(1)}% · Δ${(baseData?.model_vs_market?.delta_pp ?? 0).toFixed(1)}pp${beatsMarket ? ' ✓' : ''}`
            : '等待基线数据',
          state: baseModelAcc != null ? (beatsMarket ? 'success' : 'failed') : 'planned',
        },
        ...(persistedChanges.length > 0 ? [{
          key: 'recent_reanalysis',
          label: '最近重分析',
          value: `${persistedChanges.length} 条`,
          detail: persistedChanges.slice(0, 3).map(c => {
            const changes = Array.isArray(c.prediction_changes) ? c.prediction_changes : []
            const changeText = changes.slice(0, 2).map(item => `${item.label || ''}${item.before}→${item.after}`).join(' ')
            return `${c.match || c.lottery_match_id}${changeText ? '：' + changeText : ''}`
          }).join('；'),
          state: persistedChanges.some(c => c.prediction_changed) ? 'running' : 'success',
        }] : []),
      ]
    })

    const automationEffectCards = computed(() => {
      const a = accuracyData.value || {}
      const review = reviewInsights.value?.summary || {}
      const staleRuns = (automationAuditData.value?.collection_runs?.stale_running || []).length
      const highErrors = Number(review.high_confidence_errors || 0)
      const reviewTotal = Number(review.total || reviewSummary.value?.total || 0)
      const reviewAccuracy = review.accuracy != null ? Number(review.accuracy || 0) : Number(reviewSummary.value?.accuracy || 0)
      const reasonedRate = Number(review.reasoned_rate || 0)
      const missingTotal = auditMissingTotal.value
      const derivativeCount = Number(a.rqspf_count || 0) + Number(a.bqc_count || 0)
      const derivativeAccuracy = weightedAccuracy([a.rqspf, a.rqspf_count], [a.bqc, a.bqc_count])

      return [
        {
          key: 'overall_accuracy',
          label: '整体命中',
          value: accuracyValue(a.overall, a.total_count),
          detail: `${accuracySample(a.total_count)} · 趋势${trendText(a.trend)}`,
          state: effectPercentState(a.overall, a.total_count),
        },
        {
          key: 'spf_axis',
          label: '主判断轴',
          value: accuracyValue(a.spf, a.spf_count),
          detail: `胜平负 · ${accuracySample(a.spf_count)}`,
          state: effectPercentState(a.spf, a.spf_count),
        },
        {
          key: 'goal_axis',
          label: '进球轴',
          value: `大小球 ${accuracyValue(a.ou, a.ou_count)}`,
          detail: `比分 ${accuracyValue(a.bf, a.bf_count)} · O/U${accuracySample(a.ou_count)}`,
          state: effectPercentState(a.ou, a.ou_count),
        },
        {
          key: 'derivative_axis',
          label: '衍生玩法',
          value: `让球 ${accuracyValue(a.rqspf, a.rqspf_count)}`,
          detail: `半全场 ${accuracyValue(a.bqc, a.bqc_count)} · 联动一致性重点看`,
          state: effectPercentState(derivativeAccuracy, derivativeCount),
        },
        {
          key: 'review_learning',
          label: '复盘沉淀',
          value: `${reviewTotal}条`,
          detail: reviewTotal ? `命中${reviewAccuracy}% · 可解释${reasonedRate}%` : '等待已结束比赛落库',
          state: reviewTotal >= 20 ? 'success' : 'planned',
        },
        {
          key: 'risk_queue',
          label: '需要复核',
          value: `${highErrors + missingTotal + staleRuns}项`,
          detail: `高置信错${highErrors} · 缺口${missingTotal} · 卡住${staleRuns}`,
          state: highErrors || missingTotal || staleRuns ? 'failed' : 'success',
        },
      ]
    })

    const automationReasonLabel = (reason) => {
      const labels = {
        no_hard_play_conflicts: '无硬冲突',
        no_bqc_full_axis_gate_signal: '无BQC全场腿信号',
        no_handicap_margin_gate_signal: '无让球边界信号',
        no_eligible_ou_conflicts: '无可用O/U冲突',
        dry_run_delta_worse: '回测变差，已拦截',
        dry_run_has_regression: '存在回归，已拦截',
        skipped_validation_no_result_changes_after_audit: '赛果无变更，跳过复盘',
        skipped_learning_no_analysis_validation_or_result_changes: '无新增分析/复盘，跳过学习',
        national_reference_fact_table_missing: '国家队样本表缺失',
      }
      return labels[reason] || reason || ''
    }

    const automationTaskKindLabel = (kind) => {
      const labels = {
        result_audit: '赛果/预测审计',
        event_details: '赛果/Odds',
        ou_lines: '真实O/U盘',
        intelligence: '情报补齐',
        analysis: '分析重算',
        play_consistency_gate: '玩法一致性',
        bqc_full_axis_gate: 'BQC全场腿',
        handicap_margin_gate: '让球校准',
        validation: '复盘验证',
        national_ou_gate: '国家队O/U',
        bqc_half_time_profile: '半场画像',
        bqc_full_time_axis: '全场轴审计',
        handicap_margin_axis: '让球边界',
        prediction_error_review: '错误归因',
        learning: '学习刷新',
      }
      return labels[kind] || kind || '-'
    }

    const pairListText = (items, limit = 3) => {
      if (!items) return ''
      const normalized = Array.isArray(items)
        ? items
        : Object.entries(items || {})
      return normalized.slice(0, limit).map(item => {
        if (Array.isArray(item)) return `${item[0]} ${item[1]}`
        if (item?.key != null) return `${item.key} ${item.count ?? item.value ?? ''}`.trim()
        return String(item)
      }).filter(Boolean).join(' / ')
    }

    const issueCountsText = (counts, limit = 2) => pairListText(counts || {}, limit)

    const automationTaskMetricText = (kind, payload = {}) => {
      if (kind === 'prediction_error_review') {
        return `归因${Number(payload.saved || 0)}条 · 错误${Number(payload.wrong || 0)}/${Number(payload.plays || 0)}`
      }
      if (kind === 'bqc_half_time_profile') {
        return `画像${Number(payload.saved_profiles || 0)} · 审计${Number(payload.saved_audits || 0)} · 模式${Number(payload.saved_patterns || 0)} · 净${payload.delta_correct ?? 0}`
      }
      if (kind === 'bqc_full_time_axis') {
        return `保存${Number(payload.saved || 0)} · 样本${Number(payload.scored_matches || 0)} · BQC腿${Number(payload.bqc_full_correct || 0)}`
      }
      if (kind === 'handicap_margin_axis') {
        return `保存${Number(payload.saved || 0)} · 样本${Number(payload.scored_matches || 0)} · 命中${payload.current_accuracy ?? '-'}%`
      }
      if (kind === 'validation') {
        return `验证${Number(payload.validated || 0)} · 命中${payload.accuracy ?? '-'}%`
      }
      if (kind === 'result_audit') {
        const changes = Array.isArray(payload.changes) ? payload.changes.length : Number(payload.changes || 0)
        const pc = payload.prediction_consistency || {}
        const hardIssues = Number(payload.hard_prediction_issues ?? pc.hard_issues ?? 0)
        const checked = Number(pc.reports_checked || 0)
        return `变更${changes} · 预测硬错${hardIssues}/${checked}`
      }
      const changedReports = Number(payload.changed_reports || 0)
      const predictionRows = Number(payload.prediction_rows || 0)
      const changes = Number(payload.changes || 0)
      if (changedReports || predictionRows || changes || payload.delta_correct != null) {
        return `候选${changes} · 报告${changedReports} · 预测行${predictionRows} · 净${payload.delta_correct ?? 0}`
      }
      if (kind === 'learning') return '学习刷新完成'
      return '已执行'
    }

    const automationTaskDetailText = (payload = {}) => {
      const parts = []
      const dryRun = payload.dry_run || null
      if (dryRun) {
        parts.push(`dry-run: 改${Number(dryRun.changes || 0)} / 进${Number(dryRun.improved || 0)} / 退${Number(dryRun.regressed || 0)} / 净${dryRun.delta_correct ?? 0}`)
      }
      const topErrors = pairListText(payload.top_error_categories, 2)
      if (topErrors) parts.push(`错因: ${topErrors}`)
      const topCategories = pairListText(payload.top_categories, 2)
      if (topCategories) parts.push(`分类: ${topCategories}`)
      const topTags = pairListText(payload.top_tags, 2)
      if (topTags) parts.push(`标签: ${topTags}`)
      const modelActions = pairListText(payload.model_actions, 2)
      if (modelActions) parts.push(`模型: ${modelActions}`)
      const collectionActions = pairListText(payload.collection_actions, 2)
      if (collectionActions) parts.push(`采集: ${collectionActions}`)
      const byReason = pairListText(payload.by_reason, 2)
      if (byReason) parts.push(`原因: ${byReason}`)
      const pc = payload.prediction_consistency || payload.post_prediction_consistency || null
      if (pc) {
        const issueText = issueCountsText(pc.issue_counts, 3)
        if (issueText) parts.push(`硬错分类: ${issueText}`)
        parts.push(`预测审计: 报告${Number(pc.reports_checked || 0)} / 硬错${Number(pc.hard_issues || 0)} / 解析错${Number(pc.parse_errors || 0)}`)
      }
      const remediation = payload.prediction_remediation || payload.post_prediction_remediation || null
      if (remediation?.attempted) {
        parts.push(`自动补救: 重算${Number(remediation.analyzed || 0)}/${Number(remediation.targets || 0)} / 失败${Number(remediation.failed || 0)}`)
      }
      if (payload.error) parts.push(String(payload.error))
      return parts.join(' · ')
    }

    const automationTimelineRuns = computed(() => autoLoopRuns.value.slice(0, 8))

    const latestAutomationCenterRun = computed(() =>
      autoLoopRuns.value.find(run => ['automation_center', 'automation_retry'].includes(run.run_type)) || null
    )
    const automationCenterProgress = computed(() => latestAutomationCenterRun.value?.summary?.progress || {})

    const automationCenterTaskRows = computed(() => {
      const tasks = latestAutomationCenterRun.value?.summary?.tasks || []
      return tasks.map((item, index) => {
        const task = item.task || {}
        const payload = item.payload || {}
        const taskKey = item.source_task_key || `${Number(task.wave || 99)}:${task.kind || ''}:${task.date_from || ''}:${task.date_to || task.date_from || ''}`
        const skipped = Boolean(item.skipped || payload.skipped)
        const failed = item.success === false || payload.success === false
        const state = failed ? 'failed' : (skipped ? 'planned' : 'success')
        const reason = automationReasonLabel(item.reason || payload.reason)
        const metric = automationTaskMetricText(task.kind, payload)
        return {
          key: `${taskKey}-${index}`,
          taskKey,
          taskIndex: Number.isInteger(item.source_task_index) ? item.source_task_index : index,
          label: automationTaskKindLabel(task.kind),
          date: task.date_from === task.date_to ? task.date_from : `${task.date_from || '-'}~${task.date_to || '-'}`,
          status: failed ? '失败' : (skipped ? '跳过' : '完成'),
          state,
          summary: skipped && reason ? `${reason} · ${metric}` : metric,
          detail: automationTaskDetailText(payload),
        }
      }).sort((a, b) => {
        if (a.state === b.state) return 0
        if (a.state === 'failed') return -1
        if (b.state === 'failed') return 1
        return 0
      })
    })
    const latestAutomationCenterFailedCount = computed(() =>
      automationCenterTaskRows.value.filter(row => row.state === 'failed').length
    )

    const automationCenterBrief = computed(() => {
      const run = latestAutomationCenterRun.value
      const s = run?.summary || {}
      const p = automationCenterProgress.value || {}
      if (p.total_tasks) {
        const failed = Number(p.failed_tasks ?? s.failed_tasks ?? 0)
        const total = Number(p.total_tasks || 0)
        const done = Number(p.completed_tasks || 0)
        const running = Number(p.running_tasks || 0)
        const wave = p.current_wave ? ` · wave ${p.current_wave}` : ''
        const percent = p.progress_percent != null ? ` · ${p.progress_percent}%` : ''
        return `${formatRunTime(run?.started_at)} · ${done}/${total}${percent}${wave} · 运行${running} · 跳过${Number(p.skipped_tasks || 0)} · 失败${failed}`
      }
      const skipped = automationCenterTaskRows.value.filter(row => row.status === '跳过').length
      const failed = Number(s.failed_tasks || 0)
      return `${formatRunTime(run?.started_at)} · 任务${Number(s.task_count || automationCenterTaskRows.value.length || 0)} · 跳过${skipped} · 失败${failed}`
    })

    const latestPipelineRun = computed(() => {
      return autoLoopRuns.value.find(run => ['auto_loop_cycle', 'historical_backfill'].includes(run.run_type)) || null
    })

    const gapPlanItems = computed(() => healthRangeData.value?.gap_plan || [])

    const auditFindings = computed(() => automationAuditData.value?.findings || [])

    const auditSeverityCounts = computed(() => {
      const counts = { high: 0, medium: 0, low: 0 }
      auditFindings.value.forEach(item => {
        const severity = item?.severity || 'low'
        counts[severity] = (counts[severity] || 0) + 1
      })
      return counts
    })

    const auditTopDuplicates = computed(() => {
      const reports = automationAuditData.value?.analysis_reports || {}
      return (reports.top_active_duplicates?.length ? reports.top_active_duplicates : reports.top_duplicates || []).slice(0, 6)
    })

    const auditDuplicateTitle = computed(() => {
      const reports = automationAuditData.value?.analysis_reports || {}
      return reports.top_active_duplicates?.length ? '活跃重复报告最多的比赛' : '历史重复报告最多的比赛'
    })

    const auditSeverityLabel = (severity) => {
      const labels = { high: '高', medium: '中', low: '低' }
      return labels[severity] || severity || '-'
    }

    const auditMb = (value) => {
      const n = Number(value || 0)
      return Number.isFinite(n) ? `${n.toFixed(1).replace(/\.0$/, '')}MB` : '--'
    }

    const gapActionState = (item) => {
      const count = Number(item?.count || 0)
      if (count <= 0) return 'idle'
      return Number(item?.priority || 999) <= 20 ? 'urgent' : 'planned'
    }

    const gapExampleShort = (example) => {
      const num = example?.match_num ? `${example.match_num} ` : ''
      return `${num}${example?.teams || '-'}`.trim()
    }

    const gapExampleTitle = (example) => {
      const missing = (example?.missing || []).join(' / ') || '无缺口'
      const flags = (example?.quality_flags || []).join(' / ')
      return [
        example?.beijing_time,
        example?.match_status,
        `缺口: ${missing}`,
        flags ? `标记: ${flags}` : '',
      ].filter(Boolean).join('\n')
    }

    const formatLocalDate = (date = new Date()) => {
      const y = date.getFullYear()
      const m = String(date.getMonth() + 1).padStart(2, '0')
      const d = String(date.getDate()).padStart(2, '0')
      return `${y}-${m}-${d}`
    }

    const addLocalDays = (dateText, days) => {
      const [y, m, d] = String(dateText).split('-').map(Number)
      const date = new Date(y, (m || 1) - 1, d || 1)
      date.setDate(date.getDate() + days)
      return formatLocalDate(date)
    }

    const automationAuditWindow = () => {
      const today = formatLocalDate()
      const startDate = '2026-06-01'
      const preparedThrough = addLocalDays(today, 2)
      const endDate = today < startDate ? startDate : (preparedThrough > '2026-07-19' ? '2026-07-19' : preparedThrough)
      return { startDate, endDate }
    }

    const latestAutoRunStatus = computed(() => {
      const run = latestAutoRun.value
      if (!run) return '无记录'
      return run.status === 'success' ? '成功' : (run.status || '未知')
    })

    const schedulerJobNext = (jobId) => {
      const job = (schedulerData.value?.jobs || []).find(j => j.id === jobId)
      if (!job?.next_run) return '未计划'
      const text = String(job.next_run)
      return text.slice(5, 16).replace(' ', ' ')
    }

    const schedulerJobLabels = {
      rolling_collection: '滚动采集',
      historical_backfill: '历史补齐',
      intelligence_gap_fill: '情报缺口',
      validate_cycle: '复盘验证',
      learning_refresh: '学习刷新',
      automation_center: '并发中控',
    }

    const schedulerCoreJobs = computed(() => {
      const ids = ['automation_center', 'rolling_collection', 'historical_backfill', 'intelligence_gap_fill', 'validate_cycle', 'learning_refresh']
      return ids.map(id => {
        const job = (schedulerData.value?.jobs || []).find(item => item.id === id)
        const running = autoLoopRuns.value.some(run => run.status === 'running' && (
          (id === 'automation_center' && run.run_type?.startsWith('automation_')) ||
          (id === 'rolling_collection' && (run.run_type === 'auto_loop_cycle' || run.trigger_source === 'scheduler_rolling_auto_gap')) ||
          (id === 'historical_backfill' && (run.run_type === 'historical_backfill' || run.trigger_source === 'scheduler_historical_auto_gap')) ||
          (id === 'learning_refresh' && run.run_type === 'learning_refresh') ||
          (id === 'intelligence_gap_fill' && run.trigger_source?.includes('gap_fill'))
        ))
        return {
          id,
          label: schedulerJobLabels[id] || id,
          next: schedulerJobNext(id),
          detail: running ? '正在执行' : (job?.next_run ? '已计划' : '未注册'),
          state: running ? 'running' : (job?.next_run ? 'planned' : 'missing'),
        }
      })
    })

    const schedulerRunLabel = (run) => {
      if (run?.run_type === 'automation_retry') return '中控重试'
      const labels = {
        automation_center: '并发中控',
        automation_result_audit: '中控赛果/预测审计',
        automation_event_details: '中控赛果/Odds',
        automation_ou_lines: '中控O/U盘',
        automation_intelligence: '中控情报',
        automation_analysis: '中控分析',
        automation_play_consistency_gate: '中控玩法一致性',
        automation_bqc_full_axis_gate: '中控BQC全场腿',
        automation_handicap_margin_gate: '中控让球校准',
        automation_validation: '中控复盘',
        automation_national_ou_gate: '中控国家队O/U校准',
        automation_bqc_half_time_profile: '中控半场画像',
        automation_bqc_full_time_axis: '中控全场轴审计',
        automation_handicap_margin_axis: '中控让球边界',
        automation_prediction_error_review: '中控错误归因',
        automation_learning: '中控学习',
        auto_gap_fill: '自动缺口补齐',
        auto_loop_cycle: '当前窗口流水线',
        historical_backfill: '历史倒序补齐',
        oddsfe_event_details: 'oddsfe赛果证据',
        oddsfe_ou_lines: '真实O/U盘口',
        learning_refresh: '学习底座刷新',
        post_learning_future_reanalysis: '学习后刷新未来分析',
      }
      return labels[run?.run_type] || run?.run_type || '-'
    }

    const firstBatch = (value) => {
      if (!value) return {}
      if (Array.isArray(value.batches)) return value.batches[0] || {}
      return value
    }

    const countText = (item, doneKey, totalKey = 'candidates') => {
      const done = Number(item?.[doneKey] || 0)
      const total = Number(item?.[totalKey] ?? item?.planned_candidates ?? 0)
      return total > 0 ? `${done}/${total}` : String(done)
    }

    const stepState = (item, doneKey, totalKey = 'candidates') => {
      if (!item) return 'idle'
      if (item.error) return 'bad'
      const done = Number(item?.[doneKey] || 0)
      const total = Number(item?.[totalKey] ?? item?.planned_candidates ?? 0)
      if (done > 0) return 'ok'
      if (total > 0) return 'warn'
      return 'idle'
    }

    const pipelineStepCards = computed(() => {
      const run = latestPipelineRun.value
      const s = run?.summary || {}
      const oddsfe = firstBatch(s.oddsfe)
      const oddsfeOu = s.oddsfe_ou || {}
      const gapSummary = s.intelligence_gap_fill?.summary || s.intelligence_gap_fill || {}
      const validation = s.validation || {}
      const similar = s.similar_cases || {}
      return [
        {
          key: 'oddsfe',
          label: '赛果证据',
          value: `API ${Number(oddsfe.event_api_fetched || 0)}`,
          detail: `赛果+${Number(oddsfe.lottery_results_inserted || 0)}/${Number(oddsfe.lottery_results_updated || 0)}`,
          state: oddsfe.error ? 'bad' : (Number(oddsfe.event_api_fetched || 0) > 0 || Number(oddsfe.lottery_results_updated || 0) > 0 ? 'ok' : 'idle'),
        },
        {
          key: 'oddsfe_ou',
          label: '真实O/U盘',
          value: `${Number(oddsfeOu.updated || 0)}/${Number(oddsfeOu.candidates || 0)}`,
          detail: oddsfeOu.skipped ? oddsfeOu.reason : `缓存${Number(oddsfeOu.from_oddsfe_merged || 0)} 实时${Number(oddsfeOu.live_fetched || 0)}`,
          state: oddsfeOu.error ? 'bad' : (Number(oddsfeOu.updated || 0) > 0 ? 'ok' : (Number(oddsfeOu.candidates || 0) > 0 ? 'warn' : 'idle')),
        },
        {
          key: 'analysis',
          label: '首轮分析',
          value: countText(s.analysis, 'analyzed'),
          detail: s.analysis?.reason || '缺失/过期报告',
          state: stepState(s.analysis, 'analyzed'),
        },
        {
          key: 'intelligence',
          label: '情报补齐',
          value: `${Number(gapSummary.processed || 0)}/${Number(gapSummary.planned_candidates || 0)}`,
          detail: s.finished_intelligence_backfill?.summary ? '含已结束比赛情报回填' : '按缺口优先级',
          state: gapSummary.error ? 'bad' : (Number(gapSummary.processed || 0) > 0 ? 'ok' : 'idle'),
        },
        {
          key: 'post_intel_analysis',
          label: '情报后重算',
          value: countText(s.post_intelligence_analysis, 'analyzed'),
          detail: '情报更新后自动重算',
          state: stepState(s.post_intelligence_analysis, 'analyzed'),
        },
        {
          key: 'validation',
          label: '验证复盘',
          value: validation.validated != null ? `${validation.validated}条` : `${Number(s.queued_revalidation?.processed || 0)}队列`,
          detail: validation.accuracy != null ? `准确率${validation.accuracy}%` : '等待完赛',
          state: validation.error ? 'bad' : (Number(validation.validated || 0) > 0 ? 'ok' : 'idle'),
        },
        {
          key: 'similar',
          label: '相似案例',
          value: similar.skipped ? '跳过' : (similar.error ? '异常' : '已刷新'),
          detail: similar.reason || similar.error || '用于后续命中率提升',
          state: similar.error ? 'bad' : (similar.skipped ? 'idle' : 'ok'),
        },
      ]
    })

    const autoRunSummaryText = (run) => {
      const s = run?.summary || {}
      if (run?.run_type === 'post_learning_future_reanalysis') {
        const examples = Array.isArray(s.changed_examples) ? s.changed_examples : []
        const exampleText = examples.slice(0, 2).map(row => {
          const changes = Array.isArray(row.prediction_changes) ? row.prediction_changes : []
          const changeText = changes.slice(0, 2).map(item => `${item.label}${item.before}→${item.after}`).join('、')
          return `${row.match || row.lottery_match_id}${changeText ? `：${changeText}` : '：报告刷新'}`
        }).join('；')
        const base = `未来重算${Number(s.analyzed || 0)}/${Number(s.targets || 0)} · 新报告${Number(s.changed_reports || 0)} · 推荐变化${Number(s.prediction_changed || 0)} · 失败${Number(s.failed || 0)}`
        return exampleText ? `${base} · ${exampleText}` : base
      }
      if (run?.run_type === 'auto_gap_fill') {
        const actions = Object.values(s.action_counts || {}).reduce((sum, value) => sum + Number(value || 0), 0)
        const steps = s.steps || {}
        const analyzed = Number(steps.analysis?.analyzed || 0)
        const ouUpdated = Number(steps.ou_lines?.updated || 0)
        const eventFetched = Number(steps.event_details?.event_api_fetched || 0)
        return `动作${actions} · 赛果${eventFetched} · O/U${ouUpdated} · 分析${analyzed}`
      }
      if (run?.run_type === 'auto_loop_cycle' || run?.run_type === 'historical_backfill') {
        const analysis = Number(s.analysis?.analyzed || 0)
        const post = Number(s.post_intelligence_analysis?.analyzed || 0)
        const validation = Number(s.validation?.validated || 0)
        const oddsfe = firstBatch(s.oddsfe)
        const fetched = Number(oddsfe.event_api_fetched || 0)
        const ouUpdated = Number(s.oddsfe_ou?.updated || 0)
        return `API${fetched} · O/U${ouUpdated} · 分析${analysis} · 情报后${post} · 验证${validation}`
      }
      if (run?.run_type === 'automation_center') {
        const gate = s.model_gate || null
        const gateText = gate
          ? `门禁${modelGateDecisionLabel(gate)} Δ${gate.overall_delta_pp ?? 0}pp${modelGateRollbackLabel(gate)}`
          : '未触发门禁'
        return `任务${Number(s.task_count || 0)} · 失败${Number(s.failed_tasks || 0)} · ${gateText}`
      }
      if (run?.run_type === 'automation_result_audit') {
        const p = s.payload || {}
        const pc = p.prediction_consistency || {}
        const hardIssues = Number(p.hard_prediction_issues ?? pc.hard_issues ?? 0)
        const checked = Number(pc.reports_checked || 0)
        const changes = Array.isArray(p.changes) ? p.changes.length : Number(p.changes || 0)
        return `赛果变更${changes} · 预测硬错${hardIssues}/${checked}`
      }
      if (run?.run_type === 'automation_national_ou_gate') {
        const p = s.payload || {}
        if (p.skipped) {
          return `O/U校准跳过 · ${p.reason || '无候选'}`
        }
        return `O/U校准${Number(p.changed_reports || 0)}场 · 预测行${Number(p.prediction_rows || 0)} · 净${p.delta_correct ?? 0}`
      }
      if (run?.run_type === 'automation_play_consistency_gate') {
        const p = s.payload || {}
        if (p.skipped) {
          return `一致性跳过 · ${p.reason || '无硬冲突'}`
        }
        return `一致性${Number(p.changed_reports || 0)}场 · 预测行${Number(p.prediction_rows || 0)} · 净${p.delta_correct ?? 0}`
      }
      if (run?.run_type === 'automation_bqc_full_axis_gate') {
        const p = s.payload || {}
        if (p.skipped) {
          return `BQC全场腿跳过 · ${p.reason || '无仲裁信号'}`
        }
        return `BQC全场腿${Number(p.changed_reports || 0)}场 · 净${p.delta_correct ?? 0} · 全场腿${p.full_delta_correct ?? 0}`
      }
      if (run?.run_type === 'automation_handicap_margin_gate') {
        const p = s.payload || {}
        if (p.skipped) {
          return `让球校准跳过 · ${p.reason || '无边界信号'}`
        }
        const reasons = p.by_reason || {}
        const topReason = Object.keys(reasons)[0] || '无主因'
        return `让球校准${Number(p.changed_reports || 0)}场 · 净${p.delta_correct ?? 0} · ${topReason}`
      }
      if (run?.run_type === 'automation_bqc_half_time_profile') {
        const p = s.payload || {}
        if (p.skipped) {
          return `半场画像跳过 · ${p.reason || '无样本'}`
        }
        return `半场画像${Number(p.saved_profiles || 0)}条 · 模式${Number(p.saved_patterns || 0)}条 · 净${p.delta_correct ?? 0}`
      }
      if (run?.run_type === 'automation_bqc_full_time_axis') {
        const p = s.payload || {}
        const topDriver = Array.isArray(p.drivers) && p.drivers.length ? `${p.drivers[0][0]} ${p.drivers[0][1]}` : '无driver'
        return `全场轴${Number(p.saved || 0)}条 · BQC全场腿${Number(p.bqc_full_correct || 0)}/${Number(p.scored_matches || 0)} · ${topDriver}`
      }
      if (run?.run_type === 'automation_handicap_margin_axis') {
        const p = s.payload || {}
        const topCategory = Array.isArray(p.top_categories) && p.top_categories.length ? `${p.top_categories[0][0]} ${p.top_categories[0][1]}` : '无主错因'
        return `让球边界${Number(p.saved || 0)}条 · 命中${p.current_accuracy ?? '-'}% · ${topCategory}`
      }
      if (run?.run_type === 'automation_prediction_error_review') {
        const p = s.payload || {}
        return `归因${Number(p.saved || 0)}条 · 错误${Number(p.wrong || 0)}/${Number(p.plays || 0)}`
      }
      const inserted = Number(s.lottery_results_inserted || 0)
      const updated = Number(s.lottery_results_updated || 0)
      const fetched = Number(s.event_api_fetched || 0)
      const queued = Number(s.revalidation_queued || 0)
      return `抓取${fetched} · 赛果+${inserted}/${updated} · 复盘${queued}`
    }

    const triggerSchedulerJob = async (jobId) => {
      schedulerTriggering.value = true
      schedulerTriggerResult.value = null
      try {
        if (schedulerData.value?.scheduler_paused) {
          throw new Error('自动调度已暂停，请先启动自动')
        }
        const res = await cycleAPI.runSchedulerJob(jobId)
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '触发失败')
        }
        schedulerTriggerResult.value = { message: `${schedulerJobLabels[jobId] || jobId} 已加入调度队列` }
        await fetchHealth()
      } catch (e) {
        console.error('触发调度失败:', e)
        schedulerTriggerResult.value = { error: true, message: e.message || '触发调度失败' }
      } finally {
        schedulerTriggering.value = false
      }
    }

    const triggerAutomationCenter = async () => {
      schedulerTriggering.value = true
      schedulerTriggerResult.value = null
      try {
        const res = await lotteryAPI.runAutomationCenter({
          mode: 'mixed',
          league: '世界杯',
          historicalDates: 1,
          workers: 3,
          taskTimeout: 300,
          maxEvents: 6,
          maxAnalysis: 10,
          maxIntelligence: 6,
          maxValidationDates: 1,
          background: true,
        })
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '并发中控启动失败')
        }
        const count = Number(res.plan?.task_count || 0)
        schedulerTriggerResult.value = { message: `并发中控已启动：${count} 个任务进入后台队列` }
        await fetchHealth()
      } catch (e) {
        schedulerTriggerResult.value = { error: true, message: e.message || '并发中控启动失败' }
      } finally {
        schedulerTriggering.value = false
      }
    }

    const pauseScheduler = async () => {
      schedulerTriggering.value = true
      schedulerTriggerResult.value = null
      try {
        const res = await lotteryAPI.pauseAutomationControl()
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '暂停失败')
        }
        schedulerTriggerResult.value = { message: '自动调度已暂停，当前正在执行的任务会自然结束' }
        await fetchHealth()
      } catch (e) {
        schedulerTriggerResult.value = { error: true, message: e.message || '暂停调度失败' }
      } finally {
        schedulerTriggering.value = false
      }
    }

    const resumeScheduler = async () => {
      schedulerTriggering.value = true
      schedulerTriggerResult.value = null
      try {
        const res = await lotteryAPI.startAutomationControl({
          runNow: true,
          workers: 3,
          historicalDates: 1,
          maxEvents: 6,
          maxAnalysis: 10,
          maxIntelligence: 6,
          maxValidationDates: 1,
        })
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '启动失败')
        }
        schedulerTriggerResult.value = { message: '自动调度已启动，可继续滚动采集或历史回补' }
        await fetchHealth()
      } catch (e) {
        schedulerTriggerResult.value = { error: true, message: e.message || '启动调度失败' }
      } finally {
        schedulerTriggering.value = false
      }
    }

    const stopAutomationControl = async () => {
      schedulerTriggering.value = true
      schedulerTriggerResult.value = null
      try {
        const res = await lotteryAPI.stopAutomationControl()
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '停止失败')
        }
        schedulerTriggerResult.value = { message: '中控自动化已停止，正在执行的任务会自然结束' }
        await fetchHealth()
      } catch (e) {
        schedulerTriggerResult.value = { error: true, message: e.message || '停止中控失败' }
      } finally {
        schedulerTriggering.value = false
      }
    }

    const retryAutomationFailures = async () => {
      const runId = latestAutomationCenterRun.value?.run_id
      if (!runId) return
      schedulerTriggering.value = true
      schedulerTriggerResult.value = null
      try {
        const res = await lotteryAPI.retryAutomationFailures({ runId, background: true, workers: 2 })
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '重试失败')
        }
        schedulerTriggerResult.value = { message: `已提交失败任务重试：${latestAutomationCenterFailedCount.value} 个` }
        await fetchHealth()
      } catch (e) {
        schedulerTriggerResult.value = { error: true, message: e.message || '提交重试失败' }
      } finally {
        schedulerTriggering.value = false
      }
    }

    const retryAutomationTask = async (row) => {
      const runId = latestAutomationCenterRun.value?.summary?.source_run_id || latestAutomationCenterRun.value?.run_id
      if (!runId || !row?.taskKey) return
      schedulerTriggering.value = true
      schedulerTriggerResult.value = null
      try {
        const res = await lotteryAPI.retryAutomationFailures({
          runId,
          taskKey: row.taskKey,
          taskIndex: row.taskIndex,
          background: true,
          workers: 1,
        })
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '重试失败')
        }
        schedulerTriggerResult.value = { message: `已提交单任务重试：${row.label} ${row.date}` }
        await fetchHealth()
      } catch (e) {
        schedulerTriggerResult.value = { error: true, message: e.message || '提交单任务重试失败' }
      } finally {
        schedulerTriggering.value = false
      }
    }

    const completenessCell = (summary, okKey, missingKey) => {
      const ok = Number(summary?.[okKey] || 0)
      const missing = Number(summary?.[missingKey] || 0)
      return missing > 0 ? `${ok}/${ok + missing} 缺${missing}` : `${ok}/${ok + missing}`
    }

    const attachIntelligenceJobs = () => {
      matches.value.forEach(match => {
        const job = intelligenceJobsByLottery.value[String(match.lottery_match_id)]
        if (job) match._intelligenceJob = job
      })
    }

    const fetchIntelligenceJobs = async () => {
      const dateStr = formatDate(selectedDate.value)
      intelligenceLoading.value = true
      try {
        const res = await intelligenceAPI.listJobs({ date: dateStr, limit: 500 })
        if (res.detail) throw new Error(res.detail)
        const jobs = Array.isArray(res.data) ? res.data : []
        const next = {}
        jobs.forEach(job => {
          if (job.lottery_match_id) next[String(job.lottery_match_id)] = job
        })
        intelligenceJobsByLottery.value = next
        intelligenceAvailable.value = true
        attachIntelligenceJobs()
      } catch (e) {
        console.warn('情报任务加载失败:', e)
        intelligenceJobsByLottery.value = {}
        intelligenceAvailable.value = false
      } finally {
        intelligenceLoading.value = false
      }
    }

    // Source health for intelligence collectors
    const sourceHealthData = ref(null)
    const modelStatusData = ref(null)
    const accuracyTrendData = ref([])
    const accuracyTrendGranularity = ref('day')
    const baselineComparisonData = ref(null)
    const fetchSourceHealth = async () => {
      try {
        const res = await intelligenceAPI.sourceHealth()
        sourceHealthData.value = res
      } catch (e) {
        sourceHealthData.value = null
      }
    }
    const fetchModelStatus = async () => {
      try {
        const res = await lotteryAPI.getModelStatus()
        modelStatusData.value = res
      } catch (e) {
        modelStatusData.value = null
      }
    }
    const fetchAccuracyTrend = async (days = 30) => {
      try {
        const res = await lotteryAPI.getAccuracyTrend({ days, granularity: accuracyTrendGranularity.value })
        accuracyTrendData.value = res?.trend || []
      } catch (e) {
        accuracyTrendData.value = []
      }
    }
    const fetchBaselineComparison = async (playType = 'spf', days = 30) => {
      try {
        const res = await lotteryAPI.getBaselineComparison({ playType, days })
        baselineComparisonData.value = res?.success ? res : null
      } catch (e) {
        baselineComparisonData.value = null
      }
    }
    const intelSourceHealth = computed(() => {
      const req = sourceHealthData.value?.requirements || {}
      const labelMap = {
        injuries_suspensions: '伤停',
        team_news: '新闻',
        expected_lineup: '阵容',
        weather: '天气',
        base_info: '基本信息',
        odds_1x2: '赔率',
        market_movement: '赔率异动',
        recent_form: '近期状态',
        fifa_ranking: 'FIFA排名',
        tournament_context: '赛事背景',
      }
      const channelLabel = { news_aggregator: 'zhibo8', apifootball_match_detail: 'apifootball', api_sports_injuries: 'api-sports', bifen188_lineups: 'bifen188', weather_fetcher: 'wttr.in', fifa_ranking_fetcher: 'FIFA排名' }
      const result = []
      for (const [key, label] of Object.entries(labelMap)) {
        const channels = req[key] || []
        if (channels.length === 0) continue
        // Use the best (highest priority healthy) channel's status
        const best = channels.find(ch => ch.health_status === 'healthy') || channels[0]
        // Build detail text: channel list + next action for gaps
        const healthyChannels = channels.filter(ch => ch.health_status === 'healthy')
        const unhealthyChannels = channels.filter(ch => ch.health_status !== 'healthy')
        let detail = ''
        if (healthyChannels.length > 0) {
          detail = `可用: ${healthyChannels.map(ch => `${channelLabel[ch.channel] || ch.channel}(P${ch.priority})`).join(', ')}`
        } else {
          const next = channels.sort((a, b) => (a.priority || 99) - (b.priority || 99))[0]
          detail = `缺口! 下一步: ${channelLabel[next?.channel] || next?.channel || '无'}(P${next?.priority || '-'}), 状态: ${next?.health_status || 'unknown'}`
        }
        if (unhealthyChannels.length > 0 && healthyChannels.length > 0) {
          detail += ` | 不可用: ${unhealthyChannels.map(ch => `${channelLabel[ch.channel] || ch.channel}(${ch.health_status})`).join(', ')}`
        }
        result.push({ key, label, status: best?.health_status || 'unknown', detail })
      }
      return result
    })

    const getMatchIntelligence = (match) => {
      if (!match) return null
      return match._intelligenceJob || intelligenceJobsByLottery.value[String(match.lottery_match_id)] || null
    }

    const fetchDataCompleteness = async () => {
      const dateStr = formatDate(selectedDate.value)
      try {
        const res = await lotteryAPI.getDataCompleteness(dateStr)
        if (res.detail) throw new Error(res.detail)
        dataCompletenessState.value = res
        const next = {}
        ;(res.matches || []).forEach(item => {
          if (item.lottery_match_id) next[String(item.lottery_match_id)] = item
        })
        dataCompletenessByMatch.value = next
        matches.value.forEach(match => {
          match._dataCompleteness = next[String(match.lottery_match_id)] || null
        })
      } catch (e) {
        console.warn('数据完整度加载失败:', e)
        dataCompletenessState.value = null
        dataCompletenessByMatch.value = {}
      }
    }

    const canCorrectResult = (match) => {
      if (match?.is_schedule_fallback) return false
      const status = String(match?.match_status || match?.sell_status || '')
      return Boolean(match?.lottery_match_id && (
        match.home_goals_ft != null ||
        status === 'finished' ||
        status === 'finished_pending' ||
        status === 'started' ||
        status === 'closed'
      ))
    }

    const canRefreshResult = (match) => {
      if (match?.is_schedule_fallback) return false
      const status = String(match?.match_status || match?.sell_status || '')
      return Boolean(match?.lottery_match_id && match?.oddsfe_event_id && (
        status === 'finished' ||
        status === 'finished_pending' ||
        status === 'started' ||
        status === 'closed' ||
        match.home_goals_ft != null
      ))
    }

    const refreshMatchResult = async (match) => {
      const key = String(match?.lottery_match_id || '')
      if (!key) return
      resultRefreshingById.value = { ...resultRefreshingById.value, [key]: true }
      try {
        const res = await lotteryAPI.refreshResult(key, { overwrite: true })
        if (res.detail || res.error) throw new Error(res.detail || res.error)
        await fetchMatches()
      } catch (e) {
        console.warn('自动刷新赛果失败:', e)
        resultSyncResult.value = {
          error: e.message || '数据源暂未返回最终赛果',
          batches: 0,
          fetched: 0,
        }
      } finally {
        const next = { ...resultRefreshingById.value }
        delete next[key]
        resultRefreshingById.value = next
      }
    }

    const openResultCorrection = (match) => {
      resultCorrectionMatch.value = match
      resultCorrectionError.value = ''
      resultCorrectionForm.value = {
        home_goals_ft: match?.home_goals_ft ?? '',
        away_goals_ft: match?.away_goals_ft ?? '',
        home_goals_ht: match?.home_goals_ht ?? '',
        away_goals_ht: match?.away_goals_ht ?? '',
        reason: '',
      }
      showResultCorrectionModal.value = true
    }

    const closeResultCorrection = () => {
      showResultCorrectionModal.value = false
      resultCorrectionMatch.value = null
      resultCorrectionError.value = ''
    }

    const numberOrNull = (value) => {
      if (value === '' || value === null || value === undefined) return null
      const n = Number(value)
      return Number.isFinite(n) ? n : null
    }

    const submitResultCorrection = async () => {
      if (!resultCorrectionMatch.value) return
      resultCorrectionSaving.value = true
      resultCorrectionError.value = ''
      try {
        const payload = {
          home_goals_ft: numberOrNull(resultCorrectionForm.value.home_goals_ft),
          away_goals_ft: numberOrNull(resultCorrectionForm.value.away_goals_ft),
          source: 'manual_frontend',
          corrected_by: 'operator',
          reason: resultCorrectionForm.value.reason || 'manual correction',
        }
        const homeHt = numberOrNull(resultCorrectionForm.value.home_goals_ht)
        const awayHt = numberOrNull(resultCorrectionForm.value.away_goals_ht)
        if (homeHt !== null && awayHt !== null) {
          payload.home_goals_ht = homeHt
          payload.away_goals_ht = awayHt
        }
        if (payload.home_goals_ft === null || payload.away_goals_ft === null) {
          resultCorrectionError.value = '全场比分必须填写'
          return
        }
        const res = await lotteryAPI.correctResult(resultCorrectionMatch.value.lottery_match_id, payload)
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '保存失败')
        }
        await fetchMatches()
        closeResultCorrection()
      } catch (e) {
        resultCorrectionError.value = e.message || '保存失败'
      } finally {
        resultCorrectionSaving.value = false
      }
    }

    const intelligenceCoverageLabel = (job) => {
      if (!job) return '未建情报包'
      const coverage = Math.round(Number(job.package_completeness ?? job.package_summary?.completeness ?? 0))
      const strict = Math.round(Number(job.strict_completeness ?? job.package_summary?.strict_completeness ?? 0))
      return `证据 ${coverage}% / 严格 ${strict}%`
    }

    const intelligenceMissingLabel = (job) => {
      if (!job) return '待补齐'
      const missing = job.missing_required || job.package_summary?.missing_required || []
      if (missing.length > 0) return '缺 ' + missing.slice(0, 2).map(requirementLabel).join(' / ')
      const strict = Number(job.strict_completeness ?? job.package_summary?.strict_completeness ?? 0)
      if (strict < 80) return '有兜底证据'
      return '可分析'
    }

    const getIntelligenceClass = (match) => {
      const job = getMatchIntelligence(match)
      if (!job) return 'missing'
      const missing = job.missing_required || job.package_summary?.missing_required || []
      if (missing.length > 0) return 'risk'
      const strict = Number(job.strict_completeness ?? job.package_summary?.strict_completeness ?? 0)
      if (strict >= 80) return 'ready'
      return 'partial'
    }

    const summarizeEventSync = (res) => {
      const batches = Array.isArray(res?.batches) ? res.batches : [res]
      return {
        batches: batches.length,
        fetched: batches.reduce((sum, item) => sum + Number(item?.event_api_fetched || 0), 0),
        remaining: batches.length ? batches[batches.length - 1]?.remaining_uncached_events : null,
        skipped: Boolean(res?.skipped),
        error: res?.detail || res?.error || null,
      }
    }

    const syncEventDetails = async () => {
      resultSyncing.value = true
      resultSyncResult.value = null
      try {
        const params = new URLSearchParams({
          date_from: formatDate(selectedDate.value),
          date_to: formatDate(selectedDate.value),
          background: 'false',
          dry_run: 'false',
          fetch_schedule: 'false',
          include_schedule_only: 'true',
          max_events: String(eventSyncMaxEvents.value),
          batches: String(eventSyncBatches.value),
          batch_gap_seconds: String(eventSyncGap.value),
          schedule_padding_days: '1',
        })
        const timeoutMs = Math.min(
          600000,
          60000 + (eventSyncMaxEvents.value * eventSyncBatches.value * 8000) + (eventSyncGap.value * eventSyncBatches.value * 1000)
        )
        const r = await fetchWithTimeout(`/api/v1/lottery/sync-oddsfe-event-details?${params}`, { method: 'POST' }, timeoutMs)
        const res = await r.json()
        resultSyncResult.value = summarizeEventSync(res)
        await fetchMatches()
      } catch (e) {
        console.error('赛果补齐失败:', e)
        resultSyncResult.value = { error: e.name === 'AbortError' ? '补齐超时' : '请求失败', batches: 0, fetched: 0 }
      } finally {
        resultSyncing.value = false
      }
    }

    const syncOddsfeOuLines = async () => {
      ouLineSyncing.value = true
      ouLineSyncResult.value = null
      try {
        const res = await lotteryAPI.syncOddsfeOuLines({
          dateFrom: '2026-06-01',
          dateTo: '2026-06-21',
          background: true,
          dryRun: false,
          fetchLive: true,
          maxEvents: 8,
          reanalyze: false,
        })
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '补真实O/U盘失败')
        }
        const updated = Number(res.updated || 0)
        const planned = Number(res.planned || 0)
        const deferred = Number(res.candidates_deferred || 0)
        ouLineSyncResult.value = {
          message: res.message || `真实O/U盘补齐已启动${updated || planned ? `，本批${updated || planned}场` : ''}${deferred ? `，剩余${deferred}场` : ''}`,
        }
        await fetchHealth()
      } catch (e) {
        console.error('真实O/U盘补齐失败:', e)
        ouLineSyncResult.value = { error: true, message: e.message || '真实O/U盘补齐失败' }
      } finally {
        ouLineSyncing.value = false
      }
    }

    const runAutoGapFill = async () => {
      autoGapRunning.value = true
      autoGapResult.value = null
      try {
        const range = healthRangeData.value?.range || {}
        const params = new URLSearchParams({
          date_from: range.start_date || '2026-06-01',
          date_to: range.end_date || '2026-06-21',
          dry_run: 'false',
          background: 'true',
          max_events: '8',
          max_analysis: '12',
          max_intelligence: '8',
          max_validation_dates: '4',
          fetch_live_ou: 'true',
          network_intelligence: 'true',
          league: '世界杯',
        })
        const r = await fetchWithTimeout(`/api/v1/lottery/auto-fill-gaps?${params}`, { method: 'POST' }, 120000)
        const res = await r.json()
        if (res.detail || res.error || res.success === false) {
          throw new Error(res.detail || res.error || '自动补齐启动失败')
        }
        const missing = Number(res.summary?.missing_total || 0)
        const actions = Object.values(res.action_counts || {}).reduce((sum, value) => sum + Number(value || 0), 0)
        autoGapResult.value = {
          message: res.message || (missing > 0 ? `自动补齐已启动，缺口${missing}项，动作${actions}项` : '当前窗口没有可执行缺口'),
        }
        await fetchHealth()
      } catch (e) {
        console.error('自动补齐失败:', e)
        autoGapResult.value = { error: true, message: e.message || '自动补齐失败' }
      } finally {
        autoGapRunning.value = false
      }
    }

    const dataCompleteness = (match) => {
      const backendRow = dataCompletenessByMatch.value[String(match?.lottery_match_id)]
      if (backendRow) {
        if (backendRow.is_schedule_fallback) {
          return [
            { key: 'schedule', label: '赛程占位', status: 'partial' },
            { key: 'score', label: backendRow.has_score ? '赛果' : '待赛果', status: backendRow.has_score ? 'ready' : 'partial' },
            { key: 'source', label: '非体彩', status: 'partial' },
          ]
        }
        return [
          { key: 'odds', label: backendRow.has_odds ? '赔率' : '缺赔率', status: backendRow.has_odds ? 'ready' : 'missing' },
          { key: 'ou_line', label: backendRow.has_ou_line ? '真实O/U盘' : '缺O/U盘', status: backendRow.has_ou_line ? 'ready' : 'missing' },
          { key: 'score', label: backendRow.has_score ? '赛果' : (backendRow.result_due ? '缺赛果' : '待赛果'), status: backendRow.has_score ? 'ready' : (backendRow.result_due ? 'missing' : 'partial') },
          { key: 'half', label: backendRow.has_half_score ? '半场' : (backendRow.result_due ? '缺半场' : '待半场'), status: backendRow.has_half_score ? 'ready' : (backendRow.result_due ? 'missing' : 'partial') },
          { key: 'analysis', label: backendRow.has_analysis ? '分析' : '未分析', status: backendRow.has_analysis ? 'ready' : 'missing' },
          { key: 'intel', label: backendRow.has_intelligence ? '情报' : '缺情报', status: backendRow.has_intelligence ? 'ready' : 'missing' },
        ]
      }
      const intel = getMatchIntelligence(match)
      const hasOdds = Boolean(match.spf_odds || match.rqspf_odds)
      const hasScore = match.home_goals_ft != null && match.away_goals_ft != null
      const hasHalf = match.home_goals_ht != null && match.away_goals_ht != null
      return [
        { key: 'odds', label: hasOdds ? '赔率' : '缺赔率', status: hasOdds ? 'ready' : 'missing' },
        { key: 'score', label: hasScore ? '赛果' : (match.match_status === 'finished' ? '缺赛果' : '待赛果'), status: hasScore ? 'ready' : 'missing' },
        { key: 'half', label: hasHalf ? '半场' : (match.match_status === 'finished' ? '缺半场' : '待半场'), status: hasHalf ? 'ready' : 'partial' },
        { key: 'analysis', label: match.has_analysis ? '分析' : '未分析', status: match.has_analysis ? 'ready' : 'partial' },
        { key: 'intel', label: intel ? '情报' : '缺情报', status: intel ? 'ready' : 'missing' },
      ]
    }

    const hasCompletenessIssue = (match) => {
      const backendRow = dataCompletenessByMatch.value[String(match?.lottery_match_id)]
      if (backendRow) return (backendRow.missing || []).length > 0
      return dataCompleteness(match).some(item => item.status === 'missing')
    }

    const completenessSummary = computed(() => {
      const backendSummary = dataCompletenessState.value?.summary
      if (backendSummary) {
        return {
          missingOdds: Number(backendSummary.missingOdds ?? backendSummary.missing_odds ?? 0),
          missingOuLine: Number(backendSummary.missingOuLine ?? backendSummary.missing_ou_line ?? 0),
          missingScore: Number(backendSummary.missingScore ?? backendSummary.missing_score ?? 0),
          missingHalf: Number(backendSummary.missingHalf ?? backendSummary.missing_half_score ?? 0),
          missingAnalysis: Number(backendSummary.missingAnalysis ?? backendSummary.missing_analysis ?? 0),
          missingIntel: Number(backendSummary.missingIntel ?? backendSummary.missing_intelligence ?? 0),
        }
      }
      const summary = {
        missingOdds: 0,
        missingOuLine: 0,
        missingScore: 0,
        missingHalf: 0,
        missingAnalysis: 0,
        missingIntel: 0,
      }
      matches.value.forEach(match => {
        const hasOdds = Boolean(match.spf_odds || match.rqspf_odds)
        const hasScore = match.home_goals_ft != null && match.away_goals_ft != null
        const hasHalf = match.home_goals_ht != null && match.away_goals_ht != null
        const intel = getMatchIntelligence(match)
        if (!hasOdds) summary.missingOdds += 1
        if (match.match_status === 'finished' && !hasScore) summary.missingScore += 1
        if (match.match_status === 'finished' && !hasHalf) summary.missingHalf += 1
        if (!match.has_analysis) summary.missingAnalysis += 1
        if (!intel) summary.missingIntel += 1
      })
      return summary
    })

    const filteredMatches = computed(() => {

      let result = matches.value

      if (visibleLeagueIds.value) {

        result = result.filter(m => visibleLeagueIds.value.has(String(m.league_id)))

      }

      if (showIncompleteOnly.value) {
        result = result.filter(hasCompletenessIssue)
      }

      return result

    })



    const formatDate = (date) => {

      const d = new Date(date)

      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

    }



    const formatHandicap = (line) => {

      if (line > 0) return `-${line}`

      if (line < 0) return `+${Math.abs(line)}`

      return '0'

    }

    const getHandicapLabel = (match) => {
      // Priority: goal_line from rqspf_odds (accurate direction: -2=主让, +1=客让)
      // Fallback: handicap_line from DB (direction unreliable)
      const rqspfOdds = match.rqspf_odds
      if (rqspfOdds && rqspfOdds.goal_line) {
        const gl = String(rqspfOdds.goal_line).trim()
        // goal_line is like "-2" or "+1" — already in correct display format
        if (gl === '0') return ''
        return gl.startsWith('-') || gl.startsWith('+') ? gl : (parseFloat(gl) > 0 ? '+' + gl : gl)
      }
      // Fallback to handicap_line
      if (match.handicap_line && match.handicap_line !== 0) {
        return formatHandicap(match.handicap_line)
      }
      return ''
    }

    const getRqspfOdds = (match) => {
      return match?.rqspf_odds || match?.odds?.rqspf || null
    }

    const hasPlayType = (match, playType) => {
      const types = Array.isArray(match?.play_types) ? match.play_types : []
      return types.map(pt => String(pt).toLowerCase()).includes(playType)
    }

    const rqspfFromOdds = (match) => {
      const odds = getRqspfOdds(match)
      if (!odds) return ''
      const labels = { '3': '让胜', '1': '让平', '0': '让负' }
      const candidates = ['3', '1', '0']
        .map(code => ({ code, odds: Number(odds[code]) }))
        .filter(item => Number.isFinite(item.odds) && item.odds > 1)
      if (!candidates.length) return ''
      candidates.sort((a, b) => a.odds - b.odds)
      return labels[candidates[0].code] || ''
    }

    const hasRqspfRow = (match) => {
      return Boolean(
        match?.rqspf_rec ||
        match?.rqspf_recommendation ||
        match?.rqspf_prediction ||
        match?.rqspf_result ||
        getRqspfOdds(match) ||
        hasPlayType(match, 'rqspf') ||
        getHandicapLabel(match)
      )
    }

    const rqspfRecommendation = (match) => {
      return match?.rqspf_rec || match?.rqspf_recommendation || match?.rqspf_prediction || rqspfFromOdds(match) || '--'
    }

    const normalizePredictionText = (value) => {
      const text = String(value || '').trim()
      if (!text || text === '--') return '--'
      const direct = {
        home_win: '\u4e3b\u80dc',
        draw: '\u5e73\u5c40',
        away_win: '\u5ba2\u80dc',
        '3': '\u4e3b\u80dc',
        '1': '\u5e73\u5c40',
        '0': '\u5ba2\u80dc',
        '\u80dc': '\u4e3b\u80dc',
        '\u5e73': '\u5e73\u5c40',
        '\u8d1f': '\u5ba2\u80dc',
      }
      return direct[text] || text
    }

    const samePrediction = (predicted, actual) => {
      const pred = normalizePredictionText(predicted)
      const act = normalizePredictionText(actual)
      return Boolean(pred && act && pred !== '--' && pred === act)
    }

    const spfCardRecommendation = (match) => {
      return normalizePredictionText(match?.main_recommendation || match?.spf_rec || match?.spf_recommendation || match?.spf_prediction || '--')
    }

    const rqspfCardRecommendation = (match) => {
      return rqspfRecommendation(match)
    }

    const bqcCardRecommendation = (match) => {
      return match?.bqc_rec || match?.bqc_recommendation || match?.bqc_prediction || '--'
    }

    const ouCardRecommendation = (match) => {
      return match?.ou_rec || match?.ou_recommendation || match?.ou_prediction || '--'
    }

    const normalizeOuValue = (value) => {
      const raw = String(value || '').trim()
      const match = raw.match(/^(大|小|走)\s*(\d+(?:\.\d+)?)/)
      if (!match) return raw
      const line = Number(match[2])
      const lineText = Number.isFinite(line) ? String(line).replace(/\.0$/, '') : match[2]
      return `${match[1]}${lineText}`
    }

    const formatOuDisplay = (value) => normalizeOuValue(value)

    const sameOuOutcome = (predicted, actual) => {
      const pred = normalizeOuValue(predicted)
      const act = normalizeOuValue(actual)
      return Boolean(pred && act && pred !== '--' && pred === act)
    }



    const getPlayTypeLabel = (pt) => {

      const labels = {

        'spf': '胜平负',

        'bf': '比分',

        'bqc': '半全场',

        'rqspf': '让球'

      }

      return labels[pt] || pt

    }



    const getPlayTypeShortLabel = (pt) => {

      const labels = {

        'spf': 'SPF',

        'bf': 'BF',

        'bqc': 'BQC',

        'rqspf': 'RQ'

      }

      return labels[pt] || pt

    }



    const getSellStatusLabel = (status) => {

      const labels = {

        'selling': '在售',

        'stopped': '停售',

        'closed': '已闭',

        'finished': '已结束',

        'started': '进行中',

        'finished_pending': '已结束(待同步)',

        'scheduled': '未开赛'

      }

      return labels[status] || status

    }



    const getConfidenceClass = (match) => {

      const level = match.confidence_level

      if (level === '高' || level === 'high') return 'high'

      if (level === '低' || level === 'low') return 'low'

      return 'medium'

    }

    const confidenceTierLabel = (match) => {

      const tierLabels = { strong: '强', medium: '中', low: '弱', avoid: '观望', high: '高' }

      const tier = match?.confidence_tier

      if (tier && tierLabels[tier]) return tierLabels[tier]

      const level = match?.confidence_level

      if (level === 'high' || level === '高') return '高'

      if (level === 'medium' || level === '中') return '中'

      if (level === 'low' || level === '低') return '低'

      return level || ''

    }



    const changeDate = (delta) => {

      const newDate = new Date(selectedDate.value)

      newDate.setDate(newDate.getDate() + delta)

      selectedDate.value = newDate

    }



    const formatMatchTime = (match) => {

      // Prefer beijing_time (actual match time) over match_date + match_time (sales date)

      if (match.beijing_time) {

        const bj = match.beijing_time.slice(0, 16) // "2026-06-16 00:00"

        const dateShort = bj.slice(5, 10)  // "06-16"

        const time = bj.slice(11)          // "00:00"

        return `${dateShort} ${time}`

      }

      const date = match.match_date || ''

      const time = match.match_time || ''

      if (!date) return time

      const dateShort = date.slice(5) // "06-13"

      return time ? `${dateShort} ${time}` : dateShort

    }



    const fetchMatches = async () => {

      loading.value = true

      try {

        const dateStr = formatDate(selectedDate.value)

        const response = await fetch(`/api/v1/lottery/matches?date=${dateStr}`)

        const contentType = response.headers.get('content-type') || ''
        if (!response.ok) {
          const text = await response.text()
          throw new Error(`lottery matches API ${response.status}: ${text.slice(0, 240)}`)
        }
        if (!contentType.includes('application/json')) {
          const text = await response.text()
          throw new Error(`lottery matches API returned non-JSON: ${text.slice(0, 240)}`)
        }

        const data = await response.json()

        matches.value = data.matches || []



        // 更新统计

        stats.value = {

          total_matches: matches.value.length,

          analyzed_matches: matches.value.filter(m => m.has_analysis).length,

          value_bets: matches.value.filter(m => m.has_analysis && m.confidence_level === 'high').length,

        }



        await fetchIntelligenceJobs()

        await fetchDataCompleteness()

        await fetchSourceHealth()
        await fetchModelStatus()
        await fetchAccuracyTrend()
        await fetchBaselineComparison()



        // 获取准确率

        fetchAccuracyData()

      } catch (e) {

        console.error('获取比赛列表失败:', e)

        matches.value = []

      } finally {

        loading.value = false

      }

    }



    const fetchAccuracyData = async () => {

      try {

        const response = await fetch('/api/v1/lottery/accuracy?days=30')

        if (response.ok) {

          const data = await response.json()
          applyAccuracyPayload(data)

        }

      } catch (e) {

        console.error('获取准确率数据失败:', e)

        // Keep default zeros - don't show fake data

      }

    }



    const analyzeMatch = async (match) => {

      try {

        const response = await fetch(`/api/v1/lottery/analyze/${match.lottery_match_id}?force=true&sync=true`, {

          method: 'POST'

        })

        const data = await response.json()

        if (data.success) {

          match.has_analysis = true

          if (data.report) {

            const fp = data.report.final_prediction || {}

            const pp = data.report.play_predictions || {}

            const analyses = data.report.analyses || {}

            const rqspf = pp.rqspf || analyses.rqspf || {}

            match.main_recommendation = fp.predicted_result || '--'

            if (rqspf.recommendation || rqspf.direction) {
              const labels = { '3': '让胜', '1': '让平', '0': '让负', home_win: '让胜', draw: '让平', away_win: '让负' }
              match.rqspf_rec = labels[rqspf.direction] || rqspf.recommendation || rqspf.direction
            }

            match.confidence_level = fp.confidence_level || '中'
            match.confidence_tier = fp.confidence_tier || match.confidence_tier

            if (data.learning) {
              data.report._learning = data.learning
            }
            match._report = data.report

          }

        }

      } catch (e) {

        console.error('分析失败:', e)

      }

    }



    const viewMatchDetail = async (match) => {

      // Always open detail modal — trigger analysis if not yet done
      if (!match.has_analysis) {
        await analyzeMatch(match)
      }
      const intelJob = getMatchIntelligence(match)
      if (intelJob && !match._intelPackage) {
        try {
          const data = await intelligenceAPI.getPackage(intelJob.job_id)
          if (data.detail) throw new Error(data.detail)
          match._intelPackage = data
        } catch (e) {
          console.warn('加载单场情报包失败:', e)
        }
      }
      selectedMatch.value = match
      showDetailModal.value = true

    }



    const closeDetailModal = () => {

      showDetailModal.value = false

      selectedMatch.value = null

    }



    watch(selectedDate, fetchMatches)

    watch(activeTab, (tab) => {
      if (tab === 'health') {
        startHealthAutoRefresh()
      } else {
        stopHealthAutoRefresh()
      }
    })



    onMounted(() => {

      loadVisibleLeagues()

      fetchMatches()

      fetchAccuracyData()

    })

    onUnmounted(stopHealthAutoRefresh)



    return {

      selectedDate,

      matches,
      showIncompleteOnly,
      completenessSummary,

      filteredMatches,

      loading,

      stats,

      accuracyData,

      accuracyValue,

      accuracySample,

      trendClass,

      showDetailModal,

      selectedMatch,

      formatDate,

      formatHandicap,

      getHandicapLabel,

      hasRqspfRow,

      rqspfRecommendation,

      spfCardRecommendation,

      rqspfCardRecommendation,

      bqcCardRecommendation,

      ouCardRecommendation,

      samePrediction,

      formatOuDisplay,

      sameOuOutcome,

      formatMatchTime,

      getPlayTypeLabel,

      getPlayTypeShortLabel,

      getSellStatusLabel,

      getConfidenceClass,

      confidenceTierLabel,

      changeDate,

      analyzeMatch,

      viewMatchDetail,

      closeDetailModal,

      activeTab,
      reviewRecords,
      reviewLoading,
      reviewPlayType,
      reviewCorrect,
      reviewSummary,
      reviewInsights,
      playTypeLabel,
      reviewTagLabel,
      actionItemLabel,
      fetchReview,
      healthData,
      healthRangeData,
      automationAuditData,
      automationDashboardData,
      automationControlData,
      healthLoading,
      schedulerData,
      schedulerTriggering,
      schedulerTriggerResult,
      schedulerStateText,
      latestAutoRun,
      latestAutoRunStatus,
      autoLoopRuns,
      activeRuns,
      automationControl,
      automationControlEnabled,
      automationDashboardCards,
      automationStatusCards,
      automationEffectCards,
      automationTimelineRuns,
      latestAutomationCenterRun,
      automationCenterTaskRows,
      latestAutomationCenterFailedCount,
      automationCenterBrief,
      latestPipelineRun,
      gapPlanItems,
      auditFindings,
      auditSeverityCounts,
      auditTopDuplicates,
      auditDuplicateTitle,
      auditSeverityLabel,
      auditMb,
      gapActionState,
      gapExampleShort,
      gapExampleTitle,
      schedulerCoreJobs,
      pipelineStepCards,
      schedulerRunLabel,
      runStatusLabel,
      runStatusClass,
      formatRunTime,
      triggerSourceLabel,
      runWindowText,
      fetchHealth,
      triggerSchedulerJob,
      triggerAutomationCenter,
      pauseScheduler,
      resumeScheduler,
      stopAutomationControl,
      retryAutomationFailures,
      retryAutomationTask,
      schedulerJobNext,
      autoRunSummaryText,
      completenessCell,
      intelligenceLoading,
      intelligenceAvailable,
      intelSourceHealth,
      modelStatusData,
      accuracyTrendData,
      accuracyTrendGranularity,
      fetchAccuracyTrend,
      baselineComparisonData,
      fetchBaselineComparison,
      resultSyncing,
      resultSyncResult,
      ouLineSyncing,
      ouLineSyncResult,
      autoGapRunning,
      autoGapResult,
      eventSyncMaxEvents,
      eventSyncBatches,
      eventSyncGap,
      getMatchIntelligence,
      getIntelligenceClass,
      intelligenceCoverageLabel,
      intelligenceMissingLabel,
      syncEventDetails,
      syncOddsfeOuLines,
      runAutoGapFill,
      dataCompleteness,
      canCorrectResult,
      canRefreshResult,
      refreshMatchResult,
      resultRefreshingById,
      openResultCorrection,
      closeResultCorrection,
      submitResultCorrection,
      showResultCorrectionModal,
      resultCorrectionMatch,
      resultCorrectionForm,
      resultCorrectionSaving,
      resultCorrectionError,


      ActivityIcon,

      BarChartIcon,

      StarIcon,

      TargetIcon,

      CalendarIcon,

      ChevronLeftIcon,

      ChevronRightIcon,

      CloseIcon,

      RefreshIcon

    }

  }

}

</script>



<style scoped>

.lottery-center {

  display: flex;

  flex-direction: column;

  gap: 20px;

  min-height: 100%;

}



/* 统计卡片 */

.stats-cards {

  display: grid;

  grid-template-columns: repeat(4, 1fr);

  gap: 16px;

}



.stat-card {

  display: flex;

  align-items: center;

  gap: 12px;

  padding: 16px;

  background: #151922;

  border-radius: 12px;

  border: 1px solid rgba(31, 41, 55, 0.8);

}



.stat-icon {

  width: 40px;

  height: 40px;

  display: flex;

  align-items: center;

  justify-content: center;

  border-radius: 10px;

}



.stat-icon.matches { background: rgba(16, 185, 129, 0.2); color: #10b981; }

.stat-icon.analyzed { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }

.stat-icon.value { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }

.stat-icon.accuracy { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }



.stat-content {

  flex: 1;

}



.stat-value {

  font-size: 24px;

  font-weight: 700;

  color: white;

}



.stat-label {

  font-size: 12px;

  color: #6b7280;

}



/* 准确率追踪面板 */

.accuracy-panel {

  padding: 16px;

  background: #151922;

  border-radius: 12px;

  border: 1px solid rgba(31, 41, 55, 0.8);

}



.accuracy-panel h3 {

  font-size: 14px;

  font-weight: 600;

  color: white;

  margin-bottom: 12px;

}



.accuracy-grid {

  display: grid;

  grid-template-columns: repeat(4, 1fr);

  gap: 12px;

  margin-bottom: 12px;

}



.accuracy-item {

  display: flex;

  flex-direction: column;

  align-items: center;

  padding: 12px;

  background: rgba(255,255,255,0.02);

  border-radius: 8px;

}



.accuracy-label {

  font-size: 11px;

  color: #6b7280;

  margin-bottom: 4px;

}



.accuracy-value {

  font-size: 20px;

  font-weight: 700;

  color: #10b981;

}



.accuracy-value.overall {

  color: #f59e0b;

}



.accuracy-sample {

  font-size: 10px;

  color: #4b5563;

  margin-top: 2px;

}



.accuracy-trend {

  display: flex;

  align-items: center;

  gap: 8px;

  font-size: 12px;

}



.trend-label {

  color: #6b7280;

}



.trend-value {

  font-weight: 600;

}



.trend-value.positive {

  color: #10b981;

}



.trend-value.negative {

  color: #ef4444;

}



/* 篩选栏 */

.filter-bar {

  display: flex;

  justify-content: space-between;

  align-items: center;

  padding: 12px 16px;

  background: #151922;

  border-radius: 8px;

  border: 1px solid rgba(31, 41, 55, 0.8);

}



.date-picker {

  display: flex;

  align-items: center;

  gap: 8px;

}



.date-nav {

  width: 32px;

  height: 32px;

  display: flex;

  align-items: center;

  justify-content: center;

  background: transparent;

  border: 1px solid #374151;

  border-radius: 6px;

  color: #9ca3af;

  cursor: pointer;

}



.date-nav:hover {

  background: rgba(255,255,255,0.05);

  color: white;

}



.current-date {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 8px 16px;

  background: rgba(255,255,255,0.05);

  border-radius: 6px;

  font-size: 14px;

  color: white;

}



.calendar-icon {

  color: #10b981;

}



/* 比赛列表 */

.matches-section {

  flex: 1;

  min-height: 200px;

  overflow-y: auto;

}

.data-health-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.42);
}

.data-health-metrics {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #cbd5e1;
}

.data-health-metrics span {
  padding: 3px 7px;
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.08);
}

.missing-toggle {
  flex: 0 0 auto;
  padding: 6px 10px;
  border: 1px solid rgba(245, 158, 11, 0.28);
  border-radius: 6px;
  background: rgba(245, 158, 11, 0.10);
  color: #fbbf24;
  font-size: 12px;
  cursor: pointer;
}

.missing-toggle.active {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
}



.loading-state, .empty-state {

  display: flex;

  flex-direction: column;

  align-items: center;

  justify-content: center;

  height: 200px;

  color: #6b7280;

}



.spinner {

  width: 40px;

  height: 40px;

  border: 3px solid #374151;

  border-top-color: #10b981;

  border-radius: 50%;

  animation: spin 1s linear infinite;

}



@keyframes spin {

  to { transform: rotate(360deg); }

}



.empty-icon {

  width: 48px;

  height: 48px;

  color: #374151;

  margin-bottom: 12px;

}



.matches-grid {

  display: grid;

  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));

  gap: 16px;

  min-width: 0;

}



.match-card {

  padding: 16px;

  min-width: 0;

  overflow: hidden;

  background: #151922;

  border-radius: 12px;

  border: 1px solid rgba(31, 41, 55, 0.8);

  cursor: pointer;

  transition: all 0.2s;

}



.match-card:hover {

  border-color: #374151;

  transform: translateY(-2px);

}



.mc-header {

  display: flex;

  align-items: center;

  gap: 8px;

  margin-bottom: 10px;

}

.mc-num {

  font-size: 11px;

  font-weight: 600;

  color: #10b981;

  background: rgba(16, 185, 129, 0.1);

  padding: 1px 6px;

  border-radius: 3px;

}

.mc-league {

  font-size: 11px;

  color: #6b7280;

}

.mc-time {

  font-size: 11px;

  color: #9ca3af;

  margin-left: auto;

}



.mc-teams {

  display: flex;

  align-items: center;

  gap: 8px;

  margin-bottom: 10px;

}

.mc-team-col {

  flex: 1;

  min-width: 0;

  display: flex;

  flex-direction: column;

  align-items: center;

  gap: 2px;

}

.mc-team-col.away { }

.mc-team-name {

  font-size: 14px;

  font-weight: 700;

  color: white;

  max-width: 100%;

  overflow: hidden;

  text-overflow: ellipsis;

  white-space: nowrap;

}

.mc-team-name.home { color: #34d399; }

.mc-team-name.away { color: #f87171; }

.mc-odds-line {

  font-size: 10px;

  color: #9ca3af;

  display: flex;

  align-items: center;

  gap: 2px;

  max-width: 100%;

  min-width: 0;

  overflow: hidden;

  white-space: nowrap;

}

.mc-odds-label {

  font-size: 9px;

  color: #f59e0b;

  background: rgba(245, 158, 11, 0.12);

  padding: 0px 3px;

  border-radius: 2px;

  margin-right: 2px;

}

.mc-odds-val { font-size: 10px; }

.mc-odds-sep { color: #4b5563; margin: 0 1px; }

.mc-score-col {

  display: flex;

  flex-direction: column;

  align-items: center;

  min-width: 48px;

}

.mc-score {

  font-size: 20px;

  font-weight: 800;

  color: white;

  letter-spacing: 2px;

}

.mc-ft-tag {

  font-size: 9px;

  color: #10b981;

  background: rgba(16, 185, 129, 0.1);

  padding: 0 4px;

  border-radius: 2px;

}

.mc-hcp {

  font-size: 13px;

  font-weight: 700;

  color: #f59e0b;

  background: rgba(245, 158, 11, 0.12);

  padding: 2px 8px;

  border-radius: 4px;

}

.mc-hcp-badge {

  font-size: 10px;

  font-weight: 700;

  color: #f59e0b;

  background: rgba(245, 158, 11, 0.15);

  padding: 1px 5px;

  border-radius: 3px;

  margin-right: 4px;

  flex-shrink: 0;

}

.mc-ht-score {

  font-size: 10px;

  color: #9ca3af;

  letter-spacing: 1px;

  margin-top: 1px;

}

.mc-vs {

  font-size: 13px;

  font-weight: 700;

  color: #4b5563;

}



.mc-pred-grid {

  display: flex;

  flex-direction: column;

  gap: 3px;

  margin: 8px 0 4px;

  padding: 8px;

  background: rgba(255, 255, 255, 0.02);

  border-radius: 6px;

}

.mc-pred-row {

  display: grid;

  grid-template-columns: 86px minmax(0, 1fr) 18px minmax(0, 1fr);

  align-items: center;

  gap: 3px;

  font-size: 12px;

  min-height: 22px;

}

.mc-pred-type {

  color: #6b7280;

  font-size: 11px;

  white-space: nowrap;

  overflow: hidden;

  text-overflow: ellipsis;

}

.mc-pred-val {

  min-width: 0;

  overflow: hidden;

  text-overflow: ellipsis;

  white-space: nowrap;

}

.mc-pred-val.blue {

  font-weight: 600;

  color: #60a5fa;

  padding: 1px 6px;

  background: rgba(59, 130, 246, 0.10);

  border-radius: 3px;

  border: 1px solid rgba(59, 130, 246, 0.20);

}

.mc-pred-arrow {

  color: #4b5563;

  font-size: 11px;

}

.mc-pred-val.tag {

  font-weight: 700;

  padding: 1px 6px;

  border-radius: 3px;

  border: 1px solid;

}

.mc-pred-val.tag.ok {

  color: #10b981;

  background: rgba(16, 185, 129, 0.10);

  border-color: rgba(16, 185, 129, 0.25);

}

.mc-pred-val.tag.no {

  color: #ef4444;

  background: rgba(239, 68, 68, 0.10);

  border-color: rgba(239, 68, 68, 0.25);

}

.mc-pred-conf {

  font-size: 9px;

  padding: 1px 4px;

  border-radius: 3px;

  font-weight: 500;

}

.mc-pred-conf.high, .mc-pred-conf.strong { background: rgba(16, 185, 129, 0.15); color: #10b981; }

.mc-pred-conf.medium { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }

.mc-pred-conf.low { background: rgba(239, 68, 68, 0.15); color: #ef4444; }

.mc-pred-conf.avoid { background: rgba(107, 114, 128, 0.15); color: #6b7280; font-style: italic; }

.mc-pred-spacer { }







.no-analysis {

  display: flex;

  justify-content: center;

}



.analyze-btn {

  display: flex;

  align-items: center;

  gap: 6px;

  padding: 8px 16px;

  background: rgba(16, 185, 129, 0.1);

  border: 1px solid #10b981;

  border-radius: 6px;

  font-size: 13px;

  color: #10b981;

  cursor: pointer;

}



.analyze-btn:hover {

  background: rgba(16, 185, 129, 0.2);

}

.mc-intel-strip {

  display: flex;

  justify-content: space-between;

  align-items: center;

  gap: 8px;

  margin: 8px 0 6px;

  padding: 6px 8px;

  border-radius: 6px;

  border: 1px solid rgba(255,255,255,0.06);

  background: rgba(255,255,255,0.025);

}

.mc-intel-main {

  font-size: 11px;

  font-weight: 700;

  color: #cbd5e1;

  white-space: nowrap;

}

.mc-intel-sub {

  font-size: 10px;

  color: #94a3b8;

  overflow: hidden;

  text-overflow: ellipsis;

  white-space: nowrap;

}

.mc-intel-strip.ready { border-color: rgba(16,185,129,0.22); background: rgba(16,185,129,0.06); }
.mc-intel-strip.ready .mc-intel-main { color: #10b981; }
.mc-intel-strip.partial { border-color: rgba(245,158,11,0.24); background: rgba(245,158,11,0.06); }
.mc-intel-strip.partial .mc-intel-main { color: #f59e0b; }
.mc-intel-strip.risk, .mc-intel-strip.missing { border-color: rgba(239,68,68,0.22); background: rgba(239,68,68,0.05); }
.mc-intel-strip.risk .mc-intel-main, .mc-intel-strip.missing .mc-intel-main { color: #ef4444; }

.mc-source-health {
  display: flex;
  gap: 4px;
  padding: 0 8px 4px;
  flex-wrap: wrap;
}
.mc-sh-dot {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 500;
}
.mc-sh-dot.healthy { background: rgba(16,185,129,0.12); color: #10b981; }
.mc-sh-dot.degraded { background: rgba(245,158,11,0.12); color: #f59e0b; }
.mc-sh-dot.error { background: rgba(239,68,68,0.12); color: #ef4444; }
.mc-sh-dot.unknown { background: rgba(107,114,128,0.12); color: #6b7280; }



.play-types-row {

  display: flex;

  justify-content: center;

  gap: 6px;

  margin-bottom: 8px;

}



.play-badge {

  font-size: 11px;

  padding: 2px 8px;

  background: rgba(255,255,255,0.05);

  border-radius: 4px;

  color: #6b7280;

}



.play-badge.active {

  color: #10b981;

  background: rgba(16, 185, 129, 0.1);

}



.sell-status {

  display: flex;

  justify-content: center;

  align-items: center;

  flex-wrap: wrap;

  gap: 6px;

}

.match-card .mc-intel-strip,
.match-card .source-badge,
.match-card .quality-badge,
.match-card .result-refresh-btn,
.match-card .result-correct-btn {
  display: none;
}

.match-card .sell-status {
  margin-top: 8px;
}



.status-badge {

  font-size: 11px;

  padding: 4px 12px;

  border-radius: 4px;

}



.status-badge.selling { background: rgba(16, 185, 129, 0.1); color: #10b981; }

.status-badge.stopped { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }

.status-badge.closed { background: rgba(107, 114, 128, 0.1); color: #6b7280; }

.status-badge.started { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }

.status-badge.finished { background: rgba(16, 185, 129, 0.15); color: #10b981; }

.status-badge.scheduled { background: rgba(148, 163, 184, 0.12); color: #94a3b8; }

.status-badge.finished_pending { background: rgba(245, 158, 11, 0.14); color: #f59e0b; }

.source-badge {

  font-size: 10px;

  padding: 3px 8px;

  border-radius: 4px;

  border: 1px solid rgba(148, 163, 184, 0.22);

  color: #94a3b8;

  background: rgba(148, 163, 184, 0.08);

}

.source-badge.oddsfe {

  border-color: rgba(59, 130, 246, 0.24);

  color: #60a5fa;

  background: rgba(59, 130, 246, 0.10);

}

.source-badge.quality-badge {
  padding: 2px 6px;
}

.source-badge.quality-badge.ready {
  border-color: rgba(16, 185, 129, 0.22);
  color: #34d399;
  background: rgba(16, 185, 129, 0.08);
}

.source-badge.quality-badge.partial {
  border-color: rgba(245, 158, 11, 0.22);
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.08);
}

.source-badge.quality-badge.missing {
  border-color: rgba(239, 68, 68, 0.22);
  color: #f87171;
  background: rgba(239, 68, 68, 0.08);
}

.result-correct-btn {
  border: 1px solid rgba(96, 165, 250, 0.32);
  background: rgba(96, 165, 250, 0.10);
  color: #bfdbfe;
  border-radius: 5px;
  padding: 3px 8px;
  font-size: 10px;
  cursor: pointer;
}

.result-correct-btn:hover {
  background: rgba(96, 165, 250, 0.18);
  color: #e0f2fe;
}

.result-refresh-btn {
  border: 1px solid rgba(16, 185, 129, 0.30);
  background: rgba(16, 185, 129, 0.10);
  color: #a7f3d0;
  border-radius: 5px;
  padding: 3px 8px;
  font-size: 10px;
  cursor: pointer;
}

.result-refresh-btn:hover {
  background: rgba(16, 185, 129, 0.18);
  color: #d1fae5;
}

.result-refresh-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}







/* 弹窗 */

.modal-overlay {

  position: fixed;

  inset: 0;

  background: rgba(0, 0, 0, 0.7);

  display: flex;

  align-items: center;

  justify-content: center;

  z-index: 200;

}



.modal-content {

  width: 92%;

  max-width: 800px;

  max-height: 88vh;

  background: #0f141e;

  border-radius: 12px;

  border: 1px solid rgba(255,255,255,0.08);

  display: flex;

  flex-direction: column;

  box-shadow: 0 0 40px rgba(0,0,0,0.5);

}



.modal-header {

  display: flex;

  justify-content: space-between;

  align-items: center;

  padding: 12px 16px;

  border-bottom: 1px solid rgba(255,255,255,0.06);

}



.modal-header h2 {

  font-size: 16px;

  font-weight: 500;

  color: #e2e8f0;

}



.close-btn {

  width: 32px;

  height: 32px;

  display: flex;

  align-items: center;

  justify-content: center;

  background: transparent;

  border: none;

  color: #9ca3af;

  cursor: pointer;

  border-radius: 6px;

}



.close-btn:hover {

  background: rgba(255,255,255,0.05);

  color: white;

}



.modal-body {

  flex: 1;

  padding: 16px;

  overflow-y: auto;

}



/* 分析详情 */

.analysis-detail {

  display: flex;

  flex-direction: column;

  gap: 16px;

}



.detail-header {

  display: flex;

  justify-content: space-between;

  align-items: center;

  padding: 12px;

  background: rgba(255,255,255,0.05);

  border-radius: 8px;

}



.league {

  font-size: 14px;

  color: #6b7280;

}



.teams {

  font-size: 16px;

  font-weight: 600;

  color: white;

}



.analysis-section {

  padding: 16px;

  background: rgba(255,255,255,0.03);

  border-radius: 8px;

  border: 1px solid rgba(55, 65, 81, 0.5);

}



.analysis-section h3 {

  font-size: 14px;

  font-weight: 600;

  color: #9ca3af;

  margin-bottom: 12px;

}



.prob-bars {

  display: flex;

  flex-direction: column;

  gap: 8px;

}



.prob-bar {

  display: flex;

  align-items: center;

  gap: 8px;

}



.prob-bar .bar-fill {

  height: 20px;

  border-radius: 4px;

  transition: width 0.3s;

}



.prob-bar.home .bar-fill { background: linear-gradient(90deg, #10b981, #059669); }

.prob-bar.draw .bar-fill { background: linear-gradient(90deg, #f59e0b, #d97706); }

.prob-bar.away .bar-fill { background: linear-gradient(90deg, #ef4444, #dc2626); }



.prob-bar .label {

  font-size: 13px;

  font-weight: 600;

  color: white;

  min-width: 80px;

}



.recommendation {

  display: flex;

  align-items: center;

  gap: 8px;

  margin-top: 12px;

  padding-top: 12px;

  border-top: 1px solid rgba(55, 65, 81, 0.5);

}



.rec-label {

  font-size: 13px;

  color: #6b7280;

}



.rec-value {

  font-size: 15px;

  font-weight: 700;

  color: #10b981;

}



.rec-conf {

  margin-left: auto;

  font-size: 12px;

  color: #3b82f6;

  background: rgba(59, 130, 246, 0.1);

  padding: 4px 8px;

  border-radius: 4px;

}



/* 分析因素列表 */

.factors-section {

  padding: 16px;

  background: rgba(255,255,255,0.03);

  border-radius: 8px;

  border: 1px solid rgba(55, 65, 81, 0.5);

}



.factors-section h3 {

  font-size: 14px;

  font-weight: 600;

  color: #9ca3af;

  margin-bottom: 12px;

}



.factors-list {

  display: grid;

  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));

  gap: 8px;

  max-height: 300px;

  overflow-y: auto;

}



.factor-item {

  display: flex;

  flex-direction: column;

  padding: 8px 12px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

  border: 1px solid rgba(55, 65, 81, 0.3);

}



.factor-name {

  font-size: 12px;

  font-weight: 600;

  color: #10b981;

  margin-bottom: 4px;

}



.factor-desc {

  font-size: 11px;

  color: #9ca3af;

  flex: 1;

}



.factor-conf {

  font-size: 10px;

  color: #6b7280;

  text-align: right;

  margin-top: 4px;

}



.summary-section {

  padding: 16px;

  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(59, 130, 246, 0.1));

  border-radius: 8px;

  border: 1px solid rgba(16, 185, 129, 0.3);

}



.summary-section h3 {

  font-size: 14px;

  font-weight: 600;

  color: #9ca3af;

  margin-bottom: 8px;

}



.main-rec {

  font-size: 18px;

  font-weight: 700;

  color: #10b981;

  margin-bottom: 4px;

}



.confidence {

  font-size: 13px;

  color: #6b7280;

}



/* 详细战绩展示 */

.detailed-section {

  padding: 16px;

  background: rgba(255,255,255,0.03);

  border-radius: 8px;

  border: 1px solid rgba(55, 65, 81, 0.5);

}



.detailed-section h3 {

  font-size: 14px;

  font-weight: 600;

  color: #9ca3af;

  margin-bottom: 12px;

}



.team-stats-row {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 16px;

}



.team-stats-col {

  padding: 12px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

}



.recent-section {

  margin-bottom: 12px;

}



.recent-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #10b981;

  margin-bottom: 8px;

}



.form-summary {

  display: flex;

  gap: 8px;

  font-size: 11px;

  color: #6b7280;

}



.form-string {

  font-size: 11px;

  font-weight: 600;

  margin-top: 6px;

}



.form-string span {

  padding: 2px 4px;

  border-radius: 2px;

}



.matches-mini-list {

  display: flex;

  flex-wrap: wrap;

  gap: 4px;

  margin-top: 6px;

}



.match-result {

  font-size: 10px;

  padding: 2px 6px;

  border-radius: 3px;

  background: rgba(255,255,255,0.05);

}



.match-result.胜 { color: #10b981; background: rgba(16, 185, 129, 0.1); }

.match-result.平 { color: #f59e0b; background: rgba(245, 158, 11, 0.1); }

.match-result.负 { color: #ef4444; background: rgba(239, 68, 68, 0.1); }



.points {

  color: #10b981;

  font-weight: 600;

}



/* 历史交锋 */

.h2h-section {

  margin-top: 16px;

}



.h2h-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #f59e0b;

  margin-bottom: 8px;

}



.h2h-summary {

  display: flex;

  gap: 12px;

  margin-bottom: 8px;

}



.h2h-stat {

  font-size: 11px;

  color: #6b7280;

}



.h2h-matches {

  display: flex;

  flex-direction: column;

  gap: 6px;

}



.h2h-match {

  display: flex;

  justify-content: space-between;

  align-items: center;

  padding: 6px 8px;

  background: rgba(255,255,255,0.02);

  border-radius: 4px;

  font-size: 11px;

}



.h2h-date {

  color: #6b7280;

  font-size: 10px;

}



.h2h-score {

  color: white;

}



.h2h-result {

  padding: 2px 6px;

  border-radius: 3px;

  font-size: 10px;

  font-weight: 600;

}



.h2h-result.主胜 { color: #10b981; background: rgba(16, 185, 129, 0.1); }

.h2h-result.平局 { color: #f59e0b; background: rgba(245, 158, 11, 0.1); }

.h2h-result.客胜 { color: #ef4444; background: rgba(239, 68, 68, 0.1); }



.no-data {

  color: #6b7280;

  font-size: 11px;

}



/* Elo对比 */

.elo-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #3b82f6;

  margin-bottom: 8px;

}



.elo-bars {

  display: flex;

  flex-direction: column;

  gap: 6px;

}



.elo-bar {

  display: flex;

  align-items: center;

  gap: 8px;

}



.elo-label {

  font-size: 11px;

  color: #6b7280;

  min-width: 80px;

}



.elo-fill {

  height: 8px;

  border-radius: 4px;

  background: linear-gradient(90deg, #10b981, #3b82f6);

}



.elo-desc {

  margin-top: 8px;

  font-size: 11px;

  color: #9ca3af;

}



/* 分析总结 */

.analysis-summary-box {

  margin-top: 12px;

  padding: 10px;

  background: rgba(16, 185, 129, 0.05);

  border-radius: 6px;

  border-left: 3px solid #10b981;

}



.analysis-summary-box h4 {

  font-size: 12px;

  color: #10b981;

  margin-bottom: 6px;

}



.summary-text {

  font-size: 11px;

  color: #9ca3af;

  line-height: 1.5;

}



/* 比分预测 */

.score-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #f59e0b;

  margin-bottom: 8px;

}



.score-list {

  display: flex;

  flex-direction: column;

  gap: 6px;

}



.score-item {

  display: flex;

  justify-content: space-between;

  align-items: center;

  padding: 6px 10px;

  background: rgba(255,255,255,0.02);

  border-radius: 4px;

}



.score-rank {

  font-size: 11px;

  color: #6b7280;

}



.score-value {

  font-size: 14px;

  font-weight: 600;

  color: #10b981;

}



.score-prob {

  font-size: 11px;

  color: #3b82f6;

}



.score-info {

  display: flex;

  gap: 12px;

  margin-top: 8px;

  font-size: 11px;

  color: #6b7280;

}



.score-rec {

  margin-top: 8px;

  font-size: 12px;

  color: #9ca3af;

}



/* 大小球预测 */

.ou-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #8b5cf6;

  margin-bottom: 8px;

}



.ou-bars {

  display: flex;

  flex-direction: column;

  gap: 6px;

}



.ou-bar {

  display: flex;

  align-items: center;

  gap: 8px;

}



.ou-bar .bar-fill {

  height: 20px;

  border-radius: 4px;

}



.ou-bar.over .bar-fill { background: linear-gradient(90deg, #10b981, #059669); }

.ou-bar.under .bar-fill { background: linear-gradient(90deg, #ef4444, #dc2626); }



.expected-goals {

  margin-top: 8px;

  font-size: 12px;

  color: #f59e0b;

  font-weight: 600;

}



.goals-dist {

  margin-top: 6px;

  display: flex;

  flex-wrap: wrap;

  gap: 6px;

}



.goals-dist-label {

  font-size: 11px;

  color: #6b7280;

}



.goals-dist-item {

  font-size: 10px;

  padding: 2px 6px;

  background: rgba(255,255,255,0.05);

  border-radius: 3px;

  color: #9ca3af;

}



.ou-rec {

  margin-top: 8px;

  font-size: 12px;

  color: #10b981;

  font-weight: 600;

}



/* 联赛积分排名 */

.league-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #3b82f6;

  margin-bottom: 8px;

}



.standing-row {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 12px;

}



.standing-card {

  padding: 10px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

}



.standing-header {

  display: flex;

  justify-content: space-between;

  margin-bottom: 6px;

}



.standing-header .team-name {

  font-size: 12px;

  color: #9ca3af;

}



.standing-header .position {

  font-size: 13px;

  font-weight: 600;

  color: #10b981;

}



.standing-stats {

  display: flex;

  gap: 12px;

  font-size: 11px;

  color: #6b7280;

}



.standing-goals {

  display: flex;

  gap: 12px;

  margin-top: 4px;

  font-size: 11px;

}



.goal-diff {

  color: #f59e0b;

}



.goal-diff.positive {

  color: #10b981;

}



.home-away-record {

  margin-top: 6px;

  display: flex;

  gap: 8px;

  font-size: 10px;

  color: #6b7280;

}



/* 体能状况 */

.fitness-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #ef4444;

  margin-bottom: 8px;

}



.fitness-row {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 12px;

}



.fitness-card {

  padding: 10px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

}



.fitness-card .team-name {

  font-size: 12px;

  color: #9ca3af;

  margin-bottom: 6px;

}



.fitness-stats {

  display: flex;

  gap: 8px;

  font-size: 11px;

  color: #6b7280;

}



.fatigue-level {

  margin-top: 6px;

  padding: 4px 8px;

  border-radius: 4px;

  font-size: 11px;

}



.fatigue-level.fatigue-high {

  background: rgba(239, 68, 68, 0.2);

  color: #ef4444;

}



.fatigue-level.fatigue-medium {

  background: rgba(245, 158, 11, 0.2);

  color: #f59e0b;

}



.fatigue-level.fatigue-low {

  background: rgba(16, 185, 129, 0.2);

  color: #10b981;

}



.rest-desc {

  margin-top: 4px;

  font-size: 10px;

  color: #6b7280;

}



/* 进球时间分布 */

.goal-timing-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #8b5cf6;

  margin-bottom: 8px;

}



.timing-row {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 12px;

}



.timing-team {

  padding: 10px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

}



.timing-team .team-label {

  font-size: 12px;

  color: #9ca3af;

  margin-bottom: 8px;

  display: block;

}



.timing-bars {

  display: flex;

  flex-direction: column;

  gap: 4px;

}



.timing-slot {

  display: flex;

  align-items: center;

  gap: 6px;

}



.slot-label {

  font-size: 10px;

  color: #6b7280;

  min-width: 40px;

}



.slot-bar {

  flex: 1;

  height: 8px;

  background: rgba(255,255,255,0.1);

  border-radius: 4px;

  overflow: hidden;

}



.slot-fill {

  height: 100%;

  background: linear-gradient(90deg, #8b5cf6, #a855f7);

  border-radius: 4px;

}



.slot-count {

  font-size: 10px;

  color: #8b5cf6;

  min-width: 20px;

  text-align: right;

}



/* 球员进球详情 */

.scorers-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #f59e0b;

  margin-bottom: 8px;

}



.scorers-row {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 12px;

}



.scorers-team {

  padding: 10px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

}



.scorers-team .team-label {

  font-size: 12px;

  color: #9ca3af;

  margin-bottom: 8px;

  display: block;

}



.scorers-list {

  display: flex;

  flex-direction: column;

  gap: 6px;

}



.scorer-item {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 6px 8px;

  background: rgba(255,255,255,0.03);

  border-radius: 4px;

}



.scorer-name {

  font-size: 11px;

  color: white;

  flex: 1;

}



.scorer-goals {

  font-size: 11px;

  color: #10b981;

  font-weight: 600;

}



.scorer-matches {

  font-size: 10px;

  color: #6b7280;

}



.scorer-avg {

  font-size: 10px;

  color: #f59e0b;

}



/* 天气因素 */

.weather-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #06b6d4;

  margin-bottom: 8px;

}



.weather-info {

  display: flex;

  gap: 16px;

  margin-bottom: 8px;

}



.weather-item {

  display: flex;

  align-items: center;

  gap: 6px;

}



.weather-label {

  font-size: 11px;

  color: #6b7280;

}



.weather-value {

  font-size: 12px;

  color: white;

  font-weight: 600;

}



.weather-factors {

  display: flex;

  flex-wrap: wrap;

  gap: 6px;

  margin-bottom: 8px;

}



.weather-factor {

  font-size: 10px;

  padding: 2px 8px;

  background: rgba(6, 182, 212, 0.1);

  color: #06b6d4;

  border-radius: 4px;

}



.weather-impact {

  font-size: 11px;

  color: #9ca3af;

}



/* 价值投注 */

.value-bets-section h4 {

  font-size: 12px;

  font-weight: 600;

  color: #f59e0b;

  margin-bottom: 8px;

}



.value-bets-desc {

  font-size: 11px;

  color: #6b7280;

  margin-bottom: 12px;

}



.value-bets-list {

  display: flex;

  flex-direction: column;

  gap: 8px;

}



.value-bet-item {

  padding: 10px;

  background: rgba(245, 158, 11, 0.05);

  border: 1px solid rgba(245, 158, 11, 0.2);

  border-radius: 6px;

}



.value-bet-header {

  display: flex;

  justify-content: space-between;

  margin-bottom: 6px;

}



.value-bet-label {

  font-size: 13px;

  font-weight: 600;

  color: white;

}



.value-rating {

  font-size: 10px;

  padding: 2px 6px;

  border-radius: 4px;

}



.value-rating.high {

  background: rgba(16, 185, 129, 0.2);

  color: #10b981;

}



.value-rating.medium {

  background: rgba(245, 158, 11, 0.2);

  color: #f59e0b;

}



.value-bet-details {

  display: flex;

  gap: 12px;

  font-size: 11px;

  color: #6b7280;

}



.value-bet-edge {

  margin-top: 6px;

}



.edge-positive {

  font-size: 12px;

  font-weight: 600;

  color: #10b981;

}



.no-value-bets {

  font-size: 11px;

  color: #6b7280;

  text-align: center;

  padding: 12px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

}



.loading-state {

  display: flex;

  flex-direction: column;

  align-items: center;

  justify-content: center;

  padding: 40px;

  gap: 12px;

}



.spinner {

  width: 32px;

  height: 32px;

  border: 3px solid #374151;

  border-top-color: #10b981;

  border-radius: 50%;

  animation: spin 1s linear infinite;

}



@keyframes spin {

  to { transform: rotate(360deg); }

}



.no-report {

  text-align: center;

  color: #6b7280;

  padding: 40px;

}



.analysis-content {

  padding: 20px;

  text-align: center;

  color: #6b7280;

}



/* 采集区域 */

.sync-area {

  display: flex;

  align-items: center;

  flex-wrap: wrap;

  gap: 10px;

}

.result-correction-modal {
  width: min(92vw, 520px);
  max-height: 88vh;
  overflow: hidden;
  background: #0f141e;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  box-shadow: 0 0 40px rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
}

.result-correction-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  overflow-y: auto;
}

.result-correction-title {
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.5;
}

.result-score-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.result-score-grid label,
.result-reason-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.result-score-grid span,
.result-reason-field span {
  color: #94a3b8;
  font-size: 12px;
}

.result-score-grid input,
.result-reason-field textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: #111827;
  color: #e5e7eb;
  border-radius: 7px;
  padding: 9px 10px;
  outline: none;
}

.result-reason-field textarea {
  resize: vertical;
  min-height: 76px;
}

.result-correction-error {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.10);
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 7px;
  padding: 8px 10px;
  font-size: 12px;
}

.result-correction-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,0.06);
}

.primary-btn,
.secondary-btn {
  border-radius: 7px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}

.primary-btn {
  border: 1px solid rgba(16, 185, 129, 0.32);
  background: rgba(16, 185, 129, 0.16);
  color: #a7f3d0;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.secondary-btn {
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.08);
  color: #cbd5e1;
}



.sync-btn {

  display: flex;

  align-items: center;

  gap: 6px;

  padding: 8px 16px;

  background: rgba(16, 185, 129, 0.1);

  border: 1px solid #10b981;

  border-radius: 6px;

  font-size: 13px;

  color: #10b981;

  cursor: pointer;

  transition: all 0.2s;

  white-space: nowrap;

}



.sync-btn:hover { background: rgba(16, 185, 129, 0.2); }

.sync-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.result-sync-btn {
  background: rgba(34, 197, 94, 0.14);
  border-color: rgba(34, 197, 94, 0.34);
  color: #22c55e;
}

.result-sync-btn:hover { background: rgba(34, 197, 94, 0.24); }

.result-sync-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border: 1px solid rgba(34, 197, 94, 0.22);
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.44);
}

.result-sync-controls label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #a7f3d0;
}

.result-sync-controls select {
  height: 26px;
  min-width: 52px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 5px;
  background: #0f172a;
  color: #e5e7eb;
  font-size: 12px;
  outline: none;
}

.result-sync-controls select:disabled {
  opacity: 0.55;
}



.sync-result {

  display: flex;

  align-items: center;

  gap: 8px;

  font-size: 11px;

  color: #9ca3af;

}



.sync-ok {

  color: #10b981;

  font-weight: 600;

}

.sync-fail {

  color: #ef5350;

  font-weight: 600;

}



.sync-status {

  color: #f59e0b;

}



/* 赛事类型标签 */

.comp-type-badge {

  font-size: 10px;

  padding: 2px 6px;

  background: rgba(139, 92, 246, 0.15);

  color: #8b5cf6;

  border-radius: 3px;

  margin: 0 6px;

}



/* 赔率对比 */

.odds-comparison-grid {

  display: flex;

  flex-direction: column;

  gap: 6px;

}



.odds-comparison-row {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 6px 8px;

  background: rgba(255,255,255,0.02);

  border-radius: 4px;

  font-size: 12px;

}



.oc-label { color: #6b7280; min-width: 36px; }

.oc-model { color: #3b82f6; min-width: 80px; }

.oc-odds { color: #f59e0b; min-width: 80px; }

.oc-edge { color: #6b7280; min-width: 70px; }

.oc-edge.positive { color: #10b981; }



.mvo-info {

  display: flex;

  gap: 12px;

  margin-top: 8px;

  font-size: 11px;

  color: #9ca3af;

}



.agreement-yes { color: #10b981; font-weight: 600; }

.agreement-no { color: #ef4444; font-weight: 600; }



/* xG展示 */

.xg-row {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 12px;

}



.xg-card {

  padding: 10px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

  text-align: center;

}



.xg-team { font-size: 12px; color: #9ca3af; display: block; margin-bottom: 4px; }

.xg-value { font-size: 20px; font-weight: 700; }

.xg-value.home { color: #10b981; }

.xg-value.away { color: #ef4444; }



/* Elo基础 */

.elo-base-row {

  display: flex;

  gap: 16px;

  font-size: 12px;

  color: #9ca3af;

}



/* 动机分析 */

.motivation-row {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 12px;

  margin-bottom: 8px;

}



.motivation-card {

  padding: 10px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

}



.mot-team { font-size: 12px; color: #9ca3af; display: block; margin-bottom: 4px; }

.mot-level { font-size: 14px; font-weight: 600; color: #f59e0b; display: block; margin-bottom: 2px; }

.mot-desc { font-size: 11px; color: #6b7280; }

.mot-comparison { font-size: 12px; color: #9ca3af; }



/* 近期战绩 */

.form-section { margin-bottom: 10px; }

.form-section h4 { font-size: 12px; color: #10b981; margin-bottom: 6px; }



.form-row {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 12px;

}



.form-card {

  padding: 8px;

  background: rgba(255,255,255,0.02);

  border-radius: 6px;

}



.form-team { font-size: 12px; color: #9ca3af; display: block; margin-bottom: 4px; }

.form-string-val { font-size: 11px; font-weight: 600; color: white; display: block; margin-bottom: 2px; }

.form-summary-val { font-size: 11px; color: #6b7280; }



/* 半全场迷你 */

.bqc-grid-mini {

  display: grid;

  grid-template-columns: repeat(3, 1fr);

  gap: 6px;

}



.bqc-item-mini {

  display: flex;

  flex-direction: column;

  align-items: center;

  padding: 6px;

  background: rgba(255,255,255,0.03);

  border-radius: 4px;

}



.bqc-code-mini { font-size: 11px; font-weight: 600; color: #10b981; }

.bqc-display-mini { font-size: 9px; color: #6b7280; }

.bqc-prob-mini { font-size: 10px; color: #9ca3af; }



/* 权重 */

.weights-grid {

  display: flex;

  flex-direction: column;

  gap: 8px;

}



.weight-item {

  display: flex;

  align-items: center;

  gap: 8px;

}



.weight-name { font-size: 11px; color: #9ca3af; min-width: 80px; }

.weight-bar { flex: 1; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }

.weight-fill { height: 100%; background: linear-gradient(90deg, #10b981, #3b82f6); border-radius: 4px; }

.weight-val { font-size: 11px; color: white; min-width: 36px; text-align: right; }



/* 调整项 */

.adj-list {

  display: flex;

  flex-direction: column;

  gap: 6px;

}



.adj-item {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 8px;

  background: rgba(255,255,255,0.02);

  border-radius: 4px;

}



.adj-type { font-size: 11px; font-weight: 600; color: #f59e0b; min-width: 80px; }

.adj-desc { font-size: 11px; color: #9ca3af; flex: 1; }

.adj-delta { font-size: 11px; font-weight: 600; }

.adj-delta.up { color: #10b981; }

.adj-delta.down { color: #ef4444; }



/* MVO总结 */

.mvo-summary { font-size: 12px; color: #9ca3af; margin-top: 4px; }



/* 响应式 */

@media (max-width: 900px) {

  .stats-cards {

    grid-template-columns: repeat(2, 1fr);

  }



  .filter-bar {

    flex-direction: column;

    gap: 12px;

  }

}



@media (max-width: 600px) {

  .stats-cards {

    grid-template-columns: repeat(2, 1fr);

  }

  .lottery-center,
  .accuracy-panel,
  .filter-bar,
  .matches-section,
  .data-health-strip,
  .matches-grid,
  .match-card {
    width: 100%;
    max-width: 100%;
    min-width: 0;
  }

  .lottery-center {
    overflow-x: hidden;
    gap: 12px;
  }

  .accuracy-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .accuracy-item {
    min-width: 0;
  }

  .filter-bar {
    padding: 10px;
    align-items: stretch;
  }

  .date-picker {
    justify-content: center;
  }

  .action-buttons {
    display: flex;
    overflow-x: auto;
    gap: 8px;
    padding-bottom: 2px;
    scrollbar-width: none;
  }

  .action-buttons::-webkit-scrollbar {
    display: none;
  }

  .sync-btn {
    flex: 0 0 auto;
    white-space: nowrap;
  }

  .data-health-strip {
    align-items: stretch;
  }

  .data-health-metrics {
    flex: 1;
    min-width: 0;
    gap: 6px;
  }

  .data-health-metrics span {
    font-size: 11px;
    padding: 2px 6px;
  }



  .matches-grid {

    grid-template-columns: 1fr;

    gap: 10px;

  }

  .match-card {
    padding: 12px 10px;
    border-radius: 10px;
  }

  .mc-header {
    gap: 6px;
    margin-bottom: 8px;
  }

  .mc-time,
  .mc-league,
  .mc-num {
    font-size: 10px;
  }

  .mc-teams {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 6px;
    align-items: center;
    margin-bottom: 8px;
  }

  .mc-team-col {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 5px;
    align-items: center;
    width: 100%;
    text-align: left;
  }

  .mc-team-col.away {
    direction: ltr;
  }

  .mc-team-name {
    font-size: 13px;
  }

  .mc-score-col {
    min-width: 0;
    order: 2;
    padding: 4px 0;
    border-top: 1px solid rgba(148, 163, 184, 0.08);
    border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  }

  .mc-team-col:first-child {
    order: 1;
  }

  .mc-team-col.away {
    order: 3;
  }

  .mc-team-col.away .mc-team-name {
    color: #f87171;
  }

  .mc-score {
    font-size: 18px;
    letter-spacing: 1px;
  }

  .mc-ht-score,
  .mc-odds-line {
    font-size: 9px;
  }

  .mc-team-col .mc-odds-line {
    grid-column: 1 / -1;
    justify-self: start;
    max-width: 100%;
  }

  .mc-pred-grid {
    padding: 7px;
    margin-top: 6px;
  }

  .mc-pred-row {
    grid-template-columns: 74px minmax(0, 1fr) minmax(0, 1fr);
    gap: 2px;
    font-size: 11px;
    min-height: 21px;
  }

  .mc-pred-row .mc-pred-arrow,
  .mc-pred-row .mc-pred-spacer {
    display: none;
  }

  .mc-pred-row .mc-pred-val.tag {
    justify-self: stretch;
    margin-left: 4px;
  }

  .mc-pred-row .mc-pred-conf {
    display: none;
  }

  .mc-pred-type {
    font-size: 10px;
  }

  .mc-pred-val.blue,
  .mc-pred-val.tag {
    padding: 1px 4px;
  }



  .modal-overlay {

    align-items: flex-start;

  }



  .modal-content {

    width: 100%;

    max-width: 100%;

    max-height: 100vh;

    border-radius: 0;

    height: 100vh;
    height: 100dvh;

  }

  .result-correction-modal {
    width: 100%;
    max-width: 100%;
    max-height: 100vh;
    height: 100vh;
    height: 100dvh;
    border-radius: 0;
  }

  .result-score-grid {
    grid-template-columns: 1fr;
  }

  .result-correction-actions {
    justify-content: stretch;
  }

  .result-correction-actions button {
    flex: 1;
  }



  .modal-header {

    padding: 12px 16px;

  }



  .modal-body {

    padding: 8px;
    -webkit-overflow-scrolling: touch;

  }



  .stat-card {

    padding: 10px;

  }



  .stat-value {

    font-size: 18px;

  }

}



</style>

<style>
/* ===== Analysis Detail — E-sports Dashboard Style ===== */
.analysis-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 0;
}

.ad-loading, .ad-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 40px; gap: 12px; color: #64748b;
}

/* ---- Section base ---- */
.ad-sec {
  padding: 16px;
  background: #171d2c;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.08);
}
.ad-sec-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 14px; font-weight: 600; color: #94a3b8;
  margin-bottom: 14px;
}
.ad-sec-icon { font-size: 10px; }
.ad-sec-icon.green { color: #10b981; }
.ad-sec-icon.blue { color: #3b82f6; }
.ad-sec-icon.purple { color: #8b5cf6; }
.ad-sec-icon.orange { color: #f59e0b; }

/* ---- Data status layer ---- */
.ad-data-status.ready { border-color: rgba(16,185,129,0.18); }
.ad-data-status.warn { border-color: rgba(245,158,11,0.24); }
.ad-data-summary {
  margin-left: auto;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}
.ad-data-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.ad-data-item {
  min-width: 0;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 3px 8px;
  padding: 9px 10px;
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
}
.ad-data-item span {
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 700;
}
.ad-data-item b {
  color: #34d399;
  font-size: 11px;
}
.ad-data-item small {
  grid-column: 1 / -1;
  color: #64748b;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ad-data-item.missing {
  border-color: rgba(245,158,11,0.18);
  background: rgba(245,158,11,0.05);
}
.ad-data-item.missing b { color: #fbbf24; }
.ad-data-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.ad-data-sources em {
  font-style: normal;
  padding: 3px 7px;
  border-radius: 999px;
  color: #93c5fd;
  background: rgba(59,130,246,0.10);
  border: 1px solid rgba(59,130,246,0.16);
  font-size: 10px;
  font-weight: 700;
}

/* ---- Evidence layer ---- */
.ad-evidence.ready { border-color: rgba(16,185,129,0.22); }
.ad-evidence.partial { border-color: rgba(245,158,11,0.24); }
.ad-evidence.risk { border-color: rgba(239,68,68,0.22); }
.ad-ev-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}
.ad-ev-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 8px;
}
.ad-ev-metric span { font-size: 11px; color: #64748b; }
.ad-ev-metric b { font-size: 18px; color: #e2e8f0; }
.ad-ev-empty { font-size: 12px; color: #94a3b8; line-height: 1.6; }
.ad-ev-line, .ad-ev-actions {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px 10px;
  border-radius: 7px;
  font-size: 12px;
  color: #cbd5e1;
  background: rgba(255,255,255,0.025);
  margin-bottom: 8px;
}
.ad-ev-line.warn { background: rgba(239,68,68,0.08); color: #fecaca; }
.ad-ev-line.fallback { background: rgba(245,158,11,0.08); color: #fde68a; }
.ad-ev-label { min-width: 68px; font-weight: 700; color: #94a3b8; }
.ad-ev-artifacts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 8px; }
.ad-ev-artifact {
  display: grid;
  grid-template-columns: 72px 1fr 42px;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  background: #1a2133;
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 7px;
  font-size: 11px;
}
.ad-ev-artifact-key { color: #e2e8f0; font-weight: 600; }
.ad-ev-artifact-src { color: #64748b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ad-ev-artifact-conf { color: #10b981; text-align: right; }
.ad-ev-artifact-tier { font-size: 9px; padding: 1px 4px; border-radius: 3px; background: rgba(59,130,246,0.12); color: #93c5fd; }
.ad-ev-action-list { display: flex; flex-direction: column; gap: 3px; flex: 1; }
.ad-ev-action-item { display: flex; align-items: center; gap: 6px; font-size: 11px; }
.ad-ev-action-key { color: #e2e8f0; min-width: 56px; font-weight: 600; }
.ad-ev-action-src { color: #94a3b8; }
.ad-ev-action-health { font-weight: 700; font-size: 11px; }
.ad-ev-action-health.healthy { color: #10b981; }
.ad-ev-action-health.degraded { color: #f59e0b; }
.ad-ev-action-health.error { color: #ef4444; }
.ad-ev-action-health.unknown { color: #64748b; }

/* ---- Intelligence factor cards ---- */
.ad-intel-factors {
  border-color: rgba(34,197,94,0.18);
}
.ad-intel-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.ad-intel-card {
  min-width: 0;
  padding: 10px 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-left: 3px solid #22c55e;
  border-radius: 8px;
}
.ad-intel-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
}
.ad-intel-title {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 700;
}
.ad-intel-conf {
  flex-shrink: 0;
  font-size: 10px;
  color: #64748b;
}
.ad-intel-card b {
  display: block;
  font-size: 14px;
  line-height: 1.3;
  margin-bottom: 5px;
  overflow-wrap: anywhere;
}
.ad-intel-card p {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  color: #cbd5e1;
  overflow-wrap: anywhere;
}
.ad-intel-adjust-card {
  min-width: 0;
  padding: 10px 12px;
  background: rgba(34,197,94,0.08);
  border: 1px solid rgba(34,197,94,0.18);
  border-left: 3px solid #22c55e;
  border-radius: 8px;
}
.ad-intel-adjust-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 11px;
  color: #bbf7d0;
  font-weight: 800;
}
.ad-intel-adjust-head b {
  color: #22c55e;
  font-size: 12px;
}
.ad-intel-deltas {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  margin-bottom: 7px;
}
.ad-intel-delta {
  min-width: 0;
  padding: 6px 5px;
  border-radius: 6px;
  background: rgba(15,23,42,0.48);
  text-align: center;
}
.ad-intel-delta span {
  display: block;
  font-size: 10px;
  color: #94a3b8;
  margin-bottom: 2px;
}
.ad-intel-delta b {
  font-size: 12px;
  line-height: 1.2;
}
.ad-intel-delta.pos b { color: #22c55e; }
.ad-intel-delta.neg b { color: #f97316; }
.ad-intel-delta.flat b { color: #94a3b8; }
.ad-intel-adjust-card p {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  color: #d1fae5;
  overflow-wrap: anywhere;
}

/* ---- World Cup context ---- */
.ad-wc-context {
  border-color: rgba(245,158,11,0.22);
}
.ad-wc-label {
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.ad-wc-source {
  flex: 0 0 auto;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(245,158,11,0.10);
  border: 1px solid rgba(245,158,11,0.18);
  color: #fbbf24;
  font-size: 10px;
  font-weight: 700;
}
.ad-wc-top {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.ad-wc-pill {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding: 9px 10px;
  background: rgba(245,158,11,0.07);
  border: 1px solid rgba(245,158,11,0.16);
  border-radius: 8px;
}
.ad-wc-pill span {
  font-size: 10px;
  color: #fbbf24;
}
.ad-wc-pill b {
  font-size: 15px;
  color: #f8fafc;
  overflow-wrap: anywhere;
}
.ad-wc-teams {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.ad-wc-team {
  min-width: 0;
  padding: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
}
.ad-wc-team-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 7px;
}
.ad-wc-team-name {
  min-width: 0;
  font-size: 14px;
  font-weight: 800;
  color: #e2e8f0;
  overflow-wrap: anywhere;
}
.ad-wc-points {
  flex: 0 0 auto;
  color: #f8fafc;
  font-size: 18px;
  line-height: 1;
}
.ad-wc-team-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 8px;
}
.ad-wc-team-meta span {
  font-size: 10px;
  color: #94a3b8;
  padding: 2px 6px;
  background: rgba(255,255,255,0.04);
  border-radius: 5px;
}
.ad-wc-team-meta .ad-wc-qual {
  color: #fde68a;
  background: rgba(245,158,11,0.11);
}
.ad-wc-pressure {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.06);
  font-size: 11px;
  color: #64748b;
}
.ad-wc-pressure b { font-size: 12px; }
.ad-wc-pressure.very_high b,
.ad-wc-pressure.high b { color: #f87171; }
.ad-wc-pressure.medium b { color: #f59e0b; }
.ad-wc-pressure.low b { color: #10b981; }
.ad-wc-notes {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}
.ad-wc-note {
  font-size: 12px;
  line-height: 1.55;
  color: #cbd5e1;
  padding: 8px 10px;
  background: rgba(245,158,11,0.06);
  border: 1px solid rgba(245,158,11,0.12);
  border-radius: 8px;
  overflow-wrap: anywhere;
}
.ad-wc-sub {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.ad-wc-sub-title {
  font-size: 11px;
  font-weight: 700;
  color: #fbbf24;
  margin-bottom: 8px;
}
.ad-wc-fixtures,
.ad-wc-slots {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.ad-wc-path-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.ad-wc-fixture,
.ad-wc-slot {
  min-width: 0;
  padding: 8px 10px;
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 8px;
}
.ad-wc-fixture {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) 52px;
  gap: 8px;
  align-items: center;
  font-size: 11px;
  color: #94a3b8;
}
.ad-wc-fixture b {
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ad-wc-slot {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ad-wc-slot span {
  font-size: 12px;
  color: #e2e8f0;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.ad-wc-slot small {
  font-size: 10px;
  color: #64748b;
}
.ad-wc-path .ad-wc-slot {
  border-color: rgba(245,158,11,0.11);
  background: rgba(245,158,11,0.04);
}

/* ---- Section 1: Match Header with glow ---- */
.ad-sec-header {
  position: relative;
  text-align: center;
  background: linear-gradient(135deg, #0f172a, #1a1f36);
  border: 1px solid rgba(255,255,255,0.06);
  padding: 24px 16px 16px;
  overflow: hidden;
}
.ad-sec-header::before {
  content: '';
  position: absolute;
  top: 0; left: 10%; width: 30%; height: 100%;
  background: radial-gradient(circle at center, rgba(59,130,246,0.12), transparent 70%);
  pointer-events: none;
}
.ad-sec-header::after {
  content: '';
  position: absolute;
  top: 0; right: 10%; width: 30%; height: 100%;
  background: radial-gradient(circle at center, rgba(236,72,153,0.12), transparent 70%);
  pointer-events: none;
}
.ad-h-info {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  font-size: 12px; color: #64748b; margin-bottom: 16px; position: relative; z-index: 1;
}
.ad-h-comp {
  font-size: 10px; padding: 2px 10px;
  background: rgba(139,92,246,0.15); color: #a78bfa; border-radius: 10px;
}
.ad-header-teams {
  display: flex; align-items: center; justify-content: center; gap: 32px;
  position: relative; z-index: 1;
}
.ad-h-team { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.ad-h-name { font-size: 24px; font-weight: 800; letter-spacing: 1px; }
.ad-h-name.home { color: #34d399; text-shadow: 0 0 16px rgba(52,211,153,0.3); }
.ad-h-name.away { color: #f87171; text-shadow: 0 0 16px rgba(248,113,113,0.3); }
.ad-h-xg { font-size: 11px; color: #475569; }
.ad-h-vs { font-size: 24px; font-weight: 900; color: #374151; font-style: italic; letter-spacing: 2px; }
.ad-h-glow-line {
  position: absolute; bottom: 0; left: 0; width: 100%; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(59,130,246,0.3), transparent);
}

/* ---- Section 2: AI Recommend (3-col grid) ---- */
.ad-sec-recommend {
  padding: 16px;
  background: #171d2c;
  border: 1px solid rgba(255,255,255,0.08);
}
.ad-rec-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 0.8fr;
  gap: 16px;
  align-items: center;
  margin-top: 8px;
}
.ad-rec-main { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.ad-rec-box {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  width: 100%; padding: 14px 16px;
  background: linear-gradient(135deg, rgba(16,185,129,0.12), rgba(16,185,129,0.04));
  border: 1px solid rgba(16,185,129,0.25);
  border-radius: 12px;
  box-shadow: inset 0 0 20px rgba(16,185,129,0.04);
}
.ad-rec-text { font-size: 24px; font-weight: 900; letter-spacing: 2px; }
.ad-rec-badge {
  font-size: 11px; padding: 3px 10px; border-radius: 10px; white-space: nowrap;
}
.ad-rec-stars { font-size: 16px; }
.ad-star.on { color: #f59e0b; }
.ad-star.off { color: #1e293b; }

/* Confidence circle (SVG) */
.ad-rec-conf {
  display: flex; flex-direction: column; align-items: center;
  border-left: 1px solid rgba(255,255,255,0.06);
  padding-left: 16px;
}
.ad-conf-label { font-size: 11px; color: #64748b; margin-bottom: 8px; }
.ad-conf-circle { position: relative; width: 64px; height: 64px; }
.ad-conf-svg {
  width: 64px; height: 64px; transform: rotate(-90deg);
}
.ad-conf-num {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 800; color: #f8fafc;
}

/* Odds consistency */
.ad-rec-cons {
  display: flex; flex-direction: column; align-items: center;
  border-left: 1px solid rgba(255,255,255,0.06);
  padding-left: 16px;
}
.ad-cons-pct { font-size: 24px; font-weight: 900; }
.ad-cons-text { font-size: 11px; margin-top: 4px; }

/* ---- Section 3: Probability (single stacked bar) ---- */
.ad-prob-labels {
  display: flex; justify-content: space-between;
  margin-bottom: 8px; padding: 0 2px;
}
.ad-prob-lbl { font-size: 12px; font-weight: 600; width: 33.33%; }
.ad-prob-lbl.home { color: #10b981; text-align: left; }
.ad-prob-lbl.draw { color: #3b82f6; text-align: center; }
.ad-prob-lbl.away { color: #ef4444; text-align: right; }

.ad-prob-bar {
  display: flex; height: 8px; border-radius: 4px; overflow: hidden;
  background: #1f2937; margin-bottom: 8px;
}
.ad-prob-seg { height: 100%; transition: width 0.4s; min-width: 2px; }
.ad-prob-seg.home { background: #10b981; border-radius: 4px 0 0 4px; box-shadow: 0 0 8px rgba(16,185,129,0.4); }
.ad-prob-seg.draw { background: #3b82f6; margin: 0 2px; border-radius: 2px; }
.ad-prob-seg.away { background: #ef4444; border-radius: 0 4px 4px 0; }

.ad-prob-values {
  display: flex; justify-content: space-between;
  padding: 0 2px; margin-bottom: 12px;
}
.ad-prob-val { font-size: 14px; font-weight: 700; color: #f8fafc; width: 33.33%; }
.ad-prob-val.home { text-align: left; }
.ad-prob-val.draw { text-align: center; }
.ad-prob-val.away { text-align: right; }

.ad-prob-implied {
  text-align: center; font-size: 11px; color: #475569;
  padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.06);
}
.ad-prob-compare { display: flex; justify-content: center; gap: 12px; margin-bottom: 4px; }
.ad-pci { font-weight: 600; padding: 2px 8px; border-radius: 4px; font-size: 10px; }
.ad-pci.home { color: #10b981; background: rgba(16,185,129,0.08); }
.ad-pci.draw { color: #3b82f6; background: rgba(59,130,246,0.08); }
.ad-pci.away { color: #ef4444; background: rgba(239,68,68,0.08); }
.ad-prob-diff { font-size: 10px; color: #64748b; margin-top: 2px; }

/* ---- Section 4: 2-col layout (Expected Goals + Score Cards) ---- */
.ad-row-2col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* Expected Goals */
.ad-xg-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px;
}
.ad-xg-col { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.ad-xg-team { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.ad-xg-val { font-size: 32px; font-weight: 900; }
.ad-xg-val.home { color: #10b981; }
.ad-xg-val.away { color: #ef4444; }
.ad-xg-vs { font-size: 20px; font-weight: 900; color: #374151; }
.ad-xg-dots { display: flex; gap: 4px; }
.ad-xg-dot { font-size: 14px; transition: all 0.2s; }
.ad-xg-dot.home.on { color: #10b981; }
.ad-xg-dot.home.half { color: #10b981; opacity: 0.4; }
.ad-xg-dot.away.on { color: #ef4444; }
.ad-xg-dot.away.half { color: #ef4444; opacity: 0.4; }
.ad-xg-dot.off { color: #1e293b; }

/* Score cards */
.ad-sc-row { display: flex; gap: 8px; }
.ad-sc-card {
  flex: 1; padding: 12px 8px;
  background: #1a2133; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; text-align: center;
  display: flex; flex-direction: column; align-items: center;
  position: relative;
}
.ad-sc-card.top {
  background: rgba(16,185,129,0.06);
  border-color: rgba(16,185,129,0.2);
  box-shadow: 0 0 12px rgba(16,185,129,0.08);
}
.ad-sc-rank {
  position: absolute; top: 4px; left: 4px;
  width: 16px; height: 16px; border-radius: 50%;
  background: #f59e0b; color: #000;
  font-size: 9px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
}
.ad-sc-score { font-size: 22px; font-weight: 800; color: #e2e8f0; margin-top: 4px; letter-spacing: 1px; }
.ad-sc-card.top .ad-sc-score { color: #10b981; }
.ad-sc-pct { font-size: 11px; color: #64748b; margin-top: 4px; }
.ad-sc-label { font-size: 9px; color: #475569; margin-top: 2px; padding: 1px 6px; background: rgba(255,255,255,0.04); border-radius: 3px; }
.ad-sc-derive {
  width: 100%;
  margin-top: 8px;
  padding-top: 7px;
  border-top: 1px solid rgba(255,255,255,0.06);
  color: #94a3b8;
  font-size: 10px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ---- Section 5: Play Recommendations (horizontal scroll) ---- */
.ad-play-scroll {
  display: flex; gap: 10px;
  flex-wrap: nowrap;
  padding-bottom: 4px;
}

.ad-play-card {
  flex: 1; min-width: 0;
  padding: 14px 12px;
  background: #1a2133; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
  display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.ad-pc-head {
  display: flex; align-items: center; gap: 4px; font-size: 12px; margin-bottom: 4px;
}
.ad-pc-icon { font-size: 14px; font-weight: 700; }
.ad-pc-name { font-weight: 500; }
.ad-pc-sub {
  font-size: 9px; padding: 1px 5px; border-radius: 4px;
  background: rgba(255,255,255,0.06); color: #64748b;
}
.ad-pc-ref {
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(255,255,255,0.05);
  color: #94a3b8;
  font-size: 9px;
  font-weight: 700;
  line-height: 1.2;
}
.ad-play-card.green .ad-pc-head { color: #10b981; }
.ad-play-card.green { border-color: rgba(16,185,129,0.12); }
.ad-play-card.blue .ad-pc-head { color: #3b82f6; }
.ad-play-card.blue { border-color: rgba(59,130,246,0.12); }
.ad-play-card.purple .ad-pc-head { color: #8b5cf6; }
.ad-play-card.purple { border-color: rgba(139,92,246,0.12); }
.ad-play-card.orange .ad-pc-head { color: #f59e0b; }
.ad-play-card.orange { border-color: rgba(245,158,11,0.12); }

.ad-pc-rec {
  font-size: 16px; font-weight: 800; color: #f8fafc;
  text-align: center; min-height: 40px;
  display: flex; align-items: center;
}
.ad-pc-pct { font-size: 12px; color: #64748b; }
.ad-pc-stars { font-size: 10px; }
.ad-pc-star.on { color: #f59e0b; }
.ad-pc-star.off { color: #1e293b; }
.ad-pc-derive {
  width: 100%;
  color: #64748b;
  font-size: 10px;
  line-height: 1.45;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ---- Play derivation chain ---- */
.ad-derive-sec { border-color: rgba(34,197,94,0.12); }
.ad-derive-axis {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 6px 8px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(34,197,94,0.06);
  border: 1px solid rgba(34,197,94,0.12);
  margin-bottom: 8px;
}
.ad-derive-axis span {
  color: #86efac;
  font-size: 10px;
  font-weight: 800;
}
.ad-derive-axis b {
  min-width: 0;
  color: #e5e7eb;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ad-derive-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.ad-derive-row {
  min-width: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
}
.ad-derive-name {
  color: #e2e8f0;
  font-size: 12px;
  font-weight: 800;
}
.ad-derive-label {
  justify-self: start;
  align-self: center;
  padding: 2px 6px;
  border-radius: 999px;
  color: #bfdbfe;
  background: rgba(59,130,246,0.10);
  border: 1px solid rgba(59,130,246,0.16);
  font-size: 9px;
  font-weight: 800;
}
.ad-derive-row p {
  grid-column: 1 / -1;
  margin: 0;
  color: #94a3b8;
  font-size: 10px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ad-derive-gate {
  grid-column: 1 / -1;
  min-width: 0;
  width: fit-content;
  max-width: 100%;
  padding: 3px 6px;
  border-radius: 5px;
  color: #fef3c7;
  background: rgba(245,158,11,0.10);
  border: 1px solid rgba(245,158,11,0.22);
  font-size: 10px;
  font-weight: 800;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ad-ou-diag {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-width: 0;
}
.ad-ou-diag span {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  max-width: 100%;
  padding: 2px 5px;
  border-radius: 5px;
  background: rgba(148,163,184,0.08);
  border: 1px solid rgba(148,163,184,0.12);
}
.ad-ou-diag span.warn {
  background: rgba(245,158,11,0.10);
  border-color: rgba(245,158,11,0.22);
}
.ad-ou-diag small {
  flex: 0 0 auto;
  color: #94a3b8;
  font-size: 9px;
  font-weight: 800;
}
.ad-ou-diag b {
  min-width: 0;
  color: #e5e7eb;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- Section 6: Factors + AI Interpretation (2-col) ---- */
.ad-sec-factors {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
}
.ad-fact-left {
  padding-right: 16px;
}
.ad-fact-right {
  padding-left: 16px;
  border-left: 1px solid rgba(255,255,255,0.06);
}

/* Factor bars */
.ad-fact-list { display: flex; flex-direction: column; gap: 10px; }
.ad-fact-row { display: flex; align-items: center; gap: 8px; }
.ad-fact-name { font-size: 12px; color: #94a3b8; min-width: 64px; }
.ad-fact-track {
  flex: 1; height: 6px; background: #1f2937; border-radius: 3px; overflow: hidden;
}
.ad-fact-fill { height: 100%; border-radius: 3px; transition: width 0.4s; }
.ad-fact-pct { font-size: 12px; color: #94a3b8; min-width: 32px; text-align: right; }

/* Factor detail cards */
.ad-fact-details {
  display: flex; flex-direction: column; gap: 6px;
  margin-top: 12px; padding-top: 10px;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.ad-fd-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px; border: 1px solid rgba(255,255,255,0.04);
  border-left: 3px solid;
}
.ad-fd-label { font-size: 11px; font-weight: 600; min-width: 56px; }
.ad-fd-value { font-size: 11px; color: #94a3b8; }

/* Evidence provenance */
.ad-prov-sec { margin-top: 10px; }
.ad-prov-title { font-size: 10px; color: #64748b; margin-bottom: 6px; letter-spacing: 0.5px; }
.ad-prov-grid { display: flex; flex-direction: column; gap: 4px; }
.ad-prov-row { display: flex; align-items: center; gap: 6px; font-size: 10px; color: #94a3b8; }
.ad-prov-factor { min-width: 36px; color: #cbd5e1; font-weight: 500; }
.ad-prov-src { padding: 1px 5px; background: rgba(59,130,246,0.15); border-radius: 3px; color: #60a5fa; font-size: 9px; }
.ad-prov-conf { color: #64748b; font-size: 9px; }
.ad-prov-badge { padding: 1px 4px; border-radius: 3px; font-size: 9px; }
.ad-prov-badge.fallback { background: rgba(245,158,11,0.15); color: #f59e0b; }
.ad-prov-badge.stale { background: rgba(239,68,68,0.15); color: #ef4444; }
.ad-prov-time { color: #475569; font-size: 9px; }

/* Match script */
.ad-match-script { margin-top: 10px; }
.ms-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin: 6px 0; }
.ms-axis { background: rgba(30,41,59,0.5); border-radius: 6px; padding: 6px 8px; text-align: center; }
.ms-axis-label { font-size: 9px; color: #94a3b8; margin-bottom: 2px; }
.ms-axis-value { font-size: 12px; color: #e2e8f0; font-weight: 600; }
.ms-axis-detail { font-size: 9px; color: #64748b; margin-top: 1px; }
.ms-unc-low { color: #10b981; }
.ms-unc-medium { color: #f59e0b; }
.ms-unc-high { color: #ef4444; }
.ms-unc-very_high { color: #dc2626; }
.ms-warning { color: #f59e0b; font-size: 11px; margin-left: 4px; }
.ms-contradictions { margin-top: 6px; }
.ms-contr-title { font-size: 10px; color: #f59e0b; margin-bottom: 3px; }
.ms-contr-item { font-size: 10px; color: #cbd5e1; display: flex; align-items: center; gap: 4px; }
.ms-contr-sev { color: #ef4444; font-size: 8px; }
.ms-drivers { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.ms-drivers-label { font-size: 10px; color: #94a3b8; }
.ms-driver-tag { font-size: 9px; background: rgba(59,130,246,0.15); color: #93c5fd; padding: 1px 5px; border-radius: 3px; }

/* Reanalysis history */
.ad-reanalysis { margin-top: 10px; }
.ad-reanalysis-list { display: flex; flex-direction: column; gap: 6px; }
.ad-reanalysis-item { background: rgba(30,41,59,0.5); border-radius: 6px; padding: 8px 10px; border-left: 3px solid #3b82f6; }
.ad-reanalysis-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.ad-reanalysis-trigger { font-size: 11px; color: #93c5fd; font-weight: 600; }
.ad-reanalysis-time { font-size: 10px; color: #64748b; }
.ad-reanalysis-badge { font-size: 9px; padding: 1px 5px; border-radius: 3px; }
.ad-reanalysis-badge.changed { background: rgba(59,130,246,0.2); color: #93c5fd; }
.ad-reanalysis-badge.unchanged { background: rgba(100,116,139,0.2); color: #94a3b8; }
.ad-reanalysis-settled { font-size: 9px; padding: 1px 5px; border-radius: 3px; }
.ad-reanalysis-settled.ok { background: rgba(16,185,129,0.15); color: #10b981; }
.ad-reanalysis-settled.bad { background: rgba(239,68,68,0.15); color: #ef4444; }
.ad-reanalysis-changes { display: flex; flex-direction: column; gap: 2px; }
.ad-reanalysis-diff { display: flex; align-items: center; gap: 4px; font-size: 11px; }
.ad-reanalysis-label { color: #94a3b8; min-width: 60px; }
.ad-reanalysis-before { color: #94a3b8; }
.ad-reanalysis-arrow { color: #475569; font-size: 10px; }
.ad-reanalysis-after { color: #93c5fd; font-weight: 600; }
.ad-reanalysis-summary { font-size: 11px; margin-top: 4px; color: #cbd5e1; }

/* AI interpretation */
.ad-ai-list {
  list-style: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 8px;
}
.ad-ai-item {
  display: flex; align-items: flex-start; gap: 8px;
  font-size: 12px; color: #cbd5e1; line-height: 1.6;
}
.ad-ai-check { color: #10b981; flex-shrink: 0; margin-top: 2px; }
.ad-ai-conclusion {
  margin-top: 12px; padding-top: 10px;
  border-top: 1px solid rgba(255,255,255,0.06);
  font-size: 12px; color: #64748b;
}
.ad-ai-result { font-weight: 800; font-size: 14px; }

/* Adjustments */
.ad-adj-sec { margin-top: 12px; }
.ad-adj-toggle {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: rgba(255,255,255,0.03);
  border-radius: 8px; cursor: pointer; font-size: 12px; color: #64748b;
}
.ad-adj-toggle:hover { background: rgba(255,255,255,0.06); }
.ad-toggle-arrow { font-size: 10px; }
.ad-adj-list {
  padding: 10px 12px;
  background: rgba(255,255,255,0.02);
  border-radius: 0 0 8px 8px;
  margin-top: -4px;
}
.ad-adj-item { display: flex; gap: 8px; font-size: 11px; margin-bottom: 4px; }
.ad-adj-tag { color: #f59e0b; font-weight: 600; min-width: 56px; }
.ad-adj-txt { color: #94a3b8; }

/* Model status strip */
.mc-model-strip { display: flex; align-items: center; gap: 12px; margin-top: 6px; padding: 8px 12px; background: rgba(30,41,59,0.4); border-radius: 8px; }
.mc-model-tag { display: flex; align-items: center; gap: 6px; }
.mc-model-label { font-size: 10px; color: #64748b; }
.mc-model-ver { font-size: 11px; font-weight: 600; color: #60a5fa; padding: 2px 6px; background: rgba(59,130,246,0.15); border-radius: 4px; }
.mc-model-acc { font-size: 12px; font-weight: 700; color: #10b981; }
.mc-model-gate { font-size: 10px; font-weight: 600; color: #f59e0b; padding: 1px 4px; background: rgba(245,158,11,0.15); border-radius: 3px; }
.mc-model-changes { display: flex; align-items: center; gap: 4px; font-size: 10px; color: #94a3b8; }
.mc-model-targets { display: flex; align-items: center; gap: 4px; font-size: 10px; }
.mc-target-dot { display: inline-block; padding: 1px 5px; border-radius: 3px; font-weight: 600; cursor: help; }
.mc-target-dot.met { background: rgba(34,197,94,0.2); color: #22c55e; }
.mc-target-dot.miss { background: rgba(239,68,68,0.2); color: #ef4444; }

/* Accuracy trend chart */
.mc-trend-section { margin-top: 8px; padding: 8px 12px; background: rgba(30,41,59,0.4); border-radius: 8px; }
.mc-trend-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.mc-trend-title { font-size: 11px; font-weight: 600; color: #94a3b8; }
.mc-trend-toggle { display: flex; gap: 2px; }
.mc-trend-btn { font-size: 9px; padding: 1px 6px; border: 1px solid rgba(255,255,255,0.1); border-radius: 3px; background: transparent; color: #64748b; cursor: pointer; }
.mc-trend-btn.active { background: rgba(59,130,246,0.2); color: #93c5fd; border-color: rgba(59,130,246,0.3); }
.mc-trend-chart { display: flex; align-items: flex-end; gap: 1px; height: 48px; }
.mc-trend-bar-wrap { flex: 1; min-width: 2px; height: 100%; display: flex; align-items: flex-end; }
.mc-trend-bar { width: 100%; min-height: 2px; border-radius: 1px 1px 0 0; transition: height 0.2s; }
.mc-trend-bar.good { background: #10b981; }
.mc-trend-bar.ok { background: #f59e0b; }
.mc-trend-bar.low { background: #ef4444; }
.mc-trend-axis { display: flex; justify-content: space-between; font-size: 8px; color: #475569; margin-top: 2px; }

/* ---- Learning foundation ---- */
.ad-learning {
  background: #141b2a;
  border: 1px solid rgba(16,185,129,0.14);
}
.ad-learn-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.ad-learn-metric {
  min-width: 0;
  padding: 9px 10px;
  border-radius: 8px;
  background: rgba(255,255,255,0.035);
  border: 1px solid rgba(255,255,255,0.05);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ad-learn-metric span {
  font-size: 10px;
  color: #64748b;
}
.ad-learn-metric b {
  font-size: 13px;
  color: #d1fae5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ad-learn-block {
  padding-top: 10px;
  border-top: 1px solid rgba(255,255,255,0.06);
  margin-top: 10px;
}
.ad-learn-title {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 700;
  margin-bottom: 8px;
}
.ad-sim-list,
.ad-review-mini-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ad-sim-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
}
.ad-sim-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ad-sim-main b {
  font-size: 12px;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ad-sim-main span {
  font-size: 10px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ad-sim-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 3px;
}
.ad-sim-tag {
  max-width: 76px;
  padding: 2px 5px;
  border-radius: 999px;
  background: rgba(52, 211, 153, 0.10);
  border: 1px solid rgba(52, 211, 153, 0.18);
  color: #a7f3d0;
  font-size: 9px;
  font-weight: 700;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ad-sim-side {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}
.ad-sim-score {
  font-size: 12px;
  font-weight: 800;
  color: #34d399;
}
.ad-sim-result {
  font-size: 11px;
  color: #94a3b8;
}
.ad-sim-result.ok { color: #10b981; }
.ad-sim-result.bad { color: #ef4444; }
.ad-review-mini {
  display: grid;
  grid-template-columns: 78px minmax(0, 1fr) 42px auto;
  gap: 8px;
  align-items: center;
  padding: 7px 10px;
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
  border-left: 3px solid #64748b;
  font-size: 11px;
  color: #cbd5e1;
}
.ad-review-mini.ok { border-left-color: #10b981; }
.ad-review-mini.bad { border-left-color: #ef4444; }
.ad-review-play {
  color: #94a3b8;
  font-weight: 700;
}
.ad-review-mini b {
  color: #e2e8f0;
}
.ad-review-mini small {
  color: #f59e0b;
}
.ad-review-reason {
  grid-column: 1 / -1;
  margin: 0;
  color: #94a3b8;
  font-size: 10px;
  line-height: 1.45;
}
.ad-review-next-data { display: inline-flex; align-items: center; gap: 4px; margin-left: 4px; }
.ad-review-next-label { font-size: 9px; color: #64748b; }
.ad-review-next-ch { font-size: 9px; color: #93c5fd; padding: 0 3px; background: rgba(59,130,246,0.1); border-radius: 3px; }
.ad-review-tags {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.ad-review-tags em {
  font-style: normal;
  padding: 2px 5px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: #bfdbfe;
  font-size: 9px;
  font-weight: 700;
}

/* ---- Disclaimer ---- */
.ad-disclaimer {
  text-align: center; font-size: 10px; color: #374151;
  display: flex; align-items: center; justify-content: center; gap: 4px;
  padding-bottom: 8px;
}

/* ---- Responsive ---- */
@media (max-width: 600px) {
  .analysis-detail { gap: 8px; }
  .ad-sec { padding: 10px; border-radius: 8px; }
  .ad-sec-label { font-size: 12px; margin-bottom: 8px; }
  .ad-data-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
  .ad-data-item { padding: 7px 8px; border-radius: 6px; }
  .ad-data-item span { font-size: 11px; }
  .ad-data-item small { font-size: 9px; }
  .ad-ev-grid { grid-template-columns: 1fr; gap: 6px; }
  .ad-ev-artifacts { grid-template-columns: 1fr; }
  .ad-ev-artifact { grid-template-columns: 64px 1fr 36px; font-size: 10px; }
  .ad-intel-grid { grid-template-columns: 1fr; gap: 6px; }
  .ad-intel-card { padding: 8px 10px; border-radius: 6px; }
  .ad-intel-card b { font-size: 12px; }
  .ad-intel-card p { font-size: 10px; line-height: 1.45; }
  .ad-intel-adjust-card { padding: 8px 10px; border-radius: 6px; }
  .ad-intel-deltas { gap: 5px; }
  .ad-intel-delta { padding: 5px 4px; }
  .ad-intel-delta b { font-size: 11px; }
  .ad-wc-top { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; margin-bottom: 8px; }
  .ad-wc-pill { padding: 7px 6px; border-radius: 6px; }
  .ad-wc-pill span { font-size: 9px; }
  .ad-wc-pill b { font-size: 12px; }
  .ad-wc-teams { grid-template-columns: 1fr; gap: 6px; }
  .ad-wc-team { padding: 8px; border-radius: 6px; }
  .ad-wc-team-line { margin-bottom: 5px; }
  .ad-wc-team-name { font-size: 12px; }
  .ad-wc-points { font-size: 15px; }
  .ad-wc-team-meta { gap: 4px; margin-bottom: 6px; }
  .ad-wc-team-meta span { font-size: 9px; padding: 2px 5px; }
  .ad-wc-pressure { font-size: 10px; padding-top: 6px; }
  .ad-wc-note { font-size: 10px; padding: 6px 8px; border-radius: 6px; }
  .ad-wc-sub { margin-top: 8px; padding-top: 8px; }
  .ad-wc-sub-title { font-size: 10px; margin-bottom: 6px; }
  .ad-wc-fixtures, .ad-wc-slots { grid-template-columns: 1fr; gap: 6px; }
  .ad-wc-path-grid { grid-template-columns: 1fr; gap: 6px; }
  .ad-wc-fixture { grid-template-columns: 36px minmax(0, 1fr) 48px; gap: 6px; font-size: 10px; padding: 6px 8px; }
  .ad-wc-slot { padding: 6px 8px; }
  .ad-wc-slot span { font-size: 10px; }
  .ad-wc-slot small { font-size: 9px; }

  /* Header: smaller */
  .ad-sec-header { padding: 12px 10px 10px; }
  .ad-h-info { font-size: 10px; margin-bottom: 8px; gap: 4px; }
  .ad-h-comp { font-size: 9px; padding: 1px 6px; }
  .ad-header-teams { gap: 16px; }
  .ad-h-name { font-size: 16px; }
  .ad-h-vs { font-size: 16px; }
  .ad-h-xg { font-size: 9px; }

  /* Recommend: stack vertically on small mobile */
  .ad-rec-grid { grid-template-columns: 1fr; gap: 8px; }
  .ad-rec-conf, .ad-rec-cons { padding-left: 0; border-left: none; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px; flex-direction: row; justify-content: space-between; }
  .ad-rec-box { padding: 8px 10px; gap: 8px; border-radius: 8px; }
  .ad-rec-text { font-size: 18px; }
  .ad-rec-badge { font-size: 9px; padding: 2px 6px; }
  .ad-rec-stars { font-size: 12px; }
  .ad-conf-label { font-size: 9px; margin-bottom: 4px; }
  .ad-conf-circle { width: 48px; height: 48px; }
  .ad-conf-svg { width: 48px; height: 48px; }
  .ad-conf-num { font-size: 12px; }
  .ad-rec-conf, .ad-rec-cons { padding-left: 8px; border-left-width: 1px; }
  .ad-cons-pct { font-size: 18px; }
  .ad-cons-text { font-size: 9px; }

  /* Probability: compact */
  .ad-prob-lbl { font-size: 10px; }
  .ad-prob-bar { height: 6px; }
  .ad-prob-val { font-size: 12px; }
  .ad-prob-implied { font-size: 9px; padding-top: 6px; }

  /* 2-col: stack vertically on mobile */
  .ad-row-2col { grid-template-columns: 1fr; gap: 8px; }
  .ad-xg-row { padding: 4px 8px; }
  .ad-xg-team { font-size: 10px; }
  .ad-xg-val { font-size: 22px; }
  .ad-xg-vs { font-size: 14px; }
  .ad-xg-dots { gap: 2px; }
  .ad-xg-dot { font-size: 10px; }
  .ad-sc-card { padding: 8px 4px; border-radius: 6px; }
  .ad-sc-rank { width: 12px; height: 12px; font-size: 7px; }
  .ad-sc-score { font-size: 14px; margin-top: 2px; }
  .ad-sc-pct { font-size: 9px; margin-top: 2px; }
  .ad-derive-axis { grid-template-columns: auto minmax(0, 1fr); }
  .ad-derive-list { grid-template-columns: 1fr; }
  .ad-derive-row { padding: 7px 8px; }
  .ad-derive-row p { -webkit-line-clamp: 3; }

  /* Play cards: wrap on mobile */
  .ad-play-scroll { gap: 6px; flex-wrap: wrap; }
  .ad-play-card { min-width: calc(50% - 6px); padding: 8px 6px; border-radius: 8px; gap: 4px; }
  .ad-pc-head { font-size: 10px; margin-bottom: 2px; }
  .ad-pc-icon { font-size: 11px; }
  .ad-pc-sub { font-size: 8px; padding: 0 3px; }
  .ad-pc-rec { font-size: 12px; min-height: 28px; }
  .ad-pc-pct { font-size: 10px; }
  .ad-pc-stars { font-size: 8px; }

  /* Factors + AI: stack vertically on mobile */
  .ad-sec-factors { grid-template-columns: 1fr; }
  .ad-fact-left { padding-right: 0; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.06); }
  .ad-fact-right { padding-left: 0; padding-top: 12px; border-left: none; }
  .ad-fact-list { gap: 6px; }
  .ad-fact-row { gap: 4px; }
  .ad-fact-name { font-size: 10px; min-width: 48px; }
  .ad-fact-track { height: 4px; }
  .ad-fact-pct { font-size: 10px; min-width: 28px; }
  .ad-ai-list { gap: 4px; }
  .ad-ai-item { font-size: 10px; line-height: 1.4; gap: 4px; }
  .ad-ai-check { margin-top: 1px; font-size: 10px; }
  .ad-ai-conclusion { font-size: 10px; margin-top: 6px; padding-top: 6px; }
  .ad-ai-result { font-size: 12px; }
  .ad-adj-sec { margin-top: 6px; }
  .ad-adj-toggle { padding: 4px 8px; font-size: 10px; }
  .ad-adj-item { font-size: 9px; margin-bottom: 2px; }
  .ad-adj-tag { min-width: 40px; }
  .ad-learn-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
  .ad-learn-metric { padding: 7px 8px; border-radius: 6px; }
  .ad-learn-metric span { font-size: 9px; }
  .ad-learn-metric b { font-size: 11px; }
  .ad-sim-row { grid-template-columns: 1fr; gap: 5px; padding: 7px 8px; }
  .ad-sim-side { justify-content: space-between; }
  .ad-sim-main b { font-size: 11px; }
  .ad-sim-main span, .ad-sim-result { font-size: 9px; }
  .ad-sim-tags { gap: 3px; }
  .ad-sim-tag { max-width: 64px; padding: 2px 4px; font-size: 8px; }
  .ad-review-mini { grid-template-columns: 1fr auto; gap: 5px; font-size: 9px; }
  .ad-review-mini small { grid-column: 1 / -1; }

  .ad-disclaimer { font-size: 8px; padding-bottom: 4px; }
}

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 2px solid #2a2a3a;
  margin-bottom: 4px;
}
.tab-btn {
  padding: 8px 20px;
  background: transparent;
  border: none;
  color: #888;
  font-size: 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}
.tab-btn:hover { color: #bbb; }
.tab-btn.active {
  color: #4fc3f7;
  border-bottom-color: #4fc3f7;
}

/* Review section */
.review-section { display: flex; flex-direction: column; gap: 12px; }
.review-filter {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.review-filter select {
  background: #2a2a3a;
  color: #e0e0e0;
  border: 1px solid #3a3a4a;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 13px;
}
.review-summary { color: #888; font-size: 13px; }
.review-summary span { margin-right: 12px; }
.review-insights {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.review-insight-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.review-insight-card {
  min-width: 0;
  padding: 9px 10px;
  border-radius: 6px;
  background: #1e1e2e;
  border: 1px solid #2d3445;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px 8px;
  align-items: baseline;
}
.review-insight-card span {
  color: #9aa4b2;
  font-size: 11px;
  font-weight: 700;
}
.review-insight-card b {
  color: #e5e7eb;
  font-size: 18px;
}
.review-insight-card small {
  grid-column: 1 / -1;
  color: #64748b;
  font-size: 10px;
}
.review-insight-card.danger b { color: #f87171; }
.review-insight-card.warn b { color: #fbbf24; }
.review-insight-card.info b { color: #60a5fa; }
.review-insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.review-insight-panel,
.review-error-strip {
  min-width: 0;
  padding: 9px 10px;
  border-radius: 6px;
  background: #1e1e2e;
  border: 1px solid #2d3445;
}
.review-insight-title {
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 7px;
}
.review-insight-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px 48px;
  gap: 8px;
  align-items: center;
  padding: 4px 0;
  border-top: 1px solid rgba(255,255,255,0.04);
  font-size: 11px;
}
.review-insight-row:first-of-type { border-top: 0; }
.review-insight-row span {
  min-width: 0;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.review-insight-row b {
  color: #e5e7eb;
  text-align: right;
}
.review-insight-row small {
  color: #64748b;
  text-align: right;
}
.review-error-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.review-error-chips span {
  max-width: 260px;
  padding: 4px 7px;
  border-radius: 999px;
  background: rgba(248, 113, 113, 0.10);
  border: 1px solid rgba(248, 113, 113, 0.18);
  color: #fecaca;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.review-list { display: flex; flex-direction: column; gap: 6px; }
.review-row {
  padding: 8px 12px;
  border-radius: 6px;
  border-left: 3px solid #555;
  background: #1e1e2e;
}
.review-row.correct { border-left-color: #4caf50; }
.review-row.wrong { border-left-color: #ef5350; }
.review-main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.review-play-type {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  background: #3a3a4a;
  color: #aaa;
}
.review-teams { font-weight: 500; color: #e0e0e0; }
.review-pred { color: #4fc3f7; font-size: 13px; }
.review-actual { color: #aaa; font-size: 13px; }
.review-result { font-weight: 600; font-size: 13px; }
.review-result.ok { color: #4caf50; }
.review-result.fail { color: #ef5350; }
.review-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #666;
  margin-top: 4px;
  flex-wrap: wrap;
}
.review-attr { color: #ff9800; }
.review-conf { color: #888; }
.review-reason {
  margin-top: 7px;
  color: #9aa4b2;
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.review-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 6px;
}
.review-tags span {
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(79, 195, 247, 0.10);
  border: 1px solid rgba(79, 195, 247, 0.18);
  color: #8bd5ff;
  font-size: 10px;
  font-weight: 700;
}

@media (max-width: 760px) {
  .review-insight-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .review-insight-grid { grid-template-columns: 1fr; }
  .review-error-chips span { max-width: 100%; }
}

@media (max-width: 480px) {
  .review-insight-cards { grid-template-columns: 1fr; }
  .review-insight-row { grid-template-columns: minmax(0, 1fr) 36px 42px; gap: 6px; }
}

/* Health section */
.health-section { display: flex; flex-direction: column; gap: 12px; }
.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.health-card {
  background: #1e1e2e;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #2a2a3a;
}
.health-label { font-size: 12px; color: #888; margin-bottom: 4px; }
.health-value { font-size: 16px; font-weight: 600; color: #e0e0e0; }
.health-sub { font-size: 11px; color: #666; margin-top: 4px; }
.auto-loop-panel {
  background: #141824;
  border: 1px solid #283244;
  border-radius: 8px;
  padding: 14px;
}
.auto-loop-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.auto-loop-head h3 {
  margin: 0;
  color: #f5f5f5;
  font-size: 16px;
}
.auto-loop-head span {
  display: block;
  margin-top: 3px;
  color: #8b95a7;
  font-size: 12px;
}
.auto-loop-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.auto-loop-actions .pause {
  border-color: rgba(245, 158, 11, 0.28);
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.08);
}
.automation-status-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.automation-status-card {
  min-width: 0;
  padding: 10px;
  border-radius: 7px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: #101522;
}
.automation-status-card span {
  display: block;
  color: #94a3b8;
  font-size: 11px;
  margin-bottom: 4px;
}
.automation-status-card b {
  display: block;
  color: #e2e8f0;
  font-size: 15px;
}
.automation-status-card small {
  display: block;
  margin-top: 4px;
  color: #64748b;
  font-size: 10px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.automation-status-card.success { border-color: rgba(34, 197, 94, 0.24); }
.automation-status-card.success b { color: #86efac; }
.automation-status-card.running { border-color: rgba(59, 130, 246, 0.34); background: rgba(59, 130, 246, 0.08); }
.automation-status-card.running b { color: #93c5fd; }
.automation-status-card.failed { border-color: rgba(239, 68, 68, 0.30); }
.automation-status-card.failed b { color: #fca5a5; }
.automation-status-card.planned { border-color: rgba(148, 163, 184, 0.14); }
.automation-effect-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
  margin: 0 0 12px;
}
.automation-effect-card {
  min-width: 0;
  padding: 10px;
  border-radius: 7px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(15, 23, 42, 0.72));
}
.automation-effect-card span {
  display: block;
  color: #94a3b8;
  font-size: 11px;
  margin-bottom: 4px;
}
.automation-effect-card b {
  display: block;
  color: #e2e8f0;
  font-size: 15px;
  overflow-wrap: anywhere;
}
.automation-effect-card small {
  display: block;
  margin-top: 4px;
  color: #64748b;
  font-size: 10px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.automation-effect-card.success { border-color: rgba(34, 197, 94, 0.24); }
.automation-effect-card.success b { color: #86efac; }
.automation-effect-card.running { border-color: rgba(245, 158, 11, 0.28); }
.automation-effect-card.running b { color: #fbbf24; }
.automation-effect-card.failed { border-color: rgba(239, 68, 68, 0.30); }
.automation-effect-card.failed b { color: #fca5a5; }
.automation-effect-card.planned { border-color: rgba(148, 163, 184, 0.14); }
.auto-loop-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 12px 0 8px;
}
.auto-loop-section-title.compact {
  margin-top: 0;
}
.auto-loop-section-title b {
  color: #e2e8f0;
  font-size: 13px;
}
.auto-loop-section-title span {
  color: #64748b;
  font-size: 11px;
  text-align: right;
}
.auto-loop-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 8px;
}
.auto-loop-grid div {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 6px;
  background: #101522;
  padding: 9px 10px;
  min-width: 0;
}
.auto-loop-grid b {
  display: block;
  color: #f8fafc;
  font-size: 15px;
  overflow-wrap: anywhere;
}
.auto-loop-grid span,
.auto-loop-latest span {
  color: #94a3b8;
  font-size: 11px;
}
.auto-loop-grid small {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 10px;
}
.auto-loop-job.running {
  border-color: rgba(59, 130, 246, 0.38);
  background: rgba(59, 130, 246, 0.10);
}
.auto-loop-job.planned {
  border-color: rgba(34, 197, 94, 0.18);
}
.auto-loop-job.missing {
  border-color: rgba(239, 68, 68, 0.22);
}
.auto-loop-trigger {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 12px;
}
.auto-loop-trigger.ok {
  color: #bbf7d0;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.18);
}
.auto-loop-trigger.bad {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.18);
}
.automation-dashboard-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.automation-dashboard-card {
  min-width: 0;
  padding: 10px;
  border-radius: 7px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.76);
}
.automation-dashboard-card span {
  display: block;
  color: #94a3b8;
  font-size: 11px;
  margin-bottom: 4px;
}
.automation-dashboard-card b {
  display: block;
  color: #e2e8f0;
  font-size: 15px;
}
.automation-dashboard-card small {
  display: block;
  margin-top: 4px;
  color: #64748b;
  font-size: 10px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.automation-dashboard-card.success { border-color: rgba(34, 197, 94, 0.24); }
.automation-dashboard-card.success b { color: #86efac; }
.automation-dashboard-card.running { border-color: rgba(59, 130, 246, 0.34); background: rgba(59, 130, 246, 0.08); }
.automation-dashboard-card.running b { color: #93c5fd; }
.automation-dashboard-card.failed { border-color: rgba(239, 68, 68, 0.30); }
.automation-dashboard-card.failed b { color: #fca5a5; }
.automation-dashboard-card.planned { border-color: rgba(148, 163, 184, 0.14); }
.pipeline-run-card {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.56);
}
.pipeline-run-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}
.pipeline-run-head b {
  display: block;
  color: #f8fafc;
  font-size: 14px;
}
.pipeline-run-head span,
.pipeline-run-head small {
  color: #94a3b8;
  font-size: 11px;
}
.pipeline-steps {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
}
.pipeline-step {
  min-width: 0;
  padding: 9px 8px;
  border-radius: 7px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: #0f172a;
}
.pipeline-step span {
  display: block;
  color: #94a3b8;
  font-size: 11px;
  margin-bottom: 4px;
}
.pipeline-step b {
  display: block;
  color: #e2e8f0;
  font-size: 14px;
  margin-bottom: 3px;
  overflow-wrap: anywhere;
}
.pipeline-step small {
  display: block;
  color: #64748b;
  font-size: 10px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.pipeline-step.ok { border-color: rgba(34, 197, 94, 0.22); }
.pipeline-step.ok b { color: #86efac; }
.pipeline-step.warn { border-color: rgba(245, 158, 11, 0.26); }
.pipeline-step.warn b { color: #fbbf24; }
.pipeline-step.bad { border-color: rgba(239, 68, 68, 0.25); }
.pipeline-step.bad b { color: #fca5a5; }
.auto-loop-runs {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
}
.auto-loop-run {
  display: grid;
  grid-template-columns: 120px 64px 118px 1fr;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 7px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: #101522;
  font-size: 11px;
}
.auto-loop-run span {
  color: #cbd5e1;
  font-weight: 700;
}
.auto-loop-run b {
  color: #94a3b8;
  font-size: 11px;
}
.auto-loop-run em {
  color: #94a3b8;
  font-style: normal;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.auto-loop-run small {
  min-width: 0;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.auto-loop-run.success b { color: #22c55e; }
.auto-loop-run.running b { color: #60a5fa; }
.auto-loop-run.failed b { color: #ef4444; }
.auto-loop-run.planned b { color: #94a3b8; }
.automation-center-panel {
  margin-top: 12px;
}
.automation-center-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.automation-center-row {
  min-width: 0;
  padding: 8px 10px;
  border-radius: 7px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: #101522;
}
.automation-center-row-head {
  display: grid;
  grid-template-columns: minmax(72px, 1fr) auto auto auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 5px;
  font-size: 11px;
}
.automation-center-row-head b {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #cbd5e1;
}
.automation-center-row-head span {
  color: #94a3b8;
  white-space: nowrap;
}
.automation-center-row-head em {
  padding: 2px 6px;
  border-radius: 999px;
  font-style: normal;
  color: #94a3b8;
  background: rgba(148, 163, 184, 0.10);
  white-space: nowrap;
}
.automation-row-retry {
  height: 22px;
  padding: 0 8px;
  border: 1px solid rgba(248, 113, 113, 0.35);
  border-radius: 6px;
  color: #fecaca;
  background: rgba(239, 68, 68, 0.08);
  font-size: 11px;
  line-height: 20px;
  cursor: pointer;
  white-space: nowrap;
}
.automation-row-retry:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.automation-center-row p {
  min-width: 0;
  margin: 0;
  color: #cbd5e1;
  font-size: 11px;
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.automation-center-row small {
  display: block;
  min-width: 0;
  margin-top: 4px;
  color: #64748b;
  font-size: 10px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.automation-center-row.success { border-color: rgba(34, 197, 94, 0.20); }
.automation-center-row.success .automation-center-row-head em { color: #86efac; background: rgba(34, 197, 94, 0.10); }
.automation-center-row.failed { border-color: rgba(239, 68, 68, 0.28); }
.automation-center-row.failed .automation-center-row-head em { color: #fca5a5; background: rgba(239, 68, 68, 0.10); }
.automation-center-row.planned { border-color: rgba(148, 163, 184, 0.14); }
.automation-center-row.planned .automation-center-row-head em { color: #cbd5e1; }
.auto-loop-latest {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}
.automation-audit-panel {
  background: #141824;
  border: 1px solid #283244;
  border-radius: 8px;
  padding: 14px;
}
.automation-audit-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.automation-audit-head h3 {
  margin: 0;
  color: #f8fafc;
  font-size: 16px;
}
.automation-audit-head span {
  display: block;
  margin-top: 3px;
  color: #94a3b8;
  font-size: 12px;
}
.automation-audit-status {
  flex: 0 0 auto;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 12px;
}
.automation-audit-status.ok {
  color: #bbf7d0;
  background: rgba(34, 197, 94, 0.12);
}
.automation-audit-status.warn {
  color: #fde68a;
  background: rgba(245, 158, 11, 0.14);
}
.automation-audit-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
  gap: 8px;
}
.automation-audit-summary div {
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 6px;
  background: #101522;
}
.automation-audit-summary b {
  display: block;
  color: #e2e8f0;
  font-size: 16px;
  overflow-wrap: anywhere;
}
.automation-audit-summary span {
  color: #94a3b8;
  font-size: 11px;
}
.automation-audit-summary .warn b {
  color: #f59e0b;
}
.automation-audit-findings {
  display: grid;
  gap: 6px;
  margin-top: 12px;
}
.automation-audit-finding {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  padding: 8px 10px;
  border-radius: 7px;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.12);
}
.automation-audit-finding b {
  color: #f8fafc;
  font-size: 12px;
}
.automation-audit-finding span {
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.automation-audit-finding.high {
  border-color: rgba(239, 68, 68, 0.26);
}
.automation-audit-finding.high b {
  color: #fca5a5;
}
.automation-audit-finding.medium b {
  color: #fbbf24;
}
.automation-dup-list {
  margin-top: 12px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 8px;
  overflow: hidden;
}
.automation-dup-title,
.automation-dup-row {
  display: grid;
  grid-template-columns: minmax(90px, 1fr) 70px minmax(140px, 1.4fr);
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  background: #101522;
}
.automation-dup-title {
  display: block;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 700;
  background: #172033;
}
.automation-dup-row + .automation-dup-row {
  border-top: 1px solid rgba(148, 163, 184, 0.08);
}
.automation-dup-row b {
  color: #e2e8f0;
  font-size: 12px;
}
.automation-dup-row span {
  color: #fbbf24;
  font-size: 12px;
}
.automation-dup-row small {
  color: #64748b;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.range-health-panel {
  background: #141824;
  border: 1px solid #283244;
  border-radius: 8px;
  padding: 14px;
}
.range-health-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.range-health-head h3 {
  margin: 0;
  color: #f5f5f5;
  font-size: 16px;
}
.range-health-head span {
  display: block;
  margin-top: 3px;
  color: #8b95a7;
  font-size: 12px;
}
.range-refresh-btn {
  border: 1px solid #334155;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 6px;
  padding: 7px 10px;
  cursor: pointer;
}
.range-refresh-btn.primary {
  border-color: #2563eb;
  background: #1d4ed8;
  color: #ffffff;
}
.range-refresh-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}
.range-health-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.range-health-summary div {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 6px;
  background: #101522;
  padding: 9px 10px;
}
.range-health-summary b {
  display: block;
  color: #f8fafc;
  font-size: 17px;
}
.range-health-summary span {
  color: #94a3b8;
  font-size: 11px;
}
.range-health-summary .warn b {
  color: #f59e0b;
}
.gap-plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.gap-plan-card {
  min-width: 0;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 7px;
  background: #101522;
  padding: 10px;
}
.gap-plan-card.urgent {
  border-color: rgba(245, 158, 11, 0.30);
  background: rgba(245, 158, 11, 0.06);
}
.gap-plan-card.planned {
  border-color: rgba(59, 130, 246, 0.22);
}
.gap-plan-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
}
.gap-plan-top b {
  color: #f8fafc;
  font-size: 13px;
}
.gap-plan-top span {
  color: #fbbf24;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.gap-plan-card small,
.gap-plan-card em {
  display: block;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.35;
  font-style: normal;
  overflow-wrap: anywhere;
}
.gap-plan-card em {
  margin-top: 4px;
  color: #64748b;
}
.gap-plan-examples {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}
.gap-plan-examples span {
  max-width: 100%;
  padding: 3px 6px;
  border-radius: 5px;
  background: rgba(148, 163, 184, 0.10);
  color: #cbd5e1;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.range-table-wrap {
  overflow-x: auto;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.14);
}
.range-health-table {
  width: 100%;
  min-width: 920px;
  border-collapse: collapse;
  background: #111827;
}
.range-health-table th,
.range-health-table td {
  padding: 8px 9px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.10);
  color: #cbd5e1;
  font-size: 12px;
  text-align: left;
  white-space: nowrap;
}
.range-health-table th {
  color: #94a3b8;
  font-weight: 600;
  background: #172033;
}
.range-health-table tr.complete td {
  background: rgba(20, 184, 166, 0.06);
}
.range-health-table tr.problem td {
  background: rgba(245, 158, 11, 0.06);
}
.range-status {
  border-radius: 5px;
  padding: 3px 6px;
  font-size: 11px;
}
.range-status.ok {
  background: rgba(20, 184, 166, 0.15);
  color: #5eead4;
}
.range-status.warn {
  background: rgba(245, 158, 11, 0.14);
  color: #facc15;
}

@media (max-width: 900px) {
  .pipeline-steps {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .auto-loop-head,
  .automation-audit-head,
  .auto-loop-section-title,
  .pipeline-run-head {
    flex-direction: column;
    align-items: stretch;
  }
  .auto-loop-section-title span {
    text-align: left;
  }
  .auto-loop-actions {
    justify-content: flex-start;
  }
  .automation-status-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .auto-loop-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .automation-center-grid {
    grid-template-columns: 1fr;
  }
  .automation-center-row-head {
    grid-template-columns: minmax(0, 1fr) auto auto auto;
  }
  .pipeline-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .auto-loop-run {
    grid-template-columns: 1fr;
    gap: 3px;
  }
  .auto-loop-run small {
    white-space: normal;
  }
  .auto-loop-run em {
    white-space: normal;
  }
  .automation-dup-row {
    grid-template-columns: 1fr;
    gap: 3px;
  }
  .automation-dup-row small {
    white-space: normal;
  }
}
</style>
