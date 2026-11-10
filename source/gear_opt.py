"""
GearSwap Doctor: Gear Optimization (his request 2026-11-10: "specifically address paladin right now ... create a new tab called gear optimization. it should
be able to look at my current gear and gearswap and look at what each set does and its intention and suggest the best sets for that particular thing. it should
also be able to write it. but it should keep in mind what that job is best for").

Every set of one file, in one place:
  - what it is for (its intention), from its name and the job (pld.focus_for, job_sets.focus_for, idle.focus_for); he can pick another
  - who judges it: pld.py (a Paladin's tank sets: the guides' rules), idle.py, job_sets.py, or wsdist (damage: Build a set / the check-up)
  - the best set from his own gear for that intention, and how much better
  - the job's role first: a Paladin tanks, so its sets are listed and judged as a tank's (ROLE), and the file-wide checks are the guides' (file_checks)
  - the sets the guides say a PLD should have that the file doesn't (missing)
Nothing is written here: the tab hands edits to the app's _apply (a list of what changes, his OK, a backup).
"""
import healing
import idle
import job_guides
import job_sets
import pld

# ------------------------------------------------------------------ what a job is for (research: RESEARCH.md "Paladin, more guides (2026-11-10)")
ROLE = {
    'PLD': {
        'title': 'Paladin: the party\'s tank',
        'text': ("A Paladin's job is to hold hate and not die. So every set here is judged as a tank's set first: damage taken capped "
                 "(the 2025 FFXIAH guide: never below 50 % physical / magic in a set you tank in), HP kept up (a swap to lower max HP cuts your HP and "
                 "it doesn't come back), spells not interrupted while you're hit (102 % with 5/5 merits), and enmity up to what counts "
                 "(+200 with Crusade and Sentinel). Damage comes last: weapon skill and fighting sets keep the damage taken they have."),
        'order': ['Staying alive', 'Holding hate', 'Spells while being hit', 'Cures', 'Casting fast', 'Job abilities', 'Emergencies',
                  'Weapon skills', 'Fighting (damage)', 'Standing (Refresh, town)', 'Healing tab', 'Weapons', 'Add-on sets'],
        'sources': 'FFXIAH "The Divine Protector: PLD Guide 2025" and its thread; BG Wiki Community Paladin Guide; BG Wiki Finans Gearset Guides/Paladin.',
    },
}
GENERIC = {'title': 'Every set, judged by what it is for',
           'text': ('Each set is judged by what its name says it is for (pick another under "It is for"). The deep, job-specific rules are written for '
                    'Paladin so far; other jobs use the general rules (fast cast, enhancing, songs, rolls ...).'),
           'order': ['Staying alive', 'Casting fast', 'Spells', 'Cures', 'Job abilities', 'Pets', 'Weapon skills', 'Fighting (damage)',
                     'Standing (Refresh, town)', 'Healing tab', 'Weapons', 'Add-on sets'],
           'sources': ''}


def role(job):
    job = (job or '').upper()
    return ROLE.get(job) or job_guides.ROLE.get(job) or GENERIC


def why_text(row, job):
    """What a set is for, in the guide's words (the job's own text when there is one)."""
    f = row.get('picked') or row['focus']
    if row['judge'] == 'pld':
        return WHY.get(f, '') or row['why']
    return job_guides.why(job, f) or ((job_sets.FOCUS.get(f) or {}).get('how', '') if row['judge'] == 'job' and f else '') or row['why']


