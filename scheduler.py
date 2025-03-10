import time
import os
import logging
from datetime import datetime
from rss_to_telegram import parse_rss_feed

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get check interval from environment or default to 2 hours
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', 7200))  # Default: 2 hours in seconds

def start_scheduler():
    """Start the scheduler loop"""
    logger.info(f"Starting scheduler with {CHECK_INTERVAL} seconds interval")
    
    while True:
        try:
            start_time = time.time()
            logger.info(f"Running scheduled task at {datetime.now().isoformat()}")
            
            # Run the RSS parser
            parse_rss_feed()
            
            # Calculate sleep time to maintain consistent intervals
            elapsed = time.time() - start_time
            sleep_time = max(1, CHECK_INTERVAL - elapsed)
            
            logger.info(f"Task completed in {elapsed:.2f} seconds. Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            
        except Exception as e:
            logger.error(f"Error in scheduler: {str(e)}")
            # Sleep for a while before retrying
            time.sleep(60)

if __name__ == "__main__":
    start_scheduler()