import base64
import os
import re
import ssl
import aiohttp
from aiohttp import TCPConnector
import asyncio
from typing import List, Optional, Dict
from astrbot.api import logger
import astrbot.api.message_components as Comp
from astrbot.api.event import AstrMessageEvent

class ImageHandler:
    def __init__(self):
        self.session = None

    async def _get_aiohttp_session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp会话"""
        if self.session is None or self.session.closed:
            ssl_context = ssl.create_default_context()
            ssl_context.set_ciphers('DEFAULT')
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = TCPConnector(ssl=ssl_context)
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'http://qq.com',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive'
                }
            )
        return self.session

    def _extract_image_url(self, message: str) -> Optional[str]:
        """从消息中提取图片URL"""
        if not isinstance(message, str):
            message = str(message)
            
        pattern = r'\[CQ:image,.*?url=(.*?)(?:,|])'
        match = re.search(pattern, message)
        return match.group(1) if match else None

    async def _download_image(self, url: str, max_retries: int = 3) -> Optional[bytes]:
        """下载图片内容"""
        retry_count = 0
        while retry_count < max_retries:
            try:
                session = await self._get_aiohttp_session()
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.error(f"下载图片失败，状态码: {response.status}, URL: {url}")
            except aiohttp.ClientSSLError as e:
                logger.error(f"SSL错误 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
            except aiohttp.ClientError as e:
                logger.error(f"网络错误 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
            except Exception as e:
                logger.error(f"下载图片时出错 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
            
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(1)
        
        return None

    async def collect_images(self, event: AstrMessageEvent) -> List[Dict]:
        """收集消息中的所有图片"""
        images = []
        
        # 从消息组件中获取图片
        for component in event.message_obj.message:
            if isinstance(component, Comp.Image):
                image_data = None
                url_to_try = None
                
                if hasattr(component, 'url') and component.url:
                    url_to_try = component.url
                elif hasattr(component, 'file') and component.file:
                    if os.path.exists(component.file):
                        try:
                            with open(component.file, "rb") as f:
                                image_data = {
                                    'type': 'base64',
                                    'data': base64.b64encode(f.read()).decode()
                                }
                        except Exception as e:
                            logger.error(f"读取本地图片失败: {str(e)}")
                    elif component.file.startswith(("http://", "https://")):
                        url_to_try = component.file
                
                if url_to_try:
                    image_content = await self._download_image(url_to_try)
                    if image_content:
                        image_data = {
                            'type': 'base64',
                            'data': base64.b64encode(image_content).decode()
                        }
                
                if image_data:
                    images.append(image_data)

        # 如果没有从组件中找到图片，尝试从原始消息中提取
        if not images:
            image_url = self._extract_image_url(event.message_obj.raw_message)
            if image_url:
                image_content = await self._download_image(image_url)
                if image_content:
                    images.append({
                        'type': 'base64',
                        'data': base64.b64encode(image_content).decode()
                    })

        return images

    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close() 