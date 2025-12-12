# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 📍 路径防走丢
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = "training_data"

# --- 🎯 杨永兴策略参数 ---
OPEN_MIN = 2.0  # 高开下限: +2% (主力表态)
OPEN_MAX = 6.0  # 高开上限: +6% (太高容易是一字板，买不进)
TARGET = 2.0  # 止盈: 赚2%
STOP = -2.0  # 止损: 亏2%


def analyze_stock(file_path):
    try:
        df = pd.read_csv(file_path)
        if len(df) < 20: return None

        # 1. 整理列名
        col_map = {'date': '日期', 'open': '开盘', 'close': '收盘', 'high': '最高', 'low': '最低', 'volume': '成交量'}
        df.rename(columns=col_map, inplace=True)

        # 2. 计算昨收
        df['昨收'] = df['收盘'].shift(1)
        df['开盘涨幅'] = (df['开盘'] - df['昨收']) / df['昨收'] * 100

        # 3. 筛选出“符合杨永兴条件”的日子
        # 条件：高开 2% ~ 6%
        target_days = df[(df['开盘涨幅'] >= OPEN_MIN) & (df['开盘涨幅'] <= OPEN_MAX)].copy()

        if target_days.empty: return None

        results = []

        for i in target_days.index:
            # 必须保证有第二天的数据 (T+1)
            if i + 1 >= len(df): continue

            # T日买入价 = 开盘价
            buy_price = df.loc[i, '开盘']

            # T+1日表现
            next_day = df.loc[i + 1]

            # 模拟极短线博弈：
            # 卖出逻辑：看T+1日的最高价和开盘价
            # 如果 T+1 哪怕冲高一下，我们也能跑

            max_profit = (next_day['最高'] - buy_price) / buy_price * 100
            min_profit = (next_day['最低'] - buy_price) / buy_price * 100
            open_profit = (next_day['开盘'] - buy_price) / buy_price * 100

            # 判定胜负
            # 宽松标准：只要T+1最高冲到了 2% 以上，就算赢 (假设你能挂单卖出)
            win = 1 if max_profit >= TARGET else 0

            # 真实收益 (假设按T+1开盘跑，或者收盘跑，这里取个折中：T+1收盘)
            # 严格一点：看T+1收盘
            real_profit = (next_day['收盘'] - buy_price) / buy_price * 100

            results.append({
                'win': win,
                'profit': real_profit
            })

        return results

    except:
        return None


def main():
    print(f"📊 正在回测 [杨永兴·早盘追击策略] ...")
    print(f"🎯 买入条件: 高开 {OPEN_MIN}% ~ {OPEN_MAX}%")
    print(f"💰 目标收益: +{TARGET}% (隔日超短)")

    files = [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if f.endswith(".csv")]

    all_trades = []

    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(analyze_stock, files):
            if res:
                all_trades.extend(res)

    if not all_trades:
        print("❌ 没有找到符合条件的数据。")
        return

    df_res = pd.DataFrame(all_trades)

    total_trades = len(df_res)
    win_trades = df_res['win'].sum()
    win_rate = win_trades / total_trades * 100
    avg_profit = df_res['profit'].mean()

    print("\n" + "=" * 40)
    print("       📉 大数据回测报告")
    print("=" * 40)
    print(f"🛒 总交易次数: {total_trades} 次")
    print(f"🏆 胜率 (T+1冲高>{TARGET}%): {win_rate:.2f}%")
    print(f"💰 平均单笔收益 (T+1收盘): {avg_profit:.2f}%")
    print("-" * 40)

    if win_rate > 55:
        print("✅ 结论：策略有效！高开确实伴随着溢价。")
    else:
        print("⚠️ 结论：胜率一般。说明单纯‘无脑买高开’是亏钱的，必须上 AI 过滤！")


if __name__ == "__main__":
    main()