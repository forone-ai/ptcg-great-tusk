"""Replay one Kaggle episode's observations through the agent, sequentially, and
record the agent's choice at every main decision; hook the search internals on
TARGET steps to capture per-option sample values.

usage: run_trace.py AGENT_DIR EPISODE_ID TARGET_STEPS(csv) OUT_JSON
"""
import sys, os, json, time, hashlib, importlib.util, math

AGENT_DIR, EP, TARGETS, OUT = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")], sys.argv[4]
os.chdir(AGENT_DIR)
sys.path.insert(0, AGENT_DIR)
spec = importlib.util.spec_from_file_location("main", os.path.join(AGENT_DIR, "main.py"))
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)
assert hasattr(main, "_step"), "main._step missing"
assert hasattr(main, "search_begin"), "main.search_begin missing"

# --- hooks -----------------------------------------------------------------
rec = {"samples": []}          # (step, opt_idx, value)
hook = {"expect": False, "idx": None, "cur": None}
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
        rec["samples"].append((hook["cur"], hook["idx"], float(r[1])))
        return r
    main._puct_mod.puct_tree_value = _ptv
_orig_rc = main._rollout_cont
def _rc(*a, **k):
    r = _orig_rc(*a, **k)
    rec["samples"].append((hook["cur"], hook["idx"], float(r[1])))
    return r
main._rollout_cont = _rc
_orig_identify = main._identify

# --- replay ------------------------------------------------------------------
d = json.load(open(f"/tmp/kaggle_eps/55565424/replays/episode-{EP}-replay.json"))
names = d["info"]["TeamNames"]
mi = names.index("GO HIROSHIMA 2")
steps = d["steps"]
last = max(TARGETS)
rows = []
def sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()
for si in range(0, last + 1):
    a = steps[si][mi]
    obs = a.get("observation") or {}
    if a.get("status") != "ACTIVE" or not obs.get("select"):
        continue
    recorded = steps[si + 1][mi]["action"] if si + 1 < len(steps) else None
    is_target = si in TARGETS
    main._identify = _orig_identify if is_target else (lambda ids: None)
    hook["cur"] = si
    h0 = sha(obs)
    n0 = len(rec["samples"])
    print(f"[trace] step={si} target={int(is_target)}", file=sys.stderr, flush=True)
    t0 = time.monotonic()
    choice = main.agent(obs)
    dt = time.monotonic() - t0
    h1 = sha(obs)
    sel = obs["select"]; cur = obs["current"]
    rm = main._real_mod
    row = {
        "step": si, "turn": cur.get("turn"), "ctx": sel.get("context"), "n_opt": len(sel.get("option") or []),
        "recorded": recorded, "choice": list(choice), "match": (list(choice) == list(recorded)) if recorded is not None else None,
        "wall_s": round(dt, 3), "sha_before": h0, "sha_after": h1, "target": is_target,
        "route": getattr(rm, "get_route", lambda: None)(),
        "forced_win": bool(getattr(rm, "_FORCED_WIN_MOVE", False)),
        "endgame_on": main._ENDGAME.get("on"), "budget_left": main._budget.get("left"),
        "rule_scores": list(getattr(rm, "last_option_scores", None) or []),
        "rule_scores_final": list(getattr(rm, "last_option_scores_final", None) or []),
        "n_samples": len(rec["samples"]) - n0,
    }
    if is_target:
        smp = [s for s in rec["samples"][n0:]]
        per = {}
        for _, idx, v in smp:
            per.setdefault(idx, []).append(v)
        stat = {}
        for idx, vs in per.items():
            t = len(vs); p = sum(vs) / t
            se = math.sqrt(max(p * (1 - p), 0.04) / t)
            stat[str(idx)] = {"t": t, "mean": round(p, 4), "lcb": round(p - main.MIN_GAP_SE * se, 4),
                              "vals_head": [round(x, 3) for x in vs[:5]],
                              "n_exact_1": sum(1 for x in vs if x == 1.0), "min_val": min(vs), "max_val": max(vs)}
        row["search_stats"] = stat
        row["options"] = sel.get("option")
        row["hand"] = [c.get("id") for c in (cur["players"][cur["yourIndex"]].get("hand") or [])]
    rows.append(row)
    print(json.dumps({k: row[k] for k in ("step", "turn", "ctx", "n_opt", "recorded", "choice", "match", "wall_s", "route", "n_samples")}), flush=True)

json.dump({"agent_dir": AGENT_DIR, "episode": EP, "team_names": names, "my_index": mi, "targets": TARGETS,
           "env": {k: os.environ.get(k) for k in ("PUCT_DEBUG", "LO_SEARCH_DETS", "LO_SEARCH_CAP")},
           "rows": rows}, open(OUT, "w"), indent=1)
n_main = sum(1 for r in rows if r["ctx"] == 0)
print("SUMMARY steps_fed", len(rows), "main_steps", n_main, "matches", sum(1 for r in rows if r["match"]),
      "mismatch_steps", [r["step"] for r in rows if r["match"] is False], flush=True)
