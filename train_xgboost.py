# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, accuracy_score
import joblib

# ==========================================
# 📍 路径
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))

DATA_INDEX = "n_rebound_dataset.csv"
RAW_DATA_DIR = "training_data"
MODEL_SAVE_PATH = "n_rebound_xgb.model"


def load_data_fast(csv_path):
    """快速加载并构造特征"""
    if not os.path.exists(csv_path):
        print("❌ 找不到数据集索引文件")
        return None, None, None

    df_index = pd.read_csv(csv_path)
    print(f"📊 正在加载数据 (共 {len(df_index)} 条)...")

    X_data = []
    y_data = []

    # 缓存文件路径
    file_cache = {}
    if os.path.exists(RAW_DATA_DIR):
        for f in os.listdir(RAW_DATA_DIR):
            if f.endswith(".csv"):
                # 兼容不同命名前缀
                clean_code = f.replace(".csv", "").replace("sh", "").replace("sz", "")
                file_cache[clean_code] = os.path.join(RAW_DATA_DIR, f)

    valid_count = 0

    for _, row in df_index.iterrows():
        code = str(row['code']).zfill(6)
        buy_date = row['buy_date']
        label = int(row['label'])

        if code not in file_cache: continue

        try:
            df = pd.read_csv(file_cache[code])
            col_map = {'date': '日期', 'open': '开盘', 'close': '收盘', 'high': '最高', 'low': '最低',
                       'volume': '成交量'}
            df.rename(columns=col_map, inplace=True)
            df['日期'] = pd.to_datetime(df['日期'])

            mask = df['日期'] == pd.to_datetime(buy_date)
            if not mask.any(): continue
            idx = df.index[mask][0]

            if idx < 29: continue

            # 取30天数据
            slice_df = df.iloc[idx - 29: idx + 1].copy()
            vals = slice_df[['收盘', '成交量']].values

            # --- 特征工程 ---
            close_prices = vals[:, 0]
            vols = vals[:, 1]

            # 1. 涨幅特征
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

            feature = [p_change_5, p_change_10, p_change_30, volatility, vol_ratio_5, dist_ma5, dist_ma20]

            X_data.append(feature)
            y_data.append(label)
            valid_count += 1

            if valid_count % 2000 == 0:
                print(f"\r  已处理 {valid_count} 条...", end="")

        except:
            continue

    print(f"\n✅ 数据准备完毕! 有效样本: {len(X_data)}")
    feature_names = ['5日涨幅', '10日涨幅', '30日涨幅', '波动率', '量比', '偏离MA5', '偏离MA20']
    return np.array(X_data), np.array(y_data), feature_names


def main():
    print("🚀 启动 XGBoost 训练 (修复版)")

    X, y, feat_names = load_data_fast(DATA_INDEX)
    if X is None or len(X) == 0:
        print("❌ 数据加载失败或为空")
        return

    # 划分数据
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # 自动计算权重
    pos_count = np.sum(y == 1)
    neg_count = np.sum(y == 0)
    pos_ratio = neg_count / (pos_count + 1e-6)
    print(f"⚖️ 正负样本比例: 1:{neg_count / pos_count:.2f} | scale_pos_weight: {pos_ratio:.2f}")

    # --- 🔥 核心修复 ---
    model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=pos_ratio,
        eval_metric='logloss',
        early_stopping_rounds=50,  # 👈 移到这里了
        n_jobs=-1
    )

    print("\n🌲 开始种树 (Training)...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False
        # fit 函数里不需要 early_stopping_rounds 了
    )

    # 验证
    preds = model.predict(X_val)
    precision = precision_score(y_val, preds, zero_division=0)
    recall = recall_score(y_val, preds, zero_division=0)
    acc = accuracy_score(y_val, preds)

    print("\n" + "=" * 40)
    print("       🏆 最终战报 (XGBoost)")
    print("=" * 40)
    print(f"✅ 查准率 (Precision): {precision * 100:.2f}%")
    print(f"🎯 召回率 (Recall):    {recall * 100:.2f}%")
    print(f"📊 准确率 (Accuracy):  {acc * 100:.2f}%")

    # 特征重要性
    print("\n🔍 AI 最看重什么指标?")
    print("-" * 40)
    importance = model.feature_importances_
    indices = np.argsort(importance)[::-1]

    for f in range(X.shape[1]):
        print(f"{f + 1}. {feat_names[indices[f]]:<10} : {importance[indices[f]]:.4f}")
    print("-" * 40)

    # 保存
    if precision > 0.5:
        joblib.dump(model, MODEL_SAVE_PATH)
        print(f"💾 模型已保存: {MODEL_SAVE_PATH}")
    else:
        print("⚠️ 查准率不足 50%，模型效果不佳。")


if __name__ == "__main__":
    main()