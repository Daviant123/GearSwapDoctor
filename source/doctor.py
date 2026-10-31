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


def ws_in(path, known):
    """The weapon skill in any of its sets: sets.precast.WS.Insurgency.Acc, sets.precast.WS["Cross Reaper"].Mid."""
    import fixer
    parts = fixer._path_parts(path)
    if 'WS' in parts[:-1] and parts[parts.index('WS') + 1] in known:
        return parts[parts.index('WS') + 1]
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


NO_SUB = '(nothing)'


def with_weapons(gear, target):
    """The set with the weapons he picked for it in Build a set (target 'main' / 'sub'; sub '(nothing)' = an empty
    sub slot). His request 2026-10-30: "i cant select the weapon that i would like to use"."""
    if not target or not (target.get('main') or target.get('sub')):
        return gear
    g = dict(gear)
    for k in ('main', 'sub'):
        v = target.get(k)
        if not v:
            continue
        for alias in [x for x in g if x.lower() == k]:
            g.pop(alias)
        g[k] = {'name': 'empty' if v == NO_SUB else v, 'augments': [], 'bag': None}
    return g


def _dt_fields(info, req):
    """The damage taken of an upgrade, for the app: now / new (physical, magic), what he asked, and whether the new set
    reaches it."""
    out = {'dt_now': list(info.get('now') or (0, 0)), 'dt_best': list(info.get('best') or (0, 0))}
    if req:
        out['dt_asked'] = list(req)
        out['dt_met'] = out['dt_best'][0] <= req[0] + 0.01 and out['dt_best'][1] <= req[1] + 0.01
        out['dt_was_met'] = out['dt_now'][0] <= req[0] + 0.01 and out['dt_now'][1] <= req[1] + 0.01
    return out


# ---- each set with the weapon and conditions it's really for (his question 2026-10-30, set_name.py reads the names)
DW_MAIN = ('NIN', 'DNC', 'THF', 'BLU')
DW_SUB = ('NIN', 'DNC')


def _owns(name, owned_ids, items):
    return any(it['id'] in owned_ids for it in items.find(name))


def _best_owned(skills, job, owned_ids, items, index, names):
    """The owned weapons of these kinds this job can use, the one to test with first: in the file's lists and without sets of
    their own (those are who a "Scythe" set is for), then without sets of their own, then the rest; the strongest first."""
    import wsdist_runner as W
    found = {}
    for iid in owned_ids:
        it = items.by_id.get(iid)
        ents = it and W.entries_for(it['en'], items, index)
        if ents:
            e = W.pick_variant(ents)
            if e.get('Type') == 'Weapon' and e.get('Skill Type') in skills and job.lower() in e['Jobs']:
                found[e['Name']] = e

    def rank(e):
        own_sets = e['Name'] in names.named
        return (own_sets, not names.is_listed(e['Name']) if not own_sets else 0, -e.get('DMG', 0), e['Name'])
    return sorted(found.values(), key=rank)


