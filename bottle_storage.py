from typing import Dict, List, Optional
import json
import os
from datetime import datetime
from astrbot.api import logger
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import random


class BottleStorage:
    def __init__(self, data_dir: str, uri: str):
        self.uri = uri
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

    def _save_bottles(self, bottles: Dict[str, Dict]) -> None:
        """保存漂流瓶数据"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(bottles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存漂流瓶数据时出错: {str(e)}")

    def add_bottle(
        self, content: str, images: List[Dict], sender: str, sender_id: str
    ) -> int:
        """添加新漂流瓶"""
        client = MongoClient(self.uri, server_api=ServerApi("1"))
        database = client["DriftBottles"]
        collection = database["Bottles"]

        # 生成新的漂流瓶ID
        new_id = collection.count_documents({}) + 1

        bottle = {
            "bottle_id": new_id,
            "content": content,
            "images": images,
            "sender": sender,
            "sender_id": sender_id,
            "picked": False,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        collection.insert_one(bottle)

        return new_id

    def pick_random_bottle(self, sender_id: str) -> Optional[Dict]:
        """随机捡起一个漂流瓶"""
        # mongodb
        client = MongoClient(self.uri, server_api=ServerApi("1"))
        database = client["DriftBottles"]
        collection = database["Bottles"]
        try:
            bottles = collection.aggregate(
                [{"$match": {"picked": False,"sender_id": {"$ne": sender_id}}}, {"$sample": {"size": 1}}]
            )
            bottle = bottles.next()
        except StopIteration:
            return None
        objectId = bottle["_id"]
        collection.update_one({"_id": objectId}, {"$set": {"picked": True}})

        # local
        if sender_id not in self.data["user_list"]:
            self.data["user_list"][sender_id] = []
        del bottle["_id"]
        self.data["user_list"][sender_id].append(bottle)
        self._save_bottles(self.data)

        return bottle

    def get_picked_bottle(
        self, sender_id: str, bottle_id: Optional[int] = None
    ) -> Optional[Dict]:
        """获取指定ID或随机一个已捡起的漂流瓶"""
        if sender_id not in self.data["user_list"]:
            return None
        if bottle_id is not None:
            for bottle in self.data["user_list"][sender_id]:
                if bottle["id"] == bottle_id:
                    return bottle
            return None
        return random.choice(self.data["user_list"][sender_id])

    def get_bottle_counts(self, sender_id: str) -> tuple[int, int]:
        """获取漂流瓶数量"""
        # total active bottles
        client = MongoClient(self.uri, server_api=ServerApi("1"))
        database = client["DriftBottles"]
        collection = database["Bottles"]
        count = collection.count_documents({"picked": False})
        # picked bottles
        picked_bottles = self.data["user_list"].get(sender_id, [])
        # 尚有漂流瓶数量，用户已捡起漂流瓶数量
        return count, len(picked_bottles)

    def get_picked_bottles(self, sender_id: str) -> List[Dict]:
        """获取所有已捡起的漂流瓶"""
        bottles = self.data["user_list"].get(sender_id, [])

        return sorted(bottles, key=lambda x: x["timestamp"], reverse=True)
