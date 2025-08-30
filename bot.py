"""
Enhanced Telegram Confession Bot with Sophisticated Comment System
Features: Pagination, Like/Dislike, Replies, Reporting, and Admin Moderation
"""

import logging
import re
import os
import sqlite3
from typing import Optional
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from config import *
from db import *
from submission import *
from comments import *
from approval import admin_callback
from moderation import report_abuse, notify_admins_about_reports
from stats import get_user_stats, get_channel_stats
from utils import *
from admin_messaging import send_message_to_admins, get_pending_messages, send_admin_reply_to_user

# Import improvement modules
from rate_limiter import rate_limiter, handle_rate_limit_decorator
from error_handler import handle_telegram_errors, global_error_handler
from logger import bot_logger
from migrations import run_migrations
from analytics import analytics_manager
from backup_system import start_backup_system

# Import ranking system modules
from ranking_ui import ranking_callback_handler, show_ranking_menu
from ranking_integration import (
    award_points_for_confession_submission,
    award_points_for_confession_approval,
    award_points_for_comment,
    award_points_for_reaction_given,
    award_points_for_reaction_received
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Menu options
MAIN_MENU = [
    ["🙊 Confess/Ask Question", "🔥 Trending"],
    ["⭐ Popular Today", "🏆 My Rank"],
    ["📊 My Stats", "🔔 Smart Notifications"],
    ["📅 Daily Digest", "📞 Contact Admin"],
    ["❓ Help/About"]
]

CANCEL_BUTTON = "🚫 Cancel"
MENU_BUTTON = "🏠 Main Menu"

async def clear_user_context(context):
    """Clear user's conversation context"""
    keys_to_clear = [
        'state', 'confession_content', 'selected_category', 
        'comment_post_id', 'comment_content', 'admin_action',
        'viewing_post_id', 'reply_to_comment_id', 'current_page',
        'contact_admin_message'
    ]
    for key in keys_to_clear:
        context.user_data.pop(key, None)

async def show_menu(update, context, text="What would you like to do next?"):
    """Show the main menu"""
    await clear_user_context(context)
    
    # Get user ID to check if admin
    user_id = None
    if update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id
    elif update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.effective_user:
        user_id = update.effective_user.id
    
    # Create menu based on user type
    menu = MAIN_MENU.copy()
    if user_id and user_id in ADMIN_IDS:
        # Add admin button for admins
        menu.append(["🔧 Admin Dashboard"])
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text="🏠 Returned to main menu.")
        except:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
        )
    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
        )

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command and deep links"""
    user = update.effective_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    # Check for deep links (e.g., /start comment_123, /start view_123)
    if context.args:
        command = context.args[0]
        logger.info(f"Deep link command received: {command}")
        
        try:
            if command.startswith("comment_"):
                post_id = int(command.split("_")[1])
                logger.info(f"Processing comment deep link for post_id: {post_id}")
                await show_post_for_commenting(update, context, post_id)
                return
            elif command.startswith("view_"):
                post_id = int(command.split("_")[1])
                logger.info(f"Processing view comments deep link for post_id: {post_id}")
                await show_comments_directly(update, context, post_id)
                return
        except (ValueError, IndexError) as e:
            logger.error(f"Error processing deep link {command}: {e}")
            await update.message.reply_text(
                "❗ Invalid link. Please try again or use the main menu."
            )
            await show_menu(update, context)
            return
    
    welcome_text = f"""
🎓 *Welcome to University Confession Bot\\!*

Hi {escape_markdown_text(user.first_name or 'there')}\\! 

This bot allows you to submit anonymous confessions and questions that will be reviewed by admins before posting to our channel\\.

*What you can do:*
• 🙊 Submit anonymous confessions/questions
• 📰 View recent approved posts
• 💬 Comment on posts with reactions
• 👍👎 Like/dislike comments
• 💬 Reply to specific comments
• 🚩 Report inappropriate content
• 🏆 Climb the ranking system and earn achievements
• 📊 Check your submission stats

*Your privacy matters\\!* 
All submissions and comments are anonymous and your identity is protected\\.

Choose an option from the menu below to get started\\!
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="MarkdownV2",
        reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command"""
    await show_menu(update, context, "🏠 Main Menu")

async def handle_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu choices"""
    if not update.message or not update.message.text or not update.message.from_user:
        return
    
    text = update.message.text
    user_id = update.message.from_user.id
    
    # Handle cancel button
    if text == CANCEL_BUTTON:
        await show_menu(update, context, "🏠 Returned to main menu.")
        return
    
    # Check if user is blocked
    if is_blocked_user(user_id):
        await update.message.reply_text(
            "⛔ *Account Blocked*\n\n"
            "Your account has been blocked from submitting confessions\\. "
            "You can still view content but cannot post new confessions\\. "
            "Contact administrators if you believe this is an error\\.",
            parse_mode="MarkdownV2"
        )
        return

    # Handle current conversation states
    state = context.user_data.get('state')
    
    if state == 'writing_confession':
        await handle_confession_submission(update, context)
        return
    elif state == 'writing_comment':
        await handle_comment_submission(update, context)
        return
    elif state == 'contacting_admin':
        await handle_admin_contact(update, context)
        return
    elif state == 'admin_replying':
        await handle_admin_reply_message(update, context)
        return

    # Handle menu options
    if text == "🙊 Confess/Ask Question":
        await start_confession_flow(update, context)
    elif text == "🏆 My Rank":
        await show_ranking_menu(update, context)
    elif text == "📊 My Stats":
        await my_stats(update, context)
    elif text == "🔥 Trending":
        await trending_posts(update, context)
    elif text == "⭐ Popular Today":
        await popular_today(update, context)
    elif text == "📅 Daily Digest":
        await daily_digest(update, context)
    elif text == "🔔 Smart Notifications":
        await show_smart_notifications(update, context)
    elif text == "📞 Contact Admin":
        await start_contact_admin(update, context)
    elif text == "❓ Help/About":
        await update.message.reply_text(HELP_TEXT, parse_mode="MarkdownV2")
        await show_menu(update, context)
    elif text == "🔧 Admin Dashboard":
        await admin_dashboard(update, context)
    elif text == MENU_BUTTON:
        await show_menu(update, context, "🏠 Returned to main menu.")
    else:
        await update.message.reply_text("❗ Please choose an option from the menu below.")
        await show_menu(update, context)

