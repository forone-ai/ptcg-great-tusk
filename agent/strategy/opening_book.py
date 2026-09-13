"""★若の主戦場③ — 序盤定石★.

序盤 N ターンは「決まった最善手」を辞書で持つと安定。
ポケカは「マリガン処理」「先攻 1 ターン目の攻撃不可」など、知識で詰められる
パターンが多いので、ここで定石をハードコードしておくと評価関数の負担が減る。

## 設計

- ``lookup_opening_move(obs)`` が、現在のターン番号と手札から
  「定石が決まっているなら option index list を返す」「不明なら None」を返す。
- main.py 側で先に呼んで、None なら evaluator にフォールバック (将来拡張)。

## 磨き込みの方針

1. **マリガン (Mulligan) 対応** — 基本ポケモンを引くまでドロー
2. **先攻 1 ターン目** — 攻撃不可なので、ベンチ展開とエネ装着のみ
3. **2-3 ターン目の進化テンポ** — 進化ラインを引いたら即進化
4. **エネ加速デッキの初動** — エネ加速カードの最適打点

## 注意

cabt の Option オブジェクトの内部表現が確定したら、定石マッチング処理を実装。
最初は辞書未登録 → 全部 evaluator にフォールバック、で OK。
"""

from __future__ import annotations


def lookup_opening_move(obs: dict) -> list[int] | None:
    """序盤の定石手を返す。該当なしなら ``None``.

    Args:
        obs: cabt 観測 dict.

    Returns:
        index list (定石適用) or ``None`` (evaluator にフォールバック).
    """
    # TODO(若): ターン番号は obs["current"] から取れる。
    # 初期はゼロ実装で OK (None を返すと evaluator が動く)。
    return None
