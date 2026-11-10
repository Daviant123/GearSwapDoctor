"""
GearSwap Doctor: what the guides say each job's sets are for (his request 2026-11-10: "do the gear optimization for rdm, cor, blu, drk with the ffxiah pages
and bgwiki and guides as resources"). Used by the Gear Optimization tab (gear_opt.py): the job's role and the order of its groups, the guide's words for
each kind of set, the sets the guides expect, and checks on the whole file. Sources and what was read: RESEARCH.md "Red Mage, Corsair, Blue Mage, Dark Knight".
Paladin's are in gear_opt.py / pld.py.
"""
import difflib
import os
import re

import checks


ROLE = {
    'RDM': {
        'title': 'Red Mage: enfeebles, enhancing magic for the party, and melee',
        'text': ("A Red Mage lands enfeebles and keeps the party buffed. Enfeebles: magic accuracy so they land; potency spells by MND / INT and "
                 "\"Enfeebling magic effect\"; Frazzle III and Distract III by Enfeebling skill up to 625 / 610, Poison to 500. Enhancing magic: duration "
                 "for Haste, Refresh, Protect ... (Composure with Lethargy pieces on others), skill for Temper, Enspells, Barspells (500). Fast Cast stops at "
                 "80 % and a Red Mage has 38 % of its own, so 42 % from gear is enough. Nukes, weapon skills and TP sets are judged by wsdist."),
        'order': ['Enfeebling', 'Enhancing', 'Casting fast', 'Cures', 'Staying alive', 'Job abilities', 'Dark magic', 'Nukes and blue magic damage',
                  'Weapon skills', 'Fighting (damage)', 'Standing (Refresh, town)', 'Holding hate', 'Spells', 'Healing tab', 'Weapons', 'Add-on sets'],
        'sources': 'BG Wiki Community Red Mage Guide and Finans Gearset Guides/Red Mage; BG Wiki Enfeeble; FFXIAH "Jack Of All Trades: A Guide To Red Mage".',
    },
    'COR': {
        'title': 'Corsair: Phantom Rolls for the party, Quick Draw, shooting',
        'text': ("A Corsair's first job is its rolls. Only your highest \"Phantom Roll +n\" piece counts (Rostam path C +8; Barataria +5, Merirosvo +3 "
                 "and Regal Necklace don't add up), then roll duration (Lanun Tricorne, Compensator, Camulus's Mantle, Chasseur's Gants, Regal Necklace) and "
                 "the roll's own piece (Chasseur's for Blitzer's, Tactician's, Allies', Caster's, Courser's). Then Quick Draw (damage; accuracy for Light / "
                 "Dark Shot), and shooting: Snapshot first to 70 % (60 % from gear with 5/5 merits), then Rapid Shot. Leaden Salute, Last Stand, Savage "
                 "Blade and TP sets are judged by wsdist."),
        'order': ['Rolls and Quick Draw', 'Shooting', 'Job abilities', 'Casting fast', 'Staying alive', 'Weapon skills', 'Fighting (damage)', 'Cures',
                  'Standing (Refresh, town)', 'Spells', 'Healing tab', 'Weapons', 'Add-on sets'],
        'sources': 'BG Wiki Community Corsair Guide and Finans Gearset Guides/Corsair; FFXIAH "The Pirates\' Lair: A Guide To Corsair".',
    },
    'BLU': {
        'title': 'Blue Mage: blue magic damage, blue magic buffs, and melee',
        'text': ("A Blue Mage deals damage with physical and magical blue magic and weapon skills (judged by wsdist: \"Open in Build a set\"). Judged here: "
                 "blue magic skill for the skill spells (Occultation gives skill / 50 shadows, 600 = 12; Diamondhide, Metallic Body, Magic Barrier), the "
                 "piece for each ability (Diffusion, Chain Affinity, Burst Affinity, Efflux: worn while it is up, in midcast), cures by MND and Cure "
                 "potency, White Wind by max HP, magic accuracy for debuffs, and Fast Cast with \"Blue magic casting time\"."),
        'order': ['Blue magic (buffs, cures, accuracy)', 'Nukes and blue magic damage', 'Job abilities', 'Casting fast', 'Cures', 'Staying alive',
                  'Weapon skills', 'Fighting (damage)', 'Holding hate', 'Enhancing', 'Spells', 'Standing (Refresh, town)', 'Healing tab', 'Weapons', 'Add-on sets'],
        'sources': 'BG Wiki Community Blue Mage Guide, Occultation and Finans Gearset Guides/Blue Mage; FFXIAH "The Beast Within -- A Guide To Blue Mage".',
    },
    'DRK': {
        'title': 'Dark Knight: damage first, dark magic to help',
        'text': ("A Dark Knight deals damage: weapon skills and TP sets come first (judged by wsdist: \"Open in Build a set\"). Its spells: Dread Spikes "
                 "absorbs up to your max HP when cast x 0.5 x (1 + potency) (Heathen's Cuirass +3 +55 %, Crepuscular Scythe +50 %: pick the Scythe under "
                 "\"Make the sets with\"); Drain / Aspir by \"Drain\" and \"Aspir\" potency and Dark magic skill; Absorb spells by magic accuracy, "
                 "\"Absorb\" effect and duration; Absorb-TP by Heathen's Gauntlets; Stun by magic accuracy and Fast Cast. Each ability set needs the "
                 "piece that boosts it."),
        'order': ['Weapon skills', 'Fighting (damage)', 'Dark magic', 'Job abilities', 'Casting fast', 'Staying alive', 'Nukes and blue magic damage',
                  'Enfeebling', 'Spells', 'Cures', 'Standing (Refresh, town)', 'Holding hate', 'Healing tab', 'Weapons', 'Add-on sets'],
        'sources': 'BG Wiki Dread Spikes, Absorb-TP, Drain III, Dark Knight Guide; FFXIAH "(Don\'t) Fear The Reaper: A Dark Knight Guide" (2021 posts).',
    },
}

