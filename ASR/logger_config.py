import logging
import sys
from pathlib import Path

def setup_logger():
    """Setup unified logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # Use UTF-8 encoding for console output
            logging.StreamHandler(sys.stdout),
            # Use UTF-8 encoding for file output
            logging.FileHandler(log_dir / "app.log", encoding='utf-8')
        ]
    )
    
    # Create and return logger
    return logging.getLogger(__name__)

# Create a global logger instance
logger = setup_logger() 