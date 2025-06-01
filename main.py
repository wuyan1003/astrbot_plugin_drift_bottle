from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from typing import Optional

from .bottle_storage import BottleStorage
from .utils import collect_images
from .config_manager import ConfigManager
from .message_formatter import MessageFormatter


@register("drift_bottle", "wuyan1003", "一个简单的漂流瓶插件", "1.0.0")
class DriftBottlePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config_manager = ConfigManager(config)
        self.storage = BottleStorage("data", self.config_manager.uri)
        self.message_formatter = MessageFormatter()

    @filter.command("扔漂流瓶")
    async def throw_bottle(self, event: AstrMessageEvent, content: Optional[str] = ""):
        """扔一个漂流瓶"""
        # 收集所有图片
        images = await collect_images(event)

        # 检查内容限制
        passed, error_msg = self.config_manager.check_content_limits(content, images)
        if not passed:
            yield event.plain_result(error_msg)
            return

        # 只保留允许的最大图片数量
        images = images[: self.config_manager.max_images]

        # 添加漂流瓶
        bottle_id = self.storage.add_bottle(
            content=content,
            images=images,
            sender=event.get_sender_name(),
            sender_id=event.get_sender_id(),
        )

        yield event.plain_result(f"你的漂流瓶已经扔进大海了！瓶子的编号是 {bottle_id}")

    @filter.command("捡漂流瓶")
    async def pick_bottle(self, event: AstrMessageEvent):
        """捡起一个漂流瓶"""
        bottle = self.storage.pick_random_bottle(event.get_sender_id())
        if not bottle:
            yield event.plain_result("海面上没有别人的漂流瓶了...")
            return

        yield self.message_formatter.create_bottle_message(
            event, bottle, "你捡到了一个漂流瓶！"
        )

    @filter.command("被捡起的漂流瓶")
    async def picked_bottle(
        self, event: AstrMessageEvent, bottle_id: Optional[int] = None
    ):
        """查看已捡起的漂流瓶"""
        bottle = self.storage.get_picked_bottle(event.get_sender_id(), bottle_id)
        if not bottle:
            if bottle_id is not None:
                yield event.plain_result(f"没有找到编号为 {bottle_id} 的漂流瓶")
            else:
                yield event.plain_result("还没有被捡起的漂流瓶...")
            return

        yield self.message_formatter.create_bottle_message(
            event, bottle, "这是一个被捡起的漂流瓶！"
        )

    @filter.command("未被捡起的漂流瓶")
    async def bottle_count(self, event: AstrMessageEvent):
        """查看当前漂流瓶数量"""
        active_count, picked_count = self.storage.get_bottle_counts(
            event.get_sender_id()
        )
        yield event.plain_result(
            f"当前海面上还有 {active_count} 个漂流瓶\n"
            f"你已经捡起 {picked_count} 个漂流瓶"
        )

    @filter.command("被捡起的漂流瓶列表")
    async def list_picked_bottles(self, event: AstrMessageEvent):
        """显示所有被捡起的漂流瓶列表"""
        bottles = self.storage.get_picked_bottles(event.get_sender_id())
        message = self.message_formatter.format_picked_bottles_list(bottles)
        yield event.plain_result(message)

    async def terminate(self):
        """插件终止时的清理工作"""
        pass
