"""
GearSwap Doctor: Paladin sets (his request 2026-11-05: "incorporate this into the gearswap doctor to better gear and make gearswap for pld", the FFXIAH guide
"The Divine Protector: PLD Guide 2025", ffxiah.com/node/482, by Carbuncle.Tetsouo). wsdist only knows damage; a tank's sets are about other things, so they're judged here,
on the game's item text, by what each set is for (its name says, or he picks). The guide's rules, with its numbers (more in RESEARCH.md):

  Enmity     gear + Crusade (+30) + Sentinel (+100) stop at +200 together: a spike set (Flash, Provoke, abilities) needs at most +170 from gear
  Idle       a tank loses hate each time it's hit: Enmity+ cuts that loss (1 % per +2, up to 50 % at +100 with Crusade: +70 from gear) and so does
             "enmity retention" gear (Burtgang, Chev. Cuisses, Creed Collar: up to 50 %). Damage taken first.
  SIRD       spells cast while being hit: capped at 102 % with 5/5 merits (10 %), so 92 % from gear
  Phalanx    damage taken a hit = what Enhancing skill gives (28 + (skill - 300.5) / 28.5 above 300) + Phalanx gear
  Cures      potency up to 50 % (Majesty gives potency II), received up to 30 % on yourself, and more max HP heals (and pulls hate) more
  Fast cast  up to 80 %, keeping your HP near your idle set's: "keep HP variance within 200 HP"
  Abilities  a JA set is the enmity set with the piece that boosts it (Cab. Leggings for Sentinel ...)
  HP order   GearSwap puts the highest "priority" on first: HP pieces first, so a swap never drops your HP (priority_for)
"""
import math
import re

import fixer
import healing

BASE_HP = 2000                 # (a PLD's own HP with no gear, about; for "HP +10 %" pieces)
ENH_SKILL = 350                # Enhancing skill with no gear: 334 + 16 from merits (the guide). Master levels add more.
SIRD_MERITS = 10               # 5/5 "Spell Interruption Rate" merits: the guide's pick
SIRD_CAP = 102
ENMITY_SPIKE = 170             # +200 with Crusade's +30
ENMITY_IDLE = 70               # +100 with Crusade: the 50 % cap on hate lost when hit
KEEP_CAP = 50
FAST_CAP, POTENCY_CAP, RECEIVED_CAP = 80, 50, 30
HP_GAP = 200
TOTAL_DT_CAP = 87.5           # (BG Wiki Community PLD Guide: Aegis MDT II -50 %, max player MDT -87.5 %; Burtgang breaks the PDT cap to -68 %)
MEVA_TANK = 550

RX = [(k, re.compile(rx)) for k, rx in [
    ('phalanx', r'"?Phalanx"?(?: received)? ?\+(\d+)'), ('shield_skill', r'Shield skill ?\+(\d+)'), ('enm_keep', r'enmity retention when taking damage ?\+(\d+)'),
    ('hp_pct', r'(?<![A-Za-z"])HP ?\+(\d+)%'), ('mp_to_hp', r'Converts (\d+) MP to HP'), ('DEF', r'\bDEF: ?\+?(\d+)|\bDEF ?\+(\d+)'),
    ('status_res', r'[Rr]esistance to all status ailments ?\+(\d+)'), ('holy_water', r'"Holy Water"(?: effect)? ?\+(\d+)'), ('cursna_rec', r'"Cursna" effects? received ?\+(\d+)'),
    ('bash', r'"Shield Bash" ?\+(\d+)'),
]]
UNITY_RX = re.compile(r'Unity Ranking: ?(Enmity|HP) ?\+(\d+)\s*[～~-]\s*(\d+)')


def parse(text):
    """{stat: value} a PLD set cares about that healing.parse_text doesn't read."""
    cut = healing.CUT_RX.search(text)
    own = text[:cut.start()] if cut else text
    out = {}
    for k, rx in RX:
        n = sum(int(y) for x in rx.findall(own) for y in (x if isinstance(x, tuple) else (x,)) if y)
        if n:
            out[k] = n
    if 'Reduces Enmity decrease when taking damage' in own:          # (Creed Collar: no number in the text; the guide says 5)
        out['enm_keep'] = out.get('enm_keep', 0) + 5
    for what, low, high in UNITY_RX.findall(text):                    # (Apeile Ring's enmity is all Unity: counted at the top rank, as the guide does)
        k = 'u_enmity' if what == 'Enmity' else 'u_hp'
        out[k] = out.get(k, 0) + int(high)
    return out


