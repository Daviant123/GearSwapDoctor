"""
GearSwap Doctor: gear progression - what he has of each job's main gear goals, the next step for each piece and how to do it.
His request 2026-11-07: "build a progression gear tab ... to help towards goals and what to do and how to do it. use the
ffxibg and ffxiah as point of reference".

What it knows (BG Wiki, checked 2026-11-07; RESEARCH.md "Gear progression"):
  Artifact / Relic / Empyrean armor (Reforged): iL109 -> +1 -> +2 -> +3 -> +4, each step's NPC, content and materials
  JSE neck (Dynamis - Divergence, Oboro), Sortie earring (Old Cases), Ambuscade cape (Gorpa-Masorpa, Abdhaljs items)
  Odyssey Sheol Gaol sets (Nyame, Sakpata, Gleti, Ikenga, Agwu, Mpaca) and the job's Ultimate Weapons (rema.py)
Which items exist (and every +N) comes from the game's own list (res/items.lua), so a new +4 shows up by itself.
What he has comes from his bags (Steward's / findAll's saved copy): by item id, every bag. It can't see a piece's rank or
augments in the bags; the GearSwap files show how many different capes he has made.
Nothing here changes a file.
"""
import os
import re

import checks
import paths
import rema

JOB_ID = checks.JOBS
SLOTS = ['head', 'body', 'hands', 'legs', 'feet']
SLOT_BIT = {'head': 4, 'body': 5, 'hands': 6, 'legs': 7, 'feet': 8, 'neck': 9, 'ear': 11, 'back': 15}

# (Artifact, Relic, Empyrean) set names, as the game writes them in full (enl), per job
ARMOR = {'WAR': ("pummeler's", 'agoge', 'boii'), 'MNK': ("anchorite's", "hesychast's", 'bhikku'),
         'WHM': ('theophany', 'piety', 'ebers'), 'BLM': ("spaekona's", "archmage's", 'wicce'),
         'RDM': ('atrophy', 'vitiation', 'lethargy'), 'THF': ("pillager's", "plunderer's", "skulker's"),
         'PLD': ('reverence', 'caballarius', "chevalier's"), 'DRK': ('ignominy', "fallen's", "heathen's"),
         'BST': ('totemic', 'ankusa', 'nukumi'), 'BRD': ('brioso', 'bihu', 'fili'),
         'RNG': ('orion', 'arcadian', 'amini'), 'SAM': ('wakido', 'sakonji', 'kasuga'),
         'NIN': ('hachiya', 'mochizuki', 'hattori'), 'DRG': ('vishap', 'pteroslaver', "peltast's"),
         'SMN': ("convoker's", 'glyphic', "beckoner's"), 'BLU': ("assimilator's", 'luhlaza', 'hashishin'),
         'COR': ("laksamana's", 'lanun', "chasseur's"), 'PUP': ('foire', 'pitre', 'karagoz'),
         'DNC': ('maxixi', 'horos', 'maculele'), 'SCH': ("academic's", 'pedagogy', 'arbatel'),
         'GEO': ('geomancy', 'bagua', 'azimuth'), 'RUN': ('runeist', 'futhark', 'erilaz')}
NECK = {'WAR': "warrior's beads", 'MNK': "monk's nodowa", 'WHM': "cleric's torque", 'BLM': "sorcerer's stole",
        'RDM': "duelist's torque", 'THF': "assassin's gorget", 'PLD': "knight's beads", 'DRK': 'abyssal beads',
        'BST': 'beastmaster collar', 'BRD': "bard's charm", 'RNG': "scout's gorget", 'SAM': "samurai's nodowa",
        'NIN': 'ninja nodowa', 'DRG': "dragoon's collar", 'SMN': "summoner's collar", 'BLU': 'mirage stole',
        'COR': 'commodore charm', 'PUP': "puppetmaster's collar", 'DNC': 'etoile gorget', 'SCH': 'argute stole',
        'GEO': 'bagua charm', 'RUN': 'futhark torque'}