# the guide's words for each kind of set, per job ((job, purpose) -> text); shown under "What it is for"
WHY = {
    ('RDM', 'Enfeebling (MND)'): ("Potency spells (Slow II, Paralyze II, Addle II, Frazzle II): MND against the target's (Frazzle II: dMND to 50, skill to 350), "
                                  "\"Enfeebling magic effect\" and duration, and magic accuracy so it lands. The Community RDM Guide: Viti. Boots +4 in every "
                                  "enfeebling set; under Saboteur, Lethargy Gantherots."),
    ('RDM', 'Enfeebling (INT)'): 'INT-based enfeebles (Blind, Poisonga ...): INT against the target\'s, "Enfeebling magic effect", magic accuracy.',
    ('RDM', 'Enfeebling (skill)'): ("Frazzle III and Distract III get stronger with Enfeebling skill up to 625 / 610 (dMND to 50); Poison to 500, Poison II has "
                                    "no known cap. Skill first until the cap, then magic accuracy (Finans / Community RDM Guide)."),
    ('RDM', 'Enfeebling (accuracy)'): ("Sleep, Bind, Break, Silence, Dispel, Gravity: the effect is fixed, so it is all magic accuracy (then duration). "
                                       "Inundation can't be resisted."),
    ('RDM', 'Enhancing duration'): ("Haste II, Flurry II, Refresh, Regen, Protect, Shell scale with duration, not skill: \"Enhancing magic duration\" pieces "
                                    "(Telchine augments, Sucellos's Cape, Colada). Augmented % multiply: +25 % and an augmented +25 % = +56 %. On others: "
                                    "Composure with Lethargy pieces."),
    ('RDM', 'Enhancing skill'): 'Temper II and Enspells keep growing with Enhancing skill (no cap). Barspells and Phalanx stop at 500.',
    ('RDM', 'Refresh (cast)'): '"Refresh" potency (Atrophy Tabard +4: +2) first, then duration.',
    ('RDM', 'Stoneskin'): ("Stoneskin = Enhancing skill + 3 x MND - 190, up to 350 (475 with Stoneskin+ gear). A Red Mage caps skill and MND by itself, "
                           "so Stoneskin+ gear is what's left."),
    ('RDM', 'Aquaveil'): 'Aquaveil blocks interruptions: 2 at 355 skill; Aquaveil+ gear adds more.',
    ('RDM', 'Fast cast'): "Fast Cast stops at 80 %; a Red Mage has 38 % of its own, so 42 % from gear is enough (Atrophy Chapeau +4 is the strongest piece).",
    ('COR', 'Phantom Roll'): ("Only your highest \"Phantom Roll +n\" piece counts (Rostam path C +8; Barataria, Merirosvo, Regal Necklace don't add up). Then "
                              "roll duration (Lanun Tricorne, Compensator, Camulus's Mantle, Chasseur's Gants, Regal Necklace) and the roll's own piece. "
                              "Luzaf's Ring doubles the range (8 to 16 yalms)."),
    ('COR', 'Quick Draw: damage'): ("Quick Draw damage: Magic Atk. Bonus, magic damage, AGI, Quick Draw damage+; Chass. Bottes +3 add 31 % to the next hit of "
                                    "the element after a Quick Draw that lands."),
    ('COR', 'Quick Draw: accuracy'): "Light Shot and Dark Shot must land (sleep, dispel): magic accuracy first (Laksamana's Tricorne +4 is the best piece).",
    ('COR', 'Snapshot'): ("Snapshot first, to 70 % (60 % from gear with 5/5 merits; Flurry II adds 30 %), then Rapid Shot. Snapshot always works, "
                          "Rapid Shot is a chance."),
    ('COR', 'Ability'): ("The piece that boosts it: Lanun Bottes (Wild Card), Lanun Trews (Snake Eye), Lanun Gants (Fold; Triple Shot becomes Quad Shot "
                         "half the time), Lanun Frac (Random Deal), Chasseur's Frac (Triple Shot more often)."),
    ('BLU', 'Blue magic: skill'): ("Blue magic skill: Occultation gives skill / 50 shadows (600 = 12); Diamondhide, Metallic Body, Magic Barrier and "
                                   "Carcharian Verve also grow with it."),
    ('BLU', 'Blue magic: cures'): 'Magic Fruit, Wild Carrot, Plenilune Embrace: MND and Cure potency (up to 50 %).',
    ('BLU', 'Blue magic: White Wind'): 'White Wind heals the party by your max HP: HP first, then Cure potency.',
    ('BLU', 'Blue magic: accuracy'): 'Debuffs (Sheep Song, Dream Flower, Silent Storm, Entomb ...): magic accuracy and blue magic skill.',
    ('BLU', 'Ability'): ("The piece that boosts it: Luhlaza Charuqs (Diffusion duration), Hashishin Kavuk / Assim. Keffiyeh / Mavi Kavuk (Chain Affinity), "
                         "Hashi. Basmak (Burst Affinity), Hashishin Tayt + Rosmerta's Cape (Efflux TP). Chain and Burst Affinity gear works in midcast "
                         "(FFXIAH BLU thread)."),
    ('BLU', 'Fast cast: blue magic'): ("\"Blue magic casting time -\" counts with Fast Cast (Hashishin Mintan, Iris -7 %). BG Wiki: a Blue Mage needs 40 % "
                                       "from traits and gear to cap recast, with capped haste and Hashishin Bazubands +3."),
    ('DRK', 'Dread Spikes'): ("Dread Spikes absorbs up to your max HP when cast x 0.5 x (1 + potency): Heathen's Cuirass +3 +55 %, Crepuscular Scythe "
                              "+50 % (together over 100 % of your HP). Max HP and potency first; pick the Scythe under \"Make the sets with\"."),
    ('DRK', 'Drain and Aspir'): ('"Drain" and "Aspir" potency (Erra Pendant ...) and Dark magic skill; Nether Void before it. Drain III can push your max HP '
                                 'past its normal top for 3 minutes.'),
    ('DRK', 'Absorb'): 'Absorb-STR / DEX / ...: magic accuracy so it lands, "Absorb" effect (Erra Pendant), Absorb duration (Ignominy Burgeonet), Dark skill.',
    ('DRK', 'Absorb-TP'): '"Absorb-TP" effect: Heathen\'s Gauntlets +3 +30 %; then magic accuracy and Dark magic skill.',
    ('DRK', 'Stun'): 'Stun must land, and in time: magic accuracy and Fast Cast.',
    ('DRK', 'Dark magic'): 'Endark II, Bio and the rest: Dark magic skill.',
    ('DRK', 'Ability'): ("The piece that boosts it (from the item text): Fall. Sollerets (Last Resort), Ignominy Burgeonet (Souleater), Ignominy "
                         "Gauntlets (Weapon Bash), Ignominy Sollerets (Arcane Circle), Heath. Flanchard (Nether Void)."),
}


