# -*- coding: utf-8 -*-
import requests
import os
import time

# ==========================================
# 🛡️ 你的网络配置 (必须保持和 WebUI 一致)
# ==========================================
PROXY_PORT = "7890"
proxies = {
    "http": f"http://127.0.0.1:{PROXY_PORT}",
    "https": f"http://127.0.0.1:{PROXY_PORT}"
}


def test_sina_connection():
    print("========================================")
    print("       📡 新浪接口连通性测试 (V2.0)")
    print("========================================")
    print(f"代理设置: {proxies}")

    test_codes = ["sh600519", "sz000001"]
    url = f"http://hq.sinajs.cn/list={','.join(test_codes)}"

    print(f"\n正在尝试连接: {url} ...")

    start_time = time.time()
    try:
        # 核心修复：添加完整的 Headers 伪装
        headers = {
            # 伪装成 Chrome 120 浏览器
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # 告诉新浪，我从你的财经页面点过来的
            "Referer": "https://finance.sina.com.cn",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }

        # 发送请求
        resp = requests.get(url, headers=headers, proxies=proxies, timeout=5)

        # 尝试设置编码，防止乱码
        resp.encoding = 'gbk'

        cost_time = time.time() - start_time

        print(f"✅ 连接成功! (耗时: {cost_time:.4f}秒)")
        print(f"状态码: {resp.status_code}")

        # 检查是否成功
        if "var hq_str_" in resp.text:
            print("\n🎉 数据解析测试: 通过！")
            print("结论: 伪装成功，流量已放行。")
            print("--- 返回数据预览 ---")
            print(resp.text.strip().split('\n')[0].split(',')[0] + '...')
            print("--------------------")

        else:
            # 状态码 403 已经被我们识别
            print("\n⚠️ 数据解析测试: 失败 (服务器拒绝)")
            print("请检查你的梯子节点，可能该IP已被新浪永久封禁。")
            print(f"返回内容: {resp.text.strip()[:30]}...")

    except Exception as e:
        print(f"\n❌ 连接失败!")
        print(f"错误信息: {e}")


if __name__ == "__main__":
    test_sina_connection()
    input("\n按回车键退出...")