# Confession Flow
async def start_confession_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the confession submission flow with multiple category selection"""
    keyboard = []
    # Create two-column layout for categories
    for i in range(0, len(CATEGORIES), 2):
        row = []
        row.append(InlineKeyboardButton(CATEGORIES[i], callback_data=f"category_{i}"))
        if i + 1 < len(CATEGORIES):
            row.append(InlineKeyboardButton(CATEGORIES[i + 1], callback_data=f"category_{i + 1}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("✅ Done Selecting", callback_data="categories_done")])
    keyboard.append([InlineKeyboardButton("🚫 Cancel", callback_data="cancel_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data['selected_categories'] = []
    
    await update.message.reply_text(
        "📝 *Choose categories for your confession/question:*\n\n"
        "You can select multiple categories\\. Click on each category you want, then click '✅ Done Selecting' when finished\\.",
        reply_markup=reply_markup,
        parse_mode="MarkdownV2",
        reply_to_message_id=update.message.message_id if update.message else None
    )
    
    context.user_data['state'] = 'choosing_category'

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle multiple category selection"""
    query = update.callback_query
    await query.answer()
    
    if not query.data:
        return
    
    if query.data == "categories_done":
        selected_categories = context.user_data.get('selected_categories', [])
        if not selected_categories:
            await query.answer("❗ Please select at least one category!")
            return
        
        categories_text = ", ".join(selected_categories)
        context.user_data['selected_category'] = categories_text
        context.user_data['state'] = 'writing_confession'
        
        await query.edit_message_text(
            f"📝 *Categories selected: {escape_markdown_text(categories_text)}*\n\n"
            f"Now write your confession or question\\. You have up to {MAX_CONFESSION_LENGTH} characters\\.\n\n"
            f"Type your message below or use {CANCEL_BUTTON} to return to menu\\:",
            parse_mode="MarkdownV2"
        )
        return
        
    category_idx = int(query.data.replace("category_", ""))
    category = CATEGORIES[category_idx]
    
    selected_categories = context.user_data.get('selected_categories', [])
    
    if category in selected_categories:
        selected_categories.remove(category)
        await query.answer(f"❌ Removed: {category}")
    else:
        selected_categories.append(category)
        await query.answer(f"✅ Added: {category}")
    
    context.user_data['selected_categories'] = selected_categories
    
    # Update the keyboard to show selected categories in two columns
    keyboard = []
    # Create two-column layout for categories with selection indicators
    for i in range(0, len(CATEGORIES), 2):
        row = []
        prefix1 = "✅ " if CATEGORIES[i] in selected_categories else ""
        row.append(InlineKeyboardButton(f"{prefix1}{CATEGORIES[i]}", callback_data=f"category_{i}"))
        if i + 1 < len(CATEGORIES):
            prefix2 = "✅ " if CATEGORIES[i + 1] in selected_categories else ""
            row.append(InlineKeyboardButton(f"{prefix2}{CATEGORIES[i + 1]}", callback_data=f"category_{i + 1}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("✅ Done Selecting", callback_data="categories_done")])
    keyboard.append([InlineKeyboardButton("🚫 Cancel", callback_data="cancel_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    selected_text = f"\n\n*Selected: {', '.join(selected_categories)}*" if selected_categories else ""
    
    await query.edit_message_text(
        f"📝 *Choose categories for your confession/question:*\n\n"
        f"You can select multiple categories\\. Click on each category you want, then click '✅ Done Selecting' when finished\\.{escape_markdown_text(selected_text)}",
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def handle_confession_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confession text submission"""
    if update.message.text == CANCEL_BUTTON:
        await show_menu(update, context, "🏠 Confession cancelled. Returned to main menu.")
        return
    
    content = sanitize_content(update.message.text)
    if not content:
        await update.message.reply_text("❗ Your message contains inappropriate content or spam. Please try again.")
        return
    
    if len(content) > MAX_CONFESSION_LENGTH:
        await update.message.reply_text(f"❗ Your confession is too long. Please keep it under {MAX_CONFESSION_LENGTH} characters.")
        return
    
    category = context.user_data.get('selected_category')
    user_id = update.message.from_user.id
    
    post_id, error = save_submission(user_id, content, category)
    
    if error:
        await update.message.reply_text(f"❗ Error saving confession: {error}")
        return
    
    # Award points for confession submission
    await award_points_for_confession_submission(user_id, post_id, category, context)
    
    # Send to admins for approval
    await send_to_admins_for_approval(context, post_id, content, category, user_id)
    
    await update.message.reply_text(
        "✅ *Confession Submitted\\!*\n\n"
        "Your confession has been sent to administrators for review\\. "
        "You'll be notified once it's approved or if there are any issues\\.",
        parse_mode="MarkdownV2"
    )
    
    await show_menu(update, context)

async def send_to_admins_for_approval(context, post_id, content, category, user_id):
    """Send confession to admins for approval"""
    admin_text = f"""
📝 *New Confession Submission*

*ID:* {escape_markdown_text(f'#{post_id}')}
*Category:* {escape_markdown_text(category)}
*Submitter:* {user_id}

*Content:*
{escape_markdown_text(content)}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}")
        ],
        [
            InlineKeyboardButton("🚩 Flag", callback_data=f"flag_{post_id}"),
            InlineKeyboardButton("⛔ Block User", callback_data=f"block_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Failed to send to admin {admin_id}: {e}")

# Trending/Popular Posts
async def trending_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trending posts with different categories"""
    from trending import get_trending_posts, get_most_commented_posts_24h, get_rising_posts
    
    # Get trending posts
    trending = get_trending_posts(8)
    most_commented = get_most_commented_posts_24h(5) 
    rising = get_rising_posts(5)
    
    if not trending and not most_commented and not rising:
        await update.message.reply_text(
            "🔥 *No trending posts yet\\!*\n\n"
            "Posts become trending when they get lots of comments and engagement\\. "
            "Submit confessions and engage with others to see trending content\\!", 
            parse_mode="MarkdownV2"
        )
        await show_menu(update, context)
        return

    # Send trending posts header
    header_text = "🔥 *Trending Posts*\n\n📈 *Hot & Rising Right Now*"
    await update.message.reply_text(header_text, parse_mode="MarkdownV2")
    
    import asyncio
    from datetime import datetime
    
    # Show trending posts first
    if trending:
        for post in trending[:5]:  # Show top 5 trending
            post_id = post[0]
            content = post[1]
            category = post[2]
            timestamp = post[3]
            comment_count = post[4]
            total_likes = post[5] if len(post) > 5 else 0
            
            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_ago = format_time_ago(dt)
                escaped_time = escape_markdown_text(time_ago)
            except:
                escaped_time = escape_markdown_text("recently")
            
            # Format trending post
            trend_text = f"*{escape_markdown_text(category)}*\n\n{escape_markdown_text(truncate_text(content, 120))}\n\n"
            trend_text += f"*\\#{post_id}* 🔥 💬 {comment_count} comments \\| "
            if total_likes > 0:
                trend_text += f"👍 {total_likes} likes \\| "
            trend_text += f"{escaped_time}"
            
            # Create buttons
            keyboard = [
                [
                    InlineKeyboardButton(f"👀 See Comments ({comment_count})", callback_data=f"see_comments_{post_id}_1"),
                    InlineKeyboardButton("📖 View Full Post", callback_data=f"view_post_{post_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send trending post
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=trend_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
            
            await asyncio.sleep(0.3)
    
    # Show most commented section
    if most_commented:
        commented_header = "\n💬 *Most Discussed \\(24h\\)*"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=commented_header,
            parse_mode="MarkdownV2"
        )
        
        for post in most_commented[:3]:  # Show top 3 most commented
            post_id = post[0]
            content = post[1]
            category = post[2]
            comment_count = post[4]
            
            commented_text = f"*{escape_markdown_text(category)}*\n{escape_markdown_text(truncate_text(content, 80))}\n"
            commented_text += f"*\\#{post_id}* 💬 {comment_count} comments"
            
            keyboard = [[
                InlineKeyboardButton(f"👀 Join Discussion ({comment_count})", callback_data=f"see_comments_{post_id}_1")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=commented_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
            
            await asyncio.sleep(0.2)
    
    # Show rising section
    if rising:
        rising_header = "\n🚀 *Rising Fast*"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=rising_header,
            parse_mode="MarkdownV2"
        )
        
        for post in rising[:3]:  # Show top 3 rising
            post_id = post[0]
            content = post[1]
            category = post[2]
            comment_count = post[4]
            
            rising_text = f"*{escape_markdown_text(category)}*\n{escape_markdown_text(truncate_text(content, 80))}\n"
            rising_text += f"*\\#{post_id}* 🚀 💬 {comment_count} comments"
            
            keyboard = [[
                InlineKeyboardButton(f"👀 View Comments ({comment_count})", callback_data=f"see_comments_{post_id}_1")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=rising_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
            
            await asyncio.sleep(0.2)
    
    # Send navigation
    nav_keyboard = [
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
    ]
    nav_reply_markup = InlineKeyboardMarkup(nav_keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📋 *Navigation*",
        reply_markup=nav_reply_markup,
        parse_mode="MarkdownV2"
    )

async def popular_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's popular posts with most liked comments and rising posts"""
    from trending import get_popular_today_posts, get_posts_with_most_liked_comments
    
    # Get today's popular posts
    popular = get_popular_today_posts(10)
    liked_posts = get_posts_with_most_liked_comments(8)
    
    if not popular and not liked_posts:
        await update.message.reply_text(
            "⭐ *No popular posts today yet\\!*\n\n"
            "Posts become popular when they get comments and likes\\. "
            "Check back later or help make some posts popular by commenting\\!",
            parse_mode="MarkdownV2"
        )
        await show_menu(update, context)
        return

    # Send popular posts header
    header_text = "⭐ *Popular Today*\n\n🌟 *Today's Top Posts*"
    await update.message.reply_text(header_text, parse_mode="MarkdownV2")
    
    import asyncio
    from datetime import datetime
    
    # Show today's popular posts
    if popular:
        for post in popular[:6]:  # Show top 6 popular today
            post_id = post[0]
            content = post[1]
            category = post[2]
            timestamp = post[3]
            comment_count = post[4]
            total_likes = post[5] if len(post) > 5 else 0
            
            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%H:%M')
                escaped_time = escape_markdown_text(formatted_time)
            except:
                escaped_time = escape_markdown_text("today")
            
            # Format popular post
            popular_text = f"*{escape_markdown_text(category)}*\n\n{escape_markdown_text(truncate_text(content, 110))}\n\n"
            popular_text += f"*\\#{post_id}* ⭐ 💬 {comment_count} comments"
            if total_likes > 0:
                popular_text += f" \\| 👍 {total_likes} likes"
            popular_text += f" \\| {escaped_time}"
            
            # Create buttons
            keyboard = [
                [
                    InlineKeyboardButton(f"👀 See Comments ({comment_count})", callback_data=f"see_comments_{post_id}_1"),
                    InlineKeyboardButton("📖 View Full Post", callback_data=f"view_post_{post_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send popular post
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=popular_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
            
            await asyncio.sleep(0.4)
    
    # Show most liked comments section
    if liked_posts:
        liked_header = "\n💖 *Posts with Most Liked Comments*"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=liked_header,
            parse_mode="MarkdownV2"
        )
        
        for post in liked_posts[:4]:  # Show top 4 posts with most liked comments
            post_id = post[0]
            content = post[1]
            category = post[2]
            comment_count = post[4]
            total_likes = post[5] if len(post) > 5 else 0
            
            liked_text = f"*{escape_markdown_text(category)}*\n{escape_markdown_text(truncate_text(content, 90))}\n"
            liked_text += f"*\\#{post_id}* 💖 💬 {comment_count} comments \\| 👍 {total_likes} total likes"
            
            keyboard = [[
                InlineKeyboardButton(f"👀 See Liked Comments ({comment_count})", callback_data=f"see_comments_{post_id}_1")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=liked_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
            
            await asyncio.sleep(0.3)
    
    # Send navigation
    nav_keyboard = [
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
    ]
    nav_reply_markup = InlineKeyboardMarkup(nav_keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📋 *Navigation*",
        reply_markup=nav_reply_markup,
        parse_mode="MarkdownV2"
    )

# Recent Posts and Comments
async def recent_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent approved confessions"""
    try:
        posts = get_recent_posts(10)
        
        if not posts:
            await update.message.reply_text("📰 No approved confessions available yet.")
            await show_menu(update, context)
            return

        reply = "📰 *Recent Confessions:*\n\n"
        keyboard = []
        
        for post in posts:
            post_id = post[0]
            content = post[1]
            category = post[2]
            # Comment count is the last column from the SQL query
            comment_count = post[-1] if len(post) > 9 else 0
            
            preview = truncate_text(content, 100)
            reply += f"\\#{post_id} \\| {escape_markdown_text(category)}\n{escape_markdown_text(preview)}\n\n"
            
            keyboard.append([InlineKeyboardButton(
                f"💬 #{post_id} ({comment_count} comments)", 
                callback_data=f"view_post_{post_id}"
            )])
        
        keyboard.append([InlineKeyboardButton(f"{MENU_BUTTON}", callback_data="menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            reply,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        logger.error(f"Error in recent_posts: {e}")
        await update.message.reply_text(
            "❗ Sorry, there was an issue loading recent confessions. Please try again."
        )
        await show_menu(update, context)

async def show_post_for_commenting(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Show direct comment interface (from 'Add Comment' deep link)"""
    post = get_post_by_id(post_id)
    if not post or post[13] != 1:  # Check if approved (approved field is at index 13, value 1 = approved)
        if update.message:
            await update.message.reply_text("❗ Post not found or not available.")
            await show_menu(update, context)
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❗ Post not found or not available."
            )
        return
    
    content = post[1]
    category = post[2]
    comment_count = get_comment_count(post_id)
    
    context.user_data['comment_post_id'] = post_id
    context.user_data['state'] = 'writing_comment'
    context.user_data.pop('reply_to_comment_id', None)  # Clear any reply state
    
    # Show post content and direct comment interface
    post_text = f"""📝 *{escape_markdown_text(category)}*

{escape_markdown_text(content)}

💬 *Add your comment:*

Type your comment below \\(max {MAX_COMMENT_LENGTH} characters\\)\\.

Use 🚫 Cancel to return to main menu\\."""
    
    if update.message:
        await update.message.reply_text(
            post_text,
            parse_mode="MarkdownV2"
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=post_text,
            parse_mode="MarkdownV2"
        )

async def show_comments_directly(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Show comments directly via deep link"""
    try:
        logger.info(f"show_comments_directly called with post_id: {post_id}")
        post = get_post_by_id(post_id)
        logger.info(f"Retrieved post: {post}")
        
        if not post or post[13] != 1:  # Check if approved (approved field is at index 13, value 1 = approved)
            await update.message.reply_text("❗ Post not found or not available.")
            await show_menu(update, context)
            return
    except Exception as e:
        logger.error(f"Error in show_comments_directly: {e}")
        await update.message.reply_text("❗ Sorry, there was an issue processing your request. Please try again.")
        await show_menu(update, context)
        return
    
    # Set the post for viewing
    context.user_data['viewing_post_id'] = post_id
    
    # Show comments starting from page 1
    try:
        logger.info(f"Getting paginated comments for post_id: {post_id}")
        comments_data, current_page, total_pages, total_comments = get_comments_paginated(post_id, 1)
        logger.info(f"Retrieved comments: data={len(comments_data) if comments_data else 0}, current_page={current_page}, total_pages={total_pages}, total_comments={total_comments}")
    except Exception as e:
        logger.error(f"Error getting paginated comments: {e}")
        await update.message.reply_text("❗ Sorry, there was an issue loading comments. Please try again.")
        await show_menu(update, context)
        return
    
    if not comments_data:
        keyboard = [
            [InlineKeyboardButton("💬 Add Comment", callback_data=f"add_comment_{post_id}")],
            [InlineKeyboardButton("🔙 Back to Post", callback_data=f"view_post_{post_id}")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💬 No comments yet\\. Be the first to comment\\!",
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        return
    
    user_id = update.effective_user.id
    
    # Send header message
    header_text = f"💬 *Comments \\({total_comments} total\\)*\\n*Page {current_page} of {total_pages}*"
    await update.message.reply_text(
        header_text,
        parse_mode="MarkdownV2"
    )
    
    import asyncio
    
    # Send each comment as a separate message with delay
    for comment_data in comments_data:
        comment = comment_data['comment']
        replies = comment_data['replies']
        total_replies = comment_data['total_replies']
        
        comment_id = comment[0]
        content = comment[1]
        timestamp = comment[2]
        likes = comment[3]
        dislikes = comment[4]
        
        # Get user reaction to current comment
        user_reaction = get_user_reaction(user_id, comment_id)
        like_emoji = "👍✅" if user_reaction == "like" else "👍"
        dislike_emoji = "👎✅" if user_reaction == "dislike" else "👎"
        
        # Format comment text (clean, no reaction info)
        comment_text = f"*Comment \\#{comment_id}*\\n\\n{escape_markdown_text(content)}\\n\\n{format_timestamp(timestamp)}"
        
        # Create reaction buttons with counts
        comment_keyboard = [
            [
                InlineKeyboardButton(f"{like_emoji} {likes}", callback_data=f"like_comment_{comment_id}"),
                InlineKeyboardButton(f"{dislike_emoji} {dislikes}", callback_data=f"dislike_comment_{comment_id}"),
                InlineKeyboardButton("💬 Reply", callback_data=f"reply_comment_{comment_id}"),
                InlineKeyboardButton("⚠️ Report", callback_data=f"report_comment_{comment_id}")
            ]
        ]
        comment_reply_markup = InlineKeyboardMarkup(comment_keyboard)
        
        # Send the comment
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=comment_text,
            reply_markup=comment_reply_markup,
            parse_mode="MarkdownV2"
        )
        
        # Delay after comment to show separation
        await asyncio.sleep(1.0)
        
        # Send replies if any
        if replies:
            for reply in replies:
                reply_id = reply[0]
                reply_content = reply[1]
                reply_timestamp = reply[2]
                reply_likes = reply[3]
                reply_dislikes = reply[4]
                
                # Get user reaction to this reply
                reply_user_reaction = get_user_reaction(user_id, reply_id)
                reply_like_emoji = "👍✅" if reply_user_reaction == "like" else "👍"
                reply_dislike_emoji = "👎✅" if reply_user_reaction == "dislike" else "👎"
                
                # Format the reply text (clean, no reaction info)
                reply_text = f"↳ *Reply \\#{reply_id}*\\n\\n{escape_markdown_text(reply_content)}\\n\\n{format_timestamp(reply_timestamp)}"
                
                # Create reaction buttons for reply
                reply_keyboard = [
                    [
                        InlineKeyboardButton(f"{reply_like_emoji} {reply_likes}", callback_data=f"like_comment_{reply_id}"),
                        InlineKeyboardButton(f"{reply_dislike_emoji} {reply_dislikes}", callback_data=f"dislike_comment_{reply_id}"),
                        InlineKeyboardButton("⚠️ Report", callback_data=f"report_comment_{reply_id}")
                    ]
                ]
                reply_reply_markup = InlineKeyboardMarkup(reply_keyboard)
                
                # Send the reply
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=reply_text,
                    reply_markup=reply_reply_markup,
                    parse_mode="MarkdownV2"
                )
                
                # Small delay between replies
                await asyncio.sleep(0.3)
        
        # Show remaining replies count if any
        if total_replies > len(replies):
            remaining_text = f"↳ \\.\\.\\. and {total_replies - len(replies)} more replies"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=remaining_text,
                parse_mode="MarkdownV2"
            )
    
    # Send navigation and action buttons at the end
    nav_keyboard = []
    
    # Navigation buttons
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"see_comments_{post_id}_{current_page-1}"))
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"see_comments_{post_id}_{current_page+1}"))
    
    if nav_buttons:
        nav_keyboard.append(nav_buttons)
    
    # Action buttons
    nav_keyboard.append([
        InlineKeyboardButton("💬 Add Comment", callback_data=f"add_comment_{post_id}"),
        InlineKeyboardButton("🔙 Back to Post", callback_data=f"view_post_{post_id}")
    ])
    nav_keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu")])
    
    nav_reply_markup = InlineKeyboardMarkup(nav_keyboard)
    
    # Send navigation message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📋 *Navigation*",
        reply_markup=nav_reply_markup,
        parse_mode="MarkdownV2"
    )

async def show_post_with_options(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Show post with comment and view options (from recent posts list)"""
    query = update.callback_query
    if query:
        await query.answer()
    
    post = get_post_by_id(post_id)
    if not post or post[13] != 1:  # Check if approved (approved field is at index 13, value 1 = approved)
        message_text = "❗ Post not found or not available."
        if query:
            await query.edit_message_text(message_text)
        else:
            await update.message.reply_text(message_text)
        return
    
    content = post[1]
    category = post[2]
    comment_count = get_comment_count(post_id)
    
    context.user_data['viewing_post_id'] = post_id
    
    post_text = f"""📝 *{escape_markdown_text(category)}*

{escape_markdown_text(content)}

*Comments:* {comment_count}

Choose what you'd like to do:"""
    
    keyboard = [
        [
            InlineKeyboardButton("💬 Add Comment", callback_data=f"add_comment_{post_id}"),
            InlineKeyboardButton(f"👀 See Comments ({comment_count})", callback_data=f"see_comments_{post_id}_1")
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(
            post_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(
            post_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )

async def see_comments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle see comments callback - Display comments separately"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Parse callback data: see_comments_POST_ID_PAGE
        if context.user_data.get('refresh_comments') and context.user_data.get('callback_data'):
            # This is a refresh from a reaction, use the stored data
            callback_data = context.user_data.get('callback_data')
            parts = callback_data.split("_")
            context.user_data['refresh_comments'] = False  # Reset flag
            context.user_data.pop('callback_data', None)  # Clean up
        else:
            # This is a regular navigation request
            logger.info(f"Processing see_comments callback with data: {query.data}")
            parts = query.data.split("_")
            logger.info(f"Split callback data: {parts}")
        
        post_id = int(parts[2])
        page = int(parts[3])
        logger.info(f"Parsed post_id: {post_id}, page: {page}")
        
        # Store current page in user_data for pagination reference
        context.user_data['current_page'] = page
        
        logger.info(f"Getting paginated comments for post_id: {post_id}, page: {page}")
        comments_data, current_page, total_pages, total_comments = get_comments_paginated(post_id, page)
        logger.info(f"Retrieved comments: data={len(comments_data) if comments_data else 0}, current_page={current_page}, total_pages={total_pages}, total_comments={total_comments}")
    except Exception as e:
        logger.error(f"Error in see_comments_callback: {e}")
        await query.edit_message_text(
            "❗ Sorry, there was an issue loading comments. Please try again."
        )
        return
    
    # First, delete the previous message and send header
    try:
        await query.delete_message()
    except:
        pass
    
    if not comments_data:
        keyboard = [
            [InlineKeyboardButton("💬 Add Comment", callback_data=f"add_comment_{post_id}")],
            [InlineKeyboardButton("🔙 Back to Post", callback_data=f"view_post_{post_id}")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="💬 No comments yet\\. Be the first to comment\\!",
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        return
    
    user_id = update.effective_user.id
    
    # Send header message
    header_text = f"💬 *Comments \\({total_comments} total\\)*\\n*Page {current_page} of {total_pages}*"
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=header_text,
        parse_mode="MarkdownV2"
    )
    
    import asyncio
    
    # Send each comment as a separate message with delay
    for comment_data in comments_data:
        comment = comment_data['comment']
        replies = comment_data['replies']
        total_replies = comment_data['total_replies']
        
        comment_id = comment[0]
        content = comment[1]
        timestamp = comment[2]
        likes = comment[3]
        dislikes = comment[4]
        
        # Get user reaction to current comment
        user_reaction = get_user_reaction(user_id, comment_id)
        like_emoji = "👍✅" if user_reaction == "like" else "👍"
        dislike_emoji = "👎✅" if user_reaction == "dislike" else "👎"
        
        # Format comment text (clean, no reaction info)
        comment_text = f"*Comment \\#{comment_id}*\\n\\n{escape_markdown_text(content)}\\n\\n{format_timestamp(timestamp)}"
        
        # Create reaction buttons with counts
        comment_keyboard = [
            [
                InlineKeyboardButton(f"{like_emoji} {likes}", callback_data=f"like_comment_{comment_id}"),
                InlineKeyboardButton(f"{dislike_emoji} {dislikes}", callback_data=f"dislike_comment_{comment_id}"),
                InlineKeyboardButton("💬 Reply", callback_data=f"reply_comment_{comment_id}"),
                InlineKeyboardButton("⚠️ Report", callback_data=f"report_comment_{comment_id}")
            ]
        ]
        comment_reply_markup = InlineKeyboardMarkup(comment_keyboard)
        
        # Send the comment
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=comment_text,
            reply_markup=comment_reply_markup,
            parse_mode="MarkdownV2"
        )
        
        # Delay after comment to show separation
        await asyncio.sleep(1.0)
        
        # Send replies if any
        if replies:
            for reply in replies:
                reply_id = reply[0]
                reply_content = reply[1]
                reply_timestamp = reply[2]
                reply_likes = reply[3]
                reply_dislikes = reply[4]
                
                # Get user reaction to this reply
                reply_user_reaction = get_user_reaction(user_id, reply_id)
                reply_like_emoji = "👍✅" if reply_user_reaction == "like" else "👍"
                reply_dislike_emoji = "👎✅" if reply_user_reaction == "dislike" else "👎"
                
                # Format the reply text (clean, no reaction info)
                reply_text = f"↳ *Reply \\#{reply_id}*\\n\\n{escape_markdown_text(reply_content)}\\n\\n{format_timestamp(reply_timestamp)}"
                
                # Create reaction buttons for reply
                reply_keyboard = [
                    [
                        InlineKeyboardButton(f"{reply_like_emoji} {reply_likes}", callback_data=f"like_comment_{reply_id}"),
                        InlineKeyboardButton(f"{reply_dislike_emoji} {reply_dislikes}", callback_data=f"dislike_comment_{reply_id}"),
                        InlineKeyboardButton("⚠️ Report", callback_data=f"report_comment_{reply_id}")
                    ]
                ]
                reply_reply_markup = InlineKeyboardMarkup(reply_keyboard)
                
                # Send the reply
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=reply_text,
                    reply_markup=reply_reply_markup,
                    parse_mode="MarkdownV2"
                )
                
                # Small delay between replies
                await asyncio.sleep(0.3)
        
        # Show remaining replies count if any
        if total_replies > len(replies):
            remaining_text = f"↳ \\.\\.\\. and {total_replies - len(replies)} more replies"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=remaining_text,
                parse_mode="MarkdownV2"
            )
    
    # Send navigation and action buttons at the end
    nav_keyboard = []
    
    # Navigation buttons
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"see_comments_{post_id}_{current_page-1}"))
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"see_comments_{post_id}_{current_page+1}"))
    
    if nav_buttons:
        nav_keyboard.append(nav_buttons)
    
    # Action buttons
    nav_keyboard.append([
        InlineKeyboardButton("💬 Add Comment", callback_data=f"add_comment_{post_id}"),
        InlineKeyboardButton("🔙 Back to Post", callback_data=f"view_post_{post_id}")
    ])
    nav_keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu")])
    
    nav_reply_markup = InlineKeyboardMarkup(nav_keyboard)
    
    # Send navigation message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📋 *Navigation*",
        reply_markup=nav_reply_markup,
        parse_mode="MarkdownV2"
    )




async def add_comment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle add comment callback"""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.split("_")[2])
    context.user_data['comment_post_id'] = post_id
    context.user_data['state'] = 'writing_comment'
    context.user_data.pop('reply_to_comment_id', None)  # Clear any reply state
    
    await query.edit_message_text(
        f"💬 *Writing a comment*\n\n"
        f"Type your comment below \\(max {MAX_COMMENT_LENGTH} characters\\)\\.\n\n"
        f"Use {CANCEL_BUTTON} to cancel\\.",
        parse_mode="MarkdownV2"
    )

async def handle_comment_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle comment text submission"""
    if update.message.text == CANCEL_BUTTON:
        await show_menu(update, context, "🏠 Comment cancelled. Returned to main menu.")
        return
    
    content = sanitize_content(update.message.text)
    if not content:
        await update.message.reply_text("❗ Your comment contains inappropriate content. Please try again.")
        return
    
    if len(content) > MAX_COMMENT_LENGTH:
        await update.message.reply_text(f"❗ Your comment is too long. Please keep it under {MAX_COMMENT_LENGTH} characters.")
        return
    
    post_id = context.user_data.get('comment_post_id')
    reply_to_comment_id = context.user_data.get('reply_to_comment_id')
    user_id = update.message.from_user.id
    
    comment_id, error = save_comment(post_id, content, user_id, reply_to_comment_id)
    
    if error:
        await update.message.reply_text(f"❗ Error saving comment: {error}")
        return
    
    # Update the comment count on the channel message
    try:
        from comments import update_channel_message_comment_count
        success, result = await update_channel_message_comment_count(context, post_id)
        if success:
            logger.info(f"Updated channel message comment count for post {post_id}: {result}")
        else:
            logger.warning(f"Failed to update channel message for post {post_id}: {result}")
    except Exception as e:
        logger.error(f"Error updating channel message for post {post_id}: {e}")
    
    # Message for normal comment vs. reply
    if reply_to_comment_id:
        await update.message.reply_text("✅ Your reply was posted successfully!")
    else:
        await update.message.reply_text("✅ Comment posted successfully!")
    
    # Show the post with options to add more comments or view comments
    await show_post_with_options(update, context, post_id)

# User Stats - FIXED IMPLEMENTATION
async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show comprehensive user statistics"""
    user_id = update.message.from_user.id
    stats = get_user_stats(user_id)
    
    if not stats:
        await update.message.reply_text("❗ No statistics available. Submit your first confession!")
        await show_menu(update, context)
        return
    
    join_date = format_join_date(stats['join_date'])
    
    stats_text = f"""
📊 *Your Statistics*

*User Info:*
• User ID: `{stats['user_id']}`
• Joined: {escape_markdown_text(join_date)}
• Status: {'🚫 Blocked' if stats['blocked'] else '✅ Active'}

*Confession Stats:*
• Total Submitted: {stats['total_confessions']}
• Approved: {stats['approved_confessions']}
• Pending: {stats['pending_confessions']}
• Rejected: {stats['rejected_confessions']}

*Comment Stats:*
• Comments Posted: {stats['comments_posted']}
• Likes Received: {stats['likes_received']}
"""
    
    keyboard = [
        [InlineKeyboardButton("📝 View My Confessions", callback_data="view_my_confessions")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def view_my_confessions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's confession history one by one with See Comments buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    posts = get_user_posts(user_id, 10)
    
    if not posts:
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Stats", callback_data="back_to_stats")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 You haven't submitted any confessions yet\\!\n\n"
            "Use '🙊 Confess/Ask Question' to submit your first confession\\.",
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        return
    
    # Delete the original stats message
    try:
        await query.delete_message()
    except:
        pass
    
    # Send header message
    header_text = f"📝 *Your Recent Confessions \\({len(posts)} total\\)*"
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=header_text,
        parse_mode="MarkdownV2"
    )
    
    import asyncio
    
    # Send each confession as a separate message
    for post in posts:
        post_id = post[0]
        content = post[1]
        category = post[2]
        timestamp = post[3]
        approved = post[4]
        comment_count = post[5]
        
        status_emoji = "✅" if approved == 1 else "⏳" if approved is None else "❌"
        status_text = "Approved" if approved == 1 else "Pending" if approved is None else "Rejected"
        
        # Format timestamp without double escaping
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            formatted_timestamp = dt.strftime('%Y-%m-%d %H:%M')
            escaped_timestamp = escape_markdown_text(formatted_timestamp)
        except:
            escaped_timestamp = escape_markdown_text(str(timestamp))
        
        # Format the confession message
        confession_text = f"*{escape_markdown_text(category)}*\n\n{escape_markdown_text(content)}\n\n"
        confession_text += f"*\\#{post_id}* {status_emoji} {escape_markdown_text(status_text)} \\| "
        confession_text += f"💬 {comment_count} comments \\| {escaped_timestamp}"
        
        # Create buttons based on approval status
        keyboard = []
        if approved == 1:  # Only approved posts can have comments viewed
            keyboard.append([
                InlineKeyboardButton(f"👀 See Comments ({comment_count})", callback_data=f"see_comments_{post_id}_1")
            ])
        
        # Always show view post button for approved posts
        if approved == 1:
            keyboard.append([
                InlineKeyboardButton("📖 View Full Post", callback_data=f"view_post_{post_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        # Send the confession message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=confession_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        
        # Small delay between confessions
        await asyncio.sleep(0.5)
    
    # Send navigation message at the end
    nav_keyboard = [
        [InlineKeyboardButton("🔙 Back to Stats", callback_data="back_to_stats")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
    ]
    nav_reply_markup = InlineKeyboardMarkup(nav_keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📋 *Navigation*",
        reply_markup=nav_reply_markup,
        parse_mode="MarkdownV2"
    )

async def back_to_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to stats from confession history"""
    query = update.callback_query
    await query.answer()
    
    # Simulate calling my_stats but through callback
    user_id = update.effective_user.id
    stats = get_user_stats(user_id)
    
    if not stats:
        await query.edit_message_text("❗ No statistics available.")
        return
    
    join_date = format_join_date(stats['join_date'])
    
    stats_text = f"""
📊 *Your Statistics*

*User Info:*
• User ID: `{stats['user_id']}`
• Joined: {escape_markdown_text(join_date)}
• Status: {'🚫 Blocked' if stats['blocked'] else '✅ Active'}

*Confession Stats:*
• Total Submitted: {stats['total_confessions']}
• Approved: {stats['approved_confessions']}
• Pending: {stats['pending_confessions']}
• Rejected: {stats['rejected_confessions']}

*Comment Stats:*
• Comments Posted: {stats['comments_posted']}
• Likes Received: {stats['likes_received']}
"""
    
    keyboard = [
        [InlineKeyboardButton("📝 View My Confessions", callback_data="view_my_confessions")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

# Contact Admin - FIXED IMPLEMENTATION
async def start_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start contact admin flow"""
    await update.message.reply_text(
        "📞 *Contact Admin*\n\n"
        "Please write your message to the administrators\\. "
        "This could be feedback, suggestions, ideas, or any other message\\.\n\n"
        "Your message will be sent anonymously and admins can reply to you\\.\n\n"
        f"Type your message or use {CANCEL_BUTTON} to return to menu:",
        parse_mode="MarkdownV2"
    )
    context.user_data['state'] = 'contacting_admin'

async def handle_admin_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin contact message"""
    if update.message.text == CANCEL_BUTTON:
        await show_menu(update, context, "🏠 Contact cancelled. Returned to main menu.")
        return
    
    user_id = update.message.from_user.id
    message = update.message.text
    
    # Save message and send to admins
    success, result = await send_message_to_admins(context, user_id, message)
    
    if success:
        await update.message.reply_text(
            "✅ *Message Sent\\!*\n\n"
            "Your message has been sent to the administrators\\. "
            "They may reply to you anonymously\\.",
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(
            f"❌ *Failed to send message:* {result}\n\n"
            "Please try again later or contact the administrators directly\\.",
            parse_mode="MarkdownV2"
        )
    
    await show_menu(update, context)

async def handle_admin_reply_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin typed reply message"""
    user_id = update.message.from_user.id
    
    # Check if user is admin
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin features.")
        context.user_data.pop('state', None)
        return
    
    # Get the message ID we're replying to
    message_id = context.user_data.get('replying_to_message_id')
    if not message_id:
        await update.message.reply_text("❗ Error: No message to reply to found.")
        context.user_data.pop('state', None)
        return
    
    reply_text = update.message.text
    
    try:
        success, result = await send_admin_reply_to_user(context, message_id, user_id, reply_text)
        
        if success:
            await update.message.reply_text(
                "✅ *Reply sent successfully\\!*\n\n"
                f"Your reply has been sent anonymously to the user\\.",
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                f"❗ *Failed to send reply:* {result}\n\n"
                "Please try again or use the /reply command\\.",
                parse_mode="MarkdownV2"
            )
    
    except Exception as e:
        await update.message.reply_text(f"❗ Error sending reply: {str(e)}")
    
    # Clear the admin reply state
    context.user_data.pop('state', None)
    context.user_data.pop('replying_to_message_id', None)

# Smart Notifications
async def show_smart_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show smart notifications settings and overview"""
    from notifications import show_notification_settings
    await show_notification_settings(update, context)

# Daily Digest
async def daily_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's confessions individually"""
    from submission import get_todays_posts
    posts = get_todays_posts()
    
    if not posts:
        await update.message.reply_text("📅 No confessions posted today yet\\. Check back later\\!", parse_mode="MarkdownV2")
        await show_menu(update, context)
        return
    
    # Send header message
    header_text = f"📅 *Today's Confessions \\({len(posts)} total\\)*"
    await update.message.reply_text(
        header_text,
        parse_mode="MarkdownV2"
    )
    
    import asyncio
    from datetime import datetime
    
    # Send each confession as a separate message
    for post in posts:
        post_id = post[0]
        content = post[1]
        category = post[2]
        timestamp = post[3]
        comment_count = post[5]
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            formatted_timestamp = dt.strftime('%H:%M')
            escaped_timestamp = escape_markdown_text(formatted_timestamp)
        except:
            escaped_timestamp = escape_markdown_text(str(timestamp))
        
        # Format the confession message
        confession_text = f"*{escape_markdown_text(category)}*\n\n{escape_markdown_text(content)}\n\n"
        confession_text += f"*\\#{post_id}* \\| 💬 {comment_count} comments \\| {escaped_timestamp}"
        
        # Create buttons for each confession
        keyboard = [
            [
                InlineKeyboardButton(f"👀 See Comments ({comment_count})", callback_data=f"see_comments_{post_id}_1"),
                InlineKeyboardButton("📖 View Full Post", callback_data=f"view_post_{post_id}")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the confession message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=confession_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        
        # Small delay between confessions
        await asyncio.sleep(0.5)
    
    # Send navigation message at the end
    nav_keyboard = [
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
    ]
    nav_reply_markup = InlineKeyboardMarkup(nav_keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📋 *Navigation*",
        reply_markup=nav_reply_markup,
        parse_mode="MarkdownV2"
    )

# Callback Handlers
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries"""
    query = update.callback_query
    await query.answer()
    
    if not query.data:
        return
    
    data = query.data
    user_id = update.effective_user.id
    
    # Admin callbacks
    if data.startswith(("approve_", "reject_", "flag_", "block_", "unblock_")):
        await admin_callback(update, context)
        return
    
    # Category selection
    if data.startswith("category_") or data == "categories_done":
        await category_callback(update, context)
        return
    
    # Cancel to menu
    if data == "cancel_to_menu" or data == "menu":
        await clear_user_context(context)
        await query.edit_message_text("🏠 Returned to main menu\\. Please use the menu below\\.", parse_mode="MarkdownV2")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="What would you like to do next?",
            reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        )
        return
    
    # View post
    if data.startswith("view_post_"):
        post_id = int(data.replace("view_post_", ""))
        await show_post_with_options(update, context, post_id)
        return
    
    # Add comment
    if data.startswith("add_comment_"):
        await add_comment_callback(update, context)
        return
    
    # See comments
    if data.startswith("see_comments_"):
        await see_comments_callback(update, context)
        return
    
    # Notification callbacks
    if data.startswith(("notification_settings", "toggle_comment_notif", "toggle_daily_digest", "toggle_trending", "manage_categories", "set_digest_time", "notification_history", "set_time_", "cat_toggle_", "cat_select_all", "cat_clear_all", "test_notification", "callback_trending", "callback_popular")):
        from notifications import handle_notification_callback
        await handle_notification_callback(update, context)
        return
    
    # User stats functions
    if data == "view_my_confessions":
        await view_my_confessions_callback(update, context)
        return
    
    if data == "back_to_stats":
        await back_to_stats_callback(update, context)
        return
    
    # Like comment
    if data.startswith("like_comment_"):
        comment_id = int(data.replace("like_comment_", ""))
        success, action, likes, dislikes = react_to_comment(user_id, comment_id, "like")
        
        if success:
            # Update the current message with new reaction counts
            comment = get_comment_by_id(comment_id)
            if comment:
                # Get updated reaction info
                user_reaction = get_user_reaction(user_id, comment_id)
                like_emoji = "👍✅" if user_reaction == "like" else "👍"
                dislike_emoji = "👎✅" if user_reaction == "dislike" else "👎"
                
                # Check if this is a reply or main comment
                if comment[4]:  # parent_comment_id exists, so it's a reply
                    comment_text = f"↳ *Reply \\#{comment_id}*\\n\\n{escape_markdown_text(comment[3])}\\n\\n{format_timestamp(comment[5])}"
                else:
                    comment_text = f"*Comment \\#{comment_id}*\\n\\n{escape_markdown_text(comment[3])}\\n\\n{format_timestamp(comment[5])}"
                
                # Create updated keyboard
                if comment[4]:  # Reply
                    updated_keyboard = [
                        [
                            InlineKeyboardButton(f"{like_emoji} {likes}", callback_data=f"like_comment_{comment_id}"),
                            InlineKeyboardButton(f"{dislike_emoji} {dislikes}", callback_data=f"dislike_comment_{comment_id}"),
                            InlineKeyboardButton("⚠️ Report", callback_data=f"report_comment_{comment_id}")
                        ]
                    ]
                else:  # Main comment
                    updated_keyboard = [
                        [
                            InlineKeyboardButton(f"{like_emoji} {likes}", callback_data=f"like_comment_{comment_id}"),
                            InlineKeyboardButton(f"{dislike_emoji} {dislikes}", callback_data=f"dislike_comment_{comment_id}"),
                            InlineKeyboardButton("💬 Reply", callback_data=f"reply_comment_{comment_id}"),
                            InlineKeyboardButton("⚠️ Report", callback_data=f"report_comment_{comment_id}")
                        ]
                    ]
                
                updated_reply_markup = InlineKeyboardMarkup(updated_keyboard)
                
                try:
                    await query.edit_message_text(
                        comment_text,
                        reply_markup=updated_reply_markup,
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logger.error(f"Error updating comment message: {e}")
            
            # Show feedback
            if action == "added":
                await query.answer(f"👍 Liked! ({likes})")
            elif action == "removed":
                await query.answer(f"👍 Like removed! ({likes})")
            elif action == "changed":
                await query.answer(f"👍 Changed to like! ({likes})")
        else:
            await query.answer("❗ Error liking comment")
        return
        
        # Refresh the comments view by calling the function directly with proper data
        comment = get_comment_by_id(comment_id)
        if comment:
            post_id = comment[1]
            page = context.user_data.get('current_page', 1)
            
            # Call the comments display directly
            try:
                comments_data, current_page, total_pages, total_comments = get_comments_paginated(post_id, page)
                
                # Build and update the message with refreshed like/dislike counts
                text = f"💬 *Comments \\({total_comments} total\\)*\n*Page {current_page} of {total_pages}*\n\n"
                keyboard = []
                
                for comment_data in comments_data:
                    comment = comment_data['comment']
                    replies = comment_data['replies']
                    total_replies = comment_data['total_replies']
                    
                    comment_id = comment[0]
                    content = comment[1]
                    timestamp = comment[2]
                    likes = comment[3]
                    dislikes = comment[4]
                    
                    # Format comment
                    text += f"*Comment \\#{comment_id}*\n"
                    text += f"{escape_markdown_text(content)}\n"
                    text += f"👍 {likes} \\| 👎 {dislikes} \\| {format_timestamp(timestamp)}\n"
                    
                    # Add replies if any
                    if replies:
                        for reply in replies:
                            reply_content = reply[1]
                            text += f"↳ {escape_markdown_text(truncate_text(reply_content, 60))}\n"
                    
                    if total_replies > len(replies):
                        text += f"↳ \\.\\.\\. and {total_replies - len(replies)} more replies\n"
                    
                    text += "\n"
                    
                    # Add reaction buttons for this comment immediately after it
                    comment_row = [
                        InlineKeyboardButton("👍", callback_data=f"like_comment_{comment_id}"),
                        InlineKeyboardButton("👎", callback_data=f"dislike_comment_{comment_id}"),
                        InlineKeyboardButton("💬", callback_data=f"reply_comment_{comment_id}"),
                        InlineKeyboardButton("⚠️", callback_data=f"report_comment_{comment_id}")
                    ]
                    keyboard.append(comment_row)
                    
                    # Add a separator row between comments (except for the last one)
                    if comment_data != comments_data[-1]:
                        keyboard.append([InlineKeyboardButton("─────", callback_data="separator")])
                
                # Navigation buttons
                nav_buttons = []
                if current_page > 1:
                    nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"see_comments_{post_id}_{current_page-1}"))
                if current_page < total_pages:
                    nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"see_comments_{post_id}_{current_page+1}"))
                
                if nav_buttons:
                    keyboard.append(nav_buttons)
                
                # Action buttons
                keyboard.append([
                    InlineKeyboardButton("💬 Add Comment", callback_data=f"add_comment_{post_id}"),
                    InlineKeyboardButton("🔙 Back to Post", callback_data=f"view_post_{post_id}")
                ])
                keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                logger.error(f"Error refreshing comments view: {e}")
        return
    
    # Dislike comment
    if data.startswith("dislike_comment_"):
        comment_id = int(data.replace("dislike_comment_", ""))
        success, action, likes, dislikes = react_to_comment(user_id, comment_id, "dislike")
        
        if success:
            # Update the current message with new reaction counts
            comment = get_comment_by_id(comment_id)
            if comment:
                # Get updated reaction info
                user_reaction = get_user_reaction(user_id, comment_id)
                like_emoji = "👍✅" if user_reaction == "like" else "👍"
                dislike_emoji = "👎✅" if user_reaction == "dislike" else "👎"
                
                # Check if this is a reply or main comment
                if comment[4]:  # parent_comment_id exists, so it's a reply
                    comment_text = f"↳ *Reply \\#{comment_id}*\\n\\n{escape_markdown_text(comment[3])}\\n\\n{format_timestamp(comment[5])}"
                else:
                    comment_text = f"*Comment \\#{comment_id}*\\n\\n{escape_markdown_text(comment[3])}\\n\\n{format_timestamp(comment[5])}"
                
                # Create updated keyboard
                if comment[4]:  # Reply
                    updated_keyboard = [
                        [
                            InlineKeyboardButton(f"{like_emoji} {likes}", callback_data=f"like_comment_{comment_id}"),
                            InlineKeyboardButton(f"{dislike_emoji} {dislikes}", callback_data=f"dislike_comment_{comment_id}"),
                            InlineKeyboardButton("⚠️ Report", callback_data=f"report_comment_{comment_id}")
                        ]
                    ]
                else:  # Main comment
                    updated_keyboard = [
                        [
                            InlineKeyboardButton(f"{like_emoji} {likes}", callback_data=f"like_comment_{comment_id}"),
                            InlineKeyboardButton(f"{dislike_emoji} {dislikes}", callback_data=f"dislike_comment_{comment_id}"),
                            InlineKeyboardButton("💬 Reply", callback_data=f"reply_comment_{comment_id}"),
                            InlineKeyboardButton("⚠️ Report", callback_data=f"report_comment_{comment_id}")
                        ]
                    ]
                
                updated_reply_markup = InlineKeyboardMarkup(updated_keyboard)
                
                try:
                    await query.edit_message_text(
                        comment_text,
                        reply_markup=updated_reply_markup,
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logger.error(f"Error updating comment message: {e}")
            
            # Show feedback
            if action == "added":
                await query.answer(f"👎 Disliked! ({dislikes})")
            elif action == "removed":
                await query.answer(f"👎 Dislike removed! ({dislikes})")
            elif action == "changed":
                await query.answer(f"👎 Changed to dislike! ({dislikes})")

    
    # Reply to comment
    if data.startswith("reply_comment_"):
        comment_id = int(data.replace("reply_comment_", ""))
        comment = get_comment_by_id(comment_id)
        
        if comment:
            post_id = comment[1]
            context.user_data['comment_post_id'] = post_id
            context.user_data['reply_to_comment_id'] = comment_id
            context.user_data['state'] = 'writing_comment'
            
            comment_preview = truncate_text(comment[3], 100)
            
            await query.edit_message_text(
                f"💬 *Replying to comment \\#{comment_id}*\n\n"
                f"*Original:* {escape_markdown_text(comment_preview)}\n\n"
                f"Write your reply \\(max {MAX_COMMENT_LENGTH} characters\\)\\:\n\n"
                f"Type your reply below or use {CANCEL_BUTTON} to cancel\\:",
                parse_mode="MarkdownV2"
            )
        return
    
    # Report comment
    if data.startswith("report_comment_"):
        comment_id = int(data.replace("report_comment_", ""))
        report_count = report_abuse(user_id, "comment", comment_id, "User reported via bot")
        await query.answer("🚩 Comment reported! Admins will review it.")
        
        # Notify admins if report threshold reached
        if report_count >= 5:
            try:
                await notify_admins_about_reports(context, "comment", comment_id, report_count)
            except Exception as e:
                print(f"Failed to notify admins about reported comment {comment_id}: {e}")
        
        return
    
    # Admin dashboard callbacks
    if data == "admin_dashboard":
        await admin_dashboard_callback(update, context)
        return
    
    if data == "admin_analytics":
        await admin_analytics(update, context)
        return
        
    if data == "admin_users":
        await admin_user_management(update, context)
        return
        
    if data == "admin_blocked_users":
        await admin_blocked_users(update, context)
        return
        
    if data == "admin_active_users":
        await admin_active_users(update, context)
        return
        
    if data.startswith("admin_unblock_"):
        await admin_unblock_user_callback(update, context)
        return
        
    if data.startswith("admin_block_"):
        await admin_block_user_callback(update, context)
        return
        
    if data.startswith("admin_user_info_"):
        await admin_user_info_callback(update, context)
        return
        
    if data == "admin_content":
        await admin_content_management(update, context)
        return
        
    if data == "admin_moderation":
        await admin_moderation_panel(update, context)
        return
        
    if data == "admin_messages":
        await admin_messages_panel(update, context)
        return
        
    if data == "admin_system":
        await admin_system_info(update, context)
        return

    # Admin message management callbacks
    if data.startswith("admin_reply_"):
        await handle_admin_reply_callback(update, context)
        return
    
    if data.startswith("admin_history_"):
        await handle_admin_history_callback(update, context)
        return
    
    if data.startswith("admin_read_"):
        await handle_admin_read_callback(update, context)
        return
    
    if data.startswith("admin_ignore_"):
        await handle_admin_ignore_callback(update, context)
        return
    
    # Notification callbacks
    from notifications import handle_notification_callback
    if data.startswith(("notification_", "toggle_", "manage_", "unsub_", "test_notification")):
        await handle_notification_callback(update, context)
        return

# Admin message callback handlers
async def handle_admin_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quick reply button press from admin"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id not in ADMIN_IDS:
        await query.answer("❗ You are not authorized to use admin features.")
        return
    
    # Extract message ID from callback data
    message_id = int(query.data.replace("admin_reply_", ""))
    
    # Store the message ID in context for reply handling
    context.user_data['replying_to_message_id'] = message_id
    context.user_data['state'] = 'admin_replying'
    
    await query.edit_message_text(
        f"💬 *Quick Reply to Message \\#{message_id}*\n\n"
        f"Please type your reply message\\. It will be sent anonymously to the user\\.",
        parse_mode="MarkdownV2"
    )

async def handle_admin_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle view history button press from admin"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id not in ADMIN_IDS:
        await query.answer("❗ You are not authorized to use admin features.")
        return
    
    # Extract user ID from callback data
    sender_user_id = int(query.data.replace("admin_history_", ""))
    
    try:
        from admin_messaging import get_user_message_history
        history = get_user_message_history(sender_user_id)
        
        if not history:
            await query.answer("📋 No message history found for this user.")
            return
        
        history_text = f"📋 *Message History for User {sender_user_id}*\n\n"
        
        for i, (msg_id, content, timestamp, replied, reply_text) in enumerate(history[-10:], 1):  # Last 10 messages
            history_text += f"*Message \\#{msg_id}*\n"
            history_text += f"Time: {escape_markdown_text(timestamp[:16])}\n"
            history_text += f"Content: {escape_markdown_text(truncate_text(content, 80))}\n"
            if replied:
                reply_preview = truncate_text(reply_text, 50) if reply_text else "[Reply sent]"
                history_text += f"Reply: {escape_markdown_text(reply_preview)}\n"
            else:
                history_text += "Status: Unread\n"
            history_text += "\n"
        
        # Limit message length
        if len(history_text) > 4000:
            history_text = history_text[:4000] + "\n\n\\.\\.\\. *Message truncated*"
        
        await query.edit_message_text(
            history_text,
            parse_mode="MarkdownV2"
        )
    
    except Exception as e:
        await query.answer(f"❗ Error retrieving message history: {str(e)}")

async def handle_admin_read_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mark as read button press from admin"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id not in ADMIN_IDS:
        await query.answer("❗ You are not authorized to use admin features.")
        return
    
    # Extract message ID from callback data
    message_id = int(query.data.replace("admin_read_", ""))
    
    try:
        from admin_messaging import mark_message_as_read
        success = mark_message_as_read(message_id)
        
        if success:
            await query.answer("✅ Message marked as read!")
            await query.edit_message_text(
                f"✅ *Message \\#{message_id} marked as read*\n\n"
                f"This message has been marked as handled\\.",
                parse_mode="MarkdownV2"
            )
        else:
            await query.answer("❗ Failed to mark message as read")
    
    except Exception as e:
        await query.answer(f"❗ Error: {str(e)}")

async def handle_admin_ignore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ignore user button press from admin"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id not in ADMIN_IDS:
        await query.answer("❗ You are not authorized to use admin features.")
        return
    
    # Extract user ID from callback data
    sender_user_id = int(query.data.replace("admin_ignore_", ""))
    
    try:
        from admin_messaging import ignore_user_messages
        success = ignore_user_messages(sender_user_id)
        
        if success:
            await query.answer("🔇 User messages will be ignored!")
            await query.edit_message_text(
                f"🔇 *User {sender_user_id} ignored*\n\n"
                f"Future messages from this user will be automatically marked as ignored\\.",
                parse_mode="MarkdownV2"
            )
        else:
            await query.answer("❗ Failed to ignore user")
    
    except Exception as e:
        await query.answer(f"❗ Error: {str(e)}")

# Admin Commands
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command for administrators"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    admin_text = """
🔧 *Admin Panel*

*Basic Commands:*
• `/stats` \\- View channel statistics
• `/pending` \\- View pending submissions
• `/messages` \\- View pending user messages
• `/reply <message_id> <reply>` \\- Reply to user message
• `/admin` \\- Show this help

*Report Management:*
• `/reports` \\- View reported content

*User Management:*
• `/users [user_id]` \\- View user info or management help
• `/block <user_id>` \\- Block a user
• `/unblock <user_id>` \\- Unblock a user
• `/blocked` \\- List blocked users

*Manual Actions:*
• Use approval buttons when posts are submitted
• Monitor user activity and reports
"""
    
    await update.message.reply_text(admin_text, parse_mode="MarkdownV2")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command for administrators"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    stats = get_channel_stats()
    
    stats_text = f"""
📊 *Channel Statistics*

*Content:*
• Total Posts: {stats['total_posts']}
• Total Comments: {stats['total_comments']}
• Pending Posts: {stats['pending_posts']}

*Users:*
• Total Users: {stats['total_users']}

*Moderation:*
• Flagged Posts: {stats['flagged_posts']}
• Flagged Comments: {stats['flagged_comments']}
• Total Reactions: {stats['total_reactions']}
"""
    
    await update.message.reply_text(stats_text, parse_mode="MarkdownV2")

async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pending command to show pending submissions"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    pending_posts = get_pending_submissions()
    
    if not pending_posts:
        await update.message.reply_text("✅ No pending submissions.")
        return
    
    for post in pending_posts[:5]:  # Show first 5 pending posts
        post_id, content, category, timestamp, user_id, approved, channel_message_id, flagged, likes = post
        
        admin_text = f"""
📝 *Pending Submission {escape_markdown_text(f'#{post_id}')}*

*Category:* {escape_markdown_text(category)}
*Submitter:* {user_id}
*Time:* {timestamp[:16] if timestamp else 'Unknown'}

*Content:*
{escape_markdown_text(content)}
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}")
            ],
            [
                InlineKeyboardButton("🚩 Flag", callback_data=f"flag_{post_id}"),
                InlineKeyboardButton("⛔ Block User", callback_data=f"block_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            admin_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )

async def messages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /messages command to show pending user messages"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    pending_messages = get_pending_messages()
    
    if not pending_messages:
        await update.message.reply_text("✅ No pending user messages.")
        return
    
    messages_text = "📨 *Pending User Messages:*\n\n"
    
    for message in pending_messages[:10]:  # Show latest 10 messages
        message_id, sender_id, message_content, timestamp = message
        messages_text += f"*Message {escape_markdown_text(f'#{message_id}')}*\n"
        messages_text += f"From: {sender_id}\n"
        messages_text += f"Time: {escape_markdown_text(timestamp[:16])}\n"
        messages_text += f"Content: {escape_markdown_text(truncate_text(message_content, 100))}\n"
        messages_text += f"Reply with: `/reply {message_id} <your_message>`\n\n"
    
    await update.message.reply_text(messages_text, parse_mode="MarkdownV2")

async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reply command for admin responses"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❗ Usage: /reply <message_id> <your_reply>")
        return
    
    try:
        message_id = int(context.args[0])
        reply_text = " ".join(context.args[1:])
        
        success, result = await send_admin_reply_to_user(context, message_id, user_id, reply_text)
        
        if success:
            await update.message.reply_text("✅ Reply sent successfully!")
        else:
            await update.message.reply_text(f"❗ Failed to send reply: {result}")
    
    except ValueError:
        await update.message.reply_text("❗ Invalid message ID. Must be a number.")
    except Exception as e:
        await update.message.reply_text(f"❗ Error: {str(e)}")

async def reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reports command to show reported content"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    from moderation import get_reports
    reports = get_reports()
    
    if not reports:
        await update.message.reply_text("✅ No reports found.")
        return
    
    # Group reports by target
    from collections import defaultdict
    reports_by_target = defaultdict(list)
    
    for report in reports:
        report_id, user_id, target_type, target_id, reason, timestamp = report
        reports_by_target[(target_type, target_id)].append(report)
    
    reports_text = "🚩 *Reported Content:*\n\n"
    
    for (target_type, target_id), target_reports in reports_by_target.items():
        report_count = len(target_reports)
        first_report = target_reports[0]
        
        # Get content details
        from moderation import get_content_details
        content_details = get_content_details(target_type, target_id)
        
        if content_details:
            if target_type == 'comment':
                comment_id, post_id, content, timestamp = content_details
                preview = truncate_text(content, 100)
                reports_text += f"📝 *Comment \\#{comment_id}* \\(Post \\#{post_id}\\)\n"
                reports_text += f"Reports: {report_count}\n"
                reports_text += f"Content: {escape_markdown_text(preview)}\n\n"
            else:  # post
                post_id, content, category, timestamp = content_details
                preview = truncate_text(content, 100)
                reports_text += f"📝 *Post \\#{post_id}*\n"
                reports_text += f"Category: {escape_markdown_text(category)}\n"
                reports_text += f"Reports: {report_count}\n"
                reports_text += f"Content: {escape_markdown_text(preview)}\n\n"
        else:
            reports_text += f"❓ *{target_type.title()} \\#{target_id}* \\(Content not found\\)\n"
            reports_text += f"Reports: {report_count}\n\n"
    
    # Split long messages
    if len(reports_text) > 4000:
        reports_text = reports_text[:4000] + "\n\n\\.\\.\\. *Message truncated*"
    
    await update.message.reply_text(reports_text, parse_mode="MarkdownV2")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /users command to show user management options"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    if context.args:
        # Handle specific user ID
        try:
            target_user_id = int(context.args[0])
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, username, first_name, last_name, join_date, questions_asked, comments_posted, blocked FROM users WHERE user_id = ?",
                    (target_user_id,)
                )
                user_data = cursor.fetchone()
                
                if not user_data:
                    await update.message.reply_text(f"❗ User {target_user_id} not found in database.")
                    return
                
                uid, username, first_name, last_name, join_date, questions_asked, comments_posted, blocked = user_data
                
                status = "🚫 Blocked" if blocked else "✅ Active"
                name = f"{first_name or ''} {last_name or ''}".strip()
                
                user_text = f"""
👤 *User Information*

*Details:*
• User ID: `{uid}`
• Username: {f"@{escape_markdown_text(username)}" if username else "None"}
• Name: {escape_markdown_text(name) if name else "None"}
• Status: {status}
• Joined: {escape_markdown_text(join_date[:16]) if join_date else "Unknown"}

*Activity:*
• Confessions Posted: {questions_asked}
• Comments Posted: {comments_posted}

*Actions:*
• `/block {uid}` \\- Block user
• `/unblock {uid}` \\- Unblock user
• `/userstats {uid}` \\- View detailed stats
"""
                
                await update.message.reply_text(user_text, parse_mode="MarkdownV2")
                return
                
        except ValueError:
            await update.message.reply_text("❗ Invalid user ID. Must be a number.")
            return
    
    # Show general user management help
    users_text = """
👥 *User Management*

*Commands:*
• `/users <user_id>` \\- View specific user info
• `/block <user_id>` \\- Block a user
• `/unblock <user_id>` \\- Unblock a user
• `/blocked` \\- List blocked users

*Examples:*
• `/users 123456789`
• `/block 123456789`
• `/unblock 123456789`
"""
    
    await update.message.reply_text(users_text, parse_mode="MarkdownV2")

async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /block command to block a user"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    if not context.args:
        await update.message.reply_text("❗ Usage: /block <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        from approval import block_user, is_blocked_user
        
        if is_blocked_user(target_user_id):
            await update.message.reply_text(f"❗ User {target_user_id} is already blocked.")
            return
        
        block_user(target_user_id)
        await update.message.reply_text(f"⛔ User {target_user_id} has been blocked.")
        
    except ValueError:
        await update.message.reply_text("❗ Invalid user ID. Must be a number.")
    except Exception as e:
        await update.message.reply_text(f"❗ Error blocking user: {str(e)}")

async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unblock command to unblock a user"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    if not context.args:
        await update.message.reply_text("❗ Usage: /unblock <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        from approval import unblock_user, is_blocked_user
        
        if not is_blocked_user(target_user_id):
            await update.message.reply_text(f"❗ User {target_user_id} is not blocked.")
            return
        
        unblock_user(target_user_id)
        await update.message.reply_text(f"✅ User {target_user_id} has been unblocked.")
        
    except ValueError:
        await update.message.reply_text("❗ Invalid user ID. Must be a number.")
    except Exception as e:
        await update.message.reply_text(f"❗ Error unblocking user: {str(e)}")

async def blocked_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /blocked command to show blocked users"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin commands.")
        return
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, first_name, last_name, join_date FROM users WHERE blocked = 1 ORDER BY join_date DESC"
        )
        blocked_users = cursor.fetchall()
    
    if not blocked_users:
        await update.message.reply_text("✅ No blocked users found.")
        return
    
    blocked_text = "⛔ *Blocked Users:*\n\n"
    
    for user_data in blocked_users[:20]:  # Show max 20 users
        uid, username, first_name, last_name, join_date = user_data
        name = f"{first_name or ''} {last_name or ''}".strip()
        
        blocked_text += f"• `{uid}` \\- "
        if username:
            blocked_text += f"@{escape_markdown_text(username)}"
        elif name:
            blocked_text += escape_markdown_text(name)
        else:
            blocked_text += "No name"
        blocked_text += f" \\(joined {escape_markdown_text(join_date[:10]) if join_date else 'Unknown'}\\)\n"
    
    blocked_text += f"\n*Total blocked users:* {len(blocked_users)}\n\n"
    blocked_text += "*Use `/unblock <user_id>` to unblock a user\\.*"
    
    await update.message.reply_text(blocked_text, parse_mode="MarkdownV2")

# Admin Dashboard - Interactive Interface
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show comprehensive admin dashboard with interactive buttons"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❗ You are not authorized to use admin features.")
        return
    
    # Get quick stats
    stats = get_channel_stats()
    pending_posts = len(get_pending_submissions())
    pending_messages = len(get_pending_messages())
    
    dashboard_text = f"""
🔧 *Admin Dashboard*

*Quick Overview:*
• Total Posts: {stats['total_posts']}
• Total Users: {stats['total_users']}
• Pending Posts: {pending_posts}
• Pending Messages: {pending_messages}

Choose a section to manage:
"""
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics"),
            InlineKeyboardButton("👥 User Management", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton("📝 Content Management", callback_data="admin_content"),
            InlineKeyboardButton("🚩 Reports & Moderation", callback_data="admin_moderation")
        ],
        [
            InlineKeyboardButton("💬 Messages", callback_data="admin_messages"),
            InlineKeyboardButton("⚙️ System Info", callback_data="admin_system")
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        dashboard_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed analytics and insights"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    # Get comprehensive analytics
    stats = get_channel_stats()
    
    # Get additional analytics
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get user activity trends (last 7 days)
        cursor.execute("""
            SELECT DATE(join_date) as day, COUNT(*) as new_users 
            FROM users 
            WHERE join_date >= DATE('now', '-7 days') 
            GROUP BY DATE(join_date) 
            ORDER BY day DESC
        """)
        user_trends = cursor.fetchall()
        
        # Get post activity trends (last 7 days)
        cursor.execute("""
            SELECT DATE(timestamp) as day, COUNT(*) as posts 
            FROM posts 
            WHERE timestamp >= DATE('now', '-7 days') AND approved = 1
            GROUP BY DATE(timestamp) 
            ORDER BY day DESC
        """)
        post_trends = cursor.fetchall()
        
        # Get most active users
        cursor.execute("""
            SELECT u.first_name, u.username, u.questions_asked, u.comments_posted,
                   (u.questions_asked + u.comments_posted) as total_activity
            FROM users u
            WHERE u.blocked = 0
            ORDER BY total_activity DESC
            LIMIT 5
        """)
        top_users = cursor.fetchall()
        
        # Get category breakdown
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM posts 
            WHERE approved = 1 
            GROUP BY category 
            ORDER BY count DESC
        """)
        category_stats = cursor.fetchall()
    
    analytics_text = f"""
📊 *Detailed Analytics*

*Overall Stats:*
• Total Posts: {stats['total_posts']}
• Total Comments: {stats['total_comments']}
• Total Users: {stats['total_users']}
• Total Reactions: {stats['total_reactions']}

*User Trends \\(7 days\\):*
"""
    
    if user_trends:
        for day, count in user_trends[:3]:
            analytics_text += f"• {escape_markdown_text(str(day))}: {count} new users\n"
    else:
        analytics_text += "• No new users in the last 7 days\n"
    
    analytics_text += "\n*Post Activity \\(7 days\\):*\n"
    if post_trends:
        for day, count in post_trends[:3]:
            analytics_text += f"• {escape_markdown_text(str(day))}: {count} posts\n"
    else:
        analytics_text += "• No posts approved in the last 7 days\n"
    
    analytics_text += "\n*Top Categories:*\n"
    if category_stats:
        for category, count in category_stats[:5]:
            analytics_text += f"• {escape_markdown_text(str(category))}: {count} posts\n"
    
    analytics_text += "\n*Most Active Users:*\n"
    if top_users:
        for i, (name, username, confessions, comments, total) in enumerate(top_users, 1):
            display_name = name or username or "Anonymous"
            analytics_text += f"{i}\\. {escape_markdown_text(display_name)}: {total} activities\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📈 Export Data", callback_data="admin_export"),
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_analytics")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        analytics_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def admin_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user management interface"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    # Get user statistics
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Active users (not blocked)
        cursor.execute("SELECT COUNT(*) FROM users WHERE blocked = 0")
        active_users = cursor.fetchone()[0]
        
        # Blocked users
        cursor.execute("SELECT COUNT(*) FROM users WHERE blocked = 1")
        blocked_users = cursor.fetchone()[0]
        
        # Recent users (last 24 hours)
        cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= datetime('now', '-1 day')")
        recent_users = cursor.fetchone()[0]
    
    user_mgmt_text = f"""
👥 *User Management*

*User Statistics:*
• Total Users: {total_users}
• Active Users: {active_users}
• Blocked Users: {blocked_users}
• New Users \\(24h\\): {recent_users}

Choose an action:
"""
    
    keyboard = [
        [
            InlineKeyboardButton(f"👥 Active Users ({active_users})", callback_data="admin_active_users"),
            InlineKeyboardButton(f"⛔ Blocked Users ({blocked_users})", callback_data="admin_blocked_users")
        ],
        [
            InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user"),
            InlineKeyboardButton("📊 User Analytics", callback_data="admin_user_analytics")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        user_mgmt_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def admin_blocked_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show blocked users with unblock buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, first_name, last_name, join_date, questions_asked, comments_posted
            FROM users WHERE blocked = 1 
            ORDER BY join_date DESC LIMIT 10
        """)
        blocked_users = cursor.fetchall()
    
    if not blocked_users:
        blocked_text = "✅ *No Blocked Users*\n\nAll users are currently active\\!"
        keyboard = [[InlineKeyboardButton("🔙 Back to User Management", callback_data="admin_users")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            blocked_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        return
    
    blocked_text = f"⛔ *Blocked Users \\({len(blocked_users)} shown\\)*\n\n"
    keyboard = []
    
    for user_data in blocked_users:
        uid, username, first_name, last_name, join_date, questions_asked, comments_posted = user_data
        name = f"{first_name or ''} {last_name or ''}".strip() or username or "Anonymous"
        
        blocked_text += f"*User:* {escape_markdown_text(name)}\n"
        blocked_text += f"*ID:* `{uid}`\n"
        blocked_text += f"*Activity:* {questions_asked} posts, {comments_posted} comments\n"
        if join_date:
            blocked_text += f"*Joined:* {escape_markdown_text(join_date[:10])}\n"
        blocked_text += "\n"
        
        # Add unblock button for each user
        keyboard.append([
            InlineKeyboardButton(f"✅ Unblock {name[:15]}...", callback_data=f"admin_unblock_{uid}"),
            InlineKeyboardButton(f"👤 Info", callback_data=f"admin_user_info_{uid}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to User Management", callback_data="admin_users")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        blocked_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def admin_active_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active users with management options"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, first_name, last_name, join_date, questions_asked, comments_posted
            FROM users WHERE blocked = 0 
            ORDER BY (questions_asked + comments_posted) DESC LIMIT 15
        """)
        active_users = cursor.fetchall()
    
    active_text = f"👥 *Most Active Users \\({len(active_users)} shown\\)*\n\n"
    keyboard = []
    
    for i, user_data in enumerate(active_users, 1):
        uid, username, first_name, last_name, join_date, questions_asked, comments_posted = user_data
        name = f"{first_name or ''} {last_name or ''}".strip() or username or "Anonymous"
        total_activity = questions_asked + comments_posted
        
        active_text += f"{i}\\. *{escape_markdown_text(name)}*\n"
        active_text += f"   ID: `{uid}` \\| Activity: {total_activity}\n"
        if join_date:
            active_text += f"   Joined: {escape_markdown_text(join_date[:10])}\n"
        active_text += "\n"
        
        # Add management buttons for top users only
        if i <= 5:
            keyboard.append([
                InlineKeyboardButton(f"👤 {name[:10]}... Info", callback_data=f"admin_user_info_{uid}"),
                InlineKeyboardButton(f"⛔ Block", callback_data=f"admin_block_{uid}")
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to User Management", callback_data="admin_users")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        active_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

# Additional Admin Dashboard Handlers
async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin dashboard callback"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    # Get quick stats
    stats = get_channel_stats()
    pending_posts = len(get_pending_submissions())
    pending_messages = len(get_pending_messages())
    
    dashboard_text = f"""
🔧 *Admin Dashboard*

*Quick Overview:*
• Total Posts: {stats['total_posts']}
• Total Users: {stats['total_users']}
• Pending Posts: {pending_posts}
• Pending Messages: {pending_messages}

Choose a section to manage:
"""
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics"),
            InlineKeyboardButton("👥 User Management", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton("📝 Content Management", callback_data="admin_content"),
            InlineKeyboardButton("🚩 Reports & Moderation", callback_data="admin_moderation")
        ],
        [
            InlineKeyboardButton("💬 Messages", callback_data="admin_messages"),
            InlineKeyboardButton("⚙️ System Info", callback_data="admin_system")
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        dashboard_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def admin_unblock_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin unblock user button"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    target_user_id = int(query.data.replace("admin_unblock_", ""))
    
    try:
        from approval import unblock_user, is_blocked_user
        
        if not is_blocked_user(target_user_id):
            await query.answer("❗ User is not blocked!")
            return
        
        unblock_user(target_user_id)
        await query.answer(f"✅ User {target_user_id} unblocked!")
        
        # Refresh the blocked users list
        await admin_blocked_users(update, context)
        
    except Exception as e:
        await query.answer(f"❗ Error: {str(e)}")

async def admin_block_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin block user button"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    target_user_id = int(query.data.replace("admin_block_", ""))
    
    try:
        from approval import block_user, is_blocked_user
        
        if is_blocked_user(target_user_id):
            await query.answer("❗ User is already blocked!")
            return
        
        block_user(target_user_id)
        await query.answer(f"⛔ User {target_user_id} blocked!")
        
        # Refresh the active users list
        await admin_active_users(update, context)
        
    except Exception as e:
        await query.answer(f"❗ Error: {str(e)}")

async def admin_user_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed user information"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    target_user_id = int(query.data.replace("admin_user_info_", ""))
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, first_name, last_name, join_date, questions_asked, comments_posted, blocked FROM users WHERE user_id = ?",
            (target_user_id,)
        )
        user_data = cursor.fetchone()
        
        if not user_data:
            await query.answer("❗ User not found!")
            return
        
        uid, username, first_name, last_name, join_date, questions_asked, comments_posted, blocked = user_data
        
        status = "🚫 Blocked" if blocked else "✅ Active"
        name = f"{first_name or ''} {last_name or ''}".strip() or username or "Anonymous"
        
        # Get additional stats
        cursor.execute(
            "SELECT COUNT(*) FROM comment_reactions WHERE comment_id IN (SELECT id FROM comments WHERE user_id = ?)",
            (target_user_id,)
        )
        likes_received = cursor.fetchone()[0]
        
        user_text = f"""
👤 *User Information*

*Details:*
• Name: {escape_markdown_text(name)}
• ID: `{uid}`
• Username: {f"@{escape_markdown_text(username)}" if username else "None"}
• Status: {status}
• Joined: {escape_markdown_text(join_date[:16]) if join_date else "Unknown"}

*Activity:*
• Confessions Posted: {questions_asked}
• Comments Posted: {comments_posted}
• Likes Received: {likes_received}
• Total Activity: {questions_asked + comments_posted}
"""
        
        keyboard = [
            [
                InlineKeyboardButton(f"{'✅ Unblock' if blocked else '⛔ Block'}", 
                                   callback_data=f"admin_{'unblock' if blocked else 'block'}_{uid}")
            ],
            [
                InlineKeyboardButton("🔙 Back to User Management", callback_data="admin_users")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            user_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )

async def admin_content_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show content management panel"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    # Get content stats
    pending_posts = len(get_pending_submissions())
    
    content_text = f"""
📝 *Content Management*

*Current Status:*
• Pending Posts: {pending_posts}
• Total Posts: Calculating...

Choose an action:
"""
    
    keyboard = [
        [
            InlineKeyboardButton(f"📋 Pending Posts ({pending_posts})", callback_data="admin_pending_posts"),
            InlineKeyboardButton("📰 Recent Posts", callback_data="admin_recent_posts")
        ],
        [
            InlineKeyboardButton("📊 Content Analytics", callback_data="admin_content_stats"),
            InlineKeyboardButton("🗑️ Content Cleanup", callback_data="admin_content_cleanup")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        content_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def admin_moderation_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show moderation panel"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    from moderation import get_reports
    reports = get_reports()
    report_count = len(reports)
    
    moderation_text = f"""
🚩 *Reports & Moderation*

*Current Status:*
• Active Reports: {report_count}
• Auto-moderation: Active

Choose an action:
"""
    
    keyboard = [
        [
            InlineKeyboardButton(f"🚩 View Reports ({report_count})", callback_data="admin_view_reports"),
            InlineKeyboardButton("📊 Moderation Stats", callback_data="admin_mod_stats")
        ],
        [
            InlineKeyboardButton("🔧 Moderation Settings", callback_data="admin_mod_settings"),
            InlineKeyboardButton("📜 Audit Log", callback_data="admin_audit_log")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        moderation_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def admin_messages_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show messages management panel"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    pending_messages = len(get_pending_messages())
    
    messages_text = f"""
💬 *Message Management*

*Current Status:*
• Pending Messages: {pending_messages}
• Auto-replies: Disabled

Choose an action:
"""
    
    keyboard = [
        [
            InlineKeyboardButton(f"📨 Pending Messages ({pending_messages})", callback_data="admin_pending_messages"),
            InlineKeyboardButton("📜 Message History", callback_data="admin_message_history")
        ],
        [
            InlineKeyboardButton("🤖 Auto-Reply Settings", callback_data="admin_auto_reply"),
            InlineKeyboardButton("📊 Message Stats", callback_data="admin_message_stats")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        messages_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def admin_system_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system information panel"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❗ Not authorized")
        return
    
    import os
    import psutil
    from datetime import datetime
    
    try:
        # Get system stats
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get database size
        db_size = os.path.getsize(DB_PATH) / (1024 * 1024)  # MB
        
        system_text = f"""
⚙️ *System Information*

*Bot Status:*
• Status: ✅ Running
• Uptime: Active
• Database Size: {db_size:.1f} MB

*System Resources:*
• CPU Usage: {cpu_percent}%
• Memory: {memory.percent}% used
• Disk: {(disk.used / disk.total * 100):.1f}% used

*Last Updated:* {escape_markdown_text(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}
"""
    except Exception as e:
        system_text = f"""
⚙️ *System Information*

*Bot Status:*
• Status: ✅ Running
• Database: Connected
• Error getting system stats: {escape_markdown_text(str(e))}

*Last Updated:* {escape_markdown_text(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_system"),
            InlineKeyboardButton("🗄️ Database Stats", callback_data="admin_db_stats")
        ],
        [
            InlineKeyboardButton("📊 Performance", callback_data="admin_performance"),
            InlineKeyboardButton("💾 Backup Status", callback_data="admin_backup_status")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        system_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

def main():
    """Main function to run the bot"""
    # Initialize database
    init_db()
    
    # Run database migrations
    logger.info("Running database migrations...")
    if not run_migrations():
        logger.error("Failed to run migrations, exiting")
        return
    
    # Initialize backup system
    logger.info("Starting backup system...")
    start_backup_system()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add error handler
    application.add_error_handler(global_error_handler)
    
    # Add handlers with decorators
    application.add_handler(CommandHandler("start", handle_telegram_errors(start_handler)))
    application.add_handler(CommandHandler("menu", handle_telegram_errors(menu_command)))
    application.add_handler(CommandHandler("admin", handle_telegram_errors(admin_command)))
    application.add_handler(CommandHandler("stats", handle_telegram_errors(stats_command)))
    application.add_handler(CommandHandler("pending", handle_telegram_errors(pending_command)))
    application.add_handler(CommandHandler("messages", handle_telegram_errors(messages_command)))
    application.add_handler(CommandHandler("reply", handle_telegram_errors(reply_command)))
    application.add_handler(CommandHandler("reports", handle_telegram_errors(reports_command)))
    application.add_handler(CommandHandler("users", handle_telegram_errors(users_command)))
    application.add_handler(CommandHandler("block", handle_telegram_errors(block_command)))
    application.add_handler(CommandHandler("unblock", handle_telegram_errors(unblock_command)))
    application.add_handler(CommandHandler("blocked", handle_telegram_errors(blocked_command)))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_errors(handle_menu_choice)))
    
    # Add ranking callback handler BEFORE the general callback handler
    application.add_handler(CallbackQueryHandler(ranking_callback_handler, pattern=r"^(rank_|leaderboard_)"))
    application.add_handler(CallbackQueryHandler(handle_telegram_errors(callback_handler)))
    
    # Log bot startup
    bot_logger.log_user_action(0, "bot_started", "University Confession Bot initialized")
    
    # Run the bot
    logger.info("Starting University Confession Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

