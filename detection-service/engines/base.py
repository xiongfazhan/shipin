class BaseEngine:
    """算法插件基类，所有引擎需实现 infer 方法返回原始检测结果字典"""

    def __init__(self, **kwargs):
        pass

    def infer(self, stream_id, frame, timestamp, config):
        """推理并返回 List[Dict] 的原始结果。必须由子类实现。"""
        raise NotImplementedError 