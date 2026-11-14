"""
GearSwap Doctor: every job's other sets (his request 2026-11-09: "instead of only finding what the best dps is when it does the scan and fixes, i want it to
look at the job and then make the sets best for the individual job by using ffxiah and ffxigi as a guide").

wsdist judges weapon skill, TP and nuke sets by damage; idle.py idle sets; pld.py a Paladin's tank sets; pup.py the automaton. Everything else a job wears
(fast cast, enhancing, enfeebling, songs, rolls, Quick Draw, Snapshot, Treasure Hunter, Blood Pacts, Ready, Geomancy, Blue Magic skill / cures / accuracy,
ability sets, Diffusion / Chain Affinity / Efflux ...) is judged here: what the set is for comes from its name and the job (focus_for), and each kind of set
has its points per stat and the game's caps (FOCUS). Numbers and sources: RESEARCH.md, "Every job's sets". Cures, Cursna, Regen and Waltz use healing.py's
formulas (the same as its Healing tab).

The points are my judgement from the guides' orders (BG Wiki's spell / ability pages, FFXIAH's job guides and forum posts): the caps are the game's.
  Fast Cast        gear up to 80 % less what the job has (RDM 38, /RDM 15); song / enhancing / elemental casting time share the cap
  Snapshot         70 % in all; 10 from 5/5 merits, so 60 from gear (RNG, COR). Rapid Shot has no cap.
  Treasure Hunter  THF 8 in all (its traits give 3 at 99, so 5 from gear), other jobs 4 (BG Wiki)
  Phantom Roll     only the highest "Phantom Roll +n" counts (BG Wiki); then duration; Lanun Tricorne's "effects +50" = the job-bonus chance
  Blood Pact delay I and II stop at -15 each (BG Wiki)
  Magic burst      gear stops at 40 % (MBB II goes past it)
  Enhancing        duration first; Stoneskin, Temper, Enspells, Barspells and Phalanx get stronger with skill (capped at 500 for most)
"""
import os
import re

import checks
import fixer
import healing

# ------------------------------------------------------------------ what the item text says that the other modules don't read
RX = [(k, re.compile(rx)) for k, rx in [
    ('pr', r'"Phantom Roll" ?\+ ?(\d+)(?! *%)|(?<!")Phantom Roll ?\+(\d+)'), ('pr_dur', r'"Phantom Roll" effect duration ?\+ ?(\d+)'),
    ('pr_job', r'"Phantom Roll" effects \+(\d+)'), ('pr_delay', r'"Phantom Roll" (?:ability )?delay ?-(\d+)'),
    ('enf_eff', r'Enfeebling magic effect ?\+(\d+)'), ('enf_dur', r'Enfeebling magic (?:effect )?duration ?\+(\d+)'), ('macc_skill', r'Magic Accuracy skill ?\+(\d+)'),
    ('cast_enh', r'Enhancing magic (?:spell)?casting time ?-(\d+)'), ('cast_ele', r'Elemental magic (?:spell)?casting time ?-(\d+)'),
    ('cast_dark', r'Dark magic (?:spell)?casting time ?-(\d+)'), ('cast_blue', r'Blue magic (?:spell)?casting time ?-(\d+)'),
    ('cast_enf', r'Enfeebling magic (?:spell)?casting time ?-(\d+)'), ('cast_utsu', r'"?Utsusemi"? (?:spell)?casting time ?-(\d+)'),
    ('cast_ss', r'"?Stoneskin"? (?:spell)?casting time ?-(\d+)'), ('cast_geo', r'Geomancy (?:spell)?casting time ?-(\d+)'),
    ('enh_dur2', r'Enh\. Mag\. eff\. dur\. ?\+(\d+)'), ('refresh_pot', r'"Refresh" potency ?\+(\d+)'), ('ss', r'"Stoneskin" ?\+(\d+)'),
    ('crit_dmg', r'Critical hit damage ?\+(\d+)'), ('bp_dmg', r'"Blood Pact" damage ?\+(\d+)'), ('ready_delay', r'"Ready" (?:ability )?delay ?-(\d+)|Ready recast ?-(\d+)'),
    ('ready_tp', r'"Ready" TP Bonus ?\+(\d+)'), ('song_recast', r'Song recast delay ?-(\d+)'), ('nin_recast', r'Ninjutsu recast delay ?-(\d+)'),
    ('utsu', r'"Utsusemi" ?\+(\d+)'), ('step_acc', r'"Steps?" accuracy ?\+(\d+)'), ('jump_tp', r'Jumps? TP Bonus ?\+(\d+)|"Jump" TP Bonus ?\+(\d+)'),
    ('ds_pot', r'"Dread Spikes" (?:potency|absorption|effect) ?\+(\d+)%'), ('absorbtp', r'"Absorb-TP" (?:effect|absorbed) ?\+(\d+)'),
    ('absorb_pot', r'"Absorb" effect ?\+(\d+)%'),
    ('absorb_dur', r'"Absorb" effect duration ?\+(\d+)'), ('crit', r'Critical hit rate ?\+(\d+)'), ('charm', r'"Charm" ?\+(\d+)'), ('blue_cast_fast', r'Blue magic spellcasting time ?-(\d+)'),
]]
# a word in quotes that is a stat, not an ability (so it doesn't count as "boosts the ability")
NOT_ABILITY = {'fast cast', 'refresh', 'regen', 'store tp', 'double attack', 'triple attack', 'dual wield', 'magic atk. bonus', 'magic def. bonus',
               'treasure hunter', 'snapshot', 'rapid shot', 'subtle blow', 'subtle blow ii', 'cure', 'conserve mp', 'counter', 'recycle', 'zanshin',
               'kick attacks', 'martial arts', 'skillchain bonus', 'occ. quickens spellcasting', 'mag. atk. bns.', 'm. def. b.', 'drain', 'aspir',
               'regain', 'dbl. atk.', 'triple atk.', 'quadruple attack', 'blood pact', 'fencer', 'conserve tp', 'resist', 'stoneskin', 'phalanx',
               'magic burst damage', 'save tp', 'quick magic', 'store tp ii'}
QUOTE_RX = re.compile(r'"([^"]{3,40})"(?:[^"+\-\n|]{0,26}?)?(?:\s*([+\-])\s*(\d+))?')


def parse(text):
    """{stat: value}: the job-set stats of an item's text or one augment that healing.parse_text, gs_create.parse and pld.parse don't read."""
    cut = healing.CUT_RX.search(text)
    own = text[:cut.start()] if cut else text
    out = {}
    for k, rx in RX:
        n = sum(int(y) for x in rx.findall(own) for y in (x if isinstance(x, tuple) else (x,)) if y)
        if n:
            out[k] = n
    if 'enh_dur2' in out:                                   # (Telchine's augment "Enh. Mag. eff. dur. +10": counted as duration %)
        out['enh_dur'] = out.get('enh_dur', 0) + out.pop('enh_dur2')
    if 'Enhances "Aquaveil"' in own or '"Aquaveil" +' in own:
        out['aquaveil'] = 1
    if 'Enhances "Fast Cast" effect' in own and 'fast' not in healing.parse_text(text):      # (90 older pieces give no number: Loquac. Earring ...)
        out['fast'] = 2
    return out


# "Enhances Fast Cast effect" with no number: BG Wiki's values where they differ from the 2 % counted for the rest
FAST_NAMED = {'witful belt': 3, 'swith cape': 3, 'swith cape +1': 4}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def quoted(text):
    """{ability (normalised): n} for the abilities an item's own text names: 'Enhances "Diffusion" effect' -> {'diffusion': 1}; '"Chain Affinity"+24' -> 24."""
    cut = healing.CUT_RX.search(text or '')
    own = (text or '')[:cut.start()] if cut else (text or '')
    out = {}
    for name, sign, n in QUOTE_RX.findall(own):
        if name.lower() in NOT_ABILITY:
            continue
        k = norm(name)
        out[k] = max(out.get(k, 0), int(n) if n and sign == '+' else 1)
    return out


def boosts(c, ability):
    """How much an item boosts this ability (0: not at all). 'Samba' gear boosts Haste Samba; 'Step' gear any Step."""
    a = norm(ability)
    if not a:
        return 0
    q = c.get('quoted') or {}
    if a in q:
        return q[a]
    names = (c.get('name') or '').lower(), (c.get('enl') or '').lower()
    for piece, ab in RELIC.items():                 # (a relic whose text doesn't name the ability: its hidden augment does)
        if norm(ab) == a and any(n.startswith(piece) for n in names):
            return 1
    for fam in FAMILY:
        if a.endswith(fam) and fam in q:
            return q[fam]
    return 0


# relic pieces that boost an ability with a hidden augment, so their item text doesn't say so (2026-11-10 research: BG Wiki Community Blue Mage Guide,
# Community Corsair Guide). PLD's are in pld.JA_GEAR.
RELIC = {'luhlaza charuqs': 'Diffusion', 'luh. charuqs': 'Diffusion', 'luhlaza bazubands': 'Azure Lore', 'luh. bazubands': 'Azure Lore',
         'lanun bottes': 'Wild Card', 'lanun trews': 'Snake Eye', 'lanun gants': 'Fold'}

FAMILY = ('samba', 'step', 'steps', 'jig', 'jump', 'waltz', 'flourish', 'flourishes', 'maneuver', 'roll', 'rune', 'ward', 'effusion')

# ------------------------------------------------------------------ the game's lists
_SPELLS = _ABILS = None
SKILL = {32: 'divine', 33: 'healing', 34: 'enhancing', 35: 'enfeebling', 36: 'elemental', 37: 'dark', 38: 'summoning', 39: 'ninjutsu', 40: 'singing',
         43: 'blue', 44: 'geomancy'}


def spells():
    """{normalised spell name: (name, skill kind, targets)} from Windower's res\\spells.lua."""
    global _SPELLS
    if _SPELLS is None:
        _SPELLS = {}
        rx = re.compile(r'en="([^"]+)".*?\bskill=(\d+).*?\btargets=(\d+)')
        try:
            for line in open(os.path.join(checks.WINDOWER, 'res', 'spells.lua'), encoding='utf-8'):
                m = rx.search(line)
                if m:
                    _SPELLS.setdefault(norm(m.group(1)), (m.group(1), SKILL.get(int(m.group(2))), int(m.group(3))))
        except OSError:
            pass
    return _SPELLS


