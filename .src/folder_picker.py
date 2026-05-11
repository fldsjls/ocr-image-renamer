from __future__ import annotations

from pathlib import Path


# folder_picker.py 只负责在需要时弹出文件夹选择窗口。
# 这是可选功能：普通命令行运行仍然可以继续使用 --input 指定路径。

def select_folder(title: str) -> Path | None:
    """弹出文件夹选择窗口；用户取消时返回 None。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(title=title)
    finally:
        root.destroy()

    if not selected:
        return None
    return Path(selected)
