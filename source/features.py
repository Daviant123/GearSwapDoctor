"""
GearSwap Doctor: features to add to a GearSwap file (his request 2026-10-30: "add a suggestion, that will let the user add
relevant features or suggested features to the gearswap ... a full suite of options ... then this app should be able
to implement them within the gearswap").

How it goes into a file:
  - the shared code, gsd-features.lua (gsd_features.lua here), is copied to Windower\\addons\\GearSwap\\data
  - at the end of the job file goes one block: his choices (gsd_features = {...}) and include('gsd-features.lua')
The code runs after the file's own get_sets (and Mote's / Selindrile's include) and adds to GearSwap's events: the
file's own functions run first, the features add gear on top. Normal game commands only (no packets).

  FEATURES               the list: key, title, what it does, options
  suggest(...)           which ones fit this job, this file and the gear he owns (and why)
  read(path)             the features a file has now ({} when none)
  apply(path, conf)      write the block (backup first, the file checked before it's written); remove(path)
  simulate(path, conf)   the file + the features in a stand-in GearSwap: every event once, errors from the features
"""
import os
import re
import sys

import lupa
try:                                     # GearSwap runs on Lua 5.1 (setfenv, loadstring): test the features on it too
    from lupa import lua51 as LUA51
except ImportError:                      # pragma: no cover
    LUA51 = None

import fixer
import gs_loader
import paths
import rema

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE_NAME = 'gsd-features.lua'
START = '-- ==== GearSwap Doctor features (start) - made in GearSwap Doctor (Features tab); change them there ===='
END = '-- ==== GearSwap Doctor features (end) ===='
BLOCK_RE = re.compile(r'\n*-- ==== GearSwap Doctor features \(start\).*?-- ==== GearSwap Doctor features \(end\) ====[^\n]*\n?',
                      re.S)


def engine_source():
    base = getattr(sys, '_MEIPASS', HERE)
    for folder in (base, HERE):
        p = os.path.join(folder, 'gsd_features.lua')
        if os.path.exists(p):
            return open(p, encoding='utf-8').read()
    raise FileNotFoundError('gsd_features.lua')


def engine_version(src):
    m = re.search(r'version (\d+)', src[:300])
    return int(m.group(1)) if m else 0


IDLE_MP = r'idle.*(refresh|mp\b|latent|sublim)|(refresh|latent)\W*idle'
MELEE = {'WAR', 'MNK', 'THF', 'PLD', 'DRK', 'BST', 'SAM', 'NIN', 'DRG', 'BLU', 'DNC', 'RUN', 'COR', 'PUP', 'RNG', 'BRD', 'RDM'}
CASTERS = {'WHM', 'BLM', 'RDM', 'SCH', 'GEO', 'SMN', 'BRD', 'BLU', 'RUN', 'PLD', 'NIN', 'DRK'}
NUKERS = {'BLM', 'RDM', 'SCH', 'GEO', 'WHM', 'BLU', 'NIN', 'DRK', 'COR', 'RUN', 'PLD', 'SMN'}

KEYS = ['(none)'] + [m + 'F' + str(n) for m in ('', 'Ctrl+', 'Alt+') for n in range(1, 13)]


def bind_key(label):
    """'Ctrl+F9' -> '^f9' (Windower's bind keys)."""
    if not label or label == '(none)':
        return ''
    out = label.replace('Ctrl+', '^').replace('Alt+', '!').replace('Win+', '@')
    return out.lower()


def key_label(key):
    if not key:
        return '(none)'
    return key.replace('^', 'Ctrl+').replace('!', 'Alt+').replace('@', 'Win+').upper().replace('CTRL+', 'Ctrl+').replace('ALT+', 'Alt+')


