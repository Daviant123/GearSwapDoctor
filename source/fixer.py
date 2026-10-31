"""
GearSwap Doctor: changes to a GearSwap file, only the ones he approved, always with a backup first.

  rename(src, old, new)               a misspelled / old item name -> the real one, everywhere in the file
  set_slots(src, set_path, changes)   in one set: these slots get these items (a set made with set_combine(base, {..})
                                      gets them in its own {..}, so the shared base set and the other sets built on it
                                      are left alone)
  apply(path, edits)                  backup -> edit -> load the result again; anything that would stop the file
                                      loading is undone and the file is left as it was
"""
import datetime
import os
import re
import shutil

import gs_loader

HERE = os.path.dirname(os.path.abspath(__file__))
import paths  # noqa: E402
BACKUPS = paths.BACKUPS
SLOT_KEYS = {'main': ['main'], 'sub': ['sub'], 'range': ['range', 'ranged'], 'ammo': ['ammo'], 'head': ['head'],
             'neck': ['neck'], 'ear1': ['ear1', 'left_ear', 'lear'], 'ear2': ['ear2', 'right_ear', 'rear'],
             'body': ['body'], 'hands': ['hands'], 'ring1': ['ring1', 'left_ring', 'lring'],
             'ring2': ['ring2', 'right_ring', 'rring'], 'back': ['back'], 'waist': ['waist'], 'legs': ['legs'],
             'feet': ['feet']}


class EditError(Exception):
    pass


# ---------- reading Lua text: skip strings and comments ----------
def _skip(src, i):
    """If a string or comment starts at i, the index just after it; else None."""
    c = src[i]
    if src.startswith('--', i):
        m = re.match(r'--\[(=*)\[', src[i:])
        if m:
            end = src.find(']' + m.group(1) + ']', i)
            return len(src) if end < 0 else end + len(m.group(1)) + 2
        end = src.find('\n', i)
        return len(src) if end < 0 else end
    if c in '"\'':
        j = i + 1
        while j < len(src) and src[j] != c:
            j += 2 if src[j] == '\\' else 1
        return j + 1
    if c == '[':
        m = re.match(r'\[(=*)\[', src[i:])
        if m:
            end = src.find(']' + m.group(1) + ']', i)
            return len(src) if end < 0 else end + len(m.group(1)) + 2
    return None


def _match(src, i, open_c, close_c):
    """Index of the bracket closing the one at i."""
    depth = 0
    j = i
    while j < len(src):
        s = _skip(src, j)
        if s is not None:
            j = s
            continue
        if src[j] == open_c:
            depth += 1
        elif src[j] == close_c:
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise EditError('unbalanced ' + open_c + close_c)


def _code_positions(src):
    """A mask of which characters are code (not inside a string or comment)."""
    mask = bytearray(len(src))
    j = 0
    while j < len(src):
        s = _skip(src, j)
        if s is not None:
            j = s
            continue
        mask[j] = 1
        j += 1
    return mask


# ---------- finding a set ----------
def _path_parts(path):
    """'sets.precast.WS["Savage Blade"]' -> ['sets', 'precast', 'WS', 'Savage Blade']"""
    parts = []
    for m in re.finditer(r'\.?([A-Za-z_][A-Za-z0-9_]*)|\[\s*"((?:[^"\\]|\\.)*)"\s*\]', path):
        parts.append(m.group(1) if m.group(1) is not None else m.group(2).replace('\\"', '"'))
    return parts


def _path_regex(path):
    parts = _path_parts(path)
    rx = re.escape(parts[0])
    for p in parts[1:]:
        q = re.escape(p)
        alt = r'\[\s*["\']' + q + r'["\']\s*\]'
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', p):
            alt = r'(?:\s*\.\s*' + q + '|' + alt + ')'
        else:
            alt = r'\s*' + alt
        rx += alt
    return re.compile(rx + r'\s*=(?!=)\s*')


def find_set(src, path):
    """(start, end) of the table to edit for this set: its own {..} - the last one if it's made more than once."""
    mask = _code_positions(src)
    hits = [m for m in _path_regex(path).finditer(src) if mask[m.start()]]
    if not hits:
        raise EditError(f'{path} not found in the file')
    m = hits[-1]
    i = m.end()
    if src.startswith('{', i):
        return i, _match(src, i, '{', '}')
    if src.startswith('set_combine', i):
        p = src.index('(', i)
        close = _match(src, p, '(', ')')
        # the last table literal among set_combine's arguments
        last = None
        j = p + 1
        while j < close:
            s = _skip(src, j)
            if s is not None:
                j = s
                continue
            if src[j] == '{':
                e = _match(src, j, '{', '}')
                last = (j, e)
                j = e + 1
                continue
            if src[j] == '(':
                j = _match(src, j, '(', ')') + 1
                continue
            j += 1
        if last:
            return last
        raise EditError(f'{path} is made from other sets only - nothing of its own to change')
    raise EditError(f'{path} is copied from another set - change that set instead')


