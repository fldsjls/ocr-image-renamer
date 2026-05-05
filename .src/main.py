from __future__ import annotations

# argparse：读取命令行参数，例如 --dry-run、--input
# json：读取 config.json 配置文件
# re：正则表达式，用来查找字段、清理文件名
# shutil：复制/移动文件
# sys：让 main() 的返回值变成程序退出状态
import argparse
import json
import re
import shutil
import sys
from pathlib import Path


# 只处理这些后缀的图片文件。
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

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

# 默认配置。
# 如果 config.json 不存在，程序会用这份默认配置创建一个 config.json。
# 平时建议改 config.json，不建议直接改这里。
DEFAULT_CONFIG = {
    # fields 表示要从水印里提取哪些字段。
    # key 是程序内部代号，label 是图片水印上的字段名，fallback 是识别失败时使用的文字。
    "fields": [
        {
            "key": "project",
            "keywords": ["妇幼保健院"],
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
    # 文件名模板。{datetime}、{area} 和 {content} 会被替换成识别出来的值。
    "filename_template": "{project}_{area}_{datetime}_{content}",
    # 文件夹模板。斜杠 / 表示创建下一层文件夹。
    "folder_template": "{project}/{area}/{date}/{content}",
    # stop_labels 用来告诉程序字段在哪里结束。
    # 例如识别“施工区域”时，遇到“施工内容”就停止。
    "stop_labels": ["施工区域", "施工内容", "天气", "地点"],
}


# 函数作用：读取命令行参数。
# 例如 --dry-run、--copy、--input、--output 都是在这里定义和解析的。
def parse_args() -> argparse.Namespace:
    """定义并读取命令行参数。"""
    parser = argparse.ArgumentParser(description="识别图片水印字段，并按配置自动重命名。")
    parser.add_argument("--input", type=Path, default=Path("待整理图片"), help="图片所在目录")
    parser.add_argument("--output", type=Path, default=Path("整理后图片"), help="整理后的输出目录")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="字段和命名规则配置")
    parser.add_argument("--lang", default="chi_sim+eng", help="Tesseract 备用OCR语言，例如 chi_sim、eng、chi_sim+eng")
    parser.add_argument("--tesseract-cmd", type=Path, help=r"tesseract.exe 路径，例如 C:\Program Files\Tesseract-OCR\tesseract.exe")
    parser.add_argument("--recursive", action="store_true", help="递归处理子目录")
    parser.add_argument("--preprocess", action="store_true", help="OCR 前先灰度、增强对比度、二值化")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不真正移动或复制")
    parser.add_argument("--copy", action="store_true", help="复制图片到输出目录；默认是移动图片")
    parser.add_argument("--no-folders", action="store_true", help="不按配置创建子文件夹，只放在输出目录")
    return parser.parse_args()


# 函数作用：读取 config.json 配置文件。
# 如果配置文件不存在，就用 DEFAULT_CONFIG 自动创建一份。
def load_config(path: Path) -> dict:
    """读取配置文件；如果配置文件不存在，就自动创建一份默认配置。"""
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG

    with path.open("r", encoding="utf-8-sig") as file:
        config = json.load(file)

    # 做一些基本检查，避免配置文件写错后程序继续乱跑。
    if "fields" not in config or not isinstance(config["fields"], list):
        raise ValueError("config.json 里必须有 fields，并且 fields 必须是数组。")

    for field in config["fields"]:
        if "key" not in field:
            raise ValueError("fields 里的每一项都必须有 key。")
        if "label" not in field and "regex" not in field and "keywords" not in field:
            raise ValueError("fields 里的每一项都必须有 label、regex 或 keywords。")

    # merged 先复制默认配置，再用 config.json 的内容覆盖。
    # 这样 config.json 只写一部分时，缺失项还能使用默认值。
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    return merged


# 函数作用：批量处理图片的主流程。
# 它负责遍历图片、OCR 识别、生成目标路径，并按设置预览/复制/移动图片。
def rename_images(
    input_dir: Path,
    config: dict,
    lang: str,
    tesseract_cmd: Path | None,
    output_dir: Path | None,
    recursive: bool,
    preprocess: bool,
    dry_run: bool,
    copy_files: bool,
    no_folders: bool,
):
    """主处理流程：找图片、OCR、生成目标路径、复制或移动。"""
    ocr = build_ocr(lang, tesseract_cmd)
    total = renamed = failed = 0

    for image_path in iter_images(input_dir, recursive):
        total += 1
        try:
            text = recognize_text(ocr, image_path, preprocess)
            target = build_target_path(image_path, text, output_dir, no_folders, config)

            if dry_run:
                print(f"[预览] {image_path.name} -> {target}")
                print(f"识别文字：{text or '<空>'}")
            elif copy_files:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image_path, target)
                print(f"[复制] {image_path.name} -> {target}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(image_path), str(target))
                print(f"[移动] {image_path.name} -> {target}")

            renamed += 1
        except Exception as exc:
            failed += 1
            print(f"[失败] {image_path}: {exc}")

    print(f"\n完成：共 {total} 张，处理 {renamed} 张，失败 {failed} 张。")


# 函数作用：找到需要处理的图片。
# recursive=False 时只找当前文件夹；recursive=True 时连子文件夹一起找。
def iter_images(input_dir: Path, recursive: bool):
    """遍历图片文件。recursive=True 时会连子文件夹一起找。"""
    pattern = "**/*" if recursive else "*"
    for path in input_dir.glob(pattern):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


# 函数作用：准备 OCR 文字识别工具。
# 程序会优先用 RapidOCR；如果没有安装 RapidOCR，就尝试使用 pytesseract。
def build_ocr(lang: str, tesseract_cmd: Path | None):
    """创建 OCR 识别工具。优先使用 RapidOCR，缺少时再使用 pytesseract。"""
    try:
        from rapidocr_onnxruntime import RapidOCR

        return {"type": "rapidocr", "engine": RapidOCR(), "lang": lang}
    except ImportError:
        pass

    try:
        import pytesseract
    except ImportError as exc:
        raise SystemExit("缺少 OCR 依赖。请先运行：pip install -r requirements.txt") from exc

    # 如果用户手动指定了 tesseract.exe 路径，就告诉 pytesseract 去哪里找它。
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)

    return {"type": "pytesseract", "engine": pytesseract, "lang": lang}


