from enum import Enum
from dataclasses import dataclass
from typing import Dict, List

class RiskLevel(Enum):
    HIGH = "高"
    MEDIUM = "中" 
    LOW = "低"

@dataclass
class RiskConfig:
    level: RiskLevel
    frame_interval: float  # 抽帧间隔(秒)
    confidence_threshold: float  # 置信度阈值
    max_objects: int  # 最大检测对象数
    detection_classes: List[str]  # 检测类别
    
class RiskClassifier:
    def __init__(self):
        self.risk_configs = {
            RiskLevel.HIGH: RiskConfig(
                level=RiskLevel.HIGH,
                frame_interval=0.5,  # 高风险：0.5秒抽帧
                confidence_threshold=0.3,
                max_objects=20,
                detection_classes=["person", "car", "truck", "weapon", "knife"]
            ),
            RiskLevel.MEDIUM: RiskConfig(
                level=RiskLevel.MEDIUM,
                frame_interval=1.0,  # 中风险：1秒抽帧
                confidence_threshold=0.5,
                max_objects=10,
                detection_classes=["person", "car", "truck"]
            ),
            RiskLevel.LOW: RiskConfig(
                level=RiskLevel.LOW,
                frame_interval=2.0,  # 低风险：2秒抽帧
                confidence_threshold=0.7,
                max_objects=5,
                detection_classes=["person", "car"]
            )
        }
    
    def get_config(self, risk_level: str) -> RiskConfig:
        """根据风险等级获取配置"""
        # 支持英文和中文风险等级
        level_mapping = {
            'high': RiskLevel.HIGH,
            'medium': RiskLevel.MEDIUM,
            'low': RiskLevel.LOW,
            '高': RiskLevel.HIGH,
            '中': RiskLevel.MEDIUM,
            '低': RiskLevel.LOW
        }
        
        if risk_level in level_mapping:
            level_enum = level_mapping[risk_level]
        else:
            # 尝试直接使用枚举值
            level_enum = RiskLevel(risk_level)
            
        return self.risk_configs[level_enum]
    
    def update_config(self, risk_level: str, config: RiskConfig):
        """更新风险等级配置"""
        level_enum = RiskLevel(risk_level)
        self.risk_configs[level_enum] = config
    
    def get_all_configs(self) -> Dict[str, RiskConfig]:
        """获取所有风险等级配置"""
        return {level.value: config for level, config in self.risk_configs.items()}