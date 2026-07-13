---
name: wc-vs-wc-friendly-rule
description: "WC vs WC友谊赛默认平局规则, 偏斜<20%→平局, 赔率不可靠"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

WC vs WC友谊赛 → 默认平局, 赔率模型不可靠(只反映名义实力不反映实际出力)
**Why:** 6/2验证: 威尔士vs加纳赔率偏斜18.6%选主胜→实际1:1平局, 克罗地亚vs比利时赔率均衡→实际0:2客胜(赔率完全无法预测), 格鲁吉亚1:1罗马尼亚→平局. 5场WC vs WC友谊赛=3平2分胜负, 平局率60%
**How to apply:** WC vs WC时赔率偏斜<20% → 默认平局; ≥20% → 可跟赔率但降级置信度. WC碾压非WC不受此规则影响(10/10全对). 另外: 非WC队有球星爆点(attack≥6, rank≥50)可能逼平WC队(格鲁吉亚1:1罗马尼亚验证)