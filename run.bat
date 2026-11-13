@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0"

rem 解析真实 Python 解释器，避开 PATH 中的微软商店占位程序
set "PYEXE="
for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
if not defined PYEXE (
    echo [错误] 未检测到 Python。请先安装 Python 3.11 或更高版本，并加入 PATH。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

set "PYW=%PYEXE:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PYEXE%"

echo 正在启动 鼠标键盘活动记录重复器 ...
rem 分离启动：程序以无控制台方式运行，本窗口随即自动关闭
start "" "%PYW%" -m mkr
exit /b 0
