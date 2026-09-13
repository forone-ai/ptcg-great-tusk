"""M2 v1: 決定化1つにつき本物の木を1本育てるPUCT探索。

学習済みモデルは一切使わない: 事前分布(prior)は既存rule_policyのスコアをsoftmax
正規化したもの、リーフ評価は既存の_value_evalをそのまま流用する。

設計上の最重要制約(main.py側の呼び出しで LO_PUCT_SIMS=1 を渡した場合):
現行main.pyの_rollout_cont(1本道ロールアウト)と完全に同一の意思決定列を返すこと。
これは「木のノードを初めて訪れた時は、必ずルール方策と同じ手を選ぶ」という規則
(_find_or_make_nodeのfirst_idx)によって保証される。S=1では全てのノードがその
シミュレーション中で初訪問になるため、結果として現行のルール自動操縦と同じ経路を辿る。
"""
import math
import random
import time


def make_prior(scores, temperature):
    """決定内min-max正規化してからsoftmax。rule_policyの生スコアは条件によって
    数千〜十万単位で跳ねる(例: 退却130000、詰み優先520000級)ため、生スコアに
    そのままexpを掛けるとほぼ全部one-hotに潰れる。0-1に正規化してから温度を掛ける。"""
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [1.0 / len(scores)] * len(scores)
    norm = [(s - lo) / (hi - lo) for s in scores]
    t = max(1e-6, temperature)
    exps = [math.exp(v / t) for v in norm]
    z = sum(exps)
    return [e / z for e in exps]


def select_by_rule(select_obj, scores):
    """rule_policy._agentの最終選択ロジックの複製。select_objはto_observation_class
    経由のクラスインスタンス(maxCount/minCountは属性アクセス)。分岐ノードは
    maxCount==1限定なので通常は長さ1、まれに(全候補マイナス評価かつminCount==0)
    空リストになりうる——その場合は呼び出し側でargmaxにフォールバックする。"""
    n = len(scores)
    order = sorted(range(n), key=lambda i: scores[i], reverse=True)
    picks = []
    for idx in order:
        if len(picks) >= select_obj.maxCount:
            break
        if scores[idx] >= 0 or len(picks) < select_obj.minCount:
            picks.append(idx)
    return picks


def is_branch(sel, n):
    """分岐点として木のノードにする決定点かどうか。rootの探索対象ゲート
    (main.py: context==MAIN, maxCount==1, minCount<=1, 2<=n<=10)と同じ基準を、
    ロールアウト内の「自分の以降の主要判断」にも一律で適用する。"""
    return (int(sel.get("context", -1)) == 0
            and sel.get("maxCount") == 1
            and sel.get("minCount", 0) <= 1
            and 2 <= n <= 10)


class PuctNode:
    __slots__ = ("state", "rs", "prior", "first_idx", "N", "W", "children", "total_n")

    def __init__(self, state, rs, prior, first_idx):
        self.state = state
        self.rs = rs                 # 根(このpuct_tree_value呼び出しの起点)からの通算ステップ数
        self.prior = prior
        self.first_idx = first_idx   # 初訪問時に選ぶ添字(=ルール方策と同じ手)
        n = len(prior)
        self.N = [0] * n
        self.W = [0.0] * n
        self.children = [None] * n   # None=未展開 / float=展開済み終端リーフ / PuctNode=展開済み分岐
        self.total_n = 0


def _advance(state, mi, opp_fn, rs, ctx):
    """次の分岐点(自分の主要判断)まで、または終局/カットオフまで自動操縦で進める。
    現行_rollout_contのループ本体と同じ判定順序・同じrsの数え方(_stepごとに+1)。
    戻り値: ("branch", (state, rs)) | ("terminal", value) | ("cutoff", value)"""
    step = ctx["step"]
    while True:
        if rs >= 400:  # 現行_rollout_contの絶対上限(for _rs in range(400))と同じ安全弁
            return "cutoff", 0.5
        o = state["observation"]
        cur = o.get("current")
        if cur is None:
            return "cutoff", 0.5
        r = int(cur.get("result", -1))
        if r != -1:
            return "terminal", (1.0 if r == mi else 0.0)
        if rs >= ctx["cutoff"]():
            return "cutoff", ctx["value_eval"](cur, mi)
        sel = o.get("select") or {}
        n = len(sel.get("option") or [])
        acting = int(cur.get("yourIndex", mi))
        if acting == mi:
            if is_branch(sel, n):
                return "branch", (state, rs)
            try:
                picks = ctx["sim_agent"](o)
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
        state = step(state["searchId"], picks)
        rs += 1


