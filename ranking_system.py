"""
User Ranking System for Confession Bot
Handles points, ranks, achievements, and leaderboards
"""

import sqlite3
import json
import random
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict

from config import DB_PATH
from logger import get_logger
from utils import escape_markdown_text

logger = get_logger('ranking_system')

@dataclass
class UserRank:
    """User ranking information"""
    user_id: int
    total_points: int
    current_rank_id: int
    rank_name: str
    rank_emoji: str
    rank_progress: float
    next_rank_points: int
    points_to_next: int
    special_perks: Dict[str, Any]
    is_special_rank: bool

@dataclass
class Achievement:
    """Achievement information"""
    achievement_type: str
    achievement_name: str
    achievement_description: str
    points_awarded: int
    is_special: bool = False
    metadata: Dict[str, Any] = None

class PointSystem:
    """Manages point calculations and awards"""
    
    # Point values for different activities
    POINT_VALUES = {
        # Confession activities
        'confession_submitted': 10,
        'confession_approved': 25,
        'confession_featured': 50,
        'confession_liked': 2,
        'confession_100_likes': 100,
        'confession_popular': 75,  # Top confession of the day
        
        # Comment activities
        'comment_posted': 5,
        'comment_liked': 1,
        'comment_helpful': 15,  # Admin marks as helpful
        'comment_thread_starter': 10,
        'quality_comment': 20,  # Long, thoughtful comments
        
        # Engagement activities
        'daily_login': 2,
        'consecutive_days_bonus': 5,  # Per consecutive day after 3
        'week_streak': 25,
        'month_streak': 100,
        
        # Social activities
        'reaction_given': 1,
        'helping_others': 10,
        'positive_interaction': 5,
        
        # Special activities
        'first_confession': 50,
        'first_comment': 20,
        'milestone_reached': 100,
        'community_contribution': 30,
        
        # Penalty points (negative)
        'content_rejected': -5,
        'spam_detected': -15,
        'inappropriate_content': -25,
    }
    
    @staticmethod
    def calculate_points(activity_type: str, **kwargs) -> int:
        """Calculate points for an activity"""
        base_points = PointSystem.POINT_VALUES.get(activity_type, 0)
        
        # Apply multipliers based on context
        if activity_type == 'consecutive_days_bonus':
            consecutive_days = kwargs.get('consecutive_days', 0)
            if consecutive_days >= 7:
                return base_points * 2  # Double bonus for weekly streaks
            elif consecutive_days >= 30:
                return base_points * 3  # Triple bonus for monthly streaks
                
        elif activity_type == 'quality_comment':
            comment_length = kwargs.get('comment_length', 0)
            if comment_length > 200:
                return base_points + 10  # Bonus for detailed comments
                
        elif activity_type == 'confession_liked':
            like_count = kwargs.get('like_count', 0)
            if like_count >= 50:
                return base_points * 3  # Bonus for viral confessions
            elif like_count >= 20:
                return base_points * 2  # Bonus for popular confessions
        
        return base_points