# what each PLD intention means, in plain words (shown when a set is picked)
WHY = {
    'Tank, standing': 'Standing in front of the monster between actions: damage taken capped, HP high, Magic Evasion (550+ for a tank), '
                      'and enmity that keeps hate when you are hit.',
    'Tank, magic': 'Tanking spells and breath: magic damage taken and Magic Evasion first, Magic Def. Bonus next.',
    'Tank, fighting': 'Swinging while tanking: the guide\'s order is HP, then damage taken, then accuracy, then Store TP / Double Attack.',
    'Enmity': 'A burst of hate (Flash, Provoke, abilities, Atonement): enmity up to +170 from gear (with Crusade +30 that is the +200 cap), '
              'damage taken still counted.',
    'Enmity, not interrupted': 'Hate while being hit: interruption to 102 % first, then enmity.',
    'Phalanx': 'Phalanx strength: Enhancing skill (it goes in steps: 300 = 28, 358 = 30, 386 = 31, 415 = 32, 500 = 35) plus Phalanx+ gear.',
    'Phalanx, not interrupted': 'Phalanx while being hit: interruption first, then Phalanx.',
    'Spell, not interrupted': 'Any other spell cast while being hit (Protect, Shell, Crusade, Aquaveil, Cocoon ...): interruption to 102 %.',
    'Enlight': 'Enlight: Divine magic skill (its accuracy scales with it), not interrupted.',
    'Cure others': 'Curing someone else: Cure potency to 50 %, not interrupted, enmity from the cure.',
    'Cure yourself': 'Curing yourself: potency 50 %, Cure received 30 %, more max HP heals more, not interrupted.',
    'Fast cast': 'Starting a spell: Fast Cast to 80 %, keeping HP within 200 of your idle set (the guide: the lowest-HP set matters most).',
    'Fast cast, cure cheat': 'A cure cheat set: lower max HP on purpose so the cure after it heals (and pulls hate) more. Use with GearSwap only.',
    'Reprisal': 'Reprisal: enmity and duration, with some Fast Cast (BG Wiki Community PLD Guide).',
    'Stoneskin': 'Stoneskin: Stoneskin+ and MND, not interrupted.',
    'Covering': 'Worn while Cover is up: the pieces that make Cover stronger, then damage taken.',
    'Doom': 'Doomed: Holy Water+ and Cursna received+.',
    'Chivalry': 'Chivalry: the Cab. Gauntlets and MND (TP to MP).',
}


def _group_pld(focus):
    if focus.startswith('Tank'):
        return 'Staying alive'
    if focus.startswith('Ability') or focus in ('Chivalry', 'Covering'):
        return 'Job abilities'
    if focus.startswith('Enmity'):
        return 'Holding hate'
    if focus.startswith('Cure'):
        return 'Cures'
    if focus.startswith('Fast cast'):
        return 'Casting fast'
    if focus == 'Doom':
        return 'Emergencies'
    return 'Spells while being hit'


def _group_job(focus, job=None, path=''):
    g = job_guides.group_of(focus, job, path)
    if g:
        return g
    f = (focus or '').lower()
    if f.startswith(('fast cast', 'spell recast')):
        return 'Casting fast'
    if 'cure' in f or 'curaga' in f or 'regen' in f or 'cursna' in f or 'waltz' in f:
        return 'Cures'
    if any(x in f for x in ('blood pact', 'ready', 'pet')):
        return 'Pets'
    if any(x in f for x in ('ability', 'step', 'jump', 'roll', 'quick draw', 'flourish', 'treasure', 'sneak', 'trick', 'charm', 'doom')):
        return 'Job abilities'
    if f.startswith('enmity') or f == 'flash':
        return 'Holding hate'
    return 'Spells'


