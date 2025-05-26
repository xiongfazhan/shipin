import cv2
import threading
import time
import queue
import numpy as np
from datetime import datetime
from .database import get_db_connection
import os

# 定义视频流抽帧频率（秒/帧）
FRAME_INTERVAL = {
    '高': 1,   # 高风险：1秒1帧
    '中': 5,   # 中风险：5秒1帧
    '低': 30   # 低风险：30秒1帧
}

# 保存所有活跃的视频捕获对象
active_captures = {}
# 保存运行中的抽帧线程
active_threads = {}
# 保存最近抽取的帧
recent_frames = {}
# 帧队列，用于线程间通信
frame_queue = queue.Queue(maxsize=100)
# 线程运行状态标志
running = True
# 线程锁，用于保护共享资源
thread_lock = threading.Lock()

def start_video_processing():
    """启动视频处理主线程"""
    global running
    running = True
    
    # 启动帧处理线程（将帧送入YOLO处理）
    processing_thread = threading.Thread(target=process_frames_worker, daemon=True)
    processing_thread.start()
    
    # 启动视频流管理线程
    management_thread = threading.Thread(target=manage_video_streams, daemon=True)
    management_thread.start()
    
    print("视频处理系统已启动")
    return processing_thread, management_thread

def stop_video_processing():
    """停止所有视频处理线程"""
    global running
    running = False
    
    with thread_lock:
        # 停止并清理所有视频捕获对象
        for video_id in list(active_captures.keys()):
            try:
                cap = active_captures.pop(video_id)
                if cap and cap.isOpened():
                    cap.release()
                print(f"已关闭视频流：{video_id}")
            except Exception as e:
                print(f"关闭视频流 {video_id} 时出错: {e}")
    
    print("视频处理系统已停止")

def manage_video_streams():
    """管理视频流：检查数据库中活跃视频流，启动或停止抽帧线程"""
    while running:
        try:
            # 从数据库获取当前活跃的视频流
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("SELECT video_id, stream_url, level FROM video_streams WHERE is_active = 1")
            active_streams = {row['video_id']: {
                'url': row['stream_url'], 
                'level': row['level']
            } for row in cursor.fetchall()}
            
            with thread_lock:
                # 关闭不再活跃的视频流
                for video_id in list(active_captures.keys()):
                    if video_id not in active_streams:
                        if video_id in active_threads:
                            # 线程会自行检查running标志退出
                            active_threads.pop(video_id)
                        
                        # 释放视频捕获资源
                        cap = active_captures.pop(video_id)
                        if cap and cap.isOpened():
                            cap.release()
                        print(f"已关闭不再活跃的视频流：{video_id}")
                
                # 启动新的视频流
                for video_id, info in active_streams.items():
                    if video_id not in active_captures:
                        try:
                            # 创建视频捕获对象
                            cap = cv2.VideoCapture(info['url'])
                            if not cap.isOpened():
                                print(f"无法打开视频流 {video_id}: {info['url']}")
                                continue
                            
                            active_captures[video_id] = cap
                            
                            # 启动抽帧线程
                            thread = threading.Thread(
                                target=frame_extractor_worker,
                                args=(video_id, info['level']),
                                daemon=True
                            )
                            active_threads[video_id] = thread
                            thread.start()
                            print(f"已启动视频流 {video_id} 的抽帧线程")
                        except Exception as e:
                            print(f"初始化视频流 {video_id} 失败: {e}")
            
            # 10秒检查一次数据库
            time.sleep(10)
            
        except Exception as e:
            print(f"管理视频流时出错: {e}")
            time.sleep(30)  # 出错后延长等待时间

def frame_extractor_worker(video_id, level):
    """视频抽帧工作线程
    
    Args:
        video_id: 视频流ID
        level: 视频流风险等级，决定抽帧频率
    """
    interval = FRAME_INTERVAL.get(level, 5)  # 默认5秒/帧
    print(f"视频流 {video_id} (等级: {level}) 抽帧间隔: {interval}秒")
    
    last_frame_time = 0
    
    while running:
        try:
            with thread_lock:
                if video_id not in active_captures:
                    print(f"视频流 {video_id} 不再活跃，退出抽帧线程")
                    break
                
                cap = active_captures[video_id]
                
                # 判断是否需要抽帧
                current_time = time.time()
                if current_time - last_frame_time < interval:
                    time.sleep(0.1)  # 短暂休眠，避免CPU占用
                    continue
                
                # 读取一帧
                ret, frame = cap.read()
                if not ret:
                    print(f"视频流 {video_id} 读取失败，尝试重新连接")
                    # 可以在这里实现重新连接逻辑
                    time.sleep(5)
                    continue
                
                # 更新最后抽帧时间
                last_frame_time = current_time
                
                # 保存最近的帧
                recent_frames[video_id] = {
                    'frame': frame,
                    'timestamp': datetime.now(),
                    'level': level
                }
                
                # 将帧放入处理队列
                try:
                    frame_data = {
                        'video_id': video_id,
                        'frame': frame.copy(),  # 复制帧以避免并发修改
                        'timestamp': datetime.now(),
                        'level': level
                    }
                    frame_queue.put(frame_data, block=False)
                except queue.Full:
                    # 队列已满，丢弃帧
                    print(f"处理队列已满，丢弃视频流 {video_id} 的帧")
        
        except Exception as e:
            print(f"视频流 {video_id} 抽帧出错: {e}")
            time.sleep(interval)  # 出错后等待一个间隔周期

def process_frames_worker():
    """从队列中获取帧并送入YOLO处理"""
    from src.services.yolo_service import detect_objects, process_detection_result, save_annotated_frame
    
    # 创建检测结果目录
    detection_results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "instance", "detection_results")
    os.makedirs(detection_results_dir, exist_ok=True)
    
    while running:
        try:
            # 非阻塞方式获取帧，允许线程检查running标志
            try:
                frame_data = frame_queue.get(block=True, timeout=1)
            except queue.Empty:
                continue
            
            # 从队列中获取帧数据
            video_id = frame_data['video_id']
            frame = frame_data['frame']
            timestamp = frame_data['timestamp']
            level = frame_data['level']
            
            # 调用YOLO服务进行对象检测
            detection_result = detect_objects(frame, video_id, timestamp)
            
            # 如果有检测结果，保存到数据库
            if detection_result and detection_result.get('detections'):
                # 保存检测结果
                save_success = process_detection_result(detection_result)
                
                # 如果有检测对象且保存成功，保存带标注的图像
                if save_success and detection_result.get('detection_count', 0) > 0:
                    # 保存带标注的图像
                    image_path = save_annotated_frame(
                        frame, 
                        detection_result,
                        output_dir=detection_results_dir
                    )
                    if image_path:
                        print(f"已保存检测图像: {image_path}")
            
            # 标记任务完成
            frame_queue.task_done()
            
        except Exception as e:
            print(f"处理帧时出错: {e}")

def get_latest_frame(video_id):
    """获取指定视频流的最新帧
    
    用于调试和UI展示，实际检测使用队列机制
    
    Args:
        video_id: 视频流ID
        
    Returns:
        dict: 包含帧数据和元信息的字典，如果没有则返回None
    """
    with thread_lock:
        return recent_frames.get(video_id)

def get_frame_count():
    """获取队列中等待处理的帧数量"""
    return frame_queue.qsize()

def get_active_streams_count():
    """获取当前活跃的视频流数量"""
    with thread_lock:
        return len(active_captures) 