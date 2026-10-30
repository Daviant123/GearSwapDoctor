"""
GearSwap Doctor: wsdist (Kastra's FFXI damage simulator, merged copy in ./wsdist) run without its window.

best_ws_set(job, sub, ws, owned_names, current) -> the best set wsdist finds for that weapon skill using only gear the
character owns, plus the average damage of that set and of the current one. wsdist knows gear by name (and some by
augment path: "Nyame Helm R25 B"); owned items are matched by name, and for an item with several augment paths the
one marked in wsdist as the usual one is assumed (the report says so).
"""
import contextlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402
WS_DIR = paths.WSDIST

# wsdist slot names <- GearSwap slot names
SLOT_MAP = {'main': 'main', 'sub': 'sub', 'range': 'ranged', 'ammo': 'ammo', 'head': 'head', 'neck': 'neck',
            'ear1': 'ear1', 'ear2': 'ear2', 'body': 'body', 'hands': 'hands', 'ring1': 'ring1', 'ring2': 'ring2',
            'back': 'back', 'waist': 'waist', 'legs': 'legs', 'feet': 'feet'}
GS_SLOT = {v: k for k, v in SLOT_MAP.items()}

_mods = None


def _wsdist():
    """Import wsdist from ./wsdist (once)."""
    global _mods
    if _mods is None:
        cwd = os.getcwd()
        sys.path.insert(0, WS_DIR)
        # wsdist speeds its maths up with numba; without it (not installed here) the same functions run as plain Python
        try:
            import numba  # noqa: F401
        except ImportError:
            import types
            fake = types.ModuleType('numba')
            def njit(*a, **k):
                if len(a) == 1 and callable(a[0]) and not k:
                    return a[0]
                return lambda f: f
            fake.njit = fake.jit = njit
            sys.modules['numba'] = fake
        # matplotlib: wsdist's charts only (actions.py imports it at the top); a stand-in when it isn't installed
        try:
            import matplotlib.pyplot  # noqa: F401
        except ImportError:
            import types
            mpl = types.ModuleType('matplotlib')
            plt = types.ModuleType('matplotlib.pyplot')
            mpl.pyplot = plt
            mpl.rc = lambda *a, **k: None
            sys.modules['matplotlib'] = mpl
            sys.modules['matplotlib.pyplot'] = plt
        try:                           # (GearSwap Doctor's small fixes in wsdist - see updater.FIXES)
            import updater
            updater.apply_fixes(WS_DIR)
        except Exception:
            pass
        os.chdir(WS_DIR)               # (wsdist reads item_list.csv etc. from its own folder)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                import gear, wsdist, create_player, enemies, actions
        finally:
            os.chdir(cwd)
        _mods = {'gear': gear, 'wsdist': wsdist, 'create_player': create_player, 'enemies': enemies, 'actions': actions}
    return _mods


_GIDX = None


def gear_index():
    """{lower-case item name: [wsdist gear entries]} - several entries when wsdist lists augment paths / ranks."""
    global _GIDX
    if _GIDX is None:
        g = _wsdist()['gear']
        out = {}
        for e in g.all_gear.values():
            out.setdefault(e['Name'].lower(), []).append(e)
        _GIDX = out
    return _GIDX


def pick_variant(entries, augments=None):
    """One wsdist entry for an owned item: the plain one, else the one whose augments look like the set's, else the
    highest rank listed (R25 / R30 ...)."""
    plain = [e for e in entries if e['Name2'] == e['Name']]
    if plain:
        return plain[0]
    if augments:
        text = ' '.join(augments).lower()
        for e in entries:
            tail = e['Name2'][len(e['Name']):].strip().lower()       # e.g. "r25 b" / "path a"
            if tail and all(part in text for part in tail.replace('path', '').split()):
                return e
    # (an "(night)" / "(day)" entry is the same item with time-of-day stats: use the one that always applies)
    allday = [e for e in entries if 'night' not in e['Name2'].lower()] or entries
    return sorted(allday, key=lambda e: e['Name2'])[-1]