def abilities():
    """{normalised name: name} of every job ability (res\\job_abilities.lua)."""
    global _ABILS
    if _ABILS is None:
        _ABILS = {}
        try:
            for n in re.findall(r'\ben="([^"]+)"', open(os.path.join(checks.WINDOWER, 'res', 'job_abilities.lua'), encoding='utf-8').read()):
                _ABILS.setdefault(norm(n), n)
        except OSError:
            pass
    return _ABILS


# ------------------------------------------------------------------ what each kind of set is judged by
# pts: points for one of each stat (after its cap); show: what the words list; how: one line on what matters (from the guides)
_DT = {'phys': 0.3, 'magic': 0.3}
FOCUS = {
    'Fast cast': {'pts': {'fast': 10, 'quick': 3, 'phys': 0.2, 'magic': 0.2, 'HP': 0.002, 'MP': 0.002}, 'show': ['fast', 'quick'],
                  'how': 'Fast Cast up to the 80 % cap (with what your job gives), then Quick Magic. Past the cap does nothing.'},
    'Fast cast: songs': {'pts': {'fast': 10, 'quick': 2, 'phys': 0.2, 'magic': 0.2}, 'show': ['fast'], 'cast': ('song_fast',),
                         'how': 'Fast Cast + song casting time, one cap of 80 %.'},
    'Fast cast: enhancing': {'pts': {'fast': 10, 'quick': 3, 'phys': 0.2, 'magic': 0.2}, 'show': ['fast'], 'cast': ('cast_enh', 'cast_ss'),
                             'how': 'Fast Cast + enhancing / Stoneskin casting time, one cap of 80 %.'},
    'Fast cast: elemental': {'pts': {'fast': 10, 'quick': 3, 'phys': 0.2, 'magic': 0.2}, 'show': ['fast'], 'cast': ('cast_ele',),
                             'how': 'Fast Cast + elemental casting time, one cap of 80 %. Impact keeps its cloak.'},
    'Fast cast: Utsusemi': {'pts': {'fast': 10, 'quick': 2, 'phys': 0.5, 'magic': 0.5}, 'show': ['fast', 'phys'], 'cast': ('cast_utsu',),
                            'how': 'Fast Cast + Utsusemi casting time, one cap of 80 %; you are being hit, so damage taken next.'},
    'Fast cast: blue magic': {'pts': {'fast': 10, 'quick': 3, 'phys': 0.2, 'magic': 0.2}, 'show': ['fast'], 'cast': ('cast_blue', 'blue_cast_fast'),
                              'how': 'Fast Cast + blue magic casting time, one cap of 80 %.'},
    'Fast cast: geomancy': {'pts': {'fast': 10, 'quick': 3, 'phys': 0.2, 'magic': 0.2}, 'show': ['fast'], 'cast': ('cast_geo',),
                            'how': 'Fast Cast + geomancy casting time, one cap of 80 %.'},
    'Spell recast': {'pts': {'fast': 4, 'haste': 4, 'sird': 0.5, 'conserve': 0.3, 'phys': 0.5, 'magic': 0.5}, 'show': ['fast', 'haste', 'phys'],
                     'how': 'Fast Cast and gear haste both cut the recast (gear haste stops at 25 %); then damage taken.'},
    'Spell, not interrupted': {'pts': {'sird': 6, 'phys': 2, 'magic': 2, 'enmity': 0.5, 'HP': 0.02}, 'show': ['sird', 'phys'],
                               'how': 'Spell interruption down (102 % with 5/5 merits means never), then damage taken.'},
    # enhancing (BG Wiki Enhancing_Magic: duration gear multiplies; most skill-based spells stop at 500 skill)
    'Enhancing duration': {'pts': {'enh_dur': 8, 'enh_skill': 0.5, 'conserve': 0.3, 'fast': 0.5, 'MND': 0.05}, 'show': ['enh_dur', 'enh_skill'],
                           'how': 'Enhancing magic duration first (Haste, Flurry, Protect, Shell, Refresh on others ...); skill does nothing for these.'},
    'Enhancing skill': {'pts': {'enh_skill': 3, 'enh_dur': 2, 'conserve': 0.2, 'MND': 0.1}, 'show': ['enh_skill', 'enh_dur'],
                        'how': 'Enhancing magic skill (Temper, Enspells, Gain, Barspells get stronger with it, most stop at 500), then duration.'},
    'Barspells': {'pts': {'enh_skill': 3, 'enh_dur': 2, 'MND': 0.1, 'bar': 30}, 'show': ['enh_skill', 'enh_dur'],
                  'how': 'Enhancing magic skill (the resistance grows with it), then duration.'},
    'Refresh (cast)': {'pts': {'refresh_pot': 40, 'enh_dur': 8, 'enh_skill': 0.2, 'fast': 0.3}, 'show': ['refresh_pot', 'enh_dur'],
                       'how': 'Refresh potency gear first (each +1 is 1 more MP a tick), then enhancing duration.'},
    'Stoneskin': {'pts': {'ss': 2, 'enh_skill': 1, 'MND': 2, 'enh_dur': 0.3, 'sird': 0.5, 'conserve': 0.2}, 'show': ['ss', 'enh_skill', 'MND'],
                  'how': 'Stoneskin +n gear, MND (x3 for the cap) and Enhancing skill; it stops at 350 HP absorbed.'},
    'Aquaveil': {'pts': {'aquaveil': 40, 'sird': 5, 'enh_dur': 2, 'enh_skill': 0.2}, 'show': ['aquaveil', 'sird'],
                 'how': 'Aquaveil gear (an extra interruption it blocks), then spell interruption down and duration.'},
    'Phalanx': {'pts': {'phalanx': 30, 'enh_skill': 1, 'enh_dur': 2, 'phys': 0.5, 'magic': 0.5}, 'show': ['phalanx', 'enh_skill', 'enh_dur'],
                'how': 'Phalanx +n gear, then Enhancing skill (1 more a hit about every 28 skill above 300, to 500), then duration.'},
    # enfeebling (BG Wiki: a resisted spell does nothing; magic accuracy first, then skill and the stat the spell uses)
    'Enfeebling (MND)': {'pts': {'macc': 2, 'enf_skill': 1.5, 'MND': 1.2, 'enf_eff': 4, 'enf_dur': 2, 'macc_skill': 1.5}, 'show': ['macc', 'enf_skill', 'MND'],
                         'how': 'Magic accuracy, Enfeebling skill and MND (Slow, Paralyze, Silence, Addle, Distract, Frazzle); enfeebling effect gear next.'},
    'Enfeebling (INT)': {'pts': {'macc': 2, 'enf_skill': 1.5, 'INT': 1.2, 'enf_eff': 4, 'enf_dur': 2, 'macc_skill': 1.5}, 'show': ['macc', 'enf_skill', 'INT'],
                         'how': 'Magic accuracy, Enfeebling skill and INT (Blind, Gravity, Sleep, Bind, Break, Poison, Dispel).'},
    'Enfeebling (skill)': {'pts': {'enf_skill': 3, 'macc': 1, 'MND': 0.5, 'enf_eff': 5, 'macc_skill': 1}, 'show': ['enf_skill', 'macc'],
                           'how': 'Enfeebling skill first: Distract III, Frazzle III, Poison II and the like get stronger with it.'},
    'Enfeebling (accuracy)': {'pts': {'macc': 3, 'enf_skill': 2, 'MND': 0.6, 'INT': 0.6, 'macc_skill': 2, 'enf_dur': 1}, 'show': ['macc', 'enf_skill'],
                              'how': 'Landing it: magic accuracy and Enfeebling skill (sets for tough monsters, Dia / Bio, Inundation).'},
    'Elemental enfeeble': {'pts': {'macc': 2, 'INT': 1.5, 'ele_skill': 1.5, 'macc_skill': 1}, 'show': ['macc', 'INT', 'ele_skill'],
                           'how': 'Burn, Choke, Frost ...: INT and magic accuracy, Elemental skill.'},
    'Impact': {'pts': {'macc': 2.5, 'INT': 1, 'ele_skill': 0.5, 'enf_skill': 0.5, 'dark_skill': 0.3, 'macc_skill': 1}, 'show': ['macc', 'INT'],
               'how': 'Impact (its cloak kept): magic accuracy first, it lowers every stat of the monster.'},
    # dark magic
    'Drain and Aspir': {'pts': {'drain': 6, 'dark_skill': 2, 'macc': 1, 'INT': 0.3, 'fast': 0.2}, 'show': ['drain', 'dark_skill', 'macc'],
                        'how': '"Drain" and "Aspir" potency first, then Dark magic skill (they drain more with it), magic accuracy.'},
    'Absorb': {'pts': {'macc': 3, 'dark_skill': 1.5, 'absorb_dur': 2, 'absorb_pot': 2, 'INT': 0.4, 'macc_skill': 2}, 'show': ['macc', 'dark_skill', 'absorb_dur'],
               'how': 'Absorb spells: magic accuracy (a resist takes nothing), Dark skill, Absorb duration.'},
    'Stun': {'pts': {'macc': 3, 'dark_skill': 1.5, 'INT': 0.3, 'fast': 1, 'haste': 1, 'macc_skill': 2}, 'show': ['macc', 'dark_skill', 'fast'],
             'how': 'Stun: magic accuracy and Dark skill; Fast Cast and haste make it ready again sooner.'},
    'Dread Spikes': {'pts': {'ds_absorb': 0.05, 'phys': 1, 'magic': 0.5, 'fast': 0.1}, 'show': ['ds_absorb', 'hp', 'ds_pot'],
                     'how': 'Dread Spikes absorbs up to your max HP when cast x 0.5 x (1 + Dread Spikes potency): Heathen\'s Cuirass +3 +55 %, '
                            'Crepuscular Scythe +50 % (BG Wiki). Max HP and potency first.'},
    'Absorb-TP': {'pts': {'absorbtp': 4, 'macc': 3, 'dark_skill': 1, 'absorb_pot': 2, 'macc_skill': 2, 'INT': 0.3}, 'show': ['absorbtp', 'macc', 'dark_skill'],
                  'how': '"Absorb-TP" effect (Heathen\'s Gauntlets +3 +30 %), then magic accuracy and Dark magic skill.'},
    'Dark magic': {'pts': {'dark_skill': 3, 'macc': 1, 'INT': 0.3}, 'show': ['dark_skill', 'macc'], 'how': 'Dark magic skill (Endark, Bio, Dread Spikes ...).'},
    # divine / enmity
    'Flash': {'pts': {'enmity': 4, 'macc': 1.5, 'div_skill': 1, 'phys': 0.5, 'magic': 0.5}, 'show': ['enmity', 'macc'],
              'how': 'Flash for hate: enmity +, magic accuracy so it lands.'},
    'Enmity': {'pts': {'enmity': 5, 'phys': 1.5, 'magic': 1.5, 'HP': 0.02, 'sird': 0.3}, 'show': ['enmity', 'phys', 'magic'],
               'how': 'Enmity +, then damage taken (you hold hate, so you are hit).'},
    # songs (BG Wiki: All songs +n raises every song; duration %; dummy songs must be short so a real song never gets knocked off - RESEARCH.md "Bard songs")
    'Songs: buff': {'pts': {'songs': 40, 'song_one': 40, 'song_dur': 6, 'sing': 0.3, 'instr': 0.3, 'CHR': 0.2, 'phys': 0.2, 'magic': 0.2},
                    'show': ['songs', 'song_one', 'song_dur'],
                    'how': 'All songs +n and the song\'s own +n first (each step makes it stronger), then song duration. Instruments (range slot) aren\'t changed here.'},
    'Songs: enfeeble': {'pts': {'macc': 2, 'CHR': 1.2, 'sing': 1, 'instr': 0.8, 'songs': 8, 'song_one': 8, 'song_dur': 3}, 'show': ['macc', 'CHR', 'sing'],
                        'how': 'Lullaby, Elegy, Threnody, Finale: magic accuracy, CHR and Singing / instrument skill; All songs +n makes Lullaby last longer.'},
    'Songs: dummy': {'pts': {'fast': 2, 'song_fast': 2, 'phys': 1, 'magic': 1, 'song_dur': -10, 'songs': -2}, 'show': ['song_dur', 'phys'],
                     'how': 'A dummy song is overwritten first: it must be SHORT (no song duration gear), so damage taken and fast cast instead.'},
    # ranged
    'Snapshot': {'pts': {'snap': 6, 'rapid': 3, 'racc': 0.02, 'phys': 0.1}, 'show': ['snap', 'rapid'],
                 'how': 'Snapshot to 70 % (5/5 merits give 10, so 60 from gear), then Rapid Shot (no cap).'},
    'Ranged shots': {'pts': {'racc': 1, 'ratt': 0.5, 'AGI': 0.5, 'stp': 3, 'recycle': 0.5, 'trueshot': 2, 'crit_dmg': 0.3, 'phys': 0.3, 'magic': 0.3},
                     'show': ['racc', 'ratt', 'stp'],
                     'how': 'Shooting for TP: Store TP, ranged accuracy, then attack and AGI, True Shot; your gun / bow and ammo stay.'},
    'Ranged shots: accuracy': {'pts': {'racc': 2, 'ratt': 0.3, 'AGI': 0.6, 'stp': 1.5, 'trueshot': 1, 'phys': 0.2, 'magic': 0.2}, 'show': ['racc', 'stp'],
                               'how': 'Hitting a tough monster: ranged accuracy first, then Store TP.'},
    'Ranged shots: critical': {'pts': {'crit': 6, 'crit_dmg': 3, 'racc': 0.8, 'ratt': 0.5, 'AGI': 0.5, 'stp': 1, 'phys': 0.2, 'magic': 0.2}, 'show': ['crit', 'crit_dmg', 'racc'],
                               'how': 'Critical hit rate and damage (with Triple Shot / Hover Shot crits), then ranged accuracy.'},
    'Phantom Roll': {'pts': {'pr': 30, 'pr_dur': 0.4, 'pr_job': 0.3, 'pr_delay': 1, 'ja': 40, 'phys': 0.2, 'magic': 0.2}, 'show': ['pr', 'pr_dur', 'ja'],
                     'how': 'Only the highest "Phantom Roll +n" counts (BG Wiki), then roll duration; Lanun Tricorne gives the job bonus chance.'},
    'Quick Draw: damage': {'pts': {'qd': 3, 'matk': 3, 'mdmg': 1.5, 'macc': 1, 'AGI': 0.5, 'ja': 20}, 'show': ['qd', 'matk', 'macc'],
                           'how': 'Quick Draw damage and Magic Atk. Bonus (it is a magic shot), then magic accuracy and AGI.'},
    'Quick Draw: accuracy': {'pts': {'macc': 3, 'AGI': 1, 'qd': 0.3, 'ja': 20}, 'show': ['macc', 'AGI'],
                             'how': 'Light / Dark Shot only land: magic accuracy and AGI (BG Wiki: Marksmanship skill does not count).'},
    'Treasure Hunter': {'pts': {'th': 100, 'phys': 0.3, 'magic': 0.3, 'acc': 0.01}, 'show': ['th', 'phys'],
                        'how': 'Treasure Hunter: THF stops at 8 (traits 3 + gear 5), other jobs at 4 from gear (BG Wiki). Only its own slots change.'},
    # pets
    'Blood Pact delay': {'pts': {'bp1': 20, 'bp2': 20, 'smn_skill': 0.1, 'phys': 0.1}, 'show': ['bp1', 'bp2'],
                         'how': 'Blood Pact delay I and II: -15 each at most (BG Wiki).'},
    'Blood Pact: physical': {'pts': {'ava_att': 2, 'ava_acc': 1.5, 'ava_lvl': 40, 'ava_da': 6, 'ava_crit': 4, 'bp_dmg': 3, 'smn_skill': 0.3}, 'show': ['ava_att', 'ava_acc', 'bp_dmg'],
                             'how': 'Avatar: attack, accuracy, level, double attack, crits; Blood Pact damage.'},
    'Blood Pact: magic': {'pts': {'ava_matk': 3, 'ava_macc': 1.5, 'ava_lvl': 40, 'bp_dmg': 3, 'smn_skill': 0.3}, 'show': ['ava_matk', 'ava_macc', 'bp_dmg'],
                          'how': 'Avatar: Magic Atk. Bonus, magic accuracy, level; Blood Pact damage.'},
    'Blood Pact: accuracy': {'pts': {'ava_macc': 3, 'smn_skill': 2, 'ava_lvl': 40}, 'show': ['ava_macc', 'smn_skill'],
                             'how': 'Avatar enfeebling pacts: the avatar\'s magic accuracy and Summoning skill.'},
    'Blood Pact: skill': {'pts': {'smn_skill': 3, 'ava_lvl': 10, 'MP': 0.01}, 'show': ['smn_skill'],
                          'how': 'Ward pacts get stronger and last longer with Summoning skill.'},
    'Ready: physical': {'pts': {'pet_att': 2, 'pet_acc': 1.5, 'pet_lvl': 40, 'pet_da': 5, 'pet_haste': 3, 'ready_tp': 0.05}, 'show': ['pet_att', 'pet_acc'],
                        'how': 'Pet: attack, accuracy, level, double attack; Ready TP bonus.'},
    'Ready: magic': {'pts': {'pet_matk': 3, 'pet_macc': 1.5, 'pet_lvl': 40, 'ready_tp': 0.05}, 'show': ['pet_matk', 'pet_macc'],
                     'how': 'Pet: Magic Atk. Bonus, magic accuracy, level.'},
    'Ready recast': {'pts': {'ready_delay': 20, 'phys': 0.2, 'magic': 0.2}, 'show': ['ready_delay'], 'how': 'Ready / Sic recast down.'},
    'Geocolure': {'pts': {'geomancy': 30, 'geo_skill': 2, 'bell': 2, 'conserve': 0.5, 'fast': 0.1}, 'show': ['geomancy', 'geo_skill', 'bell'],
                  'how': 'Geomancy +n (Dunna, Idris) and Geomancy / Handbell skill (Luopan potency grows with it, to 900 in all).'},
    'Indicolure': {'pts': {'geomancy': 30, 'indi_dur': 3, 'geo_skill': 2, 'bell': 2, 'conserve': 0.3}, 'show': ['geomancy', 'indi_dur', 'geo_skill'],
                   'how': 'Geomancy +n and skill like a Geo- spell, plus Indicolure duration.'},
    # ninjutsu
    'Utsusemi': {'pts': {'utsu': 40, 'fast': 1, 'haste': 1, 'nin_recast': 2, 'phys': 1, 'magic': 0.5}, 'show': ['utsu', 'fast', 'phys'],
                 'how': 'Utsusemi +n (one more shadow), then recast: Fast Cast and haste.'},
    'Ninjutsu enfeeble': {'pts': {'macc': 2.5, 'nin_skill': 2, 'INT': 0.3, 'macc_skill': 2}, 'show': ['macc', 'nin_skill'],
                          'how': 'Kurayami, Hojo, Aisha, Yurin, Jubaku: magic accuracy and Ninjutsu skill.'},
    'Ninjutsu damage': {'pts': {'matk': 3, 'nin_dmg': 1.5, 'mdmg': 1.5, 'INT': 1, 'macc': 1, 'nin_skill': 1}, 'show': ['matk', 'nin_dmg', 'macc'],
                        'how': 'Katon, Doton, Raiton ...: Magic Atk. Bonus, Ninjutsu damage, INT, magic accuracy; Ninjutsu skill a little.'},
    'Ninjutsu burst': {'pts': {'mbb': 12, 'mbb2': 16, 'matk': 3, 'nin_dmg': 1.5, 'mdmg': 1.5, 'INT': 1, 'macc': 1, 'nin_skill': 1}, 'show': ['mbb', 'matk', 'macc'],
                       'how': 'Magic burst damage first (40 % cap from gear, II past it), then as a nuke.'},
    'Ninjutsu skill': {'pts': {'nin_skill': 3, 'macc': 0.3, 'enmity': 0.5}, 'show': ['nin_skill'],
                       'how': 'Migawari, Gekka, Yain, Kakka, Myoshu: Ninjutsu skill.'},
    # blue magic (wsdist does the damage spells: magic.py)
    'Blue magic: skill': {'pts': {'blue_skill': 3, 'fast': 0.2, 'conserve': 0.2, 'phys': 0.2, 'magic': 0.2}, 'show': ['blue_skill'],
                          'how': 'Diamondhide, Metallic Body, Occultation, Magic Barrier, Barrier Tusk ...: Blue magic skill makes them stronger.'},
    'Blue magic: White Wind': {'pts': {'hp': 0.06, 'potency': 3, 'MND': 0.2, 'enmity_down': 0.5, 'phys': 0.3, 'magic': 0.3}, 'show': ['hp', 'potency'],
                               'how': 'White Wind heals by your max HP (party, AoE): HP first, then Cure potency.'},
    'Blue magic: cures': {'pts': {'potency': 8, 'MND': 1, 'VIT': 0.3, 'blue_skill': 0.5, 'enmity_down': 0.5, 'received': 0}, 'show': ['potency', 'MND'],
                          'how': 'Cure potency (to 50 %), MND, then Blue magic skill (Magic Fruit, Wild Carrot, Healing Breeze, White Wind ...).'},
    'Blue magic: accuracy': {'pts': {'macc': 3, 'blue_skill': 1.5, 'MND': 0.3, 'INT': 0.3, 'CHR': 0.2, 'macc_skill': 2}, 'show': ['macc', 'blue_skill'],
                             'how': 'Sleep, Stun and other enfeebling blue magic: magic accuracy and Blue magic skill.'},
    'Blue magic: buffs': {'pts': {'conserve': 1, 'fast': 1, 'haste': 1, 'blue_skill': 0.3, 'phys': 1, 'magic': 1}, 'show': ['fast', 'phys'],
                          'how': 'Buff spells (Cocoon, Erratic Flutter, Mighty Guard, Battery Charge ...): duration is fixed, so fast recast and damage taken.'},
    'Conserve MP': {'pts': {'conserve': 6, 'phys': 0.3, 'magic': 0.3}, 'show': ['conserve'], 'how': 'Conserve MP.'},
    # abilities: the pieces that boost it (their text names it), damage taken in the rest
    'Ability': {'pts': {'ja': 60, 'jan': 0.5, 'phys': 0.4, 'magic': 0.4}, 'show': ['ja'],
                'how': 'The gear that boosts the ability (its text names it); the other slots stay as they are.'},
    'Steps': {'pts': {'step_acc': 2, 'acc': 1, 'DEX': 0.3, 'ja': 30}, 'show': ['step_acc', 'acc'], 'how': 'Steps land on accuracy: Step accuracy, accuracy, then Step gear.'},
    'Violent Flourish': {'pts': {'macc': 2, 'acc': 0.8, 'CHR': 1, 'ja': 30}, 'show': ['macc', 'CHR'], 'how': 'Violent Flourish (a stun): magic accuracy and CHR.'},
    'Jump': {'pts': {'jump_tp': 0.1, 'acc': 1, 'att': 0.8, 'stp': 2, 'ja': 30, 'VIT': 0.3}, 'show': ['acc', 'att', 'jump_tp'],
             'how': 'A jump is an attack: accuracy, attack, Store TP, jump TP bonus.'},
    'Sneak Attack': {'pts': {'DEX': 1.5, 'crit_dmg': 3, 'att': 0.4, 'ja': 30}, 'show': ['DEX', 'crit_dmg'],
                     'how': 'Sneak Attack is a sure critical hit with DEX added: DEX and critical hit damage.'},
    'Trick Attack': {'pts': {'AGI': 1.5, 'crit_dmg': 3, 'att': 0.4, 'ja': 30}, 'show': ['AGI', 'crit_dmg'],
                     'how': 'Trick Attack adds AGI: AGI and critical hit damage.'},
    'Doom': {'pts': {'holy_water': 6, 'cursna_rec': 6, 'phys': 0.3, 'magic': 0.3}, 'show': ['holy_water', 'cursna_rec'],
             'how': 'Holy Water + and Cursna received + (removing Doom).'},
    'Charm': {'pts': {'charm': 3, 'CHR': 1, 'ja': 30}, 'show': ['charm', 'CHR'], 'how': 'Charm + and CHR.'},
}
for _k, _v in list(FOCUS.items()):
    _v.setdefault('caps', {})

