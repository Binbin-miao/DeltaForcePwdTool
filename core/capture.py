"""
core/capture.py
屏幕区域截图，直接返回 PIL Image 对象，不写入磁盘。
"""

from PIL import Image, ImageGrab


def grab_regions(regions: list[dict]) -> list[tuple[str, Image.Image]]:
    """
    对 regions 中的每个区域截图，返回内存图像列表。

    Args:
        regions: 配置中的区域列表，每项含 name / left / top / width / height。

    Returns:
        list of (name, PIL.Image)，顺序与 regions 一致。
    """
    results: list[tuple[str, Image.Image]] = []

    for idx, region in enumerate(regions, start=1):
        name   = region.get("name", f"区域{idx}")
        left   = region["left"]
        top    = region["top"]
        width  = region["width"]
        height = region["height"]

        box = (left, top, left + width, top + height)
        img = ImageGrab.grab(bbox=box)
        results.append((name, img))

    return results
