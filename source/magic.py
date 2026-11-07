"""
GearSwap Doctor: nuke sets - black magic, scholar magic, blue magic (his request 2026-11-07: "add in magic calculations so it
will get me best in slot sets for blue magic, black magic, and scholar magic"). The damage is wsdist's (Kastra's simulator):
its spell maths follows BG Wiki's Magic Damage page step by step (RESEARCH.md, "Magic"); this file says which sets are nuke
sets, which spell judges each one, the abilities that go with it, and lets the weapons change for a mage.

  kind_of(path, job)        what a set is for: 'nuke' (elemental, helix, Kaustra, Impact), 'blue' (magical blue magic),
                            'bluephys' / 'bluebreath' (points: wsdist has no physical or breath blue magic) - or None
  spell_for(path, job)      the spell that judges it, and whether it's a magic burst
  plan(...)                 the set as wsdist sees it, with the owned gear for every slot (a mage's weapons too)
  best_set(...) / value(...)  wsdist's best set from his gear for that spell / the set as it is
"""
import contextlib
import io
import os
import re

ELEMENTS = ('Stone', 'Water', 'Aero', 'Fire', 'Blizzard', 'Thunder')
TIERS = ('', ' II', ' III', ' IV', ' V', ' VI')
ELEMENTAL = [e + t for e in ELEMENTS for t in TIERS]
JA = ['Stoneja', 'Waterja', 'Aeroja', 'Firaja', 'Blizzaja', 'Thundaja']
HELIX = ['Geohelix II', 'Hydrohelix II', 'Anemohelix II', 'Pyrohelix II', 'Cryohelix II', 'Ionohelix II', 'Luminohelix II',
         'Noctohelix II']
OTHER = ['Kaustra', 'Impact']
STORMS = ['None', 'Sandstorm II', 'Rainstorm II', 'Windstorm II', 'Firestorm II', 'Hailstorm II', 'Thunderstorm II', 'Aurorastorm II',
          'Voidstorm II', 'Sandstorm', 'Rainstorm', 'Windstorm', 'Firestorm', 'Hailstorm', 'Thunderstorm', 'Aurorastorm', 'Voidstorm']
STORM_OF = {'Earth': 'Sandstorm', 'Water': 'Rainstorm', 'Wind': 'Windstorm', 'Fire': 'Firestorm', 'Ice': 'Hailstorm',
            'Thunder': 'Thunderstorm', 'Light': 'Aurorastorm', 'Dark': 'Voidstorm'}
ELEMENT_OF = {'Stone': 'Earth', 'Water': 'Water', 'Aero': 'Wind', 'Fire': 'Fire', 'Blizzard': 'Ice', 'Thunder': 'Thunder',
              'Geo': 'Earth', 'Hydro': 'Water', 'Anemo': 'Wind', 'Pyro': 'Fire', 'Cryo': 'Ice', 'Iono': 'Thunder', 'Lumino': 'Light',
              'Nocto': 'Dark', 'Stoneja': 'Earth', 'Waterja': 'Water', 'Aeroja': 'Wind', 'Firaja': 'Fire', 'Blizzaja': 'Ice',
              'Thundaja': 'Thunder', 'Kaustra': 'Dark', 'Impact': 'Dark'}

# which spells each job can cast (the highest tier is the one a set is judged by unless its name says another)
JOB_SPELLS = {
    'BLM': ELEMENTAL + JA + ['Impact'], 'SCH': [s for s in ELEMENTAL if not s.endswith(' VI')] + HELIX + ['Kaustra', 'Impact'],
    'RDM': [s for s in ELEMENTAL if not s.endswith((' VI',))] + ['Impact'], 'GEO': [s for s in ELEMENTAL if not s.endswith(' VI')] + ['Impact'],
    'DRK': [s for s in ELEMENTAL if s.endswith(('e', 'r', 'o', 'd', ' II', ' III'))] + ['Impact'], 'WHM': ['Impact'],
}
DEFAULT_SPELL = {'BLM': 'Thunder VI', 'SCH': 'Thunder V', 'RDM': 'Thunder V', 'GEO': 'Thunder V', 'DRK': 'Thunder III', 'WHM': 'Impact'}
BLUE_DEFAULT = 'Spectral Floe'

