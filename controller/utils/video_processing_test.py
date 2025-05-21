"""
测试视频处理功能
创建一个简单的测试视频并运行处理
"""

import os
import cv2
import numpy as np
import sys
import random
from datetime import datetime
from pathlib import Path
import argparse

# 添加当前目录到路径，以便导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

def create_test_video(output_file, duration=5, fps=30, width=640, height=480):
    """创建一个简单的测试视频
    
    Args:
        output_file: 输出文件路径
        duration: 视频时长(秒)
        fps: 帧率
        width: 宽度
        height: 高度
    
    Returns:
        str: 视频文件路径
    """
    print(f"开始创建测试视频: {output_file}")
    print(f"- 时长: {duration}秒")
    print(f"- 帧率: {fps} FPS")
    print(f"- 分辨率: {width}x{height}")
    
    # 创建输出目录
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # 设置视频写入器
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    video_writer = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
    
    # 生成随机对象位置和颜色
    objects = []
    for i in range(3):  # 创建3个模拟对象
        objects.append({
            'x': random.randint(50, width-100),
            'y': random.randint(50, height-100),
            'w': random.randint(30, 80),
            'h': random.randint(30, 80),
            'color': (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
            'speed_x': random.randint(-5, 5),
            'speed_y': random.randint(-5, 5)
        })
    
    # 生成帧
    total_frames = int(duration * fps)
    for frame_idx in range(total_frames):
        # 创建空白帧
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 添加灰色背景
        frame[:, :] = (50, 50, 50)
        
        # 添加帧计数器
        cv2.putText(
            frame, 
            f"Frame: {frame_idx}/{total_frames-1}", 
            (20, 30), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, 
            (255, 255, 255), 
            2
        )
        
        # 添加时间戳
        time_pos = frame_idx / fps
        cv2.putText(
            frame, 
            f"Time: {time_pos:.2f}s", 
            (20, 60), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, 
            (255, 255, 255), 
            2
        )
        
        # 每隔30帧添加随机背景元素
        if frame_idx % 30 == 0:
            for i in range(10):
                x = random.randint(0, width-1)
                y = random.randint(0, height-1)
                radius = random.randint(3, 10)
                color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
                cv2.circle(frame, (x, y), radius, color, -1)
        
        # 绘制移动对象（模拟人或车辆）
        for obj in objects:
            # 更新位置
            obj['x'] += obj['speed_x']
            obj['y'] += obj['speed_y']
            
            # 边界检查和碰撞反弹
            if obj['x'] < 0 or obj['x'] + obj['w'] >= width:
                obj['speed_x'] *= -1
                obj['x'] = max(0, min(width - obj['w'], obj['x']))
            
            if obj['y'] < 0 or obj['y'] + obj['h'] >= height:
                obj['speed_y'] *= -1
                obj['y'] = max(0, min(height - obj['h'], obj['y']))
            
            # 绘制矩形（模拟检测对象）
            cv2.rectangle(
                frame, 
                (int(obj['x']), int(obj['y'])), 
                (int(obj['x'] + obj['w']), int(obj['y'] + obj['h'])), 
                obj['color'], 
                -1
            )
            
            # 添加标签
            cv2.putText(
                frame, 
                f"Object {objects.index(obj)+1}", 
                (int(obj['x']), int(obj['y'] - 5)), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                (255, 255, 255), 
                1
            )
        
        # 写入帧
        video_writer.write(frame)
        
        # 显示进度
        if frame_idx % 30 == 0 or frame_idx == total_frames - 1:
            progress = (frame_idx + 1) / total_frames * 100
            print(f"生成进度: {progress:.1f}% ({frame_idx+1}/{total_frames})")
    
    # 释放资源
    video_writer.release()
    print(f"测试视频创建完成: {output_file}")
    
    return output_file

def parse_arguments():
    parser = argparse.ArgumentParser(description='创建测试视频并进行处理')
    parser.add_argument('--output', type=str, default='', help='输出视频文件路径(默认创建在临时目录)')
    parser.add_argument('--duration', type=int, default=5, help='视频时长(秒)')
    parser.add_argument('--fps', type=int, default=30, help='帧率')
    parser.add_argument('--width', type=int, default=640, help='视频宽度')
    parser.add_argument('--height', type=int, default=480, help='视频高度')
    parser.add_argument('--process', action='store_true', help='创建后自动处理视频')
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_arguments()
    
    # 设置默认输出文件
    if not args.output:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(parent_dir, 'instance', 'videos')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'test_video_{timestamp}.avi')
    else:
        output_file = args.output
    
    # 创建测试视频
    video_path = create_test_video(
        output_file, 
        duration=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height
    )
    
    # 如果需要，处理视频
    if args.process:
        print("\n开始处理测试视频...")
        # 导入处理模块
        sys.path.insert(0, parent_dir)
        from main import app
        from video_file_processing import process_video_file
        from copy_images import copy_detection_images
        
        # 设置视频ID
        video_id = f"TEST_VIDEO_{Path(video_path).stem}"
        
        # 在Flask应用上下文中处理视频
        with app.app_context():
            result = process_video_file(
                video_path,
                video_id,
                extraction_interval=0.5,  # 每0.5秒抽取一帧
                frame_limit=10            # 最多处理10帧
            )
            
            # 复制检测图像到静态目录
            if result['status'] == 'completed':
                copy_detection_images()
                
                print("\n处理结果:")
                print(f"- 视频ID: {video_id}")
                print(f"- 处理帧数: {result['processed_frames']}")
                print(f"- 检测到目标的帧数: {result['detected_frames']}")
                print(f"- 检测到的目标总数: {result['detection_count']}")
                print(f"- 用时: {result['duration']:.2f}秒")
                
                print("\n要查看检测结果，请确保Web应用正在运行并访问:")
                print("http://localhost:6920")
                print("然后在检测结果查询页面过滤视频ID:", video_id)
            else:
                print(f"\n处理失败: {result.get('error', '未知错误')}")
    else:
        print(f"\n测试视频创建完成，但未进行处理。")
        print(f"您可以使用以下命令处理该视频:")
        print(f"python process_local_video.py {video_path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 