"""Search certainty vs hidden information.
Replays ladder games through the registry-restored agent; at chosen MAIN decisions the
search runs (2 s cap) and every determinized-world value is captured per option.
Writes /tmp/trace2/results.json incrementally and /tmp/trace2/progress.log.
"""
import sys, os, json, glob, random, time, math, importlib.util, traceback

AGENT_DIR = "/tmp/x16j_withopp_1789064695"
OUT_DIR = "/tmp/trace2"
PER_BUCKET = int(os.environ.get("PER_BUCKET", "12"))
MAX_PER_GAME = int(os.environ.get("MAX_PER_GAME", "2"))
MAX_TOTAL = int(os.environ.get("MAX_TOTAL", "70"))
WALL_LIMIT = float(os.environ.get("WALL_LIMIT", "1500"))
SEED = int(os.environ.get("SEED", "1"))
BUCKETS = [("H>=45", 45, 10**9), ("35-44", 35, 44), ("25-34", 25, 34), ("15-24", 15, 24), ("H<15", -10**9, 14)]
REPLAY_DIRS = ["/tmp/kaggle_eps/55565424/replays", "/tmp/kaggle_eps/55565056/replays"]

os.chdir(AGENT_DIR)
sys.path.insert(0, AGENT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)
LOG = open(os.path.join(OUT_DIR, "progress.log"), "a")
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

def bucket_of(H):
    for name, lo, hi in BUCKETS:
        if lo <= H <= hi:
            return name
    return None

def load_agent():
    spec = importlib.util.spec_from_file_location("main", os.path.join(AGENT_DIR, "main.py"))
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)
    rec = {"samples": []}
    hook = {"expect": False, "idx": None, "base": None}
    _orig_sb = main.search_begin
    def _sb(*a, **k):
        hook["expect"] = True
        return _orig_sb(*a, **k)
    main.search_begin = _sb
    _orig_step = main._step
    def _st(sid, act):
        if hook["expect"]:
            hook["idx"] = act[0] if act else None
            hook["expect"] = False
        return _orig_step(sid, act)
    main._step = _st
    if getattr(main, "_puct_mod", None) is not None:
        _orig_ptv = main._puct_mod.puct_tree_value
        def _ptv(*a, **k):
            r = _orig_ptv(*a, **k)
            rec["samples"].append((hook["idx"], float(r[1])))
            return r
        main._puct_mod.puct_tree_value = _ptv
    _orig_rc = main._rollout_cont
    def _rc(*a, **k):
        r = _orig_rc(*a, **k)
        rec["samples"].append((hook["idx"], float(r[1])))
        return r
    main._rollout_cont = _rc
    _orig_real = main._real
    def _real_w(o):
        b = _orig_real(o)
        hook["base"] = list(b) if b is not None else None
        return b
    main._real = _real_w
    return main, rec, hook, main._identify

def opp_ids_of(cur):
    op = cur["players"][1 - int(cur.get("yourIndex", 0))]
    return {pk.get("id") for pk in (op.get("active") or []) + (op.get("bench") or []) if pk}

def hidden_of(cur):
    op = cur["players"][1 - int(cur.get("yourIndex", 0))]
    return int(op.get("deckCount", 0)) + int(op.get("handCount", 0)) + len(op.get("prize") or []), op

def stats_of(vals):
    t = len(vals)
    if not t:
        return None
    m = sum(vals) / t
    var = sum((v - m) ** 2 for v in vals) / t
    return {"t": t, "mean": round(m, 4), "std": round(math.sqrt(var), 4),
            "frac_exact1": round(sum(1 for v in vals if v == 1.0) / t, 4),
            "frac_exact0": round(sum(1 for v in vals if v == 0.0) / t, 4),
            "unanimous": bool(all(v == 1.0 for v in vals) or all(v == 0.0 for v in vals)),
            "min": round(min(vals), 4), "max": round(max(vals), 4)}

files = []
for dd in REPLAY_DIRS:
    files += sorted(glob.glob(os.path.join(dd, "episode-*-replay.json")))
random.Random(SEED).shuffle(files)
log(f"files={len(files)} seed={SEED} per_bucket={PER_BUCKET} max_total={MAX_TOTAL}")

results, blocked = [], []
filled = {b[0]: 0 for b in BUCKETS}
games_used = {b[0]: set() for b in BUCKETS}
t_start = time.monotonic()
n_games_scanned = n_games_replayed = 0
main0, _, _, identify0 = load_agent()   # only for _identify during scanning

def done():
    return all(filled[b] >= PER_BUCKET for b in filled) or len(results) >= MAX_TOTAL or (time.monotonic() - t_start) > WALL_LIMIT

def dump():
    json.dump({"agent_dir": AGENT_DIR, "per_bucket": PER_BUCKET, "max_per_game": MAX_PER_GAME, "seed": SEED,
               "buckets": [b[0] for b in BUCKETS], "results": results, "blocked": blocked,
               "games_scanned": n_games_scanned, "games_replayed": n_games_replayed,
               "elapsed_s": round(time.monotonic() - t_start, 1)},
              open(os.path.join(OUT_DIR, "results.json"), "w"), indent=1)

