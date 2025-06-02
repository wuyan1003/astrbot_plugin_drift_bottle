import json
import os
import random
import aiohttp
import base64
from typing import Dict, List, Optional, Tuple, Union
from astrbot.api import logger

class CloudBottleStorage:
    def __init__(self, base_url: str = "http://wuyan1003.cn:1145"):
        self.base_url = base_url
        # 配置aiohttp使用双栈
        self.connector = aiohttp.TCPConnector(family=0)  # 0表示自动选择IPv4或IPv6
        self.session = None

    async def get_session(self) -> aiohttp.ClientSession:
        """获取或创建一个新的会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(connector=self.connector)
        return self.session

    async def process_images(self, images: List[Union[str, Dict]]) -> List[Dict[str, str]]:
        """处理图片列表，将图片转换为base64格式"""
        processed_images = []
        
        if not images:
            return []

        session = await self.get_session()
        for img in images:
            try:
                # 如果img是字典类型
                if isinstance(img, dict):
                    # 如果已经是正确的格式
                    if img.get('type') == 'base64' and isinstance(img.get('data'), str):
                        img_data = img['data']
                        # 如果数据已经包含 "base64://"，去掉这个前缀
                        if img_data.startswith('base64://'):
                            img_data = img_data.replace('base64://', '')
                        # 清理base64数据中的空白字符
                        img_data = ''.join(img_data.split())
                        processed_images.append({
                            'type': 'base64',
                            'data': img_data
                        })
                        continue
                    
                    # 尝试获取图片数据
                    if 'url' in img:
                        img = img['url']
                    elif 'path' in img:
                        img = img['path']
                    elif 'data' in img:
                        if isinstance(img['data'], str):
                            if img['data'].startswith('base64://'):
                                img_data = img['data'].replace('base64://', '')
                                img_data = ''.join(img_data.split())
                                processed_images.append({
                                    'type': 'base64',
                                    'data': img_data
                                })
                                continue
                            else:
                                img = img['data']
                        else:
                            logger.error(f"Unsupported data format in dict: {type(img['data'])}")
                            continue
                    else:
                        logger.error(f"Invalid image dict format: missing required fields")
                        continue

                # 处理字符串类型的图片数据
                if isinstance(img, str):
                    if img.startswith('base64://'):
                        img_data = img.replace('base64://', '')
                        img_data = ''.join(img_data.split())
                        processed_images.append({
                            'type': 'base64',
                            'data': img_data
                        })
                    elif img.startswith(('http://', 'https://')):
                        try:
                            async with session.get(img, timeout=30) as response:
                                if response.status == 200:
                                    image_data = await response.read()
                                    base64_data = base64.b64encode(image_data).decode('utf-8')
                                    processed_images.append({
                                        'type': 'base64',
                                        'data': base64_data
                                    })
                        except Exception as e:
                            logger.error(f"Failed to process URL image: {str(e)}")
                    else:
                        try:
                            with open(img, 'rb') as f:
                                image_data = f.read()
                                base64_data = base64.b64encode(image_data).decode('utf-8')
                                processed_images.append({
                                    'type': 'base64',
                                    'data': base64_data
                                })
                        except Exception as e:
                            logger.error(f"Failed to process local image: {str(e)}")
                else:
                    logger.error(f"Unsupported image type: {type(img)}")
            except Exception as e:
                logger.error(f"Error processing image: {str(e)}")
                continue

        return processed_images

    async def add_bottle(self, content: str, images: List[Union[str, Dict]], sender: str, sender_id: str) -> int:
        """添加一个云漂流瓶"""
        try:
            logger.info(f"Adding bottle with {len(images)} images")
            # 处理图片
            processed_images = await self.process_images(images)
            
            session = await self.get_session()
            data = {
                "content": content,
                "images": processed_images,
                "sender": sender,
                "sender_id": sender_id,
                "picked": False
            }
            logger.info(f"Sending bottle data with {len(processed_images)} processed images")
            async with session.post(f"{self.base_url}/api/bottles", json=data, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("id")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to add bottle: HTTP {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Failed to add bottle: {str(e)}")
            raise

    async def pick_random_bottle(self) -> Optional[Dict]:
        """随机捡起一个云漂流瓶"""
        try:
            session = await self.get_session()
            # 先尝试捡新瓶子
            async with session.get(f"{self.base_url}/api/bottles/random", timeout=10) as response:
                if response.status == 200:
                    bottle = await response.json()
                    if 'images' in bottle and isinstance(bottle['images'], list):
                        for img in bottle['images']:
                            if isinstance(img, dict) and img.get('type') == 'base64':
                                img['data'] = f"base64://{img['data']}"
                    return {"bottle": bottle, "is_reset": False}
                elif response.status == 404:
                    # 如果没有新瓶子，尝试重置已捡过的瓶子
                    async with session.post(f"{self.base_url}/api/bottles/reset", timeout=10) as reset_response:
                        if reset_response.status == 200:
                            # 重置成功后，再次尝试捡瓶子
                            async with session.get(f"{self.base_url}/api/bottles/random", timeout=10) as retry_response:
                                if retry_response.status == 200:
                                    bottle = await retry_response.json()
                                    if 'images' in bottle and isinstance(bottle['images'], list):
                                        for img in bottle['images']:
                                            if isinstance(img, dict) and img.get('type') == 'base64':
                                                img['data'] = f"base64://{img['data']}"
                                    return {"bottle": bottle, "is_reset": True}
                    return None
                logger.error(f"Failed to pick bottle: HTTP {response.status}")
                return None
        except Exception as e:
            logger.error(f"Failed to pick bottle: {str(e)}")
            raise

    async def get_bottle_counts(self) -> Tuple[int, int]:
        """获取云漂流瓶数量"""
        try:
            session = await self.get_session()
            async with session.get(f"{self.base_url}/api/bottles/count", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("active", 0), data.get("picked", 0)
                logger.error(f"Failed to get bottle counts: HTTP {response.status}")
                return 0, 0
        except Exception as e:
            logger.error(f"Failed to get bottle counts: {str(e)}")
            return 0, 0

    async def close(self):
        """关闭会话和连接器"""
        if self.session and not self.session.closed:
            await self.session.close()
        if self.connector and not self.connector.closed:
            await self.connector.close()

    def __del__(self):
        """确保资源被正确清理"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.session.close())
            except Exception:
                pass  # 忽略清理时的错误 