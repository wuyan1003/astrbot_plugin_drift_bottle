from typing import Dict, List, Optional
import json
import os
from astrbot.api import logger
import random
import aiohttp
from typing import Any


class BottleStorage:
    def __init__(self, data_dir: str, api_base_url: str, http_client: aiohttp.ClientSession):
        self.api_base_url = api_base_url # 这是 FastAPI 服务的基URL
        self.http_client = http_client
        self.data_file = os.path.join(data_dir, "drift_bottles.json")
        self._ensure_data_file()
        self.data = self._load_bottles()

    def _ensure_data_file(self) -> None:
        """确保数据文件存在"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            self._save_bottles({"user_list": {}})

    def _load_bottles(self) -> Dict[str, Dict]:
        """加载漂流瓶数据"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "user_list" in data:
                    return data
        except Exception as e:
            logger.error(f"加载漂流瓶数据时出错: {str(e)}")

        return {"user_list": {}}

    async def _make_api_request(self, method: str, path: str, json_data: Optional[Dict] = None) -> Any:
        url = f"{self.api_base_url}{path}"
        try:
            if method == "GET":
                async with self.http_client.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method == "POST":
                async with self.http_client.post(url, json=json_data) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except aiohttp.ClientResponseError as e:
            # 捕获 HTTP 状态码错误 (例如 404, 500)
            logger.error(f"API请求失败 (HTTP Status Error {e.status} - {method} {url}): {e}")
            raise # 重新抛出，让调用者处理，或根据需要返回 None
        except aiohttp.ClientError as e:
            # 捕获更广泛的客户端错误 (例如连接问题，超时)
            logger.error(f"API请求失败 (Client Error - {method} {url}): {e}")
            raise # 重新抛出，让调用者处理，或根据需要返回 None

    def _save_bottles(self, bottles: Dict[str, Dict]) -> None:
        """保存漂流瓶数据"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(bottles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存漂流瓶数据时出错: {str(e)}")

    async def add_bottle(
        self, content: str, images: List[Dict], sender: str, sender_id: str
    ) -> int:
        """通过API添加新漂流瓶"""
        bottle_data = {
            "content": content,
            "images": images,
            "sender": sender,
            "sender_id": sender_id,
        }
        try:
            response_data = await self._make_api_request("POST", "/bottles/", json_data=bottle_data)
            new_id = response_data.get("bottle_id")
            if new_id is None:
                raise ValueError("API did not return a bottle_id.")
            logger.info(f"成功添加漂流瓶，ID: {new_id}")
            return new_id
        except Exception as e: # 捕获 make_api_request 抛出的异常
            logger.error(f"添加漂流瓶失败: {str(e)}")
            return -1

    async def pick_random_bottle(self, sender_id: str) -> Optional[Dict]:
        """通过API随机捡起一个漂流瓶，并存储到本地"""
        try:
            picked_bottle_from_api = await self._make_api_request("POST", f"/bottles/pick/{sender_id}")
            
            if sender_id not in self.data["user_list"]:
                self.data["user_list"][sender_id] = []
            
            self.data["user_list"][sender_id].append(picked_bottle_from_api)
            self._save_bottles(self.data)
            
            logger.info(f"用户 {sender_id} 成功捡起漂流瓶，ID: {picked_bottle_from_api.get('bottle_id')}")
            return picked_bottle_from_api
        except aiohttp.ClientResponseError as e:
            if e.status == 404: # FastAPI 返回 404 表示没有可捡的瓶子
                logger.info(f"没有可供用户 {sender_id} 捡起的漂流瓶。")
                return {}
            else:
                logger.error(f"捡起漂流瓶失败 (HTTP Status Error {e.status}): {str(e)}")
                return None
        except Exception as e: # 捕获其他可能的异常，如连接问题
            logger.error(f"捡起漂流瓶失败: {str(e)}")
            return None

    def get_picked_bottle(
        self, sender_id: str, bottle_id: Optional[int] = None
    ) -> Optional[Dict]:
        """获取指定ID或随机一个已捡起的漂流瓶"""
        if sender_id not in self.data["user_list"]:
            return None
        if bottle_id is not None:
            for bottle in self.data["user_list"][sender_id]:
                if bottle["bottle_id"] == bottle_id:
                    return bottle
            return None
        return random.choice(self.data["user_list"][sender_id])

    async def get_bottle_counts(self, sender_id: str) -> tuple[int, int]:
        """获取漂流瓶数量"""
        # total active bottles: 通过API获取
        total_active_bottles = -1
        try:
            response_data = await self._make_api_request("GET", "/bottles/counts/active")
            total_active_bottles = response_data.get("total_active_bottles", 0)
        except Exception as e:
            logger.error(f"获取总活跃漂流瓶数量失败: {str(e)}")
            # 这里可以选择抛出异常，或者返回一个默认值
        
        # picked bottles: 从本地数据获取
        picked_bottles = self.data["user_list"].get(sender_id, [])
        user_picked_bottles_count = len(picked_bottles)
        
        # 尚有漂流瓶数量，用户已捡起漂流瓶数量
        return total_active_bottles, user_picked_bottles_count

    def get_picked_bottles(self, sender_id: str) -> List[Dict]:
        """获取所有已捡起的漂流瓶"""
        bottles = self.data["user_list"].get(sender_id, [])

        return sorted(bottles, key=lambda x: x["timestamp"], reverse=True)
