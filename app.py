# Add this at the very top of your app.py file
try:
    import fix_feedparser
except ImportError:
    pass
    
import os
import logging
import json
import pytz
import asyncio
import feedparser
import html
import re
from datetime import datetime, timedelta
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, ConversationHandler, 
    MessageHandler, Filters, CallbackQueryHandler
)
import threading
from pymongo import MongoClient

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB setup - uses MongoDB Atlas free tier
MONGODB_URI = os.environ.get("MONGODB_URI", "")
if not MONGODB_URI:
    logger.warning("MONGODB_URI not set! Using in-memory storage (data will be lost on restart).")
    # Use in-memory storage if MongoDB URL not provided
    feeds_collection = {}
    entries_collection = {}
    admins_collection = {}
    status_collection = {"system": {"last_check": datetime.now().isoformat(), 
                                   "entries_posted": 0, 
                                   "feeds_processed": 0,
                                   "errors": 0,
                                   "started_at": datetime.now().isoformat()}}
else:
    try:
        client = MongoClient(MONGODB_URI)
        db = client.get_database("rss_bot")
        feeds_collection = db.feeds
        entries_collection = db.entries
        admins_collection = db.admins
        status_collection = db.status
        
        # Create index on entries collection
        entries_collection.create_index([("feed_id", 1), ("entry_id", 1)], unique=True)
        
        # Create system status document if it doesn't exist
        if not status_collection.find_one({"_id": "system"}):
            status_collection.insert_one({
                "_id": "system",
                "last_check": datetime.now().isoformat(),
                "entries_posted": 0,
                "feeds_processed": 0,
                "errors": 0,
                "started_at": datetime.now().isoformat()
            })
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        # Fallback to in-memory storage
        feeds_collection = {}
        entries_collection = {}
        admins_collection = {}
        status_collection = {"system": {"last_check": datetime.now().isoformat(), 
                                       "entries_posted": 0, 
                                       "feeds_processed": 0,
                                       "errors": 0,
                                       "started_at": datetime.now().isoformat()}}

# Define conversation states
(
    ADDING_FEED_URL, ADDING_FEED_CHANNEL, ADDING_FEED_TIMEZONE, ADDING_FEED_SCHEDULE,
    ADDING_FEED_FORMAT, REMOVING_FEED, EDITING_FEED, EDITING_FEED_FIELD,
    EDITING_FEED_VALUE, ADDING_ADMIN
) = range(10)

# Define feed format templates
FEED_FORMATS = {
    "simple": "*{title}*\n\n[Read more]({link})",
    "detailed": "*{title}*\n\n{description}\n\n[Read more]({link})",
    "minimal": "[{title}]({link})",
    "custom": None  # Will be set during conversation
}

# Database helper functions
def is_admin(user_id):
    """Check if user is admin"""
    if isinstance(admins_collection, dict):
        return user_id in admins_collection or len(admins_collection) == 0
    else:
        # MongoDB check
        admin = admins_collection.find_one({"user_id": user_id})
        if admin:
            return True
        # If no admins exist, first user becomes admin
        if admins_collection.count_documents({}) == 0:
            return True
    return False

def add_admin(user_id, username):
    """Add a new admin"""
    if isinstance(admins_collection, dict):
        if user_id not in admins_collection:
            admins_collection[user_id] = {
                "user_id": user_id,
                "username": username,
                "added_at": datetime.now().isoformat()
            }
    else:
        # MongoDB insert
        if not admins_collection.find_one({"user_id": user_id}):
            admins_collection.insert_one({
                "user_id": user_id,
                "username": username,
                "added_at": datetime.now().isoformat()
            })

def get_feeds():
    """Get all active feeds"""
    if isinstance(feeds_collection, dict):
        return [f for f in feeds_collection.values() if f.get("active", True)]
    else:
        # MongoDB query
        return list(feeds_collection.find({"active": True}))

def get_feed(feed_id):
    """Get feed by ID"""
    if isinstance(feeds_collection, dict):
        return feeds_collection.get(feed_id)
    else:
        # MongoDB query
        return feeds_collection.find_one({"_id": feed_id})

def add_feed(url, channel, timezone, schedule, format_template, custom_format, user_id):
    """Add new feed"""
    feed_id = f"feed_{int(datetime.now().timestamp())}"
    feed_data = {
        "url": url,
        "channel": channel,
        "timezone": timezone,
        "schedule": schedule,
        "format_template": format_template,
        "custom_format": custom_format,
        "added_by": user_id,
        "last_check": datetime.now().isoformat(),
        "active": True,
        "created_at": datetime.now().isoformat()
    }
    
    if isinstance(feeds_collection, dict):
        feeds_collection[feed_id] = feed_data
        feeds_collection[feed_id]["_id"] = feed_id
    else:
        # MongoDB insert
        feed_data["_id"] = feed_id
        feeds_collection.insert_one(feed_data)
    
    return feed_id

def update_feed(feed_id, field, value):
    """Update feed field"""
    if isinstance(feeds_collection, dict):
        if feed_id in feeds_collection:
            feeds_collection[feed_id][field] = value
            return True
    else:
        # MongoDB update
        result = feeds_collection.update_one({"_id": feed_id}, {"$set": {field: value}})
        return result.modified_count > 0
    return False

def delete_feed(feed_id):
    """Delete feed (mark inactive)"""
    return update_feed(feed_id, "active", False)

