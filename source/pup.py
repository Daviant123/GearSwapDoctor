"""
GearSwap Doctor: Puppetmaster's automaton sets (his request 2026-10-31: "go and research pup because it is a little different from other jobs because of the automaton").
wsdist can't: its Automaton tab is "work in progress. Still need details on automaton stats" (gui_main.py) and it ignores every "Pet:" stat on gear. So a pet set is judged here,
on the game's item text and the augments his files name, by what the pet is doing. Master-only sets (sets.engaged, weapon skills) stay with wsdist.

What the sets are for and why (sources in RESEARCH.md: BG Wiki's Automaton page, FFXIAH's Toy Theater and String Theory):
  gear haste first for a pet that fights, capped at 25 % ("far more important than anything else"); magic haste comes from attachments, which gear can't touch
  tanks: pet damage taken; with Armor Plate IV, Optic Fiber I / II and a Light Maneuver about 36 % from gear is enough (Harlequin 6.25 more, Stormwaker 12.5 more)
  pet weapon skills: attack, accuracy, TP bonus (Dispersal Mantle's +500 was "noticeably significant"), automaton level
The Doctor can't see the frame, head or attachments in the game, so the set's name says the role, or he picks it.
"""
import re

import fixer
import healing

# (the game writes these on an item after "Pet:" or "Automaton:", and his augments shorter: Pet: "Dbl. Atk."+5, Pet: Rng.Atk.+22)
PET_RX = [(k, re.compile(rx, re.I)) for k, rx in [
    ('acc', r'(?<![a-z] )(?<![a-z.])(?<!Rng\. )(?<!R\. )(?<!Mag\. )(?<!M\. )(?:Accuracy|Acc\.) ?\+(\d+)(?!\s*%)'), ('racc', r'(?:Ranged Accuracy|Rng\. ?Acc\.|R\. ?Acc\.|Ranged Acc\.) ?\+(\d+)(?!\s*%)'),
    ('macc', r'(?:Magic Accuracy|Mag\. ?Acc\.|Magic Acc\.|M\. ?Acc\.) ?\+(\d+)(?!\s*%)'),
    ('att', r'(?<![a-z] )(?<![a-z.])(?<!Rng\. )(?<!R\. )(?:Attack|Atk\.) ?\+(\d+)(?!\s*%)'), ('ratt', r'(?:Ranged Attack|Rng\. ?Atk\.|R\. ?Atk\.) ?\+(\d+)(?!\s*%)'),
    ('matk', r'(?:"Magic Atk\. Bonus"|"?Mag\. ?Atk\. ?Bns\.?"?|MAB) ?\+(\d+)'), ('haste', r'\bHaste ?\+(\d+)'),
    ('da', r'(?:"Double Attack"|"Dbl\. ?Atk\."|Double Attack) ?\+(\d+)'), ('ta', r'"?(?:Triple Attack|Trpl\. ?Atk\.)"? ?\+(\d+)'), ('qa', r'"?Quad(?:ruple)? Attack"? ?\+(\d+)'),
    ('crit', r'(?:Critical hit rate|Crit\. ?hit rate) ?\+(\d+)'), ('stp', r'"Store TP" ?\+(\d+)'), ('regen', r'"?Regen"? ?\+(\d+)'), ('refresh', r'"?Refresh"? ?\+(\d+)'),
    ('regain', r'"?Regain"? ?\+(\d+)'), ('dt', r'(?<![a-z] )(?:Damage taken|DT) ?-(\d+)'), ('pdt', r'(?:Physical Damage taken|Phys\. dmg\. taken|PDT) ?-(\d+)'),
    ('mdt', r'(?:Magic Damage taken|Mag\. dmg\. taken|MDT) ?-(\d+)'), ('enmity', r'Enmity ?\+(\d+)'), ('hp', r'(?<![a-z])HP ?\+(\d+)'), ('str', r'\bSTR ?\+(\d+)'), ('dex', r'\bDEX ?\+(\d+)'),
    ('vit', r'\bVIT ?\+(\d+)'), ('int', r'\bINT ?\+(\d+)'), ('mnd', r'\bMND ?\+(\d+)'), ('lvl', r'\bLv\.? ?\+(\d+)'), ('wsd', r'Weapon Skill Damage ?\+(\d+)'), ('tpb', r'"?TP Bonus"? ?\+(\d+)'),
    ('fast', r'"Fast Cast" ?\+(\d+)'),
]]
# where a pet's part of the text ends
_ENDS = re.compile(r'(?:\bSet:|Unity Ranking:|Latent effect|Avatar:|Wyvern:|Luopan:|Enchantment:|Reives:|Campaign:|Assault:|Salvage:|Dynamis[^:]{0,20}:|Besieged:|Nighttime:|Daytime:|Dusk[^:]{0,12}:|Dawn[^:]{0,12}:|\bOn [A-Za-z]+:)')
# the master's own, for what he and the pet do together
MASTER_RX = [(k, re.compile(rx)) for k, rx in [('m_da', r'"Double Attack" ?\+(\d+)|"Dbl\. ?Atk\." ?\+(\d+)'), ('m_ta', r'"Triple Attack" ?\+(\d+)'), ('m_stp', r'"Store TP" ?\+(\d+)')]]
GEAR_HASTE_CAP, TANK_DT = 25, 36