def why(job, focus):
    return WHY.get(((job or '').upper(), focus or ''))


GROUPS = {
    'enfeebling': 'Enfeebling', 'elemental enfeeble': 'Enfeebling', 'impact': 'Nukes and blue magic damage',
    'enhancing': 'Enhancing', 'refresh (cast)': 'Enhancing', 'stoneskin': 'Enhancing', 'aquaveil': 'Enhancing', 'phalanx': 'Enhancing', 'barspells': 'Enhancing',
    'drain': 'Dark magic', 'absorb': 'Dark magic', 'dread spikes': 'Dark magic', 'dark magic': 'Dark magic',
    'blue magic': 'Blue magic (buffs, cures, accuracy)',
    'phantom roll': 'Rolls and Quick Draw', 'quick draw': 'Rolls and Quick Draw',
    'snapshot': 'Shooting', 'ranged shots': 'Shooting',
}


def group_of(focus, job, path=''):
    """The job's own group for a purpose ('Enfeebling', 'Rolls and Quick Draw' ...), or None for the general one."""
    f = (focus or '').lower()
    job = (job or '').upper()
    if f == 'stun':
        return 'Dark magic' if job == 'DRK' else 'Enfeebling'
    if f == 'ability' and job == 'COR':
        return 'Rolls and Quick Draw'
    for k, g in GROUPS.items():
        if f.startswith(k):
            return g
    return None


