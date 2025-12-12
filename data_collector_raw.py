# -*- coding: utf-8 -*-
import os
import time
import pandas as pd
import akshare as ak
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 📍 路径防走丢补丁
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ==========================================
# 🛡️ 网络配置 (新浪源通常也建议走代理以防封IP)
# ==========================================
PROXY_PORT = "7890"
os.environ["http_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"
os.environ["https_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"

# ==========================================
# ⚙️ 采集参数
# ==========================================
DATA_DIR = "training_data"
START_DATE = "2020-01-01"  # 👈 只要2020年以后的 (新浪返回格式是 YYYY-MM-DD)
MAX_WORKERS = 8  # 新浪接口快，可以开 8 线程
OVERWRITE = False  # False = 跳过已存在的 (断点续传)

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


def get_stock_list():
    """获取全市场名单"""
    print("[*] 正在获取全市场股票名单...")
    try:
        df = ak.stock_info_a_code_name()
        df = df[~df['name'].str.contains("退")]
        return df
    except Exception as e:
        print(f"[!] 名单获取失败: {e}")
        return pd.DataFrame()


def fetch_history_data_sina(row):
    pure_code = row['code']
    name = row['name']
    file_path = os.path.join(DATA_DIR, f"{pure_code}.csv")

    # --- 断点续传 ---
    if not OVERWRITE and os.path.exists(file_path):
        if os.path.getsize(file_path) > 100:
            return "SKIP"

    try:
        # 1. 构造新浪需要的代码格式 (sh60xxxx, sz00xxxx)
        if pure_code.startswith('6'):
            sina_symbol = f"sh{pure_code}"
        else:
            sina_symbol = f"sz{pure_code}"

        # 2. 调用新浪接口 (adjust="qfq" 前复权)
        # 注意：新浪接口通常忽略 start_date，直接返回全量历史
        df = ak.stock_zh_a_daily(symbol=sina_symbol, adjust="qfq")

        if df is None or df.empty:
            return False

        # 3. 数据清洗与裁剪
        # 新浪返回的列名通常是: date, open, high, low, close, volume, outstanding_share, turnover

        # 确保日期列是 datetime 格式
        df['date'] = pd.to_datetime(df['date'])

        # ✂️ 裁剪：只保留 START_DATE 之后的数据
        filter_date = pd.to_datetime(START_DATE)
        df = df[df['date'] >= filter_date]

        if df.empty:
            return False  # 也就是这只股票2020年以后没交易？(或者是新股刚上市数据没刷出来)

        # 4. 保存
        # 为了训练方便，我们保留英文列名，或者你可以改成中文，这里保持原样
        df.to_csv(file_path, index=False, encoding='utf_8_sig')
        return True

    except Exception:
        return False


def main():
    print(f"[{datetime.now()}] AI 训练数据采集器 (新浪版) 启动...")
    print(f"[-] 目标: 采集 {START_DATE} 至今的数据")
    print(f"[-] 存储目录: {os.path.abspath(DATA_DIR)}")

    stocks = get_stock_list()
    if stocks.empty: return

    # 测试阶段：你可以把下面这行取消注释，先跑 10 个看看通不通
    # stocks = stocks.head(10)

    target_stocks = stocks
    total = len(target_stocks)

    print(f"[*] 任务列表: {total} 只股票")
    print("[*] 正在全速采集 (新浪接口较快)...")

    success = 0
    skipped = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_history_data_sina, row): row['code'] for _, row in target_stocks.iterrows()}

        count = 0
        for future in as_completed(futures):
            count += 1
            res = future.result()

            if res == "SKIP":
                skipped += 1
            elif res:
                success += 1
            else:
                failed += 1

            if count % 20 == 0:
                print(f"\r进度: {count}/{total} | 成功: {success} | 跳过: {skipped} | 失败: {failed}", end="")

    print(f"\n\n[Done] 采集结束！")
    print(f"成功: {success} | 失败: {failed}")
    print(f"数据已保存在 {DATA_DIR} 文件夹")


if __name__ == "__main__":
    main()