# ------------------------------------------------------------------ every set of a file: what it is for, who judges it
def classify(loaded, job):
    """[{path, group, focus, judge, why}] in the file's order. judge: 'pld', 'idle', 'job' (judged here), 'wsdist' (damage: Build a set), None (left as is)."""
    job = (job or '').upper()
    cov = {}
    if job == 'PLD':
        for k, paths in pld.coverage(loaded).items():
            for p in paths:
                cov[p] = k
    rows = []
    for s in loaded.sets:
        p = s['path']
        row = {'path': p, 'gear': s['gear'], 'group': 'Add-on sets', 'focus': None, 'judge': None, 'why': ''}
        if job == 'PLD' and pld.takes(p, job):
            f = pld.focus_for(p)
            row.update(group=_group_pld(f), focus=f, judge='pld', why=WHY.get(f, ''))
        elif p.startswith('sets.weapons'):
            row.update(group='Weapons', why='which weapons you fight with: kept as they are')
        elif job == 'PLD' and cov.get(p) == 'ws' or job != 'PLD' and ('.ws' in p.lower() or 'ws[' in p.lower()) and not job_sets.takes(p, job):
            row.update(group='Weapon skills', judge='wsdist',
                       why=('Weapon skill damage, keeping the damage taken the set has: a tank still has to live through it '
                            '(the Community PLD Guide\'s weapon skill sets keep 39-43 % damage taken). wsdist judges damage: "Open in Build a set".')
                       if job == 'PLD' else 'Weapon skill damage: wsdist judges it. "Open in Build a set".')
        elif job != 'PLD' and _nuke(p, job):
            k = _nuke(p, job)
            row.update(group='Nukes and blue magic damage', judge='wsdist',
                       why=('Physical blue magic: damage from the spell\'s own stats (STR / DEX / VIT ...) and attack, judged by wsdist.' if k[0] == 'bluephys' else
                            'Magical blue magic: Magic Atk. Bonus, magic damage, INT / MND, magic burst bonus (40 % cap), judged by wsdist.' if k[0] == 'blue' else
                            'A nuke (or magic burst): Magic Atk. Bonus, magic damage, INT, magic burst bonus (40 % cap), judged by wsdist.')
                       + ' "Open in Build a set".')
        elif job == 'PLD' and cov.get(p) == 'tp':
            row.update(group='Fighting (damage)', judge='wsdist',
                       why='A Paladin tanks: this is for when you are not the tank (fodder, a Sortie boss you melee). wsdist judges it, keeping its damage taken.')
        elif job != 'PLD' and job_sets.takes(p, job):
            f = job_sets.focus_for(p, job)
            row.update(group=_group_job(f, job, p), focus=f, judge='job', why=job_guides.why(job, f) or (job_sets.FOCUS.get(f) or {}).get('how', ''))
        elif idle.is_idle(p) and not (job == 'PLD' and cov.get(p) == 'small'):
            f = idle.focus_for(p)
            row.update(group='Standing (Refresh, town)' if job == 'PLD' else ('Staying alive' if f in ('Damage taken', 'Magic evasion', 'Balanced')
                                                                              else 'Standing (Refresh, town)'),
                       focus=f, judge='idle', why=f'Standing still: {f}.')
        elif cov.get(p) == 'healing' or 'waltz' in p.lower():
            row.update(group='Healing tab', why='Waltz / Cure received: the Healing tab builds these.')
        else:
            import doctor
            if doctor.is_tp_set(p):
                row.update(group='Fighting (damage)', judge='wsdist', why='Fighting: wsdist judges it (time to a weapon skill). "Open in Build a set".')
            else:
                row['why'] = 'an add-on set for an item or two (Capacity, Reraise, MP ...): left as it is'
        rows.append(row)
    return rows


def _nuke(path, job):
    import magic
    try:
        return magic.kind_of(path, job)
    except Exception:
        return None


def focus_choices(row, job):
    """What he can pick under "It is for" for this set."""
    if row['judge'] == 'pld':
        return list(pld.FOCUS)
    if row['judge'] == 'job':
        return list(job_sets.FOCUS)
    if row['judge'] == 'idle':
        return list(idle.FOCUS)
    return []


# ------------------------------------------------------------------ judging
class _Sets:
    def __init__(self, sets):
        self.sets = sets


def with_weapons(set_gear, weapons):
    """The set as it would be worn with the weapon / shield he picked ({'main': candidate or None, 'sub': ...}; None = the set's own)."""
    if not weapons or not any(weapons.values()):
        return set_gear
    out = dict(set_gear)
    for slot in ('main', 'sub'):
        c = weapons.get(slot)
        if c:
            for k in [k for k in out if k.lower() == slot]:
                del out[k]
            out[slot] = {'name': c['name'], 'augments': list(c.get('augments') or [])}
    return out


