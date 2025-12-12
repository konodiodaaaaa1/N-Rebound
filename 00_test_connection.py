import akshare as ak
import pandas as pd
import os
from datetime import datetime

# --- 配置区 ---
TEST_SYMBOL = "600519"  # 贵州茅台，用来测试的大白马
TODAY = datetime.now().strftime("%Y%m%d")


def check_connection():
    print(f"[{datetime.now()}] 🚀 开始系统自检...")
    print(f"[{datetime.now()}] 正在尝试连接 AkShare 数据源...")

    try:
        # 1. 尝试获取单只股票的历史数据 (测试网络和API)
        # start_date和end_date设为近期，减少数据量
        df = ak.stock_zh_a_hist(symbol=TEST_SYMBOL, period="daily", start_date="20230101", adjust="qfq")

        if df is None or df.empty:
            print("❌ 数据获取失败：返回为空。请检查网络。")
            return

        print(f"✅ 成功获取 {TEST_SYMBOL} 数据！共 {len(df)} 行。")
        print("   数据预览 (最后3行):")
        print(df.tail(3))

        # 2. 尝试写入文件 (测试硬盘权限)
        file_name = f"test_data_{TODAY}.xlsx"
        df.to_excel(file_name, index=False)

        if os.path.exists(file_name):
            print(f"✅ 文件写入成功！已保存为: {file_name}")
            print(f"🎉 环境搭建完成！随时可以开始编写核心策略。")

            # 清理测试文件 (可选)
            # os.remove(file_name)
        else:
            print("❌ 文件写入失败，请检查文件夹权限。")

    except Exception as e:
        print(f"❌ 发生错误: {e}")
        print("💡 常见原因: 网络不通、VPN干扰、或AkShare接口更新导致。")


if __name__ == "__main__":
    check_connection()