# the cures, Cursna, Regen and Waltz are healing.py's (its formulas): what they're called here -> healing's kind
HEALING = {'Cure': 'cure', 'Curaga': 'curaga', 'Cure (yourself)': 'selfcure', 'Cure received': 'received', 'Fast cast: cures': 'precast',
           'Cursna': 'cursna', 'Regen': 'regen', 'Waltz': 'waltz'}
for _k, _kind in HEALING.items():
    FOCUS[_k] = {'pts': {}, 'show': [], 'caps': {}, 'healing': _kind, 'how': healing.KINDS[_kind]['how']}

LABEL = {'fast': 'Fast Cast', 'quick': 'Quick Magic', 'haste': 'gear haste', 'sird': 'interruption down', 'conserve': 'Conserve MP', 'phys': 'physical damage taken',
         'magic': 'magic damage taken', 'enmity': 'enmity', 'enh_dur': 'enhancing duration', 'enh_skill': 'Enhancing skill', 'refresh_pot': 'Refresh potency',
         'ss': 'Stoneskin', 'MND': 'MND', 'INT': 'INT', 'CHR': 'CHR', 'AGI': 'AGI', 'DEX': 'DEX', 'VIT': 'VIT', 'aquaveil': 'Aquaveil gear', 'phalanx': 'Phalanx',
         'macc': 'magic accuracy', 'enf_skill': 'Enfeebling skill', 'ele_skill': 'Elemental skill', 'drain': 'Drain / Aspir potency', 'dark_skill': 'Dark skill',
         'absorb_dur': 'Absorb duration', 'ds_absorb': 'Dread Spikes absorbs (HP)', 'ds_pot': 'Dread Spikes potency', 'absorbtp': '"Absorb-TP" effect',
         'absorb_pot': '"Absorb" effect', 'hp': 'HP', 'HP': 'HP', 'div_skill': 'Divine skill', 'songs': 'All songs', 'song_one': "the song's own", 'song_dur': 'song duration',
         'sing': 'Singing skill', 'snap': 'Snapshot', 'rapid': 'Rapid Shot', 'racc': 'ranged accuracy', 'ratt': 'ranged attack', 'stp': 'Store TP',
         'pr': 'Phantom Roll', 'pr_dur': 'roll duration', 'ja': 'pieces for it', 'qd': 'Quick Draw damage', 'matk': 'Magic Atk. Bonus', 'th': 'Treasure Hunter',
         'bp1': 'Blood Pact delay', 'bp2': 'Blood Pact delay II', 'ava_att': 'avatar attack', 'ava_acc': 'avatar accuracy', 'bp_dmg': 'Blood Pact damage',
         'ava_matk': 'avatar Magic Atk. Bonus', 'ava_macc': 'avatar magic accuracy', 'smn_skill': 'Summoning skill', 'pet_att': 'pet attack', 'pet_acc': 'pet accuracy',
         'pet_matk': 'pet Magic Atk. Bonus', 'pet_macc': 'pet magic accuracy', 'ready_delay': 'Ready recast', 'geomancy': 'Geomancy +', 'geo_skill': 'Geomancy skill',
         'bell': 'Handbell skill', 'indi_dur': 'Indicolure duration', 'utsu': 'Utsusemi +', 'nin_skill': 'Ninjutsu skill', 'blue_skill': 'Blue magic skill',
         'potency': 'Cure potency', 'step_acc': 'Step accuracy', 'acc': 'accuracy', 'att': 'attack', 'jump_tp': 'jump TP bonus', 'crit_dmg': 'critical hit damage',
         'crit': 'critical hit rate', 'holy_water': 'Holy Water', 'cursna_rec': 'Cursna received', 'charm': 'Charm', 'mbb': 'Magic burst damage', 'nin_dmg': 'Ninjutsu damage'}
