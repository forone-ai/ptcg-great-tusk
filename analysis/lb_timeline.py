"""Complete ladder history across all submissions: daily win rate, pool composition, per-submission summary; bias check vs repo sample."""
import json, os, csv, glob
from collections import defaultdict, Counter
ROOT=os.path.expanduser('~/projects/pokemon-tcg-ai-battle'); BASE='/tmp/kaggle_eps'
teams=json.load(open(ROOT+'/analysis/lb-deck-badges/data/state.json')).get('teams',{})
def fam(tid):
    t=teams.get(str(tid)); l=(t or {}).get('record',{}).get('label','?') if t else '?'
    ll=l.lower()
    for k,v in (('grimmsnarl','Grimmsnarl'),('alakazam','Alakazam'),('lucario','Mega Lucario'),('crustle','Crustle/LO'),('great tusk','Crustle/LO'),('dragapult','Dragapult'),('garchomp','Garchomp'),('archeops','Archeops'),('archaludon','Archaludon'),('duraludon','Archaludon'),('zoroark','Zoroark'),('gholdengo','Gholdengo'),('charizard','Charizard'),('raging bolt','Raging Bolt'),('tarountula','Tarountula'),('venusaur','Venusaur'),('abomasnow','Abomasnow')):
        if k in ll: return v
    return 'Other' if l!='?' else 'Unknown'
subs={}
for r in csv.DictReader(open(BASE+'/submissions.csv')) if os.path.exists(BASE+'/submissions.csv') else []: subs[r['ref']]=r
rows=[]
for f in glob.glob(BASE+'/*/episodes_full.json'):
    sid=f.split('/')[-2]
    for e in json.load(open(f)):
        ag=e['agents']
        if len(ag)!=2: continue
        me=[a for a in ag if a['submission_id']==sid]; op=[a for a in ag if a['submission_id']!=sid]
        if len(me)!=1 or len(op)!=1: continue
        me,op=me[0],op[0]
        rows.append(dict(eid=e['id'], sid=sid, date=e['create_time'][:10], win=(me['reward'] or 0)>(op['reward'] or 0), opp_tid=op['team_id'], opp_team=op['team_name'], fam=fam(op['team_id'])))
# dedupe (mirror games appear in both submissions' lists with different 'me')
print("games total:", len(rows), "distinct episodes:", len(set(r['eid'] for r in rows)))
print("\n== per submission (sorted by date)")
bysid=defaultdict(list)
for r in rows: bysid[r['sid']].append(r)
for sid,rs in sorted(bysid.items(), key=lambda kv: min(r['date'] for r in kv[1])):
    n=len(rs); w=sum(r['win'] for r in rs); d=subs.get(sid,{})
    print(f"  {sid} {min(r['date'] for r in rs)}..{max(r['date'] for r in rs)} n={n:4d} W%={100*w/n:5.1f} score={d.get('publicScore','?'):>6} {(d.get('fileName') or '')[:30]}")
print("\n== daily (all LO-lineage subs from 7/19 on): games, win%, pool share of top families")
LO_START='2026-07-19'
daily=defaultdict(list)
for r in rows:
    if r['date']>=LO_START: daily[r['date']].append(r)
for d in sorted(daily):
    rs=daily[d]; n=len(rs); w=sum(r['win'] for r in rs); c=Counter(r['fam'] for r in rs)
    top=" ".join(f"{k[:6]}:{100*v/n:.0f}%" for k,v in c.most_common(4))
    print(f"  {d[5:]} n={n:3d} W%={100*w/n:5.1f}  {top}")
print("\n== family win% over all LO-lineage games, split before/after 8/17")
for tag,cond in (('before 8/17', lambda r: LO_START<=r['date']<'2026-08-17'), ('8/17 onward', lambda r: r['date']>='2026-08-17')):
    rs=[r for r in rows if cond(r)]; n=len(rs); c=Counter(r['fam'] for r in rs)
    print(f"  [{tag}] n={n} W%={100*sum(r['win'] for r in rs)/max(1,n):.1f}")
    for k,v in c.most_common(9):
        wk=sum(1 for r in rs if r['fam']==k and r['win']); print(f"     {k:14s} share={100*v/n:4.0f}%  W%={100*wk/v:5.1f} (n={v})")
# bias check of repo sample
repo=set(os.path.basename(f).split('-')[1] for f in glob.glob(ROOT+'/episode-*-replay.json'))
inlists=[r for r in rows if r['eid'] in repo]
if inlists:
    print(f"\n== repo sample bias: {len(inlists)} of {len(repo)} repo replays found in lists; their W%={100*sum(r['win'] for r in inlists)/len(inlists):.1f} vs full W% of same subs={100*sum(r['win'] for r in rows if r['sid'] in set(x['sid'] for x in inlists))/max(1,sum(1 for r in rows if r['sid'] in set(x['sid'] for x in inlists))):.1f}")
    print("   repo-sample dates:", min(r['date'] for r in inlists), '..', max(r['date'] for r in inlists))
json.dump(rows, open(BASE+'/all_games.json','w'))
