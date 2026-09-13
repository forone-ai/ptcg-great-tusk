import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, sys, textwrap
rows=[("Rule sweep, 40 versions","hand-written heuristics only","~40,000 games","plateau at 48.7%","ceiling reached"),
("Search harness ported","determinized search + rule rollouts","15 proxies","48.7% → 67.2%","adopt (H1 confirmed)"),
("Human-review loop","reviewed fixes, SPRT-gated","n = 1,632","→ 71.2%","adopt"),
("Mid-game evaluators ×3","GBDT / policy clone / value net","matched AUC + A/B","0 of 3 cleared bar","reject"),
("Endgame PUCT","tree search in thin-deck regime","192-game gate","+7.8 pt vs one archetype, no confirmed loss","adopt (H2 confirmed)"),
("Prior ablation","rule prior vs uniform, same tree","same gate","tree structure carries the gain","keep"),
("Belief layer","probabilistic hand reading","192 × 8 opponents","58.8% → 61.5%; −6.3 pt vs Alakazam","not merged"),
("Five final submissions","one reviewed loss fixed per version","live ladder","Grimmsnarl 45% → 52%","ship")]
widths=[16,22,15,26,16]
wrap=lambda s,w: "\n".join(textwrap.wrap(s,w))
cells=[[wrap(c,w) for c,w in zip(r,widths)] for r in rows]
cols=["Step","Change","Sample","Effect (proxy league;\nsee §6 on its bias)","Decision"]
fig,ax=plt.subplots(figsize=(10,7.4),dpi=160); ax.axis('off')
tb=ax.table(cellText=cells,colLabels=cols,cellLoc='left',colLoc='left',colWidths=[0.17,0.24,0.16,0.27,0.16],bbox=[0,0,1,0.94])
tb.auto_set_font_size(False); tb.set_fontsize(10.5)
for (r,c),cell in tb.get_celld().items():
    cell.set_edgecolor('#cccccc'); cell.PAD=0.04
    txt=cell.get_text().get_text(); n=txt.count('\n')+1
    cell.set_height(0.055*max(n,2) + 0.02)
    if r==0: cell.set_facecolor('#e8eef7'); cell.set_text_props(fontweight='bold')
    elif rows[r-1][4].startswith('adopt') or rows[r-1][4] in ('ship','keep'): cell.set_facecolor('#f1f8f1')
    elif rows[r-1][4] in ('reject','not merged'): cell.set_facecolor('#fbf1f1')
fig.suptitle("Hypotheses tested: step, change, sample, effect, decision", fontsize=13, x=0.01, ha='left', y=0.99)
fig.savefig(sys.argv[1], bbox_inches='tight'); print("saved")
