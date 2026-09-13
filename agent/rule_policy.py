import os
from collections import defaultdict

from cg.api import (
    AreaType, CardType, Observation, OptionType, Pokemon,
    SelectContext, all_attack, all_card_data, to_observation_class,
)

# --- Core plan: aggressive Great Tusk LO + Crustle wall package ---
# Core mill package
GREAT_TUSK = 58
DURANT_EX = 198
CORNERSTONE_OGERPON = 386
TATSUGIRI = 122
FLUTTER_MANE = 56

# Crustle wall package
DWEBBLE = 344
CRUSTLE = 345

# Search / disruption / recovery
FIGHT_GONG = 1142
POKEGEAR_30 = 1122
ROTO_STICK = 1077
BUG_CATCHING_SET = 1094
ULTRA_BALL = 1121
HAND_TRIMMER = 1087
JUMBO_ICE_CREAM = 1147
SWITCH = 1123
BUDDY_BUDDY_POFFIN = 1086
POKE_PAD = 1152
FLUTE = 1091
NIGHT_STRETCHER = 1097
SACRED_ASH = 1129
ENERGY_RECYCLER = 1139
ENHANCED_HAMMER = 1081
ENERGY_LASSO = 1149
HANDY_CIRCULATOR = 1161
GRAVITY_GEM = 1166
HERO_CAPE = 1159
EXPLORER_GUIDANCE = 1185
ERI = 1186
XEROSIC_SCHEME = 1197
COLRESS_TENACITY = 1194
JUDGE = 1213
BOSS_ORDERS = 1182
LISIA_APPEAL = 1204
NEUTRAL_CENTER = 1247
CRUSHING_HAMMER = 1120
MEGATON_BLOWER = 1104
LILLIE_RESOLVE = 1227
ACEROLA_MISCHIEF = 1228
BATTLE_CAGE = 1264
LUNATONE = 675
SOLROCK = 676
MARACTUS = 255
BUDEW = 235
SUDOWOODO = 378
COUNTER_GAIN = 1168
LIVELY_STADIUM = 1251
STARYU = 1030
MEGA_STARMIE_EX = 1031
DEDENNE = 222
REDEEM_TICKET = 1114

# Energies
BASIC_GRASS_ENERGY = 1
BASIC_FIGHTING_ENERGY = 6
GROW_GRASS_ENERGY = 18
MIST_ENERGY = 11
ROCK_FIGHTING_ENERGY = 20
ENERGY_IDS = {BASIC_GRASS_ENERGY, BASIC_FIGHTING_ENERGY, GROW_GRASS_ENERGY, MIST_ENERGY, ROCK_FIGHTING_ENERGY}
GRASS_ENERGY_IDS = {BASIC_GRASS_ENERGY, GROW_GRASS_ENERGY}
BASIC_ENERGY_IDS = {BASIC_GRASS_ENERGY, BASIC_FIGHTING_ENERGY}

# Attack IDs
LAND_COLLAPSE = 62          # Great Tusk: mill 1, +3 if Ancient Supporter was played.
GIANT_TUSK_ATTACK = 63      # Great Tusk: 160点、闘2+無2(教え9の狩りプラン主砲)
GIANT_TUSK = 63             # Great Tusk: 160 damage.
DURANT_VENGEFUL_CRUSH = 267
ROCK_KAGURA = 538           # Ogerpon: attach Basic Fighting from deck.
MOUNTAIN_RAMMING = 539      # Ogerpon: 100 + mill 1.
ASCENSION = 478             # Dwebble: evolve from deck.
SUPERB_SCISSORS = 479       # Crustle: 120.

# --- Optional emergency attacker package ---
MEGA_HERACROSS_EX = 781
KORAIDON_EX = 979
TERRAKION = 607
MEGA_HAWLUCHA_EX = 886
JUGGERNAUT_HORN = 1130
HERA_MOUNTAIN_RAMMING = 1131
KORAIDON_TERA = 1408
ORICHALCUM_FANG = 1409
TERRAKION_RETALIATE = 873
TERRAKION_LAND_CRUSH = 874
SOMERSAULT_DIVE = 1277
ATTACKER_PIVOTS = {MEGA_HERACROSS_EX, KORAIDON_EX, TERRAKION, MEGA_HAWLUCHA_EX}

POKEMON_IDS = {GREAT_TUSK, DURANT_EX, CORNERSTONE_OGERPON, TATSUGIRI, FLUTTER_MANE, DWEBBLE, CRUSTLE, MEGA_HERACROSS_EX, KORAIDON_EX, TERRAKION, MEGA_HAWLUCHA_EX, LUNATONE, SOLROCK, MARACTUS, BUDEW, SUDOWOODO, DEDENNE}
SEARCH_ITEMS = {FIGHT_GONG, POKEGEAR_30, ROTO_STICK, BUG_CATCHING_SET, ULTRA_BALL, BUDDY_BUDDY_POFFIN, POKE_PAD}
RECOVERY_ITEMS = {NIGHT_STRETCHER, SACRED_ASH, ENERGY_RECYCLER}
SUPPORTERS = {EXPLORER_GUIDANCE, ERI, XEROSIC_SCHEME, COLRESS_TENACITY, JUDGE, BOSS_ORDERS, LISIA_APPEAL, LILLIE_RESOLVE, ACEROLA_MISCHIEF}
AIR_BALLOON = 1174
SACRED_CHARM = 1177
TOOLS = {HANDY_CIRCULATOR, GRAVITY_GEM, HERO_CAPE, AIR_BALLOON, SACRED_CHARM, COUNTER_GAIN}

CARD_TABLE = {card.cardId: card for card in all_card_data()}
ATTACK_TABLE = {attack.attackId: attack for attack in all_attack()}

# 進化先にex/メガを持つポケモン名 → そのex進化形の最小ワザコスト
# (go教示 2026-08-03 ep89653255: ジュラルドンにエネが載る=ブリジュラスex完成前。
#  エネは進化後も引き継ぐので、ex「予備軍」の武装もNCの引き金にする)
# ベンチ狙撃ワザ持ち(go指示 2026-08-07: ID直書きでなくカードデータから網羅)
BENCH_SNIPE_ATTACK: dict[int, int] = {}   # card_id -> その狙撃ワザの最小エネ数
for _c in CARD_TABLE.values():
    for _aid in (_c.attacks or []):
        _a = ATTACK_TABLE.get(_aid)
        _t = (getattr(_a, "text", "") or "").lower() if _a is not None else ""
        if "bench" in _t and ("damage" in _t or "counter" in _t) and "your opponent" in _t:
            _n = len(getattr(_a, "energies", []) or [])
            BENCH_SNIPE_ATTACK[_c.cardId] = min(BENCH_SNIPE_ATTACK.get(_c.cardId, 99), _n)

EX_EVOLUTION_MIN_COST: dict[str, int] = {}
for _c in CARD_TABLE.values():
    if (_c.ex or getattr(_c, "megaEx", False)) and _c.evolvesFrom:
        _costs = [len(ATTACK_TABLE[a].energies)
                  for a in (_c.attacks or []) if a in ATTACK_TABLE]
        EX_EVOLUTION_MIN_COST[_c.evolvesFrom] = min(
            EX_EVOLUTION_MIN_COST.get(_c.evolvesFrom, 99),
            min(_costs, default=99))


def _attack_ids(card_id: int) -> set[int]:
    data = CARD_TABLE.get(card_id)
    return set(getattr(data, "attacks", None) or [])


SOLROCK_ATTACK_IDS = _attack_ids(SOLROCK)
DEDENNE_ATTACK_IDS = _attack_ids(DEDENNE)
BUDEW_ATTACK_IDS = _attack_ids(BUDEW)
SUDOWOODO_ATTACK_IDS = _attack_ids(SUDOWOODO)


def _ex_evolution_ancestor_names() -> set[str]:
    ancestors = {card.evolvesFrom for card in CARD_TABLE.values() if (card.ex or getattr(card, "megaEx", False)) and card.evolvesFrom}
    changed = True
    while changed:
        changed = False
        for card in CARD_TABLE.values():
            if card.name in ancestors and card.evolvesFrom and card.evolvesFrom not in ancestors:
                ancestors.add(card.evolvesFrom)
                changed = True
    return ancestors


EX_EVOLUTION_ANCESTORS = _ex_evolution_ancestor_names()


def read_deck_csv() -> list[int]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deck.csv')
    if not os.path.exists(path):
        path = 'deck.csv'
    if not os.path.exists(path):
        path = '/kaggle_simulations/agent/deck.csv'
    with open(path, 'r') as file:
        return [int(line) for line in file.read().splitlines()[:60]]


def get_card(obs: Observation, area: AreaType, index: int, player_index: int):
    player = obs.current.players[player_index]
    zones = {
        AreaType.HAND: player.hand,
        AreaType.DISCARD: player.discard,
        AreaType.ACTIVE: player.active,
        AreaType.BENCH: player.bench,
        AreaType.PRIZE: player.prize,
        AreaType.STADIUM: obs.current.stadium,
        AreaType.LOOKING: obs.current.looking,
        AreaType.DECK: obs.select.deck,
    }
    zone = zones.get(area)
    if zone is None or index is None or not 0 <= index < len(zone):
        return None
    return zone[index]


def field_pokemon(player):
    return [p for p in player.active + player.bench if p is not None]


def active_pokemon(player):
    return player.active[0] if player.active and player.active[0] is not None else None


def attached_energy_count(pokemon: Pokemon | None) -> int:
    return len(pokemon.energies) if pokemon is not None else 0


def damage_on(pokemon: Pokemon | None) -> int:
    if pokemon is None:
        return 0
    return max(0, pokemon.maxHp - pokemon.hp)


def is_ex_card(card_id: int) -> bool:
    data = CARD_TABLE.get(card_id)
    return bool(data and (data.ex or getattr(data, "megaEx", False)))


def is_ex_pokemon(pokemon: Pokemon | None) -> bool:
    return pokemon is not None and is_ex_card(pokemon.id)


def typed_damage(base: int, attacker_card_id: int, defender_card_id: int) -> int:
    """弱点×2と抵抗力-30を反映した実効ダメージ。

    バグ修正(go指摘 2026-08-12): 旧計算は弱点だけ見て抵抗力を無視していた。
    フーディン線は全員闘抵抗-30のため、キバのギガントタスク160をフーディン
    (HP140)に「倒せる」と誤認→実際は130で空振り、ボスとエネを無駄うちしていた。
    """
    if not base:
        return 0
    ad = CARD_TABLE.get(attacker_card_id)
    dd = CARD_TABLE.get(defender_card_id)
    if ad is None or dd is None:
        return base
    at = getattr(ad, "energyType", None)
    dmg = base * (2 if getattr(dd, "weakness", None) == at else 1)
    if getattr(dd, "resistance", None) == at:
        dmg = max(0, dmg - 30)
    return dmg


def is_armed_ex_threat(pokemon: Pokemon | None) -> bool:
    """ex本体、またはexに進化する予備軍が「あと1エネ以内で攻撃圏」か。

    予備軍はエネを進化後に引き継ぐため、ジュラルドン(→ブリジュラスex)のような
    土台の武装もexの脅威として数える(go教示 2026-08-03)。
    """
    if pokemon is None:
        return False
    if is_ex_card(pokemon.id):
        return attached_energy_count(pokemon) + 1 >= attack_energy_minimum(pokemon)
    data = CARD_TABLE.get(pokemon.id)
    mc = EX_EVOLUTION_MIN_COST.get(getattr(data, "name", None) or "")
    if mc is None:
        return False
    # go裁定(2026-08-03): 判定は「進化後がex」かつ「次のターンにそのexが攻撃
    # できる想定」— つまり進化+装着1回で攻撃圏(=+1)。それより早くは貼らない
    return attached_energy_count(pokemon) + 1 >= mc


def has_tool(pokemon: Pokemon | None, tool_id: int) -> bool:
    return pokemon is not None and any(c.id == tool_id for c in pokemon.tools)


def count_in_hand(player, card_id: int) -> int:
    return sum(1 for c in (player.hand or []) if c.id == card_id)


def count_in_field(player, card_id: int) -> int:
    return sum(1 for p in field_pokemon(player) if p.id == card_id)


def has_in_field(player, card_id: int) -> bool:
    return count_in_field(player, card_id) > 0


def count_in_discard(player, card_id: int) -> int:
    return sum(1 for c in (player.discard or []) if c.id == card_id)


def count_energy_in_discard(player) -> int:
    return sum(1 for c in (player.discard or []) if c.id in ENERGY_IDS)


def count_pokemon_in_discard(player) -> int:
    n = 0
    for c in (player.discard or []):
        data = CARD_TABLE.get(c.id)
        if data is not None and data.cardType == CardType.POKEMON:
            n += 1
    return n


def can_pay_attack(pokemon: Pokemon | None, attack_id: int) -> bool:
    if pokemon is None:
        return False
    attack = ATTACK_TABLE.get(attack_id)
    if attack is None:
        return False
    # The simulator offers only legal attacks. This approximate check is for planning.
    return len(pokemon.energies) >= len(attack.energies)


# --- Route Selector v1 (plan §4/§8.8/§19 の決定的縮約, 2026-07-22) ---
# 山レースの残ターン概算からTerminal Routeを選ぶ。将来はRoute-Value学習モデルの
# 蒸留成果物に差し替え可能なインターフェースとして維持する(§27)。
_ROUTE_STATE = {"hist": [], "route": "deck_out"}

# 教え25台帳(go教示 2026-08-10): ターン頭の「ベンチのキバに付いている特殊エネ数」。
# 攻撃判断時に増分があれば「このターン貼りたて」=次の相手ターンの改造ハンマーの的。
_ITCHY_LEDGER = {"turn": -1, "base": 0, "now": 0}

# マリィ悪の代表60枚(19万試合コーパスのmax合成復元、Luca実デッキと一致確認済み)
_MARNIE_DECK_PRED = {1227: 4, 112: 4, 1152: 4, 1086: 4, 7: 10, 1259: 4, 646: 4, 1219: 4,
                     1097: 3, 1079: 3, 648: 3, 647: 3, 1182: 2, 104: 2, 860: 2,
                     1080: 1, 1231: 1, 1122: 1, 1137: 1}


_RACE_WINDOW = int(os.environ.get("LO_RACE_WINDOW", "6"))
_RACE_CAP_ROUNDS = 40  # 打ち切りラウンド数(これを超えたら山切れ時計は999扱い)


def count_remaining_unseen(me, card_id: int, state=None) -> int:
    """自分の60枚構成(_MY_DECK_60)から、既に見えている枚数(手札/トラッシュ/場
    [本体・進化前・エネルギー・どうぐ]/スタジアム/判明済みサイド落ち)を引いた
    「まだ山にある可能性がある枚数」を厳密に返す(count_in_dekのバグ修正版。
    旧実装は自分の山の中身を常に0枚とみなしていた)。
    自分のサイドは基本的に非公開のため、my_prizes_known で判明済みの分だけ追加で除く。
    サイドが未解決の残りはまだ「山にある可能性」として楽観的に含む(=下限ではなく
    到達しうる上限)。"""
    total = _MY_DECK_60.get(card_id, 0)
    if total <= 0:
        return 0
    seen = 0
    for c in (me.hand or []):
        if getattr(c, "id", None) == card_id:
            seen += 1
    for c in (me.discard or []):
        if getattr(c, "id", None) == card_id:
            seen += 1
    for pk in field_pokemon(me):
        if pk.id == card_id:
            seen += 1
        for pe in (pk.preEvolution or []):
            if getattr(pe, "id", None) == card_id:
                seen += 1
        for e_ in (pk.energyCards or []):
            if getattr(e_, "id", None) == card_id:
                seen += 1
        for t_ in (pk.tools or []):
            if getattr(t_, "id", None) == card_id:
                seen += 1
    if state is not None:
        for st_ in (getattr(state, "stadium", None) or []):
            if getattr(st_, "id", None) == card_id:
                seen += 1
    known_prizes = (_ROUTE_STATE.get("my_prizes_known") or {}).get(card_id, 0)
    return max(0, total - seen - known_prizes)


def _deck_trajectory(deck0: float, base_pace: float, bonus: float, combo_rounds: set,
                      cap: int = _RACE_CAP_ROUNDS) -> list:
    """1ラウンドずつ山を削り、0未満に潜らせない(概算禁止=整数クリップ)厳密な軌跡。
    combo_rounds に含まれるラウンドだけ bonus を上乗せする(先導コンボの前詰め)。"""
    traj = [max(0.0, float(deck0))]
    d = traj[0]
    for r in range(1, cap + 1):
        step = base_pace + (bonus if r in combo_rounds else 0.0)
        d = max(0.0, d - step)
        traj.append(d)
        if d <= 0:
            break
    return traj


def _combo_rounds(e_hand: int, e_deck: int) -> set:
    """先導コンボ(探検家)を使うラウンド番号の集合。手札にある分は即使える(前詰め)。
    山にしかない分は1ラウンド分ドローを待ってから使える想定(保守的: 山内の位置は
    不明なので早期に引ける保証はない)。"""
    rounds = set(range(1, e_hand + 1))
    start = e_hand + 2
    rounds |= set(range(start, start + max(0, e_deck)))
    return rounds


def _first_zero_round(traj: list):
    for r, d in enumerate(traj):
        if r == 0:
            continue
        if d <= 0:
            return r
    return None  # 打ち切りまでに切れない


def _race_calculator(me, opponent, state) -> None:
    """レース電卓v2 (go設計 2026-07-31 / 厳密化 2026-08-04 endgame_v1 SPEC /
    2026-08-11 lo_v28_energyfirst へ移植): 3本の時計を毎ターン計算し、間に合う
    削りプランと必要資源(先導の残弾)を _ROUTE_STATE["race"] に置く。時計:
    ①相手山0まで(勝ち) ②自山0まで(負け) ③相手サイド取り切りまで(負け)。
    goの手動対戦の頭の中の計算(「26枚だと間に合わない→先導あと3発必要」)の機械化。

    v1からの変更(概算除去):
    - ペースは生涯平均ではなく直近windowのトレンドを使う(序盤の汚染を排除)
    - e回コンボの効果は「均等に薄める」近似ではなく、ラウンド単位の整数クリップ
      軌跡で前詰めシミュレートする(自山0未満/相手山0未満を許さない)
    - 探検家の残数は count_in_deck (常に0を返す死んだ経路) ではなく
      count_remaining_unseen (60枚構成からの厳密な逆算) を使う
    - margin_cards/margin_laps: 決着時点でもう片方の山に何枚残っていたか
      (=勝敗の余裕を枚数で表す。探検家コンボ1回=相手山への相対+3枚が「1周」の単位)
    """
    hist = _ROUTE_STATE["hist"]
    phist = _ROUTE_STATE.get("prize_hist") or []
    race = {"feasible": None, "need_explorers": 0, "binding": None}
    _ROUTE_STATE["race"] = race
    if len(hist) < 3:
        return
    W = min(len(hist), _RACE_WINDOW)
    t0, m0, o0 = hist[-W]
    t1, m1, o1 = hist[-1]
    span = max(1, t1 - t0)
    intervals = max(1, W - 1)
    span_per_round = span / intervals            # 1ラウンド(=自分の1手番)あたりの生ターン数
    my_burn = max(0.34, (m0 - m1) / span) * span_per_round        # 自山の減り/ラウンド
    opp_pace = max(0.34, (o0 - o1) / span) * span_per_round       # 相手山の減り/ラウンド
    # ③サイド時計: 相手の残りprizeの減りから外挿(直近windowで同様に汚染を排除)
    t_prize = 999.0
    if len(phist) >= 2:
        Wp = min(len(phist), _RACE_WINDOW)
        pt0, pp0 = phist[-Wp]
        pt1, pp1 = phist[-1]
        pspan = max(1, pt1 - pt0)
        prize_pace = max(0.0, (pp0 - pp1) / pspan)
        if prize_pace > 0.01:
            t_prize = pp1 / prize_pace
    # 削りプラン列挙: 先導コンボe回(手札分は前詰め、山分は1ラウンド遅れ)
    explorers_hand = count_in_hand(me, EXPLORER_GUIDANCE)
    explorers_unseen = count_remaining_unseen(me, EXPLORER_GUIDANCE, state)
    max_e = min(4, explorers_unseen)
    best = None
    for e in range(0, max_e + 1):
        e_hand = min(e, explorers_hand)
        e_deck = e - e_hand
        combo_rounds = _combo_rounds(e_hand, e_deck)
        opp_traj = _deck_trajectory(opponent.deckCount, opp_pace, 3.0, combo_rounds)
        my_traj = _deck_trajectory(me.deckCount, my_burn, 6.0, combo_rounds)
        t_win_r = _first_zero_round(opp_traj)
        t_self_r = _first_zero_round(my_traj)
        win = (t_win_r is not None) and (t_self_r is None or t_win_r <= t_self_r)
        resolved_r = t_win_r if win else (t_self_r if t_self_r is not None else _RACE_CAP_ROUNDS)
        ok = win and (t_win_r * span_per_round) < t_prize
        if win:
            margin_cards = round(my_traj[min(t_win_r, len(my_traj) - 1)])
        elif t_self_r is not None:
            margin_cards = -round(opp_traj[min(t_self_r, len(opp_traj) - 1)])
        else:
            margin_cards = 0
        # 間に合うプランがあれば最速(t_win最小)を優先。無ければ「一番マシな負け方」
        # (=決着が一番遅い=直近まで互角)を代表値として報告する。resolved_rの単純最小化
        # だと「自山切れが早まるだけの手」を誤って良いプラン扱いしてしまうので符号反転する
        cand = (0, t_win_r, e) if ok else (1, -resolved_r, e)
        if best is None or cand < best[0]:
            best = (cand, e, t_win_r, t_self_r, ok, margin_cards)
    _, e_used, t_win_r, t_self_r, feasible, margin_cards = best
    race["feasible"] = feasible
    race["need_explorers"] = e_used
    race["t_win"] = round(t_win_r * span_per_round, 1) if t_win_r is not None else 999.0
    race["t_self"] = round(t_self_r * span_per_round, 1) if t_self_r is not None else 999.0
    race["t_prize"] = round(t_prize, 1)
    race["margin_cards"] = margin_cards
    # 探検家コンボ1回=相手山への相対+3枚(自山-6/相手-3、SPEC「1周」の単位)
    race["margin_laps"] = round(margin_cards / 3.0, 2)
    # どの負け時計がきついか(立ち回りの切替に使う)
    race["binding"] = "prize" if race["t_prize"] < race["t_self"] else "self"


def count_in_deck(player, card_id: int) -> int:
    try:
        return sum(1 for c in (player.deck or []) if getattr(c, "id", None) == card_id)
    except Exception:
        return 0


def race_info() -> dict:
    return _ROUTE_STATE.get("race") or {}


def crustle_unfavorable_matchup(opponent) -> bool:
    """go教示(2026-08-07): 攻めプランでキバを攻撃機に昇格するのは
    「イワパレスが苦手とする相手」が出ている時だけ(例: エースバーン=炎で
    イワパレスの弱点を突く)。ID直書きせず弱点タイプで抽象判定(go原則)"""
    wk = getattr(CARD_TABLE.get(CRUSTLE), "weakness", None)
    if wk is None:
        return False
    return any(getattr(CARD_TABLE.get(p.id), "energyType", None) == wk
               for p in field_pokemon(opponent))


def update_route(me, opponent, state) -> str:
    t = int(getattr(state, "turn", 0) or 0)
    hist = _ROUTE_STATE["hist"]
    if hist and t < hist[-1][0]:
        hist.clear()  # 新ゲーム
        _ROUTE_STATE.pop("crustle_oneshot", None)
        _ROUTE_STATE.pop("crustle_dmg", None)
    # go教示(2026-07-23 kiyotah戦勝利): 攻撃ルートの実行可能性チェック。
    # ほぼ無傷のイワパレスが一撃で場から消えた=相手火力が攻撃線を割る
    # → prizeルートの前提崩壊。以後deck_outに固定(プラン§4.3 Emergency Override)
    cur_cr = {p.serial: int(getattr(p, "damage", 0) or 0) for p in field_pokemon(me) if p.id == CRUSTLE}
    prev_cr = _ROUTE_STATE.get("crustle_dmg") or {}
    for s0, d0 in prev_cr.items():
        if s0 not in cur_cr and d0 <= 40:
            _ROUTE_STATE["crustle_oneshot"] = True
    _ROUTE_STATE["crustle_dmg"] = cur_cr
    if not hist or hist[-1][0] != t:
        hist.append((t, me.deckCount, opponent.deckCount))
        if len(hist) > 40:
            del hist[0]
        # レース電卓用: 相手のサイド取得履歴(残りprize枚数)も刻む
        _ROUTE_STATE.setdefault("prize_hist", []).append((t, len(opponent.prize or [])))
        if len(_ROUTE_STATE["prize_hist"]) > 40:
            del _ROUTE_STATE["prize_hist"][0]
    _race_calculator(me, opponent, state)
    # go指摘(2026-08-02 ep89515014 T1): 承認判定はルート決定の前に行う。
    # 旧実装は同一パスの後段で更新→認識が常に1手遅れ、T1のエネがキバに流れていた
    # go承認対面: マリィ悪(2026-07-28)。
    # メガスターミーは攻めプラン承認(8/7)を教え34改(go裁定 2026-08-12)で取り消し:
    # 上位LO(weihao)の対スターミー勝ち3局はすべて足止め+ミル。削りルートに戻す
    # 教え57(go裁定 2026-08-14): ユキノオーカイオーガも攻めプラン承認。
    # カイオーガのRiptide(トラッシュの水エネ×20→山に戻す)で山切れ勝ちが構造的に
    # 不成立(実戦ep92975429: 相手山27→30に増加、こちらがturn41自山切れ負け)。
    # 指紋: 721=カイオーガ / 723=メガユキノオーex / 418,722=ユキカブリ2種
    APPROVED_ATTACK_FINGERPRINTS = {646, 647, 648, 112, 860, 104,
                                    721, 723, 418, 722}
    _ROUTE_STATE["attack_matchup_approved"] = bool(
        opponent_visible_ids(opponent) & APPROVED_ATTACK_FINGERPRINTS)
    route = "deck_out"
    if _ROUTE_STATE.get("attack_matchup_approved"):
        # go指摘(2026-07-28 実戦ep88583931): 対面認識は初手で確定できるはず。
        # 旧実装は履歴3ターン分を待ってから切替→T4にキバで殴る初動の迷いが出ていた。
        # 指紋(公開札)が見えた瞬間に攻めプランへ直行する(履歴は不要)
        route = "prize"
    elif len(hist) >= 3:
        t0, m0, o0 = hist[0]
        t1, m1, o1 = hist[-1]
        span = max(1, t1 - t0)
        opp_pace = max(0.2, (o0 - o1) / span)   # 相手山の減り/T (自掘り+こちらの削り)
        my_pace = max(0.2, (m0 - m1) / span)
        t_opp_out = opponent.deckCount / opp_pace
        t_self_out = me.deckCount / my_pace
        lose_race = t_opp_out > t_self_out
        _ROUTE_STATE["lose_streak"] = _ROUTE_STATE.get("lose_streak", 0) + 1 if lose_race else 0
        if _ROUTE_STATE.get("crustle_oneshot"):
            # 一撃死降格(未承認対面): 攻め転換の根拠が崩れているので削り続行
            route = "deck_out"
        elif non_ex_passive_opponent(opponent):
            # go方針(2026-07-31): 非ex受動タンクにprize転落は自滅
            # (掘りスパイラルで自山7-9枚/T消失、ギガントタスクは闘エネ0で撃てない)。
            # 基本デッキ破壊を貫く。hysteresis中でもここで復帰する
            route = "deck_out"
        elif _ROUTE_STATE["route"] == "prize":
            # Hysteresis(§4.3): 一度prizeに切替えたら維持(レース逆転が明確な時だけ復帰)
            route = "deck_out" if t_opp_out <= t_self_out * 0.6 else "prize"
        elif _ROUTE_STATE["lose_streak"] >= 2 and not (opponent_visible_ids(opponent) & SELF_DIGGER_IDS):
            # go教義(2026-07-28): 「相手が自分の山を削らないデッキのときは攻めプラン」。
            # 判定は対面認識(公開札の直接証拠): 自掘りエンジン(ノコッチ線/フーディン線)が
            # 見えている相手は削りレース続行(ペース間接計測はフーディンで誤発動した)。
            # それ以外でレース劣勢2Tなら、削りが成立しない対面と判定して攻めへ(バナ50%の源泉)
            attack_line = (count_in_field(me, CRUSTLE) + count_in_hand(me, CRUSTLE)
                           + count_in_field(me, DWEBBLE) + count_in_hand(me, DWEBBLE))
            route = "prize" if attack_line > 0 else "deck_out"  # 自滅待ちはプランではない(go)
        else:
            route = "deck_out"
    _ROUTE_STATE["route"] = route
    # ==== 相手残り札カウンタ(go指示 2026-07-28): 予測60枚-公開札を毎ターン更新 ====
    # 公開札 = 相手の場(ポケモン+エネ+どうぐ) + トラッシュ + スタジアム
    # TODO(次段): プレイ中に見せて手札に加えた札もここに算入(ログ解析)
    _ROUTE_STATE["counter_err"] = None
    try:
        _counter_update(me, opponent, state)
    except Exception as _ex:
        import traceback as _tb
        _ROUTE_STATE["counter_err"] = _tb.format_exc()[-300:]
    return route


def _counter_update(me, opponent, state):
    _seen = {}
    for pk in field_pokemon(opponent):
        _seen[pk.id] = _seen.get(pk.id, 0) + 1
        for e_ in (pk.energies or []):
            _eid = e_ if isinstance(e_, int) else getattr(e_, "id", 0)
            if _eid:
                _seen[_eid] = _seen.get(_eid, 0) + 1
        for t_ in (getattr(pk, "tools", None) or []):
            _tid = t_ if isinstance(t_, int) else getattr(t_, "id", 0)
            if _tid:
                _seen[_tid] = _seen.get(_tid, 0) + 1
    for c_ in (opponent.discard or []):
        _seen[c_.id] = _seen.get(c_.id, 0) + 1
    if state.stadium and getattr(state.stadium[0], "playerIndex", None) == 1 - state.yourIndex:
        _sid = state.stadium[0].id
        _seen[_sid] = _seen.get(_sid, 0) + 1
    _ROUTE_STATE["opp_seen"] = _seen
    # 予測デッキ(対面認識が確定していれば): 残り札 = 予測60 - 公開札
    _pred = _MARNIE_DECK_PRED if (opponent_visible_ids(opponent) & {646, 647, 648, 112, 860, 104}) else None
    if _pred:
        _rem = {}
        for cid_, n_ in _pred.items():
            left = n_ - _seen.get(cid_, 0)
            if left > 0:
                _rem[cid_] = left
        _ROUTE_STATE["opp_remaining"] = _rem   # 手札+山+サイドのどこかにある札
        _ROUTE_STATE["opp_unseen_n"] = sum(_rem.values())
    else:
        _ROUTE_STATE["counter_err"] = f"pred=None vis={sorted(opponent_visible_ids(opponent))[:6]}"
    # 攻めプラン承認対面(goの承認が必要。現承認: マリィ悪 2026-07-28、
    # ユキノオーカイオーガ 教え57 2026-08-14(Riptideで山切れ不成立)。
    # メガスターミーの承認(8/7)は教え34改 2026-08-12で取り消し→削りルート)
    APPROVED_ATTACK_FINGERPRINTS = {646, 647, 648, 112, 860, 104,
                                    721, 723, 418, 722}
    _ROUTE_STATE["attack_matchup_approved"] = bool(
        opponent_visible_ids(opponent) & APPROVED_ATTACK_FINGERPRINTS)