PCT = {'ds_pot', 'absorbtp', 'absorb_pot', 'crit', 'fast', 'quick', 'haste', 'sird', 'phys', 'magic', 'enh_dur', 'song_dur', 'snap', 'potency', 'crit_dmg', 'indi_dur'}


# ------------------------------------------------------------------ what a set is for
def _words(path):
    return [p.lower() for p in fixer._path_parts(path or '')]


SMALL = ('capacity', 'capacitymantle', 'sheltered', 'organizer', 'reraise', 'learning', 'kiting', 'latent_refresh', 'latent_regen', 'hpdown', 'twilight', 'mp',
         'element', 'weapons', 'dwearrings', 'dwmax', 'wsdaybonus', 'maxtp', 'accmaxtp', 'charm', 'death', 'sleep', 'self_refresh', 'self_waltz', 'recovermp',
         'skillchain', 'naked', 'crafting', 'fishing', 'town', 'luzaf', 'warp', 'buff_sleep')
ENMITY_JA = ('provoke', 'animated flourish', 'vallation', 'valiance', 'pflug', 'swordplay', 'liement', 'battuta', 'gambit', 'rayke', 'one for all', 'embolden',
             'elemental sforzo', 'sentinel', 'palisade', 'warcry', 'yonin', 'sepulcher')
TANK_JOBS = ('RUN', 'PLD')
ROLLS_OTHER = ('random deal', 'snake eye', 'wild card', 'fold', 'double-up', 'cutting cards', 'crooked cards')
SONG_BUFF = ('minuet', 'madrigal', 'march', 'minne', 'paeon', 'ballad', 'etude', 'carol', 'mambo', 'mazurka', 'prelude', 'scherzo', 'aria', 'hymnus',
             'sirvente', 'dirge', 'operetta', 'capriccio', 'gavotte', 'round', 'fantasia', 'songenhancing', 'bardsong', 'honormarch')
SONG_ENF = ('lullaby', 'elegy', 'threnody', 'requiem', 'finale', 'nocturne', 'virelai', 'songenfeeble', 'songdebuff', 'songstringskill', 'horde', 'foe')
BLU_SKILL = ('diamondhide', 'metallic body', 'metallicbody', 'occultation', 'magic barrier', 'magicbarrier', 'barrier tusk', 'barriertusk', 'atra. libations',
             'skill', 'skillrecast', 'harden shell', 'pyric bulwark', 'reactor cool')
