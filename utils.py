from typing import List, Dict
import astrbot.api.message_components as Comp
from astrbot.api.event import AstrMessageEvent


async def collect_images(event: AstrMessageEvent) -> List[Dict]:
    """收集消息中的所有图片"""
    images = []

    for component in event.message_obj.message:
        if isinstance(component, Comp.Image):
            images.append({"type": "url", "data": component.url})

    return images
