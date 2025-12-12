@echo off
chcp 65001 >nul
title N-Rebound 指挥中心 (正在寻找 Conda...)
color 0A
cd /d "%~dp0"

echo =======================================================
echo        🦅 N-Rebound 智能选股系统
echo =======================================================
echo.

:: =========================================================
:: 🔍 核心逻辑：自动寻找 activate.bat
:: 这段代码模拟了“打开 Miniconda Prompt”的过程
:: =========================================================

set "CONDA_PATH="

:: 1. 检查当前用户目录 (默认安装位置)
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    set "CONDA_PATH=%USERPROFILE%\miniconda3"
)

:: 2. 检查 ProgramData (所有用户安装位置)
if exist "C:\ProgramData\miniconda3\Scripts\activate.bat" (
    set "CONDA_PATH=C:\ProgramData\miniconda3"
)

:: 3. 检查 D 盘常见位置 (防止装在 D 盘)
if exist "D:\miniconda3\Scripts\activate.bat" (
    set "CONDA_PATH=D:\miniconda3"
)
if exist "D:\AI\conda\Scripts\activate.bat" (
    set "CONDA_PATH=D:\AI\conda"
)

:: --- 如果上面都没找到，就在这里手动指定你的路径 ---
:: 如果你的路径很特殊，请把下面这行前面的 :: 去掉，并填入你的路径
:: set "CONDA_PATH=D:\你的\安装\路径\miniconda3"


:: =========================================================
:: 🚀 激活流程
:: =========================================================

if defined CONDA_PATH (
    echo [1/3] 发现 Conda 路径: "%CONDA_PATH%"
    echo [2/3] 正在初始化环境...
    
    :: 关键一招：调用官方激活脚本，让当前 CMD 获得 Conda 能力
    call "%CONDA_PATH%\Scripts\activate.bat"
    
    :: 激活虚拟环境
    call conda activate stock_env
    
) else (
    echo.
    echo ❌ 未自动找到 Miniconda 安装位置！
    echo.
    echo 请右键编辑此 bat 文件，在第 35 行手动填入你的 Miniconda 路径。
    pause
    exit /b
)

echo [3/3] 正在启动 WebUI...
echo.

:: 运行程序
python -m streamlit run web_monitor.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ 运行出错。
    pause
)