def get_route() -> str:
    return _ROUTE_STATE["route"]


def current_wants(me, opponent) -> dict:
    """いま手札に欲しいカード→優先度(go設計 2026-07-28)。プランから毎ターン導出。
    攻めプランの優先はgoのサーチ選択15件の実測から: どの局面でも線の部品を補給し続ける。
    サーチ(TO_HAND)・ディグ判断がこのリストを参照する。"""
    wants = {}
    if get_route() == "prize":
        line_field = count_in_field(me, CRUSTLE) + count_in_field(me, DWEBBLE)
        line_hand = count_in_hand(me, CRUSTLE) + count_in_hand(me, DWEBBLE)
        wants[DWEBBLE] = 100 if line_field + line_hand < 2 else 60
        wants[CRUSTLE] = 95 if has_in_field(me, DWEBBLE) else 45
        armed = any(p.id == CRUSTLE and len(p.energies) >= 3 for p in field_pokemon(me))
        e_hand = count_in_hand(me, BASIC_GRASS_ENERGY) + count_in_hand(me, MIST_ENERGY)
        if not armed and e_hand < 2:
            wants[BASIC_GRASS_ENERGY] = 80
            wants[MIST_ENERGY] = 75
        else:
            # go教示(2026-07-29 先導レビュー): 手札に揃っている部品は「欲しくない」。
            # 差分=理想-(盤面+手札)。足りているエネの残点を0に
            wants[BASIC_GRASS_ENERGY] = 0
            wants[MIST_ENERGY] = 0
        # go承認(2026-08-07「やってみて」): チップ対面は線の満足キャップを3→5に。
        # 解剖実測: 相手のばら撒きがHP70を落とすペースに補充が追いつかず、盤面が
        # 平均3.3体で頭打ち→T10-16に体切れ死が負けの55%。体在庫を欲しがり続ける
        _line_cap = 5 if opponent_chips_board(opponent) else 3
        if line_field + line_hand >= _line_cap:
            wants[DWEBBLE] = 0
            wants[CRUSTLE] = 0 if count_in_hand(me, CRUSTLE) else wants[CRUSTLE]
        if (opponent_chips_board(opponent)
                and any(p.id == DWEBBLE for p in field_pokemon(me))
                and count_in_hand(me, CRUSTLE) == 0):
            # イワパレス化の加速: HP70を晒す時間を最小化(150ならチップ2倍かかる)
            wants[CRUSTLE] = max(wants.get(CRUSTLE, 0), 90)
        if crustle_unfavorable_matchup(opponent):
            # go教示(2026-08-07): イワパレスが苦手な相手(弱点=炎持ち等)が出ている時だけ
            # キバを攻めプランの攻撃機に昇格して部品を欲しがる
            wants[GREAT_TUSK] = 70
        else:
            wants[GREAT_TUSK] = -1   # 攻めプランでは取らない(goの負け試合1回のみ)
    else:
        # 削りプランのwants(go設計 2026-07-29: 全決定を「いま欲しいカード」で駆動)
        kiba_field = count_in_field(me, GREAT_TUSK)
        kiba_hand = count_in_hand(me, GREAT_TUSK)
        if kiba_field == 0 and kiba_hand == 0:
            wants[GREAT_TUSK] = 100          # 砲台不在は最優先
        elif kiba_field + kiba_hand < 2:
            # go教示(2026-08-02): 対フーディンは「ミスト付きキバ複数」が勝利条件。
            # 2号機の需要を対面で引き上げ、ミストも同時に欲しがる
            wants[GREAT_TUSK] = 80 if facing_alakazam(opponent) else 55
        if facing_alakazam(opponent) and count_in_hand(me, MIST_ENERGY) == 0:
            wants[MIST_ENERGY] = max(wants.get(MIST_ENERGY, 0), 70)
        _katt = max((attached_energy_count(p) for p in field_pokemon(me)
                     if p.id == GREAT_TUSK), default=0)
        _e_hand = sum(count_in_hand(me, _e) for _e in ENERGY_IDS)
        if max(0, 2 - _katt) - _e_hand > 0:
            wants[BASIC_GRASS_ENERGY] = 85   # ミル2エネの不足分だけ欲しい
            wants[MIST_ENERGY] = 78
        if count_in_hand(me, EXPLORER_GUIDANCE) == 0:
            wants[EXPLORER_GUIDANCE] = 50    # 古代コンボの弾
        _n2 = current_needs(me, opponent)
        if "bench_body" in _n2 or "wall_body" in _n2:
            wants[BUDEW] = 40
            wants[DWEBBLE] = 38
        if opponent_chips_board(opponent):
            # 教えA(2026-07-31解剖): 削り盤面対面ではベンチのイシズマイをHP70のまま
            # 晒すのが最大の負け筋(狙撃3発)。イワパレス化(HP150)を急ぐ
            _unevolved = sum(1 for p in field_pokemon(me) if p.id == DWEBBLE)
            if _unevolved and count_in_hand(me, CRUSTLE) == 0:
                wants[CRUSTLE] = max(wants.get(CRUSTLE, 0), 70)
            # 教えB: 補充の継続(場切れ負け対策)。たねの在庫を手札に持ち続ける
            if count_in_hand(me, DWEBBLE) == 0:
                wants[DWEBBLE] = max(wants.get(DWEBBLE, 0), 45)
    # go承認(2026-08-07「やってみて」): エネ需要の常時化。エネ破壊対面(改造ハンマー系)は
    # 在庫(場の装着+手札)が4を下回る限り基本エネを欲しがり続ける。
    # 解剖実測: 対v21の撃てないターンの43%が供給不足、負け試合は盤面エネがT12に0.2まで剥がされる。
    # 基本エネ限定(改造ハンマーの的にならない)。特殊エネは既存のJITゲート維持
    if opponent_special_hazard(opponent):
        _board_e = sum(attached_energy_count(p) for p in field_pokemon(me))
        _hand_e2 = sum(count_in_hand(me, _e) for _e in ENERGY_IDS)
        if _board_e + _hand_e2 < 4:
            wants[BASIC_GRASS_ENERGY] = max(wants.get(BASIC_GRASS_ENERGY, 0), 82)
    # 教え14①(go設計 2026-08-09): 対フーディン序盤の防御形=2体目のキバをベンチに。
    # パッド/サーチの取得先としてキバを昇格(前のキバは飛ぶ前提の後継育成)
    if _ala_early_defense(me, opponent) and count_in_field(me, GREAT_TUSK) < 2:
        wants[GREAT_TUSK] = max(wants.get(GREAT_TUSK, 0), 85)
    # 狩りプラン: ギガントタスクの弾を欲しがる
    if giant_tusk_plan(me, opponent) and count_in_hand(me, ROCK_FIGHTING_ENERGY) < 2:
        wants[ROCK_FIGHTING_ENERGY] = max(wants.get(ROCK_FIGHTING_ENERGY, 0), 80)
    # 取り切りモード(攻めプランの詰め形, go設計 2026-08-06): 欠品をwantsへ
    _cp2 = closing_plan(me, opponent, None)
    if _cp2 is not None:
        for _mid in _cp2.get("missing", []):
            if _mid == SWITCH:
                wants[SWITCH] = max(wants.get(SWITCH, 0), 90)
            elif _mid == BOSS_ORDERS:
                wants[BOSS_ORDERS] = max(wants.get(BOSS_ORDERS, 0), 70)
            else:
                wants[_mid] = max(wants.get(_mid, 0), 95)
    # 在庫補正(go指摘 2026-07-29): 「取れる札」= 山に残っている or
    # (トラッシュにあって夜のタンカ経路が生きている)。どちらも無ければ欲しがらない
    dk = _ROUTE_STATE.get('my_deck_known')
    if dk:
        _tanka_alive = dk.get(NIGHT_STRETCHER, 0) > 0 or count_in_hand(me, NIGHT_STRETCHER) > 0
        _trash = {c.id for c in (me.discard or [])}
        for cid in list(wants.keys()):
            if wants[cid] > 0 and dk.get(cid, 0) == 0:
                if (_tanka_alive and cid in _trash
                        and (cid in ENERGY_IDS or getattr(CARD_TABLE.get(cid), "hp", None))):
                    wants[cid] = max(1, wants[cid] - 15)   # タンカ経由: 一手遠いぶん減点
                else:
                    wants[cid] = -1
    # wants強化#1(go方針 2026-08-10「wantsリストはもっと強化しないと」): 補給需要。
    # 対フーディン解剖の主因=札の飢餓(弾切れターンの55%でサポートが手札に無い)。
    # 手札に打てるサポートが1枚も無いなら、リーリエ(補給の再帰点)を needs に載せる。
    # 50点=取得130000未満(NC120000の温存序列は上のNC専用枝が先に発火するため不変)。
    # 在庫切れ(山に無い)は下の在庫補正が自動で除外する。
    # 手札2枚以下は既存の緊急枝(取得180000)が正解手なので、wantsで上書きしない。
    # 再較正(2026-08-10 A/B#1: 広条件50点はtetsutani-4.5/v12-3.9の毒 → 場面の救済に絞る):
    # 「サポ0×体もエネも無い死に手札」= 解剖で特定した本物の飢餓形だけに限定
    if ((me.handCount or 0) >= 3
            and not any(getattr(c, "id", None) in SUPPORTERS for c in (me.hand or []))
            and count_basics_in_hand(me) == 0
            and not any(getattr(c, "id", None) in ENERGY_IDS for c in (me.hand or []))):
        wants[LILLIE_RESOLVE] = max(wants.get(LILLIE_RESOLVE, 0), 50)
    # go規約(2026-07-29): wantsは100点満点
    for cid in list(wants.keys()):
        if wants[cid] > 100:
            wants[cid] = 100
    return wants


def expected_wants_value(me, opponent, k: int, picks: int = 2) -> int:
    """自分の残り山(残り札カウンタで既知)からk枚めくった時に取れるwants期待値。
    go設計(2026-07-29): 「山を温存するか」ではなく「いま欲しいカードが出てくるか」で
    ドロー/ディグ系を採点するための共通関数。P(出現)≈min(1, 枚数×k/山残)の一次近似"""
    dk = _ROUTE_STATE.get("my_deck_known") or {}
    total = sum(dk.values())
    if total <= 0:
        # カウンタ未確定(全公開前)はデッキリストから導出: 60枚 - 手札 - 場 - トラッシュ
        # (サイド6枚分は不確実性として山側に残す近似)
        import collections as _c
        dk = dict(_c.Counter(read_deck_csv()))
        for c in (me.hand or []):
            if dk.get(c.id, 0) > 0: dk[c.id] -= 1
        for c in (me.discard or []):
            if dk.get(c.id, 0) > 0: dk[c.id] -= 1
        for pk in field_pokemon(me):
            if dk.get(pk.id, 0) > 0: dk[pk.id] -= 1
            for e in (getattr(pk, "energyCards", None) or []):
                if dk.get(e.id, 0) > 0: dk[e.id] -= 1
            for t in (getattr(pk, "tools", None) or []):
                if dk.get(t.id, 0) > 0: dk[t.id] -= 1
        total = sum(dk.values())
        if total <= 0:
            return 0
    w = current_wants(me, opponent)
    vals = []
    for cid, cnt in dk.items():
        wv = w.get(cid, 0)
        if wv > 0 and cnt > 0:
            p = min(1.0, cnt * k / total)
            vals.append(wv * p)
    vals.sort(reverse=True)
    return int(sum(vals[:picks]))


def current_needs(me, opponent) -> set:
    """盤面ニーズ表(1425戦の実測から導出, 2026-07-22)。
    対フーディン: キバ2体62%vs0体31% / 場4体72%vs1体26% / イワパレス有62%
    対アグロ:    場4体88%vs1体31% / イワパレス有85%
    対ミラー:    展開は逆効果(キバ2体76%<1体89%) → ニーズなし
    対ドラパ:    キバ2体47-69% / 場4体46-69%
    """
    needs = set()
    opp_ids = opponent_visible_ids(opponent)
    if GREAT_TUSK in opp_ids:
        return needs  # ミラー: 展開＝自山の浪費。何も要求しない
    kiba_field = count_in_field(me, GREAT_TUSK)
    board_n = len(field_pokemon(me))
    if get_route() == "prize":
        # 攻めの本: prizeプラン中はイワパレス線と線のエネだけを欲しがる
        line = count_in_field(me, CRUSTLE) + count_in_field(me, DWEBBLE)
        if line < 2:
            needs.add("wall_body")
        if not any(p.id == CRUSTLE and len(p.energies) >= 3 for p in field_pokemon(me)):
            needs.add("crustle_energy")
        if line == 0 and kiba_field == 0:
            needs.add("kiba_body")
        return needs
    if kiba_field < 2:
        needs.add("kiba_body")
    if board_n < 4:
        needs.add("bench_body")
    if count_in_field(me, CRUSTLE) == 0:
        needs.add("wall_body")
    if not any(p.id == GREAT_TUSK and len(p.energies) >= 2 for p in field_pokemon(me)):
        needs.add("kiba_energy")
    return needs


def count_basics_in_hand(me) -> int:
    n = 0
    for c in (me.hand or []):
        data = CARD_TABLE.get(getattr(c, "id", None))
        if data is not None and getattr(data, "hp", 0) and getattr(data, "basic", False):
            n += 1
    return n


def hand_can_develop(me) -> bool:
    """今の手札で場に体を足せるか(たね or 展開グッズ)。"""
    if count_basics_in_hand(me) > 0:
        return True
    return (count_in_hand(me, BUDDY_BUDDY_POFFIN) > 0
            or count_in_hand(me, POKE_PAD) > 0
            or count_in_hand(me, NIGHT_STRETCHER) > 0
            or count_in_hand(me, BUG_CATCHING_SET) > 0)


def energy_gap_to_attack(pokemon: Pokemon | None) -> int:
    """最安ワザまでのエネ不足枚数。ワザ無しは大きい値(=攻撃不能)。"""
    if pokemon is None:
        return 9
    data = CARD_TABLE.get(pokemon.id)
    aids = getattr(data, "attacks", None) or []
    costs = [len(ATTACK_TABLE[a].energies) for a in aids if a in ATTACK_TABLE]
    if not costs:
        return 9
    return max(0, min(costs) - len(pokemon.energies))


def has_ready_tusk(player) -> bool:
    # 教え17拡張(2026-08-10): CG+サイド遅れならE1でもミル可(tusk_mill_ready)
    return any(p.id == GREAT_TUSK and tusk_mill_ready(p) for p in field_pokemon(player))


def active_tusk_ready(player) -> bool:
    a = active_pokemon(player)
    return a is not None and a.id == GREAT_TUSK and tusk_mill_ready(a)


def ready_tusk_on_bench(player) -> bool:
    return any(p.id == GREAT_TUSK and tusk_mill_ready(p) for p in player.bench)


def ready_crustle(player) -> bool:
    return any(p.id == CRUSTLE for p in field_pokemon(player))


def active_is_ready_crustle(player) -> bool:
    a = active_pokemon(player)
    return a is not None and a.id == CRUSTLE


def opponent_has_special_energy(opponent) -> bool:
    for pokemon in field_pokemon(opponent):
        for card in pokemon.energyCards:
            data = CARD_TABLE.get(card.id)
            if data is not None and data.cardType == CardType.SPECIAL_ENERGY:
                return True
    return False


def attack_energy_minimum(pokemon: Pokemon | None) -> int:
    if pokemon is None:
        return 99
    data = CARD_TABLE.get(pokemon.id)
    if data is None or not data.attacks:
        return 99
    costs = [len(ATTACK_TABLE[a].energies) for a in data.attacks if a in ATTACK_TABLE]
    return min(costs, default=99)


def ascension_line_ok(me) -> bool:
    """go教示(2026-08-04 ep89732961 / 2026-08-07 ep90413991): 入れ替え→アセンション線。
    エネ付きいしずまいを前に出せば、ワザ「アセンション」で山からイワパレスに進化できる。
    成立条件を②(拾う)と③(使う)で共有し、二重回路の食い違いを根治する。
    「場にイワパレス0体」は2体目作りの暴発(攻撃ターン損)を防ぐ安全弁(go承認 2026-08-07)。"""
    if count_in_field(me, CRUSTLE) != 0:
        return False
    if (_MY_DECK_60.get(CRUSTLE, 0) - count_in_hand(me, CRUSTLE)
            - count_in_field(me, CRUSTLE) - count_in_discard(me, CRUSTLE)) <= 0:
        return False
    if not any(p is not None and p.id == DWEBBLE and attached_energy_count(p) >= 1
               for p in (me.bench or [])):
        return False
    active = active_pokemon(me)
    return active is None or not any(
        can_pay_attack(active, aid)
        for aid in getattr(CARD_TABLE.get(active.id), "attacks", []) or [])


def budew_lock_line_ok(me, opponent, state) -> bool:
    """go教示(2026-08-07 ep90441584): 後攻1ターン目(turn=2)のスボミー=アイテムロック線。
    むずがゆかふんで相手の次ターンのグッズ(アメ/ポフィン/パッド)を止める。
    修正(go指摘 2026-08-09): むずがゆかふんのコストは空(0エネ)。旧実装の
    「エネを用意できる」条件はカード知識の誤りで、ロック線を無用に狭めていた上に
    装着の無駄遣い(176000)を誘発していた。エネ条件を撤廃。
    成立条件: ベンチにプランの体が既に居る + スボミーを前に出す手段。"""
    if getattr(state, "turn", 0) != 2:
        return False
    if not any(p is not None and p.id in (DWEBBLE, CRUSTLE, GREAT_TUSK)
               for p in (me.bench or [])):
        return False
    active = active_pokemon(me)
    if active is not None and active.id == BUDEW:
        return True
    return count_in_hand(me, SWITCH) >= 1


def opponent_can_attack_soon(opponent) -> bool:
    active = active_pokemon(opponent)
    if active is None:
        return False
    return attached_energy_count(active) + 1 >= attack_energy_minimum(active)


def opponent_ex_pressure(opponent) -> bool:
    active = active_pokemon(opponent)
    if active is not None and is_ex_pokemon(active) and opponent_can_attack_soon(opponent):
        return True
    for pokemon in opponent.bench:
        if is_ex_pokemon(pokemon) and attached_energy_count(pokemon) + 1 >= attack_energy_minimum(pokemon):
            return True
    return False


def opponent_shows_ex_evolution_line(opponent) -> bool:
    for pokemon in field_pokemon(opponent):
        data = CARD_TABLE.get(pokemon.id)
        if data is not None and (is_ex_card(data.cardId) or data.name in EX_EVOLUTION_ANCESTORS):
            return True
    return False


def retreat_cost(pokemon: Pokemon | None) -> int:
    if pokemon is None:
        return 0
    data = CARD_TABLE.get(pokemon.id)
    return getattr(data, "retreatCost", 0) if data is not None else 0


# 効果ダメカン技(素点0だが実質打点を持つ)の登録表: ハンドパワー=手札×20
_HAND_POWER_AIDS = {a for a, at in ATTACK_TABLE.items()
                    if getattr(at, "name", "") in ("ハンドパワー", "Powerful Hand")}


def _defender_blocks_effects(defender) -> bool:
    """ミスト持ち(全員)/ロック闘持ち(闘=キバ)は相手ワザの効果(ダメカン置き)を受けない。"""
    for e in (getattr(defender, "energyCards", None) or []):
        eid = getattr(e, "id", None)
        if eid == MIST_ENERGY:
            return True
        if eid == ROCK_FIGHTING_ENERGY and getattr(defender, "id", None) == GREAT_TUSK:
            return True
    return False


def next_turn_best_damage(pk, defender, owner=None, extra_energy: int = 1,
                          nc_up: bool = False, include_effects: bool = True) -> int:
    """ゆら§13修正版(2026-08-17): pkが次の番(エネ+extra枚の枚数近似)に出せる最大実効打点。
    - 素点: 弱点抵抗込み。ただし攻め手がexで、受け手がイワパレス(しんぴのいしやど)
      またはNC下の非ルールなら0(ワザのダメージを受けない)
    - 効果ダメカン(ハンドパワー等): 受け手がミスト/ロック闘持ちなら0。NC/特性では防げない
    """
    if pk is None or defender is None:
        return 0
    atk_is_ex = is_ex_card(pk.id)
    dmg_blocked = atk_is_ex and (
        getattr(defender, "id", None) == CRUSTLE
        or (nc_up and not is_ex_card(getattr(defender, "id", 0) or 0)))
    eff_blocked = _defender_blocks_effects(defender)
    best = 0
    for _aid in getattr(CARD_TABLE.get(pk.id), "attacks", None) or []:
        _at = ATTACK_TABLE.get(_aid)
        if _at is None:
            continue
        if attached_energy_count(pk) + extra_energy < len(getattr(_at, "energies", None) or []):
            continue
        d = 0
        if not dmg_blocked:
            d = typed_damage(getattr(_at, "damage", 0) or 0, pk.id, defender.id)
        if (include_effects and _aid in _HAND_POWER_AIDS
                and not eff_blocked and owner is not None):
            d = max(d, (getattr(owner, "handCount", 0) or 0) * 20)
        best = max(best, d)
    return best


def lethal_avoid_boss_target(me, opponent, nc_up: bool = False):
    """ゆら枝①修正版(2026-08-17 ep93559312 T5): 相手の前が次番こちらの前を確定KOする一方、
    ベンチに「1枚貼っても非致死かつ逃げ不能」の的がいるならその的を返す。
    救出対象はイワパレス/キバ/エネ付き/場2体以下に限定(ボスの浪費防止)。
    複数候補は「次ターン打点が低い→逃げにくい」順で選ぶ。"""
    my_act = active_pokemon(me)
    oa = active_pokemon(opponent)
    if my_act is None or oa is None:
        return None
    if not (my_act.id in (CRUSTLE, GREAT_TUSK)
            or attached_energy_count(my_act) > 0
            or len(field_pokemon(me)) <= 2):
        return None
    hp_left = getattr(my_act, "hp", 0) or 0
    # アブレーション実測(2026-08-17): 発火は「素点の致死」のみ。効果ダメカン型
    # (ハンドパワー等)への正解はミスト免疫であり、ボス救出は的がテレポート等で
    # 逃げ戻るだけの浪費だった(フーディン面-4.8の毒の根治)
    if hp_left <= 0 or next_turn_best_damage(oa, my_act, opponent, nc_up=nc_up,
                                             include_effects=False) < hp_left:
        return None
    best, best_key = None, None
    for p in (opponent.bench or []):
        if p is None:
            continue
        d = next_turn_best_damage(p, my_act, opponent, nc_up=nc_up)
        if d >= hp_left:
            continue
        if attached_energy_count(p) + 1 >= retreat_cost(p):
            continue
        key = (d, -retreat_cost(p))
        if best_key is None or key < best_key:
            best, best_key = p, key
    return best


def ex_wall_adjustment(candidate_id: int, me, opponent, nc_up: bool) -> int:
    """§1(2026-08-17): 対ex壁の不変条件。相手の前がex×NC無しの間は、前に出す駒を
    イワパレス(しんぴのいしやど=exのワザダメージを受けない)に固定し、キバの前進を抑止。
    NC下または相手の前が非ex(ハリテヤマ等)なら調整なし=通常ロジック。"""
    oa = active_pokemon(opponent)
    if oa is None or not is_ex_pokemon(oa) or nc_up:
        return 0
    if candidate_id == CRUSTLE:
        return 80000
    if candidate_id == GREAT_TUSK:
        return -60000
    return 0


def opponent_has_ex_or_ex_line_pressure(opponent) -> bool:
    return opponent_ex_pressure(opponent) or opponent_shows_ex_evolution_line(opponent)


def opponent_has_trappable_bench(opponent) -> bool:
    for p in opponent.bench:
        if p is None:
            continue
        if attached_energy_count(p) == 0 and retreat_cost(p) >= 1:
            return True
    return False


def opponent_has_trappable_basic_bench(opponent) -> bool:
    for p in opponent.bench:
        if p is None:
            continue
        data = CARD_TABLE.get(p.id)
        if data is not None and getattr(data, "basic", False) and attached_energy_count(p) == 0 and retreat_cost(p) >= 1:
            return True
    return False



# --- Opponent package recognition + generic feature layer ---
LUCARIO_STRONG_IDS = {673, 674, 675, 676, 677, 678, 1141, 1252}
DRAGAPULT_SAMPLE_IDS = {119, 120, 121, 1256, 1080}
ABOMASNOW_SAMPLE_IDS = {721, 722, 723, 1262}
ALAKAZAM_IDS = {741, 742, 743}  # ケーシィ線の本体のみ。修正(go承認 2026-08-10):
# バトルコロシアム(1264)を除外 — ミラーの相手が貼ると誤発火。
# 修正2(go承認 2026-08-12 ep92038482): テレパス超エネ(19)を除外 — ホップ/ノコッチ系の
# ゴーストデッキも使うため、教え14系の防御形(前キバ我慢等)が誤発火していた。
# 19は下のHINTとして「ミスト温存(JIT警戒)」側にだけ残す(本物のフーディンはT1-2に
# ケーシィが必ず出るので、本体検知の遅れは1ターン以内)
ALAKAZAM_HINT_IDS = {19}

def opponent_visible_ids(opponent) -> set[int]:
    ids = set()
    for p in field_pokemon(opponent):
        if p is not None:
            ids.add(p.id)
            for e in getattr(p, 'energyCards', []) or []:
                ids.add(e.id)
            for t in getattr(p, 'tools', []) or []:
                ids.add(t.id)
    for c in (opponent.discard or []):
        ids.add(c.id)
    return ids

def facing_lucario_strong(opponent) -> bool:
    return bool(opponent_visible_ids(opponent) & LUCARIO_STRONG_IDS)

def facing_dragapult_sample(opponent) -> bool:
    return bool(opponent_visible_ids(opponent) & DRAGAPULT_SAMPLE_IDS)

def facing_abomasnow_sample(opponent) -> bool:
    return bool(opponent_visible_ids(opponent) & ABOMASNOW_SAMPLE_IDS)

def facing_alakazam(opponent) -> bool:
    return bool(opponent_visible_ids(opponent) & ALAKAZAM_IDS)

STARMIE_SAMPLE_IDS = {STARYU, MEGA_STARMIE_EX}
def facing_starmie(opponent) -> bool:
    return bool(opponent_visible_ids(opponent) & STARMIE_SAMPLE_IDS)


# 教え44(go裁定 2026-08-14): 「効果ワザでこちらに触ってくるポケモン」の集合を
# カード効果文から自動導出する(ID直書き禁止のgo抽象化原則)。ミスト/ロック闘の
# 「相手のワザの効果を受けない」が実仕事をする対面の判定に使う
import re as _re44
# エンジンの効果文は英語(日本語はビューワ側の訳)。カーリー引用符(can't)の正規化必須
_EFFECT_PAT44 = _re44.compile(
    r"(is now (Poisoned|Paralyzed|Asleep|Confused|Burned)"
    r"|(put|place)s? .{0,60}damage counters? on .{0,30}opponent"
    r"|discard .{0,60}Energy from your opponent"
    r"|opponent.{0,80}(can't|cannot) (attack|retreat|play|use|evolve)"
    r"|[Ss]witch .{0,60}opponent"
    r"|opponent.{0,60}(shuffles?|puts?|returns?).{0,50}(hand|deck))", _re44.I)
def _build_effect_attacker_ids() -> set:
    out = set()
    try:
        for _cid, _cd in CARD_TABLE.items():
            for _aid in (getattr(_cd, "attacks", []) or []):
                _at = ATTACK_TABLE.get(_aid)
                _t = (getattr(_at, "text", "") or "").replace("’", "'")
                if _t and _EFFECT_PAT44.search(_t):
                    out.add(_cid)
                    break
    except Exception:
        pass
    return out
EFFECT_ATTACKER_IDS = _build_effect_attacker_ids()
def opponent_effect_attacker_visible(opponent) -> bool:
    return bool(opponent_visible_ids(opponent) & EFFECT_ATTACKER_IDS)


# 教え62(go指摘 2026-08-15): 「特性でダメカンを置く/移す」ポケモンの集合を特性文から
# 自動導出(ID直書き禁止)。旧コロシアム検知はユキワラシ(860)直書きで進化後の
# ユキメノコ(104)を見落とし、マリィ悪の負け11局中4局でコロシアム0回の主因だった。
_ABILITY_CHIP_PAT62 = _re44.compile(r"(put|move|place)s? .{0,60}damage counters?", _re44.I)
def _build_ability_chip_ids() -> set:
    out = set()
    try:
        for _cid, _cd in CARD_TABLE.items():
            for _sk in (getattr(_cd, "skills", None) or []):
                _t = (getattr(_sk, "text", "") or "").replace("\u2019", "'")
                if _t and _ABILITY_CHIP_PAT62.search(_t):
                    out.add(_cid)
                    break
    except Exception:
        pass
    return out
ABILITY_CHIP_IDS = _build_ability_chip_ids()


def attach_keeps_cost_payable(target, card_id: int) -> bool:
    """教え44改(go裁定 2026-08-14): 「ポケモンの攻撃ワザに必要なエネルギーを理解して貼る」。
    この1枚を貼った後も、対象のいずれかの攻撃ワザの色要件を残り枠で満たせるかを検算する。
    どのワザも満たせなくなる装着(例: 草0のイワパレスに非草3枚目)だけFalseを返す。
    コスト超過分の装着(CG割引運用など)と無色コストのワザは常に許容(保守的判定)。"""
    try:
        data = CARD_TABLE.get(getattr(target, "id", 0))
        attacks = getattr(data, "attacks", []) or []
        if not attacks:
            return True
        def _provides(eid):
            d = CARD_TABLE.get(eid)
            return getattr(d, "energyType", None) or 0
        new_types = [_provides(getattr(e, "id", 0))
                     for e in (getattr(target, "energyCards", None) or [])] + [_provides(card_id)]
        for aid in attacks:
            at = ATTACK_TABLE.get(aid)
            cost = list(getattr(at, "energies", []) or [])
            if not cost:
                continue
            if len(new_types) > len(cost):
                return True   # コスト超過運用は別ルールの管轄
            free = len(cost) - len(new_types)
            deficit = 0
            for ct in set(t for t in cost if t != 0):
                need = sum(1 for t in cost if t == ct)
                have = sum(1 for t in new_types if t == ct)
                deficit += max(0, need - have)
            if deficit <= free:
                return True
        return False
    except Exception:
        return True


SELF_DIGGER_IDS = {65, 66, 305, 741, 742, 743}  # ノコッチ/ノココッチ線+フーディン線: 自掘りエンジンの指紋


BENCH_CHIP_IDS = {646, 647, 648, 104, 860, 112}  # マリィ線+ユキメノコ/ユキワラシ+マシマシラ


def opponent_chips_board(opponent) -> bool:
    """解剖384戦(2026-07-31): マリィ悪/ユキメノコ系は壁を「攻撃以外の3経路」で崩す —
    シャドーバレットのベンチ30点狙撃 / ユキメノコ特性の特性持ち全体10点 /
    マシマシラのダメカン移動。短期負け83戦の95%が場切れ。
    この対面クラスは『壁で受ける』でなく『進化を急ぎ補充を続ける』が正解"""
    return bool(opponent_visible_ids(opponent) & BENCH_CHIP_IDS)