def _value_end(src, i):
    """End (exclusive) of the Lua value starting at i: a string or a {..} table."""
    if src[i] in '"\'':
        return _skip(src, i)
    if src[i] == '{':
        return _match(src, i, '{', '}') + 1
    m = re.match(r'[^,}\n]+', src[i:])
    return i + (m.end() if m else 0)


def _lua_str(name):
    """An item as Lua: "Name", or { name="Name", augments={'...','...'} } when it's one augmented copy (a dict)."""
    if isinstance(name, dict):
        aug = ','.join("'" + str(a).replace('\\', '\\\\').replace("'", "\\'") + "'" for a in name.get('augments') or [])
        return '{ name=' + _lua_str(name['name']) + (', augments={' + aug + ',}' if aug else '') + ' }'
    return '"' + name.replace('\\', '\\\\').replace('"', '\\"') + '"'


def item_text(v):
    """An item as words, for the lists he sees."""
    if isinstance(v, dict):
        return v['name'] + (' (' + ', '.join(str(a) for a in v.get('augments') or []) + ')' if v.get('augments') else '')
    return str(v)


def set_slots(src, path, changes):
    """changes: {gearswap slot: item name ('empty' to clear)}. Returns the new text."""
    start, end = find_set(src, path)
    body = src[start:end + 1]
    mask = _code_positions(body)
    for slot, name in changes.items():
        keys = SLOT_KEYS.get(slot, [slot])
        rx = re.compile(r'(?<![A-Za-z0-9_])(' + '|'.join(keys) + r')\s*=\s*', re.I)
        hit = None
        for m in rx.finditer(body):
            if mask[m.start()] and _depth(body, m.start()) == 1:
                hit = m
        if hit:
            vs = hit.end()
            ve = _value_end(body, vs)
            body = body[:vs] + _lua_str(name) + body[ve:]
        else:
            body = '{' + keys[0] + '=' + _lua_str(name) + (',' if body[1:].strip()[:1] not in ('}', '') else '') + body[1:]
        mask = _code_positions(body)
    return src[:start] + body + src[end + 1:]


def _statement_end(src, path):
    "(end of the line where this set's statement ends, its indent); None when the file doesn't make it."
    mask = _code_positions(src)
    hits = [m for m in _path_regex(path).finditer(src) if mask[m.start()]]
    if not hits:
        return None
    m = hits[-1]
    i = m.end()
    if src.startswith('{', i):
        end = _match(src, i, '{', '}') + 1
    elif src.startswith('set_combine', i):
        end = _match(src, src.index('(', i), '(', ')') + 1
    else:
        end = i
    nl = src.find('\n', end)
    line_start = src.rfind('\n', 0, m.start()) + 1
    return (len(src) if nl < 0 else nl), re.match(r'[ \t]*', src[line_start:]).group(0)


def add_new_set(src, new_path, gear, anchors):
    """A set the file doesn't have yet (sets.midcast.Cursna): after the last set beside it, else after the set it goes under,
    else after one of the file's other sets (anchors: the file's sets). Tables it needs that the file doesn't make get a
    harmless line first: sets.midcast = sets.midcast or {}."""
    mask = _code_positions(src)
    if any(mask[m.start()] for m in _path_regex(new_path).finditer(src)):
        raise EditError(f'{new_path} is in the file already')
    parts = _path_parts(new_path)
    parents = ['.'.join(parts[:i]) for i in range(2, len(parts))]
    spots = []
    if parents:
        for a in anchors:
            if a.startswith(parents[-1] + '.') or a.startswith(parents[-1] + '['):
                s = _statement_end(src, a)
                if s:
                    spots.append(s)
    for p in reversed(parents):
        if not spots:
            s = _statement_end(src, p)
            if s:
                spots.append(s)
    if not spots:
        for a in anchors:
            s = _statement_end(src, a)
            if s:
                spots.append(s)
    if not spots:
        raise EditError(f"no place for {new_path} in the file: it doesn't make any sets itself")
    end, indent = max(spots, key=lambda x: x[0])
    lines = [f'{indent}{p} = {p} or {{}}' for p in parents if not any(mask[m.start()] for m in _path_regex(p).finditer(src))]
    order = [s for s in SLOT_KEYS if s in gear]
    lines.append(indent + new_path + ' = {' + ', '.join(f'{s}={_lua_str(gear[s])}' for s in order) + '}')
    return src[:end] + '\n' + '\n'.join(lines) + src[end:]


