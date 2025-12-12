# -*- coding: utf-8 -*-
import os
import sys

# ==========================================
# 📍 路径防走丢补丁
# ==========================================
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# ==========================================

import time
import pandas as pd
import requests
import threading
import tkinter as tk
import winsound
from datetime import datetime

# ==========================================
# 🛡️ 网络配置
# ==========================================
PROXY_PORT = "7890"
proxies = {
    "http": f"http://127.0.0.1:{PROXY_PORT}",
    "https": f"http://127.0.0.1:{PROXY_PORT}",
}
# ==========================================

# --- ⚡ 核心参数 ---
REFRESH_INTERVAL = 3
TRIGGER_PCT = 0.5
COOLDOWN_SECONDS = 1800
SKIP_ALREADY_HIGH = 1.0
STOP_SIGNAL_FILE = "STOP_RADAR_SIGNAL"  # 🛑 停止信号文件名


class StockRadarLite:
    def __init__(self):
        self.watch_list = {}
        self.sina_codes = []
        self.load_watch_list()

    def load_watch_list(self):
        try:
            files = [f for f in os.listdir('.') if f.startswith('N_Rebound_Result') and f.endswith('.csv')]
            if not files: return

            files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            target_file = files[0]

            df = pd.read_csv(target_file)
            df['代码'] = df['代码'].astype(str).str.zfill(6)

            count = 0
            for _, row in df.iterrows():
                code = row['代码']
                if row['回调幅度%'] > SKIP_ALREADY_HIGH: continue

                self.watch_list[code] = {
                    'name': row['名称'],
                    'last_alert': 0
                }

                prefix = 'sh' if code.startswith('6') else 'sz'
                self.sina_codes.append(f"{prefix}{code}")
                count += 1

        except Exception:
            pass

    def fetch_sina_batch(self):
        chunk_size = 80
        all_data = {}

        for i in range(0, len(self.sina_codes), chunk_size):
            chunk = self.sina_codes[i:i + chunk_size]
            query_str = ",".join(chunk)
            url = f"http://hq.sinajs.cn/list={query_str}"

            try:
                headers = {'Referer': 'https://finance.sina.com.cn'}
                resp = requests.get(url, headers=headers, proxies=proxies, timeout=5)
                text = resp.text

                lines = text.strip().split('\n')
                for line in lines:
                    if '="' not in line: continue
                    code_part = line.split('=')[0]
                    sina_code = code_part.split('_')[-1]
                    pure_code = sina_code[2:]
                    data_part = line.split('="')[1].strip('";')
                    if not data_part: continue
                    fields = data_part.split(',')
                    if len(fields) < 4: continue

                    name = fields[0]
                    prev_close = float(fields[2])
                    current_price = float(fields[3])
                    if prev_close == 0: continue
                    pct = (current_price - prev_close) / prev_close * 100

                    all_data[pure_code] = {
                        'price': current_price, 'pct': round(pct, 2), 'name': name
                    }
            except Exception:
                pass
        return all_data

    def show_batch_alert(self, alert_list):
        def popup():
            top = tk.Tk()
            title_text = f"🔥 N字异动 ({len(alert_list)}只)"
            top.title(title_text)
            top.configure(bg='#ffcccc')
            top.attributes("-topmost", True)

            rows = len(alert_list)
            height = 100 + (rows * 30)
            if height > 600: height = 600

            w = top.winfo_screenwidth()
            h = top.winfo_screenheight()
            top.geometry(f"400x{height}+{(w - 400) // 2}+{(h - height) // 2}")

            tk.Label(top, text="⚠ 发现目标启动", font=("微软雅黑", 16, "bold"), bg='#ffcccc', fg='red').pack(pady=10)
            frame = tk.Frame(top, bg='white')
            frame.pack(fill='both', expand=True, padx=10, pady=5)
            tk.Label(frame, text="代码      名称        涨幅", font=("Consolas", 10, "bold"), bg='white').pack(
                anchor='w')
            tk.Label(frame, text="----------------------------------", bg='white').pack(anchor='w')

            for item in alert_list:
                line = f"{item['code']}   {item['name']}   +{item['pct']}%"
                tk.Label(frame, text=line, font=("Consolas", 12, "bold"), bg='white', fg='red').pack(anchor='w')

            tk.Button(top, text="朕已阅 (关闭)", command=top.destroy, font=("微软雅黑", 10), height=2).pack(pady=10,
                                                                                                            fill='x')
            for _ in range(3): winsound.Beep(1000, 100)
            top.mainloop()

        t = threading.Thread(target=popup)
        t.start()

    def show_shutdown_alert(self):
        """退出时的提示弹窗"""

        def popup():
            top = tk.Tk()
            top.title("N字猎手")
            top.geometry("300x150")
            top.attributes("-topmost", True)
            w = top.winfo_screenwidth()
            h = top.winfo_screenheight()
            top.geometry(f"+{(w - 300) // 2}+{(h - 150) // 2}")
            tk.Label(top, text="🛑 雷达监控已停止", font=("微软雅黑", 14, "bold"), fg="red").pack(pady=40)
            # 2秒后自动关闭提示窗
            top.after(2000, top.destroy)
            top.mainloop()

        t = threading.Thread(target=popup)
        t.start()

    def start_monitoring(self):
        if not self.sina_codes: return

        # 启动时先清理可能存在的旧停止信号
        if os.path.exists(STOP_SIGNAL_FILE):
            try:
                os.remove(STOP_SIGNAL_FILE)
            except:
                pass

        while True:
            try:
                # --- 🛑 核心：检查自杀信号 ---
                if os.path.exists(STOP_SIGNAL_FILE):
                    print("收到停止信号，正在退出...")
                    # 删除信号文件
                    try:
                        os.remove(STOP_SIGNAL_FILE)
                    except:
                        pass

                    # 提示用户
                    winsound.Beep(500, 500)  # 低沉的声音提示退出
                    self.show_shutdown_alert()
                    sys.exit(0)  # 退出程序
                # ---------------------------

                data_map = self.fetch_sina_batch()
                current_batch_triggers = []
                now = time.time()

                for code, info in data_map.items():
                    if code not in self.watch_list: continue
                    current_pct = info['pct']

                    if current_pct > TRIGGER_PCT:
                        last_time = self.watch_list[code]['last_alert']
                        if now - last_time > COOLDOWN_SECONDS:
                            current_batch_triggers.append({
                                'code': code, 'name': info['name'], 'price': info['price'], 'pct': current_pct
                            })
                            self.watch_list[code]['last_alert'] = now

                if current_batch_triggers:
                    current_batch_triggers.sort(key=lambda x: x['pct'], reverse=True)
                    self.show_batch_alert(current_batch_triggers)

                time.sleep(REFRESH_INTERVAL)

            except SystemExit:
                break  # 响应 sys.exit
            except Exception:
                time.sleep(3)


if __name__ == "__main__":
    radar = StockRadarLite()
    radar.start_monitoring()