# the options: (key, type, label, default, extra)
#   gear: {slot: item} picked from his gear     set: one of the file's sets     item: one item for a slot
#   int / choice / bool / text / key (a keyboard key for the command) / items (a list of names, comma separated)
FEATURES = [
    {'key': 'doom', 'title': 'Doom / Curse gear', 'group': 'Safety',
     'what': 'When you get Doom, your Doom gear goes on at once (it makes Cursna and Holy Water work better) and stays on '
             'until Doom is gone - even while you cast or weapon skill, if you want. Can also tell the party and use a '
             'Holy Water by itself.',
     'catalog': {'neck': ["Nicander's Necklace"], 'ring': ['Purity Ring', 'Saida Ring', "Eshmun's Ring", "Blenmot's Ring +1",
                                                          "Blenmot's Ring", 'Ephedra Ring', "Haoma's Ring"],
                 'waist': ['Gishdubar Sash']},
     'opts': [('gear', 'gear', 'Doom gear', {}, {'slots': ['neck', 'ring1', 'ring2', 'waist']}),
              ('say', 'text', 'Party message when you get Doom (empty = none)', 'Doomed! Cursna please', {}),
              ('holy', 'bool', 'Use a Holy Water at once', False, {}),
              ('curse', 'bool', 'Also for Curse', False, {}),
              ('casting', 'bool', 'Keep it on while casting / weapon skills too', True, {})],
     'already': r'doom'},
    {'key': 'sleep', 'title': 'Sleep gear', 'group': 'Safety',
     'what': 'While you are asleep, gear that wakes you or helps (Frenzy Sallet, Berserker\'s / Vim Torque) goes on, and '
             'comes off when you wake up.',
     'catalog': {'head': ['Frenzy Sallet'], 'neck': ["Berserker's Torque", 'Vim Torque +1', 'Vim Torque']},
     'opts': [('gear', 'gear', 'Sleep gear', {}, {'slots': ['head', 'neck']})],
     'already': r'buffactive\W+sleep|Frenzy Sallet|Vim Torque'},
    {'key': 'silence', 'title': 'Echo Drops when silenced', 'group': 'Safety',
     'what': 'If you try to cast while silenced, the spell is stopped and an Echo Drops (or Remedy) is used instead - '
             'then cast again.',
     'opts': [('item', 'choice', 'Use', 'Echo Drops', {'values': ['Echo Drops', 'Remedy', 'Vicar\'s Drink']})],
     'jobs': CASTERS, 'already': r'Echo Drops'},
    {'key': 'cancel', 'title': 'Cancel buffs that block a recast', 'group': 'Casting',
     'what': 'Takes off the old buff just before the new one lands, so it isn\'t blocked: shadows before Utsusemi: Ichi, '
             'Sneak before Spectral Jig, Stoneskin before Stoneskin, Sneak / Invisible before recasting them on '
             'yourself. Needs the Cancel addon (//lua load cancel - add it to scripts\\init.txt to have it always).',
     'opts': [('utsusemi', 'bool', 'Shadows before Utsusemi: Ichi', True, {}),
              ('jig', 'bool', 'Sneak before Spectral Jig', True, {}),
              ('stoneskin', 'bool', 'Stoneskin before Stoneskin', True, {}),
              ('sneak', 'bool', 'Sneak before Sneak / Monomi on yourself', True, {}),
              ('invisible', 'bool', 'Invisible before Invisible / Tonko on yourself', True, {}),
              ('wait', 'choice', 'Seconds after the cast starts', '1.5', {'values': ['0.5', '1', '1.5', '2', '2.5', '3']})],
     'already': r'cancel\s+66|cancel\s+71|cancel\s+37|Copy Image'},
    {'key': 'kiting', 'title': 'Movement speed gear when you run', 'group': 'Comfort',
     'what': 'While you move (and are not fighting), your movement speed gear goes on; when you stop, your idle set '
             'comes back by itself.',
     'catalog': {'legs': ['Carmine Cuisses +1', 'Carmine Cuisses', 'Blood Cuisses'],
                 'feet': ["Herald's Gaiters", 'Hippo. Socks +1', 'Hippo. Socks', 'Danzo Sune-Ate', 'Ninja Kyahan +1',
                          'Ninja Kyahan', 'Fajin Boots', 'Tandava Crackows', "Crier's Gaiters", 'Skd. Jambeaux +1',
                          'Geo. Sandals +3', 'Geo. Sandals +2', 'Geo. Sandals +1', 'Geomancy Sandals', 'Desert Boots'],
                 'ring': ['Shneddick Ring +1', 'Shneddick Ring']},
     'opts': [('gear', 'gear', 'Movement gear', {}, {'slots': ['legs', 'feet', 'ring1', 'ring2']}),
              ('set', 'set', '...or a set of your file', '', {'like': r'kit|move|run|speed'}),
              ('engaged', 'bool', 'Also while fighting (not usually wanted)', False, {})],
     'already': r'Kiting|moving|sets\.Kiting|MoveSpeed'},
    {'key': 'refresh', 'title': 'Refresh gear when MP is low', 'group': 'Comfort',
     'what': 'Standing (not fighting) with low MP: your refresh set (or gear) goes on until MP is back up.',
     'opts': [('set', 'set', 'Refresh set', '', {'like': IDLE_MP}),
              ('gear', 'gear', '...or these items', {}, {'slots': ['head', 'body', 'legs', 'feet', 'waist', 'back']}),
              ('mpp', 'int', 'MP below (%)', 50, {'lo': 10, 'hi': 95, 'step': 5})],
     'jobs': CASTERS | {'COR', 'DNC'}, 'already': r'mpp\s*<|MP\s*<'},
    {'key': 'dt', 'title': 'DT on / off with a key', 'group': 'Modes',
     'what': 'A key (or //gs c gsd dt) puts your damage taken set on top of everything when standing or fighting, until '
             'you press it again. Your casting and weapon skill sets still go on for the action.',
     'opts': [('set', 'set', 'DT set', '', {'like': r'dt|pdt|mdt|defense|damage'}),
              ('key', 'key', 'Key', '(none)', {})],
     'already': r'DefenseMode|HybridMode|gs c .*dt\b|toggle.*DT'},
    {'key': 'lowhp', 'title': 'DT set when HP is low', 'group': 'Safety',
     'what': 'When your HP falls below a level, your DT set goes on by itself; it comes off when HP is 10 % above it again.',
     'opts': [('set', 'set', 'DT set', '', {'like': r'dt|pdt|defense|damage'}),
              ('hpp', 'int', 'HP below (%)', 40, {'lo': 10, 'hi': 80, 'step': 5}),
              ('engaged_only', 'bool', 'Only while fighting', False, {})],
     'jobs': MELEE, 'already': r'hpp\s*<'},
    {'key': 'reraise', 'title': 'Reraise gear (key)', 'group': 'Safety',
     'what': 'A key (or //gs c gsd reraise) keeps your reraise gear on while you have no Reraise - for dangerous fights.',
     'catalog': {'head': ['Twilight Helm', 'Crepuscular Helm', 'Reraise Hairpin'], 'body': ['Twilight Mail', 'Crepuscular Mail'],
                 'neck': ['Reraise Gorget'], 'ear1': ['Reraise Earring']},
     'opts': [('gear', 'gear', 'Reraise gear', {}, {'slots': ['head', 'body', 'neck', 'ear1']}),
              ('key', 'key', 'Key', '(none)', {})],
     'already': r'Twilight Helm|Twilight Mail|Crepuscular'},
    {'key': 'weapons', 'title': 'Weapon lock (keep your TP)', 'group': 'Modes',
     'what': 'A key (or //gs c gsd weapons) locks your weapons so no set changes them - you don\'t lose TP when a set '
             'has other weapons.',
     'opts': [('slots', 'choice', 'Lock', 'main, sub, range', {'values': ['main, sub', 'main, sub, range', 'main, sub, range, ammo']}),
              ('start_locked', 'bool', 'Locked when the file loads', False, {}),
              ('key', 'key', 'Key', '(none)', {})],
     'jobs': MELEE, 'already': r"disable\(\s*['\"]main|WeaponLock|weapon_lock|lock_weapons"},
    {'key': 'th', 'title': 'Treasure Hunter', 'group': 'Farming',
     'what': 'Tag: your Treasure Hunter gear goes on for the first hit / spell on each new monster, then your normal '
             'set comes back. Always: TH gear stays on while fighting. A key (or //gs c gsd th) changes Off / Tag / Always.',
     'catalog': {'waist': ['Chaac Belt'], 'head': ['Volte Cap', 'Wh. Rarab Cap +1'], 'hands': ['Volte Bracers', 'Plun. Armlets +3',
                                                                                              'Plun. Armlets +2', 'Plun. Armlets +1'],
                 'feet': ['Volte Boots', 'Skulk. Poulaines +3'], 'legs': ['Volte Hose'], 'ammo': ['Per. Lucky Egg']},
     'opts': [('set', 'set', 'TH set', '', {'like': r'treasure|\bth\b|\.TH'}),
              ('gear', 'gear', '...or these items', {}, {'slots': ['ammo', 'head', 'hands', 'waist', 'legs', 'feet']}),
              ('mode', 'choice', 'Start in', 'Tag', {'values': ['Tag', 'Always', 'Off']}),
              ('tag_ws', 'bool', 'Also tag with weapon skills (costs WS damage)', False, {}),
              ('key', 'key', 'Key', '(none)', {})],
     'already': r'TreasureMode|TreasureHunter|th_gear|sets\.TH\b'},
    {'key': 'obi', 'title': 'Hachirin-no-Obi / Orpheus\'s Sash', 'group': 'Casting',
     'what': 'For nukes, cures, Drain / Aspir and magic weapon skills: the Hachirin-no-Obi when the weather or day '
             'matches the spell\'s element, or Orpheus\'s Sash when the monster is close and that is better.',
     'catalog': {'obi': ['Hachirin-no-Obi'], 'orpheus': ["Orpheus's Sash"]},
     'opts': [('obi', 'item', 'Obi', '', {'slot': 'waist', 'pick': 'obi'}),
              ('orpheus', 'item', "Orpheus's Sash", '', {'slot': 'waist', 'pick': 'orpheus'}),
              ('min', 'choice', 'Obi from a day / weather bonus of', '10', {'values': ['10', '20', '25', '35']}),
              ('orpheus_min', 'int', 'Orpheus from a bonus of (%)', 8, {'lo': 1, 'hi': 15, 'step': 1})],
     'already': r'Hachirin|Orpheus'},
    {'key': 'moonshade', 'title': 'Moonshade Earring swap at high TP', 'group': 'Weapon skills',
     'what': 'Moonshade Earring adds 250 TP to a weapon skill. Near 3000 TP that does nothing, so above the TP you pick '
             'another earring goes on instead.',
     'catalog': {'instead': ['Ishvara Earring', 'Thrud Earring', 'Lugra Earring +1', 'Sherida Earring', 'Brutal Earring',
                             'Regal Earring', 'Friomisi Earring', 'Malignance Earring', 'Odr Earring', 'Mache Earring +1',
                             'Telos Earring']},
     'opts': [('tp', 'int', 'From TP', 2750, {'lo': 2000, 'hi': 3000, 'step': 50}),
              ('instead', 'item', 'Wear instead', '', {'slot': 'ear1', 'pick': 'instead'})],
     'jobs': MELEE, 'already': r'Moonshade.*tp|tp.*Moonshade'},
    {'key': 'rings', 'title': 'Warp / Dim. / experience rings', 'group': 'Comfort',
     'what': 'Commands that put the ring on, lock it, wait for it and use it: //gs c gsd warp / dim / xp / cp. Also any '
             'of these rings you put on by hand is locked so GearSwap doesn\'t take it off before it\'s used.',
     'catalog': {'warp': ['Warp Ring'], 'dim': ['Dim. Ring (Holla)', 'Dim. Ring (Dem)', 'Dim. Ring (Mea)'],
                 'xp': ['Echad Ring', 'Caliber Ring', 'Emperor Band', 'Empress Band', 'Chariot Band', 'Resolution Ring',
                        "Kupofried's Ring"],
                 'cp': ['Trizek Ring', 'Capacity Ring', 'Facility Ring', 'Vocation Ring', 'Endorsement Ring']},
     'opts': [('warp', 'item', 'Warp ring', '', {'slot': 'ring1', 'pick': 'warp'}),
              ('dim', 'item', 'Dim. ring', '', {'slot': 'ring1', 'pick': 'dim'}),
              ('xp', 'item', 'Experience ring', '', {'slot': 'ring1', 'pick': 'xp'}),
              ('cp', 'item', 'Capacity ring', '', {'slot': 'ring1', 'pick': 'cp'}),
              ('slot', 'choice', 'Ring slot', 'ring2', {'values': ['ring1', 'ring2']}),
              ('wait', 'int', 'Seconds before using it', 11, {'lo': 5, 'hi': 20, 'step': 1}),
              ('lock', 'items', 'Lock these when worn', [], {'from': ['warp', 'dim', 'xp', 'cp'], 'extra': ['Nexus Cape']})],
     'already': r"Warp Ring.*disable|disable.*ring|Echad Ring|Trizek Ring"},
    {'key': 'cure_down', 'title': 'Lower cure when one can\'t go off', 'group': 'Healing',
     'what': 'You cast a cure that is on recast, or you have too little MP (or TP for a Waltz): the next lower one is cast '
             'on the same target instead - Cure V on recast becomes Cure IV, no lost time. Cures, Curagas and Waltzes.',
     'opts': [('say', 'bool', 'Say so in the chat', True, {})], 'jobs': CASTERS | {'DNC', 'WAR', 'SAM', 'THF'},
     'already': r'cure_down|refine_cure|get_spell_recasts|spell_recasts'},
    {'key': 'healsets', 'title': 'Healing sets go on for healing spells', 'group': 'Healing',
     'what': 'Which of your sets goes on for what: fast cast when a cure starts, your cure set when it lands, Curaga, Cursna, '
             'Regen, Waltz. For a file with no rules for them. (Mote and Selindrile files already do this: no need there.)',
     'opts': [('precast', 'set', 'Starting a cure (fast cast)', '', {'like': r'precast.*(fc|cure)|fastcast'}),
              ('cure', 'set', 'Cure', '', {'like': r'cure(?!_rec)|healing'}),
              ('curaga', 'set', 'Curaga', '', {'like': r'curaga'}),
              ('cursna', 'set', 'Cursna', '', {'like': r'cursna'}),
              ('regen', 'set', 'Regen', '', {'like': r'midcast.*regen'}),
              ('waltz', 'set', 'Waltz', '', {'like': r'waltz'})],
     'already': r'spell\.english.*Cure|name.*Cure|Cure.*spell\.|spellMap.*Cure'},
    {'key': 'keep_tp', 'title': 'Keep your weapons (and TP) when curing', 'group': 'Healing',
     'what': 'Changing your main weapon throws away your TP. With this much TP or more, a cure set\'s weapons are not put on: '
             'the rest of the set is. Good for anyone who fights and cures.',
     'opts': [('tp', 'int', 'From TP', 100, {'lo': 0, 'hi': 3000, 'step': 100})],
     'jobs': {'RDM', 'PLD', 'RUN', 'BLU', 'DRK', 'NIN', 'BRD', 'COR', 'SCH', 'WHM', 'GEO'}, 'already': r'player\.tp.*(Cure|cure)'},
    {'key': 'solace', 'title': 'Afflatus Solace reminder (WHM)', 'group': 'Healing',
     'what': 'A red line in the chat when a WHM casts a cure without Afflatus Solace on: its stoneskin and cure power are too '
             'good to forget. It only reminds you.',
     'opts': [('every', 'int', 'At most every (seconds)', 60, {'lo': 10, 'hi': 600, 'step': 10})],
     'jobs': {'WHM'}, 'already': r'buffactive\W+afflatus solace'},
    {'key': 'haste', 'title': 'Haste levels and delay cap', 'group': 'Fighting',
     'what': 'While you fight, a line in the chat when your haste changes level and whether your delay is capped with your gear and buffs: '
             'gear (cap 25 %), magic (cap 43.75 %: low, mid, high, capped), abilities like Last Resort and Hasso (cap 25 %), counting Dual Wield. '
             'It says how much is missing. //gs c gsd haste shows it any time, and the small window shows it too. '
             'Buff icons don\'t say how strong a buff is, so a Haste or March it doesn\'t see cast counts as set here: a good estimate.',
     'opts': [('tell', 'choice', 'Tell me in the chat', 'When it changes level', {'values': ['When it changes level', 'Only capped / not capped', 'Never']}),
              ('spell', 'choice', 'A Haste it did not see cast counts as', 'Haste II', {'values': ['Haste II', 'Haste']}),
              ('song', 'int', "Your singer's Songs+ gear", 7, {'lo': 0, 'hi': 9, 'step': 1}),
              ('geo', 'int', 'Indi / Geo-Haste counts as (%)', 40, {'lo': 3, 'hi': 41, 'step': 1}),
              ('blu_dw', 'int', 'A BLU\'s Dual Wield from its spells (%)', 25, {'lo': 0, 'hi': 35, 'step': 5})],
     'jobs': MELEE, 'already': r'delay.?cap|haste.*level'},
    {'key': 'aftermath', 'title': 'Aftermath gear (AM1 / AM2 / AM3)', 'group': 'Fighting',
     'what': 'While you fight with Aftermath up, gear for that level goes on, and your normal set comes back when it wears off. It uses what you pick '
             'for that level; otherwise it looks for sets named for it: sets.engaged.Liberator.AM3, sets.engaged.Liberator.AM, sets.engaged.AM3, '
             'sets.engaged.AM (or sets.TP.AM3, if your file calls them that). A Relic\'s Aftermath has no level: the Relic line. The button below makes the missing sets from your gear with wsdist.',
     'opts': [('auto', 'bool', 'Look for sets named for it', True, {}),
              ('say', 'bool', 'Say in the chat when it goes up or wears off', True, {}),
              ('set3', 'set', 'Lv.3 set', '', {'like': r'\.am3\b', 'nodefault': True}),
              ('set2', 'set', 'Lv.2 set', '', {'like': r'\.am2\b', 'nodefault': True}),
              ('set1', 'set', 'Lv.1 set', '', {'like': r'\.am1\b', 'nodefault': True}),
              ('setrelic', 'set', 'Relic set', '', {'like': r'\.am\b', 'nodefault': True}),
              ('gear3', 'gear', 'Lv.3: or these items', {}, {'slots': ['ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']}),
              ('gear2', 'gear', 'Lv.2: or these items', {}, {'slots': ['ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']}),
              ('gear1', 'gear', 'Lv.1: or these items', {}, {'slots': ['ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']}),
              ('gearrelic', 'gear', 'Relic: or these items', {}, {'slots': ['ammo', 'head', 'neck', 'ear1', 'ear2', 'body', 'hands', 'ring1', 'ring2', 'back', 'waist', 'legs', 'feet']})],
     'jobs': MELEE, 'already': r'CustomMeleeGroups:append|Aftermath: ?Lv|aftermath_up'},
    {'key': 'ammo', 'title': 'Low ammo warning', 'group': 'Comfort',
     'what': 'After each shot, a red warning in the chat when the ammo you use is running low.',
     'opts': [('count', 'int', 'Warn at (or below)', 20, {'lo': 5, 'hi': 99, 'step': 5})],
     'jobs': {'COR', 'RNG'}, 'already': r'ammo.*count|count.*ammo'},
    {'key': 'box', 'title': 'Small window with the modes', 'group': 'Modes',
     'what': 'A small window that shows DT / Treasure Hunter / weapon lock / reraise as they change. Drag it where you '
             'want it; //gs c gsd box hides / shows it.',
     'opts': [('x', 'int', 'From the left (pixels)', 400, {'lo': 0, 'hi': 3800, 'step': 10}),
              ('y', 'int', 'From the top (pixels)', 300, {'lo': 0, 'hi': 2100, 'step': 10}),
              ('size', 'int', 'Text size', 10, {'lo': 8, 'hi': 16, 'step': 1}),
              ('key', 'key', 'Key to hide / show', '(none)', {})],
     'already': r'texts\.new'},
]
BY_KEY = {f['key']: f for f in FEATURES}
GROUPS = ['Safety', 'Healing', 'Fighting', 'Modes', 'Farming', 'Casting', 'Weapon skills', 'Comfort']
KEY_CMD = {'dt': 'dt', 'th': 'th', 'weapons': 'weapons', 'reraise': 'reraise', 'box': 'box'}


