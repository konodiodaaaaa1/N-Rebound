import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
import os
import math
import time
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 📍 性能配置区 (针对 RTX 4070 优化)
# ==========================================
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BATCH_SIZE = 2048  # 🚀 激进优化
EPOCHS = 100
LEARNING_RATE = 0.001
LOOKBACK_WINDOW = 30
FEATURE_SIZE = 5

DATA_INDEX = "n_rebound_dataset.csv"
RAW_DATA_DIR = "training_data"
MODEL_SAVE_PATH = "n_rebound_model.pth"


# ==========================================
# 🛠️ 1. 极速数据集 (带内存缓存) - 保持不变
# ==========================================
class CachedStockDataset(Dataset):
    def __init__(self, index_df, root_dir):
        self.index_df = index_df
        self.root_dir = root_dir
        self.cache = {}  # 🧠 内存缓存

        print(f"🔥 正在预加载数据到内存 (共 {len(index_df)} 个样本)...")
        self._preload_data()

    def _preload_data(self):
        unique_codes = self.index_df['code'].unique()

        def load_one_stock(code):
            code_str = str(code).zfill(6)
            # 兼容多种文件名格式
            possible_names = [f"{code_str}.csv", f"sh{code_str}.csv", f"sz{code_str}.csv"]
            csv_path = None
            for name in possible_names:
                p = os.path.join(self.root_dir, name)
                if os.path.exists(p):
                    csv_path = p
                    break

            if not csv_path: return code, None

            try:
                df = pd.read_csv(csv_path)
                col_map = {'date': '日期', 'open': '开盘', 'close': '收盘', 'high': '最高', 'low': '最低',
                           'volume': '成交量'}
                df.rename(columns=col_map, inplace=True)
                df['日期'] = pd.to_datetime(df['日期'])
                return code, df
            except:
                return code, None

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = executor.map(load_one_stock, unique_codes)

        for code, df in results:
            if df is not None:
                self.cache[code] = df

        print(f"✅ 预加载完成！缓存了 {len(self.cache)} 只股票的数据。")

    def __len__(self):
        return len(self.index_df)

    def __getitem__(self, idx):
        row = self.index_df.iloc[idx]
        code = row['code']
        buy_date = row['buy_date']
        label = int(row['label'])

        if code not in self.cache:
            return torch.zeros((LOOKBACK_WINDOW, FEATURE_SIZE)), torch.tensor(0.0)

        df = self.cache[code]

        try:
            target_mask = (df['日期'] == pd.to_datetime(buy_date))
            if not target_mask.any(): raise ValueError("Date not found")

            buy_idx = np.where(target_mask)[0][0]
            start_idx = buy_idx - LOOKBACK_WINDOW + 1
            if start_idx < 0: raise ValueError("Not enough history")

            slice_df = df.iloc[start_idx: buy_idx + 1]
            if len(slice_df) != LOOKBACK_WINDOW: raise ValueError("Length mismatch")

            vals = slice_df[['开盘', '最高', '最低', '收盘', '成交量']].values.astype(np.float32)
            base_price = vals[0, 0] if vals[0, 0] != 0 else 1e-6
            price_feats = vals[:, 0:4] / base_price - 1

            base_vol = np.mean(vals[:, 4])
            if base_vol == 0: base_vol = 1e-6
            vol_feat = vals[:, 4:5] / base_vol - 1

            features = np.hstack([price_feats, vol_feat])

            return torch.tensor(features), torch.tensor(label, dtype=torch.float32)

        except Exception:
            return torch.zeros((LOOKBACK_WINDOW, FEATURE_SIZE)), torch.tensor(0.0)


# ==========================================
# 🧠 2. 模型定义 (移除 Sigmoid)
# ==========================================
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super(PositionalEncoding, self).__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        import math
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer('pe', pe)

    def forward(self, x):
        return x + self.pe[:x.size(0), :]


class NReboundTransformer(nn.Module):
    def __init__(self, input_size=5, d_model=64, nhead=4, num_layers=2, dropout=0.2):
        super(NReboundTransformer, self).__init__()
        self.embedding = nn.Linear(input_size, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        # batch_first=False 是默认值，保持现状即可
        encoder_layers = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dropout=dropout)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=num_layers)
        self.decoder = nn.Sequential(
            nn.Linear(d_model * LOOKBACK_WINDOW, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 1),
            # 🔥 修改：移除了最后的 Sigmoid！
            # 因为我们要配合 BCEWithLogitsLoss 使用，它内部自带了 Sigmoid，数值更稳定
        )

    def forward(self, src):
        src = src.permute(1, 0, 2)
        src = self.embedding(src)
        src = self.pos_encoder(src)
        output = self.transformer_encoder(src)
        output = output.permute(1, 0, 2)
        output = output.reshape(output.size(0), -1)
        prob = self.decoder(output)
        return prob.squeeze()


