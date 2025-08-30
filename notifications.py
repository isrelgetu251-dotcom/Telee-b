"""
Smart Notifications System for University Confession Bot
Features: Personalized notifications, category subscriptions, trending alerts, daily digest
"""

import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import DB_PATH, CATEGORIES
from utils import escape_markdown_text, truncate_text

logger = logging.getLogger(__name__)

class NotificationEngine:
    def __init__(self):
        self.init_notification_tables()
    
    def init_notification_tables(self):
        """Initialize notification-related database tables"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # User notification preferences
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    user_id INTEGER PRIMARY KEY,
                    comment_notifications BOOLEAN DEFAULT 1,
                    favorite_categories TEXT DEFAULT '',
                    daily_digest BOOLEAN DEFAULT 1,
                    trending_alerts BOOLEAN DEFAULT 1,
                    digest_time TEXT DEFAULT '18:00',
                    notification_frequency TEXT DEFAULT 'immediate',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Notification history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    related_post_id INTEGER,
                    related_comment_id INTEGER,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    delivered BOOLEAN DEFAULT 0,
                    clicked BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # User subscriptions to posts (for comment notifications)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    post_id INTEGER,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (post_id) REFERENCES posts (id),
                    UNIQUE(user_id, post_id)
                )
            ''')
            
            # Trending posts cache for alerts
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trending_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER,
                    trend_score REAL,
                    category TEXT,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified_users TEXT DEFAULT '',
                    FOREIGN KEY (post_id) REFERENCES posts (id)
                )
            ''')
            
            conn.commit()
            logger.info("Notification database tables initialized")

# Initialize global notification engine
notification_engine = NotificationEngine()

def get_user_preferences(user_id: int) -> Dict:
    """Get user notification preferences"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT comment_notifications, favorite_categories, daily_digest, 
                   trending_alerts, digest_time, notification_frequency
            FROM notification_preferences WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        
        logger.info(f"get_user_preferences for user {user_id}: raw result = {result}")
        
        if result:
            prefs = {
                'comment_notifications': bool(result[0]),
                'favorite_categories': result[1].split(',') if result[1] else [],
                'daily_digest': bool(result[2]),
                'trending_alerts': bool(result[3]),
                'digest_time': result[4],
                'notification_frequency': result[5]
            }
            logger.info(f"Parsed preferences for user {user_id}: {prefs}")
            return prefs
        else:
            # Create default preferences
            cursor.execute('''
                INSERT OR IGNORE INTO notification_preferences 
                (user_id, comment_notifications, daily_digest, trending_alerts)
                VALUES (?, 1, 1, 1)
            ''', (user_id,))
            conn.commit()
            
            default_prefs = {
                'comment_notifications': True,
                'favorite_categories': [],
                'daily_digest': True,
                'trending_alerts': True,
                'digest_time': '18:00',
                'notification_frequency': 'immediate'
            }
            logger.info(f"Created default preferences for user {user_id}: {default_prefs}")
            return default_prefs

