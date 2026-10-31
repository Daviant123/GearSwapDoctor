"""
GearSwap Doctor: what a set is for, read from its name and the file's own lists. His question 2026-10-30: does it detect the
weapon being used? On a Mote file like his DRK the sets name no weapon; the name says it: sets.engaged.Haste.Liberator.Acc.PDT.AM3
= Liberator, delay capped, accuracy matters, damage taken matters, Aftermath Lv.3 up.

Nothing here runs wsdist: FileInfo(loaded, index) -> .read(path) -> {'weapon', 'kind', 'form', 'am', 'haste', 'acc', 'mid', 'dt',
'reraise', 'modes'}.
"""
import re

import fixer
import rema

# Set names for a kind of weapon -> wsdist's Skill Type
KINDS = {'greatsword': 'Great Sword', 'gs': 'Great Sword', 'scythe': 'Scythe', 'sword': 'Sword', 'dagger': 'Dagger', 'axe': 'Axe',
         'greataxe': 'Great Axe', 'ga': 'Great Axe', 'polearm': 'Polearm', 'katana': 'Katana', 'greatkatana': 'Great Katana',
         'gkt': 'Great Katana', 'club': 'Club', 'staff': 'Staff', 'h2h': 'Hand-to-Hand', 'handtohand': 'Hand-to-Hand'}
ONE_HANDED = ('Sword', 'Dagger', 'Axe', 'Club', 'Katana')
# Haste levels by name: 'cap' = delay capped; a number = magic haste in % (the usual Mote dual wield steps)
HASTE = {'haste': 'cap', 'maxhaste': 'cap', 'fullhaste': 'cap', 'caphaste': 'cap', 'highhaste': 35, 'midhaste': 30, 'lowhaste': 15}
ACC = ('acc', 'accuracy', 'highacc', 'maxacc', 'fullacc')
MID = ('mid', 'midacc', 'medacc', 'lowacc')
DT = ('pdt', 'dt', 'mdt', 'hybrid', 'tank')


def norm(name):
    """'Montante +1' -> 'montante1': names in sets lose their spaces and capitals (HeishiShorinken)."""
    return re.sub(r'[^a-z0-9]', '', (name or '').lower())


def _am_token(low):
    """'am3' -> 3, 'am' -> 'up', anything else None."""
    m = re.match(r'^(?:am|aftermath)(\d?)$', low)
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else 'up'


def _set_tokens(path):
    """The parts of a set's name that can describe it: after sets.engaged / sets.TP, or after the weapon skill's name."""
    parts = fixer._path_parts(path)
    low = [p.lower() for p in parts]
    if len(parts) >= 2 and low[1] in ('engaged', 'tp'):
        return parts[2:]
    if 'ws' in low:
        return parts[low.index('ws') + 2:]
    return []


class FileInfo:
    """One file's set names. index: wsdist_runner.gear_index()."""

    def __init__(self, loaded, index):
        self.index = index
        self.weapons = {}                        # norm(name): name
        for entries in index.values():
            if entries and entries[0].get('Type') == 'Weapon':
                self.weapons[norm(entries[0]['Name'])] = entries[0]['Name']
        # the file's own lists (gsList, scytheList, remaWeapons): a list counts when at least half of it are weapons wsdist knows
        self.lists = {}
        for var, names in (getattr(loaded, 'lists', None) or {}).items():
            if sum(norm(n) in self.weapons for n in names) * 2 >= len(names) > 0:
                self.lists[var] = names
                for n in names:
                    self.weapons.setdefault(norm(n), n)
        self.listed = [n for names in self.lists.values() for n in names]
        self.short = {}                          # the first word is enough for these: sets.engaged.Dojikiri
        for name in [w for t in rema.FAMILIES.values() for w in t] + self.listed:
            word = norm(re.split(r'[\s-]', name)[0])
            if len(word) >= 5 and word != norm(name):
                self.short.setdefault(word, self.weapons.get(norm(name), name))
        paths = [s['path'] for s in loaded.sets]
        self.named = set()                       # weapons with sets of their own
        self.with_am = set()                     # weapons (or kinds, or '') that have Aftermath sets
        for p in paths:
            r = self._parse(p)
            if r['weapon']:
                self.named.add(r['weapon'])
            if r['am'] is not None:
                self.with_am.add(self.label(r))

    def _weapon(self, token):
        n = norm(token)
        return self.weapons.get(n) or self.short.get(n)

    def _parse(self, path):
        out = {'weapon': None, 'kind': None, 'form': None, 'am': None, 'haste': None, 'acc': False, 'mid': False, 'dt': False,
               'reraise': False, 'modes': []}
        for token in _set_tokens(path):
            low = norm(token)
            am = _am_token(low)
            if am is not None:
                out['am'] = am
                out['modes'].append('AM')
            elif low in HASTE:
                out['haste'] = HASTE[low]
                out['modes'].append('Haste')
            elif low in ACC:
                out['acc'] = True
                out['modes'].append('Acc')
            elif low in MID:
                out['mid'] = True
                out['modes'].append('Mid')
            elif low in DT:
                out['dt'] = True
                out['modes'].append('DT')
            elif low in ('dw', 'sw'):
                out['form'] = low.upper()
            elif low == 'reraise':
                out['reraise'] = True
            elif low in KINDS:
                out['kind'] = KINDS[low]
            elif self._weapon(token):
                out['weapon'] = self._weapon(token)
            elif low != 'normal':
                out['modes'].append(token)        # (a mode of his own: still a mode)
        return out

    @staticmethod
    def label(r):
        """What a set's weapon part is, for "one set per weapon and mode"."""
        return r['weapon'] or r['kind'] or r['form'] or ''

    def read(self, path):
        """What the set is for. 'am_down': this weapon has Aftermath sets in this file and this isn't one of them."""
        r = self._parse(path)
        r['am_down'] = r['am'] is None and self.label(r) in self.with_am
        return r

    def is_listed(self, name):
        return norm(name) in {norm(n) for n in self.listed}
