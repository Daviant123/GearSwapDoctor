"""
GearSwap Doctor: healing sets (his request 2026-10-30: "do research, and figure out how to add in a features for healing
and making healing sets. make sure to do research"). wsdist knows nothing about healing (not one cure stat in its gear
list), so this has the game's healing formulas itself and reads the stats from Windower's res\\item_descriptions.lua.

Formulas and caps: RESEARCH.md, "Healing" (BG-Wiki Cure Formula, Cure Potency, Waltz, Cursna, Afflatus Solace pages).
  Cure I-VI     Power = floor(MND/2) + floor(VIT/4) + Healing Magic skill; a table of tiers per spell
  Curaga I-V    Power = 3 MND + VIT + 3 floor(skill/5); all of them top out at floor(Power/2) = 620
  every cure    floor(floor(floor((Base + JP + "Cure"+n) x (1 + potency + potency II)) x (1 + received)) x (1 + day/weather))
                potency caps at 50 %, potency II at 30 %, received at 30 %, day/weather at 35 %
  Waltz         floor((1 + potency + received) x floor(M (CHR + target's VIT) + B + 2 JP)), caps 50 % / 30 %, M halved /DNC
  Cursna        (10 + skill/30) x (1 + Cursna/100)
  Fast cast     Fast Cast + cure casting time share one cap of 80 %

  KINDS               what a healing set is for, what it's judged by
  item_stats(...)     one item's healing stats (its text + the augments he has on it in his files)
  evaluate(...)       a set's totals and the number it's judged by
  build(...)          the best set from his gear (swaps one or two pieces at a time until nothing helps; always the same
                      answer for the same gear), with what it must also have (enmity, damage taken ...)
  find_sets(...)      which sets of a file are healing sets, what kind; missing_sets(...)  what this job should have
"""
import math
import os
import re

import checks

SLOTS = ['main', 'sub', 'ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']
PAIR = {'ear1': 'ear2', 'ear2': 'ear1', 'ring1': 'ring2', 'ring2': 'ring1'}
GS_KEY = {'left_ear': 'ear1', 'lear': 'ear1', 'right_ear': 'ear2', 'rear': 'ear2', 'left_ring': 'ring1', 'lring': 'ring1',
          'right_ring': 'ring2', 'rring': 'ring2', 'ranged': 'range'}

# Power floor / rate / HP floor of each tier, the Power where it stops, the most it heals (BG-Wiki Cure Formula; checked:
# each tier ends exactly where the next one starts)
CURE = {
    'Cure': ([(0, 4, 10), (20, 1.33, 15), (40, 8.5, 30), (125, 15, 40), (200, 20, 45)], 600, 65),
    'Cure II': ([(40, 1, 60), (70, 5.5, 90), (125, 7.5, 100), (200, 10, 110), (400, 20, 130)], 700, 145),
    'Cure III': ([(70, 2.2, 130), (125, 1.15, 155), (200, 2.5, 220), (300, 5, 260)], 700, 340),
    'Cure IV': ([(70, 1, 270), (200, 2, 400), (300, 1.43, 450), (400, 2.5, 520)], 700, 640),
    'Cure V': ([(80, 0.7, 450), (150, 1.25, 550), (190, 1.84, 582), (260, 2, 620), (300, 2.5, 640), (500, 3.33, 720)], 700, 780),
    'Cure VI': ([(90, 1.5, 600), (210, 0.9, 680), (300, 1.43, 780), (400, 2.5, 850), (500, 1.67, 890)], 700, 1010),
}
# floor(Power/2) where a band starts, rate, const; lowest and highest result. (The wiki's table is one flat row per spell:
# its bands fit together exactly and all end at floor(Power/2) = 620. Curaga V's low end is marked "information needed".)
CURAGA = {
    'Curaga': ([(40, 1, 20), (55, 2, 47.5), (85, 35.66, 87.62)], 60, 105),
    'Curaga II': ([(60, 1, 70), (90, 2, 115), (150, 15.66, 180.43)], 130, 220),
    'Curaga III': ([(70, 0.6666, 165), (110, 2, 275), (230, 6.5, 354.66)], 270, 450),
    'Curaga IV': ([(80, 0.6666, 330), (160, 1, 410), (280, 2.833, 591.2)], 450, 810),
    'Curaga V': ([(0, 1, 570), (160, 1.278, 655)], 570, 1140),
}
WALTZ = {'Curing Waltz': (0.25, 60), 'Curing Waltz II': (0.5, 130), 'Curing Waltz III': (0.75, 270), 'Curing Waltz IV': (1.0, 450),
         'Curing Waltz V': (1.25, 600), 'Divine Waltz': (0.25, 60), 'Divine Waltz II': (0.5, 280)}

CAP_POTENCY, CAP_POTENCY2, CAP_RECEIVED, CAP_DAYWX, CAP_CAST, CAP_ENMITY = 50, 30, 30, 35, 80, 50
CAP_WALTZ, CAP_WALTZ_RECEIVED, CAP_QUICK, CAP_DT = 50, 30, 10, 50
SOLACE_CAP = 300

DAYWX = {'No day or weather bonus': 0, 'Lightsday (+10)': 10, 'Light weather (+10)': 10, 'Lightsday + Light weather (+20)': 20,
         'Double Light weather (+25)': 25, 'Lightsday + double Light weather (+35)': 35}
WITHOUT_OBI = 1 / 3         # no Hachirin-no-Obi: the bonus only happens sometimes (a chance; the usual figure is about a third)

