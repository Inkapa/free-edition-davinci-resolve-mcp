# Changelog

## 0.3.0 (2026-11-13)

First release of the Windows fork.

- New request channel. A request is one file, `inbox/request.lua`, which the bridge runs with `fu:RunScript`; it hands the hex payload over through an in-memory Fusion pref. This replaces the request folders and the two `GetSubFolderList` calls per request, which cost about 18 ms each. The payload format and the response channel are unchanged.
- The bridge checks for a request every 5 ms (one `bmd.fileexists`, about 30 µs) and for stop or take-over every 100 ms.
- The server polls `Fusion.prefs` every 5 ms.
- Round trip for a small call: median 22 ms on Windows with free 21.2 (84 ms with the 0.2 channel on the same machine).
- `server.json` and the plugin manifests point at this fork.
- The server refuses to talk to a bridge from another release and says to reinstall, since a 0.2 bridge never sees a 0.3 request.
- Windows support, measured on Windows 11 with DaVinci Resolve 21.2.0.6 free.
- New `davinci_mcp/paths.py` holds every per-platform path.
- Windows request lock with `msvcrt`, pid liveness through the process table, `Fusion.prefs` read with delete sharing.
- `resolve_status` uses `tasklist` on Windows.
- Installer registers the running Python and calls the `claude` CLI by full path.
- Bridge uses backslash inbox paths for a Windows state directory and falls back to `%APPDATA%`.
- Tests run on Windows; `DAVINCI_MCP_FUSCRIPT` points them at a `fuscript` outside `%PROGRAMFILES%`.

## 0.2.0 — 2026-10-31

- Claude Code plugin: the repository is now its own plugin marketplace. `/plugin marketplace add kingjamesch/davinci-resolve-mcp` then `/plugin install davinci-resolve@davinci-resolve-mcp` registers the `davinci` MCP server without cloning.
- Bundled skill `davinci-resolve` with the measured Resolve conventions (frame spaces, marker rules, Lua idioms, Studio-only traps) so Claude drives Resolve correctly from the first call.
- `/davinci-resolve:setup` command that copies the Lua bridge into Resolve's Scripts folder from inside Claude Code.
- Bridge and stop script report version 0.2.0 (no protocol change; a 0.1.0 bridge keeps working).
- Listed on the MCP Registry as `io.github.kingjamesch/davinci-resolve-mcp` (metadata-only `server.json`).

## 0.1.0 — 2026-10-31

Initial release.

- Lua bridge (`Claude_MCP_Bridge`) that runs inside DaVinci Resolve 21.1 and answers requests through `Fusion.prefs`.
- Stop script (`Claude_MCP_Bridge_Stop`).
- Python stdio MCP server named `davinci`, standard library only, Python 3.9 compatible.
- 33 tools: 13 read tools, 19 write tools and the open-ended `run_lua`.
- Destructive tools require `confirm: true`. Responses are size-capped.
- `scripting_api_docs` searches Blackmagic's shipped scripting API reference.
- Installer (`install.sh`) with `--no-claude`, `--claude-desktop`, `--check` and `--uninstall [--purge]`, plus `uninstall.sh`.
- Generated tool reference in `docs/TOOLS.md`.
- Unit tests, an offline bridge round-trip test, and a contract test for the tool list.
