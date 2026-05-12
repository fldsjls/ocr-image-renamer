from __future__ import annotations


# config_help.py 存放配置编辑窗口中的说明文字，避免主界面文件过长。

CONFIG_HELP_TEXT = """配置文件主要控制 OCR 文本如何清洗、匹配和命名。

1. ignore_words：忽视词
OCR 得到带换行的文本后，会先逐行检查。某一行只要包含 ignore_words 中任意一个词，这一整行就会被丢弃。

例子：
{
  "ignore_words": ["水印相机"]
}

2. 换行处理
忽视词删行完成后，程序会把剩余行取消换行并拼成一段，再进入字段匹配。

3. date / datetime：默认自动匹配
date 默认匹配：
2026.05.04
2026-05-04
2026/5/4

datetime 会优先按配置 regex 匹配；如果匹配不到，会自动用 date + 时间拼成：
2026.05.04 04:01

4. project：关键字匹配
project 会优先读取 keywords 或 prefix_until_keywords 中的项目关键字。
匹配成功后，从命中的关键字开始，取到下一个符号、日期、时间、停止词前，作为项目名。

例子：
{
  "key": "project",
  "prefix_until_keywords": ["樊华似锦2期", "樊华广场"],
  "fallback": ""
}

如果 OCR 文本中有：
绵阳市·樊华似锦2期 2026.05.04

匹配到“樊华似锦2期”后，project 会取：
樊华似锦2期

5. enable_stop_label_match：停止标签匹配开关
默认 false。
关闭时，施工区域、施工内容这类 label 不会按旧标签逻辑自动提取。
开启后，才会使用 label + stop_labels 的旧逻辑兜底。

例子：
{
  "enable_stop_label_match": true
}

6. stop_labels：旧标签匹配的结束标记
只有 enable_stop_label_match 为 true 时才主要参与字段提取。

例子：
["施工区域", "施工内容", "天气", "地点"]

含义：提取“施工区域”时，遇到“施工内容/天气/地点”等内容就停止。

7. replace_with：匹配成功后替换为固定内容
适合 OCR 里项目名写法不稳定，但最终想统一成一个标准项目名。

例子：
{
  "key": "project",
  "prefix_until_keywords": ["樊华似锦"],
  "replace_with": "樊华似锦项目"
}

8. filename_template：文件名模板
例子：
{project}_{area}_{datetime}_{content}

9. folder_template：文件夹模板
例子：
{project}/{area}/{date}/{content}

如果不想创建多层子文件夹，可以在界面勾选“不创建子文件夹”，或修改模板。

10. avoid_keyword_fields：避免 keywords 快速匹配的字段
保留用于兼容旧配置；当前新逻辑里 project 主要使用关键字，area/content 默认不会因 label 自动提取，除非开启停止标签匹配。
"""
