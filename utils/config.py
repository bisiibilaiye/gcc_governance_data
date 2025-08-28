import yaml
import os
import logging
from typing import Dict, Any, List
from pathlib import Path
from .config_validator import ConfigValidator, ConfigValidationError


class ConfigManager:
    """Manages configuration loading, validation, and merging."""
    
    def __init__(self, config_dir: str = "config", validate: bool = True):
        self.config_dir = Path(config_dir)
        self.validator = ConfigValidator() if validate else None
        self.logger = logging.getLogger(__name__)
        self.common_config = self._load_common_config()
        
    def _load_common_config(self) -> Dict[str, Any]:
        """Load and validate common configuration."""
        common_path = self.config_dir / "common.yaml"
        if not common_path.exists():
            self.logger.warning(f"Common config not found: {common_path}")
            return {}
            
        try:
            if self.validator:
                self.validator.validate_config_file(common_path, 'common')
                
            with open(common_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                self.logger.info("Common configuration loaded and validated successfully")
                return config
        except ConfigValidationError as e:
            self.logger.error(f"Common configuration validation failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading common config: {e}")
            raise
        
    def load_exchange_config(self, exchange: str) -> Dict[str, Any]:
        """Load and validate configuration for a specific exchange."""
        exchange_path = self.config_dir / "exchanges" / f"{exchange.lower()}.yaml"
        
        if not exchange_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {exchange_path}")
            
        try:
            if self.validator:
                self.validator.validate_config_file(exchange_path, 'exchange', exchange.lower())
                
            with open(exchange_path, 'r') as f:
                exchange_config = yaml.safe_load(f) or {}
                
            # Merge with common config (exchange config takes precedence)
            merged_config = self._deep_merge(self.common_config.copy(), exchange_config)
            self.logger.info(f"Exchange configuration loaded and validated successfully: {exchange}")
            return merged_config
        except ConfigValidationError as e:
            self.logger.error(f"Exchange configuration validation failed for {exchange}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading exchange config for {exchange}: {e}")
            raise
        
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def get_supported_exchanges(self) -> List[str]:
        """Get list of supported exchanges."""
        exchanges_dir = self.config_dir / "exchanges"
        if not exchanges_dir.exists():
            return []
            
        exchanges = []
        for config_file in exchanges_dir.glob("*.yaml"):
            exchange_name = config_file.stem.upper()
            exchanges.append(exchange_name)
            
        return sorted(exchanges)