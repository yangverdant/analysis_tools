"""CLV赔率更新 — 14:00用oddsfe重采赔率，检测异动

流程:
1. 获取今日未开赛的比赛
2. 用oddsfe重新采集Pinnacle赔率(snapshot_type='midday')
3. 对比 opening vs midday
4. >5%异动标记CLV信号
5. 写入lottery_odds(snapshot_type='midday')
"""
import json
import logging
import sqlite3
from datetime import date, datetime
from typing import Dict, List, Optional

from pathlib import Path

from .time_utils import today_beijing, tomorrow_beijing

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH_DEFAULT = str(PROJECT_ROOT / 'data' / 'football_v2.db')


def clv_update(state=None, db_path: str = None, match_date: date = None) -> dict:
    """CLV赔率更新主函数 — 北京时间窗口"""
    db_path = db_path or DB_PATH_DEFAULT
    today = today_beijing()
    tomorrow = tomorrow_beijing()

    # 先同步oddsfe增量(获取最新赛果+赔率)
    _sync_oddsfe_before_clv(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # 1. 获取今日未开赛的比赛(北京时间窗口)
        matches = conn.execute("""
            SELECT lottery_match_id, match_date, sell_status
            FROM lottery_matches
            WHERE (
                match_date = ?
                OR (match_date = ? AND substr(match_time, 1, 2) < '12')
            ) AND sell_status != 'closed'
        """, (today, tomorrow)).fetchall()

        if not matches:
            logger.info(f"No open matches for CLV update on {match_date}")
            return {"success": True, "date": str(match_date), "updated": 0, "signals": [], "route": "normal"}

        # 2. 用oddsfe重新采集赔率(写入snapshot_type='midday')
        import sys
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from backend.app.core.collect import _fetch_and_save_oddsfe_odds
        odds_result = _fetch_and_save_oddsfe_odds(db_path, match_date, snapshot_type='midday')

        if not odds_result.get('success'):
            logger.warning(f"CLV oddsfe fetch failed: {odds_result.get('error')}")
            return {"success": False, "date": str(match_date), "error": odds_result.get('error', 'oddsfe_failed'), "route": "normal"}

        # 3. 对比opening vs midday赔率
        signals = []
        updated = 0

        for match in matches:
            lm_id = match["lottery_match_id"]

            # 获取opening赔率(opening > current > 最早的)
            opening = conn.execute("""
                SELECT odds_data FROM lottery_odds
                WHERE lottery_match_id = ? AND play_type = 'spf'
                AND snapshot_type IN ('opening', 'current')
                ORDER BY
                    CASE snapshot_type WHEN 'opening' THEN 0 ELSE 1 END,
                    created_at ASC
                LIMIT 1
            """, (lm_id,)).fetchone()

            # 获取midday赔率(刚采集的)
            midday = conn.execute("""
                SELECT odds_data FROM lottery_odds
                WHERE lottery_match_id = ? AND play_type = 'spf'
                AND snapshot_type = 'midday'
                ORDER BY created_at DESC LIMIT 1
            """, (lm_id,)).fetchone()

            if not opening or not midday:
                continue

            try:
                opening_data = json.loads(opening["odds_data"]) if isinstance(opening["odds_data"], str) else opening["odds_data"]
                midday_data = json.loads(midday["odds_data"]) if isinstance(midday["odds_data"], str) else midday["odds_data"]

                # 4. 检测异动
                signal = detect_clv_signal(lm_id, opening_data, midday_data)
                if signal:
                    signals.append(signal)
                    logger.info(f"CLV signal: {lm_id} {signal['direction']} delta={signal['delta']:.2%} ({signal['strength']})")

                # 5. 记录赔率变动
                if opening["odds_data"] != midday["odds_data"]:
                    movement = compute_movement(opening_data, midday_data)
                    conn.execute("""
                        UPDATE lottery_odds
                        SET odds_movement = ?, latest_odds = ?
                        WHERE lottery_match_id = ? AND play_type = 'spf'
                        AND snapshot_type = 'midday'
                    """, (
                        json.dumps(movement, ensure_ascii=False),
                        json.dumps(midday_data, ensure_ascii=False),
                        lm_id,
                    ))
                    updated += 1

            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"CLV parse error for {lm_id}: {e}")

        conn.commit()

        logger.info(f"CLV update: {updated} matches updated, {len(signals)} signals detected")

        # 结算bet_records(14点时上午的比赛可能已有结果)
        try:
            from .validate import _settle_bets
            settlement = _settle_bets(db_path)
            if settlement.get('settled', 0) > 0:
                logger.info(f"CLV期间结算: {settlement}")
        except Exception as e:
            logger.debug(f"CLV结算失败: {e}")

        return {
            "success": True,
            "date": str(match_date),
            "total_matches": len(matches),
            "updated": updated,
            "signals": signals,
            "settlement": settlement if 'settlement' in dir() else None,
            "route": "normal"
        }

    except Exception as e:
        logger.error(f"CLV update failed: {e}")
        conn.rollback()
        return {"success": False, "date": str(match_date), "error": str(e), "route": "normal"}
    finally:
        conn.close()


