# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
import joblib
import akshare as ak
import warnings

# 忽略 xgboost 版本警告
warnings.filterwarnings("ignore")

# ==========================================
# 📍 路径防走丢
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- ⚙️ 配置 ---
MODEL_PATH = "n_rebound_xgb.model"
LOOKBACK_WINDOW = 30


class AIFilter:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self):
        if not os.path.exists(MODEL_PATH):
            print(f"❌ 模型文件未找到: {MODEL_PATH}")
            return
        try:
            print(f"🚀 正在加载 XGBoost 模型: {MODEL_PATH}")
            self.model = joblib.load(MODEL_PATH)
            print("✅ 模型加载成功！(树模型推理速度极快)")
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")

    def predict(self, code):
        """
        输入: 股票代码
        输出: (分数0-100, 建议文本, 详细数据DataFrame)
        """
        if self.model is None: return 0, "模型未加载", None

        try:
            # 1. 构造代码
            sina_symbol = f"sh{code}" if code.startswith('6') else f"sz{code}"

            # 2. 实时拉取 (AKShare)
            # 注意：盘中实时数据可能不够30天，所以最好拉取日线历史
            df = ak.stock_zh_a_daily(symbol=sina_symbol, adjust="qfq")

            if df is None or df.empty or len(df) < LOOKBACK_WINDOW + 5:
                return 0, "数据不足", None

            # 3. 数据清洗
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values(by='date').reset_index(drop=True)

            # 取最后 30 天
            slice_df = df.tail(LOOKBACK_WINDOW).copy()

            # --- 🔥 核心：实时特征工程 (必须与训练时完全一致！) ---
            vals = slice_df[['close', 'volume']].values
            close_prices = vals[:, 0]
            vols = vals[:, 1]

            # 1. 涨幅特征
            # 注意防止除以0
            p_change_5 = (close_prices[-1] - close_prices[-5]) / (close_prices[-5] + 1e-6)
            p_change_10 = (close_prices[-1] - close_prices[-10]) / (close_prices[-10] + 1e-6)
            p_change_30 = (close_prices[-1] - close_prices[0]) / (close_prices[0] + 1e-6)

            # 2. 波动率
            volatility = np.std(close_prices[-5:]) / (np.mean(close_prices[-5:]) + 1e-6)

            # 3. 量比
            vol_ratio_5 = vols[-1] / (np.mean(vols[-5:]) + 1e-6)

            # 4. 均线偏离度
            ma5 = np.mean(close_prices[-5:])
            ma20 = np.mean(close_prices[-20:])
            dist_ma5 = (close_prices[-1] / (ma5 + 1e-6)) - 1
            dist_ma20 = (close_prices[-1] / (ma20 + 1e-6)) - 1

            # 构造特征向量 (顺序必须和训练时一样!)
            # ['5日涨幅', '10日涨幅', '30日涨幅', '波动率', '量比', '偏离MA5', '偏离MA20']
            feature = np.array([[
                p_change_5, p_change_10, p_change_30,
                volatility, vol_ratio_5,
                dist_ma5, dist_ma20
            ]])

            # 4. 推理
            # predict_proba 返回 [[负概率, 正概率]]
            probs = self.model.predict_proba(feature)
            win_prob = probs[0][1]  # 取正样本(Label 1)的概率

            score = round(win_prob * 100, 1)

            # 话术生成
            if score > 60:
                advice = "🔥 极佳 (强力推荐)"
            elif score > 50:
                advice = "✅ 良好 (胜率过半)"
            elif score > 45:
                advice = "🤔 一般 (勉强)"
            else:
                advice = "❌ 较差 (不仅N字不行，趋势也不行)"

            return score, advice, slice_df

        except Exception as e:
            # print(f"分析出错: {e}") # 调试时可打开
            return 0, f"分析出错", None


if __name__ == "__main__":
    ai = AIFilter()
    if ai.model:
        print("正在测试 600519 (贵州茅台)...")
        s, m, _ = ai.predict("600519")
        print(f"得分: {s} | 评价: {m}")