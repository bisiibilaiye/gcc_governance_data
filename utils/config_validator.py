from typing import Dict, Any, List, Optional, Union
import logging
from pathlib import Path


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigValidator:
    """Validates exchange and common configuration schemas."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def validate_common_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate common configuration schema."""
        errors = []
        
        # Required sections
        required_sections = ['scraping', 'browser', 'logging', 'output']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: '{section}'")
                
        # Scraping section validation
        if 'scraping' in config:
            scraping = config['scraping']
            scraping_errors = self._validate_scraping_config(scraping)
            errors.extend([f"scraping.{err}" for err in scraping_errors])
            
        # Browser section validation
        if 'browser' in config:
            browser = config['browser']
            browser_errors = self._validate_browser_config(browser)
            errors.extend([f"browser.{err}" for err in browser_errors])
            
        # Logging section validation
        if 'logging' in config:
            logging_config = config['logging']
            logging_errors = self._validate_logging_config(logging_config)
            errors.extend([f"logging.{err}" for err in logging_errors])
            
        return errors
        
    def validate_exchange_config(self, config: Dict[str, Any], exchange_name: str) -> List[str]:
        """Validate exchange-specific configuration schema."""
        errors = []
        
        # Required sections
        required_sections = ['exchange', 'selectors']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: '{section}'")
                
        # Exchange section validation
        if 'exchange' in config:
            exchange = config['exchange']
            exchange_errors = self._validate_exchange_info(exchange)
            errors.extend([f"exchange.{err}" for err in exchange_errors])
            
        # Selectors section validation
        if 'selectors' in config:
            selectors = config['selectors']
            selector_errors = self._validate_selectors(selectors, exchange_name)
            errors.extend([f"selectors.{err}" for err in selector_errors])
            
        return errors
        
    def _validate_scraping_config(self, scraping: Dict[str, Any]) -> List[str]:
        """Validate scraping configuration."""
        errors = []
        
        # Required fields with validation
        validations = {
            'max_retries': (int, lambda x: 1 <= x <= 10, "must be between 1 and 10"),
            'retry_delay_seconds': (Union[int, float], lambda x: 0 <= x <= 60, "must be between 0 and 60"),
            'default_timeout': (int, lambda x: 5 <= x <= 300, "must be between 5 and 300 seconds"),
            'page_load_wait': (Union[int, float], lambda x: 0 <= x <= 30, "must be between 0 and 30 seconds")
        }
        
        for field, (expected_type, validator, error_msg) in validations.items():
            if field in scraping:
                value = scraping[field]
                if not isinstance(value, expected_type):
                    errors.append(f"{field} must be {expected_type.__name__}")
                elif not validator(value):
                    errors.append(f"{field} {error_msg}")
                    
        return errors
        
    def _validate_browser_config(self, browser: Dict[str, Any]) -> List[str]:
        """Validate browser configuration."""
        errors = []
        
        # Headless validation
        if 'headless' in browser and not isinstance(browser['headless'], bool):
            errors.append("headless must be a boolean")
            
        # Window size validation
        if 'window_size' in browser:
            window_size = browser['window_size']
            if not isinstance(window_size, str):
                errors.append("window_size must be a string")
            elif not self._validate_window_size(window_size):
                errors.append("window_size must be in format 'WIDTHxHEIGHT' or 'WIDTH,HEIGHT'")
                
        # User agent validation
        if 'user_agent' in browser:
            user_agent = browser['user_agent']
            if not isinstance(user_agent, str) or len(user_agent.strip()) == 0:
                errors.append("user_agent must be a non-empty string")
                
        return errors
        
    def _validate_logging_config(self, logging_config: Dict[str, Any]) -> List[str]:
        """Validate logging configuration."""
        errors = []
        
        # Log level validation
        if 'level' in logging_config:
            level = logging_config['level']
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if level not in valid_levels:
                errors.append(f"level must be one of: {', '.join(valid_levels)}")
                
        # Format validation
        if 'format' in logging_config:
            format_str = logging_config['format']
            if not isinstance(format_str, str) or len(format_str.strip()) == 0:
                errors.append("format must be a non-empty string")
                
        return errors
        
    def _validate_exchange_info(self, exchange: Dict[str, Any]) -> List[str]:
        """Validate exchange information."""
        errors = []
        
        # Required fields
        required_fields = ['name', 'code', 'base_url']
        for field in required_fields:
            if field not in exchange:
                errors.append(f"Missing required field: '{field}'")
            elif not isinstance(exchange[field], str) or len(exchange[field].strip()) == 0:
                errors.append(f"{field} must be a non-empty string")
                
        # URL validation
        url_fields = ['base_url', 'listing_url']
        for field in url_fields:
            if field in exchange:
                url = exchange[field]
                if not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
                    errors.append(f"{field} must be a valid HTTP/HTTPS URL")
                    
        return errors
        
    def _validate_selectors(self, selectors: Dict[str, Any], exchange_name: str) -> List[str]:
        """Validate selectors configuration."""
        errors = []
        
        # Required selectors for most exchanges
        common_required = ['company_name', 'company_cards']
        
        # Exchange-specific required selectors (updated to match actual config)
        exchange_required = {
            'adx': ['sector', 'listing_date', 'board_section'],
            'bahrain': ['companies_table'],
            'dfm': ['company_table'],
            'kuwait': ['company_listing'],
            'oman': ['company_grid'],
            'saudi': ['company_list']
        }
        
        # For backwards compatibility, also accept alternative selector names
        selector_alternatives = {
            'company_cards': ['company_link', 'companies_table', 'company_listing', 'company_grid', 'company_list', 'company_list_selectors'],
            'company_table': ['companies_table', 'company_listing', 'company_grid', 'company_list'],
            'company_listing': ['companies_table', 'company_table', 'company_grid', 'company_list'],
            'company_grid': ['companies_table', 'company_table', 'company_listing', 'company_list'],
            'company_list': ['companies_table', 'company_table', 'company_listing', 'company_grid', 'company_list_selectors']
        }
        
        required_selectors = common_required + exchange_required.get(exchange_name.lower(), [])
        
        for selector in required_selectors:
            # Check if the selector exists directly
            if selector in selectors:
                selector_value = selectors[selector]
                if isinstance(selector_value, list):
                    if not selector_value or any(not isinstance(s, str) or len(s.strip()) == 0 for s in selector_value):
                        errors.append(f"selector '{selector}' list contains empty or invalid values")
                elif isinstance(selector_value, str):
                    if len(selector_value.strip()) == 0:
                        errors.append(f"selector '{selector}' cannot be empty")
                else:
                    errors.append(f"selector '{selector}' must be string or list of strings")
            else:
                # Check if any alternative exists
                alternatives = selector_alternatives.get(selector, [])
                found_alternative = False
                for alt in alternatives:
                    if alt in selectors:
                        found_alternative = True
                        break
                        
                if not found_alternative:
                    errors.append(f"Missing required selector: '{selector}' (or alternatives: {alternatives})")
                    
        return errors
        
    def _validate_window_size(self, window_size: str) -> bool:
        """Validate window size format."""
        try:
            parts = window_size.replace('x', ',').split(',')
            if len(parts) != 2:
                return False
            width, height = map(int, parts)
            return 100 <= width <= 5000 and 100 <= height <= 5000
        except (ValueError, TypeError):
            return False
            
    def validate_config_file(self, config_path: Path, config_type: str, exchange_name: Optional[str] = None) -> None:
        """Validate a configuration file and raise exception if invalid."""
        if not config_path.exists():
            raise ConfigValidationError(f"Configuration file not found: {config_path}")
            
        try:
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"Invalid YAML in {config_path}: {e}")
            
        if config_type == 'common':
            errors = self.validate_common_config(config)
        elif config_type == 'exchange':
            if not exchange_name:
                raise ValueError("exchange_name required for exchange config validation")
            errors = self.validate_exchange_config(config, exchange_name)
        else:
            raise ValueError(f"Unknown config type: {config_type}")
            
        if errors:
            error_msg = f"Configuration validation errors in {config_path}:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ConfigValidationError(error_msg)
            
        self.logger.info(f"Configuration validated successfully: {config_path}")