import streamlit as st
import pandas as pd
import requests
import os
import subprocess
import sys
import time
import akshare as ak
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==========================================
# 📍 路径与网络
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))
PROXY_PORT = "7890"
os.environ["http_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"
os.environ["https_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"

st.set_page_config(page_title="N-Rebound 指挥中心", layout="wide", page_icon="🦅")

st.markdown("""
<style>
    .stButton>button {width: 100%; font-weight: bold; border-radius: 8px;}
    .metric-card {background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# 尝试导入 AI
try:
    from ai_filter_xgboost import AIFilter

    ai_engine = AIFilter()
    has_ai = True
except ImportError:
    has_ai = False


# ==========================================
# 🛠️ 后端功能
# ==========================================
def run_screener():
    cmd = [sys.executable, "night_screener.py"]
    with st.spinner("正在执行选股..."):
        try:
            subprocess.run(cmd, capture_output=True, text=True, encoding='gbk', errors='replace')
            st.success("选股完成")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"出错: {e}")


def run_radar():
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw): pythonw = sys.executable
    subprocess.Popen([pythonw, "day_radar.py"], creationflags=0x08000000)
    st.toast("雷达已启动", icon="🚀")


def stop_all():
    subprocess.run("taskkill /F /IM pythonw.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    st.toast("已停止后台进程", icon="🛑")


def load_result():
    files = [f for f in os.listdir('.') if f.startswith('N_Rebound_Result') and f.endswith('.csv')]
    if not files: return None
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return files[0]


# ==========================================
# 🖥️ 界面布局
# ==========================================

# --- 侧边栏: 功能区 ---
with st.sidebar:
    st.header("🎮 控制台")

    with st.expander("🤖 自动化", expanded=True):
        if st.button("▶ 开启自动"):
            python_dir = os.path.dirname(sys.executable)
            pythonw = os.path.join(python_dir, "pythonw.exe")
            if not os.path.exists(pythonw): pythonw = sys.executable
            subprocess.Popen([pythonw, "auto_runner.py"], creationflags=0x08000000)
            st.toast("自动调度已开启", icon="✅")
        if st.button("⏹ 关闭所有"): stop_all()

    st.markdown("---")
    if st.button("🚀 立即选股"): run_screener()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🛡️ 开启雷达"): run_radar()
    with col2:
        if st.button("🛑 停止雷达"): stop_all()

    # --- 🤖 AI 验股机 (新增) ---
    st.markdown("---")
    st.subheader("🧪 AI 验股机")
    if has_ai:
        ai_code = st.text_input("输入代码 (如 002131):", max_chars=6)
        if st.button("🔮 AI 打分"):
            if ai_code and len(ai_code) == 6:
                with st.spinner("AI 正在读取K线形态..."):
                    score, advice, _ = ai_engine.predict(ai_code)

                if score > 60:
                    st.balloons()
                    st.success(f"**得分: {score}**\n\n{advice}")
                else:
                    st.error(f"**得分: {score}**\n\n{advice}")
            else:
                st.warning("请输入6位代码")
    else:
        st.warning("未找到 AI 模型")

# --- 主界面 ---
st.title("🦅 N-Rebound 指挥中心")

csv_file = load_result()

if csv_file:
    df = pd.read_csv(csv_file)
    df['代码'] = df['代码'].astype(str).str.zfill(6)

    st.subheader(f"📊 观察池: {csv_file}")

    # 交互式表格
    st.dataframe(df, height=300, hide_index=True, use_container_width=True)

    st.divider()

    # 详情分析
    col_list, col_chart = st.columns([1, 3])

    with col_list:
        st.markdown("**点击查看详情:**")
        # 生成带代码的列表
        opts = [f"{r['名称']} ({r['代码']})" for _, r in df.iterrows()]
        sel = st.radio("列表", opts, label_visibility="collapsed")
        sel_code = sel.split(" (")[1][:-1]

    with col_chart:
        # 画图逻辑
        try:
            sina_sym = f"sh{sel_code}" if sel_code.startswith('6') else f"sz{sel_code}"
            k_df = ak.stock_zh_a_daily(symbol=sina_sym, adjust="qfq")
            if not k_df.empty:
                k_df['date'] = pd.to_datetime(k_df['date'])
                k_df = k_df[k_df['date'] > (datetime.now() - timedelta(days=60))]

                fig = go.Figure(data=[go.Candlestick(x=k_df['date'],
                                                     open=k_df['open'], high=k_df['high'],
                                                     low=k_df['low'], close=k_df['close'])])
                fig.update_layout(xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)

                # --- 在这里也加一个快捷 AI 按钮 ---
                if has_ai:
                    if st.button(f"🔮 让 AI 评价一下 {sel_code}", key="btn_main"):
                        with st.spinner("分析中..."):
                            score, advice, _ = ai_engine.predict(sel_code)
                            st.info(f"AI 评分: **{score}** | 建议: {advice}")

        except Exception:
            st.warning("暂无行情数据")

else:
    st.info("请点击左侧【立即选股】生成数据。")