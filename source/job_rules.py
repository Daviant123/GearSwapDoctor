"""
GearSwap Doctor: what a job needs left alone. His report 2026-11-01: "daviants gearswap for cor ... the gun keeps unequipping".

The Doctor did that. wsdist knows a gun only takes bullets ("Do not equip an ammo incompatible with your ranged weapon"), but his sets name no gun, so it saw an empty range slot and offered Ginsen,
Floestone and Oshasha's Treatise. Those put in the ammo slot take the gun off. So: a job that keeps something in the range slot never gets ammo that doesn't go with it.

  COR, RNG   always: they keep a gun, bow or crossbow on whether a set names it or not
  any job    a set (or the file) that puts something in the range slot, like a BRD's instrument
Not PUP: an animator takes its oils, and stat ammo isn't known to harm it. Not a GEO's set with no bell in it: those use stat ammo on purpose.
Which ammo is which comes from the game's own data (res\\items.lua ammo_type).
"""
RANGED_JOBS = ('COR', 'RNG')
MATCHING = ('Bullet', 'Arrow', 'Bolt')
RANGE_KEYS = ('range', 'ranged')


def _keys(gear):
    return {str(k).lower() for k in (gear or {})}


def sets_range(gear):
    """Does this set name something for the range slot?"""
    return any(g.get('name', '').lower() not in ('', 'empty', 'none') for k, g in (gear or {}).items() if str(k).lower() in RANGE_KEYS)


def file_uses_range(loaded):
    return any(sets_range(s['gear']) for s in loaded.sets)


def lock_ammo(job, gear=None, file_range=False):
    """The ammo slot is left as it is for this set: nothing new goes in."""
    if (job or '').upper() in RANGED_JOBS or file_range:
        return True
    return sets_range(gear)


def takes_gun_off(name, items):
    """True for ammo that isn't a bullet, arrow or bolt (known item only)."""
    found = items.find(name) if name else []
    if not found or name.lower() in ('empty', 'none'):
        return False
    return not found[0].get('ammo_type')


def best_bullet(loaded, items, owned_ids=None):
    """What to put back: the bullet this file uses most, else one he owns."""
    count = {}
    for s in loaded.sets:
        for k, g in s['gear'].items():
            if str(k).lower() == 'ammo':
                f = items.find(g['name'])
                if f and f[0].get('ammo_type'):
                    count[f[0]['en']] = count.get(f[0]['en'], 0) + 1
    if count:
        return max(sorted(count), key=lambda n: count[n])
    for iid in sorted(owned_ids or ()):
        it = items.by_id.get(iid)
        if it and it.get('ammo_type') in MATCHING:
            return it['en']
    return None


def ammo_problems(loaded, items, job, owned_ids=None):
    """[{'item', 'sets', 'fix'}]: ammo that takes off what this job keeps in the range slot, by item."""
    out = {}
    if (job or '').upper() not in RANGED_JOBS:
        return []
    fix = best_bullet(loaded, items, owned_ids)
    for s in loaded.sets:
        for k, g in s['gear'].items():
            if str(k).lower() == 'ammo' and takes_gun_off(g['name'], items):
                p = out.setdefault(g['name'], {'item': g['name'], 'sets': [], 'fix': fix})
                p['sets'].append(s['path'])
    return list(out.values())


def safe_edits(job, edits, items):
    """A list of edits for a file, without any that would put such ammo in (an old report's upgrade can still ask)."""
    if (job or '').upper() not in RANGED_JOBS:
        return edits
    out = []
    for e in edits:
        if e[0] == 'slots' and isinstance(e[2], dict) and 'ammo' in e[2]:
            v = e[2]['ammo']
            name = v.get('name') if isinstance(v, dict) else v
            if takes_gun_off(name, items):
                changes = {k: x for k, x in e[2].items() if k != 'ammo'}
                if not changes:
                    continue
                e = (e[0], e[1], changes) + tuple(e[3:])
        out.append(e)
    return out


def ranged_for(job, entries, items, owned_ids):
    """(what a COR or RNG keeps in the range slot, ammo for it), strongest first, from what he owns. (None, None) for anyone else, or nothing owned."""
    if (job or '').upper() not in RANGED_JOBS:
        return None, None
    kinds = {'Gun': 'Bullet', 'Bow': 'Arrow', 'Crossbow': 'Bolt'}
    guns = [e for e in entries if e.get('Type') in kinds and job.lower() in e['Jobs']]
    if not guns:
        return None, None
    gun = max(guns, key=lambda e: (e.get('DMG', 0), e['Name']))
    want = kinds[gun['Type']]
    ammo = [items.by_id[i] for i in owned_ids if items.by_id.get(i) and items.by_id[i].get('ammo_type') == want]
    return gun['Name'], (sorted(a['en'] for a in ammo)[0] if ammo else None)
