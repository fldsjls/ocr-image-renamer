from __future__ import annotations

from folder_matcher import match_images_to_existing_folders
from mode_options import FolderMatchModeOptions


# folder_match_mode.py 是“模式层”的自动匹配已有文件夹入口。
# 它只负责把模式参数交给 folder_matcher.py 的匹配实现。


def run_folder_match_mode(options: FolderMatchModeOptions) -> None:
    """运行自动匹配已有文件夹模式。"""
    match_images_to_existing_folders(
        input_dir=options.input_dir,
        folder_root=options.folder_root,
        recursive=options.recursive,
        dry_run=options.dry_run,
        copy_files=options.copy_files,
        cancel_check=options.cancel_check,
    )
