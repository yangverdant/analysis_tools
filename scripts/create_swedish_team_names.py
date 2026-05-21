"""
创建瑞典超球队中英文对照表
"""
import pandas as pd
import json
import os

# 瑞典超球队中英文对照
swedish_teams = {
    "AIK": "AIK索尔纳",
    "Brommapojkarna": "布罗马波伊卡纳",
    "Degerfors": "代格福什",
    "Djurgarden": "尤尔加登",
    "Elfsborg": "埃尔夫斯堡",
    "GAIS": "哥德堡GAIS",
    "Goteborg": "哥德堡",
    "Hacken": "赫根",
    "Halmstad": "哈尔姆斯塔德",
    "Hammarby": "哈马比",
    "Malmo FF": "马尔默",
    "Mjallby": "米亚尔比",
    "Norrkoping": "北雪平",
    "Oster": "奥斯特",
    "Sirius": "天狼星",
    "Varnamo": "瓦尔纳莫"
}

# 保存为JSON
output_dir = 'd:/football_tools/data/09_other_data'
os.makedirs(output_dir, exist_ok=True)

json_file = os.path.join(output_dir, 'swedish_teams_names.json')
with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(swedish_teams, f, ensure_ascii=False, indent=2)

print(f"保存JSON: {json_file}")

# 保存为CSV
csv_data = []
for en, cn in swedish_teams.items():
    csv_data.append({
        'name_en': en,
        'name_cn': cn
    })

df = pd.DataFrame(csv_data)
csv_file = os.path.join(output_dir, 'swedish_teams_names.csv')
df.to_csv(csv_file, index=False, encoding='utf-8-sig')

print(f"保存CSV: {csv_file}")

# 显示对照表
print("\n瑞典超球队中英文对照表:")
print("-" * 40)
for en, cn in swedish_teams.items():
    print(f"{en:20} -> {cn}")

print(f"\n共 {len(swedish_teams)} 支球队")
