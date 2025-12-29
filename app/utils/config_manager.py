"""Configuration manager for VulTrial settings"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages persistent configuration for VulTrial"""
    
    # Default configuration
    DEFAULT_CONFIG = {
        "model_type": "claude",
        "model_id": "claude-neptune-v3",
        "temperature": 0.7,
        "max_tokens": 32000,
        "max_turns": 4,
        "default_analysis_scope": "2",  # All functions mode
        "default_analysis_mode": "1",  # Detailed mode
        "auto_save_results": True,
        "output_directory": "output",
        "price_input_per_million": None,
        "price_output_per_million": None
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager
        
        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Store in workspace/.vultrial/config.json
            self.config_path = Path.cwd() / ".vultrial" / "config.json"
        
        self.config = self.load()
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file
        
        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            # Return default config if file doesn't exist
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Merge with defaults to ensure all keys exist
            merged_config = self.DEFAULT_CONFIG.copy()
            merged_config.update(config)
            
            return merged_config
        
        except Exception as e:
            print(f"Warning: Could not load config from {self.config_path}: {e}")
            print("Using default configuration.")
            return self.DEFAULT_CONFIG.copy()
    
    def save(self):
        """Save configuration to file"""
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write config
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, sort_keys=True)
            
            return True
        
        except Exception as e:
            print(f"Error: Could not save config to {self.config_path}: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value and save"""
        self.config[key] = value
        self.save()
    
    def update(self, updates: Dict[str, Any]):
        """Update multiple configuration values at once"""
        self.config.update(updates)
        self.save()
    
    def reset(self):
        """Reset to default configuration"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()
    
    def get_model_config(self) -> Dict[str, Any]:
        """Get model-specific configuration"""
        return {
            "model_type": self.get("model_type"),
            "model_id": self.get("model_id"),
            "temperature": self.get("temperature"),
            "max_tokens": self.get("max_tokens")
        }
    
    def set_model_config(self, model_type: str, model_id: str, 
                        temperature: Optional[float] = None,
                        max_tokens: Optional[int] = None):
        """Set model configuration"""
        updates = {
            "model_type": model_type,
            "model_id": model_id
        }
        
        if temperature is not None:
            updates["temperature"] = temperature
        if max_tokens is not None:
            updates["max_tokens"] = max_tokens
        
        self.update(updates)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration"""
        return self.config.copy()
    
    def get_config_path(self) -> str:
        """Get path to config file"""
        return str(self.config_path)

