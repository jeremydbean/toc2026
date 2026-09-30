-- Drive the package's behaviour against a stubbed Mudlet API.
--
-- The package is written for globals Mudlet provides (send, cecho,
-- tempTimer, the mapper functions), so the harness supplies a
-- permissive stand-in for anything it does not care about and real
-- recording versions of the three that matter: what was sent, what
-- was echoed, and what timer was armed.
--
-- Run as: lua tests/mudlet_ui_spec.lua <path to extracted package lua>
-- tests/test_mudlet_assets.py extracts the script and calls this.

local target = arg and arg[1]
if not target then
  io.stderr:write("usage: mudlet_walk_spec.lua <package.lua>\n")
  os.exit(2)
end

-- A value that can be called, indexed, and compared without blowing
-- up, so tocMudlet.install() can run its UI construction against
-- nothing at all and still reach the bottom of the file.
local function permissive()
  local t = {}
  return setmetatable(t, {
    __index = function() return permissive() end,
    __call = function() return permissive() end,
  })
end

local sent, echoed, timers = {}, {}, {}

setmetatable(_G, {
  __index = function(t, k)
    local v = permissive()
    rawset(t, k, v)
    return v
  end,
})

send = function(command) sent[#sent + 1] = command end
cecho = function(text) echoed[#echoed + 1] = text end
tempTimer = function(_, fn) timers[#timers + 1] = fn; return #timers end
killTimer = function(id) timers[id] = false; return true end
roomExists = function() return true end
gotoRoom = function() end
gmcp = { Char = {}, Room = {} }

-- install() at the bottom of the package builds a UI; it may well
-- fail against stubs, and it does not matter. Everything under test
-- is defined above that call.
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

local function reset()
  sent, echoed, timers = {}, {}, {}
  if tocMudlet.walk.active then tocMudlet.walkCommand("stop") end
  sent, echoed, timers = {}, {}, {}
end

local function startWalk(dirs, rooms)
  reset()
  speedWalkDir, speedWalkPath = dirs, rooms
  doSpeedWalk()
end

-- ------------------------------------------------ one step per arrival
startWalk({ "n", "e", "e", "u" }, { 100, 101, 102, 103 })
check("the first step goes out at once", sent[1] == "north", sent[1])
check("and only the first", #sent == 1, #sent)

tocMudlet.onWalkArrival(100)
check("arriving sends the next step", sent[2] == "east", sent[2])
tocMudlet.onWalkArrival(101)
tocMudlet.onWalkArrival(102)
check("short names become long ones", sent[4] == "up", sent[4])

tocMudlet.onWalkArrival(103)
check("the last arrival sends nothing more", #sent == 4, #sent)
check("and the walk is over", tocMudlet.walk.active == false)

-- ------------------------------------------------ pushed off the route
startWalk({ "n", "e" }, { 200, 201 })
tocMudlet.onWalkArrival(999)
check("a room off the route stops the walk",
  tocMudlet.walk.active == false)
check("and sends nothing further", #sent == 1, #sent)

-- ------------------------------------------------ a special exit
startWalk({ "enter portal" }, { 300 })
check("a special exit is sent as it stands",
  sent[1] == "enter portal", sent[1])

-- ------------------------------------------------ a shut door
startWalk({ "n", "e" }, { 400, 401 })
local armed = timers[#timers]
check("a step arms a watchdog", type(armed) == "function")
armed()
check("the watchdog tries the door", sent[2] == "open north", sent[2])
check("and repeats the step", sent[3] == "north", sent[3])
check("the walk is still going", tocMudlet.walk.active == true)

local again = timers[#timers]
again()
check("a second failure gives up", tocMudlet.walk.active == false)
check("without sending anything more", #sent == 3, #sent)

-- ------------------------------------------------ nowhere to go
reset()
speedWalkDir, speedWalkPath = {}, {}
doSpeedWalk()
check("an empty route walks nowhere", #sent == 0, #sent)
check("and says so", (echoed[1] or ""):match("No route") ~= nil, echoed[1])

-- ------------------------------------------------ stopping by hand
startWalk({ "n", "n", "n" }, { 500, 501, 502 })
tocMudlet.walkCommand("stop")
check("walk stop ends it", tocMudlet.walk.active == false)
tocMudlet.onWalkArrival(500)
check("and a late arrival does not restart it", #sent == 1, #sent)

-- ------------------------------------------------ a door on the way
-- Room.Info said the door north is shut, so it should be opened
-- before walking into it rather than after a four second timeout.
tocMudlet.lastExits = { doors = { n = "closed" } }
startWalk({ "n", "e" }, { 600, 601 })
check("a door known to be shut is opened first",
  sent[1] == "open north", sent[1])
check("and then walked through", sent[2] == "north", sent[2])

tocMudlet.lastExits = { doors = { n = "open" } }
startWalk({ "n" }, { 700 })
check("an open door is not opened again", sent[1] == "north", sent[1])
tocMudlet.lastExits = nil

-- ------------------------------------------------ the chat window
local chat = {}
tocMudlet.ui.chat = { decho = function(_, line) chat[#chat + 1] = line end }

gmcp.Comm = { Channel = { channel = "gossip", speaker = "Alaric",
                          text = "hello", time = 0 } }
tocMudlet.onChannel()
check("a channel line reaches the chat window", #chat == 1, #chat)
check("naming who said it", (chat[1] or ""):find("Alaric") ~= nil, chat[1])
check("in a colour tag decho can read, decimal and not hex",
  (chat[1] or ""):match("<%d+,%d+,%d+>") ~= nil, chat[1])

gmcp.Comm.Channel = { channel = "tell", speaker = "",
                      text = "You tell Bob 'hi'", time = 0 }
tocMudlet.onChannel()
check("a tell carries its own wording",
  (chat[2] or ""):find("You tell Bob") ~= nil, chat[2])

-- ------------------------------------------------ the affects panel
local shown = {}
tocMudlet.ui.affects = { echo = function(_, text) shown[#shown + 1] = text end }
gmcp.Char = { Affects = { affects = {
  { name = "armor", duration = 40 },
  { name = "bless", duration = 3 },
  { name = "shadowmeld", duration = -1 },
} } }
tocMudlet.onAffects()

local panel = shown[#shown] or ""
check("every affect is listed",
  panel:find("bless") and panel:find("armor") and panel:find("shadowmeld"),
  panel)
check("the one about to lapse is first",
  (panel:find("bless") or 0) < (panel:find("armor") or 0), panel)
check("one that never lapses is last",
  (panel:find("shadowmeld") or 0) > (panel:find("armor") or 0), panel)

gmcp.Char.Affects = { affects = {} }
tocMudlet.onAffects()
check("an empty list says so",
  (shown[#shown] or ""):find("No spells") ~= nil, shown[#shown])

print(failures == 0 and "ALL PASS" or (failures .. " FAILED"))
os.exit(failures == 0 and 0 or 1)
