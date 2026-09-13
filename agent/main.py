"""lo_solluna_v26_search: v56探索ハーネス(実戦実績あり)をLOソルルナに移植。
ルール方策=v23、ロールアウトは公式Search APIで終局まで。ローカル用に決定化数/予算を縮小。

(v56原文)v51 Kaggle budget: v49b LCB deep search, converted for submission scale.

v49b (local-league specialist, no clock) との違い:
- 時間予算マネージャ: remainingOverageTime(1試合600秒プール)を追跡し、
  1判断あたりの上限を残量に応じて縮める。残量が閾値を切ったらルールのみ。
- __file__ 非依存 (Kaggleハーネスは main.py を __file__ なしで exec する)。
- 相手プロキシ15体を bundle 内 opponents/ に同梱 (閉世界・ネット不要)。
- 探索は同梱 cg エンジン (search_begin/SearchStep) を使用。
挙動は時間が許す限り v49b と同一 (D=48, 弱対面 D=96, LCB入替ゲート)。
"""
import collections
import ctypes
import importlib.util
import json
import math
import os
import random
import sys
import time
from pathlib import Path

# --- agent dir 解決 (__file__ なしの exec に耐える) ---
_f = globals().get("__file__")
if _f:
    _D = Path(_f).resolve().parent
elif os.path.isdir("/kaggle_simulations/agent"):
    _D = Path("/kaggle_simulations/agent")
else:
    _D = Path.cwd()
if str(_D) not in sys.path:
    sys.path.insert(0, str(_D))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    d = str(Path(path).parent)
    sys.path.insert(0, d)
    try:
        spec.loader.exec_module(m)
    finally:
        if sys.path and sys.path[0] == d:
            sys.path.pop(0)
    return m


_real_mod = _load(_D / "rule_policy.py", "v26_rule_real")
_real = _real_mod.agent
_sim_mod = _load(_D / "rule_policy.py", "v26_rule_sim")
_sim = _sim_mod.agent

_SEARCH_OK = True
try:
    from cg.api import search_begin, search_end, to_observation_class
    import cg.api as _capi
    from cg.sim import lib as _lib
    _HAS_SEARCH_STEP = hasattr(_lib, "SearchStep")
except Exception:
    _SEARCH_OK = False
    _HAS_SEARCH_STEP = False

MY_DECK = [int(x) for x in (_D / "deck.csv").read_text().split() if x.strip()]

# --- 探索パラメタ (v56: 時間予算下では均一 D=48) ---
# 根拠: 弱対面D=96はリフトなしと実証済み(v49b棄却)な上、10秒キャップ下では
# スクリーニングが予算を食い潰し最終候補が統計要件(t>=24)に届かず、
# 弱対面が事実上ルールのみ化していた(v51=弱対面0-2/8)。
ROOT_DETS = int(os.environ.get("LO_SEARCH_DETS", "20"))  # 教え67: スイープ#1でtetsutani+3.1
WEAK_OPP_KEYS = ("skarin", "multiply", "masamikobayashi", "aman", "borealis", "makthanithin")
ROOT_DETS_WEAK = int(os.environ.get("LO_SEARCH_DETS", "12"))
MIN_GAP_SE = 1.0

# --- 時間予算 ---
TOTAL_BUDGET = float(os.environ.get("PTCG_OVERAGE_BUDGET", "90"))
RESERVE_FLOOR = float(os.environ.get("LO_SEARCH_FLOOR", "10"))          # これを切ったらルールのみ (安全マージン)
PER_DECISION_CAP = float(os.environ.get("LO_SEARCH_CAP", "2.0"))       # 1判断の絶対上限秒
PER_DECISION_MIN = 0.8
_budget = {"left": TOTAL_BUDGET}

# _GROUPS: footprint(ユニークid集合)が同一の同梱相手をグループ化 (v52 mixture)
_GROUPS = []
_OPP_FN = {}
try:
    _reg = json.loads((_D / "opponents" / "registry.json").read_text())
    _by_fp = {}
    for _o in _reg.get("runnable_opponents", []):
        try:
            _deck = [int(x) for x in (_D / _o["deck"]).read_text().split() if x.strip()][:60]
            _ids = frozenset(set(_deck) - set(MY_DECK) - set(range(1, 13)))
            _by_fp.setdefault(_ids, []).append((_deck, str(_D / _o["main"])))
        except Exception:
            pass
    _GROUPS = [(set(fp), members) for fp, members in _by_fp.items()]