def parse(text):
    """{'pet_haste': 5, ...} from an item's text or one augment. What's after "Pet:" or "Automaton:", up to the next heading."""
    out = {}
    for m in re.finditer(r'(?:Pet|Automaton):', text):
        rest = text[m.end():]
        cut = _ENDS.search(rest)
        part = rest[:cut.start()] if cut else rest
        nxt = re.search(r'(?:Pet|Automaton):', part)              # (several in a row: each once)
        if nxt:
            part = part[:nxt.start()]
        for k, rx in PET_RX:
            n = sum(int(x) for x in rx.findall(part))
            if n:
                out['pet_' + k] = out.get('pet_' + k, 0) + n
    master = re.split(r'(?:Pet|Automaton):|\bSet:|Latent effect', text)[0]
    for k, rx in MASTER_RX:
        n = sum(int(y) for x in rx.findall(master) for y in (x if isinstance(x, tuple) else (x,)) if y)
        if n:
            out[k] = n
    return out


# points for each: haste up to its cap, pet damage taken up to what's asked (see above)
_MELEE = {'haste': 20, 'da': 6, 'ta': 9, 'qa': 12, 'crit': 4, 'stp': 3, 'acc': 0.5, 'att': 0.4, 'lvl': 40, 'str': 0.2, 'dex': 0.2, 'regen': 0.3, 'dt': 1, 'pdt': 1}
FOCUS = {
    'Melee (fights)': _MELEE,
    'Ranged (Sharpshot)': {'haste': 15, 'da': 3, 'crit': 3, 'stp': 4, 'racc': 0.6, 'ratt': 0.5, 'lvl': 40, 'agi': 0.2, 'dex': 0.2, 'regen': 0.3, 'dt': 1},
    'Tank': {'dt': 30, 'pdt': 26, 'mdt': 8, 'regen': 8, 'enmity': 5, 'haste': 6, 'hp': 0.05, 'acc': 0.2, 'att': 0.05, 'da': 1, 'lvl': 40, 'vit': 0.2},
    'Light tank': {'dt': 14, 'pdt': 12, 'mdt': 3, 'haste': 15, 'da': 4, 'ta': 6, 'acc': 0.3, 'att': 0.25, 'enmity': 2, 'regen': 3, 'lvl': 40},
    'Nuke': {'matk': 3, 'macc': 1, 'int': 0.5, 'refresh': 15, 'fast': 3, 'lvl': 40, 'dt': 1, 'haste': 1},
    'Heal': {'mnd': 1, 'macc': 0.4, 'refresh': 15, 'fast': 5, 'lvl': 40, 'dt': 2, 'regen': 2, 'hp': 0.02, 'haste': 1},
    'Weapon skill': {'wsd': 12, 'tpb': 0.06, 'att': 0.7, 'ratt': 0.7, 'acc': 0.5, 'racc': 0.4, 'str': 0.5, 'dex': 0.5, 'vit': 0.3, 'lvl': 60, 'crit': 3, 'da': 2},
    'Magic weapon skill': {'wsd': 10, 'tpb': 0.06, 'matk': 3, 'macc': 1, 'int': 0.5, 'mnd': 0.4, 'lvl': 60},
    'You and the pet': dict(_MELEE, m_haste=8, m_dt=3, m_da=4, m_ta=6, m_stp=2),
    'You and the pet, accuracy': dict(_MELEE, m_haste=8, m_dt=3, m_da=4, m_ta=6, m_stp=2, acc=2, racc=1),
    'Pet waiting': {'m_dt': 12, 'regen': 8, 'refresh': 8, 'dt': 4, 'pdt': 3, 'hp': 0.03, 'm_refresh': 12},
}
BOTH = ('You and the pet', 'You and the pet, accuracy', 'Pet waiting')      # (where you're in it too: what keeps you alive stays)
PET_WORDS = ('pet', 'petwsgear', 'overdrive', 'automaton', 'petenmitygear')