def style_of(src):
    if re.search(r"include\(\s*['\"]Mote-Include", src, re.I):
        return 'Mote'
    if re.search(r"include\(\s*['\"]Sel-Include", src, re.I):
        return 'Selindrile'
    return 'plain'


# ------------------------------------------------------------------ his gear
def owned_items(items, bag_names, job=None):
    """[item dict] he owns that the job can wear (bag_names: {bag: {name: count}} from data/bags_<Name>.json)."""
    import checks
    seen, out = set(), []
    for bag, content in bag_names.items():
        if bag not in checks.EQUIP_BAGS:
            continue
        for name in content:
            for it in items.find(name)[:1]:
                if it['id'] in seen:
                    continue
                if job and job in checks.JOBS and it['jobs'] and not it['jobs'] & (1 << checks.JOBS[job]):
                    continue
                seen.add(it['id'])
                out.append(it)
    return out


def fits(it, slot):
    import checks
    return any(it['slots'] & (1 << b) for b in checks.SLOT_BITS.get(slot, []))


def choices(owned, slot, catalog=()):
    """Item names for a slot: the catalog's items he owns first (best first), then the rest A-Z."""
    names = [it['en'] for it in owned if fits(it, slot)]
    low = {n.lower(): n for n in names}
    first = [low[c.lower()] for c in catalog if c.lower() in low]
    return first + sorted(n for n in names if n not in first)


