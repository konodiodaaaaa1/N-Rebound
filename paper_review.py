# -*- coding: utf-8 -*-
import pandas as pd
import os
import sys

# ==========================================
# 📍 路径防走丢
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 配置
DATA_DIR = "paper_trading_data"
HISTORY_FILE = os.path.join(DATA_DIR, "trade_history.csv")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.csv")

# 💰 初始本金 (用于计算总收益率)
INIT_CAPITAL = 100000


def analyze():
    os.system('cls' if os.name == 'nt' else 'clear')  # 清屏
    print("=========================================")
    print("       📊 N-Rebound 基金净值日报")
    print("=========================================")
    print(f"💰 初始本金: {INIT_CAPITAL:,.2f} 元")

    if not os.path.exists(HISTORY_FILE):
        print("\n❌ 暂无交易记录，等待开张...")
        return

    # 读取数据
    df_hist = pd.read_csv(HISTORY_FILE)
    df_pos = pd.read_csv(PORTFOLIO_FILE) if os.path.exists(PORTFOLIO_FILE) else pd.DataFrame()

    # ------------------------------------------------
    # 1. 历史战绩统计
    # ------------------------------------------------
    sell_records = df_hist[df_hist['action'] == 'SELL']
    total_trades = len(sell_records)

    realized_profit = 0.0
    wins = 0
    losses = 0

    if total_trades > 0:
        for info in sell_records['info']:
            try:
                # 解析 "止盈... 盈亏:1200.5"
                p = float(info.split(':')[-1])
                realized_profit += p
                if p > 0:
                    wins += 1
                else:
                    losses += 1
            except:
                pass

        win_rate = (wins / total_trades) * 100
    else:
        win_rate = 0.0

    # ------------------------------------------------
    # 2. 当前持仓分析
    # ------------------------------------------------
    holding_cost = 0.0
    holding_count = 0
    if not df_pos.empty:
        holding_cost = df_pos['cost'].sum()
        holding_count = len(df_pos)

    # ------------------------------------------------
    # 3. 核心指标输出
    # ------------------------------------------------
    print(f"\n🏆 历史胜率: {win_rate:.2f}%  ({wins}胜 / {losses}负)")
    print(f"💸 已落袋盈亏: {realized_profit:+.2f} 元")

    # 总资产 (近似值，持仓按成本价算)
    total_asset = INIT_CAPITAL + realized_profit
    roi = (total_asset - INIT_CAPITAL) / INIT_CAPITAL * 100

    print(f"📈 账户总收益率: {roi:+.2f}%")
    print("-" * 40)

    # ------------------------------------------------
    # 4. 仓位监控
    # ------------------------------------------------
    cash_left = total_asset - holding_cost
    position_pct = (holding_cost / total_asset) * 100

    print(f"📦 当前持仓: {holding_count} 只股票")
    print(f"❄️ 占用资金: {holding_cost:,.2f} 元 (仓位 {position_pct:.1f}%)")
    print(f"💵 可用现金: {cash_left:,.2f} 元")

    if not df_pos.empty:
        print("\n[持仓明细]")
        # 简单打印
        print(df_pos[['code', 'name', 'buy_date', 'buy_price', 'amount']].to_string(index=False))
    else:
        print("\n[持仓状态] 空仓观望中...")

    print("=========================================")


if __name__ == "__main__":
    analyze()
    input("\n按回车键退出...")