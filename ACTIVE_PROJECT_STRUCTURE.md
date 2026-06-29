# Active Project Structure After Cleanup

This file records the intended active architecture after archiving temporary and one-off files.

## Active Directories

- `backend/app/`: FastAPI app, routers, analytics, lottery, core analysis pipeline.
- `backend/app/intelligence/`: match-driven intelligence orchestration layer for jobs, requirements, artifacts, and packages.
- `frontend/src/`: Vue application source.
- `fetchers/`: reusable collectors and source adapters.
- `data/`: current SQLite databases, mappings, World Cup/national-team datasets. Keep only runtime data here.
- `scripts/`: active operational scripts only, such as oddsfe sync, sporttery sync, backtest, migration, rebuild, and news/national-team sync.
- `config/`, `deploy/`, Docker/nginx/start files: runtime and deployment configuration.
- Local backup root outside the project: `D:\football_backups`.
- Cloud backup root outside the project: `/opt/football_backups`.

## Match Intelligence Backbone

The intelligence module is now the active match-driven workflow:

1. Create match intelligence jobs for today/future matches.
2. Generate per-match data requirements based on competition type.
3. Record collection artifacts from odds, lineup, injuries, news, weather, ranking, Elo, standings, and World Cup context sources.
4. Store a match intelligence package with latest artifacts, artifact history, source, confidence, missing fields, and analysis factors.
5. Run national-team/World-Cup analysis first, then extend to league analysis.
6. Save post-match validation and attribution so correct and incorrect predictions can train later decisions.

## Current Intelligence Behavior

- Daily runs are logged in `intelligence_runs`; manual and scheduled runs use the same workflow.
- `intelligence_jobs` are generated from `lottery_matches` and linked back to canonical `matches` when possible.
- Built-in collectors cover base match info, odds, recent form, Elo, FIFA ranking, tournament context, and data quality.
- External/source collectors cover weather, team news, injuries/suspensions, and expected lineup.
- Injuries and lineup now have local fallback paths through `player_status`, `team_news`, `news_aggregated`, and `match_lineups`.
- World Cup/national-team tournament context now uses league rules, same-series schedule, current-competition history, and recent national-team form when standings are missing.
- Package summaries split `completeness` from `strict_completeness`: fallback evidence can make a job analyzable, while strict coverage still shows how much authoritative data is present.
- APScheduler now runs intelligence jobs using Beijing dates and includes weather, news, injuries, and lineup collectors during refreshes.
- `intelligence_reviews` records the post-match loop: prediction, actual result, correctness, attribution, and the evidence snapshot used for training/review.
- A 02:35 scheduled job syncs validated lottery results into intelligence reviews for the previous Beijing date.
- Finished lottery matches can be backfilled into intelligence jobs, packages, and reviews without network calls, which turns historical results into training samples.
- `training-samples` exposes settled reviews plus package summaries, requirement status, artifact confidence, and attribution for downstream model training.
- `training-summary` aggregates settled samples by attribution, date, analysis view, strict coverage bucket, requirement risk, and wrong-case digest.
- `training-samples/export` writes settled samples to `data/intelligence_exports/*.jsonl` for notebooks or model-training scripts.
- The Vue frontend keeps `体彩中心` as the main cockpit. Match cards now show intelligence coverage, strict coverage, missing evidence, and fallback risk directly in the daily lottery workflow.
- `frontend/src/components/IntelligenceCenter.vue` remains available as a diagnostic/training workbench, but it is no longer a primary sidebar entry.
- Match detail views in `体彩中心` now include the intelligence evidence package: coverage, strict coverage, missing required fields, fallback artifacts, artifact sources, confidence, and next actions.
- `GET /api/v1/intelligence/jobs` now includes package completeness, strict completeness, average confidence, and missing-required summaries for dashboard use.

## Restore Policy

Nothing was deleted. If an archived tool becomes useful, restore it from the matching folder under `D:\football_backups` locally or `/opt/football_backups` on the cloud, then move it into a named active module instead of putting it back as a loose script.

## Cloud Data Policy

Cloud data is the production asset. Sync project code plus safe database deltas; do not blindly overwrite `/opt/football_tools/data/football_v2.db` with local `data/football_v2.db`. Backups must stay outside `/opt/football_tools`, under `/opt/football_backups`.

## Current Intelligence APIs

- `POST /api/v1/intelligence/run-daily`: generate jobs and run the daily intelligence pipeline for a date.
- `POST /api/v1/intelligence/runs`: start and log a manual or background intelligence run.
- `GET /api/v1/intelligence/runs`: list recent manual/scheduled intelligence runs.
- `POST /api/v1/intelligence/jobs/generate`: create intelligence jobs from lottery matches.
- `POST /api/v1/intelligence/jobs/{job_id}/link-match`: link a job back to the canonical `matches` table.
- `POST /api/v1/intelligence/jobs/{job_id}/collect/builtin`: collect local artifacts from `football_v2.db`.
- `POST /api/v1/intelligence/jobs/{job_id}/collect/external`: collect network/source artifacts such as weather, news, injuries and lineup.
- `POST /api/v1/intelligence/jobs/{job_id}/package`: rebuild the match intelligence package.
- `GET /api/v1/intelligence/reviews`: list post-match reviews.
- `POST /api/v1/intelligence/reviews/auto`: auto-review jobs for a date from lottery validation/results.
- `POST /api/v1/intelligence/jobs/{job_id}/reviews/auto`: auto-review one job from lottery validation/results.
- `POST /api/v1/intelligence/jobs/{job_id}/reviews`: add a manual review.
- `POST /api/v1/intelligence/backfill-finished`: backfill finished lottery matches into jobs, packages, and reviews.
- `GET /api/v1/intelligence/training-samples`: list settled intelligence review samples for training and error analysis.
- `GET /api/v1/intelligence/training-summary`: aggregate training samples for model diagnostics.
- `POST /api/v1/intelligence/training-samples/export`: export training samples as JSONL under `data/intelligence_exports/`.