# 函数作用：识别单张图片里的文字。
# 输入图片路径，输出 OCR 识别出来的文字字符串。
# RapidOCR 可以直接接收图片路径
# RapidOCR 路线不会执行 prepare_image()
# --preprocess 当前只对 pytesseract 路线生效
# pytesseract 需要 PIL 打开图片对象
def recognize_text(ocr, image_path: Path, preprocess: bool) -> str:
    """对单张图片做 OCR，返回识别出来的文字。"""
    if ocr["type"] == "rapidocr":
        result, _ = ocr["engine"](str(image_path))
        if not result:
            return ""
        return "\n".join(item[1] for item in result if len(item) >= 2).strip()

    from PIL import Image

    with Image.open(image_path) as image:
        image = prepare_image(image, preprocess)
        return ocr["engine"].image_to_string(image, lang=ocr["lang"]).strip()


# 函数作用：在 OCR 识别前处理图片。
# 开启 --preprocess 时，会把图片转灰度、增强对比度、变黑白，让浅色水印更容易识别。
def prepare_image(image, preprocess: bool):
    """OCR 前的图片预处理。水印较浅时可以用 --preprocess 开启。"""
    if not preprocess:
        return image

    from PIL import ImageEnhance, ImageOps

    # 转灰度、增强对比度、再变成黑白图，目的是让文字更明显。
    image = ImageOps.grayscale(image)
    image = ImageEnhance.Contrast(image).enhance(2.0)
    return image.point(lambda value: 255 if value > 155 else 0)


# 函数作用：生成图片最终保存路径。
# 它会根据识别结果、文件名模板、文件夹模板，拼出完整路径。
def build_target_path(
    image_path: Path,
    text: str,
    output_dir: Path | None,
    no_folders: bool,
    config: dict,
) -> Path:
    """根据 OCR 文字和配置，生成图片最终要去的完整路径。"""
    values = extract_values(text, config)
    safe_values = {key: sanitize_filename(value, "") for key, value in values.items()}

    raw_filename = render_template(config.get("filename_template", "{area}_{content}"), safe_values)
    raw_filename = re.sub(r"_+", "_", raw_filename).strip("_")
    safe_filename = sanitize_filename(raw_filename, image_path.stem)

    if output_dir:
        if no_folders:
            target_parent = output_dir
        else:
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

    return unique_path(target_parent / f"{safe_filename}{image_path.suffix.lower()}")


# 函数作用：根据 config.json 中的 fields，一次性提取所有需要的字段。
# 例如提取 area=5层、content=暗门维修。
# labels用于得到stop_labels
def extract_values(text: str, config: dict) -> dict[str, str]:
    """按 config.json 的 fields 配置，一次性提取所有字段。"""
    labels = [field["label"] for field in config["fields"] if "label" in field]
    stop_labels = list(dict.fromkeys(labels + list(config.get("stop_labels", []))))
    values: dict[str, str] = {}

    for field in config["fields"]:
        key = field["key"]
        fallback = field.get("fallback", "")

        if "regex" in field:
            values[key] = extract_regex_field(text, field["regex"], fallback)
        elif "keywords" in field:
            values[key] = extract_keyword_field(text, field["keywords"], fallback)
        else:
            label = field["label"]
            values[key] = extract_field(text, label, stop_labels, fallback)

    return values


# 函数作用：从 OCR 文字里匹配固定关键词。
# 例如 OCR 文字里包含“妇幼保健院”，就把 project 字段设为“妇幼保健院”。
def extract_keyword_field(text: str, keywords: list[str], fallback: str) -> str:
    """按关键词列表提取字段；匹配到哪个关键词，就返回哪个关键词。"""
    compact_text = normalize_text(text)

    for keyword in keywords:
        compact_keyword = normalize_text(keyword)
        if compact_keyword and compact_keyword in compact_text:
            return keyword

    return fallback


