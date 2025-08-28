"""
Logging configuration for GCC Scraper
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and emojis for different log levels"""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green  
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    # Emojis for different log levels
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '📋',
        'WARNING': '⚠️ ',
        'ERROR': '❌',
        'CRITICAL': '💥'
    }
    
    def format(self, record):
        # Add color and emoji to the log level
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(record.levelname, '')
        reset = self.COLORS['RESET']
        
        # Create the formatted message
        log_message = super().format(record)
        
        # Add color and emoji to console output only
        if hasattr(record, 'console_output') and record.console_output:
            return f"{color}{emoji} {log_message}{reset}"
        return log_message


class ProgressLogger:
    """Specialized logger for progress tracking with different output modes"""
    
    def __init__(self, name: str, console_level=logging.INFO, file_level=logging.DEBUG):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Console handler with progress formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_formatter = ColoredFormatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with detailed formatting
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{name}_{timestamp}.log"
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
    def progress(self, message: str):
        """Log progress message (INFO level, shows on console)"""
        # Mark for console output with color/emoji
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, '', 0, message, (), None
        )
        record.console_output = True
        self.logger.handle(record)
    
    def status(self, message: str):
        """Log status message (INFO level, console + file)"""
        self.logger.info(message)
    
    def info(self, message: str):
        """Log info message (for compatibility)"""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Log debug message (for compatibility)"""
        self.logger.debug(message)
    
    def detail(self, message: str):
        """Log detailed message (DEBUG level, file only)"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """Log warning message"""
        record = self.logger.makeRecord(
            self.logger.name, logging.WARNING, '', 0, message, (), None
        )
        record.console_output = True
        self.logger.handle(record)
    
    def error(self, message: str):
        """Log error message"""
        record = self.logger.makeRecord(
            self.logger.name, logging.ERROR, '', 0, message, (), None
        )
        record.console_output = True
        self.logger.handle(record)
    
    def success(self, message: str):
        """Log success message (custom green formatting)"""
        # Use INFO level but with success emoji
        success_msg = f"✅ {message}"
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, '', 0, success_msg, (), None
        )
        record.console_output = True
        self.logger.handle(record)


def setup_scraper_logging(scraper_name: str, verbose: bool = False) -> ProgressLogger:
    """Setup logging for a scraper with appropriate levels"""
    console_level = logging.DEBUG if verbose else logging.INFO
    return ProgressLogger(f"scraper.{scraper_name.lower()}", console_level=console_level)


def setup_app_logging(verbose: bool = False) -> ProgressLogger:
    """Setup logging for the main application"""
    console_level = logging.DEBUG if verbose else logging.INFO
    return ProgressLogger("gcc_scraper", console_level=console_level)