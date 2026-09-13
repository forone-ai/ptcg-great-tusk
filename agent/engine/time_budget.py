"""10 分プールの動的時間配分.

cabt エンジンの実効制約 (HEROZ プレスリリース確認):
- **各プレイヤー合計 10 分** (600 秒) のプール制
- ターンごとのタイムアウトは設定上 0 (= per-turn 無制限)
- プールを使い切ったら即敗北

→ 「序盤は早打ち、勝負所で長考」を自動で配分するための予算管理。
   evaluator / search が「あと何秒使える?」を尋ねる窓口になる。

## ふじくん方針

「推論ランタイムの極限カスタム」のキモのひとつ。
ベースは「残り時間の何 % を、残りターン数で割る」。
盤面の決定性が高い (合法手が少ない/読まなくても明らか) なら短く、
分岐が多い (探索価値あり) なら長く。
"""

from __future__ import annotations

import time

# プール総量 (各プレイヤー 10 分 = 600 秒)。実効値はもう少しマージン取って運用する。
TOTAL_BUDGET_SEC = 600.0
SAFETY_MARGIN_SEC = 30.0  # 30 秒のセーフティ (ネット遅延・コールドスタート)


class TimeBudget:
    """1 試合分の時間予算マネージャ. シングルトンとして使う想定."""

    def __init__(self, total: float = TOTAL_BUDGET_SEC):
        self.total = total
        self.consumed = 0.0
        self._turn_start: float | None = None

    @property
    def remaining(self) -> float:
        """残り使える秒数 (セーフティマージン除く)."""
        return max(0.0, self.total - self.consumed - SAFETY_MARGIN_SEC)

    def begin_turn(self) -> None:
        """ターン開始 (= agent 関数の入口) で呼ぶ."""
        self._turn_start = time.monotonic()

    def end_turn(self) -> None:
        """ターン終了 (= agent 関数の出口) で呼ぶ. 消費秒数を記録."""
        if self._turn_start is None:
            return
        self.consumed += time.monotonic() - self._turn_start
        self._turn_start = None

    def suggest_turn_budget(self, turn_index: int, board_complexity: float = 1.0) -> float:
        """このターン使ってよい秒数を返す.

        Args:
            turn_index: 現在のターン番号 (0 始まり).
            board_complexity: 0.0〜2.0 ぐらいで「読みの価値」を渡す。
                              1.0 が標準、 2.0 で倍長考、 0.5 で半分。

        Returns:
            このターンの推奨予算 (秒).
        """
        # 想定試合長 = 40 ターン (両者合計 80 手。実際は前後する)。
        # 単純化: 残り予算 / 残り推定ターン数 * complexity。
        ASSUMED_TOTAL_TURNS = 40
        remaining_turns = max(5, ASSUMED_TOTAL_TURNS - turn_index)
        base = self.remaining / remaining_turns
        return max(0.05, base * board_complexity)


# シングルトン。 main.py の agent() 入口で begin_turn → 出口で end_turn を呼ぶと
# 自動的に消費秒数が記録される。 evaluator から global の budget を参照する。
budget = TimeBudget()
