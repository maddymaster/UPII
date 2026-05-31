import yaml
import os
from typing import Dict, Any, List
from upii.core.config import config
from upii.core.logger import logger

class FeatureFlags:
    """Manages feature toggles for UPII v1.0+."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FeatureFlags, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        self.flags = {
            "ambient_memory": False,  # Safety default
            "auto_commit": False,     # Safety default
            "watch_paths": []         
        }
        
        # In a real app, this path would be in config. Here we assume generic location
        config_dir = os.path.dirname(config.db_path) # e.g. .upii/
        self.msg_path = os.path.join(config_dir, "features.yaml")

        if os.path.exists(self.msg_path):
            try:
                with open(self.msg_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                    # Merge with defaults
                    if "features" in data:
                        self.flags.update(data["features"])
                    logger.debug(f"Loaded feature flags from {self.msg_path}")
            except Exception as e:
                logger.error(f"Failed to load feature flags: {e}")
    
    def is_enabled(self, feature: str) -> bool:
        return self.flags.get(feature, False)
        
    def get_watch_paths(self) -> List[str]:
        return self.flags.get("watch_paths", [])

    def enable(self, feature: str):
        self.flags[feature] = True
        self._save()

    def disable(self, feature: str):
        self.flags[feature] = False
        self._save()
        
    def add_watch_path(self, path: str):
        paths = set(self.flags.get("watch_paths", []))
        paths.add(os.path.abspath(path))
        self.flags["watch_paths"] = list(paths)
        self._save()

    def _save(self):
        try:
            with open(self.msg_path, 'w') as f:
                yaml.dump({"features": self.flags}, f)
        except Exception as e:
            logger.error(f"Failed to save feature flags: {e}")

features = FeatureFlags()