BLU_CURE = ('cures', 'selfcures', 'magic fruit', 'wild carrot', 'healing breeze', 'white wind', 'plenilune embrace', 'restoral', 'pollen', 'cure')
BLU_ACC = ('magicaccuracy', 'sheep song', 'sheepsong', 'dream flower', 'yawn', 'cruel joke', 'stun', 'absolute terror', 'blank gaze', 'geist wall', 'frightful roar',
           'sudden lunge', 'silent storm', 'soporific', 'actinic burst', 'temporal shift', 'blistering roar', 'tourbillion', 'osmosis', 'infrasonics', 'lowing',
           'chaotic eye', 'sandspray', 'feather tickle', 'reaving wind', 'mortal ray', 'auroral drape', 'jettatura', 'enervation', 'acc')
BLU_BUFF = ('cocoon', 'refueling', 'erratic flutter', 'mighty guard', 'nat. meditation', 'animating wail', 'carcharian verve', 'memento mori', 'battery charge',
            'buff', 'buffs', 'saline coat', 'zephyr mantle', 'warm-up', 'amplification', 'feather barrier', 'orcish counterstance', 'triumphant roar')
SMN_PHYS = ('crescent fang', 'eclipse bite', 'mountain buster', 'rock buster', 'predator claws', 'volt strike', 'chaotic strike', 'spinning dive', 'rush',
            'poison nails', 'punch', 'double punch', 'claw', 'megalith throw', 'double slap', 'tail whip', 'moonlit charge', 'hysteric assault', 'blindside',
            'regal scratch', 'welt', 'roundhouse', 'flaming crush', 'axe kick', 'shock strike', 'barracuda dive', 'physical', 'phys', 'bloodpactrage', 'physicalbp')
SMN_ACC = ('enfeebling magic', 'enfeebling', 'debuff', 'lunar cry', 'mewing lullaby', 'eerie eye', 'sleepga', 'nightmare', 'slowga', 'tidal roar', 'diamond storm',
           'shock squall', 'somnolence', 'ultimate terror', 'pavor nocturnus', 'acc')
SMN_SKILL = ('ward', 'bloodpactward', 'buff', 'skill', 'healing', 'enhancing magic', 'shining ruby', 'glittering ruby', 'crimson howl', 'hastega', 'earthen ward',
             'ecliptic howl', 'ecliptic growl', 'noctoshield', 'dream shroud', 'perfect defense', 'soothing ruby', 'pacifying ruby', 'heavenward howl')
NIN_ENF = ('kurayami', 'hojo', 'aisha', 'yurin', 'jubaku', 'dokumori', 'enfeebling', 'ninjutsu enfeeble', 'enfeebleninjutsu')
NIN_SKILL = ('migawari', 'gekka', 'yain', 'kakka', 'myoshu', 'tonko', 'monomi')
MND_ENF = ('slow', 'paralyze', 'silence', 'addle', 'distract', 'frazzle', 'mndenfeebles', 'mnd')
INT_ENF = ('blind', 'gravity', 'sleep', 'bind', 'break', 'poison', 'dispel', 'intenfeebles', 'int', 'sleepga', 'breakga', 'dispelga')
SKILL_ENF = ('distract iii', 'frazzle iii', 'poison ii', 'poisonga', 'skill', 'potency', 'enfeeblingskill')
ENH_SKILL = ('temper', 'temper ii', 'enfire', 'enblizzard', 'enaero', 'enstone', 'enthunder', 'enwater', 'enfire ii', 'enblizzard ii', 'enaero ii', 'enstone ii',
             'enthunder ii', 'enwater ii', 'gain-str', 'gain-dex', 'gain-vit', 'gain-agi', 'gain-int', 'gain-mnd', 'gain-chr', 'enspell', 'enspells', 'gainspell',
             'enhancingskill', 'skill')


def _named(path):
    """The names in brackets of a path ('sets.midcast["Sheep Song"]' -> ['Sheep Song'])."""
    return [a or b for a, b in re.findall(r'\["([^"]+)"\]|\[\'([^\']+)\'\]', path or '')]


def handled_elsewhere(path, job):
    """A set wsdist, idle.py, pld.py, pup.py or magic.py already judges."""
    import doctor
    import idle
    import magic
    import pld
    import pup
    low = (path or '').lower()
    if not low.startswith('sets.') or low.startswith('sets.weapons'):
        return True
    if ('.ws' in low or 'ws[' in low or low.startswith('sets.ws')) and '.pet.' not in low:
        return True
    if doctor.is_tp_set(path) or idle.is_idle(path) or pld.takes(path, job) or pup.is_pet_set(path, job):
        return True
    try:
        if magic.kind_of(path, job):
            return True
    except Exception:
        pass
    return False


ACC_ENF = ('sleep', 'sleepga', 'bind', 'break', 'breakga', 'silence', 'dispel', 'gravity', 'gravity ii')


def _spell_focus(name, job):
    """What a set for one spell is for, from the game's spell list."""
    sp = spells().get(norm(name))
    if not sp:
        return None
    real, skill, targets = sp
    low = real.lower()
    if skill == 'enhancing':
        if low.startswith('stoneskin'):
            return 'Stoneskin'
        if low.startswith('aquaveil'):
            return 'Aquaveil'
        if low.startswith('phalanx'):
            return 'Phalanx'
        if low.startswith('bar'):
            return 'Barspells'
        if low.startswith('refresh'):
            return 'Refresh (cast)'
        if low in ENH_SKILL or low.startswith(('temper', 'gain-', 'boost-')) or re.match(r'en(fire|blizzard|aero|stone|thunder|water)', low):
            return 'Enhancing skill'
        return 'Enhancing duration'
    if skill == 'enfeebling':
        if low in SKILL_ENF:
            return 'Enfeebling (skill)'
        if low.startswith(('dia', 'inundation')) or low.split(' ')[0] in ACC_ENF:
            return 'Enfeebling (accuracy)'
        if low.split(' ')[0] in MND_ENF:
            return 'Enfeebling (MND)'
        return 'Enfeebling (INT)'
    if skill == 'elemental':
        if low in ('burn', 'choke', 'drown', 'frost', 'rasp', 'shock'):
            return 'Elemental enfeeble'
        if low == 'impact':
            return 'Impact'
        return None
    if skill == 'dark':
        if low.startswith(('drain', 'aspir')):
            return 'Drain and Aspir'
        if low == 'absorb-tp':
            return 'Absorb-TP'
        if low.startswith('absorb'):
            return 'Absorb'
        if low == 'stun':
            return 'Stun'
        if low.startswith('dread spikes'):
            return 'Dread Spikes'
        return 'Dark magic'
    if skill == 'divine':
        return 'Flash' if low == 'flash' else None
    if skill == 'ninjutsu':
        if low.startswith('utsusemi'):
            return 'Utsusemi'
        base = low.split(':')[0]
        if base in NIN_ENF:
            return 'Ninjutsu enfeeble'
        if base in NIN_SKILL:
            return 'Ninjutsu skill'
        return None
    if skill == 'singing':
        return 'Songs: enfeeble' if any(x in low for x in SONG_ENF) else 'Songs: buff'
    if skill == 'geomancy':
        return 'Indicolure' if low.startswith('indi-') else 'Geocolure'
    if skill == 'blue':
        if low in BLU_SKILL:
            return 'Blue magic: skill'
        if low == 'white wind':
            return 'Blue magic: White Wind'
        if low in BLU_CURE:
            return 'Blue magic: cures'
        if low in BLU_BUFF or targets & 1 and not targets & 32:
            return 'Blue magic: buffs'
        return 'Blue magic: accuracy' if low in BLU_ACC else None        # (a damage spell wsdist doesn't know: not judged here)
    if skill == 'healing':
        if low.startswith('curaga'):
            return 'Curaga'
        if low.startswith('cure'):
            return 'Cure'
        if low == 'cursna':
            return 'Cursna'
        if low.startswith('regen'):
            return 'Regen'
        return 'Spell recast'
    return None


def ability_of(path):
    """The ability a JA / buff set is for ('sets.precast.JA["Chain Affinity"]', 'sets.JA.ChainAffinity', 'sets.buff.Diffusion' -> its name), or None."""
    parts = fixer._path_parts(path or '')
    low = [p.lower() for p in parts]
    for i, p in enumerate(low):
        if p in ('ja', 'buff', 'corsairroll', 'flourish1', 'flourish2', 'flourish3', 'samba', 'step', 'jig') and i + 1 < len(parts):
            a = abilities().get(norm(parts[i + 1]))
            if a:
                return a
            if p == 'buff':
                k = norm(parts[i + 1])
                pre = [v for a_, v in abilities().items() if len(a_) >= 5 and k.startswith(a_)]
                return max(pre, key=len) if pre else parts[i + 1]
        if p in ('samba', 'step', 'jig', 'jump') and i == len(low) - 1 and i >= 2:      # (sets.precast.Samba: any Samba)
            return parts[i].capitalize()
        if p.startswith('fold') and i >= 1:                       # (a COR's sets.precast.FoldDoubleBust)
            return 'Fold'
    return None


