"""
GearSwap Doctor - its own application (his request 2026-10-23: "make gearswap doctor its own application with a full gui
similiar to wsdist"). Laid out like wsdist (Kastra's damage simulator): the Windows look, tabs across the top, gear shown
in the game's equipment grid (main / sub / range / ammo, head / neck / ears, body / hands / rings, back / waist / legs /
feet), numbers in a fixed-width font.

Tabs
  Overview     each GearSwap file of the character: loads?, sets, problems, wsdist upgrades; Check now; wsdist version
  Problems     what's wrong (broken / misspelled / wrong slot / wrong job / not owned / in storage), filter by kind
  Upgrades     wsdist's better weapon skill sets, your set and the better one side by side in the equipment grid
  Sets         every set in every file, in the equipment grid, its problems marked
  Simulate     wsdist on one weapon skill set: its damage, and the best set from your gear (TP, enemy, sub job)
  My gear      what the character owns (Steward's saved copy), by bag, with a search
  Backups      every backup GearSwap Doctor made; put one back
  Settings     characters, sub job per job, TP and enemy for the check-ups, the daily check
Nothing in a GearSwap file changes without a click; each change is backed up first and refused if the file would break.
"""
import glob
import json
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
import checks   # noqa: E402
import doctor   # noqa: E402
import fixer    # noqa: E402
import gs_loader  # noqa: E402
import updater  # noqa: E402

VERSION = '2.2.0'
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

Words
  Set        a group of gear GearSwap puts on for something, e.g. sets.precast.WS["Savage Blade"]
  Slot       where an item goes: main, sub, range, ammo, head, neck, ears, body, hands, rings, back, waist, legs, feet
  Wardrobe   the Mog Wardrobes 1-8: GearSwap equips from them and the inventory, nothing else
  Upgrade    a set wsdist found that does more damage, using only gear this character owns
  wsdist     Kastra's FFXI damage simulator - its numbers are estimates for comparing sets (1500 TP on an Apex Toad,
             no buffs, unless changed in Settings), not exact in-game damage
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


def gs_slot(key):
    return gs_loader.SLOTS.get(str(key).lower())


