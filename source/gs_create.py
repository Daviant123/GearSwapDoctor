"""
GearSwap Doctor: a brand new GearSwap file, with recommended sets built from the gear a character owns (his request 2026-10-31: "add a create gearswap ... a new tab and a full suite").

Set names are the common ones (his 64 files that loaded, and Mote's): sets.precast.FC, sets.precast.WS[...], sets.midcast.Cure, sets.engaged, sets.idle, sets.defense.PDT...
so every other tab of the Doctor can work on the result. Two ways to run them:
  Standalone  all the rules are in the file itself: nothing else needed
  Mote        uses Mote-Include, which comes with GearSwap: what most shared files build on
Recommended weapon skills are BG Wiki's All Jobs Gear Sets pages. Who judges a set: wsdist (weapon skills, TP), healing.py, idle.py, pup.py, and points here for what none of them cover
(points are my judgement; caps are the game's). It never overwrites a file.
"""
import os
import re

import checks
import fixer
import healing
import idle
import pld
import pup
import rema

ALL_JOBS = list(checks.JOBS)
MAGES = ('WHM', 'BLM', 'GEO', 'SCH', 'SMN', 'BRD')
DW_MAIN, DW_SUB = ('NIN', 'DNC', 'THF', 'BLU'), ('NIN', 'DNC')
SHIELD_JOBS = ('PLD', 'WAR', 'RDM', 'BLU', 'BST', 'DRK', 'THF', 'BRD', 'NIN', 'RUN', 'WHM', 'GEO', 'SCH')
ONE_HANDED = ('Sword', 'Dagger', 'Axe', 'Club', 'Katana')
RANGED_WS = ('Archery', 'Marksmanship')

# bg-wiki.com/ffxi/All_Jobs_Gear_Sets/<job>, 2026-10-31
WS = {
    'WAR': ['Upheaval', "Ukko's Fury", "King's Justice", 'Metatron Torment', 'Raging Rush', 'Savage Blade', 'Decimation', 'Mistral Axe', 'Cloudsplitter', 'Disaster', 'Fimbulvetr', 'Scourge', 'Resolution', 'Impulse Drive', 'Stardiver', 'Judgment'],
    'MNK': ['Victory Smite', "Ascetic's Fury", 'Maru Kala', 'Shijin Spiral', 'Final Heaven', 'Dragon Blow', 'Howling Fist', 'Asuran Fists', 'Dragon Kick', 'Tornado Kick', 'Raging Fists'],
    'WHM': ['Black Halo', 'Randgrith', 'Mystic Boon', 'Hexa Strike', 'Realmrazer', 'Seraph Strike'],
    'BLM': ['Vidohunir', 'Cataclysm', 'Earth Crusher', 'Retribution', 'Shattersoul', 'Gate of Tartarus', 'Spiral Hell', 'Cross Reaper'],
    'RDM': ['Savage Blade', 'Chant du Cygne', 'Death Blossom', 'Knights of Round', 'Imperator', 'Requiescat', 'Sanguine Blade', 'Seraph Blade', 'Red Lotus Blade', 'Mercy Stroke', 'Ruthless Stroke', 'Evisceration', 'Black Halo', 'Aeolian Edge'],
    'THF': ["Rudra's Storm", 'Ruthless Stroke', 'Mandalic Stab', 'Evisceration', 'Mercy Stroke', 'Exenterator', 'Shark Bite', 'Savage Blade', 'Aeolian Edge'],
    'PLD': ['Savage Blade', 'Imperator', 'Knights of Round', 'Chant du Cygne', 'Requiescat', 'Torcleaver', 'Fimbulvetr'],
    'DRK': ['Catastrophe', 'Origin', 'Entropy', 'Quietus', 'Cross Reaper', 'Insurgency', 'Torcleaver', 'Fimbulvetr', 'Scourge', 'Resolution', 'Judgment'],
    'BST': ['Blitz', 'Decimation', 'Mistral Axe', 'Onslaught', 'Calamity', 'Rampage', 'Ruinator', 'Bora Axe', 'Primal Rend', 'Cloudsplitter'],
    'BRD': ['Mordant Rime', 'Ruthless Stroke', "Rudra's Storm", 'Mercy Stroke', 'Evisceration', 'Aeolian Edge', 'Savage Blade'],
    'RNG': ['Terminus', 'Coronach', 'Last Stand', 'Hot Shot', 'Trueflight', 'Wildfire', 'Sarv', "Jishnu's Radiance", 'Flaming Arrow', 'Namas Arrow', 'Apex Arrow', 'Savage Blade', 'Aeolian Edge'],
    'SMN': ['Garland of Bliss', 'Shattersoul', 'Retribution', 'Gate of Tartarus'],
    'SAM': ['Tachi: Fudo', 'Tachi: Mumei', 'Tachi: Shoha', 'Tachi: Kaiten', 'Tachi: Jinpu', 'Tachi: Koki', 'Tachi: Rana', 'Namas Arrow', 'Impulse Drive'],
    'NIN': ['Blade: Shun', 'Blade: Ten', 'Blade: Metsu', 'Zesho Meppo', 'Blade: Ku', 'Blade: Hi', 'Blade: Kamu', 'Savage Blade', 'Blade: Chi', 'Blade: Teki', 'Blade: To', 'Blade: Ei', 'Aeolian Edge', 'Evisceration', 'Asuran Fists'],
    'DRG': ['Diarmuid', 'Stardiver', "Camlann's Torment", 'Drakesbane', 'Impulse Drive', 'Geirskogul', 'Savage Blade'],
    'BLU': ['Expiacion', 'Chant du Cygne', 'Requiescat', 'Imperator', 'Savage Blade', 'Sanguine Blade', 'Red Lotus Blade'],
    'COR': ['Terminus', 'Last Stand', 'Hot Shot', 'Leaden Salute', 'Wildfire', 'Savage Blade', 'Evisceration', 'Aeolian Edge'],
    'PUP': ['Stringing Pummel', 'Maru Kala', 'Victory Smite', 'Shijin Spiral', 'Howling Fist', 'Dragon Blow', 'Asuran Fists'],
    'DNC': ['Ruthless Stroke', "Rudra's Storm", 'Pyrrhic Kleos', 'Evisceration', 'Exenterator', 'Shark Bite', 'Aeolian Edge'],
    'SCH': ['Omniscience', 'Cataclysm'],
    'GEO': ['Black Halo', 'Exudation'],
    'RUN': ['Dimidiation', 'Fimbulvetr', 'Resolution'],
}
RX = [(k, re.compile(rx)) for k, rx in [
    ('INT', r'\bINT ?\+(\d+)'), ('AGI', r'\bAGI ?\+(\d+)'), ('STR', r'\bSTR ?\+(\d+)'), ('DEX', r'\bDEX ?\+(\d+)'), ('matk', r'"Magic Atk\. Bonus" ?\+(\d+)|"Mag\. ?Atk\. ?Bns\." ?\+(\d+)'),
    ('mdmg', r'Magic Damage ?\+(\d+)'), ('macc', r'Magic Accuracy ?\+(\d+)|Mag\. ?Acc\. ?\+(\d+)'), ('mbb', r'Magic burst damage ?\+(\d+)'), ('mbb2', r'Magic burst damage II ?\+(\d+)'),
    ('acc', r'(?<![a-z] )\bAccuracy ?\+(\d+)'), ('att', r'(?<![a-z] )\bAttack ?\+(\d+)'), ('racc', r'Ranged Accuracy ?\+(\d+)'), ('ratt', r'Ranged Attack ?\+(\d+)'), ('stp', r'"Store TP" ?\+(\d+)'),
    ('enh_skill', r'Enhancing magic skill ?\+(\d+)'), ('enh_dur', r'Enhancing magic (?:effect )?duration ?\+(\d+)'), ('enf_skill', r'Enfeebling magic skill ?\+(\d+)'), ('dark_skill', r'Dark magic skill ?\+(\d+)'),
    ('div_skill', r'Divine magic skill ?\+(\d+)'), ('ele_skill', r'Elemental magic skill ?\+(\d+)'), ('nin_skill', r'Ninjutsu skill ?\+(\d+)'), ('nin_dmg', r'Ninjutsu damage ?\+(\d+)'), ('blue_skill', r'Blue magic skill ?\+(\d+)'),
    ('sing', r'Singing skill ?\+(\d+)'), ('instr', r'(?:String|Wind) instrument skill ?\+(\d+)'), ('songs', r'All songs ?\+(\d+)'), ('song_dur', r'Song effect duration ?\+(\d+)'), ('song_fast', r'Song spellcasting time ?-(\d+)'),
    ('geo_skill', r'Geomancy skill ?\+(\d+)'), ('geomancy', r'\bGeomancy ?\+(\d+)'), ('bell', r'Handbell skill ?\+(\d+)'), ('indi_dur', r'"?Indicolure"? (?:spell |effect )?duration ?\+(\d+)'), ('smn_skill', r'Summoning magic skill ?\+(\d+)'),
    ('bp1', r'"Blood Pact" ability delay ?-(\d+)'), ('bp2', r'"Blood Pact" ability delay II ?-(\d+)'), ('perp', r'Avatar perpetuation cost ?-(\d+)'), ('th', r'"Treasure Hunter" ?\+(\d+)'), ('roll', r'"Phantom Roll" ?\+ ?(\d+)(?! *%)|(?<!")Phantom Roll ?\+(\d+)'),
    ('qd', r'"Quick Draw" ?\+(\d+)'), ('snap', r'"Snapshot" ?\+(\d+)'), ('rapid', r'"Rapid Shot" ?\+(\d+)'), ('trueshot', r'"True Shot" ?\+(\d+)'), ('recycle', r'"Recycle" ?\+(\d+)'), ('drain', r'"Drain" and "Aspir" potency ?\+(\d+)'),
    ('dual', r'"Dual Wield" ?\+(\d+)'),
]]
AV_RX = re.compile(r'(?:Avatar|Pet):')