# ==========================================
# 🎮 3. 训练主流程 (核心改进版)
# ==========================================
def main():
    torch.set_float32_matmul_precision('medium')
    print(f"🚀 启动训练引擎 (Pro版) | 显卡: {torch.cuda.get_device_name(0)}")

    if not os.path.exists(DATA_INDEX):
        print(f"❌ 找不到 {DATA_INDEX}")
        return

    df = pd.read_csv(DATA_INDEX)

    # ⚖️ 计算正样本权重
    pos_count = len(df[df['label'] == 1])
    neg_count = len(df[df['label'] == 0])
    pos_weight_val = neg_count / (pos_count + 1e-6)
    print(f"📊 样本分布: 正 {pos_count} / 负 {neg_count} | ⚖️ 建议权重: {pos_weight_val:.2f}")

    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['label'])

    train_dataset = CachedStockDataset(train_df, RAW_DATA_DIR)
    val_dataset = CachedStockDataset(val_df, RAW_DATA_DIR)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0,
                              persistent_workers=False)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0, persistent_workers=False)

    model = NReboundTransformer().to(DEVICE)

    # 🔥 核心改进1：使用 BCEWithLogitsLoss 并加权
    pos_weight_tensor = torch.tensor([pos_weight_val]).to(DEVICE)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)

    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # 🔥 核心改进2：学习率调度器 (如果10个epoch指标不动，学习率减半)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=5, verbose=True)

    best_precision = 0.0
    patience_counter = 0  # 早停计数器
    start_time = time.time()

    print(f"\n{'Epoch':<6} | {'Loss':<8} | {'Precision':<10} | {'Recall':<8} | {'LR':<8} | {'状态'}")
    print("-" * 65)

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0

        for X, y in train_loader:
            # 强制转 float，防止报错
            X, y = X.to(DEVICE), y.to(DEVICE).float()

            optimizer.zero_grad()
            output = model(X)
            loss = criterion(output, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)

        # 验证
        model.eval()
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for X, y in val_loader:
                X, y = X.to(DEVICE), y.to(DEVICE).float()
                output = model(X)
                # 因为去掉了Sigmoid，这里要手动加Sigmoid再判断 > 0.5
                # 或者直接判断 logits > 0 (效果一样)
                predicted = (torch.sigmoid(output) > 0.5).float()

                all_preds.extend(predicted.cpu().numpy())
                all_targets.extend(y.cpu().numpy())

        # 计算指标
        precision = precision_score(all_targets, all_preds, zero_division=0)
        recall = recall_score(all_targets, all_preds, zero_division=0)
        current_lr = optimizer.param_groups[0]['lr']

        # 评价状态
        status = ""
        if precision > 0.55:
            status = "🔥 优秀"
        elif precision > 0.50:
            status = "✅ 赚钱"
        elif precision > 0.45:
            status = "🔄 震荡"
        else:
            status = "❌ 亏损"

        print(
            f"{epoch + 1:<6} | {avg_loss:<8.4f} | {precision * 100:<9.1f}% | {recall * 100:<7.1f}% | {current_lr:<8.5f} | {status}")

        # 调度器步进 (根据 Precision 调整学习率)
        scheduler.step(precision)

        # 🔥 核心改进3：只按 Precision 保存模型
        if precision > best_precision and precision > 0.5:  # 只有胜率>50%才有保存价值
            best_precision = precision
            torch.save(model.state_dict(), MODEL_SAVE_PATH)
            patience_counter = 0  # 重置早停
            status += " [💾 Saved]"
        else:
            patience_counter += 1

        # 早停
        if patience_counter >= 15:
            print(f"\n🛑 早停触发！连续 15 个 Epoch 性能未提升。")
            break

    total_time = (time.time() - start_time) / 60
    print(f"\n🏁 训练结束！总耗时: {total_time:.1f} 分钟")
    print(f"🏆 最佳查准率 (Precision): {best_precision * 100:.2f}%")
    if best_precision > 0.5:
        print("✅ 模型可用！快去替换 paper_bot 里的模型文件吧！")
    else:
        print("⚠️ 模型效果一般，可能需要更多数据或调整特征。")


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()