def add_set(src, after, new_path, gear):
    """A new set (new_path = {gear}) on the line after the set it was made from (after), with the same indent."""
    mask = _code_positions(src)
    if any(mask[m.start()] for m in _path_regex(new_path).finditer(src)):
        raise EditError(f'{new_path} is in the file already')
    hits = [m for m in _path_regex(after).finditer(src) if mask[m.start()]]
    if not hits:
        raise EditError(f'{after} not found in the file')
    m = hits[-1]
    i = m.end()
    if src.startswith('{', i):
        end = _match(src, i, '{', '}') + 1
    elif src.startswith('set_combine', i):
        end = _match(src, src.index('(', i), '(', ')') + 1
    else:
        nl = src.find('\n', i)
        end = len(src) if nl < 0 else nl
    line_start = src.rfind('\n', 0, m.start()) + 1
    indent = re.match(r'[ \t]*', src[line_start:]).group(0)
    nl = src.find('\n', end)
    end = len(src) if nl < 0 else nl
    order = [s for s in SLOT_KEYS if s in gear]
    body = ', '.join(f'{s}={_lua_str(gear[s])}' for s in order)
    return src[:end] + '\n' + indent + new_path + ' = {' + body + '}' + src[end:]


def _depth(body, pos):
    """Brace depth at pos inside a table text that starts with '{'."""
    d = 0
    j = 0
    while j < pos:
        s = _skip(body, j)
        if s is not None:
            j = s
            continue
        if body[j] == '{':
            d += 1
        elif body[j] == '}':
            d -= 1
        j += 1
    return d


def rename(src, old, new):
    """Every "old" item name (as a quoted name) -> new."""
    rx = re.compile(r'(["\'])' + re.escape(old) + r'\1')
    out, n = rx.subn(lambda m: _lua_str(new), src)
    if n == 0:
        raise EditError(f'"{old}" not found in the file')
    return out


def backup(path):
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    folder = os.path.join(BACKUPS, stamp)
    os.makedirs(folder, exist_ok=True)
    dst = os.path.join(folder, os.path.basename(path))
    shutil.copy2(path, dst)
    return dst


def apply(path, edits):
    """edits: [('rename', old, new) | ('slots', set_path, {slot: name})]. Backup first; if the edited file no longer
    loads (or loads with new problems in how sets are built), nothing is written. Returns (backup path, [messages])."""
    raw = open(path, 'rb').read()
    crlf = bytes([13, 10]) in raw                       # (the file's own line endings are kept)
    src = open(path, encoding='utf-8', errors='replace').read()
    before = gs_loader.load(path)
    new = src
    done, failed = [], []
    for e in edits:
        try:
            if e[0] == 'rename':
                new = rename(new, e[1], e[2])
                done.append(f'{e[1]} -> {e[2]}')
            elif e[0] == 'slots':
                new = set_slots(new, e[1], e[2])
                done.append(f'{e[1]}: ' + ', '.join(f'{k} {item_text(v)}' for k, v in e[2].items()))
            elif e[0] == 'add':
                new = add_set(new, e[1], e[2], e[3])
                done.append(f'new set {e[2]}')
            elif e[0] == 'new':
                new = add_new_set(new, e[1], e[2], e[3])
                done.append(f'new set {e[1]}')
        except EditError as x:
            failed.append(str(x))
    if new == src:
        return None, done, failed
    # check the result before writing it
    tmp = path + '.doctor-check.lua'
    open(tmp, 'w', encoding='utf-8').write(new)
    try:
        after = gs_loader.load(tmp)
    finally:
        os.remove(tmp)
    if after.error and not before.error:
        raise EditError("the changed file wouldn't load (" + after.error + ") - nothing was changed")
    if len(after.broken) > len(before.broken):
        raise EditError('the change would break a set - nothing was changed')
    bk = backup(path)
    open(path, 'w', encoding='utf-8', newline=chr(13) + chr(10) if crlf else chr(10)).write(new)
    return bk, done, failed