def weapon_label(c):
    a = ', '.join(c.get('augments') or [])
    return c['name'] + (f' ({a[:40]})' if a else '')


EACH = "Each set's own"


DUAL = ('NIN', 'DNC')                                      # (a sub job that lets a PLD hold a second weapon)


def weapon_choices(cands, job, sub=None):
    """({label: candidate} for the main hand, {label: candidate} for the sub slot): his own gear this job can hold, each augmented copy once.
    The sub slot: shields and grips, and one-handed weapons too when the sub job dual wields."""
    mains, subs = {}, {}
    dual = (sub or '').upper() in DUAL or (job or '').upper() in DUAL
    for c in sorted(cands, key=lambda c: c['name']):
        if healing.fits(c, 'main'):
            mains.setdefault(weapon_label(c), c)
        if healing.fits(c, 'sub') and (c.get('shield') or not healing.fits(c, 'main') or c.get('skill') == 0 or (dual and not c.get('two_handed'))):
            subs.setdefault(weapon_label(c), c)
    return mains, subs


def find_label(choices, g):
    """The label in choices for a piece as his file names it (long or short name, its augments if it has them); None when he doesn't have it."""
    if not g:
        return None
    name, aug = g['name'].lower(), list(g.get('augments') or [])
    hits = [k for k, c in choices.items() if name in (c['name'].lower(), (c.get('enl') or '').lower())]
    for k in hits:
        if list(choices[k].get('augments') or []) == aug:
            return k
    return hits[0] if hits else None


def file_weapons(loaded):
    """[(name, {'main': name, 'sub': name})]: the weapon sets of his file (sets.weapons.BurtgangAegis ...), to pick from."""
    out = []
    for s in loaded.sets:
        if s['path'].startswith('sets.weapons.'):
            g = {k.lower(): v for k, v in s['gear'].items()}
            if g.get('main') or g.get('sub'):
                out.append((s['path'][len('sets.weapons.'):], {k: g[k] for k in ('main', 'sub') if g.get(k)}))
    return out


def weapons_ok(weapons):
    """'' or why the pair can't be held together (a two-handed weapon with a shield)."""
    m, s = (weapons or {}).get('main'), (weapons or {}).get('sub')
    if m and s and m.get('two_handed') and s.get('shield'):
        return f"{m['name']} is two-handed: it can't be held with {s['name']} (pick a grip, or Each set's own)"
    return ''


class Ctx:
    """What judging needs once per file: his gear (candidates and counts), the item data, his sub job, the HP of the sets he stands in.
    weapons: {'main': candidate, 'sub': candidate} he picked (his request 2026-11-10: "the sets would be vastly different between weapons"): every set is
    made with them (their stats count, the rest is built around them); they're never written into the sets. None: each set's own."""
    def __init__(self, loaded, job, sub, cands, counts, items, data, targets=None, cap_dt=False, weapons=None):
        self.loaded, self.job, self.sub = loaded, (job or '').upper(), sub
        self.cands, self.counts, self.items, self.data = cands, counts, items, data
        self.targets = targets or {}
        self.cap_dt = cap_dt
        self.weapons = weapons if weapons and any(weapons.values()) else None
        sets = loaded if not self.weapons else _Sets([dict(s, gear=with_weapons(s['gear'], self.weapons)) for s in loaded.sets])
        self.ihp = pld.idle_hp(sets, items, data, counts) if self.job == 'PLD' else None
        self._cache = {}


def need_for(row, focus, ctx):
    """What the set must also have: his numbers for it (damage taken, interruption), and with "cap damage taken" 50 / 50 in every tank set."""
    import doctor
    need = doctor.need_of(ctx.targets.get(row['path']) or {}, sird=True)
    if ctx.cap_dt and row['judge'] == 'pld' and focus not in ('Fast cast, cure cheat',):
        need['pdt'] = max(need.get('pdt', 0), 50)
        need['mdt'] = max(need.get('mdt', 0), 50)
    return need


