# -*- coding: utf-8 -*-
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
import time
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import akshare as ak

# ==========================================
# 🛡️ 网络配置
# ==========================================
# 如果需要强制走代理，请取消注释并确认端口
# PROXY_PORT = "7890"
# os.environ["http_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"
# os.environ["https_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"
# ==========================================

# --- ⚙️ 策略参数 ---
MAX_WORKERS = 4
N_DAYS = 7  # 只看最近7天
VOL_SHRINK_RATIO = 1.2  # 缩量
UPPER_SHADOW_LIMIT = 0.06  # 上影线
MAX_POSITION_PCT = 0.6

# 文件名
TODAY = datetime.now().strftime("%Y%m%d")
RESULT_FILE = f"N_Rebound_Result_{TODAY}.csv"


def clean_old_files(days=3):
    """清理旧文件"""
    print(f"[系统自检] 正在清理 {days} 天前的旧数据...")
    now = time.time()
    cutoff = days * 86400

    deleted_count = 0
    try:
        for f in os.listdir('.'):
            if f.startswith("N_Rebound_Result") and f.endswith(".csv"):
                file_path = os.path.join('.', f)
                file_mtime = os.path.getmtime(file_path)

                if now - file_mtime > cutoff:
                    try:
                        os.remove(file_path)
                        print(f"   [-] 已删除过期文件: {f}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"   [!] 删除失败 {f}: {e}")
    except Exception:
        pass

    if deleted_count == 0:
        print("   [OK] 暂无过期文件需要清理。")
    else:
        print(f"   [OK] 清理完毕，共释放 {deleted_count} 个文件。")


def get_stock_list_simple():
    """获取股票列表"""
    print("[1/3] 正在拉取股票名单...")
    try:
        df = ak.stock_info_a_code_name()
        df = df[~df['name'].str.contains("ST")]
        df = df[~df['name'].str.contains("退")]

        def add_prefix(code):
            if code.startswith('6'):
                return f"sh{code}"
            else:
                return f"sz{code}"

        df['sina_code'] = df['code'].apply(add_prefix)
        return df
    except Exception as e:
        print(f"[Error] 名单获取失败: {e}")
        return pd.DataFrame()


def save_result_batch(results):
    """批量保存"""
    if not results: return
    df = pd.DataFrame(results)
    df = df.sort_values(by="回调幅度%", ascending=False)
    df.to_csv(RESULT_FILE, index=False, encoding='utf_8_sig')
    print(f"[保存] 结果已更新: {RESULT_FILE}")


def check_stock_sina(row):
    sina_code = row['sina_code']
    name = row['name']
    pure_code = row['code']

    try:
        # 1. 拉取更长的数据 (60天，为了看位置)
        # 新浪接口本身就是全量的，所以这里不用改请求，只改数据截取
        df = ak.stock_zh_a_daily(symbol=sina_code, adjust="qfq")

        if df is None or df.empty or len(df) < 60: return None  # 上市不满60天的不看

        # 列名标准化
        df.rename(columns={
            'date': '日期', 'open': '开盘', 'close': '收盘',
            'high': '最高', 'low': '最低', 'volume': '成交量'
        }, inplace=True)

        # 2. --- 🆕 核心新增：位置计算 ---
        # 取最近60天数据
        df_60 = df.tail(60)
        high_60 = df_60['最高'].max()
        low_60 = df_60['最低'].min()
        current_price = df_60.iloc[-1]['收盘']

        # 计算水位 (0.0 ~ 1.0)
        if high_60 == low_60:
            position = 0
        else:
            position = (current_price - low_60) / (high_60 - low_60)

        # 🚫 恐高过滤：如果水位超过 50%，直接 Pass
        if position > MAX_POSITION_PCT:
            return None
            # --------------------------------

        # 3. 后续逻辑保持不变 (补全涨跌幅，找N字)
        df['昨收'] = df['收盘'].shift(1)
        df['涨跌幅'] = (df['收盘'] - df['昨收']) / df['昨收'] * 100
        df['涨跌幅'] = df['涨跌幅'].fillna(0)

        # 只在最近 N_DAYS (比如7天) 里找涨停
        recent_df = df.tail(N_DAYS + 1)
        zt_days = recent_df[recent_df['涨跌幅'] > 9.5]
        if zt_days.empty: return None

        last_row = df.iloc[-1]

        for idx, zt_row in zt_days.iloc[::-1].iterrows():
            zt_date = zt_row['日期']
            zt_price = zt_row['开盘']

            if zt_date == last_row['日期']: continue

            # 检查涨停后的日子
            after_zt = df[df['日期'] > zt_date]
            if after_zt.empty: continue

            # 结构不破位
            if any(after_zt['收盘'] < zt_price): continue

            # 严格上影线
            upper_shadow = (last_row['最高'] - last_row['收盘']) / last_row['收盘']
            if upper_shadow > UPPER_SHADOW_LIMIT: continue

            # 严格缩量
            if last_row['成交量'] > zt_row['成交量'] * VOL_SHRINK_RATIO: continue

            pullback = (last_row['收盘'] - zt_row['收盘']) / zt_row['收盘'] * 100

            return {
                "代码": pure_code,
                "名称": name,
                "最新日期": str(last_row['日期']),
                "现价": last_row['收盘'],
                "区间位置": f"{int(position * 100)}%",  # 把位置也写进Excel给他看
                "涨停日期": str(zt_row['日期']),
                "回调幅度%": round(pullback, 2)
            }

        return None

    except Exception:
        return None


def main():
    print(f"[{datetime.now()}] N-Rebound (Sina严选版) 启动...")

    clean_old_files(days=3)

    all_stocks = get_stock_list_simple()
    if all_stocks.empty: return

    total = len(all_stocks)
    print(f"[2/3] 开始扫描 {total} 只股票 (并发{MAX_WORKERS})...")

    results = []

    count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_stock_sina, row): row for _, row in all_stocks.iterrows()}

        for future in as_completed(futures):
            count += 1
            if count % 50 == 0:
                print(f"\r   进度: {count}/{total} | 命中: {len(results)} ", end="")

            res = future.result()
            if res:
                results.append(res)
                # 将 emoji 换成普通的 [+] 号
                print(f"\n   [+] 严选命中: {res['名称']} ({res['代码']}) 跌幅: {res['回调幅度%']}%")
                if len(results) % 5 == 0:
                    save_result_batch(results)

    if results:
        save_result_batch(results)
        print(f"\n\n[完成] 扫描完成！共选出 {len(results)} 只精品。")
        print(f"[文件] 结果文件: {os.path.abspath(RESULT_FILE)}")
    else:
        print("\n\n[完成] 扫描完成，严苛条件下无标的入选。")


if __name__ == "__main__":
    main()
