#!/usr/bin/env python3
"""
logger.py - Logging Module for sipwise-backup
Handles all logging operations including:
- Log file creation and rotation
- Log retention policy (matching backup retention)
- Multiple log levels (DEBUG, INFO, WARN, ERROR, SUCCESS)
- Console and file output
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import yaml


class SipwiseLogger:
    """Centralized logging for sipwise-backup application"""
    
    # Custom log level for SUCCESS
    SUCCESS = 25  # Between INFO (20) and WARNING (30)
    
    def __init__(self, config_path: str = "/opt/sipwise-backup/config.yml"):
        """
        Initialize the SipwiseLogger
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.log_dir = Path("/opt/sipwise-backup/log")
        self._ensure_log_dir()
        
        # Register custom SUCCESS level
        logging.addLevelName(self.SUCCESS, "SUCCESS")
        
        # Set up logger
        self.logger = logging.getLogger("sipwise-backup")
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers = []
        
        # Add file handler
        self._setup_file_handler()
        
        # Add console handler
        self._setup_console_handler()
    
    def _load_config(self) -> dict:
        """Load configuration from config.yml"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    
    def _ensure_log_dir(self):
        """Ensure the log directory exists"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_log_filename(self) -> str:
        """Get the log filename for today (DDMMYYYY.log)"""
        return datetime.now().strftime("%d%m%Y.log")
    
    def _get_log_filepath(self) -> Path:
        """Get the full path to today's log file"""
        return self.log_dir / self._get_log_filename()
    
    def _setup_file_handler(self):
        """Set up file handler for logging to daily log file"""
        log_file = self._get_log_filepath()
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Format: [TIMESTAMP] [LEVEL] [MODULE] Message
        file_format = logging.Formatter(
            '[%(asctime)s] [%(levelname)-8s] [%(module)-12s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)
    
    def _setup_console_handler(self):
        """Set up console handler for stdout output"""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Simpler format for console
        console_format = logging.Formatter('[%(levelname)-8s] %(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str, module: str = ""):
        """Log debug message"""
        extra = {'module': module} if module else {}
        self.logger.debug(message, extra=extra if extra else None)
    
    def info(self, message: str, module: str = ""):
        """Log info message"""
        self.logger.info(message)
    
    def warn(self, message: str, module: str = ""):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str, module: str = ""):
        """Log error message"""
        self.logger.error(message)
    
    def success(self, message: str, module: str = ""):
        """Log success message"""
        self.logger.log(self.SUCCESS, message)
    
    def apply_retention_policy(self):
        """
        Apply retention policy to log files
        
        Deletes log files older than the configured retention days
        (uses same retention policy as backups)
        """
        backup_config = self.config.get('backup', {})
        retention_config = backup_config.get('retention', {})
        retention_days = retention_config.get('days', 30)
        
        self.info(f"Applying log retention policy (keep last {retention_days} days)")
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        for log_file in self.log_dir.glob("*.log"):
            try:
                # Parse date from filename (DDMMYYYY.log)
                date_str = log_file.stem
                file_date = datetime.strptime(date_str, "%d%m%Y")
                
                if file_date < cutoff_date:
                    log_file.unlink()
                    self.debug(f"Deleted old log file: {log_file.name}")
                    deleted_count += 1
            except ValueError:
                # Skip files that don't match the date format
                continue
        
        if deleted_count > 0:
            self.info(f"Deleted {deleted_count} old log file(s)")
        else:
            self.debug("No old log files to delete")


# Global logger instance
_logger_instance: Optional[SipwiseLogger] = None


def get_logger(config_path: str = "/opt/sipwise-backup/config.yml") -> SipwiseLogger:
    """
    Get or create the global logger instance
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        SipwiseLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SipwiseLogger(config_path)
    return _logger_instance


# Convenience functions
def debug(message: str, module: str = ""):
    get_logger().debug(message, module)

def info(message: str, module: str = ""):
    get_logger().info(message, module)

def warn(message: str, module: str = ""):
    get_logger().warn(message, module)

def error(message: str, module: str = ""):
    get_logger().error(message, module)

def success(message: str, module: str = ""):
    get_logger().success(message, module)
