"""程序装配与入口：把钩子、录制、回放、配置、界面组装在一起。"""

from __future__ import annotations

import datetime as _dt
import queue
import sys
from pathlib import Path
from typing import Any

from . import storage, winapi
from .config import Config
from .gui import ACTION_LABELS, MainWindow
from .hooks import InputHook
from .hotkeys import HotkeyManager, format_combo, is_modifier, normalize_vk, parse
from .player import Player
from .recorder import Recorder

VK_ESCAPE = 0x1B


class Controller:
    """业务控制器：连接界面与底层录制/回放引擎。"""

    def __init__(self) -> None:
        self.config = Config()
        self.recorder = Recorder()
        self.player = Player()
        self.hotkeys = HotkeyManager()
        self.ui_queue: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self.is_admin = winapi.is_admin()

        self._capture: str | None = None
        self._capture_codes: list[int] = []

        self._load_hotkeys_from_config()

        self.hook = InputHook(self._on_mouse, self._on_key, self._on_hook_error)
        self.hook.start()

    # ------------------------------------------------------------ 配置
    def _load_hotkeys_from_config(self) -> None:
        for name in ACTION_LABELS:
            combo = self.config.get(name, "")
            try:
                self.hotkeys.set_codes(name, parse(str(combo)))
            except (ValueError, TypeError):
                # 配置中的快捷键非法时，退回该动作的默认值
                from .config import DEFAULTS

                self.hotkeys.set_codes(name, parse(DEFAULTS[name]))

    def reset_hotkeys(self) -> None:
        from .config import DEFAULTS

        for name in ACTION_LABELS:
            self.hotkeys.set_codes(name, parse(DEFAULTS[name]))
            self.config.set(name, DEFAULTS[name])
        self.config.save()

    # ------------------------------------------------------------ 钩子回调（在钩子线程执行）
    def _on_mouse(self, kind: str, data: dict[str, Any]) -> None:
        self.recorder.add_mouse(kind, data)

    def _on_key(self, kind: str, data: dict[str, Any]) -> None:
        vk = int(data["vk"])
        action = str(data["action"])

        # ---- 快捷键捕获模式：只用于识别组合键，不录制、不触发动作
        if self._capture is not None:
            self._handle_capture(vk, action)
            return

        # ---- 触发全局快捷键
        for name in self.hotkeys.on_key(vk, action):
            self.ui_queue.put(("action", name))

        # ---- 正常录制（双时钟：tick 抗回调延迟，perf 提供亚毫秒细分）
        self.recorder.add_key(
            vk,
            int(data["scan"]),
            action,
            bool(data["extended"]),
            tick=data.get("tick"),
            perf=data.get("perf"),
        )

    def _handle_capture(self, vk: int, action: str) -> None:
        code = normalize_vk(vk)
        if action == "down":
            if code not in self._capture_codes:
                self._capture_codes.append(code)
            self.hotkeys._pressed.add(code)
            return

        self.hotkeys._pressed.discard(code)
        if self.hotkeys._pressed or not self._capture_codes:
            return

        codes = self._capture_codes
        target = self._capture
        self._capture = None
        self._capture_codes = []

        # Esc 单独按下 → 取消捕获
        if codes == [VK_ESCAPE]:
            self.ui_queue.put(("capture_cancelled",))
            return

        # 主键（非修饰键）放到最后，其余修饰键保持顺序
        mods = [c for c in codes if is_modifier(c)]
        mains = [c for c in codes if not is_modifier(c)]
        ordered = mods + mains
        if not mains:
            self.ui_queue.put(("capture_cancelled",))
            return

        combo = format_combo(ordered)
        self.hotkeys.set_codes(target, ordered)
        self.config.set(target, combo)
        self.ui_queue.put(("captured", target, combo))

    def _on_hook_error(self, message: str) -> None:
        self.ui_queue.put(("hook_error", message))

    # ------------------------------------------------------------ 快捷键捕获控制
    def begin_capture(self, name: str) -> None:
        self._capture = name
        self._capture_codes = []
        self.hotkeys._pressed.clear()

    def cancel_capture(self) -> None:
        self._capture = None
        self._capture_codes = []
        self.hotkeys._pressed.clear()

    # ------------------------------------------------------------ 动作
    def dispatch(self, name: str) -> None:
        if name == "hotkey_start_record":
            self.start_recording()
        elif name == "hotkey_stop_record":
            self.stop_recording()
        elif name == "hotkey_start_play":
            self.start_playback()
        elif name == "hotkey_stop_play":
            self.stop_playback()

    def start_recording(self) -> None:
        if self.player.playing or self.recorder.recording:
            return
        self.recorder.start()

    def stop_recording(self) -> None:
        if self.recorder.recording:
            self.recorder.stop()

    def start_playback(self) -> None:
        if self.recorder.recording or self.player.playing:
            return
        events = self.recorder.events_copy()
        if not events:
            return
        self.player.start(
            events,
            self.config.repeat_count,
            self.config.interval_seconds,
            speed=self.config.speed,
            on_pass_finished=lambda i, n: self.ui_queue.put(("pass", i, n)),
            on_finished=lambda aborted: self.ui_queue.put(("play_finished", aborted)),
        )

    def stop_playback(self) -> None:
        self.player.stop()

    # ------------------------------------------------------------ 存储
    def save_recording(self, name: str) -> Path:
        path = storage.save_recording(self.recorder.events_copy(), name)
        self.config.set("last_recording", str(path))
        self.config.save()
        return path

    def load_recording(self, path: Path | str) -> dict[str, Any]:
        events, meta = storage.load_recording(path)
        self.recorder.set_events(events)
        self.config.set("last_recording", str(path))
        self.config.save()
        return meta

    def default_recording_name(self) -> str:
        return _dt.datetime.now().strftime("录制_%Y%m%d_%H%M%S")

    def recordings_dir(self) -> Path:
        return storage.RECORDINGS_DIR

    # ------------------------------------------------------------ 环境信息
    def environment_info(self, lang: str = "zh") -> str:
        width, height = winapi.get_primary_size()
        refresh = winapi.get_refresh_rate()
        dpi = winapi.get_dpi()
        monitors = winapi.get_monitor_count()
        if lang == "en":
            return (
                f"Screen {width}×{height}  ·  {refresh}Hz  ·  "
                f"DPI {dpi}  ·  {monitors} monitor(s)"
            )
        return (
            f"屏幕 {width}×{height}  ·  刷新率 {refresh}Hz  ·  "
            f"DPI {dpi}  ·  {monitors} 个显示器"
        )

    # ------------------------------------------------------------ 生命周期
    def shutdown(self) -> None:
        self.player.stop()
        self.hook.stop()
        self.config.save()