def ws_list():
    """Weapon skills wsdist can simulate."""
    m = _wsdist()['wsdist']
    import inspect
    src = inspect.getsource(m.build_set)
    names = []
    for line in src.splitlines():
        if line.strip().startswith('"') and '":' in line and '[' in line:
            names += [x.strip().strip('"') for x in line.split('[', 1)[1].split(']')[0].split(',') if x.strip()]
    return set(names)


def enemies():
    """wsdist's preset enemies (names), for the app's Enemy menu."""
    return sorted(_wsdist()['enemies'].preset_enemies)


def _enemy(enemy_name):
    mods = _wsdist()
    cp, en = mods['create_player'], mods['enemies']
    e = dict(en.preset_enemies[enemy_name])
    enemy = cp.create_enemy({k: e[k] for k in e if k not in ('Level', 'Location', 'Name')})
    enemy.stats['Base Defense'] = e['Defense']
    enemy.stats['Magic Damage Taken'] = enemy.stats.pop('Magic DT%', 0)
    return enemy


TP_METRICS = {'time': 'Time to WS', 'damage': 'Damage dealt'}


def dt_of(player):
    """(physical, magic) damage taken of a wsdist player, as wsdist counts it: DT counts for both, each capped at -50 %,
    then the uncapped PDT2 / MDT2 / DT2 (negative numbers: -50 = takes 50 % less)."""
    st = player.stats
    pdt = max(-50, st.get('PDT', 0) + st.get('DT', 0)) + st.get('PDT2', 0) + st.get('DT2', 0)
    mdt = max(-50, st.get('MDT', 0) + st.get('DT', 0)) + st.get('MDT2', 0) + st.get('DT2', 0)
    return round(pdt, 1), round(mdt, 1)


def dt_requirement(target):
    """His numbers for a set ({'dt': 30, 'pdt': 50, 'mdt': 0}, as "% less damage") -> wsdist's (PDT, MDT) requirement
    (-50, -30): DT counts for both physical and magic. None when nothing is asked."""
    if not target:
        return None
    dt, p, m = (abs(float(target.get(k) or 0)) for k in ('dt', 'pdt', 'mdt'))
    if not (dt or p or m):
        return None
    return -min(50.0, max(dt, p)), -min(50.0, max(dt, m))


def _dt_score(it, need_p, need_m):
    """How much damage taken an item takes off where it's still needed (higher = more)."""
    p = -(it.get('PDT', 0) + it.get('DT', 0) + it.get('PDT2', 0) + it.get('DT2', 0))
    m = -(it.get('MDT', 0) + it.get('DT', 0) + it.get('MDT2', 0) + it.get('DT2', 0))
    return (p if need_p else 0) + (m if need_m else 0)


def dt_start(cp, job, sub, ml, start, check, req, abilities):
    """A starting set for a damage taken target: the set as it is when it has it already; otherwise the gear with the
    most damage taken goes into the slots (weapons stay). Returns (start, the target it can reach): when his gear can't
    reach the target, the most it can - wsdist then looks for the best set with that."""
    player = cp.create_player(job.lower(), sub.lower(), ml, gearset=dict(start), buffs={}, abilities=abilities)
    p, m = dt_of(player)
    if p <= req[0] + 0.01 and m <= req[1] + 0.01:
        return start, req
    new = dict(start)
    for _ in range(2):                                      # (twice: after the first pass, one of the two may be met)
        need_p, need_m = p > req[0] + 0.01, m > req[1] + 0.01
        if not (need_p or need_m):
            break
        taken = {}
        for slot in ('ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet'):
            pair = {'ear1': 'ear2', 'ear2': 'ear1', 'ring1': 'ring2', 'ring2': 'ring1'}.get(slot)
            best = new.get(slot)
            best_s = _dt_score(best, need_p, need_m) if best else 0
            for it in check.get(slot, []):
                if pair and it.get('Name2') == (new.get(pair) or {}).get('Name2') or it.get('Name') == taken.get(pair):
                    continue
                sc = _dt_score(it, need_p, need_m)
                if sc > best_s:
                    best, best_s = it, sc
            if best is not None:
                new[slot] = best
                taken[slot] = best.get('Name')
        player = cp.create_player(job.lower(), sub.lower(), ml, gearset=dict(new), buffs={}, abilities=abilities)
        p, m = dt_of(player)
    return new, (max(req[0], p), max(req[1], m))