# what the item text doesn't say: a Mythic's stats grow with its level (the guide's numbers at 119)
NAMED = {'burtgang': {'enm_keep': 20, 'pdt2': 18},
         # "Enhances ..." with no number: BG Wiki's values (from the FFXI Premium Guide 2013)
         "eshmun's ring": {'cursna_rec': 20}, 'saida ring': {'cursna_rec': 15}, "blenmot's ring": {'holy_water': 5}, "blenmot's ring +1": {'holy_water': 10}}

# the pieces that boost an ability (the guide's "JAs Sets" table); names as the game shortens them, any +1/+2/+3/+4
JA_GEAR = {
    'Invincible': ('cab. breeches', 'caballarius breeches', 'vlr. breeches +2'),
    'Holy Circle': ('rev. leggings', 'reverence leggings', 'gallant leggings', 'glt. leggings'),
    'Shield Bash': ('cab. gauntlets', 'caballarius gauntlets', 'valor gauntlets', 'vlr. gauntlets', 'fenian ring', 'knightly earring', 'sigma earring'),
    'Sentinel': ('cab. leggings', 'caballarius leggings', 'valor leggings', 'vlr. leggings'),
    'Cover': ('rev. coronet', 'reverence coronet', 'gallant coronet', 'glt. coronet'),
    'Rampart': ('cab. coronet', 'caballarius coronet', 'valor coronet', 'vlr. coronet'),
    'Fealty': ('cab. surcoat', 'caballarius surcoat', 'vlr. surcoat +2'),
    'Chivalry': ('cab. gauntlets', 'caballarius gauntlets', 'vlr. gauntlets +2'),
    'Divine Emblem': ('chev. sabatons', "chevalier's sabatons", 'creed sabatons'),
}
COVERING = ('sahip helm', 'cab. surcoat', 'caballarius surcoat', 'vlr. surcoat', 'valor surcoat')     # (worn while Cover is up: DT -12 %, hits to MP)
ENMITY_JA = ('provoke', 'palisade', 'majesty', 'warcry', 'intervene', 'animated flourish', 'vallation', 'valiance', 'pflug', 'swordplay', 'liement', 'battuta',
             # (a sub job's abilities: the guide builds every JA set on the enmity set; a tank stays a tank while it uses them)
             'berserk', 'aggressor', 'defender', 'violent flourish', 'sepulcher', 'jump', 'high jump')

# (Magic Evasion counts 3 times as much below the 550 FFXIAH posters aim for in a tank's idle set, idle.MEVA_IDLE)
_TANK = {'phys': 20, 'magic': 16, 'enmity_idle': 0.8, 'keep': 1.5, 'meva': 0.1, 'meva_low': 0.2, 'mdb': 1.5, 'hp': 0.05, 'status': 1, 'refresh': 6, 'regen': 2, 'def': 0.01}
FOCUS = {
    'Tank, standing': _TANK,
    'Tank, magic': {'phys': 8, 'magic': 30, 'meva': 0.3, 'meva_low': 0.2, 'mdb': 3, 'enmity_idle': 0.5, 'keep': 0.5, 'hp': 0.04, 'status': 1, 'refresh': 2},
    'Tank, fighting': dict(_TANK, acc=0.05, stp=1, refresh=2),
    'Enmity': {'enmity': 5, 'phys': 3, 'magic': 3, 'hp': 0.05},
    'Enmity, not interrupted': {'sird': 6, 'enmity': 4, 'phys': 2, 'magic': 2, 'hp': 0.05},
    'Phalanx': {'phalanx': 30, 'phys': 2, 'magic': 2, 'hp': 0.03},
    'Phalanx, not interrupted': {'sird': 8, 'phalanx': 20, 'phys': 2, 'magic': 2, 'hp': 0.04},
    'Spell, not interrupted': {'sird': 8, 'phys': 3, 'magic': 3, 'enmity': 1, 'hp': 0.05},
    'Enlight': {'divine': 3, 'sird': 6, 'phys': 2, 'magic': 2},
    'Cure others': {'sird': 6, 'potency': 8, 'phys': 3, 'magic': 3, 'enmity': 1, 'hp': 0.04},
    'Cure yourself': {'sird': 6, 'potency': 8, 'received': 6, 'hp': 0.1, 'enmity': 1, 'phys': 2, 'magic': 2},
    'Fast cast': {'fast': 8, 'hp': 0.06, 'phys': 0.5, 'magic': 0.5},
    # (2026-11-10 research, RESEARCH.md "Paladin, more guides"): BG Wiki's Finans PLD sets keep a "Cure Cheat" fast cast set that LOWERS max HP on purpose, so a
    # self-cure heals (and pulls hate) more; FFXIAH's 2025 guide thread: fine with GearSwap, as a separate macro. Only for a set named so (or picked).
    'Fast cast, cure cheat': {'fast': 8, 'hp': -0.04, 'phys': 1, 'magic': 1},
    # (BG Wiki Community PLD Guide: Reprisal "spell duration and enmity, with some Fast Cast"; its sets Enm.+63~79, FC+12~27 %, DT capped)
    'Reprisal': {'enmity': 3, 'fast': 2, 'enh_dur': 2, 'phys': 3, 'magic': 3, 'hp': 0.05},
    # (Finans PLD Stoneskin set: Stoneskin +110, interruption capped too)
    'Stoneskin': {'ss': 3, 'MND': 1, 'sird': 4, 'phys': 2, 'magic': 2, 'hp': 0.04},
    'Covering': {'ja': 60, 'phys': 20, 'magic': 10, 'hp': 0.02},
    'Doom': {'holy_water': 6, 'cursna_rec': 6, 'phys': 1, 'magic': 1},
    'Chivalry': {'ja': 80, 'MND': 2, 'phys': 2, 'magic': 2},
}
for _a in JA_GEAR:
    if _a != 'Chivalry':
        FOCUS['Ability: ' + _a] = {'ja': 80, 'bash': 1 if _a == 'Shield Bash' else 0, 'enmity': 5, 'phys': 3, 'magic': 3, 'hp': 0.05}


