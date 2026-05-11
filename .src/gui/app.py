from __future__ import annotations

import contextlib
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from config_loader import DEFAULT_CONFIG, validate_config
from mode_options import FolderMatchModeOptions, OcrFolderMatchModeOptions, OcrModeOptions
from mode_runner import run_mode
from tesseract_detector import find_tesseract_cmd
from .config_help import CONFIG_HELP_TEXT


# gui/app.py 是给普通用户使用的图形外壳。
# 它不重新实现整理逻辑，只把界面上的选项转换成 processor/folder_matcher 的参数。

class QueueWriter:
    """把 print 输出转发到队列，供主线程安全写入界面。"""

    # 保存后台输出队列引用。
    def __init__(self, output_queue: queue.Queue[str]):
        self.output_queue = output_queue

    # 接收 print 写入的文本，并放入线程安全队列。
    def write(self, text: str) -> int:
        if text:
            self.output_queue.put(text)
        return len(text)

    # 兼容文件对象接口，队列写入不需要实际刷新。
    def flush(self) -> None:
        pass


class App(tk.Tk):
    # 初始化主窗口状态、默认路径和 Tesseract 检测结果。
    def __init__(self) -> None:
        super().__init__()
        self.title("图片水印 OCR 自动整理工具")
        self.geometry("900x640")
        self.minsize(820, 560)

        self.output_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.detected_tesseract: Path | None = find_tesseract_cmd()

        self.input_var = tk.StringVar(value=str(Path("待整理图片").resolve()))
        self.output_var = tk.StringVar(value=str(Path("整理后图片").resolve()))
        self.config_var = tk.StringVar(value=str(Path("config.json").resolve()))
        self.tesseract_var = tk.StringVar(value=str(self.detected_tesseract) if self.detected_tesseract else "")
        self.lang_var = tk.StringVar(value="chi_sim+eng")
        self.mode_var = tk.StringVar(value="ocr")

        self.dry_run_var = tk.BooleanVar(value=True)
        self.copy_var = tk.BooleanVar(value=False)
        self.recursive_var = tk.BooleanVar(value=False)
        self.preprocess_var = tk.BooleanVar(value=False)
        self.no_folders_var = tk.BooleanVar(value=False)

        self.build_ui()
        if not self.detected_tesseract:
            self.preprocess_var.set(False)
        self.update_mode_controls()
        self.write_tesseract_status()
        self.after(100, self.drain_output_queue)

    # 创建主窗口中的路径选择、模式选项和输出区域。
    def build_ui(self) -> None:
        """创建窗口控件。"""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        container = ttk.Frame(self, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(1, weight=1)

        ttk.Label(container, text="图片文件夹").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(container, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(container, text="选择", command=lambda: self.choose_folder(self.input_var)).grid(row=0, column=2)

        ttk.Label(container, text="输出/项目文件夹").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(container, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(container, text="选择", command=lambda: self.choose_folder(self.output_var)).grid(row=1, column=2)

        ttk.Label(container, text="配置文件").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(container, textvariable=self.config_var).grid(row=2, column=1, sticky="ew", padx=8)
        ttk.Button(container, text="选择", command=self.choose_config).grid(row=2, column=2)
        ttk.Button(container, text="编辑", command=self.open_config_editor).grid(row=2, column=3, padx=(8, 0))

        ttk.Label(container, text="Tesseract 路径").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(container, textvariable=self.tesseract_var).grid(row=3, column=1, sticky="ew", padx=8)
        ttk.Button(container, text="选择", command=self.choose_tesseract).grid(row=3, column=2)

        mode_frame = ttk.LabelFrame(self, text="模式", padding=12)
        mode_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        mode_frame.columnconfigure(2, weight=1)
        ttk.Radiobutton(mode_frame, text="OCR 识别整理", variable=self.mode_var, value="ocr", command=self.update_mode_controls).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(mode_frame, text="自动匹配已有文件夹", variable=self.mode_var, value="match", command=self.update_mode_controls).grid(row=0, column=1, sticky="w", padx=20)
        ttk.Radiobutton(mode_frame, text="OCR 后匹配已有文件夹", variable=self.mode_var, value="ocr_match", command=self.update_mode_controls).grid(row=0, column=2, sticky="w")

        options = ttk.Frame(mode_frame)
        options.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.dry_run_check = ttk.Checkbutton(options, text="预览，不移动/复制", variable=self.dry_run_var, command=self.update_mode_controls)
        self.dry_run_check.grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.copy_check = ttk.Checkbutton(options, text="复制，保留原图", variable=self.copy_var, command=self.update_mode_controls)
        self.copy_check.grid(row=0, column=1, sticky="w", padx=(0, 16))
        ttk.Checkbutton(options, text="递归处理子目录", variable=self.recursive_var).grid(row=0, column=2, sticky="w", padx=(0, 16))
        self.preprocess_check = ttk.Checkbutton(options, text="OCR 预处理", variable=self.preprocess_var)
        self.preprocess_check.grid(row=1, column=0, sticky="w", pady=(8, 0), padx=(0, 16))
        self.no_folders_check = ttk.Checkbutton(options, text="不创建子文件夹", variable=self.no_folders_var)
        self.no_folders_check.grid(row=1, column=1, sticky="w", pady=(8, 0), padx=(0, 16))

        lang_frame = ttk.Frame(mode_frame)
        lang_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.lang_label = ttk.Label(lang_frame, text="Tesseract 备用语言")
        self.lang_label.grid(row=0, column=0, sticky="w")
        self.lang_entry = ttk.Entry(lang_frame, textvariable=self.lang_var, width=20)
        self.lang_entry.grid(row=0, column=1, sticky="w", padx=8)

        output_frame = ttk.LabelFrame(self, text="运行输出", padding=8)
        output_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap="word", height=16)
        self.output_text.grid(row=0, column=0, sticky="nsew")

        actions = ttk.Frame(self, padding=(12, 0, 12, 12))
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        self.run_button = ttk.Button(actions, text="开始运行", command=self.start_run)
        self.run_button.grid(row=0, column=1, padx=(8, 0))
        ttk.Button(actions, text="清空输出", command=self.clear_output).grid(row=0, column=2, padx=(8, 0))

    # 打开文件夹选择框，并把结果写回指定变量。
    def choose_folder(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(title="请选择文件夹")
        if selected:
            variable.set(selected)

    # 打开 config.json 选择框，并把结果写回配置路径。
    def choose_config(self) -> None:
        selected = filedialog.askopenfilename(title="请选择配置文件", filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if selected:
            self.config_var.set(selected)

    # 读取当前配置文件内容，并打开配置编辑窗口。
    def open_config_editor(self) -> None:
        """打开 config.json 编辑窗口。"""
        config_path = Path(self.config_var.get()).expanduser()
        if config_path.exists():
            try:
                content = config_path.read_text(encoding="utf-8-sig")
            except OSError as exc:
                messagebox.showerror("读取失败", str(exc))
                return
        else:
            content = json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2)

        ConfigEditor(self, config_path, content)

    # 打开 tesseract.exe 选择框，并同步更新 OCR 预处理可用状态。
    def choose_tesseract(self) -> None:
        selected = filedialog.askopenfilename(title="请选择 tesseract.exe", filetypes=[("EXE 文件", "*.exe"), ("所有文件", "*.*")])
        if selected:
            self.tesseract_var.set(selected)
            self.detected_tesseract = find_tesseract_cmd(Path(selected))
            if not self.detected_tesseract:
                self.preprocess_var.set(False)
                messagebox.showwarning("Tesseract 不可用", "选择的文件不是可用的 tesseract.exe，OCR 预处理已禁用。")
            self.update_mode_controls()

    # 根据当前模式切换选项的启用状态和互斥关系。
    def update_mode_controls(self) -> None:
        """根据当前模式启用/禁用相关选项。"""
        mode = self.mode_var.get()
        uses_ocr = mode in {"ocr", "ocr_match"}
        has_tesseract = self.get_tesseract_cmd() is not None

        if self.dry_run_var.get():
            self.copy_var.set(False)
        set_ttk_enabled(self.copy_check, not self.dry_run_var.get())

        set_ttk_enabled(self.preprocess_check, uses_ocr and has_tesseract)
        if not has_tesseract:
            self.preprocess_var.set(False)

        set_ttk_enabled(self.no_folders_check, mode == "ocr")
        for widget in [self.lang_label, self.lang_entry]:
            set_ttk_enabled(widget, uses_ocr)

    # 创建后台线程开始执行当前选择的整理任务。
    def start_run(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在运行", "当前任务还没有结束。")
            return

        try:
            options = self.collect_options()
        except ValueError as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self.run_button.configure(state="disabled")
        self.write_output("\n========== 开始运行 ==========\n")
        self.worker = threading.Thread(target=self.run_task, args=(options,), daemon=True)
        self.worker.start()

    # 从界面读取参数并转换成对应模式的选项对象。
    def collect_options(self) -> OcrModeOptions | FolderMatchModeOptions | OcrFolderMatchModeOptions:
        """读取界面参数，并做最基本的路径检查。"""
        input_dir = Path(self.input_var.get()).expanduser()
        output_dir = Path(self.output_var.get()).expanduser()
        config_path = Path(self.config_var.get()).expanduser()

        if not input_dir.exists() or not input_dir.is_dir():
            raise ValueError(f"图片文件夹不存在：{input_dir}")

        mode = self.mode_var.get()

        if mode in {"match", "ocr_match"} and (not output_dir.exists() or not output_dir.is_dir()):
            raise ValueError(f"项目文件夹不存在：{output_dir}")

        if mode in {"ocr", "ocr_match"} and not config_path.exists():
            raise ValueError(f"配置文件不存在：{config_path}")

        if mode == "match":
            return FolderMatchModeOptions(
                input_dir=input_dir.resolve(),
                folder_root=output_dir.resolve(),
                recursive=self.recursive_var.get(),
                dry_run=self.dry_run_var.get(),
                copy_files=self.copy_var.get(),
            )

        if mode == "ocr_match":
            return OcrFolderMatchModeOptions(
                input_dir=input_dir.resolve(),
                folder_root=output_dir.resolve(),
                config_path=config_path.resolve(),
                lang=self.lang_var.get().strip() or "chi_sim+eng",
                tesseract_cmd=self.get_tesseract_cmd(),
                recursive=self.recursive_var.get(),
                preprocess=self.preprocess_var.get(),
                dry_run=self.dry_run_var.get(),
                copy_files=self.copy_var.get(),
            )

        return OcrModeOptions(
            input_dir=input_dir.resolve(),
            output_dir=output_dir.resolve(),
            config_path=config_path.resolve(),
            lang=self.lang_var.get().strip() or "chi_sim+eng",
            tesseract_cmd=self.get_tesseract_cmd(),
            recursive=self.recursive_var.get(),
            preprocess=self.preprocess_var.get(),
            dry_run=self.dry_run_var.get(),
            copy_files=self.copy_var.get(),
            no_folders=self.no_folders_var.get(),
        )

    # 在线程中调用模式执行器，并把输出重定向到界面。
    def run_task(self, options: OcrModeOptions | FolderMatchModeOptions | OcrFolderMatchModeOptions) -> None:
        """后台线程执行整理任务，避免窗口卡住。"""
        writer = QueueWriter(self.output_queue)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                run_mode(options)
            self.output_queue.put("\n========== 运行结束 ==========\n")
        except Exception as exc:
            self.output_queue.put(f"\n[错误] {exc}\n")
        finally:
            self.output_queue.put("__TASK_DONE__")

    # 定时把后台线程输出刷入文本框。
    def drain_output_queue(self) -> None:
        """主线程定时把后台输出写到文本框。"""
        try:
            while True:
                text = self.output_queue.get_nowait()
                if text == "__TASK_DONE__":
                    self.run_button.configure(state="normal")
                else:
                    self.write_output(text)
        except queue.Empty:
            pass
        self.after(100, self.drain_output_queue)

    # 向输出文本框追加一段文本并滚动到底部。
    def write_output(self, text: str) -> None:
        self.output_text.insert("end", text)
        self.output_text.see("end")

    # 清空输出文本框。
    def clear_output(self) -> None:
        self.output_text.delete("1.0", "end")

    # 根据界面路径或系统环境返回可用的 tesseract.exe。
    def get_tesseract_cmd(self) -> Path | None:
        """按界面填写路径和系统环境检测 tesseract.exe。"""
        text = self.tesseract_var.get().strip()
        preferred = Path(text).expanduser() if text else None
        self.detected_tesseract = find_tesseract_cmd(preferred)
        return self.detected_tesseract

    # 在输出区域提示当前 Tesseract 检测状态。
    def write_tesseract_status(self) -> None:
        """启动时在输出框提示 Tesseract 检测结果。"""
        if self.detected_tesseract:
            self.write_output(f"[检测] 已找到 Tesseract：{self.detected_tesseract}\n")
        else:
            self.write_output("[检测] 未找到 tesseract.exe，OCR 预处理已禁用。\n")


class ConfigEditor(tk.Toplevel):
    """config.json 编辑窗口。"""

    # 初始化配置编辑弹窗和说明区域。
    def __init__(self, parent: App, config_path: Path, content: str) -> None:
        super().__init__(parent)
        self.parent = parent
        self.config_path = config_path
        self.title("编辑配置文件")
        self.geometry("760x620")
        self.minsize(680, 500)
        self.transient(parent)

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        header = ttk.Frame(self, padding=(12, 12, 12, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="配置文件").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=str(config_path)).grid(row=0, column=1, sticky="w", padx=8)

        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=3)
        body.rowconfigure(2, weight=2)
        body.columnconfigure(0, weight=1)
        self.editor = scrolledtext.ScrolledText(body, wrap="none", undo=True)
        self.editor.grid(row=0, column=0, sticky="nsew")
        self.editor.insert("1.0", content)

        hint = ttk.Label(
            body,
            text="保存前会校验 JSON 和 fields 结构；字段名、模板、关键词可以直接修改。",
        )
        hint.grid(row=1, column=0, sticky="w", pady=(8, 0))

        help_box = ttk.LabelFrame(body, text="配置说明和例子", padding=8)
        help_box.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        help_box.rowconfigure(0, weight=1)
        help_box.columnconfigure(0, weight=1)
        self.help_text = scrolledtext.ScrolledText(help_box, wrap="word", height=10)
        self.help_text.grid(row=0, column=0, sticky="nsew")
        self.help_text.insert("1.0", CONFIG_HELP_TEXT)
        self.help_text.configure(state="disabled")

        actions = ttk.Frame(self, padding=(12, 0, 12, 12))
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="格式化", command=self.format_json).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(actions, text="保存", command=self.save).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(actions, text="关闭", command=self.destroy).grid(row=0, column=3, padx=(8, 0))

        self.grab_set()

    # 解析编辑器中的 JSON，并校验是否符合配置结构。
    def parse_editor_json(self) -> dict:
        """读取编辑器内容，并校验 JSON 和配置结构。"""
        raw_text = self.editor.get("1.0", "end").strip()
        if not raw_text:
            raise ValueError("配置内容不能为空。")

        try:
            config = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 格式错误：第 {exc.lineno} 行，第 {exc.colno} 列：{exc.msg}") from exc

        if not isinstance(config, dict):
            raise ValueError("配置文件顶层必须是 JSON 对象。")

        validate_config(config)
        return config

    # 将当前配置内容重新排版为缩进 JSON。
    def format_json(self) -> None:
        """格式化当前 JSON 内容。"""
        try:
            config = self.parse_editor_json()
        except ValueError as exc:
            messagebox.showerror("配置错误", str(exc), parent=self)
            return

        formatted = json.dumps(config, ensure_ascii=False, indent=2)
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", formatted)

    # 保存校验通过的配置文件，并更新主窗口配置路径。
    def save(self) -> None:
        """校验并保存配置文件。"""
        try:
            config = self.parse_editor_json()
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ValueError) as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return

        self.parent.config_var.set(str(self.config_path.resolve()))
        self.parent.write_output(f"[配置] 已保存：{self.config_path.resolve()}\n")
        messagebox.showinfo("保存成功", "配置文件已保存。", parent=self)


# 启动 Tkinter 主窗口。
def main() -> None:
    app = App()
    app.mainloop()


# 统一设置 ttk 控件的普通/禁用状态。
def set_ttk_enabled(widget: ttk.Widget, enabled: bool) -> None:
    """统一切换 ttk 控件启用状态。"""
    widget.state(["!disabled"] if enabled else ["disabled"])


if __name__ == "__main__":
    main()