# a set's name that says it isn't for damage
NOT_DAMAGE = re.compile(r'enfeeb|accuracy|macc|resist(?!ant)|occult|proc|stun|dia|bio|aspir|drain|death|recover|fastrecast|'
                        r'precast|skill|conserve|enmity|refresh|regen|cure|white ?wind|diamond|sheep|dream|yawn|cruel|battery|'
                        r'buff|healing|status|elementalenfeeble|intenfeeble|mndenfeeble', re.I)
BURST = re.compile(r'(?:^|[._\[\]"\'])(?:mb|magic_?burst|burst)(?:$|[._\[\]"\'])|magicburst|resistantmagicburst|utility\.mb', re.I)


# Magical blue magic, the Doctor's own (wsdist as downloaded has no blue magic). Per spell: fTP, its stat modifiers, the dINT multiplier,
# element, MP - BG Wiki's spell pages. Damage: fTP x (stats x modifiers) + dINT x M + Magic Damage, then the same steps as BG Wiki's
# Magic Damage page (and wsdist's nukes): elemental bonus, resist, burst, burst bonus, day / weather, MAB / MDB, Magic Crit II,
# the target's magic damage taken. (BG Wiki's outdated blue page also adds "level + 2" inside the fTP part: RESEARCH.md.)
BLUE = {
    'Sandspin': (1.0, {'INT': 0.2}, 0, 'Earth', 10),
    'Cursed Sphere': (1.5, {'INT': 0.3}, 0, 'Water', 25),
    'Blastbomb': (1.375, {'INT': 0.2}, 0, 'Fire', 30),
    'Bomb Toss': (1.625, {'INT': 0.2}, 0, 'Fire', 28),
    'Death Ray': (1.625, {'INT': 0.2, 'MND': 0.1}, 0, 'Dark', 50),
    'Mysterious Light': (0.96875, {'CHR': 0.3}, 0, 'Wind', 73),
    'Blitzstrahl': (1.5625, {'INT': 0.3, 'MND': 0.1}, 0, 'Thunder', 70),
    'Ice Break': (2.25, {'INT': 0.3}, 0, 'Ice', 64),
    'Eyes On Me': (2.625, {'CHR': 0.4}, 0, 'Dark', 112),
    'Corrosive Ooze': (2.171875, {'INT': 0.2}, 0, 'Water', 30),
    'Firespit': (3.0, {'INT': 0.2, 'MND': 0.2}, 0, 'Fire', 38),
    'Regurgitation': (1.875, {'MND': 0.3}, 0, 'Water', 36),
    'Mind Blast': (2.07421875, {'MND': 0.3}, 0, 'Thunder', 82),
    'Acrid Stream': (2.296875, {'MND': 0.3}, 2.0, 'Water', 77),
    'Leafstorm': (2.75, {'STR': 0.3}, 2.0, 'Wind', 92),
    'Blazing Bound': (3.0, {'STR': 0.3}, 2.0, 'Fire', 100),
    'Thermal Pulse': (2.75, {'VIT': 0.4}, 2.0, 'Fire', 116),
    'Charged Whisker': (4.5, {'DEX': 0.5}, 2.0, 'Thunder', 183),
    'Water Bomb': (2.0, {'INT': 0.2, 'MND': 0.1}, 1.5, 'Water', 100),
    'Dark Orb': (4.5, {'INT': 0.4}, 2.0, 'Dark', 143),
    'Evryone. Grudge': (5.0, {'MND': 0.4}, 2.0, 'Dark', 170),
    'Gates of Hades': (5.0, {'STR': 0.2, 'DEX': 0.2}, 1.0, 'Fire', 219),
    'Retinal Glare': (2.75, {'INT': 0.3, 'MND': 0.1}, 2.0, 'Light', 120),
    'Rail Cannon': (6.0, {'MND': 0.4}, 2.0, 'Light', 245),
    'Uproot': (4.0, {'VIT': 0.4}, 2.0, 'Light', 150),
    'Crashing Thunder': (6.5, {'AGI': 0.3}, 2.0, 'Thunder', 265),
    'Polar Roar': (5.0, {'STR': 0.2, 'INT': 0.2}, 2.0, 'Ice', 225),
    'Molting Plumage': (4.0, {'AGI': 0.3}, 2.0, 'Wind', 160),
    'Nectarous Deluge': (3.0, {'MND': 0.3}, 2.0, 'Water', 130),
    'Searing Tempest': (4.0, {'STR': 0.8}, 2.0, 'Fire', 180),
    'Spectral Floe': (4.0, {'INT': 0.8}, 2.0, 'Ice', 180),
    'Anvil Lightning': (4.0, {'DEX': 0.8}, 2.0, 'Thunder', 180),
    'Silent Storm': (4.0, {'AGI': 0.8}, 2.0, 'Wind', 180),
    'Entomb': (4.0, {'VIT': 0.8}, 2.0, 'Earth', 180),
    'Scouring Spate': (4.0, {'MND': 0.8}, 2.0, 'Water', 180),
    'Blinding Fulgor': (4.0, {'STR': 0.3, 'DEX': 0.3, 'AGI': 0.3}, 2.0, 'Light', 180),
    'Embalming Earth': (3.0, {'VIT': 0.3}, 2.0, 'Earth', 130),
    'Rending Deluge': (3.5, {'STR': 0.2, 'VIT': 0.2}, 2.0, 'Water', 155),
    'Foul Waters': (2.25, {'STR': 0.2, 'MND': 0.2}, 2.0, 'Water', 110),
    'Tenebral Crush': (4.0, {'INT': 0.3, 'MND': 0.3, 'VIT': 0.3}, 2.0, 'Dark', 116),
    'Diffusion Ray': (5.0, {'MND': 0.4}, 0, 'Light', 140),
    'Palling Salvo': (5.0, {'AGI': 0.6}, 0, 'Dark', 140),
}


