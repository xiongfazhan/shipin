"""
本地视频文件处理模块
提供视频文件加载、抽帧、目标检测和结果保存功能
"""

import os
import cv2
import time
import sqlite3
from datetime import datetime
from .yolo_service import detect_objects, save_annotated_frame, process_detection_result
from .database import get_db_connection
from .copy_images import copy_detection_images

def process_video_file(video_path, video_id, extraction_interval=1.0, frame_limit=100, save_frames=True):
    """处理单个视频文件，进行抽帧和目标检测
    
    Args:
        video_path: 视频文件路径
        video_id: 视频ID（对应数据库中的视频流ID）
        extraction_interval: 抽帧间隔（秒）
        frame_limit: 最大抽取帧数
        save_frames: 是否保存检测结果帧
        
    Returns:
        dict: 处理结果统计信息
    """
    result_stats = {
        "video_id": video_id,
        "total_frames": 0,
        "processed_frames": 0,
        "detected_frames": 0,
        "detection_count": 0,
        "start_time": datetime.now(),
        "end_time": None,
        "duration": None,
        "status": "running"
    }
    
    # 检查文件是否存在
    if not os.path.exists(video_path):
        print(f"视频文件不存在: {video_path}")
        result_stats["status"] = "error"
        result_stats["error"] = "视频文件不存在"
        return result_stats
    
    try:
        # 获取当前目录的父目录（controller）
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        # 设置检测结果存储目录
        detection_dir = os.path.join(base_dir, "instance", "detection_results")
        os.makedirs(detection_dir, exist_ok=True)
        
        print(f"检测结果将保存到: {detection_dir}")
        
        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"无法打开视频文件: {video_path}")
            result_stats["status"] = "error"
            result_stats["error"] = "无法打开视频文件"
            return result_stats
        
        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        result_stats["total_frames"] = total_frames
        result_stats["fps"] = fps
        result_stats["duration"] = duration
        
        print(f"视频信息: {video_path}")
        print(f"- 总帧数: {total_frames}")
        print(f"- FPS: {fps}")
        print(f"- 时长: {duration:.2f}秒")
        
        # 计算需要抽取的帧
        frame_interval = int(fps * extraction_interval)
        if frame_interval < 1:
            frame_interval = 1
        
        # 连接数据库
        db = get_db_connection()
        cursor = db.cursor()
        
        # 检查视频ID是否存在
        cursor.execute("SELECT video_id FROM video_streams WHERE video_id = ?", (video_id,))
        if cursor.fetchone() is None:
            # 创建新的视频流记录
            print(f"视频ID {video_id} 不存在，创建新记录")
            cursor.execute(
                "INSERT INTO video_streams (video_id, stream_url, level, remarks, is_active) VALUES (?, ?, ?, ?, ?)",
                (video_id, os.path.basename(video_path), "中", f"本地视频文件: {os.path.basename(video_path)}", 1)
            )
            db.commit()
        
        # 开始抽帧并检测
        frame_count = 0
        processed_count = 0
        detected_count = 0
        detection_total = 0
        saved_image_paths = []  # 用于跟踪已保存的图像路径
        
        while frame_count < total_frames and processed_count < frame_limit:
            # 设置当前帧位置
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)
            
            # 读取帧
            ret, frame = cap.read()
            if not ret:
                print(f"无法读取帧 {frame_count}")
                break
            
            # 计算当前帧的时间戳
            seconds = frame_count / fps
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 检测目标
            detection_result = detect_objects(frame, video_id, timestamp)
            processed_count += 1
            
            # 如果检测到目标
            if detection_result and detection_result.get('detections', []):
                detected_count += 1
                detection_total += len(detection_result['detections'])
                
                # 首先处理检测结果（保存到数据库）
                process_result = process_detection_result(detection_result)
                
                # 保存检测结果图像
                if save_frames:
                    # 获取结果ID用于更新图像路径
                    cursor.execute(
                        "SELECT result_id FROM detection_results WHERE video_id = ? ORDER BY result_id DESC LIMIT 1",
                        (video_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        result_id = row[0]
                        detection_result['result_id'] = result_id
                    
                    filepath = save_annotated_frame(
                        frame, 
                        detection_result, 
                        output_dir=detection_dir,
                        update_db=True
                    )
                    
                    if filepath and os.path.exists(filepath):
                        saved_image_paths.append(filepath)
                        print(f"已保存图像: {filepath} (大小: {os.path.getsize(filepath)} 字节)")
                    else:
                        print(f"警告: 图像保存失败或文件不存在: {filepath}")
            
            # 更新下一帧位置
            frame_count += frame_interval
            
            # 显示进度
            if processed_count % 10 == 0 or processed_count == 1:
                progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                print(f"处理进度: {progress:.1f}% ({processed_count}/{frame_limit})")
        
        # 关闭视频
        cap.release()
        
        # 更新统计信息
        result_stats["processed_frames"] = processed_count
        result_stats["detected_frames"] = detected_count
        result_stats["detection_count"] = detection_total
        result_stats["end_time"] = datetime.now()
        result_stats["duration"] = (result_stats["end_time"] - result_stats["start_time"]).total_seconds()
        result_stats["status"] = "completed"
        
        # 确认已保存的图像文件
        print(f"处理完成，已尝试保存 {len(saved_image_paths)} 个图像文件")
        
        # 添加短暂延迟，确保文件系统完成写入
        print("等待1秒确保文件写入完成...")
        time.sleep(1)
        
        # 复制检测结果图像到静态目录
        print("\n开始复制检测图像到静态目录...")
        copy_success = copy_detection_images()
        
        # 如果复制失败，尝试检查并再次复制
        if not copy_success:
            print("第一次复制失败，再次尝试...")
            time.sleep(2)  # 多等待2秒
            copy_detection_images()
        
        # 确认图像是否已成功复制
        static_results_dir = os.path.join(base_dir, "static", "results")
        static_files = os.listdir(static_results_dir) if os.path.exists(static_results_dir) else []
        print(f"静态结果目录中有 {len(static_files)} 个文件")
        
        print(f"视频处理完成: {video_path}")
        print(f"- 处理帧数: {processed_count}")
        print(f"- 检测到目标的帧数: {detected_count}")
        print(f"- 检测到的目标总数: {detection_total}")
        print(f"- 用时: {result_stats['duration']:.2f}秒")
        
        return result_stats
    
    except Exception as e:
        import traceback
        print(f"处理视频时出错: {e}")
        traceback.print_exc()
        
        result_stats["status"] = "error"
        result_stats["error"] = str(e)
        result_stats["end_time"] = datetime.now()
        
        if 'cap' in locals():
            cap.release()
        
        return result_stats

def create_test_command():
    """创建一个测试命令行函数，用于方便测试视频处理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='视频文件处理与目标检测')
    parser.add_argument('video_path', type=str, help='视频文件路径')
    parser.add_argument('--video-id', type=str, default='LOCAL001', help='视频ID')
    parser.add_argument('--interval', type=float, default=1.0, help='抽帧间隔（秒）')
    parser.add_argument('--limit', type=int, default=20, help='最大处理帧数')
    
    args = parser.parse_args()
    
    print(f"开始处理视频: {args.video_path}")
    process_video_file(
        args.video_path, 
        args.video_id, 
        extraction_interval=args.interval,
        frame_limit=args.limit
    )
    print("处理完成！")

if __name__ == "__main__":
    create_test_command() 