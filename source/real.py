"""
Real results in place of points (PLAN.md E1, 2026-11-14): what a set really does, by the game's own formulas, where one is known.

  phalanx_hit(job, enh_skill_gear, phalanx_gear)   damage Phalanx takes off every hit, or None for a job whose Enhancing skill isn't listed here
  spell_of(path)                                    the enfeebling spell a set is named for, when its strength has a formula here
  enfeeble(spell, skill_gear, mnd_gear, effect_gear, job, sub, enemy)   {'value', 'unit', 'cap', 'words'}
  basis(judge, focus, path, job)                    ('real' or 'points', a line for the tab)

Formulas (RESEARCH.md "Real results, 2026-11-14"): BG Wiki's spell pages. Frazzle III / Distract III: exact. Slow II / Paralyze II: the pages give the
lowest and highest value and the MND difference for each; a straight line between is assumed (said as "about").
What still runs on points, and why: landing a spell needs the monster's Magic Evasion, which no source gives for the monsters in the list.
"""
import os
import math
import re

# Enhancing magic skill at 99 with no gear: the job's skill cap + 16 from merits (Master Levels add more: not counted, as pld.ENH_SKILL)
ENH_BASE = {'RDM': 404 + 16, 'RUN': 388 + 16, 'PLD': 334 + 16}
# Enfeebling magic skill with no gear (RDM A+: 424, + 16 merits). Only RDM has the spells below.
ENF_BASE = {'RDM': 424 + 16}
ENEMY = 'Apex Toad'             # the monster picked in the app (doctor.checkup and the window set it)
SPELLS = {
    'frazzleiii': 'Frazzle III', 'distractiii': 'Distract III', 'slowii': 'Slow II', 'paralyzeii': 'Paralyze II',
}
_BASE_MND = {}


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def phalanx_from_skill(skill):
    import pld
    return pld.phalanx_from_skill(skill)


def phalanx_hit(job, enh_skill_gear=0, phalanx_gear=0):
    base = ENH_BASE.get((job or '').upper())
    if base is None:
        return None
    return phalanx_from_skill(base + enh_skill_gear) + phalanx_gear


def spell_of(path):
    """'Frazzle III' for sets.midcast['Frazzle III'] ...; None for any other set."""
    parts = [_norm(p) for p in re.split(r"[.\[\]'\"]+", path or '') if p]
    for p in parts:
        if p in SPELLS:
            return SPELLS[p]
    return None


def base_mnd(job, sub):
    """MND with no gear (wsdist's table of the job at 99; a middling number when wsdist isn't there)."""
    key = ((job or '').upper(), (sub or '').upper())
    if key not in _BASE_MND:
        try:
            import healing
            _BASE_MND[key] = healing.job_base(key[0], key[1] or 'WHM')[0]
        except Exception:
            _BASE_MND[key] = 95
    return _BASE_MND[key]


def enemy_stat(stat, enemy=None, default=250):
    """A stat of the picked monster from wsdist's list (with GearSwap Doctor's own monsters)."""
    try:
        import wsdist_runner as W
        e = W._wsdist()['enemies'].preset_enemies.get(enemy or ENEMY)
        return int(e[stat]) if e and e.get(stat) else default
    except Exception:
        return default