def parse(text):
    """{stat: value} for what isn't in healing.parse_text: the master's part of an item's text or an augment."""
    cut = healing.CUT_RX.search(text)
    own = text[:cut.start()] if cut else text
    out = {}
    for k, rx in RX:
        n = sum(int(y) for x in rx.findall(own) for y in (x if isinstance(x, tuple) else (x,)) if y)
        if n:
            out[k] = n
    # an Avatar's part: SMN, and any pet that isn't an automaton (Pet: is read by pup.parse too; the names don't clash)
    for m in AV_RX.finditer(text):
        rest = text[m.end():]
        c = re.search(r'\bSet:|Latent effect|Unity Ranking:|Wyvern:|Automaton:|Enchantment:', rest)
        part = rest[:c.start()] if c else rest
        for k, rx in pup.PET_RX:
            n = sum(int(x) for x in rx.findall(part))
            if n:
                out['ava_' + k] = out.get('ava_' + k, 0) + n
    return out


# points per stat, and caps. Magic burst gear stops at 40 % (BG Wiki), Blood Pact delay at 15 each.
CAPS = {'mbb': 40, 'bp1': 15, 'bp2': 15, 'fast': 80}
POINTS = {
    'nuke': {'matk': 3, 'mdmg': 1.5, 'INT': 1.5, 'macc': 0.8, 'ele_skill': 0.5, 'conserve': 0.3},
    'burst': {'mbb': 12, 'mbb2': 16, 'matk': 3, 'mdmg': 1.5, 'INT': 1.5, 'macc': 0.8, 'ele_skill': 0.5},
    'enfeeble': {'macc': 1.5, 'enf_skill': 1.2, 'MND': 1.2, 'INT': 0.8},
    'enhancing': {'enh_dur': 8, 'enh_skill': 2, 'conserve': 0.5, 'MND': 0.2},
    'stoneskin': {'enh_skill': 1, 'MND': 2, 'sird': 1, 'conserve': 0.5},
    'aquaveil': {'sird': 5, 'enh_skill': 0.5},
    'dark': {'drain': 6, 'dark_skill': 2, 'macc': 1, 'INT': 0.8},
    'divine': {'div_skill': 2, 'MND': 1.5, 'macc': 1, 'matk': 2, 'mdmg': 1},
    'ninjutsu': {'nin_dmg': 1, 'nin_skill': 2, 'matk': 3, 'mdmg': 1.5, 'INT': 1, 'macc': 1},
    'bluemagic': {'matk': 3, 'mdmg': 1.5, 'INT': 1, 'MND': 0.3, 'macc': 0.8, 'blue_skill': 1},
    'helix': {'matk': 3, 'mdmg': 1.5, 'INT': 1.5, 'macc': 0.8},
    # physical / breath blue magic: wsdist has neither (BG Wiki: STR is safe for every physical spell, DEX second, they need
    # accuracy; breath damage is a share of your HP)
    'bluephys': {'STR': 1, 'DEX': 0.7, 'acc': 0.6, 'att': 0.4, 'blue_skill': 0.3},
    'bluebreath': {'HP': 1, 'macc': 0.1},
    'songs': {'songs': 40, 'song_dur': 10, 'CHR': 0.5, 'sing': 0.5, 'instr': 0.5, 'macc': 0.5},
    'songcast': {'song_fast': 6, 'fast': 5},
    'geomancy': {'geomancy': 30, 'geo_skill': 2, 'bell': 2, 'indi_dur': 2, 'conserve': 1},
    'summon': {'smn_skill': 2, 'perp': 10, 'bp1': 5, 'bp2': 5, 'MP': 0.02},
    'bpcast': {'bp1': 20, 'bp2': 20, 'smn_skill': 0.2},
    'bpphys': {'ava_att': 2, 'ava_acc': 1.5, 'ava_lvl': 40, 'ava_da': 6, 'ava_crit': 4, 'smn_skill': 0.5},
    'bpmagic': {'ava_matk': 3, 'ava_macc': 1.5, 'ava_lvl': 40, 'smn_skill': 0.5},
    'ready': {'pet_att': 2, 'pet_acc': 1.5, 'pet_lvl': 40, 'pet_da': 5, 'pet_haste': 3, 'pet_matk': 1},
    'waltz': {},
    'roll': {'roll': 30, 'fast': 0.1},
    'quickdraw': {'qd': 2, 'matk': 3, 'mdmg': 1.5, 'macc': 1, 'AGI': 0.5},
    'rapreshot': {'snap': 6, 'rapid': 4},
    'rangedtp': {'ratt': 1, 'racc': 1.2, 'AGI': 0.8, 'stp': 2, 'recycle': 1, 'trueshot': 3},
    'rangedws': {'ratt': 1.2, 'racc': 0.8, 'AGI': 1, 'STR': 0.5},
    'magicws': {'matk': 3, 'mdmg': 1.5, 'AGI': 0.8, 'INT': 0.8, 'macc': 0.5},
    'enmity': {'enmity': 5, 'dt': 2, 'pdt': 1, 'HP': 0.02, 'sird': 0.5},
    'th': {'th': 40, 'dt': 0.5},
    'accuracy': {'acc': 1, 'DEX': 0.75},
}


