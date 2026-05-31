import abc
import os
import yaml
import logging
from typing import Dict, Any, List, Optional
from upii.core.config import config
from upii.core.concurrency import SafeRunner
from upii.ambient.storage import StagingDB

logger = logging.getLogger("upii.ambient.sources")

class Source(abc.ABC):
    """Abstract Base Class for Ambient Sources."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.is_running = False
        self.config: Dict[str, Any] = {}
        self.storage = StagingDB()
        
    @abc.abstractmethod
    def start(self):
        """Start the passive capture loop."""
        pass
        
    @abc.abstractmethod
    def stop(self):
        """Stop capture."""
        pass
        
    def configure(self, new_config: Dict[str, Any]):
        """Update configuration."""
        self.config.update(new_config)

class SourceRegistry:
    """Manages lifecycle and configuration of sources."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SourceRegistry, cls).__new__(cls)
            cls._instance._init()
        return cls._instance
        
    def _init(self):
        self.sources: Dict[str, Source] = {}
        self.enabled_state: Dict[str, bool] = {} # Persistent state
        self.config_path = os.path.join(os.path.dirname(config.db_path), "sources.yaml")
        self._load_state()
        
    def register(self, source: Source):
        """Register a source plugin."""
        self.sources[source.name] = source
        # Load config if exists
        # (For MVP we rely on defaults or manual config injection)
        logger.debug(f"Registered source: {source.name}")
        
    def is_enabled(self, name: str) -> bool:
        return self.enabled_state.get(name, False)
        
    def enable(self, name: str):
        if name not in self.sources:
            raise ValueError(f"Source {name} not found")
            
        self.enabled_state[name] = True
        self.sources[name].start()
        self._save_state()
        self.sources[name].storage.log_audit(name, "enable", {"status": "started"})
        logger.info(f"Source enabled: {name}")

    def disable(self, name: str):
        if name not in self.sources:
             raise ValueError(f"Source {name} not found")
             
        self.enabled_state[name] = False
        self.sources[name].stop()
        self._save_state()
        self.sources[name].storage.log_audit(name, "disable", {"status": "stopped"})
        logger.info(f"Source disabled: {name}")
        
    def _load_state(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                    self.enabled_state = data.get("enabled", {})
                    # Ideally we also load per-source config here
            except Exception as e:
                logger.error(f"Failed to load source state: {e}")
                
    def _save_state(self):
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump({"enabled": self.enabled_state}, f)
        except Exception as e:
            logger.error(f"Failed to save source state: {e}")
            
    def get_all(self) -> List[Dict]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "enabled": self.is_enabled(s.name),
                "running": s.is_running
            } 
            for s in self.sources.values()
        ]

registry = SourceRegistry()
