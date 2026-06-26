"""
Logging configuration
"""

import logging
import logging.handlers
import os
from src.utils.config import Config

# Create logs directory
os.makedirs('logs', exist_ok=True)

# Create logger
logger = logging.getLogger('bank_fraud')
logger.setLevel(getattr(logging, Config.LOG_LEVEL))

# File handler with rotation
file_handler = logging.handlers.RotatingFileHandler(
    Config.LOG_FILE,
    maxBytes=Config.MAX_LOG_SIZE,
    backupCount=Config.BACKUP_COUNT
)
file_handler.setLevel(getattr(logging, Config.LOG_LEVEL))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, Config.LOG_LEVEL))

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(f'bank_fraud.{name}')
