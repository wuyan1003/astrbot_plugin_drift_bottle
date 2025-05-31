from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import json
import base64
import os
import random
from datetime import datetime
from typing import List, Dict, Optional, Union, Tuple
import astrbot.api.message_components as Comp
import re

@register("drift_bottle", "author", "一个简单的漂流瓶插件", "1.0.0")
class DriftBottlePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.data_file = os.path.join("data", "drift_bottles.json")
        self.config = config
        self._ensure_data_file()
        
    def _ensure_data_file(self):
        """确保数据文件存在"""
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump({
                    "active": [],  # 未被捡起的漂流瓶
                    "picked": []   # 已被捡起的漂流瓶
                }, f)
        else:
            # 检查并迁移旧数据
            self._migrate_data()

    def _migrate_data(self):
        """迁移旧数据到新格式"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 如果数据是列表格式，说明是旧数据
            if isinstance(data, list):
                # 将所有漂流瓶移动到active列表
                new_data = {
                    "active": data,
                    "picked": []
                }
                # 保存新格式的数据
                with open(self.data_file, "w", encoding="utf-8") as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                logger.info("漂流瓶数据已成功迁移到新格式")
        except Exception as e:
            logger.error(f"迁移数据时出错: {str(e)}")

    def _load_bottles(self) -> Dict[str, List[Dict]]:
        """加载所有漂流瓶"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 确保数据格式正确
                if isinstance(data, dict) and "active" in data and "picked" in data:
                    return data
                else:
                    # 如果数据格式不正确，返回默认格式
                    return {"active": [], "picked": []}
        except:
            return {"active": [], "picked": []}

    def _save_bottles(self, bottles: Dict[str, List[Dict]]):
        """保存漂流瓶数据"""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(bottles, f, ensure_ascii=False, indent=2)

    def _extract_image_url(self, message: str) -> Optional[str]:
        """从消息中提取图片URL"""
        # 如果message是Event对象，获取其字符串表示
        if not isinstance(message, str):
            message = str(message)
            
        # 匹配CQ码中的图片URL
        pattern = r'\[CQ:image,.*?url=(.*?)(?:,|])'
        match = re.search(pattern, message)
        if match:
            return match.group(1)
        return None

    def _format_bottle_message(self, bottle: Dict) -> str:
        """格式化漂流瓶消息"""
        message = f"漂流瓶编号：{bottle['id']}\n"
        message += f"发送者：{bottle['sender']}\n"
        message += f"时间：{bottle['timestamp']}\n"
        message += f"内容：{bottle['content']}"
        return message

    def _get_config_value(self, key: str, default_value: int) -> int:
        """从配置中获取值，如果不存在则返回默认值"""
        try:
            return int(self.config.get(key, default_value))
        except (ValueError, TypeError):
            logger.warning(f"配置项 {key} 的值无效，使用默认值 {default_value}")
            return default_value

    def _check_content_limits(self, content: str, images: List[Dict]) -> Tuple[bool, str]:
        """检查内容是否符合限制"""
        max_text_length = self._get_config_value("max_text_length", 500)
        max_images = self._get_config_value("max_images", 1)

        if len(content) > max_text_length:
            return False, f"漂流瓶内容超过长度限制（最大 {max_text_length} 字）"

        if len(images) > max_images:
            return False, f"图片数量超过限制（最大 {max_images} 张）"

        return True, ""

    def _collect_images(self, event: AstrMessageEvent) -> List[Dict]:
        """收集消息中的所有图片"""
        images = []
        # 从消息组件中获取图片
        for component in event.message_obj.message:
            if isinstance(component, Comp.Image):
                image_data = None
                if hasattr(component, 'url') and component.url:
                    image_data = {'type': 'url', 'data': component.url}
                elif hasattr(component, 'file') and component.file:
                    if os.path.exists(component.file):
                        with open(component.file, "rb") as f:
                            image_data = {
                                'type': 'base64',
                                'data': base64.b64encode(f.read()).decode()
                            }
                    elif component.file.startswith(("http://", "https://")):
                        image_data = {'type': 'url', 'data': component.file}
                
                if image_data:
                    images.append(image_data)

        # 如果没有从组件中找到图片，尝试从原始消息中提取
        if not images:
            image_url = self._extract_image_url(event.message_obj.raw_message)
            if image_url:
                images.append({'type': 'url', 'data': image_url})

        return images

    @filter.command("扔漂流瓶")
    async def throw_bottle(self, event: AstrMessageEvent, content: str):
        """扔一个漂流瓶"""
        # 收集所有图片
        images = self._collect_images(event)
        
        # 检查内容限制
        passed, error_msg = self._check_content_limits(content, images)
        if not passed:
            yield event.plain_result(error_msg)
            return

        bottles = self._load_bottles()
        
        # 生成新的漂流瓶ID
        new_id = 1
        if bottles["active"]:
            new_id = max(bottle["id"] for bottle in bottles["active"]) + 1
        if bottles["picked"]:
            new_id = max(new_id, max(bottle["id"] for bottle in bottles["picked"]) + 1)

        # 只保留允许的最大图片数量
        max_images = self._get_config_value("max_images", 1)
        images = images[:max_images]
        
        bottle = {
            "id": new_id,
            "content": content,
            "images": images,
            "sender": event.get_sender_name(),
            "sender_id": event.get_sender_id(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        bottles["active"].append(bottle)
        self._save_bottles(bottles)
        
        yield event.plain_result(f"你的漂流瓶已经扔进大海了！瓶子的编号是 {bottle['id']}")

    def _send_bottle_message(self, event: AstrMessageEvent, bottle: Dict, prefix_message: str = ""):
        """发送漂流瓶消息"""
        message = prefix_message + "\n" if prefix_message else ""
        message += self._format_bottle_message(bottle)

        # 构建消息链
        message_chain = [Comp.Plain(message)]
        
        # 添加图片到消息链
        if bottle.get('images'):
            for img in bottle['images']:
                if img['type'] == 'url':
                    message_chain.append(Comp.Image.fromURL(img['data']))
                else:  # base64
                    # 保存为临时文件
                    temp_file = os.path.join("data", f"temp_{bottle['id']}_{len(message_chain)}.jpg")
                    with open(temp_file, "wb") as f:
                        f.write(base64.b64decode(img['data']))
                    message_chain.append(Comp.Image.fromFileSystem(temp_file))
                    # 删除临时文件
                    os.remove(temp_file)

        return event.chain_result(message_chain)

    @filter.command("捡漂流瓶")
    async def pick_bottle(self, event: AstrMessageEvent):
        """捡起一个漂流瓶"""
        bottles = self._load_bottles()
        if not bottles["active"]:
            yield event.plain_result("海面上没有漂流瓶了...")
            return

        # 随机选择一个漂流瓶
        bottle = random.choice(bottles["active"])
        bottles["active"].remove(bottle)
        bottles["picked"].append(bottle)
        self._save_bottles(bottles)

        yield self._send_bottle_message(event, bottle, "你捡到了一个漂流瓶！")

    @filter.command("被捡起的漂流瓶")
    async def picked_bottle(self, event: AstrMessageEvent, bottle_id: Optional[int] = None):
        """查看已捡起的漂流瓶"""
        bottles = self._load_bottles()
        if not bottles["picked"]:
            yield event.plain_result("还没有被捡起的漂流瓶...")
            return

        if bottle_id is not None:
            # 查找指定编号的漂流瓶
            bottle = next((b for b in bottles["picked"] if b["id"] == bottle_id), None)
            if not bottle:
                yield event.plain_result(f"没有找到编号为 {bottle_id} 的漂流瓶")
                return
        else:
            # 随机选择一个已捡起的漂流瓶
            bottle = random.choice(bottles["picked"])

        yield self._send_bottle_message(event, bottle, "这是一个被捡起的漂流瓶！")

    @filter.command("未被捡起的漂流瓶")
    async def bottle_count(self, event: AstrMessageEvent):
        """查看当前漂流瓶数量"""
        bottles = self._load_bottles()
        yield event.plain_result(
            f"当前海面上还有 {len(bottles['active'])} 个漂流瓶\n"
            f"已经被捡起的漂流瓶有 {len(bottles['picked'])} 个"
        )

    @filter.command("被捡起的漂流瓶列表")
    async def list_picked_bottles(self, event: AstrMessageEvent):
        """显示所有被捡起的漂流瓶列表"""
        bottles = self._load_bottles()
        if not bottles["picked"]:
            yield event.plain_result("还没有被捡起的漂流瓶...")
            return
        
        # 按时间排序，最新的在前面
        sorted_bottles = sorted(bottles["picked"], key=lambda x: x["timestamp"], reverse=True)
        
        # 构建消息
        message = "以下是所有被捡起的漂流瓶：\n\n"
        for bottle in sorted_bottles:
            message += f"瓶子编号：{bottle['id']}\n"
            message += f"投放者：{bottle['sender']}\n"
            message += f"投放时间：{bottle['timestamp']}\n"
            message += "------------------------\n"
        
        yield event.plain_result(message.strip())

    async def terminate(self):
        """插件终止时的清理工作"""
        pass
