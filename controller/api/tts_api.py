"""
Text-to-Speech API
"""
import base64
import io
import os
import time
from flask import Blueprint, request, jsonify
import pyttsx3  # 使用离线语音引擎

# Define the Blueprint with a URL prefix
tts_api_bp = Blueprint('tts_api', __name__, url_prefix='/api') # Changed from network_bp

@tts_api_bp.route('/text_to_speech', methods=['POST']) # Route remains the same relative to blueprint
def text_to_speech():
    """文字转语音API，在控制端完成语音合成
    返回base64编码的音频数据
    """
    try:
        data = request.json
        text = data.get('text', '')
        rate = data.get('rate', 1.0)  # 语速参数
        
        if not text:
            return jsonify({'code': 1, 'message': '文本内容不能为空'})
        
        # 临时WAV文件路径
        temp_dir = "temp_audio"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, f"speech_{int(time.time())}.wav")
        
        # 使用pyttsx3进行离线语音合成
        engine = pyttsx3.init()
        
        # 设置语速 (pyttsx3的语速范围是0-400，默认是200)
        # 转换rate (0.8-1.2) 到 pyttsx3的范围
        engine_rate = int(rate * 200)
        engine.setProperty('rate', engine_rate)
        
        # 设置中文女声（如果可用）
        voices = engine.getProperty('voices')
        for voice in voices:
            if "chinese" in voice.name.lower() or "zhong" in voice.name.lower() or ("chinese" in voice.languages[0].lower() if voice.languages else False):
                engine.setProperty('voice', voice.id)
                break
        
        # 生成语音文件
        engine.save_to_file(text, temp_file)
        engine.runAndWait()
        
        # 读取文件并转为base64
        with open(temp_file, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode('utf-8')
        
        # 清理临时文件
        try:
            os.remove(temp_file)
        except:
            pass
            
        return jsonify({
            'code': 0,
            'message': '语音合成成功',
            'audioData': audio_data
        })
    except Exception as e:
        print(f"语音合成失败: {str(e)}")
        return jsonify({'code': 1, 'message': f'语音合成失败: {str(e)}'})
