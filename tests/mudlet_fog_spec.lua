-- The fog on the Mudlet map (Map.Known), against a fake mapper.
--
-- The package hides every room the character does not know by taking it
-- off the map and keeping it aside, and puts it back -- where the atlas
-- had it, linked both ways -- when the game says it is known. The fake
-- here keeps rooms, areas, coordinates and exits the way Mudlet does,
-- deleteRoom included: removing a room removes every exit into it.
--
-- Run as: lua tests/mudlet_fog_spec.lua <path to extracted package lua>
-- tests/test_mudlet_assets.py extracts the script and calls this.

local target = arg and arg[1]
if not target then
  io.stderr:write("usage: mudlet_fog_spec.lua <package.lua>\n")
  os.exit(2)
end

local function permissive()
  local t = {}
  return setmetatable(t, {
    __index = function() return permissive() end,
    __call = function() return permissive() end,
  })
end

setmetatable(_G, {
  __index = function(t, k)
    local v = permissive()
    rawset(t, k, v)
    return v
  end,
})

local LONG = { n = "north", e = "east", s = "south", w = "west", u = "up",
  d = "down", ne = "northeast", nw = "northwest", se = "southeast", sw = "southwest" }
local SHORT = {}
for short, long in pairs(LONG) do SHORT[long] = short end

-- The fake mapper. Its rules are Mudlet's own, read from its source
-- (src/TLuaInterpreterMapper.cpp, TRoom.cpp, TRoomDB.cpp and TMap.cpp on
-- the development branch, 2026-11-12):
--   * getRoomExits names exits "north" ... "down"; setExit and setExitStub
--     take "n" or "north", "u" or "up" (dirToNumber).
--   * Doors are keyed "n" ... "nw", "up", "down", "in", "out"
--     (dirCodeToShortString). setDoor refuses "u" and "d" (read as a
--     special exit the room lacks) and any direction with neither an exit
--     nor a stub, answering nil and a message; state 0 removes the door.
--   * deleteRoom removes every exit into the room and, unless the entering
--     room has a stub there, the door on that exit (removeExitExtras).
--   * setExitStub(id, dir, true) changes nothing where an exit already is.
--   * addAreaName refuses a name already used; getRoomAreaName answers -1
--     and a message for an unknown area id; getRoomCoordinates answers
--     nils for a room that is not there.
local rooms, areas, areaNames, nextArea = {}, {}, {}, 1
local timers = {}
local saved = {}

local DOOR_DIRECTION = { n = "n", e = "e", s = "s", w = "w", ne = "ne", nw = "nw",
  se = "se", sw = "sw", up = "u", down = "d" }
local DOOR_OF = { u = "up", d = "down" }

local function short(direction)
  direction = tostring(direction):lower()
  if direction == "up" then return "u" end
  if direction == "down" then return "d" end
  return SHORT[direction] or direction
end
local function doorOf(direction) return DOOR_OF[direction] or direction end

function roomExists(id) return rooms[tonumber(id)] ~= nil end
function addRoom(id)
  id = tonumber(id)
  if rooms[id] then return false end
  rooms[id] = { exits = {}, doors = {}, stubs = {}, x = 0, y = 0, z = 0, area = -1,
    name = "", env = 201 }
  return true
end
function deleteRoom(id)
  id = tonumber(id)
  if not id or id <= 0 or not rooms[id] then return nil, "invalid room id" end
  rooms[id] = nil
  for _, room in pairs(rooms) do
    for direction, to in pairs(room.exits) do
      if to == id then
        room.exits[direction] = nil
        if not room.stubs[direction] then room.doors[doorOf(direction)] = nil end
      end
    end
  end
  return true
end
function getRooms()
  local out = {}
  for id, room in pairs(rooms) do out[id] = room.name end
  return out
end
function getRoomExits(id)
  local out = {}
  for direction, to in pairs(rooms[id] and rooms[id].exits or {}) do out[LONG[direction]] = to end
  return out
end
function setExit(from, to, direction)
  from, to = tonumber(from), tonumber(to)
  if not rooms[from] then return false end
  if to < 1 then rooms[from].exits[short(direction)] = nil return true end
  if not rooms[to] then return false end
  rooms[from].exits[short(direction)] = to
  return true
