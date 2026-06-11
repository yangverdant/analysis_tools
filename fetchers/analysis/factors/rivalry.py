"""德比/宿敌因素"""

from typing import Dict, Any
from .base_factor import BaseFactor


class RivalryFactor(BaseFactor):
    factor = "rivalry"
    title = "德比/宿敌"
    factor_type = "categorical"

    # 预定义德比关系
    DERBIES = {
        frozenset(["manchester city", "manchester united"]): "曼彻斯特德比",
        frozenset(["liverpool", "everton"]): "默西塞德德比",
        frozenset(["arsenal", "tottenham hotspur"]): "北伦敦德比",
        frozenset(["chelsea", "fulham"]): "西伦敦德比",
        frozenset(["real madrid", "atletico madrid"]): "马德里德比",
        frozenset(["barcelona", "espanyol"]): "加泰罗尼亚德比",
        frozenset(["ac milan", "inter"]): "米兰德比",
        frozenset(["roma", "lazio"]): "罗马德比",
        frozenset(["juventus", "torino"]): "都灵德比",
        frozenset(["bayern munich", "1860 munich"]): "慕尼黑德比",
        frozenset(["borussia dortmund", "schalke 04"]): "鲁尔区德比",
        frozenset(["psg", "marseille"]): "法国国家德比",
        frozenset(["rosenborg", "molde"]): "挪威国家德比",
        frozenset(["ifk goteborg", "malmo ff"]): "瑞典国家德比",
        frozenset(["djurgaarden", "hammarby"]): "斯德哥尔摩德比",
        frozenset(["brann", "viking"]): "卑尔根德比",
    }

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        pair = frozenset([match["home_team"].lower(), match["away_team"].lower()])
        derby_name = self.DERBIES.get(pair)

        cat = "derby" if derby_name else "normal"

        return self._categorical(
            home_category=cat,
            away_category=cat,
            confidence=0.95 if derby_name else 0.8,
            is_derby=derby_name is not None,
            derby_name=derby_name or "",
        )