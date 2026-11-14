"""
GearSwap Doctor: the upgrade shopping list (PLAN.md A1, his plan 2026-11-13): across all his jobs, the pieces he doesn't own that would improve the
most sets, ranked, with where each comes from. It reuses the Gear Optimization judges: every judged set of every file is built from his own gear,
then each unowned piece is tried in it one at a time (gear_opt.ideas). Suggestions only: nothing is bought, moved or written.
"""
import os

import checks
import gear_opt
import gs_loader
import job_sets
import progression

# where gear families come from. The artifact / relic / empyrean ladders, necks, capes and Odyssey sets are progression.py's (researched 2026-11-07);
# the rest is from memory of BG Wiki (not re-read for this list): each row links to the item's own wiki page so he can check.
FAMILIES = [
    (('flamma', 'flam.', 'mummu', 'ayanmo', 'aya.', 'mallquis', 'mall.', "tali'ah", 'hizamaru', 'hiza.', 'inyanga', 'inyan.', 'jhakri', 'meghanada', 'meg.',
      'sulevia', 'sulev.'), 'Ambuscade (Hallmarks and Gallantry; +2 with Abdhaljs items)'),
    (('souveran', 'souv.', 'carmine', 'carm.', 'kaykaus', 'amalric', 'adhemar', 'lustratio', 'lustr.', 'ryuo', 'rao ', 'argosy'),
     "Abjurations from Escha - Ru'Aun and Reisenjima; the +1 is crafted"),
    (('chironic', 'herculean', 'valorous', 'merlinic', 'odyssean'), 'Reisenjima geas fete; augments from Oseem with stones'),
    (('telchine', 'taeon', 'acro ', 'yorium', 'helios'), 'Skirmish (Alluvion); augments with Duskdim / Leafdim / Snowdim stones'),
    (('malignance', 'malig.'), 'High-tier battlefield "Maiden of the Dusk" (Lilith)'),
    (('moonlight', 'moonbeam'), "Omen (cards from the bosses)"),
    (('regal ',), 'Omen: the final bosses'),
]


def how(it, job=None):
    """(where it comes from, its BG Wiki page) for an item of the game's list."""
    low, short = it['enl'].lower(), it['en'].lower()
    wiki = progression._wiki_page(it['enl'].title().replace("'S", "'s"))
    for label, prefix, nm in progression.ODYSSEY:
        if low.startswith(prefix):
            return f'Odyssey: Sheol Gaol, {nm} (upgrade with its materials for ranks)', wiki
    for j, fams in progression.ARMOR.items():
        for family, prefix in enumerate(fams):
            if low.startswith(prefix):
                slot = progression._slot_of(it)
                tier = progression._tier(it)
                if slot in progression.SLOT_RT:
                    try:
                        return f"{progression.FAMILY_WORD[family]} armor ({j}): " + progression.step(family, slot, tier, j)[0], wiki
                    except Exception:
                        pass
                return f'{progression.FAMILY_WORD[family]} armor ({j})', wiki
    for j, n in progression.NECK.items():
        if low.startswith(n):
            return progression._neck_how(progression._tier(it))[0], wiki
    for j, n in progression.CAPE.items():
        if low.startswith(n):
            return 'Ambuscade cape (Hallmarks), augmented with threads, dust, sap and dye', wiki
    if low.endswith(('earring +1', 'earring +2')) and any(low.startswith(f[2][:4]) for f in progression.ARMOR.values()):
        return progression._ear_how(progression._tier(it))[0], wiki
    for prefixes, where in FAMILIES:
        if low.startswith(prefixes) or short.startswith(prefixes):
            return where, wiki
    return 'see its BG Wiki page', wiki


def collect(character, files, subs=None, items=None, data=None, progress=None, stop=None, per_set=3):
    """{item name: {'name', 'slot', 'sets': [(file, set path, points)], 'jobs': set, 'item'}} over every file's judged sets."""
    import doctor
    import healing
    items = items or checks.Items()
    data = data or healing.ItemData()
    bags = checks.load_bags(character) or {}
    real = checks.load_augments(character)
    found = {}
    for i, path in enumerate(files):
        if stop and stop():
            break
        job = checks.job_of(path)
        if not job or job not in checks.JOBS:
            continue
        name = os.path.basename(path)
        if progress:
            progress(i, len(files), name)
        try:
            ld = gs_loader.load(path)
            if ld.error or not ld.sets:
                continue
            cands, counts = doctor._owned_cands(ld, job, bags, items, real)
            rows = [r for r in gear_opt.classify(ld, job) if r['judge'] in ('pld', 'job')]
            ctx = gear_opt.Ctx(ld, job, (subs or {}).get(job, 'WAR'), cands, counts, items, data)
            every = job_sets.all_candidates(job, items, data)
        except Exception:
            continue
        seen = set()
        for r in rows:
            if stop and stop():
                break
            key = (r['focus'], tuple(sorted((k, g['name']) for k, g in r['gear'].items())), job_sets.ability_of(r['path']))
            if key in seen:                      # (his ability sets are often the same gear: counted once)
                continue
            seen.add(key)
            try:
                res = gear_opt.judge(r, ctx)
                ideas = gear_opt.ideas(r, res, ctx, every, per_set) if res else []
            except Exception:
                continue
            for slot, item_name, pts in ideas:
                e = found.setdefault(item_name, {'name': item_name, 'slot': slot, 'sets': [], 'jobs': set()})
                e['sets'].append((name, r['path'], pts))
                e['jobs'].add(job)
    for e in found.values():
        hit = items.find(e['name'])
        e['item'] = hit[0] if hit else None
        e['how'], e['wiki'] = how(hit[0]) if hit else ('', '')
    return found


def ranked(found, limit=40):
    """The list, best first: the piece that helps the most sets, then the most jobs, then by name."""
    import re
    best = {}
    for e in found.values():                    # (Chass. Bottes +2 and +3 are one thing to go and get: the higher one stands for both)
        base = re.sub(r' \+\d$', '', e['name'])
        tier = int(e['name'][-1]) if re.search(r' \+\d$', e['name']) else 0
        o = best.get(base)
        if o is None:
            best[base] = dict(e, tier=tier)
        else:
            sets = {(f, p) for f, p, _ in o['sets']} | {(f, p) for f, p, _ in e['sets']}
            top = e if tier > o['tier'] else o
            best[base] = dict(top, tier=max(tier, o['tier']), jobs=o['jobs'] | e['jobs'],
                              sets=[(f, p, 0) for f, p in sorted(sets)])
    rows = sorted(best.values(), key=lambda e: (-len(e['sets']), -len(e['jobs']), e['name']))
    return rows[:limit]


def line(e):
    sets = len(e['sets'])
    return (f"{e['name']} ({e['slot']}): better in {sets} set{'s' if sets != 1 else ''} on {', '.join(sorted(e['jobs']))}. "
            f"From: {e['how']}.")
