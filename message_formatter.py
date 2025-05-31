from typing import Dict, List
import astrbot.api.message_components as Comp
from astrbot.api.event import AstrMessageEvent, MessageEventResult

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
            for img in bottle['images']:
                if img['type'] == 'base64':
                    try:
                        message_chain.append(Comp.Image(file=f"base64://{img['data']}"))
                    except Exception as e:
                        from astrbot.api import logger
                        logger.error(f"处理base64图片失败: {str(e)}")

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