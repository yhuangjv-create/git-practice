"""核心逻辑单元测试（不依赖图形界面与真实输入注入）。"""

from __future__ import annotations

import json
import time

import pytest

from mkr import hotkeys, player, storage, winapi
from mkr.config import DEFAULTS, Config
from mkr.recorder import Recorder


# ---------------------------------------------------------------- 快捷键
def test_parse_and_format_combo():
    codes = hotkeys.parse("ctrl+alt+r")
    assert codes == [0x11, 0x12, 0x52]
    assert hotkeys.format_combo(codes) == "ctrl+alt+r"


def test_parse_function_keys_and_letters():
    assert hotkeys.parse("f9") == [0x78]
    assert hotkeys.parse("F12") == [0x7B]
    assert hotkeys.parse("a") == [0x41]


def test_parse_invalid_key_raises():
    with pytest.raises(ValueError):
        hotkeys.parse("notakey")


def test_normalize_vk_maps_left_right_modifiers():
    assert hotkeys.normalize_vk(0xA2) == 0x11  # 左 Ctrl
    assert hotkeys.normalize_vk(0xA3) == 0x11  # 右 Ctrl
    assert hotkeys.normalize_vk(0xA0) == 0x10  # 左 Shift
    assert hotkeys.normalize_vk(0x41) == 0x41  # 普通键不受影响


def test_hotkey_manager_triggers_combination():
    manager = hotkeys.HotkeyManager()
    manager.set("start", "ctrl+alt+r")

    assert manager.on_key(0xA2, "down") == []  # 左 Ctrl（归一化后为 0x11）
    assert manager.on_key(0xA4, "down") == []  # 左 Alt
    assert manager.on_key(0x52, "down") == ["start"]
    # 按住不放产生的自动重复不应再次触发
    assert manager.on_key(0x52, "down") == []
    manager.on_key(0x52, "up")
    manager.on_key(0xA4, "up")
    manager.on_key(0xA2, "up")
    assert manager.on_key(0x52, "down") == []  # 缺少修饰键，不触发


def test_hotkey_manager_single_key():
    manager = hotkeys.HotkeyManager()
    manager.set("stop", "f10")
    assert manager.on_key(0x79, "down") == ["stop"]


# ---------------------------------------------------------------- 录制
def test_recorder_captures_and_counts():
    rec = Recorder()
    rec.start()
    assert rec.recording

    rec.add_mouse("move", {"x": 10, "y": 20})
    rec.add_mouse("button", {"button": "left", "action": "down", "x": 10, "y": 20})
    rec.add_mouse("button", {"button": "left", "action": "up", "x": 10, "y": 20})
    rec.add_mouse("button", {"button": "right", "action": "down", "x": 11, "y": 21})
    rec.add_mouse("wheel", {"delta": 120, "horizontal": False, "x": 10, "y": 20})
    rec.add_key(0x41, 0x1E, "down", False)

    events = rec.stop()
    assert len(events) == 6
    assert [ev["k"] for ev in events] == ["move", "btn", "btn", "btn", "whl", "key"]
    assert all(ev["t"] >= 0 for ev in events)
    # 时间戳单调不减
    assert all(events[i]["t"] <= events[i + 1]["t"] for i in range(len(events) - 1))

    snap = rec.snapshot()
    assert snap["counts"]["move"] == 1
    assert snap["counts"]["left"] == 1  # 仅统计按下
    assert snap["counts"]["right"] == 1
    assert snap["counts"]["wheel"] == 1
    assert snap["counts"]["key"] == 1


def test_recorder_ignores_events_when_not_recording():
    rec = Recorder()
    rec.add_mouse("move", {"x": 1, "y": 2})
    rec.add_key(0x41, 0x1E, "down", False)
    assert rec.event_count == 0


def test_recorder_set_events_rebuilds_stats():
    rec = Recorder()
    rec.set_events(
        [
            {"t": 0, "k": "move", "x": 1, "y": 1},
            {"t": 10, "k": "btn", "b": "middle", "a": "down", "x": 1, "y": 1},
            {"t": 20, "k": "key", "vk": 65, "sc": 30, "a": "down", "ext": False},
        ]
    )
    snap = rec.snapshot()
    assert snap["count"] == 3
    assert snap["counts"]["middle"] == 1
    assert snap["duration_ns"] == 20


