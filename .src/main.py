from __future__ import annotations

import argparse
import sys
from pathlib import Path

from folder_picker import select_folder
from mode_options import FolderMatchModeOptions, OcrFolderMatchModeOptions, OcrModeOptions
from mode_runner import run_mode


# main.py 只负责“程序入口”：
# 1. 读取命令行参数。
# 2. 读取 config.json。
# 3. 调用 processor.py 里的批量整理流程。
def parse_args() -> argparse.Namespace:
    """定义并读取命令行参数。"""
    parser = argparse.ArgumentParser(description="识别图片水印字段，并按配置自动重命名。")
    parser.add_argument("--input", type=Path, default=Path("待整理图片"), help="图片所在目录")
    parser.add_argument("--output", type=Path, default=Path("整理后图片"), help="整理后的输出目录")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="字段和命名规则配置")
    parser.add_argument("--lang", default="chi_sim+eng", help="Tesseract 备用OCR语言，例如 chi_sim、eng、chi_sim+eng")
    parser.add_argument("--tesseract-cmd", type=Path, help=r"tesseract.exe 路径，例如 C:\Program Files\Tesseract-OCR\tesseract.exe")
    parser.add_argument("--recursive", action="store_true", help="递归处理子目录")
    parser.add_argument("--preprocess", action="store_true", help="OCR 前先灰度、增强对比度、二值化")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不真正移动或复制")
    parser.add_argument("--copy", action="store_true", help="复制图片到输出目录；默认是移动图片")
    parser.add_argument("--no-folders", action="store_true", help="不按配置创建子文件夹，只放在输出目录")
    parser.add_argument("--match-folders", action="store_true", help="按图片名匹配已有文件夹，成功才放入文件夹，不做 OCR")
    parser.add_argument("--ocr-match-folders", action="store_true", help="先 OCR 生成新图片名，再按新图片名匹配已有文件夹")
    parser.add_argument("--folder-root", type=Path, help="自动匹配文件夹模式下，已有项目文件夹所在目录；默认使用 --output")
    parser.add_argument("--select-input", action="store_true", help="弹出窗口选择图片文件夹路径")
    return parser.parse_args()


def main() -> int:
    """程序入口。把参数、配置和批量整理流程串起来。"""
    args = parse_args()
    validate_mode_args(args)

    # 命令行参数里拿到的是相对路径时，先转成绝对路径，后面打印和移动文件更清楚。
    input_dir = choose_input_dir(args).resolve()
    output_dir = args.output.resolve() if args.output else None

    # 第一次运行时可能还没有“待整理图片”文件夹，这里自动创建。
    input_dir.mkdir(parents=True, exist_ok=True)
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"图片目录不存在：{input_dir}")

    run_mode(build_mode_options(args, input_dir, output_dir))
    return 0


def validate_mode_args(args: argparse.Namespace) -> None:
    """检查命令行模式参数，避免同时启用多个互斥模式。"""
    if args.match_folders and args.ocr_match_folders:
        raise SystemExit("--match-folders 和 --ocr-match-folders 不能同时使用。")


def choose_input_dir(args: argparse.Namespace) -> Path:
    """根据参数决定图片输入目录；需要时弹出文件夹选择窗口。"""
    if not args.select_input:
        return args.input

    selected = select_folder("请选择需要整理的图片文件夹")
    if not selected:
        raise SystemExit("未选择图片文件夹，已取消。")
    return selected


def build_mode_options(
    args: argparse.Namespace,
    input_dir: Path,
    output_dir: Path | None,
) -> OcrModeOptions | FolderMatchModeOptions | OcrFolderMatchModeOptions:
    """把命令行参数转换成具体模式参数。"""
    if args.match_folders:
        return FolderMatchModeOptions(
            input_dir=input_dir,
            folder_root=(args.folder_root or args.output).resolve(),
            recursive=args.recursive,
            dry_run=args.dry_run,
            copy_files=args.copy,
        )

    if args.ocr_match_folders:
        return OcrFolderMatchModeOptions(
            input_dir=input_dir,
            folder_root=(args.folder_root or args.output).resolve(),
            config_path=args.config.resolve(),
            lang=args.lang,
            tesseract_cmd=args.tesseract_cmd.resolve() if args.tesseract_cmd else None,
            recursive=args.recursive,
            preprocess=args.preprocess,
            dry_run=args.dry_run,
            copy_files=args.copy,
        )

    return OcrModeOptions(
        input_dir=input_dir,
        output_dir=output_dir,
        config_path=args.config.resolve(),
        lang=args.lang,
        tesseract_cmd=args.tesseract_cmd.resolve() if args.tesseract_cmd else None,
        recursive=args.recursive,
        preprocess=args.preprocess,
        dry_run=args.dry_run,
        copy_files=args.copy,
        no_folders=args.no_folders,
    )


if __name__ == "__main__":
    sys.exit(main())
