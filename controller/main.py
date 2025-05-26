from flask import Flask, render_template
from utils.service import get_local_ip # network_bp removed
# from utils.data_processing import data_processing_bp # This Blueprint is removed as per instructions
from controller.api.detection_api import detection_api_bp
from controller.api.video_processing_api import video_processing_bp
from controller.api.database_admin_api import database_admin_bp
from controller.api.tts_api import tts_api_bp # Added for TTS
from utils import database
import os
import logging
import controller.config as config

# 在main.py中确保有如下配置
# 设置 instance_path 为 controller/instance 目录
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.INSTANCE_FOLDER_NAME)
app = Flask(__name__, static_folder=config.STATIC_FOLDER, instance_path=instance_path)
app.config.from_object(config)

# Configure logging
logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 初始化数据库 (必须在注册蓝图之前或之后，但在运行 app 之前完成)
database.init_app(app)

# 注册蓝图
# app.register_blueprint(network_bp) # Removed
# app.register_blueprint(data_processing_bp) # Removed
app.register_blueprint(detection_api_bp) # Kept, source updated by import
app.register_blueprint(video_processing_bp) # Kept, source updated by import
app.register_blueprint(database_admin_bp) # Kept, source updated by import
app.register_blueprint(tts_api_bp) # Added for TTS

# 创建指向检测结果图像的静态路径映射
@app.route('/static/results/<filename>')
def detection_image(filename):
    return app.send_static_file(f'results/{filename}')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/database_admin')
def database_admin_page():
    return render_template('database_admin.html')

@app.route('/detection_results')
def detection_results_page():
    return render_template('detection_results.html')

if __name__ == '__main__':
    host = get_local_ip()
    app.logger.info(f"服务启动于 http://{host}:{config.PORT}")
    # open_browser(app)
    app.run(host='0.0.0.0', port=config.PORT, debug=config.DEBUG)
