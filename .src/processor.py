from __future__ import annotations

import shutil
from pathlib import Path

from image_files import iter_images
from naming import build_preview_target_path, build_target_path
from ocr_engine import build_ocr, recognize_text


# processor.py 负责批量处理流程，不关心具体字段怎么提取，也不关心 OCR 细节。
# 它只把“找到图片 -> OCR -> 生成目标路径 -> 预览/复制/移动”串起来。


def rename_images(
    input_dir: Path,
    config: dict,
    lang: str,
    tesseract_cmd: Path | None,
    output_dir: Path | None,
    recursive: bool,
    preprocess: bool,
    dry_run: bool,
    copy_files: bool,
    no_folders: bool,
):
    """主处理流程：找图片、OCR、生成目标路径、复制或移动。"""
    # OCR 引擎只初始化一次，避免每处理一张图都重复加载模型。
    ocr = build_ocr(lang, tesseract_cmd)
    total = renamed = failed = 0

    for image_path in iter_images(input_dir, recursive):
        total += 1
        try:
            # 每张图先识别文字，再把文字交给命名模块生成最终目标路径。
            text = recognize_text(ocr, image_path, preprocess)
            try:
                target = build_target_path(image_path, text, output_dir, no_folders, config)
            except ValueError as exc:
                failed += 1
                preview_target = build_preview_target_path(image_path, text, output_dir, no_folders, config)
                print(f"[失败] {image_path.name} -> {preview_target}：{exc}")
                print(f"识别文字：{text or '<空>'}")
                continue

            # dry-run 只打印预览结果，不创建文件夹，也不移动/复制图片。
            if dry_run:
                print(f"[预览] {image_path.name} -> {target}")
                print(f"识别文字：{text or '<空>'}")
            elif copy_files:
                # copy 模式保留原图，把整理后的图片复制到输出目录。
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image_path, target)
                print(f"[复制] {image_path.name} -> {target}")
            else:
                # 默认模式是移动图片，整理后原输入目录里不再保留这张图。
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(image_path), str(target))
                print(f"[移动] {image_path.name} -> {target}")

            renamed += 1
        except Exception as exc:
            failed += 1
            print(f"[失败] {image_path}: {exc}")

    print(f"\n完成：共 {total} 张，处理 {renamed} 张，失败 {failed} 张。")