def focus_for(path, job=None):
    """What a set is for (a FOCUS name), or None: the sets wsdist / idle / PLD / PUP / nukes judge, and the add-on sets for one or two items."""
    job = (job or '').upper()
    if handled_elsewhere(path, job):
        return None
    w = _words(path)
    rest = w[1:]
    if not rest or any((x in SMALL and not (x == 'sleep' and rest[0] != 'buff')) or x.startswith(('reraise', 'capacity')) for x in rest):
        return None
    joined = ' '.join(rest)
    hk = healing.kind_of(path)
    named = [n.lower() for n in _named(path)]
    ab = ability_of(path)
    if 'treasurehunter' in rest or 'th' in rest or 'treasure' in rest:
        return 'Treasure Hunter'
    if rest[0] in ('buff', 'utility') and len(rest) > 1:
        what = rest[1]
        if what == 'doom':
            return 'Doom'
        if what.startswith('composure') and job == 'RDM':          # (Composure + Lethargy pieces: longer enhancing magic on others)
            return 'Enhancing duration'
        if what in ('sneak attack', 'sneakattack', 'sa'):
            return 'Sneak Attack'
        if what in ('trick attack', 'trickattack', 'ta'):
            return 'Trick Attack'
        if rest[0] == 'utility':
            if what == 'phalanx':
                return 'Phalanx'
            if what == 'stoneskin':
                return 'Stoneskin'
            if what == 'steps':
                return 'Steps'
            return None
        return 'Ability' if ab or abilities().get(norm(what)) else None
    if hk:
        return {'cure': 'Cure', 'curaga': 'Curaga', 'selfcure': 'Cure (yourself)', 'received': 'Cure received', 'precast': 'Fast cast: cures',
                'cursna': 'Cursna', 'regen': 'Regen', 'waltz': 'Waltz'}[hk[0]]
    if rest[0] in ('enmity',) or (rest[0] == 'bluemagic' and 'enmity' in rest):
        return 'Spell, not interrupted' if 'sird' in rest else 'Enmity'
    if job == 'COR' and any(x.startswith('fold') for x in rest):     # (sets.precast.FoldDoubleBust: Lanun Gants for Fold)
        return 'Ability'
    if rest[0] == 'jump' or (ab and ab.lower().endswith('jump')):
        return 'Jump'
    if rest[0] == 'precast':
        if 'ra' in rest:
            return 'Snapshot'
        if 'corsairroll' in rest or (ab and ab.lower().endswith(' roll')) or (ab or '').lower() == 'phantom roll':
            return 'Phantom Roll'
        if 'corsairshot' in rest:
            return 'Quick Draw: accuracy' if any(x in ('light shot', 'dark shot') for x in named) else 'Quick Draw: damage'
        if rest[1:2] == ['step'] or (ab or '').lower().endswith('step'):
            return 'Steps'
        if 'violent flourish' in named or (ab or '') == 'Violent Flourish':
            return 'Violent Flourish'
        if 'fc' in rest or 'fastcast' in rest:
            if any(x in joined for x in ('song', 'bardsong')):
                return 'Fast cast: songs'
            if 'utsusemi' in joined:
                return 'Fast cast: Utsusemi'
            if any(x in joined for x in ('enhancing', 'stoneskin')):
                return 'Fast cast: enhancing'
            if any(x in joined for x in ('elemental', 'impact')):
                return 'Fast cast: elemental'
            if 'blue' in joined:
                return 'Fast cast: blue magic'
            if 'geomancy' in joined:
                return 'Fast cast: geomancy'
            return 'Fast cast'
        if any(x in rest for x in ('bloodpactward', 'bloodpactrage', 'bp')) or 'blood pact' in joined:
            return 'Blood Pact delay'
        if 'ja' in rest or rest[1:2] in (['samba'], ['jig'], ['flourish1'], ['flourish2'], ['flourish3']):
            a = (ab or '').lower()
            if a in ENMITY_JA or (job in TANK_JOBS and a in ('provoke', 'warcry', 'vallation', 'valiance', 'swordplay', 'pflug', 'liement', 'battuta')):
                return 'Enmity'
            if a == 'charm' or 'charm' in rest:
                return 'Charm'
            return 'Ability' if ab or len(rest) > 2 else None
        return None
    if rest[0] in ('ja',):
        a = (ab or '').lower()
        if a in ENMITY_JA:
            return 'Enmity'
        return 'Ability' if ab else None
    if rest[0] == 'midcast' or rest[0] == 'bluemagic':
        what = rest[1:]
        wj = ' '.join(what)
        if job in TANK_JOBS and (any(x in what for x in ('foil', 'flash', 'stun', 'jettatura', 'geist wall', 'sheep song', 'blank gaze', 'poisonga', 'banishga',
                                                          'blue magic', 'cocoon')) or 'enmity' in what):
            return 'Spell, not interrupted' if 'sird' in what or 'cocoon' in what else 'Enmity'
        if 'elementalninjutsu' in wj.replace(' ', '') or 'elementalninjutsusan' in what:
            return 'Ninjutsu burst' if 'burst' in what else 'Ninjutsu damage'
        if 'pet' in what or 'avatar' in what:
            if job == 'SMN':
                if any(x in wj for x in SMN_ACC):
                    return 'Blood Pact: accuracy'
                if any(x in wj for x in SMN_SKILL):
                    return 'Blood Pact: skill'
                if any(x in wj for x in SMN_PHYS):
                    return 'Blood Pact: physical'
                return 'Blood Pact: magic'
            if job == 'BST':
                if 'recast' in wj:
                    return 'Ready recast'
                if 'magic' in wj:
                    return 'Ready: magic'
                return 'Ready: physical'
            return None
        if 'ra' in what:
            return 'Ranged shots: critical' if 'crit' in wj else 'Ranged shots: accuracy' if 'acc' in what else 'Ranged shots'
        if 'corsairshot' in what:
            return 'Quick Draw: accuracy' if any(x in ('light shot', 'dark shot') for x in named) or 'acc' in wj else 'Quick Draw: damage'
        if 'songplaceholder' in wj or 'dummy' in wj:
            return 'Songs: dummy'
        if any(x in wj for x in SONG_ENF):
            return 'Songs: enfeeble'
        if job == 'BRD' and any(x in wj for x in SONG_BUFF):
            return 'Songs: buff'
        if 'fastrecast' in wj:
            return 'Spell recast'
        if 'geomancy' in wj:
            return 'Indicolure' if 'indi' in wj else 'Geocolure'
        for n in named + [x for x in what if x not in ('resistant', 'acc', 'fodder', 'dt', 'sird')]:   # (a set for one spell: the game's list says what kind)
            f = _spell_focus(n, job)
            if f:
                return 'Enfeebling (accuracy)' if f.startswith('Enfeebling') and ('resistant' in what or 'acc' in what) else f
        if 'inundation' in what:
            return 'Enfeebling (accuracy)'
        if what == ['ninjutsu']:
            return 'Spell recast'
        if rest[0] == 'bluemagic' or 'blue magic' in wj or job == 'BLU':
            if 'white wind' in wj or 'whitewind' in wj:
                return 'Blue magic: White Wind'
            if any(x in wj for x in BLU_CURE):
                return 'Blue magic: cures'
            if any(x in wj for x in BLU_SKILL):
                return 'Blue magic: skill'
            if any(x in wj for x in BLU_ACC):
                return 'Blue magic: accuracy'
            if 'conservemp' in wj or 'conserve' in wj:
                return 'Conserve MP'
            if 'refresh' in wj:
                return 'Blue magic: buffs'
            if any(x in wj for x in BLU_BUFF):
                return 'Blue magic: buffs'
            if 'blue magic' in wj and len(what) == 1:
                return None
        if 'sird' in what:
            return 'Spell, not interrupted'
        if 'enhancingduration' in wj or 'enhancing magic' in wj or any(x in what for x in ('haste', 'flurry', 'protect', 'shell', 'protectra', 'shellra', 'sneak',
                                                                                             'invisible', 'deodorize', 'composure', 'auspice')):
            return 'Enhancing duration' if 'skill' not in wj else 'Enhancing skill'
        if 'refresh' in what:
            return 'Refresh (cast)'
        if 'stoneskin' in what:
            return 'Stoneskin'
        if 'aquaveil' in what:
            return 'Aquaveil'
        if 'phalanx' in what:
            return 'Phalanx'
        if any(x.startswith('bar') for x in what):
            return 'Barspells'
        if any(x in what for x in ('temper', 'enspell', 'enspells', 'gainspell')):
            return 'Enhancing skill'
        if 'elementalenfeeble' in what:
            return 'Elemental enfeeble'
        if 'impact' in what:
            return 'Impact'
        if 'mndenfeebles' in what:
            return 'Enfeebling (accuracy)' if 'resistant' in what or 'acc' in what else 'Enfeebling (MND)'
        if 'intenfeebles' in what:
            return 'Enfeebling (accuracy)' if 'resistant' in what or 'acc' in what else 'Enfeebling (INT)'
        if 'enfeebling magic' in wj:
            return 'Enfeebling (accuracy)'
        if any(x in what for x in ('dia', 'diaga', 'bio')):
            return 'Enfeebling (accuracy)' if 'dia' in what[0] else 'Dark magic'
        if any(x in what for x in ('drain', 'aspir')):
            return 'Drain and Aspir'
        if 'absorb' in what:
            return 'Absorb'
        if 'stun' in what:
            return 'Stun'
        if 'dark magic' in wj or 'endark' in what:
            return 'Dark magic'
        if 'flash' in what:
            return 'Flash'
        if 'enmity' in what:
            return 'Enmity'
        if 'utsusemi' in what:
            return 'Utsusemi'
        if any(x in what for x in NIN_ENF):
            return 'Ninjutsu enfeeble'
        if any(x in what for x in NIN_SKILL):
            return 'Ninjutsu skill'
        if 'statusremoval' in what or 'erase' in what:
            return 'Spell recast'
        if 'conservemp' in what:
            return 'Conserve MP'
        return None
    return None


def takes(path, job):
    return focus_for(path, job) is not None


# ------------------------------------------------------------------ the numbers
def fast_base(job, sub):
    """Fast Cast the job gives (healing.py's numbers: RDM 38 main, 15 sub)."""
    return max(healing.FAST_MAIN.get(job, 0), healing.FAST_SUB.get(sub, 0))


def th_cap(job, sub):
    """Treasure Hunter from gear that still counts (BG Wiki: THF 8 in all, its traits 3 at 99; others 4; /THF gives 1)."""
    if job == 'THF':
        return 5
    return 3 if sub == 'THF' else 4


SNAP_GEAR_CAP = 60          # (70 % in all, 10 from 5/5 merits)


def ctx_for(job, sub, ability=None, song=None, spell=None):
    return {'job': (job or '').upper(), 'sub': (sub or '').upper(), 'ability': ability, 'song': song, 'spell': spell}


