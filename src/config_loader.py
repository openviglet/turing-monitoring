"""
Configuration Loader - Manages application settings
"""

import os
from configparser import ConfigParser


class ConfigLoader:
    """Configuration manager with support for INI files and environment variables"""
    
    def __init__(self, config_file: str = 'config.ini'):
        """
        Initialize configuration loader
        
        Args:
            config_file: Path to INI configuration file
        """
        self.config = ConfigParser()
        self.config_file = config_file
        
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        self.config.read(config_file, encoding='utf-8')
    
    def get(self, section: str, key: str, fallback: str = None) -> str:
        """
        Get configuration value (prioritizes environment variables)
        
        Priority order:
        1. Environment variable (SECTION_KEY format)
        2. config.ini file
        3. fallback value
        
        Args:
            section: Configuration section
            key: Configuration key
            fallback: Fallback value if not found
            
        Returns:
            Configuration value
        """
        # Check environment variable first
        env_key = f"{section}_{key}".upper()
        env_value = os.getenv(env_key)
        
        if env_value is not None:
            return env_value
        
        # Then check INI file
        try:
            return self.config.get(section, key)
        except:
            return fallback
    
    def get_int(self, section: str, key: str, fallback: int = None) -> int:
        """Get configuration as integer"""
        value = self.get(section, key, str(fallback) if fallback is not None else None)
        return int(value) if value is not None else None
    
    def get_float(self, section: str, key: str, fallback: float = None) -> float:
        """Get configuration as float"""
        value = self.get(section, key, str(fallback) if fallback is not None else None)
        return float(value) if value is not None else None
    
    def get_bool(self, section: str, key: str, fallback: bool = None) -> bool:
        """Get configuration as boolean"""
        value = self.get(section, key, str(fallback) if fallback is not None else None)
        if value is None:
            return None
        return value.lower() in ('true', 'yes', '1', 'on')
