import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import os
import akshare as ak

# ==========================================
# 📍 路径补丁
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- ⚙️ 配置 ---
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
LOOKBACK_WINDOW = 30
FEATURE_SIZE = 5
MODEL_PATH = "n_rebound_model.pth"
DATA_DIR = "training_data"  # 顺手存数据的地方

if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)


# ==========================================
# 🧠 模型架构 (必须与训练一致)
# ==========================================
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super(PositionalEncoding, self).__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (
                -10.46 / d_model))  # math.log(10000.0) approx 9.21, adjusting slightly or using numpy/math
        import math
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer('pe', pe)

    def forward(self, x): return x + self.pe[:x.size(0), :]


class NReboundTransformer(nn.Module):
    def __init__(self, input_size=5, d_model=64, nhead=4, num_layers=2, dropout=0.2):
        super(NReboundTransformer, self).__init__()
        self.embedding = nn.Linear(input_size, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layers = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dropout=dropout)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=num_layers)
        self.decoder = nn.Sequential(
            nn.Linear(d_model * LOOKBACK_WINDOW, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 1),
            nn.Sigmoid()
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
# 🔮 推理类
# ==========================================
class AIFilter:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self):
        if not os.path.exists(MODEL_PATH):
            return
        try:
            self.model = NReboundTransformer()
            self.model.load_state_dict(
                torch.load(MODEL_PATH, map_location=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
                           weights_only=True))
            self.model.to(DEVICE)
            self.model.eval()
        except Exception:
            pass

    def predict(self, code):
        """
        输入: 股票代码 (如 600519)
        输出: (分数0-100, 建议文本, 详细数据DataFrame)
        """
        if self.model is None: return 0, "模型未加载", None

        try:
            # 1. 构造代码
            sina_symbol = f"sh{code}" if code.startswith('6') else f"sz{code}"

            # 2. 实时拉取 (预测必须用最新的)
            df = ak.stock_zh_a_daily(symbol=sina_symbol, adjust="qfq")

            if df is None or df.empty or len(df) < LOOKBACK_WINDOW:
                return 0, "数据不足(上市时间太短)", None

            # 3. 顺手存一份到本地缓存 (积累数据)
            # csv_path = os.path.join(DATA_DIR, f"{code}.csv")
            # df.to_csv(csv_path, index=False, encoding='utf_8_sig')

            # 4. 预处理
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values(by='date').reset_index(drop=True)

            # 取最后 30 天
            slice_df = df.tail(LOOKBACK_WINDOW)

            # 归一化 (与训练一致)
            vals = slice_df[['open', 'high', 'low', 'close', 'volume']].values.astype(np.float32)
            base_price = vals[0, 0]
            if base_price == 0: base_price = 1e-6
            price_feats = vals[:, 0:4] / base_price - 1

            base_vol = np.mean(vals[:, 4])
            if base_vol == 0: base_vol = 1e-6
            vol_feat = vals[:, 4:5] / base_vol - 1

            features = np.hstack([price_feats, vol_feat])

            # 5. 推理
            tensor_x = torch.tensor(features).unsqueeze(0)
            tensor_x = tensor_x.to(DEVICE)
            with torch.no_grad():
                prob = self.model(tensor_x).item()

            score = round(prob * 100, 1)

            # 话术生成
            if score > 70:
                advice = "🔥 极佳 (强力推荐)"
            elif score > 60:
                advice = "✅ 良好 (可以考虑)"
            elif score > 50:
                advice = "🤔 一般 (胜率五五开)"
            else:
                advice = "❌ 较差 (建议观望)"

            return score, advice, slice_df

        except Exception as e:
            return 0, f"分析出错: {str(e)}", None


if __name__ == "__main__":
    ai = AIFilter()
    s, m, _ = ai.predict("600519")
    print(f"Test: {s} - {m}")
