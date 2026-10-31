"""
GearSwap Doctor: reads a GearSwap file the way GearSwap does, without the game.

The file is run inside a stand-in GearSwap (Lua, through lupa): GearSwap / Mote / Selindrile helpers are replaced by
harmless stand-ins, then get_sets / user_setup / init_gear_sets are called. What comes out is every set with its
gear, plus problems found on the way:
  - the file doesn't load (a Lua error, with the line)
  - a set is used (set_combine, or copied) but never made - e.g. sets.Enmity.DT
Nothing is sent to the game and nothing in the file is changed here.
"""
import os
import lupa

SLOTS = {
    'main': 'main', 'sub': 'sub', 'range': 'range', 'ranged': 'range', 'ammo': 'ammo', 'head': 'head', 'neck': 'neck',
    'ear1': 'ear1', 'left_ear': 'ear1', 'lear': 'ear1', 'ear2': 'ear2', 'right_ear': 'ear2', 'rear': 'ear2',
    'body': 'body', 'hands': 'hands', 'ring1': 'ring1', 'left_ring': 'ring1', 'lring': 'ring1', 'ring2': 'ring2',
    'right_ring': 'ring2', 'rring': 'ring2', 'back': 'back', 'waist': 'waist', 'legs': 'legs', 'feet': 'feet',
}