def _find_or_make_node(state, mi, rs, ctx, opp_fn):
    """_advanceで分岐点まで進め、そこにPuctNodeを1個新設して返す。
    スコア取得(_score_options)はここで1回だけ呼ぶ(_advance側では呼ばない)。
    これにより、分岐対象かどうかの判定に使うupdate_route等の副作用が
    1決定につき正確に1回だけ起きる(現行の_sim(o)呼び出しと同じ回数)。"""
    while True:
        kind, payload = _advance(state, mi, opp_fn, rs, ctx)
        if kind != "branch":
            return kind, payload
        state, rs = payload
        o = state["observation"]
        select_obj, scores = ctx["sim_score"](o)
        if select_obj is None or not scores:
            return "cutoff", ctx["value_eval"](o.get("current"), mi)
        picks = select_by_rule(select_obj, scores)
        first_idx = picks[0] if picks else max(range(len(scores)), key=lambda i: scores[i])
        # アブレーション用(2026-08-03): prior=一様分布に固定するオプション。木構造そのものの
        # 寄与とprior品質の寄与を切り分けるため。初訪問(first_idx)はequivalence設計上ルール手
        # 固定のままとし、priorはPUCT選択則(2回目以降の訪問)にのみ影響する
        if ctx.get("uniform_prior"):
            prior = [1.0 / len(scores)] * len(scores)
        else:
            prior = make_prior(scores, ctx["temperature"])
        return "node", PuctNode(state, rs, prior, first_idx)


def _puct_select(node, c_puct):
    best_a, best_score = 0, -1e18
    sqrt_total = math.sqrt(node.total_n)
    for a in range(len(node.prior)):
        na = node.N[a]
        q = node.W[a] / na if na > 0 else 0.0
        u = c_puct * node.prior[a] * sqrt_total / (1 + na)
        s = q + u
        if s > best_score:
            best_score, best_a = s, a
    return best_a


def _backup(path, v):
    for node, a in path:
        node.N[a] += 1
        node.W[a] += v


def _simulate(root, mi, opp_fn, ctx):
    """根から1回分の探索を行う。ノード初訪問(total_n==0)は必ずルール方策の手を選ぶ
    (等価性の要)。2回目以降の訪問はPUCT選択則で有望/未知の枝に配分する。"""
    path = []
    node = root
    while True:
        a = node.first_idx if node.total_n == 0 else _puct_select(node, ctx["c_puct"])
        path.append((node, a))
        node.total_n += 1
        child = node.children[a]
        if isinstance(child, PuctNode):
            node = child
            continue
        if isinstance(child, float):
            # 展開済みの終端リーフ: 値は1回のロールアウトで確定済みのものを再利用する
            # (plan通り「新規ノードの初期評価はロールアウトを1回実行した結果」)
            _backup(path, child)
            return child
        # child is None: 未展開
        try:
            next_state = ctx["step"](node.state["searchId"], [a])
        except Exception:
            node.children[a] = 0.5
            _backup(path, 0.5)
            return 0.5
        kind, payload = _find_or_make_node(next_state, mi, node.rs + 1, ctx, opp_fn)
        if kind == "node":
            node.children[a] = payload
            node = payload
            continue
        v = float(payload)
        node.children[a] = v
        _backup(path, v)
        return v


def puct_tree_value(state, mi, opp_fn, sims, deadline, ctx):
    """_rollout_cont(state, mi, opp_fn)の置き換え。戻り値の形は(None, value)で同じ。
    sims=1のとき、現行main.pyの_rollout_contと完全に同一の意思決定列・同一の返り値
    になるよう設計されている(等価性テストの土台)。"""
    kind, payload = _find_or_make_node(state, mi, 0, ctx, opp_fn)
    if kind != "node":
        return None, float(payload)
    root = payload
    n_done = 0
    for _ in range(max(1, sims)):
        if time.monotonic() > deadline:
            break
        _simulate(root, mi, opp_fn, ctx)
        n_done += 1
    if n_done == 0:
        return None, 0.5
    total_n = sum(root.N)
    if total_n == 0:
        return None, 0.5
    return None, sum(root.W) / total_n