CAPE = {'WAR': "cichol's mantle", 'MNK': "segomo's mantle", 'WHM': "alaunus's cape", 'BLM': "taranus's cape",
        'RDM': "sucellos's cape", 'THF': "toutatis's cape", 'PLD': "rudianos's mantle", 'DRK': "ankou's mantle",
        'BST': "artio's mantle", 'BRD': "intarabus's cape", 'RNG': "belenus's cape", 'SAM': "smertrios's mantle",
        'NIN': "andartia's mantle", 'DRG': "brigantia's mantle", 'SMN': "campestres's cape", 'BLU': "rosmerta's cape",
        'COR': "camulus's mantle", 'PUP': "visucius's mantle", 'DNC': "senuna's mantle", 'SCH': "lugh's cape",
        'GEO': "nantosuelta's cape", 'RUN': "ogma's cape"}
# Odyssey Sheol Gaol armor sets: (name prefix, the NM that unlocks it)
ODYSSEY = [('Nyame', 'nyame', 'Bumba'), ("Sakpata's", "sakpata's", 'Kalunga'), ("Gleti's", "gleti's", 'Ngai'),
           ("Ikenga's", "ikenga's", 'Xevioso'), ("Agwu's", "agwu's", 'Ongo'), ("Mpaca's", "mpaca's", 'Arebati')]

TIER_WORD = {0: 'iL109', 1: '+1', 2: '+2', 3: '+3', 4: '+4'}
FAMILY_WORD = ['Artifact', 'Relic', 'Empyrean']

# Each step: what it takes. {family: {tier reached: text}}; tier -1 = getting the iL109 piece.
SLOT_RT = {'head': 'Ch.1', 'body': 'Ch.2', 'hands': 'Ch.3', 'legs': 'Ch.4', 'feet': 'Ch.5'}
SLOT_RT2 = {'head': 'Ch.6', 'body': 'Ch.7', 'hands': 'Ch.8', 'legs': 'Ch.9', 'feet': 'Ch.10'}
SLOT_ING109 = {'head': 'Phoenix Feather', 'body': 'Malboro Fiber', 'hands': 'Beetle Blood', 'legs': 'Damascene Cloth',
               'feet': 'Oxblood'}
SLOT_ING1 = {'head': 'Gabbrath Horn', 'body': 'Yggdreant Bole', 'hands': 'Bztavian Stinger', 'legs': 'Waktza Rostrum',
             'feet': 'Rockfin Tooth'}
SLOT_OMEN = {'head': "Emperor Arthro's Shell", 'body': "Joyous's Moss", 'hands': "Imperator's Wing",
             'legs': "Warblade Beak's Hide", 'feet': "Abyssdiver's Feather"}
SLOT_CARDS2 = {'head': '4', 'body': '5', 'hands': '3', 'legs': '4', 'feet': '3'}
SLOT_CARDS3 = {'head': '12', 'body': '15', 'hands': '9', 'legs': '12', 'feet': '9'}
SLOT_UNITS = {'head': '20,000', 'body': '30,000', 'hands': '15,000', 'legs': '25,000', 'feet': '10,000'}
DYNA_ZONE = {'head': 'Windurst', 'body': 'all four zones', 'hands': 'Bastok', 'legs': 'Jeuno', 'feet': "San d'Oria"}
SLOT_DD3 = {'head': 'Defiant Scarf', 'body': "Hades' Claw", 'hands': 'Macuil Plating', 'legs': 'Tartarian Soul',
            'feet': 'Plovid Flesh'}
PIECE = {'head': 'Head', 'body': 'Torso', 'hands': 'Hand', 'legs': 'Leg', 'feet': 'Foot'}

WIKI = 'https://www.bg-wiki.com/ffxi/'
FAMILY_WIKI = {0: 'Reforged_Artifact_Armor', 1: 'Reforged_Relic_Armor', 2: 'Reforged_Empyrean_Armor'}
TIER_WIKI = {0: '', 1: '_%2B1', 2: '_%2B2', 3: '_%2B3', 4: '_%2B4'}