def value(gear, kind):
    t = healing.totals(gear)
    v = 0
    for k, pts in POINTS.get(kind, {}).items():
        n = t.get(k, 0)
        if k in CAPS:
            n = min(n, CAPS[k])
        v += pts * n
    return round(v, 3)


def plan_magic(job, sub):
    """(path, what, kind, how). how: 'points' or healing's kinds."""
    out = []
    def add(path, what, kind, how='points'):
        out.append({'path': path, 'title': what, 'kind': kind, 'how': how, 'group': 'Magic'})
    healer = job in ('WHM', 'RDM', 'SCH', 'GEO', 'PLD', 'RUN', 'BLU', 'BRD', 'DRK', 'NIN') or sub in ('WHM', 'RDM', 'SCH')
    if job in ('WHM', 'RDM', 'SCH', 'PLD', 'RUN', 'BLU', 'GEO', 'BRD') or sub in ('WHM', 'RDM', 'SCH'):
        add('sets.midcast.Cure', 'Cure', 'cure', 'healing')
    if job in ('WHM', 'SCH', 'RDM'):
        add('sets.midcast.Curaga', 'Curaga', 'curaga', 'healing')
    if job in ('WHM', 'SCH') or sub == 'WHM':
        add('sets.midcast.Cursna', 'Cursna', 'cursna', 'healing')
    if job in ('WHM', 'SCH'):
        add('sets.midcast.Regen', 'Regen', 'regen', 'healing')
    if job in ('WHM', 'RDM', 'SCH', 'RUN', 'PLD') or sub in ('WHM', 'RDM', 'SCH'):
        add('sets.midcast["Enhancing Magic"]', 'Enhancing magic: duration and skill', 'enhancing')
        add('sets.midcast.Stoneskin', 'Stoneskin', 'stoneskin')
    if job in ('WHM', 'RDM', 'SCH', 'NIN', 'RUN', 'PLD', 'BLU'):
        add('sets.midcast.Aquaveil', 'Aquaveil: spells not interrupted', 'aquaveil') if job in ('WHM', 'RDM', 'SCH', 'RUN') else None
    if job in ('WHM', 'RDM', 'SCH', 'BLM', 'GEO', 'DRK', 'BRD'):
        add('sets.midcast["Enfeebling Magic"]', 'Enfeebling magic', 'enfeeble')
    if job in ('BLM', 'RDM', 'SCH', 'GEO', 'DRK', 'WHM'):
        add('sets.midcast["Elemental Magic"]', 'Nukes', 'nuke', 'magic')
    if job in ('BLM', 'RDM', 'SCH', 'GEO'):
        add('sets.magic_burst', 'Magic burst: //gs c burst', 'burst', 'magic')
    if job == 'SCH':
        add('sets.midcast.Helix', 'Helix', 'helix', 'magic')
    if job in ('BLM', 'SCH', 'DRK', 'GEO', 'RDM'):
        add('sets.midcast["Dark Magic"]', 'Dark magic: Drain, Aspir', 'dark')
    if job == 'WHM':
        add('sets.midcast["Divine Magic"]', 'Divine magic: Banish, Holy', 'divine')
    if job == 'NIN':
        add('sets.midcast.Ninjutsu', 'Ninjutsu', 'ninjutsu')
    if job == 'BLU':
        add('sets.midcast["Blue Magic"]', 'Blue magic: magical spells', 'bluemagic', 'magic')
    if job == 'BRD':
        add('sets.precast.BardSong', 'Starting a song', 'songcast')
        add('sets.midcast.BardSong', 'Songs', 'songs')
    if job == 'GEO':
        add('sets.midcast.Geomancy', 'Geomancy', 'geomancy')
    if job == 'SMN':
        add('sets.midcast["Summoning Magic"]', 'Summoning, and with an avatar out', 'summon')
        add('sets.precast.BloodPactRage', 'Starting a Blood Pact', 'bpcast')
        add('sets.midcast.Pet.BloodPactRage', 'Physical Blood Pacts', 'bpphys')
        add('sets.midcast.Pet.BloodPactWard', 'Magic Blood Pacts', 'bpmagic')
    return out


def _item_bits(c, slot):
    return healing.fits(c, slot)


