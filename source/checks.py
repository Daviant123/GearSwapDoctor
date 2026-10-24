"""
GearSwap Doctor: what's wrong with the gear in a GearSwap file.

  unknown    the name isn't an item at all (a typo, or an old name) - with the closest real item names
  slot       the item can't go in that slot (a ring in an earring slot ...)
  job        the job this file is for can't wear it
  missing    the character doesn't have it anywhere
  stored     the character has it, but not in the inventory or a Mog Wardrobe - GearSwap can't equip it from there
  broken     a set is used but never made / the file doesn't load (from gs_loader)

The character's bags come from Steward's saved copy (addons/Steward/data/chars/<Name>.lua, kept up to date by
Steward whenever the bags change). Reads only.
"""
import difflib
import os
import re

import lupa

import paths

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWER = paths.WINDOWER or os.path.normpath(os.path.join(HERE, '..', '..', '..'))

JOBS = {'WAR': 1, 'MNK': 2, 'WHM': 3, 'BLM': 4, 'RDM': 5, 'THF': 6, 'PLD': 7, 'DRK': 8, 'BST': 9, 'BRD': 10, 'RNG': 11,
        'SAM': 12, 'NIN': 13, 'DRG': 14, 'SMN': 15, 'BLU': 16, 'COR': 17, 'PUP': 18, 'DNC': 19, 'SCH': 20, 'GEO': 21,
        'RUN': 22}
# the game's slot numbers; an earring / ring may go in either of its two slots
SLOT_BITS = {'main': [0], 'sub': [1], 'range': [2], 'ammo': [3], 'head': [4], 'body': [5], 'hands': [6], 'legs': [7],
             'feet': [8], 'neck': [9], 'waist': [10], 'ear1': [11, 12], 'ear2': [11, 12], 'ring1': [13, 14],
             'ring2': [13, 14], 'back': [15]}
EQUIP_BAGS = {'inventory', 'wardrobe', 'wardrobe2', 'wardrobe3', 'wardrobe4', 'wardrobe5', 'wardrobe6', 'wardrobe7',
              'wardrobe8'}
SKIP_NAMES = {'empty', '', 'none', 'remove'}


class Items:
    """The game's item list (Windower's res/items.lua): names -> ids, slots, jobs."""
    def __init__(self, path=None):
        path = path or os.path.join(WINDOWER, 'res', 'items.lua')
        self.by_id = {}
        self.by_name = {}
        pat = re.compile(r'^\s*\[(\d+)\] = \{(.*)\},?\s*$')
        for line in open(path, encoding='utf-8'):
            m = pat.match(line)
            if not m:
                continue
            body = m.group(2)
            cat = re.search(r'category="(\w+)"', body)
            if not cat or cat.group(1) not in ('Armor', 'Weapon'):
                continue
            en = re.search(r'(?:^|,)en="([^"]*)"', body)
            enl = re.search(r'(?:^|,)enl="([^"]*)"', body)
            if not en:
                continue
            iid, en, enl, rest = int(m.group(1)), en.group(1), enl.group(1) if enl else en.group(1), body
            f = dict(re.findall(r'(\w+)=(\d+)', rest))
            it = {'id': iid, 'en': en, 'enl': enl, 'jobs': int(f.get('jobs', 0)), 'slots': int(f.get('slots', 0)),
                  'level': int(f.get('level', 0))}
            self.by_id[iid] = it
            for n in (en.lower(), enl.lower()):
                self.by_name.setdefault(n, []).append(it)
        self.names = sorted({it['en'] for it in self.by_id.values()})

    def find(self, name):
        return self.by_name.get(name.lower(), [])

    def close(self, name, n=3):
        """The closest real item names (searching the long names too: "Hashishin Vasmak +3" -> "Hashi. Basmak +3")."""
        if not hasattr(self, '_low'):
            self._low = {}
            for it in self.by_id.values():
                self._low.setdefault(it['en'].lower(), it['en'])
                self._low.setdefault(it['enl'].lower(), it['en'])
        out = []
        for m in difflib.get_close_matches(name.lower(), list(self._low), n=n * 2, cutoff=0.75):
            if self._low[m] not in out:
                out.append(self._low[m])
        return out[:n]


def _findall_bags(character):
    """{bag: {item id: count}} from the findAll addon's saved copy (addons/findAll/data/<Name>.lua), which most players
    have - for the stand-alone GearSwap Doctor on PCs without Steward."""
    path = os.path.join(WINDOWER, 'addons', 'findAll', 'data', character + '.lua')
    if not os.path.exists(path):
        return None
    L = lupa.LuaRuntime(unpack_returned_tuples=True)
    try:
        t = L.execute(open(path, encoding='utf-8', errors='replace').read())
    except Exception:
        return None
    out = {}
    if t is None:
        return out
    for bag, items in t.items():
        if lupa.lua_type(items) != 'table':
            continue
        b = str(bag).replace(' ', '')
        content = {}
        for k, v in items.items():
            try:
                content[int(k)] = int(v)
            except (TypeError, ValueError):
                pass
        out[b] = content
    out['_time'] = int(os.path.getmtime(path))
    out['_source'] = 'findAll'
    return out