def step(family, slot, to, job):
    """(where / content, what it takes) to reach tier `to` (0 = the iL109 piece) of an armor piece."""
    if to == 0:
        if job in ('GEO', 'RUN'):
            return ('Adoulin commission quests',
                    'GEO / RUN get the iL109 piece from a commission in Adoulin (Bayld and crafting materials), no reforging.')
        old = ['Artifact armor (or AF +1)', 'Relic armor (+1 / +2 best)', 'Empyrean armor +1 or +2 (Abyssea)'][family]
        need = ['Promathia mission 7-5 done; talk to Sagheera, "Just wanted to chat"',
                'the Dynamis quests begun and Promathia 3-5 done; ask Sagheera about "Relic Restoration" wearing the relic',
                'nothing more'][family]
        return ('Monisette, Port Jeuno (I-8)',
                f'Trade {old} + Rem\'s Tale {SLOT_RT[slot]} x10 (x5 from the better old piece) + the job\'s ingredient + '
                f'{SLOT_ING109[slot]}. Ready in one game day. Needs {need}.')
    if to == 1:
        return ('Monisette, Port Jeuno (I-8)',
                f'Trade the iL109 piece + Rem\'s Tale {SLOT_RT2[slot]} x8 + the job\'s ingredient + {SLOT_ING1[slot]} '
                '(Rem\'s Tales and ingredients: Hard Mode battlefields, Delve, Voidwatch). Ready in one game day.')
    if family == 0:
        if to == 2:
            return ('Coelestrox, Reisenjima - Omen',
                    f'Trade the +1 + P. {job} Card x{SLOT_CARDS2[slot]} (about) + the job\'s ingredient + {SLOT_OMEN[slot]}, '
                    '10 beads. Enter Omen once first. One game day (500 beads to skip).')
        if to == 3:
            return ('Coelestrox, Reisenjima - Omen',
                    f'Day 1: 200 beads + P. {job} Card x{SLOT_CARDS3[slot]} + the job\'s boss scale (Omen floor bosses / '
                    'Sweetwater foes). Day 2: 300 beads + crafting materials and Cyan Orbs. Card counts were lowered in '
                    'May 2025: check the job table.')
        if to == 4:
            return ('Apollyon Furnace, Apollyon - Limbus',
                    f'Trade the +3 + {SLOT_UNITS[slot]} Apollyon Units (earned in Apollyon: kills, the shimmering point, '
                    'chests). Ready at once; any job.')
    if family == 1:
        if to == 2:
            return ('Aurix (???), Ru\'Lude Gardens (G-8) - Dynamis - Divergence',
                    f'Trade the +1 + {PIECE[slot]}shard: {job} x2 + the job\'s ingredient + {SLOT_ING1[slot]}. First enter '
                    f'Divergence {DYNA_ZONE[slot]} on {job}. One game day.')
        if to == 3:
            return ('Aurix (???), Ru\'Lude Gardens (G-8) - Divergence + Vagary',
                    f'Trade the +2 + {PIECE[slot]}shard: {job} x2 + Void{PIECE[slot].lower()}: {job} x2 + '
                    f'{SLOT_DD3[slot]} x2 (Vagary). Unlock: beat the mid-boss statue in Divergence {DYNA_ZONE[slot]} on '
                    f'{job} (or 100 wave-1 foes there).')
        if to == 4:
            return ('Temenos Furnace, Temenos - Limbus',
                    f'Trade the +3 + {SLOT_UNITS[slot]} Temenos Units (earned in Temenos). Open a Temenos chest once '
                    'first. Ready at once; any job.')
    if family == 2:
        if to == 2:
            return ('Ruspix, Leafallia (H-8) - Sortie',
                    'Trade the +1 + 1 Ra\'Kaz. Sapphire + 10,000 Gallimaufry. Needs the missions The Light Within and '
                    'The Orb\'s Radiance; enter Sortie once on the job. One game day.')
        if to == 3:
            return ('Ruspix, Leafallia (H-8) - Sortie',
                    'Trade the +2 + 1 Ra\'Kaz. Starstone + 70,000 Gallimaufry. Unlock: reach an area through a Bitzer '
                    'on the job. One game day.')
    return ('BG Wiki', 'This step is new; BG Wiki has the details.')


# ----------------------------------------------------------------------------- the game's item list
_ITEMS = None


def items(path=None):
    """[{'id', 'en', 'enl', 'jobs', 'slots', 'ilvl', 'cat'}] of all armor and weapons (res/items.lua)."""
    global _ITEMS
    if _ITEMS is not None and path is None:
        return _ITEMS
    path = path or paths.res_items()
    if not os.path.exists(path):
        path = os.path.join(checks.WINDOWER, 'res', 'items.lua')
    out = []
    pat = re.compile(r'^\s*\[(\d+)\] = \{(.*)\},?\s*$')
    for line in open(path, encoding='utf-8'):
        if 'category="Armor"' not in line and 'category="Weapon"' not in line:
            continue
        m = pat.match(line)
        if not m:
            continue
        b = m.group(2)
        en = re.search(r'(?:^|,)en="([^"]*)"', b)
        enl = re.search(r'(?:^|,)enl="([^"]*)"', b)
        f = dict(re.findall(r'(\w+)=(\d+)', b))
        out.append({'id': int(m.group(1)), 'en': en.group(1) if en else '', 'enl': (enl or en).group(1).lower(),
                    'jobs': int(f.get('jobs', 0)), 'slots': int(f.get('slots', 0)), 'ilvl': int(f.get('item_level', 0)),
                    'cat': 'Weapon' if 'category="Weapon"' in b else 'Armor'})
    _ITEMS = out
    return out


