# 图片水印OCR自动整理

这个工具会按 `config.json` 里的字段配置识别水印文字，并自动重命名图片。

当前默认配置会识别：

- `施工区域`，例如 `5层`
- `施工内容`，例如 `暗门维修`

默认命名为：

```text
5层_暗门维修.jpg
```

默认归档到：

```text
整理后图片/5层/暗门维修/5层_暗门维修.jpg
```

## 使用方法

1. 把图片放到 `待整理图片` 文件夹。
2. 双击 `安装依赖.bat` 安装OCR依赖。
3. 双击 `预览识别结果.bat` 查看识别结果。
4. 确认无误后，双击 `开始整理图片.bat` 正式整理。

## 修改识别字段

以后如果要识别别的字段，只改 `config.json`。

比如要识别 `楼层` 和 `维修事项`，可以改成：

```json
{
  "fields": [
    {
      "key": "floor",
      "label": "楼层",
      "fallback": "未识别楼层"
    },
    {
      "key": "repair",
      "label": "维修事项",
      "fallback": "未识别事项"
    }
  ],
  "filename_template": "{floor}_{repair}",
  "folder_template": "{floor}/{repair}",
  "stop_labels": ["楼层", "维修事项", "天气", "地点"]
}
```

说明：

- `label` 是水印图片上的字段名。
- `key` 是给这个字段起的英文代号，用在文件名模板里。
- `filename_template` 控制图片怎么命名。
- `folder_template` 控制文件夹怎么创建。
- `stop_labels` 用来告诉程序一个字段在哪里结束。

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

不创建子文件夹，只把图片放进 `整理后图片`：

```powershell
python .src/main.py --no-folders
```
