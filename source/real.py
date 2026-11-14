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
REPLACES = {'Frazzle III': ('enf_skill', 'MND', 'enf_eff'), 'Distract III': ('enf_skill', 'MND', 'enf_eff'), 'Slow II': ('MND', 'enf_eff'),
            'Paralyze II': ('MND', 'enf_eff'), 'Phalanx': ('phalanx', 'enh_skill')}
WEIGHT = {'Frazzle III': 6, 'Distract III': 6, 'Slow II': 30, 'Paralyze II': 30, 'Phalanx': 30}

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