def detect_clv_signal(match_id: str, opening: dict, current: dict, threshold: float = 0.05) -> Optional[dict]:
    """检测CLV信号 — 赔率异动>threshold

    CLV(Closing Line Value): 赔率向模型方向移动 → 增强信心
    """
    # 提取SPF赔率 — 支持 '3'/'1'/'0' 和 'home'/'draw'/'away' 两种键
    open_home = opening.get("3") or opening.get("home") or opening.get("win") or 0
    open_draw = opening.get("1") or opening.get("draw") or 0
    open_away = opening.get("0") or opening.get("away") or opening.get("loss") or 0

    cur_home = current.get("3") or current.get("home") or current.get("win") or 0
    cur_draw = current.get("1") or current.get("draw") or 0
    cur_away = current.get("0") or current.get("away") or current.get("loss") or 0

    if not all([open_home, open_draw, open_away, cur_home, cur_draw, cur_away]):
        return None

    # 计算隐含概率变化
    def implied_probs(home, draw, away):
        h, d, a = 1/home, 1/draw, 1/away
        total = h + d + a
        return h/total, d/total, a/total

    op = implied_probs(open_home, open_draw, open_away)
    cp = implied_probs(cur_home, cur_draw, cur_away)

    # 找最大异动方向
    deltas = {
        "home_win": cp[0] - op[0],
        "draw": cp[1] - op[1],
        "away_win": cp[2] - op[2]
    }

    max_dir = max(deltas, key=lambda k: abs(deltas[k]))
    max_delta = abs(deltas[max_dir])

    if max_delta < threshold:
        return None

    return {
        "match_id": match_id,
        "direction": max_dir,
        "delta": round(max_delta, 4),
        "opening_probs": {k: round(v, 4) for k, v in zip(["home_win", "draw", "away_win"], op)},
        "current_probs": {k: round(v, 4) for k, v in zip(["home_win", "draw", "away_win"], cp)},
        "signal": "clv_positive" if deltas[max_dir] > 0 else "clv_negative",
        "strength": "strong" if max_delta > 0.10 else "moderate" if max_delta > 0.07 else "weak"
    }


def compute_movement(opening: dict, current: dict) -> dict:
    """计算赔率变动方向"""
    open_home = opening.get("3") or opening.get("home") or opening.get("win") or 0
    cur_home = current.get("3") or current.get("home") or current.get("win") or 0

    if open_home and cur_home:
        home_dir = "down" if cur_home < open_home else "up" if cur_home > open_home else "stable"
    else:
        home_dir = "unknown"

    return {"home_direction": home_dir, "opening": opening, "current": current}


def _sync_oddsfe_before_clv(db_path: str) -> dict:
    """CLV前执行oddsfe增量同步 — 获取最新赛果和赔率变动"""
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(db_path).parent.parent
    oddsfe_path = str(Path(db_path).parent / 'oddsfe_merged.db')
    sync_script = str(project_root / 'scripts' / 'oddsfe_sync.py')

    if not Path(oddsfe_path).exists() or not Path(sync_script).exists():
        return {'status': 'skipped'}

    try:
        result = subprocess.run(
            [sys.executable, sync_script,
             '--oddsfe', oddsfe_path,
             '--db', db_path,
             '--incremental', '--days', '2'],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            logger.info('CLV前oddsfe增量同步完成')
            return {'status': 'ok'}
        else:
            logger.debug('CLV前oddsfe同步失败(非阻塞): %s', result.stderr[:100] if result.stderr else '')
            return {'status': 'error'}
    except Exception as e:
        logger.debug('CLV前oddsfe同步异常(非阻塞): %s', e)
        return {'status': 'error'}
