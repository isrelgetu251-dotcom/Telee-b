"""
UI Components for Ranking System
Handles display of ranks, leaderboards, achievements, and progress
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from typing import List, Dict, Optional
import math

from ranking_system import ranking_manager, UserRank
from utils import escape_markdown_text
from logger import get_logger

logger = get_logger('ranking_ui')

class RankingUI:
    """UI components for the ranking system"""
    
    @staticmethod
    def create_progress_bar(current: int, maximum: int, length: int = 10) -> str:
        """Create a text progress bar"""
        if maximum == 0:
            return "█" * length
        
        filled = int((current / maximum) * length)
        empty = length - filled
        return "█" * filled + "░" * empty
    
    @staticmethod
    def format_rank_display(user_rank: UserRank) -> str:
        """Format user rank information for display"""
        progress_bar = RankingUI.create_progress_bar(
            user_rank.total_points - (user_rank.next_rank_points - user_rank.points_to_next),
            user_rank.points_to_next if user_rank.points_to_next > 0 else 100,
            12
        )
        
        rank_text = f"""
🏆 *Your Current Rank*

{escape_markdown_text(user_rank.rank_emoji)} **{escape_markdown_text(user_rank.rank_name)}**
{escape_markdown_text('⭐' if user_rank.is_special_rank else '📊')} {user_rank.total_points:,} points

📈 *Progress to Next Rank*
{progress_bar}
"""
        
        if user_rank.points_to_next > 0:
            rank_text += f"{user_rank.points_to_next:,} points to go\\!\n"
        else:
            rank_text += "Maximum rank achieved\\! 🎉\n"
        
        # Show special perks if any
        if user_rank.special_perks:
            perks_text = "🎁 *Special Perks*\n"
            for perk, value in user_rank.special_perks.items():
                if perk == "daily_confessions":
                    perks_text += f"• Daily confessions: {value}\n"
                elif perk == "priority_review":
                    perks_text += "• Priority review ⚡\n"
                elif perk == "comment_highlight":
                    perks_text += "• Comment highlighting ✨\n"
                elif perk == "featured_chance":
                    perks_text += f"• Featured post chance: {int(value*100)}%\n"
                elif perk == "exclusive_categories":
                    perks_text += "• Exclusive categories access 🔓\n"
                elif perk == "custom_emoji":
                    perks_text += "• Custom emoji reactions 😎\n"
                elif perk == "legend_badge":
                    perks_text += "• Legend badge 👑\n"
                elif perk == "unlimited_daily":
                    perks_text += "• Unlimited daily confessions ♾️\n"
                elif perk == "all_perks":
                    perks_text += "• All available perks unlocked 🌟\n"
            
            rank_text += f"\n{perks_text}"
        
        return rank_text
    
    @staticmethod
    def create_ranking_keyboard() -> InlineKeyboardMarkup:
        """Create inline keyboard for ranking navigation"""
        keyboard = [
            [
                InlineKeyboardButton("📊 My Rank", callback_data="rank_my_rank"),
                InlineKeyboardButton("🏆 Leaderboard", callback_data="rank_leaderboard")
            ],
            [
                InlineKeyboardButton("🎯 Achievements", callback_data="rank_achievements"),
                InlineKeyboardButton("📈 Progress", callback_data="rank_progress")
            ],
            [
                InlineKeyboardButton("🔍 How to Earn Points", callback_data="rank_help"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_leaderboard_keyboard() -> InlineKeyboardMarkup:
        """Create keyboard for leaderboard timeframes"""
        keyboard = [
            [
                InlineKeyboardButton("📅 Weekly", callback_data="leaderboard_weekly"),
                InlineKeyboardButton("📆 Monthly", callback_data="leaderboard_monthly")
            ],
            [
                InlineKeyboardButton("⭐ All Time", callback_data="leaderboard_alltime"),
                InlineKeyboardButton("🔙 Back", callback_data="rank_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def format_leaderboard(leaderboard: List[Dict], timeframe: str) -> str:
        """Format leaderboard for display"""
        if not leaderboard:
            return f"📊 *{timeframe.title()} Leaderboard*\n\nNo data available yet\\. Be the first to earn points\\!"
        
        # Rank position emojis
        position_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
        
        leaderboard_text = f"📊 *{timeframe.title()} Leaderboard*\n\n"
        
        for entry in leaderboard:
            position = entry['position']
            emoji = position_emojis.get(position, f"{position}\\.")
            
            leaderboard_text += (
                f"{emoji} {escape_markdown_text(entry['rank_emoji'])} "
                f"*{escape_markdown_text(entry['anonymous_name'])}*\n"
                f"   {escape_markdown_text(entry['rank_name'])} • "
                f"{entry['points']:,} points\n\n"
            )
        
        leaderboard_text += "🎯 Keep earning points to climb the ranks\\!"
        return leaderboard_text
    
    @staticmethod
    def format_achievements(achievements: List[Dict]) -> str:
        """Format achievements list for display"""
        if not achievements:
            return "🎯 *Your Achievements*\n\nNo achievements yet\\. Start earning points to unlock your first achievement\\!"
        
        achievements_text = f"🎯 *Your Achievements* \\({len(achievements)} earned\\)\n\n"
        
        for achievement in achievements[:10]:  # Show top 10
            special_mark = "⭐" if achievement['is_special'] else "🏆"
            date_str = achievement['date'][:10] if achievement['date'] else "Unknown"
            
            achievements_text += (
                f"{special_mark} *{escape_markdown_text(achievement['name'])}*\n"
                f"   {escape_markdown_text(achievement['description'])}\n"
                f"   \\+{achievement['points']} points • {escape_markdown_text(date_str)}\n\n"
            )
        
        if len(achievements) > 10:
            achievements_text += f"\\.\\.\\. and {len(achievements) - 10} more\\!\n"
        
        return achievements_text
    
    @staticmethod
    def format_points_help() -> str:
        """Format help text for earning points"""
        return """