def _tp_weapon(r, gear, job, sub, owned_ids, items, index, names):
    """The weapon a TP set's name asks for: (gear with it in the main hand, why it's that one, why it can't be checked)."""
    import set_name
    import wsdist_runner as W
    pick = {}
    why = None
    if any(k.lower() == 'main' for k in gear):
        return gear, 'the set itself has it', None
    if r['form'] == 'DW' and job.upper() not in DW_MAIN and (sub or '').upper() not in DW_SUB:
        return gear, None, f"{job}/{sub} can't dual wield (the sub job is set per job in Settings)"
    if r['weapon']:
        w = r['weapon']
        if not _owns(w, owned_ids, items):
            return gear, None, f"you don't own {w}"
        ents = W.entries_for(w, items, index)
        if not ents:
            return gear, None, f"wsdist doesn't know {w}"
        if job.lower() not in W.pick_variant(ents)['Jobs']:
            return gear, None, f"{job} can't use {w}"
        pick['main'], why = w, "the set's name says so"
    elif r['kind']:
        best = _best_owned((r['kind'],), job, owned_ids, items, index, names)
        if not best:
            return gear, None, f"no {r['kind']} {job} can use in your bags"
        own = ' (the others have sets of their own)' if best[0]['Name'] not in names.named and len(best) > 1 else ''
        pick['main'], why = best[0]['Name'], f"the set is named for the kind: your best {r['kind']}{own}"
    elif r['form']:
        best = _best_owned(set_name.ONE_HANDED, job, owned_ids, items, index, names)
        if not best:
            return gear, None, f"no one-handed weapon {job} can use in your bags"
        pick['main'], why = best[0]['Name'], f"a {r['form']} set is for a one-handed weapon: your best one"
    if r['form'] == 'DW':
        others = [e for e in _best_owned(set_name.ONE_HANDED, job, owned_ids, items, index, names) if e['Name'] != pick.get('main')]
        if not others:
            return gear, None, 'no second one-handed weapon in your bags for a dual wield set'
        pick['sub'] = others[0]['Name']
    elif r['form'] == 'SW':
        pick['sub'] = NO_SUB
    return with_weapons(gear, pick) if pick else gear, why, None


def _ws_weapon(ws, skill, gear, weapons, job, owned_ids, items, index):
    """The weapon for a weapon skill set: (gear, why it's that one, why it can't be checked, more notes). A weapon's own skill is
    judged with that weapon; one that needs its weapon is never judged with another."""
    import rema
    import set_name
    import wsdist_runner as W
    linked = rema.ws_weapon(ws)
    if not linked:
        return gear, None, None, []
    how = rema.needs_weapon(ws)
    mains = [v['name'] for k, v in gear.items() if k.lower() == 'main']
    own_name = linked if set_name.norm(linked) in [set_name.norm(m) for m in mains] else None
    if own_name:
        return gear, f'{ws} is its own weapon skill', None, []
    if mains and not (how == 'always' and rema.family(mains[0])):       # (another Ultimate Weapon can't do it; a lesser version may)
        more = [f'{ws} on {mains[0]} needs {rema.QUEST[rema.family(linked)]}'] if how == 'quest' else []
        return gear, 'the set itself has it', None, more
    ents = W.entries_for(linked, items, index)
    if ents and _owns(linked, owned_ids, items) and job.lower() in W.pick_variant(ents)['Jobs']:
        return with_weapons(gear, {'main': linked}), f'{ws} is its own weapon skill', None, []
    if how == 'always':
        return gear, None, rema.needs_text(ws), []
    if how == 'quest':
        for _name, wg in weapons:
            main = wg.get('main')
            e = main and W.entries_for(main['name'], items, index)
            if e and W.pick_variant(e).get('Skill Type') == skill:          # (his file names a weapon of the kind for it)
                return gear, None, None, [f'{ws} on another {skill} needs {rema.QUEST[rema.family(linked)]}']
        return gear, None, rema.needs_text(ws), []
    return gear, None, None, [f"{linked} isn't in your bags: {ws} tested with another {skill}"]