except Exception:
    pass


def _identify(op_ids):
    best, hit = None, 0
    for ids, members in _GROUPS:
        h = len(op_ids & ids)
        if h > hit:
            best, hit = members, h
    return best


def _opp(mp):
    if mp not in _OPP_FN:
        try:
            _OPP_FN[mp] = _load(mp, "v56_opp_" + str(len(_OPP_FN))).agent
        except Exception:
            _OPP_FN[mp] = None
    return _OPP_FN[mp]


def _cid(x):
    if x is None:
        return 0
    return int(x.get("id", 0)) if isinstance(x, dict) else int(x)


def _used(p, include_hand):
    used = []
    for c in (p.get("discard") or []):
        if _cid(c):
            used.append(_cid(c))
    if include_hand:
        for c in (p.get("hand") or []):
            if _cid(c):
                used.append(_cid(c))
    for pk in (p.get("active") or []) + (p.get("bench") or []):
        if not pk:
            continue
        used.append(int(pk.get("id", 0)))
        for coll in ("energies", "tools", "cards"):
            for e in (pk.get(coll) or []):
                if _cid(e) and not (coll == "cards" and _cid(e) == int(pk.get("id", 0))):
                    used.append(_cid(e))
    return used


def _remaining(full, used):
    pool = collections.Counter(full)
    for u in used:
        if pool.get(u, 0) > 0:
            pool[u] -= 1
    return list(pool.elements())


try:
    from cg.api import all_card_data as _acd
    _POKE_IDS = {c.cardId for c in _acd() if getattr(c, "hp", 0)}
except Exception:
    _POKE_IDS = set()


def _weighted_hand_sample(pool, k, rng):
    """Belief誘導の決定化(§11): 手札滞留係数で重み付けサンプリング。
    実測(19.9万局面): ポケモン1.63x / その他≈0.85x。A-Res法(シード決定的)。"""
    if k <= 0 or not pool:
        return [], list(pool)
    keyed = []
    for i, cid in enumerate(pool):
        w = 1.6 if cid in _POKE_IDS else 0.85
        keyed.append((rng.random() ** (1.0 / w), i, cid))
    keyed.sort(reverse=True)
    hand_idx = {i for _, i, _ in keyed[:k]}
    hand = [cid for _, i, cid in keyed[:k]]
    rest = [cid for i, cid in enumerate(pool) if i not in hand_idx]
    rng.shuffle(rest)
    return hand, rest


def _fills(od, mi, opp_deck, seed):
    st = od["current"]; me, op = st["players"][mi], st["players"][1 - mi]
    rng = random.Random(seed)
    myp = _remaining(MY_DECK, _used(me, True)); rng.shuffle(myp)
    nd, npz = me["deckCount"], len(me.get("prize", []))
    myp = (myp + MY_DECK)[: nd + npz]
    opp_p = _remaining(opp_deck, _used(op, False)); rng.shuffle(opp_p)
    odk, opz, oh = op["deckCount"], len(op.get("prize", [])), op["handCount"]
    # 完全情報化(go研究テーマ 2026-07-28): ログで確定した相手手札を想像に強制注入。
    # 削るほど公開札が増え、想像が真実に収束する(不完全情報の漸進的完全情報化)
    _hand_known = []
    try:
        _hk = getattr(_real_mod, "_ROUTE_STATE", {}).get("opp_hand_known") or {}
        _hand_known = list(_hk.values())[:oh]
        for _c in _hand_known:
            if _c in opp_p:
                opp_p.remove(_c)
    except Exception:
        _hand_known = []
    opp_p = (opp_p + opp_deck)[: odk + opz + max(0, oh - len(_hand_known))]
    opp_hand, opp_rest = _weighted_hand_sample(opp_p, max(0, oh - len(_hand_known)), rng)
    opp_hand = _hand_known + opp_hand
    return (myp[:nd], myp[nd:nd + npz], opp_rest[:odk], opp_rest[odk:odk + opz],
            opp_hand,
            [opp_p[0] if opp_p else opp_deck[0]]
            if (op.get("active") and op["active"] and op["active"][0] is None) else [])


