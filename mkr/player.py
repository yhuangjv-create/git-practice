"""回放引擎：按录制的时间轴，以高精度定时注入输入事件。

关键点：
* 使用 ``perf_counter_ns`` 单调时钟 + "安全 sleep + 自旋" 的两阶段等待，
  达到 sub-100µs 级唤醒精度（Windows 原生 time.sleep 在 0.3~2ms 区间有
  500µs 量级的调度抖动，不能直接用）
* 回放前调用 ``timeBeginPeriod(1)`` 提升系统计时器分辨率
* 鼠标移动使用"绝对坐标 + 虚拟桌面"方式，适配多显示器与不同分辨率
* 键盘优先使用扫描码注入，兼容性更好
* 密切间隔（< 1ms）的事件会被"成批"发送——Windows scheduler 本身无法
  分辨 1ms 以内的顺序，一次 SendInput 批量注入反而更稳定原子
"""

from __future__ import annotations

import gc
import threading
import time
from collections.abc import Callable
from typing import Any

from . import winapi

# ---------------------------------------------------------------------- 等待精度

# 我们永远只 sleep 到 "deadline - SAFE_MARGIN"，然后自旋。
# SAFE_MARGIN 必须大于 time.sleep 的最坏抖动（实测 Windows 约 300-700µs），
# 留足余量：先 sleep 1.5ms，再自旋。对长间隔来说省 CPU，对短间隔直接自旋。
_SAFE_SLEEP_MARGIN_NS = 1_500_000  # 1.5ms
_SPIN_ONLY_NS = 1_000_000          # < 1ms 直接自旋，放弃 sleep

# 成批窗口：连续事件相对间隔 < 此值时合并到一次 SendInput。
# 这正好覆盖 "Ctrl down → Shift down → A down" 这种用户组合键的真实间隔。
_BATCH_WINDOW_NS = 1_000_000  # 1ms


def precise_sleep_until(deadline_ns: int) -> None:
    """等待直到 perf_counter_ns() 到达 deadline_ns，sub-100µs 级精度。

    策略：
    1. 如果剩余 < 1ms：直接自旋（time.sleep(0) 偶尔 yield 一下）
    2. 否则：先 time.sleep 到 deadline - 1.5ms，再自旋 1.5ms
    3. 永远不在 deadline 之前结束 sleep——而是 sleep 到安全余量，
       让自旋来做最后的精确定时。这样 Windows scheduler 的抖动
       只会让我们自旋更久，而不会让我们"太晚"。
    """
    while True:
        remaining = deadline_ns - time.perf_counter_ns()
        if remaining <= 0:
            return
        if remaining > _SAFE_SLEEP_MARGIN_NS:
            # 长间隔：sleep 到安全余量，剩下的自旋
            time.sleep((remaining - _SAFE_SLEEP_MARGIN_NS) / 1_000_000_000)
        elif remaining > _SPIN_ONLY_NS:
            # 中等间隔：sleep 到 deadline - 200µs，最后自旋
            time.sleep((remaining - 200_000) / 1_000_000_000)
        # 否则：剩余 < 1ms，纯自旋


# ---------------------------------------------------------------------- 事件 → INPUT 转换

def build_inputs(event: dict[str, Any]) -> list[winapi.INPUT]:
    """把一条录制事件转换成 SendInput 需要的 INPUT 数组。

    这是纯数据转换，不做任何系统调用——回放前预构建好，消除注入时的 ctypes 开销。
    """
    kind = event.get("k")
    inputs: list[winapi.INPUT] = []

    if kind == "move":
        dx, dy = winapi.to_absolute(int(event["x"]), int(event["y"]))
        inputs.append(
            winapi.mouse_input(
                winapi.MOUSEEVENTF_MOVE
                | winapi.MOUSEEVENTF_ABSOLUTE
                | winapi.MOUSEEVENTF_VIRTUALDESK,
                dx,
                dy,
            )
        )

    elif kind == "btn":
        if "x" in event and "y" in event:
            dx, dy = winapi.to_absolute(int(event["x"]), int(event["y"]))
            inputs.append(
                winapi.mouse_input(
                    winapi.MOUSEEVENTF_MOVE
                    | winapi.MOUSEEVENTF_ABSOLUTE
                    | winapi.MOUSEEVENTF_VIRTUALDESK,
                    dx,
                    dy,
                )
            )
        flags, data = _button_flags(str(event.get("b", "")), str(event.get("a", "down")))
        if flags:
            inputs.append(winapi.mouse_input(flags, data=int(data)))

    elif kind == "whl":
        if "x" in event and "y" in event:
            dx, dy = winapi.to_absolute(int(event["x"]), int(event["y"]))
            inputs.append(
                winapi.mouse_input(
                    winapi.MOUSEEVENTF_MOVE
                    | winapi.MOUSEEVENTF_ABSOLUTE
                    | winapi.MOUSEEVENTF_VIRTUALDESK,
                    dx,
                    dy,
                )
            )
        flags = winapi.MOUSEEVENTF_HWHEEL if event.get("h") else winapi.MOUSEEVENTF_WHEEL
        inputs.append(winapi.mouse_input(flags, data=int(event.get("d", 0))))

    elif kind == "key":
        up = str(event.get("a", "down")) == "up"
        vk = int(event.get("vk", 0))
        scan = int(event.get("sc", 0))
        extended = bool(event.get("ext", False))
        inputs.append(winapi.key_input(vk, scan, extended, up=up))

    return inputs


