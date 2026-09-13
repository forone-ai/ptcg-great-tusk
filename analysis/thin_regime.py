import json, glob
rows=[]
for sid in ('55565056','55565424'):
    for f in glob.glob(f'/tmp/kaggle_eps/{sid}/replays/*.json'):
        try: d=json.load(open(f))
        except Exception: continue
        names=d['info'].get('TeamNames') or [a['Name'] for a in d['info']['Agents']]
        if len(names)!=2 or names[0]==names[1]: continue
        us=[i for i,n in enumerate(names) if n=='GO HIROSHIMA 2']
        if not us: continue
        ui=us[0]; oi=1-ui; mn_opp=99; mn_me=99; reach_turn=None
        for s in d['steps']:
            c=s[ui]['observation'].get('current')
            if not c: continue
            od=c['players'][oi]['deckCount']; md=c['players'][ui]['deckCount']
            if od<mn_opp:
                mn_opp=od
                if od<=8 and reach_turn is None: reach_turn=c.get('turn')
            mn_me=min(mn_me, md)
        rows.append(dict(win=d['rewards'][ui]==1, mn_opp=mn_opp, mn_me=mn_me, reach=reach_turn))
n=len(rows)
for thr in (12,8,5):
    a=[r for r in rows if r['mn_opp']<=thr]; b=[r for r in rows if r['mn_opp']>thr]
    print(f"opp deck reached <= {thr}: n={len(a)} ({100*len(a)/n:.0f}% of games) W%={100*sum(r['win'] for r in a)/len(a):.1f} | never: n={len(b)} W%={100*sum(r['win'] for r in b)/max(1,len(b)):.1f}")
both=[r for r in rows if r['mn_opp']<=8 and r['mn_me']<=8]; print(f"both decks <=8: n={len(both)} W%={100*sum(r['win'] for r in both)/max(1,len(both)):.1f}")
rt=sorted(r['reach'] for r in rows if r['reach']); print(f"turn when opp deck first <=8: median {rt[len(rt)//2]}, p25 {rt[len(rt)//4]}, p75 {rt[3*len(rt)//4]}")