def _step(sid, picks):
    bs = _lib.SearchStep(_capi.agent_ptr, sid, (ctypes.c_int * len(picks))(*picks), len(picks))
    res = json.loads(bs)
    if res.get("error", 1) != 0:
        raise ValueError(f"err{res.get('error')}")
    return res["state"]


# 打ち切りロールアウトのリーフ評価: 5万局面から直接フィットした線形値関数
# (AUC0.825/較正±1-3%, rollout_value_v1.json 2026-07-24)。決定的な係数のみ使用。
# 価値関数v3(プラン条件付き2セット, 2026-07-28): routeがprizeなら攻めの直感、他は削りの直感
_V3 = {"attack": {"_VB": -2.00818882833574, "_VW": {"turn": 0.08204444468236487, "my_deck": -0.02306481807630291, "my_hand": 0.07135512718059703, "my_prize": 0.24545865958858198, "my_board": -0.009692878356785206, "my_dmg": 0.0, "my_energy": 0.16217139891068102, "my_tusk": 0.04687815734733279, "my_crustle": -0.06631567159673629, "op_deck": -0.0332484393546311, "op_hand": 0.014451008116894436, "op_prize": 0.3821118042242251, "op_board": -0.42345590357585844, "op_dmg": 0.0, "op_energy": -0.08453768779277523, "op_tusk": 0.0, "op_crustle": 0.0, "deck_diff": 0.05868404438659843, "prize_diff": -0.34751213272560894, "op_weak_grass": 0.390768846412684, "my_armed_crustle": -0.06185710478734793, "op_ex_board": 0.1445096336007881, "my_bench_energy": -0.08482571603452498}, "auc_val": 0.7412}, "default": {"_VB": -0.5338913756947474, "_VW": {"turn": 0.05144532490958412, "my_deck": -0.05916031771899841, "my_hand": 0.13186801243740692, "my_prize": 0.4614393841868869, "my_board": 0.06097218054652763, "my_dmg": 0.0, "my_energy": 0.291143571165365, "my_tusk": -0.0331667407478107, "my_crustle": -0.08444147930706519, "op_deck": -0.04613486749421906, "op_hand": -0.04196774809115094, "op_prize": 0.35554142634083663, "op_board": -0.3229072109806586, "op_dmg": 0.0, "op_energy": -0.12152322969291732, "op_tusk": 0.0, "op_crustle": 0.0, "deck_diff": 0.05239887463802611, "prize_diff": -0.33087286848979514, "op_weak_grass": 0.4633789139097613, "my_armed_crustle": -0.16258315616565866, "op_ex_board": -0.09135474635670439, "my_bench_energy": -0.06004027723239162}, "auc_val": 0.8041}}
_V3_KEYS = ["turn", "my_deck", "my_hand", "my_prize", "my_board", "my_dmg", "my_energy", "my_tusk", "my_crustle", "op_deck", "op_hand", "op_prize", "op_board", "op_dmg", "op_energy", "op_tusk", "op_crustle", "deck_diff", "prize_diff", "op_weak_grass", "my_armed_crustle", "op_ex_board", "my_bench_energy"]
_VW = _V3['default']['_VW']
_VB = _V3['default']['_VB']
ROLLOUT_CUTOFF = int(os.environ.get("LO_ROLLOUT_CUTOFF", "60"))
# 詰め探索モード(go設計 2026-07-30): 終盤は自山が完全既知・相手もほぼ既知=準完全情報。
# 決定化は「既知の山の並べ替え」なのでロールアウト終端=本物の勝敗。
# カットオフを伸ばして終端まで読み、価値関数でなく実際の勝率で指す
ENDGAME_CUTOFF = int(os.environ.get("LO_ENDGAME_CUTOFFF", "170"))
_ENDGAME = {"on": False}


def _endgame_check(cur, mi):
    try:
        ps = cur.get("players") or [{}, {}]
        _ENDGAME["on"] = min(int(ps[0].get("deckCount", 99)), int(ps[1].get("deckCount", 99))) <= 14
    except Exception:
        _ENDGAME["on"] = False
    return _ENDGAME["on"]


