# 图片水印 OCR 自动整理工具

这个工具用于批量识别图片水印文字，并根据识别结果自动重命名图片。

适合处理水印里包含这些信息的施工照片：

- 项目或工程名称，例如：`成都医院改造项目`
- 施工区域，例如：`5层`
- 日期时间，例如：`2026.04.23 11:05`
- 施工内容，例如：`暗门维修`

## 当前默认效果

如果 OCR 识别到：

```text
成都医院改造项目
2026.04.23 11:05
施工区域5层
施工内容暗门维修
```

默认会整理到输出目录：

```text
整理后图片/
```

文件名会变成：

```text
成都医院改造项目_5层_2026.04.2311_05_暗门维修.jpg
```

注意：Windows 文件名不能包含冒号 `:`，所以 `11:05` 会自动变成 `11_05`。

## 使用方法

1. 把图片放到 `待整理图片` 文件夹。
2. 双击 `安装依赖.bat` 安装 OCR 依赖。
3. 双击 `预览识别结果.bat` 查看识别和命名结果。
4. 确认无误后，双击 `开始整理图片.bat` 正式整理。

也可以双击 `打开操作界面.bat` 使用图形界面。界面里可以选择图片文件夹、输出文件夹、配置文件，并切换 `OCR 识别整理` 或 `自动匹配已有文件夹` 两种模式。

图形界面会自动检测电脑里是否有 `tesseract.exe`。如果没有检测到，`OCR 预处理` 会自动禁用，因为这个选项只对 Tesseract 备用识别路线有效；RapidOCR 路线会直接识别原图。

图形界面里的配置文件一栏提供 `编辑` 按钮，可以直接修改 `config.json`。保存前会检查 JSON 格式和字段结构，避免配置写错后程序继续运行。

PowerShell 中运行 `.bat` 文件时，需要加 `.\`：

```powershell
.\预览识别结果.bat
.\开始整理图片.bat
```

## 配置文件

主要修改 `config.json`，一般不需要改 Python 代码。

当前配置包含 5 个字段：

```json
{
  "fields": [
    {
      "key": "project",
      "prefix_until_keywords": ["项目", "工程"],
      "fallback": ""
    },
    {
      "key": "area",
      "label": "施工区域",
      "fallback": ""
    },
    {
      "key": "date",
      "regex": "(20\\d{2}[./-]\\d{1,2}[./-]\\d{1,2})",
      "fallback": ""
    },
    {
      "key": "datetime",
      "regex": "(20\\d{2}[./-]\\d{1,2}[./-]\\d{1,2}\\s+\\d{1,2}:\\d{2})",
      "fallback": ""
    },
    {
      "key": "content",
      "label": "施工内容",
      "fallback": ""
    }
  ],
  "filename_template": "{project}_{area}_{datetime}_{content}",
  "folder_template": "{project}/{area}/{date}/{content}",
  "stop_labels": ["施工区域", "施工内容", "天气", "地点"],
  "avoid_keyword_fields": ["area", "content"]
}
```

字段说明：

- `key`：字段代号，用在文件名和文件夹模板里。
- `label`：按水印字段名提取，例如 `施工区域5层`。
- `regex`：按正则表达式提取，例如日期、时间。
- `prefix_until_keywords`：找到关键词，并取关键词及其前面的文字，例如 `XX项目`、`XX工程`。
- `fallback`：识别不到时的备用内容。当前为空，表示识别不到就不写入文件名。
- `avoid_keyword_fields`：避免使用 `keywords` 快速匹配的字段，默认是 `area` 和 `content`。

图形界面配置文件一栏提供 `避免匹配` 和 `快速添加`：

- `避免匹配`：勾选后，该字段不会使用 `keywords` 做快速匹配。
- `项目替换`：project 匹配成功后，会把项目名替换成这里填写的固定内容；这是单个值，保存新内容会覆盖旧内容，`重置` 会清空。
- `快速添加`：`project` 会追加到 `prefix_until_keywords`；`area` 和 `content` 会修改对应 `label`；`stop_labels` 会追加字段结束标记。

如果生成的新文件名为空、和原文件名一样，或只有日期/时间，程序会判定为失败并跳过，不会创建文件夹，也不会移动或复制图片。

## 修改文件夹结构

文件夹结构由 `folder_template` 控制。

当前是：

```json
"folder_template": "{project}/{area}/{date}/{content}"
```

如果不想创建 `area` 这一层，可以改成：

```json
"folder_template": "{project}/{date}/{content}"
```

如果只想按项目和日期归档，可以改成：

```json
"folder_template": "{project}/{date}"
```

## 修改文件名

文件名由 `filename_template` 控制。

当前是：

```json
"filename_template": "{project}_{area}_{datetime}_{content}"
```

如果不想在文件名里放项目名，可以改成：

```json
"filename_template": "{area}_{datetime}_{content}"
```

如果不想在文件名里放具体时间，只放日期，可以改成：

```json
"filename_template": "{project}_{area}_{date}_{content}"
```

## 常用命令

只预览，不移动图片：

```powershell
python .src/main.py --dry-run
```

正式整理：

```powershell
python .src/main.py
```

复制到输出目录，保留原图：

```powershell
python .src/main.py --copy
```

不创建子文件夹，只把图片放进 `整理后图片`。这也是图形界面和常用 `.bat` 的默认行为：

```powershell
python .src/main.py --no-folders
```

按图片名自动匹配已有项目文件夹，不做 OCR：

```powershell
python .src/main.py --match-folders
```

这个模式会把 `待整理图片` 里的图片名和 `整理后图片` 下已有的项目文件夹名匹配。匹配成功就把图片放入对应文件夹，匹配失败就跳过，不会创建新项目文件夹。

如果已有项目文件夹不在 `整理后图片`，可以指定文件夹根目录：

```powershell
python .src/main.py --match-folders --folder-root "D:\项目文件夹"
```

如果想弹出窗口选择图片所在文件夹，可以使用：

```powershell
python .src/main.py --match-folders --select-input
```

也可以直接双击 `自动匹配文件夹.bat`，选择图片文件夹后开始匹配。

先 OCR 识别生成新图片名，再用新图片名匹配已有项目文件夹：

```powershell
python .src/main.py --ocr-match-folders
```

这个模式会先按 `config.json` 生成整理后的图片名，然后用这个新图片名去匹配 `整理后图片` 下已有的项目文件夹。匹配成功才移动/复制进去，匹配失败会跳过，不会创建新项目文件夹。

## 常见问题

如果某个字段没有识别到，默认会留空，不会写成 `未识别区域`。

如果所有字段都没有识别到，程序会用原图片名作为文件名，避免生成空文件名。

如果 OCR 把 `天气`、`地点` 识别错，程序会优先按行提取 `施工区域` 和 `施工内容`，避免把后面的地址误拼进文件名。
