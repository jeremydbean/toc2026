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

-- The package opens with `tocMudlet = tocMudlet or {}`, which reads
-- the global before assigning it. Left to the metatable above, that
-- read returns a stub, the stub is truthy, and the package adopts it
-- as its own table -- after which every tocMudlet.x is another stub.
-- Hand it a plain table to find.
tocMudlet = { handlers = {}, ui = {} }

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

-- The pane filters now, and the Chat tab leaves tells out, so the
-- tell has to be asked for by tab rather than assumed.
gmcp.Comm.Channel = { channel = "tell", speaker = "",
                      text = "You tell Bob 'hi'", time = 0 }
tocMudlet.onChannel()
check("a tell is not in the Chat tab",
  (chat[2] or ""):find("You tell Bob") == nil, chat[2])
check("but it is kept", #tocMudlet.chatLog >= 2, #tocMudlet.chatLog)

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

-- ------------------------------------------------ a console stub
local function console()
  local lines = {}
  return {
    lines = lines,
    clear = function() for i = #lines, 1, -1 do lines[i] = nil end end,
    decho = function(_, line) lines[#lines + 1] = line end,
    echo = function(_, line) lines[#lines + 1] = line end,
    show = function(self) self.shown = true end,
    hide = function(self) self.shown = false end,
    setStyleSheet = function() end,
    setClickCallback = function(self, fn) self.click = fn end,
  }
end

local function text(pane)
  return table.concat(pane.lines, "")
end

-- ------------------------------------------------ the quest panel
tocMudlet.ui.quest = console()
gmcp.Char = gmcp.Char or {}

gmcp.Char.Quest = { active = false, wait = 7 }
tocMudlet.onQuest()
check("a waiting quest says how long", text(tocMudlet.ui.quest):find("7 min") ~= nil,
  text(tocMudlet.ui.quest))

tocMudlet.ui.quest = console()
gmcp.Char.Quest = { active = true, kind = "emergency", countdown = 1,
                    target = "a cooshee", kill = true }
tocMudlet.onQuest()
local questText = text(tocMudlet.ui.quest)
check("an emergency says so", questText:find("EMERGENCY") ~= nil, questText)
check("and names the target", questText:find("cooshee") ~= nil, questText)
check("and says Kill for a kill quest", questText:find("Kill") ~= nil, questText)

-- ------------------------------------------------ the target strip
tocMudlet.ui.target = console()
gmcp.Char.Target = { fighting = false }
tocMudlet.onTarget()
check("not fighting says so",
  text(tocMudlet.ui.target):find("Not fighting") ~= nil,
  text(tocMudlet.ui.target))

tocMudlet.ui.target = console()
gmcp.Char.Target = { fighting = true, name = "a fido", percent = 30 }
tocMudlet.onTarget()
local targetText = text(tocMudlet.ui.target)
check("a target is named", targetText:find("fido") ~= nil, targetText)
check("with its percentage", targetText:find("30%%") ~= nil, targetText)

-- ------------------------------------------------ who is here
tocMudlet.ui.here = console()
gmcp.Room = gmcp.Room or {}
gmcp.Room.Chars = { chars = {} }
tocMudlet.onChars()
check("an empty room says so",
  text(tocMudlet.ui.here):find("Nobody else") ~= nil, text(tocMudlet.ui.here))

tocMudlet.ui.here = console()
gmcp.Room.Chars = { chars = {
  { name = "a guard", npc = true, aggressive = true },
  { name = "Alaric", npc = false },
} }
tocMudlet.onChars()
local hereText = text(tocMudlet.ui.here)
check("everyone is listed",
  hereText:find("guard") and hereText:find("Alaric"), hereText)
check("an aggressive is marked", hereText:find("aggressive") ~= nil, hereText)

-- ------------------------------------------------ carried and worn
tocMudlet.ui.items = console()
gmcp.Char.Items = {
  equipment = { { name = "a sub issue sword", slot = 16 } },
  inventory = { { name = "a loaf of bread" } },
}
tocMudlet.onItems()
local itemText = text(tocMudlet.ui.items)
check("the wear slot is named", itemText:find("wielded") ~= nil, itemText)
check("carried items are listed", itemText:find("bread") ~= nil, itemText)

-- ------------------------------------------------ the toast
tocMudlet.ui.toast = console()
gmcp.Char.Achievement = { title = "Rush Delivery", description = "Fast.",
                          points = 15 }
tocMudlet.onAchievement()
check("an achievement is shown", tocMudlet.ui.toast.shown == true)
check("with its title",
  text(tocMudlet.ui.toast):find("Rush Delivery") ~= nil,
  text(tocMudlet.ui.toast))

-- ------------------------------------------------ clickable exits
tocMudlet.exitButtons = {}
for i = 1, 10 do tocMudlet.exitButtons[i] = console() end
tocMudlet.showExits({ n = 100, e = 101 })
check("one button per exit",
  tocMudlet.exitButtons[1].shown == true
    and tocMudlet.exitButtons[2].shown == true
    and tocMudlet.exitButtons[3].shown == false)
check("a button walks that way", type(tocMudlet.exitButtons[1].click) == "function")

sent = {}
tocMudlet.exitButtons[1].click()
check("and sends the long direction", sent[1] == "north", sent[1])

tocMudlet.showExits({})
check("a room with no exits shows no buttons",
  tocMudlet.exitButtons[1].shown == false)

-- ------------------------------------------------ the chat tabs
tocMudlet.chatLog = {}
tocMudlet.ui.chat = console()
tocMudlet.ui.here = console()
tocMudlet.ui.items = console()
tocMudlet.ui.tabs = {}

gmcp.Comm = { Channel = { channel = "gossip", speaker = "A", text = "one",
                          time = 0 } }
tocMudlet.onChannel()
gmcp.Comm.Channel = { channel = "tell", speaker = "", text = "two", time = 0 }
tocMudlet.onChannel()

tocMudlet.showPane("tells")
local tellsOnly = text(tocMudlet.ui.chat)
check("the Tells tab shows only tells",
  tellsOnly:find("two") ~= nil and tellsOnly:find("one") == nil, tellsOnly)

tocMudlet.showPane("chat")
local chatOnly = text(tocMudlet.ui.chat)
check("the Chat tab leaves tells out",
  chatOnly:find("one") ~= nil and chatOnly:find("two") == nil, chatOnly)

tocMudlet.showPane("here")
check("the Here tab swaps the console",
  tocMudlet.ui.here.shown == true and tocMudlet.ui.chat.shown == false)

print(failures == 0 and "ALL PASS" or (failures .. " FAILED"))
os.exit(failures == 0 and 0 or 1)