for fn in files:
    if done():
        break
    try:
        d = json.load(open(fn))
    except Exception:
        continue
    n_games_scanned += 1
    names = (d.get("info") or {}).get("TeamNames") or []
    if names.count("GO HIROSHIMA 2") != 1:
        continue
    mi = names.index("GO HIROSHIMA 2")
    steps = d["steps"]
    ep = os.path.basename(fn).split("-")[1]
    src = fn.split("/")[3]
    cands = {}
    for si, st in enumerate(steps):
        a = st[mi]; obs = a.get("observation") or {}
        sel = obs.get("select"); cur = obs.get("current")
        if a.get("status") != "ACTIVE" or not sel or not cur or sel.get("context") != 0:
            continue
        n = len(sel.get("option") or [])
        if not (3 <= n <= 8) or sel.get("maxCount") != 1 or not obs.get("search_begin_input"):
            continue
        if identify0(opp_ids_of(cur)) is None:
            continue
        H, _ = hidden_of(cur)
        b = bucket_of(H)
        if b is None or filled[b] >= PER_BUCKET or ep in games_used[b]:
            continue
        cands.setdefault(b, []).append(si)
    if not cands:
        continue
    # replay this game with a fresh agent; try candidate steps until each wanted bucket yields one sample
    try:
        main, rec, hook, identify_real = load_agent()
    except Exception:
        log("load failed", ep); traceback.print_exc(); continue
    n_games_replayed += 1
    game_got = 0
    last_needed = max(max(v) for v in cands.values())
    opp_members = None
    for si in range(0, last_needed + 1):
        if game_got >= MAX_PER_GAME or done():
            break
        a = steps[si][mi]
        if a.get("status") != "ACTIVE":
            continue
        obs = a.get("observation") or {}
        if obs.get("select") is None:
            try:
                main.agent(obs)
            except Exception:
                pass
            continue
        b = None
        for bb, lst in cands.items():
            if si in lst and filled[bb] < PER_BUCKET and ep not in games_used[bb]:
                b = bb
        want = b is not None
        main._identify = identify_real if want else (lambda ids: None)
        n0 = len(rec["samples"]); hook["base"] = None
        t0 = time.monotonic()
        try:
            choice = list(main.agent(obs))
        except Exception:
            log("agent exception", ep, si); traceback.print_exc(); continue
        dt = time.monotonic() - t0
        if not want:
            continue
        cur = obs["current"]; sel = obs["select"]
        H, op = hidden_of(cur)
        rm = main._real_mod
        info = {"src": src, "episode": ep, "step": si, "turn": cur.get("turn"), "opp_team": names[1 - mi],
                "H": H, "bucket": b, "op_deck": op.get("deckCount"), "op_hand": op.get("handCount"), "op_prize": len(op.get("prize") or []),
                "my_deck": cur["players"][int(cur.get("yourIndex", 0))].get("deckCount"),
                "opp_ids": sorted(opp_ids_of(cur)), "n_opt": len(sel.get("option") or []),
                "opt_types": [o.get("type") for o in sel.get("option") or []],
                "rule_choice": hook["base"], "final_choice": choice,
                "rule_type": (sel["option"][hook["base"][0]].get("type") if hook["base"] else None),
                "route": getattr(rm, "get_route", lambda: None)(), "endgame_on": main._ENDGAME.get("on"),
                "forced_win": bool(getattr(rm, "_FORCED_WIN_MOVE", False)), "wall_s": round(dt, 3),
                "reward": steps[-1][mi].get("reward")}
        smp = rec["samples"][n0:]
        if not smp:
            info["reason_guess"] = ("forced_win" if info["forced_win"] else
                                    "rule_play_or_ability_non_endgame" if info["rule_type"] in (7, 10) and not info["endgame_on"] else
                                    "rule_attach_non_endgame_non_prize" if info["rule_type"] == 8 and not info["endgame_on"] and info["route"] != "prize" else
                                    "mate_guard_or_other")
            blocked.append(info)
            continue
        per = {}
        for idx, v in smp:
            per.setdefault(idx, []).append(v)
        info["per_option"] = {str(k): stats_of(v) for k, v in per.items()}
        info["per_option_values"] = {str(k): [round(x, 4) for x in v] for k, v in per.items()}
        info["n_samples"] = len(smp)
        info["chosen_stats"] = stats_of(per.get(choice[0], []))
        info["rule_stats"] = stats_of(per.get(hook["base"][0], [])) if hook["base"] else None
        info["agree"] = (hook["base"] == choice)
        results.append(info)
        filled[b] += 1; games_used[b].add(ep); game_got += 1
        log(f"[{len(results)}] ep={ep} step={si} T={info['turn']} H={H} {b} opp={info['opp_team']!r} n_opt={info['n_opt']} "
            f"rule={hook['base']} final={choice} agree={info['agree']} n={info['n_samples']} chosen_std={info['chosen_stats']['std']} wall={dt:.2f} filled={filled}")
        dump()
    try:
        main.search_end()
    except Exception:
        pass
    del main
dump()
log("DONE results", len(results), "blocked", len(blocked), "filled", filled, "scanned", n_games_scanned, "replayed", n_games_replayed,
    "elapsed", round(time.monotonic() - t_start, 1))
