"""★若の主戦場② — 状態評価関数とオプション選択★.

このファイルが「賢さ」の中核。 ``pick_options(obs, options, max_count)`` が
main.py から呼ばれて、選んだ option の index list を返す契約。

## 設計思想

ふじくん方針 (2026-06-17) : 「モデルじゃなく、推論ランタイムの極限カスタム」。
ここでは ML を使わず、 ゲーム知識を **重み付き線形和** にした評価関数で戦う。
若のポケカ知識をコードに落とすメイン領域。

## 磨き込みの順序 (推奨)

1. **オプションごとのヒューリスティック・スコア** (option_score) を書く
   - 「攻撃ならダメージ大きい順」「ベンチ追加なら HP 高い基本ポケモン優先」など
2. **状態評価関数** (state_score) を整える
   - サイド差・Active HP差・ベンチ厚み・手札差・エネ進行
3. **マッチアップ別の重み調整** (matchup.py — 別途作成可)
4. ★余裕があれば「先読み」: engine/search.py の MCTS / αβ 探索と連携

## 観測 (obs) の主要キー

cabt 公式ドキュメント (https://matsuoinstitute.github.io/cabt/) より:
- ``obs["select"]["option"]`` : 利用可能な選択肢のリスト
- ``obs["select"]["maxCount"]`` : 同時に選べる最大数
- ``obs["current"]`` : 現在の盤面 (State)
   - ``players[0]``, ``players[1]`` : 各 PlayerState
       - ``active`` (size 0-1), ``bench`` (max 5), ``hand``, ``prize``,
         ``deckCount``, ``discard``, ``poisoned``/``burned``/``asleep``/
         ``paralyzed``/``confused``
   - ``stadium``, ``yourIndex``, ``result`` 他
- ``obs["logs"]`` : 過去のイベントログ
"""

from __future__ import annotations

from typing import Any


# =====================================================================
# Public API: main.py から呼ばれる
# =====================================================================


def pick_options(obs: dict, options: list, max_count: int) -> list[int]:
    """選択肢にスコアをつけて、上位 ``max_count`` 個の index を返す.

    Args:
        obs: cabt エンジンからの観測 dict (current/select/logs を含む).
        options: ``obs["select"]["option"]`` と同一。便宜上分離して受け取る。
        max_count: 同時に選べる最大数 (1 以上)。

    Returns:
        ``options`` の index list。長さは 1 〜 ``max_count``。
    """
    if not options:
        return []

    # 各オプションをスコアリング (高いほど良い)
    scored = [(i, option_score(opt, obs)) for i, opt in enumerate(options)]
    scored.sort(key=lambda x: -x[1])

    # 上位 max_count 個を返す
    return [i for i, _ in scored[:max_count]]


# =====================================================================
# ★若の磨き込み領域: ここから下を肉付け
# =====================================================================


def option_score(option: Any, obs: dict) -> float:
    """1 つのオプションに対する評価スコア.

    Args:
        option: ``obs["select"]["option"]`` の 1 要素 (cabt の Option オブジェクト).
        obs: 現在の観測 (盤面参照用).

    Returns:
        スコア (float)。高いほど良い選択。
    """
    # TODO(若): ここをポケカ知識で肉付けする。
    #
    # 方針:
    #   1. option の種類を判別 (attack/play/retreat/evolve/use_ability/...)
    #   2. 種類ごとにルールベースのスコア:
    #      - attack: ダメージ量、相手 active HP、KO 可能性、自分の被害
    #      - play (手札からポケモン): 基本ポケモンを優先、ベンチ枠の重要度
    #      - evolve: 進化先 HP、攻撃力、特性
    #      - retreat: アクティブが瀕死なら +、 エネルギー無駄遣いを -
    #      - trainer card: ドロー > サーチ > 妨害（メタ次第）
    #   3. 状態評価との連動: 「いま不利なら攻めるべき option を優遇」
    #
    # 最初は雑な定数返しで OK (first_agent と同等動作 = 提出は通る)。
    return 0.0


def state_score(obs: dict) -> float:
    """局面全体の評価 (大きいほど自分有利).

    使い道:
    - ``option_score`` の中で「この option を取った後の仮想状態」を採点したい
      ときに使う (engine.search の先読み結果に対して呼ぶ)
    - 学習を入れるなら、自己対戦で重みを最適化するターゲット

    Args:
        obs: 観測 dict.

    Returns:
        スコア (float)。+ ならば自分有利、- ならば不利。
    """
    # TODO(若): ポケカ知識フル動員。雛形だけ置いとく。
    #
    # 推奨される評価軸 (重み w1..wN は調整可):
    #   + w1 * (相手のサイド残数 - 自分のサイド残数)  ← サイド差
    #   + w2 * (自分の active HP残 - 相手の active HP残) / 100
    #   + w3 * (自分のベンチ枚数 - 相手のベンチ枚数)
    #   + w4 * (自分の手札枚数 - 相手の手札枚数)
    #   + w5 * (自分の active についてるエネ - 相手の active についてるエネ)
    #   - w6 * (自分の active の status condition の数)  ← 状態異常ペナ
    #   + w7 * (相手の active の status condition の数)
    #
    # 雛形:
    try:
        current = obs.get("current") or {}
        your_index = current.get("yourIndex", 0)
        players = current.get("players") or []
        if len(players) < 2:
            return 0.0
        me = players[your_index]
        opp = players[1 - your_index]
        # サイド差 (取られたサイド枚数の差。先に 6 枚取った方が勝ち = prize が少ない方が有利)
        my_prize_taken = sum(1 for p in me.get("prize", []) if p is None)
        opp_prize_taken = sum(1 for p in opp.get("prize", []) if p is None)
        return float(opp_prize_taken - my_prize_taken)
    except Exception:
        return 0.0
