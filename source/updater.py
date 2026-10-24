"""
GearSwap Doctor: keeping wsdist current (github.com/IzaKastra/wsdist_beta, Kastra's simulator).

  check()   asks GitHub for the newest change to wsdist (read only, nothing downloaded) - once a day from the app
  update()  downloads the newest source files (not the .exe), then merges them with this copy: the local additions
            (his Blue Magic spells, the shield fix) are kept - a three-way merge (git merge-file) of
            wsdist_upstream (the version last downloaded) -> wsdist (ours) and the new download (theirs).
            A file that can't be merged cleanly keeps our version and is listed.
"""
import json
import os
import shutil
import subprocess
import time
import urllib.request

import paths

HERE = os.path.dirname(os.path.abspath(__file__))
OURS = paths.WSDIST
BASE = paths.WSDIST_BASE
STATE = os.path.join(paths.DATA, 'wsdist_version.json')


def installed():
    """Is wsdist here? (The stand-alone exe downloads it from Kastra's GitHub on first use.)"""
    return os.path.exists(os.path.join(OURS, 'wsdist.py'))


# Small fixes GearSwap Doctor needs in wsdist, made on this PC to the downloaded files (wsdist itself isn't shipped):
#   get_pdif.py - a shield or grip in the sub slot left pdif_base_cap unset ("referenced before assignment")
FIXES = [('get_pdif.py',
          'elif wpn_type_skill=="Scythe":\n        pdif_base_cap = 4.0\n',
          'elif wpn_type_skill=="Scythe":\n        pdif_base_cap = 4.0\n    else:\n'
          '        pdif_base_cap = 3.25 # (GearSwap Doctor: a shield / grip in the sub slot)\n')]


def apply_fixes(folder=None):
    """Make GearSwap Doctor's small fixes in a wsdist folder (each only once). Returns the files changed."""
    folder = folder or OURS
    done = []
    for name, old, new in FIXES:
        p = os.path.join(folder, name)
        if not os.path.exists(p):
            continue
        raw = open(p, 'rb').read().decode('utf-8', 'replace')
        crlf = chr(13) + chr(10) in raw
        text = raw.replace(chr(13) + chr(10), chr(10))
        i = text.find(old)
        # (already fixed - by this or by hand: the line after it is an else)
        if new in text or i < 0 or text[i + len(old):].lstrip(' ').startswith('else'):
            continue
        text = text.replace(old, new)
        open(p, 'w', encoding='utf-8', newline=chr(13) + chr(10) if crlf else chr(10)).write(text)
        done.append(name)
    return done


REPO = 'IzaKastra/wsdist_beta'
SKIP = ('.exe', '.png', '.ico', '.spec')


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'GearSwap-Doctor'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def state():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, 'w', encoding='utf-8'), indent=1)


def check():
    """{'sha', 'date', 'message', 'newer': bool} for the newest wsdist change on GitHub."""
    c = json.loads(_get(f'https://api.github.com/repos/{REPO}/commits?per_page=1'))[0]
    st = state()
    info = {'sha': c['sha'], 'date': c['commit']['committer']['date'][:10], 'message': c['commit']['message'].splitlines()[0]}
    info['newer'] = info['sha'] != st.get('sha')
    st['checked'] = int(time.time())
    st['latest'] = info
    _save(st)
    return info


def due():
    """A day since the last check?"""
    return time.time() - state().get('checked', 0) > 24 * 3600


def update(log=print):
    """Download the newest wsdist and merge it in. Returns (merged files, files that kept our version)."""
    info = check()
    tree = json.loads(_get(f'https://api.github.com/repos/{REPO}/git/trees/{info["sha"]}'))['tree']
    files = [t['path'] for t in tree if t['type'] == 'blob' and not t['path'].lower().endswith(SKIP)
             and '/' not in t['path'] and not t['path'].startswith('.')]
    new = BASE + '_new'
    shutil.rmtree(new, ignore_errors=True)
    os.makedirs(new)
    os.makedirs(OURS, exist_ok=True)
    for f in files:
        log('downloading ' + f)
        open(os.path.join(new, f), 'wb').write(_get(f'https://raw.githubusercontent.com/{REPO}/{info["sha"]}/{f}', 60))
    merged, kept = [], []
    for f in files:
        theirs, base, ours = os.path.join(new, f), os.path.join(BASE, f), os.path.join(OURS, f)
        if not os.path.exists(ours) or not os.path.exists(base) or not f.endswith('.py'):
            shutil.copy2(theirs, ours)                       # new file, or data (csv / pkl): take theirs
            merged.append(f)
            continue
        if open(ours, 'rb').read() == open(base, 'rb').read():
            shutil.copy2(theirs, ours)                       # no local change: theirs as it is
            merged.append(f)
            continue
        tmp = ours + '.merge'
        shutil.copy2(ours, tmp)
        try:
            r = subprocess.run(['git', 'merge-file', '-q', tmp, base, theirs], capture_output=True)
        except OSError:                                    # (no git on this PC: keep ours)
            r = None
        if r is not None and r.returncode == 0:
            shutil.move(tmp, ours)
            merged.append(f)
        else:
            os.remove(tmp)
            kept.append(f)
    apply_fixes()
    shutil.rmtree(BASE, ignore_errors=True)
    shutil.move(new, BASE)
    st = state()
    st.update({'sha': info['sha'], 'date': info['date'], 'updated': int(time.time())})
    _save(st)
    return merged, kept
