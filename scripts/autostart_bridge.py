#!/usr/bin/env python3
"""Starts the bridge in DaVinci Resolve without a click (Linux, X11).

The free edition runs no script at launch, ignores .scriptlib files and refuses external scripting,
and Resolve's bundled Qt does not publish its menus over AT-SPI. So this watcher drives the menu
with xdotool, the way a person would: it clicks Workspace, then Up (Scripts is the last entry),
Right (which opens Scripts with the first script highlighted) and Return. Scripts in the Scripts
menu come before its folders, sorted by name, so Claude_MCP_Bridge is first unless another script
sorts before it.

It finds Workspace from a screenshot of the window instead of a fixed position: the menu bar is
the first line of text at the top, its titles are separated by gaps wider than the spaces inside
a title, and Workspace is the one before Help. That holds at any font size or UI scale.

It acts only when a Resolve with a project open has never had a bridge: the bridge session
recorded in Fusion.prefs belongs to another process. A bridge stopped on purpose stays stopped.

install.py registers it in ~/.config/autostart, so it starts with the desktop session. It needs
xdotool, ImageMagick (import), Pillow and numpy.

    python3 scripts/autostart_bridge.py
"""
import io
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from davinci_mcp import paths  # noqa: E402
from davinci_mcp.transport import BridgeClient  # noqa: E402

POLL_S = 5        # how often to look for Resolve
GRACE_S = 10      # wait after a project window appears, so Resolve has finished loading
MAX_TRIES = 3     # menu walks per Resolve process before giving up on it
LOG = os.path.join(paths.STATE_DIR, "autostart.log")


def log(message):
    try:
        with open(LOG, "a") as fh:
            fh.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), message))
    except OSError:
        pass


def xdotool(*args):
    return subprocess.run(["xdotool", *args], capture_output=True, text=True).stdout.strip()


def project_window():
    """(window id, process id) of a Resolve window with a project open, or None."""
    for window in xdotool("search", "--name", "^DaVinci Resolve - ").split():
        pid = xdotool("getwindowpid", window)
        if pid.isdigit():
            return window, int(pid)
    return None


def workspace_point(image):
    """(x, y) of the Workspace title in a grab of Resolve's window."""
    import numpy as np  # Pillow and numpy are only needed once a Resolve shows up

    gray = np.asarray(image.convert("L"), dtype=np.float32)[: max(40, image.height // 20)]
    background = np.median(gray)
    bright = gray > background + 0.5 * (np.percentile(gray, 99.5) - background)
    bands, start = [], None
    for y, count in enumerate(bright.sum(1)):
        if count and start is None:
            start = y
        elif not count and start is not None:
            bands.append((start, y - 1))
            start = None
    top, bottom = next((a, b) for a, b in bands if b - a >= 5)  # first band tall enough to be text
    height = bottom - top + 1
    titles, first, last, gap = [], None, None, 0
    for x, on in enumerate(bright[top:bottom + 1].any(0)):
        if on:
            first = x if first is None else first
            last, gap = x, 0
        elif first is not None:
            gap += 1
            if gap > height * 0.6:  # wider than a space inside a title
                titles.append((first, last))
                first = None
    if first is not None:
        titles.append((first, last))
    left, right = titles[-2]  # Help is the last title
    return (left + right) // 2, (top + bottom) // 2


def start_bridge(window):
    from PIL import Image

    pointer = dict(item.split(":") for item in xdotool("getmouselocation").split()[:2])
    xdotool("windowactivate", "--sync", window)
    grab = subprocess.run(["import", "-window", window, "png:-"], capture_output=True, check=True).stdout
    x, y = workspace_point(Image.open(io.BytesIO(grab)))
    xdotool("mousemove", "--window", window, str(x), str(y), "click", "1")
    time.sleep(0.5)
    for key in ("Up", "Right", "Return"):
        xdotool("key", key)
        time.sleep(0.2)
    xdotool("mousemove", pointer["x"], pointer["y"])


def bridge_pid():
    session = BridgeClient().session() or {}
    return session.get("pid")


def main():
    log("watching for Resolve")
    tries, seen = {}, {}
    while True:
        found = project_window()
        if found and bridge_pid() != found[1]:
            window, pid = found
            seen.setdefault(pid, time.monotonic())
            if time.monotonic() - seen[pid] >= GRACE_S and tries.get(pid, 0) < MAX_TRIES:
                tries[pid] = tries.get(pid, 0) + 1
                try:
                    start_bridge(window)
                    log("Resolve %d: opened Workspace > Scripts > Claude_MCP_Bridge" % pid)
                except Exception as exc:  # a failed walk is retried up to MAX_TRIES
                    log("Resolve %d: %s" % (pid, exc))
                time.sleep(10)  # give the bridge time to record its session
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
