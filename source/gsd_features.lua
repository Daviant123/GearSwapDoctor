--[[ GearSwap Doctor features (gsd-features.lua) - written by GearSwap Doctor, version 11.

  GearSwap Doctor copies this file to Windower\addons\GearSwap\data. Your choices are not in here: they're in your
  job file, in the "GearSwap Doctor features" block at the end of it (gsd_features = {...}). Change them in
  GearSwap Doctor (Features tab), or by hand there. This file is shared by every job file that uses it and is
  rewritten when GearSwap Doctor updates it, so don't change it.

  How it fits in: it runs after your own file is set up (your get_sets, and Mote's / Selindrile's include if you use
  one), then adds to GearSwap's events - your own precast / midcast / aftercast / status_change / buff_change /
  self_command run first, exactly as before, and the features add their gear on top. Normal game commands only.

  In game: //gs c gsd help
]]

local cfg = gsd_features or {}
local G = { version = 11, cfg = cfg, orig = {}, tagged = {}, ntagged = 0, moving = false, still = 0, last = nil,
            low_hp = false, low_mp = false, locked = {}, skip = {}, binds = {}, pending = false, t = 0,
            dt = false, rr = false, wlock = false, th_mode = 'Off', th_on = false, ammo_warned = nil }
gsd = G

local function on(k) return type(cfg[k]) == 'table' and cfg[k].on == true end
local function low(s) return type(s) == 'string' and s:lower() or '' end
local function say(msg) add_to_chat(60, 'GearSwap Doctor: ' .. msg) end
local function name_of(v) if type(v) == 'table' then return v.name end return v end
local function has_gear(t) return type(t) == 'table' and next(t) ~= nil end
local function buff(n) return buffactive and buffactive[n] end

