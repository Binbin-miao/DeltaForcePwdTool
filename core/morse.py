"""
core/morse.py
摩斯码 ↔ 数字（0-9）的解码逻辑。
【纯视觉终极版】：彻底移除 OCR 依赖，全权由 OpenCV 轮廓检测接管。
"""

import cv2
import numpy as np

# 数字 0-9 的标准摩斯码
MORSE_TABLE: dict[str, str] = {
    "-----": "0",
    ".----": "1",
    "..---": "2",
    "...--": "3",
    "....-": "4",
    ".....": "5",
    "-....": "6",
    "--...": "7",
    "---..": "8",
    "----.": "9",
}

def decode_by_cv2(pil_img) -> str:
    """纯视觉：使用 OpenCV 轮廓检测提取摩斯码"""
    try:
        # 1. 转灰度图并二值化 (强化白色的点和划)
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        
        # 2. 寻找轮廓
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        symbols = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w * h < 10:  # 过滤极小的画面噪点
                continue
            
            # 根据宽高比区分点(.)和划(-)
            aspect_ratio = w / float(h)
            symbol = "-" if aspect_ratio > 2.0 else "."
            symbols.append({"x": x, "symbol": symbol})
            
        if not symbols:
            return "?"
            
        # 3. 按 X 坐标从左到右排序并拼接
        symbols.sort(key=lambda item: item["x"])
        morse_str = "".join(item["symbol"] for item in symbols)
        
        # 4. 查表
        return MORSE_TABLE.get(morse_str, "?")
    except Exception:
        return "?"


# ── 以下为跨模块依赖，需要在 core/__init__.py 中避免循环导入 ──────────────

def run_morse(regions: list[dict], app_cfg: dict) -> None:
    """
    截图 → 纯视觉识别 → 摩斯解码 → 按下数字键 → 确认点击
    """
    # 👇 看到没！这里再也没有 ocr 了！
    from core import capture
    from utils.mouse import click_sequence
    import keyboard
    import time
    from datetime import datetime

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ── 开始纯视觉摩斯码解析 ──")

    screenshots = capture.grab_regions(regions)
    digits: list[str] = []

    for name, img in screenshots:
        # 直接只使用 OpenCV 视觉轮廓检测
        digit = decode_by_cv2(img)
        method_used = "OpenCV 视觉"

        print(f"  [{name}] 解码 → {digit}  [引擎: {method_used}]")
        digits.append(digit)

    password = "".join(digits)
    print(f"\n  ★ 识别密码：{password}\n")

    all_ok = all(d.isdigit() for d in digits)

    for d in digits:
        if d.isdigit():
            keyboard.press_and_release(d)
            print(f"  → 已按下: {d}")
        else:
            print(f"  → 识别失败，跳过: {d}")
        time.sleep(0.05)

    # 确认点击：检查开关与坐标，三个数字全部成功才触发
    auto_click = app_cfg.get("morse_auto_click", True) 
    clicks = app_cfg.get("morse_confirm_clicks", [])
    
    if auto_click and clicks:
        if all_ok:
            time.sleep(0.6)
            print("  → 点击下载")
            click_sequence(clicks, delay=0.1)
        else:
            print("  → 存在识别失败的数字，跳过点击")
    elif not auto_click:
        print("  → 自动点击下载已禁用，请手动点击")

    print()