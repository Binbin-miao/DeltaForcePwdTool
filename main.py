"""
main.py —— 三角洲密码工具

用法：
    python main.py            正常启动
    python main.py --preview  预览模式：交互选择标注摩斯码/指纹区域
"""

import os
import sys
import ctypes

# 禁用控制台快速编辑模式（防止鼠标点击终端窗口导致程序暂停）
_kernel32 = ctypes.windll.kernel32
_STDIN = _kernel32.GetStdHandle(-10)
_mode = ctypes.c_ulong()
_kernel32.GetConsoleMode(_STDIN, ctypes.byref(_mode))
_kernel32.SetConsoleMode(_STDIN, _mode.value | 0x0080)

from utils import config as cfg
from core import ocr, hotkey
from core.morse import run_morse
from core.fingerprint import run_fingerprint_pipeline
from core.selector import preview_regions


# ── 主入口 ───────────────────────────────────────────────────


def main() -> None:
    preview_mode = "--preview" in sys.argv or "-p" in sys.argv

    # 预览模式
    if preview_mode:
        print("=" * 55)
        print("  三角洲密码工具  [预览模式]")
        print("=" * 55)
        app_cfg = cfg.load()
        print(f"  配置文件: {cfg.CONFIG_PATH}\n")
        print("  1 : 预览摩斯码区域")
        print("  2 : 预览指纹区域")
        choice = input("\n请输入编号 (1-2)：").strip()
        fp_cfg = app_cfg.get("fingerprint", {})
        if choice == "1":
            preview_regions(
                app_cfg["regions"], save_dir=app_cfg.get("save_dir", "temp")
            )
        elif choice == "2":
            preview_regions(
                regions=[],  # 不画摩斯码区域
                save_dir=app_cfg.get("save_dir", "temp"),
                fp_name=fp_cfg.get("name_region"),
                fp_number=fp_cfg.get("number_region"),
                fp_boxes=fp_cfg.get("candidate_boxes"),
            )
        else:
            print("无效选择，退出。")
        return

    # 正常模式
    print("=" * 55)
    print("  三角洲密码工具")
    print("=" * 55)

    app_cfg = cfg.load()
    regions = app_cfg["regions"]
    hk_morse = app_cfg["hotkeys"].get("morse", "f3")
    hk_finger = app_cfg["hotkeys"].get("fingerprint", "f4")
    hk_exit = app_cfg["hotkeys"].get("exit", "end")

    print(f"  配置文件: {cfg.CONFIG_PATH}")
    print(f"  {hk_morse.upper():<5}: 摩斯解码")
    print(f"  {hk_finger.upper():<5}: 指纹识别")
    print(f"  {hk_exit.upper():<5}: 退出程序\n")

    # 初始化 OCR
    if not ocr.init(temp_dir=app_cfg.get("temp_dir")):
        print("[错误] OCR 初始化失败，程序退出。")
        return

    # 注册热键
    hotkey.register(
        {
            hk_morse: lambda: run_morse(regions, app_cfg),
            hk_finger: lambda: run_fingerprint_pipeline(
                app_cfg, app_cfg.get("save_dir", "temp")
            ),
            hk_exit: _do_exit,
        }
    )

    # 主循环（空指令按 Enter 保持运行）
    while True:
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            break

    _do_exit()


def _do_exit() -> None:
    hotkey.unregister_all()
    ocr.destroy()
    print("已退出。")
    os._exit(0)


if __name__ == "__main__":
    main()
