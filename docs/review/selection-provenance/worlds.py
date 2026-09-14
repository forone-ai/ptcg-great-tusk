"""Validated, deck-list-conditional hidden worlds for frozen MAIN observations.

This is an offline mechanism experiment.  Supplying an opponent's initial deck
list is an oracle-deck condition, not information available to the submitted
agent.  Worlds satisfy card conservation and supported observation constraints;
they are NOT claimed to be the full posterior over all history-legal worlds.
No hidden cards from replay.visualize are used to construct sampled worlds.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import random


class WorldGenerationError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code, detail):
    raise WorldGenerationError(code, detail)


def _cid(card):
    if isinstance(card, dict):
        return int(card.get("id") or 0)
    return int(card or 0)


def _deck(cards, label):
    ids = [_cid(c) for c in cards]
    if len(ids) != 60 or any(c <= 0 for c in ids):
        _fail("invalid_full_deck", f"{label} needs exactly 60 positive card IDs")
    return Counter(ids)


def _subtract(pool, used, label):
    excess = used - pool
    if excess:
        _fail("card_multiset_mismatch", f"{label}: excess observed cards {dict(excess)}")
    return pool - used


def _size(player, key):
    value = player.get(key)
    if not isinstance(value, int) or value < 0:
        _fail("invalid_zone_size", f"{key}={value!r}")
    return value


def _snapshot(obs, your_index=None):
    if not isinstance(obs, dict) or not isinstance(obs.get("current"), dict):
        _fail("missing_observation", "an agent observation with current is required")
    cur = obs["current"]
    mi = cur.get("yourIndex")
    if mi not in (0, 1) or (your_index is not None and mi != your_index):
        _fail("mixed_observer_history", "all observations must have the same yourIndex")
    if len(cur.get("players") or []) != 2:
        _fail("invalid_players", "two players are required")
    return cur, mi


def _zones(obs):
    """Read authoritative card fields once, deduplicating repeated serials.

    energies contains energy TYPES, not card IDs; energyCards is authoritative.
    Generic cards/looking are deliberately not treated as additional zones.
    """
    cur, mi = _snapshot(obs)
    records = [dict(), dict()]
    counts = [{k: Counter() for k in ("outside", "hand", "deck", "prize")} for _ in range(2)]
    duplicates = 0
    anonymous = 0

    def add(card, owner, zone):
        nonlocal duplicates, anonymous
        cid = _cid(card)
        if cid <= 0:
            _fail("hidden_public_card", f"player {owner} has an unidentifiable {zone} card")
        if isinstance(card, dict):
            explicit = card.get("playerIndex")
            if explicit is not None and explicit != owner:
                _fail("card_owner_mismatch", f"serial {card.get('serial')} owner {explicit} != {owner}")
            serial = card.get("serial")
        else:
            serial = None
        if serial is not None and int(serial) > 0:
            serial = int(serial)
            if serial in records[1-owner]:
                _fail("duplicate_serial_owner", f"serial {serial} belongs to both players")
            prior = records[owner].get(serial)
            if prior is not None:
                if prior != (cid, zone):
                    _fail("duplicate_serial_conflict", f"serial {serial}: {prior} != {(cid, zone)}")
                duplicates += 1
                return
            records[owner][serial] = (cid, zone)
        else:
            anonymous += 1
        counts[owner][zone][cid] += 1

    for pi, player in enumerate(cur["players"]):
        for card in player.get("discard") or []:
            add(card, pi, "outside")
        for field in ("active", "bench"):
            for pokemon in player.get(field) or []:
                add(pokemon, pi, "outside")
                if pokemon.get("energies") and "energyCards" not in pokemon:
                    _fail("missing_energy_cards", "energy types cannot replace physical energy cards")
                for child_field in ("energyCards", "preEvolution", "tools"):
                    for card in pokemon.get(child_field) or []:
                        add(card, pi, "outside")
        for zone in ("hand", "deck", "prize"):
            for card in player.get(zone) or []:
                if _cid(card) > 0:
                    add(card, pi, zone)
    for stadium in cur.get("stadium") or []:
        if not isinstance(stadium, dict) or stadium.get("playerIndex") not in (0, 1):
            _fail("unknown_stadium_owner", "stadium must identify its owning player")
        add(stadium, stadium["playerIndex"], "outside")
    # A played Trainer is temporarily removed from hand but not yet discarded.
    # Effect source references to an already-in-play Pokemon are aliases instead.
    for field in ("effect", "contextCard"):
        card = (obs.get("select") or {}).get(field)
        if isinstance(card, dict) and _cid(card)>0:
            owner = card.get("playerIndex")
            serial = int(card.get("serial") or 0)
            if owner in (0, 1) and serial and serial not in records[owner]:
                add(card, owner, "outside")
    # select.deck is an alias of the observer's deck during a search, not a new zone.
    revealed_deck = (obs.get("select") or {}).get("deck")
    if revealed_deck is not None:
        for card in revealed_deck:
            add(card, mi, "deck")
    return counts, records, {"deduplicated_serial_aliases": duplicates,
                             "public_cards_without_serial": anonymous}


def _history_constraints(history, current, full_decks):
    """Track certified retained hand cards and own inferred prize multiset.

    Ambiguous hidden departures clear hand constraints rather than inventing
    which card left.  This relaxation is recorded and must not be described as
    full-history legality.  Transient looking/search-order effects are also not
    reconstructed.  Only the observer's own select.deck reveals its prize pool.
    """
    _, mi = _snapshot(current)
    known_hand = [dict(), dict()]
    serial_ids = {}
    prize_pool = None
    limitations = set()
    seen_frames = set()
    prior_hand_counts = [None, None]
    snapshots = list(history or []) + [current]
    processed = 0
    for obs in snapshots:
        if not isinstance(obs, dict) or not obs.get("current"):
            continue
        cur, _ = _snapshot(obs, mi)
        root_current = current["current"]
        if (isinstance(obs.get("step"), int) and isinstance(current.get("step"), int)
                and obs["step"] > current["step"]):
            _fail("future_history_observation", "history includes a step after the evaluated snapshot")
        if int(cur.get("turn") or 0) > int(root_current.get("turn") or 0):
            _fail("future_history_observation", "history includes a turn after the evaluated snapshot")
        if int(cur.get("turn") or 0) == 0:
            # Setup can contain face-down [None] Active/Bench placeholders.
            # Current MAIN snapshots remain strict; setup evidence is not used.
            limitations.add("setup_face_down_history_not_conditioned_on")
            continue
        # Replays repeat the last inactive observation. Its logs must not replay.
        frame = (obs.get("step"), cur.get("turn"), cur.get("turnActionCount"),
                 json.dumps(obs.get("logs") or [], sort_keys=True),
                 json.dumps([(p.get("handCount"), len(p.get("prize") or []))
                             for p in cur["players"]]))
        if frame in seen_frames:
            continue
        seen_frames.add(frame)
        processed += 1
        departures = [0, 0]
        for event in obs.get("logs") or []:
            owner = event.get("playerIndex")
            if owner not in (0, 1):
                continue
            serial = int(event.get("serial") or 0)
            cid = int(event.get("cardId") or 0)
            if serial and cid:
                if serial in serial_ids and serial_ids[serial] != cid:
                    _fail("history_serial_conflict", f"serial {serial} changed card identity")
                serial_ids[serial] = cid
            cid = cid or serial_ids.get(serial, 0)
            source, destination = event.get("fromArea"), event.get("toArea")
            if source == 2 and destination != 2:
                departures[owner] += 1
                if serial:
                    known_hand[owner].pop(serial, None)
                else:
                    known_hand[owner].clear()
                    limitations.add("unidentified_hand_departure_relaxes_prior_hand_constraints")
            if destination == 2 or event.get("type") == 4:  # HAND or DRAW
                if serial and cid:
                    known_hand[owner][serial] = cid
                elif cid:
                    limitations.add("unserialised_hand_reveal_not_tracked")
            if owner == mi and source == 6 and destination != 6 and prize_pool is not None:
                if cid and prize_pool[cid] > 0:
                    prize_pool[cid] -= 1
                    prize_pool += Counter()
                else:
                    prize_pool = None
                    limitations.add("unknown_prize_departure_relaxes_inferred_prize_pool")
        if cur.get("looking"):
            limitations.add("transient_looking_contents_and_order_not_conditioned_on")
        counts, records, _ = _zones(obs)
        for pi, p in enumerate(cur["players"]):
            for serial, (cid, zone) in records[pi].items():
                serial_ids[serial] = cid
                if zone != "hand":
                    known_hand[pi].pop(serial, None)
            hcount = _size(p, "handCount")
            # A hand decrease not explained by card-move logs may be a bulk reset.
            prev = prior_hand_counts[pi]
            if prev is not None and prev-hcount > departures[pi]:
                known_hand[pi].clear()
                limitations.add("unexplained_hand_decrease_relaxes_prior_hand_constraints")
            visible_hand = p.get("hand")
            if visible_hand is not None and len(visible_hand) == hcount and all(_cid(c)>0 for c in visible_hand):
                known_hand[pi] = {int(c["serial"]): _cid(c) for c in visible_hand
                                  if isinstance(c, dict) and int(c.get("serial") or 0)>0}
            else:
                for serial, (cid, zone) in records[pi].items():
                    if zone == "hand":
                        known_hand[pi][serial] = cid
            if len(known_hand[pi]) > hcount:
                known_hand[pi].clear()
                limitations.add("hand_count_conflict_relaxes_prior_hand_constraints")
            prior_hand_counts[pi] = hcount
        own = cur["players"][mi]
        deck_reveal = (obs.get("select") or {}).get("deck")
        if (deck_reveal is not None and len(deck_reveal) == own.get("deckCount")
                and all(_cid(c)>0 for c in deck_reveal)):
            used = counts[mi]["outside"] + counts[mi]["hand"] + counts[mi]["deck"]
            inferred = _subtract(full_decks[mi], used, "historical own prize inference")
            if sum(inferred.values()) == len(own.get("prize") or []):
                prize_pool = inferred
            else:
                limitations.add("incomplete_transient_snapshot_prevents_prize_inference")
        if prize_pool is not None and sum(prize_pool.values()) != len(own.get("prize") or []):
            prize_pool = None
            limitations.add("prize_count_change_without_identified_card")
    limitations.update(("opponent_action_likelihood_not_modelled",
                        "historical_draw_order_and_topdeck_constraints_not_reconstructed",
                        "not_a_proof_of_full_history_legality"))
    return {"hand": known_hand, "own_prizes": prize_pool,
            "limitations": sorted(limitations), "observations_processed": processed}


def _prepare(obs, own_deck, opponent_deck, history):
    cur, mi = _snapshot(obs)
    sel = obs.get("select") or {}
    if sel.get("context") != 0:
        _fail("unsupported_selection", "initial experiment supports MAIN (context 0) only")
    if cur.get("looking"):
        _fail("unsupported_transient_zone", "MAIN observation has nonempty looking cards")
    if cur.get("result", -1) != -1:
        _fail("terminal_snapshot", "cannot sample a finished game")
    full = [None, None]
    full[mi] = _deck(own_deck, "own_deck")
    full[1-mi] = _deck(opponent_deck, "opponent_deck")
    counts, records, validation = _zones(obs)
    hc = _history_constraints(history, obs, full)
    pools = []
    constraints = []
    for pi, p in enumerate(cur["players"]):
        sizes = {"deck": _size(p, "deckCount"), "hand": _size(p, "handCount"),
                 "prize": len(p.get("prize") or [])}
        if pi == mi and sum(counts[pi]["hand"].values()) != sizes["hand"]:
            _fail("own_hand_not_fully_visible", "own hand must be the actual observer's known hand")
        zones = {k: Counter(counts[pi][k]) for k in ("deck", "hand", "prize")}
        # Serial-keyed historical evidence supplements, never doubles current hand.
        for serial, cid in hc["hand"][pi].items():
            if serial not in records[pi]:
                zones["hand"][cid] += 1
        if pi == mi and hc["own_prizes"] is not None:
            _subtract(hc["own_prizes"], zones["prize"], "current vs inferred own prizes")
            zones["prize"] = Counter(hc["own_prizes"])
        for z in sizes:
            if sum(zones[z].values()) > sizes[z]:
                _fail("known_zone_overflow", f"player {pi} {z} known cards exceed zone count")
        all_known = counts[pi]["outside"] + sum(zones.values(), Counter())
        pool = _subtract(full[pi], all_known, f"player {pi}")
        slots = sum(sizes[z]-sum(zones[z].values()) for z in sizes)
        if sum(pool.values()) != slots:
            _fail("card_conservation_failure", f"player {pi}: unassigned cards={sum(pool.values())}, slots={slots}, outside={sum(counts[pi]['outside'].values())}")
        pools.append(list(pool.elements()))
        constraints.append({"sizes": sizes, "known": zones})
    validation.update({"card_conservation": True, "snapshot_consistent": True,
                       "full_history_legality_proven": False,
                       "conditioning": "supplied_complete_60_card_decklists",
                       "sampling_model": "uniform physical-card assignments conditional on supported constraints",
                       "history_constraints": hc["limitations"],
                       "history_observations_processed": hc["observations_processed"],
                       "known_retained_opponent_hand": len(hc["hand"][1-mi]),
                       "own_prize_multiset_inferred": hc["own_prizes"] is not None,
                       "unassigned_cards": [len(p) for p in pools]})
    return cur, mi, pools, constraints, validation


def _allocate(pool, constraint, rng, player):
    rest = list(pool)
    rng.shuffle(rest)
    result = {}
    for zone in ("hand", "prize", "deck"):
        known = list(constraint["known"][zone].elements())
        extra = constraint["sizes"][zone]-len(known)
        cards = known + rest[:extra]
        del rest[:extra]
        rng.shuffle(cards)
        # Preserve identities in publicly known positional prize slots.
        if zone == "prize":
            pending = list(cards)
            slots = list(player.get("prize") or [])
            placed = [None]*len(slots)
            for i, card in enumerate(slots):
                cid = _cid(card)
                if cid:
                    pending.remove(cid)
                    placed[i] = cid
            iterator = iter(pending)
            cards = [next(iterator) if x is None else x for x in placed]
        result[zone] = cards
    if rest:
        _fail("internal_unassigned_cards", "allocator did not consume its pool")
    return result


def make_worlds(obs, own_deck, opponent_deck, count, seed, history=None):
    """Return up to count UNIQUE worlds; raise on unsupported/inconsistent input.

    fills order: own deck, own prizes, opponent deck, opponent prizes,
    opponent hand, opponent face-down active (empty for supported MAIN states).
    A finite/small world space may return fewer worlds; metadata records this.
    """
    if not isinstance(count, int) or count < 1:
        _fail("invalid_count", "count must be a positive integer")
    cur, mi, pools, constraints, validation = _prepare(obs, own_deck, opponent_deck, history)
    rng = random.Random(seed)
    output = []
    seen = set()
    for attempt in range(max(32, count*30)):
        assignments = [_allocate(pools[i], constraints[i], rng, cur["players"][i]) for i in range(2)]
        own, opp = assignments[mi], assignments[1-mi]
        fills = [own["deck"], own["prize"], opp["deck"], opp["prize"], opp["hand"], []]
        key = hashlib.sha256(json.dumps(fills, separators=(",", ":")).encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        output.append({"id": key, "world_id": key, "fills": fills, "fills6": fills,
                       "validation": dict(validation, sampling_seed=seed, draw_index=attempt,
                                          requested_worlds=count)})
        if len(output) >= count:
            break
    for world in output:
        world["validation"]["unique_worlds_returned"] = len(output)
    return output


def extract_decklists_from_replay(replay):
    """Extract only initial 60-card deck-submission actions, never hidden order."""
    decks = [None, None]
    source_steps = [None, None]
    for step_index, step in enumerate(replay.get("steps") or []):
        if step_index > 12:
            break
        for pi, record in enumerate(step[:2]):
            action = record.get("action")
            if (isinstance(action, list) and len(action) == 60
                    and all(isinstance(x, int) and x > 0 for x in action)):
                _deck(action, f"initial deck for player {pi}")
                decks[pi] = sorted(action)  # destroy any apparent order deliberately
                source_steps[pi] = step_index
        if all(d is not None for d in decks):
            return {"decks": decks,
                    "metadata": {"source": "initial_deck_submission_actions",
                                 "source_steps": source_steps,
                                 "opponent_deck_is_oracle_side_information": True,
                                 "hidden_replay_zones_used": False}}
    _fail("initial_decklists_unavailable", "no two initial 60-card submission actions; supply validated registry lists explicitly")


def observations_for_player(replay, player_index, through_step):
    """Extract one observer's active observations, inclusive of through_step."""
    if player_index not in (0, 1):
        _fail("invalid_player", "player_index must be zero or one")
    result = []
    for step in (replay.get("steps") or [])[:through_step+1]:
        if len(step) <= player_index:
            continue
        record = step[player_index]
        obs = record.get("observation") or {}
        if record.get("status") == "ACTIVE" and obs.get("current"):
            _snapshot(obs, player_index)
            result.append(obs)
    return result
