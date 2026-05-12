from __future__ import annotations

import re


# text_extractors.py 只负责把 OCR 文本提取成字段值。
# 当前流程：
# 1. OCR 文本先按行过滤 ignore_words，命中忽视词的整行会被丢弃。
# 2. 剩余行取消换行并拼成一段文本。
# 3. date/datetime 默认自动提取。
# 4. project 优先使用关键字匹配：从关键字前最近符号后开始，取到关键字本身结束。
# 5. 旧的 label/stop_labels 匹配默认关闭，仅在 enable_stop_label_match=true 时启用。

DEFAULT_PROJECT_DELIMITERS = " :：，,。;；、|/\\[]()（）【】<>《》·•.。与"


def extract_values(text: str, config: dict) -> dict[str, str]:
    """按 config.json 的 fields 配置，一次性提取所有字段。"""
    cleaned_text = clean_ocr_text(text, config.get("ignore_words", []))
    stop_labels = list(dict.fromkeys(config.get("stop_labels", [])))
    enable_stop_label_match = bool(config.get("enable_stop_label_match", False))
    values: dict[str, str] = {}

    for field in config["fields"]:
        key = field["key"]
        fallback = field.get("fallback", "")

        if key == "date":
            default_date = config.get("default_date", "") if config.get("enable_default_date", False) else ""
            value = extract_date(cleaned_text, field, fallback, default_date)
        elif key == "datetime":
            value = extract_datetime(cleaned_text, field, values, fallback)
        elif key == "project":
            value = extract_project_by_keyword(cleaned_text, field, stop_labels, fallback, config)
            if not value and enable_stop_label_match:
                value = extract_configured_field(cleaned_text, field, stop_labels, fallback)
        else:
            value = extract_configured_field(cleaned_text, field, stop_labels, fallback)
            if not value and enable_stop_label_match:
                value = extract_stop_label_field(cleaned_text, field, stop_labels, fallback)

        values[key] = apply_field_replacement(key, field, value or fallback)

    return values


def clean_ocr_text(text: str, ignore_words: list[str]) -> str:
    """按行删除包含忽视词的内容，再取消换行。"""
    compact_ignore_words = [normalize_text(word) for word in ignore_words if normalize_text(str(word))]
    kept_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        compact_line = normalize_text(stripped)
        if any(word in compact_line for word in compact_ignore_words):
            continue
        kept_lines.append(stripped)

    # 取消换行但不强行删除普通空格，后续匹配会按需要再 normalize。
    return "".join(kept_lines)


