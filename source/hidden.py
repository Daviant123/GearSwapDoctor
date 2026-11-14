"""
What an item's text doesn't say (PLAN.md E3, 2026-11-14): set bonuses (the text after "Set:" has no numbers) and a few named pieces.

  family(text, name) -> the set an item belongs to (a key of SETS), or None
  bonus(gear)        -> {stat: value} the pieces of a set worn together give ({slot: candidate}, as healing.totals gets it)
  named(text, name)  -> {stat: value} of a piece whose text hides its number

Sources (RESEARCH.md "Hidden bonuses, 2026-11-14"): BG Wiki's armor set pages (Reverence, Ayanmo, Souveran, Carmine, Chevalier's), the item pages of
Carnwenhan (Level 119 III) and Daurdabla (Level 99); Kastra's wsdist create_player.py for Adhemar, Amalric, Ryuo, Lustratio.
"""
import re

# kind 'step': nothing for one piece, `per` for every piece after the first (2 pieces = per ... 5 pieces = 4 x per)
# kind 'each': nothing for one piece, then `per` for every piece worn (2 pieces = 2 x per ... 5 pieces = 5 x per)
# kind 'all':  the numbers written in the text, once every piece (`need`) is worn
# A set counts 5 pieces at most (an Ambuscade set has 6 with its ring). name: the item's name must start with it (two sets share the words).
SETS = {
    # reforged artifact armor +2 / +3 / +4, with the Regal Ring / Regal Earring (their text has the same line)
    'af': {'text': ('increases accuracy, ranged accuracy, and magic accuracy', 'accuracy+ ranged accuracy+ magic accuracy+',
                    'inc. acc., ranged acc., and magic acc.'), 'kind': 'step', 'per': 15, 'stats': ('acc', 'racc', 'macc'),
           'words': 'Accuracy, Ranged Accuracy and Magic Accuracy +15 for each piece after the first (60 with five)'},
    # Ambuscade +2 armor and its ring
    'flamma': {'text': ('increases strength, dexterity, and vitality',), 'kind': 'step', 'per': 8, 'stats': ('STR', 'DEX', 'VIT'),
               'words': 'STR, DEX and VIT +8 for each piece after the first'},
    'mummu': {'text': ('increases dexterity, agility, and charisma',), 'kind': 'step', 'per': 8, 'stats': ('DEX', 'AGI', 'CHR'),
              'words': 'DEX, AGI and CHR +8 for each piece after the first'},
    'mallquis': {'text': ('increases vitality, intelligence, and mind',), 'kind': 'step', 'per': 8, 'stats': ('VIT', 'INT', 'MND'),
                 'words': 'VIT, INT and MND +8 for each piece after the first'},
    'ayanmo': {'text': ('increases strength, vitality, and mind',), 'kind': 'step', 'per': 8, 'stats': ('STR', 'VIT', 'MND'),
               'words': 'STR, VIT and MND +8 for each piece after the first'},
    "tali'ah": {'text': ('increases dexterity, vitality, and charisma', 'increases vitality, dexterity, and charisma'), 'kind': 'step', 'per': 8,
                'stats': ('DEX', 'VIT', 'CHR'), 'words': 'DEX, VIT and CHR +8 for each piece after the first'},
    'meghanada': {'text': ('enhances "regen" effect',), 'kind': 'step', 'per': 3, 'stats': ('regen',), 'words': 'Regen +3 for each piece after the first'},
    'inyanga': {'text': ('enhances "refresh" effect',), 'kind': 'step', 'per': 1, 'stats': ('refresh',), 'words': 'Refresh +1 for each piece after the first'},
    'jhakri': {'text': ('enhances "fast cast"',), 'kind': 'step', 'per': 3, 'stats': ('fast',), 'words': 'Fast Cast +3 % for each piece after the first'},
    'sulevia': {'text': ('enhances "subtle blow" effect',), 'name': 'sulev', 'kind': 'step', 'per': 5, 'stats': ('subtle',),
                'words': 'Subtle Blow +5 for each piece after the first'},
    'hizamaru': {'text': ('enhances "counter" effect',), 'name': 'hiza', 'kind': 'step', 'per': 4, 'stats': ('counter',),
                 'words': 'Counter +4 % for each piece after the first'},
    # abjuration / Escha +1 sets
    'kaykaus': {'text': ('enhances "cure" potency ii effect',), 'kind': 'each', 'per': 2, 'stats': ('potency2',), 'words': 'Cure potency II +2 % for each piece (two or more)'},
    'souveran': {'text': ('reduces damage taken',), 'name': 'souv', 'kind': 'each', 'per': 2, 'stats': ('dt',), 'words': 'Damage taken -2 % for each piece (two or more)'},
    'carmine': {'text': ('increases accuracy',), 'name': 'carm', 'kind': 'each', 'per': 10, 'stats': ('acc',), 'words': 'Accuracy +10 for each piece (two or more)'},
    'adhemar': {'text': ('increases rate of critical hits',), 'name': 'adhe', 'kind': 'each', 'per': 2, 'stats': ('crit',),
                'words': 'Critical hit rate +2 % for each piece (two or more)'},
    'amalric': {'text': ('enhances "magic atk. bonus" effect',), 'name': 'amalric', 'kind': 'each', 'per': 10, 'stats': ('matk',),
                'words': 'Magic Atk. Bonus +10 for each piece (two or more)'},
    'ryuo': {'text': ('increases attack',), 'name': 'ryuo', 'kind': 'each', 'per': 10, 'stats': ('att',), 'words': 'Attack +10 for each piece (two or more)'},
    'lustratio': {'text': ('increases weapon skill damage',), 'name': 'lustr', 'kind': 'each', 'per': 2, 'stats': ('wsd',),
                  'words': 'Weapon skill damage +2 % for each piece (two or more)'},
    # pairs: the text gives the numbers, for both pieces together
    'bladeborn': {'text': ('"double attack"+7%',), 'kind': 'all', 'need': 2, 'add': {'da': 7}, 'words': 'Double Attack +7 % with both earrings'},
    'lifestorm': {'text': ('magic accuracy+12',), 'kind': 'all', 'need': 2, 'add': {'macc': 12}, 'words': 'Magic Accuracy +12 with both earrings'},
    'helenus': {'text': ('magic accuracy+5 "magic atk. bonus"+5',), 'kind': 'all', 'need': 2, 'add': {'macc': 5, 'matk': 5},
                'words': 'Magic Accuracy +5 and Magic Atk. Bonus +5 with both earrings'},
    'dasra': {'text': ('hp+50 mp+50',), 'kind': 'all', 'need': 2, 'add': {'HP': 50, 'MP': 50}, 'words': 'HP +50 and MP +50 with both rings'},
    'serpentes': {'text': ('"cure" potency +5%',), 'kind': 'all', 'need': 2, 'add': {'potency': 5}, 'words': 'Cure potency +5 % with both pieces'},
    'alcedo': {'text': ('magic damage taken-5%',), 'kind': 'all', 'need': 2, 'add': {'mdt': 5}, 'words': 'Magic damage taken -5 % with both pieces'},
    'susurrus': {'text': ('hp+90',), 'kind': 'all', 'need': 2, 'add': {'HP': 90}, 'words': 'HP +90 with both pieces'},
}
MOST = 5