# the kinds of healing set: what it's for, how it's judged, the spells to pick from
KINDS = {
    'cure': {'title': 'Cure (single target)', 'spells': ['Cure IV', 'Cure V', 'Cure VI', 'Cure III', 'Cure II', 'Cure'], 'unit': 'HP',
             'how': 'HP healed by the spell: potency up to 50 %, potency II up to 30 %, then skill (1 for 1), MND and VIT. Ties: less '
                    'enmity, Conserve MP, haste.'},
    'curaga': {'title': 'Curaga', 'spells': ['Curaga IV', 'Curaga V', 'Curaga III', 'Curaga II', 'Curaga'], 'unit': 'HP',
               'how': 'HP healed: potency and potency II first, then MND (worth 3 VIT or 15 skill). Curagas give no Solace stoneskin.'},
    'selfcure': {'title': 'Cure on yourself', 'spells': ['Cure IV', 'Cure V', 'Cure VI', 'Cure III'], 'unit': 'HP',
                 'how': 'HP healed when you cure yourself: as Cure, and "Cure potency received" counts too (up to 30 %).'},
    'received': {'title': 'Being cured (tanks)', 'spells': [], 'unit': '%',
                 'how': 'Cure potency received, up to 30 %. Worn while others cure you. Ties: damage taken, HP.'},
    'precast': {'title': 'Fast cast for cures', 'spells': [], 'unit': '%',
                'how': 'Fast Cast + cure / healing casting time, one cap of 80 %. Then Quick Magic (up to 10 %), then HP and MP. Gear past '
                       'the cap does nothing.'},
    'cursna': {'title': 'Cursna', 'spells': [], 'unit': '%',
               'how': 'Chance to remove Doom: (10 + skill / 30) x (1 + Cursna gear / 100). "Verification needed" on the wiki: good for '
                      'comparing sets.'},
    'regen': {'title': 'Regen', 'spells': [], 'unit': '',
              'how': 'Regen potency first, then Regen duration, then enhancing haste. The exact HP per tick is not well known.'},
    'waltz': {'title': 'Waltz', 'spells': ['Curing Waltz IV', 'Curing Waltz V', 'Curing Waltz III', 'Curing Waltz II', 'Curing Waltz',
                                           'Divine Waltz II', 'Divine Waltz'], 'unit': 'HP',
              'how': 'HP healed: Waltz potency up to 50 %, then your CHR. The target\'s VIT counts too. Half as much from CHR on a /DNC.'},
}

# "Enhances Cursna effect" items don't say how much (BG-Wiki Cursna, some values from the 2013 guide)
CURSNA_VALUE = {'hieros mittens': 10, 'malison medallion': 10, 'debilis medallion': 15, 'ephedra ring': 10, "haoma's ring": 15,
                'mending cape': 15}
STAT_RX = [
    ('potency', r'"?Cure"? potency ?\+(\d+)'), ('potency2', r'"?Cure"? potency II ?\+(\d+)'),
    ('received', r'Potency of "Cure" effects? received \+(\d+)'), ('cure_flat', r'"Cure" ?\+(\d+)(?!\s*%)'),
    ('cure_cast', r'"?Cure"? (?:spell)?casting time ?-(\d+)'), ('heal_cast', r'Healing magic casting time ?-(\d+)'),
    ('skill', r'Healing magic skill ?\+(\d+)'), ('MND', r'\bMND ?\+(\d+)'), ('VIT', r'\bVIT ?\+(\d+)'), ('CHR', r'\bCHR ?\+(\d+)'),
    ('HP', r'(?<![A-Za-z"])HP ?\+(\d+)(?![\d%])'), ('MP', r'(?<![A-Za-z"])MP ?\+(\d+)(?![\d%])'), ('fast', r'"Fast Cast" ?\+(\d+)'),
    ('quick', r'(?:Occ\. quickens spellcasting|"?Quick Magic"?) ?\+(\d+)'), ('conserve', r'"Conserve MP" ?\+(\d+)'),
    ('haste', r'\bHaste ?\+(\d+)'), ('pdt', r'(?:Physical [Dd]amage taken|Phys\. dmg\. taken|\bPDT) ?-(\d+)'),
    ('mdt', r'(?:Magic [Dd]amage taken|Magic dmg\. taken|Mag\. dmg\. taken|\bMDT) ?-(\d+)'),
    ('dt', r'(?<![A-Za-z.] )(?:Damage taken|Dmg\. taken|\bDT) ?-(\d+)'),
    # (the II kinds go past the 50 % cap)
    ('pdt2', r'Physical [Dd]amage taken II ?-(\d+)'), ('mdt2', r'Magic [Dd]amage taken II ?-(\d+)'), ('dt2', r'(?<![A-Za-z.] )Damage taken II ?-(\d+)'),
    # idle sets (idle.py)
    ('refresh', r'(?:"Refresh"|\bRefresh) ?\+(\d+)'), ('regen', r'(?:"Regen"|\bRegen) ?\+(\d+)'), ('meva', r'Magic Evasion ?\+(\d+)'),
    ('mdb', r'"Magic Def\.? Bonus" ?\+(\d+)'), ('move', r'Movement speed ?\+(\d+)'), ('waltz', r'"?Waltz"? potency ?\+(\d+)'),
    ('waltz_received', r'(?:"Waltz" potency received|Potency of "Waltz" effects received) ?\+(\d+)'), ('cursna', r'"Cursna" ?\+(\d+)'),
    ('regen_potency', r'"Regen" potency ?\+(\d+)'), ('regen_duration', r'"Regen" (?:effect )?duration ?\+(\d+)'),
    ('solace', r'"Afflatus Solace" ?\+(\d+)'), ('sird', r'[Ss]pell interruption rate (?:down )?-?(\d+)'),
]
STAT_RX = [(k, re.compile(rx)) for k, rx in STAT_RX]
ENMITY_RX = re.compile(r'Enmity ?([+\-]\d+)')
# what doesn't count: a set bonus, Unity, a latent effect, a pet's or a place's bonus
CUT_RX = re.compile(r'(?:\bSet:|Unity Ranking:|Latent effect|Pet:|Avatar:|Wyvern:|Automaton:|Enchantment:|Reives:|Campaign:|Assault:|'
                    r'Salvage:|Dynamis[^:]{0,20}:|Besieged:|Nighttime:|Daytime:|Dusk[^:]{0,12}:|Dawn[^:]{0,12}:|\bOn [A-Za-z]+:)')

MP_RX = re.compile(r'"Cure" MP consumed \+(\d+)')


def parse_text(text):
    """{stat: value} from an item's description or one augment."""
    m = CUT_RX.search(text)
    if m:
        text = text[:m.start()]
    out = {}
    for k, rx in STAT_RX:
        n = sum(int(x) for x in rx.findall(text))
        if n:
            out[k] = n
    n = sum(int(x) for x in ENMITY_RX.findall(text))
    if n:
        out['enmity'] = n
    # (no number in the text: Stikini Ring and the like give 1; plain movement speed gear is the old 12 %)
    for word, key in (('Refresh', 'refresh'), ('Regen', 'regen')):
        if f'Adds "{word}" effect' in text:
            out[key] = out.get(key, 0) + 1
    if 'Increases movement speed' in text and 'move' not in out:
        out['move'] = 12
    if 'Decreases movement speed' in text or 'Reduces movement speed' in text:
        out['slowed'] = 12
    if 'Enhances "Cursna" effect' in text and 'cursna' not in out:
        out['cursna_unknown'] = 1
    return out