def extract_date(text: str, field: dict, fallback: str, default_date: str = "") -> str:
    """优先按 OCR 文本提取日期，失败时使用界面设置的补全日期。"""
    if "regex" in field:
        value = extract_regex_field(text, field["regex"], "")
        if value:
            return value
    value = extract_regex_field(text, r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", "")
    return value or normalize_default_date(default_date) or fallback


def extract_datetime(text: str, field: dict, values: dict[str, str], fallback: str) -> str:
    """提取日期时间；即使日期和时间原本被换行分开，也会重新用空格拼接。"""
    if "regex" in field:
        value = extract_regex_field(text, field["regex"], "")
        if value:
            return value

    date = values.get("date") or extract_regex_field(text, r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", "")
    time = extract_regex_field(text, r"(\d{1,2}:\d{2})", "")
    if date and time:
        return f"{date} {time}"
    return date or fallback


def extract_project_by_keyword(
    text: str,
    field: dict,
    stop_labels: list[str],
    fallback: str,
    config: dict,
) -> str:
    """按项目关键字提取：向前回溯到最近符号，结果截止到关键字本身。"""
    keywords = collect_project_keywords(field)
    if not keywords:
        return fallback

    compact_text = normalize_text(text)
    delimiters = config.get("project_delimiters", DEFAULT_PROJECT_DELIMITERS)

    best_match: tuple[int, str] | None = None
    for keyword in keywords:
        compact_keyword = normalize_text(keyword)
        if not compact_keyword:
            continue

        start = compact_text.find(compact_keyword)
        if start < 0:
            continue
        if best_match is None or start < best_match[0]:
            best_match = (start, compact_keyword)
        elif start == best_match[0] and len(compact_keyword) > len(best_match[1]):
            best_match = (start, compact_keyword)

    if best_match is None:
        return fallback

    keyword_start, compact_keyword = best_match
    project_start = find_project_start(compact_text, keyword_start, delimiters)
    candidate = compact_text[project_start:]
    keyword_offset = keyword_start - project_start
    end = keyword_offset + len(compact_keyword)
    project = candidate[:end].strip("".join(delimiters))
    return project or fallback


def collect_project_keywords(field: dict) -> list[str]:
    """兼容旧配置，把 keywords 和 prefix_until_keywords 都视为项目关键字来源。"""
    keywords: list[str] = []
    for name in ("keywords", "prefix_until_keywords"):
        values = field.get(name, [])
        if isinstance(values, list):
            keywords.extend(str(value) for value in values if str(value).strip())
    return list(dict.fromkeys(keywords))


def find_project_start(text: str, keyword_start: int, delimiters: str) -> int:
    """从关键字向前找到最近的分隔符，项目名从分隔符后开始。"""
    for index in range(keyword_start - 1, -1, -1):
        if text[index] in delimiters:
            return index + 1
    return 0


def extract_configured_field(text: str, field: dict, stop_labels: list[str], fallback: str) -> str:
    """按非标签规则提取字段；标签规则只有开关打开后才参与。"""
    if "regex" in field:
        return extract_regex_field(text, field["regex"], fallback)
    if "keywords" in field:
        return extract_keyword_field(text, field["keywords"], fallback)
    if "prefix_until_keywords" in field and field.get("key") != "project":
        return extract_prefix_until_keyword_field(text, field["prefix_until_keywords"], fallback)
    return fallback


def extract_stop_label_field(text: str, field: dict, stop_labels: list[str], fallback: str) -> str:
    """启用旧停止标签逻辑后，按 label 提取字段。"""
    label = field.get("label")
    if not label:
        return fallback
    return extract_field(text, label, stop_labels, fallback)


def extract_prefix_until_keyword_field(text: str, keywords: list[str], fallback: str) -> str:
    """旧规则：找到关键字后，返回关键字和它前面的文本。"""
    compact_text = normalize_text(text)
    for keyword in keywords:
        compact_keyword = normalize_text(keyword)
        index = compact_text.find(compact_keyword)
        if index >= 0:
            return compact_text[: index + len(compact_keyword)]
    return fallback


def extract_keyword_field(text: str, keywords: list[str], fallback: str) -> str:
    """固定关键词匹配：出现哪个关键词，就返回哪个关键词。"""
    compact_text = normalize_text(text)
    for keyword in keywords:
        compact_keyword = normalize_text(keyword)
        if compact_keyword and compact_keyword in compact_text:
            return keyword
    return fallback


def extract_regex_field(text: str, pattern: str, fallback: str) -> str:
    """按正则表达式提取字段。"""
    match = re.search(pattern, text)
    if not match:
        compact_text = normalize_text(text)
        match = re.search(pattern, compact_text)
    if not match:
        return fallback

    if match.groups():
        return match.group(1).strip()
    return match.group(0).strip()


def extract_field(text: str, label: str, stop_labels: list[str], fallback: str) -> str:
    """旧规则：从 label 后取值，直到遇到下一个 stop_label。"""
    compact_label = normalize_text(label)
    compact_text = normalize_text(text)
    compact_stops = [normalize_text(item) for item in stop_labels if normalize_text(item) != compact_label]

    if compact_stops:
        stop_pattern = "|".join(re.escape(item) for item in compact_stops)
        pattern = rf"{re.escape(compact_label)}[:：]?(.*?)(?={stop_pattern}|$)"
    else:
        pattern = rf"{re.escape(compact_label)}[:：]?(.*?)$"

    match = re.search(pattern, compact_text)
    if not match:
        return fallback

    value = match.group(1).strip(" :：，,。;；")
    return value or fallback


def apply_field_replacement(key: str, field: dict, value: str) -> str:
    """字段匹配成功后，可按配置替换为固定内容。"""
    replacement = field.get("replace_with", "")
    if key == "project" and value and isinstance(replacement, str) and replacement.strip():
        return replacement.strip()
    return value


def normalize_text(text: str) -> str:
    """去掉空白，方便容错匹配 OCR 文字。"""
    return re.sub(r"\s+", "", str(text))


def normalize_default_date(value: str) -> str:
    """校验并清理界面输入的日期补全值。"""
    value = str(value).strip()
    if re.fullmatch(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", value):
        return value
    return ""
