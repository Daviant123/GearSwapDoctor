"""
GearSwap Doctor - its own application (his request 2026-10-23: "make gearswap doctor its own application with a full gui
similiar to wsdist"). Laid out like wsdist (Kastra's damage simulator): the Windows look, tabs across the top, gear shown
in the game's equipment grid (main / sub / range / ammo, head / neck / ears, body / hands / rings, back / waist / legs /
feet), numbers in a fixed-width font.

Tabs
  Add features GearSwap features to add to a file (Doom gear, Obi, Treasure Hunter, DT key, movement speed ...), with
               their options; suggested ones for the job and the gear owned; written into the file with a click
  Healing      every healing set of a file (cure, Curaga, fast cast, Cursna, Regen, Waltz, being cured): what it heals now, what
               is wasted over a cap, and the best set from your gear with the enmity / damage taken it must have
  Overview     each GearSwap file of the character: loads?, sets, problems, wsdist upgrades; Check now; wsdist version
  Problems     what's wrong (broken / misspelled / wrong slot / wrong job / not owned / in storage), filter by kind
  Upgrades     wsdist's better weapon skill sets, your set and the better one side by side in the equipment grid
  Sets         every set in every file, in the equipment grid, its problems marked
  Build a set  one weapon skill or TP set: the weapon (main / sub) and the damage taken, physical and magic damage
               taken it must have; wsdist builds the best set from your gear that has them - put it in the set or
               save it as a new set. The numbers are remembered per set and the check-ups use them
  My gear      what the character owns (Steward's saved copy), by bag, with a search
  Backups      every backup GearSwap Doctor made; put one back
  Settings     characters, sub job per job, TP and enemy for the check-ups, the daily check
Nothing in a GearSwap file changes without a click; each change is backed up first and refused if the file would break.
"""
import glob
import json
import re
import os
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths    # noqa: E402
import rema     # noqa: E402
import checks   # noqa: E402
import doctor   # noqa: E402
import features  # noqa: E402
import fixer    # noqa: E402
import gs_loader  # noqa: E402
import healing  # noqa: E402
import idle     # noqa: E402
import set_name  # noqa: E402
import updater  # noqa: E402
import wsdist_runner as W  # noqa: E402

VERSION = '2.10.0'
SETTINGS = paths.SETTINGS
ICONS = os.path.join(paths.WSDIST, 'icons32')
HOME = 'https://github.com/Daviant123/GearSwapDoctor'
KIND_TEXT = {'broken': 'Broken', 'unknown': 'Misspelled', 'slot': 'Wrong slot', 'job': 'Wrong job',
             'missing': 'Not owned', 'stored': 'In storage'}
KIND_COLOR = {'broken': '#f4b4b4', 'unknown': '#f4b4b4', 'slot': '#f7d79a', 'job': '#f7d79a', 'missing': '#d9d9f7',
              'stored': '#d9e9f7'}
GRID = [['main', 'sub', 'range', 'ammo'], ['head', 'neck', 'ear1', 'ear2'], ['body', 'hands', 'ring1', 'ring2'],
        ['back', 'waist', 'legs', 'feet']]
SLOT_TEXT = {'main': 'Main', 'sub': 'Sub', 'range': 'Range', 'ammo': 'Ammo', 'head': 'Head', 'neck': 'Neck', 'ear1': 'Ear 1',
             'ear2': 'Ear 2', 'body': 'Body', 'hands': 'Hands', 'ring1': 'Ring 1', 'ring2': 'Ring 2', 'back': 'Back',
             'waist': 'Waist', 'legs': 'Legs', 'feet': 'Feet'}
JOBS = ['WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 'BST', 'BRD', 'RNG', 'SAM', 'NIN', 'DRG', 'SMN', 'BLU',
        'COR', 'PUP', 'DNC', 'SCH', 'GEO', 'RUN']
OFF, ON = '☐', '☑'
TP_METRIC_TEXT = {'time': 'time to a weapon skill', 'damage': 'damage per attack round', 'dps': 'damage a second, with weapon skills'}
WPN_AUTO = '(as in the file)'

# How much each kind matters, and what it means / what to do, in plain words (his request 2026-10-30: "gearswap doctor
# gui is not very user friendly and hard to understand. add in more things to help the user make decisions")
KIND_LEVEL = {'broken': 'must', 'unknown': 'must', 'slot': 'should', 'job': 'should', 'stored': 'should', 'missing': 'info'}
LEVEL_TEXT = {'must': 'Must fix', 'should': 'Should fix', 'info': 'Just so you know'}
LEVEL_COLOR = {'must': '#d9534f', 'should': '#e0a030', 'info': '#9a9a9a', 'good': '#4caf50'}
LEVEL_RANK = {'must': 0, 'should': 1, 'info': 2}
KIND_HELP = {
    'broken': ("This set or file doesn't work. GearSwap stops reading the file there, or the set is used before it's made, "
               "so the gear in it is never worn.",
               "Open the file at the line shown in Details (or ask for help with it). This one can't be fixed with a click."),
    'unknown': ("The item name isn't a real item - a typo or an old name. GearSwap skips it, so that slot stays empty when "
                "the set is used.",
                "Tick it and click Apply ticked: the name is changed to the closest real item shown as the fix."),
    'slot': ("The item can't go in that slot (for example a ring in an earring slot). GearSwap can't equip it there.",
             "Move it to the right slot in the file, or take it out of the set."),
    'job': ("This job can't wear the item, so GearSwap can't equip it in this job's sets.",
            "Take it out of this job's file, or use an item this job can wear."),
    'stored': ("You own it, but it's in storage (Mog Safe, Locker, Satchel, Sack, Case...). GearSwap only equips gear from "
               "the inventory and the Mog Wardrobes.",
               "Move it into a Mog Wardrobe (Steward's Store does it for you, or by hand at the Mog House)."),
    'missing': ("This character doesn't have the item anywhere.",
                "Usually nothing to do: sets copied from a guide often name gear you don't have. Only matters if you "
                "plan to get it - until then GearSwap just skips that slot."),
}


class ToolTip:
    """A small yellow tip when the mouse rests on a widget."""
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind('<Enter>', self.show)
        widget.bind('<Leave>', self.hide)

    def show(self, _=None):
        if self.tip:
            return
        x, y = self.widget.winfo_rootx() + 10, self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f'+{x}+{y}')
        tk.Label(self.tip, text=self.text, background='#ffffe0', relief='solid', borderwidth=1, wraplength=380,
                 justify='left', font=('Segoe UI', 9)).pack(ipadx=4, ipady=2)

    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


BIG_GAIN_NOTE = "Gains this big usually mean the set you have now names gear you don't own, so wsdist counts those slots as empty - check the swaps before applying."


def nowbest(u):
    """'928 -> 1219', or for a TP set '15.99 s -> 13.36 s to a WS'."""
    if u.get('kind') == 'tp' and u.get('unit') == 's':
        return f"{u['now']} s -> {u['best']} s to a WS"
    if u.get('unit') == 'dps':
        return f"{u['now']:.0f} -> {u['best']:.0f} damage a second"
    if u.get('kind') == 'idle':
        return f"{u['now_text']}  ->  {u['best_text']}"
    return f"{u['now']} -> {u['best']}"


def gain_words(u):
    """What the gain is: 'average damage for Savage Blade' / 'faster to a weapon skill (TP set engaged.Acc)'."""
    if u.get('kind') == 'tp':
        return {'s': 'faster to a weapon skill', 'dps': 'more damage a second, weapon skills included'}.get(u.get('unit'), 'more damage per attack round') + f" with {u['ws'][4:]}"
    if u.get('kind') == 'idle':
        return f"better for what it's for ({u['ws']})"
    return f"average damage for {u['ws']}"


def verdict_u(u):
    """verdict() of an upgrade - or "Gets your DT" when it is there for the damage taken he asked for."""
    if u.get('dt_fix') and u.get('gain', 0) < 1:
        return 'Gets your DT'
    return verdict(u.get('gain', 0))


def gain_text(u):
    return f"{u.get('gain', 0):+.1f}%"


def dt_words(u):
    """'Damage taken: physical -12% -> -50%, magic -5% -> -31% (you asked -50 / -30)' for an upgrade."""
    if 'dt_now' not in u:
        return ''
    (pn, mn), (pb, mb) = u['dt_now'], u['dt_best']
    out = f"Damage taken: physical {pn:.0f}% -> {pb:.0f}%, magic {mn:.0f}% -> {mb:.0f}%"
    if u.get('dt_asked'):
        pa, ma = u['dt_asked']
        out += f"  (you asked {pa:.0f}% / {ma:.0f}%" + (')' if u.get('dt_met') else " - the most your gear reaches)")
        if u.get('dt_fix') and u.get('gain', 0) < 0:
            out += f"\nIt reaches your damage taken; that costs {-u['gain']:.1f}% {'speed' if u.get('kind') == 'tp' else 'damage'}."
    return out


def verdict(gain):
    """How worth it an upgrade is, in words."""
    if gain >= 15:
        return 'Big gain'
    if gain >= 5:
        return 'Good gain'
    return 'Small gain'

GUIDE = """How to use GearSwap Doctor

1. Pick the character at the top and click Check now. It reads every GearSwap file of that character, checks every
   set, and asks wsdist (Kastra's damage simulator) for better weapon skill sets made from gear you already own.

2. Open "Start here". It lists what to do, most important first:
     red     Must fix - something doesn't work in game (a file that doesn't load, a misspelled item name)
     orange  Should fix - gear GearSwap can't equip (wrong slot, wrong job, left in storage)
     green   An upgrade - more damage from gear you already have
     grey    Just so you know - nothing to do unless you want to
   Each line has a button for the next step.

3. Nothing in your files changes until you click Apply (or "Fix all" / "Apply this"). You see a list of exactly what
   will change first. Every file is backed up before it's changed; "Undo last change" puts it back.

4. In game, type //gs reload (or change job) to use the new sets.

5. "Build a set" makes a set the way you want it: pick a weapon skill or TP set, the weapon to use (main and sub),
   and how much damage taken (DT), physical (PDT) and magic damage taken (MDT) it must have. wsdist builds the best
   set from your own gear that has them. "Put it in this set" or "Save it as a new set". Tick "Remember" and the
   check-ups keep to those numbers for that set from then on.

6. "Healing" shows every healing set of a file: what it heals now, what is wasted over a cap, and what's missing. Pick a set, the
   spell, and what it must also have (enmity, damage taken ...), then "Build the best set from my gear".

7. "Add features" adds things to a GearSwap file that it may not do yet: Doom gear that goes on by itself, the
   Hachirin-no-Obi on the right day / weather, Treasure Hunter tagging, a DT key, movement speed gear when you run,
   a Moonshade swap at high TP, Warp / experience ring commands, and more. ★ marks the ones suggested for that job
   and your gear. Tick them, pick the options (your gear is in the lists), then "Add ticked features to this file".
   Your own rules stay as they are: the features run after them. In game: //gs c gsd help.

Words
  Set        a group of gear GearSwap puts on for something, e.g. sets.precast.WS["Savage Blade"]
  Slot       where an item goes: main, sub, range, ammo, head, neck, ears, body, hands, rings, back, waist, legs, feet
  Wardrobe   the Mog Wardrobes 1-8: GearSwap equips from them and the inventory, nothing else
  Upgrade    a set wsdist found that does more damage, using only gear this character owns
  wsdist     Kastra's FFXI damage simulator - its numbers are estimates for comparing sets (1500 TP on an Apex Toad,
             typical party buffs, unless changed in Settings), not exact in-game damage
  Healing    the Healing tab has the game's cure formulas: a cure set is judged by the HP it heals. Cure potency stops at 50 %,
             potency II at 30 %: gear past that is wasted. Those numbers aren't from wsdist (it has no healing)
  Buffs      what's up while a set is judged (Settings, or the Buffs list in Build a set). Haste changes a TP set the most:
             the more haste you have, the less Dual Wield it needs
"""
MONO = ('Courier New', 10)


def ago(t):
    if not t:
        return 'never'
    s = time.time() - t
    if s < 3600:
        return f'{int(s // 60)} min ago'
    if s < 86400:
        return f'{int(s // 3600)} h ago'
    return f'{int(s // 86400)} days ago'


def characters():
    """Characters with GearSwap files (<Name>_<JOB>.lua) - the ones with Steward's saved bags first."""
    names = set()
    for p in glob.glob(os.path.join(doctor.GS_DATA, '*_*.lua')):
        base = os.path.basename(p)
        who = base.split('_')[0]
        if who and who[0].isupper() and checks.job_of(base):
            names.add(who)
    have = set()
    for sub in (('Steward', 'data', 'chars'), ('findAll', 'data')):
        folder = os.path.join(checks.WINDOWER, 'addons', *sub)
        if os.path.isdir(folder):
            have |= {os.path.splitext(f)[0] for f in os.listdir(folder)}
    reports = {os.path.basename(p)[7:-5] for p in glob.glob(os.path.join(doctor.DATA, 'report_*.json'))}
    return sorted(names, key=lambda n: (n not in reports, n not in have, n))


AM_HELP = ('Your Ultimate Weapon\'s Aftermath while a set is judged. Automatic: Mythic, Ergon, Empyrean and Prime at Lv.3, a Relic\'s '
           'own effect, Aeonic none (it only adds skillchain damage). Only the main hand counts. With Automatic, an Ultimate Weapon\'s TP '
           'sets are judged by damage per second with the weapon skills in it, because time to a weapon skill can\'t see most Aftermath.')
BUFF_HELP = ('What is up while wsdist judges a set. Haste changes a TP set the most: the more haste, the less Dual Wield it needs.\n'
             'None: nothing.\n'
             'Solo: food, Haste II and two Marches from trusts.\n'
             'Typical party: food, Haste II, Dia II on the enemy, Honor and Victory March, Minuet V, Blade Madrigal, '
             'Chaos and Samurai rolls.\n'
             'Custom: tick your own.')


def am_key(label):
    """'Lv.3' -> '3'."""
    return next((k for k, v in W.AM_CHOICES.items() if v == label), 'auto')


def buff_key(label):
    """'Typical party' -> 'party'."""
    return next((k for k, v in W.BUFF_CHOICES.items() if v == label), 'none')


def gs_slot(key):
    return gs_loader.SLOTS.get(str(key).lower())


def load_settings():
    d = {'tp': 1500, 'enemy': 'Apex Toad', 'subs': {}, 'daily': True, 'character': None, 'tp_sets': True, 'ws_tp': 1000,
         'tp_metric': 'time', 'buffs': 'party', 'buffs_custom': W.buff_spec('party'), 'aftermath': 'auto'}
    try:
        d.update(json.load(open(SETTINGS, encoding='utf-8')))
    except (OSError, ValueError):
        pass
    return d


def save_settings(d):
    os.makedirs(doctor.DATA, exist_ok=True)
    try:                                              # (keep what paths.py saved there: the Windower folder)
        old = json.load(open(SETTINGS, encoding='utf-8'))
    except (OSError, ValueError):
        old = {}
    old.update(d)
    if paths.WINDOWER:
        old['windower'] = paths.WINDOWER
    json.dump(old, open(SETTINGS, 'w', encoding='utf-8'), indent=1)


def use_windower(folder):
    """Point every part at this Windower folder."""
    paths.set_windower(folder)
    checks.WINDOWER = paths.WINDOWER
    doctor.GS_DATA = paths.gs_data()


def ask_windower(parent=None):
    """First start of the stand-alone app on a PC where the Windower folder isn't found: pick it once."""
    while True:
        messagebox.showinfo('GearSwap Doctor', 'Where is your Windower 4 folder? (the folder with Windower.exe, addons '
                                               'and res in it)', parent=parent)
        folder = filedialog.askdirectory(title='Your Windower 4 folder', parent=parent)
        if not folder:
            return False
        if paths.is_windower(folder):
            use_windower(folder)
            return True
        messagebox.showerror('GearSwap Doctor', f"{folder} doesn't look like a Windower 4 folder (no addons\\GearSwap "
                                                "and res folders in it).", parent=parent)