_BY_TEXT = {}
for _k, _s in SETS.items():
    for _t in _s['text']:
        _BY_TEXT.setdefault(_t, []).append(_k)
_SET_RX = re.compile(r'\bSet: *(.*)$')


def family(text, name=''):
    """The set (a key of SETS) an item's text puts it in, or None: no "Set:" line, or a set whose bonus isn't known here."""
    m = _SET_RX.search(text or '')
    if not m:
        return None
    phrase = ' '.join(m.group(1).lower().split())
    low = (name or '').lower()
    for k in _BY_TEXT.get(phrase, ()):
        need = SETS[k].get('name')
        if not need or low.startswith(need):
            return k
    return None


def value(key, n):
    """{stat: value} for n pieces of the set worn."""
    s = SETS[key]
    n = min(n, MOST)
    if s['kind'] == 'all':
        return dict(s['add']) if n >= s['need'] else {}
    if n < 2:
        return {}
    v = s['per'] * (n - 1 if s['kind'] == 'step' else n)
    return {k: v for k in s['stats']}


def count(gear):
    """{set: pieces worn} for a set of gear ({slot: candidate}); the same item in both ears / rings counts once."""
    seen, out = set(), {}
    for c in gear.values():
        k = c and c.get('set')
        if k and (k, c['name']) not in seen:
            seen.add((k, c['name']))
            out[k] = out.get(k, 0) + 1
    return out


def bonus(gear):
    """{stat: value} from every set bonus the gear has."""
    out = {}
    for k, n in count(gear).items():
        for st, v in value(k, n).items():
            out[st] = out.get(st, 0) + v
    return out


def words(gear):
    """Plain lines about the set bonuses at work: ["Souveran: 4 pieces, Damage taken -8 %", ...]."""
    out = []
    for k, n in sorted(count(gear).items()):
        v = value(k, n)
        if v:
            nums = ', '.join(f'{st} {"-" if st in ("dt", "pdt", "mdt") else "+"}{x}' for st, x in v.items())
            out.append(f"{'Artifact armor' if k == 'af' else k.capitalize()} set bonus: {min(n, MOST)} pieces ({nums})")
    return out


# pieces whose text has no number for what they do (the final versions' values)
NAMED = [
    (re.compile(r'Increases? song effect duration V\b'), None, {'song_dur': 50}),      # Carnwenhan 119 III: "Increases Song duration by 50%"
    (re.compile(r'Increases song effect duration(?! ?\+)'), 'daurdabla', {'song_dur': 30}),   # Daurdabla 99: "Increases Song duration by 30%"
]


def named(text, name=''):
    out = {}
    low = (name or '').lower()
    for rx, who, st in NAMED:
        if (not who or low.startswith(who)) and rx.search(text or ''):
            out.update(st)
    return out
