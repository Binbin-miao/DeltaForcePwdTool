"""
utils/config.py
配置文件的读取与写入。
新增：支持分辨率自动适配（基准为 2K 2560x1440）
"""

import os
import json
import ctypes
import sys
from typing import Any

if getattr(sys, 'frozen', False):
    # 如果是 exe 运行，强制把根目录设为 exe 所在的目录
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 如果是 python 脚本运行，根目录是当前文件的上一级的上一级
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.json")


_DEFAULT_CONFIG: dict[str, Any] = {
    "wechat_path": "",
    "wechatocr_path": "",
    "save_dir": "temp",
    "temp_dir": "temp",
    "hotkeys": {
        "morse": "ctrl+alt+q",
        "fingerprint": "ctrl+alt+w",
        "exit": "end"
    },
    "fingerprint_images_dir": "images",
    "fingerprint_auto_click": False,
    "regions": []
}


def _expand_env(path: str) -> str:
    """展开路径中的 %ENV% 变量。"""
    return os.path.expandvars(path)


def _auto_scale_coordinates(cfg: dict[str, Any]) -> None:
    """
    核心魔法：自动按比例缩放坐标
    你的 settings.json 是基于 2K (2560x1440) 写的，
    这里会获取当前真实分辨率，在内存中动态缩放。
    """
    try:
        # 强制 DPI 感知，防止 Windows 缩放(如 125%)导致获取的分辨率不准
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
            
        user32 = ctypes.windll.user32
        current_w = user32.GetSystemMetrics(0)
        current_h = user32.GetSystemMetrics(1)

        # 你的配置文件的基准分辨率
        base_w, base_h = 2560, 1440

        if current_w == base_w and current_h == base_h:
            return  # 如果当前就是 2K，直接放行，不转换

        scale_x = current_w / base_w
        scale_y = current_h / base_h

        print(f"[Config] 侦测到物理分辨率: {current_w}x{current_h}，正在将 2K 坐标自动等比缩放...")

        # 1. 转换摩斯码区域 (regions)
        for region in cfg.get("regions", []):
            region["left"] = int(region["left"] * scale_x)
            region["top"] = int(region["top"] * scale_y)
            region["width"] = int(region["width"] * scale_x)
            region["height"] = int(region["height"] * scale_y)

        # 2. 转换摩斯码确认点击坐标
        for click in cfg.get("morse_confirm_clicks", []):
            click["x"] = int(click["x"] * scale_x)
            click["y"] = int(click["y"] * scale_y)

        # 3. 转换指纹识别区域
        fp = cfg.get("fingerprint", {})
        if "name_region" in fp:
            fp["name_region"]["x1"] = int(fp["name_region"]["x1"] * scale_x)
            fp["name_region"]["y1"] = int(fp["name_region"]["y1"] * scale_y)
            fp["name_region"]["x2"] = int(fp["name_region"]["x2"] * scale_x)
            fp["name_region"]["y2"] = int(fp["name_region"]["y2"] * scale_y)

        if "number_region" in fp:
            fp["number_region"]["x1"] = int(fp["number_region"]["x1"] * scale_x)
            fp["number_region"]["y1"] = int(fp["number_region"]["y1"] * scale_y)
            fp["number_region"]["x2"] = int(fp["number_region"]["x2"] * scale_x)
            fp["number_region"]["y2"] = int(fp["number_region"]["y2"] * scale_y)

# ====== 【新增：缩放大指纹区域】 ======
        if "big_fp_region" in fp:
            fp["big_fp_region"]["x1"] = int(fp["big_fp_region"]["x1"] * scale_x)
            fp["big_fp_region"]["y1"] = int(fp["big_fp_region"]["y1"] * scale_y)
            fp["big_fp_region"]["x2"] = int(fp["big_fp_region"]["x2"] * scale_x)
            fp["big_fp_region"]["y2"] = int(fp["big_fp_region"]["y2"] * scale_y)
            
        # ====== 【新增：缩放中心点坐标】 ======
        if "target_centers" in fp:
            for mode, centers in fp["target_centers"].items():
                for center in centers:
                    center["x"] = int(center["x"] * scale_x)
                    center["y"] = int(center["y"] * scale_y)
        if "candidate_boxes" in fp:
            new_boxes = []
            for box in fp["candidate_boxes"]:
                new_boxes.append([
                    int(box[0] * scale_x),
                    int(box[1] * scale_y),
                    int(box[2] * scale_x),
                    int(box[3] * scale_y)
                ])
            fp["candidate_boxes"] = new_boxes

    except Exception as e:
        print(f"[Config] 坐标自动缩放失败，将使用原始坐标: {e}")


def load() -> dict[str, Any]:
    """读取并动态处理配置文件。"""
    if not os.path.exists(CONFIG_PATH):
        save(_DEFAULT_CONFIG)
        print(f"[Config] 已生成默认配置文件：{CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["wechat_path"] = _expand_env(cfg.get("wechat_path", ""))
    cfg["wechatocr_path"] = _expand_env(cfg.get("wechatocr_path", ""))

    save_dir = cfg.get("save_dir", "captures")
    if not os.path.isabs(save_dir):
        save_dir = os.path.join(BASE_DIR, save_dir)
    cfg["save_dir"] = save_dir

    # ========= 核心触发点 =========
    # 在内存中把刚读出来的 2K 坐标，动态折算成当前屏幕坐标
    _auto_scale_coordinates(cfg)

    return cfg


def save(cfg: dict[str, Any]) -> None:
    """将配置字典写回 settings.json。"""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[Config] 配置已保存至 {CONFIG_PATH}")