def _line(x, x0, x1, y0, y1):
    x = max(x0, min(x1, x))
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def enfeeble(spell, skill_gear=0, mnd_gear=0, effect_gear=0, job='RDM', sub='', enemy=None):
    """What the spell does when it lands, with this gear: {'value': number, 'unit', 'cap', 'words', 'dmnd', 'skill'}; None for a job without the spell.
    "Enfeebling magic effect +n" gear multiplies it (n %); Saboteur is not counted (it's the same for every set)."""
    job = (job or '').upper()
    if job not in ENF_BASE or spell not in SPELLS.values():
        return None
    skill = ENF_BASE[job] + skill_gear
    dmnd = base_mnd(job, sub) + mnd_gear - enemy_stat('MND', enemy)
    mult = 1 + effect_gear / 100
    who = enemy or ENEMY
    if spell in ('Frazzle III', 'Distract III'):
        start = 205 if spell == 'Frazzle III' else 190
        raw = min(130, max(0, math.floor(6 / 21 * (skill - start))) + max(0, min(10, math.floor(dmnd / 5))))
        v = math.floor(raw * mult)
        what = 'Magic Evasion' if spell == 'Frazzle III' else 'Evasion'
        return {'value': v, 'unit': what, 'cap': 130, 'dmnd': dmnd, 'skill': skill, 'capped': raw >= 130,
                'words': f"{spell}: {what} -{v} on {who}" + (' (130 before effect gear is the most)' if raw >= 130 else f' (skill {skill}, 130 before effect gear is the most)')}
    if spell == 'Slow II':
        raw = _line(dmnd, -75, 75, 16.5, 39.1)
    else:
        raw = _line(dmnd, -40, 40, 14.0, 34.0)
    v = round(raw * mult, 1)
    top = 75 if spell == 'Slow II' else 40
    return {'value': v, 'unit': '%', 'cap': None, 'dmnd': dmnd, 'skill': skill, 'capped': dmnd >= top,
            'words': f"{spell}: about {v} % on {who} (your MND {dmnd:+d} against its MND" + (': more MND adds nothing)' if dmnd >= top else f', the most at +{top})')}


# which stats the formula stands in for (their points are dropped), and how much one unit of the real number weighs against the points that stay
REPLACES = {'Hit rate': ('racc', 'acc', 'step_acc'), 'Frazzle III': ('enf_skill', 'MND', 'enf_eff'), 'Distract III': ('enf_skill', 'MND', 'enf_eff'), 'Slow II': ('MND', 'enf_eff'),
            'Paralyze II': ('MND', 'enf_eff'), 'Phalanx': ('phalanx', 'enh_skill')}
WEIGHT = {'Frazzle III': 6, 'Distract III': 6, 'Slow II': 30, 'Paralyze II': 30, 'Phalanx': 30}

# ------------------------------------------------------------------ hit rate against the picked monster (PLAN.md E1 b, 2026-11-14)
# wsdist makes the player with only the set's weapons on (its own job tables, skills, traits, buffs); the armour's accuracy is added on top:
# Accuracy+ and DEX x 0.75 (melee), Ranged Accuracy+ and AGI x 0.75 (shots). Hit rate = 75 + (accuracy - Evasion) / 2, 20 to 95 %
# (99 % for a one-handed main weapon): BG Wiki Hit Rate, as wsdist's get_hit_rate has it.
BUFFS = None                    # what's up while sets are judged (wsdist_runner.buff_spec; the app sets it like ENEMY)
WEAPON_SLOTS = ('main', 'sub', 'range', 'ammo')
_ACC = {}


def acc_base(job, sub, weapons):
    """{'melee', 'ranged', 'cap_melee', 'evasion', 'buffs'} with only these weapons on ((slot, item name) pairs), or None when wsdist can't say."""
    key = ((job or '').upper(), (sub or '').upper(), tuple(sorted(weapons)), repr(BUFFS), ENEMY)
    if key in _ACC:
        return _ACC[key]
    out = None
    try:
        import contextlib
        import io
        import wsdist_runner as W
        mods = W._wsdist()
        cp, empty, idx = mods['create_player'], mods['gear'].Empty, W.gear_index()
        start = {s: empty for s in W.SLOT_MAP.values()}
        main_skill = None
        for slot, name in weapons:
            e = idx.get(name.lower())
            if e and slot in W.SLOT_MAP:
                start[W.SLOT_MAP[slot]] = W.pick_variant(e)
                if slot == 'main':
                    main_skill = start['main'].get('Skill Type')
        stats, debuffs, _am = W.buff_stats(BUFFS)
        cwd = os.getcwd()
        os.chdir(W.WS_DIR)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                p = cp.create_player(key[0].lower(), (key[1] or 'war').lower(), 20, gearset=start, buffs=stats, abilities={})
        finally:
            os.chdir(cwd)
        two = main_skill in ('Great Sword', 'Great Axe', 'Scythe', 'Polearm', 'Great Katana', 'Staff')
        out = {'melee': int(p.stats.get('Accuracy1', 0)), 'ranged': int(p.stats.get('Ranged Accuracy', 0)), 'cap_melee': 95 if two else 99,
               'evasion': int(W._enemy(ENEMY, debuffs).stats.get('Evasion', 0)), 'buffs': bool(BUFFS)}
        if not out['evasion']:
            out = None
    except Exception:
        out = None
    _ACC[key] = out
    return out


