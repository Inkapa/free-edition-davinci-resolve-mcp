-- Offline harness: runs bridge/Claude_MCP_Bridge.lua against fake resolve/fusion objects.
-- usage: fuscript -l lua tests/lua_harness.lua <state_dir> <prefs_file> <max_ticks> <bridge_path>
local state_dir, prefs_file, max_ticks, bridge_path = arg[1], arg[2], arg[3], arg[4]

local PREFIX = "ClaudeMCP."
local WINDOWS = package.config:sub(1, 1) == "\\"
local store, order = {}, {}

local function write_prefs()
  local lines = { "{", "\tGlobal = {", "\t\tScript = {", "\t\t\tGlobalData = {", "\t\t\t\tClaudeMCP = {" }
  for _, k in ipairs(order) do
    lines[#lines + 1] = "\t\t\t\t\t" .. k .. ' = "' .. store[k] .. '",'
  end
  lines[#lines + 1] = "\t\t\t\t}"
  lines[#lines + 1] = "\t\t\t}"
  lines[#lines + 1] = "\t\t}"
  lines[#lines + 1] = "\t}"
  lines[#lines + 1] = "}"
  -- Windows cannot rename onto a file another process has open, so write in place there;
  -- the server re-reads whenever the file's signature changes.
  local target = WINDOWS and prefs_file or (prefs_file .. ".tmp")
  local fh = assert(io.open(target, "w"))
  fh:write(table.concat(lines, "\n"), "\n")
  fh:close()
  if not WINDOWS then assert(os.rename(target, prefs_file)) end
end

local FU = {}
function FU.SetData(self, key, value)
  local short = tostring(key):gsub("^" .. PREFIX:gsub("%.", "%%."), "")
  if store[short] == nil then order[#order + 1] = short end
  store[short] = tostring(value)
  write_prefs()
end
function FU.GetData(self, key)
  local short = tostring(key):gsub("^" .. PREFIX:gsub("%.", "%%."), "")
  return store[short]
end

-- In-memory prefs, which Resolve shares between the bridge and the scripts it runs.
local mem_prefs = {}
function FU.SetPrefs(self, key, value) mem_prefs[key] = value end
function FU.GetPrefs(self, key) return mem_prefs[key] end
-- Resolve queues the file on its script executor; running it at once is the same as far as the
-- bridge can tell, since it polls GetPrefs either way.
function FU.RunScript(self, path)
  local chunk = loadfile(path)
  if not chunk then return end
  setfenv(chunk, { fu = FU })
  pcall(chunk)
end

local timeline = { GetName = function() return "Timeline 1" end }
local project = {
  GetName = function() return "Fake Project" end,
  GetTimelineCount = function() return 1 end,
  GetCurrentTimeline = function() return timeline end,
  GetMediaPool = function() return {} end,
}
local project_manager = { GetCurrentProject = function() return project end }
local fake_resolve = {
  GetProductName = function() return "DaVinci Resolve" end,
  GetVersionString = function() return "21.1.2.10" end,
  GetCurrentPage = function() return "edit" end,
  GetProjectManager = function() return project_manager end,
}

write_prefs()

-- fuscript runs the main chunk in a private environment; the bridge reads the real _G.
rawset(_G, "CMCP_CONFIG", { state_dir = state_dir, resolve = fake_resolve, fusion = FU, tick = 0.01, max_ticks = tonumber(max_ticks) })

local r1, r2 = dofile(bridge_path)
print(tostring(r1))
if r2 ~= nil then print(tostring(r2)) end
