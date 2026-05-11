from __future__ import annotations

import shutil
from pathlib import Path


# tesseract_detector.py 只负责查找本机是否有 tesseract.exe。
# pytesseract 是 Python 包，不等于电脑里已经安装了真正的 Tesseract 程序。


COMMON_TESSERACT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
]


def find_tesseract_cmd(preferred: Path | None = None) -> Path | None:
    """查找 tesseract.exe；优先使用手动指定路径，其次 PATH，最后常见安装目录。"""
    if preferred and preferred.exists() and preferred.is_file() and preferred.name.lower() == "tesseract.exe":
        return preferred

    from_path = shutil.which("tesseract")
    if from_path:
        return Path(from_path)

    for path in COMMON_TESSERACT_PATHS:
        if path.exists() and path.is_file():
            return path

    return None


def has_tesseract(preferred: Path | None = None) -> bool:
    """返回当前电脑是否能找到可用的 tesseract.exe。"""
    return find_tesseract_cmd(preferred) is not None
