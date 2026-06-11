"""
用逻辑回归从历史数据中自动学习因素权重

核心思路:
1. 收集所有finished比赛的factor数据 + 实际结果
2. 用逻辑回归拟合: 实际结果 ~ 因素diff信号
3. 对比回归系数 vs 手动权重，找出被低估/高估的因素
4. 用新权重重新运行模型
"""
import sys, io, json, sqlite3, math
import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

# 收集数据
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

matches = conn.execute(
    "SELECT match_key, home_score, away_score FROM matches "
    "WHERE status='finished' AND home_score IS NOT NULL AND away_score IS NOT NULL"
).fetchall()

print(f"加载 {len(matches)} 场比赛...")

# 因素列表 (只包含numeric因素)
NUMERIC_FACTORS = [
    'standing', 'form', 'home_away', 'home_away_deep', 'euro_odds',
    'asian_handicap', 'over_under', 'prediction', 'expected_goals',
    'poisson', 'h2h', 'schedule_difficulty', 'rest_days', 'elo_rating',
    'possession_counter', 'odds_movement', 'injury',
]

X_data = []
Y_data = []  # 0=home, 1=draw, 2=away
skipped = 0

for m in matches:
    mk = m['match_key']
    if m['home_score'] > m['away_score']:
        y = 0
    elif m['home_score'] == m['away_score']:
        y = 1
    else:
        y = 2

    # 获取因素数据
    factor_rows = conn.execute(
        "SELECT data_type, data_json FROM match_data WHERE match_key=? AND source='factor'",
        (mk,)
    ).fetchall()

    factors = {}
    for fr in factor_rows:
        name = fr['data_type'].replace('factor:', '')
        factors[name] = json.loads(fr['data_json'])

    # 收集每个因素的diff信号
    row = []
    has_data = False
    for fname in NUMERIC_FACTORS:
        f = factors.get(fname, {})
        if f.get('confidence', 0) > 0 and f.get('type') == 'numeric':
            row.append(f.get('diff', 0))
            has_data = True
        else:
            row.append(0)  # 缺失数据填0

    if not has_data:
        skipped += 1
        continue

    X_data.append(row)
    Y_data.append(y)

conn.close()

X = np.array(X_data)
Y = np.array(Y_data)

print(f"有效数据: {len(X)} 场 (跳过 {skipped} 场无数据)")
print(f"类别分布: Home={sum(Y==0)} Draw={sum(Y==1)} Away={sum(Y==2)}")

# 标准化
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.metrics import log_loss, brier_score_loss

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 逻辑回归 (多分类)
lr = LogisticRegression(multi_class='multinomial', solver='lbfgs', max_iter=1000, C=1.0)
lr.fit(X_scaled, Y)

# 交叉验证
cv_scores = cross_val_score(lr, X_scaled, Y, cv=5, scoring='accuracy')
print(f"\n=== 逻辑回归结果 ===")
print(f"交叉验证准确率: {cv_scores.mean()*100:.1f}% ± {cv_scores.std()*100:.1f}%")

# 因素重要性 (系数绝对值)
print(f"\n=== 因素系数 (标准化后) ===")
for i, fname in enumerate(NUMERIC_FACTORS):
    coef_home = lr.coef_[0][i]
    coef_draw = lr.coef_[1][i]
    coef_away = lr.coef_[2][i]
    # 主胜系数：正值=该因素diff越大越可能主胜
    importance = abs(coef_home) + abs(coef_draw) + abs(coef_away)
    print(f"  {fname:25s}: home={coef_home:+.4f} draw={coef_draw:+.4f} away={coef_away:+.4f} |imp|={importance:.4f}")

# 对比手动权重
from fetchers.analysis.models.enhanced_linear import EnhancedLinearModel
manual_weights = EnhancedLinearModel.WEIGHTS

print(f"\n=== 手动权重 vs 回归系数对比 ===")
# 归一化手动权重
total_manual = sum(manual_weights.values())
reg_importance = {}
for i, fname in enumerate(NUMERIC_FACTORS):
    coef_home = lr.coef_[0][i]
    coef_draw = lr.coef_[1][i]
    coef_away = lr.coef_[2][i]
    importance = abs(coef_home) + abs(coef_draw) + abs(coef_away)
    reg_importance[fname] = importance

total_reg = sum(reg_importance.values())

print(f"{'因素':25s} {'手动%':>8s} {'回归%':>8s} {'差距':>8s} {'建议':>10s}")
for fname in NUMERIC_FACTORS:
    manual_pct = manual_weights.get(fname, 0) / total_manual * 100
    reg_pct = reg_importance[fname] / total_reg * 100
    diff = reg_pct - manual_pct
    suggestion = "↑增加" if diff > 2 else "↓减少" if diff < -2 else "  合理"
    print(f"  {fname:25s} {manual_pct:7.1f}% {reg_pct:7.1f}% {diff:+7.1f}% {suggestion}")

# 用逻辑回归的权重优化模型
print(f"\n=== 建议权重 (基于回归系数) ===")
# 将回归系数归一化到总和=1
new_weights = {}
for fname in NUMERIC_FACTORS:
    new_weights[fname] = round(reg_importance[fname] / total_reg, 3)

# 保持总和≈1
total_new = sum(new_weights.values())
for fname in new_weights:
    new_weights[fname] = round(new_weights[fname] / total_new, 3)

for fname, weight in sorted(new_weights.items(), key=lambda x: -x[1]):
    print(f"  {fname:25s}: {weight:.3f}")

# 预测准确率
Y_pred = lr.predict(X_scaled)
accuracy = (Y_pred == Y).mean()
print(f"\n训练集准确率: {accuracy*100:.1f}%")

# Brier Score (对每个类别)
Y_prob = lr.predict_proba(X_scaled)
# one-hot encode Y
Y_onehot = np.zeros((len(Y), 3))
for i, y in enumerate(Y):
    Y_onehot[i, y] = 1
brier = np.mean((Y_prob - Y_onehot) ** 2)
print(f"训练集Brier: {brier:.4f}")
print(f"训练集Log Loss: {log_loss(Y, Y_prob):.4f}")