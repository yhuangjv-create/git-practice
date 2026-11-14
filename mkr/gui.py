"""tkinter 图形界面：Windows 软件级别的友好操作窗口（支持中/英切换）。"""

from __future__ import annotations

import queue
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

try:  # Pillow 为可选依赖，仅用于主界面封面图
    from PIL import Image, ImageTk

    _HAS_PIL = True
    try:
        _RESAMPLE = Image.Resampling.LANCZOS
    except AttributeError:  # Pillow < 9.1
        _RESAMPLE = Image.LANCZOS
except Exception:  # noqa: BLE001
    _HAS_PIL = False
    _RESAMPLE = None


def asset_dirs() -> list[Path]:
    """按优先级返回资源目录：打包目录 → 开发目录 → EXE 同级 assets。"""
    dirs: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs += [Path(meipass) / "assets", Path(meipass) / "background"]
    dirs.append(Path(__file__).resolve().parent.parent / "assets")
    dirs.append(Path(sys.executable).resolve().parent / "assets")
    return dirs

# ---------------------------------------------------------------- 配色
NAVY = "#0f2438"
PANEL = "#173350"
CARD = "#1d3e5c"
FG = "#eaf3fb"
MUTED = "#a6bdd0"
ACCENT = "#ffb703"
GREEN_H = "#2ecc71"
PURPLE = "#7d3c98"
PURPLE_H = "#a569bd"
RED = "#c0392b"
RED_H = "#e74c3c"
BLUE = "#2471a3"
BLUE_H = "#3498db"
ORANGE = "#e67e22"
ORANGE_H = "#f39c12"
GRAY = "#5d6d7e"

FONT = "Microsoft YaHei UI"
FONT_UI = (FONT, 10)
FONT_TITLE = (FONT, 19, "bold")
FONT_SUB = (FONT, 9)
FONT_BIG = (FONT, 14, "bold")
FONT_BIG_SYM = ("Segoe UI Symbol", 15, "bold")
FONT_STAT = (FONT, 10)
FONT_STAT_NUM = (FONT, 13, "bold")