def _button_flags(button: str, action: str) -> tuple[int, int]:
    """返回 (dwFlags, mouseData) 。"""
    down = action == "down"
    if button == "left":
        return (winapi.MOUSEEVENTF_LEFTDOWN if down else winapi.MOUSEEVENTF_LEFTUP), 0
    if button == "right":
        return (winapi.MOUSEEVENTF_RIGHTDOWN if down else winapi.MOUSEEVENTF_RIGHTUP), 0
    if button == "middle":
        return (winapi.MOUSEEVENTF_MIDDLEDOWN if down else winapi.MOUSEEVENTF_MIDDLEUP), 0
    if button == "x1":
        return (winapi.MOUSEEVENTF_XDOWN if down else winapi.MOUSEEVENTF_XUP), winapi.XBUTTON1
    if button == "x2":
        return (winapi.MOUSEEVENTF_XDOWN if down else winapi.MOUSEEVENTF_XUP), winapi.XBUTTON2
    return 0, 0


def inject(event: dict[str, Any], state: InjectedState | None = None) -> None:
    """兼容旧接口：单事件注入。内部委托给 build_inputs + send_inputs + state 更新。"""
    winapi.send_inputs(build_inputs(event))
    if state is not None:
        _update_state(state, event)


def _update_state(state: InjectedState, event: dict[str, Any]) -> None:
    kind = event.get("k")
    if kind == "key":
        up = str(event.get("a", "down")) == "up"
        state.key_event(
            int(event.get("vk", 0)),
            int(event.get("sc", 0)),
            bool(event.get("ext", False)),
            up=up,
        )
    elif kind == "btn":
        state.mouse_event(str(event.get("b", "")), str(event.get("a", "down")))


# ---------------------------------------------------------------------- 已注入状态

class InjectedState:
    """记录本回放实例通过 SendInput 已注入的、尚未释放的按键与鼠标按键。

    释放策略（来自实战经验）：
    * 仅在"本实例注入过 down 事件"的键上发送 up，绝不 blanket 释放——
      避免误伤用户正在物理按下的按键，也避免影响界面上的其它全局快捷键；
    * 记录使用 (scan, vk, extended) 三元组，因为 Windows 对同一个物理键
      在不同布局下 scan/vk 互有关联，三者结合能稳定定位；
    * 用集合 + 计数器处理录制中可能出现的"同键多次按下未抬"的堆叠情况。
    """

    def __init__(self) -> None:
        self._keys: dict[tuple[int, int, bool], int] = {}  # (scan, vk, ext) -> down 次数
        self._mouse: dict[str, int] = {}  # button_name -> down 次数

    # ---------------------------------------------------------------- 记录
    def key_event(self, vk: int, scan: int, extended: bool, up: bool) -> None:
        # 没有 vk 也没有 scan 时跳过，避免记录到无效条目
        if not vk and not scan:
            return
        key = (scan, vk, extended)
        if up:
            self._keys[key] = max(0, self._keys.get(key, 1) - 1)
            if self._keys[key] == 0:
                self._keys.pop(key, None)
        else:
            self._keys[key] = self._keys.get(key, 0) + 1

    def mouse_event(self, button: str, action: str) -> None:
        if button not in ("left", "right", "middle", "x1", "x2"):
            return
        if action == "down":
            self._mouse[button] = self._mouse.get(button, 0) + 1
        else:
            self._mouse[button] = max(0, self._mouse.get(button, 1) - 1)
            if self._mouse[button] == 0:
                self._mouse.pop(button, None)

    # ---------------------------------------------------------------- 释放
    def release_all(self) -> int:
        """对本实例已按下但未抬起的所有键发送释放事件，返回释放数量。

        按"先鼠标后键盘、最后修饰键"的顺序释放，尽量保持视觉上自然。
        """
        count = self._release_mouse()
        count += self._release_keys()
        return count

    def _release_mouse(self) -> int:
        buttons = list(self._mouse.items())  # [(name, count), ...]
        if not buttons:
            return 0
        released = 0
        for button, count in buttons:
            flags, data = _button_flags(button, "up")
            if flags:
                for _ in range(count):
                    winapi.send_inputs([winapi.mouse_input(flags, data=int(data))])
                    released += 1
        self._mouse.clear()
        return released

    def _release_keys(self) -> int:
        keys = list(self._keys.items())  # [(key_tuple, count), ...]
        if not keys:
            return 0

        def _is_modifier(vk: int) -> bool:
            return vk in (0x11, 0x10, 0x12, 0x5B) or 0xA0 <= vk <= 0xA5 or vk in (0x5C,)

        keys.sort(key=lambda item: (0 if _is_modifier(item[0][1]) else 1, item[0]))

        released = 0
        for (scan, vk, ext), count in keys:
            for _ in range(count):
                winapi.send_inputs([winapi.key_input(vk, scan, ext, up=True)])
                released += 1
                time.sleep(0.015)
        self._keys.clear()
        return released