def judge(row, ctx, focus=None, build=True):
    """The result of one set (the judge's own dict, plus 'gain' (%), 'better' (a change worth writing), 'need'). None for a set not judged here."""
    if row['judge'] not in ('pld', 'idle', 'job'):
        return None
    focus = focus or row['focus']
    need = need_for(row, focus, ctx)
    gear = with_weapons(row['gear'], ctx.weapons)
    key = (row['judge'], focus, tuple(sorted((k, g['name'], tuple(g.get('augments') or ())) for k, g in gear.items())),
           tuple(sorted(need.items())), row['path'].startswith('sets.buff'), build, ctx.ihp,
           job_sets.ability_of(row['path']) if row['judge'] == 'job' else None)
    if key in ctx._cache:
        return ctx._cache[key]
    a = (row['path'], gear, ctx.job, ctx.sub, ctx.cands, ctx.counts, ctx.items, ctx.data)
    keep = True if ctx.weapons else None                  # (his weapons stay put in every set)
    if row['judge'] == 'pld':
        r = pld.judge(*a, need=need, focus=focus, build=build, idle_hp=ctx.ihp)
        m0, m1 = r['now'], r['val']
    elif row['judge'] == 'idle':
        r = idle.judge(*a, need=need, focus=focus, build=build, keep_weapons=keep)
        m0, m1 = r['now'], r['val']
    else:
        r = job_sets.judge(*a, need=need, focus=focus, build=build, keep=keep)
        m0, m1 = r.get('main_now', r['now']), r.get('main_best', r['val'])
    gain = (m1 - m0) / abs(m0) * 100 if m0 else (100 if m1 > 0 else 0)
    if r['val'] <= r['now']:
        gain = 0
    fix = bool(need) and r.get('short_now', 0) > r.get('short', 0)
    if ctx.weapons:
        r['changes'] = {k: v for k, v in r['changes'].items() if k not in ('main', 'sub')}
        r['notes'] = list(r['notes']) + ['made with ' + ' and '.join(c['name'] for c in ctx.weapons.values() if c)
                                         + ' (your pick): they count in every set, but are not written into it']
    r = dict(r, gain=round(gain, 1), better=bool(r['changes']) and (gain >= 1 or fix), need=need, dt_fix=fix)
    ctx._cache[key] = r
    return r


def analyze(rows, ctx, progress=None, stop=None):
    """Judge every set that is judged here (in place: row['r']). progress(i, n, path); stop() True = stop now."""
    todo = [r for r in rows if r['judge'] in ('pld', 'idle', 'job')]
    for i, row in enumerate(todo):
        if stop and stop():
            break
        if progress:
            progress(i, len(todo), row['path'])
        try:
            row['r'] = judge(row, ctx, row.get('picked') or row['focus'])
            row.pop('error', None)
        except Exception as e:                    # (one set that can't be read doesn't stop the rest)
            row['r'], row['error'] = None, str(e)
    return rows


def words(row, r, which='now'):
    n = r['n_now'] if which == 'now' else r['n_best']
    f = r['focus']
    if row['judge'] == 'pld':
        return pld.words(n, f)
    if row['judge'] == 'job':
        return job_sets.say(n, f)
    return idle.words(n, r.get('base'))


def tip(row, r):
    if row['judge'] == 'pld':
        return pld.advice(r['n_best'], r['focus'], r.get('idle_hp'))
    if row['judge'] == 'job':
        return job_sets.tip(r['n_best'], r['focus'])
    return ''