def update_user_preferences(user_id: int, preferences: Dict) -> bool:
    """Update user notification preferences"""
    try:
        logger.info(f"update_user_preferences called for user {user_id} with preferences: {preferences}")
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            favorite_categories_str = ','.join(preferences.get('favorite_categories', []))
            logger.info(f"Favorite categories string to save: '{favorite_categories_str}'")
            
            params = (
                user_id,
                preferences.get('comment_notifications', True),
                favorite_categories_str,
                preferences.get('daily_digest', True),
                preferences.get('trending_alerts', True),
                preferences.get('digest_time', '18:00'),
                preferences.get('notification_frequency', 'immediate'),
                datetime.now().isoformat()
            )
            logger.info(f"SQL parameters: {params}")
            
            cursor.execute('''
                INSERT OR REPLACE INTO notification_preferences 
                (user_id, comment_notifications, favorite_categories, daily_digest, 
                 trending_alerts, digest_time, notification_frequency, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', params)
            conn.commit()
            
            # Verify the update by reading it back
            cursor.execute('''
                SELECT favorite_categories FROM notification_preferences WHERE user_id = ?
            ''', (user_id,))
            saved_result = cursor.fetchone()
            logger.info(f"Verified saved favorite_categories: {saved_result[0] if saved_result else 'None'}")
            
            return True
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        return False

def subscribe_to_post(user_id: int, post_id: int) -> bool:
    """Subscribe user to post notifications"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO post_subscriptions (user_id, post_id, active)
                VALUES (?, ?, 1)
            ''', (user_id, post_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error subscribing to post: {e}")
        return False

def unsubscribe_from_post(user_id: int, post_id: int) -> bool:
    """Unsubscribe user from post notifications"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE post_subscriptions SET active = 0 
                WHERE user_id = ? AND post_id = ?
            ''', (user_id, post_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error unsubscribing from post: {e}")
        return False

def get_post_subscribers(post_id: int) -> List[int]:
    """Get list of users subscribed to a post"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id FROM post_subscriptions 
            WHERE post_id = ? AND active = 1
        ''', (post_id,))
        return [row[0] for row in cursor.fetchall()]

async def send_notification(context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                          notification_type: str, title: str, content: str,
                          post_id: int = None, comment_id: int = None,
                          keyboard: InlineKeyboardMarkup = None) -> bool:
    """Send notification to user"""
    try:
        # Record notification in history
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO notification_history 
                (user_id, notification_type, title, content, related_post_id, related_comment_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, notification_type, title, content, post_id, comment_id))
            conn.commit()
        
        # Format notification message
        notification_text = f"🔔 *{escape_markdown_text(title)}*\n\n{escape_markdown_text(content)}"
        
        # Send notification
        await context.bot.send_message(
            chat_id=user_id,
            text=notification_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
        
        # Mark as delivered
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE notification_history SET delivered = 1 
                WHERE user_id = ? AND notification_type = ? AND sent_at = 
                (SELECT MAX(sent_at) FROM notification_history WHERE user_id = ?)
            ''', (user_id, notification_type, user_id))
            conn.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending notification to {user_id}: {e}")
        return False

async def notify_comment_on_post(context: ContextTypes.DEFAULT_TYPE, post_id: int, 
                                comment_content: str, commenter_id: int = None):
    """Notify subscribers when a new comment is posted"""
    try:
        # Get post details
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT content, category, user_id FROM posts WHERE id = ? AND approved = 1
            ''', (post_id,))
            post_data = cursor.fetchone()
            
            if not post_data:
                return
            
            post_content, category, post_author_id = post_data
        
        # Get subscribers (exclude the commenter and post author)
        subscribers = get_post_subscribers(post_id)
        exclude_users = {commenter_id, post_author_id} if commenter_id else {post_author_id}
        subscribers = [uid for uid in subscribers if uid not in exclude_users]
        
        # Auto-subscribe post author if they have comment notifications enabled
        author_prefs = get_user_preferences(post_author_id)
        if author_prefs['comment_notifications'] and post_author_id not in subscribers:
            subscribe_to_post(post_author_id, post_id)
            if post_author_id != commenter_id:
                subscribers.append(post_author_id)
        
        # Send notifications
        for subscriber_id in subscribers:
            prefs = get_user_preferences(subscriber_id)
            if not prefs['comment_notifications']:
                continue
            
            # Create notification content
            title = f"New Comment on Post #{post_id}"
            content = f"Category: {category}\n"
            content += f"Post: {truncate_text(post_content, 50)}...\n"
            content += f"Comment: {truncate_text(comment_content, 80)}..."
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👀 View Comments", callback_data=f"see_comments_{post_id}_1"),
                    InlineKeyboardButton("💬 Reply", callback_data=f"add_comment_{post_id}")
                ],
                [
                    InlineKeyboardButton("🔕 Unsubscribe", callback_data=f"unsub_{post_id}")
                ]
            ])
            
            await send_notification(
                context, subscriber_id, "comment", title, content, 
                post_id=post_id, keyboard=keyboard
            )
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.1)
            
        logger.info(f"Sent comment notifications for post {post_id} to {len(subscribers)} users")
        
    except Exception as e:
        logger.error(f"Error sending comment notifications: {e}")

async def notify_favorite_category_post(context: ContextTypes.DEFAULT_TYPE, post_id: int, 
                                       category: str, content: str):
    """Notify users when a post is approved in their favorite categories"""
    try:
        # Get users who have this category as favorite
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id FROM notification_preferences 
                WHERE favorite_categories LIKE ? OR favorite_categories LIKE ? OR favorite_categories LIKE ?
            ''', (f"%{category}%", f"{category},%", f",{category}"))
            
            category_subscribers = [row[0] for row in cursor.fetchall()]
        
        # Send notifications
        for user_id in category_subscribers:
            prefs = get_user_preferences(user_id)
            if category not in prefs['favorite_categories']:
                continue
            
            # Auto-subscribe to posts in favorite categories
            subscribe_to_post(user_id, post_id)
            
            title = f"New Post in {category}"
            notification_content = f"A new confession/question was posted in your favorite category!\n\n"
            notification_content += f"Preview: {truncate_text(content, 100)}..."
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📖 Read Post", callback_data=f"view_post_{post_id}"),
                    InlineKeyboardButton("💬 Comment", callback_data=f"add_comment_{post_id}")
                ],
                [
                    InlineKeyboardButton("⚙️ Notification Settings", callback_data="notification_settings")
                ]
            ])
            
            await send_notification(
                context, user_id, "favorite_category", title, notification_content,
                post_id=post_id, keyboard=keyboard
            )
            
            await asyncio.sleep(0.1)
            
        logger.info(f"Sent favorite category notifications for post {post_id} to {len(category_subscribers)} users")
        
    except Exception as e:
        logger.error(f"Error sending favorite category notifications: {e}")

