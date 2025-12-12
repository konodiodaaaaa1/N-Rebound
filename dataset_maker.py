# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 📍 路径防走丢补丁
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- ⚙️ 配置 ---
RAW_DATA_DIR = "training_data"
OUTPUT_FILE = "n_rebound_dataset.csv"  # 结果文件

# 策略定义
LOOKBACK_WINDOW = 30  # 回看30天形态
FORWARD_WINDOW = 5  # 前瞻5天定胜负
TARGET_PROFIT = 5.0  # 5天内涨超5%算赢
STOP_LOSS = -5.0  # 5天内跌超5%算输


def process_single_stock(file_path):
    try:
        df = pd.read_csv(file_path)
        if len(df) < (LOOKBACK_WINDOW + FORWARD_WINDOW + 10):
            return []

        # --- 1. 列名标准化 (中英文适配) ---
        # 建立映射字典，把各种可能的列名统一映射到标准中文名
        col_map = {
            'date': '日期', 'Date': '日期',
            'open': '开盘', 'Open': '开盘',
            'close': '收盘', 'Close': '收盘',
            'high': '最高', 'High': '最高',
            'low': '最低', 'Low': '最低',
            'volume': '成交量', 'Volume': '成交量'
        }
        df.rename(columns=col_map, inplace=True)

        # 必须要有这几列
        required = ['日期', '开盘', '收盘', '最高', '最低']
        if not all(col in df.columns for col in required):
            # print(f"缺列: {file_path}")
            return []

        # --- 2. 核心修复：手动计算涨跌幅 ---
        # 你的数据里没有'涨跌幅'，我们需要现算
        if '涨跌幅' not in df.columns:
            df['昨收'] = df['收盘'].shift(1)
            df['涨跌幅'] = (df['收盘'] - df['昨收']) / df['昨收'] * 100
            df['涨跌幅'] = df['涨跌幅'].fillna(0)  # 第一天设为0

        # --- 3. 排序与准备 ---
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values(by='日期').reset_index(drop=True)

        samples = []

        # 找到所有涨停的日子 (>9.5%)
        # 排除首尾数据不足的
        limit_up_indices = df[df['涨跌幅'] > 9.5].index

        for idx in limit_up_indices:
            if idx < LOOKBACK_WINDOW or idx > len(df) - FORWARD_WINDOW - 5:
                continue

            # T日信息
            t_row = df.iloc[idx]
            zt_price = t_row['开盘']  # 涨停日开盘价作为防守线

            # --- 4. 筛选逻辑：N字结构 ---
            # 考察涨停后 2 天 (T+1, T+2)
            check_days = 2
            check_period = df.iloc[idx + 1: idx + 1 + check_days]
            if check_period.empty: continue

            # A. 结构不破位：收盘价都在涨停开盘价之上
            if any(check_period['收盘'] < zt_price):
                continue

            # B. (可选) 这里可以加更多逻辑，比如缩量等
            # 但为了训练数据够多，我们先只用"不破位"这个硬指标

            # --- 5. 标记样本 (Labeling) ---
            # 假设我们在 T+2 收盘买入 (或者 T+3 开盘)
            buy_idx = idx + check_days
            buy_price = df.iloc[buy_idx]['收盘']

            # 看未来 N 天的表现
            future_period = df.iloc[buy_idx + 1: buy_idx + 1 + FORWARD_WINDOW]
            if future_period.empty: continue

            label = 0  # 默认是输

            # 🔥 逐日模拟：看谁先触发
            for _, day_row in future_period.iterrows():
                # 计算当天的最低/最高涨幅
                day_low_pct = (day_row['最低'] - buy_price) / buy_price * 100
                day_high_pct = (day_row['最高'] - buy_price) / buy_price * 100

                # 💀 关卡1：先触发止损？
                # 如果盘中最低价击穿了止损线 (-5%)
                if day_low_pct <= STOP_LOSS:
                    label = 0  # 判死刑，哪怕后面涨了也不算
                    break  # 交易结束

                # 🏆 关卡2：触发止盈？
                # 如果没死，且最高价摸到了止盈线 (+5%)
                if day_high_pct >= TARGET_PROFIT:
                    label = 1  # 成功止盈
                    break  # 交易结束

            # 如果5天走完，既没止盈也没止损 (死鱼横盘)，算作 0 (浪费时间成本)

            samples.append({
                "code": os.path.basename(file_path).replace(".csv", ""),
                "buy_date": df.iloc[buy_idx]['日期'].strftime('%Y-%m-%d'),
                "label": label,
                # 这里的 profit 仅作参考，不影响训练
                "profit": TARGET_PROFIT if label == 1 else STOP_LOSS
            })

        return samples

    except Exception:
        return []


def main():
    print("🤖 正在构建 N-Rebound 专用数据集 (修复版)...")
    print(f"📂 扫描目录: {os.path.abspath(RAW_DATA_DIR)}")

    if not os.path.exists(RAW_DATA_DIR):
        print(f"❌ 错误: 找不到目录 {RAW_DATA_DIR}，请先运行采集脚本！")
        return

    all_files = [os.path.join(RAW_DATA_DIR, f) for f in os.listdir(RAW_DATA_DIR) if f.endswith(".csv")]
    total_files = len(all_files)
    print(f"📊 待扫描文件数: {total_files}")

    all_samples = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_single_stock, f): f for f in all_files}

        count = 0
        for future in as_completed(futures):
            count += 1
            res = future.result()
            if res:
                all_samples.extend(res)

            if count % 100 == 0:
                print(f"\r进度: {count}/{total_files} | 累计样本: {len(all_samples)}", end="")

    print(f"\n\n✅ 数据集构建完成！")

    if all_samples:
        df_samples = pd.DataFrame(all_samples)

        pos_count = len(df_samples[df_samples['label'] == 1])
        neg_count = len(df_samples[df_samples['label'] == 0])

        print(f"📈 正样本 (Label 1): {pos_count}")
        print(f"📉 负样本 (Label 0): {neg_count}")
        print(f"⚖️ 胜率分布: {pos_count / len(df_samples) * 100 :.2f}%")

        df_samples.to_csv(OUTPUT_FILE, index=False)
        print(f"💾 样本索引表: {os.path.abspath(OUTPUT_FILE)}")
    else:
        print("❌ 依然没有提取到样本。请检查：")
        print("1. training_data 文件夹里有 CSV 文件吗？")
        print("2. 随便打开一个 CSV，里面有数据吗？")


if __name__ == "__main__":
    main()