def _title(name):
    """assimilator's -> Assimilator's (str.title() gives "Assimilator'S")."""
    return ' '.join(w[:1].upper() + w[1:] for w in name.split(' '))


def _tier(it):
    m = re.search(r'\+(\d)$', it['enl'])
    return int(m.group(1)) if m else 0


def _slot_of(it):
    for s, bit in SLOT_BIT.items():
        if it['slots'] & (1 << bit):
            return s
    return None


def _for_job(it, job):
    return bool(it['jobs'] & (1 << JOB_ID[job]))


def owned_ids(bags):
    """Every item id in his bags (all bags: wardrobes, safe, storage, satchel...)."""
    out = set()
    for bag, content in (bags or {}).items():
        if isinstance(content, dict):
            out.update(int(k) for k in content)
    return out


# ----------------------------------------------------------------------------- the goals of one job
def _armor_goal(job, family, its, have):
    prefix = ARMOR[job][family] + ' '
    pieces = {}
    for it in its:
        if it['cat'] != 'Armor' or not it['enl'].startswith(prefix) or not _for_job(it, job) or it['ilvl'] < 109:
            continue
        s = _slot_of(it)
        if s in SLOTS:
            pieces.setdefault(s, {})[_tier(it)] = it
    top = max([t for p in pieces.values() for t in p] or [0])
    rows = []
    for s in SLOTS:
        tiers = pieces.get(s, {})
        got = max([t for t, it in tiers.items() if it['id'] in have], default=None)
        nxt = 0 if got is None else got + 1
        row = {'slot': s, 'have': got, 'have_name': tiers[got]['en'] if got is not None else None, 'max': top,
               'names': [it['en'] for it in tiers.values()] + [it['enl'] for it in tiers.values()]}
        if nxt <= top and nxt in tiers:
            row['next'] = nxt
            row['next_name'] = tiers[nxt]['en']
            row['where'], row['how'] = step(family, s, nxt, job)
            row['wiki'] = WIKI + FAMILY_WIKI[family] + TIER_WIKI.get(nxt, '')
        rows.append(row)
    done = sum((r['have'] + 1) if r['have'] is not None else 0 for r in rows)
    return {'key': f'{job}|{FAMILY_WORD[family]}', 'title': f'{FAMILY_WORD[family]} armor ({_title(ARMOR[job][family])})',
            'rows': rows, 'done': done, 'total': (top + 1) * len(SLOTS),
            'summary': _armor_summary(rows, top)}


def _armor_summary(rows, top):
    n = sum(1 for r in rows if r['have'] == top)
    worst = min([r['have'] if r['have'] is not None else -1 for r in rows])
    return f'{n}/5 at {TIER_WORD[top]}' + ('' if n == 5 else f', lowest: {TIER_WORD.get(worst, "none") if worst >= 0 else "missing"}')


def _ladder_goal(key, title, job, its, have, match, slot, how_for, wiki):
    """One item that comes as NQ / +1 / +2 (neck, earring)."""
    tiers = {}
    for it in its:
        if it['cat'] == 'Armor' and match(it['enl']) and _for_job(it, job) and _slot_of(it) == slot:
            tiers.setdefault(_tier(it), it)
    if not tiers:
        return None
    top = max(tiers)
    got = max([t for t, it in tiers.items() if it['id'] in have], default=None)
    nxt = min([t for t in tiers if got is None or t > got], default=None)
    row = {'slot': slot if slot != 'ear' else 'ear', 'have': got, 'have_name': tiers[got]['en'] if got is not None else None,
           'max': top, 'names': [it['en'] for it in tiers.values()] + [it['enl'] for it in tiers.values()]}
    if nxt is not None:
        row['next'] = nxt
        row['next_name'] = tiers[nxt]['en']
        row['where'], row['how'] = how_for(nxt)
        row['wiki'] = wiki(tiers[nxt]['en'])
    return {'key': key, 'title': title, 'rows': [row], 'done': 0 if got is None else got + 1, 'total': top + 1,
            'summary': (f'have {tiers[got]["en"]}' if got is not None else 'not yet') + ('' if nxt is None else
                                                                                        f', next {tiers[nxt]["en"]}')}