# ------------------------------------------------------------------ sets the guides expect (only for files whose rules pick sets by the spell or ability name)
WANTED = {
    'RDM': [('sets.precast.FC', 'Fast cast', 'every spell starts faster'),
            ('sets.midcast["Enfeebling Magic"]', 'Enfeebling (accuracy)', 'any enfeeble without its own set'),
            ('sets.midcast["Enhancing Magic"]', 'Enhancing duration', 'any enhancing spell without its own set'),
            ('sets.midcast["Frazzle III"]', 'Enfeebling (skill)', 'Frazzle III: Enfeebling skill to 625'),
            ('sets.midcast["Distract III"]', 'Enfeebling (skill)', 'Distract III: Enfeebling skill to 610'),
            ('sets.midcast["Temper II"]', 'Enhancing skill', 'Temper II: Enhancing skill, no cap'),
            ('sets.midcast.Stoneskin', 'Stoneskin', 'Stoneskin+ gear'),
            ('sets.midcast.Aquaveil', 'Aquaveil', 'Aquaveil+ gear'),
            ('sets.midcast.Phalanx', 'Phalanx', 'Phalanx+ gear'),
            ('sets.midcast.Cure', 'Cure', 'cures')],
    'COR': [('sets.precast.CorsairRoll', 'Phantom Roll', 'every roll'),
            ('sets.precast.CorsairShot', 'Quick Draw: damage', 'Quick Draw'),
            ('sets.precast.RA', 'Snapshot', 'shooting starts faster (Snapshot)'),
            ('sets.precast.JA["Wild Card"]', 'Ability', 'Wild Card: Lanun Bottes'),
            ('sets.precast.JA["Snake Eye"]', 'Ability', 'Snake Eye: Lanun Trews'),
            ('sets.precast.JA["Random Deal"]', 'Ability', 'Random Deal: Lanun Frac'),
            ('sets.precast.JA.Fold', 'Ability', 'Fold: Lanun Gants'),
            ('sets.precast.FC', 'Fast cast', 'Utsusemi and other spells')],
    'BLU': [('sets.precast.FC["Blue Magic"]', 'Fast cast: blue magic', 'blue magic starts faster'),
            ('sets.precast.JA["Chain Affinity"]', 'Ability', 'Chain Affinity'),
            ('sets.precast.JA["Burst Affinity"]', 'Ability', 'Burst Affinity'),
            ('sets.precast.JA.Diffusion', 'Ability', 'Diffusion: Luhlaza Charuqs'),
            ('sets.precast.JA.Efflux', 'Ability', 'Efflux'),
            ('sets.precast.JA["Azure Lore"]', 'Ability', 'Azure Lore: Luhlaza Bazubands')],
    'DRK': [('sets.precast.FC', 'Fast cast', 'every spell starts faster'),
            ('sets.midcast["Dread Spikes"]', 'Dread Spikes', 'Dread Spikes: max HP and potency'),
            ('sets.midcast.Drain', 'Drain and Aspir', 'Drain: potency and Dark skill'),
            ('sets.midcast.Aspir', 'Drain and Aspir', 'Aspir: potency and Dark skill'),
            ('sets.midcast["Absorb-TP"]', 'Absorb-TP', 'Absorb-TP: Heathen\'s Gauntlets'),
            ('sets.midcast.Stun', 'Stun', 'Stun: magic accuracy and Fast Cast'),
            ('sets.precast.JA["Last Resort"]', 'Ability', 'Last Resort: Fallen\'s Sollerets'),
            ('sets.precast.JA.Souleater', 'Ability', 'Souleater: Ignominy Burgeonet'),
            ('sets.precast.JA["Arcane Circle"]', 'Ability', 'Arcane Circle: Ignominy Sollerets'),
            ('sets.precast.JA["Weapon Bash"]', 'Ability', 'Weapon Bash: Ignominy Gauntlets'),
            ('sets.precast.JA["Nether Void"]', 'Ability', 'Nether Void: Heathen\'s Flanchard')],
}


