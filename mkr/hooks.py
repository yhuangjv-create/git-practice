"""全局低级输入钩子（WH_MOUSE_LL / WH_KEYBOARD_LL）线程。

钩子必须安装在拥有消息循环的线程中，因此本模块在独立线程里安装钩子并运行
``GetMessage`` 循环。回调中已完成事件解析，并**自动过滤注入事件**（避免回放时
自身触发自身）。
"""

from __future__ import annotations

import ctypes
import threading
import time
from collections.abc import Callable
from typing import Any

from . import winapi
from .winapi import (
    HC_ACTION,
    HOOKPROC,
    KBDLLHOOKSTRUCT,
    LLKHF_EXTENDED,
    LLKHF_INJECTED,
    LLMHF_INJECTED,
    MSG,
    MSLLHOOKSTRUCT,
    WH_KEYBOARD_LL,
    WH_MOUSE_LL,
    WM_KEYDOWN,
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_MBUTTONDOWN,
    WM_MBUTTONUP,
    WM_MOUSEHWHEEL,
    WM_MOUSEMOVE,
    WM_MOUSEWHEEL,
    WM_QUIT,
    WM_RBUTTONDOWN,
    WM_RBUTTONUP,
    WM_SYSKEYDOWN,
    WM_XBUTTONDOWN,
    WM_XBUTTONUP,
    XBUTTON1,
)

MouseCallback = Callable[[str, dict[str, Any]], None]
KeyCallback = Callable[[str, dict[str, Any]], None]


def _signed_hiword(value: int) -> int:
    """取 DWORD 的高 16 位并解释为有符号整数（用于滚轮增量）。"""
    hi = (value >> 16) & 0xFFFF
    return hi - 0x10000 if hi & 0x8000 else hi


class InputHook:
    """全局鼠标/键盘钩子。"""

    def __init__(
        self,
        on_mouse: MouseCallback | None = None,
        on_key: KeyCallback | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._on_mouse = on_mouse or (lambda kind, data: None)
        self._on_key = on_key or (lambda kind, data: None)
        self._on_error = on_error or (lambda msg: None)

        self._thread: threading.Thread | None = None
        self._mouse_hook = None
        self._key_hook = None
        self._mouse_proc = None
        self._key_proc = None
        self._thread_id = 0
        self._running = False
        self._ready = threading.Event()

    # ---------------------------------------------------------------- 生命周期
    def start(self, timeout: float = 3.0) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="InputHook", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return bool(self._mouse_hook or self._key_hook)

    def stop(self, timeout: float = 3.0) -> None:
        if not self._running:
            return
        self._running = False
        if self._thread_id:
            winapi.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout)

    # ---------------------------------------------------------------- 内部实现
    def _run(self) -> None:
        # 钩子线程提权：减少消息泵分发延迟，让 perf 回调时刻更接近真实按键时刻
        winapi.set_thread_priority(winapi.THREAD_PRIORITY_HIGHEST)
        self._thread_id = int(winapi.kernel32.GetCurrentThreadId())
        # 保持回调引用，防止被垃圾回收导致崩溃
        self._mouse_proc = HOOKPROC(self._mouse_callback)
        self._key_proc = HOOKPROC(self._key_callback)

        self._mouse_hook = winapi.user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._mouse_proc, None, 0
        )
        self._key_hook = winapi.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._key_proc, None, 0
        )

        if not self._mouse_hook or not self._key_hook:
            self._on_error(
                f"安装全局输入钩子失败 (mouse={bool(self._mouse_hook)}, "
                f"key={bool(self._key_hook)}, err={ctypes.get_last_error()})"
            )

        self._ready.set()

        msg = MSG()
        while self._running:
            ret = winapi.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            winapi.user32.TranslateMessage(ctypes.byref(msg))
            winapi.user32.DispatchMessageW(ctypes.byref(msg))

        if self._mouse_hook:
            winapi.user32.UnhookWindowsHookEx(self._mouse_hook)
            self._mouse_hook = None
        if self._key_hook:
            winapi.user32.UnhookWindowsHookEx(self._key_hook)
            self._key_hook = None

    def _mouse_callback(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            try:
                message = int(w_param)
                data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if not (int(data.flags) & LLMHF_INJECTED):
                    self._dispatch_mouse(message, data)
            except Exception:
                pass
        return winapi.user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _key_callback(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            try:
                # 回调入口立刻取微秒时间戳——越早取，越接近真实按键时刻
                perf_ns = time.perf_counter_ns()
                message = int(w_param)
                data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not (int(data.flags) & LLKHF_INJECTED):
                    action = "down" if message in (WM_KEYDOWN, WM_SYSKEYDOWN) else "up"
                    self._on_key(
                        "key",
                        {
                            "vk": int(data.vkCode),
                            "scan": int(data.scanCode),
                            "action": action,
                            "extended": bool(int(data.flags) & LLKHF_EXTENDED),
                            # 双时间戳：tick（Windows 侧毫秒，抗回调大延迟）
                            # + perf（回调时刻微秒，提供亚毫秒分辨率）
                            "tick": int(data.time),
                            "perf": perf_ns,
                        },
                    )
            except Exception:
                pass
        return winapi.user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _dispatch_mouse(self, message: int, data) -> None:
        x = int(data.pt.x)
        y = int(data.pt.y)
        perf_ns = time.perf_counter_ns()
        tick = int(data.time)  # 同键盘：Windows 侧事件时间戳，消除回调延迟抖动

        kind: str | None = None
        payload: dict[str, Any] = {}

        if message == WM_MOUSEMOVE:
            kind, payload = "move", {"x": x, "y": y}
        elif message == WM_LBUTTONDOWN:
            kind, payload = "button", {"button": "left", "action": "down", "x": x, "y": y}
        elif message == WM_LBUTTONUP:
            kind, payload = "button", {"button": "left", "action": "up", "x": x, "y": y}
        elif message == WM_RBUTTONDOWN:
            kind, payload = "button", {"button": "right", "action": "down", "x": x, "y": y}
        elif message == WM_RBUTTONUP:
            kind, payload = "button", {"button": "right", "action": "up", "x": x, "y": y}
        elif message == WM_MBUTTONDOWN:
            kind, payload = "button", {"button": "middle", "action": "down", "x": x, "y": y}
        elif message == WM_MBUTTONUP:
            kind, payload = "button", {"button": "middle", "action": "up", "x": x, "y": y}
        elif message == WM_MOUSEWHEEL:
            kind, payload = "wheel", {
                "delta": _signed_hiword(int(data.mouseData)), "horizontal": False, "x": x, "y": y,
            }
        elif message == WM_MOUSEHWHEEL:
            kind, payload = "wheel", {
                "delta": _signed_hiword(int(data.mouseData)), "horizontal": True, "x": x, "y": y,
            }
        elif message in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            which = (int(data.mouseData) >> 16) & 0xFFFF
            button = "x1" if which == XBUTTON1 else "x2"
            action = "down" if message == WM_XBUTTONDOWN else "up"
            kind, payload = "button", {"button": button, "action": action, "x": x, "y": y}

        if kind is not None:
            payload["tick"] = tick
            payload["perf"] = perf_ns
            self._on_mouse(kind, payload)
