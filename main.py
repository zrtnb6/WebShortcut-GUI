import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, BooleanVar
import os
import webbrowser
import re
from tkinterdnd2 import DND_FILES, TkinterDnD

def get_invalid_chars():
    return '<>:"/\\|?*'

def safe_filename(name):
    for c in get_invalid_chars():
        name = name.replace(c, '_')
    return name.strip() or "网站快捷方式"

def log(text, error=False):
    log_output.insert(tk.END, text + "\n")
    if error:
        log_output.tag_add("error", "end-2l", "end-1l")
        log_output.tag_config("error", foreground="red")
    log_output.see(tk.END)

def generate_shortcuts(input_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    success, failed = 0, 0

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            match = re.match(r'^(.*?)\s+(https?://\S+)$', line)
            if match:
                name = safe_filename(match.group(1))
                url = match.group(2)
                shortcut_path = os.path.join(output_dir, f"{name}.url")
                with open(shortcut_path, 'w', encoding='ascii') as shortcut:
                    shortcut.write(f"""[InternetShortcut]
URL={url}
IDList=
HotKey=0
IconIndex=0
""")
                log(f"✅ 已创建: {name}.url")
                success += 1
            else:
                log(f"⚠️ 格式错误: {line}", error=True)
                failed += 1

    log(f"\n✅ 操作完成：成功 {success} 个，失败 {failed} 个")
    if success and open_dir_var.get():
        webbrowser.open(output_dir)

def choose_input_file():
    file_path = filedialog.askopenfilename(filetypes=[("文本文件", "*.txt")])
    if file_path:
        entry_input.delete(0, tk.END)
        entry_input.insert(0, file_path)

def choose_output_folder():
    folder_path = filedialog.askdirectory()
    if folder_path:
        entry_output.delete(0, tk.END)
        entry_output.insert(0, folder_path)

def start_generation():
    input_path = entry_input.get().strip()
    output_path = entry_output.get().strip()

    if not os.path.exists(input_path):
        messagebox.showerror("错误", "网址文件不存在！")
        return
    if not os.path.exists(output_path):
        messagebox.showerror("错误", "输出路径不存在！")
        return

    log_output.delete('1.0', tk.END)
    generate_shortcuts(input_path, output_path)

def clear_log():
    log_output.delete('1.0', tk.END)

def drop_input(event):
    path = event.data
    if path.startswith('{') and path.endswith('}'):
        path = path[1:-1]
    if os.path.isfile(path):
        entry_input.delete(0, tk.END)
        entry_input.insert(0, path)

def get_desktop_path():
    return os.path.join(os.path.expanduser("~"), "Desktop")

# ========== 主窗口 ==========
window = TkinterDnD.Tk()
window.title("批量网址快捷方式生成器")
window.geometry("700x530")
window.minsize(600, 450)
window.configure(bg="#f4f4f4")

default_font = ("微软雅黑", 10)
main_frame = tk.Frame(window, bg="#f4f4f4")
main_frame.pack(fill="both", expand=True, padx=10, pady=10)

# 网址文档路径
label_input = tk.Label(main_frame, text="网址文档路径：", font=default_font, bg="#f4f4f4")
label_input.grid(row=0, column=0, sticky="w")

entry_input = tk.Entry(main_frame, font=default_font)
entry_input.grid(row=0, column=1, sticky="ew", padx=5)
entry_input.drop_target_register(DND_FILES)
entry_input.dnd_bind('<<Drop>>', drop_input)

btn_input = tk.Button(main_frame, text="浏览", font=default_font, bg="#ddddff", command=choose_input_file)
btn_input.grid(row=0, column=2)

# 输出路径
label_output = tk.Label(main_frame, text="输出文件夹路径：", font=default_font, bg="#f4f4f4")
label_output.grid(row=1, column=0, sticky="w", pady=5)

entry_output = tk.Entry(main_frame, font=default_font)
entry_output.grid(row=1, column=1, sticky="ew", padx=5)
entry_output.insert(0, get_desktop_path())

btn_output = tk.Button(main_frame, text="选择", font=default_font, bg="#ddddff", command=choose_output_folder)
btn_output.grid(row=1, column=2)

# 生成后打开输出目录勾选框
open_dir_var = tk.BooleanVar(value=True)
check_open_dir = tk.Checkbutton(main_frame, text="生成后自动打开输出目录", font=default_font, bg="#f4f4f4", variable=open_dir_var)
check_open_dir.grid(row=2, column=1, sticky="w", pady=5)

# 按钮容器
frame_btn = tk.Frame(main_frame, bg="#f4f4f4")
frame_btn.grid(row=3, column=0, columnspan=3, pady=10)

btn_start = tk.Button(frame_btn, text="开始生成", width=20, font=default_font, bg="#4CAF50", fg="white", command=start_generation)
btn_start.pack(side=tk.LEFT, padx=10)

btn_clear = tk.Button(frame_btn, text="清空日志", width=10, font=default_font, bg="#2196F3", fg="white", command=clear_log)
btn_clear.pack(side=tk.LEFT)

# 日志输出框
log_output = scrolledtext.ScrolledText(main_frame, font=("Consolas", 10))
log_output.grid(row=4, column=0, columnspan=3, sticky="nsew")

# 自适应布局
main_frame.columnconfigure(1, weight=1)
main_frame.rowconfigure(4, weight=1)

window.mainloop()