# --- 終盤限定PUCT(2026-08-11移植, 出典=lo_crustle_weakmath_v1_combined 2026-08-04) ---
# 終盤(_ENDGAME on=山14枚以下)のロールアウトを「1本道」から「PUCT木(12sims)」へ。
# 非終盤はsims=1で従来の_rollout_contと同一(等価性はpuct_tree.py設計で保証)なので
# 呼び分けで従来コードをそのまま使う。M2の教訓(-5.2pt=誤差増幅)への対策=終盤限定。
try:
    _puct_mod = _load(_D / "puct_tree.py", "lo_puct_tree")
except Exception:
    _puct_mod = None   # 同梱漏れ等でもエージェントは従来動作で生存
LO_PUCT_SIMS_ENDGAME = int(os.environ.get("LO_PUCT_SIMS_ENDGAME", "12"))
LO_PUCT_CPUCT = float(os.environ.get("LO_PUCT_CPUCT", "1.5"))
LO_PUCT_TEMPERATURE = float(os.environ.get("LO_PUCT_TEMPERATURE", "0.5"))


def _puct_cutoff():
    return ENDGAME_CUTOFF if _ENDGAME.get("on") else ROLLOUT_CUTOFF


def _puct_sim_score(o):
    """puct_tree用の採点取得。v28系rule_policyには_score_options分割が無いため、
    simモジュールのagentを1回走らせてlast_option_scores_finalを読むアダプタで
    「1決定=採点1回+同じ副作用」の契約(puct_tree.py設計)を満たす。"""
    try:
        _sim(o)
        sc = list(getattr(_sim_mod, "last_option_scores_final", []) or [])
        so = to_observation_class(o).select
        return so, sc
    except Exception:
        return None, []


try:
    from cg.api import all_card_data as _acd
    _WEAK_GRASS = {c.cardId for c in _acd() if getattr(c, "weakness", None) == 1}
    _EX_IDS = {c.cardId for c in _acd()
               if getattr(c, "ex", False) or getattr(c, "megaEx", False)}
except Exception:
    _WEAK_GRASS = set(); _EX_IDS = set()


def _value_eval(cur, mi):
    try:
        me = cur["players"][mi]; op = cur["players"][1 - mi]
        def z(p, pre):
            board = [pk for pk in (p.get("active") or []) + (p.get("bench") or []) if pk]
            ids = [pk.get("id") for pk in board]
            return {
                pre + "_deck": p.get("deckCount", 0), pre + "_hand": p.get("handCount", 0),
                pre + "_prize": len(p.get("prize") or []), pre + "_board": len(board),
                pre + "_dmg": sum(int(pk.get("damage", 0) or 0) for pk in board),
                pre + "_energy": sum(len(pk.get("energyCards") or []) for pk in board),
                pre + "_tusk": ids.count(58), pre + "_crustle": ids.count(345),
            }
        f = {"turn": cur.get("turn", 0)}
        f.update(z(me, "my")); f.update(z(op, "op"))
        f["deck_diff"] = f["my_deck"] - f["op_deck"]
        f["prize_diff"] = f["my_prize"] - f["op_prize"]
        _mb = [pk for pk in (me.get("active") or []) + (me.get("bench") or []) if pk]
        _ob = [pk for pk in (op.get("active") or []) + (op.get("bench") or []) if pk]
        f["op_weak_grass"] = sum(1 for pk in _ob if pk.get("id") in _WEAK_GRASS)
        f["my_armed_crustle"] = sum(1 for pk in _mb if pk.get("id") == 345
                                    and len(pk.get("energyCards") or []) >= 3)
        f["op_ex_board"] = sum(1 for pk in _ob if pk.get("id") in _EX_IDS)
        f["my_bench_energy"] = sum(len(pk.get("energyCards") or [])
                                   for pk in (me.get("bench") or []) if pk)
        _set = _V3["attack"] if getattr(_real_mod, "_ROUTE_STATE", {}).get("route") == "prize" else _V3["default"]
        s_ = _set["_VB"]
        for k, wk in _set["_VW"].items():
            s_ += wk * f.get(k, 0)
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, s_))))
    except Exception:
        return 0.5


