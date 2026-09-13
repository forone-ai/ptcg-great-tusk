"""cabt Search API ラッパ + 先読み探索コア (スケルトン).

cabt は **公式に Search API を提供** している (発見済の重大ポイント!):
- ``search_begin(...)`` : 検索状態の初期化
- ``search_step(search_id, select)`` : 状態を 1 ステップ進める
- ``search_end()`` : 検索終了

これを使うと「現状から仮想的に N 手先を読む」ができる。
MCTS / αβ 探索 / iterative deepening の土台。

## 設計方針

ふじくん方針 (2026-06-17):
- ML/RL より **探索効率の極限化**
- 葉の評価は evaluator.state_score を呼ぶ (重み係数を後で調整)
- トランスポジション表 (状態キャッシュ) で同じ局面の再評価を回避
- iterative deepening + 時間予算と連動

## 現状 (Day 1)

スケルトンのみ。 main.py からの呼び出しはまだ無い。
若が evaluator を磨いて精度が上がった段階で、 search を組み込んで
「読みの深さで戦う」フェーズへ移行する。
"""

from __future__ import annotations

from typing import Callable


# =====================================================================
# Public API (まだ呼ばれない、将来の差し込み口)
# =====================================================================


def search_best_option(
    obs: dict,
    options: list,
    evaluator: Callable[[dict], float],
    time_budget_sec: float,
) -> int:
    """N 手先を読んで最善の option index を返す.

    Args:
        obs: 現在の観測.
        options: ``obs["select"]["option"]``.
        evaluator: 葉局面を評価する関数 (大きいほど自分有利).
        time_budget_sec: このコールに使ってよい総秒数.

    Returns:
        最善と判定された option index.
    """
    # TODO: cabt の search_begin / search_step / search_end を使った実装。
    # API の正確なシグネチャは公式ドキュメント参照:
    #   https://matsuoinstitute.github.io/cabt/
    #
    # 概形:
    #   search_id = search_begin(obs)
    #   for i, opt in enumerate(options):
    #       state = search_step(search_id, [i])
    #       # 必要なら相手の手番を任意に進める (rollout)
    #       score = evaluator(state)
    #       ...
    #   search_end(search_id)
    #   return best_i
    #
    # 当面は「最初の選択肢を返すだけ」のスタブで安全網。
    return 0


# =====================================================================
# 補助: トランスポジション表 (将来 MCTS 化したときの基礎)
# =====================================================================


class TranspositionTable:
    """状態 → スコア のキャッシュ. 同じ局面の再評価を回避."""

    def __init__(self, max_entries: int = 100_000):
        self._table: dict[int, float] = {}
        self._max = max_entries

    @staticmethod
    def hash_state(obs: dict) -> int:
        """観測から状態ハッシュを生成.

        TODO: cabt の State から「ゲームに影響する要素だけ」を抽出して
        正規化ハッシュを作る。 簡単に作るなら json.dumps + sha1 で十分.
        """
        # 雛形: 適当に文字列化
        return hash(repr(sorted((k, repr(v)) for k, v in obs.items())))

    def get(self, obs: dict) -> float | None:
        return self._table.get(self.hash_state(obs))

    def put(self, obs: dict, score: float) -> None:
        if len(self._table) >= self._max:
            self._table.clear()  # 雑だが提出環境では十分
        self._table[self.hash_state(obs)] = score


# モジュール内シングルトンのトランスポジション表
table = TranspositionTable()
