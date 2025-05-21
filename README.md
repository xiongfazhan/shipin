# 视频分析系统

基于Flask的视频分析和处理系统，提供视频流处理、目标检测和数据管理功能。

## 主要功能

- 视频流处理和分析
- 目标检测和识别
- 检测结果数据管理
- 数据库可视化管理

## 系统架构

- `controller/`: 主要应用代码
  - `main.py`: 应用入口和路由配置
  - `utils/`: 工具模块
    - `database.py`: 数据库操作
    - `detection_api.py`: 检测结果API
    - `video_processing.py`: 视频处理
    - `database_admin.py`: 数据库管理

## 安装和运行

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 初始化数据库：
```bash
python controller/init_db.py
```

3. 运行应用：
```bash
python controller/main.py
```

## 配置说明

- 默认端口：6920
- 数据库路径：controller/instance/video_streams.db
- 检测结果存储：controller/static/results/

## 注意事项

- 请确保已正确配置Python环境
- 运行前需要初始化数据库
- 检测结果图片会保存在static/results目录下