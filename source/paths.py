"""
GearSwap Doctor: where things are.

Run from the Windower folder (addons\\GearSwap\\gearcheck, as the owner does) everything sits next to the code.
Run as the stand-alone exe (anyone, anywhere), its own files go to %APPDATA%\\GearSwap Doctor (settings, reports,
backups, and wsdist - downloaded from Kastra's GitHub on first use, not shipped inside the exe), and the Windower folder
is found by itself or picked once in the app.
"""
import json
import os
import sys

FROZEN = getattr(sys, 'frozen', False)
CODE = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))

if FROZEN:
    APP = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'GearSwap Doctor')
else:
    APP = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(APP, 'data')
BACKUPS = os.path.join(APP, 'backups')
WSDIST = os.path.join(APP, 'wsdist')
WSDIST_BASE = os.path.join(APP, 'wsdist_upstream')
SETTINGS = os.path.join(DATA, 'settings.json')


def _saved_windower():
    try:
        return json.load(open(SETTINGS, encoding='utf-8')).get('windower')
    except (OSError, ValueError):
        return None


def is_windower(path):
    return bool(path) and os.path.isdir(os.path.join(path, 'addons', 'GearSwap')) and os.path.isdir(os.path.join(path, 'res'))


def find_windower():
    """The Windower 4 folder: the saved choice, the folder this runs from (or one above it), the usual places."""
    cands = [_saved_windower()]
    p = CODE
    for _ in range(5):                       # (the exe or the code inside a Windower folder)
        cands.append(p)
        p = os.path.dirname(p)
    home = os.path.expanduser('~')
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), 'C:\\', 'D:\\', os.path.join(home, 'Desktop'),
                 os.path.join(home, 'Documents'), os.path.join(home, 'Games')):
        if base:
            for name in ('Windower4', 'Windower', 'Windower 4', os.path.join('PlayOnline', 'Windower4')):
                cands.append(os.path.join(base, name))
    for c in cands:
        if is_windower(c):
            return os.path.normpath(c)
    return None


WINDOWER = find_windower()


def set_windower(path):
    """The app's folder picker: remember it and use it from now on."""
    global WINDOWER
    WINDOWER = os.path.normpath(path)
    os.makedirs(DATA, exist_ok=True)
    try:
        d = json.load(open(SETTINGS, encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    d['windower'] = WINDOWER
    json.dump(d, open(SETTINGS, 'w', encoding='utf-8'), indent=1)


def gs_data():
    return os.path.join(WINDOWER or '', 'addons', 'GearSwap', 'data')


def res_items():
    return os.path.join(WINDOWER or '', 'res', 'items.lua')
