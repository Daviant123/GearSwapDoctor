"""
GearSwap Doctor: one check-up of a character's GearSwap files.

  checkup(character) -> report: per file, its problems (checks.py) and, for each weapon skill set wsdist can simulate,
  the best set from the gear the character owns (wsdist_runner.py) when it's better than the current one.
  The report is saved (data/report_<Name>.json) with the time, so the app can show it and redo it once a day.
  snapshot(character): a small daily copy of the character's bags by item name (data/bags_<Name>.json), from
  Steward's saved copy - for the tests and for filling sets in.
"""
import datetime
import glob
import json
import os
import re
import time

import checks
import gs_loader

import paths

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = paths.DATA
GS_DATA = paths.gs_data() if paths.WINDOWER else os.path.normpath(os.path.join(HERE, '..', 'data'))
def ws_of(path, known):
    """The weapon skill a set is for, when it's that skill's plain set: sets.precast.WS["Savage Blade"], sets.WS.Expiacion
    (not .Acc / .Mid etc.)."""
    import fixer
    parts = fixer._path_parts(path)
    if len(parts) >= 3 and parts[-2] == 'WS' and parts[-1] in known:
        return parts[-1]
    return None


def files_for(character, folder=None):
    """The character's GearSwap files: <Name>_*.lua / <Name>-*.lua, without the shared globals / items files."""
    folder = folder or GS_DATA
    out = []
    for p in sorted(glob.glob(os.path.join(folder, character + '_*.lua')) + glob.glob(os.path.join(folder, character + '-*.lua'))):
        low = os.path.basename(p).lower()
        if low.endswith(('-globals.lua', '-items.lua')) or 'crafting' in low:
            continue
        out.append(p)
    return out


def snapshot(character, items=None, bags=None):
    """Write data/bags_<Name>.json: {time, bags: {bag: {item name: count}}} - weapons and armour only."""
    items = items or checks.Items()
    bags = bags if bags is not None else checks.load_bags(character)
    if bags is None:
        return None
    out = {'character': character, 'time': int(time.time()), 'from_steward': bags.get('_time'), 'bags': {}}
    for bag, content in bags.items():
        if bag.startswith('_'):
            continue
        named = {}
        for iid, n in content.items():
            it = items.by_id.get(iid)
            if it:
                named[it['en']] = named.get(it['en'], 0) + n
        if named:
            out['bags'][bag] = dict(sorted(named.items()))
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f'bags_{character}.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1)
    return path


def _gs_name(entry, items):
    """GearSwap's (the game's short) name for a wsdist entry: "Chevalier's Armet +3" -> "Chev. Armet +3"."""
    found = items.find(entry['Name'])
    return found[0]['en'] if found else entry['Name']


def _pairs_same(a, b):
    return sorted(x for x in a if x) == sorted(x for x in b if x)


