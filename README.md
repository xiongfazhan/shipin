# 视频分析系统

基于Flask的视频分析和处理系统，提供视频流处理、目标检测和数据管理功能。

## 主要功能

- 视频流处理和分析
- 目标检测和识别
- 检测结果数据管理
- 数据库可视化管理
- 本地视频文件处理（支持UI和CLI方式）

有关处理本地视频文件的详细说明，请参阅[本地视频处理指南](controller/README_视频处理.md)。

## 系统架构

- `controller/`: 主要应用代码
  - `main.py`: 应用入口和路由配置
  - `utils/`: 工具模块
    - `database.py`: 数据库操作
    - `detection_api.py`: 检测结果API
    - `video_processing.py`: 视频处理
    - `database_admin.py`: 数据库管理

## 项目结构

- `controller/`: Web应用、API端点和用户界面。
- `src/`: 核心处理逻辑、数据库模型和实用工具模块。
- `scripts/`: 用于数据导入、测试等任务的实用脚本。
- `tests/`: 项目的单元测试和集成测试。

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

## 如何贡献

我们欢迎各种形式的贡献，包括功能请求、错误报告和代码提交。如果您想为本项目做出贡献，请遵循以下步骤：
1. Fork 本仓库。
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)。
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)。
4. 推送到分支 (`git push origin feature/AmazingFeature`)。
5. 打开一个 Pull Request。

## 许可证

本项目采用 MIT 许可证。