def owned_weapons(job, entries, index_entry):
    """[wsdist entry] of owned weapons this job can use, Ultimate Weapons first, then the strongest. entries: the owned item ids' wsdist entries."""
    found = {}
    for e in entries:
        if e.get('Type') == 'Weapon' and e.get('Skill Type') and job.lower() in e['Jobs'] and e['Skill Type'] not in RANGED_WS:
            found.setdefault(e['Name'], e)
    return sorted(found.values(), key=lambda e: (rema.family(e['Name']) is None, -e.get('DMG', 0), e['Name']))


def weapon_entries(owned_ids, items, index, W):
    out = []
    for iid in owned_ids:
        it = items.by_id.get(iid)
        ents = it and W.entries_for(it['en'], items, index)
        if ents:
            out.append(W.pick_variant(ents))
    return out


def sub_for(main, weapons, job, sub, grips):
    """What goes with a weapon: a second one if the job can dual wield, a shield when it's a tank, a grip for a two-handed one."""
    if main.get('Skill Type') in ONE_HANDED:
        if job in DW_MAIN or sub in DW_SUB:
            others = [e for e in weapons if e['Name'] != main['Name'] and e.get('Skill Type') in ONE_HANDED]
            return others[0]['Name'] if others else None
        return None
    if main.get('Skill Type') == 'Hand-to-Hand':
        return None
    return grips[0] if grips else None


def recommended_ws(job, weapons, W):
    """The job's weapon skills from BG Wiki that the weapons in his bags can do: (name, why). One that needs its weapon only with that weapon."""
    known = W.ws_list()
    kinds = {e['Skill Type'] for e in weapons}
    names = {e['Name'].lower() for e in weapons}
    out = []
    for ws in WS.get(job, []):
        skill = W.ws_skill(ws)
        if ws not in known or skill not in kinds and skill not in RANGED_WS:
            continue
        linked = rema.ws_weapon(ws)
        if linked and rema.needs_weapon(ws) and linked.lower() not in names:
            continue
        out.append((ws, f'its own weapon: {linked}' if linked else f'your {skill}'))
    return out


def ability_names(res_folder):
    """Job abilities by name, from Windower's res folder."""
    try:
        text = open(os.path.join(res_folder, 'job_abilities.lua'), encoding='utf-8', errors='replace').read()
    except OSError:
        return set()
    return set(re.findall(r'\ben="([^"]+)"', text))


_ABIL_RX = re.compile(r'(?:Enhances|Increases|Augments) "([^"]+)"|"([^"]+)"(?: ability)?(?: effect| duration| delay)? ?[+\-]\d')


def ability_sets(cands, data, names, items=None, job=None):
    """{ability: {slot: candidate}} for gear whose text names one of the job's abilities (Souleater, Blood Weapon...). Only gear made for this job, at most two jobs: a ring many jobs
    can wear may name another job's ability (WAR: Phantom Roll)."""
    out = {}
    skip = {'Fast Cast', 'Regen', 'Refresh', 'Store TP', 'Double Attack', 'Triple Attack', 'Quick Draw', 'Treasure Hunter', 'Snapshot', 'Rapid Shot'}
    for c in cands:
        if items is not None and bin((items.by_id.get(c['id']) or {}).get('jobs') or 0).count('1') > 2:
            continue
        text = data.text.get(c['id'], '')
        m = healing.CUT_RX.search(text)
        text = text[:m.start()] if m else text
        for a, b in _ABIL_RX.findall(text):
            ab = a or b
            if ab in names and ab not in skip:
                for slot in healing.SLOTS:
                    if slot not in ('main', 'sub') and healing.fits(c, slot):
                        out.setdefault(ab, {}).setdefault(slot, c)
                        break
    return out


def plan(job, sub, weapons, W, ws_list=None):
    """The sets to make: [{'path', 'title', 'how', 'group', ...}], in the order they're built."""
    sub = sub or ''
    recs = []
    melee = job not in MAGES
    add = lambda **k: recs.append(k)  # noqa: E731
    add(path='sets.idle', title='Standing around: damage taken first', how='idle', group='Idle and safety', on=True)
    add(path='sets.idle.Town', title='In town: fast', how='idle', group='Idle and safety', on=True)
    add(path='sets.defense.PDT', title='Physical damage key', how='idle', group='Idle and safety', on=True)
    add(path='sets.defense.MDT', title='Magic damage key', how='idle', group='Idle and safety', on=True)
    add(path='sets.resting', title='/heal: Refresh and Regen', how='idle', group='Idle and safety', on=job in MAGES)
    add(path='sets.Kiting', title='Your fastest item, for running', how='kiting', group='Idle and safety', on=True)
    add(path='sets.precast.FC', title='Fast cast', how='healing', kind='precast', group='Magic', on=True)
    for r in plan_magic(job, sub):
        recs.append(dict(r, on=True))
    if weapons:
        add(path='sets.engaged', title='Fighting', how='tp', group='Fighting', on=melee)
        add(path='sets.engaged.Acc', title='Fighting: more accuracy', how='tp_acc', group='Fighting', on=melee)
        add(path='sets.engaged.PDT', title='Fighting: damage taken', how='tp_dt', group='Fighting', on=melee)
        add(path='sets.precast.WS', title='Any other weapon skill', how='ws', ws=None, group='Weapon skills', on=True)
        for ws, why in (ws_list if ws_list is not None else recommended_ws(job, weapons, W)):
            add(path=f'sets.precast.WS["{ws}"]', title=f'{ws}: {why}', how='ws', ws=ws, group='Weapon skills', on=True)
    if job == 'THF':
        add(path='sets.TreasureHunter', title='Treasure Hunter', how='points', kind='th', group='Fighting', on=True)
    if job in ('DNC',) or sub == 'DNC':
        add(path='sets.precast.Waltz', title='Curing Waltz', how='healing', kind='waltz', group='Abilities', on=True)
    if job == 'RUN':
        add(path='sets.precast.JA.Enmity', title='Enmity: Provoke, Flash, Sentinel...', how='points', kind='enmity', group='Abilities', on=True)
    if job == 'PLD':
        recs = pld_plan(recs, sub, weapons)
    if job == 'COR':
        add(path='sets.precast.CorsairRoll', title='Phantom Roll', how='points', kind='roll', group='Abilities', on=True)
        add(path='sets.precast.CorsairShot', title='Quick Draw', how='points', kind='quickdraw', group='Abilities', on=True)
    if job in ('COR', 'RNG'):
        add(path='sets.precast.RA', title='Starting a shot: Snapshot, Rapid Shot', how='points', kind='rapreshot', group='Abilities', on=True)
        add(path='sets.midcast.RA', title='Shooting', how='points', kind='rangedtp', group='Abilities', on=True)
    if job == 'BST':
        add(path='sets.midcast.Pet.Ready', title='Ready moves', how='points', kind='ready', group='Pet', on=True)
    if job == 'PUP':
        for p, t in (('sets.engaged.Pet', 'You and the automaton'), ('sets.idle.Pet', 'Automaton waiting'), ('sets.idle.Pet.Engaged', 'Automaton fighting'), ('sets.idle.Pet.Engaged.Tank', 'Automaton tanking'),
                     ('sets.idle.Pet.Engaged.Nuke', 'Automaton casting'), ('sets.midcast.Pet.PetWSGear', 'Automaton weapon skills')):
            add(path=p, title=t, how='pup', group='Pet', on=True)
    return recs