def _words(path):
    return [p.lower() for p in fixer._path_parts(path or '')]


def focus_for(path):
    """What a PLD set is for, from its name; None for the sets that aren't judged here (weapon skills and plain TP sets: wsdist; Refresh, town: idle.py)."""
    w = _words(path)
    if len(w) < 2 or w[0] != 'sets':
        return None
    rest = w[1:]
    if rest[0] == 'buff':
        return 'Doom' if 'doom' in rest else 'Covering' if 'cover' in rest else None
    sird = 'sird' in rest
    if rest[0] == 'precast':
        if any('cheat' in x for x in rest):
            return 'Fast cast, cure cheat'
        if 'ja' in rest:
            ja = rest[rest.index('ja') + 1] if rest.index('ja') + 1 < len(rest) else ''
            for a in JA_GEAR:
                if ja == a.lower():
                    return 'Chivalry' if a == 'Chivalry' else 'Ability: ' + a
            return 'Enmity' if ja in ENMITY_JA or ja == 'enmity' else None
        if 'fc' in rest or 'fastcast' in rest:
            return 'Fast cast'
        if 'ws' in rest and 'atonement' in rest:
            return 'Enmity'
        if rest[1:2] == ['step'] or rest[1:2] == ['flourish1']:
            return 'Enmity'
        return None
    if rest[0] == 'midcast':
        what = ' '.join(rest[1:])
        if 'phalanx' in what:
            return 'Phalanx, not interrupted' if sird else 'Phalanx'
        if 'enlight' in what:
            return 'Enlight'
        if 'flash' in what or 'stun' in what or 'jettatura' in what or 'banish' in what:
            return 'Enmity, not interrupted' if sird else 'Enmity'
        if 'blue magic' in what or any(x in what for x in ('geist wall', 'sheep song', 'blank gaze', 'soporific', 'stinking gas', 'frightful roar')):
            return 'Enmity, not interrupted'
        if 'reprisal' in what:
            return 'Spell, not interrupted' if sird else 'Reprisal'
        if 'stoneskin' in what:
            return 'Stoneskin'
        if re.search(r'self|cure_self|cureself', what):
            return 'Cure yourself'
        if 'cur' in what or 'healing magic' in what:
            return 'Cure others'
        if any(x in what for x in ('reprisal', 'crusade', 'protect', 'shell', 'stoneskin', 'enhancing magic', 'fastrecast', 'cocoon', 'refresh', 'aquaveil', 'barfire',
                                   'barblizzard', 'baraero', 'barstone', 'barthunder', 'barwater', 'raise')):
            return 'Spell, not interrupted'
        return None
    if rest[0] == 'enmity':
        return 'Enmity, not interrupted' if sird else 'Enmity'
    if rest[0] in ('self_healing', 'selfhealing', 'cure_self', 'cureself'):
        return 'Cure yourself'
    if rest[0] == 'idle':
        if any(x in rest for x in ('refresh', 'town', 'kiting', 'weak', 'reraise', 'resting')):
            return None
        return 'Tank, magic' if any(x in rest for x in ('mdt', 'meva', 'magic')) else 'Tank, standing'
    if rest[0] == 'defense':
        if len(rest) < 2 or any(x in rest[1] for x in ('death', 'charm', 'reraise')):
            return None
        return 'Tank, magic' if any(x in rest[1] for x in ('mdt', 'meva', 'bdt')) else 'Tank, standing'
    if rest[0] == 'engaged' and any('tank' in x for x in rest):
        return 'Tank, fighting'
    return None