def add(a, b):
    for k, v in b.items():
        a[k] = a.get(k, 0) + v
    return a


# "All magic skills +8" (Stikini Ring), "Magic skills +10" (Incanter's Torque): every magic skill at once, so no single skill's words match it
ALL_SKILLS_RX = re.compile(r'(?:All magic|(?<![a-z] )Magic) skills ?\+(\d+)')
MAGIC_SKILLS = ('skill', 'enh_skill', 'enf_skill', 'dark_skill', 'div_skill', 'ele_skill', 'nin_skill', 'blue_skill', 'sing', 'instr', 'geo_skill', 'bell', 'smn_skill')


def all_skills(text):
    """{every magic skill: n} for a text that raises them all."""
    m = CUT_RX.search(text or '')
    n = sum(int(x) for x in ALL_SKILLS_RX.findall((text or '')[:m.start()] if m else (text or '')))
    return {k: n for k in MAGIC_SKILLS} if n else {}


class ItemData:
    """Every item's text and its kind of weapon (Windower's res folder; read once)."""
    def __init__(self, res_folder=None):
        res = res_folder or os.path.join(checks.WINDOWER, 'res')
        self.text, self.info = {}, {}
        rx = re.compile(r'\s*\[(\d+)\] = \{id=\d+,en="((?:[^"\\]|\\.)*)"')
        for line in open(os.path.join(res, 'item_descriptions.lua'), encoding='utf-8'):
            m = rx.match(line)
            if m:
                self.text[int(m.group(1))] = m.group(2).replace('\\n', ' ').replace('\\"', '"')
        rx2 = re.compile(r'\s*\[(\d+)\] = \{')
        for line in open(os.path.join(res, 'items.lua'), encoding='utf-8'):
            m = rx2.match(line)
            if not m or 'slots=' not in line:
                continue
            sk = re.search(r'\bskill=(\d+)', line)
            self.info[int(m.group(1))] = {'skill': int(sk.group(1)) if sk else None, 'shield': 'shield_size=' in line}


TWO_HANDED = {4, 6, 7, 8, 10, 12}       # great sword, great axe, scythe, polearm, great katana, staff


def candidate(it, data, augments=None):
    """An item as the set builder sees it."""
    st = parse_text(data.text.get(it['id'], ''))
    if 'cursna_unknown' in st:
        n = CURSNA_VALUE.get(it['en'].lower()) or CURSNA_VALUE.get(it['enl'].lower()) or 10
        st.pop('cursna_unknown')
        st['cursna'] = st.get('cursna', 0) + n
    import gs_create
    import pld
    import pup
    add(st, pup.parse(data.text.get(it['id'], '')))         # (what it gives a pet)
    add(st, gs_create.parse(data.text.get(it['id'], '')))   # (the rest a new file's sets ask for)
    add(st, pld.parse(data.text.get(it['id'], '')))         # (a tank's: Phalanx, enmity kept when hit ...)
    import job_sets
    add(st, job_sets.parse(data.text.get(it['id'], '')))    # (every job's sets: rolls, casting times, Stoneskin ...)
    add(st, all_skills(data.text.get(it['id'], '')))
    if it['en'].lower() in job_sets.FAST_NAMED and st.get('fast') == 2:
        st['fast'] = job_sets.FAST_NAMED[it['en'].lower()]
    quoted = job_sets.quoted(data.text.get(it['id'], ''))   # (the abilities its text names: "Chain Affinity"+24, Enhances "Diffusion" effect)
    for a in augments or []:
        add(st, parse_text(str(a)))
        add(st, pup.parse(str(a)))
        add(st, gs_create.parse(str(a)))
        add(st, pld.parse(str(a)))
        add(st, job_sets.parse(str(a)))
        add(st, all_skills(str(a)))
        for k, v in job_sets.quoted(str(a)).items():
            quoted[k] = max(quoted.get(k, 0), v)
    info = data.info.get(it['id'], {})
    text = data.text.get(it['id'], '')
    import hidden
    for k, v in hidden.named(text, it['en']).items():       # (a number the text hides: Carnwenhan's song duration ...)
        st.setdefault(k, v)
    # (a JSE earring whose stats are all "Right ear:": nothing in the left ear, so it only goes in the right)
    side = 'ear2' if text.startswith('Right ear:') else 'ear1' if text.startswith('Left ear:') else None
    return {'name': it['en'], 'enl': it['enl'], 'id': it['id'], 'augments': list(augments or []), 'stats': st, 'slots': it['slots'], 'side': side, 'quoted': quoted,
            'blocks': blocked_slots(text),
            'set': hidden.family(text, it['en']),
            'skill': info.get('skill'), 'shield': info.get('shield', False),
            'two_handed': info.get('skill') in TWO_HANDED and bool(it['slots'] & 1)}


def fits(c, slot):
    if c.get('side') and slot in ('ear1', 'ear2') and slot != c['side']:
        return False
    return any(c['slots'] & (1 << b) for b in checks.SLOT_BITS.get(slot, []))


def known_augments(loaded_list):
    """{item name (lower): [augment lists]} - every way his GearSwap files name an augmented item. (His bags only say he
    owns it; the augments on it are only known from the files.)"""
    out = {}
    for ld in loaded_list:
        for s in ld.sets:
            for g in s['gear'].values():
                a = list(g.get('augments') or [])
                if a:
                    v = out.setdefault(g['name'].lower(), [])
                    if a not in v:
                        v.append(a)
    return out


def candidates(owned_items, data, augs=None, real=None):
    """Every owned item, once per augmented copy. real: {item id: [augment lists]} read from his bags (checks.load_augments): the gear as it
    really is; an item not in it uses what his files name (augs), as before."""
    out = []
    for it in owned_items:
        seen = (real or {}).get(it['id'])
        variants = seen or (augs or {}).get(it['en'].lower()) or (augs or {}).get(it['enl'].lower()) or [None]
        for a in variants:
            c = candidate(it, data, a)
            if seen:                    # (read from the bags: 'copies' = how many different copies of it he has)
                c['real'], c['copies'] = True, len(seen)
            out.append(c)
    return out