# a Paladin's sets: the FFXIAH PLD guide's list (pld.py judges them). Flash, Palisade, Provoke and Atonement get the enmity set (render: pld_copies).
PLD_SETS = [
    ('sets.idle', 'Standing around: damage taken, enmity kept when hit, HP', 'Tank, standing', 'Idle and safety'),
    ('sets.defense.PDT', 'Physical damage key', 'Tank, standing', 'Idle and safety'),
    ('sets.defense.MDT', 'Magic damage key: Magic Evasion, Magic Def. Bonus', 'Tank, magic', 'Idle and safety'),
    ('sets.precast.FC', 'Fast cast, keeping your HP', 'Fast cast', 'Magic'),
    ('sets.midcast.Cure', 'Cure: not interrupted, potency', 'Cure others', 'Magic'),
    ('sets.midcast.Phalanx', 'Phalanx: Phalanx gear and Enhancing skill', 'Phalanx', 'Magic'),
    ('sets.midcast["Enhancing Magic"]', 'Reprisal, Crusade, Protect...: not interrupted', 'Spell, not interrupted', 'Magic'),
    ('sets.midcast["Enlight II"]', 'Enlight II: Divine skill, not interrupted', 'Enlight', 'Magic'),
    ('sets.precast.JA.Enmity', 'Full enmity: Flash, Provoke, Palisade, Atonement...', 'Enmity', 'Abilities'),
]


def pld_plan(recs, sub, weapons):
    """The plan of a PLD file: the guide's sets in place of the plain idle / fast cast / cure ones, an ability set for each PLD ability, and the
    damage-taken fighting set as a tank set."""
    mine = {p for p, _t, _f, _g in PLD_SETS}
    out = [r for r in recs if r['path'] not in mine and r['path'] != 'sets.midcast.Stoneskin']
    for r in out:
        if r['path'] == 'sets.engaged.PDT':
            r.update(how='pld', focus='Tank, fighting', title='Fighting as the tank: damage taken, enmity, HP')
    for p, t, f, g in PLD_SETS:
        out.append({'path': p, 'title': t, 'how': 'pld', 'focus': f, 'group': g, 'on': True})
    if sub == 'BLU':
        out.append({'path': 'sets.midcast["Blue Magic"]', 'title': 'Blue magic (Geist Wall, Sheep Song...): enmity, not interrupted', 'how': 'pld',
                    'focus': 'Enmity, not interrupted', 'group': 'Magic', 'on': True})
    for a in pld.JA_GEAR:
        out.append({'path': f'sets.precast.JA["{a}"]', 'title': f'{a}: the enmity set with what boosts it', 'how': 'pld',
                    'focus': 'Chivalry' if a == 'Chivalry' else 'Ability: ' + a, 'group': 'Abilities', 'on': True})
    out.append({'path': 'sets.buff.Doom', 'title': 'Doomed: Cursna received, Holy Water', 'how': 'pld', 'focus': 'Doom', 'group': 'Idle and safety', 'on': True})
    return out


def pld_copies(built, sub, weapons):
    """The guide's sets that are the enmity set as it is: Flash, Palisade, Majesty, Provoke (/WAR), Atonement (with Burtgang)."""
    base = built.get('sets.precast.JA.Enmity')
    if not base:
        return built
    out = dict(built)
    copies = ['sets.midcast.Flash', 'sets.precast.JA.Palisade', 'sets.precast.JA.Majesty']
    if sub == 'WAR':
        copies.append('sets.precast.JA.Provoke')
    if any((w.get('main') or '').lower() == 'burtgang' for w in weapons):
        copies.append('sets.precast.WS["Atonement"]')
    for p in copies:
        out.setdefault(p, dict(base))
    return out


def _names(gear):
    return {s: healing.gs_name(c) for s, c in gear.items() if c}


def gs_slots(best, W, items):
    """wsdist's set as {gs slot: name}, without weapons."""
    import doctor
    out = {}
    for slot, e in best.items():
        gs = W.GS_SLOT.get(slot)
        if gs and gs not in ('main', 'sub', 'range') and e and e.get('Name') != 'Empty':
            out[gs] = doctor._gs_name(e, items)
    return out