class GearGrid(ttk.LabelFrame):
    """The game's equipment window: 4 x 4 slots, each with its item (and icon when wsdist's icons are there)."""
    def __init__(self, master, title, items_ref):
        super().__init__(master, text=title, padding=4)
        self.items_ref = items_ref
        self.cells, self.images = {}, {}
        for r, row in enumerate(GRID):
            for c, slot in enumerate(row):
                f = tk.Frame(self, bd=1, relief='ridge', bg='#ffffff', width=150, height=58)
                f.grid(row=r, column=c, padx=2, pady=2, sticky='nsew')
                f.grid_propagate(False)
                cap = tk.Label(f, text=SLOT_TEXT[slot], font=('Segoe UI', 7), fg='#777', bg='#ffffff', anchor='w')
                cap.pack(fill='x')
                body = tk.Label(f, text='', font=('Segoe UI', 8), bg='#ffffff', anchor='nw', justify='left', wraplength=142,
                                compound='left')
                body.pack(fill='both', expand=True)
                self.cells[slot] = (f, cap, body)
        for c in range(4):
            self.columnconfigure(c, weight=1, uniform='slot')
        for r in range(4):
            self.rowconfigure(r, uniform='row')

    def _icon(self, name):
        if not name or not os.path.isdir(ICONS):
            return None
        items = self.items_ref()
        found = items.find(name) if items else []
        if not found:
            return None
        iid = found[0]['id']
        if iid not in self.images:
            path = os.path.join(ICONS, f'{iid}.png')
            self.images[iid] = tk.PhotoImage(file=path) if os.path.exists(path) else None
        return self.images[iid]

    def show(self, gear, marks=None, tips=None):
        """gear: {gs slot: item name}; marks: {gs slot: background colour}."""
        marks, tips = marks or {}, tips or {}
        for slot, (f, cap, body) in self.cells.items():
            name = gear.get(slot) or ''
            bg = marks.get(slot, '#ffffff')
            for w in (f, cap, body):
                w.configure(bg=bg)
            img = self._icon(name)
            body.configure(text=name + (('\n' + tips[slot]) if slot in tips else ''), image=img or '')


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        style = ttk.Style()
        try:
            style.theme_use('vista' if os.name == 'nt' else 'clam')      # wsdist's look (Linux: Tk's plain one is much older)
        except tk.TclError:
            pass
        style.configure('Treeview', rowheight=22)
        style.configure('Big.TButton', font=('Segoe UI', 10, 'bold'), padding=6)
        self.title(f'GearSwap Doctor  ({VERSION})   -   uses wsdist by Kastra')
        self.geometry('1180x820')
        self.minsize(980, 640)
        self._set_icon()
        self.cfg = load_settings()
        self.chars = characters() or ['(none found)']
        self.items = None                                # checks.Items (loaded in the background)
        self.report = None
        self.loaded = {}                                 # file path -> gs_loader.Loaded
        self.busy = False
        self.ticked, self.rows, self.info = set(), {}, {}
        self.ws_ready = False
        self.enemy_list = [self.cfg['enemy']]

        top = ttk.Frame(self, padding=(8, 8, 8, 0))
        top.pack(fill='x')
        ttk.Label(top, text='Character').pack(side='left')
        self.who = tk.StringVar(value=self.cfg.get('character') if self.cfg.get('character') in self.chars else self.chars[0])
        cb = ttk.Combobox(top, textvariable=self.who, values=self.chars, state='readonly', width=16)
        cb.pack(side='left', padx=6)
        cb.bind('<<ComboboxSelected>>', lambda e: self.change_character())
        self.check_btn = ttk.Button(top, text='Check now', style='Big.TButton', command=self.run_check)
        self.check_btn.pack(side='left', padx=6)
        self.progress = ttk.Progressbar(top, mode='indeterminate', length=160)
        self.progress.pack(side='left', padx=6)
        self.status = ttk.Label(top, text='')
        self.status.pack(side='left', padx=6)

        help_btn = ttk.Button(top, text='?  How to use', command=self.show_guide)
        help_btn.pack(side='right')
        ToolTip(self.check_btn, 'Reads all of this character\'s GearSwap files again, checks every set and looks for '
                                'better weapon skill sets with wsdist. Changes nothing.')

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill='both', expand=True, padx=8, pady=8)
        self._start_tab()
        self._features_tab()
        self._healing_tab()
        self._overview_tab()
        self._problems_tab()
        self._upgrades_tab()
        self._sets_tab()
        self._simulate_tab()
        self._gear_tab()
        self._backups_tab()
        self._settings_tab()

        bottom = ttk.Frame(self, padding=(8, 0, 8, 8))
        bottom.pack(fill='x')
        b_apply = ttk.Button(bottom, text='Apply ticked', style='Big.TButton', command=self.apply)
        b_apply.pack(side='left')
        ToolTip(b_apply, 'Changes the GearSwap files for every ticked row (misspelled names, upgrades). You see the full '
                         'list first; each file is backed up.')
        b_undo = ttk.Button(bottom, text='Undo last change', command=self.undo)
        b_undo.pack(side='left', padx=8)
        ToolTip(b_undo, 'Puts back the files from the last change (from the backup made then).')
        self.tick_label = ttk.Label(bottom, text='')
        self.tick_label.pack(side='left', padx=8)
        ttk.Label(bottom, text='Damage = wsdist estimates (good for comparing sets, not exact in-game numbers).',
                  foreground='#666').pack(side='right')

        if updater.installed():
            threading.Thread(target=self._load_background, daemon=True).start()
        else:
            self.sim_status.config(text='wsdist not downloaded yet (Settings > Download wsdist now).')
            threading.Thread(target=self._load_items, daemon=True).start()
        self.show_last()
        self.show_ws()
        self.after(300, self._first_start)
        self.after(2000, self.daily)

    def _first_start(self):
        if not paths.WINDOWER and not ask_windower(self):
            self.status.config(text='No Windower folder picked - Settings > Folders > Change...')
            return
        if not updater.installed():
            self.install_wsdist(ask=True)

    def _load_items(self):
        try:
            items = checks.Items()
            self.after(0, lambda: setattr(self, 'items', items))
        except Exception:
            pass

    # ------------------------------------------------------------------ setup
    def _set_icon(self):
        folder = getattr(sys, '_MEIPASS', HERE)
        try:
            if os.name == 'nt':
                if os.path.exists(os.path.join(folder, 'gsd.ico')):
                    self.iconbitmap(os.path.join(folder, 'gsd.ico'))
            elif os.path.exists(os.path.join(folder, 'gsd.png')):       # (Linux has no .ico)
                self._icon = tk.PhotoImage(file=os.path.join(folder, 'gsd.png'))
                self.iconphoto(True, self._icon)
        except tk.TclError:
            pass

    def _load_background(self):
        try:
            items = checks.Items()
            self.after(0, lambda: setattr(self, 'items', items))
        except Exception:
            pass
        try:
            import wsdist_runner as W
            names = W.enemies()
            self.after(0, lambda: self._ws_loaded(names))
        except Exception as e:
            self.after(0, lambda e=e: self.sim_status.config(text=f'wsdist could not load: {e}'))

    def _ws_loaded(self, names):
        self.ws_ready = True
        self.enemy_list = names
        for cbx in (self.sim_enemy, self.set_enemy):
            cbx.configure(values=names)
        self.sim_status.config(text='wsdist ready.')

    def _tree(self, parent, cols, heads, widths, tree_width=240):
        frame = ttk.Frame(parent)
        t = ttk.Treeview(frame, columns=cols, show='tree headings')
        t.heading('#0', text='')
        t.column('#0', width=tree_width, stretch=False)
        for c, h, w in zip(cols, heads, widths):
            t.heading(c, text=h)
            t.column(c, width=w, anchor='w')
        sb = ttk.Scrollbar(frame, orient='vertical', command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        return frame, t

    def _textbox(self, parent, height=5):
        t = tk.Text(parent, height=height, wrap='word', relief='flat', background='#fafafa', font=('Segoe UI', 9))
        t.config(state='disabled')
        return t

    def _say(self, box, text):
        box.config(state='normal')
        box.delete('1.0', 'end')
        box.insert('1.0', text)
        box.config(state='disabled')

    # ------------------------------------------------------------------ Jobs (the main page)
    # His request 2026-10-30: "i should be able to click a job, and be able to either do everything at once or
    # individually. the gui to interface with this isnt well done and hard to navigate". Left: the jobs, with what each
    # needs; right: "All jobs" (the to-do list) or one job's page - misspelled names, upgrades, things to look at - each
    # with ticks, and "Do everything for <job>" / "Fix misspelled" / "Apply ticked upgrades".
    def _start_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.tab_start = tab
        self.nb.add(tab, text='★ Jobs')
        pw = ttk.PanedWindow(tab, orient='horizontal')
        pw.pack(fill='both', expand=True)
        left = ttk.Frame(pw)
        ttk.Label(left, text='Click a job', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        self.job_list = ttk.Treeview(left, columns=('must', 'should', 'up'), show='tree headings', selectmode='browse', height=20)
        self.job_list.heading('#0', text='Job')
        self.job_list.column('#0', width=150)
        for c, h, tip in (('must', '✖', 'must fix'), ('should', '⚠', 'should fix'), ('up', '↑', 'upgrades')):
            self.job_list.heading(c, text=h)
            self.job_list.column(c, width=36, anchor='center')
        self.job_list.tag_configure('must', foreground='#c0392b')
        self.job_list.tag_configure('ok', foreground='#2e7d32')
        self.job_list.pack(fill='both', expand=True, pady=(4, 0))
        self.job_list.bind('<<TreeviewSelect>>', lambda e: self.show_job())
        ttk.Label(left, text='✖ must fix   ⚠ should fix   ↑ upgrades', foreground='#666').pack(anchor='w', pady=(4, 0))
        pw.add(left, weight=1)
        self.job_right = ttk.Frame(pw, padding=(10, 0, 0, 0))
        pw.add(self.job_right, weight=5)

        # "All jobs": the to-do list (cards)
        self.all_frame = ttk.Frame(self.job_right)
        head = ttk.Frame(self.all_frame)
        head.pack(fill='x')
        self.start_head = ttk.Label(head, text='', font=('Segoe UI', 12, 'bold'))
        self.start_head.pack(side='left')
        self.all_btn = ttk.Button(head, text='✔ Do everything for all jobs', style='Big.TButton', command=lambda: self.do_everything(None))
        self.all_btn.pack(side='right')
        ToolTip(self.all_btn, 'Fixes every misspelled name and applies every ticked upgrade in all jobs. You see the full list of '
                              'changes first; every file is backed up.')
        self.start_job = ttk.Combobox(head, values=['All jobs'], state='readonly', width=12)   # (set by the job list)
        self.start_job.set('All jobs')
        self.start_sub = ttk.Label(self.all_frame, text='', foreground='#555', wraplength=900, justify='left')
        self.start_sub.pack(anchor='w', pady=(2, 8))
        outer = ttk.Frame(self.all_frame)
        outer.pack(fill='both', expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0, background='#f4f4f4')
        sb = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        self.start_cards = tk.Frame(canvas, background='#f4f4f4')
        self.start_cards.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        win = canvas.create_window((0, 0), window=self.start_cards, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(int(-e.delta / 120), 'units')
                        if str(self.nb.select()) == str(self.tab_start) and self.all_frame.winfo_ismapped() else None)
        for button, step in (('<Button-4>', -1), ('<Button-5>', 1)):   # (Linux's mouse wheel)
            canvas.bind_all(button, lambda e, n=step: canvas.yview_scroll(n, 'units')
                            if str(self.nb.select()) == str(self.tab_start) and self.all_frame.winfo_ismapped() else None)

        # one job's page
        self.job_frame = ttk.Frame(self.job_right)
        jh = ttk.Frame(self.job_frame)
        jh.pack(fill='x')
        self.job_title = ttk.Label(jh, text='', font=('Segoe UI', 13, 'bold'))
        self.job_title.pack(side='left')
        self.job_do = ttk.Button(jh, text='', style='Big.TButton', command=lambda: self.do_everything(self.cur_job))
        self.job_do.pack(side='right')
        self.job_files = ttk.Label(self.job_frame, text='', foreground='#555')
        self.job_files.pack(anchor='w', pady=(0, 6))
        ttk.Label(self.job_frame, text='Ticked = will be done. Click a box to tick / untick. "Do everything" does all the ticked '
                  'rows below at once; or use the button of one part. You always see the list of changes first.',
                  foreground='#555', wraplength=780).pack(anchor='w', pady=(0, 6))

        def section(title):
            lf = ttk.LabelFrame(self.job_frame, text=title, padding=6)
            lf.pack(fill='x', pady=4)
            return lf

        s1 = section('1. Misspelled names - GearSwap skips them, so those slots stay empty')
        self.jt_fix = ttk.Treeview(s1, columns=('fix', 'sets'), show='tree headings', height=4)
        self.jt_fix.heading('#0', text='Name in the file')
        self.jt_fix.column('#0', width=300)
        self.jt_fix.heading('fix', text='Becomes')
        self.jt_fix.column('fix', width=300)
        self.jt_fix.heading('sets', text='Sets')
        self.jt_fix.column('sets', width=50, anchor='center')
        self.jt_fix.pack(side='left', fill='x', expand=True)
        self.jt_fix.bind('<Button-1>', self._job_tick)
        b1 = ttk.Frame(s1)
        b1.pack(side='right', padx=6)
        ttk.Button(b1, text='Fix ticked names', command=lambda: self.do_job_part(self.cur_job, 'fix')).pack()

        s2 = section('2. Upgrades - better weapon skill sets and TP sets from gear you already own (wsdist)')
        self.jt_up = ttk.Treeview(s2, columns=('gain', 'worth', 'items', 'dmg'), show='tree headings', height=6)
        self.jt_up.heading('#0', text='Weapon skill / TP set')
        self.jt_up.column('#0', width=220)
        for c, h, w in (('gain', 'Gain', 70), ('worth', 'Worth it?', 90), ('items', 'Items', 50), ('dmg', 'Now -> best', 170)):
            self.jt_up.heading(c, text=h)
            self.jt_up.column(c, width=w, anchor='w')
        self.jt_up.tag_configure('big', foreground='#2e7d32')
        self.jt_up.tag_configure('small', foreground='#777')
        self.jt_up.pack(side='left', fill='x', expand=True)
        self.jt_up.bind('<Button-1>', self._job_tick)
        self.jt_up.bind('<<TreeviewSelect>>', lambda e: self._job_up_detail())
        b2 = ttk.Frame(s2)
        b2.pack(side='right', padx=6)
        ttk.Button(b2, text='Apply ticked upgrades', command=lambda: self.do_job_part(self.cur_job, 'up')).pack(fill='x')
        ttk.Button(b2, text='See in the gear grid', command=self._job_up_grid).pack(fill='x', pady=(4, 0))
        bdt = ttk.Button(b2, text='Set its damage taken...', command=self._job_up_dt)
        bdt.pack(fill='x', pady=(4, 0))
        ToolTip(bdt, 'Opens Build a set with this set picked: type how much damage taken, physical and magic damage '
                     'taken it must have, and wsdist builds the best set from your gear that has it.')
        self.jt_up_text = self._textbox(self.job_frame, 6)
        self.jt_up_text.pack(fill='x')

        s3 = section('3. For you to look at - these need you (or another tool) to fix')
        self.jt_look = ttk.Treeview(s3, columns=('imp', 'what', 'todo'), show='tree headings', height=5)
        self.jt_look.heading('#0', text='Item / set')
        self.jt_look.column('#0', width=220)
        for c, h, w in (('imp', 'Importance', 90), ('what', 'What', 90), ('todo', 'What to do', 460)):
            self.jt_look.heading(c, text=h)
            self.jt_look.column(c, width=w, anchor='w')
        for lv, col in LEVEL_COLOR.items():
            self.jt_look.tag_configure(lv, foreground=col if lv != 'info' else '#666')
        self.jt_look.pack(fill='x', expand=True)
        nb_ = ttk.Frame(self.job_frame)
        nb_.pack(fill='x', pady=(4, 0))
        self.job_missing = ttk.Label(nb_, text='', foreground='#666')
        self.job_missing.pack(side='left')
        ttk.Button(nb_, text='Show the list', command=lambda: self.show_problems('missing')).pack(side='left', padx=6)
        s4 = section('4. Add features - Doom gear, Obi, Treasure Hunter, a DT key, movement speed and more')
        self.job_feat = ttk.Label(s4, text='', wraplength=720, justify='left')
        self.job_feat.pack(side='left', fill='x', expand=True)
        ttk.Button(s4, text='Healing sets...', command=lambda: self.open_healing(self.cur_job)).pack(side='right', padx=(0, 6))
        ttk.Button(s4, text='Choose features...', command=lambda: self.open_features(self.cur_job)).pack(side='right', padx=6)
        self.cur_job = None
        self.job_ticks = set()          # keys of the ticked rows: ('r', path, old) / ('u', path, set)
        self.job_rowkey = {}            # tree row -> (key, edit)

    def _files_of(self, job):
        r = self.report or {}
        return [f for f in r.get('files', []) if job is None or (f.get('job') or '?') == job]

    def fill_jobs(self):
        """The job list (left) and the default ticks: names with a fix, upgrades from +5 % to +100 % (bigger ones are
        usually missing gear, smaller ones barely matter: untick / tick as you like)."""
        t = self.job_list
        keep = self.cur_job
        t.delete(*t.get_children())
        t.insert('', 'end', iid='__all__', text='★ All jobs')
        r = self.report
        self.job_ticks = set()
        if not r:
            self.show_job()
            return
        jobs = {}
        for f in r['files']:
            jobs.setdefault(f.get('job') or '?', []).append(f)
        for job in sorted(jobs):
            must = sum(1 for f in jobs[job] for p in f['problems'] if KIND_LEVEL.get(p['kind']) == 'must')
            should = sum(1 for f in jobs[job] for p in f['problems'] if KIND_LEVEL.get(p['kind']) == 'should')
            up = sum(1 for f in jobs[job] for u in f['upgrades'] if 'error' not in u)
            t.insert('', 'end', iid='job:' + job, text=job, values=(must or '', should or '', up or ''),
                     tags=('must',) if must else ('ok',) if not should and not up else ())
            for f in jobs[job]:
                for p in f['problems']:
                    if p['kind'] == 'unknown' and p.get('fix'):
                        self.job_ticks.add(('r', f['path'], p['item']))
                for u in f['upgrades']:
                    if 'error' not in u and (5 <= u['gain'] <= 100 or u.get('dt_fix')):
                        self.job_ticks.add(('u', f['path'], u['set']))
        sel = 'job:' + keep if keep and t.exists('job:' + keep) else '__all__'
        t.selection_set(sel)
        self.show_job()

    def show_job(self):
        sel = self.job_list.selection()
        key = sel[0] if sel else '__all__'
        if key == '__all__':
            self.cur_job = None
            self.job_frame.pack_forget()
            self.all_frame.pack(fill='both', expand=True)
            self.start_job.set('All jobs')
            self.fill_start()
            return
        self.cur_job = key[4:]
        self.all_frame.pack_forget()
        self.job_frame.pack(fill='both', expand=True)
        self.fill_job_page()

    def _box(self, key):
        return ON if key in self.job_ticks else OFF

    def fill_job_page(self):
        job = self.cur_job
        files = self._files_of(job)
        self.job_title.config(text=f'{self.who.get()}  -  {job}')
        self.job_do.config(text=f'✔ Do everything for {job}')
        self.job_files.config(text='Files: ' + ', '.join(f"{f['file']} ({f['sets']} sets)" for f in files))
        self.job_rowkey = {}
        for t in (self.jt_fix, self.jt_up, self.jt_look):
            t.delete(*t.get_children())
        n_fix = n_up = n_look = n_missing = 0
        for f in files:
            for p in f['problems']:
                if p['kind'] == 'unknown' and p.get('fix'):
                    key = ('r', f['path'], p['item'])
                    row = self.jt_fix.insert('', 'end', text=f"{self._box(key)} {p['item']}", values=(p['fix'], len(p['sets'])))
                    self.job_rowkey[('fix', row)] = (key, (f['path'], ('rename', p['item'], p['fix'])))
                    n_fix += 1
                elif p['kind'] == 'missing':
                    n_missing += 1
                else:
                    lv = KIND_LEVEL.get(p['kind'], 'info')
                    self.jt_look.insert('', 'end', text=p['item'], values=(LEVEL_TEXT[lv], KIND_TEXT.get(p['kind'], p['kind']),
                                        KIND_HELP.get(p['kind'], ('', ''))[1] + (f"  ({p['detail']})" if p['kind'] == 'broken' else '')),
                                        tags=(lv,))
                    n_look += 1
            for u in sorted(f['upgrades'], key=lambda u: -(u.get('gain') or -1)):
                if 'error' in u:
                    continue
                key = ('u', f['path'], u['set'])
                row = self.jt_up.insert('', 'end', text=f"{self._box(key)} {u['ws']}",
                                        values=(gain_text(u), verdict_u(u) + (' ⚑' if u['gain'] > 100 else ''),
                                                len(u['changes']), nowbest(u)),
                                        tags=('big' if u['gain'] >= 15 else 'small' if u['gain'] < 5 else '',))
                self.job_rowkey[('up', row)] = (key, (f['path'], ('slots', u['set'], u['changes'])), u)
                n_up += 1
        if not n_fix:
            self.jt_fix.insert('', 'end', text='   (none - every name is a real item)')
        if not n_up:
            self.jt_up.insert('', 'end', text='   (none - wsdist found nothing better among your gear)')
        if not n_look:
            self.jt_look.insert('', 'end', text='(nothing)', values=('', '', ''))
        self.job_missing.config(text=f"Not owned: {n_missing} item(s) named in these sets that you don't have - usually "
                                     "nothing to do." if n_missing else "Every item in these sets is one you own.")
        checked = '  '.join(t for t in (doctor.tp_checked_text(f) for f in files) if t)
        self._say(self.jt_up_text, ('Click an upgrade to see exactly what it swaps.  ' if n_up else '') + checked)
        self.job_feat.config(text=self._job_feature_text(job, files))

    def _job_feature_text(self, job, files):
        if not files:
            return ''
        path = files[0]['path']
        try:
            src = open(path, encoding='utf-8', errors='replace').read()
            have = features.read(path)
            sug = features.suggest(job, src, [x['path'] for x in self.loaded_file(path).sets], self.feat_owned(job))
        except Exception:
            return 'Click "Choose features..." to see them.'
        sug = {k: v for k, v in sug.items() if k not in have}
        out = []
        if have:
            out.append('In ' + os.path.basename(path) + ': ' + ', '.join(features.BY_KEY[k]['title'] for k in have if k in features.BY_KEY) + '.')
        if sug:
            out.append('★ Suggested: ' + ', '.join(f"{features.BY_KEY[k]['title']} ({v})" for k, v in list(sug.items())[:4])
                       + (f' and {len(sug) - 4} more' if len(sug) > 4 else '') + '.')
        am = features.am_sets([x['path'] for x in self.loaded_file(path).sets])
        if am:
            out.append(features.am_words([x['path'] for x in self.loaded_file(path).sets]))
        return '  '.join(out) or 'Nothing suggested - "Choose features..." shows them all.'

    def _job_tick(self, e):
        t = e.widget
        row = t.identify_row(e.y)
        part = 'fix' if t is self.jt_fix else 'up'
        rec = self.job_rowkey.get((part, row))
        if not rec or t.identify_column(e.x) != '#0':
            return
        key = rec[0]
        if key in self.job_ticks:
            self.job_ticks.discard(key)
        else:
            self.job_ticks.add(key)
        txt = t.item(row, 'text')
        t.item(row, text=self._box(key) + txt[1:])

    def _job_up_detail(self):
        sel = self.jt_up.selection()
        rec = self.job_rowkey.get(('up', sel[0])) if sel else None
        if not rec:
            return
        key, (path, edit), u = rec
        now = self.set_gear(path, u['set'])
        where = self.item_bags()
        lines = [f"{verdict_u(u)}: {gain_text(u)} {gain_words(u)} ({nowbest(u)})  -  "
                 f"{os.path.basename(path)}, {u['set']}"]
        if dt_words(u):
            lines.append(dt_words(u))
        for slot, new in u['changes'].items():
            bag = where.get(new.lower())
            lines.append(f"  {SLOT_TEXT.get(slot, slot):<7} {now.get(slot) or '(empty)'}  ->  {new}" + (f"   (in your {bag})" if bag else ''))
        if u['gain'] > 100:
            lines.append(BIG_GAIN_NOTE)
        self._say(self.jt_up_text, '\n'.join(lines))

    def _job_up_dt(self):
        sel = self.jt_up.selection()
        rec = self.job_rowkey.get(('up', sel[0])) if sel else None
        if rec:
            self.open_build(rec[1][0], rec[2]['set'])
        else:
            self.open_build(None, None)

    def _upg_dt(self):
        sel = self.upg.selection()
        u = self.info.get(('u', sel[0])) if sel else None
        if u and sel[0] in self.rows:
            self.open_build(self.rows[sel[0]][0], u['set'])
        else:
            self.open_build(None, None)

    def _job_up_grid(self):
        sel = self.jt_up.selection()
        rec = self.job_rowkey.get(('up', sel[0])) if sel else None
        if rec:
            self.show_upgrade_for(rec[1][0], rec[2]['set'])

    def _ticked_edits(self, job, part=None):
        """{path: [edits]} for the ticked rows of one job (None = all jobs); part 'fix' / 'up' / None = both."""
        by_file = {}
        for f in self._files_of(job):
            if part in (None, 'fix'):
                for p in f['problems']:
                    if p['kind'] == 'unknown' and p.get('fix') and ('r', f['path'], p['item']) in self.job_ticks:
                        by_file.setdefault(f['path'], []).append(('rename', p['item'], p['fix']))
            if part in (None, 'up'):
                for u in f['upgrades']:
                    if 'error' not in u and ('u', f['path'], u['set']) in self.job_ticks:
                        by_file.setdefault(f['path'], []).append(('slots', u['set'], u['changes']))
        return by_file

    def do_job_part(self, job, part):
        by_file = self._ticked_edits(job, part)
        if not by_file:
            messagebox.showinfo('GearSwap Doctor', 'Nothing ticked there. Click the boxes of the rows you want first.')
            return
        self._apply(by_file)

    def do_everything(self, job):
        """Every ticked misspelled name and upgrade of this job (None = all jobs), in one go - after the list of changes."""
        by_file = self._ticked_edits(job, None)
        if not by_file:
            messagebox.showinfo('GearSwap Doctor', 'Nothing to do' + (f' for {job}' if job else '') + ': no misspelled names to '
                                'fix and no ticked upgrades.')
            return
        self._apply(by_file)

    def _card(self, level, title, text, buttons=()):
        """One line of the to-do list: a coloured bar, what it is, why, and buttons for the next step."""
        row = tk.Frame(self.start_cards, background='#ffffff', bd=1, relief='solid', highlightthickness=0)
        row.pack(fill='x', padx=2, pady=4)
        tk.Frame(row, background=LEVEL_COLOR.get(level, '#999'), width=8).pack(side='left', fill='y')
        body = tk.Frame(row, background='#ffffff')
        body.pack(side='left', fill='both', expand=True, padx=10, pady=8)
        tag = {'must': 'MUST FIX', 'should': 'SHOULD FIX', 'info': 'JUST SO YOU KNOW', 'good': 'UPGRADE'}.get(level, '')
        tk.Label(body, text=tag, background='#ffffff', foreground=LEVEL_COLOR.get(level, '#999'),
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w')
        tk.Label(body, text=title, background='#ffffff', font=('Segoe UI', 11, 'bold'), anchor='w', justify='left',
                 wraplength=820).pack(anchor='w')
        if text:
            tk.Label(body, text=text, background='#ffffff', foreground='#444', anchor='w', justify='left',
                     wraplength=820).pack(anchor='w', pady=(2, 0))
        bar = tk.Frame(row, background='#ffffff')
        bar.pack(side='right', padx=10)
        for label, cmd in buttons:
            ttk.Button(bar, text=label, command=cmd).pack(side='left', padx=3)

    def fill_start(self):
        for w in self.start_cards.winfo_children():
            w.destroy()
        r, who = self.report, self.who.get()
        if not r:
            self.start_head.config(text=f'{who}: not checked yet')
            self.start_sub.config(text='Click Check now (top left). It takes a minute or two and changes nothing - then this page '
                                       'tells you what to do, most important first.')
            self._card('info', 'Step 1: click Check now', 'GearSwap Doctor reads every GearSwap file of this character, '
                       'checks every set against the gear you own, and asks wsdist for better weapon skill sets.',
                       [('Check now', self.run_check)])
            return
        jobs = sorted({f.get('job') for f in r['files'] if f.get('job')})
        self.start_job.configure(values=['All jobs'] + jobs)
        pick = self.start_job.get()
        files = [f for f in r['files'] if pick == 'All jobs' or f.get('job') == pick]
        r = dict(r, files=files)
        probs = [(f, p) for f in r['files'] for p in f['problems']]
        by = {}
        for f, p in probs:
            by.setdefault(p['kind'], []).append((f, p))
        ups = sorted(((f, u) for f in r['files'] for u in f['upgrades'] if 'error' not in u), key=lambda x: -x[1]['gain'])
        must = len(by.get('broken', [])) + len(by.get('unknown', []))
        self.start_head.config(text=f'{who}: ' + ('everything works' if not must else f'{must} thing(s) to fix first'))
        self.start_sub.config(text=f"Checked {ago(r['time'])}. {len(r['files'])} GearSwap files. Most important first; each line "
                                   "has a button for the next step. Nothing is changed until you click Apply / Fix.")
        # bags out of date
        bt = r.get('bags_time')
        if not bt:
            self._card('should', "Your bags aren't known", "GearSwap Doctor reads what you own from the findAll addon (or "
                       "Steward). Without it, it can't tell what you own or find upgrades. In game: //lua load findall, then "
                       "log in on this character.", [])
        elif time.time() - bt > 3 * 86400:
            self._card('info', f'Your bags were saved {ago(bt)}', 'Log in on this character (findAll / Steward save the '
                       'bags) and click Check now, so the list matches what you have today.', [('Check now', self.run_check)])
        # 1. broken
        if by.get('broken'):
            files = sorted({f['file'] for f, p in by['broken']})
            self._card('must', f"{len(by['broken'])} set(s) or file(s) don't work in game", KIND_HELP['broken'][0] + ' In: '
                       + ', '.join(files[:6]) + (' ...' if len(files) > 6 else ''), [('Show me', lambda: self.show_problems('broken'))])
        # 2. misspelled
        fixable = [(f, p) for f, p in by.get('unknown', []) if p.get('fix')]
        if by.get('unknown'):
            ex = ', '.join(f"{p['item']} -> {p['fix']}" for f, p in fixable[:3])
            self._card('must', f"{len(by['unknown'])} item name(s) are misspelled", KIND_HELP['unknown'][0]
                       + (f' For example: {ex}.' if ex else ''),
                       ([(f'Fix all {len(fixable)}', self.fix_all_misspelled)] if fixable else []) + [('Show me', lambda: self.show_problems('unknown'))])
        # 3. upgrades
        for f, u in ups[:3]:
            n = len(u['changes'])
            self._card('good', f"{u['ws']}: {verdict_u(u).lower()} ({gain_text(u)} {'faster to a weapon skill' if u.get('kind') == 'tp' else 'damage'}) in {f['file']}",
                       f"wsdist found a better set from gear you already own: {n} item(s) change "
                       f"({', '.join(list(u['changes'].values())[:4])}{' ...' if n > 4 else ''}). {'Time to a weapon skill' if u.get('kind') == 'tp' else 'Average damage'}: {nowbest(u)}."
                       + (' ' + BIG_GAIN_NOTE if u['gain'] > 100 else ''),
                       [('Look', lambda f=f, u=u: self.show_upgrade_for(f['path'], u['set'])),
                        ('Apply this', lambda f=f, u=u: self._apply({f['path']: [('slots', u['set'], u['changes'])]}))])
        if len(ups) > 3:
            self._card('good', f'{len(ups) - 3} more upgrade(s)', 'Smaller ones, or for weapon skills you may use less. '
                       'The Upgrades tab lists them all with how big each gain is.', [('Open Upgrades', lambda: self.nb.select(self.tab_upgrades))])
        # 4. should fix
        for kind, title in (('stored', "item(s) are in storage, so GearSwap can't use them"), ('slot', 'item(s) are in the wrong slot'),
                            ('job', "item(s) can't be worn by this job")):
            if by.get(kind):
                names = sorted({p['item'] for f, p in by[kind]})
                self._card('should', f"{len(by[kind])} {title}", KIND_HELP[kind][0] + ' ' + KIND_HELP[kind][1]
                           + ' Items: ' + ', '.join(names[:6]) + (' ...' if len(names) > 6 else ''),
                           [('Show me', lambda k=kind: self.show_problems(k))])
        # 5. just so you know
        if by.get('missing'):
            self._card('info', f"{len(by['missing'])} item(s) named in your sets that you don't own", KIND_HELP['missing'][1],
                       [('Show the list', lambda: self.show_problems('missing'))])
        if pick == 'All jobs' and r['files']:
            self._card('info', 'Or work one job at a time', 'Click a job on the left: its misspelled names, upgrades and the '
                       'things to look at, each with ticks, and "Do everything for" that job.', [])
        if not probs and not ups:
            self._card('good', 'All good', 'Every set loads, every item is real and wearable, and wsdist found nothing better '
                       'among the gear you own.', [])

    def show_problems(self, kind=None):
        """Problems tab showing only that kind (Start here's "Show me")."""
        for k, v in self.kind_on.items():
            v.set(kind is None or k == kind)
        self.only_fix.set(False)
        self.fill_problems()
        for fid in self.prob.get_children():
            self.prob.item(fid, open=True)
        self.nb.select(self.tab_problems)

    def fix_all_misspelled(self):
        """Tick every misspelled name that has a fix, then the usual confirm list."""
        self.show_problems('unknown')
        by_file = {}
        for row, (path, edit) in self.rows.items():
            if edit[0] == 'rename':
                by_file.setdefault(path, []).append(edit)
        if by_file:
            self._apply(by_file)

    def show_upgrade_for(self, path, set_path):
        self.nb.select(self.tab_upgrades)
        for row, (pth, edit) in self.rows.items():
            if edit[0] == 'slots' and pth == path and edit[1] == set_path:
                self.upg.see(row)
                self.upg.selection_set(row)
                self.show_upgrade()
                break

    def show_guide(self):
        w = tk.Toplevel(self)
        w.title('How to use GearSwap Doctor')
        w.geometry('820x560')
        t = tk.Text(w, wrap='word', font=('Segoe UI', 10), padx=12, pady=10)
        t.insert('1.0', GUIDE)
        t.config(state='disabled')
        t.pack(fill='both', expand=True)
        ttk.Button(w, text='Close', command=w.destroy).pack(pady=6)

    # ------------------------------------------------------------------ Add features
    # His request 2026-10-30: "add a suggestion, that will let the user add relevant features or suggested features to
    # the gearswap. make sure that it has a full suite of options. then this app should be able to implement them
    # within the gearswap". Left: the features (★ suggested, with why); right: what it does and its options (his own
    # gear in the lists); then "Add ticked features to this file" (features.py writes one block at the end of the file).
    def _features_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.tab_feat = tab
        self.nb.add(tab, text='★ Add features')
        top = ttk.Frame(tab)
        top.pack(fill='x')
        ttk.Label(top, text='GearSwap file').pack(side='left')
        self.feat_file = ttk.Combobox(top, state='readonly', width=34)
        self.feat_file.pack(side='left', padx=6)
        self.feat_file.bind('<<ComboboxSelected>>', lambda e: self.feat_load())
        self.feat_style = ttk.Label(top, text='', foreground='#555')
        self.feat_style.pack(side='left', padx=6)
        b = ttk.Button(top, text='☑ Tick the suggested ones', command=self.feat_tick_suggested)
        b.pack(side='right')
        ToolTip(b, 'Ticks every feature marked ★ (suggested for this job and your gear). Nothing changes in the file yet.')
        ttk.Label(tab, text='Click a feature to see what it does and set its options. Click its box (or press Space) to '
                            'tick it. ★ = suggested for this job and your gear. Your own GearSwap rules stay as they are: '
                            'the features run after them and add their gear on top.',
                  foreground='#555', wraplength=1100, justify='left').pack(anchor='w', pady=(4, 6))
        pw = ttk.PanedWindow(tab, orient='horizontal')
        pw.pack(fill='both', expand=True)
        left = ttk.Frame(pw)
        t = ttk.Treeview(left, columns=('why', 'state'), show='tree headings', selectmode='browse')
        t.heading('#0', text='Feature')
        t.column('#0', width=250)
        t.heading('why', text='Suggested because')
        t.column('why', width=210)
        t.heading('state', text='In this file')
        t.column('state', width=100)
        t.tag_configure('sug', foreground='#2e7d32')
        t.tag_configure('group', font=('Segoe UI', 9, 'bold'))
        sb = ttk.Scrollbar(left, orient='vertical', command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        t.bind('<Button-1>', self._feat_click)
        t.bind('<space>', lambda e: self._feat_toggle(self.feat_cur))
        t.bind('<<TreeviewSelect>>', lambda e: self.feat_show())
        self.feat_tree = t
        pw.add(left, weight=3)
        right = ttk.Frame(pw, padding=(10, 0, 0, 0))
        pw.add(right, weight=4)
        def place(e, done=[]):                                # the list left, the options right (once, when shown)
            if not done and e.width > 900:
                done.append(1)
                pw.sashpos(0, min(600, e.width - 540))
        pw.bind('<Configure>', place)
        self.feat_title = ttk.Label(right, text='', font=('Segoe UI', 12, 'bold'))
        self.feat_title.pack(anchor='w')
        self.feat_what = ttk.Label(right, text='', wraplength=500, justify='left')
        self.feat_what.pack(anchor='w', pady=(2, 4))
        self.feat_note = ttk.Label(right, text='', wraplength=500, justify='left', foreground='#b36b00')
        self.feat_note.pack(anchor='w')
        self.feat_cmds = ttk.Label(right, text='', justify='left', foreground='#2e5c8a', font=MONO, wraplength=500)
        self.feat_cmds.pack(side='bottom', anchor='w')
        # (scrolls: Aftermath has gear lists for each level)
        holder = ttk.Frame(right)
        holder.pack(fill='both', expand=True, pady=6)
        canvas = tk.Canvas(holder, highlightthickness=0)
        bar = ttk.Scrollbar(holder, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        self.feat_opts = ttk.LabelFrame(canvas, text='Options', padding=8)
        canvas.create_window((0, 0), window=self.feat_opts, anchor='nw')
        self.feat_opts.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>', lambda ev: canvas.yview_scroll(-1 if ev.delta > 0 else 1, 'units')))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))
        for button, step in (('<Button-4>', -1), ('<Button-5>', 1)):   # (Linux's mouse wheel)
            self.feat_opts.bind(button, lambda e, n=step: canvas.yview_scroll(n, 'units'))
            canvas.bind(button, lambda e, n=step: canvas.yview_scroll(n, 'units'))
        bottom = ttk.Frame(tab)
        bottom.pack(fill='x', pady=(6, 0))
        b1 = ttk.Button(bottom, text='✔ Add ticked features to this file', style='Big.TButton', command=self.feat_apply)
        b1.pack(side='left')
        ToolTip(b1, 'Writes the ticked features into the GearSwap file (and takes out the ones you unticked). You see '
                    'the list first; the file is backed up and checked before it is written.')
        ttk.Button(bottom, text='Take them all out of this file', command=self.feat_remove).pack(side='left', padx=8)
        ttk.Button(bottom, text='Show the code it adds', command=self.feat_code).pack(side='left')
        self.feat_status = ttk.Label(bottom, text='', foreground='#555', wraplength=560, justify='left')
        self.feat_status.pack(side='left', padx=10)
        self.feat_conf, self.feat_paths, self.feat_sug, self.feat_src, self.feat_sets = {}, {}, {}, '', []
        self.feat_have, self.feat_path, self.feat_cur, self.feat_job = set(), None, None, None
        self._owned_cache = {}
        self._feat_dirty = True
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.feat_load() if self._feat_dirty and
                     str(self.nb.select()) == str(self.tab_feat) else None, add='+')

    def feat_owned(self, job, force=False):
        """The gear this character owns that the job can wear (from the saved bags). Without force, nothing until the
        item list is loaded (it loads in the background at start)."""
        if self.items is None and not force:
            return []
        p = os.path.join(doctor.DATA, f'bags_{self.who.get()}.json')
        try:
            stamp = os.path.getmtime(p)
        except OSError:
            return []
        key = (self.who.get(), job, stamp)
        if key not in self._owned_cache:
            if self.items is None:
                self.items = checks.Items()
            try:
                snap = json.load(open(p, encoding='utf-8'))
            except (OSError, ValueError):
                return []
            self._owned_cache[key] = features.owned_items(self.items, snap.get('bags', {}), job)
        return self._owned_cache[key]

    def feat_fill_files(self):
        files = doctor.files_for(self.who.get())
        self.feat_paths = {os.path.basename(f): f for f in files}
        names = list(self.feat_paths)
        self.feat_file.configure(values=names)
        if names and self.feat_file.get() not in names:
            self.feat_file.set(names[0])
        if not names:
            self.feat_file.set('')
        self._feat_dirty = True
        if str(self.nb.select()) == str(self.tab_feat):
            self.feat_load()

    def open_features(self, job):
        files = self._files_of(job)
        if files and os.path.basename(files[0]['path']) in self.feat_paths:
            self.feat_file.set(os.path.basename(files[0]['path']))
            self._feat_dirty = True
        self.nb.select(self.tab_feat)
        if self._feat_dirty:
            self.feat_load()

    def feat_load(self):
        self._feat_dirty = False
        t = self.feat_tree
        t.delete(*t.get_children())
        name = self.feat_file.get()
        path = self.feat_paths.get(name)
        self.feat_path = path
        if not path:
            self.feat_style.config(text='No GearSwap files for this character.')
            return
        try:
            self.feat_src = open(path, encoding='utf-8', errors='replace').read()
        except OSError as e:
            self.feat_style.config(text=str(e))
            return
        job = checks.job_of(name)
        self.feat_job = job
        self.feat_sets = [x['path'] for x in self.loaded_file(path).sets]
        owned = self.feat_owned(job, force=True)
        have = features.read(path)
        self.feat_have = {k for k in have if k in features.BY_KEY}
        self.feat_sug = features.suggest(job, self.feat_src, self.feat_sets, owned)
        self.feat_conf = {}
        for f in features.FEATURES:
            d = features.defaults(f, owned, self.feat_sets)
            if f['key'] in have and isinstance(have[f['key']], dict):
                d.update(have[f['key']])
                d['on'] = True
            else:
                d['on'] = False
            self.feat_conf[f['key']] = d
        sty = features.style_of(self.feat_src)
        self.feat_style.config(text=f"{job or '?'} - " + {'Mote': "a Mote-style file (the features run after Mote's include)",
                                                          'Selindrile': "a Selindrile-style file (the features run after "
                                                                        "Sel-Include)"}.get(sty, 'its own rules (no include)')
                               + ('' if owned else '  -  no saved bags yet: the gear lists are empty (Check now fills them)'))
        for g in features.GROUPS:
            gid = 'g:' + g
            t.insert('', 'end', iid=gid, text=g, open=True, tags=('group',))
            for f in features.FEATURES:
                if f['group'] != g:
                    continue
                t.insert(gid, 'end', iid='f:' + f['key'], text=self._feat_text(f['key']),
                         values=(self.feat_sug.get(f['key'], ''), self._feat_state(f['key'])),
                         tags=('sug',) if f['key'] in self.feat_sug else ())
        self.feat_status.config(text=('In this file now: ' + ', '.join(features.BY_KEY[k]['title'] for k in self.feat_have))
                                if self.feat_have else 'No GearSwap Doctor features in this file yet.')
        first = 'f:' + (self.feat_cur if self.feat_cur in features.BY_KEY else features.FEATURES[0]['key'])
        t.selection_set(first)
        t.see(first)
        self.feat_show()

    def _feat_text(self, key):
        o = self.feat_conf.get(key, {})
        return f"{ON if o.get('on') else OFF} {'★ ' if key in self.feat_sug else ''}{features.BY_KEY[key]['title']}"

    def _feat_state(self, key):
        if key in self.feat_have:
            return '✔ added' + ('' if self.feat_conf.get(key, {}).get('on') else ' (untick = out)')
        if features.already(features.BY_KEY[key], self.feat_src):
            return '⚠ may have it'
        return ''

    def _feat_refresh_row(self, key):
        iid = 'f:' + key
        if self.feat_tree.exists(iid):
            self.feat_tree.item(iid, text=self._feat_text(key), values=(self.feat_sug.get(key, ''), self._feat_state(key)))

    def _feat_click(self, e):
        row = self.feat_tree.identify_row(e.y)
        if row.startswith('f:') and self.feat_tree.identify_column(e.x) == '#0' and e.x < 64:
            self._feat_toggle(row[2:])

    def _feat_toggle(self, key, value=None):
        if key not in self.feat_conf:
            return
        o = self.feat_conf[key]
        o['on'] = (not o.get('on')) if value is None else value
        self._feat_refresh_row(key)

    def _feat_set(self, key, opt, value):
        self.feat_conf[key][opt] = value
        if not self.feat_conf[key].get('on'):
            self._feat_toggle(key, True)          # (changing an option ticks the feature)

    def feat_tick_suggested(self):
        for k in self.feat_sug:
            if k in self.feat_conf:
                self._feat_toggle(k, True)

    def feat_show(self):
        sel = self.feat_tree.selection()
        if not sel or not sel[0].startswith('f:'):
            return
        key = sel[0][2:]
        self.feat_cur = key
        f = features.BY_KEY[key]
        o = self.feat_conf[key]
        owned = self.feat_owned(self.feat_job)
        self.feat_title.config(text=f['title'])
        self.feat_what.config(text=f['what'])
        notes = []
        if key in self.feat_sug:
            notes.append('★ Suggested: ' + self.feat_sug[key] + '.')
        jobs = f.get('jobs')
        if jobs and self.feat_job and self.feat_job not in jobs:
            notes.append(f'Usually not needed for {self.feat_job}.')
        al = features.already(f, self.feat_src)
        if al:
            notes.append('⚠ ' + al + ' - adding this too may double up.')
        if key == 'cancel' and not self._cancel_loaded():
            notes.append("⚠ The Cancel addon isn't loaded at game start here (scripts\\init.txt): type //lua load cancel "
                         "in game, or add the line lua load cancel to init.txt.")
        self.feat_note.config(text='\n'.join(notes))
        for w in self.feat_opts.winfo_children():
            w.destroy()
        box = self.feat_opts
        row = 0
        for k, typ, label, default, extra in f['opts']:
            if typ == 'gear':
                ttk.Label(box, text=label, font=('Segoe UI', 9, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(4, 0))
                row += 1
                gear = o.setdefault(k, {})
                for slot in extra['slots']:
                    vals = ['(none)'] + features.choices(owned, slot, features._catalog(f, slot))
                    cur = gear.get(slot) or '(none)'
                    if cur not in vals:
                        vals.append(cur)
                    ttk.Label(box, text='    ' + SLOT_TEXT.get(slot, slot)).grid(row=row, column=0, sticky='w')
                    cb = ttk.Combobox(box, values=vals, state='readonly', width=30)
                    cb.set(cur)
                    cb.grid(row=row, column=1, sticky='w', pady=1)
                    cb.bind('<<ComboboxSelected>>', lambda e, s_=slot, c=cb, k_=k: self._feat_gear(key, k_, s_, c.get()))
                    row += 1
                continue
            ttk.Label(box, text=label, wraplength=210, justify='left').grid(row=row, column=0, sticky='w', pady=2)
            cur = o.get(k, default)
            if typ in ('set', 'item', 'choice', 'key'):
                if typ == 'set':
                    like = extra.get('like')
                    import re as _re
                    rx = _re.compile(like, _re.I) if like else None
                    vals = ['(none)'] + sorted(self.feat_sets, key=lambda p_: (not (rx and rx.search(p_.replace('sets.', '', 1))),
                                                                               p_.count('.'), p_))
                elif typ == 'item':
                    vals = ['(none)'] + features.choices(owned, extra['slot'], f.get('catalog', {}).get(extra.get('pick'), []))
                elif typ == 'key':
                    vals = features.KEYS
                else:
                    vals = extra['values']
                cur = str(cur) if cur not in (None, '') else '(none)'
                if cur not in vals:
                    vals = vals + [cur]
                cb = ttk.Combobox(box, values=vals, state='readonly', width=30)
                cb.set(cur)
                cb.grid(row=row, column=1, sticky='w')
                cb.bind('<<ComboboxSelected>>', lambda e, k_=k, c=cb, t_=typ: self._feat_set(key, k_, '' if c.get() == '(none)'
                                                                                             and t_ in ('set', 'item') else c.get()))
                if typ == 'key':
                    warn = ttk.Label(box, text=self._key_clash(key, cur), foreground='#b36b00')
                    row += 1
                    warn.grid(row=row, column=1, sticky='w')
                    cb.bind('<<ComboboxSelected>>', lambda e, k_=k, c=cb, w_=warn: (self._feat_set(key, k_, c.get()),
                                                                                    w_.config(text=self._key_clash(key, c.get()))), add='+')
            elif typ == 'int':
                var = tk.StringVar(value=str(cur))
                sp = ttk.Spinbox(box, from_=extra['lo'], to=extra['hi'], increment=extra['step'], textvariable=var, width=8)
                sp.grid(row=row, column=1, sticky='w')

                def changed(*_a, k_=k, v_=var, lo=extra['lo'], hi=extra['hi']):
                    try:
                        n = int(float(v_.get()))
                    except ValueError:
                        return
                    self._feat_set(key, k_, max(lo, min(hi, n)))
                var.trace_add('write', changed)
                sp._var = var
            elif typ == 'bool':
                var = tk.BooleanVar(value=bool(cur))
                ttk.Checkbutton(box, variable=var, command=lambda k_=k, v_=var: self._feat_set(key, k_, bool(v_.get()))).grid(
                    row=row, column=1, sticky='w')
                box._keep = getattr(box, '_keep', []) + [var]
            elif typ in ('text', 'items'):
                var = tk.StringVar(value=', '.join(cur) if isinstance(cur, (list, tuple)) else str(cur or ''))
                en = ttk.Entry(box, textvariable=var, width=36)
                en.grid(row=row, column=1, columnspan=2, sticky='w')
                var.trace_add('write', lambda *_a, k_=k, v_=var: self._feat_set(key, k_, v_.get()))
                en._var = var
                if typ == 'items':
                    row += 1
                    ttk.Label(box, text='(item names, separated by commas)', foreground='#777').grid(row=row, column=1, sticky='w')
            row += 1
        if key == 'aftermath':
            ttk.Separator(box).grid(row=row, column=0, columnspan=2, sticky='ew', pady=6)
            self.feat_am_text = ttk.Label(box, text=features.am_words(self.feat_sets), wraplength=420, justify='left')
            self.feat_am_text.grid(row=row + 1, column=0, columnspan=2, sticky='w')
            ult = sorted({it['en'] for it in owned if features.fits(it, 'main') and rema.family(it['en']) not in (None, 'Aeonic')})
            ttk.Label(box, text='A set for no weapon in particular: judge it with').grid(row=row + 2, column=0, sticky='w', pady=(4, 0))
            self.feat_am_weapon = ttk.Combobox(box, values=['(your file decides)'] + ult, state='readonly', width=30)
            self.feat_am_weapon.set('(your file decides)')
            self.feat_am_weapon.grid(row=row + 2, column=1, sticky='w', pady=(4, 0))
            self.feat_am_btn = ttk.Button(box, text='Make the missing Aftermath sets from my gear...', command=self.feat_am_make)
            self.feat_am_btn.grid(row=row + 3, column=0, columnspan=2, sticky='w', pady=(4, 0))
            ToolTip(self.feat_am_btn, 'wsdist finds the best set for each Ultimate Weapon you own that has no Aftermath set yet, with Aftermath up. '
                                      'You see exactly what goes in the file before anything is written.')
        cmds = list(features.COMMANDS.get(key, []))
        if cmds:
            self.feat_cmds.config(text='In game:\n  ' + '\n  '.join(cmds) + '\n  //gs c gsd help')
        else:
            self.feat_cmds.config(text='Works by itself in game - nothing to type.')

    def feat_am_make(self):
        """The sets the Aftermath feature looks for, made with wsdist. His request 2026-10-30: 'look or add gear settings for different levels of aftermath'."""
        if not self.ws_ready:
            messagebox.showinfo('GearSwap Doctor', 'wsdist is still loading - try again in a moment.')
            return
        path, job, who = self.feat_path, self.feat_job, self.who.get()
        sub = (self.cfg.get('subs') or {}).get(job, 'WAR')
        buffs = W.buff_spec(self.cfg.get('buffs', 'party'), self.cfg.get('buffs_custom'), 'auto')
        prefer = self.feat_am_weapon.get()
        self.feat_am_btn.config(state='disabled')
        self.feat_am_text.config(text='wsdist is working ...')

        def work():
            try:
                ld = self.loaded_file(path)
                items = self.items or checks.Items()
                bags = checks.load_bags(who) or {}
                owned_ids = set()
                for b, c in bags.items():
                    if not b.startswith('_') and b in checks.EQUIP_BAGS:
                        owned_ids |= set(c)
                index = W.gear_index()
                todo, have = doctor.am_missing(ld, job, sub, owned_ids, items, index, prefer)
                made = [doctor.am_build(ld, m, job, sub, owned_ids, items, index, buffs, self.cfg.get('ws_tp', 1000), self.cfg.get('enemy', 'Apex Toad'),
                                        self.cfg.get('tp_metric', 'time')) for m in todo]
                self.after(0, lambda: self._feat_am_done(path, ld, made, have))
            except Exception as e:
                self.after(0, lambda e=e: self._feat_am_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _feat_am_failed(self, e):
        self.feat_am_btn.config(state='normal')
        self.feat_am_text.config(text=f'wsdist could not do it: {e}')

    def _feat_am_done(self, path, ld, made, have):
        self.feat_am_btn.config(state='normal')
        if not made:
            self.feat_am_text.config(text=features.am_words(self.feat_sets) + (' Nothing missing for ' + ', '.join(have) + '.' if have else
                                     ' You own no Ultimate Weapon this job can use that wsdist can count.'))
            return
        anchors = [s['path'] for s in ld.sets]
        self.feat_am_text.config(text='; '.join(f"{m['path']} for {m['weapon']}" for m in made))
        if self._apply({path: [('new', m['path'], m['gear'], anchors) for m in made]}) is not False:
            self.feat_load()
        else:
            self.feat_am_text.config(text=features.am_words(self.feat_sets))

    def _feat_gear(self, key, opt, slot, value):
        g = dict(self.feat_conf[key].get(opt) or {})
        if value in ('', '(none)'):
            g.pop(slot, None)
        else:
            g[slot] = value
        self._feat_set(key, opt, g)

    def _key_clash(self, key, label):
        b = features.bind_key(label)
        if not b:
            return ''
        for k, o in self.feat_conf.items():
            if k != key and o.get('on') and features.bind_key(o.get('key', '')) == b:
                return f"⚠ also used by {features.BY_KEY[k]['title']}"
        import re as _re
        if _re.search(r"bind\s+" + _re.escape(b) + r"\b", self.feat_src, _re.I):
            return '⚠ your file binds this key already'
        if features.style_of(self.feat_src) == 'Mote' and b in ('f9', 'f10', 'f11', 'f12', '^f9', '^f10', '^f11', '!f9', '!f10', '!f11', '!f12'):
            return "⚠ Mote's include uses this key"
        return ''

    def _cancel_loaded(self):
        try:
            txt = open(os.path.join(checks.WINDOWER, 'scripts', 'init.txt'), encoding='utf-8', errors='replace').read()
        except OSError:
            return False
        import re as _re
        return bool(_re.search(r'^\s*lua\s+(load|l)\s+cancel\b', txt, _re.I | _re.M))

    def _feat_ticked(self):
        return {k: o for k, o in self.feat_conf.items() if o.get('on')}

    def feat_apply(self):
        path = self.feat_path
        if not path:
            return
        on = self._feat_ticked()
        if not on and not self.feat_have:
            messagebox.showinfo('GearSwap Doctor', 'Tick at least one feature first (click its box).')
            return
        miss = features.missing(self.feat_conf)
        conf = {k: dict(o) for k, o in self.feat_conf.items()}
        if miss:
            if not messagebox.askyesno('GearSwap Doctor', 'These have no gear / set picked yet, so they would do nothing:\n\n  '
                                       + '\n  '.join(miss) + '\n\nAdd the others without them?'):
                return
            for k, o in conf.items():
                if features.BY_KEY[k]['title'] in miss:
                    o['on'] = False
        add = [features.BY_KEY[k]['title'] for k, o in conf.items() if o.get('on')]
        out = [features.BY_KEY[k]['title'] for k in self.feat_have if not conf.get(k, {}).get('on')]
        msg = os.path.basename(path) + ':\n'
        if add:
            msg += '\nAdd / keep:\n  - ' + '\n  - '.join(add) + '\n'
        if out:
            msg += '\nTake out:\n  - ' + '\n  - '.join(out) + '\n'
        msg += ('\nThe file is backed up first and checked before it is written. Your own rules stay as they are.\n\n'
                'In game, on that character: //gs reload  -  then //gs c gsd help for the commands.')
        if not messagebox.askyesno('GearSwap Doctor - add features', msg):
            return
        try:
            bk, names = features.apply(path, conf)
        except (fixer.EditError, OSError) as e:
            messagebox.showerror('GearSwap Doctor', f'Nothing was changed: {e}')
            return
        self.loaded.pop(path, None)
        self.feat_load()
        if bk is None:
            self.feat_status.config(text='Nothing to change - the file already has exactly these.')
            return
        self.fill_backups()
        self.feat_status.config(text=('Done: ' + ', '.join(names) if names else 'Done: the features were taken out')
                                + f'. Backup: {os.path.basename(os.path.dirname(bk))}. In game: //gs reload')
        messagebox.showinfo('GearSwap Doctor', ('Added to ' + os.path.basename(path) + ':\n  - ' + '\n  - '.join(names)
                                                if names else 'The features were taken out of ' + os.path.basename(path))
                            + '\n\nIn game, on that character: //gs reload\nThen //gs c gsd help shows the commands.')

    def feat_remove(self):
        if not self.feat_path or not self.feat_have:
            messagebox.showinfo('GearSwap Doctor', 'This file has no GearSwap Doctor features.')
            return
        if not messagebox.askyesno('GearSwap Doctor', 'Take every GearSwap Doctor feature out of ' + os.path.basename(self.feat_path)
                                   + '? The file is backed up first; your own rules are not touched.'):
            return
        try:
            bk, _ = features.remove(self.feat_path)
        except (fixer.EditError, OSError) as e:
            messagebox.showerror('GearSwap Doctor', f'Nothing was changed: {e}')
            return
        self.loaded.pop(self.feat_path, None)
        self.feat_load()
        self.fill_backups()
        self.feat_status.config(text='Taken out. In game: //gs reload')

    def feat_code(self):
        w = tk.Toplevel(self)
        w.title('The code GearSwap Doctor adds')
        w.geometry('860x560')
        t = tk.Text(w, wrap='none', font=MONO, padx=8, pady=8)
        on = self._feat_ticked()
        t.insert('1.0', (features.render(on) if on else '-- (nothing ticked)\n') + '\n-- It goes at the very end of '
                 + os.path.basename(self.feat_path or 'the file') + '.\n-- The shared code, gsd-features.lua, is put next to '
                 'it (GearSwap\'s data folder) - one copy for all your files.')
        t.config(state='disabled')
        t.pack(fill='both', expand=True)
        ttk.Button(w, text='Close', command=w.destroy).pack(pady=6)

    # ------------------------------------------------------------------ Healing
    # His request 2026-10-30: "do research, and figure out how to add in a features for healing and making healing sets".
    # healing.py has the game's formulas (wsdist has none): every healing set of the file with what it heals now, and the
    # best one from his own gear, for the spell he picks, with what it must also have. His numbers stay per set.
    def _healing_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.tab_heal = tab
        self.nb.add(tab, text='★ Healing')
        top = ttk.Frame(tab)
        top.pack(fill='x')
        one = ttk.LabelFrame(top, text='1. The healing set', padding=6)
        one.pack(side='left', fill='both', expand=True)
        bar = ttk.Frame(one)
        bar.pack(fill='x')
        ttk.Label(bar, text='File').pack(side='left')
        self.heal_file = ttk.Combobox(bar, state='readonly', width=26)
        self.heal_file.pack(side='left', padx=4)
        self.heal_file.bind('<<ComboboxSelected>>', lambda e: self.heal_load())
        ttk.Label(bar, text='Sub job').pack(side='left', padx=(8, 0))
        self.heal_sub = ttk.Combobox(bar, values=JOBS, state='readonly', width=5)
        self.heal_sub.pack(side='left', padx=4)
        self.heal_sub.bind('<<ComboboxSelected>>', lambda e: self.heal_load(keep_sub=True))
        fr = ttk.Frame(one)
        fr.pack(fill='both', expand=True, pady=(4, 0))
        t = ttk.Treeview(fr, columns=('now', 'note'), show='tree headings', selectmode='browse', height=8)
        t.heading('#0', text='Set')
        t.column('#0', width=190)
        t.heading('now', text='Now')
        t.column('now', width=115)
        t.heading('note', text='')
        t.column('note', width=150)
        t.tag_configure('miss', foreground='#b36b00')
        t.tag_configure('over', foreground='#c0392b')
        sb = ttk.Scrollbar(fr, orient='vertical', command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        t.bind('<<TreeviewSelect>>', lambda e: self.heal_show())
        self.heal_tree = t

        two = ttk.LabelFrame(top, text='2. What it is judged on', padding=6)
        two.pack(side='left', fill='both', padx=(8, 0))
        self.heal_how = ttk.Label(two, text='', wraplength=300, justify='left', foreground='#555')
        self.heal_how.grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Label(two, text='Spell').grid(row=1, column=0, sticky='w', pady=(4, 0))
        self.heal_spell = ttk.Combobox(two, state='readonly', width=18)
        self.heal_spell.grid(row=1, column=1, columnspan=3, sticky='w', padx=4, pady=(4, 0))
        self.heal_spell.bind('<<ComboboxSelected>>', lambda e: self._heal_now())
        ttk.Label(two, text='Day / weather').grid(row=2, column=0, sticky='w')
        self.heal_day = ttk.Combobox(two, state='readonly', width=32, values=list(healing.DAYWX))
        self.heal_day.set(list(healing.DAYWX)[0])
        self.heal_day.grid(row=2, column=1, columnspan=3, sticky='w', padx=4, pady=2)
        self.heal_day.bind('<<ComboboxSelected>>', lambda e: self._heal_now())
        ToolTip(self.heal_day, 'Light day and weather make cures stronger. With a Hachirin-no-Obi the bonus always happens; '
                               'without it only sometimes. Picks the Obi when it helps.')
        self.heal_base = {}
        rows = (('MND', 'MND', 0, 1, 500), ('VIT', 'VIT', 0, 3, 500), ('CHR', 'CHR', 1, 1, 500), ('skill', 'Healing skill', 1, 3, 800),
                ('jp', 'Cure power (job points)', 2, 1, 200), ('fast', 'Fast Cast from job', 2, 3, 80))
        for k, label, r, c, top_ in rows:
            ttk.Label(two, text=label).grid(row=3 + r, column=c - 1, sticky='w', padx=(0 if c == 1 else 8, 0))
            v = tk.IntVar(value=0)
            ttk.Spinbox(two, from_=0, to=top_, textvariable=v, width=5, command=self._heal_now).grid(row=3 + r, column=c, sticky='w', padx=3, pady=1)
            self.heal_base[k] = v
        ttk.Label(two, text='(without gear - change them if yours differ)', foreground='#777').grid(row=6, column=0, columnspan=4, sticky='w')

        three = ttk.LabelFrame(top, text='3. It must also have', padding=6)
        three.pack(side='left', fill='both', padx=(8, 0))
        self.heal_need = {}
        for i, (k, label, tip) in enumerate((
                ('enmity', 'Enmity -', 'Less hate from curing. The gear cap is -50.'),
                ('dt', 'Damage taken (DT) %', 'Counts for both physical and magic. 50 at most.'),
                ('pdt', 'Physical (PDT) %', 'From weapons and physical TP moves.'),
                ('mdt', 'Magic (MDT) %', 'From spells and magic TP moves.'),
                ('conserve', 'Conserve MP', 'A chance of the spell costing less.'),
                ('sird', 'Interruption -%', 'Spell Interruption Rate Down: for tanks curing while being hit.'))):
            lb = ttk.Label(three, text=label)
            lb.grid(row=i, column=0, sticky='w')
            ToolTip(lb, tip)
            v = tk.IntVar(value=0)
            ttk.Spinbox(three, from_=0, to=110, textvariable=v, width=5).grid(row=i, column=1, sticky='w', padx=4, pady=1)
            self.heal_need[k] = v
        self.heal_keep = tk.BooleanVar(value=False)
        ttk.Checkbutton(three, text='Keep my weapons', variable=self.heal_keep).grid(row=6, column=0, columnspan=2, sticky='w', pady=(4, 0))
        self.heal_solace = tk.BooleanVar(value=False)
        self.heal_solace_box = ttk.Checkbutton(three, text='Count Solace stoneskin', variable=self.heal_solace)
        self.heal_solace_box.grid(row=7, column=0, columnspan=2, sticky='w')

        btns = ttk.Frame(tab)
        btns.pack(fill='x', pady=6)
        b = ttk.Button(btns, text='4. Build the best set from my gear', style='Big.TButton', command=self.heal_build)
        b.pack(side='left')
        ToolTip(b, 'Tries your gear (inventory and wardrobes) until nothing helps. Same gear, same answer. Nothing changes in the '
                   'file until you put it in.')
        self.heal_put_btn = ttk.Button(btns, text='Put it in this set', command=self.heal_put, state='disabled')
        self.heal_put_btn.pack(side='left', padx=8)
        self.heal_new_btn = ttk.Button(btns, text='Save it as a new set...', command=self.heal_save_new, state='disabled')
        self.heal_new_btn.pack(side='left')
        self.heal_status = ttk.Label(btns, text='', wraplength=560, justify='left')
        self.heal_status.pack(side='left', padx=8)
        res = ttk.LabelFrame(tab, text='Results', padding=6)
        res.pack(fill='both', expand=True)
        self.heal_head = ttk.Label(res, text='', font=('Courier New', 11))
        self.heal_head.pack(anchor='w')
        cols = ttk.Frame(res)
        cols.pack(fill='both', expand=True)
        left, right = ttk.Frame(cols), ttk.Frame(cols)
        left.pack(side='left', fill='both', expand=True, padx=(0, 4))
        right.pack(side='left', fill='both', expand=True)
        self.heal_grid_now = GearGrid(left, 'The set now', lambda: self.items)
        self.heal_grid_now.pack(fill='x')
        self.heal_now_text = ttk.Label(left, text='', justify='left', wraplength=560)
        self.heal_now_text.pack(anchor='w', pady=(4, 0))
        self.heal_grid_best = GearGrid(right, 'Best from your gear', lambda: self.items)
        self.heal_grid_best.pack(fill='x')
        self.heal_best_text = ttk.Label(right, text='', justify='left', wraplength=560)
        self.heal_best_text.pack(anchor='w', pady=(4, 0))
        self.heal_rows, self.heal_paths, self.heal_cur, self.heal_result = {}, {}, None, None
        self._heal_data = None
        self._heal_dirty = True
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.heal_load() if self._heal_dirty and
                     str(self.nb.select()) == str(self.tab_heal) else None, add='+')

    def heal_fill_files(self):
        self.heal_paths = {os.path.basename(f): f for f in doctor.files_for(self.who.get())}
        names = list(self.heal_paths)
        self.heal_file.configure(values=names)
        if self.heal_file.get() not in names:
            first = [n for n in names if checks.job_of(n) in healing.WANTED]
            self.heal_file.set((first or names or [''])[0])
        self._heal_dirty = True
        if str(self.nb.select()) == str(self.tab_heal):
            self.heal_load()

    def open_healing(self, job):
        files = self._files_of(job)
        if files and os.path.basename(files[0]['path']) in self.heal_paths:
            self.heal_file.set(os.path.basename(files[0]['path']))
            self._heal_dirty = True
        self.nb.select(self.tab_heal)
        if self._heal_dirty:
            self.heal_load()

    def _heal_values(self, vars_):
        out = {}
        for k, v in vars_.items():
            try:
                out[k] = int(v.get())
            except (tk.TclError, ValueError):
                out[k] = 0
        return out

    def _heal_base(self):
        """His numbers without gear, plus the day / weather of this set."""
        b = dict(self._heal_defaults)
        b.update(self._heal_values(self.heal_base))
        b['daywx'] = healing.DAYWX.get(self.heal_day.get(), 0)
        return b

    def _heal_cands(self, job):
        """Every item this job can wear that he owns (once per augmented copy his files name), and how many of each."""
        if self._heal_data is None:
            self._heal_data = healing.ItemData()
        owned = self.feat_owned(job, force=True)
        loaded = []
        for p in self.heal_paths.values():
            try:
                loaded.append(self.loaded_file(p))
            except Exception:
                pass
        counts = {}
        try:
            snap = json.load(open(os.path.join(doctor.DATA, f'bags_{self.who.get()}.json'), encoding='utf-8'))
            for bag, content in snap.get('bags', {}).items():
                if bag in checks.EQUIP_BAGS:
                    for n, c in content.items():
                        counts[n] = counts.get(n, 0) + c
        except (OSError, ValueError):
            pass
        return healing.candidates(owned, self._heal_data, healing.known_augments(loaded)), counts

    def heal_load(self, keep_sub=False):
        self._heal_dirty = False
        t = self.heal_tree
        t.delete(*t.get_children())
        self.heal_rows = {}
        self.heal_result = None
        name = self.heal_file.get()
        path = self.heal_paths.get(name)
        if not path:
            self.heal_status.config(text='No GearSwap files for this character.')
            return
        job = checks.job_of(name) or 'WHM'
        if not keep_sub:
            self.heal_sub.set(self.cfg['subs'].get(job, 'WHM' if job in ('RDM', 'PLD', 'RUN') else 'SCH' if job == 'WHM' else 'WAR'))
        sub = self.heal_sub.get()
        self._heal_defaults = healing.defaults(job, sub)
        mine = (self.cfg.get('heal_stats') or {}).get(job) or {}
        for k, v in self.heal_base.items():
            v.set(int(mine.get(k, self._heal_defaults.get(k, 0))))
        self._heal_job, self._heal_path = job, path
        if self.items is None:
            self.items = checks.Items()
        if self._heal_data is None:
            self._heal_data = healing.ItemData()
        ld = self.loaded_file(path)
        base = self._heal_base()
        first = None
        for s in healing.find_sets(ld):
            spell = healing.spell_for_set(s['kind'], s['path'], job, sub)
            cur = healing.set_to_gear(s['gear'], self.items, self._heal_data)
            v, tot = healing.evaluate(s['kind'], cur, base, spell)
            note = healing.short_note(s['kind'], tot, base)
            row = t.insert('', 'end', text=s['path'][len('sets.'):], values=(healing.fmt_value(s['kind'], v), note),
                           tags=('over',) if 'wasted' in note else ())
            self.heal_rows[row] = {'path': s['path'], 'kind': s['kind'], 'gear': s['gear'], 'new': False}
            first = first or row
        for k in healing.missing_sets(ld, job, sub):
            row = t.insert('', 'end', text='＋ ' + healing.NEW_PATH[k][len('sets.'):], values=('none yet', healing.KINDS[k]['title']), tags=('miss',))
            self.heal_rows[row] = {'path': healing.NEW_PATH[k], 'kind': k, 'gear': {}, 'new': True}
            first = first or row
        self.heal_status.config(text='' if first else f'No healing sets in {name}, and {job} / {sub} doesn\'t usually need any.')
        if first:
            t.selection_set(first)
            t.see(first)
            self.heal_show()
        else:
            self.heal_head.config(text='')
            self.heal_grid_now.show({})
            self.heal_grid_best.show({})

    def heal_show(self):
        sel = self.heal_tree.selection()
        rec = self.heal_rows.get(sel[0]) if sel else None
        if not rec:
            return
        self.heal_cur = rec
        kind = rec['kind']
        K = healing.KINDS[kind]
        job, sub = self._heal_job, self.heal_sub.get()
        self.heal_how.config(text=K['title'] + ': ' + K['how'])
        h = healing.hints(rec['path'], job)
        saved = ((self.cfg.get('heal_targets') or {}).get(os.path.basename(self._heal_path)) or {}).get(rec['path']) or {}
        spell = saved.get('spell') or healing.spell_for_set(kind, rec['path'], job, sub)
        self.heal_spell.configure(values=K['spells'], state='readonly' if K['spells'] else 'disabled')
        self.heal_spell.set(spell or '')
        days = list(healing.DAYWX)
        self.heal_day.set(saved.get('day') or next((d for d in days if healing.DAYWX[d] == h['daywx']), days[0]))
        need = saved.get('need', h['need'])
        for k, v in self.heal_need.items():
            v.set(int(need.get(k, 0)))
        self.heal_keep.set(saved.get('keep', h['keep_weapons']))
        self.heal_solace.set(saved.get('solace', h['solace'] and kind == 'cure'))
        self.heal_solace_box.config(state='normal' if kind == 'cure' else 'disabled')
        self._heal_now()

    def _heal_now(self):
        """The set as it is, with the numbers as they are now."""
        rec = self.heal_cur
        if not rec:
            return
        self.heal_result = None
        self.heal_put_btn.config(state='disabled')
        self.heal_new_btn.config(state='disabled')
        base = self._heal_base()
        spell = self.heal_spell.get() or None
        cur = healing.set_to_gear(rec['gear'], self.items, self._heal_data)
        v, tot = healing.evaluate(rec['kind'], cur, base, spell)
        self.heal_head.config(text=('(this set is not in the file yet)' if rec['new'] else
                                    f"{spell or healing.KINDS[rec['kind']]['title']}: {healing.fmt_value(rec['kind'], v)}"))
        self.heal_grid_now.show({s: c['name'] for s, c in cur.items()})
        self.heal_grid_best.show({})
        self.heal_now_text.config(text='' if rec['new'] else '\n'.join(healing.describe(rec['kind'], tot, base, v, spell)))
        self.heal_best_text.config(text='')

    def heal_build(self, wait=False):
        rec = self.heal_cur
        if not rec:
            messagebox.showinfo('GearSwap Doctor', 'Pick a set on the left first.')
            return
        job, sub = self._heal_job, self.heal_sub.get()
        base = self._heal_base()
        spell = self.heal_spell.get() or None
        need = {k: v for k, v in self._heal_values(self.heal_need).items() if v}
        keep, solace, kind = bool(self.heal_keep.get()), bool(self.heal_solace.get()), rec['kind']
        cur = healing.set_to_gear(rec['gear'], self.items, self._heal_data)
        cands, counts = self._heal_cands(job)
        if not cands:
            self.heal_status.config(text='No saved bags for this character yet: Check now makes the list (from Steward or findAll).')
            return
        # remembered per set
        allt = self.cfg.setdefault('heal_targets', {})
        allt.setdefault(os.path.basename(self._heal_path), {})[rec['path']] = {'spell': spell, 'day': self.heal_day.get(), 'need': need,
                                                                               'keep': keep, 'solace': solace}
        stats = self.cfg.setdefault('heal_stats', {})
        stats[job] = self._heal_values(self.heal_base)
        save_settings({'heal_targets': allt, 'heal_stats': stats})
        self.heal_status.config(text='Trying your gear ...')
        self.progress.config(mode='indeterminate'); self.progress.start(12)

        def work():
            try:
                best, val, now = healing.build(kind, cands, cur, base, job, sub, spell=spell, need=need, keep_weapons=keep, solace=solace, counts=counts)
                done = lambda: self._heal_done(rec, cur, best, val, now, base, spell, need, keep)  # noqa: E731
            except Exception as e:
                done = lambda e=e: self._heal_failed(e)  # noqa: E731
            self.after(0, done) if not wait else done()
        if wait:
            work()
        else:
            threading.Thread(target=work, daemon=True).start()

    def _heal_failed(self, e):
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        self.heal_status.config(text=f'Could not build it: {e}')

    def _heal_done(self, rec, cur, best, val, now, base, spell, need, keep):
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        kind = rec['kind']
        v0, t0 = healing.evaluate(kind, cur, base, spell)
        v1, t1 = healing.evaluate(kind, best, base, spell)
        ch = healing.changes(cur, best, keep)
        names = {s: c['name'] for s, c in best.items()}
        self.heal_grid_now.show({s: c['name'] for s, c in cur.items()}, {s: '#fbe3c4' for s in ch})
        self.heal_grid_best.show(names, {s: '#c8efc0' for s in ch if s in names})
        self.heal_now_text.config(text='' if rec['new'] else '\n'.join(healing.describe(kind, t0, base, v0, spell)))
        self.heal_best_text.config(text='\n'.join(healing.describe(kind, t1, base, v1, spell)))
        label = spell or healing.KINDS[kind]['title']
        self.heal_head.config(text=f'{label}:  ' + (f'best {healing.fmt_value(kind, v1)}' if rec['new'] else
                                                    f'your set {healing.fmt_value(kind, v0)}   ->   best {healing.fmt_value(kind, v1)}'))
        short = healing.shortfall(t1, need)
        words = []
        if short:
            words.append(f"⚠ Your gear can't reach everything in part 3: this is the closest ({short} short in all).")
        elif need:
            words.append('✔ It has everything in part 3.')
        if not ch:
            words.append('Your set is already the best your gear can do for this.')
        if rec['new']:
            sty = features.style_of(open(self._heal_path, encoding='utf-8', errors='replace').read())
            if sty == 'plain':
                words.append('Your file has its own rules: also tick "Healing sets go on for healing spells" in Add features.')
        self.heal_status.config(text=' '.join(words))
        self.heal_result = {'rec': rec, 'changes': ch, 'gear': {s: healing.gs_name(c) for s, c in best.items()
                                                                if not (keep and s in ('main', 'sub'))}}
        self.heal_put_btn.config(text='Add this set to the file' if rec['new'] else 'Put it in this set',
                                 state='normal' if (ch or rec['new']) and self.heal_result['gear'] else 'disabled')
        self.heal_new_btn.config(state='normal' if self.heal_result['gear'] and not rec['new'] else 'disabled')

    def _heal_after_apply(self):
        self.loaded.pop(self._heal_path, None)
        self._heal_dirty = True
        self.heal_load(keep_sub=True)

    def heal_put(self):
        r = self.heal_result
        if not r:
            return
        rec = r['rec']
        if rec['new']:
            anchors = [s['path'] for s in self.loaded_file(self._heal_path).sets]
            edit = ('new', rec['path'], dict(r['gear']), anchors)
        else:
            edit = ('slots', rec['path'], dict(r['changes']))
        if self._apply({self._heal_path: [edit]}) is not False:
            self._heal_after_apply()

    def heal_save_new(self):
        r = self.heal_result
        if not r:
            return
        rec = r['rec']
        from tkinter import simpledialog
        name = simpledialog.askstring('GearSwap Doctor - save as a new set',
                                      f"A name for the new set. It goes right after {rec['path']} in the file:\n\n"
                                      f"    {rec['path']}.<name>\n\nFor example Solace, DT, SIRD. (GearSwap only uses it when your "
                                      "file's rules ask for it.)", initialvalue='DT', parent=self)
        if not name:
            return
        name = name.strip()
        new_path = rec['path'] + ('.' + name if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name) else '["' + name.replace('"', '') + '"]')
        if self._apply({self._heal_path: [('add', rec['path'], new_path, dict(r['gear']))]}) is not False:
            self._heal_after_apply()

    # ------------------------------------------------------------------ Overview
    def _overview_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text='Overview')
        self.summary = ttk.Label(tab, text='', font=('Segoe UI', 11))
        self.summary.pack(anchor='w', pady=(0, 6))
        frame, self.files_tree = self._tree(tab, ('job', 'sub', 'sets', 'loads', 'problems', 'upgrades', 'best'),
                                            ('Job', 'Sub', 'Sets', 'Loads', 'Problems', 'Upgrades', 'Best gain'),
                                            (60, 50, 60, 70, 300, 90, 90), tree_width=260)
        frame.pack(fill='both', expand=True)
        self.files_tree.heading('#0', text='GearSwap file')
        self.files_tree.bind('<Double-1>', lambda e: self._open_file_sets())
        ws = ttk.LabelFrame(tab, text='wsdist', padding=6)
        ws.pack(fill='x', pady=(8, 0))
        self.ws_label = ttk.Label(ws, text='')
        self.ws_label.pack(side='left')
        self.ws_btn = ttk.Button(ws, text='Check for a wsdist update', command=self.ws_check)
        self.ws_btn.pack(side='left', padx=8)
        ttk.Label(tab, text='Double-click a file to see its sets. Check now reads the files again and asks wsdist for better '
                            'weapon skill sets from the gear you own.', foreground='#666').pack(anchor='w', pady=(6, 0))

    def _open_file_sets(self):
        sel = self.files_tree.selection()
        if not sel:
            return
        path = self.files_tree.item(sel[0], 'tags')[0] if self.files_tree.item(sel[0], 'tags') else None
        self.nb.select(self.tab_sets)
        if path:
            self.fill_sets(focus=path)

    # ------------------------------------------------------------------ Problems
    def _problems_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.tab_problems = tab
        self.nb.add(tab, text='Problems')
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        self.only_fix = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text='Only what I can fix with a click', variable=self.only_fix, command=self.fill_problems).pack(side='left', padx=(0, 16))
        ttk.Label(bar, text='Show').pack(side='left')
        self.kind_on = {}
        self.kind_box = {}
        for k, label in KIND_TEXT.items():
            v = tk.BooleanVar(value=(k != 'missing'))        # (Not owned is mostly noise: off until asked for)
            self.kind_on[k] = v
            cbx = ttk.Checkbutton(bar, text=label, variable=v, command=self.fill_problems)
            cbx.pack(side='left', padx=4)
            self.kind_box[k] = cbx
        ToolTip(self.kind_box['missing'], 'Gear named in your sets that this character does not have. Usually nothing to do, so '
                                          'it is hidden at first - tick it to see the list.')
        frame, self.prob = self._tree(tab, ('level', 'kind', 'item', 'slot', 'detail', 'sets'),
                                      ('Importance', 'What', 'Item / set', 'Slot', 'Details', 'Sets'), (100, 90, 210, 55, 400, 45))
        for lv, col in LEVEL_COLOR.items():
            self.prob.tag_configure(lv, foreground=col if lv != 'info' else '#666')
        frame.pack(fill='both', expand=True)
        self.prob.bind('<Button-1>', self._click_tick)
        self.prob.bind('<<TreeviewSelect>>', lambda e: self._show_info(self.prob, self.prob_text))
        self.prob_text = self._textbox(tab, 6)
        self.prob_text.pack(fill='x', pady=(6, 0))
        ttk.Label(tab, text='Click a row: what it means and what to do show here. Misspelled names have a box - tick it and click '
                            'Apply ticked to fix them.', foreground='#666').pack(anchor='w')

    # ------------------------------------------------------------------ Upgrades
    def _upgrades_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.tab_upgrades = tab
        self.nb.add(tab, text='Upgrades (wsdist)')
        pw = ttk.PanedWindow(tab, orient='horizontal')
        pw.pack(fill='both', expand=True)
        left = ttk.Frame(pw)
        frame, self.upg = self._tree(left, ('gain', 'verdict', 'swaps', 'dmg'), ('Gain', 'Worth it?', 'Items', 'Now -> best'),
                                     (60, 80, 45, 120), tree_width=200)
        self.upg.tag_configure('big', foreground='#2e7d32')
        self.upg.tag_configure('small', foreground='#777')
        frame.pack(fill='both', expand=True)
        self.upg.bind('<Button-1>', self._click_tick)
        self.upg.bind('<<TreeviewSelect>>', lambda e: self.show_upgrade())
        pw.add(left, weight=1)
        right = ttk.Frame(pw, padding=(8, 0, 0, 0))
        self.upg_head = ttk.Label(right, text='Pick a weapon skill on the left.', font=MONO)
        self.upg_head.pack(anchor='w', pady=(0, 4))
        grids = ttk.Frame(right)
        grids.pack(fill='both', expand=True)
        self.grid_now = GearGrid(grids, 'Your set now', lambda: self.items)
        self.grid_now.pack(fill='x', pady=(0, 4))
        self.grid_best = GearGrid(grids, "wsdist's best from your gear", lambda: self.items)
        self.grid_best.pack(fill='x')
        self.upg_text = self._textbox(right, 9)
        self.upg_text.pack(fill='x', pady=(6, 0))
        ub = ttk.Frame(right)
        ub.pack(fill='x')
        ttk.Label(ub, text='Green = a swap. Tick the weapon skill on the left, then Apply ticked.', foreground='#666').pack(side='left')
        ttk.Button(ub, text='Set its damage taken...', command=self._upg_dt).pack(side='right')
        pw.add(right, weight=3)

    def show_upgrade(self):
        sel = self.upg.selection()
        if not sel or sel[0] not in self.rows:
            return
        path, edit = self.rows[sel[0]]
        u = self.info.get(('u', sel[0]))
        if not u:
            return
        now = self.set_gear(path, u['set'])
        best = dict(now)
        best.update(u['changes'])
        marks = {s: '#c8efc0' for s in u['changes']}
        self.upg_head.config(text=f"{u['ws']:<22} now {u['now']:>6}   best {u['best']:>6}   {gain_text(u)}")
        self.grid_now.show(now, {s: '#fbe3c4' for s in u['changes']})
        self.grid_best.show(best, marks)
        where = self.item_bags()
        lines = [f"{verdict_u(u)}: {gain_text(u)} {gain_words(u)} ({nowbest(u)}), "
                 f"{len(u['changes'])} item(s) change - all gear this character already owns."]
        if dt_words(u):
            lines.append(dt_words(u))
        lines += ['', 'The swaps:']
        for slot, new in u['changes'].items():
            old = now.get(slot) or '(empty)'
            bag = where.get(new.lower())
            lines.append(f"  {SLOT_TEXT.get(slot, slot):<7} {old}  ->  {new}" + (f"   (it's in your {bag})" if bag else ''))
        if 0 <= u['gain'] < 5 and not u.get('dt_fix'):
            lines.append('')
            lines.append('A small gain: worth it only if you use this weapon skill a lot.')
        if u['gain'] > 100:
            lines.append('')
            lines.append(BIG_GAIN_NOTE)
        lines += ['', f"{os.path.basename(path)}  -  {u['set']}"] + list(u.get('notes') or [])
        self._say(self.upg_text, '\n'.join(lines))

    def item_bags(self):
        """{item name (lower): 'Mog Wardrobe 2' ...} from the saved bags."""
        try:
            snap = json.load(open(os.path.join(doctor.DATA, f'bags_{self.who.get()}.json'), encoding='utf-8'))
        except (OSError, ValueError):
            return {}
        nice = {'inventory': 'inventory', 'wardrobe': 'Mog Wardrobe'}
        out = {}
        for bag, content in snap.get('bags', {}).items():
            label = nice.get(bag) or (('Mog Wardrobe ' + bag[8:]) if bag.startswith('wardrobe') else bag)
            for n in content:
                out.setdefault(n.lower(), label)
        return out

    # ------------------------------------------------------------------ Sets
    def _sets_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.tab_sets = tab
        self.nb.add(tab, text='Sets')
        pw = ttk.PanedWindow(tab, orient='horizontal')
        pw.pack(fill='both', expand=True)
        left = ttk.Frame(pw)
        frame, self.sets_tree = self._tree(left, ('n',), ('Items',), (50,), tree_width=330)
        frame.pack(fill='both', expand=True)
        self.sets_tree.bind('<<TreeviewSelect>>', lambda e: self.show_set())
        pw.add(left, weight=1)
        right = ttk.Frame(pw, padding=(8, 0, 0, 0))
        self.set_head = ttk.Label(right, text='Pick a set on the left.', font=MONO)
        self.set_head.pack(anchor='w', pady=(0, 4))
        self.grid_set = GearGrid(right, 'Set', lambda: self.items)
        self.grid_set.pack(fill='x')
        sim = ttk.LabelFrame(right, text='wsdist on this set (weapon skill sets)', padding=6)
        sim.pack(fill='x', pady=(8, 0))
        ttk.Label(sim, text='Enemy').pack(side='left')
        self.set_enemy = ttk.Combobox(sim, values=self.enemy_list, width=24, state='readonly')
        self.set_enemy.set(self.cfg['enemy'])
        self.set_enemy.pack(side='left', padx=4)
        ttk.Label(sim, text='TP').pack(side='left', padx=(8, 0))
        self.set_tp = tk.IntVar(value=self.cfg['tp'])
        ttk.Spinbox(sim, from_=1000, to=3000, increment=100, textvariable=self.set_tp, width=6).pack(side='left', padx=4)
        ttk.Button(sim, text='Build it with damage taken...', command=self.set_to_sim).pack(side='left', padx=8)
        self.set_text = self._textbox(right, 6)
        self.set_text.pack(fill='both', expand=True, pady=(6, 0))
        ttk.Label(right, text='Red = broken or misspelled, orange = wrong slot / job, blue = not owned or in storage.',
                  foreground='#666').pack(anchor='w')
        pw.add(right, weight=3)

    def loaded_file(self, path):
        if path not in self.loaded:
            self.loaded[path] = gs_loader.load(path)
        return self.loaded[path]

    def set_gear(self, path, set_path):
        """{gs slot: name} of one set."""
        for s in self.loaded_file(path).sets:
            if s['path'] == set_path:
                return {gs_slot(k): g['name'] for k, g in s['gear'].items() if gs_slot(k)}
        return {}

    def fill_sets(self, focus=None):
        t = self.sets_tree
        t.delete(*t.get_children())
        for path in doctor.files_for(self.who.get()):
            try:
                ld = self.loaded_file(path)
            except Exception as e:
                t.insert('', 'end', text=f'{os.path.basename(path)}  (could not read: {e})')
                continue
            fid = t.insert('', 'end', text=os.path.basename(path) + ('  - does not load!' if ld.error else ''),
                           values=(len(ld.sets),), open=(path == focus), tags=(path,))
            # sets grouped by their first part (precast / midcast / idle / engaged / ...)
            groups = {}
            for s in ld.sets:
                parts = s['path'].split('.')
                g = parts[1] if len(parts) > 1 else s['path']
                if g not in groups:
                    groups[g] = t.insert(fid, 'end', text=g, values=('',))
                t.insert(groups[g], 'end', text=s['path'][len('sets.'):] if s['path'].startswith('sets.') else s['path'],
                         values=(len(s['gear']),), tags=(path, s['path']))
            if path == focus:
                t.see(fid)
                t.selection_set(fid)

    def show_set(self):
        sel = self.sets_tree.selection()
        if not sel:
            return
        tags = self.sets_tree.item(sel[0], 'tags')
        if len(tags) < 2:
            return
        path, set_path = tags[0], tags[1]
        gear = self.set_gear(path, set_path)
        marks, lines = {}, []
        f = self._report_file(path)
        for p in (f['problems'] if f else []):
            if set_path in p.get('sets', []):
                slot = p.get('slot')
                if slot in gear:
                    marks[slot] = KIND_COLOR.get(p['kind'], '#eeeeee')
                lines.append(f"{KIND_TEXT.get(p['kind'], p['kind'])}: {p['item']} {p['detail']}")
        self.sel_set = (path, set_path)
        self.set_head.config(text=f"{os.path.basename(path)}   {set_path}")
        self.grid_set.show(gear, marks)
        aug = []
        for s in self.loaded_file(path).sets:
            if s['path'] == set_path:
                aug = [f"{gs_slot(k)}: {g['name']} ({', '.join(g['augments'])})" for k, g in s['gear'].items() if g.get('augments')]
        self._say(self.set_text, ('\n'.join(lines) if lines else 'No problems found in this set.')
                  + (('\n\nAugments:\n' + '\n'.join(aug)) if aug else ''))

    def set_to_sim(self):
        if not getattr(self, 'sel_set', None):
            return
        path, set_path = self.sel_set
        self.nb.select(self.tab_sim)
        self.sim_file.set(os.path.basename(path))
        self.sim_file_changed()
        self.sim_set.set(set_path)
        self.sim_set_changed()
        self.sim_enemy.set(self.set_enemy.get())
        if not doctor.is_tp_set(set_path):
            self.sim_tp.set(self.set_tp.get())

    def _report_file(self, path):
        for f in (self.report or {}).get('files', []):
            if os.path.basename(f['path']).lower() == os.path.basename(path).lower():
                return f
        return None

    # ------------------------------------------------------------------ Simulate
    # His request 2026-10-30: "the user should be able to dictate how much damage taken, magic damage taken, physical
    # damage taken should be in each set. there is no way to get input to make the new gearsets". Build a set: pick a
    # weapon skill or TP set, type the damage taken it must have, wsdist builds the best set from his gear that has it;
    # put it in that set or save it as a new set. The numbers are remembered per set and the check-ups use them too.
    def _simulate_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.tab_sim = tab
        self.nb.add(tab, text='Build a set')
        top = ttk.Frame(tab)
        top.pack(fill='x')
        inp = ttk.LabelFrame(top, text='1. The set', padding=8)
        inp.pack(side='left', fill='both', expand=True)
        top.columnconfigure(0, weight=1)
        ttk.Label(inp, text='File').grid(row=0, column=0, sticky='w')
        self.sim_file = ttk.Combobox(inp, width=30, state='readonly')
        self.sim_file.grid(row=0, column=1, sticky='w', padx=4, pady=2)
        self.sim_file.bind('<<ComboboxSelected>>', lambda e: self.sim_file_changed())
        ttk.Label(inp, text='Set').grid(row=1, column=0, sticky='w')
        self.sim_set = ttk.Combobox(inp, width=50, state='readonly')
        self.sim_set.grid(row=1, column=1, columnspan=3, sticky='w', padx=4, pady=2)
        self.sim_set.bind('<<ComboboxSelected>>', lambda e: self.sim_set_changed())
        ttk.Label(inp, text='Sub job').grid(row=0, column=2, sticky='w', padx=(16, 0))
        self.sim_sub = ttk.Combobox(inp, values=JOBS, width=6, state='readonly')
        self.sim_sub.set('WAR')
        self.sim_sub.grid(row=0, column=3, sticky='w', padx=4)
        ttk.Label(inp, text='Enemy').grid(row=2, column=0, sticky='w')
        self.sim_enemy = ttk.Combobox(inp, values=self.enemy_list, width=30, state='readonly')
        self.sim_enemy.set(self.cfg['enemy'])
        self.sim_enemy.grid(row=2, column=1, sticky='w', padx=4, pady=2)
        self.sim_tp_label = ttk.Label(inp, text='TP')
        self.sim_tp_label.grid(row=2, column=2, sticky='w', padx=(16, 0))
        self.sim_tp = tk.IntVar(value=self.cfg['tp'])
        tp = ttk.Frame(inp)
        tp.grid(row=2, column=3, sticky='w')
        ttk.Scale(tp, from_=1000, to=3000, variable=self.sim_tp, length=180,
                  command=lambda v: self.sim_tp.set(int(round(float(v) / 50) * 50))).pack(side='left')
        ttk.Label(tp, textvariable=self.sim_tp, font=MONO, width=5).pack(side='left', padx=4)
        ttk.Label(inp, text='Main weapon').grid(row=3, column=0, sticky='w')
        self.sim_main = ttk.Combobox(inp, width=30, state='readonly', values=[WPN_AUTO])
        self.sim_main.set(WPN_AUTO)
        self.sim_main.grid(row=3, column=1, sticky='w', padx=4, pady=2)
        ttk.Label(inp, text='Sub').grid(row=3, column=2, sticky='w', padx=(16, 0))
        self.sim_subw = ttk.Combobox(inp, width=26, state='readonly', values=[WPN_AUTO])
        self.sim_subw.set(WPN_AUTO)
        self.sim_subw.grid(row=3, column=3, sticky='w', padx=4)
        ToolTip(self.sim_main, 'The weapon wsdist builds the set for - any weapon you own that this job can use (for a '
                               'weapon skill set: of that weapon skill\'s kind). "As in the file" = the set\'s own weapon, '
                               'else your weapon set. Only for the test: your weapon sets still pick the weapon in game.')
        ToolTip(self.sim_subw, 'The sub slot: a second weapon (dual wield), a shield or a grip - or nothing.')
        lb = ttk.Label(inp, text='Buffs')
        lb.grid(row=4, column=0, sticky='w')
        self.sim_buffs = self._buffs_box(inp)
        self.sim_buffs.grid(row=4, column=1, sticky='w', padx=4, pady=2)
        ToolTip(lb, BUFF_HELP)
        ToolTip(self.sim_buffs, BUFF_HELP)
        lb = ttk.Label(inp, text='Aftermath')
        lb.grid(row=4, column=2, sticky='w', padx=(16, 0))
        self.sim_am = self._am_box(inp)
        self.sim_am.grid(row=4, column=3, sticky='w', padx=4)
        ToolTip(lb, AM_HELP)
        ToolTip(self.sim_am, AM_HELP)

        dtf = ttk.LabelFrame(top, text='2. Damage taken it must have (% less damage)', padding=8)
        dtf.pack(side='left', fill='both', padx=(8, 0))
        self.sim_dt = {}
        for i, (k, label, tip) in enumerate((
                ('dt', 'Damage taken (DT)', 'Counts for both physical and magic damage, like DT gear does.'),
                ('pdt', 'Physical damage taken (PDT)', 'From weapons and physical TP moves.'),
                ('mdt', 'Magic damage taken (MDT)', 'From spells and magic TP moves.'))):
            lb = ttk.Label(dtf, text=label)
            lb.grid(row=i, column=0, sticky='w')
            ToolTip(lb, tip)
            v = tk.IntVar(value=0)
            ttk.Spinbox(dtf, from_=0, to=50, increment=1, textvariable=v, width=5).grid(row=i, column=1, sticky='w', padx=4, pady=1)
            ttk.Label(dtf, text='%').grid(row=i, column=2, sticky='w')
            self.sim_dt[k] = v
        self.sim_dt_hint = ttk.Label(dtf, text='', foreground='#666', wraplength=300, justify='left')
        self.sim_dt_hint.grid(row=3, column=0, columnspan=3, sticky='w', pady=(4, 0))
        self.sim_remember = tk.BooleanVar(value=True)
        ttk.Checkbutton(dtf, text='Remember for this set (the check-ups use it too)', variable=self.sim_remember).grid(
            row=4, column=0, columnspan=3, sticky='w', pady=(4, 0))
        lb = ttk.Label(dtf, text='An idle set is for')
        lb.grid(row=5, column=0, sticky='w', pady=(4, 0))
        ToolTip(lb, 'Idle and defense sets: what counts most after your damage taken. It starts from the set\'s name: Refresh, Town, PDT, MEVA...')
        self.sim_focus = ttk.Combobox(dtf, values=list(idle.FOCUS), state='disabled', width=14)
        self.sim_focus.grid(row=5, column=1, columnspan=2, sticky='w', pady=(4, 0))
        self.sim_shell = tk.BooleanVar(value=False)
        self.sim_shell_btn = ttk.Checkbutton(dtf, text='Idle set: I always have Shell V (21 % magic from gear is enough)', variable=self.sim_shell, state='disabled')
        self.sim_shell_btn.grid(row=6, column=0, columnspan=3, sticky='w', pady=(2, 0))

        mine = ttk.LabelFrame(top, text='Damage taken you set', padding=6)
        mine.pack(side='left', fill='both', padx=(8, 0))
        self.dt_list = ttk.Treeview(mine, columns=('dt',), show='tree headings', height=5, selectmode='browse')
        self.dt_list.heading('#0', text='Set')
        self.dt_list.column('#0', width=150, stretch=True)
        self.dt_list.heading('dt', text='DT/PDT/MDT')
        self.dt_list.column('dt', width=80, stretch=False, anchor='center')
        self.dt_list.pack(fill='both', expand=True)
        self.dt_list.bind('<<TreeviewSelect>>', lambda e: self._dt_pick())
        ttk.Button(mine, text='Forget the picked one', command=self._dt_forget).pack(anchor='w', pady=(4, 0))

        btns = ttk.Frame(tab)
        btns.pack(fill='x', pady=6)
        ttk.Button(btns, text='How this set does now', style='Big.TButton', command=lambda: self.simulate(False)).pack(side='left')
        b = ttk.Button(btns, text='3. Build the best set from my gear', style='Big.TButton', command=lambda: self.simulate(True))
        b.pack(side='left', padx=8)
        ToolTip(b, 'wsdist tries your gear (inventory and wardrobes) and keeps the set that does the most damage (weapon '
                   'skill) or gets TP the fastest (TP set) while having at least the damage taken you typed.')
        self.sim_apply_btn = ttk.Button(btns, text='Put it in this set', command=self.sim_apply, state='disabled')
        self.sim_apply_btn.pack(side='left', padx=8)
        self.sim_new_btn = ttk.Button(btns, text='Save it as a new set...', command=self.sim_save_new, state='disabled')
        self.sim_new_btn.pack(side='left')
        self.sim_status = ttk.Label(btns, text='Loading wsdist ...', wraplength=420, justify='left')
        self.sim_status.pack(side='left', padx=8)
        res = ttk.LabelFrame(tab, text='Results', padding=8)
        res.pack(fill='both', expand=True)
        self.sim_result = ttk.Label(res, text='', font=('Courier New', 11), justify='left')
        self.sim_result.pack(anchor='w', pady=(0, 6))
        grids = ttk.Frame(res)
        grids.pack(fill='both', expand=True)
        self.sim_grid_now = GearGrid(grids, 'The set', lambda: self.items)
        self.sim_grid_now.pack(side='left', fill='both', expand=True, padx=(0, 4))
        self.sim_grid_best = GearGrid(grids, 'Best from your gear', lambda: self.items)
        self.sim_grid_best.pack(side='left', fill='both', expand=True)
        self.sim_best = None
        self.sim_best_gear = None
        self.fill_dt_list()

    # the damage taken he set: settings 'dt_targets' = {file name: {set path: {'dt', 'pdt', 'mdt'(, 'main', 'sub')}}}
    def dt_target(self, path, set_path):
        return ((self.cfg.get('dt_targets') or {}).get(os.path.basename(path or '')) or {}).get(set_path)

    def set_dt_target(self, path, set_path, t):
        allt = self.cfg.setdefault('dt_targets', {})
        f = allt.setdefault(os.path.basename(path), {})
        if t and any(t.get(k) for k in ('dt', 'pdt', 'mdt', 'main', 'sub')):
            f[set_path] = {k: int(t.get(k) or 0) for k in ('dt', 'pdt', 'mdt')}
            for k in ('main', 'sub'):
                if t.get(k):
                    f[set_path][k] = t[k]
        else:
            f.pop(set_path, None)
        if not f:
            allt.pop(os.path.basename(path), None)
        save_settings({'dt_targets': allt})
        self.fill_dt_list()

    def fill_dt_list(self):
        t = self.dt_list
        t.delete(*t.get_children())
        self._dt_rows = {}
        mine = {os.path.basename(f) for f in doctor.files_for(self.who.get())}
        for fname, sets_ in sorted((self.cfg.get('dt_targets') or {}).items()):
            if fname not in mine:
                continue
            for sp, v in sorted(sets_.items()):
                wpn = ' / '.join(x for x in (v.get('main'), v.get('sub')) if x)
                row = t.insert('', 'end', text=f"{fname.split('_', 1)[-1][:-4]}  {sp[5:]}" + (f'  ({wpn})' if wpn else ''),
                               values=(f"{v.get('dt', 0)} / {v.get('pdt', 0)} / {v.get('mdt', 0)}",))
                self._dt_rows[row] = (fname, sp)

    def _dt_pick(self):
        sel = self.dt_list.selection()
        if sel and sel[0] in self._dt_rows:
            fname, sp = self._dt_rows[sel[0]]
            self.open_build(os.path.join(doctor.GS_DATA, fname), sp, switch=False)

    def _dt_forget(self):
        sel = self.dt_list.selection()
        if sel and sel[0] in self._dt_rows:
            fname, sp = self._dt_rows[sel[0]]
            self.set_dt_target(fname, sp, None)
            if self.sim_set.get() == sp:
                for v in self.sim_dt.values():
                    v.set(0)

    def open_build(self, path, set_path, switch=True):
        """Build a set, with this file and set picked (and the damage taken he set for it)."""
        if path:
            name = os.path.basename(path)
            if name in (self.sim_file.cget('values') or ()):
                self.sim_file.set(name)
                self.sim_file_changed()
            if set_path and set_path in (self.sim_set.cget('values') or ()):
                self.sim_set.set(set_path)
                self.sim_set_changed()
        if switch:
            self.nb.select(self.tab_sim)

    def _sim_sets(self, ld):
        import wsdist_runner as W
        known = W.ws_list() if self.ws_ready else None
        ws = [s['path'] for s in ld.sets if '.WS' in s['path'] or 'WS[' in s['path']]
        if known:
            ws = [p_ for p_ in ws if doctor.ws_of(p_, known)] or ws
        tp = sorted((s['path'] for s in ld.sets if doctor.is_tp_set(s['path'])), key=lambda p_: (p_.count('.'), p_))
        rest = sorted((s['path'] for s in ld.sets if idle.is_idle(s['path'])), key=lambda p_: (p_.count('.'), p_))
        return ws + tp + rest

    def sim_file_changed(self):
        name = self.sim_file.get()
        path = os.path.join(doctor.GS_DATA, name)
        try:
            ld = self.loaded_file(path)
        except Exception:
            return
        sets = self._sim_sets(ld)
        self.sim_set.configure(values=sets)
        if sets and self.sim_set.get() not in sets:
            self.sim_set.set(sets[0])
        job = checks.job_of(name)
        if job:
            self.sim_sub.set(self.cfg['subs'].get(job, self.sim_sub.get()))
        self.sim_set_changed()

    def sim_set_changed(self):
        sp = self.sim_set.get()
        path = os.path.join(doctor.GS_DATA, self.sim_file.get())
        t = self.dt_target(path, sp) or {}
        for k, v in self.sim_dt.items():
            v.set(int(t.get(k) or 0))
        is_tp = doctor.is_tp_set(sp) if sp else False
        mains, subs = self._weapon_choices(self.sim_file.get(), sp, is_tp)
        self.sim_main.configure(values=[WPN_AUTO] + mains)
        self.sim_subw.configure(values=[WPN_AUTO, doctor.NO_SUB] + subs)
        self.sim_main.set(t.get('main') or WPN_AUTO)
        self.sim_subw.set(t.get('sub') or WPN_AUTO)
        self.sim_tp_label.config(text='WS at TP' if is_tp else 'TP')
        self.sim_tp.set(self.cfg.get('ws_tp', 1000) if is_tp else self.cfg['tp'])
        rest = idle.is_idle(sp)
        self.sim_focus.config(state='readonly' if rest else 'disabled')
        self.sim_focus.set(idle.focus_for(sp) if rest else '')
        self.sim_shell_btn.config(state='normal' if rest else 'disabled')
        self.sim_dt_hint.config(text=('An idle set: all 0 = as much as it can get, by what it is for. Enemy, TP, buffs and Aftermath don\'t matter here. ' if rest else
                                      'A TP set: all 0 = keep the damage taken it has now. ' if is_tp else
                                      'A weapon skill set: all 0 = no limit (most damage). ')
                                + 'The most is 50 % each. DT counts for both.')
        self.sim_best = None
        self.sim_apply_btn.config(state='disabled')
        self.sim_new_btn.config(state='disabled')

    def _sim_target(self):
        out = {}
        for k, v in self.sim_dt.items():
            try:
                out[k] = max(0, min(50, int(v.get())))
            except (tk.TclError, ValueError):
                out[k] = 0
        for k, cb in (('main', self.sim_main), ('sub', self.sim_subw)):
            if cb.get() and cb.get() != WPN_AUTO:
                out[k] = cb.get()
        return out

    def _weapon_choices(self, fname, set_path, is_tp):
        """(main weapons, sub items) he owns that this job can use - for a weapon skill set only that skill's weapons."""
        job = checks.job_of(fname or '')
        if not job or self.items is None:
            return [], []
        p = os.path.join(doctor.DATA, f'bags_{self.who.get()}.json')
        try:
            snap = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError):
            return [], []
        owned = features.owned_items(self.items, snap.get('bags', {}), job)
        mains = sorted({it['en'] for it in owned if it['slots'] & 1})
        subs = sorted({it['en'] for it in owned if it['slots'] & 2})
        if self.ws_ready:
            try:                                    # (only weapons wsdist knows - and of the weapon skill's kind)
                import wsdist_runner as W
                idx = W.gear_index()
                skill = None
                if not is_tp and set_path:
                    known = W.ws_list()
                    ws = doctor.ws_of(set_path, known) or (set_path.split('"')[1] if '"' in set_path and set_path.split('"')[1] in known else None)
                    skill = W.ws_skill(ws) if ws else None
                keep = []
                for n in mains:
                    ents = W.entries_for(n, self.items, idx)
                    if ents and (skill is None or W.pick_variant(ents).get('Skill Type') == skill):
                        keep.append(n)
                mains = keep
                subs = [n for n in subs if W.entries_for(n, self.items, idx)]
            except Exception:
                pass
        return mains, subs

    def _sim_idle(self, find_best):
        """An idle or defense set: judged on the game's item text (idle.py), wsdist has no idle maths."""
        name, set_path = self.sim_file.get(), self.sim_set.get()
        path = os.path.join(doctor.GS_DATA, name)
        job, sub = checks.job_of(name), self.sim_sub.get()
        target = self._sim_target()
        if find_best and self.sim_remember.get():
            self.set_dt_target(path, set_path, target)
        focus = self.sim_focus.get() or None
        shell = bool(self.sim_shell.get())
        need = {k: target[k] for k in ('dt', 'pdt', 'mdt') if target.get(k)}
        self.sim_status.config(text='Working it out from your gear ...')
        self.progress.config(mode='indeterminate'); self.progress.start(12)

        def work():
            try:
                ld = self.loaded_file(path)
                gear = doctor.with_weapons(next(s['gear'] for s in ld.sets if s['path'] == set_path), target)
                cands, counts = self._heal_cands(job)
                keep = True if target.get('main') or target.get('sub') else None
                r = idle.judge(set_path, gear, job, sub, cands, counts, self.items or checks.Items(), self._heal_data, need=need, focus=focus,
                               keep_weapons=keep, build=find_best, shell=shell)
                self.after(0, lambda: self._sim_idle_done(path, set_path, r, need, find_best))
            except Exception as e:
                self.after(0, lambda e=e: self._sim_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _sim_idle_done(self, path, set_path, r, need, find_best):
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        self.sim_status.config(text='   '.join(r['notes']))
        names = lambda g: {s: c['name'] for s, c in g.items() if c}  # noqa: E731
        now_gear = names(r['cur'])
        lines = ['Your set:  ' + idle.words(r['n_now'], r['base'])]
        if r['n_now']['over']:
            lines.append(f"⚠ {r['n_now']['over']} % of its damage taken is over the 50 % cap: that gear could be doing something else.")
        self._sim_last = (path, set_path)
        if not find_best:
            self.sim_result.config(text='\n'.join(lines))
            self.sim_grid_now.show(now_gear)
            self.sim_grid_best.show({})
            self.sim_best = None
            self.sim_apply_btn.config(state='disabled')
            self.sim_new_btn.config(state='disabled')
            return
        lines.append('Best:        ' + idle.words(r['n_best'], r['base']))
        if need and r['short']:
            lines.append(f"⚠ Your gear can't reach the damage taken you asked for: this is the closest ({r['short']} % short in all).")
        elif need:
            lines.append('✔ It has the damage taken you asked for.')
        if not r['changes']:
            lines.append('Your set is already the best your gear can do for this.')
        tip = idle.advice(r['n_best'], r['base'])
        if tip:
            lines.append(tip + '.')
        self.sim_result.config(text='\n'.join(lines))
        changes = r['changes']
        marks = list(changes)
        self.sim_grid_now.show(now_gear, {s: '#fbe3c4' for s in marks})
        self.sim_grid_best.show(names(r['best']), {s: '#c8efc0' for s in marks})
        self.sim_best = (path, set_path, changes) if changes else None
        self.sim_best_gear = {s: healing.gs_name(c) for s, c in r['best'].items() if c and s not in ('main', 'sub') or (c and not r['keep'])}
        self.sim_apply_btn.config(state='normal' if self.sim_best else 'disabled')
        self.sim_new_btn.config(state='normal' if self.sim_best_gear else 'disabled')

    def simulate(self, find_best):
        if self.sim_set.get() and idle.is_idle(self.sim_set.get()):
            self._sim_idle(find_best)
            return
        if not updater.installed():
            self.install_wsdist(ask=True)
            return
        if not self.ws_ready:
            messagebox.showinfo('GearSwap Doctor', 'wsdist is still loading - try again in a moment.')
            return
        name, set_path = self.sim_file.get(), self.sim_set.get()
        if not name or not set_path:
            messagebox.showinfo('GearSwap Doctor', 'Pick a file and a set first.')
            return
        path = os.path.join(doctor.GS_DATA, name)
        job, sub, tp, enemy = checks.job_of(name), self.sim_sub.get(), int(self.sim_tp.get()), self.sim_enemy.get()
        target = self._sim_target()
        if find_best and self.sim_remember.get():
            self.set_dt_target(path, set_path, target)
        who = self.who.get()
        metric = self.cfg.get('tp_metric', 'time')
        buff_key, buffs = self.sim_buff_choice()
        self.sim_status.config(text='wsdist is working ... (a damage taken target takes longer)' if any(target.values())
                               else 'wsdist is working ...')
        self.progress.config(mode='indeterminate'); self.progress.start(12)

        def work():
            try:
                import wsdist_runner as W
                ld = self.loaded_file(path)
                items = self.items or checks.Items()
                bags = checks.load_bags(who) or {}
                owned_ids = set()
                for b, c in bags.items():
                    if not b.startswith('_') and b in checks.EQUIP_BAGS:
                        owned_ids |= set(c)
                index = W.gear_index()
                gear = doctor.with_weapons(next(s['gear'] for s in ld.sets if s['path'] == set_path), target)
                weapons = [(s['path'], s['gear']) for s in ld.sets if s['path'].startswith('sets.weapons')]
                req = W.dt_requirement(target)
                info = {'buffs': W.buff_text(buff_key)}
                wsd = None
                names = set_name.FileInfo(ld, index)
                if doctor.is_tp_set(set_path):
                    tw, main_ws = doctor.tp_weapons(ld)
                    plan = doctor.plan_set(names, set_path, gear, job, sub, owned_ids, items, index, buffs, None, tw, main_ws)
                    what = 'tp'
                else:
                    what = doctor.ws_of(set_path, W.ws_list()) or doctor.ws_in(set_path, W.ws_list())
                    if not what:
                        raise ValueError(f"{set_path} isn't a weapon skill wsdist knows")
                    plan = doctor.plan_set(names, set_path, gear, job, sub, owned_ids, items, index, buffs, what, weapons)
                if plan['error']:
                    raise ValueError(plan['error'])
                owned, cur, notes, skill, spec = plan['owned'], plan['cur'], plan['notes'], plan['skill'], plan['spec']
                if what == 'tp':
                    wsd = doctor.tp_ws_damage(ld, job, sub, cur, owned_ids, items, index, tp, enemy, spec)
                if 'main' not in cur:
                    raise ValueError(f'no {skill or "matching"} weapon to test it with')
                now_gear = {W.GS_SLOT[s_]: doctor._gs_name(e, items) for s_, e in cur.items() if e and e.get('Name') != 'Empty'}
                best_gear = None
                if what == 'tp':
                    if find_best:
                        best, dmg, now = W.best_tp_set(job, sub, owned, cur, ws_tp=tp, enemy_name=enemy, metric=metric, req=req, info=info, buffs=spec, ws_damage=wsd)
                    else:
                        now, dmg = W.tp_set_value(job, sub, cur, ws_tp=tp, enemy_name=enemy, metric=metric, info=info, buffs=spec, ws_damage=wsd), None
                elif find_best:
                    best, dmg, now = W.best_ws_set(job, sub, what, owned, cur, tp=tp, enemy_name=enemy, req=req, info=info, buffs=spec)
                else:
                    now, dmg = W.set_damage(job, sub, what, cur, tp=tp, enemy_name=enemy, info=info, buffs=spec), None
                if dmg is not None:
                    best_gear = {W.GS_SLOT[s_]: doctor._gs_name(e, items) for s_, e in best.items() if e and e['Name'] != 'Empty'}
                info['asked'] = req
                self.after(0, lambda: self._sim_done(path, set_path, what, now, dmg, now_gear, best_gear, notes, tp, enemy, info, metric))
            except Exception as e:
                self.after(0, lambda e=e: self._sim_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _sim_done(self, path, set_path, what, now, dmg, now_gear, best_gear, notes, tp, enemy, info=None, metric='time'):
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        info = info or {}
        tpset = what == 'tp'
        label = (f'TP set, weapon skill at {tp} TP' if tpset else f'{what} at {tp} TP') + f' on {enemy}'
        if info.get('buffs'):
            label += ', ' + info['buffs']
        metric = info.get('metric', metric)
        notes = list(notes) + doctor._am_notes(info)
        self.sim_status.config(text=label + (('   (' + '; '.join(notes) + ')') if notes else ''))
        unit = {'time': ' s to a WS', 'dps': ' damage a second'}.get(metric, ' per round') if tpset else ''

        def fmt(v):
            return f'{v:>7.2f}{unit}' if tpset else f'{v:>8.0f}'

        def dts(t):
            return f'physical {t[0]:.0f}%  magic {t[1]:.0f}%' if t else '?'
        if dmg is None:
            self.sim_result.config(text=('Your set = ' + fmt(now) + '\n' if tpset else f'Average damage = {now:>8.0f}\n')
                                   + 'Damage taken: ' + dts(info.get('now')))
            self.sim_grid_now.show(now_gear)
            self.sim_grid_best.show({})
            self.sim_best = None
            self.sim_apply_btn.config(state='disabled')
            self.sim_new_btn.config(state='disabled')
            return
        if tpset and metric == 'time':
            gain = (now - dmg) / now * 100 if now else 0
        else:
            gain = (dmg - now) / now * 100 if now else 0
        lines = [f'Your set = {fmt(now)}    Best = {fmt(dmg)}    {gain:+.1f}%' + (' faster' if tpset and metric == 'time' else ''),
                 f"Damage taken:  your set {dts(info.get('now'))}   ->   best {dts(info.get('best'))}"]
        req = info.get('asked')
        if req:
            b = info.get('best') or (0, 0)
            if b[0] <= req[0] + 0.01 and b[1] <= req[1] + 0.01:
                lines.append(f'✔ It has the damage taken you asked for (physical {req[0]:.0f}%, magic {req[1]:.0f}%).')
            else:
                lines.append(f'⚠ Your gear can\'t reach physical {req[0]:.0f}% / magic {req[1]:.0f}% here - this is the '
                             'closest wsdist found.')
        self.sim_result.config(text='\n'.join(lines))
        changes = {s_: n for s_, n in best_gear.items() if s_ not in ('main', 'sub', 'range') and now_gear.get(s_) != n}
        for p1, p2 in (('ear1', 'ear2'), ('ring1', 'ring2')):          # only swapped sides: not a change
            if sorted(filter(None, [now_gear.get(p1), now_gear.get(p2)])) == sorted(filter(None, [best_gear.get(p1), best_gear.get(p2)])):
                changes.pop(p1, None)
                changes.pop(p2, None)
        self.sim_grid_now.show(now_gear, {s_: '#fbe3c4' for s_ in changes})
        self.sim_grid_best.show(best_gear, {s_: '#c8efc0' for s_ in changes})
        self.sim_best = (path, set_path, changes) if changes and (gain > 0 or req) else None
        self.sim_best_gear = {s_: n for s_, n in best_gear.items() if s_ not in ('main', 'sub', 'range')}
        self.sim_apply_btn.config(state='normal' if self.sim_best else 'disabled')
        self.sim_new_btn.config(state='normal')
        self._sim_last = (path, set_path)

    def _sim_failed(self, e):
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        self.sim_status.config(text=f'wsdist could not do it: {e}')

    def sim_apply(self):
        if not self.sim_best:
            return
        path, set_path, changes = self.sim_best
        self._apply({path: [('slots', set_path, changes)]})

    def sim_save_new(self):
        """The best set as a new set next to the one it was built from: sets.engaged + 'HighDT' -> sets.engaged.HighDT."""
        if not self.sim_best_gear or not getattr(self, '_sim_last', None):
            return
        path, set_path = self._sim_last
        from tkinter import simpledialog
        name = simpledialog.askstring('GearSwap Doctor - save as a new set',
                                      f'A name for the new set. It goes right after {set_path} in the file:\n\n'
                                      f'    {set_path}.<name>\n\nFor example DT, HighDT, Safe. (GearSwap only uses it when '
                                      "your file's rules ask for it - in Mote-style files, a set named after a mode such "
                                      'as DT is used when that mode is on.)', initialvalue='DT', parent=self)
        if not name:
            return
        name = name.strip()
        new_path = set_path + ('.' + name if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name) else '["' + name.replace('"', '') + '"]')
        target = self._sim_target()
        if self._apply({path: [('add', set_path, new_path, dict(self.sim_best_gear))]}) is not False and self.sim_remember.get():
            self.set_dt_target(path, new_path, target)

    # ------------------------------------------------------------------ My gear
    def _gear_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text='My gear')
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text='Search').pack(side='left')
        self.gear_q = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.gear_q, width=30)
        e.pack(side='left', padx=6)
        self.gear_q.trace_add('write', lambda *a: self.fill_gear())
        self.gear_bag = ttk.Combobox(bar, values=['all bags', 'equippable (inventory + wardrobes)'], state='readonly', width=34)
        self.gear_bag.set('equippable (inventory + wardrobes)')
        self.gear_bag.pack(side='left', padx=6)
        self.gear_bag.bind('<<ComboboxSelected>>', lambda e: self.fill_gear())
        self.gear_info = ttk.Label(bar, text='', foreground='#666')
        self.gear_info.pack(side='left', padx=8)
        frame, self.gear_tree = self._tree(tab, ('bag', 'count', 'used'), ('Bag', 'Count', 'Used in sets'), (140, 60, 500), tree_width=300)
        self.gear_tree.heading('#0', text='Item')
        frame.pack(fill='both', expand=True)

    def fill_gear(self):
        t = self.gear_tree
        t.delete(*t.get_children())
        p = os.path.join(doctor.DATA, f'bags_{self.who.get()}.json')
        try:
            snap = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError):
            self.gear_info.config(text='No saved bags yet - Check now makes the list (from Steward).')
            return
        used = {}
        for f in (self.report or {}).get('files', []):
            try:
                for s in self.loaded_file(f['path']).sets:
                    for g in s['gear'].values():
                        used.setdefault(g['name'].lower(), set()).add(f['file'].split('_', 1)[-1].replace('.lua', ''))
            except Exception:
                pass
        q = self.gear_q.get().strip().lower()
        only_eq = self.gear_bag.get().startswith('equippable')
        n = 0
        for bag, content in sorted(snap.get('bags', {}).items()):
            if only_eq and bag not in checks.EQUIP_BAGS:
                continue
            for name, count in content.items():
                if q and q not in name.lower():
                    continue
                t.insert('', 'end', text=name, values=(bag, count, ', '.join(sorted(used.get(name.lower(), [])))))
                n += 1
        self.gear_info.config(text=f'{n} items - bags saved by Steward {ago(snap.get("from_steward"))}')

    # ------------------------------------------------------------------ Backups
    def _backups_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text='Backups')
        frame, self.bk_tree = self._tree(tab, ('files',), ('Files',), (700,), tree_width=220)
        self.bk_tree.heading('#0', text='When')
        frame.pack(fill='both', expand=True)
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(6, 0))
        ttk.Button(bar, text='Put this backup back', command=self.restore).pack(side='left')
        ttk.Button(bar, text='Open the backups folder', command=lambda: open_folder(self._backups())).pack(side='left', padx=8)
        ttk.Label(bar, text='Every change GearSwap Doctor makes saves the file here first.', foreground='#666').pack(side='left', padx=8)

    def _backups(self):
        os.makedirs(fixer.BACKUPS, exist_ok=True)
        return fixer.BACKUPS

    def fill_backups(self):
        t = self.bk_tree
        t.delete(*t.get_children())
        for folder in sorted(glob.glob(os.path.join(self._backups(), '*')), reverse=True):
            if os.path.isdir(folder):
                name = os.path.basename(folder)
                t.insert('', 'end', iid=folder, text=name.replace('_undone', '  (put back)'), values=(', '.join(os.listdir(folder)),))

    def restore(self):
        sel = self.bk_tree.selection()
        if not sel:
            messagebox.showinfo('GearSwap Doctor', 'Click a backup first.')
            return
        folder = sel[0]
        files = os.listdir(folder)
        if not messagebox.askyesno('GearSwap Doctor', 'Put back these files from ' + os.path.basename(folder) + '?\n\n' + '\n'.join(files)):
            return
        for f in files:
            shutil.copy2(os.path.join(folder, f), os.path.join(doctor.GS_DATA, f))
        self.loaded.clear()
        messagebox.showinfo('GearSwap Doctor', 'Put back: ' + ', '.join(files) + '\n\nIn game: //gs reload')
        self.run_check(quiet=True)

    # ------------------------------------------------------------------ Settings
    def _settings_tab(self):
        tab = ttk.Frame(self.nb, padding=12)
        self.nb.add(tab, text='Settings')
        ws = ttk.LabelFrame(tab, text='wsdist in the check-ups', padding=8)
        ws.pack(fill='x')
        ttk.Label(ws, text='TP').grid(row=0, column=0, sticky='w')
        self.cfg_tp = tk.IntVar(value=self.cfg['tp'])
        ttk.Spinbox(ws, from_=1000, to=3000, increment=100, textvariable=self.cfg_tp, width=6).grid(row=0, column=1, sticky='w', padx=6)
        ttk.Label(ws, text='Enemy').grid(row=1, column=0, sticky='w')
        self.cfg_enemy = ttk.Combobox(ws, values=self.enemy_list, width=28, state='readonly')
        self.cfg_enemy.set(self.cfg['enemy'])
        self.cfg_enemy.grid(row=1, column=1, sticky='w', padx=6, pady=2)
        self.cfg_enemy.bind('<Button-1>', lambda e: self.cfg_enemy.configure(values=self.enemy_list))
        lb = ttk.Label(ws, text='Buffs')
        lb.grid(row=2, column=0, sticky='w')
        self.cfg_buffs = self._buffs_box(ws)
        self.cfg_buffs.grid(row=2, column=1, sticky='w', padx=6, pady=2)
        ttk.Button(ws, text='Custom buffs...', command=self.open_custom_buffs).grid(row=2, column=2, padx=6)
        lb = ttk.Label(ws, text='Aftermath')
        lb.grid(row=3, column=0, sticky='w')
        self.cfg_am = self._am_box(ws)
        self.cfg_am.grid(row=3, column=1, sticky='w', padx=6, pady=2)
        ToolTip(lb, AM_HELP)
        ToolTip(self.cfg_am, AM_HELP)
        ToolTip(lb, BUFF_HELP)
        ToolTip(self.cfg_buffs, BUFF_HELP)
        tpf = ttk.LabelFrame(tab, text='TP sets (engaged)', padding=8)
        tpf.pack(fill='x', pady=(8, 0))
        self.cfg_tp_sets = tk.BooleanVar(value=self.cfg.get('tp_sets', True))
        ttk.Checkbutton(tpf, text='Also check TP sets (sets.engaged / sets.TP) for faster ones from your gear', variable=self.cfg_tp_sets).grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Label(tpf, text='Judge them by').grid(row=1, column=0, sticky='w', pady=(4, 0))
        self.cfg_tp_metric = ttk.Combobox(tpf, values=list(TP_METRIC_TEXT.values()), state='readonly', width=30)
        self.cfg_tp_metric.set(TP_METRIC_TEXT.get(self.cfg.get('tp_metric'), TP_METRIC_TEXT['time']))
        self.cfg_tp_metric.grid(row=1, column=1, sticky='w', padx=6, pady=(4, 0))
        ttk.Label(tpf, text='Weapon skill at').grid(row=1, column=2, sticky='w', padx=(12, 0), pady=(4, 0))
        self.cfg_ws_tp = tk.IntVar(value=self.cfg.get('ws_tp', 1000))
        ttk.Spinbox(tpf, from_=1000, to=3000, increment=100, textvariable=self.cfg_ws_tp, width=6).grid(row=1, column=3, sticky='w', padx=6, pady=(4, 0))
        ttk.Label(tpf, text='TP sets keep the damage taken they have now (a DT set stays a DT set). Sets made for something else '
                            '(Subtle Blow, Accuracy...) are judged by speed only: check those before applying.', foreground='#666',
                  wraplength=900).grid(row=2, column=0, columnspan=4, sticky='w', pady=(4, 0))
        subs = ttk.LabelFrame(tab, text='Sub job used for each job', padding=8)
        subs.pack(fill='x', pady=8)
        self.cfg_subs = {}
        for i, job in enumerate(JOBS):
            ttk.Label(subs, text=job).grid(row=i // 8, column=(i % 8) * 2, sticky='e', padx=(8, 2), pady=2)
            cb = ttk.Combobox(subs, values=JOBS, width=5, state='readonly')
            cb.set(self.cfg['subs'].get(job, 'WAR'))
            cb.grid(row=i // 8, column=(i % 8) * 2 + 1, sticky='w')
            self.cfg_subs[job] = cb
        where = ttk.LabelFrame(tab, text='Folders', padding=8)
        where.pack(fill='x', pady=(0, 8))
        self.win_label = ttk.Label(where, text='Windower: ' + (paths.WINDOWER or '(not found)'))
        self.win_label.grid(row=0, column=0, sticky='w')
        ttk.Button(where, text='Change...', command=self.change_windower).grid(row=0, column=1, padx=8)
        ttk.Label(where, text="GearSwap Doctor's own files (settings, reports, backups, wsdist): " + paths.APP,
                  foreground='#666').grid(row=1, column=0, columnspan=2, sticky='w', pady=(4, 0))
        self.wsdist_label = ttk.Label(where, text='')
        self.wsdist_label.grid(row=2, column=0, sticky='w', pady=(4, 0))
        ttk.Button(where, text='Download wsdist now', command=self.install_wsdist).grid(row=2, column=1, padx=8)
        other = ttk.LabelFrame(tab, text='Other', padding=8)
        other.pack(fill='x')
        self.cfg_daily = tk.BooleanVar(value=self.cfg.get('daily', True))
        ttk.Checkbutton(other, text='Check by itself once a day while open (and look for a newer wsdist)', variable=self.cfg_daily).pack(anchor='w')
        ttk.Label(other, text='Characters found: ' + ', '.join(self.chars)).pack(anchor='w', pady=(6, 0))
        ttk.Label(other, text=('Item icons: ' + ('shown (wsdist icons32 folder found)' if os.path.isdir(ICONS)
                               else 'not shown (no icons32 folder in gearcheck\\wsdist)'))).pack(anchor='w')
        ttk.Button(tab, text='Save settings', style='Big.TButton', command=self.save_cfg).pack(anchor='w', pady=10)

    def change_windower(self):
        if ask_windower(self):
            self.win_label.config(text='Windower: ' + paths.WINDOWER)
            self.chars = characters() or ['(none)']
            self.loaded.clear()
            self.show_last()

    def install_wsdist(self, ask=True):
        """Download wsdist from Kastra's GitHub (it isn't shipped inside GearSwap Doctor)."""
        if ask and not messagebox.askyesno('GearSwap Doctor', "GearSwap Doctor uses wsdist (Kastra's FFXI damage simulator) "
                                           'for the weapon skill upgrades and Simulate.\n\nDownload it now from Kastra\'s '
                                           'GitHub page (github.com/IzaKastra/wsdist_beta, about 1.5 MB)?'):
            return
        self.status.config(text='Downloading wsdist ...')
        self.progress.config(mode='indeterminate'); self.progress.start(12)

        def work():
            try:
                updater.update(log=lambda m: self.after(0, lambda: self.status.config(text=m)))
                self.after(0, self._wsdist_installed)
            except Exception as e:
                self.after(0, lambda: (self.progress.stop(), self.progress.config(mode='determinate', value=0),
                                       self.status.config(text=f"Couldn't download wsdist: {e}")))
        threading.Thread(target=work, daemon=True).start()

    def _wsdist_installed(self):
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        self.status.config(text='wsdist downloaded.')
        self.show_ws()
        threading.Thread(target=self._load_background, daemon=True).start()

    # ------------------------------------------------------------------ buffs: what's up while a set is judged
    def _buffs_box(self, parent):
        box = ttk.Combobox(parent, values=list(W.BUFF_CHOICES.values()), width=22, state='readonly')
        box.set(W.BUFF_CHOICES.get(self.cfg.get('buffs'), W.BUFF_CHOICES['party']))
        box.bind('<<ComboboxSelected>>', lambda e: box.get() == W.BUFF_CHOICES['custom'] and self.open_custom_buffs())
        return box

    def _am_box(self, parent):
        box = ttk.Combobox(parent, values=list(W.AM_CHOICES.values()), width=25, state='readonly')
        box.set(W.AM_CHOICES.get(str(self.cfg.get('aftermath', 'auto')), W.AM_CHOICES['auto']))
        return box

    def sim_buff_choice(self):
        """The Build a set dropdowns: (the Buffs choice, what's up)."""
        key = buff_key(self.sim_buffs.get())
        return key, W.buff_spec(key, self.cfg.get('buffs_custom'), am_key(self.sim_am.get()))

    def open_custom_buffs(self):
        """The Custom buffs: wsdist's own lists, as tick boxes. Saved in the settings, used by Settings and Build a set."""
        if not updater.installed():
            messagebox.showinfo('GearSwap Doctor', 'wsdist has to be downloaded first (Settings > Download wsdist now).')
            return None
        opts = W.buff_options()
        spec = self.cfg.get('buffs_custom') or {}
        w = tk.Toplevel(self)
        w.title('Custom buffs')
        w.transient(self)
        self.buff_vars = v = {'songs': {}, 'rolls': {}, 'bubbles': {}, 'haste': {}, 'dia': {}, 'afterglow': {}}
        self.buff_win = w
        note = ttk.Label(w, text='Tick what is up in your party. Only what you tick counts.', foreground='#666')
        note.pack(anchor='w', padx=8, pady=(8, 0))
        cols = ttk.Frame(w, padding=8)
        cols.pack(fill='both', expand=True)

        def limit(kind, name):                                  # (no more than wsdist has places for)
            on = [n for n, b in v[kind].items() if b.get()]
            if len(on) > W.BUFF_LIMITS[kind]:
                v[kind][name].set(False)
                note.config(text=f'{W.BUFF_LIMITS[kind]} {kind} at most: untick one first.')

        def only_one(kind, name):                               # (Haste II replaces Haste, a Dia replaces a Dia)
            if v[kind][name].get():
                for n, b in v[kind].items():
                    if n != name:
                        b.set(False)

        def bonus(parent, row, label, values, val):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', pady=(6, 0))
            cb = ttk.Combobox(parent, values=values, width=7, state='readonly')
            cb.set(val)
            cb.grid(row=row, column=1, sticky='w', pady=(6, 0))
            return cb

        left = ttk.Frame(cols)
        left.pack(side='left', fill='y', anchor='n')
        whm = ttk.LabelFrame(left, text='White Magic', padding=6)
        whm.pack(fill='x')
        for kind in ('haste', 'dia'):
            for name in opts[kind]:
                b = tk.BooleanVar(value=spec.get(kind) == name)
                v[kind][name] = b
                ttk.Checkbutton(whm, text=name, variable=b, command=lambda k=kind, n=name: only_one(k, n)).pack(anchor='w')
        ttk.Label(whm, text='Boost / Gain').pack(anchor='w', pady=(6, 0))
        self.buff_boost = ttk.Combobox(whm, values=['None'] + opts['boost'], width=16, state='readonly')
        self.buff_boost.set(spec.get('boost') or 'None')
        self.buff_boost.pack(anchor='w')
        oth = ttk.LabelFrame(left, text='Food and Afterglow', padding=6)
        oth.pack(fill='x', pady=(8, 0))
        self.buff_food = ttk.Combobox(oth, values=['None'] + opts['food'], width=20, state='readonly')
        self.buff_food.set(spec.get('food') or 'None')
        self.buff_food.pack(anchor='w')
        ttk.Label(oth, text='Afterglow from someone else\'s\nUltimate Weapon, within 10\'').pack(anchor='w', pady=(6, 0))
        glow = {'Relic': 'Relic: Accuracy +15', 'Empyrean': 'Empyrean: Crit. rate +5%', 'Mythic': 'Mythic / Ergon: Attack +15'}
        for name in opts['afterglow']:
            b = tk.BooleanVar(value=name in (spec.get('afterglow') or []))
            v['afterglow'][name] = b
            ttk.Checkbutton(oth, text=glow.get(name, name), variable=b).pack(anchor='w')

        brd = ttk.LabelFrame(cols, text='Songs', padding=6)
        brd.pack(side='left', fill='y', padx=(8, 0), anchor='n')
        for i, name in enumerate(opts['songs']):
            b = tk.BooleanVar(value=name in (spec.get('songs') or []))
            v['songs'][name] = b
            ttk.Checkbutton(brd, text=name, variable=b, command=lambda n=name: limit('songs', n)).grid(
                row=i % 14, column=i // 14 * 2, columnspan=2, sticky='w', padx=(0, 8))
        self.buff_song_bonus = bonus(brd, 14, 'Songs +', list(range(10)), spec.get('song_bonus', 7))

        cor = ttk.LabelFrame(cols, text='Corsair rolls (and the number rolled)', padding=6)
        cor.pack(side='left', fill='y', padx=(8, 0), anchor='n')
        self.buff_roll_no = {}
        rolls = spec.get('rolls') or {}
        for i, name in enumerate(opts['rolls']):
            b = tk.BooleanVar(value=name in rolls)
            v['rolls'][name] = b
            ttk.Checkbutton(cor, text=name, variable=b, command=lambda n=name: limit('rolls', n)).grid(row=i, column=0, sticky='w')
            cb = ttk.Combobox(cor, values=W.ROLL_NUMBERS, width=5, state='readonly')
            cb.set(rolls.get(name, 'VII'))
            cb.grid(row=i, column=1, sticky='w', pady=1)
            self.buff_roll_no[name] = cb
        n = len(opts['rolls'])
        self.buff_roll_bonus = bonus(cor, n, 'Rolls +', list(range(9)), spec.get('roll_bonus', 7))
        self.buff_job_bonus = tk.BooleanVar(value=spec.get('job_bonus', True))
        ttk.Checkbutton(cor, text='Job bonus (the job of the roll is in the party)', variable=self.buff_job_bonus).grid(
            row=n + 1, column=0, columnspan=2, sticky='w')

        geo = ttk.LabelFrame(cols, text='Geomancer bubbles', padding=6)
        geo.pack(side='left', fill='y', padx=(8, 0), anchor='n')
        for i, name in enumerate(opts['bubbles']):
            b = tk.BooleanVar(value=name in (spec.get('bubbles') or []))
            v['bubbles'][name] = b
            ttk.Checkbutton(geo, text=name, variable=b, command=lambda n=name: limit('bubbles', n)).grid(
                row=i, column=0, columnspan=2, sticky='w')
        n = len(opts['bubbles'])
        self.buff_bubble_bonus = bonus(geo, n, 'Geomancy +', list(range(11)), spec.get('bubble_bonus', 10))
        self.buff_potency = bonus(geo, n + 1, 'Enemy bubble %', [100, 75, 50, 25], spec.get('bubble_potency', 50))
        ToolTip(self.buff_potency, 'Frailty and the other bubbles on the enemy are rarely at full strength. wsdist uses 50 %.')

        btns = ttk.Frame(w, padding=(8, 0, 8, 8))
        btns.pack(fill='x')
        ttk.Button(btns, text='Use these', style='Big.TButton', command=self.save_custom_buffs).pack(side='left')
        ttk.Button(btns, text='Cancel', command=w.destroy).pack(side='left', padx=8)
        return w

    def custom_buffs_now(self):
        """What the Custom buffs window has ticked, in the form wsdist_runner.buff_stats reads."""
        v = self.buff_vars

        def one(kind):
            return next((n for n, b in v[kind].items() if b.get()), None)

        def pick(box):
            return None if box.get() == 'None' else box.get()
        spec = {'songs': [n for n, b in v['songs'].items() if b.get()], 'song_bonus': int(self.buff_song_bonus.get()),
                'rolls': {n: self.buff_roll_no[n].get() for n, b in v['rolls'].items() if b.get()},
                'roll_bonus': int(self.buff_roll_bonus.get()), 'job_bonus': bool(self.buff_job_bonus.get()),
                'bubbles': [n for n, b in v['bubbles'].items() if b.get()], 'bubble_bonus': int(self.buff_bubble_bonus.get()),
                'bubble_potency': int(self.buff_potency.get()), 'haste': one('haste'), 'dia': one('dia'),
                'boost': pick(self.buff_boost), 'food': pick(self.buff_food), 'afterglow': [n for n, b in v['afterglow'].items() if b.get()]}
        return spec

    def save_custom_buffs(self):
        self.cfg['buffs_custom'] = self.custom_buffs_now()
        save_settings(self.cfg)
        self.buff_win.destroy()

    def save_cfg(self):
        self.cfg['tp'] = int(self.cfg_tp.get())
        self.cfg['enemy'] = self.cfg_enemy.get() or 'Apex Toad'
        self.cfg['subs'] = {j: cb.get() for j, cb in self.cfg_subs.items()}
        self.cfg['daily'] = bool(self.cfg_daily.get())
        self.cfg['tp_sets'] = bool(self.cfg_tp_sets.get())
        self.cfg['tp_metric'] = next((k for k, v in TP_METRIC_TEXT.items() if v == self.cfg_tp_metric.get()), 'time')
        self.cfg['ws_tp'] = int(self.cfg_ws_tp.get())
        self.cfg['buffs'] = buff_key(self.cfg_buffs.get())
        self.sim_buffs.set(self.cfg_buffs.get())
        self.cfg['aftermath'] = am_key(self.cfg_am.get())
        self.sim_am.set(self.cfg_am.get())
        save_settings(self.cfg)
        messagebox.showinfo('GearSwap Doctor', 'Saved. The next Check now uses them.')

    # ------------------------------------------------------------------ report
    def change_character(self):
        self.cfg['character'] = self.who.get()
        save_settings(self.cfg)
        self.loaded.clear()
        self.show_last()

    def show_last(self):
        self.report = doctor.last_report(self.who.get())
        self.fill()

    def fill(self):
        self.rows, self.ticked, self.info = {}, set(), {}
        self._update_tick_label()
        r = self.report
        names = [os.path.basename(p) for p in doctor.files_for(self.who.get())]
        self.sim_file.configure(values=names)
        if names and self.sim_file.get() not in names:
            self.sim_file.set(names[0])
        if names:
            self.sim_file_changed()
        self.fill_jobs()
        self.feat_fill_files()
        self.heal_fill_files()
        self.fill_overview()
        self.fill_problems()
        self.fill_upgrades()
        self.fill_sets()
        self.fill_gear()
        self.fill_backups()
        if not r:
            self.status.config(text=f'No check-up yet for {self.who.get()} - click Check now')
        else:
            self.status.config(text=f"Checked {ago(r['time'])}  -  bags saved by Steward {ago(r.get('bags_time'))}"
                                    + (f"  -  wsdist: {r.get('tp', 1500)} TP on {r.get('enemy', 'Apex Toad')}, {r.get('buffs_text', 'no buffs')}" + (f", {r['aftermath_text']}" if r.get('aftermath_text') else '')))

    def fill_overview(self):
        t = self.files_tree
        t.delete(*t.get_children())
        r = self.report
        if not r:
            self.summary.config(text=f'{self.who.get()}: no check-up yet. Click Check now.')
            return
        np = sum(len(f['problems']) for f in r['files'])
        nu = sum(len([u for u in f['upgrades'] if 'error' not in u]) for f in r['files'])
        broken = sum(1 for f in r['files'] for p in f['problems'] if p['kind'] == 'broken')
        self.summary.config(text=f"{self.who.get()}: {len(r['files'])} files  -  {np} problems ({broken} broken)  -  {nu} better weapon skill sets")
        for f in r['files']:
            kinds = {}
            for p in f['problems']:
                kinds[p['kind']] = kinds.get(p['kind'], 0) + 1
            good = [u for u in f['upgrades'] if 'error' not in u]
            best = max((u['gain'] for u in good), default=None)
            loads = 'no' if any(p['kind'] == 'broken' and 'load' in p['detail'].lower() for p in f['problems']) else 'yes'
            t.insert('', 'end', text=f['file'], tags=(f['path'],),
                     values=(f.get('job') or '?', f.get('sub', ''), f['sets'], loads,
                             ', '.join(f'{n} {KIND_TEXT.get(k, k).lower()}' for k, n in kinds.items()) or 'none',
                             len(good), f'+{best}%' if best else ''))

    def fill_problems(self):
        t = self.prob
        t.delete(*t.get_children())
        for row in [k for k in self.rows if self.rows[k][1][0] == 'rename']:
            self.rows.pop(row, None)
            self.ticked.discard(row)
        r = self.report
        if not r:
            return
        counts = {}
        for f in r['files']:
            for p in f['problems']:
                counts[p['kind']] = counts.get(p['kind'], 0) + 1
        for k, cbx in self.kind_box.items():
            cbx.config(text=f"{KIND_TEXT[k]} ({counts.get(k, 0)})")
        for f in r['files']:
            probs = [p for p in f['problems'] if self.kind_on[p['kind']].get()] if f['problems'] else []
            if self.only_fix.get():
                probs = [p for p in probs if p['kind'] == 'unknown' and p.get('fix')]
            probs.sort(key=lambda p: (LEVEL_RANK[KIND_LEVEL.get(p['kind'], 'info')], p['kind'], p['item']))
            if not probs:
                continue
            fid = t.insert('', 'end', iid=self._iid('p'), text=f"{f['file']}  ({len(probs)})", open=any(p['kind'] in ('broken', 'unknown') for p in probs))
            for p in probs:
                fix = p.get('fix')
                fixable = p['kind'] == 'unknown' and fix
                detail = p['detail'] + (f'   [fix: {fix}]' if fixable else '')
                lv = KIND_LEVEL.get(p['kind'], 'info')
                row = t.insert(fid, 'end', iid=self._iid('p'), text=(OFF + ' ' if fixable else '   ') + KIND_TEXT.get(p['kind'], p['kind']),
                               values=(LEVEL_TEXT[lv], KIND_TEXT.get(p['kind'], p['kind']), p['item'], p['slot'], detail, len(p['sets'])),
                               tags=(lv,))
                if fixable:
                    self.rows[row] = (f['path'], ('rename', p['item'], fix))
                where = ', '.join(x for x in p['sets'] if x)
                means, todo = KIND_HELP.get(p['kind'], ('', ''))
                self.info[row] = (f"{LEVEL_TEXT[lv]} - {KIND_TEXT.get(p['kind'], p['kind'])}: {p['item']} {p['detail']}"
                                  + (('\nIn: ' + where) if where else '')
                                  + f'\nWhat it means: {means}\nWhat to do: {todo}'
                                  + (f' (the fix: {fix})' if fixable else ''))
        self._update_tick_label()

    def fill_upgrades(self):
        t = self.upg
        t.delete(*t.get_children())
        for row in [k for k in self.rows if self.rows[k][1][0] == 'slots']:     # (the old list's rows)
            self.rows.pop(row, None)
            self.ticked.discard(row)
        self._update_tick_label()
        r = self.report
        if not r:
            return
        for f in r['files']:
            ups = f['upgrades']
            if not ups:
                continue
            good = [u for u in ups if 'error' not in u]
            checked = doctor.tp_checked_text(f)
            fid = t.insert('', 'end', iid=self._iid('u'), text=f"{f['file']}  ({len(good)})" + (f'   -   {checked}' if checked else ''), open=bool(good))
            ups = sorted(ups, key=lambda u: -(u.get('gain') or -1))           # (the biggest gains first)
            for u in ups:
                if 'error' in u:
                    row = t.insert(fid, 'end', iid=self._iid('u'), text='   ' + u['ws'], values=('-', 'not checked', '', '-'), tags=('small',))
                    self.info[row] = u['error']
                    continue
                row = t.insert(fid, 'end', iid=self._iid('u'), text=OFF + ' ' + u['ws'],
                               values=(gain_text(u), verdict_u(u), len(u['changes']), nowbest(u)),
                               tags=('big' if u['gain'] >= 15 else 'small' if u['gain'] < 5 else '',))
                self.rows[row] = (f['path'], ('slots', u['set'], u['changes']))
                self.info[('u', row)] = u

    def _iid(self, prefix):
        # each list's own row names: the Problems and Upgrades lists both started at I001, so a tick in one could land
        # on the other's row (found by test_app)
        self._n = getattr(self, '_n', 0) + 1
        return f'{prefix}{self._n}'

    def _click_tick(self, e):
        t = e.widget
        row = t.identify_row(e.y)
        if row in self.rows and t.identify_column(e.x) == '#0':
            if row in self.ticked:
                self.ticked.discard(row)
            else:
                self.ticked.add(row)
            txt = t.item(row, 'text')
            t.item(row, text=(ON if row in self.ticked else OFF) + txt[1:])
            self._update_tick_label()

    def _update_tick_label(self):
        n = len(self.ticked)
        self.tick_label.config(text=f'{n} ticked' if n else 'Nothing ticked')

    def _show_info(self, tree, box):
        sel = tree.selection()
        txt = self.info.get(sel[0], '') if sel else ''
        self._say(box, txt if isinstance(txt, str) else '')

    # ------------------------------------------------------------------ check-up
    def run_check(self, quiet=False):
        if self.busy:
            return
        self.busy = True
        self.check_btn.config(state='disabled')
        self.progress.config(mode='indeterminate'); self.progress.start(12)
        who, cfg = self.who.get(), dict(self.cfg)

        def work():
            try:
                rep = doctor.checkup(who, wsdist=updater.installed(), sub=cfg.get('subs') or 'WAR', tp=cfg.get('tp', 1500), enemy=cfg.get('enemy', 'Apex Toad'),
                                     tp_sets=cfg.get('tp_sets', True), ws_tp=cfg.get('ws_tp', 1000), tp_metric=cfg.get('tp_metric', 'time'),
                                     targets=cfg.get('dt_targets') or {}, buffs=cfg.get('buffs', 'party'), buffs_custom=cfg.get('buffs_custom'), aftermath=str(cfg.get('aftermath', 'auto')),
                                     progress=lambda m: self.after(0, lambda: self.status.config(text=m + ' ...')))
                self.after(0, lambda: self._done(rep, who))
            except Exception as e:
                self.after(0, lambda e=e: self._failed(e, quiet))
        threading.Thread(target=work, daemon=True).start()

    def _done(self, rep, who):
        self.busy = False
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        self.check_btn.config(state='normal')
        if who == self.who.get():
            self.loaded.clear()
            self.report = rep
            self.fill()

    def _failed(self, e, quiet):
        self.busy = False
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        self.check_btn.config(state='normal')
        self.status.config(text=f'Check-up failed: {e}')
        if not quiet:
            messagebox.showerror('GearSwap Doctor', f'The check-up failed:\n{e}')

    def daily(self):
        r = self.report
        if self.cfg.get('daily', True):
            if not self.busy and (not r or time.time() - r['time'] > 24 * 3600):
                self.run_check(quiet=True)
            if updater.due():
                threading.Thread(target=self._ws_check_bg, daemon=True).start()
        self.after(3600 * 1000, self.daily)

    # ------------------------------------------------------------------ applying
    def apply(self):
        if not self.ticked:
            messagebox.showinfo('GearSwap Doctor', 'Nothing ticked. Click the box in front of a misspelled item (Problems) '
                                                   'or an upgrade (Upgrades) first.')
            return
        by_file = {}
        for row in self.ticked:
            path, edit = self.rows[row]
            by_file.setdefault(path, []).append(edit)
        self._apply(by_file)

    def _apply(self, by_file):
        lines = []
        for path, edits in by_file.items():
            lines.append(os.path.basename(path) + ':')
            for e in edits:
                lines.append(f'   {e[1]} -> {e[2]}' if e[0] == 'rename' else f'   new set {e[2]}' if e[0] == 'add'
                             else f'   new set {e[1]}' if e[0] == 'new'
                             else f'   {e[1]}: ' + ', '.join(f'{k} {fixer.item_text(v)}' for k, v in e[2].items()))
        if not self.confirm_changes(by_file):
            return False
        out = []
        for path, edits in by_file.items():
            try:
                bk, done, failed = fixer.apply(path, edits)
                out.append(f"{os.path.basename(path)}: {len(done)} changed" + (f", {len(failed)} skipped: " + '; '.join(failed) if failed else ''))
            except fixer.EditError as e:
                out.append(f'{os.path.basename(path)}: not changed - {e}')
        messagebox.showinfo('GearSwap Doctor', '\n'.join(out) + '\n\nIn game: //gs reload (or change job) to use the new sets.')
        self.loaded.clear()
        self.run_check(quiet=True)
        return True

    def confirm_changes(self, by_file):
        """A clear list of exactly what will change, before anything is written. True = go ahead."""
        w = tk.Toplevel(self)
        w.title('Change these GearSwap files?')
        w.geometry('900x480')
        w.transient(self)
        n = sum(len(e[2]) if e[0] in ('slots', 'new') else len(e[3]) if e[0] == 'add' else 1 for edits in by_file.values() for e in edits)
        ttk.Label(w, text=f'{n} change(s) in {len(by_file)} file(s):', font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(10, 4))
        frame = ttk.Frame(w)
        frame.pack(fill='both', expand=True, padx=10)
        t = ttk.Treeview(frame, columns=('set', 'slot', 'now', 'new'), show='tree headings')
        for c, h, wd in (('#0', 'File', 190), ('set', 'Set / name', 250), ('slot', 'Slot', 60), ('now', 'Now', 170), ('new', 'Becomes', 190)):
            t.heading(c, text=h)
            t.column(c, width=wd, anchor='w')
        sb = ttk.Scrollbar(frame, orient='vertical', command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        for path, edits in by_file.items():
            for e in edits:
                if e[0] == 'rename':
                    t.insert('', 'end', text=os.path.basename(path), values=('misspelled name (every set)', '', e[1], e[2]))
                elif e[0] == 'add':
                    for slot, new in e[3].items():
                        t.insert('', 'end', text=os.path.basename(path), values=(e[2] + '  (new set)', slot, '', fixer.item_text(new)))
                elif e[0] == 'new':
                    for slot, new in e[2].items():
                        t.insert('', 'end', text=os.path.basename(path), values=(e[1] + '  (new set)', slot, '', fixer.item_text(new)))
                else:
                    cur = self.set_gear(path, e[1]) if path in self.loaded or os.path.exists(path) else {}
                    for slot, new in e[2].items():
                        t.insert('', 'end', text=os.path.basename(path), values=(e[1], slot, cur.get(slot, ''), fixer.item_text(new)))
        ttk.Label(w, text='Each file is backed up first ("Undo last change" puts it back). A change that would stop a file from '
                          'loading is refused. In game: //gs reload afterwards.', foreground='#555', wraplength=860).pack(anchor='w', padx=10, pady=6)
        res = {'ok': False}
        bar = ttk.Frame(w)
        bar.pack(pady=(0, 10))
        ttk.Button(bar, text=f'Change {n}', style='Big.TButton', command=lambda: (res.update(ok=True), w.destroy())).pack(side='left', padx=6)
        ttk.Button(bar, text='Cancel', command=w.destroy).pack(side='left', padx=6)
        if getattr(self, 'auto_confirm', None) is not None:          # (the tests answer for the user)
            w.after(50, lambda: (res.update(ok=self.auto_confirm), w.destroy()))
        w.grab_set()
        self.wait_window(w)
        return res['ok']

    def undo(self):
        folders = sorted(f for f in glob.glob(os.path.join(self._backups(), '*')) if not f.endswith('_undone'))
        if not folders:
            messagebox.showinfo('GearSwap Doctor', 'No backups to put back.')
            return
        last = folders[-1]
        files = os.listdir(last)
        if not messagebox.askyesno('GearSwap Doctor', 'Put back the files from ' + os.path.basename(last) + '?\n\n' + '\n'.join(files)):
            return
        for f in files:
            shutil.copy2(os.path.join(last, f), os.path.join(doctor.GS_DATA, f))
        shutil.move(last, last + '_undone')
        self.loaded.clear()
        messagebox.showinfo('GearSwap Doctor', 'Put back: ' + ', '.join(files))
        self.run_check(quiet=True)

    # ------------------------------------------------------------------ wsdist version
    def show_ws(self):
        st = updater.state()
        latest = st.get('latest') or {}
        txt = f"this copy {st.get('date', '?')}"
        if latest.get('newer'):
            txt += f"  -  newer on GitHub: {latest['date']} ({latest['message']})"
            self.ws_btn.config(text='Update wsdist', command=self.ws_update)
        else:
            txt += f"  -  up to date (looked {ago(st.get('checked'))})"
            self.ws_btn.config(text='Check for a wsdist update', command=self.ws_check)
        self.ws_label.config(text=txt)
        if hasattr(self, 'wsdist_label'):
            self.wsdist_label.config(text=('wsdist: ' + txt) if updater.installed() else 'wsdist: not downloaded yet')

    def _ws_check_bg(self):
        try:
            updater.check()
        except Exception:
            pass
        self.after(0, self.show_ws)

    def ws_check(self):
        try:
            updater.check()
        except Exception as e:
            messagebox.showerror('GearSwap Doctor', f"Couldn't reach GitHub: {e}")
        self.show_ws()

    def ws_update(self):
        if not messagebox.askyesno('GearSwap Doctor', 'Download the newest wsdist source files from GitHub '
                                   '(github.com/IzaKastra/wsdist_beta, about 1.5 MB) and merge them with this copy '
                                   '(your Blue Magic additions are kept)?'):
            return

        def work():
            try:
                merged, kept = updater.update(log=lambda m: self.after(0, lambda: self.ws_label.config(text=m)))
                msg = f'wsdist updated: {len(merged)} files.' + (f"\nKept this copy's version (couldn't merge): {', '.join(kept)}" if kept else '')
            except Exception as e:
                msg = f'The update failed: {e}'
            self.after(0, lambda: (messagebox.showinfo('GearSwap Doctor', msg), self.show_ws()))
        threading.Thread(target=work, daemon=True).start()


def open_folder(path):
    """In the file manager: Explorer on Windows, whatever the desktop uses on Linux."""
    if os.name == 'nt':
        os.startfile(path)
    else:
        import subprocess
        subprocess.Popen(['xdg-open', path])


def selftest(out_path):
    """GSD_SELFTEST=<file>: the exe checks itself without a window (the build script runs it): Windower found, items
    read, wsdist downloaded and loaded, one real check-up with wsdist. Writes the results as JSON."""
    out = {'frozen': paths.FROZEN, 'app': paths.APP, 'windower': paths.WINDOWER}
    try:
        # (what needs no Windower: Lua and the shared features code are really in the build - the Linux build checks these on GitHub)
        out['lua'] = features.simulate_src('function get_sets() sets.idle = {head="Nyame Helm"} end\n' + features.render({'haste': {'on': True, 'tell': 'Never', 'spell': 'Haste II',
                                           'song': 7, 'geo': 40, 'blu_dw': 25}}), 'Selftest_WAR.lua', features.engine_source())
        out['items'] = len(checks.Items().by_id)
        if not updater.installed():
            updater.update(log=lambda m: None)
        out['wsdist'] = updater.installed()
        import wsdist_runner as W
        out['enemies'] = len(W.enemies())
        chars = characters()
        out['characters'] = len(chars)
        for who in chars:
            files = [f for f in doctor.files_for(who) if checks.job_of(f) in ('BLU', 'PLD', 'WAR', 'SAM', 'DRK', 'THF', 'DNC', 'COR')]
            if files and checks.load_bags(who):
                rep = doctor.checkup(who, files=files[:1], buffs='party')
                f = rep['files'][0]
                out['checkup'] = {'buffs': rep['buffs_text'], 'sets': f['sets'], 'problems': len(f['problems']), 'upgrades': len(f['upgrades']),
                                  'tp_sets': [(u['ws'], u.get('now'), u.get('best')) for u in f['upgrades'] if u.get('kind') == 'tp'],
                                  'errors': [u['error'] for u in f['upgrades'] if 'error' in u][:3]}
                break
        # the features (Add features): every one of them on a real file, in the stand-in GearSwap
        conf = {f['key']: dict(features.defaults(f, [], []), on=True) for f in features.FEATURES}
        for who in chars:
            fs = doctor.files_for(who)
            if fs:
                out['features'] = {'count': len(features.FEATURES), 'file_sets': len(gs_loader.load(fs[0]).sets),
                                   'errors': features.simulate(fs[0], conf)[:3]}
                break
        # healing: every healing set of the first file that has any, built from the item list (no bags needed for the test)
        data = healing.ItemData()
        for who in chars:
            for f in doctor.files_for(who):
                ld = gs_loader.load(f)
                found = healing.find_sets(ld)
                if found:
                    job = checks.job_of(f) or 'WHM'
                    base = healing.defaults(job, 'WAR')
                    x = found[0]
                    cur = healing.set_to_gear(x['gear'], checks.Items(), data)
                    v, _ = healing.evaluate(x['kind'], cur, base, healing.spell_for_set(x['kind'], x['path'], job, 'WAR'))
                    out['healing'] = {'sets': len(found), 'first': x['kind'], 'value': v, 'texts': len(data.text), 'base': base['MND']}
                    break
            if 'healing' in out:
                break
        out['ok'] = True
    except Exception as e:
        import traceback
        out['ok'] = False
        out['error'] = traceback.format_exc()
    json.dump(out, open(out_path, 'w', encoding='utf-8'), indent=1)


def main():
    if os.environ.get('GSD_SELFTEST'):
        selftest(os.environ['GSD_SELFTEST'])
        return
    # its own taskbar button and icon (not Python's)
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('GearSwapDoctor.App')
    except Exception:
        pass
    App().mainloop()


if __name__ == '__main__':
    main()
