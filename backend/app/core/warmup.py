"""热启动 — 用oddsfe 229K历史数据做离线校准

数据源优先级:
1. oddsfe CSV (229K场, 含多联赛/国家队/友谊赛)
2. DB match_odds (13K场, 仅联赛)

输出:
- 赔率基线准确率(按场景/赔率区间)
- 初始因子权重(odds_heavy/balanced/model_heavy)
- 赔率置信度校准曲线
- 写入model_weights + model_accuracy
"""
import csv
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CSV_PATH = PROJECT_ROOT / 'fetchers' / 'odds_feed_api' / 'oddsfe_data_full_v2.csv'
DB_PATH_DEFAULT = str(PROJECT_ROOT / 'data' / 'football_v2.db')

# 赔率区间 → 校准用
ODDS_BUCKETS = [
    ('<1.30', 0, 1.30),
    ('1.30-1.60', 1.30, 1.60),
    ('1.60-2.00', 1.60, 2.00),
    ('2.00-3.00', 2.00, 3.00),
    ('>3.00', 3.00, 999),
]

# 场景分类: 用category_id粗分
# oddsfe CSV缺少tournament_name, 用tournament_id范围推断
# 国家队: 通常tournament_id > 10000 (世界杯/洲际/友谊赛)
NATIONAL_TOURNAMENT_IDS = set(range(1, 200))  # 小ID通常是大赛


def run_warmup(db_path: str = None, csv_path: str = None) -> dict:
    """热启动主函数 — 用历史数据校准初始参数"""
    db_path = db_path or DB_PATH_DEFAULT
    csv_path = csv_path or str(CSV_PATH)

    logger.info('=== 热启动: 开始校准 ===')

    # 1. 从CSV读取历史数据
    csv_result = _calibrate_from_csv(csv_path)

    # 2. 从DB补充(如果CSV不足)
    db_result = None
    if csv_result['sample_size'] < 1000:
        logger.info('CSV数据不足, 从DB补充')
        db_result = _calibrate_from_db(db_path)

    # 合并结果
    result = _merge_results(csv_result, db_result)

    # 3. 确定初始权重
    weights = _determine_initial_weights(result)
    result['initial_weights'] = weights['weights']
    result['mode'] = weights['mode']

    # 4. 写入DB
    conn = sqlite3.connect(db_path)
    try:
        _save_initial_weights(conn, weights, result['sample_size'], result['odds_accuracy'])
        _save_scene_baselines(conn, result.get('scene_breakdown', {}))
        _save_odds_calibration(conn, result.get('odds_calibration', {}))
        conn.commit()
    except Exception as e:
        logger.error(f'保存校准结果失败: {e}')
        conn.rollback()
    finally:
        conn.close()

    logger.info(f'热启动完成: accuracy={result["odds_accuracy"]:.2%}, mode={result["mode"]}, '
                f'samples={result["sample_size"]}')
    return result


