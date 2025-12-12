# -*- coding: utf-8 -*-
import os
import sys
import time
import pandas as pd
import requests
from datetime import datetime
import random

# ==========================================
# 📍 路径防走丢补丁
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ==========================================
# 🛡️ 网络配置 (照搬 WebUI 的成功配置)
# ==========================================
PROXY_PORT = "7890"
os.environ["http_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"
os.environ["https_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"

# ==========================================
# ⚙️ 策略配置
# ==========================================
INIT_CASH = 100000
SINGLE_POS_CASH = 5000

TAKE_PROFIT = 0.08
STOP_LOSS = -0.05
MAX_HOLD_DAYS = 5

AI_COEFF = 1.1
BUY_THRESHOLD = 0.55

# 监控阈值
TRIGGER_PCT = 0.1
SKIP_HIGH_OPEN = 1.5

# 路径
DATA_DIR = "paper_trading_data"
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "trade_history.csv")

try:
    from ai_filter_xgboost import AIFilter

    ai_engine = AIFilter()
    HAS_AI = True
    print("✅ AI 参谋部已就位")
except ImportError:
    HAS_AI = False
    print("⚠️ 未找到 AI 模型")


# ==========================================
# 🏦 账户管理系统
# ==========================================
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        return pd.read_csv(PORTFOLIO_FILE)
    return pd.DataFrame(columns=["code", "name", "buy_date", "buy_price", "amount", "cost"])


def save_portfolio(df):
    df.to_csv(PORTFOLIO_FILE, index=False, encoding='utf_8_sig')


def log_trade(action, code, name, price, amount, info=""):
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "code": code,
        "name": name,
        "price": price,
        "amount": amount,
        "info": info
    }
    df = pd.DataFrame([record])
    header = not os.path.exists(HISTORY_FILE)
    df.to_csv(HISTORY_FILE, mode='a', header=header, index=False, encoding='utf_8_sig')
    print(f"📝 [记账] {action} {name} {amount}股 @ {price} | {info}")


def is_trading_time(now):
    """
    判断当前时间是否在 A 股交易时间 (排除周末、节假日和午休)
    """
    # 1. 排除周末
    if now.weekday() >= 5:  # 5是周六, 6是周日
        return False

    current_time_min = now.hour * 60 + now.minute

    # 上午交易时段 (9:30 - 11:30)
    morning_start = 9 * 60 + 30
    morning_end = 11 * 60 + 30

    # 下午交易时段 (13:00 - 15:00)
    afternoon_start = 13 * 60
    afternoon_end = 15 * 60

    is_morning = morning_start <= current_time_min < morning_end
    is_afternoon = afternoon_start <= current_time_min <= afternoon_end

    return is_morning or is_afternoon


