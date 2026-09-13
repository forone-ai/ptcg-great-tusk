import json, csv, os, sys
from collections import defaultdict, Counter
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import numpy as np
BASE='/tmp/kaggle_eps'; OUT=sys.argv[1]; os.makedirs(OUT, exist_ok=True)
rows=json.load(open(BASE+'/all_games.json'))
_subs={r['ref']:r for r in csv.DictReader(open(BASE+'/submissions.csv'))}
def _is_lo(sid):
    s=_subs.get(sid,{}); fn=(s.get('fileName') or '').lower()
    return s.get('date','')>='2026-07-19' and not any(k in fn for k in ('dragapult','alakazam','lucario','hop'))
LO=[r for r in rows if _is_lo(r['sid'])]
# ---- Fig A: daily win rate + pool composition (stacked share)
days=sorted(set(r['date'] for r in LO))
fams=['Alakazam','Grimmsnarl','Mega Lucario','Archaludon','Crustle/LO','Dragapult','Other','Unknown']
cols={'Alakazam':'#7b5cd6','Grimmsnarl':'#3b3b3b','Mega Lucario':'#e07b39','Archaludon':'#6c8ebf','Crustle/LO':'#b08d57','Dragapult':'#c94c8a','Other':'#bbbbbb','Unknown':'#e5e5e5'}
def famkey(f): return f if f in fams else 'Other'
share=np.array([[sum(1 for r in LO if r['date']==d and famkey(r['fam'])==f)/max(1,sum(1 for r in LO if r['date']==d)) for f in fams] for d in days])
wr=[100*sum(1 for r in LO if r['date']==d and r['win'])/sum(1 for r in LO if r['date']==d) for d in days]
n=[sum(1 for r in LO if r['date']==d) for d in days]
plt.rcParams.update({'font.size':12})
fig,ax=plt.subplots(figsize=(9,6),dpi=160)
x=np.arange(len(days)); bottom=np.zeros(len(days))
for i,f in enumerate(fams):
    ax.bar(x, 100*share[:,i], bottom=bottom, color=cols[f], width=0.85, label=f, linewidth=0); bottom+=100*share[:,i]
ax.set_ylabel('opponent pool composition (%)'); ax.set_ylim(0,100)
ax2=ax.twinx(); ax2.plot(x, wr, color='#d1495b', lw=2, marker='o', ms=3, label='our daily win rate'); ax2.axhline(50, color='#d1495b', lw=0.8, ls='--'); ax2.set_ylim(0,100); ax2.set_ylabel('daily win rate (%)', color='#d1495b')
ax.set_xticks(x[::4]); ax.set_xticklabels([d[5:] for d in days][::4], rotation=45, fontsize=11)
gap=[i for i,d in enumerate(days) if d=='2026-08-21']
if gap: ax.axvline(gap[0]-0.5, color='k', lw=1, ls=':'); ax.text(gap[0]-0.4, 93, 'deadline Aug 16 →', fontsize=10)
h1,l1=ax.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels(); ax.legend(h1+h2,l1+l2, loc='lower left', fontsize=9, ncol=3, framealpha=0.9)
ax.set_title(f'Great Tusk lineage on the ladder, Jul 19 – Aug 31 ({len(LO):,} games, {len(set(r["sid"] for r in LO))} builds):\ndaily win rate stays near 50% while the opponent pool rotates', fontsize=12)
fig.tight_layout(); fig.savefig(OUT+'/08_ladder_daily.png'); plt.close(fig)
# ---- Fig B: matchup profile before/after Aug 17
famsB=['Mega Lucario','Archaludon','Garchomp','Dragapult','Alakazam','Grimmsnarl','Crustle/LO','Other']
def stats(rs,f):
    x=[r for r in rs if famkey(r['fam'])==f or r['fam']==f]; k=len(x); w=sum(r['win'] for r in x)
    p=w/k if k else 0; se=1.96*np.sqrt(p*(1-p)/k) if k else 0; return 100*p,100*se,k
