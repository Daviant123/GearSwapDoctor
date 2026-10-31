"""
GearSwap Doctor: Ultimate Weapons (Relic, Mythic, Empyrean, Aeonic, Ergon and Prime) and their Aftermath.
His request 2026-10-30: "takes into consideration the different types of rema weapons and their different aftermath effects,
as that can affect the gear that is being equiped and the overall dps".

Each family's Aftermath works differently (bg-wiki.com/ffxi/Category:Ultimate_Weapons, and each item's own text):
  Relic     one effect of its own (Ragnarok: critical hit rate, Apocalypse: haste, Bravura: damage taken...); the TP only sets
            how long it lasts. Also "occasionally deals double / triple damage", always on, in wsdist already.
  Mythic    Lv.1 / Lv.2: its own two stats. Lv.3: occasionally attacks twice or thrice, also on weapon skills.
  Ergon     the same as Mythic.
  Empyrean  occasionally triple damage: 30 / 40 / 50 %. Damage only: it doesn't make TP any faster.
  Aeonic    skillchain and magic burst damage only (used up by the skillchain): nothing wsdist can count.
  Prime     physical damage limit (Lorg Mor, Opashoro: magic). Damage only.
Only the main hand counts: a weapon in the sub slot gives no Aftermath, and a ranged one only helps ranged attacks.

wsdist knows most of it (abilities['Aftermath'] 0-3) but has to be told the level, one for all weapons. Here: the level each
weapon is normally kept at, and what wsdist has different from the game (extras, added as a buff).
"""
import os
import re

import paths

RELIC = {'Spharai': 'Final Heaven', 'Mandau': 'Mercy Stroke', 'Excalibur': 'Knights of Round', 'Ragnarok': 'Scourge',
         'Guttler': 'Onslaught', 'Bravura': 'Metatron Torment', 'Apocalypse': 'Catastrophe', 'Gungnir': 'Geirskogul',
         'Kikoku': 'Blade: Metsu', 'Amanomurakumo': 'Tachi: Kaiten', 'Mjollnir': 'Randgrith', 'Claustrum': 'Gate of Tartarus',
         'Yoichinoyumi': 'Namas Arrow', 'Annihilator': 'Coronach'}
MYTHIC = {'Conqueror': "King's Justice", 'Glanzfaust': "Ascetic's Fury", 'Yagrush': 'Mystic Boon', 'Laevateinn': 'Vidohunir',
          'Murgleis': 'Death Blossom', 'Vajra': 'Mandalic Stab', 'Burtgang': 'Atonement', 'Liberator': 'Insurgency',
          'Aymur': 'Primal Rend', 'Carnwenhan': 'Mordant Rime', 'Gastraphetes': 'Trueflight', 'Kogarasumaru': 'Tachi: Rana',
          'Nagi': 'Blade: Kamu', 'Ryunohige': 'Drakesbane', 'Nirvana': 'Garland of Bliss', 'Tizona': 'Expiacion',
          'Death Penalty': 'Leaden Salute', 'Kenkonken': 'Stringing Pummel', 'Terpsichore': 'Pyrrhic Kleos',
          'Tupsimati': 'Omniscience'}
ERGON = {'Idris': 'Exudation', 'Epeolatry': 'Dimidiation'}
EMPYREAN = {'Verethragna': 'Victory Smite', 'Twashtar': "Rudra's Storm", 'Almace': 'Chant du Cygne', 'Caladbolg': 'Torcleaver',
            'Farsha': 'Cloudsplitter', 'Ukonvasara': "Ukko's Fury", 'Redemption': 'Quietus', 'Rhongomiant': "Camlann's Torment",
            'Kannagi': 'Blade: Hi', 'Masamune': 'Tachi: Fudo', 'Gambanteinn': 'Dagan', 'Hvergelmir': 'Myrkr',
            'Gandiva': "Jishnu's Radiance", 'Armageddon': 'Wildfire'}
