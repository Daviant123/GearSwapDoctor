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

VERSION = '2.0.0'
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

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill='both', expand=True, padx=8, pady=8)
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
        ttk.Button(bottom, text='Apply ticked', style='Big.TButton', command=self.apply).pack(side='left')
        ttk.Button(bottom, text='Undo last change', command=self.undo).pack(side='left', padx=8)
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
        self.nb.select(3)
        if path:
            self.fill_sets(focus=path)

    # ------------------------------------------------------------------ Problems
    def _problems_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text='Problems')
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text='Show').pack(side='left')
        self.kind_on = {}
        for k, label in KIND_TEXT.items():
            v = tk.BooleanVar(value=True)
            self.kind_on[k] = v
            ttk.Checkbutton(bar, text=label, variable=v, command=self.fill_problems).pack(side='left', padx=4)
        frame, self.prob = self._tree(tab, ('kind', 'item', 'slot', 'detail', 'sets'),
                                      ('What', 'Item / set', 'Slot', 'Details', 'Sets'), (100, 220, 60, 470, 50))
        frame.pack(fill='both', expand=True)
        self.prob.bind('<Button-1>', self._click_tick)
        self.prob.bind('<<TreeviewSelect>>', lambda e: self._show_info(self.prob, self.prob_text))
        self.prob_text = self._textbox(tab, 4)
        self.prob_text.pack(fill='x', pady=(6, 0))
        ttk.Label(tab, text='Tick a Misspelled row (click its box) to fix the name; the others are for you to look at.',
                  foreground='#666').pack(anchor='w')

    # ------------------------------------------------------------------ Upgrades
    def _upgrades_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text='Upgrades (wsdist)')
        pw = ttk.PanedWindow(tab, orient='horizontal')
        pw.pack(fill='both', expand=True)
        left = ttk.Frame(pw)
        frame, self.upg = self._tree(left, ('gain', 'dmg'), ('Gain', 'Damage now -> best'), (70, 150), tree_width=230)
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
        self.upg_text = self._textbox(right, 4)
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
        self._say(self.upg_text, f"{os.path.basename(path)}  -  {u['set']}\n" + '\n'.join(u.get('notes') or []))

    # ------------------------------------------------------------------ Sets
    def _sets_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
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
        self.nb.select(4)
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
        for f in r['files']:
            probs = [p for p in f['problems'] if self.kind_on[p['kind']].get()] if f['problems'] else []
            if not probs:
                continue
            fid = t.insert('', 'end', iid=self._iid('p'), text=f"{f['file']}  ({len(probs)})", open=any(p['kind'] in ('broken', 'unknown') for p in probs))
            for p in probs:
                fix = p.get('fix')
                fixable = p['kind'] == 'unknown' and fix
                detail = p['detail'] + (f'   [fix: {fix}]' if fixable else '')
                row = t.insert(fid, 'end', iid=self._iid('p'), text=(OFF + ' ' if fixable else '   ') + KIND_TEXT.get(p['kind'], p['kind']),
                               values=(KIND_TEXT.get(p['kind'], p['kind']), p['item'], p['slot'], detail, len(p['sets'])))
                if fixable:
                    self.rows[row] = (f['path'], ('rename', p['item'], fix))
                where = ', '.join(x for x in p['sets'] if x)
                self.info[row] = (f"{KIND_TEXT.get(p['kind'], p['kind'])}: {p['item']} {p['detail']}"
                                  + (('\nIn: ' + where) if where else '')
                                  + (f'\nTick it and click Apply ticked to change it to {fix}.' if fixable else ''))
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
            for u in ups:
                if 'error' in u:
                    row = t.insert(fid, 'end', iid=self._iid('u'), text='   ' + u['ws'], values=('-', '-'))
                    self.info[row] = u['error']
                    continue
                row = t.insert(fid, 'end', iid=self._iid('u'), text=OFF + ' ' + u['ws'], values=(f"+{u['gain']}%", f"{u['now']} -> {u['best']}"))
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
        if not messagebox.askyesno('GearSwap Doctor', 'Change these GearSwap files? (each is backed up first)\n\n' + '\n'.join(lines)):
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