def ws_upgrades(loaded, job, sub, owned_ids, items, index, only=None, progress=None, tp=1500, enemy='Apex Toad'):
    """[{set, ws, now, best, gain, changes: {gs slot: name}, notes}] for weapon skill sets with a better owned set."""
    import wsdist_runner as W
    known = W.ws_list()
    # weapons to test with: the weapon sets first, then any set that names one
    weapons = [(s['path'], s['gear']) for s in loaded.sets if s['path'].startswith('sets.weapons')]
    weapons += [(s['path'], s['gear']) for s in loaded.sets if not s['path'].startswith('sets.weapons') and 'main' in s['gear']]
    out = []
    for s in loaded.sets:
        ws = ws_of(s['path'], known)
        if not ws or (only and ws not in only):
            continue
        if progress:
            progress(f'wsdist: {ws}')
        if W.ws_skill(ws) in ('Archery', 'Marksmanship'):
            out.append({'set': s['path'], 'ws': ws, 'error': 'ranged weapon skills are not checked yet'})
            continue
        try:
            owned, cur, notes, skill = W.plan_ws(job, sub, ws, s['gear'], weapons, owned_ids, items, index)
            if 'main' not in cur:
                out.append({'set': s['path'], 'ws': ws, 'error': f'no {skill or "matching"} weapon {job} can use in the bags to test it with'})
                continue
            best, dmg, now = W.best_ws_set(job, sub, ws, owned, cur, tp=tp, enemy_name=enemy)
        except Exception as e:                                         # one weapon skill failing doesn't stop the rest
            out.append({'set': s['path'], 'ws': ws, 'error': f'wsdist could not simulate it: {e}'})
            continue
        for p1, p2 in (('ear1', 'ear2'), ('ring1', 'ring2')):
            w1, w2 = W.SLOT_MAP[p1], W.SLOT_MAP[p2]
            c1 = cur.get(w1, {}).get('Name') if cur.get(w1) else None
            c2 = cur.get(w2, {}).get('Name') if cur.get(w2) else None
            if best[w1]['Name'] == c2 or best[w2]['Name'] == c1:       # keep an item on the side it already is
                best[w1], best[w2] = best[w2], best[w1]
        changes = {}
        for slot, gs in W.GS_SLOT.items():
            if slot in ('main', 'sub', 'ranged'):
                continue
            a = cur.get(slot, {}).get('Name2') if cur.get(slot) else None
            b = best[slot]['Name2'] if best.get(slot) and best[slot]['Name'] != 'Empty' else None
            if b and a != b:
                changes[gs] = _gs_name(best[slot], items)
        # earrings / rings that only swapped sides aren't a change
        for p1, p2 in (('ear1', 'ear2'), ('ring1', 'ring2')):
            w1, w2 = W.SLOT_MAP[p1], W.SLOT_MAP[p2]
            cur_pair = [cur.get(w1, {}).get('Name') if cur.get(w1) else None, cur.get(w2, {}).get('Name') if cur.get(w2) else None]
            best_pair = [best[w1]['Name'] if best[w1]['Name'] != 'Empty' else None, best[w2]['Name'] if best[w2]['Name'] != 'Empty' else None]
            if _pairs_same(cur_pair, best_pair):
                changes.pop(p1, None)
                changes.pop(p2, None)
        assumed = [f"{best[sl]['Name2']}" for sl in best if best[sl]['Name2'] != best[sl]['Name'] and W.GS_SLOT.get(sl) in changes]
        if assumed:
            notes = notes + ['augment path assumed: ' + ', '.join(assumed)]
        gain = (dmg - now) / now * 100 if now else 0
        if changes and gain >= 1:
            out.append({'set': s['path'], 'ws': ws, 'now': round(now), 'best': round(dmg), 'gain': round(gain, 1),
                        'changes': changes, 'notes': notes})
    return out


def checkup(character, files=None, wsdist=True, progress=None, sub='WAR', tp=1500, enemy='Apex Toad'):
    """(sub: one sub job for every file, or {job: sub}; tp / enemy: what wsdist simulates against)"""
    """The whole check-up; saves and returns the report."""
    items = checks.Items()
    bags = checks.load_bags(character)
    report = {'character': character, 'time': int(time.time()), 'bags_time': bags.get('_time') if bags else None,
              'tp': tp, 'enemy': enemy, 'files': []}
    owned_ids = set()
    if bags:
        for b, c in bags.items():
            if not b.startswith('_') and b in checks.EQUIP_BAGS:
                owned_ids |= set(c)
    index = None
    if wsdist and bags:
        import wsdist_runner as W
        if progress:
            progress('loading wsdist')
        index = W.gear_index()
    for path in files or files_for(character):
        if progress:
            progress('reading ' + os.path.basename(path))
        loaded = gs_loader.load(path)
        job = checks.job_of(path)
        entry = {'file': os.path.basename(path), 'path': path, 'job': job, 'sets': len(loaded.sets),
                 'problems': checks.check(loaded, items, bags, job), 'upgrades': []}
        if index is not None and job and not loaded.error:
            js = sub.get(job, 'WAR') if isinstance(sub, dict) else sub
            entry['upgrades'] = ws_upgrades(loaded, job, js, owned_ids, items, index, progress=progress, tp=tp, enemy=enemy)
            entry['sub'] = js
        report['files'].append(entry)
    os.makedirs(DATA, exist_ok=True)
    json.dump(report, open(os.path.join(DATA, f'report_{character}.json'), 'w', encoding='utf-8'), indent=1)
    snapshot(character, items, bags)
    return report


def last_report(character):
    p = os.path.join(DATA, f'report_{character}.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        sys.exit('usage: python doctor.py <character> [file ...]')
    who = sys.argv[1]
    only = sys.argv[2:] or None
    t = time.time()
    r = checkup(who, files=[os.path.join(GS_DATA, f) for f in only] if only else None, progress=lambda m: print(' ..', m))
    print(f'{who}: {len(r["files"])} files in {time.time() - t:.0f} s')
    for f in r['files']:
        kinds = {}
        for p in f['problems']:
            kinds[p['kind']] = kinds.get(p['kind'], 0) + 1
        print(f"  {f['file']}: {f['sets']} sets, problems {kinds}, upgrades {len(f['upgrades'])}")
        for u in f['upgrades']:
            if 'error' in u:
                print('     ', u['ws'], '-', u['error'])
            else:
                print(f"      {u['ws']}: {u['now']} -> {u['best']} (+{u['gain']}%) {u['changes']}")
