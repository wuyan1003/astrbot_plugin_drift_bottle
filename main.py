from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from typing import Optional

from .bottle_storage import BottleStorage
from .cloud_bottle_storage import CloudBottleStorage
from .image_handler import ImageHandler
from .config_manager import ConfigManager
from .message_formatter import MessageFormatter

@register("drift_bottle", "wuyan1003", "一个简单的漂流瓶插件", "1.1.0")
class DriftBottlePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.storage = BottleStorage("data")
        self.cloud_storage = CloudBottleStorage()
        self.image_handler = ImageHandler()
        self.config_manager = ConfigManager(config)
        self.message_formatter = MessageFormatter()

    @filter.command("扔漂流瓶")
    async def throw_bottle(self, event: AstrMessageEvent, content: str = ""):
        """扔一个漂流瓶"""
        # 收集所有图片
        images = await self.image_handler.collect_images(event)
        
        # 如果既没有文字内容也没有图片，则返回错误提示
        if not content and not images:
            yield event.plain_result("漂流瓶不能是空的哦，请至少包含文字或图片～")
            return

        # 检查内容限制
        passed, error_msg = self.config_manager.check_content_limits(content, images)
        if not passed:
            yield event.plain_result(error_msg)
            return

        # 只保留允许的最大图片数量
        max_images = self.config_manager.get_value("max_images")
        images = images[:max_images]
        
        # 添加漂流瓶
        bottle_id = self.storage.add_bottle(
            content=content,
            images=images,
            sender=event.get_sender_name(),
            sender_id=event.get_sender_id()
        )
        
        yield event.plain_result(f"你的漂流瓶已经扔进大海了！瓶子的编号是 {bottle_id}")

    @filter.command("捡漂流瓶")
    async def pick_bottle(self, event: AstrMessageEvent):
        """捡起一个漂流瓶"""
        bottle = self.storage.pick_random_bottle()
        if not bottle:
            yield event.plain_result("海面上没有漂流瓶了...")
            return

        yield self.message_formatter.create_bottle_message(event, bottle, "你捡到了一个漂流瓶！")

    @filter.command("被捡起的漂流瓶")
    async def picked_bottle(self, event: AstrMessageEvent, bottle_id: Optional[int] = None):
        """查看已捡起的漂流瓶"""
        bottle = self.storage.get_picked_bottle(bottle_id)
        if not bottle:
            if bottle_id is not None:
                yield event.plain_result(f"没有找到编号为 {bottle_id} 的漂流瓶")
            else:
                yield event.plain_result("还没有被捡起的漂流瓶...")
            return

        yield self.message_formatter.create_bottle_message(event, bottle, "这是一个被捡起的漂流瓶！")

    @filter.command("未被捡起的漂流瓶")
    async def bottle_count(self, event: AstrMessageEvent):
        """查看当前漂流瓶数量"""
        active_count, picked_count = self.storage.get_bottle_counts()
        yield event.plain_result(
            f"当前海面上还有 {active_count} 个漂流瓶\n"
            f"已经被捡起的漂流瓶有 {picked_count} 个"
        )

    @filter.command("被捡起的漂流瓶列表")
    async def list_picked_bottles(self, event: AstrMessageEvent):
        """显示所有被捡起的漂流瓶列表"""
        bottles = self.storage.get_picked_bottles()
        message = self.message_formatter.format_picked_bottles_list(bottles)
        yield event.plain_result(message)

    @filter.command("扔云漂流瓶")
    async def throw_cloud_bottle(self, event: AstrMessageEvent, content: str = ""):
        """扔一个云漂流瓶"""
        # 收集所有图片
        images = await self.image_handler.collect_images(event)
        
        # 如果既没有文字内容也没有图片，则返回错误提示
        if not content and not images:
            yield event.plain_result("漂流瓶不能是空的哦，请至少包含文字或图片～")
            return

        # 检查内容限制
        passed, error_msg = self.config_manager.check_content_limits(content, images)
        if not passed:
            yield event.plain_result(error_msg)
            return

        # 只保留允许的最大图片数量
        max_images = self.config_manager.get_value("max_images")
        images = images[:max_images]
        
        # 添加云漂流瓶
        try:
            bottle_id = await self.cloud_storage.add_bottle(
                content=content,
                images=images,
                sender=event.get_sender_name(),
                sender_id=event.get_sender_id()
            )
            if bottle_id:
                yield event.plain_result(f"你的云漂流瓶已经扔进云端大海了！瓶子的编号是 {bottle_id}")
            else:
                yield event.plain_result("抱歉，扔云漂流瓶失败了，请稍后再试...")
        except Exception as e:
            logger.error(f"Failed to throw cloud bottle: {e}")
            yield event.plain_result("抱歉，扔云漂流瓶时遇到了问题，请稍后再试...")

    @filter.command("捡云漂流瓶")
    async def pick_cloud_bottle(self, event: AstrMessageEvent):
        """捡起一个云漂流瓶"""
        try:
            result = await self.cloud_storage.pick_random_bottle()
            if not result:
                yield event.plain_result("云端海面上没有漂流瓶了...")
                return

            bottle = result["bottle"]
            is_reset = result["is_reset"]

            # 如果是重置后的瓶子，添加提示信息
            prefix_message = "你从云端捡到了一个漂流瓶！"
            if is_reset:
                prefix_message = "云端的新漂流瓶已经用完了，已经重新放出之前捡过的漂流瓶～\n" + prefix_message

            yield self.message_formatter.create_bottle_message(event, bottle, prefix_message)
        except Exception as e:
            logger.error(f"Failed to pick cloud bottle: {e}")
            yield event.plain_result("抱歉，捡云漂流瓶时遇到了问题，请稍后再试...")

    async def terminate(self):
        """插件终止时的清理工作"""
        await self.image_handler.close()