def plan_set(names, path, gear, job, sub, owned_ids, items, index, buffs=None, ws=None, weapons=(), main_ws=None):
    """One set with what it's for: {'owned', 'cur', 'notes', 'skill', 'spec', 'error'}. spec: buffs plus what the name says
    (wsdist_runner reads 'aftermath', 'aftermath_why', 'set_haste', 'keep_accuracy'). names: set_name.FileInfo."""
    import rema
    import wsdist_runner as W
    r = names.read(path)
    out = {'owned': {}, 'cur': {}, 'notes': [], 'skill': None, 'spec': dict(buffs or {}), 'error': None, 'read': r}
    more = []
    if ws:
        gear, why, out['error'], more = _ws_weapon(ws, W.ws_skill(ws), gear, weapons, job, owned_ids, items, index)
    else:
        gear, why, out['error'] = _tp_weapon(r, gear, job, sub, owned_ids, items, index, names)
    if out['error']:
        return out
    if ws:
        owned, cur, notes, out['skill'] = W.plan_ws(job, sub, ws, gear, weapons, owned_ids, items, index)
    else:
        owned, cur, notes = plan_tp(job, sub, gear, weapons, main_ws, owned_ids, items, index)
    main = cur.get('main')
    out.update(owned=owned, cur=cur)
    if main:
        off = cur.get('sub')
        more.insert(0, f"weapon: {main['Name2']}" + (f" / {off['Name2']}" if off and off.get('Name') != 'Empty' else '')
                    + f" ({why or 'nothing names a weapon for this set'})")
    spec = out['spec']
    if main and rema.family(main['Name']):
        if spec.get('aftermath') != 'auto':
            if 'aftermath' in spec:
                spec['aftermath_why'] = 'the level you picked'
        elif r['am'] is not None:
            spec['aftermath'] = rema.named_level(r['am'], main)
            spec['aftermath_why'] = "the set's name says Aftermath is up"
        elif r['am_down'] and not ws:
            spec['aftermath'] = 0
            spec['aftermath_why'] = f"this file has Aftermath sets for {names.label(r) or 'this weapon'}: this one is for when it's down"
    if r['haste']:
        spec['set_haste'] = r['haste']
        more.append("delay capped: it's a Haste set, so gear haste doesn't decide it" if r['haste'] == 'cap'
                    else f"magic haste {r['haste']}%, from the set's name")
    if r['acc'] or r['mid']:
        spec['keep_accuracy'] = True
    out['notes'] = more + notes
    return out


def _judged(s, plan, info, entry=None):
    """What a set was judged with, for the report (also when nothing better was found)."""
    main = plan['cur'].get('main') or {}
    return {'set': s['path'], 'weapon': main.get('Name2'), 'aftermath': info.get('level'), 'metric': info.get('metric'),
            'haste': plan['spec'].get('set_haste'), 'keep_accuracy': bool(plan['spec'].get('keep_accuracy')),
            'notes': plan['notes'] + _am_notes(info), 'upgrade': bool(entry)}


def ws_upgrades(loaded, job, sub, owned_ids, items, index, only=None, progress=None, tp=1500, enemy='Apex Toad',
                targets=None, buffs=None, stats=None):
    """[{set, ws, now, best, gain, changes: {gs slot: name}, notes, dt_now, dt_best (, dt_asked, dt_met)}] for weapon
    skill sets with a better owned set. targets: {set path: {'dt', 'pdt', 'mdt'}} - the damage taken he wants in that
    set (the new set must reach it, even if it costs damage). buffs: what's up (wsdist_runner.buff_spec). stats (a dict) gets
    'judged': what each set was judged with."""
    import set_name
    import wsdist_runner as W
    known = W.ws_list()
    names = set_name.FileInfo(loaded, index)
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
            plan = plan_set(names, s['path'], with_weapons(s['gear'], (targets or {}).get(s['path'])), job, sub, owned_ids, items, index,
                            buffs, ws, weapons)
            if plan['error']:
                out.append({'set': s['path'], 'ws': ws, 'error': plan['error']})
                continue
            owned, cur, notes, skill = plan['owned'], plan['cur'], plan['notes'], plan['skill']
            if 'main' not in cur:
                out.append({'set': s['path'], 'ws': ws, 'error': f'no {skill or "matching"} weapon {job} can use in the bags to test it with'})
                continue
            req = W.dt_requirement((targets or {}).get(s['path']))
            info = {}
            best, dmg, now = W.best_ws_set(job, sub, ws, owned, cur, tp=tp, enemy_name=enemy, req=req, info=info, buffs=plan['spec'])
            if stats is not None:
                stats.setdefault('judged', []).append(_judged(s, plan, info))
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
        notes = notes + _am_notes(info)
        assumed = [f"{best[sl]['Name2']}" for sl in best if best[sl]['Name2'] != best[sl]['Name'] and W.GS_SLOT.get(sl) in changes]
        if assumed:
            notes = notes + ['augment path assumed: ' + ', '.join(assumed)]
        gain = (dmg - now) / now * 100 if now else 0
        dtf = _dt_fields(info, req)
        dt_fix = bool(req) and not dtf.get('dt_was_met') and changes      # his damage taken, even if it costs damage
        if changes and (gain >= 1 or dt_fix):
            out.append(dict({'set': s['path'], 'ws': ws, 'now': round(now), 'best': round(dmg), 'gain': round(gain, 1),
                             'changes': changes, 'notes': notes, 'dt_fix': bool(dt_fix)}, **dtf))
    return out


