@echo off
chcp 65001 >nul
title N-Rebound 环境初始化
color 0B
cd /d "%~dp0"

echo =======================================================
echo        正在初始化 N-Rebound 运行环境...
echo =======================================================
echo.

:: ---------------------------------------------------------
:: 自动寻找 Conda (与启动脚本相同的逻辑)
:: ---------------------------------------------------------
set "CONDA_PATH="
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" set "CONDA_PATH=%USERPROFILE%\miniconda3"
if exist "C:\ProgramData\miniconda3\Scripts\activate.bat" set "CONDA_PATH=C:\ProgramData\miniconda3"
if exist "D:\miniconda3\Scripts\activate.bat" set "CONDA_PATH=D:\miniconda3"

if not defined CONDA_PATH (
    echo ❌ 找不到 Miniconda！请确保安装在默认位置，或手动编辑此脚本指定路径。
    pause
    exit /b
)

echo [INFO] 使用 Conda 路径: %CONDA_PATH%
:: 激活基础环境
call "%CONDA_PATH%\Scripts\activate.bat"

:: ---------------------------------------------------------
:: 开始干活
:: ---------------------------------------------------------

echo [1/3] 正在创建虚拟环境: stock_env ...
call conda create -n stock_env python=3.10 -y

echo [2/3] 正在激活环境...
call conda activate stock_env

echo [3/3] 正在安装依赖库...
pip install akshare pandas streamlit plotly requests openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo =======================================================
echo ✅ 全部完成！
echo 请双击 "启动.bat" 开始使用。
echo =======================================================
pause