pre=[r for r in LO if r['date']<'2026-08-17']; post=[r for r in LO if r['date']>='2026-08-17']
fig,ax=plt.subplots(figsize=(9,6),dpi=160); x=np.arange(len(famsB)); w=0.38
for off,(rs,lab,c) in enumerate(((pre,'before Aug 17 (earlier builds)','#9bb7d4'),(post,'Aug 17 onward (final build)','#1f4e79'))):
    v=[stats(rs,f) for f in famsB]
    ax.bar(x+(off-0.5)*w, [a for a,_,_ in v], w, yerr=[b for _,b,_ in v], color=c, label=lab, capsize=2, error_kw=dict(lw=0.8))
    for i,(a,_,k) in enumerate(v): ax.text(x[i]+(off-0.5)*w, a+3.5, f'n={k}', ha='center', fontsize=8.5, color='#333')
ax.axhline(50, color='#999', lw=0.8, ls='--'); ax.set_ylim(0,90); ax.set_ylabel('ladder win rate (%) with 95% CI')
ax.set_xticks(x); ax.set_xticklabels(famsB, fontsize=10, rotation=20); ax.legend(fontsize=10)
ax.set_title('Ladder win rate by opponent deck (95% CI):\nstrong into Lucario / Archaludon, even into Alakazam, Grimmsnarl 45% → 52%', fontsize=12)
fig.tight_layout(); fig.savefig(OUT+'/09_ladder_matchups.png'); plt.close(fig)
# ---- Fig C: submission ratings over time
subs=list(csv.DictReader(open(BASE+'/submissions.csv')))
pts=[]
for s in subs:
    try: sc=float(s['publicScore'])
    except: continue
    fn=(s['fileName'] or '')
    lo = s['date']>='2026-07-19' and not any(k in fn.lower() for k in ('dragapult','alakazam','lucario','hop'))
    pts.append((s['date'][:10], sc, lo, s['ref']))
fig,ax=plt.subplots(figsize=(9,5.5),dpi=160)
import datetime as dt
for d,sc,lo,ref in pts:
    dd=dt.datetime.strptime(d,'%Y-%m-%d')
    ax.scatter(dd, sc, s=26 if lo else 14, color='#1f4e79' if lo else '#bbbbbb', zorder=3 if lo else 2)
fin=[p for p in pts if p[3] in ('55565056','55565424')]
for d,sc,lo,ref in fin: ax.annotate(f'final {sc}', (dt.datetime.strptime(d,'%Y-%m-%d'), sc), xytext=(-70,8), textcoords='offset points', fontsize=10, color='#d1495b')
ax.axhline(799.3, color='#d1495b', lw=0.8, ls='--')
los=[sc for _,sc,lo,_ in pts if lo]
ax.set_title(f'Converged rating of every submission\n(blue = Great Tusk lineage, {len(los)} builds, median {np.median(los):.0f}; final entries at the top of the band)', fontsize=12)
ax.set_ylabel('Kaggle rating at end of play'); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(OUT+'/10_submission_ratings.png'); plt.close(fig)
print('LO subs', len(los), 'median', np.median(los), 'max', max(los), 'min', min(los))
print('pre n', len(pre), 'post n', len(post))
for f in famsB: print(f, 'pre', stats(pre,f), 'post', stats(post,f))

# summary for text
days_n=[sum(1 for r in LO if r['date']==d) for d in days]
print('LO games', len(LO), 'subs', len(set(r['sid'] for r in LO)), 'daily wr min/max', min(wr), max(wr), 'min-day n', days_n[wr.index(min(wr))])
print('post-deadline (>=8/21) n', sum(1 for r in LO if r['date']>='2026-08-21'), 'W%', 100*sum(1 for r in LO if r['date']>='2026-08-21' and r['win'])/max(1,sum(1 for r in LO if r['date']>='2026-08-21')))
for f in fams: 
    sh=[100*share[i][fams.index(f)] for i in range(len(days))]; print(f, 'share min/max', round(min(sh)), round(max(sh)))