AEONIC = {'Godhands': 'Shijin Spiral', 'Aeneas': 'Exenterator', 'Sequence': 'Requiescat', 'Lionheart': 'Resolution',
          'Tri-edge': 'Ruinator', 'Chango': 'Upheaval', 'Anguta': 'Entropy', 'Trishula': 'Stardiver',
          'Heishi Shorinken': 'Blade: Shun', 'Dojikiri Yasutsuna': 'Tachi: Shoha', 'Tishtrya': 'Realmrazer',
          'Khatvanga': 'Shattersoul', 'Fail-Not': 'Apex Arrow', 'Fomalhaut': 'Last Stand'}
PRIME = {'Varga Purnikawa': 'Maru Kala', 'Mpu Gandring': 'Ruthless Stroke', 'Caliburnus': 'Imperator', 'Helheim': 'Fimbulvetr',
         'Spalirisos': 'Blitz', 'Laphria': 'Disaster', 'Foenaria': 'Origin', 'Gae Buide': 'Diarmuid', 'Dokoku': 'Zesho Meppo',
         'Kusanagi-no-Tsurugi': 'Tachi: Mumei', 'Lorg Mor': 'Dagda', 'Opashoro': 'Oshala', 'Pinaka': 'Sarv', 'Earp': 'Terminus'}
FAMILIES = {'Relic': RELIC, 'Mythic': MYTHIC, 'Ergon': ERGON, 'Empyrean': EMPYREAN, 'Aeonic': AEONIC, 'Prime': PRIME}
# (one word for all of a family, by name in any capitals: wsdist writes "Fail-not", the game "Fail-Not")
_BY_NAME = {w.lower(): (f, w, ws) for f, t in FAMILIES.items() for w, ws in t.items()}
_BY_WS = {ws: w for t in FAMILIES.values() for w, ws in t.items()}

# The level he'd keep it at. Relic has only one effect (any level); Aeonic has nothing wsdist can count.
AUTO_LEVEL = {'Relic': 1, 'Mythic': 3, 'Ergon': 3, 'Empyrean': 3, 'Aeonic': 0, 'Prime': 3}

# Aftermath that only protects or only heals (nothing for damage)
NO_DAMAGE = {'Excalibur': 'Regen and Refresh', 'Bravura': 'damage taken and Regen', 'Claustrum': 'damage taken and Refresh'}
# wsdist's Aftermath damage taken: a set must reach his DT numbers with its gear, as with Shell V (wsdist_runner.buff_options)
AM_DT = {'Bravura': 20, 'Claustrum': 20}
# The item text / BG Wiki at 3000 TP against wsdist's 20 / 30 ("needs testing" in its code): {name: {stage: {stat: to add}}}
PRIME_MAGIC = {'Lorg Mor': {'IV': {'Magic Damage': 60}},
               'Opashoro': {'IV': {'Magic Damage': 30, 'Magic Attack': 10}, 'V': {'Magic Damage': 50, 'Magic Attack': 10}}}


def _find(name):
    return _BY_NAME.get((name or '').lower())


def family(name):
    """'Mythic' for Tizona; None for a weapon that isn't one."""
    found = _find(name)
    return found[0] if found else None


def linked_ws(name):
    """The weapon skill that gives its Aftermath (Tizona: Expiacion)."""
    found = _find(name)
    return found[2] if found else None


def ws_weapon(ws):
    """The Ultimate Weapon a weapon skill belongs to (Insurgency: Liberator), None for any other."""
    return _BY_WS.get(ws)


def needs_weapon(ws):
    """What a weapon skill asks of the weapon, from BG Wiki's weapon skill pages (2026-10-30):
    'always': Relic and Prime only work on their own weapon (or a lesser version of it, like Crisis Scythe for Catastrophe);
    'quest': Mythic, Empyrean and Ergon need their weapon until a quest opens them to any weapon of the kind (QUEST), which the
    Doctor can't see; None: any weapon of the kind (Aeonic = merit skills; any skill not listed here)."""
    return {'Relic': 'always', 'Prime': 'always', 'Mythic': 'quest', 'Empyrean': 'quest', 'Ergon': 'quest'}.get(family(ws_weapon(ws)))


QUEST = {'Mythic': 'Unlocking a Myth', 'Empyrean': "Kupofried's Weapon Skill Moogle Magic", 'Ergon': 'its job quest'}


