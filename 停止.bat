@echo off
title N-Rebound 紧急刹车系统
color 4F
cd /d "%~dp0"

echo =======================================================
echo        🛑 N-Rebound 紧急停止程序 (Kill Switch)
echo =======================================================
echo.
echo 正在扫描后台残留的“僵尸进程”...
echo.

:: 1. 强制杀死后台运行的 pythonw.exe (这是雷达的主要宿主)
taskkill /F /IM pythonw.exe /T 2>nul
if %errorlevel% equ 0 (
    echo [✅] 成功处决后台雷达进程 (pythonw.exe)
) else (
    echo [info] 未发现后台雷达进程。
)

:: 2. 强制杀死前台运行的 python.exe (这是WebUI或选股器)
taskkill /F /IM python.exe /T 2>nul
if %errorlevel% equ 0 (
    echo [✅] 成功关闭指挥中心/选股器 (python.exe)
) else (
    echo [info] 未发现前台Python进程。
)

echo.
echo =======================================================
echo ✅ 世界清静了。
echo 所有 N-Rebound 相关程序已强制停止。
echo =======================================================
pause