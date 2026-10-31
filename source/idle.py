"""
GearSwap Doctor: idle sets (his request 2026-10-30: "need to build in something to handle idle sets. so look and research that").
wsdist has no idle maths and doesn't read Refresh or Regen, so these are judged here, on the game's item text (healing.parse_text) and BG Wiki's rules:
  Damage taken   physical = DT + PDT, magic = DT + MDT, each stops at 50 %; the "II" kinds go past it (bg-wiki.com/ffxi/Damage_Taken)
  Movement       only the single best item counts, they don't add up (bg-wiki.com/ffxi/Movement_Speed)
  Refresh, Regen add up, MP or HP a tick. Refresh is no use to a job with no MP. (BG Wiki's pages give no cap.)
  Magic Evasion  about +2 for 1 % resist; "Magic Def. Bonus" divides magic damage, no cap
There's no number the game gives for "a good idle set", so a set is judged by what it's for: points per stat (FOCUS), taken from its name or picked by him.
"""
import re

import fixer
import healing

# points for 1 % physical / magic damage taken, 1 Refresh, 1 Regen, 1 Magic Evasion, 1 Magic Def. Bonus, 1 % movement. A set at the DT cap gets no more for
# more DT, so then the rest decides: the usual order of an idle set.
# Order from FFXIAH's forums: cap DT, then Magic Evasion ("the stat you want after capping MDT"), Refresh and Regen in what's left; movement is taste, a small tie-breaker.
FOCUS = {
    'Balanced':      {'pdt': 10, 'mdt': 10, 'refresh': 12, 'regen': 6, 'meva': 0.15, 'mdb': 0.5, 'move': 0.5},
    'Damage taken':  {'pdt': 20, 'mdt': 20, 'refresh': 1, 'regen': 1, 'meva': 0.05, 'mdb': 0.2, 'move': 0},
    'Refresh':       {'pdt': 5, 'mdt': 5, 'refresh': 100, 'regen': 6, 'meva': 0.05, 'mdb': 0.2, 'move': 0},
    'Regen':         {'pdt': 5, 'mdt': 5, 'refresh': 6, 'regen': 100, 'meva': 0.05, 'mdb': 0.2, 'move': 0},
    'Magic evasion': {'pdt': 3, 'mdt': 8, 'refresh': 1, 'regen': 1, 'meva': 1, 'mdb': 3, 'move': 0},
    'Movement':      {'pdt': 5, 'mdt': 5, 'refresh': 6, 'regen': 3, 'meva': 0.02, 'mdb': 0.1, 'move': 200},
}
STATS = ('dt', 'pdt', 'mdt', 'dt2', 'pdt2', 'mdt2', 'refresh', 'regen', 'meva', 'mdb', 'move', 'slowed')
MP_JOBS = ('WHM', 'BLM', 'RDM', 'PLD', 'DRK', 'BRD', 'SMN', 'BLU', 'SCH', 'GEO', 'RUN')
PET_WORDS = ('pet', 'avatar', 'spirit', 'luopan', 'wyvern', 'automaton')
SPECIAL = ('reraise', 'lock', 'geolock', 'nukelock', 'hp', 'evasion', 'tpeat')   # (sets with a job of their own: not what these points are about)
DEFENSE = ('pdt', 'mdt', 'dt', 'meva')
SHELL_V = 29                  # magic damage taken from Shell V (FFXIAH's guide: "you only need about 21 % from gear"; BG Wiki's WHM page has 27.34 for Shellra V)
MEVA_LOW, MEVA_IDLE = 450, 550       # gear Magic Evasion an FFXIAH poster gives for special sets and for idle / engaged sets. Others say there's no enough.


def _words(path):
    return [p.lower() for p in fixer._path_parts(path)]


def is_idle(path):
    """Idle, resting and defense sets: what you wear when you aren't acting."""
    w = _words(path or '')
    if len(w) < 2 or w[0] != 'sets':
        return False
    if w[1] == 'idle' or w[1] == 'resting':
        return not any(x in SPECIAL for x in w[2:])
    return w[1] == 'defense' and len(w) >= 3 and w[2] in DEFENSE


def is_pet(path):
    return any(x in PET_WORDS for x in _words(path or ''))


def focus_for(path):
    """What a set is for, from its name."""
    w = _words(path or '')
    if w[1:2] == ['resting'] or any(x in ('refresh', 'sphere', 'latent') for x in w):
        return 'Refresh'
    if 'regen' in w:
        return 'Regen'
    if any(x in ('town', 'kiting', 'move', 'movement', 'hippo') for x in w):
        return 'Movement'
    if any(x in ('meva', 'mdt') for x in w):
        return 'Magic evasion'
    if any(x in ('pdt', 'dt', 'weak', 'defense') for x in w):
        return 'Damage taken'
    return 'Balanced'


def has_mp(job, sub):
    return (job or '').upper() in MP_JOBS or (sub or '').upper() in MP_JOBS