def _rollout_cont(state, mi, opp_fn):
    sid = state["searchId"]
    for _rs in range(400):
        o = state["observation"]
        cur = o.get("current")
        if cur is None:
            return None, 0.5
        r = int(cur.get("result", -1))
        if r != -1:
            return None, (1.0 if r == mi else 0.0)
        if _rs >= (ENDGAME_CUTOFF if _ENDGAME.get("on") else ROLLOUT_CUTOFF):
            # 打ち切り: 線形値関数で期待勝率評価(終端まで回すより3-5倍のシミュ数を確保)
            return None, _value_eval(cur, mi)
        sel = o.get("select") or {}
        n = len(sel.get("option") or [])
        acting = int(cur.get("yourIndex", mi))
        if acting == mi:
            try:
                picks = _sim(o)
            except Exception:
                picks = list(range(min(max(sel.get("minCount", 1), 1), n)))
        else:
            picks = None
            if opp_fn:
                try:
                    picks = opp_fn(o)
                except Exception:
                    picks = None
            if picks is None:
                k = max(sel.get("minCount", 1), 1)
                picks = random.sample(range(n), min(k, n)) if n else []
        state = _step(sid, picks)
        sid = state["searchId"]
    return None, 0.5


_game = {"last_turn": None}


def agent(obs_dict: dict) -> list:
    t0 = time.monotonic()
    if obs_dict.get("select") is None:
        # 新規ゲームのデッキ提出 = 持ち時間プールをリセット
        # (Kaggle本番は毎試合新プロセスなので無影響。ローカル連戦評価用)
        _budget["left"] = TOTAL_BUDGET
        _game["last_turn"] = None
    else:
        # デッキ選択obsを渡さないローカルランナー向け: ターンの巻き戻り=新規ゲーム
        try:
            _t = int((obs_dict.get("current") or {}).get("turn", 0))
            if _game["last_turn"] is None or _t < _game["last_turn"]:
                _budget["left"] = TOTAL_BUDGET
            _game["last_turn"] = _t
        except Exception:
            pass
    base = _real(obs_dict)
    try:
        if not _SEARCH_OK or not _HAS_SEARCH_STEP:
            return base
        sel = obs_dict.get("select"); cur = obs_dict.get("current")
        if not sel or not cur or not obs_dict.get("search_begin_input"):
            return base
        if getattr(_real_mod, "_FORCED_WIN_MOVE", False):
            # リーサル安全網: ルールが「確実な勝ち手」を検出済み。探索に触れさせず即return
            _budget["left"] -= (time.monotonic() - t0)
            return base
        # remainingOverageTime が観測に来ていれば正とする (Kaggle 本番)
        rot = obs_dict.get("remainingOverageTime")
        if rot is not None:
            try:
                _budget["left"] = float(rot)
            except Exception:
                pass
        if _budget["left"] <= RESERVE_FLOOR:
            return base
        if sel.get("maxCount") != 1 or sel.get("minCount", 0) > 1:
            return base
        if int(sel.get("context", -1)) != 0:
            # 探索の管轄限定(2026-08-02 ep89516671): 探索はメイン行動の比較のみ。
            # サーチ先などの「効果内カード選択」は影響が長期に出るため浅い読みでは
            # 判定不能で、wants機構(ルール)の答えをランダム化していた
            # (実測: 同一局面3回でキバ/イシズマイ/イワパレスと揺れる)
            return base
        # 詰め保護(2026-08-02 ep89476451 T27): 削りルートで相手山が10枚以下、
        # かつルールが攻撃(=ミル)を選んだら探索に触らせない。浅い読み(~30本)の
        # 上書きが「勝ち確レースの1ターン」を捨てる事故の再発防止(v56h LAST_CAN_WIN系譜)
        try:
            _opx = (cur.get("players") or [{}, {}])[1 - int(cur.get("yourIndex", 0))]
            _opts = sel.get("option") or []
            if (base and _opts and int(_opx.get("deckCount", 99)) <= 10
                    and int((_opts[base[0]] or {}).get("type", -1)) == 13
                    and getattr(_real_mod, "get_route", lambda: "")() == "deck_out"):
                return base
        except Exception:
            pass
        n = len(sel.get("option") or [])
        if not (2 <= n <= 10):
            return base
        mi = int(cur.get("yourIndex", 0))
        op = (cur.get("players") or [{}, {}])[1 - mi]
        op_ids = {pk.get("id") for pk in (op.get("active") or []) + (op.get("bench") or []) if pk}
        members = _identify(op_ids)
        if not members:
            return base
        obs_dc = to_observation_class(obs_dict)
        weak = any(any(k in mp for k in WEAK_OPP_KEYS) for _, mp in members)
        dets = ROOT_DETS_WEAK if weak else ROOT_DETS

        # 1判断の締切: 残量に比例して縮める
        cap = max(PER_DECISION_MIN, min(PER_DECISION_CAP, (_budget["left"] - RESERVE_FLOOR) / 40.0))
        deadline = t0 + cap
        # 決定化 d ごとに (デッキ, 方策) を群内ローテーション: 相手不確実性のmixture
        det_plan = []
        for d in range(dets):
            deck_m, mp_m = members[d % len(members)]
            det_plan.append((_fills(obs_dict, mi, deck_m, 5000 + d), _opp(mp_m)))
        rule_idx = base[0] if base else 0
        # 決定化ロールアウトはドロー/サーチ/展開の情報価値を評価できない
        # (未来が既知の世界ではドローはコストにしか見えない)。
        # ルールがそれらを提案した時、探索に却下権を与えない。
        _opts = sel.get("option") or []
        _rt = _opts[rule_idx].get("type") if rule_idx < len(_opts) else None
        _mirror = 58 in op_ids  # 相手にイダイナキバ=LOミラー
        _weakmu = getattr(_real_mod, "_ROUTE_STATE", {}).get("route") == "prize"
        _eg = _endgame_check(cur, mi)
        # 教え10候補(go指摘 2026-08-09 ep91200095): 決定化探索はサーチの情報価値を
        # 測れない(未来既知の世界ではサーチ=コスト)。ルール1位がPLAY(7)/特性(10)なら
        # 攻めルート(weakmu)でも上書き禁止を維持する。エネ装着(8)だけは従来どおり
        if _rt in (7, 10) and not _mirror and not _eg:
            return base
        if _rt == 8 and not _mirror and not _weakmu and not _eg:
            # 詰め探索モード中はルール優先を解除: リーリエ/ディグ/入れ替えも
            # 「既知の山からの実測勝率」で計算して決める(go: 最後の詰めは予測できるはず)
            # PLAY/ATTACH/ABILITY(非ミラーのみルール優先)。弱点マッチアップ中は例外:
            # 正しい相手モデル(アグロプロキシ)を持つ探索に展開/エネ配分も評価させる
            return base
        # (旧)prizeルート全面ルール優先は撤去(2026-07-28): 相手モデル+価値v2+weakmath
        # ロールアウトなら攻めの価値を評価できる。プラン整合の枝刈りで代替。
        if os.environ.get("PUCT_DEBUG") and _eg:
            print(f"[dbgEG] 終盤探索決定に到達 rt={_rt}", file=sys.stderr, flush=True)
        _cand = list(range(n))
        if _mirror:
            # go教示(2026-07-30 ep88845055): 「キバに3エネ目はありえない」。
            # ミラーは探索に装着の裁量があるため(旧実測の名残)、価値関数の
            # エネ好きが3枚目を通していた。2エネ以上のキバへの装着を候補から物理削除
            try:
                _meP = cur.get("players", [{}, {}])[mi]
                _act_l = _meP.get("active") or []
                _ben_l = _meP.get("bench") or []
                _dropE = set()
                for _i, _o in enumerate(_opts):
                    if _o.get("type") != 8:
                        continue
                    _tg = _o.get("inPlayIndex")
                    for _fld in (_act_l, _ben_l):
                        if isinstance(_tg, int) and _tg < len(_fld) and _fld[_tg]:
                            _pk = _fld[_tg]
                            if _pk.get("id") == 58 and len(_pk.get("energyCards") or []) >= 2:
                                _dropE.add(_i)
                _cand = [i2 for i2 in _cand if i2 not in _dropE]
                if not _cand:
                    _cand = list(range(n))
            except Exception:
                pass
        if _weakmu:
            # プラン整合(go): 弱点対面では「キバを出す」を候補から外す(線ゼロの保険時以外)
            try:
                _meP = cur.get("players", [{}, {}])[mi]
                _hand = _meP.get("hand") or []
                _board = [pk for pk in (_meP.get("active") or []) + (_meP.get("bench") or []) if pk]
                _has_line = any(pk.get("id") in (344, 345) for pk in _board)
                if _board and (_has_line or any((c_.get("id") in (344,)) for c_ in _hand)):
                    _drop = set()
                    _line_open = any(pk.get("id") in (344, 345)
                                     and len(pk.get("energyCards") or []) < 3
                                     for pk in _board)
                    for _i, _o in enumerate(_opts):
                        if _o.get("type") == 7:
                            _hi = _o.get("index", -1)
                            if 0 <= _hi < len(_hand) and _hand[_hi].get("id") == 58:
                                _drop.add(_i)

                    _cand = [i2 for i2 in _cand if i2 not in _drop]
                    if rule_idx in _drop and _cand:
                        pass  # ルール手が枝刈り対象ならルール手は候補比較から除外される
            except Exception:
                pass
        stats = {idx: [0, 0] for idx in _cand} or {idx: [0, 0] for idx in range(n)}

        def add_samples(idx, plan_sub):
            if os.environ.get("PUCT_DEBUG"):
                print(f"[dbg] add_samples eg={_ENDGAME.get('on')} idx={idx}", file=sys.stderr, flush=True)
            for f, ofn in plan_sub:
                if time.monotonic() > deadline:
                    return False
                try:
                    root = search_begin(obs_dc, *f)
                    st = _step(root.searchId, [idx])
                    if _puct_mod is not None and _ENDGAME.get("on"):
                        _pctx = {"step": _step, "sim_score": _puct_sim_score,
                                 "sim_agent": _sim, "value_eval": _value_eval,
                                 "cutoff": _puct_cutoff, "c_puct": LO_PUCT_CPUCT,
                                 "temperature": LO_PUCT_TEMPERATURE}
                        _, v = _puct_mod.puct_tree_value(st, mi, ofn, LO_PUCT_SIMS_ENDGAME, deadline, _pctx)
                    else:
                        _, v = _rollout_cont(st, mi, ofn)
                    stats[idx][0] += v; stats[idx][1] += 1
                except Exception as _e:
                    if os.environ.get("PUCT_DEBUG"):
                        import traceback as _tb
                        print("[dbgERR]", repr(_e), file=sys.stderr, flush=True)
                        _tb.print_exc(limit=3, file=sys.stderr)
            return True

        # 禁じ手ガード(2026-08-03 ep89649890): ルールが負点=教義として禁止した手
        # (削り対面のボス浪費等)は探索の候補にすら入れない。40本級の浅い読みが
        # 禁止手を復活させる第4の上書き事故の封鎖。ルール手自身は常に候補に残る
        try:
            _rs = getattr(_real_mod, "last_option_scores", None)
            if isinstance(_rs, list) and len(_rs) == n:
                _cand = [i2 for i2 in _cand if i2 == rule_idx or _rs[i2] >= 0]
        except Exception:
            pass
        screen = max(4, min(8, dets // 2))
        for idx in _cand:
            if not add_samples(idx, det_plan[:screen]):
                break

        def mean(idx):
            w, t = stats[idx]
            return w / t if t else 0.0

        order = sorted(_cand, key=lambda i: -mean(i))
        finalists = {rule_idx} | set(order[:2])
        for idx in finalists:
            if not add_samples(idx, det_plan[screen:]):
                break
        # 大岩①(go承認 2026-08-10): 時間予算の使い切り。固定12決定化で仕事が尽きて
        # 締切(cap)の6割を捨てていた(実測33/90秒)。締切まで新しい決定化(新シード)を
        # 生成してファイナリストに追加サンプル=同じ判断をより多くの想定世界で検証する
        _d_extra = dets
        while time.monotonic() < deadline - 0.05:
            _deck_x, _mp_x = members[_d_extra % len(members)]
            _plan1 = [(_fills(obs_dict, mi, _deck_x, 5000 + _d_extra), _opp(_mp_x))]
            _d_extra += 1
            if not all(add_samples(idx, _plan1) for idx in finalists):
                break
        search_end()
        if rule_idx not in stats:
            # ルール手が枝刈りされた場合: 候補中の最善を採用
            _budget["left"] -= (time.monotonic() - t0)
            _bестidx = max(stats, key=lambda i2: (stats[i2][0] / stats[i2][1]) if stats[i2][1] else 0.0) if stats else rule_idx
            return [_bестidx]
        rv, rt = stats[rule_idx]
        if rt < 8:
            # 時間切れで標本不足 → 統計判断せずルール手
            _budget["left"] -= (time.monotonic() - t0)
            return base
        rmean = rv / rt
        best_idx, best_lcb = rule_idx, -1.0
        for idx in finalists:
            if idx == rule_idx:
                continue
            w, t = stats[idx]
            if t < max(8, dets // 2):
                # (2026-08-01切り分け) 最低24本化は上書き機能を事実上封印し
                # フーディン-19ptの過剰矯正だった。8に戻す。本番の薄い読み対策は
                # END上書き禁止+テレメトリ校正で行う
                continue
            p = w / t
            se = math.sqrt(max(p * (1 - p), 0.04) / t)
            lcb = p - MIN_GAP_SE * se
            try:
                _o = (sel.get("option") or [])[idx]
                _is_end = int(_o.get("type", -1)) == 14
            except Exception:
                _is_end = False
            if _is_end:
                # 探索上書きガード(2026-07-31 ep89110427): 本番の遅いCPUでは標本が薄く、
                # 「何もしないEND」が過大評価されてルールの建設的な手(進化/ハンマー)を
                # 潰していた。ENDへの上書きはルール自身がENDを選んだ時以外は禁止
                continue
            if lcb > rmean and p - rmean > 0.06 and lcb > best_lcb:
                best_idx, best_lcb = idx, lcb
        _budget["left"] -= (time.monotonic() - t0)
        # 本番テレメトリ(2026-07-31): 探索の読み本数と上書き有無をstderrへ。
        # Kaggleのエピソードログで回収でき、本番マシンの実効探索量を校正できる
        try:
            print(f"[srch] t={rt + sum(s2[1] for i2, s2 in stats.items() if i2 != rule_idx)}"
                  f" rule_t={rt} ovr={int(best_idx != rule_idx)}", file=sys.stderr, flush=True)
        except Exception:
            pass
        if best_idx != rule_idx and os.environ.get("LO_LOG_DISAGREE"):
            # Expert Iteration用計装(plan §17.1/§17.3): 探索がルールを上書きした局面を記録
            try:
                import json as _json
                _opts = sel.get("option") or []
                _me = cur.get("players", [{}, {}])[mi]
                _op = cur.get("players", [{}, {}])[1 - mi]
                def _optdesc(i):
                    o = _opts[i] if i < len(_opts) else {}
                    hd = (_me.get("hand") or [])
                    cidx = o.get("index", -1)
                    cid = None
                    if o.get("type") in (7, 8) and 0 <= cidx < len(hd):
                        cid = hd[cidx].get("id")
                    elif cid is None and 0 <= cidx:
                        # 選択系(山サーチ/公開領域): select.deck から解決を試みる
                        dk = sel.get("deck") or []
                        if cidx < len(dk) and isinstance(dk[cidx], dict):
                            cid = dk[cidx].get("id")
                    return {"type": o.get("type"), "cardId": cid, "attackId": o.get("attackId"),
                            "ctx": sel.get("context")}
                rec = {"turn": cur.get("turn"), "route": getattr(_real_mod, "_ROUTE_STATE", {}).get("route"),
                       "my_deck": _me.get("deckCount"), "op_deck": _op.get("deckCount"),
                       "opp_ids": sorted({pk.get("id") for pk in (_op.get("active") or []) + (_op.get("bench") or []) if pk}),
                       "rule": _optdesc(rule_idx), "search": _optdesc(best_idx),
                       "rule_mean": round(rmean, 3), "search_lcb": round(best_lcb, 3)}
                with open(os.environ["LO_LOG_DISAGREE"], "a") as _f:
                    _f.write(_json.dumps(rec) + "\n")
            except Exception:
                pass
        return [best_idx]
    except Exception:
        try:
            search_end()
        except Exception:
            pass
        _budget["left"] -= (time.monotonic() - t0)
        return base
