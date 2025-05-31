from typing import Any
from astrbot.api import AstrBotConfig, logger

class ConfigManager:
    def __init__(self, config: AstrBotConfig):
        self.config = config
        self.default_values = {
            "max_text_length": 500,
            "max_images": 1
        }

    def get_value(self, key: str) -> Any:
        """获取配置值，如果不存在则返回默认值"""
        try:
            return int(self.config.get(key, self.default_values.get(key)))
        except (ValueError, TypeError):
            logger.warning(f"配置项 {key} 的值无效，使用默认值 {self.default_values.get(key)}")
            return self.default_values.get(key)

    def check_content_limits(self, content: str, images: list) -> tuple[bool, str]:
        """检查内容是否符合限制"""
        max_text_length = self.get_value("max_text_length")
        max_images = self.get_value("max_images")

        if len(content) > max_text_length:
            return False, f"漂流瓶内容超过长度限制（最大 {max_text_length} 字）"

        if len(images) > max_images:
            return False, f"图片数量超过限制（最大 {max_images} 张）"

        return True, "" 