def takes(path, job):
    """A set judged here (not by wsdist or idle.py)."""
    return (job or '').upper() == 'PLD' and focus_for(path) is not None


def _named(c):
    return NAMED.get(c['name'].lower(), {})


def ja_pieces(gear, ability):
    """How many pieces of the set boost that ability."""
    names = COVERING if ability == 'Covering' else JA_GEAR.get(ability, ())
    n = 0
    for c in gear.values():
        if c and any(c['name'].lower().startswith(p) or c.get('enl', '').lower().startswith(p) for p in names):
            n += 1
    return n


def phalanx_from_skill(skill):
    """Phalanx's damage cut a hit from Enhancing magic skill (BG Wiki / the guide's table: 300 = 28, 358 = 30, 415 = 32, 500 = 35)."""
    skill = min(skill, 500)                      # (potency stops at 500 Enhancing skill: BG Wiki Community PLD Guide)
    if skill <= 300:
        return max(0, math.floor(skill / 10) - 2)
    return 28 + math.floor((skill - 300.5) / 28.5)


def step_start(skill):
    """The lowest skill that gives the same Phalanx as this skill (the start of the step it's on)."""
    f = phalanx_from_skill(skill)
    s = skill
    while s > 0 and phalanx_from_skill(s - 1) == f:
        s -= 1
    return s


def next_phalanx_skill(skill):
    """The skill where Phalanx gets 1 better (it's in steps: one point short gives the lower step)."""
    f = phalanx_from_skill(skill)
    s = skill + 1
    while phalanx_from_skill(s) <= f and s < skill + 60:
        s += 1
    return s


def hp_of(c):
    """Max HP a piece gives: HP+, Converts MP to HP, HP +%, Unity HP."""
    st = c['stats']
    return st.get('HP', 0) + st.get('mp_to_hp', 0) + st.get('u_hp', 0) + round(st.get('hp_pct', 0) * BASE_HP / 100)


def numbers(gear, focus=None):
    """What a set has, as a PLD's sets are judged."""
    t, hp = {}, 0
    for c in gear.values():
        if c:
            pre = c.get('_pld')
            if pre is None or pre[0] is not c['stats']:          # (a piece's own stats + what its text doesn't say, and its HP: worked out once)
                st = dict(c['stats'])
                healing.add(st, _named(c))
                pre = c['_pld'] = (c['stats'], [(k, v) for k, v in st.items() if v], hp_of(c))
            for k, v in pre[1]:
                t[k] = t.get(k, 0) + v
            hp += pre[2]
    pd, md = healing.dt_totals(t)
    pd, md = min(TOTAL_DT_CAP, pd), min(TOTAL_DT_CAP, md)      # (all of it stops at 87.5 %: with Aegis' MDT II -50 %, 37.5 % more from gear is enough)
    enmity = t.get('enmity', 0) + t.get('u_enmity', 0)
    skill = ENH_SKILL + t.get('enh_skill', 0)
    n = {'phys': pd, 'magic': md, 'enmity': enmity, 'keep': t.get('enm_keep', 0), 'sird': t.get('sird', 0) + SIRD_MERITS,
         'phalanx_gear': t.get('phalanx', 0), 'enh_skill': skill, 'phalanx': phalanx_from_skill(skill) + t.get('phalanx', 0),
         'divine': t.get('div_skill', 0), 'fast': t.get('fast', 0), 'potency': t.get('potency', 0), 'received': t.get('received', 0),
         'hp': hp, 'MND': t.get('MND', 0), 'meva': t.get('meva', 0), 'mdb': t.get('mdb', 0),
         'status': t.get('status_res', 0), 'refresh': t.get('refresh', 0), 'regen': t.get('regen', 0), 'def': t.get('DEF', 0), 'acc': t.get('acc', 0),
         'stp': t.get('stp', 0), 'bash': t.get('bash', 0), 'holy_water': t.get('holy_water', 0), 'cursna_rec': t.get('cursna_rec', 0),
         'ss': t.get('ss', 0), 'enh_dur': t.get('enh_dur', 0)}
    ability = focus[len('Ability: '):] if focus and focus.startswith('Ability: ') else 'Chivalry' if focus == 'Chivalry' else 'Covering' if focus == 'Covering' else None
    n['ja'] = ja_pieces(gear, ability) if ability else 0
    n['ability'] = ability
    return n