def needs_text(ws):
    """Why a weapon skill wasn't judged, in plain words."""
    weapon = ws_weapon(ws)
    if needs_weapon(ws) == 'quest':
        return (f"{ws} needs {weapon}, which isn't in your bags. If you've done {QUEST[family(weapon)]} it works on any weapon "
                f"of the kind: pick yours in Build a set to judge it")
    return f"{ws} only works on {weapon}, which isn't in your bags"


def named_level(am, entry):
    """The level a set's name asks for. am: a number (.AM3) or 'up' (.AM). A Relic has one effect, an Aeonic nothing wsdist counts."""
    fam = family((entry or {}).get('Name'))
    if not fam:
        return 0
    if am == 'up' or fam in ('Relic', 'Aeonic'):
        return AUTO_LEVEL[fam]
    return am


def level_for(setting, entry):
    """The Aftermath level to judge a set with. setting: 'auto' (what this weapon is kept at) or a level 0-3. entry: the wsdist
    entry in the main hand. (A weapon that isn't one of these: 0.)"""
    fam = family((entry or {}).get('Name'))
    if not fam:
        return 0
    if setting == 'auto':
        return AUTO_LEVEL[fam]
    return int(setting or 0)


def extras(entry, level):
    """{stat: number} to add to wsdist's own Aftermath, as a buff: what it has different from the game."""
    if level <= 0 or not entry:
        return {}
    found = _find(entry.get('Name'))
    name = found[1] if found else None
    out = {}
    if name in AM_DT:
        out['DT'] = AM_DT[name]                               # (takes it back off: only his gear counts for his DT numbers)
    if level == 3 and name in PRIME_MAGIC:
        out.update(PRIME_MAGIC[name].get(str(entry.get('Name2', '')).split()[-1], {}))
    return out


def judged_by_dps(entry, level):
    """Time to a weapon skill can't see this weapon's Aftermath (triple damage and damage limit don't make TP faster): its TP
    sets need damage counted too. (Aeonic has nothing to count; with Aftermath off, nothing changes.)"""
    fam = family((entry or {}).get('Name'))
    return bool(fam) and fam != 'Aeonic' and level > 0


def note(entry, level, setting='auto'):
    """In plain words, for the upgrade's notes."""
    found = _find((entry or {}).get('Name'))
    if not found:
        return ''
    fam, name, ws = found
    if fam == 'Aeonic':
        return (f"{name} (Aeonic): its Aftermath only adds skillchain and magic burst damage, which wsdist doesn't count, "
                f"so this set is judged without it")
    if level <= 0:
        return f"{name} ({fam}): judged without Aftermath"
    if name in NO_DAMAGE:
        return f"{name} ({fam}): its Aftermath is {NO_DAMAGE[name]}, no extra damage"
    lv = 'Aftermath' if fam == 'Relic' else f'Aftermath Lv.{level}'
    return f"{name} ({fam}): {lv} counted, as if you keep it up with {ws}"


_DMG = None


def _item_dmg(iid):
    """The DMG in the game's own item text (Windower's res folder), or None."""
    global _DMG
    if _DMG is None:
        _DMG = {}
        try:
            text = open(os.path.join(paths.WINDOWER or '', 'res', 'item_descriptions.lua'), encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'\[(\d+)\]\s*=\s*\{id=\d+,en="DMG:\+?(\d+)', text):
                _DMG[int(m.group(1))] = int(m.group(2))
        except OSError:
            pass
    return _DMG.get(iid)


def stage_ids(name, items):
    """A Prime weapon's items, strongest (stage V) first: the game has one per stage under one name. By the item's DMG: the ids
    aren't always in order (Helheim's and Lorg Mor's strongest has the lowest id)."""
    ids = sorted({it['id'] for it in items.find(name) if name.lower() in (it['en'].lower(), it['enl'].lower())})
    return sorted(ids, key=lambda i: (_item_dmg(i) or 0, i), reverse=True)


def owned_stage(name, owned_ids, items):
    """His highest stage of a Prime weapon: 5 for the strongest item, 4 for the next. None: not in his bags."""
    have = [5 - i for i, iid in enumerate(stage_ids(name, items)) if iid in owned_ids]
    return max(have) if have else None
