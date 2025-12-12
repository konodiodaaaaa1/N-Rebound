@echo off
chcp 65001 >nul
title N-Rebound 财务审计报告
color 0B
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
echo        📜 正在生成 N-Rebound 财务审计报告...
echo =======================================================
echo.

:: 直接运行 paper_review.py，显示结果
"%MY_PYTHON%" paper_review.py

:: 因为 paper_review.py 内部有一个 input("按回车键退出...")
:: 所以这里不需要再加 pause 命令。

:: 注意：paper_review.py 会在内部等待用户按回车键后自动关闭。