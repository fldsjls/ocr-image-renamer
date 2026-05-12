from __future__ import annotations

import re


# text_extractors.py 是字段提取模块：
# - 正常水印：按 config.json 的 label、regex、keywords 等规则提取。
# - 非常规水印：没有“施工区域/施工内容”等提示词时，按空格和符号拆分后兜底提取。
# 这个模块只返回字段值，不负责生成文件路径。

def extract_values(text: str, config: dict) -> dict[str, str]:
    """按 config.json 的 fields 配置，一次性提取所有字段。"""
    # stop_labels 用来判断一个字段在哪里结束，例如“施工区域”遇到“施工内容”就停止。
    labels = [field["label"] for field in config["fields"] if "label" in field]
    stop_labels = list(dict.fromkeys(labels + list(config.get("stop_labels", []))))
    avoid_keyword_fields = set(config.get("avoid_keyword_fields", ["area", "content"]))
    values: dict[str, str] = {}
    # 对没有提示词、只靠空格/符号分隔的水印，提前拆成片段备用。
    loose_tokens = split_loose_watermark_text(text)

    for field in config["fields"]:
        key = field["key"]
        fallback = field.get("fallback", "")

        # 每个字段先按 config.json 指定的常规规则提取。
        values[key] = extract_configured_field(text, field, stop_labels, fallback, avoid_keyword_fields)

        # 常规规则失败，或项目名疑似吞进日期/星期/水印相机时，再使用松散规则兜底。
        loose_value = extract_loose_field(key, field, loose_tokens, values, fallback, avoid_keyword_fields)
        if not values[key] or should_prefer_loose_value(key, values[key], loose_value):
            values[key] = loose_value
        if key == "datetime" and not values[key] and values.get("date"):
            values[key] = values["date"]
        values[key] = apply_field_replacement(key, field, values[key])

    return values


def apply_field_replacement(key: str, field: dict, value: str) -> str:
    """字段匹配成功后，可按配置替换为固定内容。"""
    replacement = field.get("replace_with", "")
    if key == "project" and value and isinstance(replacement, str) and replacement.strip():
        return replacement.strip()
    return value


def extract_configured_field(
    text: str,
    field: dict,
    stop_labels: list[str],
    fallback: str,
    avoid_keyword_fields: set[str],
) -> str:
    """按字段主规则提取；主规则失败时，可用 keywords 作为快速补充匹配。"""
    key = field["key"]
    value = fallback

    if "regex" in field:
        value = extract_regex_field(text, field["regex"], fallback)
    elif "prefix_until_keywords" in field:
        value = extract_prefix_until_keyword_field(text, field["prefix_until_keywords"], fallback)
    elif "label" in field:
        value = extract_field(text, field["label"], stop_labels, fallback)

    if (not value or value == fallback) and "keywords" in field and key not in avoid_keyword_fields:
        return extract_keyword_field(text, field["keywords"], fallback)

    return value


def extract_prefix_until_keyword_field(text: str, keywords: list[str], fallback: str) -> str:
    """找到关键词，并返回这一行中关键词及其前面的所有文字。"""
    compact_keywords = [normalize_text(keyword) for keyword in keywords if normalize_text(keyword)]

    # 逐行找“项目/工程/院/期”等关键词，命中后取关键词及其前面的内容。
    for line in text.splitlines():
        compact_line = normalize_text(line).strip(" :：，,。;；")
        if not compact_line:
            continue

        for keyword in compact_keywords:
            index = compact_line.find(keyword)
            if index >= 0:
                return compact_line[: index + len(keyword)]

    return fallback


def split_loose_watermark_text(text: str) -> list[str]:
    """把无标签水印按空格和符号拆成可识别片段，同时保留日期和时间。"""
    if not text:
        return []

    # 日期和时间必须优先匹配，否则普通中英文数字规则会把它们拆碎。
    token_pattern = re.compile(
        r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}"
        r"|\d{1,2}:\d{2}"
        r"|[\u4e00-\u9fffA-Za-z0-9]+"
    )
    tokens: list[str] = []

    for match in token_pattern.finditer(text):
        # 去掉片段边缘的标点，保留片段内部文字，例如“樊华似锦2期”。
        token = match.group(0).strip(" :：，,。;；、|\\/[]()（）【】<>《》")
        if token and token not in tokens:
            tokens.append(token)

    return tokens


