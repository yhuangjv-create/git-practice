"""Windows 底层 API 封装（纯标准库 ctypes，无第三方依赖）。

本模块提供：
* 管理员权限检测与提权（runas）
* DPI 感知设置、屏幕分辨率、刷新率、DPI 查询
* 高精度计时器（timeBeginPeriod）
* 全局低级输入钩子所需的类型与原型（WH_MOUSE_LL / WH_KEYBOARD_LL）
* SendInput 输入注入所需的类型、常量与调用封装
"""

from __future__ import annotations

import contextlib
import ctypes
import sys

# ------------------------------------------------------------------ 基础类型
BYTE = ctypes.c_ubyte
WORD = ctypes.c_ushort
DWORD = ctypes.c_ulong
LONG = ctypes.c_long
UINT = ctypes.c_uint
BOOL = ctypes.c_int
LONG_PTR = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t
WPARAM = ULONG_PTR
LPARAM = LONG_PTR
LRESULT = LONG_PTR

HHOOK = ctypes.c_void_p
HWND = ctypes.c_void_p
HINSTANCE = ctypes.c_void_p
HMODULE = ctypes.c_void_p
HDC = ctypes.c_void_p

# ------------------------------------------------------------------ DLL
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

try:
    winmm = ctypes.WinDLL("winmm", use_last_error=True)
except OSError:  # pragma: no cover - winmm 在所有 Windows 上都存在
    winmm = None

try:
    shcore = ctypes.WinDLL("shcore", use_last_error=True)
except OSError:  # pragma: no cover - 仅老系统缺失
    shcore = None

# ------------------------------------------------------------------ 常量
# 钩子类型
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0

# 鼠标消息
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_MOUSEHWHEEL = 0x020E

# 键盘消息
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

# 钩子结构体标志位（用于识别“注入事件”，避免回放时自我触发）
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01

# 虚拟屏幕度量
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SM_CMONITORS = 80

# GetDeviceCaps 索引
LOGPIXELSX = 88
VREFRESH = 116

# SendInput 常量
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

XBUTTON1 = 1
XBUTTON2 = 2

WHEEL_DELTA = 120

# DPI 感知级别
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
PROCESS_PER_MONITOR_DPI_AWARE = 2

SW_SHOWNORMAL = 1

# ------------------------------------------------------------------ 结构体


