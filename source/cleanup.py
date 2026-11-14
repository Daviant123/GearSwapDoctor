"""
GearSwap Doctor: gear cleanup (PLAN.md A5, his plan 2026-11-13). Two lists from his bags (Steward's saved copy) and every GearSwap file of the character:
  spare    gear in the inventory or a wardrobe that no set of any file uses: it takes a slot for nothing
  stored   gear that sets name, but that sits in a bag GearSwap can't wear from (safe, storage, locker, satchel, sack, case): the set skips it
Suggestions only. Nothing is moved here, and Steward's own rule stands: wardrobe gear only ever moves between wardrobes.
"""
import os

import checks
import gs_loader

BAG_WORDS = {'inventory': 'Inventory', 'safe': 'Mog Safe', 'safe2': 'Mog Safe 2', 'storage': 'Storage', 'locker': 'Mog Locker', 'satchel': 'Mog Satchel',
             'sack': 'Mog Sack', 'case': 'Mog Case'}
KEEP_WORDS = ('ring of', 'warp', 'dim. ring', 'dimensional ring', 'capacity', 'trizek', 'echad', 'endorsement', 'facility ring', 'caliber ring', 'tavnazian ring',
              'reraise', 'raising earring', 'nexus cape', 'mecisto', 'aptitude', 'empress band', 'emperor band', 'chariot band', 'resolution ring',
              'kupofried', 'vocation ring', 'guide beret', 'sprout beret', 'cumulus masque', 'homing ring', 'return ring', 'olduum', 'maat\'s cap')


def bag_word(bag):
    if bag.startswith('wardrobe'):
        return 'Wardrobe' + (' ' + bag[8:] if bag[8:] else ' 1')
    return BAG_WORDS.get(bag, bag)


def used_by(files, items, loader=None):
    """{item id: {job}} for every piece any set of these files names (a name that isn't an item is skipped)."""
    out = {}
    for path in files:
        job = checks.job_of(path) or os.path.basename(path)
        try:
            ld = (loader or gs_loader.load)(path)
        except Exception:
            continue
        for s in ld.sets:
            for g in s['gear'].values():
                for it in items.find(g['name']):
                    out.setdefault(it['id'], set()).add(job)
    return out


def _utility(it):
    low = it['enl'].lower() + ' ' + it['en'].lower()
    return any(w in low for w in KEEP_WORDS)


def spare(bags, used, items):
    """[{'name', 'bag', 'count', 'jobs': jobs that can wear it, 'utility': a ring / cape kept for its use, not its stats}] - wearable gear in the inventory
    or a wardrobe that no set uses. Sorted by bag, then name."""
    out = []
    for bag, content in (bags or {}).items():
        if bag.startswith('_') or bag not in checks.EQUIP_BAGS:
            continue
        for iid, n in content.items():
            it = items.by_id.get(iid)
            if not it or not it.get('slots') or iid in used:
                continue
            jobs = sorted(j for j, bit in checks.JOBS.items() if it['jobs'] & (1 << bit)) if it.get('jobs') else []
            # (a weapon, shield, grip, gun or ammo is often put on by hand or by a weapon key, not by a set: said apart, not counted as spare)
            out.append({'name': it['en'], 'bag': bag, 'count': n, 'jobs': jobs, 'utility': _utility(it), 'weapon': bool(it['slots'] & 0b1111)})
    return sorted(out, key=lambda e: (e['utility'] or e['weapon'], e['bag'], e['name']))


def stored(bags, used, items):
    """[{'name', 'bag', 'jobs': the jobs whose sets name it}] - gear sets use that is only in bags GearSwap can't wear from."""
    wearable = set()
    for bag, content in (bags or {}).items():
        if not bag.startswith('_') and bag in checks.EQUIP_BAGS:
            wearable |= set(content)
    out = []
    for bag, content in (bags or {}).items():
        if bag.startswith('_') or bag in checks.EQUIP_BAGS:
            continue
        for iid in content:
            if iid in used and iid not in wearable and iid in items.by_id:
                out.append({'name': items.by_id[iid]['en'], 'bag': bag, 'jobs': sorted(used[iid])})
    return sorted(out, key=lambda e: (e['bag'], e['name']))


def spare_note(e):
    where = bag_word(e['bag'])
    if e['utility']:
        return 'no set uses it, but it looks kept for its use (warp, experience, reraise ...)'
    if e.get('weapon'):
        return 'no set names it, but weapons and ammo are often put on by hand: only spare if you never use it'
    if e['bag'].startswith('wardrobe'):
        return f'no set uses it: it holds a {where} slot (wardrobe gear only moves between wardrobes: keep one for spares, or take it out by hand)'
    return 'no set uses it: it could go to storage'


def stored_note(e):
    return f"sets of {', '.join(e['jobs'])} name it, but it is in the {bag_word(e['bag'])}: GearSwap can't wear it from there"


def summary(sp, st):
    real = [e for e in sp if not e['utility'] and not e.get('weapon')]
    return (f"{len(real)} piece(s) of armor in your inventory and wardrobes that no set uses"
            + (f" (+ {len(sp) - len(real)} weapons / utility pieces no set names)" if len(sp) != len(real) else '')
            + f"; {len(st)} piece(s) your sets name that are in storage.")