def giant_tusk_plan(me, opponent) -> bool:
    """go承認(2026-08-06/07): ロック闘デッキの狩りプラン。相手の場に
    「はさみ(弱点込み)一撃圏外かつギガントタスク160で一撃圏内」の非exがいれば
    キバ4エネ武装で狩る。可変ダメージ持ち(フーディンHP140)も対象(60点条件なし)"""
    _rock_avail = (count_in_hand(me, ROCK_FIGHTING_ENERGY) > 0
                   or _MY_DECK_60.get(ROCK_FIGHTING_ENERGY, 0) > 0)
    if not _rock_avail:
        return False
    for p in field_pokemon(opponent):
        if p is None:
            continue
        if is_ex_pokemon(p):
            # 教え59(go提案 2026-08-14): 「対壁はキバの4エネ技が早い」。闘弱点のex壁
            # (ロケット団ガルーラex230/メガガルーラex300)は弱点込み160×2=320で一撃圏、
            # しかもex=サイド2枚で取得速度もはさみ超え。弱点で一撃になる時だけ狩り対象
            _tusk_hit59 = typed_damage(160, GREAT_TUSK, p.id)
            if _tusk_hit59 > 160 and _tusk_hit59 >= p.hp:
                return True
            continue
        _pd = CARD_TABLE.get(p.id)
        # 教え9付随修正(2026-08-09): p.hpは既に現在値。damage_onを引くと二重引きで
        # 「1発目を当てた瞬間に計画OFF→2発目が撃てない」バグだった
        hp_rem = p.hp
        sciss = typed_damage(120, CRUSTLE, p.id)
        if sciss < hp_rem <= 160 and (getattr(_pd, "attacks", []) or []):
            return True
        # 教え9(go提案 2026-08-09 ep91194801): 「殴ってくる壁」も狩る=160×2発プラン。
        # 実測: マント付きイワパレス壁(HP190)にギガントタスク計画が「一撃圏内限定」の
        # 条件で不発、27ターン一度も反撃せず取り切られ負け。
        # 適用範囲: 攻撃手段を持つ非exで一撃圏外(>160)、かつ
        #   ①はさみ2発でも届かない(>240) または
        #   ②回復指紋(コック1212/ジャンボアイス1147が相手の見えるゾーン) または
        #   ③道具でHP増強(maxHpがカタログ値超=マント等) — はさみの純打点が回復に食われる形。
        # キバは非exなので、倒されてもサイド1枚=「サイドを取られるのを抑制」(go)
        if hp_rem > 160 and sciss < 240 and (getattr(_pd, "attacks", []) or []):
            # 追加条件(2026-08-09 6面A/B: bc-4.7の毒切除): はさみが弱点で240になる相手
            # (草弱点=オーロンゲ等)は常にイワパレス線が上位互換(240×2>320、コストも軽い)。
            # 2発プランは「はさみが素の120でしか通らない相手」限定
            _catalog_hp = getattr(_pd, "hp", None) or 0
            _boosted = p.maxHp > _catalog_hp > 0
            _heal_fp = bool(opponent_visible_ids(opponent) & {1212, 1147})
            if hp_rem > 240 or _heal_fp or _boosted:
                return True
    return False


def closing_plan(me, opponent, state):
    """取り切りモード(go設計 2026-08-06 ep90314751): 残サイド<=2で、
    「2ターン以内に弱点込み実効打点でex(2枚分)を取り切れる」計画が成立するなら
    その内容を返す。成立中は部品(エネ/ボス/入れ替え)の温存とリーリエ禁止を統制する。"""
    try:
        if len(me.prize or []) > 2:
            return None
        best = None
        for atk in field_pokemon(me):
            if atk is None or atk.id != CRUSTLE:
                continue
            need = max(0, 3 - attached_energy_count(atk))
            if need > 2:
                continue
            _ad = CARD_TABLE.get(atk.id)
            for tgt in field_pokemon(opponent):
                if tgt is None or not is_ex_pokemon(tgt):
                    continue
                if typed_damage(120, atk.id, tgt.id) >= (tgt.hp - damage_on(tgt)):
                    cand = {"need": need, "attacker_serial": getattr(atk, "serial", None),
                            "target_id": tgt.id}
                    if best is None or need < best["need"]:
                        best = cand
        if best is None:
            return None
        # go設計(2026-08-06): 欠品は計画中止の理由ではなく「wantsに載せる差分」。
        # 攻めプランの詰め形として、足りない部品をリストで返す(理想盤面差分方式)
        _act = active_pokemon(me)
        missing = []
        if not (count_in_hand(me, SWITCH) > 0
                or (_act is not None and getattr(_act, "serial", None) == best["attacker_serial"])):
            missing.append(SWITCH)
        if count_in_hand(me, BOSS_ORDERS) == 0:
            missing.append(BOSS_ORDERS)   # 逃げ対策(必須ではないが欲しい)
        if best["need"] > count_in_hand(me, BASIC_GRASS_ENERGY) + count_in_hand(me, MIST_ENERGY):
            missing.append(BASIC_GRASS_ENERGY)
            missing.append(MIST_ENERGY)
        best["missing"] = missing
        return best
    except Exception:
        return None


def dig_lifetime_ok(me, opponent, cost: int, attacking: bool) -> bool:
    """寿命会計(go承認 2026-08-06): 自傷ディグは「掘った後の自山(寿命) >
    相手を削り切るのに必要なターン数+保険4」の時だけ許可。
    実例: 草スタール戦ep89826656 T22/T24の自殺ディグ(勝ちレースを自分で放棄)"""
    # v2(2026-08-06 切り分け確定): 序中盤(自山>20)は適用しない。旧版は
    # 「攻撃できないターン=ミル0」の悲観計算で、立て直し中の補給まで禁止し
    # フーディン-7.2ptの毒になった(自殺ディグは全て自山13以下で発生している)
    if me.deckCount > 20:
        return True
    # 教え65(2026-08-16): 保険4→6。本番のメガスターミー系50ターン級で
    # 自山切れ鼻差負け×2(ターン59で相山2/ターン45で相山10)への処方
    opp_turns = (opponent.deckCount + 1) // 2 + 6
    return me.deckCount - cost > opp_turns


def opponent_mills_us(opponent) -> bool:
    """相手の公開ポケモンに「こちらの山を削るワザ」があるか(go設計 2026-07-29:
    自山温存が要るのは①相手が自山を削る対面②自山切れが勝ち筋到達より早い時、のみ)"""
    for pk in field_pokemon(opponent):
        for aid in getattr(CARD_TABLE.get(pk.id), "attacks", []) or []:
            at = ATTACK_TABLE.get(aid)
            t = (getattr(at, "text", "") or "").lower() if at is not None else ""
            if "opponent" in t and "deck" in t and "discard" in t:
                return True
    return False


def non_ex_passive_opponent(opponent) -> bool:
    """go方針(2026-07-31 pixiux解剖): 非exしか見えない受動的な相手(タンク/壁単系)には
    基本デッキ破壊を貫く。受動 = 自掘りエンジンの指紋も見えていないこと"""
    pokes = [p for p in field_pokemon(opponent) if p is not None]
    if not pokes:
        return False
    if any(is_ex_pokemon(p) for p in pokes):
        return False
    # 別セッション発見(2026-08-06 ep90150482): エースバーン等「山からエネを探して
    # 加速するワザ」持ちは無害な受動タンクではない(数ターンで大型が完成する)。
    # ワザテキストからエネ加速の指紋を検出して受動扱いから除外(ID直書きしない)
    for p in pokes:
        if (getattr(CARD_TABLE.get(p.id), "hp", 0) or 0) < 130:
            continue   # 小物の加速は脅威扱いしない(2026-08-06切り分け: ベロバー誤反応)
        for aid in getattr(CARD_TABLE.get(p.id), "attacks", []) or []:
            at = ATTACK_TABLE.get(aid)
            t = (getattr(at, "text", "") or "").lower() if at is not None else ""
            if "energy" in t and "attach" in t and ("deck" in t or "discard pile" in t):
                return False
    return not (opponent_visible_ids(opponent) & SELF_DIGGER_IDS)


def opponent_armed_nonex_beatdown(opponent) -> bool:
    """go教示(2026-08-04 ep89726241): 相手の場に「イワパレスにダメージを通せる
    武装済み(あと1エネ以内)の非exアタッカー」がいるなら受動扱いしない。
    放置して山勘定だけしていると150点連打に殴り負ける"""
    for p in field_pokemon(opponent):
        if p is None or is_ex_pokemon(p):
            continue
        for aid in getattr(CARD_TABLE.get(p.id), "attacks", []) or []:
            at = ATTACK_TABLE.get(aid)
            if at is None or (getattr(at, "damage", 0) or 0) < 60:
                continue
            if attached_energy_count(p) + 1 >= len(getattr(at, "energies", []) or []):
                return True
    return False


def crustle_lock_counter(me, opponent) -> bool:
    """ロック反撃(go実戦 2026-07-30 ep88848623): 前のイワパレスが相手のex攻撃を
    無効化している時、勝ち筋=イワパレスで殴り続けること。エネもワザもイワパレスへ"""
    _me_act = active_pokemon(me)
    if _me_act is None or _me_act.id != CRUSTLE:
        return False
    # go指摘(2026-07-30): 見えていない非exアタッカーは判定できない。
    # 非ex線を持つと認識済みの対面(マリィ悪=オーレム/ユキメノコ線)では発動しない
    if opponent_visible_ids(opponent) & {646, 647, 648, 860, 104}:
        return False
    _atk_pokes = [pk for pk in field_pokemon(opponent)
                  if any((getattr(ATTACK_TABLE.get(_aid), "damage", 0) or 0) >= 60
                         for _aid in getattr(CARD_TABLE.get(pk.id), "attacks", []) or [])]
    return bool(_atk_pokes) and all(is_ex_pokemon(pk) for pk in _atk_pokes)


def own_deck_conservation_needed(me, opponent) -> bool:
    if opponent_mills_us(opponent):
        return True
    # go教示(2026-07-30 ep88848098): ロック成立(前のイワパレスが相手のex攻撃を無効化)
    # かつ相手のアタッカーがex主体なら、負け筋は自山切れだけになる。
    # 「本来勝てたのに自山を削って負ける」の封じ: 1枚も無駄にしない
    _me_act = active_pokemon(me)
    if _me_act is not None and _me_act.id == CRUSTLE:
        _atk_pokes = [pk for pk in field_pokemon(opponent)
                      if any((getattr(ATTACK_TABLE.get(_aid), "damage", 0) or 0) >= 60
                             for _aid in getattr(CARD_TABLE.get(pk.id), "attacks", []) or [])]
        if _atk_pokes and all(is_ex_pokemon(pk) for pk in _atk_pokes):
            return True
    if opponent_visible_ids(opponent) & SELF_DIGGER_IDS:
        # go設計の帰結(2026-07-29): 自掘りエンジン持ち(フーディン等)は放っておいても
        # 自山が減る。こちらが先導で6枚ずつ燃やすと相手の山切れより先に自滅する
        return True
    return me.deckCount <= 12   # 長期戦マージン: ここを切ったら自然消費でも自滅圏


def hand_usefulness(me, opponent, state) -> int:
    """手札が理想盤面への差分をどれだけ埋められるか(go設計: リーリエ判断は逆算で)。
    2以上=まだ手札に仕事がある。0-1=手札が差分に答えていない→リーリエで回してよい"""
    u = 0
    # エネ需要: プラン別の砲台のエネギャップに対して手札エネが充当できる分
    e_hand = sum(count_in_hand(me, _e) for _e in ENERGY_IDS)
    if get_route() == "prize":
        gap = max((3 - attached_energy_count(p) for p in field_pokemon(me)
                   if p.id == CRUSTLE), default=0)
    else:
        gap = max(0, 2 - max((attached_energy_count(p) for p in field_pokemon(me)
                              if p.id == GREAT_TUSK), default=0))
    if not getattr(state, "energyAttached", False):
        u += 2 * min(gap, min(e_hand, 1))
    # 体需要: needsにある体を手札が持っているか
    _n = current_needs(me, opponent)
    if ("wall_body" in _n or "bench_body" in _n) and (count_in_hand(me, DWEBBLE) or count_in_hand(me, BUDEW)):
        u += 2
    if "kiba_body" in _n and count_in_hand(me, GREAT_TUSK):
        u += 2
    # 進化: 場のイシズマイ+手札イワパレス
    if has_in_field(me, DWEBBLE) and count_in_hand(me, CRUSTLE):
        u += 2
    # 入れ替え: 前が動けず、ベンチに攻撃可能なキバがいるならスイッチは仕事
    # (go教示 2026-07-30: 「入れ替えでキバを前に出して相手の山を削れたはず」)
    if count_in_hand(me, SWITCH):
        _act2 = active_pokemon(me)
        _act_stuck = _act2 is None or not any(
            can_pay_attack(_act2, _aid) for _aid in getattr(CARD_TABLE.get(_act2.id), "attacks", []) or [])
        if _act_stuck and any(p.id == GREAT_TUSK and can_pay_attack(p, LAND_COLLAPSE)
                              for p in (me.bench or []) if p):
            u += 2
    # 妨害: 有効ハンマー(脅威ワザ2エネ以上の相手×折れるエネあり)
    if count_in_hand(me, CRUSHING_HAMMER):
        for pk in field_pokemon(opponent):
            if 1 <= len(pk.energies or []) <= 3:
                for aid in getattr(CARD_TABLE.get(pk.id), "attacks", []) or []:
                    at = ATTACK_TABLE.get(aid)
                    if at is not None and ((getattr(at, "damage", 0) or 0) >= 60
                                           or aid in (LAND_COLLAPSE, MOUNTAIN_RAMMING, HERA_MOUNTAIN_RAMMING)):
                        if len(getattr(at, "energies", []) or []) >= 2:
                            u += 2
                            break
                break
    return u


def opponent_special_hazard(opponent) -> bool:
    # 理由: 改造ハンマー(1081)は特殊エネ限定の確定除去。搭載対面ではミスト=1:1で剥がされる前提の投資。
    # 適用条件: 相手の公開札(場/トラッシュ)にハンマーが見えた、または指紋=ハンマー搭載型(現行: ラダー型フーディン)。
    # (go教訓 2026-07-28: 対ラダー型フーディン敗戦「改造ハンマーが強い。ミストを大事にしないといけない」)
    # go教示(2026-08-07): 枚数戦争 — 改造ハンマー4枚(積載上限)が相手トラッシュに
    # 落ち切ったら特殊エネはもう安全(ミスト2+ロック闘4=6 > ハンマー4。いずれ勝つ消耗戦)。
    # 【共有関数の意味変更・参照先3箇所を確認済み(2026-08-07)】
    #   ①ミスト温存JIT: ハンマー枯れ後は置き貼り解禁=教えの意図通り
    #   ②エネ在庫バッファwants: 枯れ後は需要緩和=意図通り
    #   ③クセロシキ早撃ち: 枯れ後は撃つ理由消滅=意図通り
    _spent = sum(1 for c in (opponent.discard or []) if getattr(c, "id", None) == 1081)
    # go裁定(2026-08-10): 解禁を4枚→3枚落ちに前倒し。ラダーのフーディンは3枚積みが
    # 多く(実測7局中5局)、4枚待ちでは永遠に解禁されない。4枚積み相手に1発貰う
    # リスクは許容(ミスト2+ロック闘4の在庫優位で消耗戦は勝てる)
    if _spent >= 3:
        return False
    return (1081 in opponent_visible_ids(opponent) or facing_alakazam(opponent)
            or bool(opponent_visible_ids(opponent) & ALAKAZAM_HINT_IDS))

def opponent_bench_counter_pressure(opponent) -> bool:
    if facing_dragapult_sample(opponent):
        return True
    for p in field_pokemon(opponent):
        data = CARD_TABLE.get(p.id)
        if data is None:
            continue
        for aid in getattr(data, 'attacks', []) or []:
            atk = ATTACK_TABLE.get(aid)
            txt = (getattr(atk, 'text', '') or '').lower() if atk is not None else ''
            if 'damage counter' in txt and 'bench' in txt:
                return True
    return False

def opponent_self_deck_pressure(opponent) -> bool:
    if facing_abomasnow_sample(opponent):
        return True
    for p in field_pokemon(opponent):
        data = CARD_TABLE.get(p.id)
        if data is None:
            continue
        for aid in getattr(data, 'attacks', []) or []:
            atk = ATTACK_TABLE.get(aid)
            text = (getattr(atk, 'text', '') or '').lower() if atk is not None else ''
            if ('discard the top' in text and 'your deck' in text) or ('discard' in text and 'your deck' in text and 'damage' in text):
                return True
    return False

def own_deck_safety_guard(me, opponent) -> bool:
    # Only stop optional self-thinning when the opponent itself is already burning deck fast.
    if not opponent_self_deck_pressure(opponent):
        return False
    return me.deckCount <= max(8, opponent.deckCount + 4) and opponent.deckCount > 4

def desired_field_floor(me, opponent, state) -> int:
    if facing_lucario_strong(opponent):
        return 5
    if opponent_bench_counter_pressure(opponent):
        return 3
    if opponent_can_attack_soon(opponent):
        return 3
    return 2

def urgent_field_rebuild(me, opponent, state) -> bool:
    return len(field_pokemon(me)) < desired_field_floor(me, opponent, state)

def generic_active_nonex_race_threat(opponent) -> bool:
    a = active_pokemon(opponent)
    if a is None or is_ex_pokemon(a):
        return False
    return attached_energy_count(a) >= 2 and a.hp <= 170


def should_wall_mode(me, opponent, state) -> bool:
    # A live boosted mill turn is worth more than moving into the wall.
    if active_tusk_ready(me) and count_in_hand(me, EXPLORER_GUIDANCE) > 0 and not state.supporterPlayed:
        return False
    if opponent.deckCount <= 20:
        return False
    active = active_pokemon(me)
    stadium_id = state.stadium[0].id if state.stadium else None
    if stadium_id == NEUTRAL_CENTER and active is not None and not is_ex_pokemon(active):
        # Neutralization Zone already turns Great Tusk into the preferred wall,
        # while keeping the primary mill attack online.
        return False
    # go指摘(2026-07-29 ep88788948: 3枚差の自滅負け): 壁は「殴ってくる相手」にだけ立てる。
    # ミル同型の相手のイワパレス線を脅威と誤認して壁を立て、ミルを止めていた
    _opp_can_hurt = any((getattr(ATTACK_TABLE.get(_aid), "damage", 0) or 0) >= 60
                        for _pk in field_pokemon(opponent)
                        for _aid in getattr(CARD_TABLE.get(_pk.id), "attacks", []) or [])
    if not _opp_can_hurt:
        return False
    # Generic wall mode: prefer a non-ex wall against visible ex/evolution-line pressure.
    if not opponent_has_ex_or_ex_line_pressure(opponent):
        return False
    if has_in_field(me, CRUSTLE) or has_in_field(me, DWEBBLE) or count_in_hand(me, DWEBBLE) or count_in_hand(me, CRUSTLE):
        return True
    return False


WALL_MARKER_IDS = {756, 24}  # メガガルーラex / ロケット団ガルーラex（ガルーラ系のみ。イワパレスはミラーにも居るため除外）


def facing_passive_wall(opponent) -> bool:
    return bool(opponent_visible_ids(opponent) & WALL_MARKER_IDS)


def opponent_max_charge(opponent) -> float:
    """相手の場で最も「攻撃成立に近い」ポケモンの充電率(0.0-1.0+)。"""
    best = 0.0
    for p in field_pokemon(opponent):
        need = attack_energy_minimum(p)
        if need <= 0 or need >= 99:
            continue
        best = max(best, attached_energy_count(p) / need)
    return best


def zone_protects_us(state) -> bool:
    return bool(state.stadium) and state.stadium[0].id == NEUTRAL_CENTER


def opponent_locked_window(opponent) -> bool:
    """goの実戦(manual 2026-07-18/19): 相手の手札が枯れて攻撃が立たない間は、
    LOを止めてサイドを取りに行く方が速い（壁のガルーラが起動する前に刈る）。
    誤発火ガード: 実証済みの受動壁アーキタイプに限定して発火させる。"""
    if not facing_passive_wall(opponent):
        return False
    return opponent.handCount <= 2 and not opponent_can_attack_soon(opponent)


def should_ko_mode(me, opponent, state) -> bool:
    active = active_pokemon(me)
    opp_active = active_pokemon(opponent)
    if active is None or opp_active is None or opponent.deckCount <= 8:
        return False
    if opponent_locked_window(opponent):
        return True
    if facing_passive_wall(opponent) and zone_protects_us(state):
        # ゾーン下の壁戦: ガルーラexの攻撃は無効。非exイワパレスの120は
        # キバ(エキサイト下170)が2発耐えるので、刈り取りのトレードは成立する。
        return True

    # Estimate both actual win routes instead of treating damage as a last-resort
    # action. Do not assume an Explorer that is not actually available.
    tusks = [p for p in field_pokemon(me) if p.id == GREAT_TUSK]
    if tusks:
        best_tusk = max(tusks, key=attached_energy_count)
        mill_setup = max(0, 2 - attached_energy_count(best_tusk))
        if best_tusk.serial != active.serial:
            mill_setup += 1
        mill_per_turn = 4 if count_in_hand(me, EXPLORER_GUIDANCE) > 0 and not state.supporterPlayed else 1
        mill_turns = mill_setup + (opponent.deckCount + mill_per_turn - 1) // mill_per_turn
    else:
        # Search, two attachments and a promotion are still required.
        mill_turns = 4 + opponent.deckCount
    prizes_taken_by_opponent = max(0, 6 - len(opponent.prize))
    durant_damage = 30 + 30 * prizes_taken_by_opponent

    plans = []
    # go指摘の系譜(2026-07-31「ギガントタスクは撃てない」/2026-08-02 ep89531719):
    # 旧表はソルルナ時代の遺物で、現デッキに不在の7種+撃てないギガントタスク(闘エネ0)で
    # KO可能性を誤認→T3でko_mode点灯→エネがキバに流れる事故の根。実在プランのみ残す
    attack_profiles = {
        CRUSTLE: (SUPERB_SCISSORS, 120),
    }
    for pokemon in field_pokemon(me):
        profile = attack_profiles.get(pokemon.id)
        if profile is None:
            continue
        attack_id, damage = profile
        attack = ATTACK_TABLE.get(attack_id)
        if attack is None or damage <= 0:
            continue
        setup_turns = max(0, len(attack.energies) - attached_energy_count(pokemon))
        switch_turns = 0 if pokemon.serial == active.serial else 1
        attack_turns = (opp_active.hp + damage - 1) // damage
        plans.append((setup_turns + switch_turns + attack_turns, damage, pokemon.id))
    if not plans:
        return False

    stadium_id = state.stadium[0].id if state.stadium else None
    zone_bypass_attacker = (
        stadium_id == NEUTRAL_CENTER
        and not is_ex_pokemon(opp_active)
        and any(is_ex_pokemon(pokemon) for pokemon in field_pokemon(opponent))
    )
    if zone_bypass_attacker:
        # Remove the non-ex attacker that bypasses the Zone, then return to the
        # protected mill plan against the opponent's ex board.
        return True

    turns_for_active_ko, damage, attacker_id = min(plans)
    prize_gain = 2 if is_ex_pokemon(opp_active) else 1
    immediate_prize_win = turns_for_active_ko == 1 and prize_gain >= len(me.prize)
    immediate_board_win = turns_for_active_ko == 1 and not opponent.bench
    if immediate_prize_win or immediate_board_win:
        return True

    # Approximate the rest of the prize race with the visible active target.
    knockouts_needed = (len(me.prize) + prize_gain - 1) // prize_gain
    # Setup/switch is paid once; subsequent visible targets are approximated by
    # the current target's attack count.
    attacks_for_target = (opp_active.hp + damage - 1) // damage
    ko_turns = turns_for_active_ko + attacks_for_target * (knockouts_needed - 1)
    board_clear_turns = turns_for_active_ko + attacks_for_target * len(opponent.bench)
    if len(opponent.bench) <= 1 and board_clear_turns <= mill_turns:
        return True
    return ko_turns < mill_turns


def bench_space(player) -> int:
    return player.benchMax - len(player.bench)


def can_bench_more(player) -> bool:
    return bench_space(player) > 0


def initial_active_score(card_id: int, me, opponent) -> int:
    # Lead with a disposable/setup body and preserve the mill attacker.
    if card_id == SOLROCK:
        return 13000
    if card_id == BUDEW:
        return 12800
    if card_id == DEDENNE:
        return 12600
    if card_id == SUDOWOODO:
        return 12300
    if card_id == LUNATONE:
        return 6000
    if card_id == DWEBBLE:
        return 12500
    if card_id == TATSUGIRI:
        return 9800
    if card_id == GREAT_TUSK:
        return 3500
    if card_id == FLUTTER_MANE:
        return 7000
    if card_id == CORNERSTONE_OGERPON:
        return 6500
    if card_id == DURANT_EX:
        return 3000
    return 1000


def setup_bench_score(card_id: int, me, opponent) -> int:
    if card_id == GREAT_TUSK:
        if (facing_starmie(opponent) and opponent.deckCount > 8
                and count_in_field(me, GREAT_TUSK) >= 1):
            # 教え34改(go裁定 2026-08-12): スターミー対面の「2体目以降の」キバは
            # 基本メリット薄(ベンチ狙撃の的が増えるだけ)。1体目は削りエンジン
            # なので通常通り。例外=最終盤(相手山が削り切り圏)の攻撃準備。
            # 禁止ではなく減点: 他に置ける体が無ければ相対順位で自然に置かれる
            return 2500
        return 10000 + 1200 * (2 - min(2, count_in_field(me, GREAT_TUSK)))
    if card_id == DWEBBLE:
        line = count_in_field(me, DWEBBLE) + count_in_field(me, CRUSTLE)
        board_n = len(field_pokemon(me))
        if board_n <= 2:
            # 体切れ保険(go指摘 2026-07-29 実戦ep: ベンチ空のまま攻撃してT3/T11即死)。
            # ベンチ出しが攻撃保留バー(18000)に負けて一度も置かれない構造バグの修正
            return 60000
        _opp_hurts = any((getattr(ATTACK_TABLE.get(_aid), "damage", 0) or 0) >= 60
                         for _pk in field_pokemon(opponent)
                         for _aid in getattr(CARD_TABLE.get(_pk.id), "attacks", []) or [])
        if board_n <= 3 and _opp_hurts:
            # go指摘(2026-07-30): 「盤面を作るのが遅いからやられる」。殴ってくる相手には
            # 3体以下で展開優先(ミル同型には適用しない: 展開=自山の浪費)
            return 40000
        if get_route() == "prize" and line < 3:
            # 理想盤面(go教示): 攻めプランは線を複数体。攻撃より先に置く
            return 34000
        return 9600 if line < 3 else 4200
    if card_id == BUDEW:
        # スボミー: アイテムロック壁+ボスの的の受け皿。薄い盤面では積極設置
        # (従来は汎用1000点でほぼ置かれなかった: go「盤面が薄い」の一因)
        board_n = len(field_pokemon(me))
        _opp_hurts2 = any((getattr(ATTACK_TABLE.get(_aid), "damage", 0) or 0) >= 60
                          for _pk in field_pokemon(opponent)
                          for _aid in getattr(CARD_TABLE.get(_pk.id), "attacks", []) or [])
        if opponent_chips_board(opponent):
            # go教示(2026-08-04 ep89732961): マシマシラ相手にスボミー(HP30)は
            # 出さない。特性のダメカン3個で即取られてサイドを献上するだけ
            return -6000
        if count_in_field(me, BUDEW) == 0 and board_n <= 3 and _opp_hurts2:
            return 32000
        return 3000
    if card_id == DURANT_EX:
        return 7100 if count_in_field(me, DURANT_EX) == 0 else 4300
    if card_id == TATSUGIRI:
        return 6500 if count_in_field(me, TATSUGIRI) == 0 else 2500
    if card_id == CORNERSTONE_OGERPON:
        return 5200
    if card_id == FLUTTER_MANE:
        return 3600
    return 1000


def card_keep_value(card_id: int, me, opponent, state, wall_mode: bool, ko_mode: bool) -> int:
    active = active_pokemon(me)
    attacking_tusk = active is not None and active.id == GREAT_TUSK and can_pay_attack(active, LAND_COLLAPSE)
    if get_route() == "prize":
        # 防御と温存の章(go分岐マイニング263件 2026-07-28):
        if card_id == NEUTRAL_CENTER:
            # NCは「相手のexが完成した時の保険」。相手ex武装(3エネ+)まで温存
            _opp_ex_armed = any(
                len(pk.energies or []) >= 3 and is_ex_card(pk.id)
                for pk in field_pokemon(opponent))
            _opp_big_e = any(len(pk.energies or []) >= 3 for pk in field_pokemon(opponent))
            if not (state.stadium and state.stadium[0].id == NEUTRAL_CENTER) and _opp_big_e:
                return 210000   # 脅威完成 → 今が保険の出し時
            return -3000        # それまで温存
        if card_id == CRUSHING_HAMMER:
            # go運用: 相手アタッカーのエネを折って「完成」を遅らせる(時間稼ぎ)
            if any(1 <= len(pk.energies or []) <= 3 for pk in field_pokemon(opponent)):
                return 120000
            return -2000
        if card_id == BOSS_ORDERS:
            # ボスは詰めの一手…だが例外: フロスラス線の早期除去(go教示 2026-07-28)
            # ユキメノコの特性ばら撒きが武装イワパレスを2発圏に押し込む元凶。
            # 育つ前(ユキワラシ)or育っても安いうちに引きずり出して潰す
            _froslass_line = [pk for pk in field_pokemon(opponent)
                              if pk.id in (860, 104)]
            _my_armed = any(p.id == CRUSTLE and len(p.energies) >= 3
                            for p in field_pokemon(me))
            if _froslass_line and _my_armed:
                _act = active_pokemon(opponent)
                if _act is None or _act.id not in (860, 104):
                    return 190000   # 引きずり出して次の攻撃で潰す
            # go教示(2026-07-29): 攻撃が成立しているなら、ボスで裏の「育成中のたね」
            # (マクノシタ等、進化先を持つ無防備な体)を引きずり出して狩る。
            # 相手の将来のアタッカーの芽を摘む=サイドとテンポの両取り
            _me_act = active_pokemon(me)
            _my_atk_dmg = 0
            if _me_act is not None:
                for _aid in getattr(CARD_TABLE.get(_me_act.id), "attacks", []) or []:
                    _at = ATTACK_TABLE.get(_aid)
                    if _at is not None and can_pay_attack(_me_act, _aid):
                        _my_atk_dmg = max(_my_atk_dmg, getattr(_at, "damage", 0) or 0)
            if _my_atk_dmg > 0:
                for _pk in (opponent.bench or []):
                    if _pk is None:
                        continue
                    _pd = CARD_TABLE.get(_pk.id)
                    if (_pd is not None and getattr(_pd, "evolvesTo", None)
                            and (getattr(_pd, "hp", 999) or 999) - damage_on(_pk) <= _my_atk_dmg):
                        return 170000   # 芽摘みボス: 呼んで今の攻撃で落とせる
            if not (ko_mode or len(opponent.prize) <= 2 or opponent.deckCount <= 6):
                return -3000
        if card_id in (POKE_PAD, SWITCH, POKEGEAR_30):
            # 線が完成・武装済みなら掘らない/動かさない(手数の経済)
            _line_ok = (count_in_field(me, CRUSTLE) + count_in_field(me, DWEBBLE) >= 2
                        and any(p.id == CRUSTLE and len(p.energies) >= 3
                                for p in field_pokemon(me)))
            if _line_ok and card_id != SWITCH:
                return -3000
    if card_id == EXPLORER_GUIDANCE:
        # go教示(2026-07-31): 先導はリーサルの弾。レース電卓が「勝ちに必要」と
        # 弾数を出している間は、手札干渉やコストで手放さない
        if (get_route() == "deck_out" and opponent.deckCount <= 12
                and count_in_hand(me, EXPLORER_GUIDANCE) <= 1):
            return 180000
        return 9800 if attacking_tusk and not state.supporterPlayed else 5400
    if card_id == BOSS_ORDERS:
        return 5200 if opponent_has_trappable_bench(opponent) else 900
    if card_id == LISIA_APPEAL:
        return 5000 if opponent_has_trappable_basic_bench(opponent) else 900
    if card_id == GREAT_TUSK:
        return 8500
    if card_id == LUNATONE:
        return 8200 if count_in_field(me, LUNATONE) == 0 else 2200
    if card_id == SOLROCK:
        return 8000 if count_in_field(me, SOLROCK) == 0 else 2100
    if card_id == XEROSIC_SCHEME:
        if facing_alakazam(opponent) and opponent.handCount >= 5:
            # go教示(2026-08-02): ミスト装着とクセロシキを絡め、相手の手札の
            # 改造ハンマーを枯らしてからミスト付きキバを立てると優位
            return 24000
        return 6200 if facing_passive_wall(opponent) else 4200
    if card_id in ENERGY_IDS:
        if active is not None and active.id == GREAT_TUSK and attached_energy_count(active) < 2:
            return 7400
        if has_in_field(me, CRUSTLE) and card_id in GRASS_ENERGY_IDS:
            return 4700
        return 3600
    if card_id == FIGHT_GONG:
        return 6800
    if card_id == ULTRA_BALL:
        return 6600
    if card_id == POKEGEAR_30:
        return 6200
    if card_id == ROTO_STICK:
        return 6000
    if card_id == BUDDY_BUDDY_POFFIN:
        return 7600 if count_in_field(me, DWEBBLE) + count_in_field(me, CRUSTLE) < 2 or count_in_field(me, TATSUGIRI) == 0 else 2200
    if card_id == POKE_PAD:
        return 7400 if count_in_field(me, GREAT_TUSK) == 0 or (has_in_field(me, DWEBBLE) and count_in_field(me, CRUSTLE) == 0) else 3000
    if card_id == BUG_CATCHING_SET:
        return 5600 if wall_mode or count_in_field(me, DWEBBLE) == 0 else 4200
    if card_id == DWEBBLE:
        return 5700
    if card_id == CRUSTLE:
        return 6200 if has_in_field(me, DWEBBLE) else 3000
    if card_id == DURANT_EX:
        return 5000 if can_bench_more(me) else 200
    if card_id == TATSUGIRI:
        return 4500 if not state.supporterPlayed else 2000
    if card_id == NEUTRAL_CENTER:
        # ACE SPEC is a one-of and opposing ex attackers often appear only
        # after evolution. Preserve it before the threat becomes visible.
        return 14000
    if card_id == COLRESS_TENACITY:
        current_stadium = state.stadium[0].id if state.stadium else None
        if current_stadium != NEUTRAL_CENTER and count_in_hand(me, NEUTRAL_CENTER) == 0:
            return 7600
        return 1200
    if card_id == AIR_BALLOON:
        return 7600 if any(p.id == GREAT_TUSK and not has_tool(p, AIR_BALLOON) for p in field_pokemon(me)) else 2600
    if card_id == SACRED_CHARM:
        return 7600 if opponent_can_attack_soon(opponent) else 2600
    if card_id in TOOLS:
        return 3600
    if card_id == NIGHT_STRETCHER:
        return 3400 if count_in_discard(me, GREAT_TUSK) or count_energy_in_discard(me) else 1200
    if card_id in (SACRED_ASH, ENERGY_RECYCLER):
        return 3000 if me.deckCount <= 18 else 1000
    if card_id == JUDGE:
        return 3000 if opponent.handCount <= 3 else 500
    if card_id in (ERI, XEROSIC_SCHEME):
        return 2300
    if card_id in (FLUTE, HAND_TRIMMER, ENHANCED_HAMMER, ENERGY_LASSO):
        return 2000
    return 800


