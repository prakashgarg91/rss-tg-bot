import os
import sys
import logging
import telegram

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_bot_token():
    """Test if the bot token is valid"""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return False
    
    try:
        bot = telegram.Bot(token=token)
        bot_info = bot.get_me()
        logger.info(f"Bot connection successful: {bot_info.username}")
        return True
    except Exception as e:
        logger.error(f"Bot token test failed: {str(e)}")
        return False

def test_channels():
    """Test if the channels are valid and bot has access"""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    channels_env = os.environ.get('TELEGRAM_CHANNEL_IDS', '')
    channels = [channel.strip() for channel in channels_env.split(',') if channel.strip()]
    
    if not channels:
        logger.error("No channels configured")
        return False
    
    try:
        bot = telegram.Bot(token=token)
        logger.info(f"Testing access to {len(channels)} channels...")
        
        for channel in channels:
            try:
                chat = bot.get_chat(channel)
                logger.info(f"Access to {channel} ({chat.title}): OK")
            except Exception as e:
                logger.error(f"Cannot access {channel}: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"Channel test failed: {str(e)}")
        return False

def test_rss_feed():
    """Test if the RSS feed is accessible"""
    import feedparser
    
    feed_url = os.environ.get('RSS_FEED_URL')
    if not feed_url:
        logger.error("RSS_FEED_URL not set")
        return False
    
    try:
        feed = feedparser.parse(feed_url)
        if hasattr(feed, 'status') and feed.status != 200:
            logger.error(f"Feed error: status {feed.status}")
            return False
        
        entry_count = len(feed.entries)
        logger.info(f"Feed test successful: {entry_count} entries found")
        return True
    except Exception as e:
        logger.error(f"Feed test failed: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Testing configuration...")
    
    # Run all tests
    bot_test = test_bot_token()
    channels_test = test_channels()
    feed_test = test_rss_feed()
    
    if all([bot_test, channels_test, feed_test]):
        logger.info("All tests passed! Configuration is valid.")
        sys.exit(0)
    else:
        logger.error("Configuration test failed.")
        sys.exit(1)