def build_one(rec, ctx):
    """One set's gear ({slot: name or {name, augments}}) and a line about it. ctx: job, sub, main (name), off, cands, counts, items, data, owned_ids, index, buffs, enemy, W."""
    how = rec['how']
    job, sub = ctx['job'], ctx['sub']
    items, data, cands, counts = ctx['items'], ctx['data'], ctx['cands'], ctx['counts']
    keep_weapons = job not in MAGES
    wield = {}
    if ctx.get('main') and keep_weapons:
        found = items.find(ctx['main'])
        if found:
            wield['main'] = healing.candidate(found[0], data)
    if how == 'idle':
        r = idle.judge(rec['path'], {}, job, sub, cands, counts, items, data, keep_weapons=keep_weapons)
        return _names({s: c for s, c in r['best'].items()}), idle.words(r['n_best'], r['base'])
    if how == 'kiting':
        best = None
        for c in cands:
            mv = c['stats'].get('move', 0)
            if mv and (best is None or mv > best['stats']['move']) and any(healing.fits(c, s) for s in ('legs', 'feet', 'ring1')):
                best = c
        if not best:
            return {}, 'no movement speed gear in your bags'
        slot = next(s for s in ('legs', 'feet', 'ring1') if healing.fits(best, s))
        return {slot: healing.gs_name(best)}, f"Movement {best['stats']['move']} %"
    if how == 'healing':
        kind = rec['kind']
        base = healing.defaults(job, sub)
        spell = healing.spell_for_set(kind, rec['path'], job, sub)
        best, val, _ = healing.build(kind, cands, wield, base, job, sub, spell=spell, keep_weapons=bool(wield), counts=counts)
        return _names({s: c for s, c in best.items() if s not in ('main', 'sub') or not wield}), f"{healing.KINDS[kind]['title']}: {healing.fmt_value(kind, val)}"
    if how == 'pup':
        r = pup.judge(rec['path'], {}, job, sub, cands, counts, items, data)
        return _names(r['best']), pup.words(r['n_best'], r['focus'])
    if how == 'pld':
        r = pld.judge(rec['path'], {}, job, sub, cands, counts, items, data, focus=rec.get('focus'))
        if rec.get('focus', '').startswith('Ability') and not r['n_best']['ja']:
            return {}, f"none of your gear boosts {r['n_best']['ability']}: the enmity set is used"
        return _names(r['best']), pld.words(r['n_best'], r['focus'])
    if how == 'magic' and ctx.get('W') is not None:
        # a nuke set: wsdist's spell maths (magic.py) - the job's strongest spell, a burst for the burst set, a SCH's storm / Klimaform
        import magic
        W = ctx['W']
        spell = {'nuke': magic.DEFAULT_SPELL.get(job, 'Thunder V'), 'burst': magic.DEFAULT_SPELL.get(job, 'Thunder V'),
                 'helix': 'Noctohelix II', 'bluemagic': magic.BLUE_DEFAULT}[rec['kind']]
        opts = magic.default_options(job, spell, rec['kind'] == 'burst')
        gear = {}
        if ctx.get('main') and job not in MAGES:
            gear['main'] = {'name': ctx['main'], 'augments': [], 'bag': None}
            if ctx.get('off'):
                gear['sub'] = {'name': ctx['off'], 'augments': [], 'bag': None}
        owned, cur, _n = magic.plan(job, sub, gear, [], ctx['owned_ids'], items, ctx['index'], free=job in MAGES)
        best, dmg, _ = magic.best_set(job, sub, spell, owned, cur, enemy_name=ctx['enemy'], buffs=ctx['buffs'], opts=opts)
        out = {}
        for slot, e in best.items():
            gs = W.GS_SLOT.get(slot)
            if gs and gs != 'range' and e and e.get('Name') != 'Empty' and (gs not in ('main', 'sub') or job in MAGES):
                import doctor
                out[gs] = doctor._gs_name(e, items)
        if out.get('body') in magic.HOODED:
            out.pop('head', None)
        return out, f"{magic.words(spell, opts)}: {dmg:,.0f} a cast"
    if how in ('points', 'magic'):
        pool = [c for c in cands if any(c['stats'].get(k) for k in POINTS.get(rec['kind'], {}))]
        best, val, _ = healing.build('points', pool, wield, {}, job, sub, spell=rec['kind'], keep_weapons=bool(wield), counts=counts)
        return _names({s: c for s, c in best.items() if s not in ('main', 'sub') or not wield}), f'{val:.0f} points'
    W = ctx['W']
    index, own, buffs, enemy = ctx['index'], ctx['owned_ids'], ctx['buffs'], ctx['enemy']
    gear = {}
    if ctx.get('main'):
        gear['main'] = {'name': ctx['main'], 'augments': [], 'bag': None}
    if ctx.get('off'):
        gear['sub'] = {'name': ctx['off'], 'augments': [], 'bag': None}
    if how == 'ws':
        ws = rec.get('ws')
        skill = W.ws_skill(ws) if ws else None
        if skill in RANGED_WS:
            kind = 'magicws' if ws in ('Leaden Salute', 'Wildfire', 'Trueflight', 'Hot Shot') else 'rangedws'
            pool = [c for c in cands if any(c['stats'].get(k) for k in POINTS[kind])]
            best, val, _ = healing.build('points', pool, wield, {}, job, sub, spell=kind, keep_weapons=bool(wield), counts=counts)
            return _names({s: c for s, c in best.items() if s not in ('main', 'sub') or not wield}), f'{val:.0f} points: wsdist does not check ranged yet'
        use = ws or next((w for w in WS.get(job, []) if W.ws_skill(w) == (ctx.get('main_skill') or skill)), None) or 'Savage Blade'
        linked = rema.ws_weapon(use)
        g = dict(gear)
        if linked and items.find(linked) and any(i['id'] in own for i in items.find(linked)):
            g = {'main': {'name': linked, 'augments': [], 'bag': None}}
        owned, cur, _n, _s = W.plan_ws(job, sub, use, g, [], own, items, index)
        if 'main' not in cur:
            return {}, f'no weapon for {use} in your bags'
        best, dmg, _ = W.best_ws_set(job, sub, use, owned, cur, tp=ctx.get('tp', 1500), enemy_name=enemy, buffs=buffs)
        return gs_slots(best, W, items), f"{use}: {dmg:,.0f} with {cur['main']['Name2']}"
    owned, cur, _n, _s = W.plan_ws(job, sub, None, gear, [], own, items, index)
    if 'main' not in cur:
        return {}, 'no weapon picked'
    spec = dict(buffs or {})
    req = None
    if how == 'tp_dt':
        req = W.dt_requirement({'dt': 40})
    if how == 'tp_acc':
        spec['keep_accuracy'] = True
        accgear = healing.build('points', [c for c in cands if c['stats'].get('acc')], wield, {}, job, sub, spell='accuracy', keep_weapons=bool(wield), counts=counts)[0]
        for s, c in accgear.items():
            ents = W.entries_for(c['name'], items, index)
            wslot = W.SLOT_MAP.get(s)
            if ents and wslot and s not in ('main', 'sub'):
                cur = dict(cur, **{wslot: W.pick_variant(ents, c.get('augments'))})
    info = {}
    best, val, _ = W.best_tp_set(job, sub, owned, cur, enemy_name=enemy, req=req, info=info, buffs=spec)
    word = {'time': f'{val:.1f} s to a weapon skill', 'dps': f'{val:,.0f} damage a second', 'damage': f'{val:,.0f} a round'}.get(info.get('metric', 'time'))
    return gs_slots(best, W, items), f"{word} with {cur['main']['Name2']}"


def existing(character, job, folder=None):
    """His files for this job: the Doctor doesn't make one if he has one."""
    import doctor
    return [p for p in doctor.files_for(character, folder) if checks.job_of(p) == job]


