"""Windows capture exclusion for streaming (TikTok Live Studio, OBS).

SetWindowDisplayAffinity with WDA_EXCLUDEFROMCAPTURE keeps a window
visible on the physical monitor while screen-capture APIs see through
it, so recommendation arrows and controls never reach the stream.
"""
import ctypes
import sys

WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11


def set_exclude_from_capture(widget, exclude=True):
    """Apply capture exclusion to a Qt widget's native window. No-op elsewhere."""
    if sys.platform != 'win32' or widget is None:
        return False
    try:
        hwnd = int(widget.winId())
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(
            ctypes.c_void_p(hwnd),
            WDA_EXCLUDEFROMCAPTURE if exclude else WDA_NONE))
    except (AttributeError, OSError, ValueError):
        return False
