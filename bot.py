import os
import logging
import json
import pytz
import re
import asyncio
import feedparser
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, ConversationHandler, 
    MessageHandler, Filters, CallbackQueryHandler
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
(
    ADDING_FEED_URL, ADDING_FEED_CHANNEL, ADDING_FEED_TIMEZONE, ADDING_FEED_SCHEDULE,
    ADDING_FEED_FORMAT, REMOVING_FEED, EDITING_FEED, EDITING_FEED_FIELD,
    EDITING_FEED_VALUE
) = range(9)

# Define feed format templates
FEED_FORMATS = {
    "simple": "*{title}*\n\n[Read more]({link})",
    "detailed": "*{title}*\n\n{description}\n\n[Read more]({link})",
    "minimal": "[{title}]({link})",
    "custom": None  # Will be set during conversation
}

# Database setup
def setup_database():
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    # Create feeds table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feeds (
        id INTEGER PRIMARY KEY,
        url TEXT NOT NULL,
        channel TEXT NOT NULL,
        timezone TEXT DEFAULT 'UTC',
        schedule TEXT DEFAULT '2h',
        format_template TEXT DEFAULT 'detailed',
        custom_format TEXT,
        last_check TIMESTAMP,
        added_by INTEGER,
        active BOOLEAN DEFAULT 1
    )
    ''')
    
    # Create posted entries table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posted_entries (
        id INTEGER PRIMARY KEY,
        feed_id INTEGER,
        entry_id TEXT,
        posted_at TIMESTAMP,
        FOREIGN KEY (feed_id) REFERENCES feeds (id),
        UNIQUE(feed_id, entry_id)
    )
    ''')
    
    # Create admins table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        added_at TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# Feed management functions
def add_feed(url, channel, timezone, schedule, format_template, custom_format, user_id):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO feeds (url, channel, timezone, schedule, format_template, custom_format, added_by, last_check)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (url, channel, timezone, schedule, format_template, custom_format, user_id, datetime.now().isoformat()))
    
    feed_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return feed_id

def get_feeds():
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM feeds WHERE active = 1')
    feeds = cursor.fetchall()
    
    conn.close()
    return feeds

def get_feed(feed_id):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM feeds WHERE id = ?', (feed_id,))
    feed = cursor.fetchone()
    
    conn.close()
    return feed

def update_feed(feed_id, field, value):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(f'UPDATE feeds SET {field} = ? WHERE id = ?', (value, feed_id))
    
    conn.commit()
    conn.close()

def delete_feed(feed_id):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE feeds SET active = 0 WHERE id = ?', (feed_id,))
    
    conn.commit()
    conn.close()

def is_entry_posted(feed_id, entry_id):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT 1 FROM posted_entries WHERE feed_id = ? AND entry_id = ?', (feed_id, entry_id))
    exists = cursor.fetchone() is not None
    
    conn.close()
    return exists

