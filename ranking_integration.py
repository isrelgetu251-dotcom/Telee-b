"""
Integration layer for ranking system with existing bot functionality
Connects point awards to user actions throughout the bot
"""

from telegram import Update
from telegram.ext import ContextTypes
from typing import Optional

from ranking_system import ranking_manager
from ranking_ui import notify_rank_up, notify_achievement_earned, show_ranking_menu
from logger import get_logger
from config import ADMIN_IDS

logger = get_logger('ranking_integration')

class RankingIntegration:
    """Integrates ranking system with existing bot features"""
    
    @staticmethod
    async def handle_confession_submitted(user_id: int, post_id: int, category: str, context: ContextTypes.DEFAULT_TYPE):
        """Handle points when confession is submitted"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='confession_submitted',
                reference_id=post_id,
                reference_type='confession',
                description=f"Submitted confession in {category}"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for confession submission")
                
                # Check if this is their first confession
                await RankingIntegration.check_first_time_achievements(user_id, 'confession', context)
                
        except Exception as e:
            logger.error(f"Error awarding points for confession submission: {e}")
    
    @staticmethod
    async def handle_confession_approved(user_id: int, post_id: int, admin_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Handle points when confession is approved"""
        try:
            # Award points to user
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='confession_approved',
                reference_id=post_id,
                reference_type='confession',
                description="Confession approved by admin"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for approved confession")
                
                # Check for rank up and notify user
                await RankingIntegration.check_and_notify_rank_up(user_id, context)
                
                # Daily login bonus (if they haven't been active today)
                await RankingIntegration.award_daily_login_bonus(user_id)
                
        except Exception as e:
            logger.error(f"Error awarding points for confession approval: {e}")
    
    @staticmethod
    async def handle_confession_rejected(user_id: int, post_id: int, admin_id: int):
        """Handle points when confession is rejected"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='content_rejected',
                reference_id=post_id,
                reference_type='confession',
                description="Confession rejected by admin"
            )
            
            if success:
                logger.info(f"Deducted {abs(points)} points from user {user_id} for rejected confession")
                
        except Exception as e:
            logger.error(f"Error deducting points for confession rejection: {e}")
    
    @staticmethod
    async def handle_comment_posted(user_id: int, post_id: int, comment_id: int, content: str, context: ContextTypes.DEFAULT_TYPE):
        """Handle points when comment is posted"""
        try:
            # Base comment points
            activity_type = 'comment_posted'
            
            # Check if it's a quality comment (longer, thoughtful)
            if len(content) > 100:
                activity_type = 'quality_comment'
            
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type=activity_type,
                reference_id=comment_id,
                reference_type='comment',
                comment_length=len(content),
                description=f"Posted comment on confession {post_id}"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for comment")
                
                # Check if this is their first comment
                await RankingIntegration.check_first_time_achievements(user_id, 'comment', context)
                
                # Check for rank up
                await RankingIntegration.check_and_notify_rank_up(user_id, context)
                
        except Exception as e:
            logger.error(f"Error awarding points for comment: {e}")
    
    @staticmethod
    async def handle_reaction_given(user_id: int, target_id: int, target_type: str, reaction_type: str):
        """Handle points when user gives a reaction"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='reaction_given',
                reference_id=target_id,
                reference_type=target_type,
                description=f"Gave {reaction_type} reaction to {target_type}"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for reaction")
                
        except Exception as e:
            logger.error(f"Error awarding points for reaction: {e}")
    
    @staticmethod
    async def handle_reaction_received(user_id: int, target_id: int, target_type: str, reaction_type: str, context: ContextTypes.DEFAULT_TYPE):
        """Handle points when user receives a reaction on their content"""
        try:
            activity_type = 'confession_liked' if target_type == 'confession' else 'comment_liked'
            
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type=activity_type,
                reference_id=target_id,
                reference_type=target_type,
                description=f"Received {reaction_type} on {target_type}"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for receiving reaction")
                
                # Check for viral post achievements
                if target_type == 'confession':
                    await RankingIntegration.check_viral_achievements(user_id, target_id, context)
                
        except Exception as e:
            logger.error(f"Error awarding points for received reaction: {e}")
    
    @staticmethod
    async def handle_spam_detected(user_id: int, content_id: int, content_type: str):
        """Handle point deduction for spam"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='spam_detected',
                reference_id=content_id,
                reference_type=content_type,
                description=f"Spam detected in {content_type}"
            )
            
            if success:
                logger.info(f"Deducted {abs(points)} points from user {user_id} for spam")
                
        except Exception as e:
            logger.error(f"Error deducting points for spam: {e}")
    
    @staticmethod
    async def handle_inappropriate_content(user_id: int, content_id: int, content_type: str):
        """Handle point deduction for inappropriate content"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='inappropriate_content',
                reference_id=content_id,
                reference_type=content_type,
                description=f"Inappropriate content in {content_type}"
            )
            
            if success:
                logger.info(f"Deducted {abs(points)} points from user {user_id} for inappropriate content")
                
        except Exception as e:
            logger.error(f"Error deducting points for inappropriate content: {e}")
    
    @staticmethod
    async def check_first_time_achievements(user_id: int, activity_type: str, context: ContextTypes.DEFAULT_TYPE):
        """Check and award first-time achievements"""
        try:
            # This will be handled automatically by the achievement system
            # but we can add special notifications here
            pass
            
        except Exception as e:
            logger.error(f"Error checking first-time achievements: {e}")
    
    @staticmethod
    async def check_viral_achievements(user_id: int, post_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Check for viral post achievements based on likes"""
        try:
            import sqlite3
            from config import DB_PATH
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                # Get total likes for this post (assuming you have a likes system)
                cursor.execute("""
                    SELECT COUNT(*) FROM reactions 
                    WHERE target_id = ? AND target_type = 'post' AND reaction_type = 'like'
                """, (post_id,))
                
                like_count = cursor.fetchone()[0]
                
                # Check for viral achievements
                if like_count >= 100:
                    success, points = ranking_manager.award_points(
                        user_id=user_id,
                        activity_type='confession_100_likes',
                        reference_id=post_id,
                        reference_type='confession',
                        like_count=like_count,
                        description=f"Confession reached {like_count} likes"
                    )
                    
                    if success:
                        # Notify about viral achievement
                        await notify_achievement_earned(
                            context,
                            user_id,
                            "🔥 Viral Post",
                            f"Your confession got {like_count}+ likes!",
                            points
                        )
                
        except Exception as e:
            logger.error(f"Error checking viral achievements: {e}")
    
    @staticmethod
    async def check_and_notify_rank_up(user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Check if user ranked up and notify them"""
        try:
            user_rank = ranking_manager.get_user_rank(user_id)
            if not user_rank:
                return
                
            # Check rank history to see if they just ranked up
            import sqlite3
            from config import DB_PATH
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT new_rank_id, rd.rank_name, rd.rank_emoji
                    FROM rank_history rh
                    JOIN rank_definitions rd ON rh.new_rank_id = rd.rank_id
                    WHERE rh.user_id = ?
                    ORDER BY rh.created_at DESC
                    LIMIT 1
                """, (user_id,))
                
                result = cursor.fetchone()
                if result:
                    new_rank_id, rank_name, rank_emoji = result
                    if new_rank_id == user_rank.current_rank_id:
                        # They just ranked up, notify them
                        await notify_rank_up(context, user_id, rank_name, rank_emoji)
                
        except Exception as e:
            logger.error(f"Error checking rank up: {e}")
    
    @staticmethod
    async def award_daily_login_bonus(user_id: int):
        """Award daily login bonus if user hasn't been active today"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='daily_login',
                description="Daily login bonus"
            )
            
            if success and points > 0:
                logger.info(f"Awarded daily login bonus to user {user_id}")
                
        except Exception as e:
            logger.error(f"Error awarding daily login bonus: {e}")
    
    @staticmethod
    async def handle_admin_action(admin_id: int, action_type: str, target_user_id: Optional[int] = None):
        """Handle admin actions (optional - admins could also earn points)"""
        try:
            if admin_id in ADMIN_IDS and action_type in ['approve_post', 'moderate_content']:
                success, points = ranking_manager.award_points(
                    user_id=admin_id,
                    activity_type='community_contribution',
                    description=f"Admin action: {action_type}"
                )
                
                if success:
                    logger.info(f"Awarded {points} points to admin {admin_id} for {action_type}")
                    
        except Exception as e:
            logger.error(f"Error awarding admin points: {e}")

