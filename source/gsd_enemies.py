"""
GearSwap Doctor's own enemies, added to wsdist's (Kastra's) list: it survives a wsdist update, and it can grow without waiting for one.

Numbers from each monster's BG Wiki page, the middle of its range. That's Kastra's way: Apex Toad's page says DEF 1206-1272, EVA 1103-1163, his table 1239 and 1133.
No page gives VIT, AGI, MND, INT or CHR for these: they come from wsdist's Apex monsters of about the same level. A missing DEF or EVA does too, and says so (note()).
'Magic Defense' is above the usual 100, as wsdist counts it (Apex Toad's page says 100, his table 0).
"""
# name: (level, DEF or None, EVA or None, M.DEF or None, zone). bg-wiki.com/ffxi/<name>, 2026-10-31
LOCUS = {
    'Locus Colibri': (134, 1259, 1202, 114, 'Bhaflau Thickets'),
    'Locus Wivre': (136, 1404, 1254, 100, 'Bhaflau Thickets'),
    'Locus Bight Rarab': (136, 1380, 1254, 100, 'Bibiki Bay'),
    'Locus Camelopard': (136, 1380, 1254, 100, 'Bibiki Bay'),
    'Locus Hypnos Eft': (136, 1380, 1254, 100, 'Bibiki Bay'),
    'Locus Fiddler Crab': (138, 1446, 1341, 122, 'Bibiki Bay'),
    'Locus Ghost Crab': (138, 1446, 1341, 122, 'Bibiki Bay'),
    # (these pages have gaps. Dire Bat's one number, 1272 - 1344, fits DEF at its level; Imp's, 1171 - 1231, fits EVA)
    'Locus Dire Bat': (134, 1308, None, None, "King Ranperre's Tomb"),
    'Locus Imp': (135, None, 1201, None, 'Caedarva Mire'),
    'Locus Armet Beetle': (134, None, None, None, "King Ranperre's Tomb"),
    'Locus Tomb Worm': (132, None, None, None, "King Ranperre's Tomb"),
}
# Content monsters (PLAN.md A3, 2026-11-14): BG Wiki gives their level but not Defense or Evasion, so both are estimated from the level with wsdist's
# Apex table (the same way as a Locus page with gaps) and every result says so. Levels: BG Wiki Bumba (139), Category:Sortie (sector foes A 119-121 ...
# H 137-139, Naakuals 140). Sortie's bosses have no level on the wiki: the Naakual's 140 stands for them.
CONTENT = {
    'Odyssey boss (level 139)': (139, None, None, None, 'Sheol Gaol'),
    'Sortie foes A-D (level 126)': (126, None, None, None, 'Sortie'),
    'Sortie foes E-H (level 137)': (137, None, None, None, 'Sortie'),
    'Sortie boss / Naakual (level 140)': (140, None, None, None, 'Sortie'),
}
LOCUS = dict(LOCUS, **CONTENT)

# Where he is going: the monster and the buffs a set is judged with, in one pick. buffs: a key of wsdist_runner.BUFF_PRESETS. A profile with no
# monster keeps the one he has picked (Dynamis and Ambuscade monsters have no published level to estimate from; Ambuscade changes every month).
PROFILES = [
    {'name': 'Apex monsters with trusts (solo)', 'enemy': 'Apex Toad', 'buffs': 'solo',
     'what': 'Farming Apex monsters alone: food and trust buffs (Haste II, two Marches).'},
    {'name': 'Apex monsters in a party', 'enemy': 'Apex Bat', 'buffs': 'party',
     'what': 'An experience or capacity party: a healer, a Bard and a Corsair.'},
    {'name': 'Master levels (Locus monsters)', 'enemy': 'Locus Colibri', 'buffs': 'party',
     'what': 'A master level party on Locus monsters.'},
    {'name': 'Odyssey boss (Sheol Gaol)', 'enemy': 'Odyssey boss (level 139)', 'buffs': 'party',
     'what': 'A Sheol Gaol boss. Level 139 is from BG Wiki; its Defense and Evasion are estimated from that level, and a real Vengeance fight is harder.'},
    {'name': 'Sortie, sectors A-D', 'enemy': 'Sortie foes A-D (level 126)', 'buffs': 'party',
     'what': 'Sortie ground floor foes (levels 119-133). Defense and Evasion estimated from the level.'},
    {'name': 'Sortie, sectors E-H', 'enemy': 'Sortie foes E-H (level 137)', 'buffs': 'party',
     'what': 'Sortie basement foes (levels 134-139). Defense and Evasion estimated from the level.'},
    {'name': 'Sortie bosses', 'enemy': 'Sortie boss / Naakual (level 140)', 'buffs': 'party',
     'what': 'Sortie bosses: BG Wiki gives them no level, so the Naakuals\' 140 stands in. Defense and Evasion estimated.'},
    {'name': 'Dynamis - Divergence', 'enemy': None, 'buffs': 'party',
     'what': 'Party buffs. No level is published for its monsters, so the monster you picked stays.'},
    {'name': 'Ambuscade', 'enemy': None, 'buffs': 'party',
     'what': 'Party buffs. The monster changes every month, so the monster you picked stays.'},
]


def profile(name):
    return next((p for p in PROFILES if p['name'] == name), None)


def profile_of(enemy, buffs):
    """The profile these settings are, or '' (his own mix)."""
    return next((p['name'] for p in PROFILES if p['enemy'] == enemy and p['buffs'] == buffs), '')


STATS = ('VIT', 'AGI', 'MND', 'INT', 'CHR')
_estimated = {}


def _from_table(table, level, stat):
    """A stat at this level, from the Apex monsters in wsdist's table: straight between the two nearest levels."""
    rows = sorted((e['Level'], e[stat]) for n, e in table.items() if n.startswith('Apex') and e.get('Level', 0) < 200)
    below = [r for r in rows if r[0] <= level]
    above = [r for r in rows if r[0] >= level]
    if not below or not above:
        return (below or above)[-1 if below else 0][1]
    a, b = below[-1], above[0]
    if a[0] == b[0]:
        return a[1]
    return round(a[1] + (b[1] - a[1]) * (level - a[0]) / (b[0] - a[0]))


def add_to(table):
    """Put ours in wsdist's preset_enemies (a monster it has itself stays as it is)."""
    for name, (level, dfn, eva, mdef, zone) in LOCUS.items():
        if name in table:
            continue
        guessed = []
        e = {'Name': name, 'Level': level, 'Magic Evasion': 0, 'Magic Defense': max(0, (mdef or 100) - 100), 'Magic DT%': 0, 'Location': zone}
        e['Defense'] = dfn if dfn else _from_table(table, level, 'Defense')
        e['Evasion'] = eva if eva else _from_table(table, level, 'Evasion')
        if not dfn:
            guessed.append('Defense')
        if not eva:
            guessed.append('Evasion')
        for s in STATS:
            e[s] = _from_table(table, level, s)
        _estimated[name] = guessed
        table[name] = e
    return table


def note(name):
    """For the notes: how much of a monster's numbers are known."""
    if name not in _estimated:
        return ''
    guessed = _estimated[name]
    if name in CONTENT:
        return f"{name}: its level is from BG Wiki; Defense and Evasion are estimated from the level, so treat the numbers as a guide"
    if guessed:
        return f"{name}: {' and '.join(guessed)} not on BG Wiki yet, estimated from its level"
    return f"{name}: Defense and Evasion from BG Wiki"
