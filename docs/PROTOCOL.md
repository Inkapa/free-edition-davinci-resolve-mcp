# Bridge protocol (0.3): Python server and the Lua script inside DaVinci Resolve

The request payload and the response envelope are version 1, as upstream. Release 0.3.0 of this
fork changed how a request reaches the bridge: one Lua file run with `fu:RunScript` instead of a
folder of hex-named folders read with `GetSubFolderList`. Server and bridge must come from the same
release; the server checks the `bridge` field of `CMCP_Session` and refuses a mismatch.

Both sides derive every path from `HOME`:

```
STATE_DIR = ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/ClaudeMCP
INBOX     = STATE_DIR/inbox
REQUEST   = INBOX/request.lua
PREFS     = ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Profiles/*/Fusion.prefs  (newest)
```

On Windows (no `HOME`; the installer stamps the state directory into the bridge) the same layout
sits under Resolve's per-user support folder:

```
STATE_DIR = %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\ClaudeMCP
PREFS     = %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Profiles\*\Fusion.prefs  (newest)
```

The Lua side cannot read or write files (no `io`, and on 21.2 free no `loadfile`, `dofile` or
`fusion:SavePrefs` either). It can (a) test file existence (`bmd.fileexists`), (b) run a Lua file
with `fu:RunScript(path)`, whose script shares the in-memory prefs (`fu:SetPrefs` / `fu:GetPrefs`)
with the bridge, and (c) persist strings with `fu:SetData(key, value)`, which rewrites
`Fusion.prefs` synchronously. Everything below follows from that.

## Request (server → bridge): one Lua file

1. `id` = 6–32 chars of `[a-z0-9]`, unique per request (`<base36 time><random>`).
2. `payload` = UTF-8 bytes of a **Lua table literal without `return`**, e.g.
   `{ v = 1, id = "k3f9x2a1", ts = 1793437964, op = "run", timeout = 30, max_kb = 64,
      code = [==[ return resolve:GetVersionString() ]==], args = { name = "Timeline 1" } }`
   Strings use long brackets `[=*[ ... ]=*]` with a level that does not occur in the content;
   numbers are plain; booleans `true/false`; JSON arrays become `{a, b}`; JSON objects become
   `{ ["key"] = value }`; `null` becomes `nil` (omitted).
3. Server writes `REQUEST.tmp` with one line,
   `fu:SetPrefs("Global.ClaudeMCP.Request", "<id>:<lowercase hex of payload>")`, then renames it
   to `REQUEST` (atomic). The string holds only `[a-z0-9:]`, so it needs no escaping.
4. One request in flight at a time across every server process on the machine: each server takes an
   exclusive lock on `STATE_DIR/lock` for the whole request (`flock` on macOS, `msvcrt.locking` on
   Windows; several Claude Code sessions share one bridge). Max payload 256 KB.
5. After reading the response the server deletes `REQUEST`. On Windows a replace or delete that
   meets `RunScript` reading the file is retried for up to a second.

Ops: `ping` (no code) · `run` (`code` required; `args` optional table) · `stop`.

## Bridge loop (inside Resolve, script thread)

At start the bridge reads the id of a request file already present and marks it seen without
running it: a request posted to a previous bridge instance (restart or take-over) times out on the
server side instead of executing twice. The bridge refuses to parse or run anything if `setfenv` is
unavailable.

```
every TICK (5 ms):
  every 100 ms: if GetData("ClaudeMCP.CMCP_Stop") ~= "" or GetData("ClaudeMCP.CMCP_Owner") ~= session → exit
  if bmd.fileexists(REQUEST):
    SetPrefs(KEY, "") ; RunScript(REQUEST) ; poll GetPrefs(KEY) every 1 ms, up to 2 s ; SetPrefs(KEY, "")
    split "<id>:<hex>" ; skip if id not id-shaped or already seen
    payload = hexdecode(hex) ; req = loadstring("return " .. payload) with empty env
    validate v==1, id matches, |os.time()-ts| ≤ 120, op known, code string ≤ 256 KB
    execute (see below) ; respond ; seen[id]=true
  every 15 s: SetData("ClaudeMCP.CMCP_Beat", os.time()); 10 s after a response: SetData("ClaudeMCP.CMCP_Resp", "")
  if REQUEST holds an id already seen for more than 5 checks in a row: re-read it only 4x per second
```

