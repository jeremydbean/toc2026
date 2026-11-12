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

-- The fake mapper.
local rooms, areas, areaNames, nextArea = {}, {}, {}, 1
local timers = {}
local saved = {}

local function short(direction) return SHORT[direction] or direction end

function roomExists(id) return rooms[tonumber(id)] ~= nil end
function addRoom(id)
  id = tonumber(id)
  if rooms[id] then return false end
  rooms[id] = { exits = {}, doors = {}, x = 0, y = 0, z = 0, area = -1, name = "", env = 201 }
  return true
end
function deleteRoom(id)
  id = tonumber(id)
  if not rooms[id] then return false end
  rooms[id] = nil
  for _, room in pairs(rooms) do
    for direction, to in pairs(room.exits) do
      if to == id then room.exits[direction] = nil end
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
  if to == -1 then rooms[from].exits[short(direction)] = nil return true end
  if not rooms[to] then return false end
  rooms[from].exits[short(direction)] = to
  return true
end
function setExitStub() end
function getRoomCoordinates(id) local r = rooms[id] return r.x, r.y, r.z end
function setRoomCoordinates(id, x, y, z) local r = rooms[id] r.x, r.y, r.z = x, y, z end
function getAreaTable() return areas end
function addAreaName(name)
  areas[name] = nextArea
  areaNames[nextArea] = name
  nextArea = nextArea + 1
  return areas[name]
end
function setRoomArea(id, area) rooms[id].area = area end
function getRoomArea(id) return rooms[id].area end
function getRoomAreaName(area) return areaNames[area] end
function setRoomName(id, name) rooms[id].name = name end
function getRoomName(id) return rooms[id].name end
function setRoomEnv(id, env) rooms[id].env = env end
function getRoomEnv(id) return rooms[id].env end
function setRoomChar(id, mark) rooms[id].char = mark end
function getRoomChar(id) return rooms[id].char or "" end
function setDoor(id, direction, state) rooms[id].doors[short(direction)] = state end
function getDoors(id) return rooms[id].doors end
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

pcall(assert(loadfile(target)))

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
  setDoor(5, "e", 2)
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

-- Map.Known before any part 1 is ignored, not half-applied.
atlas()
tocMudlet.knownPending = nil
gmcp.Map = { Known = { part = 2, parts = 2, all = false, rooms = { {1, 1} } } }
tocMudlet.onMapKnown()
check("a stray last part does nothing", present(1, 2, 3, 4, 5, 6, 10))

if failures > 0 then
  print(failures .. " FAILED")
  os.exit(1)
end
print("ALL PASS")