def play_score(card_id: int, me, opponent, state, wall_mode: bool, ko_mode: bool) -> int:
    _ROUTE_STATE["_turn"] = int(getattr(state, "turn", 0) or 0)
    _ROUTE_STATE["_nc_up"] = bool(getattr(state, "stadium", None)) and state.stadium[0].id == NEUTRAL_CENTER
    if (card_id in (BUG_CATCHING_SET, POKE_PAD, BUDDY_BUDDY_POFFIN)
            and len(field_pokemon(me)) <= 2
            and len([p for p in (me.bench or []) if p is not None]) < (getattr(me, "benchMax", 5) or 5)):
        # §7(2026-08-17 ep93570093): 緊急場作り。体に届くグッズはリーリエ(450000)より先に吐く
        return 470000
    active = active_pokemon(me)
    active_ready_tusk = active is not None and active.id == GREAT_TUSK and tusk_mill_ready(active)
    has_explorer = count_in_hand(me, EXPLORER_GUIDANCE) > 0
    score = -10000

    if (card_id == XEROSIC_SCHEME and not state.supporterPlayed
            and opponent.handCount >= 5
            and bool(opponent_visible_ids(opponent) & {646, 647, 648})):
        # 教え66(スイープ#1採用 2026-08-16: 2面+1.5pt/tetsutani+1.1): オーロンゲ対面は
        # パンクアップ/シャドバレ部品を落とす枚数戦争を優先(進化崩落の1-2ターン前に撃つ)
        return 120000

    if card_id == EXPLORER_GUIDANCE:
        # go教示(レビュー#3): ベンチ0×手札に体なし→探検家で6枚から2枚ディグして場を作る。
        # 手札が死んでいるならリーリエ全リセット(450000)が上、手札が良いならこちらが上。
        if (not state.supporterPlayed and len(field_pokemon(me)) <= 2
                and not hand_can_develop(me)):
            # 寿命会計(2026-08-06): 場1体以下=体切れ即死リスクなので寿命より優先。
            # 場2体なら会計に従う(ep89826656 T22: 場ありで勝ちレースを掘り捨てた)
            if len(field_pokemon(me)) <= 1 or dig_lifetime_ok(me, opponent, 6, active_ready_tusk):
                return 430000
        # Route Selector v2: 封印(v1)は機械には毒(手札枯れ→場切れ264敗)。
        # go原則の正形=ペーシング: レースの余裕(山差)が6枚コストを賄える時だけ払う。
        if (not state.supporterPlayed and get_route() == "prize"
                and _ROUTE_STATE.get("attack_matchup_approved")
                and len(me.hand or []) <= 6):
            # go裁定(2026-08-02 ep89531719「使う」): 承認攻め対面(マリィ等)では
            # サポート枠を遊ばせず先導で手札+2(手札枯れ負けep89478668の対策)。
            # 係数は控えめの固定値: 攻撃保留バー(18000)は超える=攻撃前に使う。
            # go教示(2026-08-02): 飢餓(手札≤3)は95000で最優先級に引き上げ
            if not dig_lifetime_ok(me, opponent, 6, active_ready_tusk):
                return -5000
            return 95000 if len(me.hand or []) <= 3 else 50000
        if not state.supporterPlayed and get_route() == "deck_out":
            # go設計(2026-07-29): 先導の価値 = 「6枚の中に欲しいカードがいる期待値」
            # + 古代コンボのミル価値(-3)。温存は独立概念ではなく、
            # ミル同型/自山薄でコスト側が勝つ時に自然と点が下がる形にする
            _gain = expected_wants_value(me, opponent, 6)         # 0〜185程度
            _mill = 120 if active_ready_tusk else 0               # 相手山-3の換算値
            _burn = 60 if own_deck_conservation_needed(me, opponent) else 0
            if (non_ex_passive_opponent(opponent) and not opponent_mills_us(opponent)
                    and not opponent_armed_nonex_beatdown(opponent)):
                # go方針(2026-07-31): 受動タンク相手の先導は自山6 vs 削り+3の逆ザヤ。
                # 素のLand Collapse(相手-2/T vs 自山-1/T)が勝ちレース。
                # ミル加点を消し温存を常時課す(緊急の場作り430000と詰めの520000は生きる)
                _mill = 0
                _burn = 60
            if _gain >= 80 and me.deckCount >= 18:
                # go教示(2026-07-29): 致命的な欠品がある時は温存より掘る。
                # ただし山18枚未満では飢餓でも掘らない(2026-07-30: 削りすぎ注意)
                _burn = 0
            if (count_in_hand(me, EXPLORER_GUIDANCE) >= 2
                    and not any(getattr(c, "id", None) in ENERGY_IDS for c in (me.hand or []))
                    and not any(p is not None and p.id == GREAT_TUSK and tusk_mill_ready(p)
                                for p in field_pokemon(me))):
                # 教え20(go裁定 2026-08-10 ep91302456 T20): 三すくみ解除。
                # キバ未武装×手札エネ0×探検家2枚以上なら1枚は掘りに使う
                # (詰め弾は残り1枚で確保)。「探検家はキバ待ち、キバはエネ待ち、
                # エネは探検家待ち」のデッドロックで3枚抱えたまま負けた事故の根治
                return 70000
            # 教え47(go設計 2026-08-14 ep92920526の自殺根治): 詰め免除の2条件修正。
            # ①サイド判定は「相手の」サイド残を見る(相手が最後の1ターンで勝ち切れないか。
            #   旧実装は自分のサイド残を見ていた=両者6-6以外で誤判定する歪み)
            # ②自分の時計: 相手山が残るなら、探検家(6枚消費)後も自山1枚以上
            #   (勝ちまでに必要な自分の強制ドローはちょうど1回。go検算 2026-08-14)
            _d47 = max(0, opponent.deckCount - 4)
            # go裁定②(2026-08-14): うちは全員非ex=1KO1枚なので係数は×1
            # (×2のex想定は自デッキ構成に合わない過剰防衛だった)
            _lethal22 = (active_ready_tusk and opponent.deckCount <= 5
                         and _d47 < len(opponent.prize or [])
                         and (_d47 == 0 or me.deckCount - 6 >= 3))
            if not dig_lifetime_ok(me, opponent, 6, active_ready_tusk) and not (
                    active_ready_tusk and opponent.deckCount <= 4) and not _lethal22:
                return -5000   # 寿命会計: 勝ちレースを掘りで捨てない(教え22の詰めは免除)
            if active_ready_tusk and opponent.deckCount <= 4:
                # go教示(2026-07-31 手動勝利 vs pixiux): リーサル計算。
                # 先導→Land Collapse4枚で相手山0→END、相手が先にドローして死ぬ。
                # 相手山0にできるなら自山コストは無関係(go実戦: 自山3で発射し勝ち)。
                # 旧ガードme.deckCount>=7はこの勝ち手を禁止していた誤り
                return 520000   # 詰めの一撃(最優先・EVゲートより先に判定)
            if active_ready_tusk and opponent.deckCount <= 5:
                # 教え22(go指摘 2026-08-10 ep91369894): 詰め判定は固定「山4以下」でなく
                # レース算数。削った後の相手山d=deckCount-4 → 相手の残り攻撃ターン=d、
                # その間に取られる最大サイド(2/T=ex想定)がこちらの貯金未満なら発射。
                # 実戦: 相手山5×こちらサイド残3で発火せず、1枚差の詰めを逃して敗北
                _d_after = max(0, opponent.deckCount - 4)
                if _d_after < len(opponent.prize or []) and (
                        _d_after == 0 or me.deckCount - 6 >= 3):
                    # 教え47(go設計 2026-08-14): サイドは相手の残りで判定+自山1枚の生存検算
                    return 520000
            if opponent.deckCount <= 12 and count_in_hand(me, EXPLORER_GUIDANCE) <= 1:
                # go教示(2026-07-31): 射程圏では最後の先導はリーサル専用弾
                return -5000
            if len(me.hand or []) <= 3 and not (active_ready_tusk and state.energyAttached):
                # go教示(2026-08-02): ドローソースは基本使う。飢餓ならEV節制より補給。
                # 教え11(go 2026-08-09 ep91202793): 「ターン完結済み」(装着済み+攻撃可キバ)
                # なら早期リターンせずEV式へ(古代コンボのミル+3=_mill120を織り込む)。
                # 欲しい札が残っているならリーリエの8枚が確率優位(goの分岐原則)
                return 60000
            _ev = _gain + _mill - _burn
            if _ev >= 100:
                return 60000 + _ev * 900                          # 最大〜240000
            elif (active_ready_tusk and me.deckCount >= 24
                    and me.deckCount - opponent.deckCount >= 8):
                # 山差リードが探検家コスト(自山6)を吸収できる時だけ加速
                score = 200000
            elif (me.deckCount >= 34
                    and me.deckCount - opponent.deckCount >= 12):
                # 序盤の大リード時のみ、リソース回収として許容
                score = 15000
            elif _gain >= 60:
                # go教示(2026-08-01): イダイナキバ攻撃可能待ちで無期限に温存しない。
                # ミル加点(_mill)が無くても掘る価値(_gain)自体が十分ならその場で使う
                # (実戦2026-08-01 ep89136669: T7に引いてからT11まで4ターン塩漬け事故)
                score = 20000 + int(_gain * 700)
            else:
                score = -10000
        else:
            score = -10000
    elif card_id == COLRESS_TENACITY:
        current_stadium = state.stadium[0].id if state.stadium else None
        need_zone = current_stadium != NEUTRAL_CENTER and count_in_hand(me, NEUTRAL_CENTER) == 0
        ex_threat = opponent_ex_pressure(opponent) or opponent_shows_ex_evolution_line(opponent)
        if not state.supporterPlayed and ex_threat and need_zone:
            # Search the one-of Zone before an evolved ex starts taking prizes.
            score = 340000
        elif not state.supporterPlayed and me.deckCount >= 8:
            score = 9000
    elif card_id == BUDDY_BUDDY_POFFIN and "bench_body" in current_needs(me, opponent):
        # 実測: 対アグロ/フーディンは場4体で勝率+46〜57pt。ベンチ厚を最優先展開
        score = 130000
    elif card_id == BUDDY_BUDDY_POFFIN:
        if can_bench_more(me):
            wall_count = count_in_field(me, DWEBBLE) + count_in_field(me, CRUSTLE)
            if len(field_pokemon(me)) <= 1 or wall_count < 2:
                score = 94000
            elif count_in_field(me, TATSUGIRI) == 0 and not has_ready_tusk(me):
                score = 36000
            else:
                score = 11000
    elif card_id == POKE_PAD:
        engine_incomplete = count_in_field(me, LUNATONE) == 0 or count_in_field(me, SOLROCK) == 0
        if count_in_field(me, GREAT_TUSK) == 0 or engine_incomplete or urgent_field_rebuild(me, opponent, state):
            score = 92000
        elif wall_mode and count_in_field(me, CRUSTLE) == 0:
            score = 90000
        elif has_in_field(me, DWEBBLE) and count_in_field(me, CRUSTLE) == 0:
            score = 68000
        else:
            score = 18000
    elif card_id == FIGHT_GONG:
        need_tusk = count_in_field(me, GREAT_TUSK) == 0 and count_in_hand(me, GREAT_TUSK) == 0
        need_energy_for_tusk = any(p.id == GREAT_TUSK and attached_energy_count(p) < 2 for p in field_pokemon(me))
        engine_incomplete = count_in_field(me, LUNATONE) == 0 or count_in_field(me, SOLROCK) == 0
        if need_tusk or need_energy_for_tusk or engine_incomplete or urgent_field_rebuild(me, opponent, state):
            score = 90000
        else:
            score = 21000
    elif card_id == ULTRA_BALL:
        # Universal Pokémon search: bridges Great Tusk and Crustle packages.
        if count_in_field(me, GREAT_TUSK) == 0 or (wall_mode and count_in_field(me, CRUSTLE) == 0):
            score = 82000
        elif has_in_field(me, DWEBBLE) and count_in_field(me, CRUSTLE) == 0:
            score = 52000
        else:
            score = 16000
    elif card_id == POKEGEAR_30:
        if not state.supporterPlayed and not has_explorer and active_ready_tusk and me.deckCount >= 7:
            score = 88000
        elif not state.supporterPlayed and not has_explorer and me.deckCount >= 10:
            score = 23000
    elif card_id == ROTO_STICK:
        if not state.supporterPlayed and not has_explorer and active_ready_tusk and me.deckCount >= 4:
            score = 86000
        elif not state.supporterPlayed and not has_explorer and me.deckCount >= 9:
            score = 21000
    elif card_id == BUG_CATCHING_SET:
        if (not state.energyAttached
                and not any(getattr(c, "id", None) in ENERGY_IDS for c in (me.hand or []))
                and any(p is not None and p.id in (CRUSTLE, DWEBBLE, GREAT_TUSK)
                        and attached_energy_count(p) < attack_energy_minimum(p)
                        for p in field_pokemon(me))):
            # 教え23(go指摘 2026-08-10 ep91374725 T8): エネは毎ターン貼る。装着権が
            # 未使用×手札エネ0×未武装の貼り先ありなら、むしとりを攻撃保留バー(18000)の
            # 上に置き「むしとり→装着→攻撃」の順で同じ攻撃をしながら1枚進める
            score = 60000
        elif wall_mode or count_in_field(me, DWEBBLE) == 0 or (has_in_field(me, DWEBBLE) and count_in_field(me, CRUSTLE) == 0):
            score = 42000
        else:
            score = 9000
    elif card_id == GREAT_TUSK:
        if (facing_starmie(opponent) and opponent.deckCount > 8
                and count_in_field(me, GREAT_TUSK) >= 1
                and not urgent_field_rebuild(me, opponent, state)):
            # 教え34改(go裁定 2026-08-12): スターミー対面は2体目以降のキバを
            # 並べない(狙撃の的)。1体目=削りエンジンは通常通り。
            # 例外=最終盤の攻撃準備(相手山8枚以下)と体切れ回避
            score = 4000 if can_bench_more(me) else 0
        elif can_bench_more(me) and count_in_field(me, GREAT_TUSK) < 2:
            score = 95000
        elif can_bench_more(me) and urgent_field_rebuild(me, opponent, state):
            score = 60000
    elif card_id == MEGA_HERACROSS_EX:
        if can_bench_more(me) and facing_lucario_strong(opponent) and count_in_field(me, MEGA_HERACROSS_EX) == 0 and len(field_pokemon(me)) >= 3:
            score = 64000
    elif card_id == KORAIDON_EX:
        if can_bench_more(me) and facing_lucario_strong(opponent) and count_in_field(me, KORAIDON_EX) == 0 and len(field_pokemon(me)) >= 3:
            score = 54000
    elif card_id == TERRAKION:
        if can_bench_more(me) and facing_lucario_strong(opponent) and count_in_field(me, TERRAKION) == 0 and len(field_pokemon(me)) >= 2:
            score = 52000
    elif card_id == MEGA_HAWLUCHA_EX:
        if can_bench_more(me) and facing_lucario_strong(opponent) and count_in_field(me, MEGA_HAWLUCHA_EX) == 0 and len(field_pokemon(me)) >= 3:
            score = 56000
    elif card_id == DWEBBLE:
        _line_n = count_in_field(me, DWEBBLE) + count_in_field(me, CRUSTLE)
        if can_bench_more(me) and _line_n < 2:
            score = 60000 if wall_mode else 36000
        elif can_bench_more(me) and _line_n < 4 and opponent_chips_board(opponent):
            # 教えB(2026-07-31解剖): 狙撃・特性削り対面は盤面が構造的に消耗する。
            # 場切れ負け(短期83敗の95%)対策として線を4体まで補充し続ける
            score = 40000
    elif card_id == CRUSTLE:
        # Normally handled by EVOLVE option, but keep playable/evolution choices high where applicable.
        score = 34000 if has_in_field(me, DWEBBLE) else -1000
    elif card_id == DURANT_EX:
        if can_bench_more(me) and opponent.deckCount > 0:
            # Guaranteed 1-card mill on play. Keep high, but lower than boosted Explorer.
            score = 70000 if count_in_field(me, DURANT_EX) == 0 else 42000
            if opponent_can_attack_soon(opponent):
                score -= 6000
    elif card_id == TATSUGIRI:
        if can_bench_more(me) and not state.supporterPlayed and not has_explorer and count_in_field(me, TATSUGIRI) == 0:
            score = 28000
    elif card_id == FLUTTER_MANE:
        if can_bench_more(me) and count_in_field(me, FLUTTER_MANE) == 0:
            score = 12000
    elif card_id == CORNERSTONE_OGERPON:
        if can_bench_more(me) and count_in_field(me, CORNERSTONE_OGERPON) == 0:
            score = 15000
    elif card_id == NEUTRAL_CENTER:
        current_stadium = state.stadium[0].id if state.stadium else None
        _own_stadium = bool(state.stadium) and getattr(state.stadium[0], "playerIndex", None) == state.yourIndex
        if not state.stadiumPlayed and current_stadium != NEUTRAL_CENTER:
            # go教示(2026-08-02 ep89515014): NCの最良タイミングは「次のターンexに
            # 攻撃される」直前。早貼りは相手が剥がし札を引く時間を与えるだけ
            # (1枚差しACE SPEC=貼り直し不可)。「攻撃されそう」全般ではなく
            # 「ex/メガが武装済み(あと1エネ以内で攻撃圏)」だけを引き金にする
            _opp_ex_soon = any(
                is_armed_ex_threat(pk) for pk in field_pokemon(opponent))
            if _opp_ex_soon:
                # go裁定(2026-08-03): ex武装済みなら自分のスタジアム上書きでも貼る
                # (コロシアムのベンチ保護 < バレット級の本体無効)。自壊分だけ少し減点
                score = 180000 if _own_stadium else 330000
            elif _own_stadium:
                # 脅威が無いのに自分の保護スタジアムを自壊しない(ep89649890)
                score = -5000
            elif (current_stadium is not None and current_stadium != LIVELY_STADIUM
                    and opponent.deckCount <= 12):
                score = 24000   # 終盤の相手スタジアム上書きのみ例外的に許容
            else:
                score = -2000   # それまで温存
    elif card_id == BATTLE_CAGE:
        current_stadium = state.stadium[0].id if state.stadium else None
        if not state.stadiumPlayed and current_stadium not in (BATTLE_CAGE, NEUTRAL_CENTER):
            # ベンチばら撒き対面の検知(go読み 2026-07-29: マリィ悪・ドラパルトに効くはず):
            # ドラパルト線(ファントムダイブ) / ユキメノコ線(特性ばら撒き=武装イワパレスを
            # 2発圏に押し込む元凶) / マシマシラ(ダメカン移動)。すべて「ワザの効果・特性による
            # ベンチへのダメカン配置」なのでバトルコロシアム(Battle Cage)で丸ごと無効化できる
            # go教示(2026-08-07 ep90364695): スタジアムは「効果が使える時」に貼る。
            # 指紋だけでT1に貼る→効果ゼロのまま張り替えられて1枚損。
            # 「飛ばし手が動ける状態」(マシマシラ=エネ付き/ユキメノコ系=進化済み/
            # ドラパルト=進化済み)かつ守るベンチがいる時だけ高得点
            _armed_sniper = False
            for _pk in field_pokemon(opponent):
                if _pk is None:
                    continue
                # 教え62(go指摘 2026-08-15): 特性チップは自動導出集合で検知。
                # マシマシラ(112)だけは悪エネ装着が起動条件なのでエネ付きで武装扱い
                if _pk.id in ABILITY_CHIP_IDS:
                    if _pk.id == 112:
                        if attached_energy_count(_pk) >= 1:
                            _armed_sniper = True
                    else:
                        _armed_sniper = True
                if _pk.id in (121, 120):
                    _armed_sniper = True
                # ワザ系(データ網羅68種: シャドーバレット等): あと1エネ以内で狙撃圏
                _sn = BENCH_SNIPE_ATTACK.get(_pk.id)
                if _sn is not None and attached_energy_count(_pk) + 1 >= _sn:
                    _armed_sniper = True
            _my_bench_n = len([p for p in (me.bench or []) if p is not None])
            if _armed_sniper and _my_bench_n >= 1:
                score = 150000
            elif current_stadium is not None:
                # 相手スタジアムの上書き=妨害になるタイミング
                score = 52000
            else:
                # go教示(2026-07-30): スタジアムは適当に貼らない。
                # 「貼ることで相手の妨害になるターン」まで温存(特にコロシアム)
                score = 3000
    elif card_id == FLUTE:
        if opponent.benchMax - len(opponent.bench) > 0 and opponent.deckCount >= 5:
            score = 21000
    elif card_id == HAND_TRIMMER:
        their_loss = max(0, opponent.handCount - 5)
        our_loss = max(0, me.handCount - 5)
        if their_loss > our_loss:
            score = 16000 + 1600 * (their_loss - our_loss)
    elif card_id == SWITCH:
        active_id = active.id if active is not None else None
        # go教示(2026-07-30 ep88847578): スボミーはバトル場でいい。むずむずかふん
        # (アイテムロック)は強く、攻撃できるキバが準備できていないなら入れ替え不要
        if active_id == BUDEW and not ready_tusk_on_bench(me):
            return -5000
        # go指摘(2026-07-29 ep88779353): ロックイン・イワパレスは相手のexワザの
        # ダメージを全て防ぐ無敵の壁。相手のアタッカーがex主体なら、前から
        # 動かすこと自体が損(メガルカリオの前から退避していた誤り)
        _opp_ex_only = False
        _atk_pokes = [pk for pk in field_pokemon(opponent)
                      if any((getattr(ATTACK_TABLE.get(aid), "damage", 0) or 0) >= 60
                             for aid in getattr(CARD_TABLE.get(pk.id), "attacks", []) or [])]
        if _atk_pokes and all(is_ex_pokemon(pk) for pk in _atk_pokes):
            _opp_ex_only = True
        if active_id == CRUSTLE and _opp_ex_only:
            score = -8000
        elif wall_mode and active_id != CRUSTLE and any(p.id == CRUSTLE for p in me.bench):
            score = 400000
        elif active_id != GREAT_TUSK and ready_tusk_on_bench(me):
            score = 210000
        elif (lambda _c=closing_plan(me, opponent, state): _c is not None and _c["need"] == 0
                and (active is None or getattr(active, "serial", None) != _c["attacker_serial"]))():
            # 取り切りモード実行ターン: 武装済みアタッカーを前へ
            score = 300000
        elif (active is not None
                and any(p is not None and p.id == CRUSTLE
                        and scissors_ready(p, me, opponent)
                        for p in (me.bench or []))
                and not any(can_pay_attack(active, _aid)
                            for _aid in getattr(CARD_TABLE.get(active.id), "attacks", []) or [])
                and (attached_energy_count(active)
                     + (1 if (not state.energyAttached
                              and any(getattr(c2, "id", None) in ENERGY_IDS
                                      for c2 in (me.hand or []))) else 0))
                    < attack_energy_minimum(active)):
            # 教え8b(2026-08-08 ep90718153解剖): ベンチに武装済みイワパレス(はさみ即撃ち可)
            # がいるのに、このターン中に武装できない前を立たせ続けない。入れ替えて即攻撃。
            # 実測: 引いた入れ替えを14ターン握ったまま負けた(前E0→武装T8/ベンチE2凍結T11)。
            # 適用範囲: 前が「エネ装着を足しても今ターン攻撃不能」の時のみ。
            # 既存ガード(ex一辺倒-8000/スボミーロック-5000)はelif順で先に発火し不可侵。
            score = 190000
        elif ascension_line_ok(me):
            # go教示(2026-08-04 ep89732961): 攻撃できないバトル場は入れ替えて
            # エネ付きいしずまいを前へ→アセンションで山からイワパレスに進化。
            # 手札にイワパレスが無くても線が立つ(その後リーリエで手札補充)
            score = 130000
        elif (budew_lock_line_ok(me, opponent, state)
                and any(p is not None and p.id == BUDEW for p in (me.bench or []))):
            # go教示(2026-08-07): 後攻T2 スボミーを前へ→1エネ→むずがゆかふんでグッズロック
            score = 135000
    elif card_id == JUMBO_ICE_CREAM:
        # 教え40移植(go裁定 2026-08-13完全版、v29.5からv29.14aへ 2026-08-14):
        # 旧条件(前限定×エネ3+)はキバに一生使えず、マシマシラ輸送ダメカンも救えない。
        # 新条件=「価値ある体(イワパレス線/キバ or エネ持ち)にダメージ40以上」。
        # go裁定(2026-08-14): ジャンボの本懐は「イワパレスを1ターン延命させる」こと
        if active is not None and damage_on(active) >= 40 and attached_energy_count(active) >= 1:
            score = 350000 + damage_on(active)
        elif any(p is not None and damage_on(p) >= 40
                 and (p.id in (CRUSTLE, GREAT_TUSK) or attached_energy_count(p) >= 1)
                 for p in field_pokemon(me)):
            score = 60000
    elif card_id == ENHANCED_HAMMER:
        if opponent_has_special_energy(opponent):
            score = 26000
    elif card_id == ENERGY_LASSO:
        if opponent.handCount >= 6 and opponent_can_attack_soon(opponent):
            score = 11000
    elif card_id == BOSS_ORDERS:
        _nc_up_yz = bool(state.stadium) and state.stadium[0].id == NEUTRAL_CENTER
        if (not state.supporterPlayed
                and lethal_avoid_boss_target(me, opponent, nc_up=_nc_up_yz) is not None):
            # ゆら枝①修正版(2026-08-17): 致死回避ボス
            return 460000 if len(field_pokemon(me)) <= 2 else 185000
        if (not state.supporterPlayed and _ala_early_defense(me, opponent, state.turn)
                and any(p is not None and attached_energy_count(p) == 0
                        and not getattr(CARD_TABLE.get(p.id), "stage1", False)
                        and not getattr(CARD_TABLE.get(p.id), "stage2", False)
                        for p in (opponent.bench or []))):
            # 教え14③(go設計 2026-08-09): エネなしのたね(ケーシィ等)をボスで前へ。
            # エネが無ければ攻撃できない=1ターンの時間稼ぎ+アメ進化してもエネ不足。
            # 「序盤の足止めボス禁止」の例外(禁止の由来は削り対面の浪費。こちらは
            # 進化ex対面で前のキバがKO圏に入る防御局面なので条件が異なる)
            return 60000
        _chip_on_bench = any(p.id in (104, 860, 112) for p in (opponent.bench or []) if p)
        _crustle_ready = any(p.id == CRUSTLE and scissors_ready(p, me, opponent)
                             for p in field_pokemon(me))
        if (not state.supporterPlayed and _chip_on_bench and _crustle_ready
                and opponent_chips_board(opponent)):
            # go教示(2026-07-31): マリィ戦の要諦=ユキメノコ/ユキワラシ/マシマシラを
            # ボスで呼んでイワパレスで倒す(全員はさみ120でワンパン)。
            # 削りエンジンを根本から抜く一手はロックより価値が高い
            score = 130000
        elif (
            not state.supporterPlayed
            and facing_passive_wall(opponent)
            and not ko_mode
            and not (has_in_field(me, SOLROCK) and any(p.id == DWEBBLE for p in opponent.bench))
        ):
            # 対受動壁: 縛る価値のある的がない限りサポート枠を渡さない
            # …だが go教示(2026-08-04 ep89726241): 単イワパレスのような
            # 「非exの単騎アタッカーが殴り続ける」対面は例外。武装済みの前を
            # ボスで退かし、エネの無い体を縛って攻撃テンポを遅延させないと
            # 150点連打に殴り負ける
            _opp_act = active_pokemon(opponent)
            _opp_armed = _opp_act is not None and any(
                can_pay_attack(_opp_act, _aid)
                and (getattr(ATTACK_TABLE.get(_aid), "damage", 0) or 0) >= 60
                for _aid in getattr(CARD_TABLE.get(_opp_act.id), "attacks", []) or [])
            _lock_tgt = any(
                p is not None and attached_energy_count(p) + 1 < attack_energy_minimum(p)
                for p in (opponent.bench or []))
            if _opp_armed and _lock_tgt:
                score = 88000
            else:
                score = 15000
        elif not state.supporterPlayed and opponent_has_trappable_bench(opponent):
            if active_ready_tusk and count_in_hand(me, EXPLORER_GUIDANCE) > 0:
                score = 120000
            elif opponent.deckCount <= 10 or len(opponent.prize) <= 1:
                score = 390000
            elif opponent_has_ex_or_ex_line_pressure(opponent) and len(opponent.prize) <= 4:
                score = 120000
            else:
                # go原則(2026-08-01): ボスは①とどめ(呼んだ的を今ターン確実にKOできる)
                # ②足止め(呼んだ的が今後もしばらく攻撃できない=相手に立て直しを強制)
                # のどちらかでなければ撃たない。見返りのない交代は無駄うち
                _my_dmg = 0
                _active2 = active_pokemon(me)
                if _active2 is not None and _active2.id == CRUSTLE and scissors_ready(_active2, me, opponent):
                    _my_dmg = 120
                elif _active2 is not None and _active2.id == GREAT_TUSK and can_pay_attack(_active2, GIANT_TUSK):
                    _my_dmg = 160
                def _eff_dmg(p):
                    # 弱点×2+抵抗-30込みの実効打点(go指摘 2026-08-06 / 抵抗は2026-08-12修正)
                    if _active2 is None or _my_dmg == 0:
                        return 0
                    return typed_damage(_my_dmg, _active2.id, p.id)
                _has_ko = any(
                    p is not None and _eff_dmg(p) > 0 and _eff_dmg(p) >= (p.hp - damage_on(p))
                    for p in (opponent.bench or [])
                )
                _has_lock = any(
                    p is not None and attached_energy_count(p) + 1 < attack_energy_minimum(p)
                    for p in (opponent.bench or [])
                )
                _oa = active_pokemon(opponent)
                _oa_armed = _oa is not None and any(
                    can_pay_attack(_oa, _aid)
                    and (getattr(ATTACK_TABLE.get(_aid), "damage", 0) or 0) >= 60
                    for _aid in getattr(CARD_TABLE.get(_oa.id), "attacks", []) or [])
                if not _oa_armed and opponent.deckCount > 12:
                    # go指摘(2026-08-05 ep90072833): 序盤は相手ベンチ全員エネ0で
                    # 「足止め成立」が常時点灯していた。止める価値(=相手の前が
                    # 攻撃圏)が無い足止めはサポート枠の浪費
                    _has_lock = False
                if opponent_chips_board(opponent):
                    # go教示(2026-08-02 ep89478668): マリィ悪/ユキメノコ系の対面では
                    # ボスは希少資源(3枚)で本来の仕事は削り屋の除去(とどめ)。
                    # ユキワラシはいずれユキメノコ化して壁を削る=後でボスの的になるからこそ、
                    # 倒せない今「ただの足止め」に浪費しない
                    _has_lock = False
                score = 50000 if (_has_ko or _has_lock) else -8000
    elif card_id == LISIA_APPEAL:
        if not state.supporterPlayed and opponent_has_trappable_basic_bench(opponent):
            if active_ready_tusk and count_in_hand(me, EXPLORER_GUIDANCE) > 0:
                score = 115000
            elif opponent.deckCount <= 12 or len(opponent.prize) <= 1:
                score = 390000
            elif opponent_has_ex_or_ex_line_pressure(opponent) and len(opponent.prize) <= 4:
                score = 120000
            else:
                score = 52000
    elif card_id == ERI:
        if not state.supporterPlayed and opponent.handCount >= 6 and not active_ready_tusk:
            score = 11000
    elif card_id == XEROSIC_SCHEME:
        if (not state.supporterPlayed and active_ready_tusk and count_in_hand(me, EXPLORER_GUIDANCE) > 0
                and not (facing_alakazam(opponent) and opponent.handCount >= 8)):
            # 教え74(2026-08-17 本番0勝4敗解剖): 対フーディンはハンドパワー=手札×20点。
            # 手札が8枚を超えたら(=160点圏)クセロシキ温存の例外を解除し、
            # 下の手札爆発枝(265000+)に落とす。実測: ep93735761 T13 相手手札19枚(380点)で
            # クセロシキを握ったままリーリエを回して敗北
            score = 60000
        elif not state.supporterPlayed and opponent.handCount >= 8:
            score = 265000 + 2500 * (opponent.handCount - 8)
        elif (not state.supporterPlayed and opponent_special_hazard(opponent)
                and opponent.handCount >= 6):
            # go教示(2026-08-07): エネ破壊対面はクセロシキで改造ハンマーを手札から
            # 落とさせる(枚数戦争: ミスト2+ロック4 > ハンマー4 の消耗を早回し)
            # ※教え29b(実物確認への厳格化)は2026-08-12 go裁定「やりすぎ」で撤回。
            #   多数派(ハンマー3-4積み)への初動価値を優先し指紋発火を維持
            score = 130000
        elif not state.supporterPlayed and facing_passive_wall(opponent) and opponent.handCount >= 6:
            # 補充で肥えた手札を叩き落とす（goの撃ち時）
            score = 120000
        elif (
            not state.supporterPlayed
            and GREAT_TUSK in opponent_visible_ids(opponent)
            and opponent.handCount >= 6
            and not active_ready_tusk
        ):
            # LOミラー: 相手のドロー無しデッキは手札を枯らすと止まる（v13-15実測で有効）
            score = 110000
        elif not state.supporterPlayed and opponent.handCount >= 6:
            # 修理(go指摘 2026-08-09 ep91205484): 手札4枚に撃つと捨て1枚(相手選択)で
            # 価値ゼロなのにサポート権+2枚しかない弾を浪費。撃ち時は6枚以上から
            score = 42000
    elif card_id == JUDGE:
        net_mill = 4 - opponent.handCount
        if not state.supporterPlayed and net_mill > 0 and not active_ready_tusk:
            score = 11000 + 1500 * net_mill
    elif card_id == NIGHT_STRETCHER:
        if urgent_field_rebuild(me, opponent, state) and count_pokemon_in_discard(me) > 0 and (
            facing_lucario_strong(opponent) or opponent_ex_pressure(opponent)
        ):
            # 場切れ防止: 攻撃的な相手にのみボディ再生を最優先（ミラーでは温存）
            score = 90000
        elif count_in_discard(me, GREAT_TUSK) and count_in_field(me, GREAT_TUSK) == 0:
            score = 32000
        elif count_energy_in_discard(me) and any(p.id == GREAT_TUSK and attached_energy_count(p) < 2 for p in field_pokemon(me)):
            score = 18000
    elif card_id == SACRED_ASH:
        if count_pokemon_in_discard(me) >= 3 and me.deckCount <= 18:
            score = 13500
    elif card_id == ENERGY_RECYCLER:
        if count_energy_in_discard(me) >= 3 and me.deckCount <= 18:
            score = 13000
    elif card_id == CRUSHING_HAMMER:
        total = sum(attached_energy_count(p) for p in field_pokemon(opponent))
        if total > 0:
            charge = opponent_max_charge(opponent)
            if (opponent_chips_board(opponent)
                    and any(p.id in (112, 649) and attached_energy_count(p) >= 1
                            for p in field_pokemon(opponent))):
                # モルペコ(649)追加(go指摘 2026-08-12 ep92053665): Spiky Wheel=悪エネ×40。
                # 悪エネを折る価値はマシマシラ(輸送)と同格以上
                # go教示(2026-08-07): チップ対面のハンマー=マシマシラの悪エネ割り。
                # 悪エネが無いとアドレナブレイン(ダメカン輸送)が使えない=特性エンジン停止
                score = 96000
            elif facing_passive_wall(opponent) or GREAT_TUSK in opponent_visible_ids(opponent):
                # goの壁戦/ミラー: ハンマーは展開系より先。相手キバのエネを折れば削り自体が止まる
                score = 95000
            elif total <= 2:
                # 教え31(go設計 2026-08-12 ep91979471): 序盤のエネ破壊は全対面で刺さる。
                # 相手の場のエネが2枚以下=希少期は、1枚割る≒攻撃権1回分の強奪。
                # 「クラハン>リーリエ」(go)。3枚以上に増えたら従来の温存ペーシングへ
                score = 85000
            elif opponent_can_attack_soon(opponent):
                score = 82000
            elif charge >= 0.5:
                # 攻撃成立が近い脅威の充電を折る。それ以外は温存（ペーシング）。
                score = 62000
            else:
                score = 8000
    elif card_id == MEGATON_BLOWER:
        opp_tools = sum(1 for p in field_pokemon(opponent) if getattr(p, "tools", None))
        if opponent_has_special_energy(opponent) or opp_tools:
            score = 40000
    elif card_id == ACEROLA_MISCHIEF:
        if not state.supporterPlayed and not has_explorer:
            # 終盤限定(相手サイド残2以下)。ex攻撃から壁を1ターン守り、LO完走の時間を買う
            if opponent_ex_pressure(opponent) and opponent.deckCount <= 20:
                score = 90000
            elif opponent_can_attack_soon(opponent):
                score = 24000
    elif card_id == LILLIE_RESOLVE:
        if not state.supporterPlayed:
            if closing_plan(me, opponent, state) is not None:
                # 取り切りモード: 計画部品(ミスト/ボス/入替)を山に戻すリセット厳禁
                return -5000
            _net_cost = max(0, 7 - len(me.hand or []))
            if _net_cost > 0 and not dig_lifetime_ok(me, opponent, _net_cost, active is not None and active.id == GREAT_TUSK and can_pay_attack(active, LAND_COLLAPSE)):
                return -5000   # 寿命会計: 山が細い時のリーリエ回転は寿命の切り売り
            # 教え61a(go裁定 2026-08-15 ep93188778「この場面はリーリエだな、絶対に」):
            # 攻めプラン承認対面×手札飢餓(≤3)はリーリエ優先。探検家(95000)は山4枚を
            # 捨てて+2枚、リーリエは山を減らさず6枚(サイド6なら8枚)+探検家も山に温存
            if (get_route() == "prize" and _ROUTE_STATE.get("attack_matchup_approved")
                    and me.handCount <= 3):
                return 110000
            board_n = len(field_pokemon(me))
            # go設計(2026-07-29): リーリエ判断は理想盤面からの逆算。
            # 手札がまだ差分を埋められる(usefulness>=2)なら先に使い切る
            if hand_usefulness(me, opponent, state) >= 2 and board_n > 2:
                return 3000
            # (2026-07-30) 終盤のリーリエ判断は詰め探索モード(main側)が
            # 既知の山からの実測勝率で計算する。ルール側の一律封印は撤去(go: 安直)
            # go教示(2026-07-22 レビュー#1): アグロ対面は「次の相手ターンに前が倒される」前提。
            # 展開できない手札を1ターンも抱えない。枚数でなく質(体を足せるか)で判定する。
            if board_n <= 2 and not hand_can_develop(me):
                aggro = opponent_can_attack_soon(opponent) or opponent_ex_pressure(opponent)
                # 教え58(go教示 2026-08-14 ep92996035): 対フーディンの緊急場作りは
                # リーリエから。理由①探検家の温存(ミスト/ロック/草を狙い撃つ本命の
                # 掘り札。リーリエなら手札の探検家も山に帰る=消費しない)
                # ②この対面のNCは死に札(主砲が非ex)=リセットのコストが低い
                if facing_alakazam(opponent) and has_explorer:
                    score = 450000
                else:
                    score = 450000 if aggro else 160000
            elif (count_basics_in_hand(me) == 0
                    and not any(getattr(c2, "id", None) in ENERGY_IDS for c2 in (me.hand or []))
                    and any(p.id in (CRUSTLE, GREAT_TUSK) and attached_energy_count(p) < attack_energy_minimum(p)
                            for p in field_pokemon(me))):
                # go教示(2026-08-07): 「毎ターン貼る」ための手札補充。エネ0の手札は
                # 盤面の武装課題に答えていない→未武装アタッカーがいるなら回して引き直す
                score = 62000 + (15000 if len(me.prize) == 6 else 0)
            elif count_basics_in_hand(me) == 0 and (
                    me.handCount <= 6
                    or not any(getattr(c2, "id", None) in ENERGY_IDS for c2 in (me.hand or []))):
                # go教示(レビュー#5 yanakatsu): リーリエは回転札。手札が体を含まず
                # 課題に答えていないなら、条件を待たずに回す(4枚はそのための枚数)。
                # go正解手(2026-08-07 ep90436075): 体もエネも無いトレーナーズ束は
                # 「枚数に関わらず」回す(手札7枚で枚数キャップに阻まれ0サポ終了した敗着)。
                # サイド6枚ちょうどはリーリエ8ドロー(カード効果)でさらに価値増
                score = 60000 + (15000 if len(me.prize) == 6 else 0)
            elif me.handCount <= 3 and not has_explorer:
                score = 20000
            elif me.deckCount <= 12 and me.handCount >= 7 and not has_explorer:
                score = 12000
            if score >= 20000:
                # 教え8a: 当たり札(入れ替え)が山に確実に生きているならドロー価値増
                score += _lillie_confirmed_outs_bonus(me, state)
    elif card_id == LUNATONE:
        if can_bench_more(me) and count_in_field(me, LUNATONE) == 0:
            # ドローエンジンの起点。盤面最優先で設置する。
            score = 130000
        elif can_bench_more(me) and urgent_field_rebuild(me, opponent, state):
            score = 48000
    elif card_id == SOLROCK:
        if can_bench_more(me) and count_in_field(me, SOLROCK) == 0:
            score = 128000
        elif can_bench_more(me) and (urgent_field_rebuild(me, opponent, state) or (has_in_field(me, LUNATONE) and count_in_field(me, SOLROCK) < 2)):
            score = 46000
    elif card_id == MARACTUS:
        if can_bench_more(me) and count_in_field(me, MARACTUS) == 0:
            score = 44000 if urgent_field_rebuild(me, opponent, state) else 26000
    elif card_id == BUDEW:
        if not any(p is not None for p in (me.bench or [])):
            # go教示(2026-08-07 ep90441584): ベンチ0の体保険はスボミー禁止に勝つ。
            # 「置くな」は余分な体としての話で、体切れ即死リスクの前では保険優先
            score = 90000
        elif budew_lock_line_ok(me, opponent, state):
            # go教示(2026-08-07): 後攻T2アイテムロック線。出して入れ替えで前へ
            score = 85000
        elif opponent_chips_board(opponent):
            score = -6000   # ダメカン飛ばし対面はHP30を置かない(go 2026-08-04)
        elif can_bench_more(me) and count_in_field(me, BUDEW) == 0 and len(opponent.prize) == 6:
            score = 42000 if urgent_field_rebuild(me, opponent, state) else 24000
    elif card_id == DEDENNE:
        if can_bench_more(me) and count_in_field(me, DEDENNE) == 0:
            score = 40000 if urgent_field_rebuild(me, opponent, state) else 20000
    elif card_id == REDEEM_TICKET:
        zone_seen = (
            count_in_hand(me, NEUTRAL_CENTER)
            or count_in_discard(me, NEUTRAL_CENTER)
            or (state.stadium and state.stadium[0].id == NEUTRAL_CENTER)
        )
        if not zone_seen and me.deckCount <= 30:
            score = 9000
    elif card_id == LIVELY_STADIUM:
        current_stadium = state.stadium[0].id if state.stadium else None
        if state.stadiumPlayed or current_stadium in (NEUTRAL_CENTER, LIVELY_STADIUM):
            score = -10000
        elif current_stadium is not None:
            score = 90000
        else:
            score = 22000
    return score