# ---------------------------------------------------------------- 国际化
I18N: dict[str, dict[str, str]] = {
    "zh": {
        "window_title": "鼠标键盘活动记录重复器 V1.6.2  ·  Clara",
        "title_main": "鼠标键盘活动记录重复器 V1.6.2",
        "title_sub": "记录鼠标轨迹 / 按键 / 滚轮 / 键盘，并按次数与间隔完整重复   ·   Clara 出品",
        "admin_ok": "✔ 管理员模式",
        "admin_no": "⚠ 普通权限（建议以管理员运行）",
        "controls": "操作控制",
        "start_rec": "开始录制",
        "stop_rec": "结束录制",
        "start_play": "开始重复播放",
        "stop_play": "停止播放",
        "save": "保存录制",
        "load": "载入录制",
        "clear": "清空",
        "settings": "回放设置",
        "repeat": "重复次数",
        "interval": "重复间隔 (秒)",
        "speed": "回放速度 (倍)",
        "apply": "✔  应用并保存设置",
        "sys_btn": "⚙  系统设置（快捷键 / 精度）",
        "stats": "本段录制统计",
        "st_move": "鼠标移动",
        "st_left": "左键点击",
        "st_right": "右键点击",
        "st_middle": "中键点击",
        "st_wheel": "滚轮滚动",
        "st_key": "键盘输入",
        "total": "事件总数：{n}    时长：{d}",
        "fmt_dur_m": "{m} 分 {s:.3f} 秒",
        "fmt_dur_s": "{s:.3f} 秒",
        "ready": "● 就绪",
        "hint_start": "点击「开始录制」或按 {k} 开始",
        "recording": "● 录制中…  已记录 {n} 个事件",
        "playing": "↻ 回放中…  第 {i} / {t} 次",
        "passing": "回放进行中：已完成第 {i} / {n} 次",
        "play_stopped": "回放已停止",
        "play_done": "回放完成 ✔",
        "saved": "设置已保存 ✔",
        "captured": "已将「{a}」快捷键设为 {k}",
        "default_hotkeys": "已恢复默认快捷键",
        "no_hotkey": "未设置",
        # messagebox
        "err_hook_title": "钩子安装失败",
        "warn_input_title": "输入有误",
        "warn_input_msg": "重复次数 / 间隔 / 速度 必须是数字。",
        "info_empty_title": "无内容",
        "info_empty_msg": "当前没有可保存的录制内容，请先录制一段操作。",
        "dlg_save_title": "保存录制",
        "dlg_save_prompt": "请输入录制名称：",
        "err_save_title": "保存失败",
        "info_save_title": "保存成功",
        "info_save_msg": "已保存到：\n{p}",
        "dlg_load_title": "选择录制文件",
        "dlg_load_filter1": "录制文件",
        "dlg_load_filter2": "所有文件",
        "err_load_title": "载入失败",
        "loaded": "已载入录制：{n}（{c} 个事件）",
        "dlg_clear_title": "确认清空",
        "dlg_clear_msg": "确定要清空当前录制内容吗？",
        "cleared": "已清空当前录制内容",
        # 系统设置窗口
        "sys_title": "系统设置  ⚙",
        "hotkey_title": "⚙  快捷键设置",
        "hotkey_hint": "点击右侧按钮后，按下想要的组合键即可完成设置（Esc 取消）。",
        "precision_title": "⚙  录制与回放精度",
        "precision_info": (
            "• 录制时间戳精度：微秒级（perf_counter_ns，纳秒计数）\n"
            "• 回放定时精度：约 0.3 毫秒（自旋等待 + 系统计时器 1ms）\n"
            "• 当前屏幕：{e}\n"
            "• 鼠标轨迹按物理像素记录，回放适配虚拟桌面绝对坐标\n"
            "• 键盘优先使用扫描码注入，兼容性更好\n"
            "• 回放产生的注入事件会被自动过滤，避免自我触发"
        ),
        "reset_hotkeys": "恢复默认快捷键",
        "close": "关闭",
        "capture_prompt": "请按下按键…（Esc 取消）",
    },
    "en": {
        "window_title": "Mouse & Keyboard Recorder V1.6.2  ·  Clara",
        "title_main": "Mouse & Keyboard Recorder V1.6.2",
        "title_sub": "Record mouse trajectories / keys / wheels / keyboards, replay by count & interval   ·   Clara",
        "admin_ok": "✔ Admin Mode",
        "admin_no": "⚠ Normal Mode (Run as admin recommended)",
        "controls": "Controls",
        "start_rec": "Start Recording",
        "stop_rec": "Stop Recording",
        "start_play": "Start Playback",
        "stop_play": "Stop Playback",
        "save": "Save",
        "load": "Load",
        "clear": "Clear",
        "settings": "Playback Settings",
        "repeat": "Repeat Count",
        "interval": "Interval (sec)",
        "speed": "Speed (x)",
        "apply": "✔  Apply & Save",
        "sys_btn": "⚙  System Settings (Hotkeys / Precision)",
        "stats": "Recording Stats",
        "st_move": "Mouse Moves",
        "st_left": "Left Clicks",
        "st_right": "Right Clicks",
        "st_middle": "Middle Clicks",
        "st_wheel": "Scrolls",
        "st_key": "Key Presses",
        "total": "Total Events: {n}    Duration: {d}",
        "fmt_dur_m": "{m}m {s:.3f}s",
        "fmt_dur_s": "{s:.3f}s",
        "ready": "● Ready",
        "hint_start": "Click \"Start Recording\" or press {k} to begin",
        "recording": "● Recording…  {n} events captured",
        "playing": "↻ Playing…  Pass {i} / {t}",
        "passing": "Playback in progress: pass {i} / {n}",
        "play_stopped": "Playback stopped",
        "play_done": "Playback complete ✔",
        "saved": "Settings saved ✔",
        "captured": "Hotkey for \"{a}\" set to {k}",
        "default_hotkeys": "Default hotkeys restored",
        "no_hotkey": "Not set",
        "err_hook_title": "Hook Installation Failed",
        "warn_input_title": "Invalid Input",
        "warn_input_msg": "Repeat count / interval / speed must be numbers.",
        "info_empty_title": "Nothing to Save",
        "info_empty_msg": "No recording to save. Please record something first.",
        "dlg_save_title": "Save Recording",
        "dlg_save_prompt": "Enter recording name:",
        "err_save_title": "Save Failed",
        "info_save_title": "Saved",
        "info_save_msg": "Saved to:\n{p}",
        "dlg_load_title": "Select Recording File",
        "dlg_load_filter1": "Recordings",
        "dlg_load_filter2": "All Files",
        "err_load_title": "Load Failed",
        "loaded": "Loaded: {n} ({c} events)",
        "dlg_clear_title": "Confirm Clear",
        "dlg_clear_msg": "Clear the current recording?",
        "cleared": "Recording cleared",
        "sys_title": "System Settings  ⚙",
        "hotkey_title": "⚙  Hotkeys",
        "hotkey_hint": "Click a button, then press the desired key combination (Esc to cancel).",
        "precision_title": "⚙  Recording & Playback Precision",
        "precision_info": (
            "• Recording timestamp: microsecond-level (perf_counter_ns)\n"
            "• Playback timing: ~0.3 ms (spin-wait + 1 ms system timer)\n"
            "• Screen: {e}\n"
            "• Mouse trajectory recorded in physical pixels, replayed to virtual-desktop absolute coords\n"
            "• Keys use scan code injection for best compatibility\n"
            "• Injected events are auto-filtered to avoid self-triggering"
        ),
        "reset_hotkeys": "Restore Default Hotkeys",
        "close": "Close",
        "capture_prompt": "Press the keys… (Esc to cancel)",
    },
}

ACTION_LABELS = {
    "hotkey_start_record": ("start_rec", "开始录制", "Start Recording"),
    "hotkey_stop_record": ("stop_rec", "结束录制", "Stop Recording"),
    "hotkey_start_play": ("start_play", "开始重复播放", "Start Playback"),
    "hotkey_stop_play": ("stop_play", "停止播放", "Stop Playback"),
}