HP_FLOOR_PTS = 0.4             # (points lost for each HP a swap set is below the sets you stand in: that much HP is cut every time it goes on)
NO_FLOOR = ('Doom', 'Covering', 'Fast cast, cure cheat')
TANK_FLOOR_PTS = 0.15          # (a tank set below that line has less of an HP pool: the guide keeps its idle set the highest in HP; damage taken still comes first)


def value(gear, focus):
    """focus: what the set is for, or (it, HP floor): HP below the floor costs points (his fidelity check 2026-11-05: "how it needs to keep its hp up")."""
    floor = None
    if isinstance(focus, tuple):
        focus, floor = focus
    w = FOCUS.get(focus) or _TANK
    n = numbers(gear, focus)
    capped = {'enmity': min(ENMITY_SPIKE, n['enmity']), 'enmity_idle': min(ENMITY_IDLE, max(0, n['enmity'])), 'keep': min(KEEP_CAP, n['keep']),
              'sird': min(SIRD_CAP, n['sird']) - SIRD_MERITS, 'fast': min(FAST_CAP, n['fast']), 'potency': min(POTENCY_CAP, n['potency']),
              'received': min(RECEIVED_CAP, n['received']), 'meva_low': min(MEVA_TANK, n['meva'])}
    v = 0
    for k, pts in w.items():
        v += pts * capped.get(k, n.get(k, 0))
    if floor:
        v -= (TANK_FLOOR_PTS if focus.startswith('Tank') else HP_FLOOR_PTS) * max(0, floor - n['hp'])
    return round(v, 3)


def words(n, focus=None):
    """'damage taken 50 % / 50 %, enmity +62, HP +890 ...': what matters for the set's focus."""
    f = focus or ''
    out = [f"damage taken {n['phys']} % / {n['magic']} %"]
    if f.startswith('Tank'):
        out.append(f"enmity +{n['enmity']} (hate kept when hit {min(50, max(0, n['enmity'] + 30) // 2)} % + {min(KEEP_CAP, n['keep'])} %)")
        out += [f"Magic Evasion {n['meva']}", f"Magic Def. Bonus +{n['mdb']}"]
        if n['refresh']:
            out.append(f"Refresh +{n['refresh']}")
        if n['status']:
            out.append(f"status resistance +{n['status']}")
    if 'Enmity' in f or f.startswith('Ability'):
        out.append(f"enmity +{n['enmity']} of {ENMITY_SPIKE}")
    if 'interrupted' in f or f.startswith('Cure') or f == 'Enlight':
        out.append(f"interruption -{n['sird']} % of {SIRD_CAP} (10 from merits)")
    if f.startswith('Phalanx'):
        out.append(f"Phalanx -{n['phalanx']} a hit (Enhancing skill {n['enh_skill']}, gear +{n['phalanx_gear']})")
    if f == 'Enlight':
        out.append(f"Divine skill +{n['divine']}")
    if f.startswith('Cure'):
        out.append(f"Cure potency {n['potency']} % of {POTENCY_CAP}")
        if f == 'Cure yourself':
            out.append(f"received {n['received']} % of {RECEIVED_CAP}")
    if f.startswith('Fast cast') or f == 'Reprisal':
        out.append(f"Fast Cast {n['fast']} % of {FAST_CAP}")
    if f == 'Reprisal':
        out.append(f"enmity +{n['enmity']}, duration +{n['enh_dur']} %")
    if f == 'Stoneskin':
        out.append(f"Stoneskin +{n['ss']}, MND +{n['MND']}, interruption -{n['sird']} %")
    if n.get('ability'):
        out.append(f"{n['ja']} piece(s) for {n['ability']}" if n['ja'] else f"nothing for {n['ability']}")
    if f == 'Doom':
        out.append(f"Holy Water +{n['holy_water']}, Cursna received +{n['cursna_rec']}")
    out.append(f"HP +{n['hp']}")
    return ', '.join(out)


