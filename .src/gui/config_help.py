from __future__ import annotations


# config_help.py 存放配置编辑窗口右侧/下方的说明文字。
# 把大段说明从 app.py 里拿出来，避免 GUI 主文件过长。

CONFIG_HELP_TEXT = """配置文件主要分为 4 块：

1. fields：告诉程序从 OCR 文字里提取哪些字段
每个字段至少需要 key，并选择一种匹配方式。

常见字段：
- project：项目名
- area：施工区域
- date：日期
- datetime：日期时间
- content：施工内容

2. label：按提示词提取
适合水印里有固定提示词的情况，例如：
施工区域: 5层
施工内容: 暗门维修

配置例子：
{
  "key": "area",
  "label": "施工区域",
  "fallback": ""
}

含义：找到“施工区域”后面的内容，直到遇到下一个 stop_labels。

3. regex：按正则表达式提取
适合日期、时间、编号这类格式稳定的内容。

配置例子：
{
  "key": "date",
  "regex": "(20\\\\d{2}[./-]\\\\d{1,2}[./-]\\\\d{1,2})",
  "fallback": ""
}

可匹配：
2026.05.04
2026-05-04
2026/5/4

4. prefix_until_keywords：取关键词以及关键词前面的文字
适合项目名，例如“成都医院改造项目”“樊华似锦2期”。

配置例子：
{
  "key": "project",
  "prefix_until_keywords": ["项目", "工程", "院", "期"],
  "fallback": ""
}

含义：某一行里找到“项目/工程/院/期”后，取它前面的文字和关键词本身。

5. keywords：固定关键词匹配
适合你提前知道项目名或区域名，只想判断是否出现。

配置例子：
{
  "key": "project",
  "keywords": ["樊华似锦2期", "樊华广场"],
  "fallback": ""
}

含义：OCR 文字里出现哪个关键词，就返回哪个关键词。

6. fallback：识别不到时的备用值
如果 fallback 是空字符串，识别不到就留空。

配置例子：
{
  "key": "content",
  "label": "施工内容",
  "fallback": "未识别内容"
}

7. filename_template：文件名模板
例子：
{project}_{area}_{datetime}_{content}

如果识别结果是：
project = 樊华似锦2期
area = 5层
datetime = 2026.05.04 04:01
content = 暗门维修

文件名会类似：
樊华似锦2期_5层_2026.05.04 04_01_暗门维修.jpg

8. folder_template：文件夹模板
例子：
{project}/{area}/{date}/{content}

含义：按项目、区域、日期、施工内容创建多层文件夹。

如果不想按区域分层，可以改成：
{project}/{date}/{content}

9. stop_labels：字段结束标记
例子：
["施工区域", "施工内容", "天气", "地点"]

含义：提取“施工区域”时，遇到“施工内容/天气/地点”就停止，避免把后面的文字也吞进去。
"""
