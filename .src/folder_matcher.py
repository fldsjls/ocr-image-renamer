from __future__ import annotations

import re
import shutil
from pathlib import Path

from image_files import iter_images
from naming import unique_path


# folder_matcher.py 负责“自动匹配文件夹模式”：
# - 不做 OCR。
# - 不新建项目文件夹。
# - 只把图片名和已有文件夹名匹配。
# - 匹配成功就放入对应文件夹，匹配失败就跳过不操作。

MIN_COMMON_TEXT_LENGTH = 4
CHINESE_DIGITS = str.maketrans(
    {
        "零": "0",
        "〇": "0",
        "一": "1",
        "二": "2",
        "三": "3",
        "四": "4",
        "五": "5",
        "六": "6",
        "七": "7",
        "八": "8",
        "九": "9",
    }
)


def match_images_to_existing_folders(
    input_dir: Path,
    folder_root: Path,
    recursive: bool,
    dry_run: bool,
    copy_files: bool,
):
    """把图片按文件名匹配到 folder_root 下面已有的文件夹。"""
    folders = collect_existing_folders(folder_root)
    if not folders:
        raise SystemExit(f"没有找到可匹配的已有文件夹：{folder_root}")

    total = matched = skipped = failed = 0
    for image_path in iter_images(input_dir, recursive):
        total += 1
        folder = find_best_folder_match(image_path.stem, folders)
        if not folder:
            skipped += 1
            print(f"[跳过] {image_path.name}：未匹配到已有文件夹")
            continue

        target = unique_path(folder / image_path.name)
        try:
            if dry_run:
                print(f"[预览] {image_path.name} -> {target}")
            elif copy_files:
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


def collect_existing_folders(folder_root: Path) -> list[Path]:
    """收集已有文件夹，按名称长度从长到短排序，优先匹配更具体的文件夹。"""
    if not folder_root.exists() or not folder_root.is_dir():
        raise SystemExit(f"文件夹根目录不存在：{folder_root}")

    folders = [path for path in folder_root.iterdir() if path.is_dir()]
    return sorted(folders, key=lambda path: len(normalize_match_text(path.name)), reverse=True)


def find_best_folder_match(image_name: str, folders: list[Path]) -> Path | None:
    """从已有文件夹中找出和图片名最匹配的文件夹。"""
    normalized_image_name = normalize_match_text(image_name)
    if not normalized_image_name:
        return None

    best_folder: Path | None = None
    best_score = 0
    for folder in folders:
        normalized_folder_name = normalize_match_text(folder.name)
        score = score_folder_match(normalized_image_name, normalized_folder_name)
        if score > best_score:
            best_score = score
            best_folder = folder

    return best_folder if best_score > 0 else None


def score_folder_match(image_name: str, folder_name: str) -> int:
    """计算图片名和文件夹名的匹配分数。分数越高，越优先匹配。"""
    if not image_name or not folder_name:
        return 0

    # 完整包含最可靠：文件夹名在图片名中，或图片名中的核心名在文件夹名中。
    if folder_name in image_name:
        return 10_000 + len(folder_name)
    if image_name in folder_name:
        return 9_000 + len(image_name)

    common_text = longest_common_text(image_name, folder_name)
    if len(common_text) < MIN_COMMON_TEXT_LENGTH:
        return 0

    # 公共片段越长、占文件夹名比例越高，越可信。
    common_ratio = len(common_text) / max(len(folder_name), 1)
    return int(len(common_text) * 100 + common_ratio * 100)


def longest_common_text(left: str, right: str) -> str:
    """返回两个字符串中最长的连续公共片段。"""
    if not left or not right:
        return ""

    best = ""
    previous_row = [0] * (len(right) + 1)
    for left_index, left_char in enumerate(left, start=1):
        current_row = [0] * (len(right) + 1)
        for right_index, right_char in enumerate(right, start=1):
            if left_char != right_char:
                continue
            current_row[right_index] = previous_row[right_index - 1] + 1
            if current_row[right_index] > len(best):
                start = left_index - current_row[right_index]
                best = left[start:left_index]
        previous_row = current_row

    return best


def normalize_match_text(text: str) -> str:
    """统一匹配文本：去掉空格和常见符号，只保留中英文、数字。"""
    text = text.translate(CHINESE_DIGITS)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text).lower()