def _catalog(f, slot):
    cat = f.get('catalog', {})
    if slot in cat:
        return cat[slot]
    if slot in ('ring1', 'ring2'):
        return cat.get('ring', [])
    if slot in ('ear1', 'ear2'):
        return cat.get('ear', [])
    return []


def defaults(f, owned, set_paths):
    """The options a feature starts with: his best catalog items, the file's set that looks right."""
    out = {}
    for k, typ, label, default, extra in f['opts']:
        if typ == 'gear':
            g, used = {}, set()
            for slot in extra['slots']:
                for n in choices(owned, slot, _catalog(f, slot)):
                    if n.lower() in {c.lower() for c in _catalog(f, slot)} and n not in used:
                        g[slot] = n
                        used.add(n)
                        break
            out[k] = g
        elif typ == 'item':
            cat = f.get('catalog', {}).get(extra.get('pick'), [])
            c = [n for n in choices(owned, extra['slot'], cat) if n.lower() in {x.lower() for x in cat}]
            out[k] = c[0] if c else ''
        elif typ == 'set':
            out[k] = '' if extra.get('nodefault') else best_set(set_paths, extra.get('like', ''))
        elif typ == 'items':
            names = []
            for src in extra.get('from', []):
                if out.get(src):
                    names.append(out[src])
            for src in extra.get('from', []):
                names += [n for n in f.get('catalog', {}).get(src, []) if n not in names]
            out[k] = names + [n for n in extra.get('extra', []) if n not in names]
        else:
            out[k] = default
    return out


