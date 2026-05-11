from __future__ import annotations

import re
from pathlib import Path

from text_extractors import extract_values


# naming.py 负责把“识别出来的字段”变成安全的文件夹和文件名。
# 它不做 OCR，也不判断字段规则，只处理模板渲染、非法字符、重名避让。

# Windows 不能直接使用这些名字作为文件名。
# 比如不能创建 CON.jpg、NUL.jpg，所以后面会特别处理。
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def build_target_path(
    image_path: Path,
    text: str,
    output_dir: Path | None,
    no_folders: bool,
    config: dict,
) -> Path:
    """根据 OCR 文字和配置，生成图片最终要去的完整路径。"""
    safe_filename = build_safe_image_stem(image_path, text, config)
    safe_values = build_safe_values(text, config)

    if output_dir:
        if no_folders:
            target_parent = output_dir
        else:
            # folder_template 里的 / 或 \ 表示创建下一层目录。
            folder_template = config.get("folder_template", "")
            folder_text = render_template(folder_template, safe_values).strip("/\\")
            target_parent = output_dir
            if folder_text:
                for part in re.split(r"[/\\]+", folder_text):
                    safe_part = sanitize_filename(part, "")
                    if safe_part:
                        target_parent = target_parent / safe_part
    else:
        target_parent = image_path.parent

    # unique_path 会避免覆盖已有文件。
    return unique_path(target_parent / f"{safe_filename}{image_path.suffix.lower()}")


def build_safe_image_name(image_path: Path, text: str, config: dict) -> str:
    """根据 OCR 文字和配置，生成安全的新图片文件名。"""
    safe_filename = build_safe_image_stem(image_path, text, config)
    return f"{safe_filename}{image_path.suffix.lower()}"


def build_safe_image_stem(image_path: Path, text: str, config: dict) -> str:
    """根据 OCR 文字和配置，生成不含扩展名的安全文件名。"""
    safe_values = build_safe_values(text, config)
    raw_filename = render_template(config.get("filename_template", "{area}_{content}"), safe_values)
    raw_filename = re.sub(r"_+", "_", raw_filename).strip("_")
    return sanitize_filename(raw_filename, image_path.stem)


def build_safe_values(text: str, config: dict) -> dict[str, str]:
    """提取字段并清理成可用于文件名/文件夹名的安全值。"""
    values = extract_values(text, config)
    return {key: sanitize_filename(value, "") for key, value in values.items()}


def render_template(template: str, values: dict[str, str]) -> str:
    """把模板里的 {字段名} 替换成识别结果。"""
    def replace_placeholder(match: re.Match) -> str:
        key = match.group(1)
        return str(values.get(key, ""))

    return re.sub(r"{([^{}]+)}", replace_placeholder, template)


def sanitize_filename(name: str, fallback: str) -> str:
    """把文字变成安全的 Windows 文件名。"""
    # 替换 Windows 文件名不允许的字符，例如 : * ? < > 等。
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # 普通空格仍然删除，避免项目名或施工内容里出现多余空格。
    name = re.sub(r"\s+", "", name).strip(" .")
    # 但日期和时间之间需要补回一个空格，避免 2026.05.0404_01 粘在一起。
    name = re.sub(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})(\d{1,2}[_:]\d{2})", r"\1 \2", name)
    name = name or fallback

    # Windows 保留名不能直接作为文件名。
    if name.upper() in WINDOWS_RESERVED_NAMES:
        name = f"{name}_file"

    # 控制长度，降低路径过长导致保存失败的概率。
    return name[:120]


def unique_path(path: Path) -> Path:
    """如果目标文件已存在，就自动加 _2、_3，避免覆盖旧文件。"""
    if not path.exists():
        return path

    # 目标文件存在时依次尝试 xxx_2.jpg、xxx_3.jpg。
    stem = path.stem
    suffix = path.suffix
    counter = 2

    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
