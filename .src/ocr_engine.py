from __future__ import annotations

from pathlib import Path


# ocr_engine.py 只负责 OCR：
# - 优先使用 RapidOCR，适合中文水印，且不需要额外安装 Tesseract 程序。
# - 如果 RapidOCR 不可用，再退回 pytesseract。
# - --preprocess 当前只对 pytesseract 路线生效。

def build_ocr(lang: str, tesseract_cmd: Path | None):
    """创建 OCR 识别工具。优先使用 RapidOCR，缺少时再使用 pytesseract。"""
    # RapidOCR 能直接接收图片路径，作为首选。
    try:
        from rapidocr_onnxruntime import RapidOCR

        return {"type": "rapidocr", "engine": RapidOCR(), "lang": lang}
    except ImportError:
        pass

    # 没有 RapidOCR 时，尝试 pytesseract。pytesseract 还依赖本机 tesseract.exe。
    try:
        import pytesseract
    except ImportError as exc:
        raise SystemExit("缺少 OCR 依赖。请先运行：pip install -r requirements.txt") from exc

    # 用户指定 tesseract.exe 路径时，显式告诉 pytesseract 去哪里找。
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)

    return {"type": "pytesseract", "engine": pytesseract, "lang": lang}


def recognize_text(ocr, image_path: Path, preprocess: bool) -> str:
    """对单张图片做 OCR，返回识别出来的文字。"""
    if ocr["type"] == "rapidocr":
        # RapidOCR 返回的是带坐标和置信度的列表，这里只取文字部分并按行拼接。
        result, _ = ocr["engine"](str(image_path))
        if not result:
            return ""
        return "\n".join(item[1] for item in result if len(item) >= 2).strip()

    from PIL import Image

    with Image.open(image_path) as image:
        image = prepare_image(image, preprocess)
        return ocr["engine"].image_to_string(image, lang=ocr["lang"]).strip()


def prepare_image(image, preprocess: bool):
    """OCR 前的图片预处理。水印较浅时可以用 --preprocess 开启。"""
    if not preprocess:
        return image

    from PIL import ImageEnhance, ImageOps

    # 灰度 -> 增强对比度 -> 二值化，用来提高浅色水印在 Tesseract 里的可读性。
    image = ImageOps.grayscale(image)
    image = ImageEnhance.Contrast(image).enhance(2.0)
    return image.point(lambda value: 255 if value > 155 else 0)
