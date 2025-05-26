"""
设置系统环境
创建必要的目录和文件
"""

import os
import sys

def setup_directories():
    """创建系统所需的目录结构"""
    # 获取当前文件(setup.py)的目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 获取controller目录
    controller_dir = os.path.dirname(current_dir)
    
    # 创建instance目录
    instance_dir = os.path.join(controller_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # 创建检测结果目录
    detection_results_dir = os.path.join(instance_dir, 'detection_results')
    os.makedirs(detection_results_dir, exist_ok=True)
    
    # 创建视频上传存储目录
    videos_dir = os.path.join(instance_dir, 'videos')
    os.makedirs(videos_dir, exist_ok=True)
    
    # 创建静态结果目录
    static_results_dir = os.path.join(controller_dir, 'static', 'results')
    os.makedirs(static_results_dir, exist_ok=True)
    
    print(f"目录结构创建完成:")
    print(f"- 实例目录: {instance_dir}")
    print(f"- 检测结果目录: {detection_results_dir}")
    print(f"- 视频存储目录: {videos_dir}")
    print(f"- 静态结果目录: {static_results_dir}")

if __name__ == "__main__":
    setup_directories() 