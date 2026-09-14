"""
core/hotkey.py
全局热键的注册与生命周期管理。
"""

import keyboard


def register(bindings: dict[str, callable]) -> None:
    """
    批量注册全局热键。

    Args:
        bindings: {热键字符串: 回调函数}，例如 {"f1": on_f1, "end": on_end}
    """
    for key, callback in bindings.items():
        keyboard.add_hotkey(key, callback)


def unregister_all() -> None:
    """注销所有已注册的热键。"""
    keyboard.unhook_all_hotkeys()
