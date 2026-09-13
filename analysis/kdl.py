"""Robust Kaggle episode fetcher: episode lists (with agents) for all submissions, replays for selected ones."""
import sys, os, json, time, subprocess
from kaggle.api.kaggle_api_extended import KaggleApi
BASE='/tmp/kaggle_eps'; KB=os.path.expanduser('~/projects/pokemon-tcg-ai-battle/.venv/bin/kaggle')
api=KaggleApi(); api.authenticate()
subs=sys.argv[1].split(','); replay_subs=set(sys.argv[2].split(',')) if len(sys.argv)>2 and sys.argv[2] else set()
for sid in subs:
    d=f'{BASE}/{sid}'; os.makedirs(d+'/replays', exist_ok=True)
    eps=api.competition_list_episodes(int(sid))
    rows=[]
    for e in eps:
        rows.append(dict(id=str(e.id), create_time=str(e.create_time), end_time=str(e.end_time), state=str(e.state), type=str(e.type),
            agents=[dict(index=a.index, reward=a.reward, state=str(a.state), submission_id=str(a.submission_id), team_id=str(a.team_id), team_name=a.team_name) for a in (e.agents or [])]))
    json.dump(rows, open(d+'/episodes_full.json','w'))
    print(f'[{sid}] episodes listed: {len(rows)}', flush=True)
    if sid not in replay_subs: continue
    ok=fail=skip=0
    for r in rows:
        eid=r['id']; out=f'{d}/replays/episode-{eid}-replay.json'
        if os.path.exists(out): skip+=1; continue
        for attempt in range(3):
            p=subprocess.run([KB,'competitions','replay',eid,'-p',d+'/replays','-q'],capture_output=True,text=True)
            if os.path.exists(out): ok+=1; break
            time.sleep(5*(attempt+1))
        else:
            fail+=1; open(d+'/replay_errors.txt','a').write(eid+'\t'+(p.stderr or p.stdout).strip()[-200:]+'\n')
        time.sleep(0.4)
        if (ok+fail)%50==0: print(f'[{sid}] ok={ok} fail={fail} skip={skip}', flush=True)
    print(f'[{sid}] DONE ok={ok} fail={fail} skip={skip}', flush=True)
print('ALL_DONE')