def tp_ws_damage(loaded, job, sub, cur, owned_ids, items, index, ws_tp, enemy, buffs, cache=None):
    """What a weapon skill does with this TP set's weapon, for judging by overall damage per second: the set in his file for
    the weapon's linked weapon skill, else his first weapon skill set of that weapon's kind. None: no such set (wsdist_runner
    then uses the linked weapon skill with the TP set on)."""
    import rema
    import wsdist_runner as W
    main = cur.get('main')
    if not main or not rema.family(main['Name']):
        return None
    key = (main['Name2'], (cur.get('sub') or {}).get('Name2'), (buffs or {}).get('aftermath'))
    if cache is not None and key in cache:
        return cache[key]
    known, linked = W.ws_list(), rema.linked_ws(main['Name'])
    found, first = None, None
    for s in loaded.sets:
        ws = ws_of(s['path'], known)
        if not ws or W.ws_skill(ws) != main.get('Skill Type'):
            continue
        if rema.needs_weapon(ws) and ws != linked:                     # (another weapon's own: not this one's)
            continue
        first = first or (s, ws)
        if ws == linked:
            found = (s, ws)
    out = None
    if found or first:
        s, ws = found or first
        try:
            _o, wc, _n, _s = W.plan_ws(job, sub, ws, s['gear'], [], owned_ids, items, index)
            wc = dict(wc, main=main)
            if cur.get('sub'):
                wc['sub'] = cur['sub']
            spec = {k: v for k, v in (buffs or {}).items() if k not in ('set_haste', 'keep_accuracy', 'aftermath_why')}
            out = W.set_damage(job, sub, ws, wc, tp=ws_tp, enemy_name=enemy, buffs=spec)
        except Exception:
            out = None
    if cache is not None:
        cache[key] = out
    return out


def is_tp_set(path):
    """A TP (engaged / melee) set: sets.engaged..., or sets.TP... as some files name them."""
    import fixer
    parts = fixer._path_parts(path)
    return len(parts) >= 2 and parts[1].lower() in ('engaged', 'tp')


def tp_order(rows, names):
    """The TP sets in the order to check them: first the plainest set of each weapon, then each weapon with each mode (Acc, Mid,
    damage taken, Aftermath, Haste), then the rest, fewest modes first. rows: [set]. Returns (the order, how many of them are the
    first two: the ones that cover every weapon and mode)."""
    plain = sorted(rows, key=lambda s: (len(names.read(s['path'])['modes']), s['path'].count('.'), len(s['path'])))
    first, seen = [], set()
    for s in plain:
        r = names.read(s['path'])
        if names.label(r) not in seen:
            seen.add(names.label(r))
            first.append(s)
    second = []
    for s in plain:
        r = names.read(s['path'])
        for mode in r['modes']:
            if (names.label(r), mode) not in seen:
                seen.add((names.label(r), mode))
                if s not in first and s not in second:
                    second.append(s)
    return first + second + [s for s in plain if s not in first and s not in second], len(first) + len(second)