def _wiki_page(name):
    return WIKI + name.replace(' ', '_').replace('+', '%2B')


def _neck_how(t):
    return ('Dynamis - Divergence, then Oboro, Port Jeuno (E-6)',
            'The neck comes from Dynamis - Divergence. Rank it up with Oboro: trade Heroism Crystals (10 points) or '
            'Aggregates (50), or wear it while killing in Divergence. Max rank: NQ 15, +1 20, +2 25 (25,150 points). '
            'Once you start ranking a neck it can\'t be sold or traded.')


def _ear_how(t):
    case = 'an Old Case +2' if t >= 2 else 'an Old Case +1'
    return ('Sortie, Leafallia',
            f'Open {case} (from Sortie bosses); it gives a job earring of any job at random. +1 earrings have two augments, '
            '+2 earrings three.')


def _cape_goal(job, its, have, sets):
    name = CAPE[job]
    ids = [it['id'] for it in its if it['enl'] == name and it['cat'] == 'Armor']
    if not ids:
        return None
    got = any(i in have for i in ids)
    kinds = set()
    for s in sets or []:
        for g in s['gear'].values():
            if str(g.get('name', '')).lower() in (name, _en_of(its, ids[0]).lower()):
                kinds.add(tuple(sorted(g.get('augments') or [])))
    real = [k for k in kinds if k]
    row = {'slot': 'back', 'have': 0 if got else None, 'have_name': _en_of(its, ids[0]) if got else None, 'max': 0,
           'names': [name, _en_of(its, ids[0])], 'kinds': len(real), 'next': 0, 'next_name': _en_of(its, ids[0]),
           'where': 'Ambuscade - Gorpa-Masorpa, Mhaura',
           'how': ('Buy "Ambuscade Voucher: Back" with Hallmarks and trade it for the cape. Make it with Abdhaljs items: '
                   'Thread x20 (the stat), Dust x20 (accuracy / attack or magic), Sap x10 (STR / DEX / INT ...), Dye x10 '
                   '(one more stat) and Resin x5 (double attack, store TP, WS damage, fast cast ...). A Needle lets you '
                   'change a stat without losing what was put in. Most jobs make several: TP, weapon skill, nuke, idle...'),
           'wiki': _wiki_page(_en_of(its, ids[0]))}
    if got:                                  # (owned: the how-to stays for making more kinds, but it isn't a next step)
        row['more'] = row.pop('next') is not None and row.pop('next_name')
    return {'key': f'{job}|Cape', 'title': f'Ambuscade cape ({_en_of(its, ids[0])})', 'rows': [row],
            'done': 1 if got else 0, 'total': 1,
            'summary': ('have it' + (f', {len(real)} kinds made in your GearSwap' if real else '')) if got else 'not yet'}


def _en_of(its, iid):
    for it in its:
        if it['id'] == iid:
            return it['en']
    return ''


def _odyssey_goal(job, its, have, label, prefix, nm):
    pieces = {}
    for it in its:
        if it['cat'] == 'Armor' and it['enl'].startswith(prefix + ' ') and _for_job(it, job) and it['ilvl'] >= 119:
            s = _slot_of(it)
            if s in SLOTS:
                pieces.setdefault(s, it)
    if len(pieces) < 3:
        return None
    rows = []
    for s in SLOTS:
        it = pieces.get(s)
        if not it:
            continue
        got = it['id'] in have
        row = {'slot': s, 'have': 0 if got else None, 'have_name': it['en'] if got else None, 'max': 0,
               'names': [it['en'], it['enl']]}
        if not got:
            row.update({'next': 0, 'next_name': it['en'], 'where': f'Odyssey - Sheol Gaol ({nm}), Pilgrim Moogle in Rabao',
                        'how': (f'Beat {nm} in Sheol Gaol (Odyssey) to be able to buy it with gil from the Moogle in Rabao; '
                                'the price drops as the server beats it more. Then rank it up (Rank 15 to 30) with points from '
                                'fights at V+1 or harder - how high depends on the Vengeance you unlocked it at.'),
                        'wiki': _wiki_page(it['en'])})
        rows.append(row)
    n = sum(1 for r in rows if r['have'] is not None)
    return {'key': f'{job}|{label}', 'title': f'{label} set (Odyssey, {nm})', 'rows': rows, 'done': n, 'total': len(rows),
            'summary': f'{n}/{len(rows)} pieces'}