end
function setExitStub(id, direction, status)
  local room = rooms[tonumber(id)]
  if not room then error("setExitStub: roomId doesn't exist") end
  direction = short(direction)
  if status then
    if room.exits[direction] then return end -- Mudlet logs it and changes nothing
    room.stubs[direction] = true
  else
    room.stubs[direction] = nil
  end
end
function getRoomCoordinates(id)
  local r = rooms[id]
  if not r then return nil, nil, nil end
  return r.x, r.y, r.z
end
function setRoomCoordinates(id, x, y, z) local r = rooms[id] r.x, r.y, r.z = x, y, z end
function getAreaTable() return areas end
function addAreaName(name)
  if areas[name] then return nil, "area names may not be duplicated" end
  areas[name] = nextArea
  areaNames[nextArea] = name
  nextArea = nextArea + 1
  return areas[name]
end
function setRoomArea(id, area) rooms[id].area = area end
function getRoomArea(id) return rooms[id] and rooms[id].area or nil end
function getRoomAreaName(area)
  if areaNames[area] then return areaNames[area] end
  return -1, "not a valid area id"
end
function setRoomName(id, name) rooms[id].name = name end
function getRoomName(id) return rooms[id].name end
function setRoomEnv(id, env) rooms[id].env = env end
function getRoomEnv(id) return rooms[id].env end
function setRoomChar(id, mark) rooms[id].char = mark end
function getRoomChar(id) return rooms[id].char or "" end
function setDoor(id, key, state)
  local room = rooms[tonumber(id)]
  if not room then return nil, "invalid room id" end
  local direction = DOOR_DIRECTION[key]
  if not direction then return nil, "no special exit '" .. tostring(key) .. "'" end
  if not room.exits[direction] and not room.stubs[direction] then
    return nil, "no normal exit or stub exit in direction '" .. key .. "'"
  end
  state = tonumber(state)
  if not state or state < 0 or state > 3 then return nil, "bad door type" end
  if state == 0 then
    local had = room.doors[key] ~= nil
    room.doors[key] = nil
    return had
  end
  room.doors[key] = state
  return true
end
function getDoors(id)
  local out = {}
  for key, state in pairs(rooms[id] and rooms[id].doors or {}) do out[key] = state end
  return out
