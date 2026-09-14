"""
core/fingerprint.py
规则修正版：
不再根据 OCR 识别出的残缺数字进行过滤。
严格遵守游戏规则，根据模式最大值，强制按 1 到 N 的顺序依次点击所有指纹！
"""

import os
import re
import time
import traceback
import numpy as np
import cv2
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageGrab
from core import ocr as _ocr

_OCR_CORRECTION_MAP = {
    "克菜尔": "克莱尔",
}

def _crop(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray | None:
    try:
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        return img[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else None
    except Exception:
        return None

def _cv2_read(path: str) -> np.ndarray | None:
    if not os.path.exists(path): return None
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def _cv2_save(path: str, img: np.ndarray) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg"):
        _, buf = cv2.imencode(ext, img)
        buf.tofile(path)
    else:
        cv2.imwrite(path, img)

def _pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def _correct_person_name(raw_name: str, images_dir: str) -> str:
    name = raw_name.strip()
    if name in _OCR_CORRECTION_MAP: return _OCR_CORRECTION_MAP[name]
    if os.path.isdir(os.path.join(images_dir, name)): return name
    try:
        candidates = [d for d in os.listdir(images_dir) if os.path.isdir(os.path.join(images_dir, d))]
        best = max(candidates, key=lambda c: sum(1 for char in name if char in c) / max(len(name), len(c), 1), default=None)
        if best and sum(1 for char in name if char in best) / max(len(name), len(best), 1) >= 0.6:
            return best
    except OSError:
        pass
    return name

def load_templates(person_name: str, images_dir: str, max_count: int = 9) -> list[dict]:
    templates = []
    person_dir = os.path.join(images_dir, person_name)
    if os.path.isdir(person_dir):
        for i in range(1, max_count + 1):
            path = os.path.join(person_dir, f"{i}.png")
            img = _cv2_read(path)
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                templates.append({"index": i, "image": gray})
    return templates

def find_best_match(candidate_img: np.ndarray, templates: list[dict], threshold: float = 0.45) -> tuple[int | None, float]:
    if not templates: return None, 0.0

    cand_gray = cv2.cvtColor(candidate_img, cv2.COLOR_BGR2GRAY) if len(candidate_img.shape) == 3 else candidate_img
    ch, cw = cand_gray.shape

    best_idx, best_score = None, 0.0

    margin_y = max(1, int(ch * 0.15))
    margin_x = max(1, int(cw * 0.15))

    for tmpl in templates:
        tmpl_img = tmpl["image"]
        tmpl_resized = cv2.resize(tmpl_img, (cw, ch), interpolation=cv2.INTER_AREA)
        tmpl_core = tmpl_resized[margin_y:ch-margin_y, margin_x:cw-margin_x]

        result = cv2.matchTemplate(cand_gray, tmpl_core, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        if max_val > best_score:
            best_score = max_val
            best_idx = tmpl["index"]

    return (best_idx, best_score) if best_score > threshold else (None, best_score)

def _save_debug(screen_bgr: np.ndarray, save_dir: str) -> None:
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, f"fp_{datetime.now().strftime('%H%M%S')}_error.png")
    _cv2_save(path, screen_bgr)
    print(f"  [调试] 已触发异常截图，保存至: {path}")

def run_fingerprint_pipeline(app_cfg: dict, save_dir: str = None) -> None:
    try:
        _run_core(app_cfg, save_dir)
    except Exception as e:
        print(f"\n  [ERROR] 程序异常: {e}")
        traceback.print_exc()

def _run_core(app_cfg: dict, save_dir: str = None) -> None:
    fp_cfg = app_cfg.get("fingerprint", {})
    name_reg = fp_cfg.get("name_region", {})
    num_reg = fp_cfg.get("number_region", {})
    boxes = [tuple(b) for b in fp_cfg.get("candidate_boxes", [])]
    mode_map = {int(k): (v["mode"], v["candidates"], v["indices"]) for k, v in fp_cfg.get("mode_config", {}).items()}
    images_dir = app_cfg.get("fingerprint_images_dir", "images")
    save_dir = save_dir or app_cfg.get("save_dir", "temp")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ── 核心滑动指纹识别开始 ──")
    screen_bgr = _pil_to_cv2(ImageGrab.grab())

    name_img = _crop(screen_bgr, name_reg.get("x1",0), name_reg.get("y1",0), name_reg.get("x2",0), name_reg.get("y2",0))
    if name_img is None: return
    raw_name = _ocr.recognize(Image.fromarray(cv2.cvtColor(name_img, cv2.COLOR_BGR2RGB))).strip()
    person_name = _correct_person_name(raw_name, images_dir)
    print(f"  识别到人名: {person_name}")

    num_img = _crop(screen_bgr, num_reg.get("x1",0), num_reg.get("y1",0), num_reg.get("x2",0), num_reg.get("y2",0))
    if num_img is None: return
    numbers = [int(n) for n in re.findall(r"\d+", _ocr.recognize(Image.fromarray(cv2.cvtColor(num_img, cv2.COLOR_BGR2RGB))))]
    print(f"  OCR读取数字: {numbers}")
    if not numbers: return

    max_num = max(numbers)
    # 根据最大数字判断是哪种模式：8、6、4
    mode_key = 8 if max_num > 6 else (6 if max_num > 4 else 4)
    if mode_key not in mode_map: return
    mode_name, n_candidates, indices = mode_map[mode_key]
    
    # ──────── 核心修复：生成 1 到 N 的强制点击序列 ────────
    # 无视 OCR 读漏了什么数字，直接生成 [1, 2, 3, 4, 5, 6, 7, 8]
    target_sequence = list(range(1, mode_key + 1))
    print(f"  识别模式: {mode_name} (最大目标 {mode_key}) | 游戏规则强制点击: {target_sequence}")

    print(f"  正在读取 {images_dir}\\{person_name} 目录下的模板...")
    templates = load_templates(person_name, images_dir, 9)
    if not templates:
        print(f"  [ERROR] 找不到此人的模板，请确保本地文件夹中有图。")
        _save_debug(screen_bgr, save_dir)
        return

    print("  滑动容错对齐匹配中...")
    matches: dict[int, int] = {}
    
    # 新增：用于记录每个模板匹配到的最高分和对应的候选编号
    best_scores: dict[int, float] = {} 
    temp_matches: dict[int, int] = {}  

    for ci in indices:
        cand_no = ci + 1
        cand_img = _crop(screen_bgr, *boxes[ci])
        if cand_img is None: continue

        idx, score = find_best_match(cand_img, templates, threshold=0.45)
        if idx is not None:
            print(f"    候选 {cand_no}: 匹配 模板 {idx} (最稳合分数={score:.3f})")
            # 只要匹配上的编号在强制序列 (1到N) 里，就加入点击任务！
            if idx in target_sequence:
                # 核心去重逻辑：保留分数最高的匹配
                if idx not in best_scores or score > best_scores[idx]:
                    if idx in best_scores:
                        old_cand = temp_matches[idx]
                        old_score = best_scores[idx]
                        print(f"      -> [修正] 候选 {cand_no} ({score:.3f}) 优于 候选 {old_cand} ({old_score:.3f})，接管目标 {idx}")
                    best_scores[idx] = score
                    temp_matches[idx] = cand_no
                else:
                    print(f"      -> [忽略] 候选 {cand_no} ({score:.3f}) 低于 候选 {temp_matches[idx]} ({best_scores[idx]:.3f})，不予记录")
        else:
            print(f"    候选 {cand_no}: 未匹配 (最高分={score:.3f})")

    # 将去重后的最佳匹配还原给 matches 字典，供后续画图和点击使用
    matches = {cn: tn for tn, cn in temp_matches.items()}

    if not matches:
        print("\n  ★ 未找到任何要点击的项！请检查坐标偏移是否过于严重。")
        _save_debug(screen_bgr, save_dir)
    else:
        print(f"\n  ★ 解析成功，准备点击:")
        for cand_no in sorted(matches):
            print(f"    点击 候选 {cand_no} (对应目标 {matches[cand_no]})")

    if app_cfg.get("fingerprint_auto_click", False):
        _do_auto_click(boxes, matches, app_cfg)
    else:
        _do_annotated(screen_bgr, person_name, target_sequence, matches, name_reg, num_reg, boxes, save_dir)

def _do_annotated(screen_bgr, person_name, target_sequence, matches, name_reg, num_reg, boxes, save_dir):
    pil_img = Image.fromarray(cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    try: font = ImageFont.truetype("msyh.ttc", 16)
    except: font = ImageFont.load_default()
    
    draw.rectangle([name_reg["x1"], name_reg["y1"], name_reg["x2"], name_reg["y2"]], outline=(255, 120, 120))
    draw.rectangle([num_reg["x1"], num_reg["y1"], num_reg["x2"], num_reg["y2"]], outline=(120, 255, 255))
    
    for cand_no in sorted(matches):
        x1, y1, x2, y2 = boxes[cand_no - 1]
        draw.rectangle([x1, y1, x2, y2], outline=(120, 255, 120), width=3)
        draw.text((x1, y1 - 25), f" 点击 (它是 {matches[cand_no]}) ", fill=(120, 255, 120), font=font)
        
    os.makedirs(save_dir, exist_ok=True)
    pil_img.save(os.path.join(save_dir, f"fp_{datetime.now().strftime('%H%M%S')}_annotated.png"))

def _do_auto_click(boxes, matches, app_cfg):
    from utils.mouse import win_click, find_game_window, activate_window, click_sequence
    print("\n  执行自动点击...")
    hwnd = find_game_window()
    if hwnd: activate_window(hwnd); time.sleep(0.1)
    
    t2c = {tn: cn for cn, tn in matches.items()}
    for tn in sorted(t2c):
        cn = t2c[tn]
        x1, y1, x2, y2 = boxes[cn - 1]
        win_click((x1 + x2) // 2, (y1 + y2) // 2)
        print(f"    目标 {tn} → 点击候选 {cn}")
        time.sleep(0.05)
        
    if app_cfg.get("morse_auto_click", False) and app_cfg.get("morse_confirm_clicks", []):
        time.sleep(1.7)
        click_sequence(app_cfg.get("morse_confirm_clicks", []), delay=0.05)