# ------------------------------------------------------------------ the numbers
def base_cure(spell, power):
    tiers, upper, cap = CURE[spell]
    p = min(power, upper)
    floor_, rate, hp = tiers[0]
    for t in tiers:
        if p >= t[0]:
            floor_, rate, hp = t
    return min(cap, math.floor(max(0, p - floor_) / rate) + hp)


def base_curaga(spell, power):
    bands, low, high = CURAGA[spell]
    half = math.floor(power / 2)
    rate, const = bands[0][1], bands[0][2]
    for start, r, c in bands:
        if half >= start:
            rate, const = r, c
    return max(low, min(high, math.floor(half / rate + const)))


def job_base(job, sub):
    """(MND, VIT, CHR) with no gear - wsdist's table of each job at 99, else a middling guess. He can change them."""
    try:
        import wsdist_runner as W
        mods = W._wsdist()
        empty = mods['gear'].Empty
        cwd = os.getcwd()
        os.chdir(W.WS_DIR)
        try:
            p = mods['create_player'].create_player(job.lower(), sub.lower(), 20, gearset={s: empty for s in W.SLOT_MAP.values()},
                                                    buffs={}, abilities={'Enemy Resist Rank': 0, '99999': False, 'Aftermath': 0,
                                                                         'Storm spell': 'None', 'Enhancing Skill': 0,
                                                                         'Verbose Swaps': False})
        finally:
            os.chdir(cwd)
        return int(p.stats.get('MND', 90)), int(p.stats.get('VIT', 90)), int(p.stats.get('CHR', 90))
    except Exception:
        return 95, 90, 90


# Healing Magic skill with no gear, at 99 (BG-Wiki); WHM with its job gifts. As a sub job: the level 49 numbers.
SKILL_MAIN = {'WHM': 450, 'PLD': 373, 'RDM': 368, 'SCH': 404}
SKILL_SUB = {'WHM': 150, 'PLD': 139, 'RDM': 139, 'SCH': 144}
FAST_MAIN = {'RDM': 38, 'BLU': 0}
FAST_SUB = {'RDM': 15}


def defaults(job, sub):
    mnd, vit, chr_ = job_base(job, sub)
    return {'MND': mnd, 'VIT': vit, 'CHR': chr_, 'skill': max(SKILL_MAIN.get(job, 0), SKILL_SUB.get(sub, 0)), 'jp': 0,
            'waltz_jp': 0, 'target_vit': 130, 'fast': max(FAST_MAIN.get(job, 0), FAST_SUB.get(sub, 0)), 'daywx': 0,
            'sub_dnc': sub == 'DNC' and job != 'DNC', 'cure_merit': 0}


def totals(gear):
    """The stats of a set: {slot: candidate}, with the set bonuses its pieces give together (hidden.py: the Kaykaus set's "Enhances Cure potency II",
    4-10 %: 2 per piece; artifact armor's accuracy; Souveran's damage taken ...)."""
    t = {}
    sets = False
    for c in gear.values():
        if c:
            add(t, c['stats'])
            sets = sets or bool(c.get('set'))
    if sets:
        import hidden
        b = hidden.bonus(gear)
        if b:
            add(t, b)
            if b.get('potency2'):
                t['set_bonus'] = b['potency2']
    return t


def _has_obi(gear):
    w = gear.get('waist')
    return bool(w) and w['name'].lower() == 'hachirin-no-obi'


def healed(spell, t, base, daywx=0, obi=False, self_cast=False):
    """HP healed by a cure with these totals."""
    mnd, vit, skill = base['MND'] + t.get('MND', 0), base['VIT'] + t.get('VIT', 0), base['skill'] + t.get('skill', 0)
    if spell in CURAGA:
        b = base_curaga(spell, 3 * mnd + vit + 3 * math.floor(skill / 5))
    else:
        b = base_cure(spell, math.floor(mnd / 2) + math.floor(vit / 4) + skill)
    eq = 1 + min(CAP_POTENCY, t.get('potency', 0)) / 100 + min(CAP_POTENCY2, t.get('potency2', 0)) / 100
    rec = 1 + (min(CAP_RECEIVED, t.get('received', 0)) / 100 if self_cast else 0)
    d = min(CAP_DAYWX, daywx) / 100
    if not obi:
        d *= WITHOUT_OBI
    return math.floor(math.floor(math.floor((b + base.get('jp', 0) + t.get('cure_flat', 0)) * eq) * rec) * (1 + d))


def stoneskin(potential, t):
    """Afflatus Solace: min(25 % of what the cure could heal, 300) + the gear's % of it."""
    return min(math.floor(0.25 * potential), SOLACE_CAP) + math.floor(t.get('solace', 0) / 100 * potential)


def waltz(spell, t, base):
    m, b = WALTZ[spell]
    if base.get('sub_dnc'):
        m /= 2
    chr_ = base['CHR'] + t.get('CHR', 0)
    eq = 1 + min(CAP_WALTZ, t.get('waltz', 0)) / 100
    return math.floor(eq * math.floor(m * (chr_ + base.get('target_vit', 130)) + b + 2 * base.get('waltz_jp', 0)))


def cursna_rate(t, base):
    return min(100.0, (10 + (base['skill'] + t.get('skill', 0)) / 30) * (1 + t.get('cursna', 0) / 100))


def dt_totals(t):
    """(physical, magic) damage taken of the set, as positive "% less", capped."""
    return (min(CAP_DT, t.get('dt', 0) + t.get('pdt', 0)) + t.get('pdt2', 0) + t.get('dt2', 0),
            min(CAP_DT, t.get('dt', 0) + t.get('mdt', 0)) + t.get('mdt2', 0) + t.get('dt2', 0))


def cast_total(t, base, cures=True):
    n = base.get('fast', 0) + t.get('fast', 0)
    if cures:
        n += t.get('cure_cast', 0) + t.get('heal_cast', 0) + base.get('cure_merit', 0)
    return n