# ---------------------------------------------------------------------- 回放器

class Player:
    """线程安全的回放器，支持重复次数与重复间隔。"""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._playing = False
        self.current_pass = 0
        self.total_passes = 0
        self.progress = 0.0

    @property
    def playing(self) -> bool:
        return self._playing

    def start(
        self,
        events: list[dict[str, Any]],
        repeat: int,
        interval_seconds: float,
        speed: float = 1.0,
        on_pass_finished: Callable[[int, int], None] | None = None,
        on_finished: Callable[[bool], None] | None = None,
    ) -> bool:
        if self._playing or not events:
            return False
        self._stop.clear()
        self._playing = True
        self.total_passes = max(1, int(repeat))
        self.current_pass = 0
        self.progress = 0.0
        # 预构建所有事件的 INPUT 数组，消除回放循环中的 ctypes 开销
        prebuilt = [(e, build_inputs(e)) for e in events]
        self._thread = threading.Thread(
            target=self._run,
            args=(
                prebuilt,
                self.total_passes,
                max(0.0, float(interval_seconds)),
                max(0.01, float(speed)),
                on_pass_finished,
                on_finished,
            ),
            name="Player",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _run(
        self,
        prebuilt: list[tuple[dict[str, Any], list[winapi.INPUT]]],
        repeat: int,
        interval: float,
        speed: float,
        on_pass_finished: Callable[[int, int], None] | None,
        on_finished: Callable[[bool], None] | None,
    ) -> None:
        winapi.begin_time_period(1)
        # 确定性保障：同一录制重复回放，每次的时间轴必须完全一致。
        # 两大随机停顿源：
        # 1) Python GC 停顿可达数毫秒且回合随机 → 回放期间禁用；
        # 2) 线程调度抢占 → 回放线程提升到 TIME_CRITICAL。
        # 事件时间轴只用绝对 deadline（不自增累积），抖动不会跨事件传播。
        gc_was_enabled = gc.isenabled()
        gc.disable()
        aborted = False
        state = InjectedState()
        try:
            winapi.set_thread_priority(winapi.THREAD_PRIORITY_TIME_CRITICAL)
            t0 = prebuilt[0][0]["t"]
            total = len(prebuilt)
            for i in range(repeat):
                if self._stop.is_set():
                    aborted = True
                    break
                self.current_pass = i + 1
                base = time.perf_counter_ns()
                idx = 0
                while idx < total:
                    if self._stop.is_set():
                        aborted = True
                        break
                    event, inputs = prebuilt[idx]
                    deadline = base + int((event["t"] - t0) / speed)
                    precise_sleep_until(deadline)
                    if self._stop.is_set():
                        aborted = True
                        break

                    # ---- 成批窗口：连续事件相对间隔 < 此值时合并到一次 SendInput。
                    #      关键：窗口必须跟随 speed 缩放。speed 越大，回放时间轴上
                    #      所有事件间隔都被同比例压缩，窗口也必须同比例缩小，
                    #      否则高倍速下本应分开的事件（如 Ctrl→Shift 间隔 4ms
                    #      在 5x 下变为 0.8ms）会被错误合并成"同时按下"，
                    #      破坏录制时的按键顺序与时长语义。
                    #      缩放后窗口在"录制时间轴"上恒为 1ms，语义各倍速一致。
                    batch_window_ns = max(100_000, int(_BATCH_WINDOW_NS / speed))

                    batch_inputs: list[winapi.INPUT] = list(inputs)
                    batch_events = [event]
                    j = idx + 1
                    while j < total:
                        next_event, next_inputs = prebuilt[j]
                        next_deadline = base + int((next_event["t"] - t0) / speed)
                        if next_deadline - deadline <= batch_window_ns:
                            batch_inputs.extend(next_inputs)
                            batch_events.append(next_event)
                            j += 1
                        else:
                            break

                    winapi.send_inputs(batch_inputs)
                    for ev in batch_events:
                        _update_state(state, ev)

                    idx = j
                    self.progress = idx / total
                if aborted:
                    break
                if on_pass_finished:
                    on_pass_finished(i + 1, repeat)
                if i < repeat - 1:
                    wait_end = time.perf_counter_ns() + int(interval * 1_000_000_000)
                    while not self._stop.is_set():
                        remaining = wait_end - time.perf_counter_ns()
                        if remaining <= 0:
                            break
                        time.sleep(min(0.05, remaining / 1_000_000_000))
                    if self._stop.is_set():
                        aborted = True
                        break
        finally:
            # 精准释放：仅释放本次回放已注入 down 但尚未 up 的键，
            # 避免用户再手动点一下 Ctrl/Alt/Shift 才能解除"一直按着"。
            state.release_all()
            if gc_was_enabled:
                gc.enable()
            if not aborted:
                self.progress = 1.0
            self._playing = False
            winapi.end_time_period(1)
            if on_finished:
                on_finished(aborted)