def hit_rate(accuracy, evasion, cap=95):
    """% of hits that land."""
    return max(20.0, min(float(cap), 75 + 0.5 * (accuracy - evasion)))


def hit(kind, base, gear, extra=0):
    """{'value' (%), 'acc', 'words'} for a set: gear = {slot: candidate}; the weapons are in base already. kind 'ranged' / 'melee'."""
    import math
    arm = [c['stats'] for s, c in gear.items() if c and s not in WEAPON_SLOTS]
    if kind == 'ranged':
        acc = base['ranged'] + sum(x.get('racc', 0) for x in arm) + math.floor(0.75 * sum(x.get('AGI', 0) for x in arm))
        cap = 95
    else:
        acc = base['melee'] + sum(x.get('acc', 0) for x in arm) + math.floor(0.75 * sum(x.get('DEX', 0) for x in arm)) + extra
        cap = base['cap_melee']
    v = hit_rate(acc, base['evasion'], cap)
    over = acc - (base['evasion'] + 2 * (cap - 75))
    return {'value': round(v, 1), 'acc': acc, 'cap': cap,
            'words': (f"hits {v:.0f} % of the time on {ENEMY} ({'ranged ' if kind == 'ranged' else ''}accuracy {acc} against its Evasion {base['evasion']}"
                      + (f': {over} more than the {cap} % cap needs' if over > 0 else f', the cap is {cap} %')
                      + ('' if base['buffs'] else ', no buffs counted') + ')')}


REAL_FOCUS = ('Fast cast', 'Dread Spikes', 'Snapshot', 'Treasure Hunter', 'Blood Pact delay', 'Phantom Roll')


def basis(judge, focus, path='', job=''):
    """('real' | 'points', a plain line): how this set is scored. For the Gear Optimization tab."""
    job = (job or '').upper()
    f = focus or ''
    if judge == 'wsdist':
        return 'real', 'Scored by real results: damage simulated against the monster you picked (wsdist).'
    if judge == 'pld' and f.startswith('Phalanx'):
        return 'real', 'Scored by real results: the damage Phalanx takes off each hit (Enhancing skill steps + Phalanx gear).'
    if judge == 'job':
        sp = spell_of(path)
        if sp and job in ENF_BASE and f.startswith('Enfeebling') and f != 'Enfeebling (accuracy)':
            return 'real', (f"Scored by real results: what {sp} does to the monster you picked (BG Wiki's formula). Landing it is still points: no source "
                            "gives the monster's Magic Evasion.")
        if f.startswith('Ranged shots') or f == 'Steps':
            return 'real', ("Scored by real results where wsdist is there: how often you hit the monster you picked (accuracy against its Evasion, "
                            "with the buffs you set); accuracy past the cap counts for nothing.")
        if f == 'Phalanx' and job in ENH_BASE:
            return 'real', 'Scored by real results: the damage Phalanx takes off each hit (Enhancing skill steps + Phalanx gear).'
        if f.startswith('Fast cast'):
            return 'real', 'Scored by real results: casting time cut, against the 80 % cap.'
        if f in ('Cure', 'Curaga', 'Cure (self)', 'Waltz') or f.startswith(('Cure', 'Curaga')):
            return 'real', 'Scored by real results: HP healed by the spell.'
        if f in REAL_FOCUS:
            return 'real', 'Scored by real results: the number the game uses, against its cap.'
        if any(w in f.lower() for w in ('enfeebl', 'accuracy', 'stun', 'absorb', 'flash', 'impact', 'songs: enfeeble')):
            return 'points', "Scored by points: landing it depends on the monster's Magic Evasion, which no source gives, so each stat counts by the guides' order."
    return 'points', "Scored by points: no formula is known for this kind of set, so each stat counts by the guides' order."