WEAPON_HOW = {'Relic': 'Dynamis (Byne Bills, Bronze Pieces, Shells) and its long quest',
              'Mythic': 'Nyzul Isle, Assault and Salvage (Alexandrite), then Unlocking a Myth for the weapon skill',
              'Empyrean': 'Abyssea NMs (Atma), then Kupofried\'s weapon skill quest',
              'Aeonic': 'Escha / Reisenjima (Geas Fete) and Ambuscade items',
              'Ergon': 'its own job quest line',
              'Prime': 'Prime weapon quests (stages I to V)'}


def _weapon_goal(job, its, have):
    rows = []
    seen = set()
    for fam, table in rema.FAMILIES.items():
        for w in table:
            ids = [it['id'] for it in its if it['cat'] == 'Weapon' and it['en'].lower() == w.lower() and _for_job(it, job)]
            if not ids or w in seen:
                continue
            seen.add(w)
            got = any(i in have for i in ids)
            row = {'slot': fam, 'have': 0 if got else None, 'have_name': w if got else None, 'max': 0, 'names': [w]}
            if not got:
                row.update({'next': 0, 'next_name': w, 'where': fam + ' weapon',
                            'how': f'{w} ({fam}): {WEAPON_HOW[fam]}. BG Wiki has every step.', 'wiki': _wiki_page(w)})
            rows.append(row)
    if not rows:
        return None
    n = sum(1 for r in rows if r['have'] is not None)
    return {'key': f'{job}|Weapons', 'title': 'Ultimate weapons',
            'rows': rows, 'done': n, 'total': len(rows), 'summary': f'{n}/{len(rows)} owned'}


def goals(job, bags, sets=None, its=None):
    """Every gear goal of a job, with what he has and the next step of each piece.
    sets: the sets of his GearSwap file(s) for this job (gs_loader sets), to count where each piece is used."""
    its = its or items()
    have = owned_ids(bags)
    out = [_armor_goal(job, f, its, have) for f in range(3)]
    base = {NECK[job]} | {it['enl'] for it in its if it['en'].lower() == NECK[job]}       # (Knight's Beads: "knight's bead necklace")
    out.append(_ladder_goal(f'{job}|Neck', f'JSE neck ({_title(NECK[job])})', job, its, have,
                            lambda n: re.sub(r' \+\d$', '', n) in base, 'neck', _neck_how, _wiki_page))
    emp = ARMOR[job][2]
    out.append(_ladder_goal(f'{job}|Earring', f'Sortie earring ({_title(emp)} Earring)', job, its, have,
                            lambda n: n.startswith(emp + ' earring'), 'ear', _ear_how, _wiki_page))
    out.append(_cape_goal(job, its, have, sets))
    for label, prefix, nm in ODYSSEY:
        out.append(_odyssey_goal(job, its, have, label, prefix, nm))
    out.append(_weapon_goal(job, its, have))
    out = [g for g in out if g]
    used = used_counts(sets)
    for g in out:
        for r in g['rows']:
            r['used'] = sum(used.get(n.lower(), 0) for n in set(x.lower() for x in r['names']))
    return out


def used_counts(sets):
    """{item name (lower): number of sets it is in}."""
    out = {}
    for s in sets or []:
        for n in {str(g.get('name', '')).lower() for g in s['gear'].values()}:
            out[n] = out.get(n, 0) + 1
    return out


def next_steps(gs, limit=12):
    """The steps most worth doing next: a missing piece or upgrade of gear his sets use most, cheaper steps first."""
    cand = []
    for g in gs:
        for r in g['rows']:
            if 'next' not in r:
                continue
            missing = r['have'] is None
            score = r.get('used', 0) * 3 + (6 if missing and not g['key'].endswith('Weapons') else 0) - r['next']
            if g['key'].endswith('Weapons'):
                score -= 5
            cand.append((score, g, r))
    cand.sort(key=lambda c: -c[0])
    return [(g, r) for s, g, r in cand[:limit]]


def percent(g):
    return int(100 * g['done'] / g['total']) if g['total'] else 0