def mark_entry_posted(feed_id, entry_id):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR IGNORE INTO posted_entries (feed_id, entry_id, posted_at)
    VALUES (?, ?, ?)
    ''', (feed_id, entry_id, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def update_last_check(feed_id):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE feeds SET last_check = ? WHERE id = ?', (datetime.now().isoformat(), feed_id))
    
    conn.commit()
    conn.close()

def add_admin(user_id, username):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR IGNORE INTO admins (user_id, username, added_at)
    VALUES (?, ?, ?)
    ''', (user_id, username, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = sqlite3.connect('rss_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    is_admin = cursor.fetchone() is not None
    
    # If no admins exist, make the first user an admin
    if not is_admin:
        cursor.execute('SELECT COUNT(*) FROM admins')
        count = cursor.fetchone()[0]
        if count == 0:
            is_admin = True
    
    conn.close()
    return is_admin

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    add_admin(user.id, user.username)  # Ensure user is in admins table
    
    welcome_message = (
        f"Welcome, {user.first_name}! 📢\n\n"
        "I'm your RSS Feed Manager Bot. I can help you publish RSS feed updates to your Telegram channels automatically.\n\n"
        "Here's what I can do:\n"
        "• Add new RSS feeds to monitor\n"
        "• Schedule automatic updates to your channels\n"
        "• Customize message formats\n"
        "• Manage time zones\n"
        "• View and edit your feed subscriptions\n\n"
        "Use /help to see all available commands."
    )
    
    keyboard = [
        [InlineKeyboardButton("Add Feed", callback_data="add_feed")],
        [InlineKeyboardButton("List Feeds", callback_data="list_feeds")],
        [InlineKeyboardButton("Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(welcome_message, reply_markup=reply_markup)

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
        "/removefeed - Remove a feed\n"
        "/editfeed - Edit a feed's settings\n\n"
        
        "*Testing & Monitoring:*\n"
        "/testfeed - Test a feed without posting\n"
        "/fetchnow - Fetch and post updates from a feed immediately\n"
        "/status - Check bot status and next scheduled runs\n\n"
        
        "*Admin Commands:*\n"
        "/addadmin - Add a new admin user\n\n"
        
        "For more help, contact the bot developer."
    )
    
    keyboard = [
        [InlineKeyboardButton("Add Feed", callback_data="add_feed")],
        [InlineKeyboardButton("List Feeds", callback_data="list_feeds")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

def add_feed_command(update: Update, context: CallbackContext) -> int:
    if not is_admin(update.effective_user.id):
        update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return ConversationHandler.END
        
    update.message.reply_text(
        "Let's add a new RSS feed! 📰\n\n"
        "Please send me the URL of the RSS feed."
    )
    return ADDING_FEED_URL

def add_feed_url(update: Update, context: CallbackContext) -> int:
    url = update.message.text.strip()
    context.user_data["feed_url"] = url
    
    try:
        # Test if the feed is valid
        feed = feedparser.parse(url)
        if hasattr(feed, 'bozo_exception') and feed.bozo_exception:
            update.message.reply_text(
                f"Error parsing the feed: {feed.bozo_exception}\n"
                "Please check the URL and try again."
            )
            return ADDING_FEED_URL
            
        if not feed.entries:
            update.message.reply_text(
                "The feed seems to be empty or not a valid RSS/Atom feed.\n"
                "Please check the URL and try again."
            )
            return ADDING_FEED_URL
            
        title = feed.feed.get('title', 'Untitled Feed')
        entries_count = len(feed.entries)
        
        update.message.reply_text(
            f"✅ Feed validated successfully!\n\n"
            f"*Title:* {title}\n"
            f"*Entries:* {entries_count}\n\n"
            "Now, please specify the Telegram channel where you want to post updates.\n"
            "Format: @channelname or -100123456789",
            parse_mode=ParseMode.MARKDOWN
        )
        return ADDING_FEED_CHANNEL
        
    except Exception as e:
        update.message.reply_text(
            f"Error validating feed: {str(e)}\n"
            "Please check the URL and try again."
        )
        return ADDING_FEED_URL

def add_feed_channel(update: Update, context: CallbackContext) -> int:
    channel = update.message.text.strip()
    context.user_data["feed_channel"] = channel
    
    # Offer time zone options
    keyboard = []
    for tz in ["UTC", "US/Eastern", "US/Pacific", "Europe/London", "Asia/Tokyo", "Asia/Kolkata"]:
        keyboard.append([InlineKeyboardButton(tz, callback_data=f"tz_{tz}")])
    keyboard.append([InlineKeyboardButton("Other (specify)", callback_data="tz_other")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "Great! Now select the time zone for this feed:",
        reply_markup=reply_markup
    )
    return ADDING_FEED_TIMEZONE

def add_feed_timezone_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    
    data = query.data
    if data == "tz_other":
        query.edit_message_text(
            "Please enter your preferred time zone (e.g., 'Europe/Berlin', 'Asia/Singapore').\n"
            "You can find all time zones at https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        )
        return ADDING_FEED_TIMEZONE
    else:
        timezone = data[3:]  # Remove 'tz_' prefix
        context.user_data["feed_timezone"] = timezone
        
        # Offer schedule options
        keyboard = [
            [InlineKeyboardButton("1 hour", callback_data="schedule_1h")],
            [InlineKeyboardButton("2 hours", callback_data="schedule_2h")],
            [InlineKeyboardButton("6 hours", callback_data="schedule_6h")],
            [InlineKeyboardButton("12 hours", callback_data="schedule_12h")],
            [InlineKeyboardButton("24 hours", callback_data="schedule_24h")],
            [InlineKeyboardButton("Custom", callback_data="schedule_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            f"Time zone set to {timezone}.\n"
            f"Now select how often you want to check for updates:",
            reply_markup=reply_markup
        )
        return ADDING_FEED_SCHEDULE

def add_feed_timezone_text(update: Update, context: CallbackContext) -> int:
    timezone = update.message.text.strip()
    try:
        pytz.timezone(timezone)
        context.user_data["feed_timezone"] = timezone
        
        # Offer schedule options
        keyboard = [
            [InlineKeyboardButton("1 hour", callback_data="schedule_1h")],
            [InlineKeyboardButton("2 hours", callback_data="schedule_2h")],
            [InlineKeyboardButton("6 hours", callback_data="schedule_6h")],
            [InlineKeyboardButton("12 hours", callback_data="schedule_12h")],
            [InlineKeyboardButton("24 hours", callback_data="schedule_24h")],
            [InlineKeyboardButton("Custom", callback_data="schedule_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"Time zone set to {timezone}.\n"
            f"Now select how often you want to check for updates:",
            reply_markup=reply_markup
        )
        return ADDING_FEED_SCHEDULE
    except Exception as e:
        update.message.reply_text(
            f"Invalid time zone: {str(e)}.\n"
            "Please enter a valid time zone (e.g., 'Europe/Berlin', 'Asia/Singapore')."
        )
        return ADDING_FEED_TIMEZONE

def add_feed_schedule_callback(update: Update, context: CallbackContext) -> int:
    query =