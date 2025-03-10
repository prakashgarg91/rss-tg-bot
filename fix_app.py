# Import fix for feedparser compatibility with Python 3.13+
try:
    import fix_feedparser
except ImportError:
    pass

import os
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update, ParseMode
import feedparser
import time
import json
import pytz
from datetime import datetime
import threading

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Get bot token from environment variable
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("No TELEGRAM_BOT_TOKEN found in environment variables!")
    exit(1)

# In-memory storage for feeds
feeds = {}

# Admin list
ADMIN_IDS = [int(id) for id in os.environ.get('ADMIN_IDS', '').split(',') if id.strip()]
if not ADMIN_IDS:
    # If no admin IDs are set, consider the first user as admin
    logger.warning("No ADMIN_IDS set. First user to interact will become admin.")

def is_admin(user_id):
    return len(ADMIN_IDS) == 0 or user_id in ADMIN_IDS

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # If no admins yet, make this user an admin
    if not ADMIN_IDS and user.id not in ADMIN_IDS:
        ADMIN_IDS.append(user.id)
        logger.info(f"Added first user {user.id} as admin")
    
    if not is_admin(user.id):
        update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    update.message.reply_text(f"Hello {user.first_name}! I'm a RSS Feed Bot. Use /help to see available commands.")

def help_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
        
    help_text = (
        "📚 *RSS Feed Manager Bot Commands*\n\n"
        "*Basic Commands:*\n"
        "/start - Start the bot and show main menu\n"
        "/help - Show this help message\n\n"
        
        "*Feed Management:*\n"
        "/addfeed - Add a new RSS feed to monitor\n"
        "/listfeeds - List all active feeds\n"
        "/removefeed - Remove a feed\n\n"
        
        "*Status:*\n"
        "/status - Check bot status\n\n"
        
        "For more help, contact the bot developer."
    )
    
    update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

def status(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    feed_count = len(feeds)
    
    status_text = (
        "🤖 *Bot Status*\n\n"
        f"Active feeds: {feed_count}\n"
        f"Bot running since: {start_time_str}\n"
        f"Current time: {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    )
    
    update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

# Record when the bot started
start_time = datetime.now(pytz.UTC)
start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S UTC")

def main() -> None:
    # Create the Updater and pass it your bot's token
    updater = Updater(BOT_TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Basic command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("status", status))
    
    # Log successful startup
    logger.info("Bot started successfully!")
    
    # Periodically log to keep the process alive
    def keepalive_log():
        while True:
            logger.info("Bot is still running")
            time.sleep(3600)  # Log once per hour
    
    # Start keepalive thread
    threading.Thread(target=keepalive_log, daemon=True).start()
    
    # Start the Bot
    updater.start_polling()
    
    # Run the bot until the user presses Ctrl-C or the process receives SIGINT, SIGTERM or SIGABRT
    updater.idle()

if __name__ == '__main__':
    logger.info("Starting bot...")
    main()