def extract_loose_field(
    key: str,
    field: dict,
    tokens: list[str],
    values: dict[str, str],
    fallback: str,
    avoid_keyword_fields: set[str],
) -> str:
    """无标签水印的兜底提取：从拆分片段里补日期、时间和项目名。"""
    if not tokens:
        return fallback

    # date 字段只需要第一个日期片段。
    if key == "date":
        return first_matching_token(tokens, r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", fallback)

    # datetime 由日期和时间拼起来。优先复用前面已经提取出的 date，保证两个字段一致。
    if key == "datetime":
        date = values.get("date") or first_matching_token(tokens, r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", "")
        time = first_matching_token(tokens, r"\d{1,2}:\d{2}", "")
        if date and time:
            return f"{date} {time}"
        return date or fallback

    # project 这类字段通常配置为 prefix_until_keywords，用拆分片段找更干净。
    if "prefix_until_keywords" in field:
        return extract_loose_prefix_until_keyword(tokens, field["prefix_until_keywords"], fallback)

    if "keywords" in field and key not in avoid_keyword_fields:
        return extract_loose_keyword(tokens, field["keywords"], fallback)

    return fallback


def should_prefer_loose_value(key: str, value: str, loose_value: str) -> bool:
    """无标签水印可能把日期、星期和地点整行吞进项目名，这时使用拆分后的片段。"""
    # 目前只替换 project，避免影响施工区域、施工内容等正常字段。
    if not loose_value or key != "project":
        return False

    # 项目名里出现这些内容，通常说明按行提取时把整行水印吞进来了。
    noisy_patterns = [
        r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}",
        r"\d{1,2}:\d{2}",
        r"星期[一二三四五六日天]",
        r"水印相机",
    ]
    return any(re.search(pattern, value) for pattern in noisy_patterns)


def first_matching_token(tokens: list[str], pattern: str, fallback: str) -> str:
    """返回第一个完整匹配正则的片段。"""
    for token in tokens:
        if re.fullmatch(pattern, token):
            return token
    return fallback


def extract_loose_prefix_until_keyword(tokens: list[str], keywords: list[str], fallback: str) -> str:
    """在无标签片段中查找以指定关键词结尾或包含关键词的项目名。"""
    compact_keywords = [normalize_text(keyword) for keyword in keywords if normalize_text(keyword)]
    ignored_tokens = {"水印相机"}

    # 例如 tokens 里有“樊华似锦2期”，关键词有“期”，就返回“樊华似锦2期”。
    for token in tokens:
        compact_token = normalize_text(token)
        if not compact_token or compact_token in ignored_tokens:
            continue

        for keyword in compact_keywords:
            index = compact_token.find(keyword)
            if index >= 0:
                return compact_token[: index + len(keyword)]

    return fallback


def extract_loose_keyword(tokens: list[str], keywords: list[str], fallback: str) -> str:
    """在无标签片段中匹配固定关键词。"""
    compact_tokens = [normalize_text(token) for token in tokens]

    for keyword in keywords:
        compact_keyword = normalize_text(keyword)
        if compact_keyword and compact_keyword in compact_tokens:
            return keyword

    return fallback


def extract_keyword_field(text: str, keywords: list[str], fallback: str) -> str:
    """按关键词列表提取字段；匹配到哪个关键词，就返回哪个关键词。"""
    compact_text = normalize_text(text)

    for keyword in keywords:
        compact_keyword = normalize_text(keyword)
        if compact_keyword and compact_keyword in compact_text:
            return keyword

    return fallback


def extract_regex_field(text: str, pattern: str, fallback: str) -> str:
    """按正则表达式提取字段；如果没有匹配到，就返回 fallback。"""
    match = re.search(pattern, text)
    if not match:
        return fallback

    if match.groups():
        return match.group(1).strip()
    return match.group(0).strip()


def extract_field(text: str, label: str, stop_labels: list[str], fallback: str) -> str:
    """从 OCR 文字中提取某个字段后面的值。"""
    compact_label = normalize_text(label)

    # 优先按单行提取，避免把后面的天气、地点等内容一起吞进来。
    for line in text.splitlines():
        compact_line = normalize_text(line)
        if not compact_line or compact_label not in compact_line:
            continue

        value = compact_line.split(compact_label, 1)[1].strip(" :：，,。;；")
        if value:
            return value

    compact_text = normalize_text(text)
    compact_stops = [normalize_text(item) for item in stop_labels if normalize_text(item) != compact_label]

    # 单行没取到时，再按整段文字取到下一个 stop_label 为止。
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


def normalize_text(text: str) -> str:
    """去掉空格和换行，方便匹配 OCR 文字。"""
    return re.sub(r"\s+", "", text)
