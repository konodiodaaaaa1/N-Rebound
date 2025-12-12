@echo off
chcp 65001 >nul
title N-Rebound 智能启动器
color 0A
cd /d "%~dp0"

:: =========================================================
:: 🔴 必填：请确认这是老电脑上 Python 的真实路径
:: =========================================================
set "MY_PYTHON=D:\AI\conda\envs\stock_env\python.exe"

if not exist "%MY_PYTHON%" (
    echo ❌ 错误：找不到 Python解释器，请编辑脚本修正路径！
    pause
    exit
)

echo =======================================================
echo        🦅 N-Rebound 懒人启动系统 (Python版)
echo =======================================================
echo.

:: 直接调用 launcher.py，逻辑判断全部交给 Python
"%MY_PYTHON%" launcher.py

pause