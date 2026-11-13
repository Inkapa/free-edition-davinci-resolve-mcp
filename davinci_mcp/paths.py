"""Where Resolve, the bridge and the MCP clients keep their files, per platform.

macOS and Windows lay out Resolve's per-user folder the same way below one root:
``~/Library/Application Support/Blackmagic Design/DaVinci Resolve`` on macOS and
``%APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support`` on Windows. Every other module takes its
paths from here.
"""

import os
import sys

WINDOWS = sys.platform == "win32"

if WINDOWS:
    _APPDATA = os.environ.get("APPDATA") or os.path.expanduser(os.path.join("~", "AppData", "Roaming"))
    _PROGRAMDATA = os.environ.get("PROGRAMDATA") or "C:\\ProgramData"
    RESOLVE_SUPPORT = os.path.join(_APPDATA, "Blackmagic Design", "DaVinci Resolve", "Support")
    DOCS_DIR = os.path.join(_PROGRAMDATA, "Blackmagic Design", "DaVinci Resolve", "Support", "Developer", "Scripting")
    DESKTOP_CONFIG = os.path.join(_APPDATA, "Claude", "claude_desktop_config.json")
    # The interpreter running the installer; Windows has no system Python at a fixed path.
    PYTHON = sys.executable
    FUSCRIPT = os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"),
                            "Blackmagic Design", "DaVinci Resolve", "fuscript.exe")
    RESOLVE_IMAGE = "Resolve.exe"
else:
    _SUPPORT = os.path.expanduser("~/Library/Application Support")
    RESOLVE_SUPPORT = os.path.join(_SUPPORT, "Blackmagic Design", "DaVinci Resolve")
    DOCS_DIR = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
    DESKTOP_CONFIG = os.path.join(_SUPPORT, "Claude", "claude_desktop_config.json")
    PYTHON = "/usr/bin/python3"
    FUSCRIPT = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fuscript"
    RESOLVE_IMAGE = "DaVinci Resolve.app/Contents/MacOS/Resolve"

# Resolve can be installed elsewhere (another drive on Windows); the tests honour this override.
FUSCRIPT = os.environ.get("DAVINCI_MCP_FUSCRIPT") or FUSCRIPT

SCRIPTS_UTILITY = os.path.join(RESOLVE_SUPPORT, "Fusion", "Scripts", "Utility")
PROFILES_DIR = os.path.join(RESOLVE_SUPPORT, "Fusion", "Profiles")
STATE_DIR = os.path.join(RESOLVE_SUPPORT, "ClaudeMCP")