# 函数作用：用正则表达式从 OCR 文字里提取字段。
# 例如从“2026.04.23 11:08”中提取日期，保存到 date 字段。
def extract_regex_field(text: str, pattern: str, fallback: str) -> str:
    """按正则表达式提取字段；如果没有匹配到，就返回 fallback。"""
    match = re.search(pattern, text)
    if not match:
        return fallback

    # 如果正则里有括号，优先返回第一个括号捕获到的内容。
    # 如果没有括号，就返回整个匹配结果。
    if match.groups():
        return match.group(1).strip()
    return match.group(0).strip()


# 函数作用：从 OCR 文字里提取某个字段的值。
# 例如从“施工区域5层施工内容暗门维修”中，按 label="施工区域" 提取出“5层”。
def extract_field(text: str, label: str, stop_labels: list[str], fallback: str) -> str:
    """从 OCR 文字中提取某个字段后面的值。"""
    compact_label = normalize_text(label)

    # 优先按“单行”提取。
    # 水印通常是一行一个字段，例如：
    # 施工区域5层
    # 施工内容暗门维修
    # 这样可以避免“天气/地点”被 OCR 识别错后，把后面的地址也吞进文件名。
    for line in text.splitlines():
        compact_line = normalize_text(line)
        if not compact_line or compact_label not in compact_line:
            continue

        value = compact_line.split(compact_label, 1)[1].strip(" :：，,。;；")
        if value:
            return value

    # 如果单行提取失败，再用整段文字提取。
    # 这可以兼容 OCR 把字段和值识别到不同行的情况。
    compact_text = normalize_text(text)
    compact_stops = [normalize_text(item) for item in stop_labels if normalize_text(item) != compact_label]

    # 示例：
    # OCR文字：施工区域5层施工内容暗门维修天气晴
    # label：施工区域
    # stop_labels：施工内容、天气、地点
    # 提取结果：5层
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


# 函数作用：规范化 OCR 文字。
# 主要是去掉空格和换行，避免 OCR 把“施工区域”识别成“施 工 区 域”后匹配失败。
def normalize_text(text: str) -> str:
    """去掉空格和换行，方便匹配 OCR 文字。"""
    return re.sub(r"\s+", "", text)


# 函数作用：把模板转换成真实文字。
# 例如把 "{area}_{content}" 替换成 "5层_暗门维修"。
def render_template(template: str, values: dict[str, str]) -> str:
    """把模板里的 {字段名} 替换成识别结果。"""
    def replace_placeholder(match: re.Match) -> str:
        key = match.group(1)
        return str(values.get(key, ""))

    return re.sub(r"{([^{}]+)}", replace_placeholder, template)


# 函数作用：清理文件名。
# 把 Windows 文件名不允许的字符替换掉，并处理空文件名、保留名、过长文件名。
def sanitize_filename(name: str, fallback: str) -> str:
    """把文字变成安全的 Windows 文件名。"""
    # 替换 Windows 文件名不允许的字符。
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # 去掉多余空白、首尾点号，避免生成奇怪文件名。
    name = re.sub(r"\s+", "", name).strip(" .")
    name = name or fallback

    if name.upper() in WINDOWS_RESERVED_NAMES:
        name = f"{name}_file"

    # 控制长度，避免文件名过长。
    return name[:120]


# 函数作用：避免覆盖已有文件。
# 如果目标文件已经存在，就自动生成 xxx_2.jpg、xxx_3.jpg 这样的新名字。
def unique_path(path: Path) -> Path:
    """如果目标文件已存在，就自动加 _2、_3，避免覆盖旧文件。"""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 2

    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


# 函数作用：程序总入口。
# 它把“读取参数、读取配置、检查文件夹、开始处理图片”串起来。
def main() -> int:
    """程序入口。把前面的函数按顺序组织起来。"""
    args = parse_args()
    input_dir = args.input.resolve()
    output_dir = args.output.resolve() if args.output else None
    config = load_config(args.config.resolve())

    # 没有“待整理图片”文件夹时，自动创建一个，方便第一次使用。
    input_dir.mkdir(parents=True, exist_ok=True)
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"图片目录不存在：{input_dir}")

    rename_images(
        input_dir=input_dir,
        config=config,
        lang=args.lang,
        tesseract_cmd=args.tesseract_cmd,
        output_dir=output_dir,
        recursive=args.recursive,
        preprocess=args.preprocess,
        dry_run=args.dry_run,
        copy_files=args.copy,
        no_folders=args.no_folders,
    )
    return 0


# 只有直接运行这个文件时，才执行 main()。
# 如果以后这个文件被其他 Python 文件 import，就不会自动开始整理图片。
if __name__ == "__main__":
    sys.exit(main())