-- 'sets.engaged.DT' / 'sets.defense["PDT"]' -> that set (looked up when it's needed: Mote makes sets late)
function G.resolve(path)
    if type(path) ~= 'string' or path:sub(1, 4) ~= 'sets' then return nil end
    local t, rest = sets, path:sub(5)
    while rest ~= '' and type(t) == 'table' do
        local k, r = rest:match('^%.([%a_][%w_]*)(.*)$')
        if not k then k, r = rest:match('^%["(.-)"%](.*)$') end
        if not k then k, r = rest:match("^%['(.-)'%](.*)$") end
        if not k then
            local n
            n, r = rest:match('^%[(%d+)%](.*)$')
            k = tonumber(n)
        end
        if k == nil then return nil end
        t, rest = rawget(t, k) or t[k], r
    end
    return type(t) == 'table' and t or nil
end

-- a feature's gear: its own picks ({neck=..., waist=...}) or a set of the file ('sets.TreasureHunter')
local function gear_of(f)
    if type(f) ~= 'table' then return nil end
    if type(f.set) == 'string' and f.set ~= '' then
        local s = G.resolve(f.set)
        if s then return s end
    end
    if has_gear(f.gear) then return f.gear end
    return nil
end
local function put(f) local g = gear_of(f) if g then equip(g) return true end return false end

local MAGIC_WS = {}
for _, n in ipairs({ 'Leaden Salute', 'Wildfire', 'Hot Shot', 'Aeolian Edge', 'Cyclone', 'Gust Slash', 'Sanguine Blade',
    'Red Lotus Blade', 'Burning Blade', 'Seraph Blade', 'Shining Blade', 'Frostbite', 'Freezebite', 'Herculean Slash',
    'Thunder Thrust', 'Raiden Thrust', 'Blade: Ei', 'Blade: Yu', 'Blade: Teki', 'Blade: To', 'Blade: Chi', 'Tachi: Jinpu',
    'Tachi: Koki', 'Tachi: Goten', 'Tachi: Kagero', 'Dark Harvest', 'Shadow of Death', 'Infernal Scythe', 'Energy Steal',
    'Energy Drain', 'Shining Strike', 'Seraph Strike', 'Flash Nova', 'Rock Crusher', 'Earth Crusher', 'Starburst',
    'Sunburst', 'Cataclysm', 'Vidohunir', 'Garland of Bliss', 'Omniscience', 'Primal Rend', 'Cloudsplitter', 'Trueflight',
    'Flaming Arrow', 'Burning Blade', 'Spirits Within' }) do MAGIC_WS[n] = true end
local NIN_NUKE = { Katon = true, Suiton = true, Raiton = true, Doton = true, Huton = true, Hyoton = true }
local BLU_MAGIC = {}
for _, n in ipairs({ 'Anvil Lightning', 'Spectral Floe', 'Searing Tempest', 'Blinding Fulgor', 'Scouring Spate',
    'Silent Storm', 'Entomb', 'Tenebral Crush', 'Subduction', 'Magic Hammer', 'Rending Deluge', 'Charged Whisker',
    'Thermal Pulse', 'Gates of Hades', 'Leafstorm', 'Firespit', 'Molting Plumage', 'Uproot', 'Tem. Upheaval',
    'Polar Roar', 'Water Bomb', 'Regurgitation', 'Eyes On Me', 'Magic Fruit', 'Wild Carrot', 'White Wind',
    'Healing Breeze', 'Plenilune Embrace', 'Restoral', 'Evryone. Grudge', 'Acrid Stream', 'Dark Orb', 'Ice Break',
    'Death Ray', 'Blazing Bound', 'Droning Whirlwind', 'Crashing Thunder', 'Nectarous Deluge', 'Atra. Libations' }) do
    BLU_MAGIC[n] = true
end

-- does this action get the day / weather bonus (so the Obi / Orpheus's Sash helps)?
local function elemental(spell)
    local el = spell.element
    if type(el) ~= 'string' or el == 'None' or el == '' then return nil end
    if spell.type == 'WeaponSkill' then return MAGIC_WS[spell.english] and el or nil end
    local sk = spell.skill
    if sk == 'Elemental Magic' or sk == 'Healing Magic' or sk == 'Divine Magic' then return el end
    if sk == 'Dark Magic' then return (spell.english:find('^Drain') or spell.english:find('^Aspir')) and el or nil end
    if sk == 'Ninjutsu' then return NIN_NUKE[(spell.english:match('^(%a+):') or '')] and el or nil end
    if sk == 'Blue Magic' then return BLU_MAGIC[spell.english] and el or nil end
    return nil
end

function G.obi(spell)
    if not on('obi') then return end
    local el = elemental(spell)
    if not el then return end
    local c = cfg.obi
    local b = 0
    if world and world.weather_element == el then b = ((world.weather_intensity or 1) >= 2) and 25 or 10 end
    if world and world.day_element == el then b = b + 10 end
    local o = 0
    local d = spell.target and spell.target.distance
    if c.orpheus and c.orpheus ~= '' and type(d) == 'number' and spell.target.type == 'MONSTER' then
        o = math.max(1, math.min(15, 16 - d))
    end
    if c.obi and c.obi ~= '' and b >= (c.min or 10) and b >= o then
        equip({ waist = c.obi })
    elseif c.orpheus and c.orpheus ~= '' and o >= (c.orpheus_min or 8) then
        equip({ waist = c.orpheus })
    end
end

-- Moonshade Earring gives +250 TP: at high TP it does nothing, so wear the other earring
function G.moonshade(spell)
    if not on('moonshade') or spell.type ~= 'WeaponSkill' then return end
    local c = cfg.moonshade
    if not c.instead or c.instead == '' or (player.tp or 0) < (c.tp or 2750) then return end
    local el = gearswap and gearswap.equip_list or {}
    local l, r = name_of(el.left_ear), name_of(el.right_ear)
    if low(l) == 'moonshade earring' and low(r) ~= low(c.instead) then equip({ left_ear = c.instead })
    elseif low(r) == 'moonshade earring' and low(l) ~= low(c.instead) then equip({ right_ear = c.instead }) end
end

-- Treasure Hunter: tag each new monster once (or always while engaged)
local function me_id()
    local p = windower.ffxi.get_player()
    return p and p.id
end
local function untagged(target)
    if type(target) ~= 'table' or not target.id then return false end
    if target.type and target.type ~= 'MONSTER' then return false end
    if target.spawn_type and target.spawn_type ~= 16 then return false end
    return not G.tagged[target.id]
end
function G.th_tag(spell, casting)
    if not on('th') then return end
    if G.th_mode == 'Off' then return end
    local t = spell.target
    if not t or t.type ~= 'MONSTER' then return end
    if spell.type == 'WeaponSkill' and not cfg.th.tag_ws then return end
    if G.th_mode == 'Always' or untagged(t) then
        if put(cfg.th) then G.th_on = true end
    end
end

-- Aftermath: gear for the level that's up (his request 2026-10-30). Your picks for that level first, then the sets named for it:
-- sets.engaged.<weapon>.AM3, sets.engaged.<weapon>.AM, sets.engaged.AM3, sets.engaged.AM (or sets.TP..., as some files name them)
function G.am_level()
    for lv = 3, 1, -1 do
        if buff('aftermath: lv.' .. lv) then return lv end
    end
    if buff('aftermath') then return 0 end                 -- (a Relic's has no level)
    return nil
end
local function am_named(lv)
    local main = player.equipment and name_of(player.equipment.main)
    local bases = {}
    for _, root in ipairs({ rawget(sets, 'engaged') or false, rawget(sets, 'TP') or false }) do
        if type(root) == 'table' then
            if type(main) == 'string' then
                bases[#bases + 1] = rawget(root, main)
                bases[#bases + 1] = rawget(root, (main:gsub('[^%w]', '')))
            end
            bases[#bases + 1] = root
        end
    end
    local keys = lv == 0 and { 'AM', 'AM1' } or { 'AM' .. lv, 'AM' }
    for _, b in ipairs(bases) do
        for _, k in ipairs(keys) do
            local t = type(b) == 'table' and rawget(b, k)
            if type(t) == 'table' then return t end
        end
    end
    return nil
end
function G.am_put()
    if not on('aftermath') then return end
    local lv = G.am_level()
    if not lv then return end
    local c = cfg.aftermath
    local key = lv == 0 and 'relic' or tostring(lv)
    local g = G.resolve(c['set' .. key])
    if not g and has_gear(c['gear' .. key]) then g = c['gear' .. key] end
    if not g and c.auto ~= false then g = am_named(lv) end
    if g then equip(g) end
end

-- gear worn on top of whatever your file put on (after aftercast / status / buff / commands)
function G.overlay(casting)
    local st = player and player.status
    if not casting then
        G.th_on = false
        if st == 'Engaged' then G.am_put() end
        if on('th') and st == 'Engaged' and G.th_mode ~= 'Off' then
            local t = windower.ffxi.get_mob_by_target('t')
            if G.th_mode == 'Always' or (t and t.spawn_type == 16 and not G.tagged[t.id]) then
                if put(cfg.th) then G.th_on = true end
            end
        end
        if on('kiting') and G.moving and (st == 'Idle' or (cfg.kiting.engaged and st == 'Engaged')) then put(cfg.kiting) end
        if on('refresh') and st == 'Idle' and G.low_mp then put(cfg.refresh) end
        if on('dt') and G.dt then put(cfg.dt) end
        if on('lowhp') and G.low_hp and (st == 'Engaged' or not cfg.lowhp.engaged_only) then put(cfg.lowhp) end
        if on('reraise') and G.rr and not buff('reraise') then put(cfg.reraise) end
        if on('sleep') and buff('sleep') then put(cfg.sleep) end
        if on('react') and G.react then equip(G.react.gear) end
    end
    if on('doom') and (buff('doom') or (cfg.doom.curse and buff('curse'))) and (not casting or cfg.doom.casting ~= false) then
        put(cfg.doom)
    end
    G.locks()
end

-- rings (and the like) that must stay on until they're used: Warp Ring, Dim. Rings, experience / capacity rings
local RING_SLOTS = { ring1 = 'left_ring', ring2 = 'right_ring', back = 'back' }
local function lock_list()
    local out = {}
    for _, n in ipairs((cfg.rings and cfg.rings.lock) or {}) do out[low(n)] = true end
    return out
end
function G.locks()
    if not on('rings') or not player or not player.equipment then return end
    local list = lock_list()
    for slot, long in pairs(RING_SLOTS) do
        local worn = low(name_of(player.equipment[long]) or name_of(player.equipment[slot]))
        if G.skip[slot] and G.skip[slot] ~= worn then G.skip[slot] = nil end
        if list[worn] and not G.locked[slot] and G.skip[slot] ~= worn then
            disable(slot)
            G.locked[slot] = worn
            if gearswap and gearswap.equip_list then gearswap.equip_list[long] = nil end
        elseif G.locked[slot] and not list[worn] and G.locked[slot] ~= 'pending' then
            G.locked[slot] = nil
            enable(slot)
        end
    end
end
function G.unlock(why)
    local any = false
    for slot, worn in pairs(G.locked) do
        G.skip[slot] = (worn ~= 'pending') and worn or nil
        G.locked[slot] = nil
        any = true
        send_command('gs enable ' .. slot)
    end
    if any then
        if why then say('ring slot unlocked (' .. why .. ')') end
        send_command('wait 0.5; gs c gsd refresh')
    end
end
function G.use_ring(which)
    local c = cfg.rings or {}
    local r = c[which]
    if not on('rings') or type(r) ~= 'string' or r == '' then
        say('no ' .. which .. ' ring picked (GearSwap Doctor > Features > Rings)')
        return
    end
    local slot = c.slot or 'ring2'
    enable(slot)
    equip({ [slot] = r })
    G.locked[slot] = 'pending'
    G.skip[slot] = nil
    local wait = c.wait or 11
    say(r .. ': putting it on, using it in ' .. wait .. ' s')
    send_command('wait 1.5; gs disable ' .. slot .. '; wait ' .. wait .. '; input /item "' .. r .. '" <me>')
end

-- your gear as your file would put it on now (then the features go on top)
function G.refresh()
    if type(handle_equipping_gear) == 'function' then
        handle_equipping_gear(player.status)
    elseif type(G.orig.status_change) == 'function' then
        G.orig.status_change(player.status, player.status)
    else
        local s = (player.status == 'Engaged' and rawget(sets, 'engaged')) or rawget(sets, 'idle')
        if type(s) == 'table' then equip(s) end
    end
end

-- the little window with the modes
function G.box_update()
    if not on('box') then return end
    if not G.box and type(texts) == 'table' and texts.new then
        G.box = texts.new('', { pos = { x = cfg.box.x or 400, y = cfg.box.y or 300 }, text = { size = cfg.box.size or 10 },
                               bg = { alpha = 170 }, flags = { draggable = true } })
    end
    if not G.box then return end
    local parts = {}
    if on('dt') then parts[#parts + 1] = 'DT: ' .. (G.dt and 'ON' or 'off') end
    if on('th') then parts[#parts + 1] = 'TH: ' .. G.th_mode end
    if on('weapons') then parts[#parts + 1] = 'Weapons: ' .. (G.wlock and 'LOCKED' or 'free') end
    if on('reraise') then parts[#parts + 1] = 'Reraise gear: ' .. (G.rr and 'ON' or 'off') end
    if on('kiting') and G.moving then parts[#parts + 1] = 'moving' end
    if on('lowhp') and G.low_hp then parts[#parts + 1] = 'LOW HP' end
    if on('haste') and G.haste_short then parts[#parts + 1] = G.haste_short end
    if on('acc') and G.acc_short then parts[#parts + 1] = G.acc_short end
    if on('warn') and G.warn_short and G.warn_short ~= '' then parts[#parts + 1] = G.warn_short end
    if G.box.text then G.box:text('GSD  ' .. table.concat(parts, '  |  ')) end
    if G.box.show and not G.hidden then G.box:show() end
end

local function weapons_lock(v)
    local slots = (cfg.weapons and cfg.weapons.slots) or { 'main', 'sub', 'range' }
    G.wlock = v
    if v then disable(unpack(slots)) else enable(unpack(slots)) end
end

local HELP = {
    'dt - damage taken set on / off', 'th - Treasure Hunter: Off / Tag / Always', 'weapons - lock / free your weapons',
    'reraise - reraise gear on / off', 'warp / dim / xp / cp - put on that ring, lock it, use it',
    'unlock - free the ring slots', 'box - show / hide the window', 'refresh - put your gear back on',
    'haste - how much haste you have and what is still missing',
    'acc - your accuracy and Double Attack now, and what they come from',
    'warn - your real hit rate on this monster and the damage taken you are wearing',
    'sneak / invis / deo / si - that spell on yourself with Accession (si = Sneak then Invisible)', 'macro - put your macro book and page on again',
}
function G.command(w)
    local c = low(w[2])
    local v = low(w[3])
    local function toggle(cur) if v == 'on' then return true elseif v == 'off' then return false end return not cur end
    if c == 'dt' and on('dt') then
        G.dt = toggle(G.dt)
        say('DT ' .. (G.dt and 'ON' or 'off'))
        G.refresh()
    elseif c == 'th' and on('th') then
        local order = { off = 'Off', tag = 'Tag', always = 'Always' }
        if order[v] then G.th_mode = order[v]
        else G.th_mode = (G.th_mode == 'Off' and 'Tag') or (G.th_mode == 'Tag' and 'Always') or 'Off' end
        say('Treasure Hunter: ' .. G.th_mode)
        G.refresh()
    elseif c == 'weapons' and on('weapons') then
        weapons_lock(toggle(G.wlock))
        say('weapons ' .. (G.wlock and 'LOCKED' or 'free'))
    elseif c == 'reraise' and on('reraise') then
        G.rr = toggle(G.rr)
        say('reraise gear ' .. (G.rr and 'ON' or 'off'))
        G.refresh()
    elseif c == 'warp' or c == 'dim' or c == 'xp' or c == 'cp' then
        G.use_ring(c)
    elseif c == 'unlock' then
        G.unlock('by hand')
    elseif c == 'box' then
        G.hidden = not G.hidden
        if G.box then if G.hidden then G.box:hide() else G.box:show() end end
    elseif c == 'refresh' then
        G.refresh()
    elseif c == 'haste' then
        local h = G.haste_now()
        if h then say(G.haste_words(h)) else say('haste: nothing to read yet') end
    elseif c == 'macro' then
        if on('macro') then G.macro_set() say(('macro book %d, page %d'):format(G.macro_now.book, G.macro_now.page)) else say('the macro book feature is off') end
    elseif c == 'sneak' or c == 'invis' or c == 'invisible' or c == 'deo' or c == 'deodorize' or c == 'si' then
        if not on('accession') then say('the Accession feature is off')
        else
            local list = (c == 'si' and { 'sneak', 'invisible' }) or { (c == 'invis' and 'invisible') or (c == 'deo' and 'deodorize') or c }
            G.acc_cast(list)
        end
    elseif c == 'warn' then
        local rate, n, mob = G.hit_now()
        local ok, pd, md = pcall(G.dt_now)
        say((rate and ('you hit %s %.0f %% of the time (last %d swings)'):format(mob, rate, n) or 'hit rate: fewer than 20 swings so far')
            .. (ok and pd and ('; damage taken from the gear you wear: %d %% physical, %d %% magic'):format(pd, md) or ''))
    elseif c == 'acc' then
        local ok, a = pcall(G.acc_now)
        if ok and a then say(G.acc_words(a)) else say('accuracy: nothing to read yet') end
    else
        say('commands (//gs c gsd ...):')
        for _, h in ipairs(HELP) do add_to_chat(60, '   ' .. h) end
    end
    G.box_update()
end

-- healing: the next lower cure when this one can't go off (his request 2026-10-30, "features for healing")
local LOWER = {}
for _, t in ipairs({ { 'Cure VI', 'Cure V', 'Cure IV', 'Cure III', 'Cure II', 'Cure' }, { 'Curaga V', 'Curaga IV', 'Curaga III', 'Curaga II', 'Curaga' },
                     { 'Curing Waltz V', 'Curing Waltz IV', 'Curing Waltz III', 'Curing Waltz II', 'Curing Waltz' },
                     { 'Divine Waltz II', 'Divine Waltz' } }) do
    for i = 1, #t - 1 do LOWER[t[i]] = t[i + 1] end
end
local function heal_kind(spell)
    local n = spell.english or ''
    if n:find('^Curaga') then return 'curaga' end
    if n:find('^Cure') then return 'cure' end
    if n == 'Cursna' then return 'cursna' end
    if n:find('^Regen') then return 'regen' end
    if n:find('Waltz') and n ~= 'Healing Waltz' then return 'waltz' end
    return nil
end
function G.cure_down(spell)
    if not on('cure_down') then return false end
    local lower = LOWER[spell.english]
    if not lower then return false end
    local c = cfg.cure_down
    local waltz = heal_kind(spell) == 'waltz'
    local why
    local rec = spell.recast_id
    if rec then
        local list = waltz and windower.ffxi.get_ability_recasts() or windower.ffxi.get_spell_recasts()
        if type(list) == 'table' and (tonumber(list[rec]) or 0) > 0 then why = 'not ready' end
    end
    if waltz then
        if type(spell.tp_cost) == 'number' and (player.tp or 0) < spell.tp_cost then why = 'not enough TP' end
    elseif type(spell.mp_cost) == 'number' and (player.mp or 0) < spell.mp_cost then
        why = 'not enough MP'
    end
    if not why then return false end
    cancel_spell()
    local t = spell.target or {}
    local where = (type(t.raw) == 'string' and t.raw:find('^<') and t.raw) or (t.type == 'SELF' and '<me>') or t.name or '<t>'
    send_command('input ' .. (waltz and '/ja' or '/ma') .. ' "' .. lower .. '" ' .. where)
    if c.say ~= false then say(spell.english .. ' ' .. why .. ': ' .. lower .. ' instead') end
    return true
end
-- a healing set the file has but no rule for (a plain file): which set goes on for what
local HEAL_SET = { cure = 'cure', curaga = 'curaga', cursna = 'cursna', regen = 'regen' }
function G.heal_pre(spell)
    if not on('healsets') then return end
    local k = heal_kind(spell)
    if not k then return end
    if k == 'waltz' then
        local s = G.resolve(cfg.healsets.waltz)
        if s then equip(s) end
    elseif k == 'cure' or k == 'curaga' then
        local s = G.resolve(cfg.healsets.precast)
        if s then equip(s) end
    end
end
function G.heal_mid(spell)
    if not on('healsets') then return end
    local k = HEAL_SET[heal_kind(spell) or '']
    local s = k and G.resolve(cfg.healsets[k])
    if not s and k == 'curaga' then s = G.resolve(cfg.healsets.cure) end
    if s then equip(s) end
end
-- swapping the main weapon loses your TP: above this much TP, your weapons stay on for cures
function G.keep_tp(spell)
    if not on('keep_tp') or not heal_kind(spell) or heal_kind(spell) == 'waltz' then return end
    if (player.tp or 0) < (cfg.keep_tp.tp or 100) then return end
    local el = gearswap and gearswap.equip_list
    if el then el.main, el.sub, el.range = nil, nil, nil end
end
function G.solace(spell)
    if not on('solace') or player.main_job ~= 'WHM' or heal_kind(spell) ~= 'cure' or buff('afflatus solace') then return end
    local now = os.time and os.time() or 0
    if now - (G.solace_said or 0) < (cfg.solace.every or 60) then return end
    G.solace_said = now
    add_to_chat(28, 'GearSwap Doctor: Afflatus Solace is not on')
end

-- ------------------------------------------------------------------ Macro book (his request 2026-11-15: "a feature that lets me select a macro book for
-- the gearswap"): the book and page go on when the file loads and when the sub job changes; a sub job can have its own page.
function G.macro_set(delay)
    if not on('macro') then return end
    local c = cfg.macro
    local book, page = tonumber(c.book) or 1, tonumber(c.page) or 1
    local sub = low(player and player.sub_job)
    for job, n in tostring(c.subs or ''):gmatch('(%a%a%a)%s*=%s*(%d+)') do
        if job:lower() == sub then page = tonumber(n) or page end
    end
    send_command(('wait %s; input /macro book %d; wait 0.6; input /macro set %d'):format(tostring(delay or 0.1), book, page))
    G.macro_now = { book = book, page = page }
end

-- ------------------------------------------------------------------ Accession for Sneak, Invisible, Deodorize (his request 2026-11-15: "if the caster
-- is /sch or main sch that sneak, invisible, deodorize will automatically get accession added to it with the command or sneak, invisible,
-- deodorize in the party chat"). Normal game commands only: /ja "Accession", then the spell.
local ACC_SPELLS = { sneak = 'Sneak', invisible = 'Invisible', deodorize = 'Deodorize' }

local function is_sch()
    return low(player and player.main_job) == 'sch' or low(player and player.sub_job) == 'sch'
end

-- stratagem charges left (main SCH at 99: 5, one every 48 s; /SCH at 49: 2, one every 120 s), from the game's one shared timer
local function strat_charges()
    local main = low(player and player.main_job) == 'sch'
    local max, per = main and 5 or 2, main and 48 or 120
    local r = windower.ffxi.get_ability_recasts and windower.ffxi.get_ability_recasts()
    local left = type(r) == 'table' and tonumber(r[231]) or 0
    return math.max(0, max - math.ceil(left / per))
end

-- before the spell: true = it was stopped and sent again behind Accession
function G.acc_spell(spell)
    if not on('accession') or not spell or spell.action_type ~= 'Magic' then return false end
    local name = spell.english
    if not (name == 'Sneak' or name == 'Invisible' or name == 'Deodorize') or not is_sch() then return false end
    local c = cfg.accession
    if (name == 'Sneak' and c.sneak == false) or (name == 'Invisible' and c.invisible == false) or (name == 'Deodorize' and c.deodorize == false) then return false end
    if buff('Accession') then return false end
    local now = os.clock()
    if now < (G.acc_pass or 0) then return false end               -- (the spell we sent again: it goes through, with Accession or without)
    local light = buff('Light Arts') or buff('Addendum: White')
    if not light and c.arts == false then return false end
    if strat_charges() < 1 then
        if now > (G.acc_none or 0) then G.acc_none = now + 30 say('no stratagem charge for Accession: ' .. name .. ' goes on you alone') end
        return false
    end
    cancel_spell()
    G.acc_pass = now + 10
    local target = (spell.target and spell.target.raw) or '<me>'
    local cmd = ''
    if not light then cmd = 'input /ja "Light Arts" <me>; wait 1.6; ' end
    send_command(cmd .. 'input /ja "Accession" <me>; wait 1.6; input /ma "' .. name .. '" ' .. target)
    return true
end

-- cast these on yourself one after the other (each gets its Accession on the way through precast)
function G.acc_cast(list)
    local parts = {}
    for i, key in ipairs(list) do
        local name = ACC_SPELLS[key]
        if name then
            if #parts > 0 then parts[#parts + 1] = 'wait 9' end
            parts[#parts + 1] = 'input /ma "' .. name .. '" <me>'
        end
    end
    if #parts > 0 then G.acc_pass = 0 send_command(table.concat(parts, '; ')) end
    return #parts > 0
end

-- "sneak", "invis", "deo" (or "sneak invis", "sneak and invis please") said in the party: which spells
function G.party_words(msg)
    local m = ' ' .. low(tostring(msg or '')):gsub('[^%a%s]', ' ') .. ' '
    if #m > 42 or m:find(' attack') or m:find(' no ') or m:find(' dont ') or m:find(' not ') then return {} end
    local out = {}
    if m:find(' sneak ') or m:find(' sneaks ') then out[#out + 1] = 'sneak' end
    if m:find(' invis ') or m:find(' invisible ') or m:find(' invisi ') then out[#out + 1] = 'invisible' end
    if m:find(' deo ') or m:find(' deodorize ') or m:find(' deodorise ') or m:find(' deod ') then out[#out + 1] = 'deodorize' end
    return out
end

local function acc_chat(message, sender, mode)
    if not on('accession') or cfg.accession.chat == false or mode ~= 4 or not is_sch() then return end
    local list = G.party_words(message)
    if #list == 0 then return end
    local now = os.clock()
    if now < (G.acc_chat_t or 0) or (midaction and midaction()) then return end
    G.acc_chat_t = now + 15
    say((sender and (tostring(sender) .. ' asked: ') or '') .. table.concat(list, ', ') .. ' with Accession')
    G.acc_cast(list)
end

-- what happens before your own precast: Echo Drops when silenced, cancel Sneak for Spectral Jig
function G.pre(spell)
    if spell.type == 'WeaponSkill' then G.ws_tp = math.floor((player.tp or 0) / 500) * 500 end
    if G.tools_pre(spell) then return true end
    if on('silence') and spell.action_type == 'Magic' and buff('silence') then
        cancel_spell()
        local item = cfg.silence.item or 'Echo Drops'
        send_command('input /item "' .. item .. '" <me>')
        say('silenced: using ' .. item)
        return true
    end
    if G.acc_spell(spell) then return true end
    if on('cancel') and cfg.cancel.jig and spell.english == 'Spectral Jig' and buff('sneak') then
        send_command('cancel 71')
    end
    if G.cure_down(spell) then return true end
    G.solace(spell)
    return false
end

-- Bard: Honor March needs Marsyas and Aria of Passion needs Loughnashade from the start of the song; Carnwenhan for buff songs when not fighting
local SONG_DEBUFF = { 'lullaby', 'elegy', 'threnody', 'requiem', 'finale', 'nocturne', 'virelai', 'foe ', 'horde ', 'magic finale', 'pining' }
function G.song_gear(spell)
    if not on('songs') or spell.type ~= 'BardSong' then return end
    local c, n = cfg.songs, spell.english
    if n == 'Honor March' and c.honor and c.honor ~= '' then
        equip({ range = c.honor })
    elseif n == 'Aria of Passion' and c.aria and c.aria ~= '' then
        equip({ range = c.aria })
    end
    if c.weapon and c.weapon ~= '' and player and player.status ~= 'Engaged' and spell.target and spell.target.type ~= 'MONSTER' then
        local l = low(n)
        for _, d in ipairs(SONG_DEBUFF) do if l:find(d, 1, true) then return end end
        equip({ main = c.weapon })
    end
end

local COPY_IMAGE = 'cancel 66; cancel 444; cancel 445; cancel 446'
function G.mid(spell)
    if not on('cancel') then return end
    local c, n = cfg.cancel, spell.english
    local w = 'wait ' .. tostring(c.wait or 1.5) .. '; '
    if c.utsusemi and n == 'Utsusemi: Ichi' and (buff('copy image') or buff('copy image (2)') or buff('copy image (3)') or buff('copy image (4+)')) then
        send_command(w .. COPY_IMAGE)
    elseif c.stoneskin and n == 'Stoneskin' and buff('stoneskin') then
        send_command(w .. 'cancel 37')
    elseif c.sneak and (n == 'Sneak' or n == 'Monomi: Ichi') and buff('sneak') and spell.target and spell.target.type == 'SELF' then
        send_command(w .. 'cancel 71')
    elseif c.invisible and (n == 'Invisible' or n == 'Tonko: Ichi' or n == 'Tonko: Ni') and buff('invisible') and spell.target and spell.target.type == 'SELF' then
        send_command(w .. 'cancel 69')
    end
end

function G.ammo(spell)
    if not on('ammo') or spell.action_type ~= 'Ranged Attack' then return end
    local a = player.equipment and player.equipment.ammo
    if type(a) ~= 'string' or a == '' or a == 'empty' then return end
    local n = 0
    for _, bag in ipairs({ 'inventory', 'wardrobe', 'wardrobe2', 'wardrobe3', 'wardrobe4', 'wardrobe5', 'wardrobe6',
                           'wardrobe7', 'wardrobe8' }) do
        local b = player[bag]
        local it = type(b) == 'table' and b[a]
        if type(it) == 'table' and it.count then n = n + it.count end
    end
    if n <= (cfg.ammo.count or 20) and G.ammo_warned ~= n and (n % 5 == 0 or n <= 5) then
        G.ammo_warned = n
        add_to_chat(28, 'GearSwap Doctor: ' .. a .. ' - only ' .. n .. ' left!')
    end
end

-- Haste (his request 2026-10-30): which level, and is delay capped with gear + buffs. The caps are the game's: gear 25 %, magic 43.75 %,
-- abilities 25 %, delay 80 % less at most. Gear is read from the items worn; the buffs from their icons, which don't say how strong: a Haste or
-- March seen landing on you counts as what it was, otherwise the ones in the options. So: a good estimate, not the server's number.
local GEAR_CAP, MAGIC_CAP, JA_CAP, DELAY_CAP = 25, 43.75, 25, 80
-- bg-wiki.com/ffxi/Attack_Speed: Haste 150/1024, Haste II 30 %, Refueling 10, Erratic Flutter 30, Animating Wail 15, Hastega 153/1024
local HASTE_SPELLS = { [57] = 14.65, [511] = 30, [530] = 10, [710] = 30, [661] = 15, [358] = 14.94 }
-- March: {base, each Songs+, Songs+ that count}, out of 1024: the same page's ranges (Advancing 10.55-18.95 %, Victory 15.92-28.61 %, Honor 12.30-16.99 %)
local MARCHES = { [419] = { 108, 10.75, 8 }, [420] = { 163, 16.25, 8 }, [417] = { 126, 12, 4 } }
local TWO_HANDED_SKILL = { [4] = true, [6] = true, [7] = true, [8] = true, [10] = true, [12] = true }
local DW_MAIN = { NIN = 35, DNC = 30, THF = 25 }             -- (at 99; the higher of job and sub job, they don't add up: FFXIAH, 49635)
local DW_SUB = { NIN = 25, DNC = 15 }
local WORN = { 'main', 'sub', 'range', 'ammo', 'head', 'neck', 'left_ear', 'right_ear', 'body', 'hands', 'left_ring', 'right_ring',
               'back', 'waist', 'legs', 'feet' }
local gear_stats = {}

-- Haste and Dual Wield of one item: its text up to the first "Set:", "Pet:", "Latent effect:" ... (those don't count), and its augments
local function item_stats(it)
    local key = tostring(it.id) .. '/' .. tostring(it.extdata)
    if gear_stats[key] then return gear_stats[key] end
    local out = { haste = 0, dw = 0 }
    local res = gearswap and gearswap.res
    local d = res and res.item_descriptions and res.item_descriptions[it.id]
    local text = d and d.en or ''
    local from = 1
    while true do
        local a, b, word = text:find('(%a+):', from)
        if not a then break end
        if word ~= 'DEF' and word ~= 'DMG' and word ~= 'Delay' then text = text:sub(1, a - 1) break end
        from = b + 1
    end
    out.haste = tonumber(text:match('Haste%+(%d+)')) or 0
    out.dw = tonumber(text:match('Dual Wield"?%+(%d+)')) or 0
    local ok, dec = pcall(function() return gearswap.extdata.decode(it) end)
    for _, aug in ipairs(ok and type(dec) == 'table' and dec.augments or {}) do
        if type(aug) == 'string' and not aug:find(':') then
            out.haste = out.haste + (tonumber(aug:match('Haste%+(%d+)')) or 0)
            out.dw = out.dw + (tonumber(aug:match('Dual Wield"?%+(%d+)')) or 0)
        end
    end
    gear_stats[key] = out
    return out
end

local function march_percent(id)
    local m = MARCHES[id]
    return (m[1] + math.min(m[3], (cfg.haste and cfg.haste.song) or 7) * m[2]) / 1024 * 100
end

-- {gear, magic, ja, total, need, capped, word}, or nil when the game has nothing to read yet
function G.haste_now()
    local p = windower.ffxi.get_player()
    if not p or type(p.buffs) ~= 'table' then return nil end
    local eq = windower.ffxi.get_items and windower.ffxi.get_items('equipment')
    local gear, dw, two_handed, off_weapon, main_name, main_level = 0, 0, false, false, nil, 0
    if type(eq) == 'table' then
        for _, slot in ipairs(WORN) do
            local idx = eq[slot]
            if idx and idx ~= 0 then
                local it = windower.ffxi.get_items(eq[slot .. '_bag'], idx)
                if type(it) == 'table' and it.id and it.id ~= 0 then
                    local st = item_stats(it)
                    gear, dw = gear + st.haste, dw + st.dw
                    local info = gearswap and gearswap.res and gearswap.res.items and gearswap.res.items[it.id]
                    if slot == 'main' and info and TWO_HANDED_SKILL[info.skill or 0] then two_handed = true end
                    if slot == 'main' and info then main_name, main_level = info.en, info.item_level or 0 end
                    if slot == 'sub' and info and info.category == 'Weapon' and (info.skill or 0) > 0 then off_weapon = true end
                end
            end
        end
    end
    local c = cfg.haste or {}
    local magic, ja, marches = 0, 0, 0
    local main_job, sub_job = player and player.main_job, player and player.sub_job
    for _, id in ipairs(p.buffs) do
        if id == 33 then magic = magic + (G.haste_seen or (c.spell == 'Haste' and 14.65 or 30))
        elseif id == 580 then magic = magic + (c.geo or 40)
        elseif id == 214 then marches = marches + 1
        elseif id == 228 then magic = magic + 25.9                -- Embrava, its maximum
        elseif id == 604 then magic = magic + 15                  -- Mighty Guard
        elseif id == 13 or id == 565 then magic = magic - 29.2    -- Slow, at its worst (7.3 - 29.2 %; the wiki has nothing on Slow II)
        elseif id == 194 then magic = magic - 50                  -- Elegy, at its worst (Carnage Elegy)
        elseif id == 273 and main_name == 'Apocalypse' then              -- its Aftermath: ability haste at iLv119 III, gear haste below (Attack_Speed)
            if main_level >= 119 then ja = ja + 10 else gear = gear + 10 end
        elseif id == 64 and two_handed then ja = ja + ((main_job == 'DRK') and 25 or 15)
        elseif id == 353 and two_handed then ja = ja + 10
        elseif id == 370 then ja = ja + ((main_job == 'DNC') and 10 or 5)
        end
    end
    local seen = G.marches_seen or {}
    for i = 1, marches do
        magic = magic + march_percent(seen[#seen - i + 1] or (i == 1 and 420 or 419))
    end
    gear, magic, ja = math.min(gear, GEAR_CAP), math.max(0, math.min(magic, MAGIC_CAP)), math.min(ja, JA_CAP)
    local total = gear + magic + ja
    local need = DELAY_CAP
    if off_weapon then
        dw = dw + math.max(main_job == 'BLU' and (c.blu_dw or 25) or DW_MAIN[main_job] or 0, DW_SUB[sub_job] or 0)
        need = dw >= DELAY_CAP and 0 or (1 - 0.2 / (1 - dw / 100)) * 100
    end
    local word = (magic >= MAGIC_CAP - 0.01 and 'capped') or (magic >= 35 and 'high') or (magic >= 30 and 'mid') or (magic >= 14 and 'low') or 'none'
    return { gear = gear, magic = magic, ja = ja, total = total, need = need, dw = off_weapon and dw or 0, capped = total >= need - 0.01, word = word }
end

function G.haste_words(h)
    local parts = ('gear %.0f/%d, magic %.1f/43.75 (%s), abilities %.0f/%d'):format(h.gear, GEAR_CAP, h.magic, h.word, h.ja, JA_CAP)
    if h.dw > 0 then parts = parts .. (', Dual Wield %.0f'):format(h.dw) end
    if h.capped then
        return ('Delay capped: %.1f%% haste, %.1f%% needed (%s)'):format(h.total, h.need, parts)
    end
    return ('Haste %.1f%%: %.1f%% short of the delay cap (%s)'):format(h.total, h.need - h.total, parts)
end

-- Every 2 s while fighting and not in an action: tell when it has stayed at a new level for one more look (swaps and refreshes don't count)
function G.haste_tick(status)
    if not on('haste') or status ~= 1 or (midaction and midaction()) then return end
    local now = os.clock()
    if now < (G.haste_next or 0) then return end
    G.haste_next = now + 2
    local ok, h = pcall(G.haste_now)
    if not ok or not h then return end
    G.haste_short = h.capped and 'Delay capped' or ('Haste %.0f/%.0f'):format(h.total, h.need)
    local tell = cfg.haste.tell or 'When it changes level'
    local key = tell == 'Only capped / not capped' and tostring(h.capped) or (tostring(h.capped) .. '|' .. h.word .. '|' .. math.floor(h.gear) .. '|' .. math.floor(h.ja))
    if key == G.haste_told then return end
    if key ~= G.haste_maybe then G.haste_maybe = key return end
    G.haste_told = key
    if tell ~= 'Never' then add_to_chat(h.capped and 56 or 60, 'GearSwap Doctor: ' .. G.haste_words(h)) end
    G.box_update()
end

-- A Haste or March landing on you says how strong it is
local function on_spell(act)
    if not on('haste') or not act or act.category ~= 4 then return end
    local id = me_id()
    for _, t in ipairs(act.targets or {}) do
        if t.id == id then
            if HASTE_SPELLS[act.param] then G.haste_seen = HASTE_SPELLS[act.param]
            elseif MARCHES[act.param] then
                local seen = G.marches_seen or {}
                seen[#seen + 1] = act.param
                if #seen > 4 then table.remove(seen, 1) end
                G.marches_seen = seen
            end
            return
        end
    end
end

-- Real fights (his request 2026-10-31): your own hits and weapon skills, added up and written to a file now and then, so GearSwap Doctor can set them beside wsdist's numbers.
-- Only reads what the game shows you; nothing is sent. data\gsd_fights_<Name>.csv: see real_fights.py.
local FIGHT_HIT, FIGHT_CRIT, FIGHT_MISS = { [1] = true, [67] = true }, { [67] = true }, { [15] = true, [63] = true }
local WS_HIT, WS_MISS = { [185] = true, [187] = true }, { [188] = true }     -- (res action_messages.lua: damage, HP drained; a miss)
-- ------------------------------------------------------------------ Accuracy and Double Attack (his request 2026-11-13: "a feature that shows the double
-- attack and current accuracy, including buffs"). The game doesn't send your accuracy, so it is worked out with BG Wiki's formula:
--   accuracy = weapon skill (up to 200 as is, then 0.9 / 0.8 / 0.9 a point) + floor(DEX x 0.75) + Accuracy+ gear + traits + buffs
-- DEX (with gear and buffs) comes from the game's own character stats (it sends them whenever gear or buffs change). Double Attack: gear + the
-- Warrior trait + Fighter's Roll / Temper. Rolls and Madrigals it sees land use their real number; the others count as set in GearSwap Doctor.
local ACC_TRAIT = { RNG = { { 10, 10 }, { 30, 22 }, { 50, 35 }, { 70, 48 }, { 86, 60 }, { 96, 73 } },
                    DRG = { { 30, 10 }, { 60, 22 }, { 76, 35 } }, DNC = { { 30, 10 }, { 60, 22 }, { 76, 35 } },
                    RUN = { { 50, 10 }, { 70, 22 }, { 90, 35 } } }                          -- (BG Wiki Accuracy Bonus)
local DA_TRAIT = { WAR = { { 25, 10 }, { 50, 12 }, { 75, 14 }, { 85, 16 }, { 99, 18 } } }  -- (BG Wiki Double Attack; job points add more)
local HUNTER = { 10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50 }                            -- (BG Wiki Hunter's Roll; +5 a Phantom Roll +1)
local FIGHTER = { 1, 2, 3, 4, 10, 5, 6, 6, 1, 7, 15 }                                   -- (BG Wiki Fighter's Roll; +1 a Phantom Roll +1)
local ROLL_IDS = { [98] = 'fighter', [108] = 'hunter' }
local LUCKY = { fighter = 5, hunter = 4 }
local MADRIGAL = { [399] = { 45, 4.5 }, [400] = { 60, 6 } }                             -- (Sword / Blade Madrigal: base, a Songs+ point)
local acc_cache = {}

local function trait(t, lv)
    local v = 0
    for _, x in ipairs(t or {}) do if (lv or 0) >= x[1] then v = x[2] end end
    return v
end

local function skill_acc(s)
    if s <= 200 then return s end
    if s <= 400 then return math.floor((s - 200) * 0.9) + 200 end
    if s <= 600 then return math.floor((s - 400) * 0.8) + 380 end
    return math.floor((s - 600) * 0.9) + 540
end

-- Accuracy+, Double Attack and "<weapon> skill +" of one item: its own text (not Set: / Latent effect: ...), and its augments
local function acc_item(it, skill_name)
    local key = tostring(it.id) .. '/' .. tostring(it.extdata) .. '/' .. tostring(skill_name)
    if acc_cache[key] then return acc_cache[key] end
    local out = { acc = 0, da = 0, skill = 0 }
    local res = gearswap and gearswap.res
    local d = res and res.item_descriptions and res.item_descriptions[it.id]
    local text = d and d.en or ''
    local from = 1
    while true do
        local a, b, word = text:find('(%a+):', from)
        if not a then break end
        if word ~= 'DEF' and word ~= 'DMG' and word ~= 'Delay' then text = text:sub(1, a - 1) break end
        from = b + 1
    end
    local function read(s)
        for pos, n in s:gmatch('()Accuracy%+(%d+)') do
            local before = s:sub(math.max(1, pos - 7), pos - 1)
            if not before:find('Magic') and not before:find('Ranged') then out.acc = out.acc + tonumber(n) end
        end
        for pos, n in s:gmatch('()Acc%.%+(%d+)') do
            local before = s:sub(math.max(1, pos - 5), pos - 1)
            if not before:find('Mag') and not before:find('Rng') then out.acc = out.acc + tonumber(n) end
        end
        out.da = out.da + (tonumber(s:match('Double Attack"?%+(%d+)')) or 0) + (tonumber(s:match('Dbl%.Atk%."?%+(%d+)')) or 0)
        if skill_name then out.skill = out.skill + (tonumber(s:match(skill_name .. ' skill %+(%d+)')) or 0) end
    end
    read(text)
    local ok, dec = pcall(function() return gearswap.extdata.decode(it) end)
    for _, aug in ipairs(ok and type(dec) == 'table' and dec.augments or {}) do
        if type(aug) == 'string' and not aug:find(':') then read(aug) end
    end
    acc_cache[key] = out
    return out
end

local function roll_value(kind)
    local c = cfg.acc or {}
    local n = (G.rolls or {})[kind]
    if not n then
        n = c.roll == '11' and 11 or tonumber(c.roll) or LUCKY[kind]
    end
    n = math.max(1, math.min(11, n))
    local t = kind == 'hunter' and HUNTER or FIGHTER
    return t[n] + (c.roll_plus or 0) * (kind == 'hunter' and 5 or 1), n
end

-- {acc, da, att, parts, da_parts, exact} or nil when the game has nothing to read yet
function G.acc_now()
    local p = windower.ffxi.get_player()
    if not p or type(p.buffs) ~= 'table' then return nil end
    local res = gearswap and gearswap.res
    local c = cfg.acc or {}
    local eq = windower.ffxi.get_items and windower.ffxi.get_items('equipment')
    local skill_id, two_handed
    if type(eq) == 'table' and eq.main and eq.main ~= 0 then
        local it = windower.ffxi.get_items(eq.main_bag, eq.main)
        local info = type(it) == 'table' and res and res.items and res.items[it.id]
        if info then skill_id, two_handed = info.skill, TWO_HANDED_SKILL[info.skill or 0] end
    end
    local skill_name = skill_id and res and res.skills and res.skills[skill_id] and res.skills[skill_id].en or (skill_id == nil and 'Hand-to-Hand' or nil)
    local gear_acc, gear_da, gear_skill = 0, 0, 0
    if type(eq) == 'table' then
        for _, slot in ipairs(WORN) do
            local idx = eq[slot]
            if idx and idx ~= 0 then
                local it = windower.ffxi.get_items(eq[slot .. '_bag'], idx)
                if type(it) == 'table' and it.id and it.id ~= 0 then
                    local st = acc_item(it, skill_name)
                    gear_acc, gear_da, gear_skill = gear_acc + st.acc, gear_da + st.da, gear_skill + st.skill
                end
            end
        end
    end
    local base_skill
    if skill_name and type(p.skills) == 'table' then
        base_skill = p.skills[(skill_name:lower():gsub("[%s%-]", "_"))]
    end
    local skill = (base_skill or 0) + gear_skill
    local main_job, sub_job = p.main_job or (player and player.main_job), p.sub_job or (player and player.sub_job)
    local main_lv, sub_lv = p.main_job_level or 99, p.sub_job_level or 49
    local traits = math.max(trait(ACC_TRAIT[main_job], main_lv), trait(ACC_TRAIT[sub_job], sub_lv))
    local buffs, da_buffs, names, da_names, madrigals = 0, 0, {}, {}, 0
    local seen_m = G.madrigals_seen or {}
    for _, id in ipairs(p.buffs) do
        if id == 199 then
            madrigals = madrigals + 1
            local m = MADRIGAL[seen_m[#seen_m - madrigals + 1] or 400]
            local v = math.floor(m[1] + m[2] * (c.song or 4))
            buffs = buffs + v
            names[#names + 1] = 'Madrigal ' .. v
        elseif id == 320 then
            local v, n = roll_value('hunter')
            buffs = buffs + v
            names[#names + 1] = ("Hunter's Roll %d (%d)"):format(n, v)
        elseif id == 58 then buffs = buffs + 25 names[#names + 1] = 'Aggressor 25'
        elseif id == 353 and two_handed then buffs = buffs + 10 names[#names + 1] = 'Hasso 10'
        elseif id == 251 and (c.food or 0) > 0 then buffs = buffs + c.food names[#names + 1] = 'food ' .. c.food
        elseif (id == 90 or id == 553) and (c.geo or 0) > 0 then buffs = buffs + c.geo names[#names + 1] = 'Accuracy Boost ' .. c.geo
        elseif id == 310 then
            local v, n = roll_value('fighter')
            da_buffs = da_buffs + v
            da_names[#da_names + 1] = ("Fighter's Roll %d (%d%%)"):format(n, v)
        elseif id == 432 and (c.temper or 0) > 0 then da_buffs = da_buffs + c.temper da_names[#da_names + 1] = 'Temper ' .. c.temper .. '%'
        end
    end
    local extra = c.extra or 0
    local dex = G.dex
    if not dex then                                  -- (GearSwap reads the same stats when you log in: player.dex, until the game sends new ones)
        local ok, v = pcall(function() return player and tonumber(player.dex) end)
        if ok and v and v > 0 then dex = v end
    end
    local acc = skill_acc(skill) + (dex and math.floor(dex * 0.75) or 0) + gear_acc + traits + buffs + extra
    local da_trait = math.max(trait(DA_TRAIT[main_job], main_lv), trait(DA_TRAIT[sub_job], sub_lv))
    local da = gear_da + da_trait + da_buffs + (c.da_extra or 0)
    local parts = ('%s skill %d (%d from gear) = %d, DEX %s = %s, gear +%d, traits +%d, buffs +%d%s%s'):format(
        skill_name or 'weapon', skill, gear_skill, skill_acc(skill), dex and tostring(dex) or '?', dex and tostring(math.floor(dex * 0.75)) or '?',
        gear_acc, traits, buffs, #names > 0 and (' (' .. table.concat(names, ', ') .. ')') or '', extra ~= 0 and (', your own +' .. extra) or '')
    local da_parts = ('gear %d%%, traits %d%%, buffs %d%%%s'):format(gear_da, da_trait, da_buffs,
        #da_names > 0 and (' (' .. table.concat(da_names, ', ') .. ')') or '')
    return { acc = acc, da = da, att = G.att, parts = parts, da_parts = da_parts, exact = dex ~= nil and base_skill ~= nil }
end

function G.acc_words(a)
    local s = ('Accuracy %s%d (%s). Double Attack %d%% (%s).'):format(a.exact and '' or 'about ', a.acc, a.parts, a.da, a.da_parts)
    if a.att then s = s .. (' Attack %d (the game\'s own number).'):format(a.att) end
    if not a.exact then s = s .. ' (DEX not read yet: it comes with your next gear change.)' end
    return s
end

-- Every 2 s while fighting and not in an action: the window line, and a chat line when it changes and stays changed
function G.acc_tick(status)
    if not on('acc') or (midaction and midaction()) then return end
    if status ~= 1 and not cfg.acc.idle then return end
    local now = os.clock()
    if now < (G.acc_next or 0) then return end
    G.acc_next = now + 2
    local ok, a = pcall(G.acc_now)
    if not ok or not a then return end
    G.acc_short = ('Acc %s%d  DA %d%%'):format(a.exact and '' or '~', a.acc, a.da)
    local key = math.floor(a.acc / 10) .. '|' .. a.da
    if key ~= G.acc_told then
        if key ~= G.acc_maybe then G.acc_maybe = key
        else
            G.acc_told = key
            if (cfg.acc.tell or 'When it changes') ~= 'Never' then add_to_chat(60, 'GearSwap Doctor: ' .. G.acc_words(a)) end
        end
    end
    G.box_update()
end

-- The game's own character stats: DEX (with gear and buffs) and Attack
local function acc_chunk(id, data)
    if id ~= 0x061 or not on('acc') then return end
    pcall(function()
        G.dex = data:unpack('H', 0x17) + data:unpack('h', 0x25)
        G.att = data:unpack('H', 0x31)
    end)
end

-- A roll or a Madrigal landing on you says how strong it is (Double-Up: the roll its Corsair last rolled)
local function acc_action(act)
    if not on('acc') or not act then return end
    local id = me_id()
    if act.category == 6 and (ROLL_IDS[act.param] or act.param == 123) then
        G.roll_by = G.roll_by or {}
        local kind = ROLL_IDS[act.param] or G.roll_by[act.actor_id]
        if ROLL_IDS[act.param] then G.roll_by[act.actor_id] = ROLL_IDS[act.param] end
        if not kind then return end
        for _, t in ipairs(act.targets or {}) do
            local a = t.actions and t.actions[1]
            if t.id == id and a and a.param and a.param >= 1 and a.param <= 12 then
                G.rolls = G.rolls or {}
                G.rolls[kind] = a.param <= 11 and a.param or nil
            end
        end
    elseif act.category == 4 and MADRIGAL[act.param] then
        for _, t in ipairs(act.targets or {}) do
            if t.id == id then
                local seen = G.madrigals_seen or {}
                seen[#seen + 1] = act.param
                if #seen > 2 then table.remove(seen, 1) end
                G.madrigals_seen = seen
                return
            end
        end
    end
end

-- ------------------------------------------------------------------ Warnings while you fight (PLAN.md A4, 2026-11-14)
-- Three things the guides call mistakes, said when they happen:
--   hit rate  your own swings on the monster in front of you, as they really land (the game never sends a monster's Evasion, so it is counted from
--             the hits and misses it shows you): under the cap for the last 50 swings = how much accuracy is missing (2 accuracy a %)
--   damage taken  fighting with less than the damage taken you set, read from the gear you wear (its text and augments)
--   max HP    a gear swap that cuts your max HP by more than you set: that HP is gone until it is healed back
local warn_cache = {}

local function dt_item(it)
    local key = tostring(it.id) .. '/' .. tostring(it.extdata)
    if warn_cache[key] then return warn_cache[key] end
    local out = { dt = 0, pdt = 0, mdt = 0 }
    local res = gearswap and gearswap.res
    local d = res and res.item_descriptions and res.item_descriptions[it.id]
    local text = d and d.en or ''
    local from = 1
    while true do
        local a, b, word = text:find('(%a+):', from)
        if not a then break end
        if word ~= 'DEF' and word ~= 'DMG' and word ~= 'Delay' then text = text:sub(1, a - 1) break end
        from = b + 1
    end
    local function read(s)
        for kind, n in s:gmatch('(%a*) ?[Dd]amage taken ?%-(%d+)') do
            local k = kind:lower()
            if k == 'physical' then out.pdt = out.pdt + tonumber(n) elseif k == 'magic' then out.mdt = out.mdt + tonumber(n)
            elseif k ~= 'breath' then out.dt = out.dt + tonumber(n) end
        end
        for kind, n in s:gmatch('(%a+)%.? dmg%. taken ?%-(%d+)') do
            local k = kind:lower()
            if k:sub(1, 4) == 'phys' then out.pdt = out.pdt + tonumber(n) elseif k:sub(1, 3) == 'mag' then out.mdt = out.mdt + tonumber(n) end
        end
    end
    read(text)
    local ok, dec = pcall(function() return gearswap.extdata.decode(it) end)
    for _, aug in ipairs(ok and type(dec) == 'table' and dec.augments or {}) do
        if type(aug) == 'string' and not aug:find(':') then read(aug) end
    end
    warn_cache[key] = out
    return out
end

-- (physical, magic) damage taken "% less" of the gear worn now, each capped at 50
function G.dt_now()
    local eq = windower.ffxi.get_items and windower.ffxi.get_items('equipment')
    if type(eq) ~= 'table' then return nil end
    local dt, pdt, mdt = 0, 0, 0
    for _, slot in ipairs(WORN) do
        local idx = eq[slot]
        if idx and idx ~= 0 then
            local it = windower.ffxi.get_items(eq[slot .. '_bag'], idx)
            if type(it) == 'table' and it.id and it.id ~= 0 then
                local st = dt_item(it)
                dt, pdt, mdt = dt + st.dt, pdt + st.pdt, mdt + st.mdt
            end
        end
    end
    return math.min(50, dt + pdt), math.min(50, dt + mdt)
end

local WARN_SWINGS = 50
-- your own swing landed or missed: the last 50 on this monster
local function warn_swing(mob, hit)
    local w = G.warn_hits
    if not w or w.mob ~= mob then w = { mob = mob, list = {}, hits = 0 } G.warn_hits = w end
    w.list[#w.list + 1] = hit
    if hit then w.hits = w.hits + 1 end
    if #w.list > WARN_SWINGS then
        if table.remove(w.list, 1) then w.hits = w.hits - 1 end
    end
end

function G.hit_now()
    local w = G.warn_hits
    if not w or #w.list < 20 then return nil end
    return w.hits / #w.list * 100, #w.list, w.mob
end

local function warn_action(act)
    if not on('warn') or not act or act.category ~= 1 or act.actor_id ~= me_id() then return end
    for _, t in ipairs(act.targets or {}) do
        local m = windower.ffxi.get_mob_by_id(t.id)
        if m and m.is_npc ~= false and m.name then
            for _, a in ipairs(t.actions or {}) do
                if FIGHT_HIT[a.message] then warn_swing(m.name, true) elseif FIGHT_MISS[a.message] then warn_swing(m.name, false) end
            end
        end
    end
end

local function warn_say(key, msg)
    local now = os.clock()
    G.warn_told = G.warn_told or {}
    if (G.warn_told[key] or -999) + (cfg.warn.again or 60) > now then return end
    G.warn_told[key] = now
    add_to_chat(28, 'GearSwap Doctor: ' .. msg)
end

-- every 2 s: the window line and the warnings
function G.warn_tick(status, p)
    if not on('warn') then return end
    local now = os.clock()
    if now < (G.warn_next or 0) then return end
    G.warn_next = now + 2
    local c = cfg.warn
    local parts = {}
    -- max HP cut by a swap (any time: casting sets do it)
    local max_hp = p and p.vitals and p.vitals.max_hp
    if max_hp and (c.hp or 0) > 0 then
        local was = G.warn_maxhp
        if was and was - max_hp >= c.hp then
            warn_say('hp', ('a gear swap cut your max HP by %d (%d -> %d): that HP is lost until it is healed back'):format(was - max_hp, was, max_hp))
        end
        G.warn_maxhp = max_hp
    end
    if status == 1 and not (midaction and midaction()) then
        if c.hit ~= false then
            local rate, n, mob = G.hit_now()
            if rate then
                parts[#parts + 1] = ('Hit %.0f%%'):format(rate)
                local cap = tonumber(c.cap) or 95
                if n >= WARN_SWINGS and rate < cap - 4 then
                    warn_say('hit', ('you hit %s %.0f %% of the time (last %d swings): about %d more accuracy would reach %d %%')
                             :format(mob, rate, n, math.floor((cap - rate) * 2 + 0.5), cap))
                end
            end
        end
        if (c.dt or 0) > 0 then
            local ok, pd, md = pcall(G.dt_now)
            if ok and pd then
                parts[#parts + 1] = ('DT %d/%d'):format(pd, md)
                if pd < c.dt then
                    G.warn_low = (G.warn_low or 0) + 1
                    if G.warn_low >= 3 then            -- (it has stayed low for 6 s: not a weapon skill set passing by)
                        warn_say('dt', ('fighting with %d %% physical damage taken from gear: you set %d %% as your floor'):format(pd, c.dt))
                    end
                else
                    G.warn_low = 0
                end
            end
        end
    else
        G.warn_low = 0
    end
    local short = table.concat(parts, '  ')
    if short ~= (G.warn_short or '') then G.warn_short = short G.box_update() end
end

local function fight_am()
    return G.am_level and (G.am_level() or -1) or -1
end
local function fight_add(mob, kind, name, tp, damage, crit, miss)
    local main = player and player.equipment and name_of(player.equipment.main) or ''
    local key = table.concat({ (tostring(mob):gsub(',', ' ')), kind, name, tostring(main):gsub(',', ' '), tostring(fight_am()), tostring(tp) }, ',')
    local t = G.fights[key] or { n = 0, total = 0, crits = 0, miss = 0 }
    t.n, t.total = t.n + 1, t.total + (damage or 0)
    if crit then t.crits = t.crits + 1 end
    if miss then t.miss = t.miss + 1 end
    G.fights[key] = t
    G.fights_any = true
end
function G.fights_flush()
    if not on('fights') or not G.fights_any or not player or not player.name then return end
    local io_ = gearswap and gearswap.io
    local folder = rawget(_G, 'lua_base_path') or (windower and windower.addon_path)
    if not io_ or type(folder) ~= 'string' then return end
    local f = io_.open(folder .. 'data/gsd_fights_' .. player.name .. '.csv', 'a')
    if not f then return end
    local now = os.time and os.time() or 0
    for key, t in pairs(G.fights) do
        local mob, kind, name, main, am, tp = key:match('^([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*)$')
        if mob then
            f:write(table.concat({ now, player.main_job or '', player.sub_job or '', mob, kind, name, main, am, tp, t.n, t.total, t.crits, t.miss }, ','), '\n')
        end
    end
    f:close()
    G.fights, G.fights_any = {}, false
end
local function on_fight(act)
    if not on('fights') or not act or act.actor_id ~= me_id() then return end
    if act.category ~= 1 and act.category ~= 3 then return end
    local ws
    if act.category == 3 then
        local r = gearswap and gearswap.res and gearswap.res.weapon_skills and gearswap.res.weapon_skills[act.param]
        ws = r and r.en
        if not ws then return end
    end
    for _, t in ipairs(act.targets or {}) do
        local m = windower.ffxi.get_mob_by_id(t.id)
        if m and m.is_npc ~= false and m.name then
            for _, a in ipairs(t.actions or {}) do
                if ws then
                    if WS_HIT[a.message] then fight_add(m.name, 'ws', ws, G.ws_tp or 0, a.param, false, false)
                    elseif WS_MISS[a.message] then fight_add(m.name, 'ws', ws, G.ws_tp or 0, 0, false, true) end
                elseif FIGHT_HIT[a.message] then fight_add(m.name, 'melee', '', 0, a.param, FIGHT_CRIT[a.message], false)
                elseif FIGHT_MISS[a.message] then fight_add(m.name, 'melee', '', 0, 0, false, true) end
            end
        end
    end
end

-- buffs: doom message / Holy Water, rings unlock when the experience ring's buff lands
function G.buff(name, gain)
    local n = low(name)
    if on('aftermath') and n:find('^aftermath') then
        if cfg.aftermath.say ~= false then
            say(gain and (name .. ' is up') or (name .. ' wore off'))
        end
        G.pending = true                                      -- (when it wears off your file's set has to come back)
    end
    if on('doom') and gain and (n == 'doom' or (cfg.doom.curse and n == 'curse')) then
        if type(cfg.doom.say) == 'string' and cfg.doom.say ~= '' then send_command('input /p ' .. cfg.doom.say) end
        if cfg.doom.holy then send_command('input /item "Holy Water" <me>') end
    end
    if gain and (n == 'dedication' or n == 'commitment') and next(G.locked) then G.unlock('ring used') end
end

-- Toolbags / card cases (his request 2026-11-07): a Ninjutsu spell (or a Quick Draw) with no tool (card) left opens the
-- right Toolbag (Card Case) from the inventory. GearSwap itself stops a Ninjutsu with no tools before your file sees it,
-- so the typed / macro command is read as it goes out. No spam: a bag isn't opened again for 8 s, at most 3 times in a row
-- without the tools showing up, never while you're in an action, and only with a free inventory slot. Normal /item only.
local NIN_TOOLS = {   -- spell family -> {its own tool, its Toolbag, the universal tool (Ninja main only), its Toolbag}
    Katon = { 'Uchitake', 'Toolbag (Uchi)', 'Inoshishinofuda', 'Toolbag (Ino)' },
    Hyoton = { 'Tsurara', 'Toolbag (Tsura)', 'Inoshishinofuda', 'Toolbag (Ino)' },
    Huton = { 'Kawahori-Ogi', 'Toolbag (Kawa)', 'Inoshishinofuda', 'Toolbag (Ino)' },
    Doton = { 'Makibishi', 'Toolbag (Maki)', 'Inoshishinofuda', 'Toolbag (Ino)' },
    Raiton = { 'Hiraishin', 'Toolbag (Hira)', 'Inoshishinofuda', 'Toolbag (Ino)' },
    Suiton = { 'Mizu-Deppo', 'Toolbag (Mizu)', 'Inoshishinofuda', 'Toolbag (Ino)' },
    Utsusemi = { 'Shihei', 'Toolbag (Shihe)', 'Shikanofuda', 'Toolbag (Shika)' },
    Jubaku = { 'Jusatsu', 'Toolbag (Jusa)', 'Chonofuda', 'Toolbag (Cho)' },
    Hojo = { 'Kaginawa', 'Toolbag (Kagi)', 'Chonofuda', 'Toolbag (Cho)' },
    Kurayami = { 'Sairui-Ran', 'Toolbag (Sai)', 'Chonofuda', 'Toolbag (Cho)' },
    Dokumori = { 'Kodoku', 'Toolbag (Kodo)', 'Chonofuda', 'Toolbag (Cho)' },
    Aisha = { 'Soshi', 'Toolbag (Soshi)', 'Chonofuda', 'Toolbag (Cho)' },
    Yurin = { 'Jinko', 'Toolbag (Jinko)', 'Chonofuda', 'Toolbag (Cho)' },
    Tonko = { 'Shinobi-Tabi', 'Toolbag (Shino)', 'Shikanofuda', 'Toolbag (Shika)' },
    Monomi = { 'Sanjaku-Tenugui', 'Toolbag (Sanja)', 'Shikanofuda', 'Toolbag (Shika)' },
    Myoshu = { 'Kabenro', 'Toolbag (Kaben)', 'Shikanofuda', 'Toolbag (Shika)' },
    Migawari = { 'Mokujin', 'Toolbag (Moku)', 'Shikanofuda', 'Toolbag (Shika)' },
    Kakka = { 'Ryuno', 'Toolbag (Ryuno)', 'Shikanofuda', 'Toolbag (Shika)' },
    Gekka = { 'Ranka', 'Toolbag (Ranka)', 'Shikanofuda', 'Toolbag (Shika)' },
    Yain = { 'Furusumi', 'Toolbag (Furu)', 'Shikanofuda', 'Toolbag (Shika)' },
}
local COR_CARDS = {   -- Quick Draw -> {its card, its Card Case}; Trump Card works for all of them
    ['Fire Shot'] = { 'Fire Card', 'Fire Card Case' }, ['Ice Shot'] = { 'Ice Card', 'Ice Card Case' },
    ['Wind Shot'] = { 'Wind Card', 'Wind Card Case' }, ['Earth Shot'] = { 'Earth Card', 'Earth Card Case' },
    ['Thunder Shot'] = { 'Thunder Card', 'Thnd. Card Case' }, ['Water Shot'] = { 'Water Card', 'Water Card Case' },
    ['Light Shot'] = { 'Light Card', 'Light Card Case' }, ['Dark Shot'] = { 'Dark Card', 'Dark Card Case' },
}
G.tool_try, G.tool_want, G.tool_said = {}, {}, {}

local function inv_count(name)
    local b = player and player.inventory
    local it = type(b) == 'table' and b[name]
    if type(it) == 'table' then return tonumber(it.count) or 0 end
    return 0
end
local function job(which) return low(player and player[which]) end

-- {tools that work, bags to open (in order)} for a spell / Quick Draw, or nil when it isn't ours
function G.tools_for(name)
    if type(name) ~= 'string' then return nil end
    local fam = name:match('^(%a+):')
    local t = fam and NIN_TOOLS[fam]
    if t and on('tools') and cfg.tools.nin ~= false and (job('main_job') == 'nin' or job('sub_job') == 'nin') then
        if job('main_job') == 'nin' then
            if cfg.tools.universal ~= false then return { t[1], t[3] }, { t[4], t[2] } end
            return { t[1], t[3] }, { t[2], t[4] }
        end
        return { t[1] }, { t[2] }
    end
    local c = COR_CARDS[name]
    if c and on('tools') and cfg.tools.cor ~= false and job('main_job') == 'cor' then
        if cfg.tools.trump ~= false then return { c[1], 'Trump Card' }, { 'Trump Card Case', c[2] } end
        return { c[1], 'Trump Card' }, { c[2], 'Trump Card Case' }
    end
    return nil
end

local function tools_left(tools)
    local n = 0
    for _, x in ipairs(tools) do n = n + inv_count(x) end
    return n
end

local function free_slot()
    local ok, info = pcall(function() return windower.ffxi.get_bag_info(0) end)
    if ok and type(info) == 'table' and tonumber(info.max) and tonumber(info.count) then
        return tonumber(info.count) < tonumber(info.max)
    end
    return true
end

local function tools_say(key, msg)
    local now = os.clock()
    if now - (G.tool_said[key] or -100) < 60 then return end
    G.tool_said[key] = now
    add_to_chat(28, 'GearSwap Doctor: ' .. msg)
end

-- open a bag for this spell now, if it needs one (false: nothing done)
function G.tools_open(name)
    local tools, bags = G.tools_for(name)
    if not tools then return false end
    if tools_left(tools) > 0 then
        for _, b in ipairs(bags) do G.tool_try[b] = nil end
        return false
    end
    local now = os.clock()
    for _, b in ipairs(bags) do
        if inv_count(b) > 0 then
            local t = G.tool_try[b]
            if t and now < t.till then return false end              -- just opened one: give it time
            if t and t.n >= 3 then
                tools_say(b, b .. " didn't give any tools after 3 tries - stopped (//gs reload to try again)")
                return false
            end
            if not free_slot() then
                tools_say('full', 'no ' .. tools[1] .. ' left and the inventory is full - make room to open ' .. b)
                return false
            end
            G.tool_try[b] = { till = now + 8, n = (t and t.n or 0) + 1 }
            send_command('input /item "' .. b .. '" <me>')
            say('no ' .. tools[1] .. ' left: opening ' .. b)
            return true
        end
    end
    tools_say(tools[1], 'no ' .. tools[1] .. ' left, and no ' .. table.concat(bags, ' / ') .. ' in the inventory!')
    return false
end

-- a spell / Quick Draw that needs a look at its tools (when you're free: not mid-action)
local function tools_want(name, delay)
    if G.tools_for(name) then G.tool_want[name] = os.clock() + (delay or 0) end
end

function G.tools_tick()
    if not on('tools') or not next(G.tool_want) or (midaction and midaction()) then return end
    local now = os.clock()
    for name, at in pairs(G.tool_want) do
        if now >= at then
            G.tool_want[name] = nil
            if G.tools_open(name) then return end                   -- one bag at a time
        end
    end
end

-- the command as it goes out: /ma "Utsusemi: Ni" <me>, /nin ..., /ninjutsu ...
local function tools_text(original)
    if not on('tools') or type(original) ~= 'string' then return end
    local cmd, name = original:match('^%s*/(%a+)%s+"([^"]+)"')
    if not cmd then cmd, name = original:match('^%s*/(%a+)%s+(%a+: ?%a+)') end
    if not cmd or not name then return end
    cmd = cmd:lower()
    if cmd == 'ma' or cmd == 'magic' or cmd == 'nin' or cmd == 'ninjutsu' then tools_want(name) end
end

-- a Quick Draw with no card: stopped (it can't go off) and the case opened; any spell / shot: the next one ready
function G.tools_pre(spell)
    if not on('tools') or spell.type ~= 'CorsairShot' then return false end
    local tools = G.tools_for(spell.english)
    if tools and tools_left(tools) == 0 then
        cancel_spell()
        tools_want(spell.english)
        return true
    end
    return false
end
function G.tools_after(spell)
    if not on('tools') or cfg.tools.ahead == false then return end
    if spell.type == 'Ninjutsu' or spell.type == 'CorsairShot' then tools_want(spell.english, 1) end
end

-- every quarter second: moving or standing, low HP / MP, a Treasure Hunter tag that landed
local function tick()
    local now = os.clock()
    if now - G.t < 0.25 then return end
    G.t = now
    local p = windower.ffxi.get_player()
    if not p or not p.vitals then return end
    local status = p.status
    if on('kiting') then
        local me = windower.ffxi.get_mob_by_target('me')
        if me then
            if G.last then
                local d = (me.x - G.last.x) ^ 2 + (me.y - G.last.y) ^ 2
                local was = G.moving
                if d > 0.01 then
                    G.still = 0
                    G.moving = true
                else
                    G.still = G.still + 1
                    if G.still >= 2 then G.moving = false end
                end
                if was ~= G.moving and (status == 0 or cfg.kiting.engaged) then G.pending = true end
            end
            G.last = { x = me.x, y = me.y }
        end
    end
    if on('lowhp') then
        local th = cfg.lowhp.hpp or 40
        local l = G.low_hp
        if not l and p.vitals.hpp > 0 and p.vitals.hpp < th then l = true
        elseif l and (p.vitals.hpp >= th + 10 or p.vitals.hpp == 0) then l = false end
        if l ~= G.low_hp then G.low_hp = l G.pending = true end
    end
    if on('refresh') then
        local th = cfg.refresh.mpp or 50
        local l = G.low_mp
        if not l and p.vitals.mpp < th then l = true elseif l and p.vitals.mpp >= math.min(100, th + 15) then l = false end
        if l ~= G.low_mp then G.low_mp = l if status == 0 then G.pending = true end end
    end
    if G.react and now > G.react.ends then G.react = nil G.pending = true end        -- (no "landed" seen: off after the seconds you set)
    if G.pending and (status == 0 or status == 1) and not (midaction and midaction()) then
        G.pending = false
        send_command('gs c gsd refresh')
    end
    G.haste_tick(status)
    G.acc_tick(status)
    G.warn_tick(status, p)
    G.tools_tick()
    if on('fights') and now - (G.fights_t or 0) > 60 then
        G.fights_t = now
        pcall(G.fights_flush)
    end
end

-- React (his request 2026-11-28: "acts similarly to the windower addon react ... identify things happening and equip different gear sets",
-- like the auto-defense in his BLU file): a monster starts a TP move or a spell at you (or near you) -> the set for that kind of move goes on,
-- and comes off when the move lands, is interrupted, or after a few seconds. Never while you cast: it waits for the cast to end.
local REACT_BEGIN, REACT_STOP = 24931, 28787
local REACT_KIND = { p = 'physical', m = 'magic', h = 'hybrid', s = 'status', e = 'element' }
local function react_own(name)
    local own = cfg.react and cfg.react.own
    if type(own) ~= 'string' or own == '' or not name then return nil end
    for part in own:gmatch('[^,]+') do
        local n, s = part:match('^%s*(.-)%s*=%s*(.-)%s*$')
        if n and s and s ~= '' and low(n) == low(name) then return s end
    end
    return nil
end
local function react_gear(kind, name)
    local c = cfg.react
    local own = react_own(name)
    if own then
        local g = G.resolve(own)
        if g then return g, own end
    end
    local key = REACT_KIND[kind or '']
    if key and type(c[key]) == 'string' and c[key] ~= '' then
        local g = G.resolve(c[key])
        if g then return g, c[key] end
    end
    if type(c.set) == 'string' and c.set ~= '' then
        local g = G.resolve(c.set)
        if g then return g, c.set end
    end
    return nil
end
function G.react_action(act)
    if not on('react') or not act then return end
    local cat = act.category
    if cat ~= 7 and cat ~= 8 and cat ~= 11 and cat ~= 4 then return end
    local mob = windower.ffxi.get_mob_by_id(act.actor_id)
    if not (mob and mob.is_npc and mob.spawn_type == 16) then return end
    if cat == 11 or cat == 4 then                                  -- (the move landed: back to your own set)
        if G.react and G.react.actor == act.actor_id then G.react = nil G.pending = true end
        return
    end
    if act.param == REACT_STOP then
        if G.react and G.react.actor == act.actor_id then G.react = nil G.pending = true end
        return
    end
    if act.param ~= REACT_BEGIN then return end
    local c = cfg.react
    if c.engaged and player and player.status ~= 'Engaged' then return end
    local t = act.targets and act.targets[1]
    local first = t and t.actions and t.actions[1]
    local id = first and first.param or 0
    local mine = t and t.id == me_id()
    local near = mob.distance and math.sqrt(mob.distance) <= (tonumber(c.range) or 8)
    if not (mine or (c.who == 'Any monster nearby' and near)) then return end
    local kind, name
    if cat == 7 then
        kind = G.MOVES and G.MOVES[id]
        name = res and res.monster_abilities and res.monster_abilities[id] and res.monster_abilities[id].en
    else
        kind = G.MOVE_SPELLS and G.MOVE_SPELLS[id]
        name = res and res.spells and res.spells[id] and res.spells[id].en
        if not kind and not react_own(name) then return end         -- (a spell: only the ones known to hurt, or your own list)
    end
    local g, which = react_gear(kind, name)
    if not g then return end
    G.react = { gear = g, actor = act.actor_id, ends = os.clock() + (tonumber(c.seconds) or 6) }
    G.pending = true
    if c.say then say((name or ('move ' .. id)) .. ': ' .. tostring(which)) end
end

local function on_action(act)
    if not on('th') or not act or act.actor_id ~= me_id() then return end
    for _, t in ipairs(act.targets or {}) do
        if t.id and not G.tagged[t.id] then
            G.tagged[t.id] = true
            G.ntagged = G.ntagged + 1
            if G.th_on and G.th_mode == 'Tag' then G.pending = true end
        end
    end
    if G.ntagged > 300 then G.tagged, G.ntagged = {}, 0 end
end

-- hook into GearSwap's events (your functions run first)
local function wrap(name, before, after)
    local orig = rawget(_G, name)
    if type(orig) ~= 'function' then orig = nil end
    G.orig[name] = orig
    _G[name] = function(...)
        if before and before(...) then return end
        if orig then orig(...) end
        if after then after(...) end
    end
end

function G.install()
    if G.installed then return end
    G.installed = true
    G.th_mode = (on('th') and cfg.th.mode) or 'Off'
    wrap('precast', G.pre, function(spell) G.heal_pre(spell) G.keep_tp(spell) G.moonshade(spell) G.obi(spell) G.song_gear(spell)
        if spell.action_type ~= 'Magic' and spell.action_type ~= 'Ranged Attack' then G.th_tag(spell) end
        G.overlay(true) end)
    wrap('midcast', nil, function(spell) G.mid(spell) G.heal_mid(spell) G.keep_tp(spell) G.song_gear(spell)
        if spell.action_type == 'Magic' then G.obi(spell) end
        if spell.action_type == 'Magic' or spell.action_type == 'Ranged Attack' then G.th_tag(spell) end
        G.overlay(true) end)
    wrap('aftercast', nil, function(spell) G.ammo(spell) G.tools_after(spell) G.overlay() G.box_update() end)
    wrap('status_change', nil, function() G.overlay() G.box_update() end)
    wrap('buff_change', nil, function(name, gain) G.buff(name, gain) G.overlay() end)
    -- //gs c gsd ... is ours; everything else goes to your self_command as before
    local orig_cmd = rawget(_G, 'self_command')
    if type(orig_cmd) ~= 'function' then orig_cmd = nil end
    G.orig.self_command = orig_cmd
    self_command = function(cmd, ...)
        local s = type(cmd) == 'table' and table.concat(cmd, ' ') or tostring(cmd or '')
        local w = {}
        for x in s:gmatch('%S+') do w[#w + 1] = x end
        if low(w[1]) == 'gsd' then
            G.command(w)
        elseif orig_cmd then
            orig_cmd(cmd, ...)
        end
        G.overlay()
    end
    wrap('file_unload', nil, function()
        for _, k in ipairs(G.binds) do send_command('unbind ' .. k) end
        pcall(G.fights_flush)
        if G.box and G.box.destroy then G.box:destroy() end
    end)
    if on('kiting') or on('lowhp') or on('refresh') or on('th') or on('aftermath') or on('haste') or on('fights') or on('tools') or on('acc') or on('warn') or on('react') then
        windower.raw_register_event('prerender', tick)
    end
    if on('tools') then windower.raw_register_event('outgoing text', function(o) pcall(tools_text, o) end) end
    if on('fights') then
        G.fights = {}
        windower.raw_register_event('action', function(act) pcall(on_fight, act) end)
    end
    if on('haste') then windower.raw_register_event('action', on_spell) end
    if on('warn') then windower.raw_register_event('action', function(act) pcall(warn_action, act) end) end
    if on('accession') and cfg.accession.chat ~= false then
        windower.raw_register_event('chat message', function(message, sender, mode) pcall(acc_chat, message, sender, mode) end)
        -- (his report 2026-11-15 "typing sneak, invis, deo does not work in the chat": the event above is only for what others say, so the line
        -- he types himself counts too - "/p sneak", or just "sneak" in whatever chat mode he is in. The line still goes out as he typed it.)
        windower.raw_register_event('outgoing text', function(original)
            pcall(function()
                local text = tostring(original or '')
                local said = text:match('^/p%s+(.+)$') or text:match('^/party%s+(.+)$') or (text:sub(1, 1) ~= '/' and text) or nil
                if said then acc_chat(said, nil, 4) end
            end)
        end)
    end
    if on('macro') then
        wrap('sub_job_change', nil, function() G.macro_set(1) end)
        G.macro_set(2)                       -- (after the file's own macro page, if it sets one)
    end
    if on('acc') then
        windower.raw_register_event('action', function(act) pcall(acc_action, act) end)
        windower.raw_register_event('incoming chunk', acc_chunk)
    end
    if on('th') then windower.raw_register_event('action', on_action) end
    if on('react') then windower.raw_register_event('action', function(act) pcall(G.react_action, act) end) end
    if on('th') or on('rings') then
        windower.raw_register_event('zone change', function()
            G.tagged, G.ntagged = {}, 0
            if next(G.locked) then G.unlock('zoned') end
        end)
    end
    local binds = type(cfg.binds) == 'table' and cfg.binds or {}
    for cmd, key in pairs(binds) do
        if type(key) == 'string' and key ~= '' then
            send_command('bind ' .. key .. ' gs c gsd ' .. cmd)
            G.binds[#G.binds + 1] = key
        end
    end
    if on('weapons') and cfg.weapons.start_locked then weapons_lock(true) end
    G.box_update()
end

-- after your get_sets (and Mote's / Selindrile's include that it loads)
local gsd_old_get_sets = rawget(_G, 'get_sets')
function get_sets()
    if type(gsd_old_get_sets) == 'function' then gsd_old_get_sets() end
    G.install()
end

-- A Selindrile "<Name>_<Job>_Gear.lua" file is read from INSIDE the job file's get_sets, so the get_sets above is never called again and nothing was
-- switched on (his report 2026-11-15: "i tried it on all characters, nothing worked at all"). So: a moment after this file is read, switch on if that
-- hasn't happened yet. By then the job file has finished setting up (its precast, midcast ... exist to run first).
if type(windower) == 'table' and windower.raw_register_event then
    local read_at = os.clock()
    windower.raw_register_event('prerender', function()
        if G.installed or os.clock() - read_at < 1 then return end
        local ok, err = pcall(G.install)
        if not ok then G.installed = true add_to_chat(28, 'GearSwap Doctor: the features could not start: ' .. tostring(err)) end
    end)
end

-- React: what kind of move each monster TP move (G.MOVES) and spell (G.MOVE_SPELLS) is - p physical, m magic, h both (breath and
-- hybrid), s an ailment (magic evasion / status resistance), e elemental (resistance). From the community Resistance_Sets.lua move table
-- (sets_against_actions / sets_against_spells) his BLU file uses.
G.MOVES = {
[257]='p',[264]='s',[266]='p',[270]='s',[271]='p',[273]='p',[279]='p',[287]='h',[292]='s',[295]='h',[297]='s',
[298]='e',[300]='s',[301]='s',[302]='s',[310]='s',[319]='s',[323]='h',[329]='s',[331]='e',[335]='h',[336]='p',
[338]='p',[345]='s',[346]='h',[353]='p',[360]='e',[364]='s',[372]='s',[377]='s',[378]='s',[386]='s',[388]='p',
[393]='s',[394]='m',[395]='p',[402]='h',[404]='p',[410]='s',[418]='h',[421]='m',[426]='s',[433]='m',[434]='s',
[437]='s',[448]='h',[452]='p',[461]='h',[462]='s',[466]='s',[475]='s',[476]='s',[483]='e',[485]='m',[489]='s',
[497]='s',[501]='s',[502]='s',[505]='s',[509]='e',[511]='e',[513]='p',[514]='s',[516]='s',[523]='s',[525]='h',
[528]='s',[530]='h',[535]='s',[549]='e',[555]='h',[560]='s',[565]='p',[566]='p',[569]='h',[571]='e',[572]='e',
[573]='e',[574]='e',[575]='e',[577]='s',[580]='h',[584]='p',[586]='s',[589]='s',[590]='p',[591]='e',[592]='e',
[597]='e',[600]='s',[609]='s',[612]='s',[617]='s',[622]='p',[629]='s',[634]='m',[635]='e',[638]='s',[643]='s',
[644]='e',[645]='p',[653]='s',[659]='s',[665]='h',[666]='p',[667]='p',[675]='p',[676]='s',[683]='p',[687]='s',
[727]='s',[741]='p',[742]='p',[743]='p',[777]='p',[778]='p',[779]='p',[785]='s',[791]='s',[792]='h',[800]='e',
[805]='s',[807]='h',[810]='p',[820]='e',[821]='s',[841]='e',[845]='e',[850]='e',[854]='e',[859]='e',[862]='s',
[863]='e',[868]='e',[870]='h',[872]='e',[877]='e',[879]='s',[881]='e',[886]='e',[890]='e',[892]='h',[901]='s',
[925]='h',[928]='s',[929]='e',[952]='p',[957]='s',[958]='s',[959]='p',[977]='h',[978]='h',[1035]='p',[1040]='p',
[1045]='s',[1046]='s',[1048]='s',[1050]='h',[1061]='s',[1068]='s',[1076]='s',[1081]='p',[1088]='p',[1089]='e',
[1090]='e',[1092]='p',[1137]='e',[1143]='h',[1146]='s',[1149]='p',[1150]='p',[1152]='s',[1169]='s',[1170]='e',
[1171]='p',[1179]='s',[1180]='e',[1181]='p',[1220]='s',[1230]='p',[1255]='h',[1275]='p',[1279]='s',[1280]='p',
[1281]='e',[1284]='s',[1285]='s',[1286]='s',[1290]='p',[1295]='s',[1296]='s',[1300]='p',[1305]='s',[1306]='s',
[1310]='p',[1315]='s',[1316]='s',[1352]='h',[1354]='e',[1358]='e',[1366]='s',[1384]='s',[1407]='p',[1412]='s',
[1413]='s',[1441]='s',[1446]='p',[1447]='p',[1456]='s',[1458]='e',[1459]='e',[1463]='h',[1470]='e',[1517]='p',
[1548]='s',[1556]='h',[1566]='h',[1567]='p',[1570]='h',[1572]='s',[1576]='p',[1582]='s',[1583]='h',[1584]='s',
[1585]='s',[1586]='s',[1593]='h',[1595]='s',[1602]='s',[1615]='s',[1618]='p',[1622]='s',[1628]='e',[1634]='s',
[1637]='p',[1640]='h',[1642]='s',[1643]='p',[1646]='s',[1649]='p',[1650]='s',[1660]='h',[1663]='m',[1666]='s',
[1667]='p',[1674]='h',[1675]='s',[1677]='s',[1678]='p',[1679]='p',[1685]='s',[1686]='s',[1691]='s',[1701]='s',
[1703]='h',[1707]='s',[1711]='p',[1713]='s',[1722]='h',[1724]='h',[1727]='s',[1733]='e',[1734]='h',[1744]='h',
[1745]='s',[1753]='p',[1758]='s',[1766]='p',[1771]='s',[1778]='p',[1782]='h',[1785]='e',[1786]='e',[1787]='p',
[1788]='s',[1790]='e',[1810]='s',[1817]='s',[1818]='p',[1821]='h',[1824]='p',[1829]='h',[1845]='p',[1848]='p',
[1851]='h',[1853]='e',[1855]='e',[1857]='e',[1862]='s',[1867]='p',[1875]='h',[1877]='m',[1882]='s',[1883]='s',
[1887]='s',[1897]='h',[1898]='s',[1923]='e',[1924]='h',[1952]='h',[1955]='h',[1958]='h',[1959]='s',[1963]='s',
[2024]='s',[2037]='h',[2040]='e',[2041]='h',[2045]='e',[2048]='e',[2051]='e',[2052]='h',[2054]='e',[2061]='h',
[2062]='h',[2073]='p',[2077]='h',[2078]='s',[2101]='s',[2106]='p',[2118]='s',[2153]='s',[2154]='p',[2161]='s',
[2163]='s',[2173]='h',[2174]='h',[2176]='p',[2178]='s',[2181]='s',[2185]='s',[2224]='s',[2229]='s',[2232]='s',
[2290]='h',[2291]='h',[2292]='h',[2293]='h',[2407]='e',[2421]='e',[2423]='h',[2431]='s',[2436]='s',[2562]='s',
[2564]='e',[2566]='s',[2568]='s',[2572]='s',[2603]='e',[2612]='h',[2613]='s',[2629]='s',[2631]='s',[2667]='h',
[2705]='h',[2735]='s',[2736]='e',[2737]='s',[2738]='s',[2739]='e',[2740]='s',[2741]='s',[2742]='s',[2765]='m',
[2814]='s',[2827]='s',[2828]='s',[2916]='p',[2930]='s',[2958]='h',[2967]='s',[2970]='s',[2974]='s',[2988]='p',
[2991]='s',[2994]='p',[3005]='s',[3014]='h',[3020]='s',[3030]='s',[3046]='s',[3059]='h',[3063]='e',[3072]='e',
[3099]='s',[3131]='p',[3137]='s',[3153]='h',[3242]='h',[3246]='s',[3261]='e',[3262]='p',[3304]='s',[3316]='p',
[3319]='s',[3330]='h',[3351]='s',[3354]='s',[3356]='p',[3358]='s',[3363]='s',[3372]='s',[3427]='s',[3433]='s',
[3448]='p',[3475]='h',[3521]='e',[3523]='s',[3524]='m',[3525]='m',[3526]='s',[3531]='s',[3548]='h',[3549]='h',
[3552]='s',[3584]='s',[3624]='h',[3691]='p',[3704]='s',[3730]='e',[3731]='e',[3765]='h',[3771]='s',[3772]='s',
[3777]='s',[3778]='s',[3783]='s',[3784]='s',[3785]='s',[3786]='e',[3787]='s',[3798]='s',[3800]='e',[3824]='s',
[3826]='s',[3840]='p',[3843]='s',[3844]='s',[3845]='s',[3848]='s',[3849]='p',[3850]='p',[3855]='s',[3860]='s',
[3865]='h',[3870]='s',[3875]='p',[3880]='s',[3885]='p',[3886]='s',[3889]='s',[3896]='s',[3898]='s',[3903]='h',
[3904]='s',[3905]='s',[3912]='e',[3914]='s',[3916]='s',[3918]='h',[3920]='h',[3929]='e',[3931]='p',[3936]='s',
[3939]='s',[3942]='p',[3949]='s',[3969]='s',[4033]='p',[4124]='e',[4125]='p',
}
G.MOVE_SPELLS = {
[1]='h',[2]='h',[3]='h',[4]='h',[5]='h',[6]='h',[7]='h',[8]='h',[9]='h',[10]='h',[11]='h',[12]='h',[13]='h',[14]='h',
[15]='h',[16]='s',[17]='h',[18]='h',[19]='h',[20]='h',[21]='e',[22]='e',[23]='s',[24]='s',[25]='s',[26]='s',[27]='s',
[28]='e',[29]='e',[30]='e',[31]='e',[32]='e',[33]='s',[34]='s',[35]='s',[36]='s',[37]='s',[38]='e',[39]='e',[40]='e',
[41]='e',[42]='e',[43]='h',[44]='h',[45]='h',[46]='h',[47]='h',[48]='h',[49]='h',[50]='h',[51]='h',[52]='h',[53]='h',
[54]='h',[55]='h',[56]='s',[57]='h',[58]='s',[59]='s',[60]='h',[61]='h',[62]='h',[63]='h',[64]='h',[65]='h',[66]='h',
[67]='h',[68]='h',[69]='h',[70]='h',[71]='h',[72]='h',[73]='h',[74]='h',[75]='h',[76]='h',[77]='h',[78]='h',[79]='s',
[80]='s',[81]='h',[82]='h',[83]='h',[84]='h',[85]='h',[86]='h',[87]='h',[88]='h',[89]='h',[90]='h',[91]='h',[92]='h',
[93]='h',[94]='h',[95]='h',[96]='h',[97]='h',[98]='s',[99]='h',[100]='h',[101]='h',[102]='h',[103]='h',[104]='h',
[105]='h',[106]='h',[107]='h',[108]='h',[109]='h',[110]='h',[111]='h',[112]='s',[113]='h',[114]='h',[115]='h',
[116]='h',[117]='h',[118]='h',[119]='h',[120]='h',[121]='h',[122]='h',[123]='h',[124]='h',[125]='h',[126]='h',
[127]='h',[128]='h',[129]='h',[130]='h',[131]='h',[132]='h',[133]='h',[134]='h',[135]='h',[136]='h',[137]='h',
[138]='h',[139]='h',[140]='h',[141]='h',[142]='h',[143]='h',[144]='e',[145]='e',[146]='e',[147]='e',[148]='e',
[149]='e',[150]='e',[151]='e',[152]='e',[153]='e',[154]='e',[155]='e',[156]='e',[157]='e',[158]='e',[159]='e',
[160]='e',[161]='e',[162]='e',[163]='e',[164]='e',[165]='e',[166]='e',[167]='e',[168]='e',[169]='e',[170]='e',
[171]='e',[172]='e',[173]='e',[174]='e',[175]='e',[176]='e',[177]='e',[178]='e',[179]='e',[180]='e',[181]='e',
[182]='e',[183]='e',[184]='e',[185]='e',[186]='e',[187]='e',[188]='e',[189]='e',[190]='e',[191]='e',[192]='e',
[193]='e',[194]='e',[195]='e',[196]='e',[197]='e',[198]='e',[199]='e',[200]='e',[201]='e',[202]='e',[203]='e',
[204]='e',[205]='e',[206]='e',[207]='e',[208]='e',[209]='e',[210]='e',[211]='e',[212]='e',[213]='e',[214]='e',
[215]='e',[216]='s',[217]='s',[218]='m',[219]='e',[220]='s',[221]='s',[222]='s',[223]='s',[224]='s',[225]='s',
[226]='s',[227]='s',[228]='s',[229]='s',[230]='s',[231]='s',[232]='s',[233]='s',[234]='s',[235]='s',[236]='s',
[237]='s',[238]='s',[239]='s',[240]='s',[241]='h',[242]='s',[243]='s',[244]='m',[245]='m',[246]='m',[247]='s',
[248]='s',[249]='h',[250]='h',[251]='h',[252]='s',[253]='s',[254]='s',[255]='s',[256]='s',[257]='s',[258]='s',
[259]='s',[260]='s',[261]='h',[262]='h',[263]='h',[264]='h',[265]='h',[266]='s',[267]='s',[268]='s',[269]='s',
[270]='s',[271]='s',[272]='s',[273]='s',[274]='s',[275]='s',[276]='s',[277]='h',[278]='s',[279]='s',[280]='s',
[281]='s',[282]='s',[283]='s',[284]='s',[285]='s',[286]='s',[287]='h',[288]='h',[289]='h',[290]='h',[291]='h',
[292]='h',[293]='h',[294]='h',[295]='h',[296]='h',[297]='h',[298]='h',[299]='h',[300]='h',[301]='h',[302]='h',
[303]='h',[304]='h',[305]='h',[306]='h',[307]='h',[308]='h',[309]='h',[310]='h',[311]='h',[312]='h',[313]='h',
[314]='h',[315]='h',[316]='h',[317]='h',[318]='h',[319]='s',[320]='e',[321]='e',[322]='e',[323]='e',[324]='e',
[325]='e',[326]='e',[327]='e',[328]='e',[329]='e',[330]='e',[331]='e',[332]='e',[333]='e',[334]='e',[335]='e',
[336]='e',[337]='e',[338]='h',[339]='h',[340]='h',[341]='s',[342]='s',[343]='s',[344]='s',[345]='s',[346]='s',
[347]='s',[348]='s',[349]='s',[350]='s',[351]='s',[352]='s',[353]='h',[354]='h',[355]='h',[356]='s',[357]='s',
[358]='h',[359]='s',[360]='s',[361]='s',[362]='s',[363]='s',[364]='s',[365]='s',[366]='s',[367]='s',[368]='s',
[369]='s',[370]='s',[371]='s',[372]='s',[373]='s',[374]='s',[375]='s',[376]='s',[377]='s',[378]='h',[379]='h',
[380]='h',[381]='h',[382]='h',[383]='h',[384]='h',[385]='h',[386]='h',[387]='h',[388]='h',[389]='h',[390]='h',
[391]='h',[392]='h',[393]='h',[394]='h',[395]='h',[396]='h',[397]='h',[398]='h',[399]='h',[400]='h',[401]='h',
[402]='h',[403]='h',[404]='h',[405]='h',[406]='h',[407]='h',[408]='h',[409]='h',[410]='h',[412]='h',[413]='h',
[414]='h',[415]='h',[416]='h',[417]='h',[418]='h',[419]='h',[420]='h',[421]='s',[422]='s',[423]='s',[424]='h',
[425]='h',[426]='h',[427]='h',[428]='h',[429]='h',[430]='h',[431]='h',[432]='h',[433]='h',[434]='h',[435]='h',
[436]='h',[437]='h',[438]='h',[439]='h',[440]='h',[441]='h',[442]='h',[443]='h',[444]='h',[445]='h',[446]='h',
[447]='h',[448]='h',[449]='h',[450]='h',[451]='h',[452]='h',[453]='h',[454]='s',[455]='s',[456]='s',[457]='s',
[458]='s',[459]='s',[460]='s',[461]='s',[462]='s',[463]='s',[464]='h',[465]='h',[466]='s',[467]='h',[468]='h',
[469]='h',[470]='h',[471]='s',[472]='s',[473]='h',[474]='h',[475]='h',[476]='h',[477]='h',[478]='h',[479]='h',
[480]='h',[481]='h',[482]='h',[483]='h',[484]='h',[485]='h',[486]='h',[487]='h',[488]='h',[489]='h',[490]='h',
[491]='h',[492]='h',[493]='h',[494]='h',[495]='h',[496]='e',[497]='e',[498]='e',[499]='e',[500]='e',[501]='e',
[502]='s',[503]='s',[504]='h',[505]='h',[506]='h',[507]='h',[508]='h',[509]='h',[510]='h',[511]='h',[512]='h',
[513]='s',[515]='s',[517]='h',[519]='p',[521]='m',[522]='s',[524]='s',[527]='p',[529]='p',[530]='h',[531]='s',
[532]='s',[533]='e',[534]='s',[535]='s',[536]='s',[537]='s',[538]='h',[539]='s',[540]='p',[541]='m',[542]='m',
[543]='p',[544]='s',[545]='p',[547]='h',[548]='s',[549]='h',[551]='p',[554]='p',[555]='s',[557]='e',[560]='p',
[561]='s',[563]='s',[564]='p',[565]='s',[567]='p',[569]='p',[570]='m',[572]='s',[573]='s',[574]='h',[575]='s',
[576]='s',[577]='p',[578]='h',[579]='s',[581]='h',[582]='s',[584]='s',[585]='p',[587]='p',[588]='s',[589]='p',
[591]='e',[592]='s',[593]='h',[594]='p',[595]='h',[596]='s',[597]='s',[598]='s',[599]='s',[603]='s',[604]='s',
[605]='s',[606]='s',[608]='s',[610]='s',[611]='s',[612]='s',[613]='h',[614]='h',[615]='e',[616]='s',[617]='p',
[618]='s',[620]='s',[621]='s',[622]='h',[623]='s',[626]='e',[628]='p',[629]='e',[631]='p',[632]='h',[633]='s',
[634]='s',[636]='h',[637]='e',[638]='s',[640]='s',[641]='p',[642]='h',[643]='p',[644]='s',[645]='h',[646]='h',
[647]='h',[648]='s',[649]='p',[650]='s',[651]='s',[652]='s',[653]='p',[654]='s',[655]='h',[656]='s',[657]='e',
[658]='h',[659]='s',[660]='s',[661]='h',[662]='h',[663]='e',[664]='h',[665]='p',[666]='p',[667]='p',[668]='h',
[669]='s',[670]='s',[671]='s',[672]='s',[673]='p',[674]='h',[675]='s',[676]='p',[677]='p',[678]='s',[679]='h',
[680]='e',[681]='h',[682]='p',[683]='m',[684]='s',[685]='h',[686]='s',[687]='s',[688]='p',[689]='e',[690]='h',
[691]='p',[692]='s',[693]='p',[694]='e',[695]='e',[696]='h',[697]='p',[698]='e',[699]='s',[700]='h',[701]='e',
[702]='h',[703]='s',[704]='s',[705]='s',[706]='p',[707]='s',[708]='s',[709]='p',[710]='h',[711]='h',[712]='e',
[713]='e',[714]='p',[715]='e',[716]='s',[717]='p',[718]='e',[719]='s',[720]='s',[721]='e',[722]='s',[723]='s',
[724]='h',[725]='e',[726]='s',[727]='s',[728]='s',[736]='s',[737]='h',[738]='s',[739]='e',[740]='s',[741]='h',
[742]='s',[743]='p',[744]='s',[745]='h',[746]='s',[747]='h',[748]='e',[749]='s',[750]='h',[751]='s',[752]='s',
[753]='s',[754]='p',[755]='p',[756]='p',[757]='p',[758]='p',[759]='p',[760]='p',[761]='p',[762]='p',[763]='p',
[764]='p',[765]='p',[766]='p',[767]='p',[768]='h',[769]='h',[770]='h',[771]='h',[772]='h',[773]='h',[774]='h',
[775]='h',[776]='h',[777]='h',[778]='h',[779]='h',[780]='h',[781]='h',[782]='h',[783]='h',[784]='h',[785]='h',
[786]='h',[787]='h',[788]='h',[789]='h',[790]='h',[791]='h',[792]='h',[793]='h',[794]='h',[795]='h',[796]='h',
[797]='h',[798]='h',[799]='h',[800]='h',[801]='h',[802]='h',[803]='h',[804]='h',[805]='h',[806]='h',[807]='h',
[808]='h',[809]='h',[810]='h',[811]='h',[812]='h',[813]='h',[814]='h',[815]='h',[816]='h',[817]='h',[818]='h',
[819]='h',[820]='h',[821]='h',[822]='h',[823]='h',[824]='h',[825]='h',[826]='h',[827]='h',[828]='e',[829]='e',
[830]='e',[831]='e',[832]='e',[833]='e',[834]='e',[835]='e',[836]='e',[837]='e',[838]='e',[839]='e',[840]='h',
[841]='s',[842]='s',[843]='s',[844]='s',[845]='h',[846]='h',[847]='h',[848]='h',[849]='e',[850]='e',[851]='e',
[852]='e',[853]='e',[854]='e',[855]='h',[856]='h',[857]='h',[858]='h',[859]='h',[860]='h',[861]='h',[862]='h',
[863]='h',[864]='h',[865]='e',[866]='e',[867]='e',[868]='e',[869]='e',[870]='e',[871]='s',[872]='s',[873]='s',
[874]='s',[875]='s',[876]='s',[877]='s',[878]='s',[879]='s',[880]='m',[881]='s',[882]='s',[883]='s',[884]='s',
[885]='s',[886]='s',[887]='s',[888]='s',[889]='s',[890]='s',[891]='s',[892]='s',[893]='h',[894]='h',[895]='h',
[896]='h',[897]='h',[898]='h',[899]='h',[900]='h',[901]='h',[902]='h',[903]='h',[904]='h',[905]='h',[906]='h',
[907]='h',[908]='h',[909]='h',[910]='h',[911]='h',[912]='h',[913]='h',[914]='h',[915]='h',[916]='h',[917]='h',
[918]='h',[919]='h',[920]='h',[921]='h',[922]='h',[923]='h',[924]='h',[925]='h',[926]='h',[927]='h',[928]='h',
[929]='h',[930]='h',[931]='h',[932]='h',[933]='h',[934]='h',[935]='h',[936]='h',[937]='h',[938]='h',[939]='h',
[940]='h',[941]='h',[942]='h',[943]='h',[944]='h',[945]='h',[946]='h',[947]='h',[948]='h',[949]='h',[950]='h',
[951]='h',[952]='h',[953]='h',[954]='h',[955]='h',[956]='h',[957]='h',[958]='h',[959]='h',[960]='h',[961]='h',
[962]='h',[963]='h',[964]='h',[965]='h',[966]='h',[967]='h',[968]='s',[969]='h',[970]='h',[971]='h',[972]='h',
[973]='h',[974]='h',[975]='h',[976]='h',[977]='h',[978]='h',[979]='h',[980]='h',[981]='h',[982]='h',[983]='h',
[984]='h',[985]='h',[986]='h',[987]='h',[988]='h',[989]='h',[990]='h',[991]='h',[992]='h',[993]='h',[994]='h',
[995]='h',[996]='h',[997]='h',[998]='h',[1004]='h',[1005]='h',[1006]='h',[1007]='h',[1008]='h',[1009]='h',[1010]='h',
[1011]='h',[1012]='h',[1013]='h',[1014]='h',[1015]='h',[1016]='h',[1017]='h',[1018]='h',[1019]='h',
}
