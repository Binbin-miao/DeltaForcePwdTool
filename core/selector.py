"""
core/selector.py
截取当前全屏，将配置文件中的区域用彩色框标注后保存，
并用系统默认图片查看器打开，方便核对坐标是否正确。

用法：
    from core.selector import preview_regions
    preview_regions(regions, save_dir="captures")
"""

import os
import subprocess
import sys
from datetime import datetime
from PIL import Image, ImageGrab, ImageDraw, ImageFont

# 每个区域依次使用不同颜色，循环取用
_PALETTE = [
    "#FF4444",  # 红
    "#44AAFF",  # 蓝
    "#44DD44",  # 绿
]
_LINE_WIDTH  = 3
_FONT_SIZE   = 20
_LABEL_PAD   = 4   # 标签文字与框边的间距


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """尝试加载系统字体，失败则回退到默认字体。"""
    candidates = [
        "msyh.ttc",          # 微软雅黑（Windows）
        "simhei.ttf",        # 黑体
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def preview_regions(
    regions: list[dict],
    save_dir: str = "captures",
    *,
    fp_name: dict | None = None,
    fp_number: dict | None = None,
    fp_boxes: list[list[int]] | None = None,
) -> str:
    """
    截取当前全屏，在图上标注区域的彩色矩形框与名称，
    将结果保存到 save_dir，然后用系统默认图片程序打开。

    Args:
        regions:      区域列表，每项含 name / left / top / width / height。
        save_dir:      截图保存目录，默认为 captures/。
        fp_name:       指纹人名区域 {x1, y1, x2, y2}。
        fp_number:    指纹数字区域 {x1, y1, x2, y2}。
        fp_boxes:     指纹候选格子列表，每项 [x1, y1, x2, y2]。
    """
    screenshot: Image.Image = ImageGrab.grab()
    draw = ImageDraw.Draw(screenshot)
    font = _get_font(_FONT_SIZE)

    # ── 摩斯码区域 ───────────────────────────────────────
    for idx, region in enumerate(regions):
        name   = region.get("name", f"区域{idx + 1}")
        left   = region["left"]
        top_   = region["top"]
        right  = left + region["width"]
        bottom = top_ + region["height"]
        color  = _PALETTE[idx % len(_PALETTE)]
        _draw_box(draw, font, left, top_, right, bottom, color, name)

    # ── 指纹区域 ─────────────────────────────────────────
    if fp_name:
        _draw_box(draw, font,
                  fp_name["x1"], fp_name["y1"], fp_name["x2"], fp_name["y2"],
                  "#FFAA00", "人名")

    if fp_number:
        _draw_box(draw, font,
                  fp_number["x1"], fp_number["y1"], fp_number["x2"], fp_number["y2"],
                  "#FF8800", "数字")

    if fp_boxes:
        for idx, box in enumerate(fp_boxes):
            x1, y1, x2, y2 = box
            _draw_box(draw, font, x1, y1, x2, y2,
                      _PALETTE[idx % len(_PALETTE)], f"格子{idx + 1}")

    # ── 保存并打开 ────────────────────────────────────────
    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(save_dir, f"preview_{timestamp}.png")
    screenshot.save(save_path)
    _open_image(save_path)
    print(f"[预览] 已保存并打开标注图：{save_path}")
    return save_path


def _draw_box(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    x1: int, y1: int, x2: int, y2: int,
    color: str,
    label: str,
) -> None:
    """在给定矩形区域上画边框和标签。"""
    for offset in range(_LINE_WIDTH):
        draw.rectangle([x1 - offset, y1 - offset, x2 + offset, y2 + offset],
                       outline=color)
    bbox = font.getbbox(f" {label} ")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    lx = x1
    ly = max(0, y1 - text_h - _LABEL_PAD * 2 - _LINE_WIDTH)
    draw.rectangle(
        [lx, ly, lx + text_w + _LABEL_PAD * 2, ly + text_h + _LABEL_PAD * 2],
        fill=color,
    )
    draw.text((lx + _LABEL_PAD, ly + _LABEL_PAD), f" {label} ",
              fill="white", font=font)


def _open_image(path: str) -> None:
    """跨平台用系统默认程序打开图片。"""
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