def short(row, r, which='now'):
    """A few numbers for the list ('DT 50/50, Meva 640, HP +1100')."""
    n = r['n_now'] if which == 'now' else r['n_best']
    f = r['focus'] or ''
    if row['judge'] != 'pld':
        w = words(row, r, which)
        return w if len(w) <= 44 else w[:42] + '...'
    out = []
    if f.startswith('Tank'):
        out += [f"DT {n['phys']}/{n['magic']}", f"Meva {n['meva']}"]
    elif f.startswith('Enmity') or f == 'Reprisal' or f.startswith('Ability'):
        out.append(f"enmity +{n['enmity']}")
    if 'interrupted' in f or f.startswith('Cure') or f in ('Stoneskin', 'Enlight'):
        out.append(f"SIRD {n['sird']}%")
    if f.startswith('Phalanx'):
        out.append(f"Phalanx -{n['phalanx']}")
    if f.startswith('Cure'):
        out.append(f"cure {n['potency']}%")
    if f.startswith('Fast cast') or f == 'Reprisal':
        out.append(f"FC {n['fast']}%")
    if n.get('ability'):
        out.append(f"{n['ja']} JA piece(s)")
    if f == 'Doom':
        out.append(f"Holy Water +{n['holy_water']}")
    if f == 'Stoneskin':
        out.append(f"Stoneskin +{n['ss']}")
    out.append(f"HP +{n['hp']}")
    return ', '.join(out)


# ------------------------------------------------------------------ gear he doesn't have
def ideas(row, r, ctx, every, n=3):
    """[(slot, item name, points more)]: the pieces he doesn't own that would do the most for this set (one at a time in the best set)."""
    if row['judge'] == 'job':
        spec = (r['focus'], job_sets.ctx_for(ctx.job, ctx.sub, job_sets.ability_of(row['path']), None)) if hasattr(job_sets, 'ctx_for') else r['focus']
        try:
            return job_sets.upgrade_ideas(r['best'], spec, every, ctx.counts, None, True, n, job=ctx.job)
        except Exception:
            return []
    if row['judge'] != 'pld':
        return []
    floor = ctx.ihp if ctx.ihp and not r['focus'].startswith(pld.NO_FLOOR) else None
    spec = (r['focus'], floor) if floor else r['focus']
    only = set(r['cur']) if row['path'].startswith('sets.buff') else None
    pool = pld.useful([c for c in every if c['name'] not in (ctx.counts or {})])
    v0 = pld.value(r['best'], spec)
    found = {}
    for s in healing.SLOTS:
        if s in ('main', 'sub') or (only is not None and s not in only):
            continue
        for c in pool:
            if not healing.fits(c, s):
                continue
            g = dict(r['best'])
            g[s] = c
            d = pld.value(g, spec) - v0
            if d > 0.5 and d > found.get(c['name'], ('', 0))[1]:
                found[c['name']] = (s, d)
    top = sorted(found.items(), key=lambda x: -x[1][1])[:n]
    return [(s, name, round(d, 1)) for name, (s, d) in top]


