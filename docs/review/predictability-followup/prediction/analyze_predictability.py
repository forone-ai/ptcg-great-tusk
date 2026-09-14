"""Post-hoc score prediction error from fixed raw continuations; no simulation."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import time
import numpy as np

SEED=2026091461
BOOTSTRAPS=4000
BANDS=('low','mid','high')
METRICS=('hidden_mse','revealed_mse','prediction_gain')


def score_error_bounds(qlo,qhi,ylo,yhi):
    lower=np.maximum(0,np.maximum(qlo-yhi,ylo-qhi))**2
    upper=np.maximum(np.abs(qlo-yhi),np.abs(qhi-ylo))**2
    return lower,upper


def metrics_for_cube(scores):
    lo=np.nan_to_num(scores,nan=0.)
    hi=np.nan_to_num(scores,nan=1.)
    sums={name:np.zeros((scores.shape[0],2)) for name in METRICS[:2]}
    folds=[]
    for wp in (0,1):
        held_worlds=np.arange(16)%2==wp
        for rp in (0,1):
            held_repeats=np.arange(32)%2==rp
            ylo=lo[:,held_worlds][:,:,held_repeats]
            yhi=hi[:,held_worlds][:,:,held_repeats]
            hidden_lo=lo[:,~held_worlds][:,:,~held_repeats].mean(axis=(1,2))[:,None,None]
            hidden_hi=hi[:,~held_worlds][:,:,~held_repeats].mean(axis=(1,2))[:,None,None]
            reveal_lo=lo[:,held_worlds][:,:,~held_repeats].mean(axis=2)[:,:,None]
            reveal_hi=hi[:,held_worlds][:,:,~held_repeats].mean(axis=2)[:,:,None]
            fold={'held_world_parity':wp,'held_repeat_parity':rp}
            for name,qlo,qhi in (('hidden_mse',hidden_lo,hidden_hi),('revealed_mse',reveal_lo,reveal_hi)):
                lower,upper=score_error_bounds(qlo,qhi,ylo,yhi)
                bounds=np.stack([lower.mean(axis=(1,2)),upper.mean(axis=(1,2))],axis=1)
                sums[name]+=bounds/4
                fold[name+'_bounds']=bounds.mean(axis=0).tolist()
            folds.append(fold)
    sums['prediction_gain']=np.stack([sums['hidden_mse'][:,0]-sums['revealed_mse'][:,1],
                                      sums['hidden_mse'][:,1]-sums['revealed_mse'][:,0]],axis=1)
    return sums,folds


def stable_rng(label):
    salt=int.from_bytes(hashlib.sha256(label.encode()).digest()[:8],'big')
    return np.random.default_rng((SEED+salt)%(2**64))


def bootstrap_bounds(records,label):
    if not records:return {'positions':0,'games':0}
    grouped={}
    for row in records:grouped.setdefault(row['game_id'],[]).append(row)
    # Equal positions within a game, then equal independent games. There is one
    # position per game in every band, enforced below.
    array=np.array([[np.mean([r[m+'_bounds'] for r in group],axis=0) for m in METRICS]
                    for group in grouped.values()])
    n=len(array)
    rng=stable_rng(label)
    boot=array[rng.integers(0,n,size=(BOOTSTRAPS,n))].mean(axis=1)
    result={'positions':len(records),'games':n,'bootstrap_replicates':BOOTSTRAPS,'metrics':{}}
    for i,name in enumerate(METRICS):
        bounds=array[:,i].mean(axis=0)
        result['metrics'][name]={'mean_bounds':bounds.tolist(),
            'outer_two_sided_95':[float(np.quantile(boot[:,i,0],.025)),float(np.quantile(boot[:,i,1],.975))]}
    return result


def paired_summary(records,nonsaturated):
    by={}
    for row in records:
        if row['band'] not in ('low','high') or row['unresolved_cells']:continue
        if nonsaturated and row['saturation'] in ('all_win','all_loss'):continue
        by.setdefault(row['game_id'],{})[row['band']]=row
    paired=[]
    ids=[]
    for game,sides in sorted(by.items()):
        if set(sides)!=set(('low','high')):continue
        ids.append(game)
        item={'game_id':game}
        for name in METRICS:
            item[name+'_bounds']=[sides['high'][name+'_bounds'][0]-sides['low'][name+'_bounds'][1],
                                  sides['high'][name+'_bounds'][1]-sides['low'][name+'_bounds'][0]]
        paired.append(item)
    result=bootstrap_bounds(paired,'paired_nonsat' if nonsaturated else 'paired_all')
    result['contrast']='high minus low within the same game; observational association'
    result['game_ids']=ids
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    source=args.source.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    assert source.name=='confirm-1'
    paths=sorted(source.glob('*.meta.json'))
    assert len(paths)==900
    final=json.loads((source/'final-summary.json').read_text())
    assert final['complete_selected_cohort']
    records=[];actions=[];input_hashes=[];seen=set();began=time.time()
    for index,path in enumerate(paths):
        meta=json.loads(path.read_text())
        assert meta['status']=='complete' and meta['phase']=='confirmatory'
        game=str(meta['game_id']);band=meta['band'];pos=meta['position_id']
        assert (game,band) not in seen
        seen.add((game,band))
        wlookup={w['world_id']:i for i,w in enumerate(meta['worlds'])}
        assert len(wlookup)==16 and meta['settings']['repeats']==32
        n=meta['n_actions'];cube=np.full((n,16,32),np.nan);observed=np.zeros_like(cube,dtype=bool)
        raw=path.with_name(path.name.replace('.meta.json','.jsonl'));digest=hashlib.sha256()
        error_kinds=Counter();first=None
        with raw.open('rb') as stream:
            for line in stream:
                digest.update(line);row=json.loads(line)
                assert row['position_id']==pos and row['band']==band
                a,w,r=int(row['action_id']),wlookup[row['world_id']],int(row['repeat'])
                assert not observed[a,w,r]
                observed[a,w,r]=True
                if first is None:first=row
                if row.get('terminal') and row.get('score_kind')=='terminal' and not row.get('error') and not row.get('own_tracking_errors'):
                    assert row['score'] in (0,.5,1)
                    cube[a,w,r]=row['score']
                else:error_kinds[str(row.get('score_kind','missing'))]+=1
        assert observed.all()
        stats,folds=metrics_for_cube(cube)
        unresolved=int(np.isnan(cube).sum())
        saturation=('unresolved' if unresolved else 'all_win' if np.all(cube==1) else
                    'all_loss' if np.all(cube==0) else 'all_draw' if np.all(cube==.5) else 'varied')
        record={'position_id':pos,'game_id':game,'band':band,'H':meta['hidden_count'],'actions':n,
            'global_turn':first.get('turn'),'own_deck':first.get('my_deck_count'),'own_prizes':first.get('my_prize_count'),
            'cells':cube.size,'unresolved_cells':unresolved,'error_kinds':dict(error_kinds),'saturation':saturation,
            **{m+'_bounds':stats[m].mean(axis=0).tolist() for m in METRICS},'folds':folds}
        if not unresolved:
            for m in METRICS:assert abs(record[m+'_bounds'][0]-record[m+'_bounds'][1])<1e-12
        records.append(record)
        for a in range(n):actions.append({'position_id':pos,'game_id':game,'band':band,'H':meta['hidden_count'],
            'action_id':a,'root_option':meta['root_options'][a],**{m+'_bounds':stats[m][a].tolist() for m in METRICS}})
        input_hashes.append({'position_id':pos,'meta_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'raw_sha256':digest.hexdigest()})
        if (index+1)%100==0:print(json.dumps({'positions':index+1,'seconds':round(time.time()-began,1)}),flush=True)
    assert Counter(r['band'] for r in records)=={'low':300,'mid':300,'high':300}
    assert sum(r['unresolved_cells'] for r in records)==185
    assert sum(r['cells'] for r in records)==final['counts']['analysis_cell_rows']
    complete=[r for r in records if not r['unresolved_cells']]
    nonsat=[r for r in complete if r['saturation'] not in ('all_win','all_loss')]
    assert len(complete)==898
    groups={}
    for name,subset in (('all900_with_unresolved_bounds',records),('complete_cases',complete),
                        ('complete_nonsaturated_posthoc',nonsat)):
        groups[name]={b:bootstrap_bounds([r for r in subset if r['band']==b],name+'_'+b) for b in BANDS}
    result={'status':'posthoc_secondary_exploratory','source':str(source),'seed':SEED,'bootstrap_replicates':BOOTSTRAPS,
        'coverage':{'all_positions':len(records),'complete_case_positions':len(complete),'nonsaturated_complete_positions':len(nonsat),
            'unresolved_cells':185,'unresolved_positions':[r for r in records if r['unresolved_cells']],
            'by_band_saturation':{b:dict(Counter(r['saturation'] for r in records if r['band']==b)) for b in BANDS}},
        'method':{'outcome':'Terminal score: win=1, draw=0.5, loss=0. This is MSE for score prediction, not a binary Brier probability score.',
            'folds':'Four symmetric held-out folds: world-index parity x repeat-index parity; indices are zero-based as saved in metadata.',
            'hidden_q':'Mean of the other 8 worlds and other 16 repeats for the same action; 128 training cells.',
            'revealed_q':'Mean of the same held-out world and other 16 repeats for the same action; 16 training cells.',
            'evaluation':'Each held-out world/repeat terminal score appears exactly once. Equal action weight within each position; equal positions/games within band.',
            'gain':'Hidden MSE minus revealed MSE; positive means the finite same-world predictor has smaller error.',
            'unresolved':'Unknown training scores and held-out scores independently bounded in [0,1], giving conservative squared-error bounds. No loss imputation. Gain lower=hidden lower-revealed upper and upper=hidden upper-revealed lower.',
            'nonsaturated':'Post-hoc subset of complete positions excluding all-cells-win and all-cells-loss positions. Unresolved positions excluded from this subset.',
            'interval':'4000 game-cluster bootstrap resamples with fixed seed; outer two-sided 95% percentile limits include unresolved-case bounds.',
            'limits':'Observational across H, fixed policies and sampled worlds with supplied complete decklists; no causal H claim, no true win-probability calibration. Predictor training sizes differ (128 vs 16), so prediction gain also reflects estimation noise. Broad score saturation can reduce MSE.'},
        'groups':groups,'paired_high_minus_low_complete':paired_summary(complete,False),
        'paired_high_minus_low_both_nonsaturated_posthoc':paired_summary(complete,True),
        'source_final_summary_sha256':hashlib.sha256((source/'final-summary.json').read_bytes()).hexdigest(),
        'analyzer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'elapsed_seconds':time.time()-began}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'input-hashes.json').write_text(json.dumps(input_hashes,indent=2)+'\n')
    for name,data in (('positions',records),('actions',actions)):
        with (out/f'{name}.jsonl').open('w') as stream:
            for row in data:stream.write(json.dumps(row)+'\n')
    with (out/'positions.csv').open('w',newline='') as stream:
        fields=['position_id','game_id','band','H','actions','saturation','cells','unresolved_cells']+[m+s for m in METRICS for s in ('_lower','_upper')]
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for r in records:writer.writerow({**{k:r[k] for k in fields[:8]},**{m+s:r[m+'_bounds'][i] for m in METRICS for i,s in enumerate(('_lower','_upper'))}})
    print(json.dumps({k:v for k,v in result.items() if k not in ('coverage','method')},indent=2))


if __name__=='__main__':main()
