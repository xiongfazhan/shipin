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
    parser.add_argument('video_path', type=str, help='视频文件路径')
    parser.add_argument('--video-id', type=str, default='LOCAL001', help='视频ID标识')
    parser.add_argument('--interval', type=float, default=100.0, help='抽帧间隔（秒）')
    parser.add_argument('--limit', type=int, default=20, help='最大处理帧数')
    parser.add_argument('--no-save', action='store_true', help='不保存检测结果图像')
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # 检查视频文件是否存在
    video_path = args.video_path
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        return 1
    
    print(f"=== 开始处理视频: {video_path} ===")
    print(f"- 视频ID: {args.video_id}")
    print(f"- 抽帧间隔: {args.interval}秒")
    print(f"- 最大处理帧数: {args.limit}")
    print(f"- 保存检测结果: {'否' if args.no_save else '是'}")
    
    # 创建Flask应用上下文
    with app.app_context():
        start_time = datetime.now()
        
        # 处理视频文件
        stats = process_video_file(
            video_path,
            args.video_id,
            extraction_interval=args.interval,
            frame_limit=args.limit,
            save_frames=not args.no_save
        )
        
        # 如果保存了图像，则确保复制到静态目录
        if not args.no_save:
            copy_detection_images()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
    
    # 显示处理结果
    if stats["status"] == "completed":
        print("\n=== 视频处理完成 ===")
        print(f"- 总帧数: {stats['total_frames']}")
        print(f"- 处理帧数: {stats['processed_frames']}")
        print(f"- 检测到目标的帧数: {stats['detected_frames']}")
        print(f"- 检测到的目标总数: {stats['detection_count']}")
        print(f"- 总处理时间: {duration:.2f}秒")
        print("\n检测结果可以在Web界面的\"检测结果查询\"页面中查看和分析")
        return 0
    else:
        print("\n=== 视频处理失败 ===")
        print(f"错误: {stats.get('error', '未知错误')}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 