def _calibrate_from_csv(csv_path: str) -> dict:
    """从oddsfe CSV校准 — 229K场"""
    csv_file = Path(csv_path)
    if not csv_file.exists():
        logger.warning(f'CSV不存在: {csv_path}')
        return {'sample_size': 0, 'odds_accuracy': 0, 'scene_breakdown': {}, 'odds_calibration': {}}

    correct = 0
    total = 0
    scene_stats = {}  # scene -> {correct, total}
    bucket_stats = {}  # bucket -> {correct, total, draw_total, draw_correct}
    # 按赔率偏差校准: predicted prob vs actual freq
    prob_bins = {}  # 0.0-0.1, 0.1-0.2, ... -> {predicted_sum, actual_count, total}

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('event_status') != 'FINISHED':
                    continue
                ew = row.get('event_winner', '')
                if ew not in ('0', '1', '2'):
                    continue

                # 解析赔率
                odds = _parse_main_out(row)
                if not odds:
                    continue
                o0, o1, o2 = odds

                total += 1

                # 隐含概率
                imp_h = 1.0 / o0
                imp_d = 1.0 / o1
                imp_a = 1.0 / o2
                imp_total = imp_h + imp_d + imp_a
                probs = {'0': imp_h / imp_total, '1': imp_d / imp_total, '2': imp_a / imp_total}

                # Argmax
                predicted = max(probs, key=probs.get)
                if predicted == ew:
                    correct += 1

                # 场景分类(粗略)
                scene = _infer_scene_from_csv(row)
                if scene not in scene_stats:
                    scene_stats[scene] = {'correct': 0, 'total': 0}
                scene_stats[scene]['total'] += 1
                if predicted == ew:
                    scene_stats[scene]['correct'] += 1

                # 赔率区间(按主队赔率)
                home_odds = o0
                bucket_name = _get_odds_bucket(home_odds)
                if bucket_name not in bucket_stats:
                    bucket_stats[bucket_name] = {'correct': 0, 'total': 0, 'draw_total': 0, 'draw_correct': 0}
                bucket_stats[bucket_name]['total'] += 1
                if predicted == ew:
                    bucket_stats[bucket_name]['correct'] += 1
                if ew == '1':
                    bucket_stats[bucket_name]['draw_total'] += 1
                    if probs['1'] > probs['0'] and probs['1'] > probs['2']:
                        bucket_stats[bucket_name]['draw_correct'] += 1

                # 概率校准: 记录每个概率bin的实际频率
                for outcome, prob in probs.items():
                    bin_idx = min(int(prob * 10), 9)
                    if bin_idx not in prob_bins:
                        prob_bins[bin_idx] = {'predicted_sum': 0.0, 'actual_count': 0, 'total': 0}
                    prob_bins[bin_idx]['predicted_sum'] += prob
                    prob_bins[bin_idx]['total'] += 1
                    if outcome == ew:
                        prob_bins[bin_idx]['actual_count'] += 1

    except Exception as e:
        logger.error(f'CSV读取失败: {e}')
        return {'sample_size': total, 'odds_accuracy': correct / max(total, 1),
                'scene_breakdown': {}, 'odds_calibration': {}}

    odds_accuracy = correct / total if total > 0 else 0

    # 场景breakdown
    scene_breakdown = {}
    for scene, s in scene_stats.items():
        scene_breakdown[scene] = {
            'accuracy': round(s['correct'] / s['total'], 4) if s['total'] > 0 else 0,
            'sample_size': s['total'],
        }

    # 赔率校准
    odds_calibration = {}
    for bucket_name, s in bucket_stats.items():
        odds_calibration[bucket_name] = {
            'accuracy': round(s['correct'] / s['total'], 4) if s['total'] > 0 else 0,
            'draw_rate': round(s['draw_total'] / s['total'], 4) if s['total'] > 0 else 0,
            'sample_size': s['total'],
        }

    # 概率校准曲线
    prob_calibration = {}
    for bin_idx in sorted(prob_bins.keys()):
        b = prob_bins[bin_idx]
        if b['total'] > 0:
            avg_predicted = b['predicted_sum'] / b['total']
            actual_freq = b['actual_count'] / b['total']
            prob_calibration[f'{avg_predicted:.2f}'] = {
                'predicted': round(avg_predicted, 3),
                'actual': round(actual_freq, 3),
                'samples': b['total'],
            }

    return {
        'sample_size': total,
        'odds_accuracy': round(odds_accuracy, 4),
        'scene_breakdown': scene_breakdown,
        'odds_calibration': odds_calibration,
        'prob_calibration': prob_calibration,
    }


