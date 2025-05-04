import logging
import sys
from pathlib import Path
from config import LOG_LEVEL, LOG_FILE

def setup_logger(name=None):
    """Setup unified logging configuration"""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # Use UTF-8 encoding for console output
            logging.StreamHandler(sys.stdout),
            # Use UTF-8 encoding for file output
            logging.FileHandler(LOG_FILE, encoding='utf-8')
        ]
    )
    
    # Create and return logger
    return logging.getLogger(name)

# Create a global logger instance
logger = setup_logger() 