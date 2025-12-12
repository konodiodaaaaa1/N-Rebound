# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
from datetime import datetime

# ==========================================
# 📍 路径防走丢补丁
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)
# ==========================================

# --- ⚙️ 配置 ---
TARGET_HOUR = 16  # 下午 16 点 (4点)
TARGET_MINUTE = 0  # 00 分
LOG_FILE = "scheduler.log"
STOP_SIGNAL_FILE = "STOP_SCHEDULER_SIGNAL"


def log(msg):
    """记录日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def run_task():
    """执行选股任务"""
    log("⏰ 时间已到，开始执行【自动选股】任务...")

    # 调用 night_screener.py
    # 强制使用 python.exe (有窗口模式下可以看到进度，但后台模式下我们需要捕获输出)
    cmd = [sys.executable, "night_screener.py"]

    try:
        # 使用 gbk 解码防止中文系统崩溃
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='gbk',
            errors='replace'
        )

        if result.returncode == 0:
            log("✅ 自动选股成功！Excel文件已生成。")
        else:
            log("❌ 自动选股失败！错误信息如下：")
            log(result.stderr)

    except Exception as e:
        log(f"❌ 启动脚本失败: {e}")


def main():
    log("🚀 N-Rebound 自动调度器已启动。")
    log(f"📅 设定时间: 每天 {TARGET_HOUR:02d}:{TARGET_MINUTE:02d} 执行选股。")

    last_run_date = None

    while True:
        # 1. 检查停止信号
        if os.path.exists(STOP_SIGNAL_FILE):
            log("🛑 收到停止信号，调度器退出。")
            try:
                os.remove(STOP_SIGNAL_FILE)
            except:
                pass
            sys.exit(0)

        # 2. 检查时间
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")

        # 如果还没到今天的任务时间，或者今天已经跑过了
        is_time = (now.hour == TARGET_HOUR and now.minute == TARGET_MINUTE)

        if is_time:
            if last_run_date != current_date:
                # 触发任务
                run_task()
                last_run_date = current_date
                # 任务跑完后，休眠61秒防止同一分钟内重复触发
                time.sleep(61)
            else:
                # 今天已经跑过了，跳过
                pass

        # 每30秒检查一次时间
        time.sleep(30)


if __name__ == "__main__":
    main()