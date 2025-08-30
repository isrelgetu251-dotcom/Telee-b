import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS, CHANNEL_ID, BOT_USERNAME, DB_PATH
from utils import escape_markdown_text
from db import get_comment_count

# Import ranking system integration
from ranking_integration import award_points_for_confession_approval, RankingIntegration

def approve_post(post_id, message_id):
    """Approve a post and save channel message ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE posts SET approved=1, channel_message_id=? WHERE post_id=?",
            (message_id, post_id)
        )
        conn.commit()

def reject_post(post_id):
    """Reject a post"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET approved=0 WHERE post_id=?", (post_id,))
        conn.commit()

def flag_post(post_id):
    """Flag a post for review"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET flagged=1 WHERE post_id=?", (post_id,))
        conn.commit()

def block_user(user_id):
    """Block a user"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET blocked=1 WHERE user_id=?", (user_id,))
        conn.commit()

def unblock_user(user_id):
    """Unblock a user"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET blocked=0 WHERE user_id=?", (user_id,))
        conn.commit()

def get_post_by_id(post_id):
    """Get a specific post by ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE post_id=?", (post_id,))
        return cursor.fetchone()

def is_blocked_user(user_id):
    """Check if user is blocked"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin approval/rejection callbacks"""
    query = update.callback_query
    await query.answer()
    data = query.data
    admin_id = update.effective_user.id
    admin_user = update.effective_user
    admin_name = admin_user.first_name or admin_user.username or f"Admin {admin_id}"

    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❗ You are not authorized to moderate.")
        return

    if data.startswith("approve_"):
        post_id = int(data.split("_")[1])
        post = get_post_by_id(post_id)
        if not post:
            await query.edit_message_text("❗ Post not found.")
            return
        
        # Check if already approved
        if post[13] == 1:  # approved field is at index 13
            await query.edit_message_text(
                f"✅ *Already Approved*\n\n"
                f"This confession was already approved and posted to the channel\\.",
                parse_mode="MarkdownV2"
            )
            return
        
        # Check if already rejected
        if post[13] == 0:
            await query.edit_message_text(
                f"❌ *Already Rejected*\n\n"
                f"This confession was already rejected by an admin\\.",
                parse_mode="MarkdownV2"
            )
            return
        
        # Extract data from post tuple (correct indices based on DB structure)
        # post structure: (post_id, user_id, content, status, category, ...)
        content = post[2]  # content is at index 2
        category = post[4]  # category is at index 4
        submitter_id = post[1]  # user_id is at index 1
        
        comment_link = f"https://t.me/{BOT_USERNAME}?start=comment_{post_id}"
        
        try:
            # Get current comment count
            comment_count = get_comment_count(post_id)
            
            # Create inline buttons for the channel post
            # Strip @ symbol from BOT_USERNAME for URL
            bot_username_clean = BOT_USERNAME.lstrip('@')
            keyboard = [
                [
                    InlineKeyboardButton(
                        "💬 Add Comment", 
                        url=f"https://t.me/{bot_username_clean}?start=comment_{post_id}"
                    ),
                    InlineKeyboardButton(
                        f"👀 See Comments ({comment_count})", 
                        url=f"https://t.me/{bot_username_clean}?start=view_{post_id}"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Format channel message with category as heading
            msg = await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=(
                    f"*{escape_markdown_text(category)}*\n\n"
                    f"{escape_markdown_text(content)}"
                ),
                parse_mode="MarkdownV2",
                reply_markup=reply_markup
            )
            approve_post(post_id, msg.message_id)
            
            # Update the admin message to show approval and remove buttons
            admin_message = f"✅ *APPROVED by {escape_markdown_text(admin_name)} \\({admin_id}\\)*\n\n"
            admin_message += f"*Category:* {escape_markdown_text(category)}\n\n"
            admin_message += f"*Content:*\n{escape_markdown_text(content)}\n\n"
            admin_message += f"*Posted to channel and submitter notified\\.*"
            
            await query.edit_message_text(
                admin_message,
                parse_mode="MarkdownV2"
            )
            
            # Award points for approved confession
            await award_points_for_confession_approval(submitter_id, post_id, admin_id, context)
            
            # Notify the submitter
            if submitter_id:
                try:
                    await context.bot.send_message(
                        chat_id=submitter_id,
                        text=f"🎉 Your confession in category *{escape_markdown_text(category)}* was approved and posted to the channel\\!",
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logging.warning(f"Could not notify user {submitter_id}: {e}")
                    
        except Exception as e:
            logging.error(f"Failed to post to channel: {e}")
            await query.edit_message_text(f"❗ Failed to post to channel: {e}")

    elif data.startswith("reject_"):
        post_id = int(data.split("_")[1])
        post = get_post_by_id(post_id)
        if not post:
            await query.edit_message_text("❗ Post not found.")
            return
        
        # Check if already approved
        if post[13] == 1:  # approved field is at index 13
            await query.edit_message_text(
                f"✅ *Already Approved*\n\n"
                f"This confession was already approved and posted to the channel\\.",
                parse_mode="MarkdownV2"
            )
            return
        
        # Check if already rejected
        if post[13] == 0:
            await query.edit_message_text(
                f"❌ *Already Rejected*\n\n"
                f"This confession was already rejected by an admin\\.",
                parse_mode="MarkdownV2"
            )
            return
            
        # Extract data from post tuple (correct indices based on DB structure)
        content = post[2]  # content is at index 2
        category = post[4]  # category is at index 4
        submitter_id = post[1]  # user_id is at index 1
        
        reject_post(post_id)
        
        # Update the admin message to show rejection and remove buttons
        admin_message = f"❌ *REJECTED by {escape_markdown_text(admin_name)} \\({admin_id}\\)*\n\n"
        admin_message += f"*Category:* {escape_markdown_text(category)}\n\n"
        admin_message += f"*Content:*\n{escape_markdown_text(content)}\n\n"
        admin_message += f"*Submitter has been notified of rejection\\.*"
        
        await query.edit_message_text(
            admin_message,
            parse_mode="MarkdownV2"
        )
        
        # Deduct points for rejected confession
        await RankingIntegration.handle_confession_rejected(submitter_id, post_id, admin_id)
        
        if submitter_id:
            try:
                await context.bot.send_message(
                    chat_id=submitter_id,
                    text=f"❌ Your confession in category *{escape_markdown_text(category)}* was rejected by the admins\\.",
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                logging.warning(f"Could not notify user {submitter_id}: {e}")

    elif data.startswith("flag_"):
        post_id = int(data.split("_")[1])
        flag_post(post_id)
        await query.edit_message_text("🚩 Submission flagged for review.")

    elif data.startswith("block_"):
        block_uid = int(data.split("_")[1])
        block_user(block_uid)
        await query.edit_message_text(f"⛔ User {block_uid} blocked.")

    elif data.startswith("unblock_"):
        block_uid = int(data.split("_")[1])
        unblock_user(block_uid)
        await query.edit_message_text(f"✅ User {block_uid} unblocked.")