class RankingManager:
    """Main ranking system manager"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.anonymous_names = self._generate_anonymous_names()
    
    def _generate_anonymous_names(self) -> List[str]:
        """Generate pool of anonymous names for leaderboards"""
        adjectives = [
            'Mysterious', 'Silent', 'Thoughtful', 'Wise', 'Clever', 'Brave',
            'Gentle', 'Creative', 'Curious', 'Humble', 'Witty', 'Bold',
            'Peaceful', 'Bright', 'Swift', 'Noble', 'Kind', 'Cheerful'
        ]
        nouns = [
            'Confessor', 'Student', 'Dreamer', 'Thinker', 'Writer', 'Scholar',
            'Observer', 'Listener', 'Helper', 'Friend', 'Sage', 'Storyteller',
            'Guardian', 'Seeker', 'Wanderer', 'Explorer', 'Creator', 'Mentor'
        ]
        
        names = []
        for adj in adjectives:
            for noun in nouns:
                names.append(f"{adj} {noun}")
        return names
    
    def initialize_user_ranking(self, user_id: int) -> bool:
        """Initialize ranking data for a new user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO user_rankings (user_id)
                    VALUES (?)
                ''', (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to initialize ranking for user {user_id}: {e}")
            return False
    
    def award_points(self, user_id: int, activity_type: str, reference_id: int = None, 
                    reference_type: str = None, **kwargs) -> Tuple[bool, int]:
        """Award points to a user for an activity"""
        try:
            self.initialize_user_ranking(user_id)
            
            points = PointSystem.calculate_points(activity_type, **kwargs)
            description = kwargs.get('description', f"Points for {activity_type}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Record point transaction
                cursor.execute('''
                    INSERT INTO point_transactions 
                    (user_id, points_change, transaction_type, reference_id, reference_type, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, points, activity_type, reference_id, reference_type, description))
                
                # Update user's total points
                cursor.execute('''
                    UPDATE user_rankings 
                    SET total_points = total_points + ?,
                        weekly_points = weekly_points + ?,
                        monthly_points = monthly_points + ?,
                        last_activity = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (points, points, points, user_id))
                
                # Update consecutive days if it's a daily login
                if activity_type == 'daily_login':
                    self._update_consecutive_days(cursor, user_id)
                
                conn.commit()
                
                # Check for rank up
                self._check_rank_up(user_id)
                
                # Check for achievements
                self._check_achievements(user_id, activity_type, **kwargs)
                
                logger.info(f"Awarded {points} points to user {user_id} for {activity_type}")
                return True, points
                
        except Exception as e:
            logger.error(f"Failed to award points to user {user_id}: {e}")
            return False, 0
    
    def _update_consecutive_days(self, cursor, user_id: int):
        """Update consecutive days count"""
        cursor.execute('''
            SELECT last_activity, consecutive_days 
            FROM user_rankings WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        if not result:
            return
            
        last_activity_str, consecutive_days = result
        if last_activity_str:
            last_activity = datetime.fromisoformat(last_activity_str).date()
            today = date.today()
            yesterday = today - timedelta(days=1)
            
            if last_activity == yesterday:
                # Consecutive day
                new_consecutive = consecutive_days + 1
                cursor.execute('''
                    UPDATE user_rankings 
                    SET consecutive_days = ?
                    WHERE user_id = ?
                ''', (new_consecutive, user_id))
                
                # Award bonus points for streak
                if new_consecutive >= 3:
                    bonus_points = PointSystem.calculate_points(
                        'consecutive_days_bonus', 
                        consecutive_days=new_consecutive
                    )
                    cursor.execute('''
                        INSERT INTO point_transactions 
                        (user_id, points_change, transaction_type, description)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, bonus_points, 'consecutive_days_bonus', 
                          f"Consecutive days bonus: {new_consecutive} days"))
                    
                    cursor.execute('''
                        UPDATE user_rankings 
                        SET total_points = total_points + ?
                        WHERE user_id = ?
                    ''', (bonus_points, user_id))
                    
            elif last_activity != today:
                # Streak broken
                cursor.execute('''
                    UPDATE user_rankings 
                    SET consecutive_days = 1
                    WHERE user_id = ?
                ''', (user_id,))
    
    def _check_rank_up(self, user_id: int) -> bool:
        """Check if user should rank up"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get user's current points and rank
                cursor.execute('''
                    SELECT ur.total_points, ur.current_rank_id, rd.points_required
                    FROM user_rankings ur
                    JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
                    WHERE ur.user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if not result:
                    return False
                
                total_points, current_rank_id, current_rank_points = result
                
                # Find the highest rank this user qualifies for
                cursor.execute('''
                    SELECT rank_id, rank_name, points_required
                    FROM rank_definitions
                    WHERE points_required <= ?
                    ORDER BY points_required DESC
                    LIMIT 1
                ''', (total_points,))
                
                new_rank_result = cursor.fetchone()
                if not new_rank_result:
                    return False
                
                new_rank_id, new_rank_name, _ = new_rank_result
                
                if new_rank_id > current_rank_id:
                    # Rank up!
                    cursor.execute('''
                        UPDATE user_rankings
                        SET current_rank_id = ?,
                            highest_rank_achieved = CASE 
                                WHEN ? > highest_rank_achieved THEN ?
                                ELSE highest_rank_achieved
                            END
                        WHERE user_id = ?
                    ''', (new_rank_id, new_rank_id, new_rank_id, user_id))
                    
                    # Record rank change
                    cursor.execute('''
                        INSERT INTO rank_history
                        (user_id, old_rank_id, new_rank_id, points_at_change, reason)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, current_rank_id, new_rank_id, total_points, 'Points threshold reached'))
                    
                    conn.commit()
                    
                    # Award rank up achievement
                    self._award_achievement(
                        user_id, 
                        'rank_up', 
                        f'Ranked Up to {new_rank_name}',
                        f'Achieved {new_rank_name} rank!',
                        50
                    )
                    
                    logger.info(f"User {user_id} ranked up to {new_rank_name}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Failed to check rank up for user {user_id}: {e}")
            return False
    
    def _check_achievements(self, user_id: int, activity_type: str, **kwargs):
        """Check and award achievements"""
        achievements_to_check = self._get_achievement_definitions()
        
        for achievement in achievements_to_check:
            if self._user_qualifies_for_achievement(user_id, achievement, activity_type, **kwargs):
                self._award_achievement(
                    user_id,
                    achievement.achievement_type,
                    achievement.achievement_name,
                    achievement.achievement_description,
                    achievement.points_awarded,
                    achievement.is_special
                )
    
    def _get_achievement_definitions(self) -> List[Achievement]:
        """Get list of available achievements"""
        return [
            # First time achievements
            Achievement('first_confession', '🎯 First Confession', 'Posted your first confession', 50),
            Achievement('first_comment', '💬 First Comment', 'Made your first comment', 20),
            Achievement('first_like', '👍 First Like', 'Received your first like', 10),
            
            # Milestone achievements
            Achievement('confession_milestone_10', '📝 Storyteller', 'Posted 10 confessions', 100),
            Achievement('confession_milestone_50', '📚 Author', 'Posted 50 confessions', 300),
            Achievement('confession_milestone_100', '✍️ Master Writer', 'Posted 100 confessions', 500, True),
            
            Achievement('comment_milestone_50', '💬 Conversationalist', 'Made 50 comments', 100),
            Achievement('comment_milestone_200', '🗣️ Community Voice', 'Made 200 comments', 300),
            Achievement('comment_milestone_500', '🎙️ Discussion Leader', 'Made 500 comments', 500, True),
            
            # Engagement achievements
            Achievement('popular_confession', '🔥 Viral Post', 'Got 100+ likes on a confession', 200, True),
            Achievement('helpful_commenter', '🤝 Helper', 'Received 50+ likes on comments', 150),
            Achievement('community_favorite', '⭐ Community Star', 'Top 10 on monthly leaderboard', 300, True),
            
            # Streak achievements
            Achievement('week_streak', '🔥 Week Warrior', '7 consecutive days active', 100),
            Achievement('month_streak', '💪 Monthly Master', '30 consecutive days active', 500, True),
            Achievement('quarter_streak', '👑 Quarter Champion', '90 consecutive days active', 1000, True),
            
            # Special achievements
            Achievement('early_bird', '🌅 Early Bird', 'Posted 10 confessions before 8 AM', 100),
            Achievement('night_owl', '🦉 Night Owl', 'Posted 10 confessions after 10 PM', 100),
            Achievement('quality_contributor', '💎 Quality Contributor', '10 high-quality posts', 250, True),
        ]
    
    def _user_qualifies_for_achievement(self, user_id: int, achievement: Achievement, 
                                      activity_type: str, **kwargs) -> bool:
        """Check if user qualifies for a specific achievement"""
        # Check if user already has this achievement
        if self._user_has_achievement(user_id, achievement.achievement_type):
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if achievement.achievement_type == 'first_confession' and activity_type == 'confession_approved':
                    return True
                elif achievement.achievement_type == 'first_comment' and activity_type == 'comment_posted':
                    return True
                elif achievement.achievement_type == 'first_like' and activity_type == 'confession_liked':
                    return True
                elif achievement.achievement_type == 'confession_milestone_10':
                    cursor.execute('SELECT COUNT(*) FROM posts WHERE user_id = ? AND approved = 1', (user_id,))
                    count = cursor.fetchone()[0]
                    return count >= 10
                elif achievement.achievement_type == 'confession_milestone_50':
                    cursor.execute('SELECT COUNT(*) FROM posts WHERE user_id = ? AND approved = 1', (user_id,))
                    count = cursor.fetchone()[0]
                    return count >= 50
                elif achievement.achievement_type == 'confession_milestone_100':
                    cursor.execute('SELECT COUNT(*) FROM posts WHERE user_id = ? AND approved = 1', (user_id,))
                    count = cursor.fetchone()[0]
                    return count >= 100
                # Add more achievement checks here...
                
        except Exception as e:
            logger.error(f"Error checking achievement qualification: {e}")
        
        return False
    
    def _user_has_achievement(self, user_id: int, achievement_type: str) -> bool:
        """Check if user already has an achievement"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM user_achievements 
                    WHERE user_id = ? AND achievement_type = ?
                ''', (user_id, achievement_type))
                return cursor.fetchone()[0] > 0
        except Exception as e:
            logger.error(f"Error checking user achievement: {e}")
            return True  # Assume they have it to prevent duplicate awards
    
    def _award_achievement(self, user_id: int, achievement_type: str, name: str, 
                          description: str, points: int, is_special: bool = False):
        """Award an achievement to a user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Award achievement
                cursor.execute('''
                    INSERT INTO user_achievements
                    (user_id, achievement_type, achievement_name, achievement_description, 
                     points_awarded, is_special)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, achievement_type, name, description, points, is_special))
                
                # Award points
                cursor.execute('''
                    INSERT INTO point_transactions
                    (user_id, points_change, transaction_type, description)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, points, 'achievement', f'Achievement: {name}'))
                
                # Update user points and achievement count
                cursor.execute('''
                    UPDATE user_rankings
                    SET total_points = total_points + ?,
                        total_achievements = total_achievements + 1
                    WHERE user_id = ?
                ''', (points, user_id))
                
                conn.commit()
                logger.info(f"Awarded achievement '{name}' to user {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to award achievement to user {user_id}: {e}")
    
    def get_user_rank(self, user_id: int) -> Optional[UserRank]:
        """Get complete ranking information for a user"""
        try:
            self.initialize_user_ranking(user_id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ur.total_points, ur.current_rank_id, ur.rank_progress,
                           rd.rank_name, rd.rank_emoji, rd.special_perks, rd.is_special_rank,
                           next_rd.points_required as next_rank_points
                    FROM user_rankings ur
                    JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
                    LEFT JOIN rank_definitions next_rd ON next_rd.rank_id = rd.rank_id + 1
                    WHERE ur.user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if not result:
                    return None
                
                (total_points, current_rank_id, rank_progress, rank_name, 
                 rank_emoji, special_perks_json, is_special_rank, next_rank_points) = result
                
                special_perks = json.loads(special_perks_json or '{}')
                points_to_next = (next_rank_points or 0) - total_points
                
                return UserRank(
                    user_id=user_id,
                    total_points=total_points,
                    current_rank_id=current_rank_id,
                    rank_name=rank_name,
                    rank_emoji=rank_emoji,
                    rank_progress=rank_progress,
                    next_rank_points=next_rank_points or 0,
                    points_to_next=max(0, points_to_next),
                    special_perks=special_perks,
                    is_special_rank=bool(is_special_rank)
                )
                
        except Exception as e:
            logger.error(f"Failed to get user rank for {user_id}: {e}")
            return None
    
    def get_leaderboard(self, timeframe: str = 'weekly', limit: int = 10) -> List[Dict]:
        """Get leaderboard for specified timeframe"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if timeframe == 'weekly':
                    cursor.execute('''
                        SELECT ur.weekly_points, rd.rank_emoji, rd.rank_name,
                               ROW_NUMBER() OVER (ORDER BY ur.weekly_points DESC) as position
                        FROM user_rankings ur
                        JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
                        WHERE ur.weekly_points > 0
                        ORDER BY ur.weekly_points DESC
                        LIMIT ?
                    ''', (limit,))
                elif timeframe == 'monthly':
                    cursor.execute('''
                        SELECT ur.monthly_points, rd.rank_emoji, rd.rank_name,
                               ROW_NUMBER() OVER (ORDER BY ur.monthly_points DESC) as position
                        FROM user_rankings ur
                        JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
                        WHERE ur.monthly_points > 0
                        ORDER BY ur.monthly_points DESC
                        LIMIT ?
                    ''', (limit,))
                else:  # all-time
                    cursor.execute('''
                        SELECT ur.total_points, rd.rank_emoji, rd.rank_name,
                               ROW_NUMBER() OVER (ORDER BY ur.total_points DESC) as position
                        FROM user_rankings ur
                        JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
                        WHERE ur.total_points > 0
                        ORDER BY ur.total_points DESC
                        LIMIT ?
                    ''', (limit,))
                
                results = cursor.fetchall()
                leaderboard = []
                
                for i, (points, rank_emoji, rank_name, position) in enumerate(results):
                    # Generate anonymous name
                    anonymous_name = random.choice(self.anonymous_names)
                    
                    leaderboard.append({
                        'position': position,
                        'anonymous_name': anonymous_name,
                        'points': points,
                        'rank_emoji': rank_emoji,
                        'rank_name': rank_name
                    })
                
                return leaderboard
                
        except Exception as e:
            logger.error(f"Failed to get leaderboard: {e}")
            return []
    
    def get_user_achievements(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Get user's achievements"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT achievement_name, achievement_description, points_awarded,
                           earned_date, is_special
                    FROM user_achievements
                    WHERE user_id = ?
                    ORDER BY earned_date DESC
                    LIMIT ?
                ''', (user_id, limit))
                
                achievements = []
                for row in cursor.fetchall():
                    achievements.append({
                        'name': row[0],
                        'description': row[1],
                        'points': row[2],
                        'date': row[3],
                        'is_special': bool(row[4])
                    })
                
                return achievements
                
        except Exception as e:
            logger.error(f"Failed to get achievements for user {user_id}: {e}")
            return []

# Global ranking manager instance
ranking_manager = RankingManager()
