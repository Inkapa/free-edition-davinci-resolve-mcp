"""Reading the bridge's keys out of Fusion.prefs (docs/PROTOCOL.md, "Response").

Fusion writes the file as a Lua table; our values are ``<id>:<hex>``, ``<hex>`` or digits, so a
word-boundary regex with a closing quote is exact. Resolve replaces the file atomically (new inode),
so a read never sees a half-written key; a line break before the closing quote means "not ours".
"""

import json
import os
import re
from typing import Dict, Optional, Tuple

from .paths import PROFILES_DIR, WINDOWS

if WINDOWS:
    import ctypes
    import msvcrt

    _create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    _create_file.restype = ctypes.c_void_p   # a HANDLE is pointer-sized
PREFS_FILE_NAME = "Fusion.prefs"
KEYS = ("CMCP_Resp", "CMCP_Session", "CMCP_Owner", "CMCP_Beat", "CMCP_Stop")
_KEY_RES = {k: re.compile(r"\b" + k + r' = "([^"\r\n]*)"') for k in KEYS}


def find_prefs_file(profiles_dir: str = None) -> Optional[str]:
    """Newest ``<profiles_dir>/<profile>/Fusion.prefs`` or None."""
    base = profiles_dir or PROFILES_DIR
    best, best_m = None, -1.0
    try:
        names = os.listdir(base)
    except OSError:
        return None
    for name in names:
        candidate = os.path.join(base, name, PREFS_FILE_NAME)
        try:
            st = os.stat(candidate)
        except OSError:
            continue
        if st.st_mtime > best_m:
            best, best_m = candidate, st.st_mtime
    return best


def file_signature(path: str) -> Optional[Tuple[int, int, int]]:
    """(mtime_ns, size, inode) — changes whenever Fusion rewrites the file."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size, st.st_ino)


def read_text(path: str) -> Optional[str]:
    try:
        with _open_shared(path) as fh:
            return fh.read()
    except OSError:
        return None


def _open_shared(path: str):
    """Open for reading without blocking a writer that replaces or deletes the file.

    Windows' default open() denies delete sharing, so a poll that overlaps a save makes the save
    fail and the response is lost. Opening through CreateFileW with FILE_SHARE_DELETE avoids that.
    """
    if not WINDOWS:
        return open(path, "r", encoding="utf-8", errors="replace")
    generic_read = 0x80000000
    share_all = 0x1 | 0x2 | 0x4   # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
    open_existing = 3
    handle = _create_file(path, generic_read, share_all, None, open_existing, 0, None)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "cannot open " + path)
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    return open(fd, "r", encoding="utf-8", errors="replace")


def extract_keys(text: str) -> Dict[str, str]:
    """Last complete value of every CMCP_* key present in ``text`` (missing keys absent)."""
    out = {}
    for key, rx in _KEY_RES.items():
        last = None
        for m in rx.finditer(text):
            last = m.group(1)
        if last is not None:
            out[key] = last
    return out


def decode_hex(hexstr: str) -> str:
    if len(hexstr) % 2 != 0:
        raise ValueError("hex body has odd length")
    if not re.match(r"^[0-9a-fA-F]*$", hexstr):
        raise ValueError("hex body has a non-hex character")
    return bytes.fromhex(hexstr).decode("utf-8", errors="replace")


def decode_hex_json(hexstr: str) -> dict:
    text = decode_hex(hexstr)
    try:
        obj = json.loads(text)
    except ValueError as exc:
        raise ValueError("bridge payload is not valid JSON: %s" % exc)
    if not isinstance(obj, dict):
        raise ValueError("bridge payload is not a JSON object")
    return obj


def split_resp(value: str) -> Tuple[str, str]:
    """``<id>:<hex>`` -> (id, hex). An empty value means "no response yet"."""
    if not value:
        return "", ""
    colon = value.find(":")
    if colon < 0:
        return value, ""
    return value[:colon], value[colon + 1:]