🎯 *How to Earn Points*

*Confession Activities:*
• Submit confession: \\+10 points
• Approved confession: \\+25 points
• Each like received: \\+2 points
• Featured confession: \\+50 points
• 100\\+ likes bonus: \\+100 points

*Comment Activities:*
• Post comment: \\+5 points
• Comment gets liked: \\+1 point
• Quality comment: \\+20 points
• Start discussion: \\+10 points

*Daily Activities:*
• Daily login: \\+2 points
• Consecutive days \\(3\\+\\): \\+5 points/day
• Weekly streak: \\+25 points
• Monthly streak: \\+100 points

*Social Activities:*
• Give reactions: \\+1 point
• Help others: \\+10 points
• Positive interaction: \\+5 points

*Special Bonuses:*
• First confession: \\+50 points
• Milestones: \\+100 points
• Achievements: Varies

*Rank Up Rewards:*
• Each rank up: \\+50 points
• Special ranks: Extra bonuses

🚫 *Point Penalties:*
• Content rejected: \\-5 points
• Spam detected: \\-15 points
• Inappropriate content: \\-25 points

💡 *Tips:*
• Be active daily for streak bonuses
• Write quality, thoughtful content
• Engage positively with others
• Help build the community

The more you contribute, the faster you'll climb the ranks\\!
"""

async def show_ranking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main ranking menu"""
    user_id = update.effective_user.id
    user_rank = ranking_manager.get_user_rank(user_id)
    
    if not user_rank:
        # Initialize user ranking
        ranking_manager.initialize_user_ranking(user_id)
        user_rank = ranking_manager.get_user_rank(user_id)
    
    if not user_rank:
        await update.message.reply_text("❗ Error loading ranking information. Please try again.")
        return
    
    rank_display = RankingUI.format_rank_display(user_rank)
    keyboard = RankingUI.create_ranking_keyboard()
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                rank_display,
                parse_mode="MarkdownV2",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await update.callback_query.answer("Error updating display. Please try again.")
    else:
        await update.message.reply_text(
            rank_display,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )

async def show_leaderboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show leaderboard selection menu"""
    keyboard = RankingUI.create_leaderboard_keyboard()
    
    text = """
🏆 *Community Leaderboard*

Choose a timeframe to view the top contributors:

📅 *Weekly:* Top performers this week
📆 *Monthly:* Top performers this month  
⭐ *All Time:* Highest ranking members ever