def blue_spells():
    return list(BLUE)


def _blue_names():
    return list(BLUE)


RANKS = ["150%", "130%", "115%", "100%", "85%", "70%", "60%", "50%", "40%", "30%", "25%", "20%", "15%", "10%", "5%"]
RANK_BONUS = {"150%": 1.5, "130%": 1.15, "115%": 0.85, "100%": 0.60, "85%": 0.50, "70%": 0.40, "60%": 0.15, "50%": 0.05}
STORM_ELEMENT = {k: v for v, k in STORM_OF.items()}


def blue_cast(player, enemy, spell_name, input_metric='Damage dealt'):
    """One magical blue spell's average damage, as wsdist's cast_spell gives it: (damage, [damage, TP back, 1])."""
    import nuking
    ftp, wsc, dint_m, element, mp = BLUE[spell_name]
    st, es = player.stats, enemy.stats
    dint = max(0, st.get('INT', 0) - es.get('INT', 0))
    base = int(ftp * sum(st.get(k, 0) * v for k, v in wsc.items()) + dint_m * dint + st.get('Magic Damage', 0))
    macc = st.get('Magic Accuracy', 0) + st.get('main Magic Accuracy Skill', 0) + st.get('Blue Magic Skill', 0)         + nuking.get_dstat_macc(st.get('INT', 0), es.get('INT', 0))
    burst, bonus = 1.0, 1.0
    if player.abilities.get('Magic Burst'):
        macc += 100 + st.get('Magic Burst Accuracy', 0)
        rank = player.abilities.get('Enemy Resist Rank', '100%')
        up = RANKS[max(0, RANKS.index(rank) - 1)] if rank in RANKS else '115%'          # (a burst lowers the resist rank one step)
        burst += 0.35 + RANK_BONUS.get(up, 0)
        bonus += min(40, st.get('Magic Burst Damage', 0)) / 100 + st.get('Magic Burst Damage II', 0) / 100 + st.get('Magic Burst Damage Trait', 0) / 100
    meva = es.get('Magic Evasion', 0)
    hit = nuking.get_magic_hit_rate(macc, meva) if meva > 0 else 1.0
    resist = nuking.get_resist_state_average(hit)
    elem = 1 + (st.get(f'{element} Elemental Bonus', 0) + st.get('Elemental Bonus', 0)) / 100
    day = 1.0
    storm = player.abilities.get('Storm spell') or 'None'
    if player.gearset['waist']['Name'] == 'Hachirin-no-Obi' and STORM_ELEMENT.get(storm.replace(' II', '')) == element:
        day += 0.25 if 'II' in storm else 0.1
    ratio = (100 + st.get('Magic Attack', 0)) / (100 + es.get('Magic Defense', 0))
    crit = 1 + 0.25 * st.get('Magic Crit Rate II', 0) / 100
    mdt = 1 + es.get('Magic Damage Taken', 0) / 100
    dmg = base
    for m in (elem, resist, burst, bonus, day, ratio, crit, mdt):
        dmg = int(dmg * m)
    tp = int(mp * st.get('Occult Acumen', 0) / 100) * (1 + st.get('Store TP', 0) / 100)
    if input_metric == 'TP return':
        return tp, [dmg, tp, 1]
    return dmg, [dmg, tp, 1]