async def notify_trending_post(context: ContextTypes.DEFAULT_TYPE, post_id: int, 
                              trend_score: float, category: str):
    """Notify users about trending posts"""
    try:
        # Get post details
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT content, user_id FROM posts WHERE id = ? AND approved = 1
            ''', (post_id,))
            post_data = cursor.fetchone()
            
            if not post_data:
                return
            
            post_content, post_author = post_data
            
            # Check if we've already notified about this trending post recently
            cursor.execute('''
                SELECT notified_users FROM trending_cache 
                WHERE post_id = ? AND cached_at > datetime('now', '-2 hours')
                ORDER BY cached_at DESC LIMIT 1
            ''', (post_id,))
            cache_result = cursor.fetchone()
            
            previously_notified = []
            if cache_result and cache_result[0]:
                previously_notified = cache_result[0].split(',')
        
        # Get users who want trending alerts
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id FROM notification_preferences WHERE trending_alerts = 1
            ''', ())
            trending_subscribers = [str(row[0]) for row in cursor.fetchall()]
        
        # Filter out already notified users and post author
        new_subscribers = [uid for uid in trending_subscribers 
                          if uid not in previously_notified and int(uid) != post_author]
        
        if not new_subscribers:
            return
        
        # Send notifications
        notified_count = 0
        for user_id_str in new_subscribers[:50]:  # Limit to 50 notifications per trending alert
            user_id = int(user_id_str)
            
            title = f"🔥 Trending Post in {category}"
            content = f"This post is getting lots of attention!\n\n"
            content += f"Preview: {truncate_text(post_content, 100)}...\n\n"
            content += f"Trend Score: {trend_score:.1f}"
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔥 See What's Hot", callback_data=f"view_post_{post_id}"),
                    InlineKeyboardButton("💬 Join Discussion", callback_data=f"see_comments_{post_id}_1")
                ],
                [
                    InlineKeyboardButton("⚙️ Notification Settings", callback_data="notification_settings")
                ]
            ])
            
            success = await send_notification(
                context, user_id, "trending", title, content,
                post_id=post_id, keyboard=keyboard
            )
            
            if success:
                notified_count += 1
            
            await asyncio.sleep(0.2)
        
        # Update trending cache with notified users
        all_notified = previously_notified + new_subscribers
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO trending_cache 
                (post_id, trend_score, category, notified_users)
                VALUES (?, ?, ?, ?)
            ''', (post_id, trend_score, category, ','.join(all_notified)))
            conn.commit()
        
        logger.info(f"Sent trending notifications for post {post_id} to {notified_count} users")
        
    except Exception as e:
        logger.error(f"Error sending trending notifications: {e}")

def get_users_for_daily_digest() -> List[Tuple[int, str]]:
    """Get users who want daily digest and their preferred time"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, digest_time FROM notification_preferences 
            WHERE daily_digest = 1
        ''', ())
        return cursor.fetchall()