PRELUDE = r'''
local GHOSTS = {}          -- sets made up on the spot because something used them before (or without) making them
local ANY
local anymt = {}
anymt.__index = function(t, k) return ANY end
anymt.__newindex = function(t, k, v) end
anymt.__call = function(...) return ANY end
anymt.__concat = function(a, b) return '' end
anymt.__add = function() return 0 end anymt.__sub = anymt.__add anymt.__mul = anymt.__add anymt.__div = anymt.__add
anymt.__unm = function() return 0 end anymt.__len = function() return 0 end
anymt.__lt = function() return false end anymt.__le = anymt.__lt
anymt.__tostring = function() return '' end
ANY = setmetatable({}, anymt)

-- sets: a missing set is made on demand (GearSwap's own tables are like that for sets.precast.JA etc.), but it is
-- remembered; one that is still empty at the end and was read as a set is a broken reference
local setmt
local SLOTKEY = { main=1, sub=1, range=1, ranged=1, ammo=1, head=1, neck=1, ear1=1, ear2=1, left_ear=1, right_ear=1, lear=1,
  rear=1, body=1, hands=1, ring1=1, ring2=1, left_ring=1, right_ring=1, lring=1, rring=1, back=1, waist=1, legs=1, feet=1 }
local function keypath(base, k)
  return base .. ((type(k) == 'string' and k:match('^[%a_][%w_]*$')) and ('.' .. k) or ('[' .. string.format('%q', tostring(k)) .. ']'))
end
local function newset(path) return setmetatable({}, { __index = setmt.__index, __newindex = setmt.__newindex, __path = path }) end
setmt = {}
-- a table put into a set (sets.precast.WS = {...}) gets the same tracking, unless it's an item ({name=...})
setmt.__newindex = function(t, k, v)
  rawset(t, k, v)
  if type(v) == 'table' and getmetatable(v) == nil and rawget(v, 'name') == nil and not (type(k) == 'string' and SLOTKEY[k:lower()]) then
    local mt = getmetatable(t)
    setmetatable(v, { __index = setmt.__index, __newindex = setmt.__newindex, __path = keypath(mt and mt.__path or 'sets', k) })
  end
end
setmt.__index = function(t, k)
  if type(k) ~= 'string' and type(k) ~= 'number' then return nil end
  local mt = getmetatable(t)
  local path = keypath(mt and mt.__path or 'sets', k)
  local s = newset(path)
  rawset(t, k, s)
  local info = debug.getinfo(2, 'l')
  GHOSTS[#GHOSTS + 1] = { t = s, path = path, line = info and info.currentline or 0 }
  return s
end

local env
local function copy(t, out)
  out = out or {}
  if type(t) ~= 'table' then return out end
  for k, v in pairs(t) do if type(v) ~= 'table' or (rawget(v, 'name') ~= nil) then out[k] = v end end
  return out
end
local USED = {}            -- sets read as a set (set_combine arguments)
-- GearSwap's set_combine treats slot aliases as one slot (unify_slots): a later set's ear2 replaces an earlier
-- right_ear
local ALIAS = { left_ear = 'ear1', lear = 'ear1', right_ear = 'ear2', rear = 'ear2', left_ring = 'ring1', lring = 'ring1',
  right_ring = 'ring2', rring = 'ring2', ranged = 'range' }
local NILS = {}             -- set_combine given a set that doesn't exist: {line}
local function set_combine(...)
  local out = {}
  for i = 1, select('#', ...) do
    local s = select(i, ...)
    if s == nil then
      local info = debug.getinfo(2, 'l')
      NILS[#NILS + 1] = info and info.currentline or 0
    end
    if type(s) == 'table' then
      USED[s] = true
      local c = copy(s)
      local u = {}
      for k, v in pairs(c) do u[(type(k) == 'string' and ALIAS[k:lower()]) or k] = v end
      for k, v in pairs(u) do out[k] = v end
    end
  end
  return out
end

local function sandbox()
  local e = {}
  for _, k in ipairs({ 'string', 'table', 'math', 'pairs', 'ipairs', 'type', 'tostring', 'tonumber', 'select', 'next',
                       'pcall', 'error', 'assert', 'unpack', 'rawget', 'rawset', 'setmetatable', 'getmetatable', 'os' }) do
    e[k] = _G[k]
  end
  e.unpack = e.unpack or table.unpack
  e.sets = setmetatable({}, { __index = setmt.__index, __newindex = setmt.__newindex, __path = 'sets' })
  -- gear.xxx is made by Mote-Globals / a player's globals (gear.default.obi_waist, gear.DarkRing.name = ...): a stand-in for those
  e.gear = setmetatable({}, { __index = function(t, k) local v = {} rawset(t, k, v) return v end })
  e.set_combine = set_combine
  -- Windower's sets (S{...}): membership plus the methods job files call on them
  local setmethods = { contains = function(self, v) return rawget(self, v) == true end,
                       add = function(self, v) rawset(self, v, true) return self end,
                       remove = function(self, v) rawset(self, v, nil) return self end }
  e.S = function(t) local s = {} for _, v in ipairs(t or {}) do s[v] = true end
    return setmetatable(s, { __index = function(_, k) return setmethods[k] or false end }) end
  e.T = function(t) return t or {} end
  e.L = e.T
  e.M = function(...) return ANY end
  e.include = function() return true end
  e.require = function() return ANY end
  e.windower = ANY
  e.player = setmetatable({ main_job = 'BLU', sub_job = 'WAR', name = 'Player', main_job_level = 99, status = 'Idle' }, anymt)
  e.state = ANY
  e.world = ANY
  e.buffactive = ANY
  e.info = ANY
  e.send_command = function() end
  e.add_to_chat = function() end
  e.windower = ANY
  setmetatable(e, { __index = function(t, k) return ANY end })
  e._G = e
  return e
end

local function chunk(src, name)
  local fn, err
  if setfenv then
    fn, err = loadstring(src, '=' .. name)
    if fn then setfenv(fn, env) end
  else
    fn, err = load(src, '=' .. name, 't', env)
  end
  return fn, err
end

-- before: the files GearSwap loads ahead of the job's sets (Sel-Include: user-globals, <Name>-globals, <Name>-items)
function GS_LOAD(src, name, before)
  GHOSTS, USED, NILS = {}, {}, {}
  env = sandbox()
  local errs = {}
  for i = 1, #(before or {}) do
    local f = chunk(before[i][1], before[i][2])
    if f then local ok, e = pcall(f) if not ok then errs[#errs + 1] = tostring(e) end end
  end
  local fn, err = chunk(src, name)
  if not fn then return nil, err end
  local ok, e = pcall(fn)
  if not ok then return nil, e end
  for _, f in ipairs({ 'get_sets', 'user_setup', 'job_setup', 'init_gear_sets', 'user_job_setup' }) do
    local g = rawget(env, f)
    if type(g) == 'function' then
      local ok2, e2 = pcall(g)
      if not ok2 then errs[#errs + 1] = f .. ': ' .. tostring(e2) end
    end
  end
  return env, errs
end

-- the walk: every set (a table that holds gear or subsets) with its gear
function GS_WALK(env, slots)
  local out = {}
  local seen = {}
  local function walk(t, path)
    if seen[t] then return end
    seen[t] = true
    local gear = {}
    for k, v in pairs(t) do
      if type(k) == 'string' and slots[k:lower()] and (type(v) == 'string' or (type(v) == 'table' and type(rawget(v, 'name')) == 'string')) then
        if type(v) == 'string' then gear[k] = { name = v }
        else
          local augs = {}
          if type(rawget(v, 'augments')) == 'table' then for _, a in ipairs(v.augments) do augs[#augs + 1] = tostring(a) end end
          gear[k] = { name = v.name, augments = augs, bag = type(rawget(v, 'bag')) == 'string' and v.bag or nil }
        end
      end
    end
    if next(gear) then out[#out + 1] = { path = path, gear = gear } end
    for k, v in pairs(t) do
      if type(v) == 'table' and not (type(k) == 'string' and slots[k:lower()]) and rawget(v, 'name') == nil then
        local kp = (type(k) == 'string' and k:match('^[%a_][%w_]*$')) and (path .. '.' .. k) or (path .. '[' .. string.format('%q', tostring(k)) .. ']')
        walk(v, kp)
      end
    end
  end
  walk(rawget(env, 'sets'), 'sets')
  -- the file's own lists of names (gsList = S{'Ragnarok', ...}, or a plain list): what the job file says about its weapons
  LISTS = {}
  for name, v in pairs(env) do
    if type(name) == 'string' and type(v) == 'table' and name ~= '_G' then
      local names, ok = {}, true
      for k, x in next, v do
        if type(k) == 'string' and x == true then names[#names + 1] = k
        elseif type(k) == 'number' and type(x) == 'string' then names[#names + 1] = x
        else ok = false break end
      end
      if ok and #names > 0 then LISTS[name] = names end
    end
  end
  -- broken references: made on demand, never filled, and used as a set
  local broken = {}
  for _, g in ipairs(GHOSTS) do
    if next(g.t) == nil and USED[g.t] then broken[#broken + 1] = { path = g.path, line = g.line } end
  end
  for _, line in ipairs(NILS) do broken[#broken + 1] = { path = 'a set that does not exist (set_combine)', line = line } end
  return out, broken
end
'''