HEAL_CARDS = {1212: 60, 1147: 60, 1211: 0}   # コック=60回復, ジャンボアイス=60回復(概算)
HEAL_DECK_COUNTS = {1212: 4, 1147: 4}         # タンク型定番の積載枚数(保守的な上限)


def race_matchup(opponent) -> bool:
    """教え19(2026-08-10): レース対面指紋 = 非exの殴り壁/単騎タンク
    (回復・マント・スパイク系が見えている or 単騎)。削りレースの継続性が勝敗を決める"""
    try:
        pk = [p for p in field_pokemon(opponent) if p is not None]
        if pk and len(pk) == 1 and not is_ex_pokemon(pk[0]):
            return True
        vis = opponent_visible_ids(opponent)
        if vis & {1212, 1147, 1159}:   # コック/ジャンボ/マント
            return bool(opponent_armed_nonex_beatdown(opponent)) or bool(vis & {345})
        return False
    except Exception:
        return False


def second_tusk_unfueled(me) -> bool:
    """教え19①: 2番手のキバ(ミル継続保険)が2エネ未満か"""
    try:
        gts = sorted((attached_energy_count(p) for p in field_pokemon(me)
                      if p is not None and p.id == GREAT_TUSK), reverse=True)
        return len(gts) >= 2 and gts[1] < 2
    except Exception:
        return False


def opponent_heal_stock(opponent) -> int:
    """教え18(2026-08-10 単騎タンク経済戦): 相手の回復在庫の残量(回復量換算の上限)。
    捨て札から使用済みを差し引く(サイド落ち台帳と同じ subtraction 原理の簡易版)。
    単騎相手はチェレン(体を手札に戻す)が使えないため、コック+ジャンボだけ数えれば足りる"""
    try:
        used = 0
        remain = 0
        disc = [getattr(c, "id", None) for c in (opponent.discard or [])]
        for cid, heal in HEAL_CARDS.items():
            if heal <= 0:
                continue
            n_used = sum(1 for x in disc if x == cid)
            n_left = max(0, HEAL_DECK_COUNTS.get(cid, 0) - n_used)
            remain += n_left * heal
        return remain
    except Exception:
        return 480


def solo_tank_effective_hp(opponent) -> int:
    """教え18: 単騎タンクの実効HP = 現在HP + 残り回復総量。
    「あと何発で削り切れるか」のレース計算に使う"""
    tgt = None
    try:
        pk = [p for p in field_pokemon(opponent) if p is not None]
        if len(pk) == 1:
            tgt = pk[0]
    except Exception:
        pass
    if tgt is None:
        return 9999
    return tgt.hp + opponent_heal_stock(opponent)


def solo_oneshot_target(opponent):
    """教え16v2(2026-08-09): 相手が非ex単騎(ベンチ0)かつギガントタスク160で一撃圏内なら
    その1体を返す。1KO=ベンチ切れ即勝ちなので、キバ4エネ完成が最優先の勝ち筋になる。
    実測: pixiux型攻撃タンク(素150)に5-10% — 教え15の反撃武装(175000)が狩り弾込め
    (170000)からエネを横取りし、一撃必殺のキバが永遠に完成しない優先順位の逆転が原因"""
    try:
        pk = [p for p in field_pokemon(opponent) if p is not None]
        if len(pk) != 1 or is_ex_pokemon(pk[0]):
            return None
        t = _PRIZE_LEDGER.get("turn", 99)
        if t is not None and t < 4 and not (opponent_visible_ids(opponent) & {1212, 1147}):
            return None
        if pk[0].hp <= 160:
            return pk[0]
        return None
    except Exception:
        return None


def tusk_mill_ready(pokemon) -> bool:
    """教え17拡張(go裁定 2026-08-10): ラントコラプス(無2)もCG+サイド遅れでコスト1。
    「カウンターゲインが効く状況ならキバのエネは1つでいい」— キバの武装判定にCG割引を反映"""
    try:
        if can_pay_attack(pokemon, LAND_COLLAPSE):
            return True
        return (has_tool(pokemon, COUNTER_GAIN)
                and bool(_ROUTE_STATE.get("behind_prizes"))
                and attached_energy_count(pokemon) >= 1)
    except Exception:
        return can_pay_attack(pokemon, LAND_COLLAPSE)


def scissors_ready(pokemon, me, opponent) -> bool:
    """教え17(go指摘 2026-08-09): はさみの武装判定にカウンターゲイン割引を反映。
    CG装着中かつサイド遅れなら技コスト-1(=エネ2枚+草1で撃てる)。
    旧: can_pay_attackがCGを知らず「E2+CGは未武装」と誤認→3枚目を貼る無駄"""
    try:
        if can_pay_attack(pokemon, SUPERB_SCISSORS):
            return True
        if (has_tool(pokemon, COUNTER_GAIN)
                and len(me.prize) > len(opponent.prize)
                and attached_energy_count(pokemon) >= 2
                and any(getattr(e, "id", None) in GRASS_ENERGY_IDS or getattr(e, "id", None) == MIST_ENERGY
                        for e in (getattr(pokemon, "energyCards", None) or []))):
            return True
        return False
    except Exception:
        return can_pay_attack(pokemon, SUPERB_SCISSORS)


def crustle_energy_need(pokemon, me, opponent) -> int:
    """教え17: イワパレスの必要エネ枚数(CG割引込み)。武装完成/キャップ判定用"""
    try:
        if has_tool(pokemon, COUNTER_GAIN) and len(me.prize) > len(opponent.prize):
            return 2
    except Exception:
        pass
    return 3


def _ala_early_defense(me, opponent, turn=None) -> bool:
    """教え14(go設計 2026-08-09 ep91280773): 対フーディン序盤の防御形。
    相手手札のアメ+フーディンで前のキバが飛ぶ前提で受けを作る。
    発火条件: フーディン指紋 × 序盤(T<=4) × 前がキバ。
    turn未指定時はサイド落ち台帳が追跡しているturnを使う(attach経路はstateを持たないため)。"""
    try:
        if not facing_alakazam(opponent):
            return False
        t = turn if turn is not None else _PRIZE_LEDGER.get("turn", 99)
        if t is None or t > 4:
            return False
        act = active_pokemon(me)
        return act is not None and act.id == GREAT_TUSK
    except Exception:
        return False


def _front_gt_doomed(me, opponent) -> bool:
    """教え12(go承認の解剖 2026-08-09 ep91203698): 前のキバが相手の前の
    今払えるワザ(弱点込み表記ダメージ)でKO圏内か。保守判定(コイン/狙撃は数えない)。"""
    try:
        act = active_pokemon(me)
        opp_act = active_pokemon(opponent)
        if act is None or act.id != GREAT_TUSK or opp_act is None:
            return False
        if opponent.asleep or opponent.paralyzed:
            return False
        _def = CARD_TABLE.get(act.id)
        best = 0
        for _aid in getattr(CARD_TABLE.get(opp_act.id), "attacks", []) or []:
            if not can_pay_attack(opp_act, _aid):
                continue
            _atk = ATTACK_TABLE.get(_aid)
            # 2026-08-12修正: 旧コードは攻撃側タイプをATTACK_TABLEから読んでいたが
            # その属性は存在せず弱点×2が一度も発動していなかった。抵抗力も併せて反映
            dmg = typed_damage(getattr(_atk, "damage", 0) or 0, opp_act.id, act.id)
            best = max(best, dmg)
        return best >= act.hp
    except Exception:
        return False