def best_set(set_paths, like):
    """The file's set that fits a pattern best (shortest name first: sets.defense.PDT before sets.defense.PDT.Acc)."""
    if not like:
        return ''
    rx = re.compile(like, re.I)
    hits = [p for p in set_paths if rx.search(p.replace('sets.', '', 1))]
    hits.sort(key=lambda p: (p.count('.') + p.count('['), len(p)))
    return hits[0] if hits else ''


def suggest(job, src, set_paths, owned):
    """{feature key: reason} for the features that fit this job, file and gear. Not suggested: what the file seems to
    do already (see already())."""
    names = {it['en'].lower() for it in owned}
    has = lambda *ns: [n for n in ns if n.lower() in names]  # noqa: E731
    sty = style_of(src)
    out = {}
    d = has(*(BY_KEY['doom']['catalog']['neck'] + BY_KEY['doom']['catalog']['ring'] + BY_KEY['doom']['catalog']['waist']))
    if d:
        out['doom'] = 'you own ' + ', '.join(d[:3])
    if job in MELEE and has(*(BY_KEY['sleep']['catalog']['head'] + BY_KEY['sleep']['catalog']['neck'])):
        out['sleep'] = 'you own ' + ', '.join(has(*(BY_KEY['sleep']['catalog']['head'] + BY_KEY['sleep']['catalog']['neck']))[:2])
    if job in CASTERS:
        out['silence'] = f'{job} casts spells'
    if job in ('NIN', 'DNC') or re.search(r'Utsusemi|Spectral Jig|Stoneskin', src):
        out['cancel'] = 'your file uses ' + ', '.join(n for n in ('Utsusemi', 'Spectral Jig', 'Stoneskin') if n in src) \
            if re.search(r'Utsusemi|Spectral Jig|Stoneskin', src) else f'{job} uses Utsusemi / Spectral Jig'
    k = has(*[n for v in BY_KEY['kiting']['catalog'].values() for n in v])
    if k and sty == 'plain':
        out['kiting'] = 'you own ' + ', '.join(k[:2])
    if job in CASTERS and best_set(set_paths, IDLE_MP):
        out['refresh'] = 'your file has ' + best_set(set_paths, IDLE_MP)
    dt = best_set(set_paths, r'dt|pdt|defense')
    if dt and sty == 'plain':
        out['dt'] = 'your file has ' + dt + ' but no key for it'
    if dt and job in MELEE:
        out['lowhp'] = 'a safety net with ' + dt
    r = has(*[n for v in BY_KEY['reraise']['catalog'].values() for n in v])
    if r:
        out['reraise'] = 'you own ' + ', '.join(r[:2])
    if job in MELEE and job not in ('BRD', 'RDM'):
        out['weapons'] = f'{job} builds TP - a lock keeps it'
    th_set = best_set(set_paths, r'treasure|\bth\b|\.TH')
    t = has(*[n for v in BY_KEY['th']['catalog'].values() for n in v])
    if job == 'THF' or th_set or t:
        out['th'] = ('your file has ' + th_set) if th_set else ('you own ' + ', '.join(t[:2])) if t else 'THF'
    o = has('Hachirin-no-Obi', "Orpheus's Sash")
    if o and job in NUKERS:
        out['obi'] = 'you own ' + ' and '.join(o)
    if has('Moonshade Earring') and job in MELEE and re.search(r'Moonshade', src):
        out['moonshade'] = 'your weapon skill sets use Moonshade Earring'
    rg = has(*[n for v in BY_KEY['rings']['catalog'].values() for n in v])
    if rg:
        out['rings'] = 'you own ' + ', '.join(rg[:3])
    if job in ('COR', 'RNG'):
        out['ammo'] = f'{job} shoots'
    cures = re.search(r'\bCure\b|Curaga|Curing Waltz', src)
    if cures and job in BY_KEY['cure_down']['jobs']:
        out['cure_down'] = 'your file has cures'
    if job == 'WHM':
        out['solace'] = 'WHM: Afflatus Solace'
    if sty == 'plain' and best_set(set_paths, r'cure|curaga|cursna') and not re.search(r'spell\.english.*Cure|Cure.*spell\.', src):
        out['healsets'] = 'your file has healing sets, but no rule for them'
    if cures and job in ('RDM', 'PLD', 'RUN', 'BLU', 'DRK', 'NIN'):
        out['keep_tp'] = f'{job} fights and cures'
    if job in MELEE and job != 'BRD':
        named = [p for p in set_paths if re.search(r'haste', p, re.I)]
        out['haste'] = f'your file has {len(named)} Haste sets: this says when they apply' if named else f'{job} fights: know when delay is capped'
    ult = [it['en'] for it in owned if fits(it, 'main') and rema.family(it['en']) not in (None, 'Aeonic')]
    if am_sets(set_paths):
        out['aftermath'] = f'your file has {len(am_sets(set_paths))} Aftermath sets'
    elif ult and job in MELEE:
        out['aftermath'] = 'you own ' + ', '.join(sorted(set(ult))[:3])
    return out