class Loaded:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.sets = []          # [{'path': 'sets.precast.WS["Savage Blade"]', 'gear': {slot_key: {'name', 'augments', 'bag'}}}]
        self.broken = []        # [{'path', 'line'}]
        self.error = None       # the file didn't load: Lua's message
        self.warnings = []      # a setup function failed (the sets made before it are still read)
        self.lists = {}         # the file's own lists of names: {'gsList': ['Ragnarok', ...]}


_lua = None


def _runtime():
    global _lua
    if _lua is None:
        _lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        _lua.execute(PRELUDE)
    return _lua


def companions(path):
    """The files GearSwap loads before a character's job sets (Sel-Include order): user-globals, <Name>-Globals,
    <Name>-Items - from the file name's leading character name (Name_Pld_Gear.lua -> Name)."""
    folder, base = os.path.split(os.path.abspath(path))
    who = base.split('_')[0].split('-')[0]
    out = []
    names = {n.lower(): n for n in os.listdir(folder)}
    for want in ('user-globals.lua', who.lower() + '-globals.lua', who.lower() + '-items.lua'):
        if want in names and names[want].lower() != base.lower():
            out.append(os.path.join(folder, names[want]))
    return out


def load(path):
    """Read one GearSwap file: its sets and what's wrong with how they're built."""
    L = _runtime()
    res = Loaded(path)
    try:
        src = open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        res.error = str(e)
        return res
    before = []
    for c in companions(path):
        before.append(L.table_from([open(c, encoding='utf-8', errors='replace').read(), os.path.basename(c)]))
    env, errs = L.globals().GS_LOAD(src, os.path.basename(path), L.table_from(before))
    if env is None:
        res.error = str(errs)
        return res
    if errs:
        res.warnings = [str(errs[i]) for i in range(1, len(errs) + 1)]
    slots = L.table_from({k: True for k in SLOTS})
    sets, broken = L.globals().GS_WALK(env, slots)
    for i in range(1, len(sets) + 1):
        s = sets[i]
        gear = {}
        for k, v in s.gear.items():
            augs = [str(v.augments[j]) for j in range(1, len(v.augments) + 1)] if v.augments else []
            gear[str(k)] = {'name': str(v.name), 'augments': augs, 'bag': str(v.bag) if v.bag else None}
        res.sets.append({'path': str(s.path), 'gear': gear})
    for i in range(1, len(broken) + 1):
        res.broken.append({'path': str(broken[i].path), 'line': int(broken[i].line)})
    lists = L.globals().LISTS
    for name in list(lists):
        names = lists[name]
        res.lists[str(name)] = sorted(str(names[j]) for j in range(1, len(names) + 1))
    res.sets.sort(key=lambda s: s['path'])
    return res


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        r = load(p)
        print(r.name, 'ERROR' if r.error else '', r.error or '', len(r.sets), 'sets', len(r.broken), 'broken', r.warnings[:2])
        for b in r.broken[:10]:
            print('   broken:', b)
