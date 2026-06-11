import sys,sqlite3,json,math
sys.path.insert(0,'.');sys.stdout.reconfigure(encoding='utf-8')

db_path='data/football_v2.db'
conn=sqlite3.connect(db_path)
conn.row_factory=sqlite3.Row
c=conn.cursor()

def dec(k):
    if k.startswith('s') and k.count('s')>=2:
        p=k[1:].split('s')
        try: return f'{int(p[0])}:{int(p[1])}'
        except: return k
    if k=='s1sa': return '胜其他'
    if k=='s1sd': return '平其他'
    if k=='s1sh': return '负其他'
    return k

def poisson_p(lam,k):
    return math.exp(-lam)*lam**k/math.factorial(k)

def top_scores(hxg,axg,n=5):
    scores={}
    for h in range(5):
        for a in range(5):
            p=poisson_p(hxg,h)*poisson_p(axg,a)
            scores[f'{h}:{a}']=p
    return sorted(scores.items(),key=lambda x:x[1],reverse=True)[:n]

spf_label={'3':'主胜','1':'平局','0':'客胜'}
bqc_map={'hh':'胜胜','hd':'胜平','ha':'胜负','dh':'平胜','dd':'平平','da':'平负','ah':'负胜','ad':'负平','aa':'负负'}

