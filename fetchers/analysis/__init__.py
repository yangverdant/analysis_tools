"""
分析层

两层架构:
1. 因素提取器 (factors/) — 原始数据 → 可量化字段，存DB
2. 概率模型 (models/) — 因素 → 概率预测，存DB

用法:
    from fetchers.analysis import run_all_factors, run_model
    run_all_factors("2026-05-25|arsenal|chelsea", storage)
    run_model("basic_linear", "2026-05-25|arsenal|chelsea", storage)
"""

from fetchers.storage.crud import UnifiedStorage
from .factors import ALL_FACTORS, FACTOR_MAP
from .models import ALL_MODELS, MODEL_MAP


def run_all_factors(match_key: str, storage: UnifiedStorage = None,
                    force: bool = False) -> dict:
    """运行所有因素提取器"""
    if storage is None:
        storage = UnifiedStorage()
    results = {}
    for FactorCls in ALL_FACTORS:
        f = FactorCls()
        try:
            results[f.factor] = f.run(match_key, storage, force=force)
        except Exception as e:
            results[f.factor] = {"factor": f.factor, "confidence": 0.0,
                                  "error": str(e)}
    return results


def run_factor(factor_name: str, match_key: str, storage: UnifiedStorage = None,
               force: bool = False) -> dict:
    """运行单个因素"""
    if storage is None:
        storage = UnifiedStorage()
    if factor_name not in FACTOR_MAP:
        raise ValueError(f"未知因素: {factor_name}, 可用: {list(FACTOR_MAP.keys())}")
    f = FACTOR_MAP[factor_name]()
    return f.run(match_key, storage, force=force)


def run_model(model_name: str, match_key: str, storage: UnifiedStorage = None,
              force: bool = False) -> dict:
    """运行概率模型"""
    if storage is None:
        storage = UnifiedStorage()
    if model_name not in MODEL_MAP:
        raise ValueError(f"未知模型: {model_name}, 可用: {list(MODEL_MAP.keys())}")
    m = MODEL_MAP[model_name]()
    return m.run(match_key, storage, force=force)


def get_match_analysis(match_key: str, storage: UnifiedStorage = None) -> dict:
    """获取某场比赛的完整分析（因素+模型）"""
    if storage is None:
        storage = UnifiedStorage()
    import json

    factors = {}
    conn = storage._conn()
    rows = conn.execute(
        "SELECT data_type, data_json FROM match_data "
        "WHERE match_key=? AND source='factor' AND data_type LIKE 'factor:%'",
        (match_key,)
    ).fetchall()
    conn.close()
    for r in rows:
        name = r["data_type"].replace("factor:", "")
        factors[name] = json.loads(r["data_json"])

    models = {}
    conn = storage._conn()
    rows = conn.execute(
        "SELECT data_type, data_json FROM match_data "
        "WHERE match_key=? AND source='model' AND data_type LIKE 'model:%'",
        (match_key,)
    ).fetchall()
    conn.close()
    for r in rows:
        name = r["data_type"].replace("model:", "")
        models[name] = json.loads(r["data_json"])

    return {"match_key": match_key, "factors": factors, "models": models}