def evaluate(kind, gear, base, spell=None, solace=False):
    """(the number the set is judged by, its totals). gear: {slot: candidate}."""
    t = totals(gear)
    if kind in ('cure', 'selfcure', 'curaga'):
        spell = spell or KINDS[kind]['spells'][0]
        v = healed(spell, t, base, base.get('daywx', 0), _has_obi(gear), self_cast=kind == 'selfcure')
    elif kind == 'waltz':
        v = waltz(spell or 'Curing Waltz IV', t, base)
    elif kind == 'received':
        v = min(CAP_RECEIVED, t.get('received', 0))
    elif kind == 'precast':
        v = min(CAP_CAST, cast_total(t, base))
    elif kind == 'cursna':
        v = round(cursna_rate(t, base), 1)
    elif kind == 'regen':
        v = t.get('regen_potency', 0) + t.get('regen_duration', 0) / 100
    elif kind == 'idle':
        import idle
        v = idle.value(gear, spell, base)
    elif kind == 'pet':
        import pup
        v = pup.value(gear, spell)
    elif kind == 'points':
        import gs_create
        v = gs_create.value(gear, spell)
    elif kind == 'pld':
        import pld
        v = pld.value(gear, spell)
    elif kind == 'jobset':
        import job_sets
        v = job_sets.value(gear, spell)
    else:
        raise ValueError(kind)
    return v, t


def _ties(kind, t, base):
    """A little for the things that don't change the main number (never enough to outweigh it)."""
    pd, md = dt_totals(t)
    en = min(CAP_ENMITY, -min(0, t.get('enmity', 0)))
    if kind in ('cure', 'curaga', 'selfcure'):
        return 0.02 * en + 0.01 * t.get('conserve', 0) + 0.005 * min(26, t.get('haste', 0)) + 0.002 * (pd + md) + 0.0002 * t.get('MP', 0)
    if kind == 'received':
        return 0.02 * (pd + md) + 0.001 * t.get('HP', 0)
    if kind == 'precast':
        return 0.3 * min(CAP_QUICK, t.get('quick', 0)) + 0.0005 * (t.get('HP', 0) + t.get('MP', 0))
    if kind == 'cursna':
        return 0.02 * en + 0.001 * t.get('skill', 0) + 0.0002 * t.get('MP', 0)
    if kind == 'regen':
        return 0.002 * min(26, t.get('haste', 0)) + 0.001 * t.get('conserve', 0)
    if kind == 'waltz':
        return 0.002 * (pd + md) + 0.005 * t.get('HP', 0) * 0.1
    return 0


def shortfall(t, need):
    """How far a set is below what it must also have (0 = it has it all)."""
    if not need:
        return 0
    pd, md = dt_totals(t)
    n = 0
    dt = need.get('dt', 0)
    n += max(0, max(dt, need.get('pdt', 0)) - pd) + max(0, max(dt, need.get('mdt', 0)) - md)
    if need.get('enmity'):                                  # (less enmity asked for; enmity+ gear isn't "short" of anything otherwise)
        n += max(0, need['enmity'] - (-t.get('enmity', 0)))
    n += max(0, need.get('sird', 0) - t.get('sird', 0))
    n += max(0, need.get('conserve', 0) - t.get('conserve', 0))
    return n


def _need_value(st, need):
    n = 0
    if need.get('dt') or need.get('pdt'):
        n += st.get('dt', 0) + st.get('pdt', 0)
    if need.get('dt') or need.get('mdt'):
        n += st.get('dt', 0) + st.get('mdt', 0)
    if need.get('enmity'):
        n -= min(0, st.get('enmity', 0))
    if need.get('sird'):
        n += st.get('sird', 0)
    if need.get('conserve'):
        n += st.get('conserve', 0)
    return n


def score(kind, gear, base, spell, need, solace=False):
    v, t = evaluate(kind, gear, base, spell)
    s = float(v) + _ties(kind, t, base)
    if solace and kind in ('cure',):
        pot = healed(spell or 'Cure IV', t, base, 0, True)
        s += 0.5 * stoneskin(pot, t)                  # (a stoneskin point is worth half an HP healed)
    return s - 1000 * shortfall(t, need)


BLOCK_RX = re.compile(r'cannot equip (headgear|handgear|leggear|footgear|hand or footgear|hand)', re.I)
BLOCK_SLOTS = {'headgear': ('head',), 'handgear': ('hands',), 'hand': ('hands',), 'leggear': ('legs',), 'footgear': ('feet',), 'hand or footgear': ('hands', 'feet')}


def blocked_slots(text):
    """The slots a piece leaves no room for (his report 2026-11-14: "crepuscular cloak and sakpata's helm can't be equipped at the same time"): a
    cloak's text says "Cannot equip headgear", some suits hand / leg / foot gear."""
    out = set()
    for m in BLOCK_RX.findall(text or ''):
        out |= set(BLOCK_SLOTS[m.lower()])
    return tuple(sorted(out))


def clash(gear, slot, c):
    """The piece that can't be worn together with c in this slot, or None: c covers a slot that is filled, or a worn piece covers c's slot."""
    if c is None:
        return None
    for b in c.get('blocks') or ():
        if b != slot and gear.get(b):
            return gear[b]
    for s, x in gear.items():
        if x and s != slot and slot in (x.get('blocks') or ()):
            return x
    return None


def uncovered(gear):
    """The set without the pieces another piece leaves no room for (the head under a cloak)."""
    covered = {b for c in gear.values() if c for b in (c.get('blocks') or ())}
    return {s: c for s, c in gear.items() if not (c and s in covered)}


def covered_pairs(gear):
    """[(the piece that covers, the slot, the piece that can't be worn)] in a set."""
    return [(c['name'], b, gear[b]['name']) for c in gear.values() if c for b in (c.get('blocks') or ()) if gear.get(b)]


