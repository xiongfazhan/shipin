from flask import Flask, render_template
from utils.service import network_bp, get_local_ip
from utils.data_processing import data_processing_bp
from utils.detection_api import detection_api_bp
from utils.video_processing_api import video_processing_bp
from utils.database_admin import database_admin_bp
from utils import database
import os

# 在main.py中确保有如下配置
# 设置 instance_path 为 controller/instance 目录
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
app = Flask(__name__, static_folder='static', instance_path=instance_path)

# 初始化数据库 (必须在注册蓝图之前或之后，但在运行 app 之前完成)
database.init_app(app)

# 注册蓝图
app.register_blueprint(network_bp)
app.register_blueprint(data_processing_bp)
app.register_blueprint(detection_api_bp)
app.register_blueprint(video_processing_bp)
app.register_blueprint(database_admin_bp)

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
    port = 6920
    print(f"服务启动于 http://{host}:{port}")
    # open_browser(app)
    app.run(host='0.0.0.0', port=port, debug=True)
