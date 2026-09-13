"""Final-submission ladder analysis: win rate by opponent rating band, by opponent rank tier, repeated-opponent consistency."""
import json, csv, os, glob
from collections import defaultdict, Counter
BASE='/tmp/kaggle_eps'
lbf=glob.glob(BASE+'/lb/*.csv')[0]
lb={r['TeamId']:(int(r['Rank']), float(r['Score'])) for r in csv.DictReader(open(lbf, encoding='utf-8-sig'))}
rows=[r for r in json.load(open(BASE+'/all_games.json')) if r['sid'] in ('55565056','55565424')]
print("final-submission games:", len(rows))
bands=[(1100,9999,'>=1100 (top ~0.5%)'),(1000,1100,'1000-1099 (top 1.5%)'),(900,1000,'900-999 (top 6%)'),(850,900,'850-899 (bronze zone)'),(800,850,'800-849'),(750,800,'750-799 (our band)'),(700,750,'700-749'),(0,700,'<700')]
byband=defaultdict(lambda:[0,0]); unknown=0
for r in rows:
    t=lb.get(r['opp_tid'])
    if not t: unknown+=1; continue
    sc=t[1]
    for lo,hi,name in bands:
        if lo<=sc<hi: byband[name][0]+=1; byband[name][1]+=r['win']; break
print("opponents not on final LB:", unknown)
print("\n== win rate by opponent's FINAL rating band")
for lo,hi,name in bands:
    n,w=byband[name]
    if n: print(f"  {name:24s} n={n:4d}  W%={100*w/n:5.1f}")
tiers=[(1,100,'rank 1-100'),(101,500,'rank 101-500'),(501,1150,'rank 501-1150'),(1151,3000,'rank 1151-3000'),(3001,99999,'rank 3001+')]
print("\n== win rate by opponent's final RANK tier")
for lo,hi,name in tiers:
    x=[r for r in rows if lb.get(r['opp_tid']) and lo<=lb[r['opp_tid']][0]<=hi]
    if x: print(f"  {name:16s} n={len(x):4d}  W%={100*sum(r['win'] for r in x)/len(x):5.1f}")
print("\n== repeated opponents (played >=5 times): consistency")
c=Counter(r['opp_tid'] for r in rows)
rep=[(tid,n) for tid,n in c.items() if n>=5]
res=[]
for tid,n in rep:
    x=[r for r in rows if r['opp_tid']==tid]; w=sum(r['win'] for r in x); sc=lb.get(tid,(None,None))
    res.append((n,w,x[0]['opp_team'],x[0]['fam'],sc))
res.sort(key=lambda t:-t[0])
for n,w,name,fam,sc in res[:15]: print(f"  {name[:22]:22s} {fam:14s} rank={sc[0]} score={sc[1]}  {w}/{n} = {100*w/n:.0f}%")
print("  ... repeated-opponent pairs:", len(rep), " games:", sum(n for _,n in rep))
# top-100 opponents faced: names
top=[r for r in rows if lb.get(r['opp_tid']) and lb[r['opp_tid']][0]<=100]
print("\n== games vs top-100 teams:", len(top), "wins:", sum(r['win'] for r in top))
for r in sorted(top, key=lambda r: lb[r['opp_tid']][0])[:12]: print(f"   rank {lb[r['opp_tid']][0]:3d} {r['opp_team'][:20]:20s} {r['fam']:12s} {'W' if r['win'] else 'L'}")