def _tp_value(out, metric):
    """What to show for a TP set: seconds to the weapon skill, or damage per attack round."""
    return out[0] if metric == 'time' else out[1][0]


def best_tp_set(job, sub, owned, current, ws_tp=1000, enemy_name='Apex Toad', metric='time', ml=20, req=None, info=None):
    """The best TP (engaged) set from the owned gear (wsdist's "attack round" - Melee TP set). metric 'time': the
    seconds of auto-attacks from 0 TP to ws_tp (lower is better); 'damage': damage per attack round. Returns (best
    {slot: entry}, best value, current value). req: (PDT, MDT) the new set must reach (his numbers, dt_requirement);
    None = at least what the set has now. info (a dict) gets the damage taken: now / best / asked."""
    mods = _wsdist()
    cp, ws_mod, act = mods['create_player'], mods['wsdist'], mods['actions']
    enemy = _enemy(enemy_name)
    empty = mods['gear'].Empty
    start = {slot: current.get(slot) or empty for slot in SLOT_MAP.values()}
    check = {slot: list(owned.get(slot, [])) for slot in SLOT_MAP.values()}
    for slot in check:
        seen, uniq = set(), []
        for x in check[slot]:
            if x['Name2'] not in seen:
                seen.add(x['Name2']); uniq.append(x)
        check[slot] = uniq
        if start[slot] is not empty and all(x['Name2'] != start[slot]['Name2'] for x in check[slot]):
            check[slot].append(start[slot])
        if not check[slot]:
            check[slot] = [start[slot]]
    abilities = {'Enemy Resist Rank': 0, '99999': False, 'Aftermath': 0, 'Storm spell': 'None', 'Enhancing Skill': 0,
                 'Verbose Swaps': False}
    m = TP_METRICS.get(metric, 'Time to WS')
    cwd = os.getcwd()
    os.chdir(WS_DIR)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            player0 = cp.create_player(job.lower(), sub.lower(), ml, gearset=dict(start), buffs={}, abilities=abilities)
            now = act.average_attack_round(player0, enemy, 0, ws_tp, m)
            # keep the set's damage taken: a TP.DT set made "faster" by dropping its DT gear would be no use - the new
            # set must have at least the physical / magic DT the set has now (wsdist's PDT / MDT requirement)
            pdt, mdt = dt_of(player0)
            req_p, req_m = req if req else (min(0, pdt), min(0, mdt))
            first = start
            if req:
                first, (req_p, req_m) = dt_start(cp, job, sub, ml, start, check, req, abilities)
            best, _ = ws_mod.build_set(job.lower(), sub.lower(), ml, {}, abilities, enemy, 'None', 'None', 'attack round', ws_tp,
                                       check, dict(first), req_p, req_m, m, False, 0)
            after = act.average_attack_round(best, enemy, 0, ws_tp, m)
            dt_best = dt_of(best)
    finally:
        os.chdir(cwd)
    best_tp_set.kept_dt = (req_p, req_m) if not req else req
    if info is not None:
        info.update({'now': (pdt, mdt), 'best': dt_best, 'asked': req, 'kept': not req})
    return best.gearset, _tp_value(after, metric), _tp_value(now, metric)


def tp_set_value(job, sub, current, ws_tp=1000, enemy_name='Apex Toad', metric='time', ml=20, info=None):
    """A TP set as it is: seconds to the weapon skill (or damage per round); info gets its damage taken."""
    mods = _wsdist()
    cp, act = mods['create_player'], mods['actions']
    enemy = _enemy(enemy_name)
    empty = mods['gear'].Empty
    start = {slot: current.get(slot) or empty for slot in SLOT_MAP.values()}
    abilities = {'Enemy Resist Rank': 0, '99999': False, 'Aftermath': 0, 'Storm spell': 'None', 'Enhancing Skill': 0,
                 'Verbose Swaps': False}
    cwd = os.getcwd()
    os.chdir(WS_DIR)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            player0 = cp.create_player(job.lower(), sub.lower(), ml, gearset=dict(start), buffs={}, abilities=abilities)
            now = act.average_attack_round(player0, enemy, 0, ws_tp, TP_METRICS.get(metric, 'Time to WS'))
            if info is not None:
                info['now'] = dt_of(player0)
    finally:
        os.chdir(cwd)
    return _tp_value(now, metric)


