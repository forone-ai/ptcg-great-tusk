"""Hidden-information curve: opponent's unseen cards (deck + hand + remaining prizes) by turn, from final-entry ladder replays."""
import json, glob, sys
from collections import defaultdict
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
OUT=sys.argv[1]
by_turn=defaultdict(list); by_turn_win=defaultdict(list); by_turn_loss=defaultdict(list); by_turn_me=defaultdict(list); parts=defaultdict(lambda:[[],[],[]])
entry_unseen=[]; end_unseen=[]; end_unseen_noreach=[]; games=0
for sid in ('55565056','55565424'):
    for f in glob.glob(f'/tmp/kaggle_eps/{sid}/replays/*.json'):
        try: d=json.load(open(f))
        except Exception: continue
        names=d['info'].get('TeamNames') or [a['Name'] for a in d['info']['Agents']]
        if len(names)!=2 or names[0]==names[1]: continue
        us=[i for i,n in enumerate(names) if n=='GO HIROSHIMA 2']
        if not us: continue
        ui=us[0]; oi=1-ui; win=d['rewards'][ui]==1; games+=1
        seen=set(); last=None; reached=False; entry=None
        per_turn={}
        for s in d['steps']:
            c=s[ui]['observation'].get('current')
            if not c: continue
            op=c['players'][oi]; t=c.get('turn')
            prz=op.get('prize'); npr=len(prz) if isinstance(prz,list) else 6
            unseen=op['deckCount']+op['handCount']+npr
            me_=c['players'][ui]; mpr=me_.get('prize'); nmp=len(mpr) if isinstance(mpr,list) else 6
            if t is not None: by_turn_me[t].append(me_['deckCount']+me_['handCount']+nmp); parts[t][0].append(op['deckCount']); parts[t][1].append(op['handCount']); parts[t][2].append(npr)
            per_turn[t]=unseen; last=unseen
            if op['deckCount']<=8 and not reached: reached=True; entry=unseen
        for t,u in per_turn.items():
            if t is None: continue
            by_turn[t].append(u); (by_turn_win if win else by_turn_loss)[t].append(u)
        if last is not None:
            end_unseen.append(last) if reached else end_unseen_noreach.append(last)
        if entry is not None: entry_unseen.append(entry)
turns=sorted(t for t in by_turn if t<=40)
mean=[np.mean(by_turn[t]) for t in turns]; n=[len(by_turn[t]) for t in turns]
mw=[np.mean(by_turn_win[t]) if by_turn_win[t] else np.nan for t in turns]; ml=[np.mean(by_turn_loss[t]) if by_turn_loss[t] else np.nan for t in turns]
fig,ax=plt.subplots(figsize=(9,4.4),dpi=160)
ax.plot(turns, mean, color='#1f4e79', lw=2.2, label='all games (mean)')
ax.plot(turns, [np.mean(by_turn_me[t]) for t in turns], color='#e07b39', lw=2.2, label='our own unseen cards (opponent\'s view)')
ax.plot(turns, mw, color='#2a9d8f', lw=1.4, ls='--', label='games we won')
ax.plot(turns, ml, color='#d1495b', lw=1.4, ls='--', label='games we lost')
ax.axhline(60, color='#999', lw=0.8, ls=':'); ax.text(0.3, 60.8, 'all 60 opponent cards hidden', fontsize=7.5, color='#666')
ax.set_xlabel('turn'); ax.set_ylabel('unseen cards of a player\n(deck + hand + remaining Prizes)'); ax.set_ylim(0,64); ax.set_xlim(0,40)
ax.legend(fontsize=8, loc='upper right')
ax.set_title(f"Hidden information shrinks for both players as the mill plan runs: {games:,} final-entry ladder games", fontsize=10)
fig.tight_layout(); fig.savefig(OUT); print('saved', OUT)
print('games', games)
for t in (1,5,10,15,16,20,25,30): 
    if t in by_turn: print(f'turn {t}: mean unseen {np.mean(by_turn[t]):.1f} (n={len(by_turn[t])}), win-games {np.mean(by_turn_win[t]) if by_turn_win[t] else float("nan"):.1f}, loss-games {np.mean(by_turn_loss[t]) if by_turn_loss[t] else float("nan"):.1f}')
print(f'unseen at regime entry (opp deck<=8): median {np.median(entry_unseen):.0f}, p25 {np.percentile(entry_unseen,25):.0f}, p75 {np.percentile(entry_unseen,75):.0f}, n={len(entry_unseen)}')
print(f'unseen at game end: reached-regime games median {np.median(end_unseen):.0f} (n={len(end_unseen)}); never-reached games median {np.median(end_unseen_noreach):.0f} (n={len(end_unseen_noreach)})')

for t in (1,10,16,20,30):
    if t in by_turn_me: print(f'turn {t}: OUR unseen {np.mean(by_turn_me[t]):.1f} | opp unseen split deck {np.mean(parts[t][0]):.1f} hand {np.mean(parts[t][1]):.1f} prizes {np.mean(parts[t][2]):.1f}')