def is_entry_posted(feed_id, entry_id):
    """Check if entry already posted"""
    entry_key = f"{feed_id}_{entry_id}"
    
    if isinstance(entries_collection, dict):
        return entry_key in entries_collection
    else:
        # MongoDB query
        return entries_collection.find_one({"feed_id": feed_id, "entry_id": entry_id}) is not None

def mark_entry_posted(feed_id, entry_id):
    """Mark entry as posted"""
    entry_key = f"{feed_id}_{entry_id}"
    entry_data = {
        "feed_id": feed_id,
        "entry_id": entry_id,
        "posted_at": datetime.now().isoformat()
    }
    
    if isinstance(entries_collection, dict):
        entries_collection[entry_key] = entry_data
    else:
        # MongoDB insert
        try:
            entries_collection.insert_one(entry_data)
        except Exception:
            # Entry might already exist, ignore
            pass

def update_last_check(feed_id):
    """Update last check time"""
    update_feed(feed_id, "last_check", datetime.now().isoformat())

def update_status(field, increment=1):
    """Update status counters"""
    if isinstance(status_collection, dict):
        if field in status_collection["system"] and isinstance(status_collection["system"][field], int):
            status_collection["system"][field] += increment
        else:
            status_collection["system"][field] = increment
    else:
        # MongoDB update
        status_collection.update_one(
            {"_id": "system"},
            {"$inc": {field: increment}}
        )

def get_status():
    """Get system status"""
    if isinstance(status_collection, dict):
        return status_collection.get("system", {})
    else:
        # MongoDB query
        return status_collection.find_one({"_id": "system"}) or {}

def clean_html(html_text):
    """Remove HTML tags from text"""
    if not html_text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<.*?>', '', html_text)
    # Fix common HTML entities
    clean = html.unescape(clean)
    # Limit length
    if len(clean) > 300:
        clean = clean[:297] + "..."
    return clean

def format_entry(entry, template):
    """Format entry with template"""
    title = entry.get('title', 'No Title')
    link = entry.get('link', '')
    
    # Get description/summary, clean HTML
    description = ''
    if 'description' in entry:
        description = clean_html(entry.description)
    elif 'summary' in entry:
        description = clean_html(entry.summary)
    
    try:
        message = template.format(
            title=title,
            link=link,
            description=description
        )
        return message
    except Exception as e:
        logger.error(f"Error formatting message: {str(e)}")
        # Fallback to simple format
        return f"*{title}*\n\n[Read more]({link})"

def parse_schedule(schedule):
    """Parse schedule string to minutes"""
    minutes = 120  # Default 2 hours
    
    if schedule.endswith('m'):
        try:
            minutes = int(schedule[:-1])
        except ValueError:
            pass
    elif schedule.endswith('h'):
        try:
            minutes = int(schedule[:-1]) * 60
        except ValueError:
            pass
    elif schedule.endswith('d'):
        try:
            minutes = int(schedule[:-1]) * 60 * 24
        except ValueError:
            pass
    
    return minutes

# RSS feed checking function
def check_feed_for_updates(context: CallbackContext, feed_id=None):
    """Check feed for updates and post new entries"""
    if feed_id:
        feeds = [get_feed(feed_id)]
        if not feeds[0]:
            logger.error(f"Feed {feed_id} not found")
            return
    else:
        feeds = get_feeds()
    
    for feed in feeds:
        feed_id = feed.get("_id")
        url = feed.get("url")
        channel = feed.get("channel")
        format_template = feed.get("format_template", "detailed")
        custom_format = feed.get("custom_format")
        
        if not feed.get("active", True):
            continue
            
        logger.info(f"Checking feed {feed_id}: {url}")
        
        try:
            # Parse the feed
            parsed_feed = feedparser.parse(url)
            
            if hasattr(parsed_feed, 'bozo_exception') and parsed_feed.bozo_exception:
                logger.error(f"Feed parsing error for {url}: {parsed_feed.bozo_exception}")
                update_status("errors")
                continue
            
            # Get the template
            if format_template == "custom" and custom_format:
                template = custom_format
            else:
                template = FEED_FORMATS.get(format_template, FEED_FORMATS["detailed"])
            
            # Get the 10 most recent entries
            entries = parsed_feed.entries[:10]
            posted_count = 0
            
            for entry in entries:
                entry_id = entry.get('id', entry.get('link', ''))
                if not entry_id:
                    continue
                    
                if is_entry_posted(feed_id, entry_id):
                    continue
                
                # Format and post the message
                message = format_entry(entry, template)
                
                try:
                    context.bot.send_message(
                        chat_id=channel,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=False
                    )
                    
                    mark_entry_posted(feed_id, entry_id)
                    posted_count += 1
                    
                    # Add a delay to avoid rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error posting to channel {channel}: {str(e)}")
                    update_status("errors")
            
            # Update status
            if posted_count > 0:
                logger.info(f"Posted {posted_count} new entries for feed {feed_id}")
                update_status("entries_posted", posted_count)
            
            # Update last check time
            update_last_check(feed_id)
            update_status("feeds_processed")
            
        except Exception as e:
            logger.error(f"Error checking feed {feed_id}: {str(e)}")
            update_status("errors")

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text(
            "Welcome! This is an RSS to Telegram bot.\n\n"
            "You are not currently an admin. Only admins can manage feeds.\n"
            "The first user to interact with the bot becomes an admin automatically."
        )
        return
    
    add_admin(user.id, user.username)  # Ensure user is in admins table
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Feed", callback_data="add_feed")],
        [InlineKeyboardButton("📋 List Feeds", callback_data="list_feeds")],
        [InlineKeyboardButton("📊 Status", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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