def load_settings():
    d = {'tp': 1500, 'enemy': 'Apex Toad', 'subs': {}, 'daily': True, 'character': None}
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
            style.theme_use('vista')                     # wsdist's look
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
        ico = os.path.join(getattr(sys, '_MEIPASS', HERE), 'gsd.ico')
        try:
            if os.path.exists(ico):
                self.iconbitmap(ico)
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
            self.after(0, lambda: self.sim_status.config(text=f'wsdist could not load: {e}'))

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

        s2 = section('2. Upgrades - better weapon skill sets from gear you already own (wsdist)')
        self.jt_up = ttk.Treeview(s2, columns=('gain', 'worth', 'items', 'dmg'), show='tree headings', height=6)
        self.jt_up.heading('#0', text='Weapon skill')
        self.jt_up.column('#0', width=220)
        for c, h, w in (('gain', 'Gain', 70), ('worth', 'Worth it?', 90), ('items', 'Items', 50), ('dmg', 'Damage now -> best', 140)):
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
                    if 'error' not in u and 5 <= u['gain'] <= 100:
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
                                        values=(f"+{u['gain']}%", verdict(u['gain']) + (' ⚑' if u['gain'] > 100 else ''),
                                                len(u['changes']), f"{u['now']} -> {u['best']}"),
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
        self._say(self.jt_up_text, 'Click an upgrade to see exactly what it swaps.' if n_up else '')

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
        lines = [f"{verdict(u['gain'])}: +{u['gain']}% average damage for {u['ws']} ({u['now']} -> {u['best']})  -  "
                 f"{os.path.basename(path)}, {u['set']}"]
        for slot, new in u['changes'].items():
            bag = where.get(new.lower())
            lines.append(f"  {SLOT_TEXT.get(slot, slot):<7} {now.get(slot) or '(empty)'}  ->  {new}" + (f"   (in your {bag})" if bag else ''))
        if u['gain'] > 100:
            lines.append(BIG_GAIN_NOTE)
        self._say(self.jt_up_text, '\n'.join(lines))

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
            self._card('good', f"{u['ws']}: {verdict(u['gain']).lower()} (+{u['gain']}% damage) in {f['file']}",
                       f"wsdist found a better set from gear you already own: {n} item(s) change "
                       f"({', '.join(list(u['changes'].values())[:4])}{' ...' if n > 4 else ''}). Average damage {u['now']} -> {u['best']}."
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
        frame, self.upg = self._tree(left, ('gain', 'verdict', 'swaps', 'dmg'), ('Gain', 'Worth it?', 'Items', 'Damage now -> best'),
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
        ttk.Label(right, text='Green = a swap. Tick the weapon skill on the left, then Apply ticked.', foreground='#666').pack(anchor='w')
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
        self.upg_head.config(text=f"{u['ws']:<22} now {u['now']:>6}   best {u['best']:>6}   +{u['gain']}%")
        self.grid_now.show(now, {s: '#fbe3c4' for s in u['changes']})
        self.grid_best.show(best, marks)
        where = self.item_bags()
        lines = [f"{verdict(u['gain'])}: +{u['gain']}% average damage for {u['ws']} ({u['now']} -> {u['best']}), "
                 f"{len(u['changes'])} item(s) change - all gear this character already owns.", '', 'The swaps:']
        for slot, new in u['changes'].items():
            old = now.get(slot) or '(empty)'
            bag = where.get(new.lower())
            lines.append(f"  {SLOT_TEXT.get(slot, slot):<7} {old}  ->  {new}" + (f"   (it's in your {bag})" if bag else ''))
        if u['gain'] < 5:
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
        ttk.Button(sim, text='Send to Simulate', command=self.set_to_sim).pack(side='left', padx=8)
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
        self.sim_enemy.set(self.set_enemy.get())
        self.sim_tp.set(self.set_tp.get())

    def _report_file(self, path):
        for f in (self.report or {}).get('files', []):
            if os.path.basename(f['path']).lower() == os.path.basename(path).lower():
                return f
        return None

    # ------------------------------------------------------------------ Simulate
    def _simulate_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.tab_sim = tab
        self.nb.add(tab, text='Simulate')
        inp = ttk.LabelFrame(tab, text='Inputs', padding=8)
        inp.pack(fill='x')
        ttk.Label(inp, text='File').grid(row=0, column=0, sticky='w')
        self.sim_file = ttk.Combobox(inp, width=30, state='readonly')
        self.sim_file.grid(row=0, column=1, sticky='w', padx=4, pady=2)
        self.sim_file.bind('<<ComboboxSelected>>', lambda e: self.sim_file_changed())
        ttk.Label(inp, text='Weapon skill set').grid(row=1, column=0, sticky='w')
        self.sim_set = ttk.Combobox(inp, width=50, state='readonly')
        self.sim_set.grid(row=1, column=1, columnspan=3, sticky='w', padx=4, pady=2)
        ttk.Label(inp, text='Sub job').grid(row=0, column=2, sticky='w', padx=(16, 0))
        self.sim_sub = ttk.Combobox(inp, values=JOBS, width=6, state='readonly')
        self.sim_sub.set('WAR')
        self.sim_sub.grid(row=0, column=3, sticky='w', padx=4)
        ttk.Label(inp, text='Enemy').grid(row=2, column=0, sticky='w')
        self.sim_enemy = ttk.Combobox(inp, values=self.enemy_list, width=30, state='readonly')
        self.sim_enemy.set(self.cfg['enemy'])
        self.sim_enemy.grid(row=2, column=1, sticky='w', padx=4, pady=2)
        ttk.Label(inp, text='TP').grid(row=2, column=2, sticky='w', padx=(16, 0))
        self.sim_tp = tk.IntVar(value=self.cfg['tp'])
        tp = ttk.Frame(inp)
        tp.grid(row=2, column=3, sticky='w')
        ttk.Scale(tp, from_=1000, to=3000, variable=self.sim_tp, length=180,
                  command=lambda v: self.sim_tp.set(int(round(float(v) / 50) * 50))).pack(side='left')
        ttk.Label(tp, textvariable=self.sim_tp, font=MONO, width=5).pack(side='left', padx=4)
        btns = ttk.Frame(tab)
        btns.pack(fill='x', pady=6)
        ttk.Button(btns, text='Damage of this set', style='Big.TButton', command=lambda: self.simulate(False)).pack(side='left')
        ttk.Button(btns, text='Find the best set from my gear', style='Big.TButton', command=lambda: self.simulate(True)).pack(side='left', padx=8)
        self.sim_apply_btn = ttk.Button(btns, text='Put the best set in the file', command=self.sim_apply, state='disabled')
        self.sim_apply_btn.pack(side='left', padx=8)
        self.sim_status = ttk.Label(btns, text='Loading wsdist ...')
        self.sim_status.pack(side='left', padx=8)
        res = ttk.LabelFrame(tab, text='Results', padding=8)
        res.pack(fill='both', expand=True)
        self.sim_result = ttk.Label(res, text='', font=('Courier New', 11))
        self.sim_result.pack(anchor='w', pady=(0, 6))
        grids = ttk.Frame(res)
        grids.pack(fill='both', expand=True)
        self.sim_grid_now = GearGrid(grids, 'The set', lambda: self.items)
        self.sim_grid_now.pack(side='left', fill='both', expand=True, padx=(0, 4))
        self.sim_grid_best = GearGrid(grids, 'Best from your gear', lambda: self.items)
        self.sim_grid_best.pack(side='left', fill='both', expand=True)
        self.sim_best = None

    def sim_file_changed(self):
        name = self.sim_file.get()
        path = os.path.join(doctor.GS_DATA, name)
        try:
            ld = self.loaded_file(path)
        except Exception:
            return
        import wsdist_runner as W
        known = W.ws_list() if self.ws_ready else None
        sets = [s['path'] for s in ld.sets if '.WS' in s['path'] or 'WS[' in s['path']]
        if known:
            sets = [p for p in sets if doctor.ws_of(p, known)] or sets
        self.sim_set.configure(values=sets)
        if sets:
            self.sim_set.set(sets[0])
        job = checks.job_of(name)
        if job:
            self.sim_sub.set(self.cfg['subs'].get(job, self.sim_sub.get()))

    def simulate(self, find_best):
        if not updater.installed():
            self.install_wsdist(ask=True)
            return
        if not self.ws_ready:
            messagebox.showinfo('GearSwap Doctor', 'wsdist is still loading - try again in a moment.')
            return
        name, set_path = self.sim_file.get(), self.sim_set.get()
        if not name or not set_path:
            messagebox.showinfo('GearSwap Doctor', 'Pick a file and a weapon skill set first.')
            return
        path = os.path.join(doctor.GS_DATA, name)
        job, sub, tp, enemy = checks.job_of(name), self.sim_sub.get(), int(self.sim_tp.get()), self.sim_enemy.get()
        who = self.who.get()
        self.sim_status.config(text='wsdist is working ...')
        self.progress.config(mode='indeterminate'); self.progress.start(12)

        def work():
            try:
                import wsdist_runner as W
                ld = self.loaded_file(path)
                known = W.ws_list()
                ws = doctor.ws_of(set_path, known)
                if not ws and '"' in set_path and set_path.split('"')[1] in known:
                    ws = set_path.split('"')[1]
                if not ws:
                    raise ValueError(f"{set_path} isn't a weapon skill wsdist knows")
                items = self.items or checks.Items()
                bags = checks.load_bags(who) or {}
                owned_ids = set()
                for b, c in bags.items():
                    if not b.startswith('_') and b in checks.EQUIP_BAGS:
                        owned_ids |= set(c)
                index = W.gear_index()
                gear = next(s['gear'] for s in ld.sets if s['path'] == set_path)
                weapons = [(s['path'], s['gear']) for s in ld.sets if s['path'].startswith('sets.weapons')]
                owned, cur, notes, skill = W.plan_ws(job, sub, ws, gear, weapons, owned_ids, items, index)
                if 'main' not in cur:
                    raise ValueError(f'no {skill or "matching"} weapon to test it with')
                now_gear = {W.GS_SLOT[s]: doctor._gs_name(e, items) for s, e in cur.items() if e and e.get('Name') != 'Empty'}
                if find_best:
                    best, dmg, now = W.best_ws_set(job, sub, ws, owned, cur, tp=tp, enemy_name=enemy)
                    best_gear = {W.GS_SLOT[s]: doctor._gs_name(e, items) for s, e in best.items() if e and e['Name'] != 'Empty'}
                else:
                    now, dmg, best_gear = W.set_damage(job, sub, ws, cur, tp=tp, enemy_name=enemy), None, None
                self.after(0, lambda: self._sim_done(path, set_path, ws, now, dmg, now_gear, best_gear, notes, tp, enemy))
            except Exception as e:
                self.after(0, lambda: self._sim_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _sim_done(self, path, set_path, ws, now, dmg, now_gear, best_gear, notes, tp, enemy):
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        self.sim_status.config(text=f'{ws} at {tp} TP on {enemy}' + (('   (' + '; '.join(notes) + ')') if notes else ''))
        if dmg is None:
            self.sim_result.config(text=f'Average damage = {now:>8.0f}')
            self.sim_grid_now.show(now_gear)
            self.sim_grid_best.show({})
            self.sim_best = None
            self.sim_apply_btn.config(state='disabled')
            return
        gain = (dmg - now) / now * 100 if now else 0
        self.sim_result.config(text=f'Your set = {now:>8.0f}    Best = {dmg:>8.0f}    {gain:+.1f}%')
        changes = {s: n for s, n in best_gear.items() if s not in ('main', 'sub', 'range') and now_gear.get(s) != n}
        for p1, p2 in (('ear1', 'ear2'), ('ring1', 'ring2')):          # only swapped sides: not a change
            if sorted(filter(None, [now_gear.get(p1), now_gear.get(p2)])) == sorted(filter(None, [best_gear.get(p1), best_gear.get(p2)])):
                changes.pop(p1, None)
                changes.pop(p2, None)
        self.sim_grid_now.show(now_gear, {s: '#fbe3c4' for s in changes})
        self.sim_grid_best.show(best_gear, {s: '#c8efc0' for s in changes})
        self.sim_best = (path, set_path, changes) if changes and gain > 0 else None
        self.sim_apply_btn.config(state='normal' if self.sim_best else 'disabled')

    def _sim_failed(self, e):
        self.progress.stop(); self.progress.config(mode='determinate', value=0)
        self.sim_status.config(text=f'wsdist could not do it: {e}')

    def sim_apply(self):
        if not self.sim_best:
            return
        path, set_path, changes = self.sim_best
        self._apply({path: [('slots', set_path, changes)]})

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
        ttk.Button(bar, text='Open the backups folder', command=lambda: os.startfile(self._backups())).pack(side='left', padx=8)
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

    def save_cfg(self):
        self.cfg['tp'] = int(self.cfg_tp.get())
        self.cfg['enemy'] = self.cfg_enemy.get() or 'Apex Toad'
        self.cfg['subs'] = {j: cb.get() for j, cb in self.cfg_subs.items()}
        self.cfg['daily'] = bool(self.cfg_daily.get())
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
                                    + (f"  -  wsdist: {r.get('tp', 1500)} TP on {r.get('enemy', 'Apex Toad')}"))

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
            fid = t.insert('', 'end', iid=self._iid('u'), text=f"{f['file']}  ({len(good)})", open=bool(good))
            ups = sorted(ups, key=lambda u: -(u.get('gain') or -1))           # (the biggest gains first)
            for u in ups:
                if 'error' in u:
                    row = t.insert(fid, 'end', iid=self._iid('u'), text='   ' + u['ws'], values=('-', 'not checked', '', '-'), tags=('small',))
                    self.info[row] = u['error']
                    continue
                row = t.insert(fid, 'end', iid=self._iid('u'), text=OFF + ' ' + u['ws'],
                               values=(f"+{u['gain']}%", verdict(u['gain']), len(u['changes']), f"{u['now']} -> {u['best']}"),
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
                                     progress=lambda m: self.after(0, lambda: self.status.config(text=m + ' ...')))
                self.after(0, lambda: self._done(rep, who))
            except Exception as e:
                self.after(0, lambda: self._failed(e, quiet))
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
                lines.append(f'   {e[1]} -> {e[2]}' if e[0] == 'rename' else f'   {e[1]}: ' + ', '.join(f'{k} {v}' for k, v in e[2].items()))
        if not self.confirm_changes(by_file):
            return
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

    def confirm_changes(self, by_file):
        """A clear list of exactly what will change, before anything is written. True = go ahead."""
        w = tk.Toplevel(self)
        w.title('Change these GearSwap files?')
        w.geometry('900x480')
        w.transient(self)
        n = sum(len(e[2]) if e[0] == 'slots' else 1 for edits in by_file.values() for e in edits)
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
                else:
                    cur = self.set_gear(path, e[1]) if path in self.loaded or os.path.exists(path) else {}
                    for slot, new in e[2].items():
                        t.insert('', 'end', text=os.path.basename(path), values=(e[1], slot, cur.get(slot, ''), new))
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


def selftest(out_path):
    """GSD_SELFTEST=<file>: the exe checks itself without a window (the build script runs it): Windower found, items
    read, wsdist downloaded and loaded, one real check-up with wsdist. Writes the results as JSON."""
    out = {'frozen': paths.FROZEN, 'app': paths.APP, 'windower': paths.WINDOWER}
    try:
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
                rep = doctor.checkup(who, files=files[:1])
                f = rep['files'][0]
                out['checkup'] = {'sets': f['sets'], 'problems': len(f['problems']), 'upgrades': len(f['upgrades']),
                                  'errors': [u['error'] for u in f['upgrades'] if 'error' in u][:3]}
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