async def send_daily_digest(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Send daily digest to user"""
    try:
        # Get today's posts
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, content, category, 
                       (SELECT COUNT(*) FROM comments WHERE post_id = posts.id) as comment_count
                FROM posts 
                WHERE DATE(timestamp) = DATE('now') AND approved = 1
                ORDER BY 
                    (SELECT COUNT(*) FROM comments WHERE post_id = posts.id) DESC,
                    id DESC
                LIMIT 5
            ''', ())
            todays_posts = cursor.fetchall()
            
            # Get user's favorite categories
            prefs = get_user_preferences(user_id)
            favorite_categories = prefs['favorite_categories']
            
            # Get posts in favorite categories from last 2 days
            favorite_posts = []
            if favorite_categories:
                placeholders = ','.join('?' * len(favorite_categories))
                cursor.execute(f'''
                    SELECT id, content, category,
                           (SELECT COUNT(*) FROM comments WHERE post_id = posts.id) as comment_count
                    FROM posts 
                    WHERE DATE(timestamp) >= DATE('now', '-2 days') 
                    AND approved = 1 AND category IN ({placeholders})
                    ORDER BY comment_count DESC
                    LIMIT 3
                ''', favorite_categories)
                favorite_posts = cursor.fetchall()
        
        if not todays_posts and not favorite_posts:
            return False
        
        # Build digest content
        title = "📅 Your Daily Digest"
        content = f"Here's what happened today!\n\n"
        
        if todays_posts:
            content += f"🌟 Today's Posts ({len(todays_posts)}):\n"
            for post_id, post_content, category, comment_count in todays_posts:
                content += f"• #{post_id} - {category}\n"
                content += f"  {truncate_text(post_content, 60)}...\n"
                content += f"  💬 {comment_count} comments\n\n"
        
        if favorite_posts:
            content += f"❤️ From Your Favorite Categories:\n"
            for post_id, post_content, category, comment_count in favorite_posts:
                content += f"• #{post_id} - {category}\n"
                content += f"  {truncate_text(post_content, 60)}...\n"
                content += f"  💬 {comment_count} comments\n\n"
        
        content += "Have a great day! 😊"
        
        # Create keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔥 View Trending", callback_data="callback_trending"),
                InlineKeyboardButton("⭐ Popular Today", callback_data="callback_popular")
            ],
            [
                InlineKeyboardButton("⚙️ Digest Settings", callback_data="notification_settings")
            ]
        ])
        
        success = await send_notification(
            context, user_id, "daily_digest", title, content, keyboard=keyboard
        )
        
        return success
        
    except Exception as e:
        logger.error(f"Error sending daily digest to {user_id}: {e}")
        return False

async def handle_notification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle notification-related callbacks"""
    query = update.callback_query
    await query.answer()
    
    if not query.data:
        return
    
    data = query.data
    user_id = update.effective_user.id
    
    # Handle unsubscribe from post
    if data.startswith("unsub_"):
        post_id = int(data.replace("unsub_", ""))
        success = unsubscribe_from_post(user_id, post_id)
        if success:
            await query.answer("🔕 Unsubscribed from this post!")
            await query.edit_message_text(
                "🔕 *Unsubscribed*\n\nYou won't receive notifications for new comments on this post.",
                parse_mode="MarkdownV2"
            )
        else:
            await query.answer("❗ Error unsubscribing. Please try again.")
    
    # Handle notification settings
    elif data == "notification_settings":
        await show_notification_settings(update, context)
    
    # Handle toggle comment notifications
    elif data == "toggle_comment_notif":
        await toggle_comment_notifications(update, context)
    
    # Handle toggle daily digest
    elif data == "toggle_daily_digest":
        await toggle_daily_digest(update, context)
    
    # Handle toggle trending alerts
    elif data == "toggle_trending":
        await toggle_trending_alerts(update, context)
    
    # Handle manage favorite categories
    elif data == "manage_categories":
        await show_category_management(update, context)
    
    # Handle set digest time
    elif data == "set_digest_time":
        await show_digest_time_options(update, context)
    
    # Handle notification history
    elif data == "notification_history":
        await show_notification_history(update, context)
    
    # Handle digest time selection
    elif data.startswith("set_time_"):
        await set_digest_time(update, context)
    
    # Handle category toggle
    elif data.startswith("cat_toggle_"):
        await toggle_favorite_category(update, context)
    
    # Handle select all categories
    elif data == "cat_select_all":
        await select_all_categories(update, context)
    
    # Handle clear all categories
    elif data == "cat_clear_all":
        await clear_all_categories(update, context)
    
    # Handle test notification
    elif data == "test_notification":
        await send_test_notification(update, context)
    
    # Handle callback shortcuts for daily digest
    elif data == "callback_trending":
        from bot import trending_posts  # Import here to avoid circular imports
        await trending_posts(update, context)
    
    elif data == "callback_popular":
        from bot import popular_today  # Import here to avoid circular imports
        await popular_today(update, context)

async def show_notification_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show notification settings interface"""
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    
    digest_time_text = escape_markdown_text(f"(at {prefs['digest_time']})")
    favorites_display = escape_markdown_text(', '.join(prefs['favorite_categories'])) if prefs['favorite_categories'] else 'None'
    
    settings_text = f"""
🔔 *Smart Notifications Settings*

*Current Settings:*
• Comment Notifications: {'✅' if prefs['comment_notifications'] else '❌'}
• Daily Digest: {'✅' if prefs['daily_digest'] else '❌'} {digest_time_text}
• Trending Alerts: {'✅' if prefs['trending_alerts'] else '❌'}
• Favorite Categories: {favorites_display}

Configure your personalized notifications:
"""
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'🔕' if prefs['comment_notifications'] else '🔔'} Comment Notifications",
                callback_data="toggle_comment_notif"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'🔕' if prefs['daily_digest'] else '📅'} Daily Digest",
                callback_data="toggle_daily_digest"
            ),
            InlineKeyboardButton("⏰ Set Time", callback_data="set_digest_time")
        ],
        [
            InlineKeyboardButton(
                f"{'🔕' if prefs['trending_alerts'] else '🔥'} Trending Alerts",
                callback_data="toggle_trending"
            )
        ],
        [
            InlineKeyboardButton("❤️ Manage Favorite Categories", callback_data="manage_categories")
        ],
        [
            InlineKeyboardButton("📊 Notification History", callback_data="notification_history"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            settings_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(
            settings_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )

async def toggle_comment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle comment notification setting"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    prefs = get_user_preferences(user_id)
    new_value = not prefs['comment_notifications']
    prefs['comment_notifications'] = new_value
    
    success = update_user_preferences(user_id, prefs)
    if success:
        status = "enabled" if new_value else "disabled"
        await query.answer(f"💬 Comment notifications {status}!")
        await show_notification_settings(update, context)
    else:
        await query.answer("❗ Error updating settings. Try again.")

async def toggle_daily_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle daily digest setting"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    prefs = get_user_preferences(user_id)
    new_value = not prefs['daily_digest']
    prefs['daily_digest'] = new_value
    
    success = update_user_preferences(user_id, prefs)
    if success:
        status = "enabled" if new_value else "disabled"
        await query.answer(f"📅 Daily digest {status}!")
        await show_notification_settings(update, context)
    else:
        await query.answer("❗ Error updating settings. Try again.")

async def toggle_trending_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle trending alerts setting"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    prefs = get_user_preferences(user_id)
    new_value = not prefs['trending_alerts']
    prefs['trending_alerts'] = new_value
    
    success = update_user_preferences(user_id, prefs)
    if success:
        status = "enabled" if new_value else "disabled"
        await query.answer(f"🔥 Trending alerts {status}!")
        await show_notification_settings(update, context)
    else:
        await query.answer("❗ Error updating settings. Try again.")

async def show_category_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show favorite categories management interface"""
    query = update.callback_query
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    
    current_favorites = prefs['favorite_categories']
    logger.info(f"show_category_management: user={user_id}, current_favorites={current_favorites}")
    
    categories_text = "❤️ *Manage Favorite Categories*\n\n"
    categories_text += "Tap categories to add/remove from favorites\\. You can select multiple categories\\!\n\n"
    
    # Show currently selected favorites
    if current_favorites:
        favorites_text = escape_markdown_text(', '.join(current_favorites))
        count_text = escape_markdown_text(f"({len(current_favorites)})")
        categories_text += f"*Currently selected {count_text}:* {favorites_text}\n\n"
    else:
        categories_text += "*No favorites selected yet\\.*\n\n"
    
    categories_text += "Choose your favorite categories:"
    
    keyboard = []
    
    # Create category buttons in pairs
    for i in range(0, len(CATEGORIES), 2):
        row = []
        
        # First category
        cat1 = CATEGORIES[i]
        is_favorite1 = cat1 in current_favorites
        emoji1 = "✅" if is_favorite1 else "⬜"
        button_text1 = f"{emoji1} {cat1}"
        logger.info(f"Button {i}: {button_text1}, is_favorite={is_favorite1}")
        row.append(InlineKeyboardButton(
            button_text1, 
            callback_data=f"cat_toggle_{i}"
        ))
        
        # Second category (if exists)
        if i + 1 < len(CATEGORIES):
            cat2 = CATEGORIES[i + 1]
            is_favorite2 = cat2 in current_favorites
            emoji2 = "✅" if is_favorite2 else "⬜"
            button_text2 = f"{emoji2} {cat2}"
            logger.info(f"Button {i+1}: {button_text2}, is_favorite={is_favorite2}")
            row.append(InlineKeyboardButton(
                button_text2, 
                callback_data=f"cat_toggle_{i + 1}"
            ))
        
        keyboard.append(row)
    
    # Add control buttons
    keyboard.append([
        InlineKeyboardButton("✨ Select All", callback_data="cat_select_all"),
        InlineKeyboardButton("🗳️ Clear All", callback_data="cat_clear_all")
    ])
    keyboard.append([
        InlineKeyboardButton("💾 Save & Back", callback_data="notification_settings")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    logger.info(f"About to edit message text. Text length: {len(categories_text)}")
    logger.info(f"Message text: {categories_text}")
    
    try:
        await query.edit_message_text(
            categories_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        logger.info("Successfully edited message with updated keyboard")
    except Exception as e:
        logger.error(f"Error editing message: {e}")

async def toggle_favorite_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle a favorite category"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Extract category index from callback data
    category_index = int(query.data.replace("cat_toggle_", ""))
    category = CATEGORIES[category_index]
    
    # Debug logging
    logger.info(f"Toggle category: user={user_id}, category_index={category_index}, category={category}")
    
    prefs = get_user_preferences(user_id)
    current_favorites = prefs['favorite_categories'].copy()  # Make a copy to ensure we're working with a fresh list
    
    logger.info(f"Current favorites before toggle: {current_favorites}")
    
    if category in current_favorites:
        current_favorites.remove(category)
        await query.answer(f"💔 Removed {category} from favorites")
        action = "removed"
    else:
        current_favorites.append(category)
        await query.answer(f"💚 Added {category} to favorites")
        action = "added"
    
    logger.info(f"Current favorites after toggle: {current_favorites}, action: {action}")
    
    prefs['favorite_categories'] = current_favorites
    success = update_user_preferences(user_id, prefs)
    
    logger.info(f"Update preferences success: {success}")
    
    if success:
        await show_category_management(update, context)
    else:
        await query.answer("❗ Error updating preferences")

async def show_digest_time_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show digest time selection options"""
    query = update.callback_query
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    current_time = prefs['digest_time']
    
    time_text = f"⏰ *Set Daily Digest Time*\n\n"
    time_text += f"Current time: {escape_markdown_text(current_time)}\n\n"
    time_text += "Choose when you'd like to receive your daily digest:"
    
    time_options = ["08:00", "12:00", "16:00", "18:00", "20:00", "22:00"]
    
    keyboard = []
    for i in range(0, len(time_options), 2):
        row = []
        time1 = time_options[i]
        emoji1 = "⏰" if time1 == current_time else "🕐"
        row.append(InlineKeyboardButton(
            f"{emoji1} {time1}", 
            callback_data=f"set_time_{time1.replace(':', '')}"
        ))
        
        if i + 1 < len(time_options):
            time2 = time_options[i + 1]
            emoji2 = "⏰" if time2 == current_time else "🕐"
            row.append(InlineKeyboardButton(
                f"{emoji2} {time2}", 
                callback_data=f"set_time_{time2.replace(':', '')}"
            ))
        
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Settings", callback_data="notification_settings")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        time_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def set_digest_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the digest time"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Extract time from callback data
    time_str = query.data.replace("set_time_", "")
    new_time = f"{time_str[:2]}:{time_str[2:]}"
    
    prefs = get_user_preferences(user_id)
    prefs['digest_time'] = new_time
    
    success = update_user_preferences(user_id, prefs)
    if success:
        await query.answer(f"⏰ Digest time set to {new_time}!")
        await show_notification_settings(update, context)
    else:
        await query.answer("❗ Error updating digest time")

async def show_notification_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's notification history"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT notification_type, title, content, sent_at, delivered
                FROM notification_history 
                WHERE user_id = ? 
                ORDER BY sent_at DESC 
                LIMIT 10
            ''', (user_id,))
            history = cursor.fetchall()
        
        if not history:
            history_text = "📊 *Notification History*\n\nNo notifications sent yet\\. When you receive notifications, they'll appear here\\."
        else:
            history_text = f"📊 *Notification History*\n\nYour last {len(history)} notifications:\n\n"
            
            for notif_type, title, content, sent_at, delivered in history:
                status_emoji = "✅" if delivered else "⏳"
                type_emoji = {
                    'comment': '💬',
                    'favorite_category': '❤️', 
                    'trending': '🔥',
                    'daily_digest': '📅'
                }.get(notif_type, '🔔')
                
                # Format timestamp
                try:
                    dt = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
                    time_str = dt.strftime('%m-%d %H:%M')
                except:
                    time_str = sent_at[:16] if sent_at else "Unknown"
                
                history_text += f"{type_emoji} {status_emoji} {escape_markdown_text(title)}\n"
                history_text += f"   {escape_markdown_text(time_str)}\n\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🧹 Clear History", callback_data="clear_history"),
                InlineKeyboardButton("🔔 Test Notification", callback_data="test_notification")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="notification_settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        logger.error(f"Error showing notification history: {e}")
        await query.answer("❗ Error loading history")

async def select_all_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select all categories as favorites"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    prefs = get_user_preferences(user_id)
    prefs['favorite_categories'] = CATEGORIES.copy()  # Select all categories
    
    success = update_user_preferences(user_id, prefs)
    if success:
        await query.answer(f"✨ Selected all {len(CATEGORIES)} categories!")
        await show_category_management(update, context)
    else:
        await query.answer("❗ Error updating preferences")

async def clear_all_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all favorite categories"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    prefs = get_user_preferences(user_id)
    prefs['favorite_categories'] = []  # Clear all categories
    
    success = update_user_preferences(user_id, prefs)
    if success:
        await query.answer("🗳️ Cleared all favorites!")
        await show_category_management(update, context)
    else:
        await query.answer("❗ Error updating preferences")

async def send_test_notification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a test notification to the user"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    title = "🧪 Test Notification"
    content = "This is a test notification to verify your settings are working correctly!"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Back to Settings", callback_data="notification_settings")
        ]
    ])
    
    success = await send_notification(
        context, user_id, "test", title, content, keyboard=keyboard
    )
    
    if success:
        await query.answer("🧪 Test notification sent!")
    else:
        await query.answer("❗ Failed to send test notification")

# Export functions for use in other modules
__all__ = [
    'notification_engine',
    'get_user_preferences',
    'update_user_preferences',
    'subscribe_to_post',
    'unsubscribe_from_post',
    'send_notification',
    'notify_comment_on_post',
    'notify_favorite_category_post',
    'notify_trending_post',
    'send_daily_digest',
    'get_users_for_daily_digest',
    'handle_notification_callback',
    'show_notification_settings'
]