def am_sets(set_paths):
    """The file's sets named for Aftermath (sets.engaged.Liberator.AM3, sets.engaged.AM)."""
    return [p for p in set_paths if re.match(r'sets\.(engaged|tp)\b', p, re.I) and re.search(r'\.AM\d?(\.|$)', p, re.I)]


def am_words(set_paths):
    """For the job page and the Aftermath feature."""
    found = am_sets(set_paths)
    if not found:
        return 'No sets named for Aftermath in this file yet.'
    modes = {'engaged', 'tp', 'sets', 'haste', 'acc', 'mid', 'pdt', 'dt', 'dw', 'sw'}
    weapons = sorted({w for p in found for w in fixer._path_parts(p) if w.lower() not in modes and not re.match(r'^AM\d?$', w, re.I)})
    return f"{len(found)} set{'s' if len(found) != 1 else ''} named for Aftermath in this file" + (f" ({', '.join(weapons)})" if weapons else '') + '.'


LOGIC = re.compile(r'\bif\b|equip\s*\(|==|~=|buffactive|send_command|windower\.|disable\s*\(|state\.|cancel', re.I)


def already(f, src):
    """A note when the file seems to do this already (then adding it may double up)."""
    rx = f.get('already')
    if not rx:
        return ''
    rxc = re.compile(rx, re.I)
    for n, l in enumerate(BLOCK_RE.sub('', src).splitlines(), 1):
        t = l.strip()
        # only the rules (if / equip / buffactive / commands), not an item named in a set
        if t.startswith('--') or not LOGIC.search(t):
            continue
        if rxc.search(t):
            return f'Your file may do this already (line {n}: "{t[:70]}")'
    return ''


# ------------------------------------------------------------------ the block in the file
def _lua(v, indent=1):
    pad = '    ' * indent
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
    if isinstance(v, (list, tuple)):
        return '{' + ', '.join(_lua(x, indent + 1) for x in v) + '}'
    if isinstance(v, dict):
        if not v:
            return '{}'
        parts = []
        for k, x in v.items():
            key = k if re.match(r'^[A-Za-z_]\w*$', str(k)) else '[' + _lua(str(k)) + ']'
            parts.append(f'{key} = {_lua(x, indent + 1)}')
        one = '{' + ', '.join(parts) + '}'
        if len(one) < 100 or indent > 1:
            return one
        return '{\n' + ''.join(f'{pad}    {p},\n' for p in parts) + pad + '}'
    raise TypeError(type(v))


def clean(conf):
    """Only what the file needs: the ticked features with their options (numbers as numbers, keys -> binds)."""
    out, binds = {}, {}
    for key, opts in conf.items():
        f = BY_KEY.get(key)
        if not f or not opts.get('on'):
            continue
        c = {'on': True}
        for k, typ, label, default, extra in f['opts']:
            v = opts.get(k, default)
            if typ == 'key':
                b = bind_key(v) if v and not re.match(r'^[\^!@]?f\d+$', str(v)) else (v or '')
                if b and key in KEY_CMD:
                    binds[KEY_CMD[key]] = b
                continue
            if typ == 'gear':
                v = {s: n for s, n in (v or {}).items() if n and n != '(none)'}
            elif typ == 'int':
                v = int(v)
            elif typ == 'choice' and k in ('wait', 'min'):
                v = float(v) if '.' in str(v) else int(v)
            elif typ == 'choice' and k == 'slots':
                v = [s.strip() for s in str(v).split(',') if s.strip()]
            elif typ == 'items':
                v = [n.strip() for n in (v.split(',') if isinstance(v, str) else v) if n and n.strip()]
            elif typ in ('item', 'set', 'text'):
                v = '' if v in (None, '(none)') else str(v)
            c[k] = v
        out[key] = c
    if binds:
        out['binds'] = binds
    return out


def render(conf):
    c = clean(conf)
    order = [f['key'] for f in FEATURES if f['key'] in c] + (['binds'] if 'binds' in c else [])
    lines = [START, '-- What they do, and the commands: //gs c gsd help', 'gsd_features = {']
    for k in order:
        lines.append(f'    {k} = {_lua(c[k], 2)},')
    lines += ['}', "include('" + ENGINE_NAME + "')", END]
    return '\n'.join(lines) + '\n'


def strip(src):
    return BLOCK_RE.sub('\n', src).rstrip() + '\n'


def _to_py(t):
    if lupa.lua_type(t) != 'table' and (LUA51 is None or LUA51.lua_type(t) != 'table'):
        return t
    keys = list(t.keys())
    if keys and all(isinstance(k, int) for k in keys) and sorted(keys) == list(range(1, len(keys) + 1)):
        return [_to_py(t[i]) for i in range(1, len(keys) + 1)]
    return {str(k): _to_py(v) for k, v in t.items()}


def read(path):
    """{feature key: options (with on=True), 'binds': {...}} from the file's block; {} when it has none."""
    try:
        src = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return {}
    m = BLOCK_RE.search(src)
    if not m:
        return {}
    body = m.group(0)
    body = re.sub(r"include\(\s*['\"]gsd-features(\.lua)?['\"]\s*\)", '', body)
    L = lupa.LuaRuntime(unpack_returned_tuples=True)
    try:
        t = L.execute('local gsd_features\n' + body.replace('gsd_features = {', 'gsd_features = {', 1) + '\nreturn gsd_features')
    except lupa.LuaError:
        return {}
    conf = _to_py(t) if t is not None else {}
    binds = conf.get('binds', {}) or {}
    for key, cmd in KEY_CMD.items():
        if key in conf and isinstance(conf[key], dict):
            conf[key]['key'] = key_label(binds.get(cmd, ''))
    return conf


