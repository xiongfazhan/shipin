"""
网络服务功能模块
包含IP获取、浏览器自动打开等基础网络功能
"""
import socket
import webbrowser
import threading
import time
import base64
import io
import os
from flask import Blueprint, request, jsonify # Blueprint, request, jsonify might not be needed if no routes left
import pyttsx3  # pyttsx3 might not be needed if no tts functions left

# network_bp = Blueprint('network', __name__) # Removed, as it's moved to tts_api.py

def get_local_ip():
    """获取本机局域网IP地址
    返回：
        str: 成功返回IP字符串，失败返回127.0.0.1
    """
    try:
        # 使用UDP协议获取有效IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def open_browser(app):
    """自动打开浏览器线程
    参数：
        app: Flask应用实例
    """
    def _open():
        time.sleep(1.5)  # 等待服务启动
        url = f"http://{get_local_ip()}:5000"
        print(f"浏览器访问地址：{url}")
        webbrowser.open(url)
    # 使用守护线程避免影响主程序退出
    threading.Thread(target=_open, daemon=True).start()

# The /text_to_speech route and its Blueprint (network_bp) have been moved to controller/api/tts_api.py