def picks_by_name(loaded):
    """True when the file looks like it picks sets by the spell / ability name (Mote, Selindrile, plain files with sets.precast.JA / sets.midcast)."""
    paths = [s['path'] for s in loaded.sets]
    return any(p.startswith('sets.midcast') for p in paths) and any(p.startswith('sets.precast') for p in paths)


# ------------------------------------------------------------------ set names GearSwap can never use (a typo in a spell or ability name)
_NAMES = None


def known_names():
    """{lower name: name} of every spell, job ability, weapon skill, magic skill and trust (Windower's res files)."""
    global _NAMES
    if _NAMES is None:
        _NAMES = {}
        for f in ('spells.lua', 'job_abilities.lua', 'weapon_skills.lua'):
            try:
                for n in re.findall(r'\ben="([^"]+)"', open(os.path.join(checks.WINDOWER, 'res', f), encoding='utf-8').read()):
                    _NAMES[n.lower()] = n
            except OSError:
                pass
        for n in ('Enhancing Magic', 'Enfeebling Magic', 'Elemental Magic', 'Dark Magic', 'Divine Magic', 'Healing Magic', 'Blue Magic', 'Ninjutsu',
                  'Singing', 'Geomancy', 'Summoning Magic', 'Trust'):
            _NAMES[n.lower()] = n
    return _NAMES