def numbers(gear, focus, ctx=None):
    """What a set has, as this kind of set is judged."""
    ctx = ctx or {}
    f = FOCUS.get(focus) or FOCUS['Ability']
    t = healing.totals(gear)
    pd, md = healing.dt_totals(t)
    n = dict(t)
    n['phys'], n['magic'] = pd, md
    job, sub = ctx.get('job', ''), ctx.get('sub', '')
    fb = fast_base(job, sub)
    n['fast_job'] = fb
    n['fast'] = t.get('fast', 0) + sum(t.get(k, 0) for k in f.get('cast', ()))
    n['fast_cap'] = max(0, healing.CAP_CAST - fb)
    n['haste'] = t.get('haste', 0)
    n['enmity'] = t.get('enmity', 0) + t.get('u_enmity', 0)
    n['enmity_down'] = max(0, -t.get('enmity', 0))
    n['pr'] = max([c['stats'].get('pr', 0) for c in gear.values() if c] + [0])       # (only the highest counts)
    n['th_cap'] = th_cap(job, sub)
    import pld
    n['phalanx'] = t.get('phalanx', 0)
    a = ctx.get('ability')
    if a:
        pieces = [boosts(c, a) for c in gear.values() if c]
        n['ja'] = sum(1 for x in pieces if x)
        n['jan'] = sum(x for x in pieces if x > 1)
    else:
        n['ja'] = n['jan'] = 0
    song = ctx.get('song')
    n['song_one'] = sum(boosts(c, song) for c in gear.values() if c) if song else 0
    n['ability'] = a
    n['hp'] = sum(pld.hp_of(c) for c in gear.values() if c)
    n['ds_absorb'] = round((pld.BASE_HP + n['hp']) * 0.5 * (1 + t.get('ds_pot', 0) / 100))
    # real results where a formula is known (real.py, PLAN.md E1): the points of the stats it stands for are dropped in value()
    import real
    if focus == 'Phalanx':
        hit = real.phalanx_hit(job, t.get('enh_skill', 0), t.get('phalanx', 0))
        if hit is not None:
            n['real'], n['real_value'] = 'Phalanx', hit
            n['real_words'] = f"Phalanx -{hit} a hit (Enhancing skill {real.ENH_BASE[job] + t.get('enh_skill', 0)}, gear +{t.get('phalanx', 0)})"
    elif ctx.get('spell'):
        e = real.enfeeble(ctx['spell'], t.get('enf_skill', 0), t.get('MND', 0), t.get('enf_eff', 0), job, sub)
        if e:
            n['real'], n['real_value'], n['real_words'] = ctx['spell'], e['value'], e['words']
    return n


def _pts(f, c):
    """(points per stat, extra points) for a set's numbers: a real result takes the place of the stats it is worked out from."""
    if not c.get('real'):
        return f['pts'], 0
    import real
    gone = real.REPLACES[c['real']]
    return {k: p for k, p in f['pts'].items() if k not in gone}, real.WEIGHT[c['real']] * c['real_value']


def capped(n, focus):
    """The numbers after the game's caps."""
    c = dict(n)
    c['fast'] = min(n.get('fast', 0), n.get('fast_cap', 80))
    c['haste'] = min(n.get('haste', 0), 26)
    c['quick'] = min(n.get('quick', 0), healing.CAP_QUICK)
    c['sird'] = min(n.get('sird', 0), 92)
    c['th'] = min(n.get('th', 0), n.get('th_cap', 4))
    c['snap'] = min(n.get('snap', 0), SNAP_GEAR_CAP)
    c['bp1'] = min(n.get('bp1', 0), 15)
    c['bp2'] = min(n.get('bp2', 0), 15)
    c['potency'] = min(n.get('potency', 0), healing.CAP_POTENCY)
    c['enmity_down'] = min(n.get('enmity_down', 0), healing.CAP_ENMITY)
    c['aquaveil'] = min(n.get('aquaveil', 0), 1)
    c['mbb'] = min(n.get('mbb', 0), 40)
    return c


def value(gear, focus):
    """The points of a set. focus: a FOCUS name, or (name, ctx)."""
    ctx = None
    if isinstance(focus, tuple):
        focus, ctx = focus
    f = FOCUS.get(focus) or FOCUS['Ability']
    c = capped(numbers(gear, focus, ctx), focus)
    pts, extra = _pts(f, c)
    v = sum(p * c.get(k, 0) for k, p in pts.items()) + extra
    return round(v, 3)


def main_value(gear, focus):
    """The points of only what the set is for (its 'show' stats): a set isn't "better" for damage taken alone when that isn't its job."""
    ctx = None
    if isinstance(focus, tuple):
        focus, ctx = focus
    f = FOCUS.get(focus) or FOCUS['Ability']
    c = capped(numbers(gear, focus, ctx), focus)
    keys = set(f['show']) | ({'jan'} if 'ja' in f['show'] else set()) | ({'song_one'} if 'songs' in f['show'] else set())
    if 'phys' in keys:
        keys.add('magic')
    pts, extra = _pts(f, c)
    return round(sum(p * c.get(k, 0) for k, p in pts.items() if k in keys) + extra, 3)


def words(n, focus=None):
    """'Fast Cast 64 % of 80, Quick Magic 2 %': what matters for the set."""
    f = FOCUS.get(focus or '') or FOCUS['Ability']
    out = []
    gone = ()
    if n.get('real'):                       # (the real result first; the stats it is worked out from aren't listed again)
        import real
        out.append(n['real_words'])
        gone = real.REPLACES[n['real']]
    for k in f['show']:
        if k in gone:
            continue
        v = n.get(k, 0)
        if k == 'ja':
            if n.get('ability'):
                out.append(f"{v} piece(s) for {n['ability']}" if v else f"nothing for {n['ability']}")
            continue
        if k == 'song_one':
            if v:
                out.append(f"the song's own +{v}")
            continue
        lab = LABEL.get(k, k)
        if k in ('phys', 'magic'):
            if not any(x.startswith('damage taken') for x in out):
                out.append(f"damage taken {n['phys']} % / {n['magic']} %")
            continue
        if k == 'fast':
            out.append(f"Fast Cast {v} % of {n.get('fast_cap', 80)}" + (f" (your job gives {n['fast_job']})" if n.get('fast_job') else ''))
            continue
        if k == 'th':
            out.append(f"Treasure Hunter +{v} of {n.get('th_cap', 4)} from gear")
            continue
        if k == 'snap':
            out.append(f"Snapshot {v} % of {SNAP_GEAR_CAP} from gear")
            continue
        if k in ('bp1', 'bp2'):
            out.append(f"{lab} -{v} of 15")
            continue
        if k == 'pr':
            out.append(f"Phantom Roll +{v} (only the highest piece counts)")
            continue
        if k == 'potency':
            out.append(f"Cure potency {v} % of 50")
            continue
        sign = '-' if k in ('ready_delay',) else '+'
        out.append(f"{lab} {sign}{v}{' %' if k in PCT else ''}")
    if not any(k in f['show'] for k in ('phys', 'magic')) and (n.get('phys') or n.get('magic')):
        out.append(f"damage taken {n['phys']} % / {n['magic']} %")
    return ', '.join(out)


def advice(n, focus):
    """A line about the set's numbers against the caps; '' when there's nothing to say."""
    tips = []
    f = focus or ''
    fz = FOCUS.get(f) or {}
    if 'fast' in fz.get('pts', {}) and fz['pts']['fast'] >= 10:
        if n.get('fast', 0) > n.get('fast_cap', 80):
            tips.append(f"Fast Cast {n['fast']} %: {n['fast'] - n['fast_cap']} % past the cap does nothing - that slot could carry something else")
        elif n.get('fast', 0) < n.get('fast_cap', 80):
            tips.append(f"Fast Cast {n['fast']} % of {n['fast_cap']}: {n['fast_cap'] - n['fast']} % short of the cap")
    if f == 'Treasure Hunter' and n.get('th', 0) < n.get('th_cap', 4):
        tips.append(f"Treasure Hunter +{n.get('th', 0)} from gear: the most that counts is +{n['th_cap']}")
    if f == 'Treasure Hunter' and n.get('th', 0) > n.get('th_cap', 4):
        tips.append(f"Treasure Hunter +{n['th']}: past +{n['th_cap']} does nothing")
    if f == 'Snapshot' and n.get('snap', 0) < SNAP_GEAR_CAP:
        tips.append(f"Snapshot {n.get('snap', 0)} %: {SNAP_GEAR_CAP} % from gear is the cap (with 5/5 merits); Flurry from a RDM / GEO adds more")
    if f == 'Snapshot' and n.get('snap', 0) > SNAP_GEAR_CAP:
        tips.append(f"Snapshot {n['snap']} %: past {SNAP_GEAR_CAP} % from gear does nothing without Flurry off")
    if f == 'Blood Pact delay' and (n.get('bp1', 0) > 15 or n.get('bp2', 0) > 15):
        tips.append('Blood Pact delay past -15 (each kind) does nothing')
    if f == 'Songs: dummy' and n.get('song_dur', 0):
        tips.append(f"song duration +{n['song_dur']} %: a dummy song should be short, so a new song overwrites it and not a real one")
    if fz.get('pts', {}).get('ja') and n.get('ability') and not n.get('ja'):
        tips.append(f"none of your gear boosts {n['ability']}")
    if f == 'Phantom Roll' and n.get('pr', 0) == 0:
        tips.append('no "Phantom Roll +n" piece: Regal Necklace, Lanun Knife or Rostam make every roll stronger')
    if 'potency' in fz.get('pts', {}) and n.get('potency', 0) > healing.CAP_POTENCY:
        tips.append(f"Cure potency {n['potency']} %: past 50 % is wasted")
    return '; '.join(tips)


# ------------------------------------------------------------------ building a set
def useful(cands, focus, ctx=None):
    """The candidates with anything this kind of set counts."""
    f = FOCUS.get(focus) or FOCUS['Ability']
    keys = set(f['pts']) | set(f.get('cast', ()))
    keys |= {'dt', 'pdt', 'mdt', 'dt2', 'pdt2', 'mdt2'} if ('phys' in keys or 'magic' in keys) else set()
    if 'enmity_down' in keys:
        keys.add('enmity')
    a = (ctx or {}).get('ability')
    s = (ctx or {}).get('song')
    return [c for c in cands if any(c['stats'].get(k) for k in keys) or (a and boosts(c, a)) or (s and boosts(c, s))]