def attach_score(card_id: int, target: Pokemon | None, in_play_area, me, opponent, wall_mode: bool, ko_mode: bool) -> int:
    # 教え38(go裁定 2026-08-12 ep92055560): 装着→攻撃の2手合成とどめ。
    # 前のキバにカウンターゲインを付ければギガントタスク(CG割引で3エネ)が今ターン
    # 撃てて、かつ相手の前をKOできるなら、CG装着はとどめ級(292000)。
    # 実戦: CG2枚を握ったままLand Collapseを撃ち、残HP110の雪男に160を撃ち損ねた敗着。
    # 条件は狭く: 対象=前のキバ×CG×サイド遅れ×闘エネ2枚以上×КОライン成立、のみ
    if (card_id == COUNTER_GAIN and in_play_area == AreaType.ACTIVE
            and target is not None and target.id == GREAT_TUSK
            and not has_tool(target, COUNTER_GAIN)
            and len(me.prize or []) > len(opponent.prize or [])):
        try:
            _oa38 = active_pokemon(opponent)
            _fight38 = sum(1 for e in (getattr(target, "energyCards", None) or [])
                           if getattr(e, "id", None) in (BASIC_FIGHTING_ENERGY, ROCK_FIGHTING_ENERGY))
            if (_oa38 is not None and _fight38 >= 2
                    and attached_energy_count(target) >= 3):   # CGで4→3
                _od38 = CARD_TABLE.get(_oa38.id)
                _hp38 = getattr(_od38, "hp", None) or 999
                _hp38 = max(_hp38, getattr(_oa38, "maxHp", 0) or 0)
                _d38 = typed_damage(160, target.id, _oa38.id)
                if _d38 + damage_on(_oa38) >= _hp38 - 0:
                    if _d38 >= (_hp38 - damage_on(_oa38)):
                        return 292000
        except Exception:
            pass
    if (card_id in ENERGY_IDS and in_play_area == AreaType.ACTIVE and target is not None
            and target.id in (DWEBBLE, CRUSTLE)):
        # ゆら枝②修正版(2026-08-17 ep93559312 T1): 前が次の相手番に確定KOされ、
        # この装着でも今ターン攻撃が立たない(または先攻T1で攻撃自体が不能)、
        # かつ後ろに同系の育成先が居るなら捨て駒への貼り。エネは後ろへ保存
        _oa_yz = active_pokemon(opponent)
        _enables_yz = attached_energy_count(target) + 1 >= attack_energy_minimum(target)
        _t1_yz = _ROUTE_STATE.get("_turn", 99) == 1
        if (_oa_yz is not None
                and next_turn_best_damage(_oa_yz, target, opponent,
                                          nc_up=_ROUTE_STATE.get("_nc_up", False))
                    >= (getattr(target, "hp", 0) or 0) > 0
                and (not _enables_yz or _t1_yz)
                and any(p is not None and p.id in (DWEBBLE, CRUSTLE)
                        for p in (me.bench or []))):
            return 900
    if (in_play_area == AreaType.ACTIVE and target is not None
            and target.id == GREAT_TUSK and card_id in ENERGY_IDS
            and any(p is not None and p.id == GREAT_TUSK for p in (me.bench or []))
            and _front_gt_doomed(me, opponent)):
        # 教え12: 弾込めの貼り先選択。前のキバがKO圏内なら、エネはベンチの
        # 無事なキバへ(実測 ep91203698: HP70の前キバに3枚目→4枚目を待たずKOで
        # エネ3枚と狩りプランが消失、1枚差のレース負けの敗着)。
        # ベンチにキバが居ない時は従来どおり(最後の砲台に貼らない事故を避ける)
        return 3000
    if (in_play_area == AreaType.ACTIVE and target is not None
            and target.id == GREAT_TUSK and card_id in ENERGY_IDS
            and _ala_early_defense(me, opponent)
            and (any(p is not None and p.id == GREAT_TUSK for p in (me.bench or []))
                 or count_in_hand(me, GREAT_TUSK) > 0
                 or count_in_hand(me, POKE_PAD) > 0)):
        # 教え14②(go設計 2026-08-09): 対フーディン序盤、前のキバは「アメ+フーディンで
        # 飛ぶ」前提。エネはベンチのキバへ(ベンチに居なければ先にパッド/キバで用意できる
        # 時のみ前を我慢する。用意する手段が無いなら従来どおり=最後の砲台に貼らない事故回避)
        return 4000
    if (target is not None and card_id in ENERGY_IDS
            and race_matchup(opponent) and second_tusk_unfueled(me)):
        # 教え19①(2026-08-10 ep91302456: 終盤5空白ターン=5枚のミル差で負け):
        # レース対面の装着は「次に前へ出るキバを2エネに」が最優先。
        # 供給ライン(1装着/T=攻撃手1体/2T)を破断させる貼り先を全部止める
        if (target.id == GREAT_TUSK and attached_energy_count(target) < 2
                and not tusk_mill_ready(target)):
            # go裁定①の完成第3弾(2026-08-12 ep92056548): CG+遅れ+E1=完成品には
            # 貼らない(レース枝も生カウントでなくCG割引込みのmill_readyで判定)
            # §12修正(2026-08-17 ep93610466): 対フーディンの2枚目はミスト/ロック闘を
            # 草より優先(完成と同時にハンドパワー完全免疫。この枝がエネ種を区別せず
            # 200000均一だったのが草貼りの真犯人)
            if (card_id in (MIST_ENERGY, ROCK_FIGHTING_ENERGY)
                    and facing_alakazam(opponent) and attached_energy_count(target) >= 1):
                return 205000
            return 200000
        if not (target.id == GREAT_TUSK and attached_energy_count(target) < 2
                and not tusk_mill_ready(target)):
            return 3500
    if (target is not None and target.id == GREAT_TUSK
            and solo_oneshot_target(opponent) is not None
            and attached_energy_count(target) < 4
            and not (in_play_area == AreaType.ACTIVE and _front_gt_doomed(me, opponent)
                     and any(p is not None and p.id == GREAT_TUSK for p in (me.bench or [])))):
        # 教え16v2: 単騎×一撃圏はキバ4エネ完成が勝ち筋そのもの。ロック闘は190000で
        # 反撃武装(175000)より上、他エネも色構成(教え13)を守りつつ168000
        _f16 = sum(1 for e in (getattr(target, "energyCards", None) or [])
                   if getattr(e, "id", None) == ROCK_FIGHTING_ENERGY)
        if card_id == ROCK_FIGHTING_ENERGY:
            return 190000
        if (2 - _f16) <= (4 - (attached_energy_count(target) + 1)):
            return 168000
        return -5000
    if (target is not None and target.id == GREAT_TUSK and card_id in ENERGY_IDS
            and card_id != ROCK_FIGHTING_ENERGY and giant_tusk_plan(me, opponent)):
        # 教え13(go指摘 2026-08-09 ep91216215): ギガントタスクのコストは闘2+無2。
        # 「4枚付いているのに闘1で撃てない」事故の根治: この装着の後で
        # 残り枠(4-n-1)が不足闘数(2-闘枚数)を下回るなら、その枠は闘専用として温存
        _f13 = sum(1 for e in (getattr(target, "energyCards", None) or [])
                   if getattr(e, "id", None) == ROCK_FIGHTING_ENERGY)
        _n13 = attached_energy_count(target)
        if (2 - _f13) > (4 - (_n13 + 1)):
            return -5000
    if (target is not None and target.id == GREAT_TUSK and get_route() == "prize"
            and not giant_tusk_plan(me, opponent)):
        # go裁定(2026-08-07): 攻めルートのキバ「エネ」装着は原則後回しだがゼロではない。
        # エネ限定(go指摘 2026-08-07 ep90443790: カウンターゲインが素通りでキバに
        # 貼られた事故の根治。道具は下のカード別評価で判定する)
        if card_id in ENERGY_IDS:
            if crustle_unfavorable_matchup(opponent):
                # go教示(2026-08-07): イワパレスが苦手な相手が出ている時はキバが攻撃機。
                # エネはイワパレスよりキバへ
                return 125000
            if opponent_chips_board(opponent) and any(
                    p.id in (CRUSTLE, DWEBBLE) for p in field_pokemon(me)):
                # go教示(2026-08-07): チップ対面はエネをイワパレスラインにしか貼らない。
                # キバへの無駄貼りは1ターン1枚の装着権の浪費(武装が間に合わない主因)。
                # 適用範囲: イワパレス線が場に生きている時だけ。線が全滅したらキバが
                # 最後の勝ち筋なので禁止しない(素点マイナス=探索から除外される仕様のため、
                # 無条件禁止は「キバしか居ない終盤に誰にも貼れない」事故になる)
                return -3000
            return 8000
    if target is not None and target.id == CRUSTLE and attached_energy_count(target) >= crustle_energy_need(target, me, opponent):
        # go指摘(2026-08-07 ep90364695): はさみは3エネで完成。4枚目以降は浪費
        # (実戦でイワパレスに6枚→手札のエネ枯れ→緊急取得の無限ループ)
        return -4000
    _cp = closing_plan(me, opponent, None)
    if _cp is not None and target is not None:
        if (getattr(target, "serial", None) == _cp["attacker_serial"] and _cp["need"] > 0
                and card_id in ENERGY_IDS):
            return 400000   # 取り切りモード: 計画アタッカーの弾込め(エネ)が全てに優先
    if target is not None and target.id == BUDEW:
        # go指摘(2026-08-05 ep90072833): スボミーは使い捨ての先頭。エネ(キバの燃料)を
        # 載せたら体ごと失われる。「とりあえず貼る」の既定値で流れるのを禁止
        return -3000
    if target is None:
        return -10000
    if card_id == COUNTER_GAIN:
        if has_tool(target, COUNTER_GAIN):
            return -5000
        if len(me.prize) <= len(opponent.prize):
            # go指摘(2026-07-22): サイドで負けていなければ効果ゼロの置物。貼らない
            return -5000
        # go指摘(2026-08-01): 技コスト軽減は今のプランのアタッカーに寄せる。
        # 削り(deck_out)はいだいなきばのLand Collapse連打、攻め(prize)はイワパレスのはさみ。
        # go指摘(2026-08-02 ep89476451 T21): ただし既に攻撃可能な個体への貼りは無駄。
        # 「まだ立っていない」個体に貼って起動を1エネ分早めるのがこの道具の仕事
        # go教示(2026-08-07): カウンターゲインをうまく使う。ここに到達=サイド負け中
        # (上のガードで五分以下は-5000済み)なので効果が生きている。次のアタッカーの
        # 起動短縮(3T→2T)は最優先級(チップ対面解剖: 武装が撃墜に間に合わないのが主因)
        if get_route() == "prize":
            if target.id == CRUSTLE and not scissors_ready(target, me, opponent):
                return 90000
            return -5000
        else:
            if target.id == GREAT_TUSK and not can_pay_attack(target, LAND_COLLAPSE):
                return 90000
            return -5000
    active = active_pokemon(me)
    if card_id in ENERGY_IDS:
        # 教え44改(go裁定 2026-08-14): 装着前にワザの色要件を検算。この1枚で
        # どのワザのコストも満たせなくなる貼り方は全経路で禁止(汎用入り口ガード)
        if target is not None and not attach_keeps_cost_payable(target, card_id):
            return -8000
        score = 0
        if card_id == MIST_ENERGY and count_in_hand(me, BASIC_GRASS_ENERGY) > 0:
            # go教示(2026-08-02確定版): 0エネのキバには草から(ハンマー耐性)。
            # ミストは「次のターン、草付きキバへの2枚目」= JIT例外で自然に通り、
            # 貼った瞬間にLand Collapse完成+以後は効果の鎧(ミスト+32000補正が担保)。
            # この並びで「ミスト付きキバを複数早く」(対フーディン勝利条件)が成立する
            # 教え44②例外(go裁定 2026-08-14): 攻めプランのイワパレス線で草1枚確保済み
            # ×効果ワザ持ちの相手が見えている時は、完成前でもミストを通す(鎧の前倒し)
            _mist44_ok = (get_route() == "prize" and target is not None
                          and target.id in (CRUSTLE, DWEBBLE)
                          and any(getattr(e, "id", None) in GRASS_ENERGY_IDS
                                  for e in (getattr(target, "energyCards", None) or []))
                          and opponent_effect_attacker_visible(opponent))
            _need0 = attack_energy_minimum(target)
            _n0 = attached_energy_count(target)
            if not (_need0 and _n0 + 1 >= _need0) and not _mist44_ok:
                return -2000
        if card_id == MIST_ENERGY and target.id != GREAT_TUSK and opponent_special_hazard(opponent):
            # ミスト温存(go教訓 2026-07-28): ハンマー対面のミストは「貼った瞬間に仕事をする」時だけ。
            # 置き貼りは剥がされてイワパレスの3エネが永遠に揃わない(T4/T6置き→敗戦の実例)。
            # キバは既存のJITゲート(下)がgo調整済みなので対象外。
            _need = attack_energy_minimum(target)
            _n = attached_energy_count(target)
            if not (_need and _n + 1 >= _need):
                if count_in_hand(me, BASIC_GRASS_ENERGY) > 0:
                    return -2000   # 基本エネを先に(ハンマーで取られない)
                return 2500        # 手札に温存 > エネ装着テンポ
        if get_route() == "prize" and not ko_mode:
            # 攻めの本(go 2026-07-28): プランがprizeならエネはイワパレス線へ。
            # キバには「一切」張らない(張り先がなければ手札に温存=goの実プレイ)
            if target.id in (CRUSTLE, DWEBBLE):
                _grass44 = sum(1 for e in (getattr(target, "energyCards", None) or [])
                               if getattr(e, "id", None) in GRASS_ENERGY_IDS)
                # 教え44①は汎用版attach_keeps_cost_payable(入り口ガード)に統合済み
                # 教え44②(go裁定 2026-08-14): 効果ワザ持ちの相手が見えている対面は、
                # 草1枚確保済みのイワパレス線へのミストを草より優先(鎧の価値が実在する)。
                # ロック闘は草タイプに保護が乗らないため対象外(従来どおりキバ用)
                _mist44 = 3000 if (card_id == MIST_ENERGY and _grass44 >= 1
                                   and opponent_effect_attacker_visible(opponent)) else 0
                # 教え32(go教示 2026-08-12 ep92042351): ロック闘は闘タイプに貼らないと
                # ただの無色1個(効果はキバ専用)、ミストは2枚の希少品。草が手札にあるなら
                # 草から(8/9ミスト同点降格と同型。同点×手札順のロック闘浪費の根治)
                _scarce = 4000 if (card_id in (MIST_ENERGY, ROCK_FIGHTING_ENERGY)
                                   and count_in_hand(me, BASIC_GRASS_ENERGY) > 0
                                   and not _mist44) else 0
                return (175000 if attached_energy_count(target) < 3 else 30000) + _mist44 - _scarce
            if target.id == GREAT_TUSK:
                return -5000
        if get_route() == "deck_out" and not ko_mode:
            # go教示(レビュー#2): 削りルートを選んだらエネ配分もルートに従属。
            # キバ2エネ成立が最優先。キバ未成立の間、壁へのエネ投資は後回し。
            if (giant_tusk_plan(me, opponent) and card_id == ROCK_FIGHTING_ENERGY
                    and target.id == GREAT_TUSK and attached_energy_count(target) < 4):
                return 170000   # 狩りプラン: ギガントタスクの弾込め
            if card_id == ROCK_FIGHTING_ENERGY and target.id in (CRUSTLE, DWEBBLE):
                return 2500     # ロック闘は原則キバ用
            # go裁定(2026-08-10): 「CGが効くならキバのエネは1つでいい」を貼る側にも反映。
            # 武装済み判定はtusk_mill_ready(CG+サイド遅れ+エネ1=完成)に統一し、
            # 完成済みキバへの2枚目は貼らない(装着権を他へ回す)
            kiba_unready = any(p.id == GREAT_TUSK and not tusk_mill_ready(p) for p in field_pokemon(me))
            _kiba_armed = sum(1 for p in field_pokemon(me)
                              if p.id == GREAT_TUSK and tusk_mill_ready(p))
            if target.id == GREAT_TUSK and not tusk_mill_ready(target) and attached_energy_count(target) < 2:
                # go教示(2026-08-04 ep89726241): キバ武装はミル本体+保険の2体まで。
                # 修理(go指摘 2026-08-09 ep91284463): 同点タイブレークでミストが草より
                # 先に選ばれる事故。基本エネが手札にあるならミストを1段下げる
                # (ミストは2枚の希少品=ハンマーの的・鎧用途)
                _mist_demote = 4000 if (card_id == MIST_ENERGY
                                        and count_in_hand(me, BASIC_GRASS_ENERGY) > 0) else 0
                # 教え44②拡張(go裁定 2026-08-14): キバ(闘)はロック闘でも鎧が乗る。
                # 効果ワザ持ちの相手が見えていて、キバに既にエネが1枚あり、かつ
                # ハンマー対面でない(温存ルール優先)なら、特殊エネを草より優先
                _shield44 = 3000 if (card_id in (MIST_ENERGY, ROCK_FIGHTING_ENERGY)
                                     and attached_energy_count(target) >= 1
                                     and opponent_effect_attacker_visible(opponent)
                                     and not opponent_special_hazard(opponent)) else 0
                if _shield44:
                    _mist_demote = 0
                return (165000 if _kiba_armed < 2 else 4500) - _mist_demote + _shield44
            if (opponent_armed_nonex_beatdown(opponent) and target.id == CRUSTLE
                    and card_id in GRASS_ENERGY_IDS and attached_energy_count(target) < 3):
                # go教示(2026-08-04): 殴ってくる非ex単騎(単イワパレス等)を放置しない。
                # 教え15(2026-08-09 ep91281682 ガルーラ壁0-6完封の敗因): この140000が
                # キバ再補充165000に毎ターン負けて、イワパレスが30ターン裸だった。
                # キバに貼るのは相手のはさみへの餌の再生産。反撃武装を上に置く
                return 175000
            if kiba_unready and target.id in (CRUSTLE, DWEBBLE):
                return 4000
        if facing_alakazam(opponent) and not ko_mode:
            # goのJIT原則: 適用条件=「相手が剥がし札持ちと判明している対面」(2026-07-23全対面化を
            # 実測63.4%で棄却→ゲート復帰)。剥がしが来ない相手には早張りミスト=無料の保険。
            if target.id == GREAT_TUSK:
                n = attached_energy_count(target)
                if not giant_tusk_plan(me, opponent) and tusk_mill_ready(target):
                    # go裁定①の完成(2026-08-12 ep92038482): CG+サイド遅れ+E1=完成品への
                    # 追い貼りはJIT枝でも禁止(昨日のガードは通常枝のみで素通りしていた)
                    return -5000
                if n >= (4 if giant_tusk_plan(me, opponent) else 2):
                    # 絶対キャップはJIT枝にも適用(go指摘 2026-08-04 ep89726241:
                    # 「n>=1で300000」が上限なしで3枚目/4枚目のミストを通していた。
                    # キャップを覆す独立の穴・第4例)
                    return -5000
                both_in_hand = count_in_hand(me, BASIC_GRASS_ENERGY) > 0 and count_in_hand(me, MIST_ENERGY) > 0
                if card_id == BASIC_GRASS_ENERGY:
                    return 130000 if n == 0 else 15000
                if card_id in (MIST_ENERGY, ROCK_FIGHTING_ENERGY):
                    if n >= 1:
                        # §12修正(2026-08-17 ep93610466): 2枚目=攻撃成立+ハンドパワー完全免疫の
                        # 完成瞬間。ベンチ完成(160000)も新品への基本エネ(130000)より優先する。
                        # 1枚目は従来どおり基本エネ先行(改造ハンマーの的にしない)
                        return 300000 if in_play_area == AreaType.ACTIVE else 160000
                    # go訂正: 「基本エネ先行」は両方持っている時の基本形。
                    # 基本エネを取りに行ける手(むしとりセット)があるならフェッチ優先、
                    # 無ければミストでも張る。毎ターン1回のエネ装着を絶やさないのが最重要。
                    if both_in_hand:
                        return 6000
                    if count_in_hand(me, BUG_CATCHING_SET) > 0:
                        return 12000
                    return 60000
                return 15000
            if target.id in (CRUSTLE, DWEBBLE):
                # 教え29a(go裁定 2026-08-12 ep91973803): キバが場にも手札にも居ない間は
                # イシズマイ1枚目(アセンション起動)を許可。全面禁止は先攻キバ無し初手で
                # 装着権を3ターン捨てる自傷だった(初攻撃T14→1ターン差負けの敗着)
                if (count_in_field(me, GREAT_TUSK) == 0 and count_in_hand(me, GREAT_TUSK) == 0
                        and target.id == DWEBBLE and attached_energy_count(target) == 0):
                    return 52000
                return -3000      # 非ex主体相手に壁へのエネ投資は無駄(教えの本旨は維持)
        if target.id == GREAT_TUSK:
            _cap = 4 if giant_tusk_plan(me, opponent) else 2
            if attached_energy_count(target) >= _cap or (
                    not giant_tusk_plan(me, opponent) and tusk_mill_ready(target)):
                # go裁定(2026-08-10): CG+サイド遅れ+エネ1のキバは完成品。2枚目も絶対禁止側
                # (狩りプラン中は例外=ギガントタスクの4エネ弾込めを塞がない)
                # go再三指摘(2026-08-02 ep89516671確定): ミルは2エネで完成、
                # ギガントタスクは闘エネ0で永遠に不発。3枚目はいかなる補正
                # (前+12000/ミスト+32000/旧ko_mode90000)でも覆せない絶対禁止
                return -5000
            score = 120000
            if card_id == MIST_ENERGY and count_in_hand(me, BASIC_GRASS_ENERGY) == 0:
                # 修理(2026-08-09): ミスト加点は基本エネが手札に無い時だけ(希少品温存)
                score += 32000
            if in_play_area == AreaType.ACTIVE:
                score += 12000
            if count_in_hand(me, EXPLORER_GUIDANCE) > 0 and attached_energy_count(target) == 1:
                score += 40000
        elif target.id == SOLROCK:
            if has_in_field(me, LUNATONE) and attached_energy_count(target) < 1 and card_id in (BASIC_FIGHTING_ENERGY, ROCK_FIGHTING_ENERGY):
                score = 70000
            else:
                score = 4000
        elif target.id == DWEBBLE:
            # Ascension costs 1 colorless; attach if Dwebble is active and can evolve.
            if wall_mode and in_play_area == AreaType.ACTIVE and attached_energy_count(target) < 1:
                score = 160000 if card_id in GRASS_ENERGY_IDS else 130000
            else:
                score = 52000 if in_play_area == AreaType.ACTIVE and attached_energy_count(target) < 1 else 9000
        elif target.id == CRUSTLE:
            if get_route() == "prize" and card_id in GRASS_ENERGY_IDS and attached_energy_count(target) < 3:
                # prizeルート: イワパレスが主砲。エネ投資を最優先線に
                score = 150000 if in_play_area == AreaType.ACTIVE else 120000
            elif (opponent_chips_board(opponent) and card_id in GRASS_ENERGY_IDS
                    and attached_energy_count(target) < 3
                    and not any(p.id == CRUSTLE and scissors_ready(p, me, opponent)
                                for p in field_pokemon(me))):
                # go教示(2026-07-31): マリィ戦は「ボスで削り屋を呼んではさみでKO」が軸。
                # 撃てるイワパレスを常に1体維持する(3エネ充填を削り体制の一部と扱う)
                score = 125000 if in_play_area == AreaType.ACTIVE else 105000
            elif in_play_area == AreaType.ACTIVE and facing_lucario_strong(opponent) and attached_energy_count(target) >= 2 and can_pay_attack(target, SUPERB_SCISSORS):
                score = 9000
            elif card_id in GRASS_ENERGY_IDS:
                if wall_mode and attached_energy_count(target) < 3:
                    score = 130000 if in_play_area == AreaType.ACTIVE else 110000
                else:
                    score = 18000
            else:
                score = 12000
        elif target.id == MEGA_HERACROSS_EX:
            if facing_lucario_strong(opponent) and card_id in GRASS_ENERGY_IDS and attached_energy_count(target) < 3 and has_ready_tusk(me):
                score = 104000 if in_play_area == AreaType.ACTIVE else 82000
            else:
                score = 3000
        elif target.id == KORAIDON_EX:
            if facing_lucario_strong(opponent) and card_id in (BASIC_FIGHTING_ENERGY, ROCK_FIGHTING_ENERGY, MIST_ENERGY) and attached_energy_count(target) < 3 and has_ready_tusk(me):
                score = 98000 if in_play_area == AreaType.ACTIVE else 76000
            else:
                score = 3000
        elif target.id == TERRAKION:
            if facing_lucario_strong(opponent) and card_id in (BASIC_FIGHTING_ENERGY, ROCK_FIGHTING_ENERGY, MIST_ENERGY) and attached_energy_count(target) < 2 and has_ready_tusk(me):
                score = 82000 if in_play_area == AreaType.ACTIVE else 60000
            else:
                score = 3000
        elif target.id == MEGA_HAWLUCHA_EX:
            if facing_lucario_strong(opponent) and card_id in (BASIC_FIGHTING_ENERGY, ROCK_FIGHTING_ENERGY, MIST_ENERGY) and attached_energy_count(target) < 3 and has_ready_tusk(me):
                score = 90000 if in_play_area == AreaType.ACTIVE else 70000
            else:
                score = 3000
        elif target.id == DURANT_EX:
            if card_id in GRASS_ENERGY_IDS:
                score = (72000 if ko_mode else 22000) if attached_energy_count(target) < 3 else 6000
            else:
                score = 9000
        elif target.id == CORNERSTONE_OGERPON:
            score = 15000 if card_id == BASIC_FIGHTING_ENERGY else 5000
        else:
            score = 2000
        return score
    if card_id == HERO_CAPE:
        if not has_tool(target, HERO_CAPE):
            if target.id == CRUSTLE and wall_mode:
                return 260000 if in_play_area == AreaType.ACTIVE else 220000
            if target.id == GREAT_TUSK:
                return 210000 if in_play_area == AreaType.ACTIVE else 170000
            if target.id == CRUSTLE:
                return 150000
            return 50000
        return -10000
    if card_id == AIR_BALLOON:
        if not has_tool(target, AIR_BALLOON):
            if target.id == GREAT_TUSK:
                return 140000 if in_play_area == AreaType.ACTIVE else 90000
            if target.id in (DWEBBLE, CRUSTLE):
                return 50000
        return -10000
    if card_id == SACRED_CHARM:
        if not has_tool(target, SACRED_CHARM):
            if target.id in (GREAT_TUSK, CRUSTLE, DWEBBLE) and opponent_can_attack_soon(opponent):
                return 110000
            return 25000
        return -10000
    if card_id == GRAVITY_GEM:
        if in_play_area == AreaType.ACTIVE and not has_tool(target, GRAVITY_GEM):
            if target.id == CRUSTLE and wall_mode:
                return 42000
            if target.id == GREAT_TUSK:
                return 20000
            return 12000
        return -10000
    if card_id == HANDY_CIRCULATOR:
        if in_play_area == AreaType.ACTIVE and not has_tool(target, HANDY_CIRCULATOR):
            if target.id == CRUSTLE and wall_mode:
                return 39000
            if target.id == GREAT_TUSK:
                return 18000
            return 8000
        return -10000
    return -10000


def switch_score(card: Pokemon, player_index: int, me, opponent, state, wall_mode: bool, ko_mode: bool) -> int:
    if player_index != state.yourIndex:
        # Select opponent target: in LO mode, trap high-retreat/low-energy targets.
        data = CARD_TABLE.get(card.id)
        retreat = data.retreatCost if data is not None else 0
        score = 1000 + retreat * 700 - attached_energy_count(card) * 800
        if facing_lucario_strong(opponent):
            if card.id in (674, 673) and attached_energy_count(card) <= 1:
                score += 8500
            elif card.id in (675, 676, 677) and attached_energy_count(card) == 0:
                score += 5200
        if facing_abomasnow_sample(opponent):
            if card.id in (723, 722) and attached_energy_count(card) <= 2:
                score += 6500
            if card.id == 721 and attached_energy_count(card) >= 2:
                score -= 2500
        if facing_dragapult_sample(opponent):
            if card.id == 121:
                score += 4500
            if card.id in (119, 235) and retreat == 0:
                score -= 2000
        if get_route() == "prize" and card.id in (860, 104):
            score += 9000   # フロスラス線の早期除去(go教示: ばら撒き特性の芽を摘む)
        if (facing_starmie(opponent) and card.id == MEGA_STARMIE_EX
                and bool(state.stadium) and state.stadium[0].id == NEUTRAL_CENTER):
            # 教え34改(go裁定 2026-08-12): NCが場にある限りメガスターミーexは
            # こちらの非ルール全員に0ダメージ=最高の置物。本体を前に呼んで
            # 攻撃ターンを空費させる(weihao対スターミー勝ち3局の実測パターン)
            score += 20000
        if card.id in (104, 860, 112) and opponent_chips_board(opponent):
            # go教示(2026-07-31): 削り屋(ユキメノコ/ユキワラシ/マシマシラ)を最優先で前へ。
            # イワパレスが攻撃可能なら確定KO圏(はさみ120 vs HP70-110)
            _crustle_ready2 = any(p.id == CRUSTLE and scissors_ready(p, me, opponent)
                                  for p in field_pokemon(me))
            if _crustle_ready2:
                score += 22000
            else:
                score += 8000
        # go原則(2026-07-22): 縛り先=「逃げが重く、かつすぐ攻撃できない」ポケモン。
        # (ノココッチ等の個別IDではなく抽象条件。攻撃0コスト持ち(フーディン等)は自然と対象外)
        gap = energy_gap_to_attack(card)
        if retreat >= 2 and gap >= 2:
            score += 7000
        elif retreat >= 2 and gap >= 1:
            score += 3500
        elif retreat >= 1 and gap >= 2:
            score += 2500
        if gap == 0:
            score -= 2000  # 既に攻撃可能な駒を前に出すのは利敵
        if ko_mode:
            score = max(score, 3500 - card.hp + attached_energy_count(card) * 300)
        if is_ex_pokemon(card) and not ko_mode and not (facing_abomasnow_sample(opponent) or facing_dragapult_sample(opponent)):
            score -= 300
        return score

    if facing_alakazam(opponent) and not ko_mode:
        # go棋譜28件から抽出(2026-07-22): 前出しは3軸で決める。
        # ①序中盤は壁/安い駒を差し出しキバ温存 ②攻撃可キバ+探検家使用可なら前へ(コンボ価値)
        # ③終盤(自山<=22)は未成立キバでもテンポ優先で前へ
        explorer_usable = count_in_hand(me, EXPLORER_GUIDANCE) > 0 and not state.supporterPlayed
        race_on = me.deckCount <= 22 or opponent.deckCount <= 15
        if card.id == GREAT_TUSK:
            ready = can_pay_attack(card, LAND_COLLAPSE)
            if ready and (explorer_usable or race_on):
                return 200000 + attached_energy_count(card) * 500 - damage_on(card)
            if race_on:
                return 90000 + attached_energy_count(card) * 800 - damage_on(card)
            if ready:
                # 攻撃可でも探検家が無いなら壁優先(go: コンボが乗らない削りは急がない)
                return 30000 - damage_on(card)
            return 8000 - damage_on(card)
        if card.id == CRUSTLE:
            return 140000 - damage_on(card)
        if card.id == DWEBBLE:
            return 60000 - damage_on(card)
        if card.id == BUDEW:
            return 55000
    if card.id == GREAT_TUSK and can_pay_attack(card, LAND_COLLAPSE) and opponent.deckCount <= 20:
        return 190000 + attached_energy_count(card) * 500 - damage_on(card)
    if wall_mode and card.id == CRUSTLE:
        return 150000 + attached_energy_count(card) * 600 - damage_on(card)
    if card.id == GREAT_TUSK and can_pay_attack(card, LAND_COLLAPSE):
        return 120000 + attached_energy_count(card) * 500 - damage_on(card)
    if card.id == DWEBBLE and wall_mode:
        return 68000 + attached_energy_count(card) * 900
    if facing_lucario_strong(opponent) and card.id == MEGA_HERACROSS_EX and can_pay_attack(card, HERA_MOUNTAIN_RAMMING):
        return 170000 + attached_energy_count(card) * 800 - damage_on(card)
    if facing_lucario_strong(opponent) and card.id == KORAIDON_EX and can_pay_attack(card, ORICHALCUM_FANG):
        return 165000 + attached_energy_count(card) * 800 - damage_on(card)
    if facing_lucario_strong(opponent) and card.id == TERRAKION and can_pay_attack(card, TERRAKION_RETALIATE):
        return 135000 + attached_energy_count(card) * 800 - damage_on(card)
    if facing_lucario_strong(opponent) and card.id == MEGA_HAWLUCHA_EX and can_pay_attack(card, SOMERSAULT_DIVE):
        # Do not abandon Neutralization Zone too casually; this is for KO mode or enemy stadium races.
        if state.stadium and state.stadium[0].id != NEUTRAL_CENTER:
            return 190000 + attached_energy_count(card) * 900 - damage_on(card)
        if ko_mode and opponent.deckCount <= 26:
            return 165000 + attached_energy_count(card) * 900 - damage_on(card)
    if card.id == TATSUGIRI and not state.supporterPlayed and count_in_hand(me, EXPLORER_GUIDANCE) == 0:
        return 36000
    if card.id == FLUTTER_MANE and opponent_can_attack_soon(opponent):
        return 24000
    if card.id == CORNERSTONE_OGERPON and ko_mode:
        return 30000
    if card.id == DURANT_EX:
        return 105000 + attached_energy_count(card) * 500 if ko_mode and can_pay_attack(card, DURANT_VENGEFUL_CRUSH) else -20000
    return 1000 + attached_energy_count(card) * 300 - damage_on(card) // 2


def attack_score(attack_id: int | None, me, opponent, state, wall_mode: bool, ko_mode: bool) -> int:
    active = active_pokemon(me)
    if active is None:
        return -10000
    opp_active = active_pokemon(opponent)
    # go教示(2026-07-28 スボミー30点KO): 全ワザ共通の「とどめ算数」。
    # むずむずかふん10×草弱点2倍+既存ダメカン10=ちょうど30でKOした実戦例の一般化。
    # 弱点込みダメージ+既存ダメカン >= 残りHP なら、どのワザでも最速のサイド。
    if attack_id is not None and opp_active is not None:
        _atk = ATTACK_TABLE.get(attack_id)
        _od = CARD_TABLE.get(opp_active.id)
        _ad = CARD_TABLE.get(active.id)
        _base = (getattr(_atk, "damage", 0) or 0) if _atk is not None else 0
        if _base > 0 and _od is not None:
            # go指摘(2026-08-06 ep90314751): 旧コードは存在しない属性名"type"を見て
            # いたため弱点×2が一度も発動していなかった(はさみ120→オーロンゲ草弱点240)
            _eff_base = typed_damage(_base, active.id, opp_active.id)
            _hp = getattr(_od, "hp", None) or 999
            if state.stadium and state.stadium[0].id == LIVELY_STADIUM and getattr(_od, "stage", None) in (None, 0):
                _hp += 30
            # 教え9付随修正(2026-08-09): 道具でHPが増えた個体(マント等)はカタログHPでなく
            # 実maxHpで判定する。旧: 160でHP190のマント壁を「とどめ」と誤認していた
            _hp = max(_hp, getattr(opp_active, "maxHp", 0) or 0)
            if _eff_base + damage_on(opp_active) >= _hp:
                if ko_mode or get_route() == "prize":
                    return 295000   # 攻めプラン: とどめ>あらゆる置物
                if (active.id == GREAT_TUSK
                        and can_pay_attack(active, GIANT_TUSK_ATTACK)
                        and not is_ex_pokemon(opp_active)):
                    # 教え9: 狩りプランの2発目(とどめ)は削りルートでもミルより優先。
                    # 「4エネ武装済みキバ」は計画の産物なので、とどめ時点で計画条件
                    # (硬い敵の存在)が消えていても撃ち切る。アタッカーを抜けばレースが止まる
                    return 290000
                if not is_ex_pokemon(opp_active):
                    return 61000    # 削りプラン: 主砲のミルは超えないが、殴れる置物なら取る
        # 教え18②: 単騎非ex対面はダメージ技>ミル。回復在庫は有限(捨て札で追跡)なので
        # 打点を当て続ければ在庫が尽きて削り切れる。在庫が尽きた瞬間からは純打点レース
        if (attack_id is not None and opp_active is not None
                and solo_oneshot_target(opponent) is not None or (
                    attack_id is not None and opp_active is not None
                    and len([p for p in field_pokemon(opponent) if p is not None]) == 1
                    and not is_ex_pokemon(opp_active)
                    and _PRIZE_LEDGER.get("turn", 0) >= 4)):
            if (getattr(ATTACK_TABLE.get(attack_id), "damage", 0) or 0) >= 100:
                return 250000
        # 教え9(go提案 2026-08-09): 狩りプランの1発目(非KO)。ギガントタスク160を
        # 「殴ってくる壁」(一撃圏外の非ex)に置く。2発で320=マント壁190も圏内。
        # 適用範囲: 計画発火中+自分がキバ+ワザ63+相手前が非exで一撃圏外の時のみ
        if (attack_id == GIANT_TUSK_ATTACK and active.id == GREAT_TUSK
                and opp_active is not None and not is_ex_pokemon(opp_active)
                and giant_tusk_plan(me, opponent)):
            _od9 = CARD_TABLE.get(opp_active.id)
            _hp9 = (getattr(_od9, "hp", None) or 0)
            if state.stadium and state.stadium[0].id == LIVELY_STADIUM and getattr(_od9, "stage", None) in (None, 0):
                _hp9 += 30
            _hp9 = max(_hp9, getattr(opp_active, "maxHp", 0) or 0)
            if _hp9 and 160 + damage_on(opp_active) < _hp9:
                return 240000
    if attack_id is not None and attack_id in SOLROCK_ATTACK_IDS and has_in_field(me, LUNATONE):
        if opp_active is not None and not is_ex_pokemon(opp_active):
            data = CARD_TABLE.get(opp_active.id)
            base_hp = getattr(data, "hp", None) or 999
            if state.stadium and state.stadium[0].id == LIVELY_STADIUM and getattr(data, "stage", None) in (None, 0):
                base_hp += 30
            if damage_on(opp_active) + 70 >= base_hp:
                return 300000
            if ko_mode:
                # ロック中のチップ戦術: 3発でイワパレスも落ちる。素のミルより優先。
                return 280000
        if not has_ready_tusk(me) and (ko_mode or not facing_passive_wall(opponent)):
            return 60000
        return 8000
    if attack_id is not None and attack_id in DEDENNE_ATTACK_IDS:
        key_in_discard = count_in_discard(me, EXPLORER_GUIDANCE) or count_in_discard(me, XEROSIC_SCHEME)
        if key_in_discard and not has_ready_tusk(me) and count_in_hand(me, EXPLORER_GUIDANCE) == 0:
            # goの実戦: 序盤はソナーで先導を拾い直してから削りに入る
            return 62000
        trainer_in_discard = sum(
            1 for cid in (LILLIE_RESOLVE, XEROSIC_SCHEME, BOSS_ORDERS, EXPLORER_GUIDANCE)
            if count_in_discard(me, cid)
        )
        return 15000 if trainer_in_discard else 1500
    if attack_id is not None and attack_id in BUDEW_ATTACK_IDS:
        # 教え25(go教示 2026-08-10、採用): このターン、ベンチのキバに特殊エネ(ミスト/ロック闘)を
        # 貼った(=草から貼れなかった)なら、むずがゆかふんでグッズロック。貼りたての
        # 特殊エネを次の相手ターンの改造ハンマーから守る(対フーディンはアメも同時に縛れる)。
        # 175000=反撃武装と同格。武装済みキバの前出し(SWITCH 210000)は超えない=殴れるならそっち
        if (_ITCHY_LEDGER.get("turn") == getattr(state, "turn", -2)
                and _ITCHY_LEDGER.get("now", 0) > _ITCHY_LEDGER.get("base", 0)):
            return 175000
        if len(opponent.prize) == 6:
            return 70000
        # go教示(2026-07-30): 攻撃できるキバ不在の間、むずむずかふんは
        # 「時間を稼ぎながらアイテムを縛る」最善の置き手
        if get_route() != "prize" and not any(
                p.id == GREAT_TUSK and can_pay_attack(p, LAND_COLLAPSE)
                for p in field_pokemon(me)):
            return 60000
        return 2000
    if attack_id is not None and attack_id in SUDOWOODO_ATTACK_IDS:
        return 26000
    if attack_id == LAND_COLLAPSE:
        score = 180000
        if state.supporterPlayed:
            score += 90000
        else:
            # Attack is still better than doing nothing, but Explorer + attack should outrank raw attack.
            score += 10000
        if opponent.deckCount <= (4 if state.supporterPlayed else 1):
            score += 100000
        return score
    if attack_id == ASCENSION:
        if active.id == DWEBBLE and count_in_field(me, CRUSTLE) == 0:
            return 125000 if wall_mode else 80000
        return 1000
    if attack_id == MOUNTAIN_RAMMING:
        score = 32000 if not ko_mode else 300000
        if opponent.deckCount <= 1:
            score += 100000
        return score
    if attack_id == ROCK_KAGURA:
        return 42000 if active.id == CORNERSTONE_OGERPON and attached_energy_count(active) < 3 else 8000
    if attack_id == SUPERB_SCISSORS:
        # go分岐マイニング(2026-07-27 vsオーロンゲ2勝): 機械はこの技を評価せず
        # にげる/置物に化けていた(分岐10+回)。弱点込みダメージ計算の汎用ゲート:
        # 「弱点で一撃圏なら殴るのが最速のサイド」「弱点持ち相手なら2発圏でも殴り得」
        if opp_active is not None:
            _d = CARD_TABLE.get(opp_active.id)
            if _d is not None:
                _weak = getattr(_d, "weakness", None) == 1  # 草弱点(自技タイプ)
                _dmg = 120 * (2 if _weak else 1)
                _hp = (getattr(_d, "hp", None) or 999)
                if state.stadium and state.stadium[0].id == LIVELY_STADIUM and getattr(_d, "stage", None) in (None, 0):
                    _hp += 30
                if _dmg >= _hp - damage_on(opp_active):
                    return 262000   # 一撃圏: 殴る>あらゆる置物
                if _weak:
                    return 232000   # 弱点2発圏: 継続攻撃が最速レース
        if ko_mode:
            return 350000
        if get_route() == "prize":
            # LOレース不成立 → サイド取り切りが勝ち筋 (goの壁戦: はさみ21連打)
            return 240000
        if facing_lucario_strong(opponent) or generic_active_nonex_race_threat(opponent):
            return 235000
        if wall_mode:
            return 65000
        return 9000
    if attack_id == DURANT_VENGEFUL_CRUSH:
        return 300000 if ko_mode else 10000
    if attack_id == HERA_MOUNTAIN_RAMMING:
        if facing_lucario_strong(opponent):
            return 285000 if ko_mode or opponent.deckCount <= 28 else 90000
        return 12000
    if attack_id == JUGGERNAUT_HORN:
        return 250000 if facing_lucario_strong(opponent) and ko_mode else 16000
    if attack_id == ORICHALCUM_FANG:
        return 285000 if facing_lucario_strong(opponent) and ko_mode else 12000
    if attack_id == KORAIDON_TERA:
        return 16000
    if attack_id == TERRAKION_RETALIATE:
        return 235000 if facing_lucario_strong(opponent) and ko_mode else 20000
    if attack_id == TERRAKION_LAND_CRUSH:
        return 220000 if facing_lucario_strong(opponent) and ko_mode else 12000
    if attack_id == SOMERSAULT_DIVE:
        if facing_lucario_strong(opponent):
            if state.stadium and state.stadium[0].id != NEUTRAL_CENTER:
                return 300000 if ko_mode else 185000
            # Avoid discarding our own Neutralization Zone unless the game is already near terminal.
            if state.stadium and state.stadium[0].id == NEUTRAL_CENTER and opponent.deckCount > 12:
                return 18000
            return 260000 if ko_mode else 28000
        return 12000
    if attack_id == GIANT_TUSK:
        return 300000 if ko_mode else -5000
    attack = ATTACK_TABLE.get(attack_id)
    damage = attack.damage if attack is not None else 0
    return (6000 + damage * 8) if ko_mode else (1200 - damage * 5)


