import json
import os
import random
import aiohttp
import base64
from typing import Dict, List, Optional, Tuple, Union
from astrbot.api import logger
import asyncio
from aiohttp.client_exceptions import ClientConnectorError, ServerDisconnectedError

class CloudBottleStorage:
    def __init__(self, base_url: str = "http://47.109.207.155:1145"):
        self.base_url = base_url
        # 使用简化的连接配置
        self.connector = aiohttp.TCPConnector(
            force_close=True,  # 改回强制关闭连接
            enable_cleanup_closed=True,
            limit=10,
            ttl_dns_cache=300
        )
        self.timeout = aiohttp.ClientTimeout(
            total=30,
            connect=10,
            sock_connect=10,
            sock_read=15
        )
        self.session = None
        self.headers = {
            'User-Agent': 'CloudBottle/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        self._lock = asyncio.Lock()  # 添加锁来保护会话创建
        # 添加速率限制处理
        self._rate_limit_remaining = {}  # 记录每个IP剩余的请求次数
        self._rate_limit_reset = {}  # 记录每个IP的重置时间

    async def get_session(self) -> aiohttp.ClientSession:
        """获取或创建一个新的会话"""
        async with self._lock:  # 使用锁来保护会话创建
            try:
                if self.session is None or self.session.closed:
                    if self.session and not self.session.closed:
                        await self.session.close()
                    self.session = aiohttp.ClientSession(
                        connector=self.connector,
                        timeout=self.timeout,
                        headers=self.headers,
                        trust_env=True
                    )
                return self.session
            except Exception as e:
                logger.error(f"创建会话时出错: {str(e)}")
                raise

    async def _make_request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """发送HTTP请求的通用方法"""
        max_retries = 3
        retry_count = 0
        last_exception = None

        while retry_count < max_retries:
            session = None
            try:
                # 创建新的会话并设置为不验证SSL
                connector = aiohttp.TCPConnector(
                    force_close=True,
                    enable_cleanup_closed=True,
                    verify_ssl=False
                )
                session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=self.timeout,
                    headers=self.headers,
                    trust_env=True
                )
                
                # 发送请求并等待响应
                async with session:  # 使用上下文管理器确保会话被正确关闭
                    async with session.request(method, url, **kwargs) as response:
                        # 读取响应内容
                        await response.read()
                        return response

            except Exception as e:
                last_exception = e
                logger.error(f"请求失败 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
                retry_count += 1
                
                if session and not session.closed:
                    await session.close()
                
                if retry_count < max_retries:
                    await asyncio.sleep(1)
                continue

        logger.error(f"达到最大重试次数，最后的错误: {str(last_exception)}")
        raise last_exception

    async def process_images(self, images: List[Union[str, Dict]]) -> List[Dict[str, str]]:
        """处理图片列表，将图片转换为base64格式"""
        processed_images = []
        
        if not images:
            return []

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
                            # 为每个图片下载创建新的会话
                            async with aiohttp.ClientSession(
                                connector=self.connector,
                                timeout=self.timeout,
                                headers=self.headers
                            ) as session:
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

    async def _handle_rate_limit_headers(self, response: aiohttp.ClientResponse, endpoint: str):
        """处理速率限制相关的响应头"""
        # 从响应头中获取速率限制信息
        remaining = response.headers.get('X-RateLimit-Remaining')
        reset = response.headers.get('X-RateLimit-Reset')
        
        if remaining is not None:
            self._rate_limit_remaining[endpoint] = int(remaining)
        if reset is not None:
            self._rate_limit_reset[endpoint] = float(reset)

        # 如果遇到速率限制
        if response.status == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                retry_after = float(retry_after)
                # 根据不同的端点返回不同的提示信息
                if endpoint == 'add_bottle':
                    return {"error": f"发送漂流瓶太频繁了，请等待 {retry_after:.0f} 秒后再试"}
                elif endpoint == 'pick_bottle':
                    return {"error": f"捡漂流瓶太频繁了，请等待 {retry_after:.0f} 秒后再试"}
                else:
                    return {"error": f"操作太频繁了，请等待 {retry_after:.0f} 秒后再试"}
            else:
                return {"error": "操作太频繁了，请稍后再试"}
        return None

    async def add_bottle(self, content: str, images: List[Union[str, Dict]], sender: str, sender_id: str) -> int:
        """添加一个云漂流瓶"""
        try:
            logger.info(f"Adding bottle with {len(images)} images")
            processed_images = await self.process_images(images)
            
            data = {
                "content": content,
                "images": processed_images,
                "sender": sender,
                "sender_id": sender_id,
                "picked": False
            }
            logger.info(f"Sending bottle data with {len(processed_images)} processed images")
            logger.info(f"Attempting to connect to {self.base_url}/api/bottles")
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(verify_ssl=False, force_close=True),
                timeout=self.timeout,
                headers=self.headers
            ) as session:
                async with session.post(
                    f"{self.base_url}/api/bottles",
                    json=data
                ) as response:
                    # 处理速率限制
                    rate_limit_result = await self._handle_rate_limit_headers(response, 'add_bottle')
                    if rate_limit_result:
                        return rate_limit_result
                        
                    if response.status == 200:
                        result = await response.json()
                        bottle_id = result.get("id")
                        logger.info(f"Successfully added bottle with ID {bottle_id}")
                        return bottle_id
                    elif response.status == 403:
                        error_text = await response.text()
                        logger.warning(f"Blocked attempt from blacklisted sender: {sender_id}")
                        return {"error": "您已被加入黑名单，无法使用漂流瓶功能"}
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to add bottle: HTTP {response.status} - {error_text}")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"Connection error details: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to add bottle: {str(e)}")
            raise

    async def pick_random_bottle(self, sender_id: str) -> Optional[Dict]:
        """随机捡起一个云漂流瓶"""
        try:
            logger.info("尝试捡起随机漂流瓶...")
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(verify_ssl=False, force_close=True),
                timeout=self.timeout,
                headers=self.headers
            ) as session:
                async with session.get(f"{self.base_url}/api/bottles/random?sender_id={sender_id}") as response:
                    # 处理速率限制
                    rate_limit_result = await self._handle_rate_limit_headers(response, 'pick_bottle')
                    if rate_limit_result:
                        return rate_limit_result
                        
                    response_text = await response.text()
                    logger.info(f"收到响应: 状态码 {response.status}")
                    logger.info(f"响应内容: {response_text}")

                    if response.status == 200:
                        try:
                            bottle = await response.json()
                            logger.info(f"成功解析漂流瓶数据: {json.dumps(bottle, ensure_ascii=False)}")
                            if 'images' in bottle and isinstance(bottle['images'], list):
                                for img in bottle['images']:
                                    if isinstance(img, dict) and img.get('type') == 'base64':
                                        img['data'] = f"base64://{img['data']}"
                            return {"bottle": bottle, "is_reset": False}
                        except json.JSONDecodeError as e:
                            logger.error(f"解析响应JSON失败: {str(e)}, 响应内容: {response_text}")
                            raise
                    elif response.status == 403:
                        logger.warning(f"用户 {sender_id} 在黑名单中，无法捡起漂流瓶")
                        return {"error": "您已被加入黑名单，无法使用漂流瓶功能"}
                    elif response.status == 404:
                        logger.info("没有找到可用的漂流瓶，尝试重置...")
                        async with session.post(f"{self.base_url}/api/bottles/reset") as reset_response:
                            # 处理重置操作的速率限制
                            rate_limit_result = await self._handle_rate_limit_headers(reset_response, 'reset_bottle')
                            if rate_limit_result:
                                return rate_limit_result
                                
                            if reset_response.status == 200:
                                logger.info("重置成功，重新尝试捡瓶子...")
                                async with session.get(f"{self.base_url}/api/bottles/random?sender_id={sender_id}") as retry_response:
                                    # 处理速率限制
                                    rate_limit_result = await self._handle_rate_limit_headers(retry_response, 'pick_bottle')
                                    if rate_limit_result:
                                        return rate_limit_result
                                        
                                    if retry_response.status == 200:
                                        try:
                                            bottle = await retry_response.json()
                                            logger.info(f"重置后成功获取漂流瓶: {json.dumps(bottle, ensure_ascii=False)}")
                                            if 'images' in bottle and isinstance(bottle['images'], list):
                                                for img in bottle['images']:
                                                    if isinstance(img, dict) and img.get('type') == 'base64':
                                                        img['data'] = f"base64://{img['data']}"
                                            return {"bottle": bottle, "is_reset": True}
                                        except json.JSONDecodeError as e:
                                            logger.error(f"解析重试响应JSON失败: {str(e)}")
                                            raise
                                    elif retry_response.status == 403:
                                        logger.warning(f"用户 {sender_id} 在黑名单中，无法捡起漂流瓶")
                                        return {"error": "您已被加入黑名单，无法使用漂流瓶功能"}
                                    else:
                                        retry_text = await retry_response.text()
                                        logger.error(f"重置后获取漂流瓶失败: HTTP {retry_response.status} - {retry_text}")
                            else:
                                reset_text = await reset_response.text()
                                logger.error(f"重置漂流瓶失败: HTTP {reset_response.status} - {reset_text}")
                        return None
                    else:
                        logger.error(f"获取漂流瓶失败: HTTP {response.status} - {response_text}")
                        return None
                    
        except aiohttp.ClientError as e:
            logger.error(f"网络请求错误: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"捡漂流瓶时发生未知错误: {str(e)}", exc_info=True)
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
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def __del__(self):
        """确保资源被正确清理"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.session.close())
            except Exception as e:
                logger.error(f"Error during cleanup in destructor: {str(e)}")
                pass  # 忽略清理时的错误 