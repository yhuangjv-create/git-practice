"""录制文件读写（JSON 格式，便于查看与迁移）。

用户数据存放目录的决定逻辑见 config._resolve_user_dir。
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from . import __company__, __version__, winapi
from .config import USER_DIR

RECORDINGS_DIR = USER_DIR / "recordings"

APP_NAME = "鼠标键盘活动记录重复器"


def _ensure_dir() -> Path:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return RECORDINGS_DIR


def build_meta(events: list[dict[str, Any]], name: str = "") -> dict[str, Any]:
    """根据当前系统环境与事件列表生成录制元数据。"""
    width, height = winapi.get_primary_size()
    virt = winapi.get_virtual_screen()
    return {
        "app": APP_NAME,
        "company": __company__,
        "version": __version__,
        "name": name,
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "screen": {
            "width": width,
            "height": height,
            "refresh_hz": winapi.get_refresh_rate(),
            "dpi": winapi.get_dpi(),
            "monitors": winapi.get_monitor_count(),
            "virtual": {"left": virt[0], "top": virt[1], "width": virt[2], "height": virt[3]},
        },
        "duration_ns": events[-1]["t"] if events else 0,
        "count": len(events),
    }


def save_recording(
    events: list[dict[str, Any]], name: str = "", directory: Path | None = None
) -> Path:
    """保存录制到 JSON 文件，返回文件路径。"""
    folder = Path(directory) if directory else _ensure_dir()
    folder.mkdir(parents=True, exist_ok=True)

    if not name:
        name = _dt.datetime.now().strftime("recording_%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "recording"
    path = folder / f"{safe_name}.json"

    payload = {"meta": build_meta(events, safe_name), "events": events}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_recording(path: Path | str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """读取录制文件，返回 (事件列表, 元数据)。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        # 兼容仅保存事件数组的旧格式
        return list(raw), {}
    events = list(raw.get("events", []))
    meta = dict(raw.get("meta", {}))
    return events, meta


def list_recordings(directory: Path | None = None) -> list[Path]:
    """列出录制目录下的所有录制文件，按修改时间倒序。"""
    folder = Path(directory) if directory else _ensure_dir()
    if not folder.exists():
        return []
    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files
