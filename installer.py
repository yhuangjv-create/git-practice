"""简易安装器：选择目录 → 拷文件 → 创建快捷方式。

PyInstaller 打包后作为安装包 EXE 发布。
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "ClaraRecorder"
APP_TITLE = "鼠标键盘活动记录重复器 V1.6.1"
COMPANY = "Clara"
VERSION = "1.6.1"


def _resource_dir() -> Path:
    """PyInstaller 打包后资源在 _MEIPASS 临时目录。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent / "dist"


def _copy_shortcut(target: Path, shortcut_path: Path, desc: str = "") -> None:
    """用 ctypes 创建 .lnk 快捷方式。"""
    import pythoncom
    from win32com.shell import shell, shellcon  # noqa: F401

    pythoncom.CoInitialize()
    try:
        shortcut = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
        )
        shortcut.SetPath(str(target))
        shortcut.SetWorkingDirectory(str(target.parent))
        if desc:
            shortcut.SetDescription(desc)
        persist = shortcut.QueryInterface(pythoncom.IID_IPersistFile)
        persist.Save(str(shortcut_path), 0)
    finally:
        pythoncom.CoUninitialize()


def _create_shortcut_simple(target: Path, shortcut_path: Path) -> None:
    """不依赖 pywin32 的快捷方式创建（用 PowerShell WScript.Shell）。"""
    import subprocess

    ps = (
        '$s = (New-Object -ComObject WScript.Shell).CreateShortcut("'
        + str(shortcut_path).replace("\\", "/")
        + '"); '
        + f'$s.TargetPath = "{target}"; '
        + f'$s.WorkingDirectory = "{target.parent}"; '
        + '$s.Save()'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def _get_desktop_dir() -> Path:
    """获取桌面目录（兼容 OneDrive 重定向）。"""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as k:
            val, _ = winreg.QueryValueEx(k, "Desktop")
            val = os.path.expandvars(val)
            return Path(val)
    except Exception:
        return Path.home() / "Desktop"


class InstallerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} - 安装向导")
        self.root.geometry("560x420")
        self.root.resizable(False, False)
        self.root.configure(bg="#f0f2f5")

        self._page = 0
        self._install_dir = tk.StringVar(value=r"C:\Program Files\ClaraRecorder")
        self._desktop_sc = tk.BooleanVar(value=True)
        self._startmenu_sc = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self) -> None:
        self.container = tk.Frame(self.root, bg="#f0f2f5")
        self.container.pack(fill="both", expand=True, padx=30, pady=20)

        self.header = tk.Label(
            self.container, text="", font=("Segoe UI", 16, "bold"),
            bg="#f0f2f5", fg="#1a1a2e",
        )
        self.header.pack(anchor="w", pady=(0, 10))

        self.body = tk.Frame(self.container, bg="#ffffff", highlightthickness=1,
                             highlightbackground="#d0d5dd")
        self.body.pack(fill="both", expand=True)

        self.footer = tk.Frame(self.container, bg="#f0f2f5")
        self.footer.pack(fill="x", pady=(15, 0))

        self.btn_back = ttk.Button(self.footer, text="< 上一步", width=10, command=self._prev)
        self.btn_next = ttk.Button(self.footer, text="下一步 >", width=10, command=self._next)
        self.btn_cancel = ttk.Button(self.footer, text="取消", width=8, command=self._cancel)

        self.btn_back.pack(side="left")
        self.btn_cancel.pack(side="right")
        self.btn_next.pack(side="right", padx=(0, 10))

        self._show_page(0)

    def _clear_body(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()

    def _show_page(self, n: int) -> None:
        self._page = n
        self._clear_body()

        if n == 0:
            self._page_welcome()
        elif n == 1:
            self._page_options()
        elif n == 2:
            self._page_progress()
        elif n == 3:
            self._page_finish()

        self.btn_back.config(state=("normal" if n > 0 and n != 2 else "disabled"))
        self.btn_next.config(text=("安装" if n == 1 else ("完成" if n == 3 else "下一步 >")))
        if n == 2:
            self.btn_next.config(state="disabled")
            self.btn_back.config(state="disabled")

    def _page_welcome(self) -> None:
        self.header.config(text=f"欢迎使用 {APP_TITLE} 安装向导")
        tk.Label(
            self.body,
            text=(
                f"本程序将引导你在电脑上安装 {APP_TITLE}。\n\n"
                f"建议在安装前关闭所有其他应用程序，以确保安装过程顺利完成。\n\n"
                f"版本：V{VERSION}  |  出品：{COMPANY}"
            ),
            font=("Segoe UI", 10), bg="#ffffff", fg="#333",
            justify="left", wraplength=460,
        ).pack(anchor="w", padx=25, pady=25)

    def _page_options(self) -> None:
        self.header.config(text="选择安装目录")
        frm = tk.Frame(self.body, bg="#ffffff")
        frm.pack(fill="x", padx=25, pady=25)

        tk.Label(frm, text="安装到：", font=("Segoe UI", 10), bg="#ffffff").grid(
            row=0, column=0, sticky="w", pady=5
        )
        entry = tk.Entry(frm, textvariable=self._install_dir, width=55)
        entry.grid(row=0, column=1, sticky="we", padx=5)
        ttk.Button(frm, text="浏览...", command=self._browse).grid(row=0, column=2)
        frm.columnconfigure(1, weight=1)

        tk.Label(frm, text="磁盘空间：需要约 25 MB", font=("Segoe UI", 9),
                 bg="#ffffff", fg="#666").grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 15))

        tk.Checkbutton(frm, text="在桌面创建快捷方式", variable=self._desktop_sc,
                       bg="#ffffff", font=("Segoe UI", 10)).grid(row=2, column=0, columnspan=3, sticky="w", pady=3)
        tk.Checkbutton(frm, text="在开始菜单创建快捷方式", variable=self._startmenu_sc,
                       bg="#ffffff", font=("Segoe UI", 10)).grid(row=3, column=0, columnspan=3, sticky="w", pady=3)

    def _browse(self) -> None:
        d = filedialog.askdirectory(initialdir=self._install_dir.get(),
                                     title="选择安装目录")
        if d:
            self._install_dir.set(d)

    def _page_progress(self) -> None:
        self.header.config(text="正在安装...")
        frm = tk.Frame(self.body, bg="#ffffff")
        frm.pack(fill="both", expand=True, padx=25, pady=25)

        self.progress = ttk.Progressbar(frm, length=480, mode="determinate", maximum=100)
        self.progress.pack(pady=(10, 15))

        self.status_label = tk.Label(frm, text="准备中...", font=("Segoe UI", 10),
                                      bg="#ffffff", fg="#333")
        self.status_label.pack(pady=5)

        self.detail_label = tk.Label(frm, text="", font=("Segoe UI", 9),
                                      bg="#ffffff", fg="#888")
        self.detail_label.pack(pady=5)

        threading.Thread(target=self._do_install, daemon=True).start()

    def _do_install(self) -> None:
        try:
            install_dir = Path(self._install_dir.get())
            res_dir = _resource_dir()
            source_exe = res_dir / "ClaraRecorder.exe"

            if not source_exe.exists():
                # 开发模式 fallback：从 dist 取
                source_exe = Path(__file__).resolve().parent / "dist" / "ClaraRecorder.exe"

            if not source_exe.exists():
                self.root.after(0, lambda: messagebox.showerror("错误",
                    f"找不到程序文件 ClaraRecorder.exe\n路径: {source_exe}"))
                self.root.after(0, lambda: self._show_page(0))
                return

            # 创建目录
            self._set_status("创建安装目录...", str(install_dir), 5)
            install_dir.mkdir(parents=True, exist_ok=True)

            # 拷 EXE
            dest_exe = install_dir / "ClaraRecorder.exe"
            self._set_status("复制程序文件...", f"ClaraRecorder.exe ({source_exe.stat().st_size // 1024} KB)", 30)
            shutil.copy2(source_exe, dest_exe)

            # 创建资产目录（如果资源里有）
            assets_src = res_dir / "assets" / "background"
            if assets_src.exists():
                assets_dest = install_dir / "assets" / "background"
                assets_dest.mkdir(parents=True, exist_ok=True)
                for f in assets_src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, assets_dest / f.name)
                self._set_status("复制资源文件...", "background.jpg", 55)

            # 创建快捷方式
            if self._desktop_sc.get():
                self._set_status("创建桌面快捷方式...", "", 70)
                desktop = _get_desktop_dir()
                _create_shortcut_simple(dest_exe, desktop / "ClaraRecorder.lnk")

            if self._startmenu_sc.get():
                self._set_status("创建开始菜单快捷方式...", "", 85)
                sm_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                sm_dir.mkdir(parents=True, exist_ok=True)
                _create_shortcut_simple(dest_exe, sm_dir / "ClaraRecorder.lnk")

            self._set_status("安装完成！", f"已安装到 {install_dir}", 100)
            self.root.after(500, lambda: self._show_page(3))

        except PermissionError:
            target = str(self._install_dir.get())
            self.root.after(0, lambda: messagebox.showerror(
                "安装失败：没有写入权限",
                f"无法写入目录：\n{target}\n\n"
                "Program Files 属于系统受保护目录，需要管理员权限。\n\n"
                "解决办法（任选其一）：\n"
                "1. 关闭本窗口，右键 ClaraSetup.exe → 以管理员身份运行\n"
                "2. 在第 2 步换一个普通目录，例如 D:\\ClaraRecorder"))
            self.root.after(0, lambda: self._show_page(0))
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("安装失败", str(exc)))
            self.root.after(0, lambda: self._show_page(0))

    def _set_status(self, text: str, detail: str, pct: int) -> None:
        def _upd() -> None:
            self.status_label.config(text=text)
            self.detail_label.config(text=detail)
            self.progress["value"] = pct
            self.root.update_idletasks()
        self.root.after(0, _upd)

    def _page_finish(self) -> None:
        self.header.config(text="安装完成")
        frm = tk.Frame(self.body, bg="#ffffff")
        frm.pack(fill="both", expand=True, padx=25, pady=25)

        tk.Label(frm, text="✓", font=("Segoe UI", 32),
                 bg="#ffffff", fg="#28a745").pack(pady=(10, 5))
        tk.Label(frm, text=f"{APP_TITLE} 已成功安装到你的计算机。",
                 font=("Segoe UI", 11), bg="#ffffff", fg="#333").pack(pady=5)

        tk.Button(frm, text="立即运行 ClaraRecorder", font=("Segoe UI", 10, "bold"),
                  bg="#6c5ce7", fg="white", relief="flat", padx=20, pady=8,
                  command=self._run_now).pack(pady=15)

    def _run_now(self) -> None:
        import subprocess
        exe = Path(self._install_dir.get()) / "ClaraRecorder.exe"
        if exe.exists():
            subprocess.Popen([str(exe)])
        self.root.destroy()

    def _next(self) -> None:
        if self._page == 1:
            # 验证安装目录
            d = Path(self._install_dir.get())
            if d.exists() and not os.access(str(d), os.W_OK):
                messagebox.showerror("错误", "该目录没有写入权限，请选择其他位置。")
                return
        self._show_page(self._page + 1)

    def _prev(self) -> None:
        if self._page > 0:
            self._show_page(self._page - 1)

    def _cancel(self) -> None:
        if messagebox.askyesno("确认退出", "确定要取消安装吗？"):
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    InstallerApp().run()