def numbers(gear):
    """What a set has. gear: {slot: candidate}. Damage taken: the caps count; movement: the best item, less for one that slows you."""
    t = healing.totals(gear)
    pd, md = healing.dt_totals(t)
    moves = [c['stats'].get('move', 0) for c in gear.values() if c]
    return {'pdt': pd, 'mdt': md, 'refresh': t.get('refresh', 0), 'regen': t.get('regen', 0), 'meva': t.get('meva', 0), 'mdb': t.get('mdb', 0),
            'move': max(moves + [0]) - t.get('slowed', 0), 'over': max(0, t.get('dt', 0) + t.get('pdt', 0) - healing.CAP_DT) + max(0, t.get('dt', 0) + t.get('mdt', 0) - healing.CAP_DT)}


def value(gear, focus, base):
    """The points of a set, for what it's for."""
    w = FOCUS.get(focus) or FOCUS['Balanced']
    n = numbers(gear)
    if (base or {}).get('shell'):                         # (Shell V does the rest: more magic gear is wasted)
        n['mdt'] = min(n['mdt'], healing.CAP_DT - SHELL_V)
    v = sum(w[k] * n[k] for k in ('pdt', 'mdt', 'regen', 'meva', 'mdb', 'move'))
    if (base or {}).get('mp', True):
        v += w['refresh'] * n['refresh']
    return round(v, 3)


def words(n, base=None):
    """'damage taken 50 % / 31 %, Refresh +3, Regen +1, Magic Evasion 512, Movement 12 %'"""
    out = [f"damage taken {n['pdt']} % / {n['mdt']} %"]
    if (base or {}).get('mp', True) or n['refresh']:
        out.append(f"Refresh +{n['refresh']}")
    out += [f"Regen +{n['regen']}", f"Magic Evasion {n['meva']}", f"Magic Def. Bonus +{n['mdb']}"]
    if n['move']:
        out.append(f"Movement {n['move']} %")
    return ', '.join(out)


def useful(cands, current=None):
    """The items with something an idle set wants (the search is much quicker with only these)."""
    return [c for c in cands if any(c['stats'].get(k) for k in STATS)]


def advice(n, base=None):
    """A line about a set's numbers, from the forums' targets; '' when it has nothing to say."""
    out = []
    if n['meva'] < MEVA_IDLE:
        out.append(f"Magic Evasion {n['meva']}: FFXIAH posters aim for {MEVA_IDLE}+ in an idle set" + (f" and {MEVA_LOW} at the least" if n['meva'] < MEVA_LOW else '') + ' (no agreed cap)')
    if (base or {}).get('shell') and n['mdt'] > healing.CAP_DT - SHELL_V:
        out.append(f"with Shell V up, {healing.CAP_DT - SHELL_V} % magic from gear is enough")
    return '; '.join(out)


def judge(path, set_gear, job, sub, cands, counts, items, data, need=None, focus=None, keep_weapons=None, build=True, shell=False):
    """One idle set: {'cur', 'best', 'now', 'val', 'n_now', 'n_best', 'changes', 'focus', 'keep', 'notes', 'short', 'base'}. set_gear: the set as read from the file.
    keep_weapons None: a job that fights keeps them (a new weapon throws TP away), a mage may change them."""
    focus = focus or focus_for(path)
    base = {'mp': has_mp(job, sub), 'shell': shell}
    cur = healing.set_to_gear(set_gear, items, data)
    keys = {k.lower() for k in set_gear}
    keep = keep_weapons if keep_weapons is not None else (job or '').upper() not in healing.MAGE_JOBS
    # (anything in the range slot stays, and an instrument or bell there leaves no room for ammo)
    pool = [c for c in useful(cands) if not (({'range', 'ranged'} & keys) and healing.fits(c, 'ammo'))]
    notes = [f'judged for: {focus}']
    if keep and 'main' in keys or keep and 'sub' in keys:
        notes.append('weapons kept: a new weapon throws away your TP')
    elif keep:
        notes.append('no weapons changed: this job fights')
    if not base['mp']:
        notes.append(f'{job}/{sub} has no MP: Refresh counts for nothing')
    if is_pet(path):
        notes.append("a set for your pet: only your own numbers are counted here, not the pet's")
    n0 = numbers(cur)
    v0 = value(cur, focus, base)
    out = {'cur': cur, 'best': cur, 'now': v0, 'val': v0, 'n_now': n0, 'n_best': n0, 'changes': {}, 'focus': focus, 'keep': keep, 'notes': notes, 'short': 0, 'base': base}
    if build:
        best, val, now = healing.build('idle', pool, cur, base, job, sub, spell=focus, need=need or None, keep_weapons=keep, counts=counts)
        out.update(best=best, val=val, now=now, n_best=numbers(best), changes=healing.changes(cur, best, keep),
                   short=healing.shortfall(healing.totals(best), need or None))
    out['short_now'] = healing.shortfall(healing.totals(cur), need or None)
    return out


def checked_sets(loaded, limit=6):
    """The idle sets a check-up looks at, plainest first. Not a pet's: its numbers aren't counted."""
    paths = [s for s in loaded.sets if is_idle(s['path']) and not is_pet(s['path']) and not re.search(r'\.indi\b', s['path'], re.I)]
    paths.sort(key=lambda s: (s['path'].count('.'), len(s['path'])))
    return paths[:limit]