def _words(path):
    return [p.lower() for p in fixer._path_parts(path or '')]


def is_pet_set(path, job='PUP'):
    """A set that's about the automaton: judged here, not by wsdist."""
    if (job or '').upper() != 'PUP':
        return False
    return any(w in PET_WORDS for w in _words(path)) or any(w == 'masterpet' for w in _words(path))


def focus_for(path):
    w = _words(path)
    midcast_ws = 'petwsgear' in w or 'weaponskill' in w or ('pet' in w and 'ws' in w) or any(x.startswith('wsftp') or x.startswith('wsnoftp') for x in w)
    if midcast_ws:
        return 'Magic weapon skill' if any(x in ('magic', 'nuke', 'heal') for x in w) else 'Weapon skill'
    if 'overdrive' in w:
        return 'Melee (fights)'
    if 'lighttank' in w:
        return 'Light tank'
    if 'tank' in w:
        return 'Tank'
    if 'nuke' in w or 'magic' in w or 'elemental magic' in w or 'enfeebling magic' in w:
        return 'Nuke'
    if 'heal' in w:
        return 'Heal'
    if 'ranged' in w or 'sharpshot' in w:
        return 'Ranged (Sharpshot)'
    if w[1:2] == ['engaged'] or 'masterpet' in w:
        return 'You and the pet, accuracy' if any(x in ('acc', 'fullacc', 'mid', 'fodder') for x in w) else 'You and the pet'
    if w[1:2] == ['idle'] and 'engaged' in w:
        return 'Melee (fights)'
    if w[1:2] == ['idle']:
        return 'Pet waiting'
    return 'Melee (fights)'


def numbers(gear):
    """What a set gives the pet (and the master's part that counts here)."""
    t = healing.totals(gear)
    n = {k[4:]: v for k, v in t.items() if k.startswith('pet_')}
    n['gear_haste'] = min(GEAR_HASTE_CAP, n.get('haste', 0))
    n['haste_over'] = max(0, n.get('haste', 0) - GEAR_HASTE_CAP)
    pd, md = healing.dt_totals(t)
    n['m_dt'], n['m_mdt'] = pd, md
    n['m_haste'] = min(GEAR_HASTE_CAP, t.get('haste', 0))
    n['m_refresh'] = t.get('refresh', 0)
    for k in ('m_da', 'm_ta', 'm_stp'):
        n[k] = t.get(k, 0)
    return n


def value(gear, focus):
    w = FOCUS.get(focus) or _MELEE
    n = numbers(gear)
    v = 0
    for k, pts in w.items():
        if k == 'haste':
            v += pts * n['gear_haste']
        elif k in ('dt', 'pdt') and focus in ('Tank', 'Light tank'):
            continue                                             # (below, together)
        else:
            v += pts * n.get(k, 0)
    if focus in ('Tank', 'Light tank'):
        v += w['dt'] * min(TANK_DT, n.get('dt', 0) + n.get('pdt', 0))
    return round(v, 3)