def advice(n, focus, idle_hp=None):
    """A line from the guide about the set's numbers; '' when there's nothing to say."""
    tips = []
    f = focus or ''
    if f.startswith('Tank') and (n['phys'] < 50 or n['magic'] < 50):
        tips.append('the guide caps physical and magic damage taken in every tank set (magic: Shell does part of it)')
    if ('interrupted' in f or f.startswith('Cure')) and n['sird'] < SIRD_CAP:
        tips.append(f"interruption {n['sird']} %: {SIRD_CAP} % means spells are never cut off while you're hit (with 5/5 merits)")
    if f.startswith('Phalanx'):
        over = n['enh_skill'] - step_start(n['enh_skill'])
        tips.append(f"Enhancing skill {n['enh_skill']}: past 500 more skill does nothing for Phalanx, only Phalanx+ gear" if n['enh_skill'] >= 500 else
                    f"Enhancing skill {n['enh_skill']}: Phalanx gets 1 better at {next_phalanx_skill(n['enh_skill'])}"
                    + (f" ({over} skill past the step you're on does nothing: Phalanx goes in steps, BG Wiki's 'common mistake')" if over >= 5 and n['enh_skill'] < 500 else ''))
    if f == 'Fast cast, cure cheat':
        tips.append('a cure cheat set: lower max HP on purpose, so your own cures heal (and pull hate) more; the guides say use it with GearSwap only')
    if 'Enmity' in f and n['enmity'] > ENMITY_SPIKE:
        tips.append(f"enmity +{n['enmity']}: with Crusade (+30) more than +{ENMITY_SPIKE} from gear is wasted")
    if f == 'Fast cast' and n['fast'] > FAST_CAP:
        tips.append(f"Fast Cast {n['fast']} %: past {FAST_CAP} % is wasted")
    if n.get('ability') and not n['ja']:
        tips.append(f"none of your gear boosts {n['ability']}")
    if idle_hp and not f.startswith(NO_FLOOR + ('Tank',)) and idle_hp - n['hp'] > 0:
        tips.append(f"HP +{n['hp']} is {idle_hp - n['hp']} below the sets you stand in (+{idle_hp}): your HP is cut by that much each time this set goes on, and it doesn't come back")
    return '; '.join(tips)


_USEFUL = {}


def useful_cached(cands):
    key = id(cands)
    if key not in _USEFUL or _USEFUL[key][0] is not cands:
        _USEFUL[key] = (cands, useful(cands))
    return _USEFUL[key][1]


def useful(cands):
    keys = ('ss', 'enh_dur', 'dt', 'pdt', 'mdt', 'dt2', 'pdt2', 'mdt2', 'enmity', 'u_enmity', 'enm_keep', 'sird', 'phalanx', 'enh_skill', 'div_skill', 'fast', 'potency', 'received',
            'HP', 'mp_to_hp', 'u_hp', 'hp_pct', 'MND', 'meva', 'mdb', 'status_res', 'refresh', 'regen', 'holy_water', 'cursna_rec', 'bash')
    names = {p for t in JA_GEAR.values() for p in t} | set(COVERING) | set(NAMED)
    return [c for c in cands if any(c['stats'].get(k) for k in keys) or any(c['name'].lower().startswith(p) for p in names)]


# (the stats numbers() reads: candidates are trimmed to these before a build, so adding up a set is quick - his Gear Optimization tab judges 100+ sets)
STATS = ('dt', 'pdt', 'mdt', 'dt2', 'pdt2', 'mdt2', 'enmity', 'u_enmity', 'enm_keep', 'sird', 'phalanx', 'enh_skill', 'div_skill', 'fast', 'potency', 'received',
         'HP', 'mp_to_hp', 'u_hp', 'hp_pct', 'MND', 'meva', 'mdb', 'status_res', 'refresh', 'regen', 'DEF', 'acc', 'stp', 'bash', 'holy_water', 'cursna_rec',
         'ss', 'enh_dur')
_SLIM = {}


def slim(cands):
    """The same candidates with only the stats a PLD set is judged on (cached per list)."""
    key = id(cands)
    if key in _SLIM and _SLIM[key][0] is cands:
        return _SLIM[key][1]
    out = []
    for c in cands:
        d = dict(c)
        d['stats'] = {k: v for k, v in c['stats'].items() if k in STATS and v}
        out.append(d)
    _SLIM[key] = (cands, out)
    return out


