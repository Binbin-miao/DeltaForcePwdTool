"""
utils/mouse.py
Windows API 鼠标操作的统一封装：
- DPI 感知声明
- 高精度点击
- 游戏窗口查找与激活
"""

import ctypes
import time
from ctypes import windll

# ── Windows API 基础 ─────────────────────────────────────────

_user32 = ctypes.WinDLL("user32", use_last_error=True)

# ── DPI 感知（进程级，启动时执行一次）──────────────────────────

try:
    windll.shcore.SetProcessDpiAwareness(2)      # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        _user32.SetProcessDPIAware()              # 兜底：系统 DPI 感知
    except Exception:
        pass


# ── 鼠标事件常量 ─────────────────────────────────────────────

_MOUSE_DOWN = 0x0002   # MOUSEEVENTF_LEFTDOWN
_MOUSE_UP   = 0x0004   # MOUSEEVENTF_LEFTUP


# ── 窗口操作 ────────────────────────────────────────────────

def find_game_window() -> int:
    """按窗口标题查找游戏窗口句柄。"""
    for title in ("三角洲", "Delta Force", "游戏"):
        hwnd = _user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
    return 0


def activate_window(hwnd: int) -> None:
    """将指定窗口置前并激活。"""
    if not hwnd:
        return
    if _user32.IsIconic(hwnd):                    # 若最小化则还原
        _user32.ShowWindow(hwnd, 9)               # SW_RESTORE
    _user32.SetForegroundWindow(hwnd)


# ── 鼠标点击 ────────────────────────────────────────────────

def win_click(x: int, y: int) -> None:
    """
    在屏幕坐标 (x, y) 执行一次左键单击。
    依赖进程级 DPI 感知，坐标直接对应物理像素。
    """
    _user32.SetCursorPos(x, y)
    _user32.mouse_event(_MOUSE_DOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    _user32.mouse_event(_MOUSE_UP, 0, 0, 0, 0)


def click_sequence(coords: list[dict], delay: float = 0.05) -> None:
    """
    依次点击一组坐标。
    coords: [{"x": int, "y": int}, ...]
    delay:  每次点击后的等待时间（秒）
    """
    for pt in coords:
        win_click(pt["x"], pt["y"])
        time.sleep(delay)
