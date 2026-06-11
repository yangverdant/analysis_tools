"""体彩赛前情报分析Pipeline

流程:
1. 获取体彩开售比赛+赔率
2. 中文队名→英文队名映射
3. 对每场国际赛采集5维度赛前情报
4. 用情报修正赔率隐含概率
5. 输出修正后的预测建议

使用:
    python -m fetchers.scripts.pre_match_pipeline
    python -m fetchers.scripts.pre_match_pipeline 2026-06-05
"""

import json
import sys
from datetime import date
from typing import Optional

from fetchers.sporttery.get_matches import get_match_list
from fetchers.pre_match.collector import PreMatchCollector


# 中文队名→英文队名映射(体彩用中文名,情报系统用英文名)
CN_TO_EN = {
    # 国际赛常见
    '中国': 'China', '新加坡': 'Singapore', '韩国': 'South Korea', '日本': 'Japan',
    '澳大利亚': 'Australia', '伊朗': 'Iran', '沙特阿拉伯': 'Saudi Arabia',
    '伊拉克': 'Iraq', '阿联酋': 'United Arab Emirates', '乌兹别克斯坦': 'Uzbekistan',
    '卡塔尔': 'Qatar', '阿曼': 'Oman', '巴林': 'Bahrain',
    # 欧洲
    '英格兰': 'England', '法国': 'France', '德国': 'Germany', '西班牙': 'Spain',
    '意大利': 'Italy', '葡萄牙': 'Portugal', '荷兰': 'Netherlands',
    '比利时': 'Belgium', '克罗地亚': 'Croatia', '塞尔维亚': 'Serbia',
    '瑞士': 'Switzerland', '丹麦': 'Denmark', '瑞典': 'Sweden',
    '挪威': 'Norway', '波兰': 'Poland', '奥地利': 'Austria',
    '捷克': 'Czech Republic', '土耳其': 'Turkey', '乌克兰': 'Ukraine',
    '苏格兰': 'Scotland', '爱尔兰': 'Ireland', '威尔士': 'Wales',
    '希腊': 'Greece', '罗马尼亚': 'Romania', '匈牙利': 'Hungary',
    '斯洛伐克': 'Slovakia', '保加利亚': 'Bulgaria', '芬兰': 'Finland',
    '黑山': 'Montenegro', '阿尔巴尼亚': 'Albania', '斯洛文尼亚': 'Slovenia',
    '北爱尔兰': 'Northern Ireland', '冰岛': 'Iceland', '俄罗斯': 'Russia',
    # 南美
    '巴西': 'Brazil', '阿根廷': 'Argentina', '哥伦比亚': 'Colombia',
    '乌拉圭': 'Uruguay', '智利': 'Chile', '秘鲁': 'Peru',
    '厄瓜多尔': 'Ecuador', '巴拉圭': 'Paraguay', '玻利维亚': 'Bolivia',
    '委内瑞拉': 'Venezuela',
    # 北美
    '美国': 'United States', '墨西哥': 'Mexico', '加拿大': 'Canada',
    '哥斯达黎加': 'Costa Rica', '牙买加': 'Jamaica', '巴拿马': 'Panama',
    '洪都拉斯': 'Honduras',
    # 非洲
    '尼日利亚': 'Nigeria', '加纳': 'Ghana', '科特迪瓦': 'Ivory Coast',
    '喀麦隆': 'Cameroon', '塞内加尔': 'Senegal', '摩洛哥': 'Morocco',
    '阿尔及利亚': 'Algeria', '突尼斯': 'Tunisia', '埃及': 'Egypt',
    '南非': 'South Africa', '刚果': 'Congo', '民主刚果': 'DR Congo',
    '马里': 'Mali', '布基纳法索': 'Burkina Faso', '佛得角': 'Cape Verde',
    # 亚洲其他
    '泰国': 'Thailand', '越南': 'Vietnam', '印度尼西亚': 'Indonesia',
    '马来西亚': 'Malaysia', '菲律宾': 'Philippines', '印度': 'India',
    '叙利亚': 'Syria', '黎巴嫩': 'Lebanon', '巴勒斯坦': 'Palestine',
    '塔吉克斯坦': 'Tajikistan', '吉尔吉斯斯坦': 'Kyrgyzstan',
}

# 国际赛/友谊赛联赛名(中文)
FRIENDLY_LEAGUES = {'国际赛', '国际友谊赛', '友谊赛', '国际比赛'}


def odds_to_probability(h: float, d: float, a: float) -> dict:
    """将赔率转换为隐含概率(去除margin)"""
    inv_h, inv_d, inv_a = 1/h, 1/d, 1/a
    total = inv_h + inv_d + inv_a
    return {
        'home': inv_h / total,
        'draw': inv_d / total,
        'away': inv_a / total,
        'margin': total - 1.0
    }