def _hook():
    """wsdist's set builder works out spells with its own cast_spell: a blue spell goes to blue_cast instead (no file of wsdist's
    changes for this; the updater's fix only names blue spells 'Blue Magic' in build_set, using BLUE from here)."""
    import wsdist_runner as W
    mods = W._wsdist()
    ws = mods['wsdist']
    if getattr(ws, '_gsd_blue', False):
        return mods
    orig = ws.cast_spell

    def cast(player, enemy, spell_name, spell_type, input_metric):
        if spell_name in BLUE:
            return blue_cast(player, enemy, spell_name, input_metric)
        return orig(player, enemy, spell_name, spell_type, input_metric)
    ws.cast_spell = cast
    ws.blu_spell_data = BLUE
    ws._gsd_blue = True
    return mods


def _cast(act, player, enemy, spell):
    if spell in BLUE:
        return blue_cast(player, enemy, spell)
    return act.cast_spell(player, enemy, spell, 'Elemental Magic', 'Damage dealt')


def kind_of(path, job):
    """What a set of this job is for, from its name. ('nuke' | 'blue' | 'bluephys' | 'bluebreath', spell named in it or None,
    burst) or None."""
    low = path.lower()
    named = None
    for s in re.findall(r'\["([^"]+)"\]|\[\'([^\']+)\'\]', path):
        s = s[0] or s[1]
        if s in ELEMENTAL + JA + HELIX + OTHER or s in _blue_names():
            named = s
    if job == 'BLU':
        if low.startswith('sets.weapons') or 'precast' in low or 'engaged' in low or low.startswith('sets.idle'):
            return None
        if named and named in _blue_names():
            return 'blue', named, bool(BURST.search(path))
        if 'breath' in low:
            return 'bluebreath', None, False
        if re.search(r'physical|\.str(?:$|\W)|strdex|strvit|strmnd|heavystrike|\.agi$|\.dex$|\.vit$', low):
            return 'bluephys', None, False
        if 'charged' in low and 'whisker' in low:
            return 'blue', 'Charged Whisker', False
        if NOT_DAMAGE.search(low) and 'magicalaccuracy' not in low:
            return None
        if re.search(r'bluemagic\.int|magical|\.dark$|\.earth$|nuke', low):
            spell = 'Tenebral Crush' if low.endswith('.dark') else 'Entomb' if low.endswith('.earth') else BLUE_DEFAULT
            return 'blue', spell, bool(BURST.search(path))
        if BURST.search(path):
            return 'blue', BLUE_DEFAULT, True
        return None
    if job not in JOB_SPELLS:
        return None
    if 'precast' in low or 'pet' in low or low.startswith('sets.weapons') or low.startswith('sets.idle') or 'engaged' in low:
        return None
    if named and named in JOB_SPELLS[job]:
        return 'nuke', named, bool(BURST.search(path))
    if NOT_DAMAGE.search(low.replace('resistant', '')):
        return None
    if 'helix' in low and job == 'SCH':
        return 'nuke', 'Noctohelix II', True if BURST.search(path) else False
    if 'kaustra' in low and job == 'SCH' and not re.search(r'resist', low):
        return 'nuke', 'Kaustra', bool(BURST.search(path))
    if re.search(r'impact(?!\.occult)', low) and 'occult' not in low:
        return 'nuke', 'Impact', bool(BURST.search(path))
    if NOT_DAMAGE.search(low) and 'resistant' not in low:
        return None
    if re.search(r'elemental magic|elemental_magic|\.elemental\b|nuke|hightier|freenuke|magicburst|magic_burst|\.mb\b|\.burst\b', low) \
            or BURST.search(path):
        return 'nuke', None, bool(BURST.search(path))
    return None


