"""Ladder test: does search convert the thin-deck regime into wins? Compare P(win | reached regime) for games where the agent visibly searched (any decision > 2.5 s) vs games where it did not."""
import json, glob, csv, os
from collections import defaultdict
BASE='/tmp/kaggle_eps'
subs={r['ref']:r for r in csv.DictReader(open(BASE+'/submissions.csv'))}
rows=[]
for d in glob.glob(BASE+'/*/replays'):
    sid=d.split('/')[-2]
    for f in glob.glob(d+'/*.json'):
        try: g=json.load(open(f))
        except Exception: continue
        names=g['info'].get('TeamNames') or [a['Name'] for a in g['info']['Agents']]
        if len(names)!=2 or names[0]==names[1]: continue
        us=[i for i,n in enumerate(names) if n=='GO HIROSHIMA 2']
        if not us: continue
        ui=us[0]; oi=1-ui; prev=None; maxthink=0; mn_opp=99; used=0
        for s in g['steps']:
            o=s[ui]['observation']; c=o.get('current'); t=o.get('remainingOverageTime')
            if c: mn_opp=min(mn_opp, c['players'][oi]['deckCount'])
            if t is not None:
                if prev is not None and s[ui]['status']=='ACTIVE': maxthink=max(maxthink, prev-t)
                prev=t
        rows.append(dict(sid=sid, date=subs.get(sid,{}).get('date','')[:10], win=g['rewards'][ui]==1, reached=mn_opp<=8, maxthink=maxthink, searched=maxthink>2.5, final=sid in ('55565056','55565424')))
print("games:", len(rows), "| final-entry:", sum(r['final'] for r in rows), "| earlier:", sum(1 for r in rows if not r['final']))
def summarize(label, rs):
    n=len(rs); 
    if not n: print(label, "n=0"); return
    reach=[r for r in rs if r['reached']]; no=[r for r in rs if not r['reached']]
    print(f"{label}: n={n} W%={100*sum(r['win'] for r in rs)/n:.1f} | reached regime {100*len(reach)/n:.0f}% -> W% {100*sum(r['win'] for r in reach)/max(1,len(reach)):.1f} (n={len(reach)}) | not reached -> W% {100*sum(r['win'] for r in no)/max(1,len(no)):.1f} (n={len(no)})")
earlier=[r for r in rows if not r['final']]
summarize("FINAL build (no search)", [r for r in rows if r['final']])
summarize("EARLIER builds, search visible (max think>2.5s)", [r for r in earlier if r['searched']])
summarize("EARLIER builds, no visible search", [r for r in earlier if not r['searched']])
# by submission (earlier), show search share
bysid=defaultdict(list)
for r in earlier: bysid[r['sid']].append(r)
print("\nper earlier submission: date, n, searched%, W%, P(win|reach), P(win|no reach)")
for sid,rs in sorted(bysid.items(), key=lambda kv: kv[1][0]['date']):
    n=len(rs); reach=[r for r in rs if r['reached']]; no=[r for r in rs if not r['reached']]
    print(f"  {sid} {rs[0]['date']} n={n:3d} searched={100*sum(r['searched'] for r in rs)/n:3.0f}% W%={100*sum(r['win'] for r in rs)/n:5.1f} | reach {100*len(reach)/n:3.0f}% W|reach={100*sum(r['win'] for r in reach)/max(1,len(reach)):5.1f} W|no={100*sum(r['win'] for r in no)/max(1,len(no)):5.1f} {subs.get(sid,{}).get('fileName','')[:22]}")
json.dump(rows, open(BASE+'/regime_rows.json','w'))
