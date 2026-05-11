from __future__ import annotations

from config_loader import load_config
from mode_options import OcrModeOptions
from processor import rename_images
from tesseract_detector import find_tesseract_cmd


# ocr_mode.py 是“模式层”的 OCR 识别整理入口。
# 以后如果 OCR 模式新增参数，优先改这里和 OcrModeOptions。


def run_ocr_mode(options: OcrModeOptions) -> None:
    """运行 OCR 识别整理模式。"""
    tesseract_cmd = find_tesseract_cmd(options.tesseract_cmd)
    preprocess = options.preprocess
    if preprocess and not tesseract_cmd:
        print("[提示] 未检测到 tesseract.exe，已自动忽略 OCR 预处理。")
        preprocess = False

    config = load_config(options.config_path)
    rename_images(
        input_dir=options.input_dir,
        config=config,
        lang=options.lang,
        tesseract_cmd=tesseract_cmd,
        output_dir=options.output_dir,
        recursive=options.recursive,
        preprocess=preprocess,
        dry_run=options.dry_run,
        copy_files=options.copy_files,
        no_folders=options.no_folders,
    )