def spell_for(path, job):
    """(spell, burst) a nuke set is judged by - None when it isn't a nuke set."""
    k = kind_of(path, job)
    if not k or k[0] not in ('nuke', 'blue'):
        return None
    kind, named, burst = k
    if named:
        return named, burst
    if kind == 'blue':
        return BLUE_DEFAULT, burst
    low = path.lower()
    spell = DEFAULT_SPELL.get(job, 'Thunder V')
    if 'hightier' in low and job == 'BLM':
        spell = 'Thunder VI'
    return spell, burst


GEAR_SLOTS = ('ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet')


def base_set(loaded, path, job):
    """A burst set with only a few pieces (sets.Utility.MB, sets.MagicBurst = {hands=..., ring2=...}) goes on top of the nuke set:
    that set's path, or None. (Judged alone, it would look far worse than it is in game.)"""
    from gs_loader import SLOTS
    me = next((s for s in loaded.sets if s['path'] == path), None)
    if not me:
        return None
    k = kind_of(path, job)
    if not k or not k[2]:
        return None
    mine = {SLOTS.get(x.lower()) for x in me['gear']} & set(GEAR_SLOTS)
    if len(mine) >= 9:
        return None
    best, n = None, -1
    for s in loaded.sets:
        kk = kind_of(s['path'], job)
        if s['path'] == path or not kk or kk[2] or kk[0] != k[0]:
            continue
        slots = {SLOTS.get(x.lower()) for x in s['gear']} & set(GEAR_SLOTS)
        low = s['path'].lower()
        if re.search(r'helix|kaustra|impact', low) and not re.search(r'helix|kaustra|impact', path.lower()):
            continue                                 # (a burst of tier spells goes on the nuke set, not the helix set)
        score = len(slots) * 10 - s['path'].count('.') - s['path'].count('[') + (50 if 'elemental' in low else 0) \
            - (30 if re.search(r'resist|fodder|proc|occult', low) else 0)
        if len(slots) >= 9 and score > n:
            best, n = s['path'], score
    return best


def merged_gear(loaded, path, job):
    """The set as it is worn: its base nuke set with this one on top (base_set), else the set itself. (gear, base path or None)"""
    from gs_loader import SLOTS
    me = next(s for s in loaded.sets if s['path'] == path)
    base = base_set(loaded, path, job)
    if not base:
        return dict(me['gear']), None
    under = next(s for s in loaded.sets if s['path'] == base)
    out = {}
    for x, g in under['gear'].items():
        out[SLOTS.get(x.lower(), x)] = g
    for x, g in me['gear'].items():
        out[SLOTS.get(x.lower(), x)] = g
    return out, base


def spells_for(job):
    if job == 'BLU':
        return _blue_names()
    return JOB_SPELLS.get(job, ELEMENTAL)


def element_of(spell):
    if spell in BLUE:
        return BLUE[spell][3]
    head = spell.split()[0]
    for k, v in ELEMENT_OF.items():
        if head.startswith(k):
            return v
    return None


