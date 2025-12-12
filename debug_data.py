# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
import os

# ==========================================
# 🛡️ 混合网络策略
# 既然百度能通，我们保留梯子设置，试试新浪能不能扛得住
# 如果新浪也报错，你可以尝试把下面这两行注释掉再跑一次
# ==========================================
# 假设你的梯子端口是 7890 (Clash默认)
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"


def check_sina_source():
    # 新浪接口需要的代码格式带有前缀，比如 sz002131
    TEST_SYMBOL = "sz002131"
    TEST_NAME = "利欧股份"

    print(f"🔄 正在尝试切换至【新浪财经】接口获取 {TEST_NAME} ...")

    try:
        # 使用 ak.stock_zh_a_daily (新浪源)
        # 注意：这个接口比较老，可能不需要 start_date/end_date，它直接给全部历史
        df = ak.stock_zh_a_daily(symbol=TEST_SYMBOL, adjust="qfq")

        if df is None or df.empty:
            print("❌ 新浪接口返回空数据。")
            return

        print(f"✅ 新浪接口成功！获取到 {len(df)} 行数据。")

        # 看看最后几行
        print("\n📋 数据预览:")
        print(df.tail(5))

        # 这里的列名通常是英文的，我们需要确认一下
        print("\n🔑 列名列表:", df.columns.tolist())

        # 简单验证一下涨停数据
        # 新浪的数据通常没有直接的'涨跌幅'列，需要我们自己算，或者看看有没有
        # 常用列名映射: date, open, high, low, close, volume

        last_close = df.iloc[-1]['close']
        prev_close = df.iloc[-2]['close']

        change_pct = (last_close - prev_close) / prev_close * 100
        print(f"\n🧮 手动计算今日涨幅: {change_pct:.2f}%")

        if change_pct > 9.0:
            print("🎉 数据验证通过！确实捕捉到了涨停板。")
        else:
            print(f"⚠️ 数据看似正常，但涨幅计算结果 ({change_pct:.2f}%) 不像涨停，可能是日期没更新。")

    except Exception as e:
        print(f"❌ 新浪接口也失败了: {e}")


if __name__ == "__main__":
    check_sina_source()