class POINT(ctypes.Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", DWORD),
        ("scanCode", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("message", UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", DWORD),
        ("pt", POINT),
        ("lPrivate", DWORD),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", LONG),
        ("dy", LONG),
        ("mouseData", DWORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", WORD),
        ("wScan", WORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", DWORD),
        ("wParamL", WORD),
        ("wParamH", WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", DWORD),
        ("u", _INPUTUNION),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)

# ------------------------------------------------------------------ 函数原型

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, HINSTANCE, DWORD]
user32.SetWindowsHookExW.restype = HHOOK

user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = BOOL

user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LRESULT

user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), HWND, UINT, UINT]
user32.GetMessageW.restype = ctypes.c_int

user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]

user32.PostThreadMessageW.argtypes = [DWORD, UINT, WPARAM, LPARAM]
user32.PostThreadMessageW.restype = BOOL

user32.SendInput.argtypes = [UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = UINT

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

user32.GetDC.argtypes = [HWND]
user32.GetDC.restype = HDC

user32.ReleaseDC.argtypes = [HWND, HDC]
user32.ReleaseDC.restype = ctypes.c_int

user32.GetDpiForSystem.argtypes = []
user32.GetDpiForSystem.restype = UINT

shell32.IsUserAnAdmin.argtypes = []
shell32.IsUserAnAdmin.restype = BOOL

shell32.ShellExecuteW.argtypes = [
    HWND,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.c_int,
]
shell32.ShellExecuteW.restype = HINSTANCE

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = DWORD

kernel32.GetTickCount.argtypes = []
kernel32.GetTickCount.restype = DWORD

kernel32.GetCurrentThread.argtypes = []
kernel32.GetCurrentThread.restype = ctypes.c_void_p  # 伪句柄，仅当前线程可用

kernel32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
kernel32.SetThreadPriority.restype = BOOL

THREAD_PRIORITY_HIGHEST = 2
THREAD_PRIORITY_TIME_CRITICAL = 15


def set_thread_priority(priority: int) -> bool:
    """提升当前线程优先级（TIME_CRITICAL=15 / HIGHEST=2），减少调度抖动。"""
    try:
        return bool(kernel32.SetThreadPriority(kernel32.GetCurrentThread(), int(priority)))
    except Exception:
        return False

gdi32.GetDeviceCaps.argtypes = [HDC, ctypes.c_int]
gdi32.GetDeviceCaps.restype = ctypes.c_int

if winmm is not None:
    winmm.timeBeginPeriod.argtypes = [UINT]
    winmm.timeBeginPeriod.restype = UINT
    winmm.timeEndPeriod.argtypes = [UINT]
    winmm.timeEndPeriod.restype = UINT

if shcore is not None:
    shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
    shcore.SetProcessDpiAwareness.restype = ctypes.c_int

# ------------------------------------------------------------------ 工具函数


def is_admin() -> bool:
    """当前进程是否以管理员权限运行。"""
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(workdir: str | None = None) -> bool:
    """以管理员权限重新启动当前程序。

    PyInstaller 打包后 ``sys.executable`` 直接是 EXE 本身，不需要
    ``-m mkr`` 参数；开发模式下是 ``python.exe -m mkr``。
    成功拉起（返回句柄 > 32）时返回 True；用户取消 UAC 时返回 False。
    """
    # PyInstaller onefile / onedir 环境：直接 runas 当前 EXE
    params = "" if getattr(sys, "frozen", False) else "-m mkr"
    try:
        ret = shell32.ShellExecuteW(
            None, "runas", sys.executable, params, workdir or None, SW_SHOWNORMAL
        )
    except Exception:
        return False
    return int(ret) > 32


def enable_dpi_awareness() -> None:
    """声明进程为每显示器 DPI 感知，保证坐标为物理像素，避免缩放误差。"""
    try:
        if shcore is not None:
            shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
            return
    except Exception:
        pass
    with contextlib.suppress(Exception):
        ctypes.windll.user32.SetProcessDPIAware()


def get_primary_size() -> tuple[int, int]:
    """主显示器分辨率（物理像素）。"""
    return int(user32.GetSystemMetrics(SM_CXSCREEN)), int(user32.GetSystemMetrics(SM_CYSCREEN))


def get_virtual_screen() -> tuple[int, int, int, int]:
    """多显示器虚拟桌面矩形 (left, top, width, height)，物理像素。"""
    left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    return left, top, width, height


def get_monitor_count() -> int:
    return int(user32.GetSystemMetrics(SM_CMONITORS))


def get_refresh_rate() -> int:
    """主显示器刷新率（Hz）。"""
    hdc = user32.GetDC(None)
    if not hdc:
        return 0
    try:
        return int(gdi32.GetDeviceCaps(hdc, VREFRESH))
    finally:
        user32.ReleaseDC(None, hdc)


def get_dpi() -> int:
    """系统 DPI（96 为 100% 缩放）。"""
    try:
        dpi = int(user32.GetDpiForSystem())
        if dpi > 0:
            return dpi
    except Exception:
        pass
    hdc = user32.GetDC(None)
    if not hdc:
        return 96
    try:
        return int(gdi32.GetDeviceCaps(hdc, LOGPIXELSX))
    finally:
        user32.ReleaseDC(None, hdc)


def begin_time_period(period_ms: int = 1) -> bool:
    """将系统计时器分辨率提升到 period_ms 毫秒，提高 sleep 精度。"""
    if winmm is None:
        return False
    try:
        return winmm.timeBeginPeriod(UINT(period_ms)) == 0
    except Exception:
        return False


def get_tick_count() -> int:
    """系统启动以来的毫秒数（与钩子结构体的 time 字段同一时钟源）。"""
    return int(kernel32.GetTickCount())


def end_time_period(period_ms: int = 1) -> None:
    if winmm is None:
        return
    with contextlib.suppress(Exception):
        winmm.timeEndPeriod(UINT(period_ms))


def to_absolute(x: int, y: int) -> tuple[int, int]:
    """把屏幕物理坐标转换为 SendInput 绝对坐标（0..65535，覆盖整个虚拟桌面）。"""
    left, top, width, height = get_virtual_screen()
    width = max(1, width)
    height = max(1, height)
    nx = round((x - left) * 65535 / max(1, width - 1))
    ny = round((y - top) * 65535 / max(1, height - 1))
    return max(0, min(65535, nx)), max(0, min(65535, ny))


def mouse_input(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
    """构造鼠标 INPUT 事件。"""
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dx = dx
    inp.mi.dy = dy
    inp.mi.mouseData = data & 0xFFFFFFFF
    inp.mi.dwFlags = flags
    inp.mi.time = 0
    inp.mi.dwExtraInfo = 0
    return inp


def key_input(vk: int, scan: int, extended: bool, up: bool) -> INPUT:
    """构造键盘 INPUT 事件。

    同时填写 vkCode 与 scanCode。只填 scanCode（KEYEVENTF_SCANCODE + wVk=0）
    时，Windows 输入法框架、热键管理器等组件不会正确维护修饰键状态表
    ——它们靠 vkCode 判断 Ctrl/Shift/Alt 是否被按下，导致回放修饰键时
    系统不认"修饰键已按下"，后续按键被当成无修饰键处理，事件顺序被
    输入法重排。把两者都填上，两条识别路径都能正确工作。
    """
    flags = 0
    if scan:
        flags |= KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if up:
        flags |= KEYEVENTF_KEYUP

    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk            # 始终填 vkCode，保证修饰键状态表正确
    inp.ki.wScan = scan        # 有 scanCode 就填，兼容游戏窗口
    inp.ki.dwFlags = flags
    inp.ki.time = 0
    inp.ki.dwExtraInfo = 0
    return inp


def send_inputs(inputs: list[INPUT]) -> int:
    """批量注入输入事件，返回成功注入的事件数。"""
    if not inputs:
        return 0
    n = len(inputs)
    array = (INPUT * n)(*inputs)
    return int(user32.SendInput(n, array, ctypes.sizeof(INPUT)))
