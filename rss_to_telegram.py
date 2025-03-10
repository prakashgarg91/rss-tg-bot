import os
import time
import json
import logging
import feedparser
from datetime import datetime
import telegram
from telegram.error import TelegramError

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration - load from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
RSS_FEED_URL = os.environ.get('RSS_FEED_URL')
HISTORY_FILE = 'posted_entries.json'

# Get telegram channels from environment variable (comma-separated list)
telegram_channels_env = os.environ.get('TELEGRAM_CHANNEL_IDS', '')
TELEGRAM_CHANNEL_IDS = [channel.strip() for channel in telegram_channels_env.split(',') if channel.strip()]

def load_history():
    """Load history of previously posted entries"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading history: {str(e)}")
        return {}

def save_history(history):
    """Save history of posted entries"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f)
    except Exception as e:
        logger.error(f"Error saving history: {str(e)}")

def post_to_telegram(entry):
    """Post a message to all configured Telegram channels"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram bot token not configured")
        return False
    
    if not TELEGRAM_CHANNEL_IDS:
        logger.error("No Telegram channels configured")
        return False

    try:
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Format message
        message = f"*{entry.get('title', 'No Title')}*\n\n"
        if entry.get('summary'):
            # Clean up summary and limit length
            summary = entry.get('summary', '')
            if len(summary) > 200:
                summary = summary[:197] + "..."
            message += f"{summary}\n\n"
        
        message += f"[Read more]({entry.get('link', '')})"
        
        success_count = 0
        for channel in TELEGRAM_CHANNEL_IDS:
            try:
                bot.send_message(
                    chat_id=channel, 
                    text=message, 
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                success_count += 1
                # Add a small delay between messages to avoid rate limiting
                time.sleep(1)
            except TelegramError as te:
                logger.error(f"Error posting to channel {channel}: {str(te)}")
        
        logger.info(f"Posted to {success_count}/{len(TELEGRAM_CHANNEL_IDS)} channels")
        return success_count > 0
    except Exception as e:
        logger.error(f"Error in post_to_telegram: {str(e)}")
        return False

def parse_rss_feed():
    """Parse RSS feed and post new entries"""
    if not RSS_FEED_URL:
        logger.error("RSS feed URL not configured")
        return

    try:
        logger.info(f"Fetching RSS feed: {RSS_FEED_URL}")
        feed = feedparser.parse(RSS_FEED_URL)
        
        if hasattr(feed, 'status') and feed.status != 200:
            logger.error(f"Failed to fetch RSS feed. Status: {feed.status}")
            return
        
        if not feed.entries:
            logger.info("No entries found in the feed")
            return
        
        history = load_history()
        current_time = datetime.utcnow().isoformat()
        posted_count = 0
        
        for entry in feed.entries[:10]:  # Process the 10 most recent entries
            entry_id = entry.get('id', entry.get('link', ''))
            
            # Skip if already posted
            if entry_id in history:
                continue
                
            logger.info(f"New entry found: {entry.get('title', 'No Title')}")
            
            if post_to_telegram(entry):
                history[entry_id] = current_time
                posted_count += 1
                
        if posted_count > 0:
            logger.info(f"Posted {posted_count} new entries")
            save_history(history)
        else:
            logger.info("No new entries to post")
            
    except Exception as e:
        logger.error(f"Error parsing RSS feed: {str(e)}")

def main():
    """Main function to run the script"""
    logger.info("Starting RSS to Telegram script")
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return
        
    if not RSS_FEED_URL:
        logger.error("RSS_FEED_URL environment variable not set")
        return
        
    if not TELEGRAM_CHANNEL_IDS:
        logger.error("TELEGRAM_CHANNEL_IDS environment variable not set or empty")
        return
        
    logger.info(f"Configured to post to {len(TELEGRAM_CHANNEL_IDS)} channels")
    parse_rss_feed()
    logger.info("Script execution completed")

if __name__ == "__main__":
    main()