def _allowed(gear, slot, c, counts, job, sub):
    """May this item go in this slot, with the rest of the set as it is?"""
    if c is not None and not fits(c, slot):
        return False
    if clash(gear, slot, c):
        return False
    if c is not None:
        used = sum(1 for s, x in gear.items() if s != slot and x and x['name'] == c['name'])
        if used + 1 > counts.get(c['name'], 1):
            return False
    if slot not in ('main', 'sub'):          # (only a weapon change can make the weapons wrong: a set with a grip and no weapon can still change its earrings)
        return True
    other = dict(gear)
    other[slot] = c
    m, s_ = other.get('main'), other.get('sub')
    if s_ is None or m is None:
        return not (s_ is not None and m is None and not s_['shield'])
    grip = not s_['shield'] and s_.get('skill') == 0
    if m['two_handed']:
        return grip
    if grip:
        return False
    if s_['shield']:
        return True
    return job in ('NIN', 'DNC', 'THF', 'BLU') or sub in ('NIN', 'DNC')        # a second weapon: dual wield only


def build(kind, cands, current, base, job, sub, spell=None, need=None, keep_weapons=False, solace=False, counts=None, only_slots=None):
    """The best set. cands: [candidate]; current: {slot: candidate}. Returns (best {slot: candidate}, best number, the
    number of the set now). Starts from the set as it is and from nothing; one swap at a time, then two together when
    one alone doesn't help; then a wider look from more starting points (whole set-bonus families, each slot's own best)."""
    counts = counts or {}
    import job_rules
    no_ammo = job_rules.lock_ammo(job)                      # (a COR's or RNG's gun comes off with the wrong ammo)
    slots = [s for s in SLOTS if not (keep_weapons and s in ('main', 'sub')) and not (no_ammo and s == 'ammo') and (only_slots is None or s in only_slots)]
    per_slot = {}
    for s in slots:
        seen, opts = set(), [None]
        for c in cands:
            key = (c['name'], tuple(c['augments']))
            if key not in seen and fits(c, s):
                seen.add(key)
                opts.append(c)
        if current.get(s) and (current[s]['name'], tuple(current[s]['augments'])) not in seen:
            opts.append(current[s])
        per_slot[s] = opts
    fixed = {s: current.get(s) for s in ('main', 'sub')} if keep_weapons else {}
    if only_slots is not None:                              # (the rest of the set stays as it is: a set worn on top of others)
        fixed.update({s: current.get(s) for s in SLOTS if s not in slots and current.get(s)})
    if no_ammo:
        fixed['ammo'] = current.get('ammo')
    # (a set that has a cloak and a helm: in game the cloak wins and the helm stays off, so the search starts without the covered piece)
    current = uncovered(current)
    fixed = uncovered(fixed)
    best_set, best_s = None, None
    starts = [dict(current), dict(fixed)]
    if need:                                                # (also from the gear with the most of what the set must have)
        g = dict(fixed)
        for s in slots:
            opts = [c for c in per_slot[s] if c and _allowed(g, s, c, counts, job, sub)]
            if opts:
                pick = max(opts, key=lambda c: _need_value(c['stats'], need))
                if _need_value(pick['stats'], need) > 0:
                    g[s] = pick
        starts.append(g)
    def climb(g, pairs=True):
        """Swap one piece at a time while that helps; then (pairs) two together; until nothing does."""
        g = dict(g)
        cur_s = score(kind, g, base, spell, need, solace)
        for _ in range(60):
            improved = False
            for s in slots:                                 # one piece
                for c in per_slot[s]:
                    if c is g.get(s) or not _allowed(g, s, c, counts, job, sub):
                        continue
                    t = dict(g)
                    t[s] = c
                    sc = score(kind, t, base, spell, need, solace)
                    if sc > cur_s + 1e-9:
                        g, cur_s, improved = t, sc, True
            if improved:
                continue
            if not pairs:
                break
            for i, s1 in enumerate(slots):                  # two pieces together
                for s2 in slots[i + 1:]:
                    for c1 in per_slot[s1]:
                        if not _allowed(g, s1, c1, counts, job, sub) and s1 not in ('main', 'sub'):
                            continue
                        t1 = dict(g)
                        t1[s1] = c1
                        for c2 in per_slot[s2]:
                            if not _allowed(t1, s2, c2, counts, job, sub):
                                continue
                            t = dict(t1)
                            t[s2] = c2
                            if s1 in ('main', 'sub') and not _allowed(t, s1, c1, counts, job, sub):
                                continue
                            sc = score(kind, t, base, spell, need, solace)
                            if sc > cur_s + 1e-9:
                                g, cur_s, improved = t, sc, True
                                t1 = dict(g)
                                t1[s1] = g.get(s1)
            if not improved:
                break
        return g, cur_s

    for start in starts:
        g, cur_s = climb(start)
        if best_s is None or cur_s > best_s:
            best_set, best_s = g, cur_s
    # A wider look (PLAN.md E2, 2026-11-14): one or two swaps can't reach a set bonus that only pays with three or more pieces, or a set that is
    # only better once several slots change together. So more starting points, each climbed one swap at a time (quick), and only one that ends
    # above the best so far gets the full climb. The same gear always gives the same answer: the starts are made in a fixed order.
    extra = []
    fam = {}
    for sl in slots:                                        # (a) every piece of a set he has two or more pieces of
        for c in per_slot[sl]:
            if c and c.get('set'):
                fam.setdefault(c['set'], {}).setdefault(sl, c)
    for k in sorted(fam, key=lambda k: (-len(fam[k]), k))[:4]:
        if len(fam[k]) >= 2:
            g = dict(best_set)
            for sl, c in fam[k].items():
                if _allowed(g, sl, c, counts, job, sub):
                    g[sl] = c
            extra.append(g)
    g = dict(fixed)                                         # (b) each slot's own best piece, picked on its own from nothing
    s0 = score(kind, g, base, spell, need, solace)
    for sl in slots:
        top, top_s = None, s0
        for c in per_slot[sl]:
            if c and _allowed(g, sl, c, counts, job, sub):
                t = dict(fixed)
                t[sl] = c
                sc = score(kind, t, base, spell, need, solace)
                if sc > top_s + 1e-9:
                    top, top_s = c, sc
        if top and _allowed(g, sl, top, counts, job, sub):
            g[sl] = top
    extra.append(g)
    for start in extra:
        g, cur_s = climb(start, pairs=False)
        if cur_s > best_s + 1e-9:
            g, cur_s = climb(g)
            best_set, best_s = g, cur_s
    best_set = _only_what_helps(kind, best_set, current, base, spell, need, solace, counts, job, sub, slots)
    best_set = {s: c for s, c in best_set.items() if c}
    now, _ = evaluate(kind, current, base, spell)
    val, _ = evaluate(kind, best_set, base, spell)
    return best_set, val, now


