"""全局快捷键的解析与匹配。

快捷键以字符串表示，例如 ``"f9"``、``"ctrl+alt+r"``。
最后一个键为主键，其余为修饰键；当主键被按下且所有修饰键同时处于按下状态时触发。
"""

from __future__ import annotations

# 名称 -> 虚拟键码
_NAME_TO_VK: dict[str, int] = {
    # 修饰键
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "win": 0x5B,
    "super": 0x5B,
    "cmd": 0x5B,
    # 常用功能键
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "capslock": 0x14,
    "pause": 0x13,
}

for _i in range(1, 25):
    _NAME_TO_VK[f"f{_i}"] = 0x70 + (_i - 1)

for _c in "abcdefghijklmnopqrstuvwxyz":
    _NAME_TO_VK[_c] = ord(_c.upper())

for _d in "0123456789":
    _NAME_TO_VK[_d] = 0x30 + int(_d)

# 特定左右修饰键 -> 通用修饰键
_VK_ALIAS = {
    0xA0: 0x10,  # 左 Shift
    0xA1: 0x10,  # 右 Shift
    0xA2: 0x11,  # 左 Ctrl
    0xA3: 0x11,  # 右 Ctrl
    0xA4: 0x12,  # 左 Alt
    0xA5: 0x12,  # 右 Alt
    0x5C: 0x5B,  # 右 Win
}

_VK_TO_NAME: dict[int, str] = {}
for _name, _code in _NAME_TO_VK.items():
    _VK_TO_NAME.setdefault(_code, _name)


def normalize_vk(vk: int) -> int:
    """把左/右专用修饰键码统一为通用修饰键码，便于组合键匹配。"""
    return _VK_ALIAS.get(vk, vk)


def parse(combo: str) -> list[int]:
    """把 ``"ctrl+alt+r"`` 解析为虚拟键码列表 ``[17, 18, 82]``。"""
    codes: list[int] = []
    for token in str(combo).split("+"):
        token = token.strip().lower()
        if not token:
            continue
        if token not in _NAME_TO_VK:
            raise ValueError(f"无法识别的按键: {token}")
        codes.append(_NAME_TO_VK[token])
    if not codes:
        raise ValueError("快捷键不能为空")
    return codes


def format_combo(codes: list[int]) -> str:
    """把虚拟键码列表还原为可读字符串。"""
    return "+".join(_VK_TO_NAME.get(c, f"0x{c:02X}") for c in codes)


def is_modifier(vk: int) -> bool:
    return normalize_vk(vk) in (0x10, 0x11, 0x12, 0x5B)


class HotkeyManager:
    """维护“动作名 -> 组合键”的绑定，并根据键盘事件判断是否触发。"""

    def __init__(self) -> None:
        self.bindings: dict[str, list[int]] = {}
        self._pressed: set[int] = set()

    def set(self, name: str, combo: str) -> None:
        self.bindings[name] = parse(combo)

    def set_codes(self, name: str, codes: list[int]) -> None:
        self.bindings[name] = list(codes)

    def get_combo(self, name: str) -> str:
        codes = self.bindings.get(name)
        return format_combo(codes) if codes else ""

    @property
    def pressed(self) -> set[int]:
        return set(self._pressed)

    def on_key(self, vk: int, action: str) -> list[str]:
        """喂入一个键盘事件，返回本次触发的动作名列表。

        ``action`` 为 ``"down"`` 或 ``"up"``。按住不放产生的自动重复不会重复触发。
        """
        code = normalize_vk(vk)
        triggered: list[str] = []

        if action == "down":
            is_repeat = code in self._pressed
            self._pressed.add(code)
            if not is_repeat:
                for name, codes in self.bindings.items():
                    if not codes:
                        continue
                    main = normalize_vk(codes[-1])
                    if code == main and all(normalize_vk(c) in self._pressed for c in codes[:-1]):
                        triggered.append(name)
        else:
            self._pressed.discard(code)

        return triggered