def install_engine(gs_data=None):
    """Copy the shared code into GearSwap's data folder (only when it's missing or older)."""
    gs_data = gs_data or paths.gs_data()
    dst = os.path.join(gs_data, ENGINE_NAME)
    src = engine_source()
    try:
        cur = open(dst, encoding='utf-8').read()
    except OSError:
        cur = None
    if cur != src and (cur is None or engine_version(cur) <= engine_version(src)):
        open(dst, 'w', encoding='utf-8', newline='\n').write(src)
    return dst


def apply(path, conf, gs_data=None):
    """Write the features block into the file (an empty conf takes it out). Backup first; the result must still load
    and the features must run in the stand-in GearSwap, or nothing is written. Returns (backup, what changed)."""
    raw = open(path, 'rb').read()
    crlf = bytes([13, 10]) in raw
    src = open(path, encoding='utf-8', errors='replace').read().replace('\r\n', '\n')
    c = clean(conf)
    new = strip(src)
    if any(k != 'binds' for k in c):
        new = new + '\n' + render(conf)
    if new == src:
        return None, []
    before = gs_loader.load(path)
    tmp = path + '.doctor-check.lua'
    open(tmp, 'w', encoding='utf-8').write(new)
    try:
        after = gs_loader.load(tmp)
    finally:
        os.remove(tmp)
    if after.error and not before.error:
        raise fixer.EditError("the changed file wouldn't load (" + after.error + ') - nothing was changed')
    if len(after.broken) > len(before.broken):
        raise fixer.EditError('the change would break a set - nothing was changed')
    if any(k != 'binds' for k in c):
        errs = simulate_src(new, os.path.basename(path), engine_source())
        if errs:
            raise fixer.EditError('the features failed a test run (' + errs[0] + ') - nothing was changed')
        install_engine(gs_data or os.path.dirname(path))     # (GearSwap looks for includes next to the job file too)
    bk = fixer.backup(path)
    open(path, 'w', encoding='utf-8', newline='\r\n' if crlf else '\n').write(new)
    names = [BY_KEY[k]['title'] for k in c if k in BY_KEY]
    return bk, names


def remove(path):
    return apply(path, {})


# ------------------------------------------------------------------ a stand-in GearSwap, to test the features
SIM = r'''
local ANY
local anymt = {}
anymt.__index = function(t, k) return ANY end
anymt.__newindex = function(t, k, v) end
anymt.__call = function(...) return ANY end
anymt.__concat = function(a, b) return '' end
anymt.__add = function() return 0 end anymt.__sub = anymt.__add anymt.__mul = anymt.__add anymt.__div = anymt.__add
anymt.__unm = function() return 0 end anymt.__len = function() return 0 end
anymt.__lt = function() return false end anymt.__le = anymt.__lt
anymt.__eq = function() return false end
anymt.__tostring = function() return '' end
ANY = setmetatable({}, anymt)

local SLOT = { main='main', sub='sub', range='range', ranged='range', ammo='ammo', head='head', neck='neck', ear1='left_ear',
  left_ear='left_ear', lear='left_ear', ear2='right_ear', right_ear='right_ear', rear='right_ear', body='body', hands='hands',
  ring1='left_ring', left_ring='left_ring', lring='left_ring', ring2='right_ring', right_ring='right_ring', rring='right_ring',
  back='back', waist='waist', legs='legs', feet='feet' }

local function ci(t)   -- GearSwap's tables ignore upper / lower case
  local d = {}
  for k, v in pairs(t or {}) do d[tostring(k):lower()] = v end
  return setmetatable({}, { __index = function(_, k) return d[tostring(k):lower()] end,
                            __newindex = function(_, k, v) d[tostring(k):lower()] = v end })
end

function SIM_NEW(src, name, engine)
  local S = { equip = {}, disabled = {}, cmds = {}, chat = {}, events = {}, cancel = false, errors = {} }
  local e = {}
  for _, k in ipairs({ 'string', 'table', 'math', 'pairs', 'ipairs', 'type', 'tostring', 'tonumber', 'select', 'next',
                       'pcall', 'error', 'assert', 'unpack', 'rawget', 'rawset', 'setmetatable', 'getmetatable', 'os' }) do
    e[k] = _G[k]
  end
  e.unpack = e.unpack or table.unpack
  e.sets = {}
  local function merge(out, t)
    for k, v in pairs(t) do
      local s = type(k) == 'string' and SLOT[k:lower()]
      if s then
        if S.disabled[s] then else out[s] = v end
      end
    end
  end
  e.equip = function(...) for i = 1, select('#', ...) do local t = select(i, ...) if type(t) == 'table' then merge(S.equip, t) end end end
  e.set_combine = function(...) local o = {} for i = 1, select('#', ...) do local t = select(i, ...)
      if type(t) == 'table' then for k, v in pairs(t) do o[(type(k) == 'string' and SLOT[k:lower()]) or k] = v end end end return o end
  e.disable = function(...) for _, s in ipairs({...}) do S.disabled[SLOT[s] or s] = true end end
  e.enable = function(...) for _, s in ipairs({...}) do S.disabled[SLOT[s] or s] = nil end end
  e.send_command = function(c) S.cmds[#S.cmds + 1] = c end
  e.add_to_chat = function(_, m) S.chat[#S.chat + 1] = m end
  e.cancel_spell = function() S.cancel = true end
  e.midaction = function() return false end
  e.S = function(t) local s = {} for _, v in ipairs(t or {}) do s[v] = true end return s end
  e.T = function(t) return t or {} end
  e.L = e.T
  e.texts = { new = function(txt, settings)
      local b = { shown = false, txt = txt or '' }
      function b:text(t) self.txt = t end
      function b:show() self.shown = true end
      function b:hide() self.shown = false end
      function b:destroy() self.gone = true end
      S.box = b
      return b
    end }
  e.player = { status = 'Idle', tp = 1000, name = 'Tester', main_job = 'WAR', sub_job = 'NIN', equipment = ci({}) }
  e.buffactive = ci({})
  e.world = { weather_element = 'None', day_element = 'Light', weather_intensity = 1 }
  S.me = { id = 1, x = 0, y = 0, status = 0, vitals = { hpp = 100, mpp = 100 }, buffs = {} }
  S.eq, S.bag, S.desc, S.ritems, S.augs = {}, {}, {}, {}, {}
  S.recasts = {}
  S.mobs = {}
  e.windower = setmetatable({
    ffxi = { get_player = function() return { id = S.me.id, status = S.me.status, vitals = S.me.vitals, buffs = S.me.buffs } end,
             get_items = function(a, b) if a == 'equipment' then return S.eq end return S.bag[b] end,
             get_mob_by_target = function(t) if t == 'me' then return S.me end return S.mobs[t] end,
             get_spell_recasts = function() return S.recasts end, get_ability_recasts = function() return S.recasts end },
    raw_register_event = function(n, f) S.events[n] = f return 1 end,
    register_event = function(n, f) S.events[n] = f return 1 end,
  }, anymt)
  e.include = function(n)
    if tostring(n):lower():gsub('%.lua$', '') == 'gsd-features' then
      local f, err = loadstring(engine, '=gsd-features.lua')
      if not f then error(err) end
      setfenv(f, e)
      return f()
    end
    return true
  end
  e.require = function() return ANY end
  e.gearswap = { equip_list = S.equip, res = { item_descriptions = S.desc, items = S.ritems },
                 extdata = { decode = function(it) return { augments = S.augs[it.id] } end } }
  setmetatable(e, { __index = function(t, k) return ANY end })
  e._G = e
  S.env = e
  local f, err = loadstring(src, '=' .. name)
  if not f then return nil, err end
  setfenv(f, e)
  local ok, err2 = pcall(f)
  if not ok then return nil, err2 end
  return S, false
end

function SIM_CALL(S, fn, ...)
  for k in pairs(S.equip) do S.equip[k] = nil end
  S.cancel = false
  local f = rawget(S.env, fn)
  if type(f) ~= 'function' then return false, 'no ' .. fn end
  local ok, e = pcall(f, ...)
  return ok, e or false
end

function SIM_TICK(S)
  local f = S.events.prerender
  if f then
    S.env.gsd.t = -1
    local ok, e = pcall(f)
    return ok, e or false
  end
  return true, false
end
'''


