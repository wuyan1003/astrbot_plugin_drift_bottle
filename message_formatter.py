from typing import Dict, List
import astrbot.api.message_components as Comp
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api import logger
import base64
import re

class MessageFormatter:
    @staticmethod
    def format_bottle_message(bottle: Dict) -> str:
        """格式化漂流瓶消息"""
        message = f"漂流瓶编号：{bottle['id']}\n"
        message += f"发送者：{bottle['sender']}\n"
        message += f"时间：{bottle['timestamp']}\n"
        message += f"内容：{bottle['content']}"
        return message

    @staticmethod
    def create_bottle_message(event: AstrMessageEvent, bottle: Dict, prefix_message: str = "") -> MessageEventResult:
        """创建漂流瓶消息结果"""
        message = prefix_message + "\n" if prefix_message else ""
        message += MessageFormatter.format_bottle_message(bottle)

        # 构建消息链
        message_chain = [Comp.Plain(message)]
        
        # 添加图片到消息链
        if bottle.get('images'):
            logger.info(f"Processing {len(bottle['images'])} images")
            for img in bottle['images']:
                if img.get('type') == 'base64' and img.get('data'):
                    try:
                        # 获取base64数据
                        img_data = img['data']
                        logger.info(f"Processing image data length: {len(img_data)}")

                        # 如果数据已经包含 "base64://"，去掉这个前缀
                        if img_data.startswith('base64://'):
                            img_data = img_data.replace('base64://', '')
                        
                        # 清理base64数据中的空白字符
                        img_data = ''.join(img_data.split())

                        # 尝试解码base64数据以验证其有效性
                        try:
                            base64.b64decode(img_data)
                            logger.info("Base64 data validation successful")
                        except Exception as e:
                            logger.error(f"Base64 decode failed: {str(e)}")
                            continue

                        # 分批发送大图片
                        if len(img_data) > 1024 * 1024:  # 如果图片大于1MB
                            logger.info("Large image detected, sending as separate message")
                            # 先发送文本消息
                            event.chain_result(message_chain)
                            # 再单独发送图片
                            return event.chain_result([Comp.Image(file=f"base64://{img_data}")])
                        else:
                            logger.info("Adding image to message chain")
                            message_chain.append(Comp.Image(file=f"base64://{img_data}"))
                            logger.info("Image added successfully")
                    except Exception as e:
                        logger.error(f"处理base64图片失败: {str(e)}")
                else:
                    logger.error(f"Invalid image format: {img}")

        return event.chain_result(message_chain)

    @staticmethod
    def format_picked_bottles_list(bottles: List[Dict]) -> str:
        """格式化已捡起的漂流瓶列表"""
        if not bottles:
            return "还没有被捡起的漂流瓶..."
        
        message = "以下是所有被捡起的漂流瓶：\n\n"
        for bottle in bottles:
            message += f"瓶子编号：{bottle['id']}\n"
            message += f"投放者：{bottle['sender']}\n"
            message += f"投放时间：{bottle['timestamp']}\n"
            message += "------------------------\n"
        
        return message.strip() 