# ------------------------------------------------------------------ the guides' checks on the whole file
def file_checks(rows, ctx):
    """[(level, text)] level 'bad' / 'warn' / 'ok': the guides' rules on the file as a whole (Paladin here; RDM, COR, BLU, DRK in job_guides)."""
    out = []
    fixes = job_guides.name_fixes(ctx.loaded) if ctx.loaded is not None else []
    if fixes:
        out.append(('bad', job_guides.rename_text(fixes)))
    if ctx.job != 'PLD':
        judged = [r for r in rows if r.get('r') and r['judge'] in ('job', 'idle')]
        if not judged:
            return out
        out += job_guides.file_checks(rows, ctx)
        better = [r for r in judged if r['r'].get('better')]
        out.append(('warn', f"{len(better)} sets can be better from gear you already own: tick them on the left and press Write.") if better else
                   ('ok', 'Every judged set is already the best your gear can do for what it is for.'))
        return out
    judged = [r for r in rows if r.get('r') and r['judge'] == 'pld']
    if not judged:
        return out
    tank = [r for r in judged if r['r']['focus'].startswith('Tank')]
    low = [r for r in tank if r['r']['n_now']['phys'] < 50 or r['r']['n_now']['magic'] < 50]
    if low:
        out.append(('bad', f"{len(low)} of {len(tank)} tank sets aren't at 50 % physical and magic damage taken "
                           f"({', '.join(r['path'][5:] for r in low[:4])}{' ...' if len(low) > 4 else ''}). "
                           "The 2025 guide's rule: never below 50 % in a set you tank in (magic: Shell does part of it)."))
    elif tank:
        out.append(('ok', f"All {len(tank)} tank sets are at 50 % damage taken."))
    if ctx.ihp:
        swaps = [r for r in judged if not r['r']['focus'].startswith(pld.NO_FLOOR + ('Tank',))]
        if swaps:
            lowest = min(swaps, key=lambda r: r['r']['n_now']['hp'])
            gap = ctx.ihp - lowest['r']['n_now']['hp']
            far = [r for r in swaps if ctx.ihp - r['r']['n_now']['hp'] > pld.HP_GAP]
            if far:
                out.append(('warn', f"{len(far)} sets have more than {pld.HP_GAP} HP less than the sets you stand in (+{ctx.ihp}). The lowest is "
                                    f"{lowest['path'][5:]} (HP +{lowest['r']['n_now']['hp']}, {gap} less): each time it goes on your HP is cut and it "
                                    "doesn't come back. The guide: the lowest-HP set (usually Fast Cast) matters more than your idle HP."))
            else:
                out.append(('ok', f"Every swap set keeps HP within {pld.HP_GAP} of the sets you stand in (+{ctx.ihp})."))
    sird = [r for r in judged if ('interrupted' in r['r']['focus'] or r['r']['focus'].startswith('Cure')) and r['r']['n_now']['sird'] < pld.SIRD_CAP]
    if sird:
        out.append(('warn', f"{len(sird)} sets cast while being hit are below 102 % interruption ({', '.join(r['path'][5:] for r in sird[:4])}"
                            f"{' ...' if len(sird) > 4 else ''}): 102 % (92 from gear with 5/5 merits) means a hit never stops the spell."))
    over = [r for r in judged if r['r']['focus'].startswith('Enmity') and r['r']['n_now']['enmity'] > pld.ENMITY_SPIKE]
    if over:
        out.append(('warn', f"{len(over)} enmity sets have more than +{pld.ENMITY_SPIKE} enmity: with Crusade (+30) past +200 is wasted; trade it for damage taken or HP."))
    for r in judged:
        f = r['r']['focus']
        if f.startswith('Phalanx'):
            skill = r['r']['n_now']['enh_skill']
            extra = min(skill - pld.step_start(skill), skill - pld.ENH_SKILL)      # (only the skill his gear adds can be traded away)
            if extra >= 10 and skill < 500:
                out.append(('warn', f"{r['path'][5:]}: Enhancing skill {skill} is {extra} past the Phalanx step it's on (it goes in steps). Phalanx gets 1 better at "
                                    f"{pld.next_phalanx_skill(skill)}; until then that skill gear could be Phalanx+ or interruption gear."))
    better = [r for r in judged if r['r'].get('better')]
    if better:
        out.append(('warn', f"{len(better)} sets can be better from gear you already own: tick them on the left and press Write."))
    else:
        out.append(('ok', 'Every judged set is already the best your gear can do for what it is for.'))
    return out


