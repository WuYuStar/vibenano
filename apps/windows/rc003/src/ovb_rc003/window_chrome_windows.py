"""Best-effort native title-bar colors for the Windows settings window."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
from typing import Callable, Optional


_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36

_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_SWP_NOOWNERZORDER = 0x0200
_PROMOTE_OVERLAY_FLAGS = (
    _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE | _SWP_NOOWNERZORDER
)


def _colorref(color: object) -> int:
    """Convert a QColor-like object to Windows COLORREF (0x00BBGGRR)."""

    red = int(color.red())  # type: ignore[attr-defined]
    green = int(color.green())  # type: ignore[attr-defined]
    blue = int(color.blue())  # type: ignore[attr-defined]
    if not all(0 <= channel <= 255 for channel in (red, green, blue)):
        raise ValueError("color channel outside 0..255")
    return red | (green << 8) | (blue << 16)


def _load_set_window_attribute() -> Callable[..., int]:
    set_attribute = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
    set_attribute.argtypes = (
        wintypes.HWND,
        wintypes.DWORD,
        wintypes.LPCVOID,
        wintypes.DWORD,
    )
    set_attribute.restype = ctypes.c_long
    return set_attribute


def apply_settings_window_chrome(
    window: object,
    *,
    platform: Optional[str] = None,
    set_window_attribute: Optional[Callable[..., int]] = None,
) -> bool:
    """Keep the native caption consistent with the QML shell when activated."""

    current_platform = sys.platform if platform is None else platform
    if current_platform != "win32":
        return False

    try:
        hwnd = int(window.winId())  # type: ignore[attr-defined]
        property_value = window.property  # type: ignore[attr-defined]
        colors = (
            (_DWMWA_BORDER_COLOR, property_value("nativeBorderColor")),
            (_DWMWA_CAPTION_COLOR, property_value("nativeCaptionColor")),
            (_DWMWA_TEXT_COLOR, property_value("nativeCaptionTextColor")),
        )
        colorrefs = tuple((attribute, _colorref(color)) for attribute, color in colors)
        setter = set_window_attribute or _load_set_window_attribute()
    except (AttributeError, OSError, TypeError, ValueError):
        return False

    applied = True
    for attribute, colorref in colorrefs:
        value = wintypes.DWORD(colorref)
        try:
            result = setter(
                wintypes.HWND(hwnd),
                wintypes.DWORD(attribute),
                ctypes.byref(value),
                wintypes.DWORD(ctypes.sizeof(value)),
            )
        except (OSError, TypeError, ValueError):
            applied = False
            continue
        applied = applied and result == 0
    return applied


def _load_set_window_pos() -> Callable[..., int]:
    set_pos = ctypes.WinDLL("user32", use_last_error=True).SetWindowPos
    set_pos.argtypes = (
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    )
    set_pos.restype = wintypes.BOOL
    return set_pos


def promote_overlay_topmost(
    window: object,
    *,
    platform: Optional[str] = None,
    set_window_pos: Optional[Callable[..., int]] = None,
) -> bool:
    """Re-assert HWND_TOPMOST for the voice overlay without stealing focus.

    On Windows 11, hidden WS_EX_TOPMOST tool windows can be demoted below
    ordinary windows after lock-screen, sleep, or Explorer transitions while
    retaining the WS_EX_TOPMOST style bit. Re-asserting HWND_TOPMOST on show
    restores top Z-order with zero background polling and no focus change.
    """

    current_platform = sys.platform if platform is None else platform
    if current_platform != "win32":
        return False

    try:
        hwnd = int(window.winId())  # type: ignore[attr-defined]
        if hwnd <= 0:
            return False
        setter = set_window_pos or _load_set_window_pos()
        return bool(
            setter(
                wintypes.HWND(hwnd),
                wintypes.HWND(_HWND_TOPMOST),
                0,
                0,
                0,
                0,
                wintypes.UINT(_PROMOTE_OVERLAY_FLAGS),
            )
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return False