def _locked(cur, data):
    """Slots that must stay: an item that lets you cast a spell (Twilight / Crepuscular Cloak for Impact, Daybreak for Dispelga), and the head under a cloak."""
    out = set()
    for slot, c in cur.items():
        text = data.text.get(c['id'], '') if data else ''
        if 'Able to cast' in text or 'Enables' in text or 'Cannot Equip Headgear' in text:
            out.add(slot)
            if 'Cannot Equip Headgear' in text:
                out.add('head')
    return out


ONTOP = ('Ability', 'Treasure Hunter', 'Sneak Attack', 'Trick Attack', 'Doom')


def judge(path, set_gear, job, sub, cands, counts, items, data, need=None, focus=None, build=True, base=None, ideas=None, keep=None):
    """One set, the same shape as pld.judge / pup.judge. base: healing.defaults(job, sub) for cures (worked out when None).
    ideas: (all candidates for the job) to say which gear he doesn't own would do better."""
    job, sub = (job or '').upper(), (sub or '').upper()
    focus = focus or focus_for(path, job) or 'Ability'
    ab = ability_of(path)
    song = None
    if focus == 'Songs: buff':
        for x in SONG_BUFF:
            if x in path.lower() and x not in ('songenhancing', 'bardsong', 'honormarch'):
                song = x.capitalize()
                break
    ctx = ctx_for(job, sub, ab if (ab and focus in ('Ability', 'Phantom Roll', 'Steps', 'Violent Flourish', 'Jump', 'Charm', 'Sneak Attack', 'Trick Attack',
                                                      'Quick Draw: damage', 'Quick Draw: accuracy')) else None, song)
    if focus == 'Phantom Roll' and ab == 'Phantom Roll':
        ctx['ability'] = None
    if focus.startswith('Enfeebling') and focus != 'Enfeebling (accuracy)':      # (a set for one spell whose strength has a formula: real.py)
        import real
        ctx['spell'] = real.spell_of(path)
    cur = healing.set_to_gear(set_gear, items, data, cands=cands)
    notes = [f'judged for: {focus} ({FOCUS[focus]["how"]})']
    away = sorted({c['name'] for c in cur.values() if counts and c['name'] not in counts})
    if away:
        cur = {s: c for s, c in cur.items() if c['name'] not in away}
        notes.append(f"not in your inventory or wardrobes, so GearSwap can't wear it: {', '.join(away)}")
    hk = FOCUS[focus].get('healing')
    import gs_create
    keep_weapons = job not in gs_create.MAGES or focus in ONTOP or focus.startswith(('Phantom', 'Quick Draw', 'Ranged', 'Snapshot', 'Steps', 'Jump'))
    if keep is not None:                                   # (he picked the weapons the sets are made with: Gear Optimization)
        keep_weapons = keep
    if keep_weapons:
        notes.append('weapons kept: a new weapon throws away TP')
    locked = _locked(cur, data)
    only = None
    if focus in ONTOP:                                      # (worn over your other gear: only its own slots, plus slots where a piece for the ability goes)
        only = set(cur)
        if ctx.get('ability'):
            for c in cands:
                if boosts(c, ctx['ability']):
                    only |= {s for s in healing.SLOTS if healing.fits(c, s)}
        if focus == 'Treasure Hunter':
            only |= {s for c in cands if c['stats'].get('th') for s in healing.SLOTS if healing.fits(c, s)} if not cur else set()
        notes.append('a set worn on top of your other gear: only its own slots (and slots where gear for it goes) change')
    if locked:
        only = (only if only is not None else set(healing.SLOTS)) - locked
        notes.append('kept: ' + ', '.join(sorted(cur[s]['name'] for s in locked if s in cur)) + ' (it lets you cast the spell)')
    if hk:
        base = base or _base(job, sub)
        spell = healing.spell_for_set(hk, path, job, sub)
        v0 = healing.evaluate(hk, cur, base, spell)[0]
        out = {'cur': cur, 'best': cur, 'now': v0, 'val': v0, 'n_now': _hnumbers(hk, cur, base, v0, spell), 'changes': {}, 'focus': focus, 'notes': notes,
               'short': 0, 'keep': keep_weapons, 'ideas': []}
        out['n_best'] = out['n_now']
        if build:
            best, val, now = healing.build(hk, cands, cur, base, job, sub, spell=spell, need=need or None, keep_weapons=keep_weapons, counts=counts,
                                           only_slots=only, solace=job == 'WHM' and hk == 'cure')
            out.update(best=best, val=val, now=now, n_best=_hnumbers(hk, best, base, val, spell), changes=healing.changes(cur, best, keep_weapons),
                       short=healing.shortfall(healing.totals(best), need or None))
        return out
    pool = useful(cands, focus, ctx)
    if {k.lower() for k in set_gear} & {'range', 'ranged'} and 'ammo' not in {k.lower() for k in set_gear}:
        pool = [c for c in pool if not healing.fits(c, 'ammo')]     # (a bow or gun in the range slot: other ammo would take it off, as idle.py does)
    spec = (focus, ctx)
    n0 = numbers(cur, focus, ctx)
    v0 = value(cur, spec)
    m0 = main_value(cur, spec)
    out = {'cur': cur, 'best': cur, 'now': v0, 'val': v0, 'n_now': n0, 'n_best': n0, 'changes': {}, 'focus': focus, 'keep': keep_weapons, 'notes': notes, 'short': 0,
           'short_now': healing.shortfall(healing.totals(cur), need or None), 'ideas': [], 'main_now': m0, 'main_best': m0}
    if build:
        best, val, now = healing.build('jobset', pool, cur, {}, job, sub, spell=spec, need=need or None, keep_weapons=keep_weapons, counts=counts, only_slots=only)
        out.update(best=best, val=val, now=now, n_best=numbers(best, focus, ctx), changes=healing.changes(cur, best, keep_weapons),
                   short=healing.shortfall(healing.totals(best), need or None))
        out['main_best'] = main_value(best, spec)
        if ideas:
            out['ideas'] = upgrade_ideas(out['best'], spec, ideas, counts, only, keep_weapons, job=job)
    return out


def _hnumbers(kind, gear, base, v, spell):
    t = healing.totals(gear)
    pd, md = healing.dt_totals(t)
    return {'healing': kind, 'lines': healing.describe(kind, t, base, v, spell), 'short': healing.short_note(kind, t, base), 'value': v,
            'unit': healing.fmt_value(kind, v), 'phys': pd, 'magic': md}


_BASES = {}


def _base(job, sub):
    if (job, sub) not in _BASES:
        _BASES[(job, sub)] = healing.defaults(job, sub)
    return _BASES[(job, sub)]


def hwords(n):
    return (n.get('unit', '') + ': ' if n.get('unit') else '') + '; '.join(n.get('lines', [])[:2])


def say(n, focus):
    """words() for any focus (the cures' own words)."""
    return hwords(n) if n.get('healing') else words(n, focus)


def tip(n, focus):
    return n.get('short', '') if n.get('healing') else advice(n, focus)


# ------------------------------------------------------------------ gear he doesn't have (the guides' "best in slot", from the game's item list)
def all_candidates(job, items, data):
    """Every level 99 item this job can wear, as a candidate (its text only: augments aren't known for gear he doesn't own). Read once per job."""
    key = (job, id(items))
    if key in _ALL:
        return _ALL[key]
    bit = 1 << checks.JOBS[job] if job in checks.JOBS else 0
    out = []
    for it in items.by_id.values():
        if it.get('level', 0) != 99 or (bit and it['jobs'] and not it['jobs'] & bit):
            continue
        if not it['slots']:
            continue
        out.append(healing.candidate(it, data))
    _ALL[key] = out
    return out


_ALL = {}


def upgrade_ideas(best, spec, every, counts, only=None, keep_weapons=True, n=3, job=None):
    """[(slot, item name, points more)] - the gear he doesn't own that would do the most for what this set is for (main_value: not damage taken), one piece at
    a time (the set as built, that piece swapped in)."""
    import job_rules
    focus, ctx = spec
    v0 = main_value(best, spec)
    no_ammo = job_rules.lock_ammo(job) if job else False
    pool = useful([c for c in every if c['name'] not in (counts or {})], focus, ctx)
    found = {}
    for s in healing.SLOTS:
        if (keep_weapons and s in ('main', 'sub')) or (only is not None and s not in only) or (no_ammo and s == 'ammo'):
            continue
        for c in pool:
            if not healing.fits(c, s):
                continue
            if s in ('main', 'sub'):
                continue                                    # (weapons: two-handed / shield rules - left to the set builder)
            g = dict(best)
            g[s] = c
            d = main_value(g, spec) - v0
            if d > 0.5 and d > found.get(c['name'], ('', 0))[1]:
                found[c['name']] = (s, d)
    top = sorted(found.items(), key=lambda x: -x[1][1])[:n]
    return [(s, name, round(d, 1)) for name, (s, d) in top]


def ideas_text(ideas):
    if not ideas:
        return ''
    return 'gear you don\'t have that would do more: ' + ', '.join(f"{name} ({s})" for s, name, d in ideas)


# ------------------------------------------------------------------ which sets of a file
def checked_sets(loaded, job, limit=None):
    """The sets judged here: one of each focus first, then the rest, plainest first."""
    rows = [s for s in loaded.sets if focus_for(s['path'], job)]
    rows.sort(key=lambda s: (s['path'].count('.'), len(s['path'])))
    first, seen = [], set()
    for s in rows:
        f = focus_for(s['path'], job)
        if f not in seen:
            seen.add(f)
            first.append(s)
    rows = first + [s for s in rows if s not in first]
    return rows[:limit] if limit else rows


def coverage(loaded, job):
    """{focus: n sets} of a file, for the job page's line."""
    out = {}
    for s in loaded.sets:
        f = focus_for(s['path'], job)
        if f:
            out[f] = out.get(f, 0) + 1
    return out


def coverage_text(cov, judged=None):
    if not cov:
        return ''
    n = sum(cov.values())
    top = ', '.join(f'{k} {v}' for k, v in sorted(cov.items(), key=lambda x: -x[1])[:6])
    return f"Job sets (by what the set is for): {judged if judged is not None else n} of {n} checked ({top}{' ...' if len(cov) > 6 else ''})"
