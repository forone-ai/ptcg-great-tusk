"""Publication plot for post-hoc terminal-score prediction MSE."""
import argparse
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args()
root=args.directory.resolve();source=root/'summary.json';summary=json.loads(source.read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
    'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42,'text.color':'#263445',
    'axes.labelcolor':'#263445','xtick.color':'#263445','ytick.color':'#263445'})
fig,axes=plt.subplots(1,2,figsize=(11.8,7.5),sharey=True)
fig.subplots_adjust(left=.105,right=.98,top=.77,bottom=.31,wspace=.22)
fig.suptitle('Lower hidden-card counts accompany lower prediction error',x=.035,y=.965,ha='left',fontsize=16,weight='bold')
fig.text(.035,.90,'Post-hoc analysis of fixed continuations. Observational association; hidden-card count was not manipulated.',fontsize=11)
fig.text(.035,.845,'Forecast: mean terminal score from other sampled worlds. Lower error means easier score prediction.',fontsize=11)
labels=['H ≥ 35','H = 15–34','H < 15'];bands=['high','mid','low'];colors=['#E8B05A','#647487','#157F82']
groups=['all900_with_unresolved_bounds','complete_nonsaturated_posthoc']
titles=['A. All 900 positions','B. Excluding all-win / all-loss positions']
for ax,group,title in zip(axes,groups,titles):
    ax.set_title(title,loc='left',fontsize=12,weight='bold',pad=18)
    ax.set_xlim(-.45,2.45);ax.set_ylim(0,.16)
    ax.set_yticks(np.arange(0,.161,.04));ax.grid(axis='y',alpha=.17)
    for i,(band,color) in enumerate(zip(bands,colors)):
        record=summary['groups'][group][band];stats=record['metrics']['hidden_mse']
        lo,hi=stats['mean_bounds'];lower,upper=stats['outer_two_sided_95'];center=(lo+hi)/2
        ax.errorbar(i,center,yerr=[[center-lower],[upper-center]],fmt='o',color=color,
                    markersize=8,linewidth=2,capsize=6)
        ax.vlines(i,lo,hi,color=color,lw=5)
        ax.text(i,upper+.008,f'{center:.3f}',ha='center',fontsize=12,weight='bold',color='#263445')
    ax.set_xticks(range(3),[f"{label}\nn = {summary['groups'][group][band]['games']} games" for label,band in zip(labels,bands)])
    ax.tick_params(axis='x',length=0,pad=9)
axes[0].set_ylabel('Mean squared error of terminal-score forecast\n(lower = more predictable)',fontsize=11,labelpad=14)
fig.text(.035,.21,'Terminal score: win = 1, draw = 0.5, loss = 0. Actions and positions receive equal weight.',fontsize=11)
fig.text(.035,.155,'Whiskers: 95% game-bootstrap limits. In A, 185 unresolved cells are bounded in [0, 1], including training values.',fontsize=11)
fig.text(.035,.10,'In B, unresolved positions and positions where every continuation won or every continuation lost are excluded.',fontsize=11)
fig.text(.035,.045,'H counts opposing deck, hand and Prize cards. Results concern these sampled worlds and fixed policies.',fontsize=11)
for ext in ('png','svg','pdf'):fig.savefig(root/f'predictability-by-hidden-count.{ext}',dpi=240,facecolor='white')
plt.close(fig)
caption=[
'Post-hoc secondary analysis of terminal-score prediction error. Smaller mean squared error (MSE) means that the outcome scores are easier to forecast with this finite predictor; this is not a binary Brier score or a test of true winning-probability calibration. '
'The displayed predictor does not observe the held-out world configuration. For every action, worlds are divided by zero-based index parity and repeats by zero-based index parity, yielding four symmetric held-out folds. '
'The forecast is the mean score from the other eight worlds and the opposite 16 repeats (128 training cells). Each held-out world/repeat score is evaluated exactly once. '
'Action errors are averaged equally within position, then positions/games equally within band. The x-axis runs from high to low H; H is opposing deck count plus hand count plus remaining Prize count, not entropy.',
'Panel A includes all 900 sampled positions, 300 in each band. The 185 unresolved continuation cells occur in two positions (one middle, one high). '
'Every unresolved training score and test score is bounded in [0,1]; lower and upper MSE bounds propagate uncertainty through both the forecast mean and squared test error. No unresolved score is assigned a loss. '
'Points show the midpoint of the mean bounds, whose widths are visually very small. Whiskers are the lower 2.5th percentile endpoint for the lower bound and upper 97.5th percentile endpoint for the upper bound, from 4,000 game-cluster bootstrap resamples with fixed seed 2026091461.',
'Panel B is a post-hoc complete-case subset excluding positions where every action/world/repeat cell won or every cell lost. Unresolved positions are excluded. '
'The denominators are high 297, middle 220 and low 95. This subset check reduces the contribution of completely saturated outcomes; selection into it is itself outcome-dependent and is not causal adjustment.'
]
for group in groups:
    caption.append(group+':')
    for band in bands:
        record=summary['groups'][group][band];stats=record['metrics']['hidden_mse']
        caption.append(f"{band}: n={record['games']}; MSE mean bounds={stats['mean_bounds']}; outer 95% bootstrap limits={stats['outer_two_sided_95']}.")