def set_damage(job, sub, ws, current, tp=1500, enemy_name='Apex Toad', ml=20, info=None):
    """The average damage of one weapon skill with this set (wsdist's Quicklook), or raises."""
    mods = _wsdist()
    cp, act = mods['create_player'], mods['actions']
    enemy = _enemy(enemy_name)
    empty = mods['gear'].Empty
    start = {slot: current.get(slot) or empty for slot in SLOT_MAP.values()}
    abilities = {'Enemy Resist Rank': 0, '99999': False, 'Aftermath': 0, 'Storm spell': 'None', 'Enhancing Skill': 0,
                 'Verbose Swaps': False}
    cwd = os.getcwd()
    os.chdir(WS_DIR)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            player0 = cp.create_player(job.lower(), sub.lower(), ml, gearset=dict(start), buffs={}, abilities=abilities)
            now = act.average_ws(player0, enemy, ws, tp, 'melee', 'Damage dealt')
            if info is not None:
                info['now'] = dt_of(player0)
    finally:
        os.chdir(cwd)
    return now[1][0]


def best_ws_set(job, sub, ws, owned, current, tp=1500, enemy_name='Apex Toad', ml=20, req=None, info=None):
    """owned: {wsdist slot: [entries]}; current: {wsdist slot: entry}. Returns (best {slot: entry}, best damage,
    current damage) or raises. req: (PDT, MDT) the new set must reach (dt_requirement), None = no damage taken asked.
    info (a dict) gets the damage taken: now / best / asked."""
    mods = _wsdist()
    cp, en, ws_mod, act = mods['create_player'], mods['enemies'], mods['wsdist'], mods['actions']
    e = dict(en.preset_enemies[enemy_name])
    enemy = cp.create_enemy({k: e[k] for k in e if k not in ('Level', 'Location', 'Name')})
    enemy.stats['Base Defense'] = e['Defense']
    enemy.stats['Magic Damage Taken'] = enemy.stats.pop('Magic DT%', 0)
    empty = mods['gear'].Empty
    start = {slot: current.get(slot) or empty for slot in SLOT_MAP.values()}
    check = {slot: list(owned.get(slot, [])) for slot in SLOT_MAP.values()}
    for slot in check:
        # (a slot can't be offered the same ring / earring twice: wsdist keeps ring1 and ring2 apart itself)
        seen, uniq = set(), []
        for x in check[slot]:
            if x['Name2'] not in seen:
                seen.add(x['Name2']); uniq.append(x)
        check[slot] = uniq
    for slot in check:                                       # the current item is always one of the options
        if start[slot] is not empty and all(x['Name2'] != start[slot]['Name2'] for x in check[slot]):
            check[slot].append(start[slot])
        if not check[slot]:
            check[slot] = [start[slot]]
    abilities = {'Enemy Resist Rank': 0, '99999': False, 'Aftermath': 0, 'Storm spell': 'None', 'Enhancing Skill': 0,
                 'Verbose Swaps': False}
    cwd = os.getcwd()
    os.chdir(WS_DIR)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            player0 = cp.create_player(job.lower(), sub.lower(), ml, gearset=dict(start), buffs={}, abilities=abilities)
            now = act.average_ws(player0, enemy, ws, tp, 'melee', 'Damage dealt')
            dt_now = dt_of(player0)
            rp, rm = req if req else (0, 0)
            first = start
            if req:
                first, (rp, rm) = dt_start(cp, job, sub, ml, start, check, req, abilities)
            best, _ = ws_mod.build_set(job.lower(), sub.lower(), ml, {}, abilities, enemy, ws, 'None', 'weapon skill', tp,
                                       check, dict(first), rp, rm, 'Damage dealt', False, 0)
            after = act.average_ws(best, enemy, ws, tp, 'melee', 'Damage dealt')
            dt_best = dt_of(best)
    finally:
        os.chdir(cwd)
    if info is not None:
        info.update({'now': dt_now, 'best': dt_best, 'asked': req})
    return best.gearset, after[1][0], now[1][0]


