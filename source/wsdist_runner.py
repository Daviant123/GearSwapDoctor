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


def gear_index():
    """{lower-case item name: [wsdist gear entries]} - several entries when wsdist lists augment paths / ranks."""
    g = _wsdist()['gear']
    out = {}
    for e in g.all_gear.values():
        out.setdefault(e['Name'].lower(), []).append(e)
    return out


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


def set_damage(job, sub, ws, current, tp=1500, enemy_name='Apex Toad', ml=20):
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
    finally:
        os.chdir(cwd)
    return now[1][0]


def best_ws_set(job, sub, ws, owned, current, tp=1500, enemy_name='Apex Toad', ml=20):
    """owned: {wsdist slot: [entries]}; current: {wsdist slot: entry}. Returns (best {slot: entry}, best damage,
    current damage) or raises."""
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
            best, _ = ws_mod.build_set(job.lower(), sub.lower(), ml, {}, abilities, enemy, ws, 'None', 'weapon skill', tp,
                                       check, dict(start), 0, 0, 'Damage dealt', False, 0)
            after = act.average_ws(best, enemy, ws, tp, 'melee', 'Damage dealt')
    finally:
        os.chdir(cwd)
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
    skill = ws_skill(ws)
    if 'main' not in current:
        for wname, wg in weapon_sets:
            main = wg.get('main')
            ents = main and entries_for(main['name'], items, index)
            if ents and pick_variant(ents).get('Skill Type') == skill:
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
