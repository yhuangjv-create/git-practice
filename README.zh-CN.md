# 鼠标键盘活动记录重复器 V1.6 · Clara

> 零第三方依赖（纯 `ctypes` + `tkinter` + Python 标准库）的 Windows 桌面工具。
> 微秒级时间分辨率录制，sub-100µs 精度回放注入。

[English](README.md) | **简体中文**

> 本文档为**中文完整版**，也是项目的权威文档；英文版 [`README.md`](README.md) 为精简摘要。
> 两者如有出入，以本文档为准。

<!-- ==================================================================
  ⚠️  每次程序改动 / 版本升级，必须同步完成两件事：

  【A. 版本号四处同步】
      1. mkr/__init__.py  → __version__ 字符串（版本号单一真源）
      2. mkr/gui.py      → I18N 字典中文 window_title / title_main 里的 Vx.y
      3. mkr/gui.py      → I18N 字典英文 window_title / title_main 里的 Vx.y
      4. 本 README.zh-CN.md / README.md → 顶部标题里的 Vx.y + 元数据示例里的 version 值
      搜索关键字 "V1.5" 和 "1.5.0" 即可定位所有需要改的位置

  【B. README 内容同步更新】
      - 改动涉及的模块 → 更新第 3 节（调用关系）和第 4 节（逐文件解释）对应条目
      - 新增 / 删除功能 → 更新第 1.1 节（功能一览）
      - 设计要点变更    → 更新第 1.2 节（关键设计要点）
      - 目录结构变化    → 更新第 2 节（目录树）
      - 注意事项变化    → 更新第 1.3 节（注意事项）
      - 无论改动大小    → 在本文件末尾 CHANGELOG 区块追加一条记录
      - 英文版 README.md → 功能表 / 快速开始 / 技术亮点 三节同步（精简摘要即可）
  ================================================================== -->

---

## 目录