def _lua_item(v, priority=None):
    if priority is not None:                       # (a PLD's HP order: GearSwap puts the highest on first)
        name = v['name'] if isinstance(v, dict) else v
        augs = ', '.join('"' + a.replace('"', '\\"') + '"' for a in (v.get('augments') or [] if isinstance(v, dict) else []))
        return '{name="' + name.replace('"', '\\"') + '"' + (', augments={' + augs + '}' if augs else '') + f', priority={int(priority)}' + '}'
    if isinstance(v, dict):
        augs = ', '.join('"' + a.replace('"', '\\"') + '"' for a in v.get('augments') or [])
        return '{name="' + v['name'].replace('"', '\\"') + '", augments={' + augs + '}}'
    return '"' + v.replace('"', '\\"') + '"'


ORDER = ['main', 'sub', 'range', 'ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']


def set_lines(built, indent='    ', prios=None):
    """The sets as Lua, parents first; a table a set goes under is made only if nothing has."""
    lines, made = [], set()
    for path in sorted(built, key=lambda p: (len(fixer._path_parts(p)), p)):
        parts = fixer._path_parts(path)
        for i in range(2, len(parts)):
            parent = _path(parts[:i])
            if parent not in built and parent not in made:
                made.add(parent)
                lines.append(f'{indent}{parent} = {parent} or {{}}')
        gear = built[path]
        pr = (prios or {}).get(path) or {}
        items_ = ', '.join(f'{s}={_lua_item(gear[s], pr.get(s))}' for s in ORDER if s in gear)
        lines.append(f'{indent}{path} = {{{items_}}}')
    return lines


def _path(parts):
    out = parts[0]
    for p in parts[1:]:
        out += '.' + p if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', p) else '["' + p + '"]'
    return out


HEAD = '''-- {name}'s {job} GearSwap: made by GearSwap Doctor {version} on {date} from the gear in {name}'s bags ({style}).
-- Everything here is yours to change. The Doctor's other tabs work on it too. In game: //gs c help
'''

MOTE = '''{head}
function get_sets()
    mote_include_version = 2
    include('Mote-Include.lua')
end

function user_setup()
    state.OffenseMode:options('Normal', 'Acc')
    state.HybridMode:options('Normal', 'PDT')
    state.IdleMode:options('Normal', 'PDT')
    state.PhysicalDefenseMode:options('PDT')
    state.MagicalDefenseMode:options('MDT')
    gsd_weapon = 1
    gsd_burst = false
    send_command('bind ^f8 gs c weapon')
end

function file_unload()
    send_command('unbind ^f8')
end

function init_gear_sets()
{sets}
end

-- Keys from Mote: F9 fight mode, Ctrl+F9 damage taken mode, F10 / F11 physical / magic damage set, F12 what's on. Ctrl+F8 next weapon. //gs c burst magic burst on / off.
function job_self_command(cmd, eventArgs)
    if cmd[1] == 'weapon' then
        gsd_weapon = gsd_weapon % #GSD_WEAPONS + 1
        equip(sets.weapons[GSD_WEAPONS[gsd_weapon]])
        add_to_chat(207, 'Weapon: ' .. GSD_WEAPONS[gsd_weapon])
        eventArgs.handled = true
    elseif cmd[1] == 'burst' then
        gsd_burst = not gsd_burst
        add_to_chat(207, 'Magic burst ' .. (gsd_burst and 'ON' or 'off'))
        eventArgs.handled = true
    end
end

function job_post_midcast(spell, action, spellMap, eventArgs)
    if gsd_burst and spell.skill == 'Elemental Magic' and sets.magic_burst then
        equip(sets.magic_burst)
    end
end
'''

