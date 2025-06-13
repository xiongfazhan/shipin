#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mock Client Webhook – 接收 Analytics-Service 主动推送
运行:
    pip install flask rich
    python mock_client.py
"""

import os, json, datetime
from flask import Flask, request, jsonify
from rich import print

APP_PORT   = 9000             # ← 如需更换端口改这里
ENDPOINT   = "/iot/receive"   # ← 如需更换路径改这里
LOG_FILE   = "received.log"   # 保存推送记录

app = Flask(__name__)

def _log(payload: dict):
    """把推送内容附带时间戳写入文件"""
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts}  {json.dumps(payload, ensure_ascii=False)}\n")

@app.route(ENDPOINT, methods=["POST"])
def receive():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid json"}), 400

    # 终端彩色打印
    print(f"[green]{ENDPOINT} 收到推送:[/]", data)
    _log(data)          # 写文件持久化

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    print(f"🚀 Mock-Client 正在监听 http://0.0.0.0:{APP_PORT}{ENDPOINT}")
    app.run(host="0.0.0.0", port=APP_PORT, threaded=True)