def tp_upgrades(loaded, job, sub, owned_ids, items, index, progress=None, ws_tp=1000, enemy='Apex Toad', metric='time',
                limit=None, targets=None, buffs=None, seconds=300, stats=None):
    """[{set, ws: 'TP: <set>', kind: 'tp', now, best, gain, unit, changes, notes}] for TP sets with a better owned set
    (his question 2026-10-30: "it seems to do for weaponskills, but does not do anything for calculating TP").
    One set per weapon and mode first (tp_order), then more up to 40 sets, or `limit` sets; about `seconds` of wsdist at most (it runs
    without numba here); sets with the same gear and conditions cost nothing. stats (a dict) gets 'total', 'checked', 'not_checked'
    {why: n}, 'stopped' (out of time), 'judged'."""
    import set_name
    import wsdist_runner as W
    weapons, main_ws = tp_weapons(loaded)
    names = set_name.FileInfo(loaded, index)
    tps = sorted((s for s in loaded.sets if is_tp_set(s['path'])), key=lambda s: (s['path'].count('.'), len(s['path'])))
    stats = stats if stats is not None else {}
    stats.update(total=len(tps), checked=0, same=0, not_checked={}, stopped=False)
    out = []
    wanted = [s for s in tps if (targets or {}).get(s['path'])]       # (sets he gave damage taken for: always checked)
    # what can't be checked at all: said once for each reason, and it doesn't use up the limit
    rows, cant = [], {}
    for s in tps:
        r = names.read(s['path'])
        target = (targets or {}).get(s['path'])
        if r['reraise'] and not target:
            cant.setdefault('it\'s for Reraise, not for speed', []).append(s)
            continue
        _g, _why, err = _tp_weapon(r, with_weapons(s['gear'], target), job, sub, owned_ids, items, index, names)
        if err:
            cant.setdefault(err, []).append(s)
        else:
            rows.append(s)
    for why, group in cant.items():
        stats['not_checked'][why] = len(group)
        out.append({'set': group[0]['path'], 'ws': 'TP: ' + group[0]['path'][len('sets.'):], 'kind': 'tp',
                    'error': f"{why}: {len(group)} TP set{'s' if len(group) != 1 else ''} not checked"})
    order, cover = tp_order(rows, names)
    limit = max(cover, 40) if limit is None else limit
    todo = order[:limit] + [s for s in wanted if s not in order[:limit] and s in rows]
    worth, done = {}, {}
    started = time.time()
    for s in todo:
        if s not in wanted and time.time() - started > seconds:
            stats['stopped'] = True
            break
        label = 'TP: ' + s['path'][len('sets.'):]
        if progress:
            progress(f'wsdist: {label}')
        try:
            plan = plan_set(names, s['path'], with_weapons(s['gear'], (targets or {}).get(s['path'])), job, sub, owned_ids, items, index,
                            buffs, None, weapons, main_ws)
            if plan['error']:
                out.append({'set': s['path'], 'ws': label, 'kind': 'tp', 'error': plan['error']})
                continue
            owned, cur, notes, spec = plan['owned'], plan['cur'], plan['notes'], plan['spec']
            if 'main' not in cur:
                out.append({'set': s['path'], 'ws': label, 'kind': 'tp', 'error': 'no weapon in this set or a weapon set to test it with'})
                continue
            req = W.dt_requirement((targets or {}).get(s['path']))
            key = (tuple(sorted((k, e['Name2']) for k, e in cur.items() if e)), req, spec.get('aftermath'), spec.get('set_haste'),
                   bool(spec.get('keep_accuracy')))
            if key in done:                                            # (the same gear for the same conditions: the same answer)
                best, val, now, info, kept = done[key]
                stats['same'] += 1
            else:
                info = {}
                wsd = tp_ws_damage(loaded, job, sub, cur, owned_ids, items, index, ws_tp, enemy, spec, worth)
                best, val, now = W.best_tp_set(job, sub, owned, cur, ws_tp=ws_tp, enemy_name=enemy, metric=metric, req=req, info=info,
                                               buffs=spec, ws_damage=wsd)
                kept = getattr(W.best_tp_set, 'kept_dt', (0, 0))
                done[key] = (best, val, now, info, kept)
            stats['checked'] += 1
            stats.setdefault('judged', []).append(_judged(s, plan, info))
            kp, km = info.get('asked') or kept
            if req:
                notes = notes + [f'damage taken as you asked (physical {kp:.0f}%, magic {km:.0f}%)']
            elif kp < 0 or km < 0:
                notes = notes + [f'damage taken kept as it is now (physical {kp:.0f}%, magic {km:.0f}%)']
        except Exception as e:
            out.append({'set': s['path'], 'ws': label, 'kind': 'tp', 'error': f'wsdist could not simulate it: {e}'})
            continue
        out += _tp_entry(W, s, label, cur, best, val, now, notes + _am_notes(info), items, info.get('metric', metric), info, req)
    return out


