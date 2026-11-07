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
    if guessed:
        return f"{name}: {' and '.join(guessed)} not on BG Wiki yet, estimated from its level"
    return f"{name}: Defense and Evasion from BG Wiki"