NOTE = 'weapons and shield kept: a new weapon throws away TP and Aftermath'


def judge(path, set_gear, job, sub, cands, counts, items, data, need=None, focus=None, build=True, idle_hp=None):
    """One PLD set, the same shape as pup.judge. idle_hp: the HP of the sets you stand in (standing_hp): a swap set should have at least that much.
    counts: what's in the inventory and wardrobes; an item that isn't (in storage, not owned) isn't worn by GearSwap, so it's left out of "now"."""
    focus = focus or focus_for(path) or 'Tank, standing'
    cur = healing.set_to_gear(set_gear, items, data)
    notes = [f'judged for: {focus}', NOTE]
    away = sorted({c['name'] for c in cur.values() if counts and c['name'] not in counts})
    if away:
        cur = {s: c for s, c in cur.items() if c['name'] not in away}
        notes.append(f"not in your inventory or wardrobes, so GearSwap can't wear it: {', '.join(away)}")
    floor = idle_hp if idle_hp and not focus.startswith(NO_FLOOR) else None
    if floor:
        notes.append(f'HP kept at +{floor} or more (the most of the sets you stand in)' + ('' if focus.startswith('Tank') else ": so this set doesn't cut your HP when it goes on"))
    # a buff set (sets.buff.Cover, .Doom) goes on over whatever else you wear: only the slots it has now change
    only = set(cur) if _words(path)[1:2] == ['buff'] else None
    if only:
        notes.append('a set worn on top of your other gear: only the slots it has are changed')
    if focus.startswith('Phalanx'):
        notes.append('Sakpata\'s Sword and Priwen add Phalanx too, if losing TP is fine (the guide, between fights)')
    n0 = numbers(cur, focus)
    v0 = value(cur, (focus, floor) if floor else focus)
    if 'sird' not in (need or {}) and 'sird' in FOCUS.get(focus, {}) and n0['sird'] >= SIRD_CAP:      # (it never gets cut off now: the new set mustn't either)
        need = dict(need or {}, sird=SIRD_CAP - SIRD_MERITS)
        notes.append(f'interruption kept at {SIRD_CAP} %')
    elif (need or {}).get('sird'):
        notes.append(f"interruption down: at least {need['sird'] + SIRD_MERITS} % (yours, with 5/5 merits)")
    out = {'cur': cur, 'best': cur, 'now': v0, 'val': v0, 'n_now': n0, 'n_best': n0, 'changes': {}, 'focus': focus, 'keep': True, 'notes': notes, 'short': 0, 'idle_hp': idle_hp,
           'short_now': healing.shortfall(healing.totals(cur), need or None)}
    if build:
        best, val, now = healing.build('pld', slim(useful_cached(cands)), cur, {}, job, sub, spell=(focus, floor) if floor else focus, need=need or None, keep_weapons=True,
                                       counts=counts, only_slots=only)
        out.update(best=best, val=val, now=now, n_best=numbers(best, focus), changes=healing.changes(cur, best, True), short=healing.shortfall(healing.totals(best), need or None))
    return out


STANDING = ('sets.idle', 'sets.idle.Tank', 'sets.engaged', 'sets.engaged.Tank')


def idle_hp(loaded, items, data, counts=None):
    """HP from gear of the sets you stand in between actions (idle, and engaged as the tank): the most of them. A swap set with less max HP cuts your HP
    to its max when it goes on, and the HP doesn't come back when the max goes up again (the FFXIAH PLD guide's HP management)."""
    best = None
    for s in loaded.sets:
        if s['path'] in STANDING:
            g = {k: c for k, c in healing.set_to_gear(s['gear'], items, data).items() if not counts or c['name'] in counts}
            hp = numbers(g)['hp']
            best = hp if best is None else max(best, hp)
    return best


standing_hp = idle_hp


def checked_sets(loaded, limit=None):
    """The PLD sets a check-up looks at (all of them, unless limit): one of each focus first, then the rest, plainest first."""
    rows = [s for s in loaded.sets if takes(s['path'], 'PLD')]
    rows.sort(key=lambda s: (s['path'].count('.'), len(s['path'])))
    first, seen = [], set()
    for s in rows:
        f = focus_for(s['path'])
        if f not in seen:
            seen.add(f)
            first.append(s)
    rows = first + [s for s in rows if s not in first]
    return rows[:limit] if limit else rows