# ==========================================
# 🕵️‍♂️ 交易员逻辑
# ==========================================
class PaperTrader:
    def __init__(self):
        self.watch_list = {}
        self.load_watchlist()

    def load_watchlist(self):
        try:
            files = [f for f in os.listdir('.') if f.startswith('N_Rebound_Result') and f.endswith('.csv')]
            if not files:
                print("❌ 没找到选股结果！")
                return

            files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            target_file = files[0]
            print(f"📂 读取选股名单: {target_file}")

            df = pd.read_csv(target_file)
            df['代码'] = df['代码'].astype(str).str.zfill(6)

            self.watch_list = {
                row['代码']: {'name': row['名称'], 'last_check': 0}
                for _, row in df.iterrows()
            }
            print(f"📊 监控列表已装载: {len(self.watch_list)} 只")

        except Exception as e:
            print(f"加载失败: {e}")

    def execute_buy(self, code, name, current_price, score):
        df_pos = load_portfolio()
        if not df_pos.empty and code in df_pos['code'].astype(str).values: return

        current_used_cash = df_pos['cost'].sum() if not df_pos.empty else 0
        if current_used_cash + SINGLE_POS_CASH > INIT_CASH:
            print(f"   ⚠️ 资金不足，放弃买入")
            return

        shares = int(SINGLE_POS_CASH / current_price / 100) * 100
        if shares == 0: shares = 100

        cost = shares * current_price

        new_pos = {
            "code": code,
            "name": name,
            "buy_date": datetime.now().strftime("%Y-%m-%d"),
            "buy_price": current_price,
            "amount": shares,
            "cost": cost
        }
        df_pos = pd.concat([df_pos, pd.DataFrame([new_pos])], ignore_index=True)
        save_portfolio(df_pos)
        log_trade("BUY", code, name, current_price, shares, f"AI评分:{score:.1f}")

    def execute_sell(self, row, current_price, reason):
        df_pos = load_portfolio()
        df_pos = df_pos[df_pos['code'].astype(str) != str(row['code'])]
        save_portfolio(df_pos)
        profit = (current_price - row['buy_price']) * row['amount']
        log_trade("SELL", row['code'], row['name'], current_price, row['amount'], f"{reason} 盈亏:{profit:.2f}")

    # =======================================================
    # 📡 核心修复：完全照搬 WebUI 的网络请求逻辑
    # =======================================================
    def get_realtime_data(self, codes):
        data = {}
        chunk_size = 80

        # 强制使用代理 (和 WebUI 保持一致)
        proxies = {
            "http": f"http://127.0.0.1:{PROXY_PORT}",
            "https": f"http://127.0.0.1:{PROXY_PORT}"
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://finance.sina.com.cn",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }

        sina_codes = []
        code_map = {}
        for c in codes:
            prefix = 'sh' if c.startswith('6') else 'sz'
            sc = f"{prefix}{c}"
            sina_codes.append(sc)
            code_map[sc] = c

        for i in range(0, len(sina_codes), chunk_size):
            chunk = sina_codes[i:i + chunk_size]
            url = f"http://hq.sinajs.cn/list={','.join(chunk)}"
            try:
                # 必须带上 proxies，否则你的环境连不上
                resp = requests.get(url, headers=headers, proxies=proxies, timeout=5)

                # 尝试自动处理编码 (防止乱码)
                resp.encoding = 'gbk'

                lines = resp.text.strip().split('\n')
                for line in lines:
                    if '="' not in line: continue
                    s_code = line.split('=')[0].split('_')[-1]
                    parts = line.split('="')[1].strip('";').split(',')
                    if len(parts) < 4: continue

                    pure_code = code_map.get(s_code)
                    pre_close = float(parts[2])
                    price = float(parts[3])
                    if pre_close == 0: continue
                    pct = (price - pre_close) / pre_close * 100

                    data[pure_code] = {'price': price, 'pct': pct, 'name': parts[0]}
            except Exception as e:
                # print(f"网络波动: {e}")
                pass
        return data

    def run(self):
        print("🤖 N-Rebound 全自动交易员已上岗...")
        print(f"🎯 黄金窗口: 涨幅 {TRIGGER_PCT}% ~ {SKIP_HIGH_OPEN}%")

        while True:
            try:
                now = datetime.now()
                if not is_trading_time(now):
                    sleep_duration = 300
                    current_time_min = now.hour * 60 + now.minute
                    if 9 * 60 + 25 <= current_time_min < 9 * 60 + 30:
                        sleep_duration = 1  # 临近开盘，切到 1 秒刷新的高精度模式
                    elif 12 * 60 + 55 <= current_time_min < 13 * 60:
                        sleep_duration = 1  # 临近午盘，切到 1 秒刷新的高精度模式
                    sys.stdout.write(f"\r[{now.strftime('%H:%M:%S')}] 😴 休市中，等待开盘...")
                    sys.stdout.flush()
                    time.sleep(sleep_duration)
                    continue

                df_pos = load_portfolio()
                holding_codes = df_pos['code'].astype(str).tolist() if not df_pos.empty else []
                watch_codes = list(self.watch_list.keys())

                all_codes = list(set(holding_codes + watch_codes))
                if not all_codes:
                    print("😴 暂无目标，休息...")
                    time.sleep(20)
                    continue

                # 拉行情
                market_data = self.get_realtime_data(all_codes)

                # 如果没拉到数据，跳过本次循环
                if not market_data:
                    sys.stdout.write(f"\r[{now.strftime('%H:%M:%S')}] 网络连接中... ")
                    sys.stdout.flush()
                    time.sleep(3)
                    continue

                # 3. 检查卖出
                for _, row in df_pos.iterrows():
                    code = str(row['code']).zfill(6)
                    #  T+1 检查
                    # 如果买入日期等于今天，强制锁仓，跳过后续判断
                    if row['buy_date'] == now.strftime("%Y-%m-%d"):
                        continue
                    if code not in market_data: continue
                    info = market_data[code]
                    curr_price = info['price']
                    buy_price = row['buy_price']
                    profit_pct = (curr_price - buy_price) / buy_price
                    buy_date = datetime.strptime(row['buy_date'], "%Y-%m-%d")
                    hold_days = (now - buy_date).days

                    sell_reason = None
                    if profit_pct >= TAKE_PROFIT:
                        sell_reason = f"止盈({profit_pct * 100:.1f}%)"
                    elif profit_pct <= STOP_LOSS:
                        sell_reason = f"止损({profit_pct * 100:.1f}%)"
                    elif hold_days >= MAX_HOLD_DAYS:
                        sell_reason = "时间到期"

                    if sell_reason:
                        self.execute_sell(row, curr_price, sell_reason)

                # 4. 检查买入
                for code, info in market_data.items():
                    if code in holding_codes: continue
                    if code not in self.watch_list: continue

                    current_pct = info['pct']

                    if TRIGGER_PCT <= current_pct <= SKIP_HIGH_OPEN:
                        last_check = self.watch_list[code]['last_check']
                        if time.time() - last_check > 1800:
                            print(f"\n🔍 发现猎物: {info['name']} (+{current_pct:.2f}%)")
                            score = 0
                            if HAS_AI:
                                score, _, _ = ai_engine.predict(code)
                                print(f"   🤖 AI 评分: {score}")
                            else:
                                score = 65

                            final_score = (score / 100.0) * AI_COEFF
                            if final_score >= BUY_THRESHOLD:
                                print("   ⚡ 执行买入！")
                                self.execute_buy(code, info['name'], info['price'], score)
                            else:
                                print(f"   ✋ 放弃")
                            self.watch_list[code]['last_check'] = time.time()

                sys.stdout.write(
                    f"\r[{now.strftime('%H:%M:%S')}] 监控中... 持仓:{len(holding_codes)} 监控:{len(watch_codes)} (数据正常)   ")
                sys.stdout.flush()
                time.sleep(3)

            except KeyboardInterrupt:
                print("\n🛑 停止运行。")
                break
            except Exception as e:
                print(f"\n❌ 错误: {e}")
                time.sleep(5)


if __name__ == "__main__":
    bot = PaperTrader()
    bot.run()