# ------------------------------------------------------------------ sets the guides say a Paladin has, that this file doesn't
# (only names GearSwap files pick by the spell or ability's own name: Mote's and Selindrile's rules both do; a plain file needs its own rule)
WANTED = {
    'PLD': [
        ('sets.precast.FC', 'Fast cast', 'every spell starts faster'),
        ('sets.midcast.Flash', 'Enmity', 'Flash: your main hate spell'),
        ('sets.midcast.Phalanx', 'Phalanx', 'Phalanx: the guide calls it core to tanking, "not a bonus"'),
        ('sets.midcast.Reprisal', 'Reprisal', 'Reprisal: enmity and duration'),
        ('sets.midcast.Cure', 'Cure yourself', 'cures while being hit'),
        ('sets.precast.JA.Invincible', 'Ability: Invincible', 'Invincible: Cab. Breeches'),
        ('sets.precast.JA["Holy Circle"]', 'Ability: Holy Circle', 'Holy Circle: Rev. Leggings'),
        ('sets.precast.JA["Shield Bash"]', 'Ability: Shield Bash', 'Shield Bash: Cab. Gauntlets'),
        ('sets.precast.JA.Sentinel', 'Ability: Sentinel', 'Sentinel: Cab. Leggings'),
        ('sets.precast.JA.Rampart', 'Ability: Rampart', 'Rampart: Cab. Coronet'),
        ('sets.precast.JA.Fealty', 'Ability: Fealty', 'Fealty: Cab. Surcoat'),
        ('sets.precast.JA.Chivalry', 'Chivalry', 'Chivalry: Cab. Gauntlets and MND'),
        ('sets.precast.JA["Divine Emblem"]', 'Ability: Divine Emblem', 'Divine Emblem: Chev. Sabatons'),
        ('sets.precast.JA.Cover', 'Ability: Cover', 'Cover: Rev. Coronet'),
        ('sets.buff.Doom', 'Doom', 'Doom: Holy Water+ and Cursna received+'),
    ],
}


def _norm(p):
    return p.replace('["', '.').replace('"]', '').replace("['", '.').replace("']", '').lower()


def missing(loaded, job):
    """[{path, group, focus, judge, why, gear: {}, new: True}] for the sets the guides list that the file doesn't have."""
    have = {_norm(s['path']) for s in loaded.sets}
    job = (job or '').upper()
    out = []
    if job != 'PLD' and not job_guides.picks_by_name(loaded):
        return out                    # (a file with its own set names - sets.BlueMagic.*, sets.JA.* - wouldn't use a set named the usual way)
    # (a set the "Fix the set names" button would make, or one the file has under its own name - sets.precast.FoldDoubleBust - counts as there)
    have |= {_norm(new) for old, new, w, h in job_guides.name_fixes(loaded)}
    squashed = {_norm(s['path']).replace(' ', '').replace("'", '') for s in loaded.sets}
    for path, focus, why in WANTED.get(job) or job_guides.WANTED.get(job, []):
        if _norm(path) in have:
            continue
        last = _norm(path).split('.')[-1].replace(' ', '').replace("'", '')
        if job != 'PLD' and focus == 'Ability' and any(x.split('.')[-1].startswith(last) for x in squashed):
            continue
        if job == 'PLD':
            out.append({'path': path, 'gear': {}, 'group': _group_pld(focus), 'focus': focus, 'judge': 'pld', 'new': True,
                        'why': f"Not in your file yet: {why}. " + WHY.get(focus, '')})
        else:
            out.append({'path': path, 'gear': {}, 'group': _group_job(focus, job, path), 'focus': focus, 'judge': 'job', 'new': True,
                        'why': f"Not in your file yet: {why}. " + (job_guides.why(job, focus) or (job_sets.FOCUS.get(focus) or {}).get('how', ''))})
    return out


def nothing_to_add(row):
    """A set the guides list that the file lacks, but his gear has nothing for (no piece that boosts the ability): not offered."""
    r = row.get('r')
    if not row.get('new') or not r:
        return False
    if not r.get('best'):
        return True
    n = r.get('n_best') or {}
    return bool(n.get('ability')) and not n.get('ja')


# ------------------------------------------------------------------ what gets written
def edit_for(row, loaded):
    """The fixer edit for one set's best gear: ('slots', path, changes) or, for a set the file doesn't have, ('new', path, gear, anchors)."""
    r = row.get('r')
    if not r:
        return None
    if row.get('new'):
        gear = {s: healing.gs_name(c) for s, c in r['best'].items() if c and s not in ('main', 'sub')}
        return ('new', row['path'], gear, [s['path'] for s in loaded.sets]) if gear else None
    if not r['changes']:
        return None
    return ('slots', row['path'], dict(r['changes']))