`KEY` is `Global.ClaudeMCP.Request`. It is cleared right after reading so the next `SetData`, which
saves every pref to disk, never writes a request into `Fusion.prefs`. An already-seen request file
is normal for a check or two after each answer, until the server deletes it.

Execution of `run`: `fn = loadstring(code, "=claude")`, `setfenv(fn, env)` where `env` has
`print` (captured), `resolve`, `fusion`, `fu`, `app`, `bmd`, `args`, plus fresh helpers
`project` (current project or nil), `timeline` (current timeline or nil), `mediaPool`,
`projectManager`, and `__index = _G`. `xpcall(fn)`; first return value is the result.

## Response (bridge → server): one SetData

`fu:SetData("ClaudeMCP.CMCP_Resp", id .. ":" .. hex(json))` where `json` is

```
{"v":1,"id":"…","session":"…","op":"run","ok":true,"ms":12,
 "result":<json>,"error":null,"prints":["…"],"truncated":false,"result_bytes":123,"bridge":"0.2.0"}
```

JSON encoding of Lua values: `nil`→`null`; tables with keys exactly `1..n` → arrays; other tables →
objects with string keys (numeric keys stringified); userdata → `"<object …>"`; cycles → `"<cycle>"`;
depth > 16 → `"<depth>"`. Result capped at `max_kb` KB (default 64, ceiling 256): over the cap the
result becomes a string preview and `truncated=true`, `result_bytes` = full size.

Other keys (same `ClaudeMCP.*` namespace in `Fusion.prefs` under `Global.Script.GlobalData`):

| key | writer | value |
|---|---|---|
| `CMCP_Session` | bridge at start/stop | hex(json `{v,session,pid,started,state:"running"|"stopped",product,version,bridge}`) |
| `CMCP_Owner` | bridge at start | session id — a second start takes over; the old loop exits |
| `CMCP_Beat` | bridge every 15 s idle | unix seconds |
| `CMCP_Stop` | stop script | `"1"`; bridge clears it on exit |

## Server wait

After writing `REQUEST`, the server polls `PREFS` every 5 ms (stat first; parse on change) for
`CMCP_Resp = "<id>:<hex>"` whose id matches, decodes hex → JSON, then deletes `REQUEST`. Timeout
(default 30 s, per-call) → error; the file is still deleted. On startup the server removes inbox
entries older than 5 minutes under the lock (a request file, or folders and `PENDING` left by a 0.2
server). On Windows the server opens `Fusion.prefs` with delete sharing, so a poll never makes
Resolve's save of the file fail.
On exit the bridge clears `CMCP_Resp`, except the acknowledgement of an `op=stop` request. Liveness:
`CMCP_Session.state == "running"`, `CMCP_Session.bridge` equal to the server's version, and
(`CMCP_Beat` within 45 s or a 3 s `ping` succeeds); the bridge's `pid` must be a live process.

## Why these constants

Measured on Windows with free 21.2.0.6: `fu:RunScript` returns in about 0.4 ms and the pref it sets
is readable about 2 ms later, `SetData` takes about 6 ms, `bmd.fileexists` about 30 µs and `GetData`
about 0.1 ms. A request costs the wait for the next tick, one `RunScript` and one `SetData`. The 0.2
channel needed two `GetSubFolderList` calls per request instead, at about 18 ms each whatever the
folder held. With `TICK` 5 ms an idle tick is one `fileexists`; the two `GetData` calls for stop and
take-over run every 100 ms. Measured round trip for a small request: median 22 ms, p99 44 ms over 300
calls (upstream's channel: median 84 ms, 107 ms back to back). While Resolve's main thread is busy
with UI work, calls can take two or three times as long. Stale window 120 s guards against replaying a request left by a crashed
server.
