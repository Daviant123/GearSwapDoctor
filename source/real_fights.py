"""
GearSwap Doctor: what really happened in the game, next to what wsdist says should. His request 2026-10-31: wsdist is the base, "however at this point the program should be
evolving past that and use data from kastra and that is collected to improve the program overall".

The feature "Record my real damage" (gsd_features.lua) writes addons\\GearSwap\\data\\gsd_fights_<Name>.csv in game. Each line is a minute or so of one thing:
  time, job, sub, monster, kind (melee / ws), weapon skill, weapon, Aftermath level, TP (to the 500 below), uses, total damage, crits, misses
Nothing here goes anywhere: it stays on his PC, and isn't in what's published.
"""
import csv
import glob
import os

FIELDS = ('time', 'job', 'sub', 'mob', 'kind', 'name', 'weapon', 'am', 'tp', 'n', 'total', 'crits', 'miss')
ENOUGH = 10              # fewer weapon skills than this say little: it's said


def path_of(character, folder):
    return os.path.join(folder, f'gsd_fights_{character}.csv')


def read(character, folder):
    """Every line recorded for a character. A broken line (the game closed mid-write) is left out."""
    out = []
    try:
        f = open(path_of(character, folder), encoding='utf-8', errors='replace', newline='')
    except OSError:
        return out
    with f:
        for row in csv.reader(f):
            if len(row) != len(FIELDS):
                continue
            r = dict(zip(FIELDS, row))
            try:
                for k in ('am', 'tp', 'n', 'total', 'crits', 'miss'):
                    r[k] = int(float(r[k]))
            except ValueError:
                continue
            out.append(r)
    return out


def _sum(rows):
    n = sum(r['n'] for r in rows)
    miss = sum(r['miss'] for r in rows)
    hits = n - miss
    total = sum(r['total'] for r in rows)
    return {'n': n, 'hits': hits, 'miss': miss, 'total': total, 'avg': total / hits if hits else 0, 'hit_rate': hits / n * 100 if n else 0,
            'crit_rate': sum(r['crits'] for r in rows) / hits * 100 if hits else 0}


def mobs(rows):
    """The monsters fought, most first."""
    count = {}
    for r in rows:
        count[r['mob']] = count.get(r['mob'], 0) + r['n']
    return sorted(count, key=lambda m: -count[m])


def ws(rows, name, weapon=None, tp=None, mob=None, job=None):
    """A weapon skill's real numbers, as close to the case asked as there's data for: this monster if it has been fought, this weapon, the TP to the 500. None: never used."""
    pick = [r for r in rows if r['kind'] == 'ws' and r['name'].lower() == name.lower() and (not job or r['job'] == job)]
    if not pick:
        return None
    notes = []
    for test, words in ((lambda r: weapon and r['weapon'].lower() == weapon.lower(), f'with {weapon}'), (lambda r: tp is not None and r['tp'] == tp // 500 * 500, f'at about {tp} TP'),
                        (lambda r: mob and r['mob'].lower() == mob.lower(), f'on {mob}')):
        narrower = [r for r in pick if test(r)]
        if narrower:
            pick = narrower
            notes.append(words)
    return dict(_sum(pick), where=' '.join(notes), mobs=mobs(pick))


def melee(rows, weapon=None, mob=None, job=None):
    """Auto-attacks: hit rate, crit rate, damage a hit."""
    pick = [r for r in rows if r['kind'] == 'melee' and (not job or r['job'] == job)]
    if weapon:
        pick = [r for r in pick if r['weapon'].lower() == weapon.lower()] or pick
    if mob:
        pick = [r for r in pick if r['mob'].lower() == mob.lower()] or pick
    return _sum(pick) if pick else None


def compare(real, simulated, enemy):
    """A line: real average against wsdist's for this set. The two aren't the same set unless he wore it, and it says so."""
    if not real or not real['hits']:
        return ''
    line = f"Your real fights {real['where']}: {real['hits']} hits, average {real['avg']:,.0f}".replace('fights :', 'fights:')
    if real['miss']:
        line += f", {real['miss']} missed"
    if simulated:
        diff = (real['avg'] - simulated) / simulated * 100
        word = 'higher' if diff >= 0 else 'lower'
        line += f". wsdist says {simulated:,.0f} for this set on {enemy}: real is {abs(diff):.0f} % {word}"
    if real['hits'] < ENOUGH:
        line += f" (only {real['hits']}: too few to trust yet)"
    return line + '.'


def melee_line(real):
    if not real or not real['n']:
        return ''
    return f"Your real auto-attacks: {real['hit_rate']:.1f} % hit, {real['crit_rate']:.1f} % crits, {real['avg']:,.0f} a hit ({real['n']:,} swings)."


def summary(character, folder, job=None):
    """For the job pages: what has been recorded."""
    rows = [r for r in read(character, folder) if not job or r['job'] == job]
    if not rows:
        return ''
    m = mobs(rows)
    names = {r['name'] for r in rows if r['kind'] == 'ws'}
    uses = sum(r['n'] for r in rows if r['kind'] == 'ws')
    return f"Real fights recorded: {uses:,} weapon skills ({len(names)} kinds) on {len(m)} monsters, most on {m[0]}."


def files(folder):
    return glob.glob(os.path.join(folder, 'gsd_fights_*.csv'))
