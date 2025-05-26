"""
视频文件处理命令行工具
用于简单地处理本地视频文件，进行目标检测并生成结果
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 确保Flask应用上下文可用（用于数据库操作）
from controller.main import app
from src.video_processing.file_processor import process_video_file
from scripts.copy_images import copy_detection_images # Assuming copy_images is now in scripts

def parse_arguments():
    parser = argparse.ArgumentParser(description='视频文件处理与目标检测')
    parser.add_argument('video_path', type=str, default='test.mp4', help='视频文件路径')
    parser.add_argument('--video-id', type=str, default='', help='视频ID标识，不指定则自动生成')
    parser.add_argument('--interval', type=float, default=100.0, help='抽帧间隔（秒）')
    parser.add_argument('--limit', type=int, default=20, help='最大处理帧数')
    parser.add_argument('--no-save', action='store_true', help='不保存检测结果图像')
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_arguments()
    
    # 检查视频文件路径
    video_path = args.video_path
    if not os.path.exists(video_path):
        print(f"错误：视频文件不存在: {video_path}")
        return 1
    
    # 如果没有指定视频ID，则根据文件名自动生成
    video_id = args.video_id
    if not video_id:
        # 从文件名生成视频ID
        filename = Path(video_path).stem
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        video_id = f'VID_{filename}_{timestamp[:8]}'
    
    print("=" * 60)
    print(f"处理视频文件: {video_path}")
    print(f"视频ID: {video_id}")
    print(f"抽帧间隔: {args.interval} 秒")
    print(f"最大处理帧数: {args.limit}")
    print(f"保存检测结果图像: {'否' if args.no_save else '是'}")
    print("=" * 60)
    
    # 设置数据库上下文
    with app.app_context():
        # 处理视频文件
        result = process_video_file(
            video_path,
            video_id,
            extraction_interval=args.interval,
            frame_limit=args.limit,
            save_frames=not args.no_save
        )
        
        # 如果成功处理并保存帧，则复制图像到静态目录
        if result['status'] == 'completed' and not args.no_save:
            print("\n复制检测图像到静态目录...")
            copy_detection_images()
    
    # 处理结果
    if result['status'] == 'completed':
        print("\n" + "=" * 60)
        print("视频处理成功完成！")
        print(f"- 处理帧数: {result['processed_frames']}")
        print(f"- 检测到目标的帧数: {result['detected_frames']}")
        print(f"- 检测到的目标总数: {result['detection_count']}")
        print(f"- 用时: {result['duration']:.2f} 秒")
        
        # 提示用户如何查看结果
        print("\n要查看检测结果，请启动Web应用并访问 http://localhost:6920")
        print("在检测结果查询页面过滤视频ID: " + video_id)
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print(f"视频处理失败: {result.get('error', '未知错误')}")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 