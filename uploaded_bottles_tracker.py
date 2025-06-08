import json
import os
from typing import Set, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class UploadedBottlesTracker:
    def __init__(self, data_dir: str):
        self.data_file = os.path.join(data_dir, "uploaded_bottles.json")
        self._ensure_data_file()
    
    def _ensure_data_file(self) -> None:
        """确保数据文件存在"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            self._save_data({"uploaded_ids": [], "last_upload": None})
    
    def _load_data(self) -> Dict:
        """加载已上传的漂流瓶ID数据"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载已上传漂流瓶数据时出错: {str(e)}")
            return {"uploaded_ids": [], "last_upload": None}
    
    def _save_data(self, data: Dict) -> None:
        """保存已上传的漂流瓶ID数据"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存已上传漂流瓶数据时出错: {str(e)}")
    
    def mark_as_uploaded(self, bottle_id: int) -> None:
        """标记漂流瓶为已上传"""
        data = self._load_data()
        if bottle_id not in data["uploaded_ids"]:
            data["uploaded_ids"].append(bottle_id)
            data["last_upload"] = datetime.now().isoformat()
            self._save_data(data)
    
    def is_uploaded(self, bottle_id: int) -> bool:
        """检查漂流瓶是否已上传"""
        data = self._load_data()
        return bottle_id in data["uploaded_ids"]
    
    def get_last_upload_time(self) -> str:
        """获取最后一次上传时间"""
        data = self._load_data()
        return data["last_upload"]
    
    def get_uploaded_count(self) -> int:
        """获取已上传的漂流瓶数量"""
        data = self._load_data()
        return len(data["uploaded_ids"]) 