for key in ('paired_high_minus_low_complete','paired_high_minus_low_both_nonsaturated_posthoc'):
    record=summary[key];stats=record['metrics']['hidden_mse']
    caption.append(f"Supplementary paired same-game contrast, {key}: n={record['games']}; high minus low MSE={stats['mean_bounds']}; 95% interval={stats['outer_two_sided_95']}.")
caption.extend([
'All comparisons describe associations among sampled positions under fixed continuation policies and supplied complete decklists; neither H nor visibility was randomized across positions. '
'Different game phases, action sets, matchup composition, saturation and residual world-sampling limitations can influence the pattern. '
'Auxiliary same-world predictor results are saved in summary.json: that predictor uses 16 training repeats rather than the hidden predictor’s 128 training cells, so its gain also reflects different estimation precision. It is not shown as the main result.',
f'Source: {source}; SHA256={hashlib.sha256(source.read_bytes()).hexdigest()}. Source raw-file and metadata hashes are in input-hashes.json.'
])
(root/'figurecaption.txt').write_text('\n\n'.join(caption)+'\n')
report=['# 終局得点の予測誤差：主分析後の探索的確認','',
'既存900局面の継続結果だけを再集計した追加分析です。主分析の対象や指標を変更していません。誤差は低いほど、この固定予測器で終局得点を予測しやすいことを示します。','',
'| 対象 | H高 | H中 | H低 |','|---|---|---|---|']
for group,title in zip(groups,['全900局面（未解決を有界化）','全勝・全敗と未解決を除外（探索的）']):
    cells=[]
    for band in bands:
        r=summary['groups'][group][band];m=r['metrics']['hidden_mse'];v=sum(m['mean_bounds'])/2;lo,hi=m['outer_two_sided_95']
        cells.append(f'{v:.5f} [{lo:.5f}, {hi:.5f}], n={r["games"]}')
    report.append('| '+title+' | '+' | '.join(cells)+' |')
report.extend(['','角括弧はゲーム単位4,000回bootstrapの95%区間です。全900局面の点の値は、未解決による平均範囲の中点を簡潔に表示しています。厳密な上下限はsummary.jsonに保存しています。',
'','同一試合で高帯域と低帯域の両方を持つ116試合では、高−低の誤差差は0.10190 [0.08336, 0.12024]でした。両局面とも非飽和の42試合でも0.04748 [0.01519, 0.08057]でした。',
'','未知枚数が少ない局面ほど終局得点の予測誤差が小さいという関連は、全勝・全敗を除いても残りました。ただし、見えるカードを増やす操作の因果効果を示した実験ではありません。試合段階、行動候補、相手、世界の生成条件なども異なります。',
'','方法はworld偶奇×repeat偶奇の4foldです。予測に使う128継続と、評価する継続はworldとrepeatの両方で分離しています。同world16反復の予測器は補助集計に保存していますが、訓練件数が異なるため、その差を純粋な情報効果と解釈しません。',
'','185件の未解決結果は、訓練の平均とテスト得点の両方で[0,1]に有界化しました。敗北への代入はしていません。低帯域の主分析に未解決はなく、今回の追加分析でも元データは変更していません。'])
(root/'readme-ja.md').write_text('\n'.join(report)+'\n')
print(root/'predictability-by-hidden-count.png')