def _fmt_duration(ns: int, lang: str = "zh") -> str:
    seconds = ns / 1_000_000_000
    t = I18N[lang]
    if seconds >= 60:
        return t["fmt_dur_m"].format(m=int(seconds // 60), s=seconds % 60)
    return t["fmt_dur_s"].format(s=seconds)


class MainWindow:
    """主窗口。"""

    def __init__(self, controller: Any) -> None:
        self.c = controller
        self.lang: str = "zh"

        self.root = tk.Tk()
        self.root.title(self._t("window_title"))
        self.root.configure(bg=NAVY)
        self.root.minsize(900, 620)
        self._apply_tk_scaling()

        self._settings_window: tk.Toplevel | None = None
        self._settings_buttons: dict[str, tk.Button] = {}
        self._action_buttons: dict[str, tk.Button] = {}
        self._action_meta: dict[str, tuple[str, str]] = {}
        self._spinboxes: dict[str, tk.Spinbox] = {}

        # 可控件引用（用于切换语言时刷新）
        self._ref_title_main: tk.Label | None = None
        self._ref_title_sub: tk.Label | None = None
        self._ref_lang_btn: tk.Button | None = None
        self._ref_controls_label: tk.Label | None = None
        self._ref_save_btn: tk.Button | None = None
        self._ref_load_btn: tk.Button | None = None
        self._ref_clear_btn: tk.Button | None = None
        self._ref_settings_label: tk.Label | None = None
        self._ref_repeat_label: tk.Label | None = None
        self._ref_interval_label: tk.Label | None = None
        self._ref_speed_label: tk.Label | None = None
        self._ref_apply_btn: tk.Button | None = None
        self._ref_sys_btn: tk.Button | None = None
        self._ref_stats_label: tk.Label | None = None
        self._ref_stat_labels: dict[str, tk.Label] = {}

        self._build_header()
        self._build_body()
        self._build_statusbar()
        self._auto_size_window(self.root, (900, 620))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(120, self._poll)

    # ------------------------------------------------------------ i18n
    def _t(self, key: str) -> str:
        return I18N[self.lang].get(key, key)

    def _at(self, key: str) -> str:
        """返回当前语言下 ACTION_LABELS 的中文/英文。"""
        entry = ACTION_LABELS.get(key)
        if entry is None:
            return key
        return entry[1] if self.lang == "zh" else entry[2]

    def _switch_lang(self) -> None:
        self.lang = "en" if self.lang == "zh" else "zh"
        self.root.title(self._t("window_title"))
        self._render_lang_button()
        self._refresh_texts()
        if self._settings_window and self._settings_window.winfo_exists():
            self._rebuild_settings_window()

    def _render_lang_button(self) -> None:
        """重绘语言按钮颜色（当前语言白字，另一语言灰字）。"""
        if self._ref_lang_btn is None:
            return
        kids = self._ref_lang_btn.winfo_children()
        if len(kids) < 2:
            return
        zh_fg = "#ffffff" if self.lang == "zh" else "#2b1810"
        en_fg = "#ffffff" if self.lang == "en" else "#2b1810"
        kids[0].configure(fg=zh_fg)
        kids[1].configure(fg=en_fg)

    def _refresh_texts(self) -> None:
        """切换语言后刷新所有已创建控件文本。"""
        # header（Canvas 横幅上的文字项）
        if self._ref_title_main:
            self._banner.itemconfig(self._ref_title_main, text=self._t("title_main"))
        if self._ref_title_sub:
            self._banner.itemconfig(self._ref_title_sub, text=self._t("title_sub"))
        # 大按钮
        self._refresh_action_buttons()
        # 保存/载入/清空
        if self._ref_save_btn:
            self._ref_save_btn.configure(text=self._t("save"))
        if self._ref_load_btn:
            self._ref_load_btn.configure(text=self._t("load"))
        if self._ref_clear_btn:
            self._ref_clear_btn.configure(text=self._t("clear"))
        # 设置面板
        if self._ref_controls_label:
            self._ref_controls_label.configure(text=self._t("controls"))
        if self._ref_settings_label:
            self._ref_settings_label.configure(text=self._t("settings"))
        if self._ref_repeat_label:
            self._ref_repeat_label.configure(text=self._t("repeat"))
        if self._ref_interval_label:
            self._ref_interval_label.configure(text=self._t("interval"))
        if self._ref_speed_label:
            self._ref_speed_label.configure(text=self._t("speed"))
        if self._ref_apply_btn:
            self._ref_apply_btn.configure(text=self._t("apply"))
        if self._ref_sys_btn:
            self._ref_sys_btn.configure(text=self._t("sys_btn"))
        # 统计
        if self._ref_stats_label:
            self._ref_stats_label.configure(text=self._t("stats"))
        for key, lbl in self._ref_stat_labels.items():
            lbl.configure(text=self._t(f"st_{key}"))
        # 环境信息（右下角 + 系统设置窗口内）
        self._set_var(self.var_env, self.c.environment_info(self.lang))
        # hint 重置为默认文案
        self._set_var(
            self.var_hint,
            self._t("hint_start").format(
                k=self.c.hotkeys.get_combo("hotkey_start_record") or self._t("no_hotkey")
            ),
        )
        # 状态
        self._refresh()

    # ------------------------------------------------------------ 初始化
    def _apply_tk_scaling(self) -> None:
        try:
            dpi = self.root.winfo_fpixels("1i")
            if dpi > 0:
                self.root.tk.call("tk", "scaling", dpi / 72.0)
        except tk.TclError:
            pass

    def _auto_size_window(self, win: tk.Tk | tk.Toplevel, min_size: tuple[int, int]) -> None:
        """窗口自适应：取内容自然大小，clamp 到屏幕 85%，居中显示。

        只在构建完控件后调用一次，之后用户手动拉伸不受影响。
        """
        win.update_idletasks()
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        # 保证不小于 minsize
        w = max(w, min_size[0])
        h = max(h, min_size[1])
        # clamp 到屏幕 85%，避免内容特别多时窗口超出屏幕
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        max_w = int(sw * 0.85)
        max_h = int(sh * 0.85)
        w = min(w, max_w)
        h = min(h, max_h)
        # 居中
        x = (sw - w) // 2
        y = (sh - h) // 3  # 偏上一点更符合视觉习惯
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _build_header(self) -> None:
        """顶部封面横幅：背景图 cover 裁剪 + 标题叠加。"""
        self._banner = tk.Canvas(self.root, height=168, bg=NAVY, highlightthickness=0, bd=0)
        self._banner.pack(fill="x", padx=16, pady=(14, 6))
        self._banner_photo = None
        self._banner_job = None
        self._banner_src = self._load_banner_source()

        # 图片 → 压暗遮罩 → 文字，按此顺序创建，后者覆盖前者
        self._banner_img_id = self._banner.create_image(0, 0, anchor="nw")
        self._banner_shade_id = self._banner.create_rectangle(
            0, 0, 0, 0, fill="#000000", stipple="gray25", outline=""
        )
        self._banner_title_id = self._banner.create_text(
            24, 68, anchor="w", text=self._t("title_main"), font=FONT_TITLE, fill=FG
        )
        self._banner_sub_id = self._banner.create_text(
            24, 96, anchor="w", text=self._t("title_sub"), font=FONT_SUB, fill=MUTED
        )
        # 复用旧刷新入口：这两个变量现在是 Canvas item id
        self._ref_title_main = self._banner_title_id
        self._ref_title_sub = self._banner_sub_id

        # 语言切换按钮（浮在横幅中部右侧）
        lang_frame = tk.Frame(self._banner, bg=ORANGE, bd=0, highlightthickness=0, cursor="hand2")
        lang_frame.place(relx=1.0, rely=0.5, anchor="e", x=-16)
        zh_fg = "#ffffff" if self.lang == "zh" else "#2b1810"
        en_fg = "#ffffff" if self.lang == "en" else "#2b1810"
        tk.Label(
            lang_frame, text="\u4e2d\u6587", font=(FONT, 10, "bold"), fg=zh_fg, bg=ORANGE, padx=8, pady=4, cursor="hand2"
        ).pack(side="left")
        tk.Label(
            lang_frame, text="English", font=(FONT, 10, "bold"), fg=en_fg, bg=ORANGE, padx=8, pady=4, cursor="hand2"
        ).pack(side="left")
        for w in (lang_frame, lang_frame.winfo_children()[0], lang_frame.winfo_children()[1]):
            w.bind("<Button-1>", lambda _e: self._switch_lang())
        self._ref_lang_btn = lang_frame  # 复用为切换时重绘的锚点

        self._banner.bind("<Configure>", self._on_banner_configure)
        self._redraw_banner()

    def _load_banner_source(self):
        """读取封面图；Pillow 缺失或文件不存在时返回 None（横幅退回纯色）。"""
        if not _HAS_PIL:
            return None
        for base in asset_dirs():
            for name in ("background.jpg", "background.png"):
                p = base / name
                if p.is_file():
                    try:
                        return Image.open(p).convert("RGB")
                    except Exception:  # noqa: BLE001
                        return None
        return None

    def _on_banner_configure(self, _event=None) -> None:
        if self._banner_job:
            self._banner.after_cancel(self._banner_job)
        self._banner_job = self._banner.after(80, self._redraw_banner)

    def _redraw_banner(self) -> None:
        self._banner_job = None
        w = self._banner.winfo_width()
        h = self._banner.winfo_height()
        if w <= 1 or h <= 1:
            return
        self._banner.coords(self._banner_shade_id, 0, 0, w, h)
        self._banner.coords(self._banner_title_id, 24, h // 2 - 14)
        self._banner.coords(self._banner_sub_id, 24, h // 2 + 16)
        if self._banner_src is None:
            return
        src = self._banner_src
        sw, sh = src.size
        scale = max(w / sw, h / sh)
        nw, nh = max(1, int(sw * scale + 0.5)), max(1, int(sh * scale + 0.5))
        resized = src.resize((nw, nh), _RESAMPLE)
        left = (nw - w) // 2
        top = (nh - h) // 2
        cropped = resized.crop((left, top, left + w, top + h))
        self._banner_photo = ImageTk.PhotoImage(cropped)
        self._banner.itemconfig(self._banner_img_id, image=self._banner_photo)
        self._banner.coords(self._banner_img_id, 0, 0)

    def _render_lang_button(self) -> None:
        """重绘语言按钮颜色。"""
        if self._ref_lang_btn is None:
            return
        kids = self._ref_lang_btn.winfo_children()
        if len(kids) < 2:
            return
        zh_fg = "#ffffff" if self.lang == "zh" else "#2b1810"
        en_fg = "#ffffff" if self.lang == "en" else "#2b1810"
        kids[0].configure(fg=zh_fg)
        kids[1].configure(fg=en_fg)

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=NAVY)
        body.pack(fill="both", expand=True, padx=16, pady=6)
        body.columnconfigure(0, weight=3, uniform="col")
        body.columnconfigure(1, weight=2, uniform="col")
        body.rowconfigure(0, weight=1)

        self._build_controls(body)
        self._build_settings(body)

    def _build_controls(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=PANEL, bd=0, highlightthickness=1, highlightbackground=CARD)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self._ref_controls_label = tk.Label(
            panel, text=self._t("controls"), font=(FONT, 12, "bold"), fg=ACCENT, bg=PANEL
        )
        self._ref_controls_label.pack(anchor="w", padx=16, pady=(14, 8))

        self.btn_start_rec = self._big_button(
            panel, "▶", "start_rec", "hotkey_start_record", PURPLE, PURPLE_H,
            lambda: self.c.start_recording(),
        )
        self.btn_stop_rec = self._big_button(
            panel, "■", "stop_rec", "hotkey_stop_record", RED, RED_H,
            lambda: self.c.stop_recording(),
        )
        self.btn_start_play = self._big_button(
            panel, "↻", "start_play", "hotkey_start_play", BLUE, BLUE_H,
            lambda: self.c.start_playback(),
        )
        self.btn_stop_play = self._big_button(
            panel, "■", "stop_play", "hotkey_stop_play", ORANGE, ORANGE_H,
            lambda: self.c.stop_playback(),
        )

        sep = tk.Frame(panel, bg=CARD, height=1)
        sep.pack(fill="x", padx=16, pady=12)

        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x", padx=16, pady=(0, 14))
        self._ref_save_btn = self._make_small_btn(row, "save", self._save_recording)
        self._ref_save_btn.pack(side="left", expand=True, fill="x", padx=4)
        self._ref_load_btn = self._make_small_btn(row, "load", self._load_recording)
        self._ref_load_btn.pack(side="left", expand=True, fill="x", padx=4)
        self._ref_clear_btn = self._make_small_btn(row, "clear", self._clear_recording)
        self._ref_clear_btn.pack(side="left", expand=True, fill="x", padx=4)

    def _make_small_btn(self, parent: tk.Widget, key: str, cmd: Any) -> tk.Button:
        return tk.Button(
            parent,
            text=self._t(key),
            font=FONT_UI,
            bg=CARD,
            fg=FG,
            activebackground=GRAY,
            activeforeground=FG,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=8,
            command=cmd,
        )

    def _big_button(
        self,
        parent: tk.Widget,
        symbol: str,
        i18n_key: str,
        hotkey_name: str,
        bg: str,
        active_bg: str,
        command: Any,
    ) -> tk.Button:
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(fill="x", padx=16, pady=5)

        btn = tk.Button(
            frame,
            text=self._action_text(symbol, i18n_key, hotkey_name),
            font=FONT_BIG,
            bg=bg,
            fg="#ffffff",
            activebackground=active_bg,
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            anchor="w",
            padx=16,
            pady=12,
            command=command,
        )
        btn.pack(fill="x")
        self._action_buttons[hotkey_name] = btn
        self._action_meta[hotkey_name] = (symbol, i18n_key)
        return btn

    def _action_text(self, symbol: str, i18n_key: str, hotkey_name: str) -> str:
        combo = self.c.hotkeys.get_combo(hotkey_name) or self._t("no_hotkey")
        return f"  {symbol}    {self._t(i18n_key)}        ({combo})"

    def _refresh_action_buttons(self) -> None:
        for name, btn in self._action_buttons.items():
            symbol, i18n_key = self._action_meta[name]
            btn.configure(text=self._action_text(symbol, i18n_key, name))

    def _build_settings(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=PANEL, bd=0, highlightthickness=1, highlightbackground=CARD)
        panel.grid(row=0, column=1, sticky="nsew")

        self._ref_settings_label = tk.Label(
            panel, text=self._t("settings"), font=(FONT, 12, "bold"), fg=ACCENT, bg=PANEL
        )
        self._ref_settings_label.pack(anchor="w", padx=16, pady=(14, 8))

        form = tk.Frame(panel, bg=PANEL)
        form.pack(fill="x", padx=16)

        self.var_repeat = tk.StringVar(value=str(self.c.config.repeat_count))
        self.var_interval = tk.StringVar(value=f"{self.c.config.interval_seconds:g}")
        self.var_speed = tk.StringVar(value=f"{self.c.config.speed:g}")

        self._ref_repeat_label = self._spin_row(form, "repeat", self.var_repeat, 1, 99999, 1)
        self._ref_interval_label = self._spin_row(form, "interval", self.var_interval, 0, 9999, 0.5)
        self._ref_speed_label = self._spin_row(form, "speed", self.var_speed, 0.1, 20, 0.1)

        for var, key, lo, hi, cast in (
            (self.var_repeat, "repeat_count", 1, 99999, int),
            (self.var_interval, "interval_seconds", 0.0, 9999.0, float),
            (self.var_speed, "speed", 0.1, 20.0, float),
        ):
            def _make_tracer(v=var, k=key, lo_=lo, hi_=hi, c=cast):
                def _trace(*_args: object) -> None:
                    try:
                        val = c(float(v.get()))
                    except ValueError:
                        return
                    val = max(lo_, min(hi_, val))
                    self.c.config.set(k, val)
                    self.c.config.save()
                return _trace
            var.trace_add("write", _make_tracer())

        self._ref_apply_btn = tk.Button(
            panel,
            text=self._t("apply"),
            font=FONT_UI,
            bg=CARD,
            fg=FG,
            activebackground=GRAY,
            activeforeground=FG,
            relief="flat",
            cursor="hand2",
            pady=8,
            command=self._apply_settings,
        )
        self._ref_apply_btn.pack(fill="x", padx=16, pady=(12, 6))

        self._ref_sys_btn = tk.Button(
            panel,
            text=self._t("sys_btn"),
            font=FONT_UI,
            bg=ACCENT,
            fg="#20140a",
            activebackground="#ffc94d",
            activeforeground="#20140a",
            relief="flat",
            cursor="hand2",
            pady=9,
            command=self._open_settings,
        )
        self._ref_sys_btn.pack(fill="x", padx=16, pady=(0, 12))

        tk.Frame(panel, bg=CARD, height=1).pack(fill="x", padx=16, pady=(0, 10))

        self._ref_stats_label = tk.Label(
            panel, text=self._t("stats"), font=(FONT, 11, "bold"), fg=ACCENT, bg=PANEL
        )
        self._ref_stats_label.pack(anchor="w", padx=16)

        stats = tk.Frame(panel, bg=PANEL)
        stats.pack(fill="x", padx=16, pady=(6, 6))
        stats.columnconfigure(0, weight=1)
        stats.columnconfigure(1, weight=1)

        self.stat_vars: dict[str, tk.StringVar] = {}
        items = [
            ("move", 0, 0),
            ("left", 0, 1),
            ("right", 1, 0),
            ("middle", 1, 1),
            ("wheel", 2, 0),
            ("key", 2, 1),
        ]
        for key, r, col in items:
            cell = tk.Frame(stats, bg=CARD)
            cell.grid(row=r, column=col, sticky="nsew", padx=3, pady=3)
            lbl = tk.Label(cell, text=self._t(f"st_{key}"), font=FONT_SUB, fg=MUTED, bg=CARD)
            lbl.pack(anchor="w", padx=10, pady=(6, 0))
            self._ref_stat_labels[key] = lbl
            var = tk.StringVar(value="0")
            tk.Label(cell, textvariable=var, font=FONT_STAT_NUM, fg=FG, bg=CARD).pack(
                anchor="w", padx=10, pady=(0, 6)
            )
            self.stat_vars[key] = var

        self.var_total = tk.StringVar(value=self._t("total").format(n=0, d=_fmt_duration(0, self.lang)))
        tk.Label(
            panel, textvariable=self.var_total, font=FONT_SUB, fg=MUTED, bg=PANEL, justify="left"
        ).pack(anchor="w", padx=16, pady=(6, 2))

        self.var_env = tk.StringVar(value=self.c.environment_info(self.lang))
        tk.Label(
            panel, textvariable=self.var_env, font=FONT_SUB, fg=MUTED, bg=PANEL, justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 14))

    def _spin_row(
        self,
        parent: tk.Frame,
        key: str,
        var: tk.StringVar,
        lo: float,
        hi: float,
        step: float,
    ) -> tk.Label:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=4)
        lbl = tk.Label(row, text=self._t(key), font=FONT_UI, fg=FG, bg=PANEL, width=16, anchor="w")
        lbl.pack(side="left")
        spin = tk.Spinbox(
            row,
            from_=lo,
            to=hi,
            increment=step,
            textvariable=var,
            font=FONT_UI,
            width=10,
            justify="center",
            bg="#ffffff",
            fg="#102030",
            relief="flat",
            validate="none",
        )
        spin.pack(side="right")
        self._spinboxes[key] = spin
        return lbl

    def _build_statusbar(self) -> None:
        bar = tk.Frame(self.root, bg="#0b1b2b")
        bar.pack(fill="x", side="bottom")

        inner = tk.Frame(bar, bg="#0b1b2b")
        inner.pack(fill="x", padx=16, pady=8)

        self.var_status = tk.StringVar(value=self._t("ready"))
        tk.Label(inner, textvariable=self.var_status, font=(FONT, 11, "bold"), fg=GREEN_H, bg="#0b1b2b").pack(
            side="left"
        )

        self.var_hint = tk.StringVar(
            value=self._t("hint_start").format(
                k=self.c.hotkeys.get_combo("hotkey_start_record") or self._t("no_hotkey")
            )
        )
        tk.Label(inner, textvariable=self.var_hint, font=FONT_SUB, fg=MUTED, bg="#0b1b2b").pack(
            side="left", padx=16
        )

        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", side="bottom", padx=16, pady=(0, 6))

    # ------------------------------------------------------------ 事件轮询
    def _poll(self) -> None:
        try:
            while True:
                msg = self.c.ui_queue.get_nowait()
                self._handle_message(msg)
        except queue.Empty:
            pass
        self._refresh()
        self.root.after(120, self._poll)

    def _handle_message(self, msg: tuple[Any, ...]) -> None:
        tag = msg[0]
        if tag == "action":
            self.c.dispatch(msg[1])
        elif tag == "captured":
            _, name, combo = msg
            if self._settings_window and self._settings_window.winfo_exists():
                self._settings_buttons[name].configure(text=combo, fg=GREEN_H)
            self._refresh_action_buttons()
            self.c.config.save()
            self.var_hint.set(self._t("captured").format(a=self._at(name), k=combo))
        elif tag == "capture_cancelled":
            self._refresh_settings_buttons()
        elif tag == "hook_error":
            messagebox.showerror(self._t("err_hook_title"), str(msg[1]))
        elif tag == "pass":
            _, i, n = msg
            self.var_hint.set(self._t("passing").format(i=i, n=n))
        elif tag == "play_finished":
            aborted = bool(msg[1])
            self.var_hint.set(self._t("play_stopped") if aborted else self._t("play_done"))

    def _refresh(self) -> None:
        rec = self.c.recorder.recording
        play = self.c.player.playing
        snap = self.c.recorder.snapshot()

        self._set_state(self.btn_start_rec, not rec and not play)
        self._set_state(self.btn_stop_rec, rec)
        self._set_state(self.btn_start_play, not rec and not play and snap["count"] > 0)
        self._set_state(self.btn_stop_play, play)

        counts = snap["counts"]
        for key in self.stat_vars:
            self._set_var(self.stat_vars[key], str(counts.get(key, 0)))
        self._set_var(
            self.var_total,
            self._t("total").format(n=snap["count"], d=_fmt_duration(snap["duration_ns"], self.lang)),
        )

        if rec:
            self._set_var(self.var_status, self._t("recording").format(n=snap["count"]))
            self._set_progress(0)
        elif play:
            pct = max(0.0, min(1.0, self.c.player.progress)) * 100
            self._set_var(
                self.var_status,
                self._t("playing").format(i=self.c.player.current_pass, t=self.c.player.total_passes),
            )
            self._set_progress(pct)
        else:
            self._set_var(self.var_status, self._t("ready"))
            self._set_progress(0)

    def _set_progress(self, value: float) -> None:
        if float(self.progress["value"]) != value:
            self.progress["value"] = value

    @staticmethod
    def _set_var(var: tk.StringVar, value: str) -> None:
        if var.get() != value:
            var.set(value)

    @staticmethod
    def _set_state(button: tk.Button, enabled: bool) -> None:
        desired = "normal" if enabled else "disabled"
        if str(button["state"]) != desired:
            button.configure(state=desired)

    # ------------------------------------------------------------ 用户动作
    def _apply_settings(self) -> None:
        try:
            repeat = int(float(self.var_repeat.get()))
            interval = float(self.var_interval.get())
            speed = float(self.var_speed.get())
        except ValueError:
            messagebox.showwarning(self._t("warn_input_title"), self._t("warn_input_msg"))
            return

        repeat = max(1, min(99999, repeat))
        interval = round(max(0.0, min(9999.0, interval)), 3)
        speed = round(max(0.1, min(20.0, speed)), 2)

        self.c.config.set("repeat_count", repeat)
        self.c.config.set("interval_seconds", interval)
        self.c.config.set("speed", speed)
        self.c.config.save()

        self._set_var(self.var_repeat, str(repeat))
        self._set_var(self.var_interval, f"{interval:g}")
        self._set_var(self.var_speed, f"{speed:g}")

        for spin in self._spinboxes.values():
            spin.selection_clear()
        self.root.focus_set()

        self.var_hint.set(self._t("saved"))

    def _save_recording(self) -> None:
        events = self.c.recorder.events_copy()
        if not events:
            messagebox.showinfo(self._t("info_empty_title"), self._t("info_empty_msg"))
            return
        default = self.c.default_recording_name()
        name = simpledialog.askstring(
            self._t("dlg_save_title"), self._t("dlg_save_prompt"),
            initialvalue=default, parent=self.root,
        )
        if not name:
            return
        try:
            path = self.c.save_recording(name)
        except OSError as exc:
            messagebox.showerror(self._t("err_save_title"), str(exc))
            return
        messagebox.showinfo(self._t("info_save_title"), self._t("info_save_msg").format(p=path))

    def _load_recording(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("dlg_load_title"),
            initialdir=str(self.c.recordings_dir()),
            filetypes=[(self._t("dlg_load_filter1"), "*.json"), (self._t("dlg_load_filter2"), "*.*")],
        )
        if not path:
            return
        try:
            meta = self.c.load_recording(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror(self._t("err_load_title"), str(exc))
            return
        name = meta.get("name") or self._t("no_hotkey")
        self.var_hint.set(self._t("loaded").format(n=name, c=self.c.recorder.event_count))

    def _clear_recording(self) -> None:
        if self.c.recorder.recording or self.c.player.playing:
            return
        if messagebox.askyesno(self._t("dlg_clear_title"), self._t("dlg_clear_msg")):
            self.c.recorder.clear()
            self.var_hint.set(self._t("cleared"))

    # ------------------------------------------------------------ 系统设置
    def _open_settings(self) -> None:
        if self._settings_window and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_force()
            return
        self._build_settings_window()

    def _rebuild_settings_window(self) -> None:
        self._close_settings()
        self._build_settings_window()

    def _build_settings_window(self) -> None:
        win = tk.Toplevel(self.root)
        win.title(self._t("sys_title"))
        win.configure(bg=NAVY)
        win.minsize(560, 580)
        win.transient(self.root)
        win.resizable(True, True)
        self._settings_window = win

        tk.Label(win, text=self._t("hotkey_title"), font=(FONT, 13, "bold"), fg=ACCENT, bg=NAVY).pack(
            anchor="w", padx=20, pady=(16, 2)
        )
        tk.Label(
            win,
            text=self._t("hotkey_hint"),
            font=FONT_SUB,
            fg=MUTED,
            bg=NAVY,
        ).pack(anchor="w", padx=20, pady=(0, 10))

        self._settings_buttons = {}
        for name in ACTION_LABELS:
            row = tk.Frame(win, bg=PANEL)
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=self._at(name), font=FONT_UI, fg=FG, bg=PANEL, width=18, anchor="w").pack(
                side="left"
            )
            btn = tk.Button(
                row,
                text=self.c.hotkeys.get_combo(name) or self._t("no_hotkey"),
                font=(FONT, 10, "bold"),
                bg=CARD,
                fg=ACCENT,
                activebackground=GRAY,
                activeforeground=FG,
                relief="flat",
                cursor="hand2",
                width=18,
                pady=7,
            )
            btn.configure(command=lambda n=name, b=btn: self._start_capture(n, b))
            btn.pack(side="right")
            self._settings_buttons[name] = btn

        tk.Frame(win, bg=CARD, height=1).pack(fill="x", padx=20, pady=14)

        tk.Label(win, text=self._t("precision_title"), font=(FONT, 13, "bold"), fg=ACCENT, bg=NAVY).pack(
            anchor="w", padx=20
        )
        info = self._t("precision_info").format(e=self.c.environment_info(self.lang))
        tk.Label(win, text=info, font=FONT_SUB, fg=FG, bg=NAVY, justify="left").pack(
            anchor="w", padx=20, pady=(6, 0)
        )

        btns = tk.Frame(win, bg=NAVY)
        btns.pack(fill="x", padx=20, pady=18)
        tk.Button(
            btns,
            text=self._t("reset_hotkeys"),
            font=FONT_UI,
            bg=CARD,
            fg=FG,
            activebackground=GRAY,
            activeforeground=FG,
            relief="flat",
            cursor="hand2",
            pady=8,
            command=self._reset_hotkeys,
        ).pack(side="left")
        tk.Button(
            btns,
            text=self._t("close"),
            font=FONT_UI,
            bg=ACCENT,
            fg="#20140a",
            activebackground="#ffc94d",
            relief="flat",
            cursor="hand2",
            pady=8,
            padx=24,
            command=self._close_settings,
        ).pack(side="right")

        win.protocol("WM_DELETE_WINDOW", self._close_settings)
        self._auto_size_window(win, (560, 580))

    def _start_capture(self, name: str, button: tk.Button) -> None:
        button.configure(text=self._t("capture_prompt"), fg=ACCENT)
        self.c.begin_capture(name)

    def _reset_hotkeys(self) -> None:
        self.c.reset_hotkeys()
        self._refresh_settings_buttons()
        self._refresh_action_buttons()
        self.var_hint.set(self._t("default_hotkeys"))

    def _refresh_settings_buttons(self) -> None:
        for name, btn in self._settings_buttons.items():
            btn.configure(text=self.c.hotkeys.get_combo(name) or self._t("no_hotkey"), fg=ACCENT)

    def _close_settings(self) -> None:
        self.c.cancel_capture()
        if self._settings_window and self._settings_window.winfo_exists():
            self._settings_window.destroy()
        self._settings_window = None
        self._settings_buttons = {}

    # ------------------------------------------------------------ 关闭
    def _on_close(self) -> None:
        try:
            self.c.shutdown()
        finally:
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
