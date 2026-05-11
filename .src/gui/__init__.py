from __future__ import annotations

from .app import main

# 对外只暴露 main，便于批处理脚本用 `python -m gui` 启动界面。
__all__ = ["main"]