def _calibrate_from_db(db_path: str) -> dict:
    """从DB match_odds_normalized校准"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT m.home_goals, m.away_goals,
                   mo.home as ps_home, mo.draw as ps_draw, mo.away as ps_away,
                   COALESCE(m.competition_type, l.competition_type) as competition_type,
                   COALESCE(m.participant_type, l.participant_type) as participant_type
            FROM matches m
            JOIN match_odds_normalized mo ON m.match_id = mo.match_id
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE m.status = 'finished'
            AND m.home_goals IS NOT NULL
            AND mo.bookmaker = 'PINNACLE' AND mo.snapshot_type = 'prematch' AND mo.market = '1X2'
            AND mo.home > 1 AND mo.draw > 1 AND mo.away > 1
        """).fetchall()
        conn.close()
    except Exception as e:
        logger.debug(f'DB校准数据获取失败: {e}')
        return {'sample_size': 0, 'odds_accuracy': 0, 'scene_breakdown': {}}

    if not rows:
        return {'sample_size': 0, 'odds_accuracy': 0, 'scene_breakdown': {}}

    correct = 0
    total = 0
    scene_stats = {}

    for row in rows:
        home_p = 1.0 / row['ps_home']
        draw_p = 1.0 / row['ps_draw']
        away_p = 1.0 / row['ps_away']
        total_p = home_p + draw_p + away_p
        probs = {'home_win': home_p / total_p, 'draw': draw_p / total_p, 'away_win': away_p / total_p}

        odds_rec = max(probs, key=probs.get)
        if row['home_goals'] > row['away_goals']:
            actual = 'home_win'
        elif row['home_goals'] < row['away_goals']:
            actual = 'away_win'
        else:
            actual = 'draw'

        total += 1
        if odds_rec == actual:
            correct += 1

        scene = row['competition_type'] or 'unknown'
        p_type = row['participant_type'] or 'club'
        key = f'{scene}_{p_type}'
        if key not in scene_stats:
            scene_stats[key] = {'correct': 0, 'total': 0}
        scene_stats[key]['total'] += 1
        if odds_rec == actual:
            scene_stats[key]['correct'] += 1

    scene_breakdown = {}
    for key, s in scene_stats.items():
        scene_breakdown[key] = {
            'accuracy': round(s['correct'] / s['total'], 4) if s['total'] > 0 else 0,
            'sample_size': s['total'],
        }

    return {
        'sample_size': total,
        'odds_accuracy': round(correct / total, 4) if total > 0 else 0,
        'scene_breakdown': scene_breakdown,
    }


def _merge_results(csv_result: dict, db_result: Optional[dict]) -> dict:
    """合并CSV和DB结果"""
    if not db_result or db_result['sample_size'] == 0:
        return csv_result

    # CSV为主, DB补充scene_breakdown
    merged = dict(csv_result)
    for key, stats in db_result.get('scene_breakdown', {}).items():
        if key not in merged.get('scene_breakdown', {}):
            merged.setdefault('scene_breakdown', {})[key] = stats

    return merged


def _determine_initial_weights(result: dict) -> dict:
    """根据校准结果确定初始权重"""
    accuracy = result.get('odds_accuracy', 0)

    # oddsfe 229K场基线是54.13%
    # 如果赔率基线>50% → odds_heavy
    # 如果赔率基线45-50% → balanced
    # 如果赔率基线<45% → model_heavy(不太可能)
    if accuracy >= 0.50:
        mode = 'odds_heavy'
        weights = {
            'elo': 0.15, 'poisson': 0.15, 'h2h': 0.08,
            'form': 0.10, 'home_away': 0.07, 'motivation': 0.05,
            'news_factors': 0.05, 'odds': 0.35,
        }
    elif accuracy >= 0.45:
        mode = 'balanced'
        weights = {
            'elo': 0.20, 'poisson': 0.20, 'h2h': 0.10,
            'form': 0.12, 'home_away': 0.08, 'motivation': 0.07,
            'news_factors': 0.05, 'odds': 0.18,
        }
    else:
        mode = 'model_heavy'
        weights = {
            'elo': 0.22, 'poisson': 0.25, 'h2h': 0.10,
            'form': 0.15, 'home_away': 0.10, 'motivation': 0.08,
            'news_factors': 0.05, 'odds': 0.05,
        }

    # 根据场景breakdown微调
    scene_breakdown = result.get('scene_breakdown', {})
    # 如果友谊赛准确率低 → 增加odds权重
    for key, stats in scene_breakdown.items():
        if 'friendly' in key and stats.get('accuracy', 0) < 0.40:
            weights['odds'] = min(weights.get('odds', 0.35) + 0.05, 0.45)

    return {'mode': mode, 'weights': weights}


