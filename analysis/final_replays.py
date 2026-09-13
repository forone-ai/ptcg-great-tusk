"""Final-submission replays: first/second player, win/loss reasons, game length, thinking time, mulligan-ish opening."""
import json, glob, os
from collections import Counter, defaultdict
rows=[]
for sid in ('55565056','55565424'):
    for f in glob.glob(f'/tmp/kaggle_eps/{sid}/replays/*.json'):
        try: d=json.load(open(f))
        except Exception: continue
        names=d['info'].get('TeamNames') or [a['Name'] for a in d['info']['Agents']]
        if len(names)!=2: continue
        us=[i for i,n in enumerate(names) if n=='GO HIROSHIMA 2']
        if not us: continue
        if names[0]==names[1]: continue  # skip mirrors (ambiguous index)
        ui=us[0]; oi=1-ui; steps=d['steps']
        last=None; first=None; prev=None; thinks=[]; maxstep=0
        for s in steps:
            o=s[ui]['observation']; c=o.get('current')
            if c:
                last=c
                if first is None and c.get('firstPlayer',-1)!=-1: first=c['firstPlayer']
            t=o.get('remainingOverageTime')
            if t is not None:
                if prev is not None and s[ui]['status']=='ACTIVE': thinks.append(prev-t)
                prev=t
        if not last: continue
        me=last['players'][ui]; op=last['players'][oi]; win=d['rewards'][ui]==1
        def prizes(p): 
            pr=p.get('prize'); return len(pr) if isinstance(pr,list) else p.get('prizeCount')
        mp,opz=prizes(me),prizes(op)
        if win:
            reason='deck-out' if op['deckCount']==0 else ('prizes' if mp==0 else ('opp-no-pokemon' if not op['active'] and not op['bench'] else 'other'))
        else:
            reason='deck-out' if me['deckCount']==0 else ('prizes' if opz==0 else ('no-pokemon' if not me['active'] and not me['bench'] else 'other'))
        rows.append(dict(sid=sid, win=win, first=(first==ui) if first is not None else None, turn=last.get('turn'), reason=reason, used=600-prev if prev else None, maxthink=max(thinks) if thinks else 0, our_deck=me['deckCount'], opp_deck=op['deckCount']))
n=len(rows); print("non-mirror final-submission replays:", n)
w=sum(r['win'] for r in rows); print(f"W%={100*w/n:.1f}")
for lab,cond in (('going first',lambda r:r['first'] is True),('going second',lambda r:r['first'] is False)):
    x=[r for r in rows if cond(r)]; print(f"  {lab}: n={len(x)} W%={100*sum(r['win'] for r in x)/max(1,len(x)):.1f}")
print("\nwin reasons:", Counter(r['reason'] for r in rows if r['win']))
print("loss reasons:", Counter(r['reason'] for r in rows if not r['win']))
t=sorted(r['turn'] for r in rows if r['turn'] is not None); print(f"\ngame length (turns): median {t[len(t)//2]}, p10 {t[len(t)//10]}, p90 {t[int(len(t)*.9)]}")
tw=sorted(r['turn'] for r in rows if r['win'] and r['turn']); tl=sorted(r['turn'] for r in rows if not r['win'] and r['turn'])
print(f"  wins median {tw[len(tw)//2]}, losses median {tl[len(tl)//2]}")
u=sorted(r['used'] for r in rows if r['used'] is not None); print(f"\ntime used per game (s): median {u[len(u)//2]:.1f}, p95 {u[int(len(u)*.95)]:.1f}, max {u[-1]:.1f}; timeouts(<1s left): {sum(1 for r in rows if r['used'] and r['used']>599)}")
m=sorted(r['maxthink'] for r in rows); print(f"max single decision (s): median {m[len(m)//2]:.2f}, p95 {m[int(len(m)*.95)]:.2f}, max {m[-1]:.2f}")
short=[r for r in rows if r['turn'] and r['turn']<=8]; print(f"\ngames ended by turn 8: {len(short)} ({100*len(short)/n:.1f}%), our W% there {100*sum(r['win'] for r in short)/max(1,len(short)):.0f}")
json.dump(rows, open('/tmp/kaggle_eps/final_replay_rows.json','w'))
