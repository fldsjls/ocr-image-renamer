from __future__ import annotations

from pathlib import Path


# image_files.py 存放所有模式都会用到的图片文件遍历逻辑。
# OCR 整理模式和自动匹配文件夹模式都从这里拿图片列表。

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def iter_images(input_dir: Path, recursive: bool):
    """遍历图片文件。recursive=True 时会连子文件夹一起找。"""
    pattern = "**/*" if recursive else "*"
    for path in input_dir.glob(pattern):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path
