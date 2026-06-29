param(
    [string]$HostName = "1.117.70.20",
    [string]$User = "ubuntu",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\football_server",
    [string]$RemoteDir = "/opt/football_tools",
    [switch]$SkipBuild,
    [switch]$NoRestart,
    [switch]$ApplySnapshotCleanup
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not (Test-Path $KeyPath)) {
    throw "SSH key not found: $KeyPath"
}

if (-not $SkipBuild) {
    Push-Location "frontend"
    try {
        npm run build
    }
    finally {
        Pop-Location
    }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = if ($env:FOOTBALL_BACKUP_DIR) {
    $env:FOOTBALL_BACKUP_DIR
} else {
    Join-Path (Split-Path $ProjectRoot -Parent) "football_backups"
}
$packageDir = Join-Path $backupRoot "sync_tmp"
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
$package = Join-Path $packageDir "football_code_sync_$stamp.tar.gz"
$remotePackage = "/tmp/football_code_sync_$stamp.tar.gz"

$include = @(
    "ACTIVE_PROJECT_STRUCTURE.md",
    "backend/app",
    "backend/run.py",
    "backend/requirements.txt",
    "config/config.yaml",
    "config/loader.py",
    "fetchers/odds_feed_api/__init__.py",
    "fetchers/odds_feed_api/align_oddsfe_csv.py",
    "fetchers/odds_feed_api/config.py",
    "fetchers/odds_feed_api/get_odds.py",
    "fetchers/odds_feed_api/oddsfe_auth.py",
    "fetchers/odds_feed_api/oddsfe_clean_merge.py",
    "fetchers/odds_feed_api/oddsfe_collector.py",
    "fetchers/odds_feed_api/oddsfe_ou_concurrent.py",
    "fetchers/odds_feed_api/oddsfe_realtime_detail.py",
    "fetchers/odds_feed_api/oddsfe_realtime_detail_v2.py",
    "fetchers/odds_feed_api/oddsfe_realtime_refresh.py",
    "fetchers/odds_feed_api/oddsfe_realtime_schedule.py",
    "frontend/dist",
    "scripts/audit_auto_loop_health.py",
    "scripts/audit_collection_channels.py",
    "scripts/audit_data_foundation.py",
    "scripts/audit_match_input_fingerprints.py",
    "scripts/audit_ou_goal_axis.py",
    "scripts/audit_prediction_consistency.py",
    "scripts/backfill_data_foundation.py",
    "scripts/backfill_lottery_results_from_oddsfe.py",
    "scripts/build_league_calibration.py",
    "scripts/build_ou_line_calibration.py",
    "scripts/build_similar_match_cases.py",
    "scripts/build_team_match_facts.py",
    "scripts/cloud_automation_tick.sh",
    "scripts/cloud_learning_refresh.sh",
    "scripts/compare_reanalysis_backup.py",
    "scripts/cleanup_bqc_axis_adjustments.py",
    "scripts/cleanup_foundation_snapshots.py",
    "scripts/cleanup_stale_analysis_reports.py",
    "scripts/diagnose_prediction_errors.py",
    "scripts/import_data_delta_safe.py",
    "scripts/mark_duplicate_reports_stale.py",
    "scripts/mark_stale_collection_runs.py",
    "scripts/migrate_data_foundation.py",
    "scripts/model_change_gate.py",
    "scripts/reanalyze_unstarted_after_learning.py",
    "scripts/rebuild_lottery_validation.py",
    "scripts/repair_lottery_market_fields.py",
    "scripts/repair_lottery_team_canonical_ids.py",
    "scripts/repair_lottery_team_mappings.py",
    "scripts/repair_world_cup_lottery_bridge.py",
    "scripts/run_auto_gap_segment.py",
    "scripts/run_automation_center.py",
    "scripts/run_automation_task.py",
    "scripts/run_idle_historical_backfill.py",
    "scripts/run_learning_refresh.py",
    "scripts/run_model_reanalysis_stage.py",
    "scripts/run_segmented_auto_loop.py",
    "scripts/settle_reanalysis_changes.py",
    "scripts/sync_finished_results.py",
    "scripts/sync_national_teams_multi_channel.py",
    "scripts/sync_oddsfe_event_details.py",
    "scripts/sync_oddsfe_ou_lines.py",
    "scripts/sync_results_manual.py",
    "scripts/sync_sporttery_matches.py",
    "deploy/cloud_post_sync_maintenance.sh",
    "docs/项目运行同步与自动化手册.md"
)

$existing = $include | Where-Object { Test-Path $_ }
if (-not $existing) {
    throw "No sync paths found."
}

tar -czf $package --exclude="__pycache__" --exclude="*.pyc" --exclude="*.db" --exclude="*.sqlite" --exclude="*.csv" --exclude="*.bak" --exclude="*.backup" --exclude="*_backup.*" @existing

scp -i $KeyPath -o ConnectTimeout=20 $package "${User}@${HostName}:${remotePackage}"

$cleanupArg = if ($ApplySnapshotCleanup) { "--apply-snapshot-cleanup" } else { "" }
$restartArg = if ($NoRestart) { "--no-restart" } else { "" }
$remoteCommand = @"
set -e
sudo mkdir -p '$RemoteDir'
sudo tar -xzf '$remotePackage' -C '$RemoteDir'
rm -f '$remotePackage'
sudo chmod +x '$RemoteDir/deploy/cloud_post_sync_maintenance.sh'
cd '$RemoteDir'
sudo bash deploy/cloud_post_sync_maintenance.sh $cleanupArg $restartArg
"@

ssh -i $KeyPath -o ConnectTimeout=20 "${User}@${HostName}" $remoteCommand

Write-Host "Synced code package: $package"