def name_fixes(loaded):
    """[(set path, fixed path, wrong name, real name)]: sets named in brackets for a spell / ability / weapon skill that doesn't exist, when one name is
    very close (his DRK file's precast.JA["Weapn Bash"], an RDM file's midcast["[Regen II"]). GearSwap only uses a set whose name matches exactly."""
    names = known_names()
    have = {s['path'] for s in loaded.sets}
    out = []
    for s in loaded.sets:
        p = s['path']
        if not p.startswith(('sets.precast', 'sets.midcast')):
            continue
        for part in re.findall(r'\["([^"]+)"\]', p):
            if part.lower() in names:
                continue
            clean = part.strip('[] ')
            hit = names.get(clean.lower())
            if not hit:
                close = difflib.get_close_matches(clean.lower(), list(names), n=1, cutoff=0.88)
                hit = names[close[0]] if close else None
            if hit and hit != part:
                new = p.replace(f'["{part}"]', f'["{hit}"]', 1)
                if new not in have:
                    out.append((p, new, part, hit))
    return out


def rename_edits(fixes):
    """fixer's 'rename' edits: the wrong name -> the real one, everywhere it is quoted in the file (so the file's own rules that name it change too)."""
    out, seen = [], set()
    for _, _, wrong, real in fixes:
        if wrong not in seen:
            seen.add(wrong)
            out.append(('rename', wrong, real))
    return out