All rankings are completely anonymous to protect your privacy\\!
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, timeframe: str):
    """Show leaderboard for specific timeframe"""
    leaderboard = ranking_manager.get_leaderboard(timeframe, limit=10)
    leaderboard_text = RankingUI.format_leaderboard(leaderboard, timeframe)
    
    keyboard = [
        [
            InlineKeyboardButton("📅 Weekly", callback_data="leaderboard_weekly"),
            InlineKeyboardButton("📆 Monthly", callback_data="leaderboard_monthly"),
            InlineKeyboardButton("⭐ All Time", callback_data="leaderboard_alltime")
        ],
        [
            InlineKeyboardButton("🔙 Back to Rankings", callback_data="rank_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            leaderboard_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

async def show_user_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's achievements"""
    user_id = update.effective_user.id
    achievements = ranking_manager.get_user_achievements(user_id)
    achievements_text = RankingUI.format_achievements(achievements)
    
    keyboard = [
        [
            InlineKeyboardButton("🎯 More Achievements", callback_data="achievements_all"),
            InlineKeyboardButton("📊 My Rank", callback_data="rank_my_rank")
        ],
        [
            InlineKeyboardButton("🔙 Back to Rankings", callback_data="rank_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            achievements_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

async def show_points_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help for earning points"""
    help_text = RankingUI.format_points_help()
    
    keyboard = [
        [
            InlineKeyboardButton("📊 My Rank", callback_data="rank_my_rank"),
            InlineKeyboardButton("🏆 Leaderboard", callback_data="rank_leaderboard")
        ],
        [
            InlineKeyboardButton("🔙 Back to Rankings", callback_data="rank_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            help_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

async def show_user_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed user progress"""
    user_id = update.effective_user.id
    user_rank = ranking_manager.get_user_rank(user_id)
    
    if not user_rank:
        await update.callback_query.answer("Error loading progress information.")
        return
    
    # Get recent achievements
    recent_achievements = ranking_manager.get_user_achievements(user_id, limit=5)
    
    progress_text = f"""
📈 *Your Progress Report*

🏆 *Current Status:*
{escape_markdown_text(user_rank.rank_emoji)} {escape_markdown_text(user_rank.rank_name)}
{user_rank.total_points:,} total points earned

📊 *Recent Activity:*
"""
    
    if recent_achievements:
        progress_text += "\n🎯 *Recent Achievements:*\n"
        for achievement in recent_achievements[:3]:
            progress_text += f"• {escape_markdown_text(achievement['name'])} \\(\\+{achievement['points']} pts\\)\n"
    else:
        progress_text += "\n🎯 No recent achievements\\. Keep engaging to earn more\\!\n"
    
    # Show next milestone
    if user_rank.points_to_next > 0:
        progress_text += f"\n🎯 *Next Goal:*\n{user_rank.points_to_next:,} points to {escape_markdown_text(user_rank.rank_name)} rank\\!\n"
    
    # Add progress bar
    progress_bar = RankingUI.create_progress_bar(
        user_rank.total_points,
        user_rank.next_rank_points if user_rank.next_rank_points > 0 else user_rank.total_points,
        15
    )
    progress_text += f"\n📈 *Progress:*\n{progress_bar}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("🎯 All Achievements", callback_data="rank_achievements"),
            InlineKeyboardButton("🏆 Leaderboard", callback_data="rank_leaderboard")
        ],
        [
            InlineKeyboardButton("🔙 Back to Rankings", callback_data="rank_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            progress_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

async def notify_rank_up(context: ContextTypes.DEFAULT_TYPE, user_id: int, new_rank_name: str, new_rank_emoji: str):
    """Notify user about rank up"""
    try:
        notification_text = f"""
🎉 *RANK UP ACHIEVED\\!*

Congratulations\\! You've been promoted to:

{escape_markdown_text(new_rank_emoji)} **{escape_markdown_text(new_rank_name)}**

Keep up the great work in our community\\!

🎁 *\\+50 bonus points awarded*
"""
        
        keyboard = [
            [InlineKeyboardButton("🏆 View My Rank", callback_data="rank_my_rank")],
            [InlineKeyboardButton("🎯 See Achievements", callback_data="rank_achievements")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=notification_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Failed to send rank up notification to {user_id}: {e}")

async def notify_achievement_earned(context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                                  achievement_name: str, achievement_description: str, points: int):
    """Notify user about new achievement"""
    try:
        notification_text = f"""
🎯 *ACHIEVEMENT UNLOCKED\\!*

{escape_markdown_text(achievement_name)}

{escape_markdown_text(achievement_description)}

🎁 *\\+{points} points earned*
"""
        
        keyboard = [
            [InlineKeyboardButton("🎯 View All Achievements", callback_data="rank_achievements")],
            [InlineKeyboardButton("📊 Check My Rank", callback_data="rank_my_rank")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=notification_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Failed to send achievement notification to {user_id}: {e}")

# Callback handlers for ranking system
async def ranking_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ranking system callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "rank_menu" or data == "rank_my_rank":
        await show_ranking_menu(update, context)
    elif data == "rank_leaderboard":
        await show_leaderboard_menu(update, context)
    elif data.startswith("leaderboard_"):
        timeframe = data.replace("leaderboard_", "")
        await show_leaderboard(update, context, timeframe)
    elif data == "rank_achievements":
        await show_user_achievements(update, context)
    elif data == "rank_help":
        await show_points_help(update, context)
    elif data == "rank_progress":
        await show_user_progress(update, context)
    elif data == "main_menu":
        # Return to main menu - import needed functions
        from telegram import ReplyKeyboardMarkup
        
        # Clear user context and show main menu
        keys_to_clear = [
            'state', 'confession_content', 'selected_category', 
            'comment_post_id', 'comment_content', 'admin_action',
            'viewing_post_id', 'reply_to_comment_id', 'current_page',
            'contact_admin_message'
        ]
        for key in keys_to_clear:
            context.user_data.pop(key, None)
        
        # Main menu options
        MAIN_MENU = [
            ["🙊 Confess/Ask Question", "📰 View Recent Confessions"],
            ["🏆 My Rank", "📊 My Stats"],
            ["📅 Daily Digest", "📞 Contact Admin"],
            ["❓ Help/About"]
        ]
        
        await query.edit_message_text("🏠 Returned to main menu\\. Please use the menu below\\.", parse_mode="MarkdownV2")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="What would you like to do next?",
            reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        )
    else:
        await query.answer("Unknown ranking option.")
