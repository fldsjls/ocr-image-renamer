from __future__ import annotations

import shutil
from pathlib import Path

from config_loader import load_config
from folder_matcher import collect_existing_folders, find_best_folder_match
from image_files import iter_images
from mode_options import OcrFolderMatchModeOptions
from naming import build_preview_image_name, build_safe_image_name, unique_path
from ocr_engine import build_ocr, recognize_text
from tesseract_detector import find_tesseract_cmd


# ocr_folder_match_mode.py 是“先 OCR 命名，再匹配已有文件夹”的模式。
# 它不会按 folder_template 创建目录，只会把 OCR 生成的新文件名匹配到已有文件夹。


def run_ocr_folder_match_mode(options: OcrFolderMatchModeOptions) -> None:
    """运行 OCR 后自动匹配已有文件夹模式。"""
    config = load_config(options.config_path)
    folders = collect_existing_folders(options.folder_root)
    if not folders:
        raise SystemExit(f"没有找到可匹配的已有文件夹：{options.folder_root}")

    tesseract_cmd = find_tesseract_cmd(options.tesseract_cmd)
    preprocess = options.preprocess
    if preprocess and not tesseract_cmd:
        print("[提示] 未检测到 tesseract.exe，已自动忽略 OCR 预处理。")
        preprocess = False

    ocr = build_ocr(options.lang, tesseract_cmd)
    total = matched = skipped = failed = 0

    for image_path in iter_images(options.input_dir, options.recursive):
        total += 1
        try:
            text = recognize_text(ocr, image_path, preprocess)
            try:
                new_name = build_safe_image_name(image_path, text, config)
            except ValueError as exc:
                failed += 1
                preview_name = build_preview_image_name(image_path, text, config)
                print(f"[失败] {image_path.name} -> {preview_name}：{exc}")
                print(f"识别文字：{text or '<空>'}")
                continue
            matched_folder = find_best_folder_match(Path(new_name).stem, folders)

            if not matched_folder:
                skipped += 1
                print(f"[跳过] {image_path.name} -> {new_name}：未匹配到已有文件夹")
                continue

            target = unique_path(matched_folder / new_name)
            if options.dry_run:
                print(f"[预览] {image_path.name} -> {target}")
                print(f"识别文字：{text or '<空>'}")
            elif options.copy_files:
                shutil.copy2(image_path, target)
                print(f"[复制] {image_path.name} -> {target}")
            else:
                shutil.move(str(image_path), str(target))
                print(f"[移动] {image_path.name} -> {target}")
            matched += 1
        except Exception as exc:
            failed += 1
            print(f"[失败] {image_path}: {exc}")

    print(f"\n完成：共 {total} 张，匹配 {matched} 张，跳过 {skipped} 张，失败 {failed} 张。")
