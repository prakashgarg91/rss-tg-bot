import os

# Default configuration
DEFAULT_CONFIG = {
    "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "feeds": [
        {
            "url": os.environ.get("RSS_FEED_URL", ""),
            "channels": os.environ.get("TELEGRAM_CHANNEL_IDS", "").split(","),
            "last_check": None,
            "post_limit": 5  # Maximum number of posts per check
        }
    ],
    "check_interval": 7200,  # 2 hours in seconds
}

def get_config():
    """Load configuration from environment or use defaults"""
    # You could extend this to load from a database or a file
    return DEFAULT_CONFIG