# ---------------------------------------------------------------- 回放
def test_button_flags_mapping():
    assert player._button_flags("left", "down") == (winapi.MOUSEEVENTF_LEFTDOWN, 0)
    assert player._button_flags("left", "up") == (winapi.MOUSEEVENTF_LEFTUP, 0)
    assert player._button_flags("x1", "down") == (winapi.MOUSEEVENTF_XDOWN, winapi.XBUTTON1)
    assert player._button_flags("x2", "up") == (winapi.MOUSEEVENTF_XUP, winapi.XBUTTON2)
    assert player._button_flags("unknown", "down") == (0, 0)


def test_precise_sleep_returns_immediately_for_past_deadline():
    start = time.perf_counter_ns()
    player.precise_sleep_until(start - 1)
    assert time.perf_counter_ns() - start < 50_000_000  # 应几乎立即返回


def test_precise_sleep_waits_about_requested_time():
    target = time.perf_counter_ns() + 5_000_000  # 5ms
    player.precise_sleep_until(target)
    assert time.perf_counter_ns() >= target


def test_player_start_requires_events():
    p = player.Player()
    assert p.start([], 1, 0.0) is False


# ---------------------------------------------------------------- 存储
def test_storage_round_trip(tmp_path):
    events = [
        {"t": 0, "k": "move", "x": 3, "y": 4},
        {"t": 1000, "k": "key", "vk": 65, "sc": 30, "a": "down", "ext": False},
    ]
    path = storage.save_recording(events, "单元测试", directory=tmp_path)
    assert path.exists()

    loaded, meta = storage.load_recording(path)
    assert loaded == events
    assert meta["company"] == "Clara"
    assert meta["count"] == 2
    assert meta["app"] == storage.APP_NAME

    files = storage.list_recordings(tmp_path)
    assert path in files


def test_storage_sanitizes_name(tmp_path):
    path = storage.save_recording([], "bad/name:with*chars", directory=tmp_path)
    assert path.exists()
    assert "/" not in path.name and ":" not in path.name and "*" not in path.name


# ---------------------------------------------------------------- 配置
def test_config_defaults_and_persistence(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg = Config(cfg_path)
    assert cfg.repeat_count == DEFAULTS["repeat_count"]
    assert cfg.interval_seconds == DEFAULTS["interval_seconds"]

    cfg.set("repeat_count", 7)
    cfg.set("interval_seconds", 2.5)
    assert cfg.save()

    again = Config(cfg_path)
    assert again.repeat_count == 7
    assert again.interval_seconds == 2.5


def test_config_handles_corrupt_file(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{ not valid json", encoding="utf-8")
    cfg = Config(cfg_path)
    assert cfg.repeat_count == DEFAULTS["repeat_count"]


# ---------------------------------------------------------------- Win API
def test_to_absolute_is_in_range():
    for x, y in [(0, 0), (100, 200), (1920, 1080), (-500, 3000)]:
        nx, ny = winapi.to_absolute(x, y)
        assert 0 <= nx <= 65535
        assert 0 <= ny <= 65535


def test_mouse_and_key_input_construction():
    mi = winapi.mouse_input(winapi.MOUSEEVENTF_MOVE, dx=10, dy=20)
    assert mi.type == winapi.INPUT_MOUSE
    assert mi.mi.dx == 10 and mi.mi.dy == 20

    ki = winapi.key_input(0x41, 0x1E, extended=False, up=True)
    assert ki.type == winapi.INPUT_KEYBOARD
    assert ki.ki.wScan == 0x1E
    assert ki.ki.dwFlags & winapi.KEYEVENTF_KEYUP
    assert ki.ki.dwFlags & winapi.KEYEVENTF_SCANCODE


def test_input_struct_sizes_match_windows():
    # x64 下 INPUT 应为 40 字节，MOUSEINPUT 32 字节，KEYBDINPUT 24 字节
    import ctypes

    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert ctypes.sizeof(winapi.INPUT) == 40
        assert ctypes.sizeof(winapi.MOUSEINPUT) == 32
        assert ctypes.sizeof(winapi.KEYBDINPUT) == 24


def test_environment_queries_return_sane_values():
    assert winapi.get_primary_size()[0] > 0
    assert winapi.get_dpi() > 0
    width, height = winapi.get_primary_size()
    assert width >= 640 and height >= 480


def test_json_recording_format_is_readable(tmp_path):
    events = [{"t": 0, "k": "move", "x": 1, "y": 1}]
    path = storage.save_recording(events, "fmt", directory=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"meta", "events"}
