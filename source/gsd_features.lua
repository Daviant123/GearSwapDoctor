--[[ GearSwap Doctor features (gsd-features.lua) - written by GearSwap Doctor, version 2.

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
local G = { version = 2, cfg = cfg, orig = {}, tagged = {}, ntagged = 0, moving = false, still = 0, last = nil,
            low_hp = false, low_mp = false, locked = {}, skip = {}, binds = {}, pending = false, t = 0,
            dt = false, rr = false, wlock = false, th_mode = 'Off', th_on = false, ammo_warned = nil }
gsd = G

local function on(k) return type(cfg[k]) == 'table' and cfg[k].on == true end
local function low(s) return type(s) == 'string' and s:lower() or '' end
local function say(msg) add_to_chat(207, 'GearSwap Doctor: ' .. msg) end
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

-- gear worn on top of whatever your file put on (after aftercast / status / buff / commands)
function G.overlay(casting)
    local st = player and player.status
    if not casting then
        G.th_on = false
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
    else
        say('commands (//gs c gsd ...):')
        for _, h in ipairs(HELP) do add_to_chat(207, '   ' .. h) end
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
    add_to_chat(167, 'GearSwap Doctor: Afflatus Solace is not on')
end

-- what happens before your own precast: Echo Drops when silenced, cancel Sneak for Spectral Jig
function G.pre(spell)
    if on('silence') and spell.action_type == 'Magic' and buff('silence') then
        cancel_spell()
        local item = cfg.silence.item or 'Echo Drops'
        send_command('input /item "' .. item .. '" <me>')
        say('silenced: using ' .. item)
        return true
    end
    if on('cancel') and cfg.cancel.jig and spell.english == 'Spectral Jig' and buff('sneak') then
        send_command('cancel 71')
    end
    if G.cure_down(spell) then return true end
    G.solace(spell)
    return false
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
        add_to_chat(167, 'GearSwap Doctor: ' .. a .. ' - only ' .. n .. ' left!')
    end
end

-- buffs: doom message / Holy Water, rings unlock when the experience ring's buff lands
function G.buff(name, gain)
    local n = low(name)
    if on('doom') and gain and (n == 'doom' or (cfg.doom.curse and n == 'curse')) then
        if type(cfg.doom.say) == 'string' and cfg.doom.say ~= '' then send_command('input /p ' .. cfg.doom.say) end
        if cfg.doom.holy then send_command('input /item "Holy Water" <me>') end
    end
    if gain and (n == 'dedication' or n == 'commitment') and next(G.locked) then G.unlock('ring used') end
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
    if G.pending and (status == 0 or status == 1) and not (midaction and midaction()) then
        G.pending = false
        send_command('gs c gsd refresh')
    end
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
    wrap('precast', G.pre, function(spell) G.heal_pre(spell) G.keep_tp(spell) G.moonshade(spell) G.obi(spell)
        if spell.action_type ~= 'Magic' and spell.action_type ~= 'Ranged Attack' then G.th_tag(spell) end
        G.overlay(true) end)
    wrap('midcast', nil, function(spell) G.mid(spell) G.heal_mid(spell) G.keep_tp(spell)
        if spell.action_type == 'Magic' then G.obi(spell) end
        if spell.action_type == 'Magic' or spell.action_type == 'Ranged Attack' then G.th_tag(spell) end
        G.overlay(true) end)
    wrap('aftercast', nil, function(spell) G.ammo(spell) G.overlay() G.box_update() end)
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
        if G.box and G.box.destroy then G.box:destroy() end
    end)
    if on('kiting') or on('lowhp') or on('refresh') or on('th') then
        windower.raw_register_event('prerender', tick)
    end
    if on('th') then windower.raw_register_event('action', on_action) end
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
