"""Ladder analysis from episode lists + team->deck badges (no replays needed)."""
import json, os, csv, sys
from collections import defaultdict, Counter
ROOT=os.path.expanduser('~/projects/pokemon-tcg-ai-battle'); BASE='/tmp/kaggle_eps'
state=json.load(open(ROOT+'/analysis/lb-deck-badges/data/state.json'))
teams=state.get('teams',{})
def badge(tid):
    t=teams.get(str(tid)); 
    if not t: return ('?','?')
    r=t.get('record',{}); return (r.get('label','?'), r.get('archetype','?'))
lb={}
p=ROOT+'/analysis/lb-deck-badges/data/leaderboard_full.csv'
if os.path.exists(p):
    rd=csv.DictReader(open(p)); cols=rd.fieldnames
    for r in rd: lb[str(r.get('teamId') or r.get('TeamId') or r.get('team_id') or '')]=r
    print("leaderboard_full cols:", cols)
LABEL={'55392200':'v28j (peak lineage, sub 8/10)','55546161':'v28j re-sub 8/16','55546126':'16c sub 8/16','55562198':'16h sub 8/17','55565056':'16j final B','55565424':'16j final A'}
def fam(label):
    l=label.lower()
    for k,v in (('grimmsnarl','Grimmsnarl'),('alakazam','Alakazam'),('lucario','Mega Lucario'),('crustle','Crustle/LO'),('great tusk','Crustle/LO'),('dragapult','Dragapult'),('garchomp','Garchomp'),('archeops','Archeops'),('archaludon','Archaludon'),('duraludon','Archaludon'),('zoroark','Zoroark'),('gholdengo','Gholdengo'),('charizard','Charizard'),('raging bolt','Raging Bolt'),('tarountula','Tarountula'),('venusaur','Venusaur'),('abomasnow','Abomasnow')):
        if k in l: return v
    return label if label!='?' else 'Unknown team'
print("badge teams:", len(teams))
allrows=[]
for sid in LABEL:
    f=f'{BASE}/{sid}/episodes_full.json'
    if not os.path.exists(f): print(f"\n#### {sid} {LABEL[sid]}: list not fetched yet"); continue
    eps=json.load(open(f)); rows=[]
    for e in eps:
        ag=e['agents']
        if len(ag)!=2: continue
        me=[a for a in ag if a['submission_id']==sid]; op=[a for a in ag if a['submission_id']!=sid]
        if len(me)!=1 or len(op)!=1: continue
        me,op=me[0],op[0]; lab,arc=badge(op['team_id'])
        rows.append(dict(sid=sid, date=e['create_time'][:10], win=(me['reward'] or 0)>(op['reward'] or 0), draw=me['reward']==op['reward'], opp_team=op['team_name'], opp_tid=op['team_id'], opp_sub=op['submission_id'], label=lab, arche=arc, fam=fam(lab)))
    allrows+=rows; n=len(rows); w=sum(r['win'] for r in rows)
    print(f"\n#### {sid} {LABEL[sid]}: games={n} W%={100*w/max(1,n):.1f} draws={sum(r['draw'] for r in rows)} dates {min(r['date'] for r in rows)}..{max(r['date'] for r in rows)} unknown-team={sum(1 for r in rows if r['fam']=='Unknown team')}")
    days=sorted(set(r['date'] for r in rows))
    print("  by day: " + " ".join(f"{d[5:]}:{sum(1 for r in rows if r['date']==d and r['win'])}/{sum(1 for r in rows if r['date']==d)}" for d in days))
    fams=Counter(r['fam'] for r in rows)
    print("  by opponent family (pool share, win%):")
    for f_,c in fams.most_common(10):
        wf=sum(1 for r in rows if r['fam']==f_ and r['win']); print(f"    {f_:18s} n={c:4d} ({100*c/n:4.0f}%)  W%={100*wf/c:5.1f}")
    arcs=Counter(r['arche'] for r in rows)
    print("  by archetype class:", ", ".join(f"{a}: {sum(1 for r in rows if r['arche']==a and r['win'])}/{c}" for a,c in arcs.most_common(6)))
json.dump(allrows, open(BASE+'/allrows_lists.json','w')); print("\nsaved", len(allrows))