def acquisition_score(cid, card, me, opponent, state, wall_mode: bool, ko_mode: bool):
    """TO_HAND(取得判断)チェーン。ステップ1(2026-08-10): select_card_scoreから
    純コード移動(数値不変)。wants強化(go指示)はこの関数に対して1件ずつ行う。"""
    active = active_pokemon(me)
    # === v29.14a: 底辺固定だった4枚の動的化(go指示 2026-08-14「盤面によって変わる」) ===
    # 教え53(goクイズ 2026-08-14 ep92937338): アタッカーがあと1エネで起動する×
    # 手札にエネ0の時、基本エネの取得は体在庫(72000)より上。体3体はもう足りている
    if cid in GRASS_ENERGY_IDS:
        _short53 = any(
            p is not None and p.id in (GREAT_TUSK, CRUSTLE)
            and attack_energy_minimum(p) and attached_energy_count(p) + 1 >= attack_energy_minimum(p)
            and not any(can_pay_attack(p, _a) for _a in getattr(CARD_TABLE.get(p.id), "attacks", []) or [])
            for p in field_pokemon(me))
        if _short53 and not any(getattr(c, "id", None) in ENERGY_IDS for c in (me.hand or [])):
            return 95000

    if cid == JUMBO_ICE_CREAM:
        # 教え48: 回復需要駆動。価値ある体(イワパレス線/キバ/エネ持ち)の最大被ダメで跳ねる
        _worst48 = max((damage_on(p) for p in field_pokemon(me)
                        if p is not None and (p.id in (CRUSTLE, GREAT_TUSK)
                                              or attached_energy_count(p) >= 1)), default=0)
        if _worst48 >= 40:
            return 60000 + min(_worst48, 120) * 250   # 40dmg→70000 / 120dmg→90000
    if cid == MIST_ENERGY and opponent_special_hazard(opponent):
        # ハンマー/剥がし対面のミスト=鎧の主部品。枯渇棚(3600)から救出
        _kiba_alive = any(p is not None and p.id == GREAT_TUSK for p in field_pokemon(me)) \
            or count_in_hand(me, GREAT_TUSK) > 0
        if _kiba_alive and count_in_hand(me, MIST_ENERGY) == 0:
            return 90000
    if cid == XEROSIC_SCHEME and opponent.handCount >= 6:
        # 教え50②(go設計 2026-08-14): 相手の手札が膨らんでいる時のクセロシキは
        # 必要札を落とさせる妨害弾。取得側にも同じ判断を映す
        return 60000
    if cid == 1123 and active is not None:
        # いれかえ: 前が詰まっている(攻撃不能×にげる重い)×ベンチに攻撃可能な体、の時だけ跳ねる
        _stuck = (not any(can_pay_attack(active, _a)
                          for _a in getattr(CARD_TABLE.get(active.id), "attacks", []) or [])
                  and (getattr(CARD_TABLE.get(active.id), "retreatCost", 0) or 0) >= 1)
        _ready_back = any(p is not None and any(
            can_pay_attack(p, _a) for _a in getattr(CARD_TABLE.get(p.id), "attacks", []) or [])
            for p in (me.bench or []))
        if _stuck and _ready_back:
            return 60000
    # ベンチ0緊急プロトコル(go承認 2026-08-06 ep90128213): 体切れ目前は
    # たね本体と「体の配達員」が全カードに優先する。配達員の届き先はカード毎:
    # ポフィン=HP70以下のたね2体(いしずまい/スボミー、キバ不可)
    # パッド=ルールボックス無し全般(キバはこれだけ) / むしとり=草(いしずまい)
    if (not any(p is not None for p in (me.bench or []))
            and count_basics_in_hand(me) == 0):
        _dc = CARD_TABLE.get(cid)
        if _dc is not None and getattr(_dc, "basic", False) and getattr(_dc, "hp", None):
            # go教示(2026-08-07 ep90441584): 体なら何でも良くない。緊急時も
            # プラン序列で拾う(いしずまい>キバ>スボミー、チップ対面のスボミーは最下位)。
            # 一律同点でスボミーを拾い「チップ対面に置けない」袋小路になった試合の根治
            if cid == DWEBBLE:
                return 246000
            if cid == GREAT_TUSK:
                return 243000
            if cid == BUDEW and opponent_chips_board(opponent):
                return 238000
            return 240000
        if cid == BUDDY_BUDDY_POFFIN:
            return 230000
        if cid == POKE_PAD:
            return 210000
        if cid == BUG_CATCHING_SET:
            return 200000
    # go正解手(2026-08-07 ep90413991): アセンション線が立つ場では、拾う側でも
    # 入れ替えを最上位に。イワパレスは「ワザで山から取れるパーツ」なので拾わない
    # (実戦: 探検家でイワパレス+エネを拾い手札0継続→-64大敗。正解=入れ替え+リーリエ)
    if ascension_line_ok(me):
        if cid == SWITCH and count_in_hand(me, SWITCH) == 0:
            return 185000
        if cid == CRUSTLE:
            return 15000
    if cid == BUDEW and budew_lock_line_ok(me, opponent, state):
        # go教示(2026-08-07): 後攻T2ロック線が立つなら、プラン外の体より優先で拾う
        return 90000
    # Search target priorities. Ultra Ball can search both Great Tusk and Crustle.
    if get_route() == "prize":
        _w = current_wants(me, opponent)
        # go教示(2026-08-03 ep89657841): 「なるべく1ターンに1エネは貼りたい」。
        # 手札に貼れるエネが0枚なら、エネの取得を配達員(パッド等)より上に置く
        # (この試合は草160000 vs パッド167500の僅差で草を見送り→補給線が切れた)
        if (cid in ENERGY_IDS
                and count_in_hand(me, BASIC_GRASS_ENERGY) + count_in_hand(me, MIST_ENERGY) == 0
                and any(attached_energy_count(p) < attack_energy_minimum(p)
                        for p in field_pokemon(me))):
            # go指摘(2026-08-07 ep90364695): 緊急確保は1枚で足りる。
            # 複数枚選択で全エネが最高点になり2枚ともエネで埋まる穴を封鎖
            if not _ROUTE_STATE.get("_emg_energy_used"):
                _ROUTE_STATE["_emg_energy_used"] = True
                return 175000
            # go教義の両立(2026-08-07): 未武装アタッカーが2体以上(キバ2体E0等)なら
            # 2枚目も正当な需要。1体以下なら浪費ループ対策で降格
            _unarmed = sum(1 for p in field_pokemon(me)
                           if p is not None and p.id in (GREAT_TUSK, CRUSTLE)
                           and attached_energy_count(p) < attack_energy_minimum(p))
            return 175000 if _unarmed >= 2 else 30000
        # 配達員価値(go教示 2026-07-29): サーチ札の価値=その先で取れる物のwants最大×割引。
        # 例: エネが手札に有る→むしとり≈0点 / 体が不足→パッド=体wants×0.9で高得点。
        # goの実戦解「先導でパッド2枚取り」を再現する連鎖引き算
        if cid == POKE_PAD:
            _best = max((v for k, v in _w.items()
                         if k in (DWEBBLE, CRUSTLE, BUDEW, DEDENNE, SUDOWOODO, MARACTUS) and v > 0),
                        default=0)
            return 40000 + int(_best * 0.9) * 1500 if _best > 0 else 3000
        if cid == BUG_CATCHING_SET:
            _best = max((v for k, v in _w.items()
                         if k in (BASIC_GRASS_ENERGY, DWEBBLE, CRUSTLE) and v > 0),
                        default=0)
            return 40000 + int(_best * 0.85) * 1500 if _best > 0 else 2500
        if cid in _w:
            _pw = _w[cid]
            return -5000 if _pw < 0 else 40000 + _pw * 1500
    if cid == NEUTRAL_CENTER:
        return 120000
    if cid == COLRESS_TENACITY and (opponent_ex_pressure(opponent) or opponent_shows_ex_evolution_line(opponent)):
        return 110000
    if cid == LILLIE_RESOLVE:
        # go教示(2026-08-02): 先導でリーリエを拾えると安定感が上がる
        # go指摘(2026-08-03 ep89657841): 手札1枚でリーリエ2枚を見送り→枯れ死。
        # 手札が細いほどドロー札の取得価値を引き上げる
        # go正解手(2026-08-07 ep90413991): 手札0〜2ならパーツ/緊急エネ(175000)より
        # リーリエ優先。「リーリエで山に戻る物を拾う意味はない、エネは6枚から引ける読み」
        if me.handCount <= 2:
            return 180000
        # wants強化#1(go方針 2026-08-10): 削りルート初のwants接続(1件ずつ方式)。
        # 補給需要(サポ手札0×手札3枚以上)が立っている時は 40000+50*1500=115000 で拾う
        # (NC120000は超えない)。全面配線は過去-4pt(2026-08-04)の教訓により単カード限定
        _w_lil = current_wants(me, opponent).get(LILLIE_RESOLVE, 0)
        if _w_lil > 0:
            return 40000 + _w_lil * 1500
        if me.handCount <= 4:
            return 30000
    if cid == EXPLORER_GUIDANCE and active_tusk_ready(me) and not state.supporterPlayed:
        return 160000
    if cid == EXPLORER_GUIDANCE:
        # 教え46(goクイズ答え合わせ 2026-08-14): 手札枯渇(≤2)の探検家は復旧手段
        if me.handCount <= 2:
            return 120000
        # go教示(2026-08-02): ポケカは手札が多い方が強い。先導はコンボ弾であると
        # 同時に手札+2の補給カード。所持数に関わらず補給価値で取る
        return 34000
    if cid == POKEGEAR_30 and me.handCount <= 2 and not any(
            getattr(c, "id", None) in SUPPORTERS for c in (me.hand or [])):
        # 教え46: 手札枯渇×サポート無し→ポケギアはリーリエ/探検家を探す復旧初手
        return 90000
    if cid == BOSS_ORDERS and opponent_has_trappable_bench(opponent):
        return 75000 if opponent.deckCount <= 10 or len(opponent.prize) <= 1 else 26000
    if cid == LISIA_APPEAL and opponent_has_trappable_basic_bench(opponent):
        return 80000 if opponent.deckCount <= 12 or len(opponent.prize) <= 1 else 24000
    if cid == GREAT_TUSK:
        _v = 100000 if "kiba_body" in current_needs(me, opponent) else 45000
        return _v // 8 if count_in_hand(me, GREAT_TUSK) >= 1 else _v
    if cid == CRUSTLE and has_in_field(me, DWEBBLE):
        # 手札差し引き(go教訓 2026-07-29 第2弾): 既に手札にある体は「欲しくない」。
        # 実戦ep88714698 T3: 手札1枚あるのに先導でイワパレス2枚両取り
        # →ハンマー/パッドをトラッシュした事故の根治
        if count_in_hand(me, CRUSTLE) >= 1:
            return 9000
        return 78000 if wall_mode else 43000
    if cid == DWEBBLE:
        _n = current_needs(me, opponent)
        # 教え61b(go教示 2026-08-15 ep93269044): ポフィンを持っているならイシズマイは
        # ポフィンで直接2体置ける。パッド/先導の枠をイシズマイに使うのは配達員の
        # 無駄遣い(サーチ枠は進化線=イワパレス/キバへ)
        if count_in_hand(me, BUDDY_BUDDY_POFFIN) >= 1:
            return 9000
        _v = (72000 if ("wall_body" in _n or "bench_body" in _n)
              else (64000 if wall_mode or count_in_field(me, DWEBBLE) == 0 else 22000))
        return _v // 6 if count_in_hand(me, DWEBBLE) >= 1 else _v
    if cid == CRUSHING_HAMMER:
        if facing_alakazam(opponent):
            # go指摘(2026-08-04 ep89808243): フーディン指紋が出たら見えている
            # ワザに関わらずハンマーは安い(1エネで殴る相手に折る意味なし)。
            # 「コスト不明→とりあえず有効52000」の誤発火を対面認識で封鎖
            return 5000
        # go教義(2026-07-29): ハンマーの価値=相手の攻撃コスト依存。
        # 1エネで殴れる相手(フーディン)は折っても足止めにならない→低priority。
        # 2エネ以上必要な相手(オーロンゲ等)には遅延として有効
        _opp_min_cost = 99
        for pk in field_pokemon(opponent):
            for aid in getattr(CARD_TABLE.get(pk.id), "attacks", []) or []:
                _at = ATTACK_TABLE.get(aid)
                # 脅威ワザ(60点以上orミル)のみ算入。しょうてん等の0点1エネ技で
                # 「1エネ相手」と誤判定しない(goレビュー: 対イワパレスはエネ破壊有効)
                if _at is not None and ((getattr(_at, "damage", 0) or 0) >= 60
                                        or aid in (LAND_COLLAPSE, MOUNTAIN_RAMMING, HERA_MOUNTAIN_RAMMING)):
                    _opp_min_cost = min(_opp_min_cost, len(getattr(_at, "energies", []) or []))
        if _opp_min_cost >= 2 and any(1 <= len(pk.energies or []) <= 3
                                      for pk in field_pokemon(opponent)):
            # 相手の正体が見え切る前(公開2体未満)は高得点にしない(go: 早計取得の抑制)
            if len(field_pokemon(opponent)) < 2:
                return 24000
            return 52000
        return 5000
    if cid == BUG_CATCHING_SET:
        # 配達員価値・削りプラン版: むしとり=キバの基本草エネの配達員。
        # エネ需要は「場の装着+手札のエネ」から引き算(go指摘: 手札のミストも2エネ目)
        _kiba_att = max((attached_energy_count(p) for p in field_pokemon(me)
                         if p.id == GREAT_TUSK), default=0)
        _e_hand = count_in_hand(me, BASIC_GRASS_ENERGY) + count_in_hand(me, MIST_ENERGY)
        if max(0, 2 - _kiba_att - _e_hand) > 0:
            return 50000
        # go承認(2026-08-07): エネ破壊対面の在庫バッファ(場+手札<4)も配達需要
        # (解剖: 削り側の拾う回路がwantsのバッファを見ていない配線切れの修理)
        if (opponent_special_hazard(opponent)
                and sum(attached_energy_count(p) for p in field_pokemon(me))
                + sum(count_in_hand(me, _e) for _e in ENERGY_IDS) < 4):
            return 48000
        return 6000
    if cid == POKE_PAD:
        # go実戦解(2026-07-29): 削りプランのパッド=イダイナキバの配達員
        _bodies = count_in_field(me, GREAT_TUSK) + count_in_hand(me, GREAT_TUSK)
        return 45000 if _bodies < 2 else 5000
    if cid == EXPLORER_GUIDANCE and get_route() != "prize":
        # go教示(2026-07-30 ep88847578): 「デッキ破壊のために探検家は大事に」。
        # 古代コンボの弾=削りプランの生命線。ハンマーより上位で確保する
        if count_in_hand(me, EXPLORER_GUIDANCE) == 0:
            return 56000
        return 4000
    if cid in ENERGY_IDS and any(p.id == GREAT_TUSK and attached_energy_count(p) < 2 for p in field_pokemon(me)):
        if count_in_hand(me, BASIC_GRASS_ENERGY) + count_in_hand(me, MIST_ENERGY) >= 2:
            return 12000   # 手札にエネ2枚以上あるなら追加は薄い
        return 56000
    if (cid in GRASS_ENERGY_IDS and opponent_special_hazard(opponent)
            and sum(attached_energy_count(p) for p in field_pokemon(me))
            + sum(count_in_hand(me, _e) for _e in ENERGY_IDS) < 4):
        # go承認(2026-08-07): エネ破壊対面は基本エネの在庫バッファを常時需要
        # (負け試合の盤面エネがT12までに0.2まで剥がされる実測への処方。配線切れ修理)
        return 54000
    if cid == MEGA_HERACROSS_EX:
        return 52000 if facing_lucario_strong(opponent) and count_in_field(me, MEGA_HERACROSS_EX) == 0 and len(field_pokemon(me)) >= 3 else 8000
    if cid == KORAIDON_EX:
        return 44000 if facing_lucario_strong(opponent) and count_in_field(me, KORAIDON_EX) == 0 and len(field_pokemon(me)) >= 3 else 7000
    if cid == TERRAKION:
        return 40000 if facing_lucario_strong(opponent) and count_in_field(me, TERRAKION) == 0 else 7000
    if cid == MEGA_HAWLUCHA_EX:
        return 42000 if facing_lucario_strong(opponent) and count_in_field(me, MEGA_HAWLUCHA_EX) == 0 and len(field_pokemon(me)) >= 3 else 7000
    if cid == DURANT_EX:
        return 42000 if count_in_field(me, DURANT_EX) == 0 else 24000
    if cid == BUG_CATCHING_SET:
        return 32000
    return card_keep_value(cid, me, opponent, state, wall_mode, ko_mode)
    return None


def select_card_score(card, player_index, context, me, opponent, state, wall_mode: bool, ko_mode: bool) -> int:
    _ROUTE_STATE["_turn"] = int(getattr(state, "turn", 0) or 0)
    _ROUTE_STATE["_nc_up"] = bool(getattr(state, "stadium", None)) and state.stadium[0].id == NEUTRAL_CENTER
    if card is None:
        return -10000
    cid = card.id
    if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
        if isinstance(card, Pokemon):
            base = switch_score(card, player_index, me, opponent, state, wall_mode, ko_mode)
            _nc_up_s1 = bool(state.stadium) and state.stadium[0].id == NEUTRAL_CENTER
            if player_index == state.yourIndex:
                base += ex_wall_adjustment(card.id, me, opponent, _nc_up_s1)
                # go教示(2026-07-28): 「攻撃できるイダイナキバが用意できるならキバを出す。
                # 無理そうなら壁でしのぐ」。対面を問わない原則。readyには
                # 「エネ1枚+手札エネでこのターン完成する」JITケースも含める。
                _e_hand = any(count_in_hand(me, _e) for _e in ENERGY_IDS)
                _tusk_ready = card.id == GREAT_TUSK and (
                    can_pay_attack(card, LAND_COLLAPSE)
                    or (attached_energy_count(card) >= 1 and _e_hand))
                if get_route() == "prize":
                    # 攻めプラン: 弱点数学が立つ相手(草弱点)ならイワパレス主砲を前へ。
                    # 立たない相手(フシギバナ等)は攻めでもキバ削り継続(rc5でバナ40%に落ちた教訓)。
                    _opp_grass_weak = any(
                        getattr(CARD_TABLE.get(p.id), "weakness", None) == 1
                        for p in field_pokemon(opponent))
                    _cr = card.id == CRUSTLE and can_pay_attack(card, SUPERB_SCISSORS)
                    if _opp_grass_weak and _cr:
                        base += 40000
                    elif not _opp_grass_weak and _tusk_ready:
                        base += 40000
                    elif card.id in (BUDEW, DEDENNE, MARACTUS, SUDOWOODO):
                        base += 25000
                    return base
                if _tusk_ready:
                    base += 40000
                elif card.id in (BUDEW, DEDENNE, MARACTUS, SUDOWOODO):
                    # 生け贄ペーシング: 安い駒から差し出しエンジンと次のキバを守る
                    base += 25000
                elif card.id in (LUNATONE, SOLROCK):
                    base -= 15000
            else:
                _lk_yz = lethal_avoid_boss_target(me, opponent, nc_up=_nc_up_s1)
                if _lk_yz is not None and (card is _lk_yz or (
                        getattr(card, "serial", None) is not None
                        and getattr(card, "serial", None) == getattr(_lk_yz, "serial", None))):
                    # ゆら枝①: 「1枚貼っても非致死かつ逃げ不能」の的を最優先で前へ
                    base += 90000
            return base
    if context == SelectContext.SETUP_ACTIVE_POKEMON:
        return initial_active_score(cid, me, opponent)
    if context in (SelectContext.SETUP_BENCH_POKEMON, SelectContext.TO_BENCH, SelectContext.TO_FIELD):
        if (context == SelectContext.TO_FIELD and cid == BUDEW
                and getattr(state, "turn", 0) == 2
                and not getattr(state, "energyAttached", False)
                and any(getattr(c, "id", None) in ENERGY_IDS for c in (me.hand or []))
                and any(p is not None and p.id in (DWEBBLE, CRUSTLE, GREAT_TUSK)
                        for p in (me.bench or []))):
            # go教示(2026-08-07): 入れ替え後の前はスボミー(後攻T2ロック線)。
            # この時点で入れ替えは消費済みなのでbudew_lock_line_okの入れ替え条件は見ない
            return 250000
        return setup_bench_score(cid, me, opponent)
    if context in (SelectContext.EVOLVES_TO, SelectContext.EVOLVE):
        if cid == CRUSTLE:
            return 90000 if wall_mode or has_in_field(me, DWEBBLE) else 30000
        return 1000
    if context == SelectContext.EVOLVES_FROM:
        if cid == DWEBBLE:
            return 90000
        return 1000
    if context == SelectContext.TO_HAND:
        _acq = acquisition_score(cid, card, me, opponent, state, wall_mode, ko_mode)
        if _acq is not None:
            return _acq
    if context in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
        # Choose low-value cards to discard. Preserve Explorer for the boosted Great Tusk turn.
        value = card_keep_value(cid, me, opponent, state, wall_mode, ko_mode)
        score = 7000 - value
        if cid == EXPLORER_GUIDANCE:
            score -= 8000
        if cid == LILLIE_RESOLVE:
            # go指摘(2026-08-03 ep89651006): ドローソースは手札補給の生命線。
            # 強制捨てで真っ先に切ってはいけない(捨てた後にドロー0で枯れ死)
            score -= 8000
        if cid == GREAT_TUSK:
            score -= 9000
        if cid == CRUSTLE and has_in_field(me, DWEBBLE):
            score -= 5000
        if cid in ENERGY_IDS and any(p.id == GREAT_TUSK and attached_energy_count(p) < 2 for p in field_pokemon(me)):
            score -= 4000
        return score
    if context in (SelectContext.TO_DECK, SelectContext.TO_DECK_BOTTOM):
        if cid == GREAT_TUSK:
            return 85000
        if cid in ENERGY_IDS:
            return 70000
        if cid == EXPLORER_GUIDANCE:
            return 55000
        if cid in (DWEBBLE, CRUSTLE, TATSUGIRI, DURANT_EX, MEGA_HERACROSS_EX, KORAIDON_EX, TERRAKION, MEGA_HAWLUCHA_EX):
            return 30000
        return 1000
    if context == SelectContext.ATTACH_FROM and isinstance(card, Pokemon):
        if cid == GREAT_TUSK:
            return 85000
        if cid == CRUSTLE:
            return 50000 if wall_mode else 18000
        if cid == DURANT_EX:
            return 20000
        if cid == MEGA_HERACROSS_EX:
            return 52000 if facing_lucario_strong(opponent) else 1000
        if cid == KORAIDON_EX:
            return 48000 if facing_lucario_strong(opponent) else 1000
        if cid == TERRAKION:
            return 42000 if facing_lucario_strong(opponent) else 1000
        if cid == MEGA_HAWLUCHA_EX:
            return 46000 if facing_lucario_strong(opponent) else 1000
        return 1000
    if context in (SelectContext.DETACH_FROM, SelectContext.DISCARD_ENERGY_CARD, SelectContext.DISCARD_ENERGY):
        # 注(2026-08-07): ハンマー等の「相手のエネを選ぶ」selectはOptionType.ENERGY経路
        # (エネ単位オプションの採点部)で処理される。ここに相手駒分岐を足しても届かない
        # (実挙動トレースで確認済み)。マシマシラ優先はENERGY経路側に実装
        if isinstance(card, Pokemon):
            return -attached_energy_count(card) * 1000
        return 100
    if context in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
        if isinstance(card, Pokemon):
            if player_index == state.yourIndex:
                return -5000
            return 3500 if ko_mode else -1000
    if context in (SelectContext.HEAL, SelectContext.REMOVE_DAMAGE_COUNTER):
        if isinstance(card, Pokemon) and player_index == state.yourIndex:
            return damage_on(card) + (3000 if card.id in (GREAT_TUSK, CRUSTLE) else 0)
    # 2026-08-12除去: SelectContext.HANDは存在しない属性で、ここに到達する選択
    # (ハンマーの的選択など)がAttributeErrorで死んでいた
    if card is not None and not isinstance(card, Pokemon) and getattr(card, "id", None) == LILLIE_RESOLVE and player_index == state.yourIndex:
        return card_keep_value(LILLIE_RESOLVE, me, opponent, state, wall_mode, ko_mode) + 6000
    if (
        isinstance(card, Pokemon) and player_index != state.yourIndex and has_in_field(me, SOLROCK)
        and not is_ex_pokemon(card) and (ko_mode or not facing_passive_wall(opponent))
    ):
        _data = CARD_TABLE.get(card.id)
        _hp = getattr(_data, "hp", None) or 999
        if damage_on(card) + 70 >= _hp:
            return 88000
    if (not isinstance(card, Pokemon) and player_index != state.yourIndex
            and getattr(CARD_TABLE.get(getattr(card, "id", 0)), "cardType", None) in (5, 6)):
        # 教え42(go裁定 2026-08-12): 相手のエネを折る時(クラハン等)の的の優先順位。
        # 最優先=マシマシラの悪エネ: アドレナブレインの燃料で、折れば回復30/ターンが
        # 止まる(コロシアムでは止まらないことが公式裁定で確認済み。回復だけは通る)。
        # 次点=あと1個折れば攻撃が止まる主砲のエネ(従来の遅延価値の明文化)
        _serial42 = getattr(card, "serial", None)
        for _pk42 in field_pokemon(opponent):
            _ecs42 = getattr(_pk42, "energyCards", None) or []
            if _serial42 is not None and any(
                    getattr(e, "serial", None) == _serial42 for e in _ecs42):
                if _pk42.id == 112:
                    return 60000
                _n42 = attached_energy_count(_pk42)
                _need42 = attack_energy_minimum(_pk42)
                if _need42 and _n42 == _need42:
                    return 30000   # ちょうど攻撃圏の体から1個折る=次の攻撃を止める
                return 8000
    if isinstance(card, Pokemon):
        return switch_score(card, player_index, me, opponent, state, wall_mode, ko_mode)
    return card_keep_value(cid, me, opponent, state, wall_mode, ko_mode)


# --- サイド落ち台帳 (go指示 2026-08-08) ---
# 原理: 自分のデッキ60枚は既知(_MY_DECK_60)。山サーチで山の全リストが見えた瞬間、
#   60枚 − 手札 − トラッシュ − 場(進化元/エネ/どうぐ込み) − 自スタジアム − 表向きサイド − 山
#   = 裏向きサイドの中身、が枚数まで完全に確定する。
#   実証: ep90718153 step31(ポフィン)/step33(ポケパッド)で真値と完全一致。
# 適用範囲: select.deck が存在し、かつ枚数が自分の deckCount と完全一致する時のみ
#   (上からN枚だけ見る効果では確定できないので何もしない)。
# 危険条件の手当:
#   - 解決中のトレーナー(このステップの PLAY ログの札)は手札にも捨て札にもいない
#     宙ぶらりん状態(実測)。まず補正なしで枚数照合し、合わない時だけ補正して再照合。
#     どちらも裏向きサイド枚数と一致しなければコミットしない(誤った確定より無知が安全)
#   - 同一プロセスで複数試合を回すローカルリーグ対策: turn が前回観測より小さくなったら
#     新しい試合とみなして台帳をリセット(試合内で turn は減らない)
#   - 台帳は補助情報なので例外は全て握りつぶす。本体の採点を絶対に落とさない
_PRIZE_LEDGER = {"turn": -1, "prizes": None}


def _reset_prize_ledger() -> None:
    _PRIZE_LEDGER["turn"] = -1
    _PRIZE_LEDGER["prizes"] = None