def sim_runtime():
    L = (LUA51 or lupa).LuaRuntime(unpack_returned_tuples=True)
    L.execute(SIM)
    return L


def simulate_src(src, name, engine):
    """Run the file with its features in the stand-in GearSwap: get_sets, then every event once. Errors that come from
    the features' code (gsd-features.lua) are returned - the file's own code isn't judged here (the stand-in can't
    play the game)."""
    L = sim_runtime()
    S, err = L.globals().SIM_NEW(src, name, engine)
    if S is None:
        return [f'the file: {err}'] if 'gsd-features' in str(err) else []
    out = []

    def run(fn, *args):
        ok, e = L.globals().SIM_CALL(S, fn, *args)
        if not ok and 'gsd-features' in str(e):
            out.append(f'{fn}: {e}')

    run('get_sets')
    spell = lambda **kw: L.table_from(kw)  # noqa: E731
    tgt = L.table_from({'type': 'MONSTER', 'id': 5, 'distance': 3, 'spawn_type': 16, 'name': 'Mob'})
    ws = spell(english='Savage Blade', type='WeaponSkill', action_type='Ability', element='Light', target=tgt)
    nuke = spell(english='Fire VI', type='BlackMagic', action_type='Magic', skill='Elemental Magic', element='Fire', target=tgt)
    cure = spell(english='Cure V', type='WhiteMagic', action_type='Magic', skill='Healing Magic', element='Light', mp_cost=135, recast_id=5,
                 target=L.table_from({'type': 'SELF', 'raw': '<me>', 'name': 'Tester', 'id': 1}))
    wz = spell(english='Curing Waltz III', type='Waltz', action_type='Ability', tp_cost=500, recast_id=217, target=tgt)
    for sp in (ws, nuke, cure, wz):
        run('precast', sp)
        run('midcast', sp)
        run('aftercast', sp)
    run('status_change', 'Engaged', 'Idle')
    run('buff_change', 'Doom', True)
    run('buff_change', 'Doom', False)
    run('buff_change', 'Aftermath: Lv.3', True)
    run('buff_change', 'Aftermath: Lv.3', False)
    for c in ('gsd help', 'gsd dt', 'gsd th', 'gsd weapons', 'gsd reraise', 'gsd refresh', 'gsd box', 'gsd warp', 'gsd unlock', 'gsd haste'):
        run('self_command', c)
    ok, e = L.globals().SIM_TICK(S)
    if not ok and 'gsd-features' in str(e):
        out.append(f'prerender: {e}')
    run('file_unload')
    return out


def simulate(path, conf):
    src = strip(open(path, encoding='utf-8', errors='replace').read().replace('\r\n', '\n')) + '\n' + render(conf)
    return simulate_src(src, os.path.basename(path), engine_source())


# what a ticked feature must have to do anything
NEEDS = {'doom': ('gear',), 'sleep': ('gear',), 'kiting': ('gear', 'set'), 'refresh': ('set', 'gear'), 'dt': ('set',),
         'lowhp': ('set',), 'reraise': ('gear',), 'th': ('set', 'gear'), 'obi': ('obi', 'orpheus'),
         'moonshade': ('instead',), 'rings': ('warp', 'dim', 'xp', 'cp', 'lock')}
COMMANDS = {'dt': ['//gs c gsd dt'], 'th': ['//gs c gsd th', '//gs c gsd th off / tag / always'],
            'weapons': ['//gs c gsd weapons'], 'reraise': ['//gs c gsd reraise'],
            'rings': ['//gs c gsd warp', '//gs c gsd dim', '//gs c gsd xp', '//gs c gsd cp', '//gs c gsd unlock'],
            'box': ['//gs c gsd box'], 'haste': ['//gs c gsd haste']}


def missing(conf):
    """Titles of ticked features that have nothing picked yet (no gear / set / item), so they would do nothing."""
    out = []
    for key, need in NEEDS.items():
        o = conf.get(key) or {}
        if not o.get('on'):
            continue
        ok = False
        for k in need:
            v = o.get(k)
            if isinstance(v, dict):
                ok = ok or any(x and x != '(none)' for x in v.values())
            elif isinstance(v, (list, tuple)):
                ok = ok or any(v)
            else:
                ok = ok or bool(v and v != '(none)' and str(v).strip())
        if not ok:
            out.append(BY_KEY[key]['title'])
    return out
