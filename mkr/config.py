"""用户配置读写。

开发模式下配置文件位于项目根目录 ``config.json``；
PyInstaller 打包后：
  - EXE 所在目录可写（便携模式）→ EXE 同目录 ``config.json``
  - EXE 所在目录只读（如 Program Files，安装模式）→ ``%APPDATA%/ClaraRecorder/config.json``
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _resolve_user_dir() -> Path:
    """决定用户数据存放目录（配置 + 录制文件）。"""
    if getattr(sys, "frozen", False):
        # PyInstaller：尝试 EXE 所在目录（便携模式），不可写则退到 AppData
        exe_dir = Path(sys.executable).resolve().parent
        try:
            test = exe_dir / ".write_test_tmp"
            test.write_text("ok")
            test.unlink()
            return exe_dir
        except (PermissionError, OSError):
            appdata = Path(os.environ.get("APPDATA", str(Path.home())))
            target = appdata / "ClaraRecorder"
            target.mkdir(parents=True, exist_ok=True)
            return target
    else:
        # 开发模式：项目根目录
        return Path(__file__).resolve().parent.parent


USER_DIR = _resolve_user_dir()
CONFIG_PATH = USER_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "repeat_count": 1,
    "interval_seconds": 1.0,
    "speed": 1.0,
    "hotkey_start_record": "alt+shift+f9",
    "hotkey_stop_record": "alt+shift+f10",
    "hotkey_start_play": "alt+shift+f11",
    "hotkey_stop_play": "alt+shift+f12",
    "last_recording": "",
}


class Config:
    """简单的 JSON 配置对象。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else CONFIG_PATH
        self.data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        self.data = dict(DEFAULTS)
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key, value in raw.items():
                        self.data[key] = value
        except (OSError, json.JSONDecodeError):
            # 配置损坏时回退到默认值，不影响程序使用
            self.data = dict(DEFAULTS)

    def save(self) -> bool:
        try:
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return True
        except OSError:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    # ------------------------------------------------------------ 便捷读取
    @property
    def repeat_count(self) -> int:
        try:
            return max(1, int(self.get("repeat_count", 1)))
        except (TypeError, ValueError):
            return 1

    @property
    def interval_seconds(self) -> float:
        try:
            return max(0.0, float(self.get("interval_seconds", 1.0)))
        except (TypeError, ValueError):
            return 1.0

    @property
    def speed(self) -> float:
        try:
            return max(0.05, float(self.get("speed", 1.0)))
        except (TypeError, ValueError):
            return 1.0
