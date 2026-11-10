"""Read packaged Start-menu entries and launch through the system Shell."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
from . import key_mapping


def windows_directory():
    if sys.platform != "win32":
        raise OSError("Windows applications are unavailable")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetWindowsDirectoryW.argtypes = (wintypes.LPWSTR, wintypes.UINT)
    api.GetWindowsDirectoryW.restype = wintypes.UINT
    value = ctypes.create_unicode_buffer(32768)
    count = api.GetWindowsDirectoryW(value, len(value))
    if not count or count >= len(value):
        raise ctypes.WinError(ctypes.get_last_error())
    return Path(value.value)


def installed_apps():
    shell = windows_directory() / "System32/WindowsPowerShell/v1.0/powershell.exe"
    command = ("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
               "@(Get-StartApps | Where-Object { $_.AppID -like '*!*' } | "
               "Select-Object Name,AppID) | ConvertTo-Json -Compress")
    result = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", command],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8-sig",
        errors="replace", timeout=15, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    data = json.loads(result.stdout.strip() or "[]")
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("invalid installed application list")
    rows, seen = [], set()
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name, identity = entry.get("Name"), entry.get("AppID")
        if not isinstance(name, str) or not isinstance(identity, str) or not name.strip():
            continue
        try:
            target = key_mapping.normalize_program_path(key_mapping.STORE_APP_PREFIX + identity)
        except ValueError:
            continue
        if target.casefold() in seen:
            continue
        seen.add(target.casefold())
        rows.append({"name": name.strip()[:256], "target": target})
    return sorted(rows, key=lambda row: (row["name"].casefold(), row["target"].casefold()))
