from typing import Dict, List, Optional
import json
import os
from datetime import datetime
from astrbot.api import logger

class BottleStorage:
    def __init__(self, data_dir: str):
        self.data_file = os.path.join(data_dir, "drift_bottles.json")
        self._ensure_data_file()
        
    def _ensure_data_file(self) -> None:
        """确保数据文件存在"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            self._save_bottles({"active": [], "picked": []})
        else:
            self._migrate_data()

    def _migrate_data(self) -> None:
        """迁移旧数据到新格式"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, list):
                new_data = {
                    "active": data,
                    "picked": []
                }
                self._save_bottles(new_data)
                logger.info("漂流瓶数据已成功迁移到新格式")
        except Exception as e:
            logger.error(f"迁移数据时出错: {str(e)}")

    def _load_bottles(self) -> Dict[str, List[Dict]]:
        """加载所有漂流瓶"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "active" in data and "picked" in data:
                    return data
        except Exception as e:
            logger.error(f"加载漂流瓶数据时出错: {str(e)}")
        
        return {"active": [], "picked": []}

    def _save_bottles(self, bottles: Dict[str, List[Dict]]) -> None:
        """保存漂流瓶数据"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(bottles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存漂流瓶数据时出错: {str(e)}")

    def add_bottle(self, content: str, images: List[Dict], sender: str, sender_id: str) -> int:
        """添加新漂流瓶"""
        bottles = self._load_bottles()
        
        # 生成新的漂流瓶ID
        new_id = 1
        if bottles["active"]:
            new_id = max(bottle["id"] for bottle in bottles["active"]) + 1
        if bottles["picked"]:
            new_id = max(new_id, max(bottle["id"] for bottle in bottles["picked"]) + 1)

        bottle = {
            "id": new_id,
            "content": content,
            "images": images,
            "sender": sender,
            "sender_id": sender_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        bottles["active"].append(bottle)
        self._save_bottles(bottles)
        return new_id

    def pick_random_bottle(self) -> Optional[Dict]:
        """随机捡起一个漂流瓶"""
        bottles = self._load_bottles()
        if not bottles["active"]:
            return None

        import random
        bottle = random.choice(bottles["active"])
        bottles["active"].remove(bottle)
        bottles["picked"].append(bottle)
        self._save_bottles(bottles)
        return bottle

    def get_picked_bottle(self, bottle_id: Optional[int] = None) -> Optional[Dict]:
        """获取指定ID或随机一个已捡起的漂流瓶"""
        bottles = self._load_bottles()
        if not bottles["picked"]:
            return None

        if bottle_id is not None:
            return next((b for b in bottles["picked"] if b["id"] == bottle_id), None)
        
        import random
        return random.choice(bottles["picked"])

    def get_bottle_counts(self) -> tuple[int, int]:
        """获取漂流瓶数量"""
        bottles = self._load_bottles()
        return len(bottles["active"]), len(bottles["picked"])

    def get_picked_bottles(self) -> List[Dict]:
        """获取所有已捡起的漂流瓶"""
        bottles = self._load_bottles()
        return sorted(bottles["picked"], key=lambda x: x["timestamp"], reverse=True) 