def abilities(job, spell, burst=False, storm='None', ebullience=False, klimaform=False, extra=None):
    """wsdist's abilities for a spell: the burst, a SCH's storm / Ebullience / Klimaform. (wsdist's spell maths reads the enemy's
    resist rank as '100%' and the like: 0 makes it stop.)"""
    import wsdist_runner as W
    out = W._abilities(0, ())
    out['Enemy Resist Rank'] = '100%'
    out['Magic Burst'] = bool(burst)
    out['Storm spell'] = storm or 'None'
    if job == 'SCH':
        out['Ebullience'] = bool(ebullience)
        out['Klimaform'] = bool(klimaform)
    out.update(extra or {})
    return out


def default_options(job, spell, burst=False):
    """What goes with a spell by default: a SCH has the matching storm II up and Klimaform for a helix / burst (BG Wiki's All Jobs
    Gear Sets/Scholar: 'Klimaform + Hailstorm II + Ebullience')."""
    o = {'burst': bool(burst), 'storm': 'None', 'ebullience': False, 'klimaform': False}
    if job == 'SCH':
        el = element_of(spell)
        if el in STORM_OF:
            o['storm'] = STORM_OF[el] + ' II'
        o['klimaform'] = True
        o['ebullience'] = spell in HELIX or spell == 'Kaustra'
    return o


MAGE_WEAPONS = ('BLM', 'SCH', 'GEO', 'WHM', 'RDM')


def free_weapons(job):
    """A mage's nuke set may change its weapons (they don't keep TP); a BLU's or a melee job's keep theirs."""
    return job in ('BLM', 'SCH', 'GEO', 'WHM')


def plan(job, sub, gear, weapon_sets, owned_ids, items, index, free=None):
    """(owned {wsdist slot: [entries]}, current {wsdist slot: entry}, notes): plan_ws for a spell, with the weapons opened up for a
    mage (any owned weapon / grip / shield this job can use, wsdist keeps a staff with a grip)."""
    import checks
    import wsdist_runner as W
    owned, cur, notes, _ = W.plan_ws(job, sub, None, gear, weapon_sets, owned_ids, items, index)
    if free is None:
        free = free_weapons(job)
    if free:
        for slot, bit in (('main', 0), ('sub', 1)):
            opts, seen = [], set()
            for iid in owned_ids:
                it = items.by_id.get(iid)
                if not it or not it['slots'] & (1 << bit):
                    continue
                if it['jobs'] and job in checks.JOBS and not it['jobs'] & (1 << checks.JOBS[job]):
                    continue
                ents = W.entries_for(it['en'], items, index)
                if not ents:
                    continue
                e = W.pick_variant(ents)
                if job.lower() in e.get('Jobs', []) and e['Name2'] not in seen:
                    seen.add(e['Name2'])
                    opts.append(e)
            if cur.get(slot) and cur[slot]['Name2'] not in seen:
                opts.append(cur[slot])
            owned[slot] = opts or ([cur[slot]] if cur.get(slot) else [])
        notes.append('the weapons may change too (a mage keeps no TP)')
    return owned, cur, notes


def _setup(job, sub, current, enemy_name, buffs, opts):
    import wsdist_runner as W
    mods = _hook()
    stats, debuffs, _aftermath = W.buff_stats(buffs)
    enemy = W._enemy(enemy_name, debuffs)
    empty = mods['gear'].Empty
    start = {slot: current.get(slot) or empty for slot in W.SLOT_MAP.values()}
    return mods, stats, enemy, empty, start