STANDALONE = r'''{head}
-- All the rules are below your sets; nothing else is needed. Same set names as most shared files.
local modes = {{ fight = {{ 'Normal', 'Acc', 'PDT' }}, idle = {{ 'Normal', 'PDT', 'MDT' }} }}
local at = {{ fight = 1, idle = 1, weapon = 1 }}
local burst = false

function get_sets()
{sets}
    send_command('bind f9 gs c fight')
    send_command('bind f10 gs c idle')
    send_command('bind f12 gs c show')
    send_command('bind ^f8 gs c weapon')
end

function file_unload()
    for _, k in ipairs({{ 'f9', 'f10', 'f12', '^f8' }}) do send_command('unbind ' .. k) end
end

local function pick(t, ...)
    for _, k in ipairs({{ ... }}) do
        local s = type(t) == 'table' and k and t[k]
        if type(s) == 'table' then return s end
    end
    return nil
end

-- a tank's abilities that are about hate: the enmity set when they have no set of their own
local enmity_ja = {{}}
for _, n in ipairs({{ 'Provoke', 'Sentinel', 'Palisade', 'Majesty', 'Rampart', 'Shield Bash', 'Invincible', 'Cover', 'Holy Circle', 'Fealty', 'Divine Emblem', 'Intervene',
                     'Sepulcher', 'Warcry', 'Vallation', 'Valiance', 'Pflug', 'Swordplay', 'Liement', 'Battuta', 'Animated Flourish' }}) do enmity_ja[n] = true end

local function has_gear(t)
    return type(t) == 'table' and (rawget(t, 'head') or rawget(t, 'body') or rawget(t, 'legs') or rawget(t, 'feet') or rawget(t, 'hands') or rawget(t, 'neck') or rawget(t, 'waist') or rawget(t, 'back'))
end

-- what you wear between actions
local function rest_set()
    local status = player.status
    local pet_on = type(pet) == 'table' and pet.isvalid == true
    if pet_on and pet.status == 'Engaged' then
        if status == 'Engaged' and sets.engaged and sets.engaged.Pet then return sets.engaged.Pet end
        if sets.idle and sets.idle.Pet and sets.idle.Pet.Engaged then return sets.idle.Pet.Engaged end
    end
    if status == 'Engaged' and has_gear(sets.engaged) then
        local mode = modes.fight[at.fight]
        return (mode ~= 'Normal' and has_gear(sets.engaged[mode])) and sets.engaged[mode] or sets.engaged
    end
    if status == 'Resting' and has_gear(sets.resting) then return sets.resting end
    local mode = modes.idle[at.idle]
    if mode ~= 'Normal' and sets.defense and has_gear(sets.defense[mode]) then return sets.defense[mode] end
    if pet_on and sets.idle and has_gear(sets.idle.Pet) then return sets.idle.Pet end
    if areas_cities and world and areas_cities[world.area] and sets.idle and has_gear(sets.idle.Town) then return sets.idle.Town end
    return sets.idle or {{}}
end

local function spell_map(spell)
    local n = spell.english or ''
    if n:find('^Curaga') then return 'Curaga' end
    if n:find('^Cure') then return 'Cure' end
    return n
end

function precast(spell)
    local t = spell.type
    if spell.action_type == 'Magic' then
        if t == 'BardSong' and sets.precast.BardSong then equip(sets.precast.BardSong)
        elseif sets.precast.FC then equip(sets.precast.FC) end
    elseif t == 'WeaponSkill' then
        equip(pick(sets.precast.WS, spell.english) or sets.precast.WS or {{}})
    elseif spell.action_type == 'Ranged Attack' then
        if sets.precast.RA then equip(sets.precast.RA) end
    elseif t == 'Waltz' then
        if sets.precast.Waltz then equip(sets.precast.Waltz) end
    elseif t == 'CorsairRoll' or t == 'CorsairShot' then
        if sets.precast[t] then equip(sets.precast[t]) end
    elseif t == 'BloodPactRage' or t == 'BloodPactWard' then
        if sets.precast.BloodPactRage then equip(sets.precast.BloodPactRage) end
    elseif sets.precast.JA then
        local s = pick(sets.precast.JA, spell.english)
        if s then equip(s) elseif sets.precast.JA.Enmity and enmity_ja[spell.english] then equip(sets.precast.JA.Enmity) end
    end
end

function midcast(spell)
    if spell.action_type == 'Ranged Attack' then
        if sets.midcast.RA then equip(sets.midcast.RA) end
        return
    end
    if spell.action_type ~= 'Magic' then return end
    local s = pick(sets.midcast, spell.english, spell_map(spell), spell.skill, spell.type)
    if s then equip(s) end
    if burst and spell.skill == 'Elemental Magic' and sets.magic_burst then equip(sets.magic_burst) end
end

function aftercast(spell)
    equip(rest_set())
end

function status_change(new, old)
    equip(rest_set())
end

function pet_change(p, gain)
    equip(rest_set())
end

function pet_status_change(new, old)
    equip(rest_set())
end

function pet_midcast(spell)
    local s = sets.midcast.Pet
    if type(s) ~= 'table' then return end
    local g = pick(s, spell.type, 'PetWSGear', 'Ready')
    if g then equip(g) end
end

function pet_aftercast(spell)
    equip(rest_set())
end

function self_command(cmd)
    local w = {{}}
    for x in tostring(cmd):gmatch('%S+') do w[#w + 1] = x end
    local c = w[1]
    if c == 'fight' or c == 'idle' then
        at[c] = at[c] % #modes[c] + 1
        add_to_chat(207, c .. ': ' .. modes[c][at[c]])
        equip(rest_set())
    elseif c == 'weapon' and GSD_WEAPONS and #GSD_WEAPONS > 0 then
        at.weapon = at.weapon % #GSD_WEAPONS + 1
        equip(sets.weapons[GSD_WEAPONS[at.weapon]])
        add_to_chat(207, 'Weapon: ' .. GSD_WEAPONS[at.weapon])
    elseif c == 'burst' then
        burst = not burst
        add_to_chat(207, 'Magic burst ' .. (burst and 'ON' or 'off'))
    elseif c == 'show' then
        add_to_chat(207, 'Fight: ' .. modes.fight[at.fight] .. '  Idle: ' .. modes.idle[at.idle] .. '  Burst: ' .. (burst and 'ON' or 'off'))
    else
        add_to_chat(207, 'F9 fight mode, F10 idle mode, F12 what is on, Ctrl+F8 next weapon, //gs c burst magic burst on / off')
    end
end
'''


def weapon_lines(weapons, indent='    '):
    """[{'name', 'main', 'sub'}] as sets.weapons and the list the commands go through."""
    lines = [f'{indent}sets.weapons = {{}}']
    names = []
    for w in weapons:
        key = re.sub(r'[^A-Za-z0-9_]', '', w['main']) or 'Weapon'
        parts = f'main="{w["main"]}"' + (f', sub="{w["sub"]}"' if w.get('sub') else '')
        if w.get('range'):                                       # (a COR's gun and its bullet stay together)
            parts += f', range="{w["range"]}"' + (f', ammo="{w["ammo"]}"' if w.get('ammo') else '')
        lines.append(f'{indent}sets.weapons.{key} = {{{parts}}}')
        names.append(key)
    lines.append(f'{indent}GSD_WEAPONS = {{' + ', '.join(f'"{n}"' for n in names) + '}')
    return lines


def render(name, job, style, built, weapons, version, date, sub=None):
    """The whole file. A PLD's sets get the guide's HP order (pld.priority_for): HP pieces go on first."""
    head = HEAD.format(name=name, job=job, version=version, date=date, style='Mote-Include' if style == 'Mote' else 'no other files needed')
    # a gun's ammo for what shoots (nothing else in a COR's or RNG's ammo slot: job_rules)
    keep = next((w for w in weapons if w.get('range') and w.get('ammo')), None)
    if keep:
        for p in ('sets.precast.RA', 'sets.midcast.RA', 'sets.precast.CorsairShot'):
            if p in built:
                built = dict(built, **{p: dict(built[p], ammo=keep['ammo'])})
    # (these tables exist in Mote; a standalone file needs them too, whatever was ticked)
    must = ['    sets.precast = sets.precast or {}', '    sets.midcast = sets.midcast or {}']
    prios = None
    if job == 'PLD':
        built = pld_copies(built, sub, weapons)
        prios = {}
        for p, g in built.items():
            pr = pld.priority_for({s: (v if isinstance(v, dict) else {'name': v}) for s, v in g.items()})
            if pr:
                prios[p] = pr
    body = '\n'.join(must + weapon_lines(weapons) + set_lines(built, prios=prios))
    if style == 'Mote':
        return MOTE.format(head=head, sets=body).replace('\r\n', '\n')
    return STANDALONE.format(head=head, sets=body).replace('\r\n', '\n')


def path_for(character, job, folder):
    return os.path.join(folder, f'{character}_{job}.lua')


def write(path, text):
    """Never over a file that's there. The new file must load, or nothing is written."""
    import gs_loader
    if os.path.exists(path):
        raise FileExistsError(path)
    tmp = path + '.doctor-check.lua'
    open(tmp, 'w', encoding='utf-8', newline='\n').write(text)
    try:
        loaded = gs_loader.load(tmp)
    finally:
        os.remove(tmp)
    if loaded.error:
        raise ValueError('the new file would not load: ' + str(loaded.error))
    open(path, 'w', encoding='utf-8', newline='\r\n').write(text)
    return loaded