CARES_ABOUT_TIES = ('cure', 'curaga', 'selfcure')      # (at the cap: less enmity, Conserve MP are reasons to change a cure set)


def _only_what_helps(kind, best, current, base, spell, need, solace, counts, job, sub, slots):
    """Put back every piece of the set as it is that changes nothing that matters: no swaps for nothing. A cure set may change
    for enmity, Conserve MP and the like too (they're worth having when the HP is at its cap); the other kinds only for their
    main number (or what the set must also have)."""
    g = dict(best)
    for s in slots:
        a, b = current.get(s), g.get(s)
        if a is b or (a and b and a['name'] == b['name'] and a['augments'] == b['augments']) or not _allowed(g, s, a, counts, job, sub):
            continue
        t = dict(g)
        t[s] = a
        if kind in CARES_ABOUT_TIES:
            keep = score(kind, t, base, spell, need, solace) >= score(kind, g, base, spell, need, solace) - 1e-9
        else:
            v1, t1 = evaluate(kind, t, base, spell)
            v0, t0 = evaluate(kind, g, base, spell)
            keep = v1 >= v0 and shortfall(t1, need) <= shortfall(t0, need)
        if keep:
            g = t
    return g


def gs_name(c):
    """How the item goes in a GearSwap file: its name, or {name, augments} when his files tell one copy from another. A piece read from his bags
    (real) only gets its augments written when he has two different copies of it: with one copy the name is enough."""
    if c.get('real') and c.get('copies', 1) < 2:
        return c['name']
    if c.get('augments'):
        return {'name': c['name'], 'augments': list(c['augments'])}
    return c['name']


def changes(current, best, keep_weapons=False):
    """{gs slot: item} to put in the set (an item only moved between ear 1 / 2 or ring 1 / 2 isn't a change)."""
    out = {}
    same = lambda a, b: bool(a) == bool(b) and (not a or (a['name'] == b['name'] and a['augments'] == b['augments']))  # noqa: E731
    for s in SLOTS:
        if keep_weapons and s in ('main', 'sub'):
            continue
        a, b = current.get(s), best.get(s)
        if not same(a, b):
            out[s] = gs_name(b) if b else 'empty'
    for p, q in (('ear1', 'ear2'), ('ring1', 'ring2')):
        if same(current.get(p), best.get(q)) and same(current.get(q), best.get(p)):
            out.pop(p, None)
            out.pop(q, None)
    return out


def real_copy(item_id, augments, cands):
    """The copy in his bags a set's entry means (cands made with real=): the one with the same augments; else his only copy (the file's augments are
    old, or it names none); else the copy that shares the most augments, the first one when the file names none. None: no copy read from the bags."""
    mine = [c for c in cands or () if c.get('real') and c['id'] == item_id]
    if not mine:
        return None
    want = sorted(str(a) for a in augments or [])
    for c in mine:
        if sorted(str(a) for a in c['augments']) == want:
            return c
    if len(mine) == 1 or not want:
        return mine[0]
    return max(mine, key=lambda c: len(set(want) & {str(a) for a in c['augments']}))


def set_to_gear(gear_of_set, items, data, by_name=None, cands=None):
    """A set of a file ({key: {'name', 'augments'}}) as {slot: candidate}. Names that aren't items are left out. cands: his gear (candidates): a piece
    whose augments were read from his bags is taken as it really is, whatever the file says about its augments."""
    from gs_loader import SLOTS as GS_SLOTS
    out = {}
    for key, g in gear_of_set.items():
        slot = GS_SLOTS.get(str(key).lower())
        if slot not in SLOTS or str(g['name']).lower() in ('empty', 'none', ''):
            continue
        found = items.find(g['name'])
        if found:
            mine = None
            for f in found:
                mine = real_copy(f['id'], g.get('augments'), cands)
                if mine:
                    break
            out[slot] = mine or candidate(found[0], data, g.get('augments') or None)
    return out


# ------------------------------------------------------------------ which sets are healing sets
def kind_of(path):
    """(kind, its spell if the name says) for a set's path, or None. sets.midcast.Cure -> cure; sets.precast.FC.Cure -> precast;
    sets.Self_Healing -> selfcure; sets.Cure_Received -> received; sets.precast.Waltz -> waltz ..."""
    low = path.lower()
    if 'pet' in low or 'healing waltz' in low or 'bluemagic' in low:
        return None
    if 'idle' in low or 'extraregen' in low or 'hpcure' in low:
        return None
    if 'waltz' in low:
        return 'waltz', None
    if 'cursna' in low:
        return 'cursna', None
    if 'received' in low:
        return 'received', None
    if 'precast' in low and re.search(r'cur[ea]|healing', low):
        return 'precast', None
    if 'precast' in low:
        return None
    if 'regen' in low:
        return 'regen', None
    if 'curaga' in low:
        return 'curaga', None
    if re.search(r'self.?(heal|cure)|cure.?self', low):
        return 'selfcure', None
    if 'cure' in low or low.endswith('["healing magic"]') or low.endswith("['healing magic']"):
        return 'cure', None
    return None


def find_sets(loaded):
    out = []
    for s in loaded.sets:
        k = kind_of(s['path'])
        if k:
            out.append({'path': s['path'], 'kind': k[0], 'spell': k[1], 'gear': s['gear']})
    return sorted(out, key=lambda x: (list(KINDS).index(x['kind']), x['path'].count('.'), x['path']))


# which healing sets a job should have, and the name a new one gets
WANTED = {
    'WHM': ['cure', 'curaga', 'precast', 'cursna', 'regen'], 'SCH': ['cure', 'curaga', 'precast', 'regen'],
    'RDM': ['cure', 'precast'], 'PLD': ['cure', 'precast', 'received'], 'RUN': ['received'], 'DNC': ['waltz', 'received'],
}
WANTED_SUB = {'WHM': ['cure', 'precast'], 'RDM': ['cure', 'precast'], 'SCH': ['cure', 'precast'], 'DNC': ['waltz']}
NEW_PATH = {'cure': 'sets.midcast.Cure', 'curaga': 'sets.midcast.Curaga', 'selfcure': 'sets.midcast.CureSelf', 'received': 'sets.Cure_Received',
            'precast': 'sets.precast.FC.Cure', 'cursna': 'sets.midcast.Cursna', 'regen': 'sets.midcast.Regen', 'waltz': 'sets.precast.Waltz'}


