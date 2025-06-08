from typing import Dict, Any, List
from astrbot.api import AstrBotConfig

class ConfigManager:
    def __init__(self, config: AstrBotConfig):
        self.config = config
    
    def get_value(self, key: str) -> Any:
        """获取配置值"""
        return self.config.get(key)
    
    def set_value(self, key: str, value: Any) -> None:
        """设置配置值"""
        self.config[key] = value
    
    def check_content_limits(self, content: str, images: List[Dict]) -> tuple[bool, str]:
        """检查内容是否符合限制"""
        if len(content) > self.get_value("max_content_length"):
            return False, f"文本内容超过{self.get_value('max_content_length')}字符限制"
        
        if len(images) > self.get_value("max_images"):
            return False, f"图片数量超过{self.get_value('max_images')}张限制"
        
        return True, ""
    
    def is_cloud_sync_enabled(self) -> bool:
        """检查是否启用云同步"""
        return self.get_value("cloud_sync_enabled")
    
    def get_cloud_sync_interval(self) -> int:
        """获取云同步间隔时间（秒）"""
        return self.get_value("cloud_sync_interval")
    
    def get_cloud_sync_batch_size(self) -> int:
        """获取每次同步的漂流瓶数量"""
        return self.get_value("cloud_sync_batch_size")
    
    def get_cloud_server_url(self) -> str:
        """获取云服务器地址"""
        return self.get_value("cloud_sync_server_url") 