def _show_error(exc: BaseException) -> None:
    """在无控制台（pythonw）场景下，用弹窗显示致命错误。"""
    import traceback

    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("鼠标键盘活动记录重复器 - 启动失败", detail)
        root.destroy()
    except Exception:
        print(detail, file=sys.stderr)


def _run_self_check() -> None:
    """环境自检模式：打印底层环境信息，便于排查。"""
    winapi.enable_dpi_awareness()
    width, height = winapi.get_primary_size()
    left, top, vw, vh = winapi.get_virtual_screen()
    print("=== 鼠标键盘活动记录重复器 · 环境自检 ===")
    print(f"Python 版本     : {sys.version.split()[0]}")
    print(f"管理员权限      : {'是' if winapi.is_admin() else '否'}")
    print(f"主屏分辨率      : {width} x {height}")
    print(f"虚拟桌面        : left={left}, top={top}, size={vw} x {vh}")
    print(f"刷新率 / DPI    : {winapi.get_refresh_rate()} Hz / {winapi.get_dpi()}")
    print(f"显示器数量      : {winapi.get_monitor_count()}")
    print(f"计时器精度提升  : {'成功' if winapi.begin_time_period(1) else '失败'}")
    winapi.end_time_period(1)
    print("自检完成 ✔")


def main() -> None:
    if "--check" in sys.argv:
        _run_self_check()
        return

    try:
        winapi.enable_dpi_awareness()

        # 请求完全管理员权限：非管理员时尝试以 runas 重新拉起自身
        # PyInstaller 打包后 workdir 不需要（EXE 自带完整运行环境）
        # 注意：PyInstaller --uac-admin manifest 会让 Windows 自动弹 UAC，
        # is_admin() 检查后若仍需提权才走到 relaunch_as_admin 分支
        if not winapi.is_admin() and winapi.relaunch_as_admin(
            None if getattr(sys, "frozen", False) else str(Path(__file__).resolve().parent.parent)
        ):
            return

        controller = Controller()
        window = MainWindow(controller)
        window.run()
    except Exception as exc:  # 顶层兜底，保证异常时有可见的错误提示
        _show_error(exc)


if __name__ == "__main__":
    main()