def tp_weapons(loaded):
    """The weapons to test a file's TP sets with: its weapon sets (and sets that name a weapon), and the weapon skill
    the file uses most - for a TP set with no weapon at all (a COR's Savage Blade sets -> a sword, the strongest one
    owned, the same rule the weapon skill sets use)."""
    import wsdist_runner as W
    weapons = [(s['path'], s['gear']) for s in loaded.sets if s['path'].startswith('sets.weapons')]
    weapons += [(s['path'], s['gear']) for s in loaded.sets if not s['path'].startswith('sets.weapons') and 'main' in s['gear']]
    known = W.ws_list()
    kinds = {}
    for s0 in loaded.sets:
        w0 = ws_of(s0['path'], known)
        if w0 and W.ws_skill(w0) not in ('Archery', 'Marksmanship'):
            kinds.setdefault(W.ws_skill(w0), w0)
            kinds[W.ws_skill(w0) + '#n'] = kinds.get(W.ws_skill(w0) + '#n', 0) + 1
    main_ws = None
    best_n = 0
    for k, v in kinds.items():
        if k.endswith('#n') and v > best_n:
            best_n, main_ws = v, kinds[k[:-2]]
    return weapons, main_ws


def plan_tp(job, sub, gear, weapons, main_ws, owned_ids, items, index):
    """wsdist_runner.plan_ws for a TP set: any weapon from the weapon sets, else the file's main weapon skill's."""
    import wsdist_runner as W
    owned, cur, notes, _ = W.plan_ws(job, sub, None, gear, weapons, owned_ids, items, index)
    if 'main' not in cur and main_ws:
        owned, cur, notes, _ = W.plan_ws(job, sub, main_ws, gear, weapons, owned_ids, items, index)
    return owned, cur, notes


def _am_notes(info):
    """The Aftermath it was judged with, and the time to a weapon skill when it was judged by damage."""
    out = [info['aftermath']] if info.get('aftermath') else []
    if info.get('abilities'):
        out.append(info['abilities'])
    if info.get('accuracy') is not None:
        out.append(f"this set is for accuracy: kept at {info['accuracy']:.0f} or more")
    if info.get('time'):
        out.append(f"time to a weapon skill: {info['time'][0]:.1f} s -> {info['time'][1]:.1f} s")
    return out


def tp_checked_text(f):
    """For the app: 'TP sets: 30 of 91 checked...'; '' for a file without TP sets or an older report."""
    if not f.get('tp_total'):
        return ''
    text = f"TP sets: {f.get('tp_checked', 0)} of {f['tp_total']} checked, one per weapon and mode first"
    if f.get('tp_stopped'):
        text += ' (stopped at the time limit)'
    if f.get('tp_not_checked'):
        text += '; not checked: ' + ', '.join(f'{n} ({why})' for why, n in f['tp_not_checked'].items())
    return text


