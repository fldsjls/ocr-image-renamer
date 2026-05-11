from __future__ import annotations

from folder_match_mode import run_folder_match_mode
from mode_options import FolderMatchModeOptions, OcrFolderMatchModeOptions, OcrModeOptions
from ocr_folder_match_mode import run_ocr_folder_match_mode
from ocr_mode import run_ocr_mode


# mode_runner.py 是模式分发器。
# main.py 和 gui.py 不再直接调用 OCR 或文件夹匹配的底层函数。


def run_mode(options: OcrModeOptions | FolderMatchModeOptions | OcrFolderMatchModeOptions) -> None:
    """根据参数对象类型运行对应模式。"""
    if isinstance(options, OcrModeOptions):
        run_ocr_mode(options)
        return

    if isinstance(options, OcrFolderMatchModeOptions):
        run_ocr_folder_match_mode(options)
        return

    if isinstance(options, FolderMatchModeOptions):
        run_folder_match_mode(options)
        return

    raise TypeError(f"未知运行模式：{type(options).__name__}")