# who looks at the sets this file doesn't judge, and why (for "every set in the file": his request 2026-11-05)
SMALL = ('capacity', 'mp', 'twilight', 'reraise', 'sheltered', 'treasurehunter', 'th', 'latent_refresh', 'latent_regen', 'self_refresh', 'kiting', 'cure_received',
         'maxtp', 'accmaxtp', 'passive', 'sleep', 'charm', 'death', 'weak', 'doom')


def coverage(loaded):
    """{who: [set paths]} for every set of a PLD file: 'pld' (here), 'ws' and 'tp' (wsdist, damage taken kept), 'idle' (idle.py), 'weapons', 'small' (add-on sets for one or
    two items: Capacity, Reraise, MP ...), 'healing' (Waltz, Cure received: the Healing tab)."""
    import doctor
    import idle
    out = {}
    for s in loaded.sets:
        p = s['path']
        w = _words(p)
        if takes(p, 'PLD'):
            k = 'pld'
        elif p.startswith('sets.weapons'):
            k = 'weapons'
        elif '.ws' in p.lower() or 'ws[' in p.lower():
            k = 'ws'
        elif any(x in SMALL or x.startswith('reraise') for x in w[1:]) or w[1:2] in (['buff'], ['passive']):
            k = 'small'
        elif doctor.is_tp_set(p):
            k = 'tp'
        elif idle.is_idle(p):
            k = 'idle'
        elif 'waltz' in p.lower() or 'received' in p.lower():
            k = 'healing'
        else:
            k = 'small'
        out.setdefault(k, []).append(p)
    return out


def coverage_text(cov, judged=None):
    """'Tank sets (PLD guide): 79 of 79; weapon skills and fighting: wsdist, damage taken kept; not judged: 12 add-on sets (Capacity, MP ...)'"""
    if not cov:
        return ''
    n = len(cov.get('pld', []))
    parts = [f"Tank sets (the PLD guide): {judged if judged is not None else n} of {n} checked"]
    w = len(cov.get('ws', [])) + len(cov.get('tp', []))
    if w:
        parts.append(f"{w} weapon skill / fighting sets: wsdist, keeping the damage taken they have")
    if cov.get('idle'):
        parts.append(f"{len(cov['idle'])} Refresh / town sets: the idle check")
    if cov.get('small'):
        names = ', '.join(p[len('sets.'):] for p in cov['small'][:5])
        parts.append(f"not judged: {len(cov['small'])} add-on sets for an item or two ({names}{' ...' if len(cov['small']) > 5 else ''})")
    return '; '.join(parts)


# ------------------------------------------------------------------ HP order
def priority_for(gear):
    """{gs slot: priority} for a set ({slot key: {'name', ...}}) as written: a piece's own HP (the guide's "priority by raw HP": GearSwap puts the highest on first,
    so HP pieces go on before the ones that take HP off). None when the set has fewer than two HP pieces."""
    items, data = _items(), _data()
    out, with_hp = {}, 0
    for key, g in gear.items():
        found = items.find(g['name']) if str(g['name']).lower() not in ('empty', '') else None
        if not found:
            continue
        hp = hp_of(healing.candidate(found[0], data, g.get('augments') or None))
        out[key] = hp
        with_hp += hp > 0
    return out if with_hp >= 2 else None


_DATA = _ITEMS = None


def _items():
    global _ITEMS
    if _ITEMS is None:
        import checks
        _ITEMS = checks.Items()
    return _ITEMS


def _data():
    global _DATA
    if _DATA is None:
        _DATA = healing.ItemData()
    return _DATA


def hp_order(loaded, src=None):
    """{set path: {slot key: priority}} for the sets in the file's own text whose HP pieces have no priority yet. src: the file's text (sets it only borrows
    from another set, with set_combine, are left to that set)."""
    out = {}
    for s in loaded.sets:
        if not takes(s['path'], 'PLD') and not s['path'].startswith(('sets.idle', 'sets.engaged', 'sets.defense', 'sets.precast', 'sets.midcast')):
            continue
        if any('priority' in g for g in s['gear'].values()):
            continue
        own = s['gear']
        if src is not None:
            try:
                a, b = fixer.find_set(src, s['path'])
            except Exception:
                continue
            body = src[a:b + 1]
            own = {k: g for k, g in s['gear'].items() if re.search(r'(?<![A-Za-z0-9_])' + re.escape(k) + r'\s*=\s*["\'{]', body)}
        p = priority_for(own)
        if p:
            out[s['path']] = p
    return out