LABELS = (('lvl', 'level +{}'), ('dt', 'damage taken {} %'), ('pdt', 'physical {} %'), ('mdt', 'magic {} %'), ('da', 'Double Attack {} %'), ('ta', 'Triple Attack {} %'), ('qa', 'Quad {} %'),
          ('crit', 'crits {} %'), ('stp', 'Store TP {}'), ('acc', 'accuracy +{}'), ('att', 'attack +{}'), ('racc', 'ranged accuracy +{}'), ('ratt', 'ranged attack +{}'), ('macc', 'magic accuracy +{}'),
          ('matk', 'magic attack +{}'), ('regen', 'Regen +{}'), ('refresh', 'Refresh +{}'), ('regain', 'Regain +{}'), ('enmity', 'enmity +{}'), ('hp', 'HP +{}'), ('wsd', 'weapon skill damage {} %'), ('tpb', 'TP bonus +{}'),
          ('str', 'STR +{}'), ('dex', 'DEX +{}'), ('vit', 'VIT +{}'))


def words(n, focus=None):
    """'Automaton: haste 20/25 %, Double Attack 24 %, accuracy +190 ...; you: damage taken 30 %'"""
    out = [f"haste {n['gear_haste']}/{GEAR_HASTE_CAP} %"]
    for k, text in LABELS:
        if n.get(k):
            out.append(text.format(n[k]))
    line = 'Automaton: ' + ', '.join(out)
    if focus in BOTH:
        line += f"; you: haste {n['m_haste']}/{GEAR_HASTE_CAP} %, damage taken {n['m_dt']} % / {n['m_mdt']} %"
    return line


def advice(n, focus):
    """A line from the guides."""
    tips = []
    if focus in ('Melee (fights)', 'Ranged (Sharpshot)', 'You and the pet', 'You and the pet, accuracy', 'Light tank') and n['gear_haste'] < GEAR_HASTE_CAP:
        tips.append(f"pet gear haste {n['gear_haste']} %: guides say get it to {GEAR_HASTE_CAP} first (magic haste comes from attachments)")
    if n['haste_over']:
        tips.append(f"{n['haste_over']} % pet haste is over the cap")
    if focus == 'Tank' and n.get('dt', 0) + n.get('pdt', 0) < TANK_DT:
        tips.append(f"pet physical damage taken {n.get('dt', 0) + n.get('pdt', 0)} % from gear: about {TANK_DT} % caps it with Armor Plate IV, Optic Fiber and a Light Maneuver (Harlequin 6 more, Stormwaker 12 more)")
    return '; '.join(tips)


NOTE = "the Doctor can't see your frame, head or attachments: pick what the set is for if its name doesn't say"


def judge(path, set_gear, job, sub, cands, counts, items, data, need=None, focus=None, build=True):
    """One automaton set, the same shape as idle.judge. Weapons and the animator stay as they are: they're what makes the pet."""
    focus = focus or focus_for(path)
    cur = healing.set_to_gear(set_gear, items, data)
    pool = [c for c in cands if any(k.startswith(('pet_', 'm_')) for k in c['stats']) or (focus in BOTH and any(c['stats'].get(k) for k in ('dt', 'pdt', 'mdt', 'dt2', 'pdt2', 'mdt2')))]
    notes = [f'judged for: {focus}', NOTE]
    n0 = numbers(cur)
    if focus in BOTH and not need:                           # (his numbers, or at least what the set has now: like a TP set)
        need = {k: v for k, v in (('pdt', n0['m_dt']), ('mdt', n0['m_mdt'])) if v}
        if need:
            notes.append(f"your damage taken kept as it is now ({n0['m_dt']} % / {n0['m_mdt']} %)")
    v0 = value(cur, focus)
    out = {'cur': cur, 'best': cur, 'now': v0, 'val': v0, 'n_now': n0, 'n_best': n0, 'changes': {}, 'focus': focus, 'keep': True, 'notes': notes, 'short': 0}
    if build:
        best, val, now = healing.build('pet', pool, cur, {}, job, sub, spell=focus, need=need or None, keep_weapons=True, counts=counts)
        out.update(best=best, val=val, now=now, n_best=numbers(best), changes=healing.changes(cur, best, True), short=healing.shortfall(healing.totals(best), need or None))
    return out


def checked_sets(loaded, limit=8):
    """The automaton sets a check-up looks at, plainest first."""
    paths = [s for s in loaded.sets if is_pet_set(s['path'])]
    paths.sort(key=lambda s: (s['path'].count('.'), len(s['path'])))
    return paths[:limit]