def _save_initial_weights(conn, weights_result: dict, sample_size: int, accuracy: float):
    """保存初始权重到model_weights"""
    weights = weights_result['weights']
    mode = weights_result['mode']

    conn.execute("UPDATE model_weights SET is_active = 0 WHERE is_active = 1")
    conn.execute("""
        INSERT OR REPLACE INTO model_weights
        (version, elo_weight, poisson_weight, h2h_weight, form_weight,
         home_away_weight, motivation_weight, news_factors_weight,
         sample_size, accuracy_rate, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        f'warmup_{mode}',
        weights.get('elo', 0.15), weights.get('poisson', 0.15),
        weights.get('h2h', 0.08), weights.get('form', 0.10),
        weights.get('home_away', 0.07), weights.get('motivation', 0.05),
        weights.get('news_factors', 0.05),
        sample_size, accuracy,
        datetime.now().isoformat()
    ))


def _save_scene_baselines(conn, scene_breakdown: dict):
    """保存场景基线到model_accuracy"""
    for key, stats in scene_breakdown.items():
        parts = key.rsplit('_', 1)
        scene = parts[0] if len(parts) > 1 else key
        p_type = parts[1] if len(parts) > 1 else 'club'

        conn.execute("""
            INSERT OR REPLACE INTO model_accuracy
            (scene_type, participant_type, total_matches,
             model_accuracy, odds_baseline_accuracy,
             model_brier, odds_brier, period, calculated_at)
            VALUES (?, ?, ?, 0, ?, 0, 0, 'warmup', ?)
        """, (
            scene, p_type, stats.get('sample_size', 0),
            stats.get('accuracy', 0),
            datetime.now().isoformat()
        ))


def _save_odds_calibration(conn, odds_calibration: dict):
    """保存赔率校准曲线 — 写入config表或json"""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS odds_calibration (
                cal_key TEXT PRIMARY KEY,
                cal_data TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            INSERT OR REPLACE INTO odds_calibration (cal_key, cal_data, updated_at)
            VALUES ('odds_bucket_accuracy', ?, ?)
        """, (json.dumps(odds_calibration, ensure_ascii=False), datetime.now().isoformat()))
    except Exception as e:
        logger.debug(f'保存赔率校准失败: {e}')


def _parse_main_out(row: dict) -> Optional[Tuple[float, float, float]]:
    """解析main_out_0/1/2赔率"""
    m0 = row.get('main_out_0', '')
    m1 = row.get('main_out_1', '')
    m2 = row.get('main_out_2', '')
    try:
        o0 = float(m0.split()[0]) if m0.strip() else 0
        o1 = float(m1.split()[0]) if m1.strip() else 0
        o2 = float(m2.split()[0]) if m2.strip() else 0
    except (ValueError, IndexError):
        return None
    if o0 < 1.01 or o1 < 1.01 or o2 < 1.01:
        return None
    return (o0, o1, o2)


def _infer_scene_from_csv(row: dict) -> str:
    """从CSV行推断赛事场景(粗略)"""
    # CSV缺少tournament_name，用category推断
    cat_id = row.get('category_id', '')
    cat_name = (row.get('category_name', '') or '').lower()
    tournament_id = row.get('tournament_id', '')

    # 国家队: category通常含"International"或特定ID
    if 'international' in cat_name:
        return 'international_national'

    # 用category_name中的关键词
    if 'cup' in cat_name or 'copa' in cat_name:
        return 'cup_club'

    if 'friendly' in cat_name:
        return 'friendly_national'

    # 大多数无category信息 → 默认league_club
    return 'league_club'


def _get_odds_bucket(home_odds: float) -> str:
    """按主队赔率分桶"""
    for name, lo, hi in ODDS_BUCKETS:
        if lo <= home_odds < hi:
            return name
    return '>3.00'