# ------------------------------------------------------------------ the guides' checks on a whole file (RDM, COR, BLU, DRK)
def file_checks(rows, ctx, loaded=None):
    """[(level, text)] for the job's own rules (gear_opt.file_checks adds the ones every file gets)."""
    job = ctx.job
    out = []
    judged = [r for r in rows if r.get('r') and r['judge'] == 'job']
    by_focus = {}
    for r in judged:
        by_focus.setdefault(r['r']['focus'], []).append(r)
    fc = [r for r in judged if r['r']['focus'].startswith('Fast cast') and r['path'].lower().rstrip('.') in ('sets.precast.fc', 'sets.precast.fc.standard')]
    for r in (fc[:1] if job not in ('COR', 'WAR', 'MNK', 'THF', 'SAM', 'DRG', 'DNC', 'RNG', 'PUP', 'BST') else []):
        n = r['r']['n_now']
        need = n.get('fast_cap', 80)
        if n.get('fast', 0) < need - 5:
            out.append(('warn', f"{r['path'][5:]}: Fast Cast {n.get('fast', 0)} % from gear; with {job}'s own {n.get('fast_job', 0)} % you can use "
                                f"{need} % (it stops at 80 %)."))
        elif n.get('fast', 0) > need:
            out.append(('warn', f"{r['path'][5:]}: Fast Cast {n.get('fast', 0)} % from gear, but {need} % is all that counts with {job}'s own "
                                f"{n.get('fast_job', 0)} %: the rest could be HP or damage taken."))
        else:
            out.append(('ok', f"{r['path'][5:]}: Fast Cast {n.get('fast', 0)} % from gear + {n.get('fast_job', 0)} % of your own: at the cap."))
    owned = set((ctx.counts or {}).keys())
    if job == 'RDM':
        boots = sorted(n for n in owned if n.lower().startswith(('viti. boots', 'vitiation boots')))
        enf = [r for g in ('Enfeebling (MND)', 'Enfeebling (INT)', 'Enfeebling (skill)', 'Enfeebling (accuracy)') for r in by_focus.get(g, [])]
        if boots and enf:
            without = [r for r in enf if not any(c and c['name'].lower().startswith(('viti. boots', 'vitiation boots')) for c in r['r']['cur'].values())]
            if without:
                out.append(('warn', f"{len(without)} enfeebling sets don't have your {boots[-1]} ({', '.join(r['path'][5:] for r in without[:4])}"
                                    f"{' ...' if len(without) > 4 else ''}): the Community RDM Guide puts them in every enfeebling set."))
        for r in by_focus.get('Enfeebling (skill)', []):
            n = r['r']['n_best']
            if n.get('enf_skill', 0):
                out.append(('ok', f"{r['path'][5:]}: Enfeebling skill +{n.get('enf_skill', 0)} from gear in the best set (Frazzle III stops at 625 skill, "
                                  "Distract III at 610, Poison at 500)."))
    if job == 'COR':
        rolls = by_focus.get('Phantom Roll', [])
        if rolls:
            best = max(r['r']['n_best'].get('pr', 0) for r in rolls)
            low = [r for r in rolls if r['r']['n_now'].get('pr', 0) < best]
            if low:
                out.append(('bad', f"{len(low)} roll sets don't have your best Phantom Roll +{best} piece ({', '.join(r['path'][5:] for r in low[:4])}"
                                   f"{' ...' if len(low) > 4 else ''}): it is the biggest part of every roll."))
            else:
                out.append(('ok', f"Every roll set has your best Phantom Roll +{best} piece."))
        for r in by_focus.get('Snapshot', [])[:1]:
            n = r['r']['n_now']
            out.append(('ok' if n.get('snap', 0) >= 60 else 'warn',
                        f"{r['path'][5:]}: Snapshot {n.get('snap', 0)} % from gear (60 % with 5/5 merits makes 70 %, Flurry II adds 30 %), "
                        f"Rapid Shot {n.get('rapid', 0)} %."))
        if 'Luzaf\'s Ring' in owned and not any('luzaf' in r['path'].lower() for r in rows):
            out.append(('warn', "You have Luzaf's Ring but no set for it: it doubles your rolls' range (8 to 16 yalms)."))
    if job == 'BLU':
        for r in by_focus.get('Blue magic: skill', [])[:1]:
            n = r['r']['n_best']
            out.append(('ok', f"{r['path'][5:]}: blue magic skill +{n.get('blue_skill', 0)} from gear in the best set; Occultation gives one shadow "
                              "for every 50 skill (600 = 12)."))
        for r in by_focus.get('Ability', []):
            if r['r']['n_now'].get('ja', 0) == 0 and r['r']['n_best'].get('ja', 0) > 0:
                out.append(('warn', f"{r['path'][5:]}: none of its gear boosts {r['r']['n_now'].get('ability') or 'the ability'}, and you own a piece that does."))
    if job == 'DRK':
        for r in by_focus.get('Dread Spikes', [])[:1]:
            n = r['r']['n_now']
            scythe = 'Crepuscular Scythe' in owned
            picked = ctx.weapons and any(c and c['name'] == 'Crepuscular Scythe' for c in ctx.weapons.values())
            out.append(('ok', f"{r['path'][5:]}: absorbs about {n.get('ds_absorb', 0)} HP (HP +{n.get('hp', 0)} from gear, potency +{n.get('ds_pot', 0)} %)."
                        + (" You have Crepuscular Scythe (+50 %): pick it under \"Make the sets with\" to make the set with it." if scythe and not picked else '')))
        for r in by_focus.get('Ability', []):
            if r['r']['n_now'].get('ja', 0) == 0 and r['r']['n_best'].get('ja', 0) > 0:
                out.append(('warn', f"{r['path'][5:]}: none of its gear boosts {r['r']['n_now'].get('ability') or 'the ability'}, and you own a piece that does."))
    return out


def rename_text(fixes):
    if not fixes:
        return ''
    return (f"{len(fixes)} set name(s) are not a spell or ability, so GearSwap never uses them: "
            + ', '.join(f'"{w}" (did you mean "{h}"?)' for _, _, w, h in fixes[:4]) + ('...' if len(fixes) > 4 else '') + ' "Fix the set names" renames them.')