- [1. 功能介绍与注意事项](#1-功能介绍与注意事项)
  - [1.1 功能一览](#11-功能一览)
  - [1.2 关键设计要点](#12-关键设计要点)
  - [1.3 注意事项](#13-注意事项)
- [2. 目录树与文件夹作用](#2-目录树与文件夹作用)
- [3. 文件作用与互相调用逻辑](#3-文件作用与互相调用逻辑)
  - [3.1 模块调用关系图](#31-模块调用关系图)
  - [3.2 启动链路](#32-启动链路)
  - [3.3 录制链路](#33-录制链路)
  - [3.4 回放链路](#34-回放链路)
- [4. 逐文件代码解释](#4-逐文件代码解释)
  - [4.1 `mkr/__init__.py`](#41-mkr__init__py)
  - [4.2 `mkr/__main__.py`](#42-mkr__main__py)
  - [4.3 `mkr/winapi.py`](#43-mkrwinapipy)
  - [4.4 `mkr/hooks.py`](#44-mkrhookspy)
  - [4.5 `mkr/hotkeys.py`](#45-mkrhotkeyspy)
  - [4.6 `mkr/recorder.py`](#46-mkrrecorderpy)
  - [4.7 `mkr/player.py`](#47-mkrplayerpy)
  - [4.8 `mkr/config.py`](#48-mkrconfigpy)
  - [4.9 `mkr/storage.py`](#49-mkrstoragepy)
  - [4.10 `mkr/gui.py`](#410-mkrguipy)
  - [4.11 `mkr/app.py`](#411-mkrapppy)
  - [4.12 `run.bat`](#412-runbat)
  - [4.13 `config.json`](#413-configjson)

---

## 1. 功能介绍与注意事项

### 1.1 功能一览

| 功能 | 说明 |
|---|---|
| 全局录制 | 微秒级分辨率，鼠标轨迹、按键按下/抬起、滚轮、键盘全部记录 |
| 全局回放 | `SendInput` 注入，高精度定时，支持次数 / 间隔 / 倍速 |
| 倍速回放 | 0.1×–20× 连续可调，修饰键顺序语义不丢失（成批窗口跟随 speed 缩放） |
| 录制保存 / 载入 | JSON 文件，含环境元数据，便于迁移 |
| 全局快捷键 | 4 个动作均可自定义组合键 |
| 中 / 英界面切换 | 右上角橙色按钮一键切换，所有文字同步刷新 |
| 主界面背景图 | cover 模式（等比缩放 + 居中裁剪，不变形），自适应窗口尺寸 |
| 窗口自适应 | 首次打开自动按内容调整到合适大小，支持手动拉伸 |
| 自动提权 | 非管理员启动时自动 `runas` 以管理员权限重启自身 |

### 1.2 关键设计要点

**录制精度 — 双时钟融合**（`recorder.py::_now_ns`）：

```
tick  >= 1ms  →  用 tick 锚定绝对时刻（抗回调分发延迟）
tick 相同     →  用 perf 差细分（亚毫秒分辨率）
```

- `tick` = Windows 在事件进入系统时打的毫秒戳（`KBDLLHOOKSTRUCT.time`）
- `perf` = 钩子回调入口取的 `perf_counter_ns()`（越早取越接近真实按键）
- 录制期间 `timeBeginPeriod(1)` 把 tick 粒度从 ~15.6ms 提到 ~1ms

**回放精度 — 安全 sleep + 自旋 + 成批发送**（`player.py`）：

```
deadline - 当前时刻  >  1.5ms  → sleep 到 deadline-1.5ms，再自旋
deadline - 当前时刻  >  200µs  → sleep 到 deadline-200µs，再自旋
deadline - 当前时刻  ≤  200µs  → 纯自旋（放弃 sleep）
```

- 永远不在 deadline 之前 sleep 完——sleep 只到安全余量，让自旋做最后精准等待
- 唤醒误差实测 avg ~323ns，p95 ~1.1µs（Windows 原生 sleep 在 0.3–2ms 区间抖动 300–700µs）
- 连续事件间隔 < `batch_window_ns` 合并到一次 `SendInput` 调用（成批窗口跟随 `speed` 缩放）
- 回放期间禁用 GC + 线程提权到 `THREAD_PRIORITY_TIME_CRITICAL`，消除随机停顿
- 时间轴只用绝对 deadline，抖动不会跨事件传播

**修饰键状态自动释放**（`player.py::InjectedState`）：

- 只释放本实例**已注入 down 但未 up** 的键，绝不 blanket 释放——避免误伤用户正在物理按下的键
- 用 `(scan, vk, extended)` 三元组做键标识（`scanCode` 和 `vkCode` 同时填写，保证输入法框架正确维护修饰键状态表）
- 堆叠计数器处理"同键多次按下未抬"的情况

### 1.3 注意事项

| 事项 | 原因 |
|---|---|
| **必须管理员权限运行** | 普通权限下无法捕获发往高权限窗口的输入，也无法回放 SendInput 到管理员窗口。程序会自动以 `runas` 重启 |
| **不能录制自身的注入事件** | 已通过 `LLKHF_INJECTED` / `LLMHF_INJECTED` 标志过滤，但如果安装了反作弊等内核级钩子仍可能被拦截 |
| **输入法切换依赖修饰键状态** | 修饰键的 `vkCode` 和 `scanCode` 必须同时填写（不能只填 scanCode 而 vkCode=0），否则 Windows 输入法框架不认 |
| **录制文件是 JSON** | 直接可读、可编辑、可迁移，但大量事件时文件会变大 |
| **无网络功能** | 所有数据本地存储，不上传任何信息 |
| **背景图分辨率** | 当前使用 1080×2158 竖图，在横屏窗口上会被上下裁剪（cover 模式） |

---

## 2. 目录树与文件夹作用

```
MouseKeyboardRecorder/
│
├── run.bat                    # 启动脚本（自动 UAC 提权 + 分离控制台）
├── entry.py                   # PyInstaller 打包入口（绝对导入，避免 __main__ 相对导入问题）
├── installer.py               # 安装器 GUI（自定义目录 + 快捷方式勾选）
├── config.json                # 用户配置（快捷键、重复次数、倍速等）
│
├── assets/
│   └── background.jpg         # 主界面背景图（cover 模式，等比裁剪不变形）
│
├── mkr/                        # 主程序包
│   ├── __init__.py            # 版本号 + 模块说明
│   ├── __main__.py            # 入口：python -m mkr
│   ├── winapi.py              # Windows ctypes 底层封装
│   ├── hooks.py               # WH_KEYBOARD_LL / WH_MOUSE_LL 钩子线程
│   ├── hotkeys.py             # 全局快捷键解析与匹配
│   ├── recorder.py            # 录制引擎（双时钟融合）
│   ├── player.py              # 回放引擎（安全 sleep + 自旋 + 成批）
│   ├── config.py              # JSON 配置读写（frozen 环境智能选用户目录）
│   ├── storage.py             # 录制文件读写（同 config 的用户目录）
│   ├── gui.py                 # tkinter 界面（含 i18n、背景图、自适应窗口）
│   └── app.py                 # 程序装配：把上面所有模块连起来
│
├── recordings/                 # 用户保存的录制文件（首次保存自动创建）
│   └── *.json                 # 每个录制是一个 JSON 文件
│
├── tests/                      # 单元测试
│   └── test_mkr.py
│
├── pyproject.toml              # ruff + pytest 配置
└── README.md                   # 本文件
```

**文件夹作用**：

| 文件夹 | 作用 |
|---|---|
| `mkr/` | 主程序包，零第三方依赖（PIL 可选，仅背景图功能需要） |
| `assets/` | 静态资源，目前只有一张背景图 |
| `recordings/` | 用户保存的录制文件存放目录 |
| `tests/` | 单元测试，覆盖 hooks / recorder / player / hotkeys / config |

---

## 3. 文件作用与互相调用逻辑

### 3.1 模块调用关系图

```
                    ┌─────────────────┐
                    │   run.bat       │
                    │ pythonw -m mkr  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  __main__.py    │  入口转发
                    └────────┬────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │              app.py                  │
          │  Controller / main() / _run_self_check
          └──┬─────┬─────┬─────┬─────┬─────┬─────┘
             │     │     │     │     │     │
    ┌────────▼┐ ┌──▼───┐ ┌▼──┐ ┌▼──┐ ┌▼──┐ ┌▼──┐
    │  gui.py │ │hooks │ │hrk│ │rec│ │plr│ │cfg│
    │ MainWin │ │InputH│ │Hkm│ │Rec│ │Ply│ │Cfg│
    └────┬────┘ └──┬───┘ └───┘ └─┬─┘ └─┬─┘ └─┬─┘
         │         │              │     │     │
         ▼         ▼              ▼     ▼     ▼
      hotkeys.py  recorder.py    player.py  config.py  storage.py
      (解析/匹配) (录制/时间戳) (回放/注入) (读写)    (读写)
         │              │           │
         └──────────────┼───────────┘
                        ▼
                   winapi.py
              (ctypes 全部 Windows 调用)
```

### 3.2 启动链路

```
run.bat
  → pythonw -m mkr
    → __main__.py::main()
      → app.py::main()
        → winapi.enable_dpi_awareness()
        → winapi.relaunch_as_admin()  # 非管理员时 UAC 提权重启自身
        → Controller()
            → Config()             # 载入 config.json
            → Recorder()           # 初始化录制器
            → Player()             # 初始化回放器
            → HotkeyManager()      # 载入快捷键绑定
            → InputHook(start)     # 启动钩子线程（WH_KEYBOARD_LL + WH_MOUSE_LL）
        → MainWindow(controller)   # 构建 GUI
        → window.run()             # 进入 tkinter mainloop
```

### 3.3 录制链路

```
用户按下 Ctrl 键
  → 硬件中断 → Windows 内核
    → win32k.sys 生成 WM_KEYDOWN
      → 钩子线程 GetMessageW() 捕获
        → hooks.py::_key_callback()
            → time.perf_counter_ns()  # 回调入口立刻取微秒戳
            → cast(l_param, KBDLLHOOKSTRUCT)  # 解析扫描码、vkCode、time
            → 检查 LLKHF_INJECTED  # 过滤回放自触发
            → Controller._on_key("key", {vk, scan, action, extended, tick, perf})
                → HotkeyManager.on_key()  # 匹配快捷键组合（只返回名称，不录制）
                → Recorder.add_key(vk, scan, action, extended, tick, perf)
                    → _now_ns(tick, perf)  # 双时钟融合 → 纳秒级时间戳
                    → _events.append({t, k:"key", vk, sc, a:"down", ext})
                    → _stats["key"] += 1
```

### 3.4 回放链路

```
用户按回放快捷键（或 GUI 按钮）
  → Controller.start_playback()
    → Player.start(events, repeat, interval, speed)
        → build_inputs(e) × N   # 预构建所有事件的 INPUT 数组
        → threading.Thread(target=_run, prebuilt, repeat, interval, speed)
            → timeBeginPeriod(1)  # 提升计时器精度
            → gc.disable()         # 消除 GC 停顿
            → set_thread_priority(TIME_CRITICAL)  # 提升线程优先级
            → for pass in range(repeat):
                → for event in prebuilt:
                    → precise_sleep_until(base + event.t / speed)
                        # 安全 sleep + 两阶段自旋
                    → 成批扫描（batch_window_ns 跟随 speed 缩放）
                    → winapi.send_inputs(batch_inputs)  # 一次 SendInput 批量注入
                    → InjectedState._update_state()  # 记录已注入按键
                → interval 等待（pass 之间）
            → InjectedState.release_all()  # 精准释放：先鼠标→普通键→修饰键
            → gc.enable()
            → end_time_period(1)
            → ui_queue.put(("play_finished", aborted))
                → GUI 刷新状态栏
```

---

## 4. 逐文件代码解释

### 4.1 `mkr/__init__.py`

**作用**：模块元信息 + 版本号单一真源。

```python
__version__ = "1.5.0"   # ← 每次改版本号只改这里，gui.py I18N 字典里的 Vx.y 要同步改
__company__ = "Clara"
```

版本号标记注释块清晰说明了修改位置和联动点。

### 4.2 `mkr/__main__.py`

**作用**：让 `python -m mkr` 可以直接运行。

```python
from .app import main
if __name__ == "__main__":
    main()
```

只做入口转发，一行逻辑。

### 4.3 `mkr/winapi.py`

**作用**：Windows 所有 ctypes 声明——整个程序与操作系统对话的唯一通道。

**常量区**：

```python
WH_KEYBOARD_LL = 13     # 低级键盘钩子类型
WH_MOUSE_LL = 14        # 低级鼠标钩子类型
LLKHF_INJECTED = 0x10   # 回调标志：此事件是 SendInput 注入的（用来过滤自触发）
LLMHF_INJECTED = 0x01   # 同上，鼠标版
INPUT_MOUSE = 0         # SendInput 输入类型
INPUT_KEYBOARD = 1
MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK  # 鼠标坐标用 0..65535 绝对坐标 + 跨显示器虚拟桌面
KEYEVENTF_SCANCODE = 0x0008  # 键盘事件用扫描码注入（兼容性好）
KEYEVENTF_KEYUP = 0x0002
THREAD_PRIORITY_TIME_CRITICAL = 15  # 回放线程最高优先级
```

**结构体**（`ctypes.Structure`）：

- `INPUT` — SendInput 需要的输入联合结构
- `KEYBDINPUT` — 键盘输入细节
- `MOUSEINPUT` — 鼠标输入细节
- `MSLLHOOKSTRUCT` — 低级鼠标钩子回调收到的数据（含 `time` tick）
- `KBDLLHOOKSTRUCT` — 低级键盘钩子回调收到的数据（含 `time` tick）
- `MSG` — GetMessage 循环的消息结构

**核心函数**：

| 函数 | 作用 |
|---|---|
| `is_admin()` | `IsUserAnAdmin()` 检测是否管理员 |
| `relaunch_as_admin(dir)` | `ShellExecuteExW` runas 自动提权重启自身 |
| `enable_dpi_awareness()` | `SetProcessDpiAwarenessContext`，让坐标不是 125% DPI 下缩放后的值 |
| `get_primary_size()` | `GetSystemMetrics(SM_CXSCREEN/CYSCREEN)` |
| `get_virtual_screen()` | 多显示器虚拟桌面边界 |
| `get_refresh_rate()` | `GetDeviceCaps(VREFRESH)` |
| `get_dpi()` | `GetDeviceCaps(LOGPIXELSX)` |
| `get_monitor_count()` | `GetSystemMetrics(SM_CMONITORS)` |
| `begin_time_period(1)` / `end_time_period(1)` | `timeBeginPeriod(1)` 提升系统计时器精度到 1ms |
| `get_tick_count()` | `GetTickCount()` 毫秒时间戳 |
| `to_absolute(x, y)` | 把物理像素坐标转成 SendInput 需要的 0..65535 绝对坐标 |
| `mouse_input(flags, data, x, y)` | 构造一个 MOUSEINPUT 结构体 |
| `key_input(vk, scan, extended, up)` | 构造一个 KEYBDINPUT——**vk 和 scan 同时填写**（这是修饰键正常工作的关键） |
| `send_inputs([INPUT,...])` | 一次 SendInput 批量注入多个事件 |
| `set_thread_priority(priority)` | `SetThreadPriority` 提升钩子/回放线程 |

### 4.4 `mkr/hooks.py`

**作用**：在独立线程里安装全局低级输入钩子，所有物理输入事件的第一入口。

**核心结构**：

```python
class InputHook:
    def start(self):    # 启动钩子线程（安装 WH_KEYBOARD_LL + WH_MOUSE_LL，运行 GetMessage 循环）
    def stop(self):     # PostThreadMessage(WM_QUIT) 让消息循环退出
    def _run(self):     # 钩子线程体：安装钩子 → GetMessage 循环 → 卸载钩子
    def _mouse_callback(self, ...):  # 鼠标回调：过滤注入事件 → 解析 WM_* → 调用 on_mouse()
    def _key_callback(self, ...):    # 键盘回调：入口先取 perf_counter_ns → 过滤注入 → 调用 on_key()
    def _dispatch_mouse(self, ...):   # 消息分发给 payload 字典
```

**关键细节**：

1. **线程模型**：钩子必须在拥有消息循环的线程里安装，所以 `_run` 独立线程 + `GetMessageW/TranslateMessage/DispatchMessageW` 循环。
2. **回调引用保活**：`self._mouse_proc = HOOKPROC(self._mouse_callback)` 存在实例属性里，防止 GC 回收导致 `SetWindowsHookEx` 传入的函数指针变成野指针。
3. **注入事件过滤**：
   ```python
   if not (int(data.flags) & LLKHF_INJECTED):  # 只录制物理输入，忽略 SendInput 注入
   ```
4. **双时间戳**：每个回调都同时携带 `tick`（Windows 毫秒戳）和 `perf`（回调入口微秒戳），供 recorder 融合。

### 4.5 `mkr/hotkeys.py`

**作用**：全局快捷键的"字符串 ↔ 虚拟键码"双向映射 + 组合键匹配引擎。

**数据结构**：

```python
_NAME_TO_VK = { "ctrl": 0x11, "f9": 0x78, "a": 0x41, ... }  # 名称 → VK 码
_VK_ALIAS   = { 0xA0: 0x10, 0xA2: 0x11, ... }  # 左/右专用修饰键 → 通用码
_HotkeyManager:
    bindings = { "hotkey_start_record": [0x78], ... }  # 动作名 → 组合键码列表
    _pressed = set()  # 当前物理按下的键集合
```

**核心函数**：

| 函数 | 作用 |
|---|---|
| `normalize_vk(vk)` | 把左 Shift(0xA0)、右 Ctrl(0xA3) 等专用码统一为通用码（0x10、0x11），便于组合键匹配 |
| `parse("ctrl+alt+f9")` → `[0x11, 0x12, 0x78]` | 字符串 → VK 码列表 |
| `format_combo([0x11, 0x78])` → `"ctrl+f9"` | VK 码列表 → 字符串 |
| `is_modifier(vk)` | 判断是否修饰键 |

**组合键匹配算法**（`HotkeyManager.on_key`）：

```
收到一个 down 事件：
  code = normalize_vk(vk)
  if code 不是自动重复（第一次 down）:
      for 每个注册的组合键:
          main = 组合键最后一个码（主键）
          if code == main and 所有修饰键都已按下:
              触发该动作
收到一个 up 事件：
  从 _pressed 集合移除 code
```

### 4.6 `mkr/recorder.py`

**作用**：线程安全的录制引擎，钩子线程写入、UI 线程读取。

**双时钟融合算法**（`_now_ns`，精度关键）：

```python
def _now_ns(self, tick: int | None, perf: int | None) -> int:
    prev_t = self._prev_out_t
    delta_ms = (tick - self._prev_tick) & 0xFFFFFFFF  # 处理 tick 回绕（GetTickCount 49.7 天溢出）
    if 0 < delta_ms < 0x8000_0000:
        # tick 差 >= 1ms：以 tick 为准（抗回调大延迟）
        t = prev_t + delta_ms * 1_000_000
    else:
        # tick 相同：同一毫秒内的快速连按，用 perf 差细分
        t = prev_t + max(1, perf - self._prev_perf)
    return t  # 保证严格递增
```

**为什么要这么做**：

- 单时钟 `perf_counter_ns()`：钩子回调有随机 0–几 ms 的分发延迟，录制的时间间隔被扭曲（手速越快，误差占比越大）
- 单时钟 `GetTickCount()`：只有 1ms 粒度，快速连按会被量化成一团
- 融合：tick 锚定绝对时刻（回调延迟再大也不影响），perf 提供亚毫秒分辨率（同一 tick 内的按键能分辨先后）

**事件字典格式**（统一紧凑结构）：

```python
{"t": <纳秒>, "k": "move", "x": .., "y": ..}
{"t": <纳秒>, "k": "btn",  "b": "left|right|middle|x1|x2", "a": "down|up", "x": .., "y": ..}
{"t": <纳秒>, "k": "whl",  "d": <滚轮增量>, "h": <bool 是否横向>, "x": .., "y": ..}
{"t": <纳秒>, "k": "key",  "vk": .., "sc": .., "a": "down|up", "ext": <bool>}
```

### 4.7 `mkr/player.py`

**作用**：高精度回放引擎，支持次数 / 间隔 / 倍速。

**核心函数 `precise_sleep_until`**（sub-100µs 级唤醒精度）：

```python
def precise_sleep_until(deadline_ns):
    while True:
        remaining = deadline_ns - time.perf_counter_ns()
        if remaining <= 0: return
        if remaining > 1.5ms:
            time.sleep(remaining - 1.5ms)   # sleep 到安全余量
        elif remaining > 200µs:
            time.sleep(remaining - 200µs)  # sleep 到更小的余量
        # 否则纯自旋，让 CPU 做最后的精确等待
```

关键：**永远不 sleep 到 deadline**，只 sleep 到"安全余量 + 自旋"。Windows scheduler 的 300–700µs 抖动只会让我们"自旋更久"，绝不会让我们"太晚"。

**成批发送**（`Player._run`）：

```python
batch_window_ns = max(100_000, int(_BATCH_WINDOW_NS / speed))
# ↑ 窗口跟随 speed 同比例缩放！
# 这样 5× 下 Ctrl→Shift 间隔 4ms 变成 0.8ms，窗口 1ms→0.2ms，不会被错误合并
```

`for j in range(idx+1, total):` 扫描连续事件，间隔 < `batch_window_ns` 的合并到同一次 `SendInput`。这正好覆盖"Ctrl down → Shift down → A down"这种用户组合键的真实间隔（通常 < 1ms），一次原子注入反而更稳定。

**`InjectedState` 精准释放**：

- 记录本实例已注入 down 但未 up 的键（三元组 `(scan, vk, ext)` + 堆叠计数）
- `release_all()` 按"先鼠标→普通键→修饰键"顺序释放
- 绝不 blanket 释放，避免误伤用户正在物理按下的键

**`build_inputs(event)` 预构建**：

纯数据转换函数，回放前把所有事件一次性转成 `INPUT` 数组，消除回放循环中的 ctypes 开销。

### 4.8 `mkr/config.py`

**作用**：用户配置的 JSON 读写。

**默认值**（`DEFAULTS`）：

```python
{
    "repeat_count": 1,                    # 重复次数
    "interval_seconds": 1.0,              # 重复间隔（秒）
    "speed": 1.0,                         # 回放倍速
    "hotkey_start_record": "f9",          # 4 个全局快捷键
    "hotkey_stop_record": "f10",
    "hotkey_start_play": "f11",
    "hotkey_stop_play": "f12",
    "last_recording": "",                 # 上次保存的录制文件路径
}
```

**损坏兜底**：JSON 解析失败 → 回退到 DEFAULTS，不影响程序启动。

**便捷属性**：`repeat_count` / `interval_seconds` / `speed` 自动做边界校验（负数变 0，speed 最低 0.05x）。

### 4.9 `mkr/storage.py`

**作用**：录制文件的 JSON 保存与读取。

**元数据**（`build_meta`）：

```python
{
    "app": "鼠标键盘活动记录重复器",
    "company": "Clara",
    "version": "1.5.0",
    "name": "录制_20261112_143015",
    "created": "2026-11-12T14:30:15",
    "screen": { "width": 1920, "height": 1080, "refresh_hz": 144, "dpi": 150, "monitors": 2, "virtual": {...} },
    "duration_ns": 2_500_000_000,
    "count": 42,
}
```

**兼容性**：`load_recording` 同时支持新格式（`{"meta": {...}, "events": [...]}`）和旧格式（纯事件数组），旧录制文件不会打不开。

### 4.10 `mkr/gui.py`

**作用**：tkinter 界面——整个程序唯一的 UI 文件。

**架构**：

```
root
└── base Frame (pack fill=both expand=True)
    ├── Canvas (place relwidth=1 relheight=1) ← 背景图（cover 模式）
    └── content Frame (place relwidth=1 relheight=1, tkraise 到 Canvas 之上)
        ├── header (pack) ← 品牌栏 + 版本号 + 语言切换按钮
        ├── body (pack fill=both expand=True)
        │   ├── left: 操作控制面板 (pack) ← 4 个大按钮 + 保存/载入/清空
        │   └── right: 回放设置面板 (pack) ← 重复次数/间隔/速度 + 系统设置 + 统计
        └── statusbar (pack side=bottom) ← 状态文本 + 进度条
```

**关键技术点**：

| 特性 | 实现方式 |
|---|---|
| 背景图 cover 模式 | `scale = max(w/sw, h/sh)` + 居中裁剪，PIL `LANCZOS` 高质量缩放 |
| 背景图层级 | Canvas 和 content 都 `place` 在同一个 `base` Frame 里（同 geometry manager），content 用 `tkraise()` 提到 Canvas 之上。**不同 geometry manager 混用时 place 永远在 pack/grid 之上**，这是之前背景图被面板盖住的根因 |
| resize 防抖 | `after(80ms)` 重绘，避免每帧缩放卡顿 |
| i18n | 顶部 `I18N` 字典约 70 个 key，zh/en 两套。`_t(key)` 取当前语言值，`_refresh_texts()` 遍历缓存的控件引用逐一 `configure(text=...)` |
| 版本号同步 | 窗口标题 / Header 标题 / 副标题三处，中文和英文各两处——共 6 处 V1.5 硬编码 |
| 自适应窗口 | `_auto_size_window`: `winfo_reqwidth/height()` 取内容自然尺寸，clamp 到 `[minsize, 屏幕85%]`，居中。只在首次构建后调用一次 |
| 语言切换按钮 | Frame + 两个 Label 模拟橙色按钮，当前语言白字、另一语言深棕字，点击切换后 `_refresh_texts()` 全量刷新 |

**系统设置窗口**（`_build_settings_window`）：

独立 `Toplevel`，同样走 `_auto_size_window`，包含：
- 快捷键设置（4 个可点击捕获按钮）
- 录制精度说明
- 恢复默认快捷键 / 关闭 按钮

### 4.11 `mkr/app.py`

**作用**：程序装配——把上面所有模块串成一个可运行的应用。

**`Controller` 类**（业务协调者）：

```
Controller.__init__()
  ├── Config()              # 载入 config.json
  ├── Recorder()            # 录制引擎
  ├── Player()              # 回放引擎
  ├── HotkeyManager()       # 快捷键解析
  ├── InputHook()           # 钩子线程（回调 → Controller._on_mouse / _on_key）
  └── ui_queue: Queue       # 钩子线程 → UI 线程的消息通道
```

**钩子回调 → Controller 的分发逻辑**：

```python
def _on_key(self, kind, data):
    if self._capture is not None:        # 快捷键捕获模式
        self._handle_capture(vk, action)
        return
    # 正常路径
    for name in self.hotkeys.on_key(vk, action):  # 匹配全局快捷键
        self.ui_queue.put(("action", name))
    self.recorder.add_key(..., tick, perf)  # 录制（双时钟）
```

**UI 线程消息轮询**（`gui.py::_poll`）：

```python
while True:
    msg = ui_queue.get_nowait()
    handle(msg)  # ("captured", name, combo) → 刷新按钮文字
                 # ("action", name) → Controller.dispatch()
                 # ("hook_error", msg) → messagebox.showerror()
                 # ("pass", i, n) → 更新"第 i/n 次"
                 # ("play_finished", aborted) → 更新"回放完成/停止"
```

**`main()` 入口函数**：

```python
def main():
    enable_dpi_awareness()
    if not is_admin() and relaunch_as_admin(): return  # 非管理员 → runas 重启自身
    Controller()  # 装配所有模块，启动钩子
    MainWindow().run()  # 进入 tkinter mainloop
```

### 4.12 `run.bat`

```batch
@echo off
chcp 936 >nul                       # GBK 编码避免中文乱码
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)"') do set PY=%%i
for %%P in ("%PY%") do set PY_DIR=%%~dpP

if exist "%PY_DIR%pythonw.exe" (
    start "" "%PY_DIR%pythonw.exe" -m mkr   # 分离控制台，pythonw.exe 不创建黑窗口
) else (
    start "" "%PY%" -m mkr
)
```

关键点：`pythonw.exe` 分离启动 + 路径通过 `sys.executable` 动态解析（避免微软商店别名 `WindowsApps\pythonw.exe` 占位劫持）。

### 4.13 `config.json`

程序运行时自动读写，首次启动时用 `config.py::DEFAULTS` 创建。修改快捷键、倍速、重复次数后立即写回。

```json
{
  "hotkey_start_record": "alt+shift+f9",
  "hotkey_stop_record": "alt+shift+f10",
  "hotkey_start_play": "alt+shift+f11",
  "hotkey_stop_play": "alt+shift+f12",
  "repeat_count": 5,
  "interval_seconds": 0.5,
  "speed": 3.0,
  "last_recording": "C:/.../recordings/录制_20261112.json"
}
```

---

## CHANGELOG

> 格式：`### V版本号 (日期) \n - 改动内容（按影响模块分组）`
> 每次改动后追加一条，不可删除历史记录。

### V1.6.0 (2026-11-13)

**打包与发布**：
- 新增 `PyInstaller` 打包支持：`--onefile --windowed --uac-admin` 一键生成单文件 EXE
- 新增 Python + tkinter 安装器 `installer.py`，支持：自定义安装目录、桌面快捷方式勾选、开始菜单快捷方式勾选
- 最终产物：`ClaraRecorder.exe`（便携版，双击即用，自动 UAC 提权）+ `ClaraSetup.exe`（安装向导）

**PyInstaller 适配**：
- `relaunch_as_admin`：frozen 环境下不加 `-m mkr` 参数（EXE 自身就是入口）
- `app.py::main`：frozen 环境下 `relaunch_as_admin` 传 `workdir=None`
- `config.py` + `storage.py`：用户数据目录智能选择——EXE 同目录可写则存 EXE 旁（便携模式），不可写则存 `%APPDATA%/ClaraRecorder`（安装模式）

### V1.5.0 (2026-11-12)

**架构改动**：
- 全局低级输入钩子线程 + 消息循环（WH_KEYBOARD_LL / WH_MOUSE_LL），注入事件自动过滤
- 录制引擎改用 **双时钟融合**：`tick`（Windows 毫秒戳抗回调延迟）+ `perf`（回调入口微秒戳提供亚毫秒分辨率）
- 回放引擎三阶段精确等待：`precise_sleep_until` 安全 sleep + 自旋，唤醒误差 avg ~323ns（原 Windows sleep 抖动 ~523µs）
- 回放期间禁用 GC + 线程提权 TIME_CRITICAL，消除随机停顿源
- 成批发送窗口跟随 speed 同比例缩放，保证修饰键顺序语义在各倍速下一致
- `InjectedState` 精准释放：只释放本实例已注入 down 但未 up 的键，不 blanket 释放
- 修饰键 `key_input` 同时填写 `vkCode` 和 `scanCode`（不能只填 scanCode 而 vk=0）

**GUI 新增**：
- 主界面背景图：assets/background.jpg，cover 模式（等比缩放 + 居中裁剪不变形），Canvas + content 同 geometry manager 解决图层遮挡
- 中 / 英界面切换：右上角橙色按钮，I18N 字典 ~70 个 key，`_refresh_texts()` 全量刷新
- 窗口自适应：`_auto_size_window` 按内容自然尺寸 + 屏幕 85% clamp + 居中
- 系统设置窗口同走自适应 + 可拉伸

**配置与存储**：
- `config.json` 四快捷键 + 重复次数 + 间隔 + 倍速，损坏回退 DEFAULTS
- 录制文件 JSON + 元数据（屏幕 / DPI / 刷新率 / 显示器数），新旧格式兼容

### V1.0.0 (2026-11-11)

- 首个稳定版本：微秒级录制 + 高精度 SendInput 回放 + 全局快捷键 + 管理员自动提权