def load_bags(character, steward_chars=None):
    """{bag: {item id: count}} from Steward's saved copy (or findAll's), or None when there isn't one."""
    folder = steward_chars or os.path.join(WINDOWER, 'addons', 'Steward', 'data', 'chars')
    path = os.path.join(folder, character + '.lua')
    if not os.path.exists(path):
        return None if steward_chars else _findall_bags(character)
    L = lupa.LuaRuntime(unpack_returned_tuples=True)
    t = L.execute(open(path, encoding='utf-8').read())
    out = {}
    if t is None or t.bags is None:
        return out
    for bag, items in t.bags.items():
        out[str(bag)] = {int(k): int(v) for k, v in items.items()} if items else {}
    out['_time'] = int(t.time or 0)
    return out


def job_of(filename):
    """BLU from Name_BLU.lua / Name_Blu_Gear.lua / BLU.lua; None when the name doesn't say."""
    base = os.path.splitext(os.path.basename(filename))[0]
    for part in reversed(re.split(r'[_\-\s]', base)):
        if part.upper() in JOBS:
            return part.upper()
    return None


def check(loaded, items, bags, job=None):
    """Problems in one loaded file: [{kind, item, slot, sets: [paths], detail, fix}] - one entry per item and problem."""
    from gs_loader import SLOTS
    job = job or job_of(loaded.name)
    problems = {}

    def add(kind, item, slot, path, detail, fix=None):
        key = (kind, item.lower(), slot if kind == 'slot' else '')
        p = problems.setdefault(key, {'kind': kind, 'item': item, 'slot': slot, 'sets': [], 'detail': detail, 'fix': fix})
        if path not in p['sets']:
            p['sets'].append(path)

    if loaded.error:
        add('broken', loaded.name, '', '', "the file doesn't load - GearSwap can't use it: " + loaded.error)
    for w in loaded.warnings:
        add('broken', loaded.name, '', '', 'part of the file stops early: ' + w)
    for b in loaded.broken:
        add('broken', b['path'], '', b['path'], f"{b['path']} is used (line {b['line']}) but never made")

    where = {}
    if bags:
        for bag, content in bags.items():
            if bag.startswith('_'):
                continue
            for iid, n in content.items():
                where.setdefault(iid, set()).add(bag)

    for s in loaded.sets:
        for key, g in s['gear'].items():
            name = g['name']
            if name.lower() in SKIP_NAMES:
                continue
            slot = SLOTS.get(key.lower(), key.lower())
            found = items.find(name)
            if not found:
                close = items.close(name)
                add('unknown', name, slot, s['path'], "isn't an item" + (f" - did you mean {close[0]}?" if close else ''),
                    fix=close[0] if close else None)
                continue
            bits = SLOT_BITS.get(slot, [])
            if bits and not any(it['slots'] & (1 << b) for it in found for b in bits):
                add('slot', name, slot, s['path'], f"can't go in the {slot} slot")
            if job and job in JOBS and not any(it['jobs'] & (1 << JOBS[job]) for it in found):
                add('job', name, slot, s['path'], f"{job} can't wear it")
            if bags is not None:
                locs = set()
                for it in found:
                    locs |= where.get(it['id'], set())
                if not locs:
                    add('missing', name, slot, s['path'], "isn't in any of the character's bags")
                elif not (locs & EQUIP_BAGS):
                    add('stored', name, slot, s['path'], 'is in ' + ', '.join(sorted(locs)) +
                        " - GearSwap can only equip from the inventory or a Mog Wardrobe")
    order = {'broken': 0, 'unknown': 1, 'slot': 2, 'job': 3, 'missing': 4, 'stored': 5}
    return sorted(problems.values(), key=lambda p: (order[p['kind']], p['item'].lower()))


if __name__ == '__main__':
    import sys
    import gs_loader
    items = Items()
    for p in sys.argv[1:]:
        who = os.path.basename(p).split('_')[0].split('-')[0]
        bags = load_bags(who)
        r = gs_loader.load(p)
        probs = check(r, items, bags)
        print(f'== {r.name}: {len(r.sets)} sets, {len(probs)} problems')
        for x in probs:
            print(f"  [{x['kind']}] {x['item']} ({x['slot']}) {x['detail']}  - in {len(x['sets'])} set(s)")