# Convenience functions for easy integration
async def award_points_for_confession_submission(user_id: int, post_id: int, category: str, context: ContextTypes.DEFAULT_TYPE):
    """Convenience function for confession submission"""
    await RankingIntegration.handle_confession_submitted(user_id, post_id, category, context)

async def award_points_for_confession_approval(user_id: int, post_id: int, admin_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Convenience function for confession approval"""
    await RankingIntegration.handle_confession_approved(user_id, post_id, admin_id, context)

async def award_points_for_comment(user_id: int, post_id: int, comment_id: int, content: str, context: ContextTypes.DEFAULT_TYPE):
    """Convenience function for comment posting"""
    await RankingIntegration.handle_comment_posted(user_id, post_id, comment_id, content, context)

async def award_points_for_reaction_given(user_id: int, target_id: int, target_type: str, reaction_type: str):
    """Convenience function for giving reactions"""
    await RankingIntegration.handle_reaction_given(user_id, target_id, target_type, reaction_type)

async def award_points_for_reaction_received(user_id: int, target_id: int, target_type: str, reaction_type: str, context: ContextTypes.DEFAULT_TYPE):
    """Convenience function for receiving reactions"""
    await RankingIntegration.handle_reaction_received(user_id, target_id, target_type, reaction_type, context)

# Function to add to main menu
async def show_my_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's rank - to be added to main menu"""
    await show_ranking_menu(update, context)
