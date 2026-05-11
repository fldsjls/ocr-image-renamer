from __future__ import annotations

import json
from pathlib import Path


# config_loader.py 只处理配置文件：
# - DEFAULT_CONFIG 是没有 config.json 时使用的默认规则。
# - load_config() 负责读取、校验，并把缺失的顶层配置项补成默认值。

# 默认配置。
# 如果 config.json 不存在，程序会用这份默认配置创建一个 config.json。
# 平时建议改 config.json，不建议直接改这里。
DEFAULT_CONFIG = {
    "fields": [
        {
            "key": "project",
            "prefix_until_keywords": ["项目", "工程"],
            "fallback": "",
        },
        {"key": "area", "label": "施工区域", "fallback": ""},
        {
            "key": "date",
            "regex": r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})",
            "fallback": "",
        },
        {
            "key": "datetime",
            "regex": r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}\s+\d{1,2}:\d{2})",
            "fallback": "",
        },
        {"key": "content", "label": "施工内容", "fallback": ""},
    ],
    "filename_template": "{project}_{area}_{datetime}_{content}",
    "folder_template": "{project}/{area}/{date}/{content}",
    "stop_labels": ["施工区域", "施工内容", "天气", "地点"],
}


def load_config(path: Path) -> dict:
    """读取配置文件；如果配置文件不存在，就自动创建一份默认配置。"""
    # 没有配置文件时自动生成一份，方便第一次使用。
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG

    # utf-8-sig 可以兼容带 BOM 的 config.json，避免 Windows 编辑器保存后读取失败。
    with path.open("r", encoding="utf-8-sig") as file:
        config = json.load(file)

    validate_config(config)

    # 允许 config.json 只覆盖部分顶层配置，其余沿用默认值。
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    return merged


def validate_config(config: dict) -> None:
    """校验 config.json 的基本结构。"""
    # fields 是字段提取规则的核心，没有它就不知道要从 OCR 文本里取什么。
    if "fields" not in config or not isinstance(config["fields"], list):
        raise ValueError("config.json 里必须有 fields，并且 fields 必须是数组。")

    # 每个字段必须有 key，并且至少有一种提取方式。
    for field in config["fields"]:
        if "key" not in field:
            raise ValueError("fields 里的每一项都必须有 key。")
        if (
            "label" not in field
            and "regex" not in field
            and "keywords" not in field
            and "prefix_until_keywords" not in field
        ):
            raise ValueError("fields 里的每一项都必须有 label、regex、keywords 或 prefix_until_keywords。")
