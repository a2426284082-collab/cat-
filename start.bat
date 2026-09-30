@echo off
setlocal

:: ==================================================
:: LogicLens 架构师专用启动脚本 (非管理员免装版)
:: ==================================================

:: 1. 尝试直接调用 pythonw (无窗口模式)
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
start "" pythonw logiclens_main.py
exit
)

:: 2. 如果上面失败，尝试寻找常见的用户目录路径 (Python 3.10 默认路径)
set "PY_PATH=%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
if exist "%PY_PATH%" (
start "" "%PY_PATH%" logiclens_main.py
exit
)

:: 3. 如果还是找不到，提示用户
echo [错误] 找不到 Python 3.10 环境。
echo 请确保已安装 Python，或者尝试在命令行运行: python logiclens_main.py
pause