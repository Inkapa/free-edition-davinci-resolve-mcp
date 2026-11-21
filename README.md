# davinci-resolve-mcp (Windows fork)

Let Claude Code drive the free edition of DaVinci Resolve 21.1 and 21.2 on Windows, as well as on macOS.

This is a fork of [kingjamesch/davinci-resolve-mcp](https://github.com/kingjamesch/davinci-resolve-mcp), which only runs on macOS. It keeps upstream's 33 tools, request payload and response channel, adds Windows support, and replaces the way requests reach Resolve with a faster one. Use the server and the bridge from the same release: the server refuses a bridge from another release and tells you to reinstall.

## Who this is for

You use the free edition of DaVinci Resolve 21.1 or later on Windows and want Claude Code to control it.

Since 21.1, the free edition no longer lists Python scripts in Workspace > Scripts and refuses external scripting connections, so Python-based Resolve MCP servers cannot reach it. On 21.2 the free edition also dropped `loadfile`, `dofile`, `fusion:SavePrefs` and `fusion:LoadPrefs` from the Lua sandbox, which breaks the bridges that read requests or write answers with them. What still works on free 21.2 is running a Lua file with `fu:RunScript`, sharing in-memory prefs with it, and writing answers with `fu:SetData`, which saves `Fusion.prefs`. This fork runs on those three calls.

If you have Resolve Studio, Blackmagic's own MCP server and the Python-based servers already work and you do not need this.

## What this fork changes

- Requests reach Resolve as one file, `inbox/request.lua`, which the bridge runs with `fu:RunScript`. Upstream hex-encodes each request into folder names and reads them with two `MediaStorage:GetSubFolderList` calls, which cost about 18 ms each on Windows. Answers still go through `fu:SetData`.
- The bridge checks for a request every 5 ms instead of 30 ms (one `bmd.fileexists`, about 30 µs) and checks for stop or take-over every 100 ms. The server polls for the answer every 5 ms instead of 15 ms.
- The server checks the bridge's version and refuses a bridge from another release, instead of timing out.
- Every per-platform path (Resolve's support folder, `Fusion.prefs`, the Scripts folder, the scripting docs, the Claude Desktop config, `fuscript`) lives in `davinci_mcp/paths.py`, with Windows and macOS values.
- The cross-process request lock uses `msvcrt` on Windows instead of `flock`.
- The bridge liveness check asks the Windows process table for Resolve's pid. `os.kill(pid, 0)` would send Ctrl+C on Windows.
- `Fusion.prefs` is read with delete sharing on Windows, so a poll never makes Resolve's save of the file fail.
- `resolve_status` finds Resolve with `tasklist` on Windows.
- The installer registers the Python that runs it, and calls the `claude` CLI by its full path (it is a `.cmd` shim on Windows).
- The Lua bridge builds its paths with backslashes when the stamped state directory is a Windows path, and falls back to `%APPDATA%` when `HOME` is unset.
- The tests run on Windows: Lua paths use forward slashes, POSIX mode checks are skipped, and the offline harness fakes `RunScript` and the in-memory prefs.

Measured on Windows 11 with DaVinci Resolve 21.2.0.6 free and Python 3.13. The new request channel has not been tried on macOS yet; if `fu:RunScript` is missing there, use upstream on macOS.

## How it works in short

Resolve 21.1 free removed Python scripts from the Workspace > Scripts menu and blocks external scripting. Lua menu scripts still run. This project uses that gap. A Lua bridge runs inside Resolve and a tiny Python MCP server runs outside. The server sends Lua to the bridge, the bridge runs it against the live `resolve` object and sends the answer back. A small call takes about 20 to 30 ms (measured on Windows with free 21.2, median 22 ms; upstream's channel took 70 to 110 ms on the same machine), and a 200 KB request about 80 ms. There are 33 tools, plus `run_lua` for anything the named tools do not cover.

## Requirements

- macOS, Windows 10/11, or Linux with X11
- DaVinci Resolve 21.1.2 or 21.2, free or Studio (Windows measured on free 21.2.0.6)
- Claude Code
- Python 3.9 or newer: `/usr/bin/python3` on macOS; on Windows, whichever Python runs the installer
- No pip installs. The server uses the standard library only.

## Install on Windows

```powershell
git clone https://github.com/Inkapa/free-edition-davinci-resolve-mcp.git
cd free-edition-davinci-resolve-mcp
python install.py
```

The installer does the same four things as on macOS (below), with these paths, and also sets up the bridge autostart (next section):

- Lua scripts: `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\`
- State directory: `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\ClaudeMCP`
- Responses are read from `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Profiles\<profile>\Fusion.prefs`
- The Claude Code registration uses the Python that ran `install.py`.

`--check`, `--uninstall`, `--purge` and `--claude-desktop` work the same way. The plugin install below is macOS only.

## Bridge autostart (Windows and Linux)

The free edition runs nothing at launch: it ignores `.scriptlib` files and refuses external scripting. Without help, the bridge needs a click in Workspace > Scripts after every Resolve launch. So on Windows and Linux the installer also starts a small watcher at login. When a Resolve with a project open has never started the bridge, the watcher opens Workspace > Scripts > Claude_MCP_Bridge itself. A bridge you stop with Claude_MCP_Bridge_Stop stays stopped until Resolve restarts. The watcher logs to `autostart.log` in the state directory. Pass `--no-autostart` to skip it; `--uninstall` removes it.

- **Windows:** the scheduled task "davinci-resolve-mcp bridge autostart" runs `scripts\autostart_bridge.ps1` at logon. It reaches the menu through Windows UI Automation.
- **Linux (X11):** `~/.config/autostart/davinci-resolve-mcp-bridge.desktop` runs `scripts/autostart_bridge.py` with the desktop session (GNOME, KDE, or i3 with `dex --autostart`). Resolve's bundled Qt does not publish its menus over AT-SPI, so the watcher uses `xdotool`: it finds the Workspace title in a screenshot of the window, clicks it, then presses Up, Right and Return. That runs the first script in the Scripts menu, which is Claude_MCP_Bridge unless you have another script whose name sorts before it. It needs `xdotool`, ImageMagick's `import`, and Python's Pillow and numpy; the installer says which are missing. Wayland sessions are not supported.

## Install on Linux

```bash
git clone https://github.com/Inkapa/free-edition-davinci-resolve-mcp.git
cd free-edition-davinci-resolve-mcp
python3 install.py
```

Resolve is looked for in `/opt/resolve` (Blackmagic's installer and the AUR package; set `RESOLVE_INSTALL_DIR` otherwise). Its per-user folder is `~/.local/share/DaVinciResolve` (or `$XDG_DATA_HOME/DaVinciResolve`), which holds `Fusion/Scripts/Utility/`, `Fusion/Profiles/<profile>/Fusion.prefs` and the `ClaudeMCP` state directory. The bridge needs Resolve's Fusion scripting to start: if Resolve's log (`~/.local/share/DaVinciResolve/logs/ResolveDebug.txt`) says "Fusion DoAction ... ignored, init not completed", Lua menu scripts do not run and the bridge cannot either.

## Install on macOS

```bash
git clone https://github.com/Inkapa/davinci-resolve-mcp.git
cd davinci-resolve-mcp
./install.sh
```

The installer does four things:

1. Copies the two Lua scripts into `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`. It stamps the state directory path into the bridge.
2. Creates the state directory `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/ClaudeMCP` with mode 0700.
3. Registers the server with Claude Code at user scope as `davinci`.
4. Prints the next steps.

Next steps, as the installer prints them:

```
NEXT STEPS
1) Quit and reopen DaVinci Resolve once (it scans the Scripts menu only at startup).
2) In Resolve: Workspace > Scripts > Claude_MCP_Bridge (do this once per Resolve session; Claude_MCP_Bridge_Stop stops it).
3) In Claude Code run /mcp and check that 'davinci' is connected, then ask for resolve_status.
```

The Resolve restart is needed once, after the first install. Resolve only reads the Scripts folder at startup.

Other flags:

| Flag | Effect |
|---|---|
| `--claude-desktop` | Also adds `davinci` to the Claude Desktop config. Optional. An existing config is backed up first. |
| `--no-claude` | Skip the Claude Code registration. |
| `--check` | Report what is installed. |
| `--uninstall` | Remove the Lua scripts and the Claude Code registration. Add `--purge` to delete the state directory too. `./uninstall.sh` does the same. |

## Install as a Claude Code plugin (macOS)

If you only use Claude Code on macOS, skip the clone. Inside Claude Code:

```
/plugin marketplace add Inkapa/davinci-resolve-mcp
/plugin install davinci-resolve@davinci-resolve-mcp
/davinci-resolve:setup
```

The plugin registers the `davinci` server itself; `/davinci-resolve:setup` copies the two Lua
scripts into Resolve's Scripts folder. Then restart Resolve once and click Workspace > Scripts >
Claude_MCP_Bridge. The plugin also ships a `resolve` skill with the conventions Claude needs
(absolute frames, marker rules, Lua idioms, Studio-only traps).

Use either the plugin or `./install.sh`, not both, or Claude Code sees two `davinci` servers
(`claude mcp remove davinci -s user` removes the clone-based one).

Upstream is listed on the [MCP Registry](https://registry.modelcontextprotocol.io/v0.1/servers?search=davinci-resolve-mcp)
as `io.github.kingjamesch/davinci-resolve-mcp`. That listing installs upstream, not this fork, and the
two are not interchangeable: a 0.2 bridge and a 0.3 server cannot talk to each other.

## Daily use

1. Open Resolve with a project.
2. On Windows and Linux the autostart watcher starts the bridge within about 15 s. On macOS, or if you installed with `--no-autostart`, click Workspace > Scripts > Claude_MCP_Bridge once per Resolve session.
3. In Claude Code, ask for `resolve_status` first. It tells you whether the bridge is alive.
4. To stop the bridge, click Workspace > Scripts > Claude_MCP_Bridge_Stop.

Example prompts:

- "Call resolve_status, then list my timelines."
- "Add a red marker named 'fix audio' at 00:00:10:00 on the current timeline."
- "Import everything in /Users/me/Footage/day1 and make a timeline called Day 1 from it."
- "Queue an mp4 render of the current timeline into /Users/me/Exports, start it and tell me when it finishes."
- "Use run_lua to list the clip colors on video track 1."

## Tools

The full reference, with every argument, is in [docs/TOOLS.md](docs/TOOLS.md). It is generated from the code.

- **Status and project:** `resolve_status`, `list_projects`, `get_project_info`, `get_project_setting`, `open_project`, `save_project`, `set_project_setting`, `open_page`
- **Timelines:** `list_timelines`, `get_timeline_info`, `get_timeline_items`, `get_timeline_markers`, `set_current_timeline`, `set_timecode`, `create_timeline`, `add_marker`, `delete_markers`, `insert_timeline_element`, `delete_timeline_items`, `export_timeline`
- **Media pool:** `list_media_pool`, `get_clip_properties`, `create_media_pool_folder`, `import_media`, `append_clips_to_timeline`
- **Render:** `get_render_status`, `list_render_options`, `add_render_job`, `start_render`, `stop_render`, `delete_render_job`
- **Escape hatch:** `run_lua` runs any Lua 5.1 chunk inside Resolve. `scripting_api_docs` searches Blackmagic's shipped API reference so Claude can write that Lua correctly.

Conventions: paths are absolute, frames are integers in the timeline's own numbering, timecodes are `HH:MM:SS:FF`, and track and item indexes start at 1.

## How it works

- Claude Code starts `server.py` over stdio. The server speaks MCP and holds no network socket.
- To send a request, the server writes `inbox/request.lua` under the state directory. The file holds one line that stores the hex-encoded request in an in-memory Fusion pref.
- The Lua bridge checks for that file every 5 ms, runs it with `fu:RunScript`, reads the request from the pref, and runs it with the `resolve` object bound.
- The bridge returns the answer with `fu:SetData`, which Resolve writes to `Fusion.prefs`. The server polls that file.
- The last response stays in `Fusion.prefs` and is cleared about 10 seconds after it was written; the bridge also clears it when it stops.
- Several Claude Code sessions can share one Resolve: every server takes a lock in the state directory, so requests run one at a time.

The wire format is in [docs/PROTOCOL.md](docs/PROTOCOL.md). The design record is in [docs/MCP-RECORD.md](docs/MCP-RECORD.md).

## Troubleshooting

- **Tools say the bridge is not running.** Open Resolve with a project and click Workspace > Scripts > Claude_MCP_Bridge, then retry.
- **Workspace > Scripts shows no Claude_MCP_Bridge.** Resolve was not restarted after the install. Quit and reopen it. Run `./install.sh --check` to confirm the files are in place.
- **A tool times out.** Resolve is probably showing a dialog, such as the Studio upsell or a frame-rate question after an import. Dismiss it in Resolve. Long operations also block the bridge until they finish.
- **A Studio-only feature fails.** Do not use Studio-only features on the free edition. They fail or open an upgrade dialog that blocks the bridge.
- **The old davinci-resolve-lite-mcp Python scripts do nothing.** They cannot work on 21.1 or later, because Python scripts no longer appear in the Scripts menu and external scripting is blocked.

## Not included yet

Color-page node tools, gallery and stills, Fairlight, compound and Fusion clips, keyboard and preset import or export, project archive and restore, automatic bridge start when Resolve launches, a Claude Desktop `.mcpb` package, and the plugin install on Windows. `run_lua` covers most of these in the meantime. Set `DAVINCI_MCP_DISABLE_RUN_LUA=1` in the server environment to remove `run_lua` from the tool list.

## Security posture

- Local only. The server opens no network port and sends no telemetry.
- There are no credentials. The identity is your OS user.
- Anyone who can write to the state directory can run Lua inside Resolve as you. On macOS the directory is created with mode 0700; on Windows it inherits the ACLs of your `%APPDATA%`.
- Destructive tools need `confirm: true`. `run_lua` is open-ended, so Claude is told to ask you before running code that deletes or overwrites.
- Responses are size-capped. Over-cap results come back marked `truncated`.
- `Fusion.prefs` is readable by your user and holds the last response until it is cleared.
- To shut it down, run the Stop script and delete the state directory.
- The server logs only the tool name, status and duration to stderr. It never logs arguments or results.

## Development

Run the tests:

```bash
/usr/bin/python3 -m unittest discover -s tests
```

On Windows run `python -m unittest discover -s tests`. The tests that need `fuscript` look for it under `%PROGRAMFILES%`; set `DAVINCI_MCP_FUSCRIPT` to its full path when Resolve is installed elsewhere.

Regenerate the tool reference after changing any tool:

```bash
/usr/bin/python3 scripts/gen_tools_doc.py
```

A test fails if `docs/TOOLS.md` is stale or if a tool is renamed.

Layout:

```
server.py                  stdio entry point
install.py, install.sh     installer, uninstaller (uninstall.sh)
bridge/                    Lua scripts that run inside Resolve
davinci_mcp/               server, transport, prefs parser, Lua encoder, docs index, per-OS paths
davinci_mcp/tools/         one module per tool group
docs/                      MCP-RECORD.md, PROTOCOL.md, TOOLS.md (generated)
scripts/gen_tools_doc.py   generates docs/TOOLS.md
tests/                     unit tests and the offline bridge round trip
```

## Credits

- The JSON encoder and several measured host facts are adapted from [saadk408/davinci-resolve-lua-mcp](https://github.com/saadk408/davinci-resolve-lua-mcp), MIT.
- The idea of using Lua over the preferences file as a channel comes from AutoSubs.

## License

MIT. See [LICENSE](LICENSE).