def adjust_probabilities(base: dict, adj: dict) -> dict:
    """用友谊赛修正值调整概率"""
    adjusted = {
        'home': base['home'] + adj.get('home_win_adj', 0),
        'draw': base['draw'] + adj.get('draw_adj', 0),
        'away': base['away'] + adj.get('away_win_adj', 0),
    }
    # 确保概率在[0.01, 0.97]范围内
    for k in adjusted:
        adjusted[k] = max(0.01, min(0.97, adjusted[k]))
    # 归一化
    total = sum(adjusted.values())
    for k in adjusted:
        adjusted[k] /= total
    return adjusted


def probability_to_odds(prob: float) -> str:
    """概率转回赔率"""
    return f'{1/prob:.2f}'


def is_friendly(league_cn: str) -> bool:
    """判断是否友谊赛"""
    return league_cn in FRIENDLY_LEAGUES or '友谊' in league_cn or '国际赛' in league_cn


def run_pipeline(target_date: str = None):
    """运行完整pipeline"""

    if target_date is None:
        target_date = date.today().strftime('%Y-%m-%d')

    print(f"{'='*70}")
    print(f"体彩赛前情报分析 — {target_date}")
    print(f"{'='*70}\n")

    # 1. 获取体彩开售比赛
    matches = get_match_list(target_date)
    if not matches:
        print("无开售比赛")
        return

    # 2. 筛选国际赛(友谊赛)
    friendlies = [m for m in matches if is_friendly(m['league_name_cn'])]
    league_matches = [m for m in matches if not is_friendly(m['league_name_cn'])]

    print(f"共{len(matches)}场比赛: {len(friendlies)}场国际赛 + {len(league_matches)}场联赛\n")

    if friendlies:
        print(f"{'─'*70}")
        print(f"国际赛赛前情报分析")
        print(f"{'─'*70}\n")

        collector = PreMatchCollector()

        for m in friendlies:
            home_cn = m['home_team_cn']
            away_cn = m['away_team_cn']
            home_en = CN_TO_EN.get(home_cn, home_cn)
            away_en = CN_TO_EN.get(away_cn, away_cn)

            spf = m['odds'].get('spf', {})
            rqspf = m['odds'].get('rqspf', {})

            if not spf:
                print(f"  {m['match_num']} {home_cn} vs {away_cn} — 暂无赔率")
                continue

            # 赔率隐含概率
            try:
                base_prob = odds_to_probability(
                    float(spf['h']), float(spf['d']), float(spf['a'])
                )
            except (ValueError, KeyError):
                print(f"  {m['match_num']} {home_cn} vs {away_cn} — 赔率格式错误")
                continue

            # 采集赛前情报(传入赔率用于分级修正)
            report = collector.collect(
                home_team=home_en,
                away_team=away_en,
                date=target_date,
                league='Friendly',
                odds={'home': float(spf['h']), 'draw': float(spf['d']), 'away': float(spf['a'])}
            )

            # 修正概率
            adj_prob = adjust_probabilities(base_prob, report.friendly_adjustment)

            # 输出
            print(f"  {m['match_num']} {home_cn}({home_en}) vs {away_cn}({away_en})")
            print(f"  赔率: SPF {spf['h']}/{spf['d']}/{spf['a']}")
            if rqspf:
                print(f"        RQSPF {rqspf['h']}/{rqspf['d']}/{rqspf['a']} (让球{m['handicap_line']:+.0f})")

            print(f"  隐含概率: 主{base_prob['home']:.0%} 平{base_prob['draw']:.0%} 客{base_prob['away']:.0%} (margin {base_prob['margin']:.1%})")

            # 关键洞察
            if report.key_insights:
                print(f"  关键洞察:")
                for insight in report.key_insights:
                    print(f"    - {insight}")

            # 修正后概率
            if report.friendly_adjustment.get('friendly_type') != 'not_friendly':
                print(f"  修正概率: 主{adj_prob['home']:.0%} 平{adj_prob['draw']:.0%} 客{adj_prob['away']:.0%}")
                new_odds = {
                    'home': probability_to_odds(adj_prob['home']),
                    'draw': probability_to_odds(adj_prob['draw']),
                    'away': probability_to_odds(adj_prob['away']),
                }
                print(f"  修正赔率: {new_odds['home']}/{new_odds['draw']}/{new_odds['away']}")

                # 简要建议
                prob_diff = adj_prob['draw'] - base_prob['draw']
                if prob_diff >= 0.08:
                    print(f"  >>> 平局概率大幅提升(+{prob_diff:.0%}), 关注平局!")
                elif adj_prob['home'] < base_prob['home'] - 0.10:
                    print(f"  >>> 主胜概率大幅下调, 警惕主队翻车!")

            print(f"  可信度: {report.confidence:.0%}")
            print()

    # 联赛简要展示
    if league_matches:
        print(f"{'─'*70}")
        print(f"联赛比赛(无友谊赛修正)")
        print(f"{'─'*70}\n")

        for m in league_matches:
            spf = m['odds'].get('spf', {})
            if spf:
                print(f"  {m['match_num']} {m['home_team_cn']} vs {m['away_team_cn']} | "
                      f"SPF {spf.get('h','?')}/{spf.get('d','?')}/{spf.get('a','?')}")

    print(f"\n{'='*70}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sys.stdout.reconfigure(encoding='utf-8')
    run_pipeline(target)