def missing_sets(loaded, job, sub=None):
    have = {x['kind'] for x in find_sets(loaded)}
    want = list(WANTED.get(job, []))
    want += [k for k in WANTED_SUB.get(sub, []) if k not in want]
    return [k for k in want if k not in have]


def spell_for_set(kind, path, job, sub):
    """Which spell to judge a set by, to start with: the strongest this job has."""
    if kind == 'cure' or kind == 'selfcure':
        if job == 'WHM':
            return 'Cure VI'
        return 'Cure IV' if job in ('RDM', 'SCH', 'PLD') else 'Cure III'
    if kind == 'curaga':
        return 'Curaga V' if job == 'WHM' else 'Curaga III'
    if kind == 'waltz':
        return 'Curing Waltz V' if job == 'DNC' else 'Curing Waltz III'
    return None


def fmt_value(kind, v):
    if kind in ('cure', 'curaga', 'selfcure', 'waltz'):
        return f'{v} HP'
    if kind == 'regen':
        return f'potency +{int(v)}%, duration +{round((v - int(v)) * 100)}'
    return f'{v}%'


def short_note(kind, t, base):
    "What stands out about a set, in a few words, for the list."
    if kind in ('cure', 'curaga', 'selfcure'):
        n = t.get('potency', 0)
        return f'potency {n}% ({n - CAP_POTENCY} wasted)' if n > CAP_POTENCY else f'potency {n}% of {CAP_POTENCY}' \
            + (f', potency II {t["potency2"]}%' if t.get('potency2') else '')
    if kind == 'precast':
        n = cast_total(t, base)
        return f'{n}% ({n - CAP_CAST} wasted)' if n > CAP_CAST else f'{n}% of {CAP_CAST}'
    if kind == 'received':
        return f"{t.get('received', 0)}% of {CAP_RECEIVED}"
    if kind == 'waltz':
        return f"Waltz potency {t.get('waltz', 0)}% of {CAP_WALTZ}"
    if kind == 'cursna':
        return f"Cursna gear +{t.get('cursna', 0)}"
    return ''


MAGE_JOBS = ('WHM', 'SCH', 'BLM', 'GEO', 'SMN', 'BRD')


def hints(path, job):
    """What a set's name says about how to build it: sets.midcast.CureMelee keeps the weapons, .DT wants damage taken ..."""
    low = path.lower()
    h = {'keep_weapons': 'melee' in low or job not in MAGE_JOBS, 'solace': job == 'WHM' and 'curaga' not in low, 'daywx': 0, 'need': {}}
    if 'lightweather' in low:
        h['daywx'] = 10
    elif 'lightday' in low:
        h['daywx'] = 10
    if low.endswith('.dt') or '.dt.' in low:
        h['need']['dt'] = 30
    if 'sird' in low:
        h['need']['sird'] = 70
    return h


def power_note(kind, t, base, spell=None):
    """Past this Power, more skill / MND / VIT does nothing for this spell."""
    mnd, vit, skill = base['MND'] + t.get('MND', 0), base['VIT'] + t.get('VIT', 0), base['skill'] + t.get('skill', 0)
    if kind == 'curaga':
        p = 3 * mnd + vit + 3 * math.floor(skill / 5)
        return p, 1240
    p = math.floor(mnd / 2) + math.floor(vit / 4) + skill
    return p, CURE[spell or 'Cure IV'][1]


def describe(kind, t, base, value, spell=None):
    """Plain words about a set's totals: where it stands against each cap."""
    out = []

    def cap(label, n, top):
        if n > top:
            return f'{label} {n}% (cap {top}%: {n - top}% wasted)'
        return f'{label} {n}% of {top}%' + (' (full)' if n == top else f' ({top - n}% short)')
    if kind in ('cure', 'curaga', 'selfcure'):
        out.append(cap('Cure potency', t.get('potency', 0), CAP_POTENCY))
        out.append(cap('Potency II', t.get('potency2', 0), CAP_POTENCY2))
        p, top = power_note(kind, t, base, spell)
        out.append(f"Healing skill {base['skill'] + t.get('skill', 0)} (+{t.get('skill', 0)} gear)   MND {base['MND'] + t.get('MND', 0)}"
                   f"   VIT {base['VIT'] + t.get('VIT', 0)}   Power {p} of {top}" + (' (more does nothing)' if p >= top else ''))
    if kind in ('received', 'selfcure'):
        out.append(cap('Potency received', t.get('received', 0), CAP_RECEIVED))
    if kind == 'precast':
        n = cast_total(t, base)
        out.append(cap('Casting time', n, CAP_CAST) + f"  (Fast Cast {t.get('fast', 0)}, cure / healing casting time "
                   f"{t.get('cure_cast', 0) + t.get('heal_cast', 0)}" + (f", from your job {base.get('fast', 0)}" if base.get('fast') else '') + ')')
        out.append(f"Quick Magic {t.get('quick', 0)}%")
    if kind == 'cursna':
        out.append(f"Doom removal about {value}%  (Cursna gear +{t.get('cursna', 0)}, Healing skill {base['skill'] + t.get('skill', 0)})")
    if kind == 'regen':
        out.append(f"Regen potency +{t.get('regen_potency', 0)}%   Regen duration +{t.get('regen_duration', 0)}")
    if kind == 'waltz':
        out.append(cap('Waltz potency', t.get('waltz', 0), CAP_WALTZ))
        out.append(f"CHR {base['CHR'] + t.get('CHR', 0)}")
    pd, md = dt_totals(t)
    en = t.get('enmity', 0)
    line = f'Enmity {en:+d}' + (f' (cap -{CAP_ENMITY}: {-en - CAP_ENMITY} wasted)' if en < -CAP_ENMITY else '')
    line += f'   Damage taken: physical -{pd}%, magic -{md}%'
    if t.get('conserve'):
        line += f"   Conserve MP {t['conserve']}"
    if t.get('sird'):
        line += f"   Interruption -{t['sird']}%"
    out.append(line)
    if kind == 'cure' and t.get('solace'):
        out.append(f"Afflatus Solace stoneskin +{t['solace']}%")
    return out
