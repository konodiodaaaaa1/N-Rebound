# -*- coding: utf-8 -*-
import os
import sys
import subprocess
from datetime import datetime, timedelta
import time

# ==========================================
# 📍 配置：文件新鲜度阈值 (根据你的要求调整)
# ==========================================
# 设定阈值为 20 小时。
# 逻辑：如果选股结果文件超过 20 小时没更新，就重新跑一遍。
# （这能覆盖你下午开机和电脑跑过夜的需求）
FRESHNESS_HOURS = 20

# ==========================================
# 📍 路径防走丢 (不变)
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def find_newest_result_file():
    """查找最新生成的选股结果文件路径及其修改时间"""
    newest_file_path = None
    latest_mtime = 0

    try:
        files = [f for f in os.listdir('.') if f.startswith('N_Rebound_Result') and f.endswith('.csv')]

        for f in files:
            f_path = os.path.join(os.getcwd(), f)
            mtime = os.path.getmtime(f_path)

            if mtime > latest_mtime:
                latest_mtime = mtime
                newest_file_path = f_path

    except Exception as e:
        print(f"❌ 查找文件时出错: {e}")
        return None, None

    return newest_file_path, latest_mtime


def main():
    print("========================================")
    print("        🦅 N-Rebound 智能启动器")
    print("========================================")

    # 1. 查找最新文件
    newest_path, latest_timestamp = find_newest_result_file()

    needs_rerun = False

    if newest_path is None:
        print("❌ 未找到任何选股文件，必须重新运行选股。")
        needs_rerun = True
    else:
        # 2. 检查文件新鲜度
        file_mtime = datetime.fromtimestamp(latest_timestamp)
        stale_threshold = datetime.now() - timedelta(hours=FRESHNESS_HOURS)

        print(f"✅ 最新文件: {os.path.basename(newest_path)}")
        print(f"🕒 创建时间: {file_mtime.strftime('%Y-%m-%d %H:%M:%S')}")

        if file_mtime < stale_threshold:
            print(f"⚠️ 文件已过期 (超过 {FRESHNESS_HOURS} 小时)，需要更新！")
            needs_rerun = True
        else:
            print("🚀 文件新鲜度足够，跳过选股。")

    # 3. 执行操作
    if needs_rerun:
        print("\n[执行] 正在启动 night_screener.py 补跑选股...")
        print("-" * 40)
        # sys.executable 是当前 Conda 环境的 Python 解释器路径
        subprocess.run([sys.executable, "night_screener.py"])
        print("-" * 40)

    # 4. 启动机器人
    print("\n🚀 正在启动全自动交易机器人 (paper_bot)...")
    # sys.executable 是当前 Conda 环境的 Python 解释器路径
    subprocess.run([sys.executable, "paper_bot.py"])


if __name__ == "__main__":
    main()