def _tp_entry(W, s, label, cur, best, val, now, notes, items, metric, info, req):
    """The upgrade entry for one TP set ([] when nothing better was found)."""
    out = []
    changes = {}
    for slot, gs in W.GS_SLOT.items():
        if slot in ('main', 'sub', 'ranged'):
            continue
        a = cur.get(slot, {}).get('Name2') if cur.get(slot) else None
        b = best[slot]['Name2'] if best.get(slot) and best[slot]['Name'] != 'Empty' else None
        if b and a != b:
            changes[gs] = _gs_name(best[slot], items)
    for p1, p2 in (('ear1', 'ear2'), ('ring1', 'ring2')):
        w1, w2 = W.SLOT_MAP[p1], W.SLOT_MAP[p2]
        cp_ = [cur.get(w1, {}).get('Name') if cur.get(w1) else None, cur.get(w2, {}).get('Name') if cur.get(w2) else None]
        bp_ = [best[w1]['Name'] if best[w1]['Name'] != 'Empty' else None, best[w2]['Name'] if best[w2]['Name'] != 'Empty' else None]
        if _pairs_same(cp_, bp_):
            changes.pop(p1, None)
            changes.pop(p2, None)
    if metric == 'time':
        gain = (now - val) / now * 100 if now else 0          # faster to the weapon skill
        unit = 's'
    else:
        gain = (val - now) / now * 100 if now else 0
        unit = 'dps' if metric == 'dps' else ''
    dtf = _dt_fields(info, req)
    dt_fix = bool(req) and not dtf.get('dt_was_met') and changes
    if changes and (gain >= 1 or dt_fix):
        out.append(dict({'set': s['path'], 'ws': label, 'kind': 'tp', 'now': round(now, 2 if unit == 's' else 0),
                         'best': round(val, 2 if unit == 's' else 0), 'gain': round(gain, 1), 'unit': unit, 'changes': changes,
                         'notes': notes, 'dt_fix': bool(dt_fix)}, **dtf))
    return out


def checkup(character, files=None, wsdist=True, progress=None, sub='WAR', tp=1500, enemy='Apex Toad', tp_sets=True,
            ws_tp=1000, tp_metric='time', targets=None, buffs='none', buffs_custom=None, aftermath='auto'):
    """(sub: one sub job for every file, or {job: sub}; tp / enemy: what wsdist simulates against; targets: {file name:
    {set path: {'dt', 'pdt', 'mdt'}}} - the damage taken he set for those sets; buffs: 'none' / 'solo' / 'party' /
    'custom' with his own in buffs_custom - what's up while the sets are judged, saved in the report; aftermath: 'auto' =
    what each Ultimate Weapon is kept at (rema.py), or a level)"""
    """The whole check-up; saves and returns the report."""
    import wsdist_runner as W
    spec = W.buff_spec(buffs, buffs_custom, aftermath)
    items = checks.Items()
    bags = checks.load_bags(character)
    report = {'character': character, 'time': int(time.time()), 'bags_time': bags.get('_time') if bags else None,
              'tp': tp, 'enemy': enemy, 'tp_sets': tp_sets, 'ws_tp': ws_tp, 'tp_metric': tp_metric, 'buffs': buffs,
              'buffs_text': W.buff_text(buffs), 'buffs_spec': spec, 'aftermath': aftermath,
              'aftermath_text': W.AM_TEXT.get(aftermath, ''), 'files': []}
    owned_ids = set()
    if bags:
        for b, c in bags.items():
            if not b.startswith('_') and b in checks.EQUIP_BAGS:
                owned_ids |= set(c)
    index = None
    if wsdist and bags:
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
            tg = (targets or {}).get(os.path.basename(path)) or {}
            ws_stats, tp_stats = {}, {}
            entry['upgrades'] = ws_upgrades(loaded, job, js, owned_ids, items, index, progress=progress, tp=tp, enemy=enemy,
                                            targets=tg, buffs=spec, stats=ws_stats)
            if tp_sets or any(is_tp_set(k) for k in tg):
                entry['upgrades'] += tp_upgrades(loaded, job, js, owned_ids, items, index, progress=progress, ws_tp=ws_tp,
                                                 enemy=enemy, metric=tp_metric, targets=tg, buffs=spec, stats=tp_stats)
                entry.update(tp_total=tp_stats['total'], tp_checked=tp_stats['checked'], tp_not_checked=tp_stats['not_checked'],
                             tp_stopped=tp_stats['stopped'])
            entry['judged'] = ws_stats.get('judged', []) + tp_stats.get('judged', [])
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
        if tp_checked_text(f):
            print('     ', tp_checked_text(f))
        for u in f['upgrades']:
            if 'error' in u:
                print('     ', u['ws'], '-', u['error'])
            else:
                print(f"      {u['ws']}: {u['now']} -> {u['best']} (+{u['gain']}%) {u['changes']}")