def ws_skill(ws):
    """'Sword' for Savage Blade - from wsdist's own weapon skill table."""
    import inspect
    src = inspect.getsource(_wsdist()['wsdist'].build_set)
    for line in src.splitlines():
        line = line.strip()
        if line.startswith('"') and '":' in line and '[' in line:
            skill = line.split('"')[1]
            if '"' + ws + '"' in line:
                return skill
    return None


def entries_for(name, items, index):
    """wsdist entries for a GearSwap item name, through the game's short and long names."""
    out = index.get(name.lower())
    if out:
        return out
    for it in items.find(name):
        for n in (it['en'].lower(), it['enl'].lower()):
            if n in index:
                return index[n]
    return None


def plan_ws(job, sub, ws, set_gear, weapon_sets, owned_ids, items, index, bag_where=None):
    """Everything for one weapon skill set: the options per slot (owned, this job, known to wsdist), the current set
    as wsdist sees it, locked slots (the weapon, items wsdist doesn't know). Returns (owned, current, notes)."""
    import checks
    from gs_loader import SLOTS
    notes = []
    current, locked = {}, set()
    for key, g in set_gear.items():
        gs = SLOTS.get(key.lower())
        slot = SLOT_MAP.get(gs)
        if not slot or g['name'].lower() in ('empty', 'none', ''):
            continue
        ents = entries_for(g['name'], items, index)
        if ents:
            current[slot] = pick_variant(ents, g.get('augments'))
        else:
            locked.add(slot)
            notes.append(f"{g['name']} ({gs}) isn't in wsdist: kept as it is")
    # the weapon: the set's own, else the first weapon set with the right kind of weapon for this weapon skill
    skill = ws_skill(ws) if ws else None                 # (a TP set: any weapon from the weapon sets)
    if 'main' not in current:
        for wname, wg in weapon_sets:
            main = wg.get('main')
            ents = main and entries_for(main['name'], items, index)
            if ents and (ws is None or pick_variant(ents).get('Skill Type') == skill):
                current['main'] = pick_variant(ents)
                subg = wg.get('sub')
                se = subg and entries_for(subg['name'], items, index)
                if se:
                    current['sub'] = pick_variant(se)
                notes.append(f"weapon from {wname}: {main['name']}" + (f" / {subg['name']}" if se else ''))
                break
    if 'main' not in current and skill:
        # no set names one: the strongest owned weapon of that kind this job can use (DMG, then name)
        best = None
        for iid in owned_ids:
            it = items.by_id.get(iid)
            ents = it and entries_for(it['en'], items, index)
            if not ents:
                continue
            e = pick_variant(ents)
            if e.get('Skill Type') == skill and job.lower() in e['Jobs'] and e.get('Type') == 'Weapon':
                if best is None or (e.get('DMG', 0), e['Name']) > (best.get('DMG', 0), best['Name']):
                    best = e
        if best:
            current['main'] = best
            notes.append(f"no weapon set: tested with your {best['Name']}")
    locked |= {'main', 'sub', 'ranged'}                     # weapons are GearSwap's weapon sets' business
    owned = {}
    for iid in owned_ids:
        it = items.by_id.get(iid)
        if not it:
            continue
        ents = entries_for(it['en'], items, index)
        if not ents:
            continue
        e = pick_variant(ents)
        if job.lower() not in e['Jobs']:
            continue
        for slot in SLOT_MAP.values():
            if slot in locked:
                continue
            bits = checks.SLOT_BITS.get(GS_SLOT[slot])
            if bits and any(it['slots'] & (1 << b) for b in bits):
                owned.setdefault(slot, []).append(e)
    for slot in locked:
        owned[slot] = [current[slot]] if slot in current else []
    return owned, current, notes, skill
