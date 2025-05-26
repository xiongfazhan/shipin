"""
测试视频处理功能的入口脚本
创建一个测试视频并运行处理
"""

import os
import sys

# 添加当前目录到路径，以便导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 导入测试模块
from test_video_processing_utils import create_test_video, main as test_main # Updated path

if __name__ == "__main__":
    # 直接调用测试模块的main函数
    print("创建并处理测试视频...")
    print("注意：这会创建一个5秒的测试视频，并使用YOLO模型进行检测")
    print("过程可能需要几分钟，请耐心等待...\n")
    
    # 强制启用处理模式
    sys.argv.append('--process')
    
    # 运行测试
    exit_code = test_main()
    
    # 退出
    sys.exit(exit_code) 