end
function updateMap() end
function centerview() end
function tempTimer(_, fn) timers[#timers + 1] = fn return #timers end
function killTimer() return true end
function cecho() end
function send() end
function getMudletHomeDir() return "/nonexistent-toc-fog-spec" end
table.save = function(path, t)
  local function copy(v)
    if type(v) ~= "table" then return v end
    local c = {}
    for k, x in pairs(v) do c[k] = copy(x) end
    return c
  end
  saved[path] = copy(t)
end
table.load = function() end
gmcp = { Char = {}, Room = {} }
yajl = { to_value = function(value) return value end }
tocMudlet = { handlers = {}, ui = {} }

-- Mudlet 5's setConfig: "showUpperLowerLevels" takes a boolean
-- (TLuaInterpreter::setConfig, development and Mudlet-5.1.1).
local config = {}
function setConfig(key, value)
  if key ~= "showUpperLowerLevels" or type(value) ~= "boolean" then
    return nil, "not a valid configuration option"
  end
  config[key] = value
  return true
end
local userData = {}
function setMapUserData(key, value) userData[key] = value return true end
function getMapUserData(key) return userData[key] end

pcall(assert(loadfile(target)))
local levelsAtInstall = config.showUpperLowerLevels

local failures = 0
local function check(name, ok, detail)
  if ok then
    print("  ok   " .. name)
  else
    failures = failures + 1
    print("  FAIL " .. name .. (detail and ("  -- " .. tostring(detail)) or ""))
  end
end

-- The atlas: area A is rooms 1-6 in a line, 1 north to 2 north to 3, then
-- east 4, 5, 6; area B is room 10, up from 3. Every exit has its way back.
local function atlas()
  rooms, areas, areaNames, nextArea = {}, {}, {}, 1
  local a, b = addAreaName("Area A"), addAreaName("Area B")
  local spots = { [1] = {0, 0}, [2] = {0, 1}, [3] = {0, 2}, [4] = {1, 2}, [5] = {2, 2}, [6] = {3, 2} }
  for id, xy in pairs(spots) do
    addRoom(id) setRoomArea(id, a) setRoomCoordinates(id, xy[1], xy[2], 0)
    setRoomName(id, "Room " .. id) setRoomEnv(id, 203)
  end
  addRoom(10) setRoomArea(10, b) setRoomCoordinates(10, 5, 5, 1) setRoomName(10, "Tower")
  local function link(x, dir, y, back) setExit(x, y, dir) setExit(y, x, back) end
  link(1, "n", 2, "s") link(2, "n", 3, "s") link(3, "e", 4, "w")
  link(4, "e", 5, "w") link(5, "e", 6, "w") link(3, "u", 10, "d")
  assert(setDoor(5, "e", 2))
  assert(setDoor(2, "n", 2))
  assert(setDoor(10, "down", 3))
  assert(setDoor(3, "up", 1))
  assert(setDoor(3, "u", 1) == nil, "the fake must refuse a door keyed u, as Mudlet does")
  setRoomChar(6, "$")
  tocMudlet.fog = {}
  tocMudlet.known, tocMudlet.knownAll, tocMudlet.walked = nil, false, {}
end

local function known(parts)
  for index, part in ipairs(parts) do
    gmcp.Map = { Known = { part = index, parts = #parts, all = part.all == true, rooms = part.rooms or {} } }
    tocMudlet.onMapKnown()
  end
end

local function present(...)
  for _, id in ipairs({...}) do if not rooms[id] then return false, id end end
  return true
end
local function absent(...)
  for _, id in ipairs({...}) do if rooms[id] then return false, id end end
  return true
end

atlas()
-- install() armed timers of its own against stubs; only the fog's are run.
timers = {}
tocMudlet.fogSaveTimer = nil

-- Nothing happens before the last part.
gmcp.Map = { Known = { part = 1, parts = 2, all = false, rooms = { {1, 2} } } }
tocMudlet.onMapKnown()
check("a part before the last changes nothing", present(1, 2, 3, 4, 5, 6, 10))
gmcp.Map = { Known = { part = 2, parts = 2, all = false, rooms = { {10, 10} } } }
tocMudlet.onMapKnown()
check("known rooms stay", present(1, 2, 10))
check("unknown rooms leave the map", absent(3, 4, 5, 6))
check("they are kept aside", tocMudlet.fog[3] and tocMudlet.fog[6] and not tocMudlet.fog[1])
check("an exit into the fog goes with it", rooms[2].exits.n == nil and rooms[10].exits.d == nil)
check("a room left on the map keeps a stub there", rooms[2].stubs.n and rooms[10].stubs.d)
check("and the door on it", rooms[2].doors.n == 2 and rooms[10].doors.down == 3,
  tostring(rooms[2].doors.n) .. "/" .. tostring(rooms[10].doors.down))
check("a fogged room's doors are kept, whichever room went first",
  tocMudlet.fog[5] and tocMudlet.fog[5].doors and tocMudlet.fog[5].doors.e == 2
  and tocMudlet.fog[3].doors and tocMudlet.fog[3].doors.up == 1)
check("the fog is kept aside to be saved", #timers > 0)
for _, fn in ipairs(timers) do if fn then fn() end end
check("and saved in the profile", saved["/nonexistent-toc-fog-spec/toc-fog.lua"] ~= nil
  and saved["/nonexistent-toc-fog-spec/toc-fog.lua"][4] ~= nil)

-- A step into a fogged room brings it back, where the atlas put it.
gmcp.Room = { Info = { num = 4, name = "Room 4", area = "Area A", environment = "field",
  exits = { w = 3, e = 5 } } }
tocMudlet.onRoomInfo()
check("the room walked into is back", rooms[4] ~= nil)
check("at its atlas square", rooms[4] and rooms[4].x == 1 and rooms[4].y == 2)
check("in its own area", rooms[4] and rooms[4].area == areas["Area A"])
check("its neighbours stay in the fog", absent(3, 5))
check("a walked room is known", tocMudlet.isKnown(4))

-- A map learned: the next Map.Known holds the whole area.
known({ { rooms = { {1, 6}, {10, 10} } } })
check("every room of the area is back", present(1, 2, 3, 4, 5, 6, 10))
check("exits are linked both ways again",
  rooms[2].exits.n == 3 and rooms[3].exits.s == 2 and rooms[3].exits.e == 4
  and rooms[4].exits.w == 3 and rooms[4].exits.e == 5 and rooms[5].exits.w == 4
  and rooms[5].exits.e == 6 and rooms[6].exits.w == 5 and rooms[3].exits.u == 10
  and rooms[10].exits.d == 3)
check("names and marks come back", rooms[6].name == "Room 6" and rooms[6].char == "$")
check("doors come back", rooms[5].doors.e == 2)
check("doors on both ends of a link come back",
  rooms[2].doors.n == 2 and rooms[10].doors.down == 3 and rooms[3].doors.up == 1)
local stubbed = nil
for id, room in pairs(rooms) do if next(room.stubs) then stubbed = id end end
check("no stub is left where a room came back", stubbed == nil, stubbed)
check("nothing is left aside", next(tocMudlet.fog) == nil)

-- Fogged in two passes, revealed in the other order: still linked.
known({ { rooms = { {1, 2} } } })
check("a second fog", absent(3, 4, 5, 6, 10))
gmcp.Room = { Info = { num = 5, name = "Room 5", area = "Area A", environment = "field", exits = {} } }
tocMudlet.onRoomInfo()
known({ { rooms = { {1, 3}, {5, 5} } } })
check("3 back, 4 still fogged", present(3, 5) and absent(4))
known({ { rooms = { {1, 6} } } })
check("4 between them links to both", rooms[4] and rooms[4].exits.w == 3 and rooms[4].exits.e == 5
  and rooms[3].exits.e == 4 and rooms[5].exits.w == 4)

-- Staff know everything.
known({ { rooms = { {1, 1} } } })
check("fogged again", absent(2, 3, 10))
known({ { all = true } })
check("all brings everything back", present(1, 2, 3, 4, 5, 6, 10))

-- A Hyrule plan room in the fog comes back through Hyrule.MapRoom.
known({ { rooms = { {1, 2} } } })
gmcp.Hyrule = { MapRoom = { num = 6, level = 1, name = "Room 6", area = "Area A",
  environment = "inside", x = 3, y = 2, z = 0, exits = {} } }
tocMudlet.onMapRoom()
check("a dungeon plan room leaves the fog", rooms[6] ~= nil and tocMudlet.fog[6] == nil)

-- A whole new map (TOCGUI ATLAS) starts the fog again from it.
atlas()
tocMudlet.known = { {1, 2} }
tocMudlet.fog = { [99] = { exits = {}, incoming = {} } }
tocMudlet.onMapReplaced()
check("the old fog is dropped", tocMudlet.fog[99] == nil)
check("the new map is fogged", absent(3, 4, 5, 6, 10) and present(1, 2))

-- A map taken away (staff GRANTMAP ... REVOKE): the next Map.Known is
-- smaller, and the rooms no longer known leave the map again.
atlas()
known({ { rooms = { {1, 6}, {10, 10} } } })
check("a whole area known", present(1, 2, 3, 4, 5, 6, 10))
known({ { rooms = { {1, 3} } } })
check("a map taken away fogs its rooms", present(1, 2, 3) and absent(4, 5, 6, 10))
check("with stubs where they were",
  rooms[3].stubs.e and rooms[3].stubs.u and rooms[3].doors.up == 1)

-- Room.Info's doors are "u" and "d"; Mudlet's are "up" and "down".
atlas()
tocMudlet.lastRoom, tocMudlet.lastExits = nil, nil
known({ { all = true } })
gmcp.Room = { Info = { num = 3, name = "Room 3", area = "Area A", environment = "field",
  exits = { s = 2, e = 4, u = 10 }, doors = { u = "locked", e = "closed" } } }
tocMudlet.onRoomInfo()
check("an up door from Room.Info is drawn", rooms[3].doors.up == 3, tostring(rooms[3].doors.up))
check("an east door from Room.Info is drawn", rooms[3].doors.e == 2)

-- Map.Known before any part 1 is ignored, not half-applied.
atlas()
tocMudlet.knownPending = nil
gmcp.Map = { Known = { part = 2, parts = 2, all = false, rooms = { {1, 1} } } }
tocMudlet.onMapKnown()
check("a stray last part does nothing", present(1, 2, 3, 4, 5, 6, 10))

-- Owner, 2026-11-12: "the way the layers look on the map in mudlet is
-- disorienting". A room the atlas laid out stays in its area, whatever
-- name Room.Info gives the game's area (a seasonal copy renames it).
atlas()
known({ { all = true } })
gmcp.Room = { Info = { num = 4, name = "Room 4", area = "Area A (Halloween)",
  environment = "field", exits = { w = 3, e = 5 } } }
tocMudlet.onRoomInfo()
check("an atlas room keeps its area", rooms[4].area == areas["Area A"],
  tostring(rooms[4].area))
check("and its square", rooms[4].x == 1 and rooms[4].y == 2 and rooms[4].z == 0)

-- A Hyrule dungeon room walked into goes to its dungeon's own area, on
-- its floor plan square -- and one an older package drew under the
-- overworld is moved there on the next step into it.
local eagle = "Hyrule: Level 1 (The Eagle)"
gmcp.Room = { Info = { num = 30401, name = "Level 1: Eagle Gate", area = "Area A",
  environment = "underground", exits = { u = 6 },
  map = { area = eagle, x = 2, y = 0, z = 0 } } }
tocMudlet.lastRoom, tocMudlet.lastExits = 6, { exits = { d = 30401 } }
tocMudlet.onRoomInfo()
check("a dungeon room has its own area", rooms[30401] and rooms[30401].area == areas[eagle]
  and rooms[30401].area ~= areas["Area A"])
check("at its plan square", rooms[30401].x == 2 and rooms[30401].y == 0 and rooms[30401].z == 0,
  rooms[30401].x .. "," .. rooms[30401].y .. "," .. rooms[30401].z)
setRoomArea(30401, areas["Area A"]) setRoomCoordinates(30401, 3, 2, -1)
tocMudlet.onRoomInfo()
check("a dungeon room drawn under the overworld is put right",
  rooms[30401].area == areas[eagle] and rooms[30401].x == 2 and rooms[30401].z == 0)

-- Its map's plan lands on the same squares: the floor on z 0, a cellar on
-- z -1, in the same area -- no ten-levels-down offset any more.
gmcp.Hyrule = { MapRoom = { num = 30417, level = 1, name = "Level 1: Undercroft",
  area = eagle, environment = "underground", x = 1, y = -5, z = -1, exits = {} } }
tocMudlet.onMapRoom()
check("a cellar is a level below its floor, in the dungeon's area",
  rooms[30417] and rooms[30417].area == areas[eagle] and rooms[30417].z == -1)
gmcp.Hyrule = { MapRoom = { num = 30402, level = 1, name = "Level 1: Room",
  area = "Killum Hyrule", environment = "underground", x = 3, y = 0, z = 0, exits = {} } }
tocMudlet.onMapRoom()
check("an older server's plan keeps the old offset", rooms[30402] and rooms[30402].z == -10)

-- The levels above and below are not drawn unless the player asks.
check("install turns Mudlet's upper/lower levels off", levelsAtInstall == false,
  tostring(levelsAtInstall))
tocMudlet.toggleLevels()
check("tocgui levels turns them on", config.showUpperLowerLevels == true)
check("and the choice is kept", saved["/nonexistent-toc-fog-spec/toc-settings.lua"]
  and saved["/nonexistent-toc-fog-spec/toc-settings.lua"].showLevels == true)
tocMudlet.toggleLevels()
check("and off again", config.showUpperLowerLevels == false)

-- A profile holding the old layout is told once; one that loaded the new
-- atlas is not.
tocMudlet.atlasLayoutNoted = nil
userData = {}
local told = 0
cecho = function(text) if text:find("tocgui atlas", 1, true) then told = told + 1 end end
tocMudlet.noteAtlasLayout() tocMudlet.noteAtlasLayout()
check("an old layout is noted once a session", told == 1, told)
tocMudlet.atlasLayoutNoted = nil
told = 0
tocMudlet.onMapReplaced()
tocMudlet.noteAtlasLayout()
check("the new atlas is not", told == 0 and userData.tocAtlasLayout == tocMudlet.ATLAS_LAYOUT)
cecho = function() end

if failures > 0 then
  print(failures .. " FAILED")
  os.exit(1)
end
print("ALL PASS")
