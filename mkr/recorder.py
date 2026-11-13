"""录制引擎：以 Windows 事件时间戳为准记录输入事件。

事件以紧凑的字典形式保存在内存中，字段含义如下::

    {"t": <相对录制起点的纳秒数>, "k": "move",  "x": .., "y": ..}
    {"t": .., "k": "btn", "b": "left|right|middle|x1|x2", "a": "down|up", "x": .., "y": ..}
    {"t": .., "k": "whl", "d": <滚轮增量>, "h": <是否横向>, "x": .., "y": ..}
    {"t": .., "k": "key", "vk": .., "sc": .., "a": "down|up", "ext": <是否扩展键>}

计时策略（精度关键，双时钟融合）：
* tick：Windows 在事件进入系统时打的毫秒时间戳（钩子结构体 time 字段），
  绝对时刻准确、不受钩子回调延迟影响，但粒度 1ms。
* perf：钩子回调入口取的微秒时间戳，分辨率高但含回调分发延迟。
* 融合规则：与上一事件 tick 差 >= 1ms → 用 tick 锚定（消灭回调大延迟）；
  tick 相同（1ms 内的快速连按）→ 用 perf 差细分（微秒级分辨率）。
  这样录制的时间轴既有抗抖动的绝对锚点，又有亚毫秒精度。
* 录制期间 timeBeginPeriod(1) 把 tick 粒度从 ~15.6ms 提到 ~1ms。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from . import winapi


def _empty_stats() -> dict[str, int]:
    return {
        "move": 0,
        "left": 0,
        "right": 0,
        "middle": 0,
        "xbutton": 0,
        "wheel": 0,
        "key": 0,
    }


class Recorder:
    """线程安全的输入录制器。钩子线程写入，界面线程读取。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._stats = _empty_stats()
        self._recording = False
        self._timer_boost = False
        # 双时钟融合状态：上一事件的 (输出时刻, tick, perf)
        self._prev_out_t = 0
        self._prev_tick = 0
        self._prev_perf = 0
        self.duration_ns = 0

    # ---------------------------------------------------------------- 状态
    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self._events)

    def snapshot(self) -> dict[str, Any]:
        """返回统计数据快照，供界面刷新显示。"""
        with self._lock:
            counts = dict(self._stats)
            n = len(self._events)
            duration = self._events[-1]["t"] if self._events else 0
        return {"counts": counts, "count": n, "duration_ns": duration}

    # ---------------------------------------------------------------- 控制
    def start(self) -> None:
        with self._lock:
            self._events = []
            self._stats = _empty_stats()
            # 提升 tick 粒度到 ~1ms（默认 15.6ms 会把快速连按量化成一团）
            self._timer_boost = winapi.begin_time_period(1)
            # 虚拟起点：输出时刻 0 对应 (tick0, perf0)
            self._prev_out_t = 0
            self._prev_tick = winapi.get_tick_count()
            self._prev_perf = time.perf_counter_ns()
            self._recording = True
            self.duration_ns = 0

    def stop(self) -> list[dict[str, Any]]:
        with self._lock:
            self._recording = False
            if self._timer_boost:
                winapi.end_time_period(1)
                self._timer_boost = False
            self.duration_ns = self._events[-1]["t"] if self._events else 0
            return list(self._events)

    def _now_ns(self, tick: int | None, perf: int | None) -> int:
        """双时钟融合：tick 锚定绝对时刻，perf 提供亚毫秒细分。

        * tick 差 >= 1ms：t = prev_t + tick差。回调延迟再大也不影响。
        * tick 相同：t = prev_t + perf差（微秒级）。同 tick 事件即 1ms 内
          的快速连按，用 perf 分辨先后与间隔。
        * perf 缺失或 tick 出现回绕式跳变时退回可用时钟；输出保证严格递增。
        """
        prev_t = self._prev_out_t
        if tick is not None:
            delta_ms = (tick - self._prev_tick) & 0xFFFFFFFF
            if 0 < delta_ms < 0x8000_0000:
                t = prev_t + delta_ms * 1_000_000
                self._prev_out_t = t
                self._prev_tick = tick
                self._prev_perf = perf if perf is not None else self._prev_perf
                return t
        t = prev_t + max(1, perf - self._prev_perf) if perf is not None else prev_t + 1
        self._prev_out_t = t
        if tick is not None:
            self._prev_tick = tick
        if perf is not None:
            self._prev_perf = perf
        return t

    def clear(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._events = []
            self._stats = _empty_stats()
            self.duration_ns = 0

    def events_copy(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def set_events(self, events: list[dict[str, Any]]) -> None:
        """载入已有录制（用于读取文件后直接回放）。"""
        with self._lock:
            if self._recording:
                return
            self._events = list(events)
            self.duration_ns = self._events[-1]["t"] if self._events else 0
            stats = _empty_stats()
            for ev in self._events:
                kind = ev.get("k")
                if kind == "move":
                    stats["move"] += 1
                elif kind == "btn":
                    if ev.get("a") == "down":
                        b = ev.get("b")
                        if b in ("left", "right", "middle"):
                            stats[b] += 1
                        else:
                            stats["xbutton"] += 1
                elif kind == "whl":
                    stats["wheel"] += 1
                elif kind == "key":
                    stats["key"] += 1
            self._stats = stats

    # ---------------------------------------------------------------- 写入
    def add_mouse(self, kind: str, data: dict[str, Any]) -> None:
        with self._lock:
            if not self._recording:
                return
            t = self._now_ns(data.get("tick"), data.get("perf"))
            if kind == "move":
                self._events.append({"t": t, "k": "move", "x": data["x"], "y": data["y"]})
                self._stats["move"] += 1
            elif kind == "button":
                button = data["button"]
                action = data["action"]
                self._events.append(
                    {
                        "t": t,
                        "k": "btn",
                        "b": button,
                        "a": action,
                        "x": data.get("x", 0),
                        "y": data.get("y", 0),
                    }
                )
                if action == "down":
                    if button in ("left", "right", "middle"):
                        self._stats[button] += 1
                    else:
                        self._stats["xbutton"] += 1
            elif kind == "wheel":
                self._events.append(
                    {
                        "t": t,
                        "k": "whl",
                        "d": data["delta"],
                        "h": bool(data["horizontal"]),
                        "x": data.get("x", 0),
                        "y": data.get("y", 0),
                    }
                )
                self._stats["wheel"] += 1

    def add_key(
        self,
        vk: int,
        scan: int,
        action: str,
        extended: bool,
        tick: int | None = None,
        perf: int | None = None,
    ) -> None:
        with self._lock:
            if not self._recording:
                return
            t = self._now_ns(tick, perf)
            self._events.append(
                {"t": t, "k": "key", "vk": vk, "sc": scan, "a": action, "ext": bool(extended)}
            )
            self._stats["key"] += 1