def value(job, sub, spell, current, enemy_name='Apex Toad', ml=20, buffs=None, opts=None, info=None):
    """The average damage of one cast with this set."""
    import wsdist_runner as W
    opts = opts or {}
    mods, stats, enemy, empty, start = _setup(job, sub, current, enemy_name, buffs, opts)
    ab = abilities(job, spell, opts.get('burst'), opts.get('storm'), opts.get('ebullience'), opts.get('klimaform'))
    st = _spell_type(spell)
    cwd = os.getcwd()
    os.chdir(W.WS_DIR)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            p = mods['create_player'].create_player(job.lower(), sub.lower(), ml, gearset=dict(start), buffs=stats, abilities=ab)
            dmg = _cast(mods['actions'], p, enemy, spell)
            if info is not None:
                info['now'] = W.dt_of(p)
    finally:
        os.chdir(cwd)
    return dmg[1][0]


def _spell_type(spell):
    return 'Blue Magic' if spell in _blue_names() else 'Elemental Magic'


def best_set(job, sub, spell, owned, current, enemy_name='Apex Toad', ml=20, req=None, info=None, buffs=None, opts=None):
    """(best {wsdist slot: entry}, its damage, the damage now): wsdist's build_set for a spell, from the gear he owns. req: the
    damage taken it must have (wsdist_runner.dt_requirement)."""
    import wsdist_runner as W
    opts = opts or {}
    mods, stats, enemy, empty, start = _setup(job, sub, current, enemy_name, buffs, opts)
    cp, ws_mod, act = mods['create_player'], mods['wsdist'], mods['actions']
    check = {slot: list(owned.get(slot, [])) for slot in W.SLOT_MAP.values()}
    for slot in check:
        seen, uniq = set(), []
        for x in check[slot]:
            if x['Name2'] not in seen:
                seen.add(x['Name2'])
                uniq.append(x)
        check[slot] = uniq
        if start[slot] is not empty and all(x['Name2'] != start[slot]['Name2'] for x in check[slot]):
            check[slot].append(start[slot])
        if not check[slot]:
            check[slot] = [start[slot]]
    ab = abilities(job, spell, opts.get('burst'), opts.get('storm'), opts.get('ebullience'), opts.get('klimaform'))
    st = _spell_type(spell)
    cwd = os.getcwd()
    os.chdir(W.WS_DIR)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            p0 = cp.create_player(job.lower(), sub.lower(), ml, gearset=dict(start), buffs=stats, abilities=ab)
            now = _cast(act, p0, enemy, spell)[1][0]
            dt_now = W.dt_of(p0)
            rp, rm = req if req else (0, 0)
            first = start
            if req:
                first, (rp, rm) = W.dt_start(cp, job, sub, ml, start, check, req, ab, stats)
            try:
                best, _ = ws_mod.build_set(job.lower(), sub.lower(), ml, stats, ab, enemy, 'None', spell, 'spell cast', 1000,
                                           check, dict(first), rp, rm, 'Damage dealt', False, 0)
            except UnboundLocalError:                        # (wsdist found nothing to change)
                best = cp.create_player(job.lower(), sub.lower(), ml, gearset=dict(first), buffs=stats, abilities=ab)
            after = _cast(act, best, enemy, spell)[1][0]
            dt_best = W.dt_of(best)
    finally:
        os.chdir(cwd)
    if info is not None:
        info.update({'now': dt_now, 'best': dt_best, 'asked': req})
    return best.gearset, after, now


HOODED = ('Cohort Cloak', 'Cohort Cloak +1', 'Crepuscular Cloak', 'Twilight Cloak')


def head_in(gear):
    return any(str(k).lower() == 'head' and str(g.get('name', '')).lower() not in ('', 'empty') for k, g in (gear or {}).items())


def hood_fix(changes, best_body, cur_head):
    """A hooded cloak covers the head: the set's head has to go ('empty'), or GearSwap tries to wear both."""
    if best_body in HOODED and cur_head:
        changes['head'] = 'empty'
    return changes


def words(spell, opts):
    """'Thunder VI, magic burst, Thunderstorm II, Klimaform'."""
    out = [spell]
    if opts.get('burst'):
        out.append('magic burst')
    if opts.get('storm') and opts['storm'] != 'None':
        out.append(opts['storm'])
    if opts.get('ebullience'):
        out.append('Ebullience')
    if opts.get('klimaform'):
        out.append('Klimaform')
    return ', '.join(out)