for lm_id,nm,hid,aid in [('202606092202','匈牙利 vs 哈萨克斯坦',456,505),('202606092203','阿根廷 vs 冰岛',66,460),('202606092201','中国 vs 泰国',218,904)]:
    print(f'\n{"="*65}')
    print(f'  {nm}')
    print(f'{"="*65}')

    # Get prediction
    c.execute('SELECT report_data FROM lottery_analysis_reports WHERE lottery_match_id=? AND report_type="prediction"',(lm_id,))
    row=c.fetchone()
    report=json.loads(row[0]) if isinstance(row[0],str) else row[0]
    probs=report.get('final_prediction',{}).get('probabilities',{})
    h=float(probs.get('home_win',0));d=float(probs.get('draw',0));a=float(probs.get('away_win',0))
    xg=report.get('xg_analysis',{});hxg=float(xg.get('home_xg',0));axg=float(xg.get('away_xg',0))
    ob=report.get('odds_baseline');mvo=report.get('model_vs_odds')
    mot=report.get('motivation_analysis');adjs=report.get('adjustments',[])

    # ── SPF 胜平负 ──
    print(f'\n  【胜平负 SPF】')
    c.execute('SELECT odds_data FROM lottery_odds WHERE lottery_match_id=? AND play_type="spf" ORDER BY created_at DESC LIMIT 1',(lm_id,))
    spf_row=c.fetchone()
    if spf_row:
        spf=json.loads(spf_row[0])if isinstance(spf_row[0],str)else spf_row[0]
        print(f'  体彩赔率: 主胜={spf.get("3","-")} | 平={spf.get("1","-")} | 客胜={spf.get("0","-")}')
    else:
        print(f'  体彩赔率: 无SPF赔率')

    print(f'  模型概率: 主胜={h:.1%} | 平={d:.1%} | 客胜={a:.1%}')
    best_spf='3' if h>=d and h>=a else ('1' if d>=a else '0')
    print(f'  >>> 推荐: {spf_label[best_spf]}')

    if ob:
        ob_best=max(ob,key=lambda k:float(ob[k])if isinstance(ob[k],(int,float))else 0)
        ob_code={'home_win':'3','draw':'1','away_win':'0'}.get(ob_best,'?')
        if best_spf==ob_code:
            print(f'  (模型与赔率一致→高可信)')
        else:
            print(f'  (模型与赔率不一致→模型发现价值点)')

    # ── RQSPF 让球胜平负 ──
    print(f'\n  【让球胜平负 RQSPF】')
    c.execute('SELECT odds_data FROM lottery_odds WHERE lottery_match_id=? AND play_type="rqspf" ORDER BY created_at DESC LIMIT 1',(lm_id,))
    rq_row=c.fetchone()
    if rq_row:
        rq=json.loads(rq_row[0])if isinstance(rq_row[0],str)else rq_row[0]
        gl=rq.get('goal_line','?')
        # RQSPF: 让球后, 概率基于xG差值减去让球数
        handicap=float(gl) if gl not in ('?','') else 0
        adj_hxg=max(0.1,hxg+handicap*0.3)  # 粗略: 让N球≈xG减N*0.3
        adj_axg=max(0.1,axg+abs(handicap)*0.3 if handicap<0 else axg)

        # 用RQSPF赔率反推让球后概率
        rh=float(rq.get('3',0));rd=float(rq.get('1',0));ra=float(rq.get('0',0))
        if rh>1 and rd>1 and ra>1:
            t=1/rh+1/rd+1/ra
            rq_probs={'3':round((1/rh)/t,3),'1':round((1/rd)/t,3),'0':round((1/ra)/t,3)}
            rq_best=max(rq_probs,key=rq_probs.get)
        else:
            rq_probs={'3':h,'1':d,'0':a}
            rq_best=best_spf

        print(f'  让球: {gl}')
        print(f'  体彩赔率: 主胜={rq.get("3","-")} | 平={rq.get("1","-")} | 客胜={rq.get("0","-")}')
        print(f'  让球后概率(赔率): 主={rq_probs.get("3",0):.1%} | 平={rq_probs.get("1",0):.1%} | 客={rq_probs.get("0",0):.1%}')
        print(f'  >>> 推荐: {spf_label.get(rq_best,rq_best)}')
    else:
        print(f'  无RQSPF赔率')

    # ── BF 比分 ──
    print(f'\n  【比分 BF】')
    scores=top_scores(hxg,axg,5)
    print(f'  xG: 主={hxg:.2f} 客={axg:.2f}')
    print(f'  模型最可能比分:')
    for s,p in scores:
        marker=' <<<' if s in ['1:0','2:0','2:1','0:0','1:1','0:1'] else ''
        print(f'    {s}: {p:.1%}{marker}')

    c.execute('SELECT odds_data FROM lottery_odds WHERE lottery_match_id=? AND play_type="bf" ORDER BY created_at DESC LIMIT 1',(lm_id,))
    bf_row=c.fetchone()
    if bf_row:
        bf=json.loads(bf_row[0])if isinstance(bf_row[0],str)else bf_row[0]
        sb=sorted(bf.items(),key=lambda x:float(x[1])if x[1]else 999)
        print(f'  体彩最低赔率比分:')
        for k,v in sb[:5]:
            print(f'    {dec(k)}={v}')

    # 推荐3个比分
    print(f'  >>> 推荐比分:')
    for i,(s,p) in enumerate(scores[:3]):
        print(f'    {i+1}. {s} ({p:.1%})')

    # ── BQC 半全场 ──
    print(f'\n  【半全场 BQC】')
    c.execute('SELECT odds_data FROM lottery_odds WHERE lottery_match_id=? AND play_type="bqc" ORDER BY created_at DESC LIMIT 1',(lm_id,))
    bqc_row=c.fetchone()
    if bqc_row:
        bqc=json.loads(bqc_row[0])if isinstance(bqc_row[0],str)else bqc_row[0]
        sb2=sorted(bqc.items(),key=lambda x:float(x[1])if x[1]else 999)
        print(f'  体彩赔率(前5):')
        for k,v in sb2[:5]:
            label=bqc_map.get(k,k)
            print(f'    {label}={v}')

        # 简单推荐: 强队半场平→全场胜(dh) 或 强队全场胜(hh)
        if h>a:
            print(f'  >>> 推荐: 胜胜(hh) 或 平胜(dh)')
        else:
            print(f'  >>> 推荐: 负负(aa) 或 平负(da)')

    # ── 关键因素 ──
    print(f'\n  【关键因素】')
    if mot:
        hm=mot.get('home_motivation',{});am=mot.get('away_motivation',{})
        print(f'  动机: 主={hm.get("urgency","?")}({hm.get("motivation_type","?")}) 客={am.get("urgency","?")}({am.get("motivation_type","?")})')
        sigs_h=hm.get('signals',[]);sigs_a=am.get('signals',[])
        if sigs_h: print(f'    主队信号: {", ".join(sigs_h)}')
        if sigs_a: print(f'    客队信号: {", ".join(sigs_a)}')

    adj_strs=[]
    for adj in adjs:
        t=adj.get('type')
        if t=='h2h': adj_strs.append(f'交锋{adj.get("factor",0):+.2f}')
        elif t=='form': adj_strs.append(f'状态{adj.get("factor",0):+.2f}')
        elif t=='home_away': adj_strs.append(f'主客{adj.get("factor",0):+.2f}')
        elif t=='motivation_simplified': adj_strs.append(f'动机差{adj.get("urgency_diff",0):+d}')
        elif t=='news_factors': adj_strs.append(f'因素{adj.get("factor",0):+.2f}')
    if adj_strs: print(f'  调整: {" | ".join(adj_strs)}')

conn.close()