def _visible_own_counts(state, me) -> dict:
    """自分の札のうち中身が見えているもの(手札/捨て札/場/自スタジアム/表サイド)を数える。"""
    visible = defaultdict(int)
    for c in (me.hand or []):
        visible[c.id] += 1
    for c in (me.discard or []):
        visible[c.id] += 1
    for p in (me.active or []) + (me.bench or []):
        if p is None:
            continue
        visible[p.id] += 1
        for c in (getattr(p, "energyCards", None) or []) + \
                 (getattr(p, "tools", None) or []) + \
                 (getattr(p, "preEvolution", None) or []):
            visible[c.id] += 1
    for c in (state.stadium or []):
        if getattr(c, "playerIndex", None) == state.yourIndex:
            visible[c.id] += 1
    for c in (me.prize or []):
        if c is not None:
            visible[c.id] += 1
    return visible


def update_prize_ledger(obs) -> None:
    """毎select呼ぶ。山の全リストが見えた瞬間にサイドの中身を差し引きで確定して覚える。"""
    try:
        state = obs.current
        if state is None:
            return
        turn = state.turn
        if turn < _PRIZE_LEDGER["turn"]:
            _reset_prize_ledger()
        _PRIZE_LEDGER["turn"] = turn

        deck_view = getattr(obs.select, "deck", None) if obs.select is not None else None
        if not deck_view:
            return
        me = state.players[state.yourIndex]
        if len(deck_view) != me.deckCount:
            return

        visible = _visible_own_counts(state, me)
        facedown = sum(1 for c in (me.prize or []) if c is None)
        deck_counts = defaultdict(int)
        for c in deck_view:
            deck_counts[c.id] += 1

        def _infer(extra):
            prizes = {}
            total = 0
            for cid, n in _MY_DECK_60.items():
                rest = n - visible.get(cid, 0) - deck_counts.get(cid, 0) - extra.get(cid, 0)
                if rest < 0:
                    return None
                if rest > 0:
                    prizes[cid] = rest
                    total += rest
            return prizes if total == facedown else None

        prizes = _infer({})
        if prizes is None:
            # 宙ぶらりん補正: このステップでプレイされた自分のトレーナー(LogType.PLAY=10)
            limbo = defaultdict(int)
            for lg in (obs.logs or []):
                if getattr(lg, "type", None) == 10 and \
                        getattr(lg, "playerIndex", None) == state.yourIndex:
                    limbo[lg.cardId] += 1
            if limbo:
                prizes = _infer(limbo)
        if prizes is not None:
            _PRIZE_LEDGER["prizes"] = prizes
    except Exception:
        pass


def prize_ledger_known() -> bool:
    return _PRIZE_LEDGER["prizes"] is not None


def confirmed_prized(card_id: int):
    """確定済みならサイドにある枚数(0=サイド落ちなし)。未確定なら None。"""
    p = _PRIZE_LEDGER["prizes"]
    return None if p is None else p.get(card_id, 0)


def deck_alive_count(card_id: int, state, me):
    """山に生きている枚数の保守的な見積もり(下限)。未確定なら None。

    未見枚数(60枚−見えている札)からサイド確定分を引く。サイドが後で取られても
    確定分を引き続けるため常に下限側に倒れる(「山にある」と言った時は必ずある)。
    """
    p = _PRIZE_LEDGER["prizes"]
    if p is None:
        return None
    visible = _visible_own_counts(state, me)
    unseen = _MY_DECK_60.get(card_id, 0) - visible.get(card_id, 0)
    return max(0, unseen - p.get(card_id, 0))


def _lillie_confirmed_outs_bonus(me, state) -> int:
    """教え8a(2026-08-08 go承認「1から着手」): 欲しい札が山に確実に生きていると
    台帳で確定している時、リーリエのドロー価値を上げる。

    適用範囲: リーリエのPLAY採点で既にプラス分岐(>=20000)が発火している時のみ加算。
      ガード(取り切り/寿命の-5000)や弱い分岐(3000/12000)には触らない。
    欠品の定義(今回は入れ替えのみ): ベンチにエネ2枚以上のアタッカー(イワパレス/キバ)が
      座っていて、前のエネがそれ未満(=前を替えたい盤面)。かつ入れ替えを手札に未所持。
    危険条件の手当: deck_alive_count は下限保証(「ある」と言ったら必ずある)。
      未確定(None)や下限0では加点しない。ブーストのみで減点はしない
      (素点負=探索除外の事故を避ける)。例外時は0(本体を落とさない)。
    """
    try:
        alive = deck_alive_count(SWITCH, state, me)
        if not alive:
            return 0
        if count_in_hand(me, SWITCH):
            return 0
        act = active_pokemon(me)
        if act is None:
            return 0
        bench_best = 0
        for p in (me.bench or []):
            if p is not None and p.id in (CRUSTLE, GREAT_TUSK):
                bench_best = max(bench_best, attached_energy_count(p))
        if bench_best >= 2 and attached_energy_count(act) < bench_best:
            return 12000
        return 0
    except Exception:
        return 0


def _agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()

    state = obs.current
    select = obs.select
    context = select.context
    me = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    update_prize_ledger(obs)
    _ROUTE_STATE["behind_prizes"] = len(me.prize or []) > len(opponent.prize or [])
    wall_mode = should_wall_mode(me, opponent, state)
    ko_mode = should_ko_mode(me, opponent, state)
    update_route(me, opponent, state)
    active = active_pokemon(me)

    _ROUTE_STATE["_emg_energy_used"] = False
    scores = []
    for option in select.option:
        score = 0
        if context == SelectContext.MAIN:
            if option.type == OptionType.PLAY:
                card = get_card(obs, AreaType.HAND, option.index, state.yourIndex)
                if card is not None:
                    score = play_score(card.id, me, opponent, state, wall_mode, ko_mode)
            elif option.type == OptionType.EVOLVE:
                # このデッキの進化はイシズマイ→イワパレスのみ(2026-08-01: 他進化系統は
                # デッキに存在せず発火しないため掃除。lo_crustle_weakmath_v1限定)
                score = 90000
                if wall_mode:
                    score += 40000
                if opponent_chips_board(opponent):
                    # 教えA(2026-07-31解剖): 狙撃対面の進化は「壁」でなく「狙撃耐性」。
                    # 他の行動(サーチ/妨害)より常に先に立てる
                    score += 60000
                # go教示(2026-08-01): イワパレスのにげるコスト(3)はイシズマイ(2)より
                # 重く、進化はエネルギーを増やさない。相手の山が薄く(詰みが近く)、
                # ベンチにいだいなきばがいる時に進化すると、今のエネルギーでは
                # にげるコストを払えなくなり、いだいなきばへの交代=Land Collapseでの
                # 詰めを封じてしまう。route判定には頼らない(実測: 同一ターン内で
                # deck_out→prizeに切り替わり条件が外れるケースを確認した2026-08-01)。
                # 詰めの一撃(EXPLORER_GUIDANCEの520000分岐)と同じ山4枚基準に少し
                # 余裕を持たせ、進化を後回しにする
                if (opponent.deckCount <= 6
                        and active is not None and active.id == DWEBBLE
                        and attached_energy_count(active) < CARD_TABLE[CRUSTLE].retreatCost
                        and any(p.id == GREAT_TUSK for p in me.bench)):
                    score = -10000
            elif option.type == OptionType.ATTACH:
                card = get_card(obs, option.area, option.index, state.yourIndex)
                target = get_card(obs, option.inPlayArea, option.inPlayIndex, state.yourIndex)
                if card is not None:
                    score = attach_score(card.id, target, option.inPlayArea, me, opponent, wall_mode, ko_mode)
                    # 修正(go指摘 2026-08-09 ep91293332): むずがゆかふんのコストは空(0エネ)。
                    # 旧「ロック起動弾176000」はカード知識の誤りで、装着権を丸ごと浪費していた。
                    # スボミーへの装着は常に-3000(attach_score側)に統一
            elif option.type == OptionType.ABILITY:
                # タツゴロー/デュラントex/ルナトーンはこのデッキに未採用のため掃除
                # (2026-08-01)。実測で出るのは相手のスタジアム(スパイクスタウンジム等)の
                # 共有特性で、うちのデッキに検索対象がないため実質無価値=フィラー据え置き
                score = 12000
            elif option.type == OptionType.RETREAT:
                _atk_ok = active is not None and any(
                    can_pay_attack(active, _aid)
                    for _aid in getattr(CARD_TABLE.get(active.id), "attacks", []) or [])
                _rc0 = (getattr(CARD_TABLE.get(active.id), "retreatCost", 0) or 0) if active is not None else 0
                _win_line = False
                _oa2 = active_pokemon(opponent)
                if _oa2 is not None:
                    _worth = 2 if is_ex_pokemon(_oa2) else 1
                    for _bp in (me.bench or []):
                        if _bp is None:
                            continue
                        _bd = CARD_TABLE.get(_bp.id)
                        for _ba in (getattr(_bd, "attacks", []) or []):
                            _bat = ATTACK_TABLE.get(_ba)
                            if _bat is None or not can_pay_attack(_bp, _ba):
                                continue
                            _dmg2 = typed_damage(getattr(_bat, "damage", 0) or 0, _bp.id, _oa2.id)
                            if _dmg2 >= (_oa2.hp - damage_on(_oa2)) and len(me.prize or []) <= _worth:
                                _win_line = True
                if _atk_ok and _rc0 >= 2 and not _win_line:
                    # go指摘(2026-08-07 ep90386436): 攻撃成立中の重コスト退却=自壊。
                    # 例外=勝ち筋(go裁定: ベンチの体で前を取り切って勝てる時)
                    scores.append(-8000)
                    continue
                neutral_tusk = (
                    active is not None
                    and active.id == GREAT_TUSK
                    and state.stadium
                    and state.stadium[0].id == NEUTRAL_CENTER
                )
                if (wall_mode and not neutral_tusk and any(
                        p.id == CRUSTLE and (
                            scissors_ready(p, me, opponent)
                            or attached_energy_count(p) + 1 >= crustle_energy_need(p, me, opponent))
                        for p in me.bench)):
                    # 教え52(go承認 2026-08-14 ep92934691): 壁対面のイワパレス前出しは
                    # 「はさみ即撃ち可 or 装着1回で完成」の個体がいる時だけ。
                    # 丸腰イワパレスを差し出してスボミーのロックを手放したT4の敗着根治
                    score = 130000
                elif ready_tusk_on_bench(me):
                    score = 125000
                # go指摘(2026-08-02 ep89516872): 「にげる」はコストのエネを捨てる行為。
                # 3エネ払いの退却=主砲の解体で、後ろに何がいようとほぼ常に損
                # (入れ替え札ならコスト0なので対象外=SWITCHはPLAY側で別評価)。
                # 退却コスト分を必ず差し引く: rc2=-84000 / rc3=-126000
                if active is not None and score > 0:
                    _rc = getattr(CARD_TABLE.get(active.id), "retreatCost", 0) or 0
                    if _rc >= 2:
                        score -= 42000 * _rc
                elif active is not None and active.id == GREAT_TUSK and not can_pay_attack(active, LAND_COLLAPSE):
                    # Do not leave a useless Great Tusk active if legal retreat exists.
                    score = 70000
                elif active is not None and active.id == TATSUGIRI and (state.supporterPlayed or count_in_hand(me, EXPLORER_GUIDANCE) > 0):
                    score = 36000
                else:
                    score = -10000
            elif option.type == OptionType.ATTACK:
                # 「技未確定(attackId=None)」の汎用ボタン分岐は掃除(2026-08-01)。
                # 実測(loss_autopsy約200ターン分)でattackId=Noneは一度も出現せず、
                # エンジンは常に具体的な技IDを選択肢に出す。ソルルナ型(SOLROCK/LUNATONE)
                # 向けの分岐も含め死んだコードだった
                score = attack_score(option.attackId, me, opponent, state, wall_mode, ko_mode)
            elif option.type == OptionType.END:
                score = -100
            else:
                score = 1000
        elif option.type == OptionType.CARD:
            card = get_card(obs, option.area, option.index, option.playerIndex)
            score = select_card_score(card, option.playerIndex, context, me, opponent, state, wall_mode, ko_mode)
        elif option.type == OptionType.YES:
            effect = select.effect or select.contextCard
            score = 100
            if select.context == SelectContext.IS_FIRST:
                # 先攻選択(go教示+rc8切り分けで確定): 削りレース主要対面(オーロンゲ+2.0/
                # ラダーフーディン+4.3/自作フーディン+9.4)で先攻が優位。コントロール系の
                # -5pt前後は転換条件の修正(rc9)で相殺する読み。「攻撃回数=命」
                score = 2000
            if effect is not None and effect.id in (FIGHT_GONG, ULTRA_BALL, BUG_CATCHING_SET, POKEGEAR_30, ROTO_STICK, EXPLORER_GUIDANCE, TATSUGIRI):
                score = 2000
        elif option.type == OptionType.NO:
            score = 0
            if select.context == SelectContext.IS_FIRST:
                score = -1000
        elif option.type == OptionType.NUMBER:
            n = option.number or 0
            if context == SelectContext.DRAW_COUNT:
                # Do not over-protect deck if drawing/searching unlocks Tusk mill.
                score = -10 * n
                if not has_ready_tusk(me) and me.deckCount > 8:
                    score += 18 * n
            elif context in (SelectContext.DAMAGE_COUNTER_COUNT, SelectContext.REMOVE_DAMAGE_COUNTER_COUNT):
                score = n if ko_mode else -n
            else:
                score = n
        elif option.type in (OptionType.ENERGY, OptionType.ENERGY_CARD, OptionType.TOOL_CARD):
            score = option.count or 0
            owner = getattr(option, "playerIndex", None)
            if owner is not None and owner != state.yourIndex:
                holder = get_card(obs, option.area, option.index, owner)
                if holder is not None:
                    need = attack_energy_minimum(holder)
                    have = attached_energy_count(holder)
                    if 0 < need < 99:
                        score += int(6000 * min(1.5, have / need))
                    holder_data = CARD_TABLE.get(holder.id)
                    if holder_data is not None and getattr(holder_data, "evolvesTo", None):
                        # 進化前へのエネはメガ進化アタッカーの燃料。優先で折る。
                        score += 2500
                    if holder.id in (LUNATONE, SOLROCK):
                        # 相手のドロー/チップエンジンの足も折る(goの実戦2戦共通)
                        score += 2000
                    if holder.id == 112 and opponent_chips_board(opponent):
                        # go教示(2026-08-07): チップ対面のエネ割りの的はマシマシラ最優先。
                        # 悪エネが無いとアドレナブレイン(ダメカン輸送)が撃てない=特性停止。
                        # 2026-08-09 ep91217113: +8000では前ベロバー(バトル場+3000/進化前
                        # +2500/充足率)に1000点差で負けた→16000に増額し序列を確定させる
                        score += 16000
                if option.area == AreaType.ACTIVE:
                    score += 3000
        elif option.type == OptionType.ATTACK:
            score = attack_score(option.attackId, me, opponent, state, wall_mode, ko_mode)
        elif option.type == OptionType.SKILL:
            score = 100
        else:
            score = 0
        scores.append(score)

    # 教え55(go承認 2026-08-14): 詰めルームの自傷ディグ封鎖(決定論ゲート)。
    # 自山6枚以下×攻撃可能な体がいる時、自分の山を消費するプレイ(探検家/リーリエ/
    # ギア/むしとり/パッド)は、詰めの一撃(50万点級)でない限り素点負=探索からも禁止。
    # 根拠: ep92920526(自山3で探検家→自山0→自滅)。攻撃できるなら殴って待つのが常に上
    if context == SelectContext.MAIN and me.deckCount <= 6:
        _can_atk55 = any(o5.type == OptionType.ATTACK for o5 in select.option)
        if _can_atk55:
            _dig_ids55 = {EXPLORER_GUIDANCE, LILLIE_RESOLVE, POKEGEAR_30, BUG_CATCHING_SET, POKE_PAD}
            for _i55, (_o55, _s55) in enumerate(zip(select.option, scores)):
                if (_o55.type == OptionType.PLAY and _o55.index is not None
                        and _o55.index < len(me.hand or [])
                        and getattr(me.hand[_o55.index], "id", None) in _dig_ids55
                        and 0 < _s55 < 500000):
                    scores[_i55] = -4000

    # 禁じ手ガード用は「攻撃保留の減点前」の素点を公開する(2026-08-04切り分けで確定:
    # 減点後の値を使うと攻撃がターンの大半で探索候補から消え、オーロンゲ-17.5pt)
    globals()["last_option_scores"] = list(scores)

    _win_idxs = []
    _imm_win = []
    if context == SelectContext.MAIN:
        # リーサル安全網(nn-features監査 2026-08-12統合): 即勝利手+とどめ算数290000以上は
        # 攻撃保留バーの-100万減点から除外し、存在すれば強制選択する。
        # 教え33との整合: 即勝利は装着より優先(ゲームが終わる)。勝ちきらないとどめは
        # 装着権の消化後に強制選択(装着→とどめの順で両方できる)
        _imm_win = list(_immediate_win_attack_idxs(select, me, opponent, state))
        _win_idxs = list(_imm_win)
        for i2, (o2, s2) in enumerate(zip(select.option, scores)):
            if o2.type == OptionType.ATTACK and s2 >= 290000 and i2 not in _win_idxs:
                _win_idxs.append(i2)

        # go教示(2026-08-06 ep90314751): リーリエ(手札を山へ戻す)より先に、
        # 手札から置ける物(エネ装着/進化/たね出し)を消化する。
        # 戻した後にエネを引き直せる保証はないから
        _lidx = [i2 for i2, o2 in enumerate(select.option)
                 if o2.type == OptionType.PLAY and o2.index is not None
                 and o2.index < len(me.hand or [])
                 and getattr(me.hand[o2.index], "id", None) == LILLIE_RESOLVE]
        if _lidx:
            _placeable = [scores[i2] for i2, o2 in enumerate(select.option)
                          if (o2.type in (OptionType.ATTACH, OptionType.EVOLVE)
                              or (o2.type == OptionType.PLAY and o2.index is not None
                                  and o2.index < len(me.hand or [])
                                  and (getattr(CARD_TABLE.get(getattr(me.hand[o2.index], "id", 0) or 0), "hp", None)
                                       or getattr(me.hand[o2.index], "id", 0) in (CRUSHING_HAMMER, ENHANCED_HAMMER))))
                          and scores[i2] > 0]
            if _placeable:
                for i2 in _lidx:
                    scores[i2] = min(scores[i2], max(_placeable) - 1)

        # goの指し順: 展開/装着/特性/サポートを全て済ませてから攻撃する。
        # 攻撃はターンを終了させるため、有用な非攻撃プレイが残る限り保留。
        best_nonattack = max(
            (s for o, s in zip(select.option, scores) if o.type not in (OptionType.ATTACK, OptionType.END)),
            default=-10**9,
        )
        # ミラーでは低価値プレイでターンを引き延ばすと自山を余計に消費する。
        # 重要プレイのみ攻撃より先。それ以外は攻撃してターンを畳む。
        # 2026-07-31 A/Bで検証: バーを85000に上げたところ短期戦8.3%(旧23.5%)/
        # 総合35.0%(旧41.7%)に悪化(n=60each)。「フィラーは攻撃を止めるな」という
        # 仮説は誤りで、18000〜85000帯のプレイ(ポケパッド在庫確認等)は実際には
        # 攻撃より優先すべき価値を持っていた。18000に戻す。要再診断。
        attack_hold_bar = 100000 if GREAT_TUSK in opponent_visible_ids(opponent) else 18000  # ミラーはエネ装着のみ攻撃より先
        # 教え33(go裁定 2026-08-12 ep92042351 T7/T9): 「攻撃は一番最後」。装着権は
        # そのターン限りで失効するので、未使用×正点の装着があるならバーの高さに関係なく
        # 攻撃を待たせる(装着→攻撃の順で同じ攻撃ができる。失うものはゼロ)
        _pending_attach = (not state.energyAttached and any(
            o2.type == OptionType.ATTACH and s2 > 0
            for o2, s2 in zip(select.option, scores)))
        globals()["_PENDING_ATTACH"] = _pending_attach
        if best_nonattack >= attack_hold_bar or _pending_attach:
            scores = [
                s if (o.type == OptionType.ATTACK and i2 in _win_idxs
                      and (i2 in _imm_win or not _pending_attach)) else
                (s - 1_000_000 if o.type == OptionType.ATTACK else s)
                for i2, (o, s) in enumerate(zip(select.option, scores))
            ]
        if best_nonattack >= 100000:
            # 教え54(go承認 2026-08-14 ep92938485): 10万点級の必須プレイ(ボス130000等)が
            # 未消化の間、攻撃(=ターン終了)はとどめ以外を「素点負」にして探索からも封鎖する。
            # 攻撃はターンを終える構造上、必須プレイ先行は常に得(ボス→攻撃で両方できる)。
            # 現行犯: ルールがボスを選んだのに探索が攻撃で上書き→マシマシラ狩りを逃した
            _los = globals().get("last_option_scores")
            if isinstance(_los, list) and len(_los) == len(scores):
                for _i54, _o54 in enumerate(select.option):
                    if (_o54.type == OptionType.ATTACK and _i54 not in _win_idxs
                            and _los[_i54] > 0):
                        _los[_i54] = -1000

    _pending_attach_flag = bool(globals().get("_PENDING_ATTACH")) if context == SelectContext.MAIN else False
    _force_now = [i2 for i2 in _win_idxs
                  if i2 in _imm_win or not (context == SelectContext.MAIN and _pending_attach_flag)]
    if _force_now:
        globals()["last_option_scores_final"] = list(scores)
        globals()["_FORCED_WIN_MOVE"] = True
        return [_force_now[0]]
    globals()["_FORCED_WIN_MOVE"] = False
    globals()["last_option_scores_final"] = list(scores)  # PUCT prior用(減点込み)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    result = []
    for index in order:
        if len(result) >= select.maxCount:
            break
        if scores[index] >= 0 or len(result) < select.minCount:
            result.append(index)
    return result


_MY_DECK_60 = {58: 4, 344: 4, 345: 4, 235: 1, 1152: 4, 1120: 2, 1123: 3, 1086: 1, 1094: 2, 1168: 2, 1122: 2, 1097: 1, 1185: 4, 1227: 4, 1182: 3, 1197: 2, 1264: 2, 1247: 1, 11: 2, 1: 6, 20: 4, 1147: 2}


def _immediate_win_attack_idxs(select, me, opponent, state) -> list[int]:
    """「今すぐ勝てる合法手」の最終安全網(go指示 2026-08-11 nn-features監査対応)。

    背景: attack_score()の「とどめ算数」(295000点)は、①同ターン内で他の非攻撃プレイ
    (退却/進化/装着など)が18000点(ミラーは100000点)以上ある場合、後段の
    attack_hold_bar処理で全ATTACK選択肢が一律-1,000,000点される保留ロジックに
    巻き込まれて握りつぶされる、②その後のPUCT探索側の統計判定でも上書きされ得る、
    という2つの経路で無効化される余地があった。とりわけ①は「にげる」が130000点/
    125000点と高く出る局面で、今使っているアクティブ(=とどめの技を持つ本人)を
    にげさせてしまうと、次の手番ではもうそのKOを取り直せない(退却後のポケモンは
    別の技しか持たない)という取り返しのつかない見逃しを生み得る。

    ここでは「このKOを取ればこのターン中に自分の残りサイドが0になる=即勝利」という
    最も狭くて安全な条件だけを判定し、該当すればあらゆるスコアリング/保留/探索より
    先に確定選択する。KOではあるが即勝利ではない(サイドがまだ残る)ケースは対象外
    ―― そちらは戦略的に攻撃を保留する価値が本当にある場合もあるため、この安全網では
    触らない。
    """
    try:
        if select is None or select.context != SelectContext.MAIN:
            return []
        active = active_pokemon(me)
        opp_active = active_pokemon(opponent)
        if active is None or opp_active is None:
            return []
        my_prizes_left = len(me.prize or [])
        if my_prizes_left <= 0:
            return []
        od = CARD_TABLE.get(opp_active.id)
        ad = CARD_TABLE.get(active.id)
        if od is None:
            return []
        worth = 3 if getattr(od, "megaEx", False) else (2 if getattr(od, "ex", False) else 1)
        if my_prizes_left > worth:
            return []  # このKOだけでは取り切れない=即勝利ではない
        hp = getattr(od, "hp", None) or 999
        if state.stadium and state.stadium[0].id == LIVELY_STADIUM and getattr(od, "stage", None) in (None, 0):
            hp += 30
        hp = max(hp, getattr(opp_active, "maxHp", 0) or 0)
        dmg_on = damage_on(opp_active)
        idxs = []
        for i, o in enumerate(select.option):
            if o.type != OptionType.ATTACK or not o.attackId:
                continue
            if not can_pay_attack(active, o.attackId):
                continue
            atk = ATTACK_TABLE.get(o.attackId)
            base = (getattr(atk, "damage", 0) or 0) if atk is not None else 0
            if base <= 0:
                continue
            if typed_damage(base, active.id, opp_active.id) + dmg_on >= hp:
                idxs.append(i)
        return idxs
    except Exception:
        # 安全網自身は絶対に例外で本体のフォールバック(ランダム選択)を誘発しない
        return []



def _track_observation(obs_dict):
    """毎観測の頭の中の更新(go設計 2026-07-28):
    ①相手の公開イベント(MOVE_CARD/PLAY/ATTACH等)をシリアル番号で厳密追跡
      → 残り札カウンタが「見せて手札に加えた札」も含めて正確になる
    ②自分のサーチ時のselect.deck(山の全公開)からサイド落ち6枚を特定"""
    cur = obs_dict.get('current') or {}
    yi = int(cur.get('yourIndex', 0) or 0)
    t = int(cur.get('turn', 0) or 0)
    if t <= 1 and _ROUTE_STATE.get('_trk_turn', 99) > 1:
        for k in ('opp_known', 'my_prizes_known', 'my_deck_known'):
            _ROUTE_STATE.pop(k, None)
    _ROUTE_STATE['_trk_turn'] = t
    opp = 1 - yi
    known = _ROUTE_STATE.setdefault('opp_known', {})
    hand_known = _ROUTE_STATE.setdefault('opp_hand_known', {})
    # 公開ログイベント(シリアル→カードID)。toArea=HAND(2)なら確定手札として追跡
    for ev in (obs_dict.get('logs') or []):
        if ev.get('playerIndex') == opp and ev.get('cardId') and ev.get('serial') is not None:
            known[ev['serial']] = ev['cardId']
            if ev.get('type') == 6 and ev.get('toArea') == 2:
                hand_known[ev['serial']] = ev['cardId']   # 見せて手札に加えた札
            elif ev.get('type') in (10, 11, 12) or ev.get('toArea') in (3, 4, 5, 7):
                hand_known.pop(ev['serial'], None)         # 使われた/移動した
    # 相手の場・トラッシュ(常時公開، シリアル付き)
    pls = cur.get('players') or []
    if len(pls) > opp:
        op = pls[opp]
        for c in (op.get('discard') or []):
            if c.get('serial') is not None and c.get('id'):
                known[c['serial']] = c['id']
                hand_known.pop(c['serial'], None)
        for pk in (op.get('active') or []) + (op.get('bench') or []):
            if not pk:
                continue
            if pk.get('serial') is not None and pk.get('id'):
                known[pk['serial']] = pk['id']
                hand_known.pop(pk['serial'], None)
            for pe in (pk.get('preEvolution') or []):
                if isinstance(pe, dict) and pe.get('serial') is not None and pe.get('id'):
                    known[pe['serial']] = pe['id']
            for e_ in (pk.get('energyCards') or []):
                if isinstance(e_, dict) and e_.get('serial') is not None and e_.get('id'):
                    known[e_['serial']] = e_['id']
    # 教え25台帳: ベンチのキバに付く特殊エネ数のターン頭基準値と現在値
    if len(pls) > yi:
        _n_sp25 = 0
        for pk in (pls[yi].get('bench') or []):
            if pk and pk.get('id') == GREAT_TUSK:
                _n_sp25 += sum(1 for e_ in (pk.get('energyCards') or [])
                               if isinstance(e_, dict)
                               and e_.get('id') in (MIST_ENERGY, ROCK_FIGHTING_ENERGY))
        if _ITCHY_LEDGER.get('turn') != t:
            _ITCHY_LEDGER['turn'] = t
            _ITCHY_LEDGER['base'] = _n_sp25
        _ITCHY_LEDGER['now'] = _n_sp25
    # 残り札 = 予測60 − 既知(シリアル厳密)
    if opponent_marnie := (set(known.values()) & {646, 647, 648, 112, 860, 104}):
        seen_counts = {}
        for cid in known.values():
            seen_counts[cid] = seen_counts.get(cid, 0) + 1
        rem = {}
        for cid, n_ in _MARNIE_DECK_PRED.items():
            left = n_ - seen_counts.get(cid, 0)
            if left > 0:
                rem[cid] = left
        _ROUTE_STATE['opp_remaining'] = rem
        _ROUTE_STATE['opp_unseen_n'] = sum(rem.values())
    # 自分の山ビュー→サイド落ち特定
    sel = obs_dict.get('select') or {}
    dk = sel.get('deck') or []
    if dk and len(pls) > yi and all((c.get('playerIndex') == yi) for c in dk[:3]):
        deck_now = {}
        for c in dk:
            if c.get('id'):
                deck_now[c['id']] = deck_now.get(c['id'], 0) + 1
        _ROUTE_STATE['my_deck_known'] = deck_now
        me = pls[yi]
        used = {}
        def _add(cid, k=1):
            if cid:
                used[cid] = used.get(cid, 0) + k
        for c in (me.get('hand') or []): _add(c.get('id'))
        for c in (me.get('discard') or []): _add(c.get('id'))
        for pk in (me.get('active') or []) + (me.get('bench') or []):
            if not pk:
                continue
            _add(pk.get('id'))
            for pe in (pk.get('preEvolution') or []):
                _add(pe.get('id') if isinstance(pe, dict) else None)  # 進化の下敷き
            for e_ in (pk.get('energyCards') or []):
                _add(e_.get('id') if isinstance(e_, dict) else None)
            for t_ in (pk.get('tools') or []):
                _add(t_.get('id') if isinstance(t_, dict) else None)
        for st_ in (cur.get('stadium') or []):
            if isinstance(st_, dict) and st_.get('playerIndex') == yi:
                _add(st_.get('id'))
        prizes = {}
        for cid, n_ in _MY_DECK_60.items():
            left = n_ - deck_now.get(cid, 0) - used.get(cid, 0)
            if left > 0:
                prizes[cid] = left
        prev = _ROUTE_STATE.get('my_prizes_known')
        if prev is not None and sum(prizes.values()) > sum(prev.values()):
            prizes = prev  # サイドは増えない: 過大計上は下敷き等の見落とし→前回値を維持
        _ROUTE_STATE['my_prizes_known'] = prizes   # サイド落ちの内訳(残り枚数分)


def agent(obs_dict: dict, configuration=None) -> list[int]:
    try:
        _track_observation(obs_dict)
    except Exception:
        pass
    try:
        return _agent(obs_dict)
    except Exception:
        if os.environ.get("DEBUG_AGENT") == "1":
            import traceback
            traceback.print_exc()
        select = obs_dict.get('select') if isinstance(obs_dict, dict) else None
        if select is None:
            return read_deck_csv()
        options = select.get('option') or []
        min_count = max(0, int(select.get('minCount', 0)))
        max_count = max(0, int(select.get('maxCount', len(options))))
        return list(range(min(min_count, max_count, len(options))))
