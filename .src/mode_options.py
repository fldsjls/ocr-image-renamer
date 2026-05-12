from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


# mode_options.py 定义“模式参数对象”。
# 这样 GUI 和命令行只负责收集参数，具体运行逻辑由 mode_runner.py 分发。


@dataclass(frozen=True)
class CommonOptions:
    input_dir: Path
    recursive: bool
    dry_run: bool
    copy_files: bool


@dataclass(frozen=True)
class OcrModeOptions(CommonOptions):
    output_dir: Path | None
    config_path: Path
    lang: str
    tesseract_cmd: Path | None
    preprocess: bool
    no_folders: bool
    cancel_check: Callable[[], bool] | None = None


@dataclass(frozen=True)
class FolderMatchModeOptions(CommonOptions):
    folder_root: Path
    cancel_check: Callable[[], bool] | None = None


@dataclass(frozen=True)
class OcrFolderMatchModeOptions(CommonOptions):
    folder_root: Path
    config_path: Path
    lang: str
    tesseract_cmd: Path | None
    preprocess: bool
    cancel_check: Callable[[], bool] | None = None
