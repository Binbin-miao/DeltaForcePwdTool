"""
core/ocr.py
微信本地 OCR 的初始化与调用封装。
支持传入文件路径（str）或 PIL Image 对象。
新增：微信更新导致路径失效时的全自动侦测与修复功能。
"""

import os
import sys
from datetime import datetime

# 添加根目录到 Python 路径，以便导入 wcocr
_OCR_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_OCR_DIR)

# 导入 wcocr
sys.path.insert(0, _PROJECT_ROOT)
import wcocr

from PIL import Image

_initialized = False
_temp_dir = "captures"  # OCR 中转图存放目录，识别完毕后立即删除

def fuzzy_match_name(raw_text: str, correction_map: dict, threshold: float = 0.6) -> str:
    """
    对 OCR 识别出的人名进行模糊纠错匹配。
    即使 OCR 识别出少量错别字，也能强行纠正为正确的角色名。
    """
    import difflib
    
    if not raw_text:
        return ""

    # 1. 直接包含正确名字 (精确匹配)
    valid_names = list(set(correction_map.values()))
    for name in valid_names:
        if name in raw_text:
            return name

    # 2. 计算相似度 (模糊匹配)
    best_match = ""
    best_ratio = 0.0
    candidates = list(correction_map.keys()) + valid_names

    for cand in candidates:
        ratio = difflib.SequenceMatcher(None, raw_text, cand).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = correction_map.get(cand, cand)

    if best_ratio >= threshold:
        return best_match

    return ""

def _find_latest_version_dir(base_dir: str) -> str:
    """在指定的父目录下，寻找版本号最高的子文件夹。"""
    if not os.path.exists(base_dir):
        return ""
    
    versions = []
    for item in os.listdir(base_dir):
        full_path = os.path.join(base_dir, item)
        if os.path.isdir(full_path):
            # 过滤出纯数字(如 8082) 或 带点的版本号(如 4.1.8.28)
            clean_item = item.replace('.', '')
            if clean_item.isdigit():
                versions.append(item)
                
    if not versions:
        return ""
        
    # 按版本号大小排序 (例如 4.1.8.29 会排在 4.1.8.28 后面)
    versions.sort(key=lambda x: [int(p) for p in x.split('.') if p.isdigit()])
    return os.path.join(base_dir, versions[-1])


def init(
    wechatocr_path: str = None, wechat_path: str = None, temp_dir: str = None
) -> bool:
    """
    初始化微信 OCR 引擎。
    带有自动寻找最新版本功能的智能初始化。
    """
    global _initialized, _temp_dir

    # 从配置读取默认路径
    from utils.config import load as load_config
    cfg = load_config()

    # 设置临时目录
    _temp_dir = temp_dir if temp_dir else cfg.get("temp_dir", "temp")
    if not os.path.isabs(_temp_dir):
        _temp_dir = os.path.join(_PROJECT_ROOT, _temp_dir)

    # 读取配置中的路径，并展开环境变量 (如 %APPDATA%)
    configured_wx_path = wechat_path if wechat_path else cfg.get("wechat_path", "")
    configured_wx_path = os.path.expandvars(configured_wx_path)
    
    configured_ocr_path = wechatocr_path if wechatocr_path else cfg.get("wechatocr_path", "")
    configured_ocr_path = os.path.expandvars(configured_ocr_path)

    # ================= 核心魔法：自动侦测与修复微信路径 =================
    
    actual_wx_path = configured_wx_path
    if not os.path.isdir(actual_wx_path):
        # 如果当前版本文件夹没了，就去上一级目录找最新的
        parent_dir = os.path.dirname(actual_wx_path)
        print(f"  [OCR] 侦测到微信目录已失效，正在自动搜寻 {parent_dir} 下的新版本...")
        new_wx_path = _find_latest_version_dir(parent_dir)
        if new_wx_path:
            actual_wx_path = new_wx_path
            print(f"  [OCR] ✨ 自动寻路成功！微信主目录 -> {actual_wx_path}")

    # ================= 核心魔法：自动侦测与修复 OCR DLL 路径 =================
    
    actual_ocr_path = configured_ocr_path
    if not os.path.isfile(actual_ocr_path):
        # 你的配置是 ...\WeChatOcr\8082\extracted\wxocr.dll
        # 退回三级，找到 WeChatOcr 目录
        ocr_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(actual_ocr_path)))
        print(f"  [OCR] 侦测到 DLL 路径已失效，正在自动搜寻 {ocr_base_dir} 下的新版本...")
        new_version_dir = _find_latest_version_dir(ocr_base_dir)
        
        if new_version_dir:
            # 兼容不同版本微信的 DLL 命名习惯
            for dll_name in ["wxocr.dll", "wechatocr.exe"]:
                test_path = os.path.join(new_version_dir, "extracted", dll_name)
                if os.path.isfile(test_path):
                    actual_ocr_path = test_path
                    print(f"  [OCR] ✨ 自动寻路成功！OCR 引擎 -> {actual_ocr_path}")
                    break

    # ================= 最终校验 =================
    
    if not os.path.isfile(actual_ocr_path):
        print(f"[错误] 经过自动搜寻，仍找不到 wxocr.dll，请检查微信是否安装正确。\n最终搜寻路径：{actual_ocr_path}")
        return False
    if not os.path.isdir(actual_wx_path):
        print(f"[错误] 经过自动搜寻，仍找不到微信目录，请检查微信是否安装正确。\n最终搜寻路径：{actual_wx_path}")
        return False

    # 传给底层的 DLL
    wcocr.init(actual_ocr_path, actual_wx_path)
    _initialized = True
    return True


def destroy() -> None:
    """释放 OCR 引擎资源。"""
    global _initialized
    if _initialized:
        wcocr.destroy()
        _initialized = False


def _parse_result(result) -> str:
    """将 wcocr.ocr() 的返回值统一解析为文本字符串。"""
    texts: list[str] = []
    if isinstance(result, dict):
        for item in result.get("ocr_response", []):
            t = item.get("text", "").strip()
            if t:
                texts.append(t)
    elif isinstance(result, list):
        for item in result:
            t = (
                item.get("text", "").strip()
                if isinstance(item, dict)
                else str(item).strip()
            )
            if t:
                texts.append(t)
    else:
        texts.append(str(result).strip())
    return " ".join(texts)


def recognize(source: str | Image.Image) -> str:
    """
    对图片执行 OCR，返回拼接后的文本字符串。
    """
    if not _initialized:
        raise RuntimeError("[OCR] 引擎未初始化，请先调用 ocr.init()")

    if isinstance(source, str):
        return _parse_result(wcocr.ocr(source))

    os.makedirs(_temp_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    tmp_path = os.path.join(_temp_dir, f"_ocr_tmp_{timestamp}.png")
    try:
        source.save(tmp_path)
        return _parse_result(wcocr.ocr(tmp_path))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass