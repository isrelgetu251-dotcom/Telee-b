"""
Database migration for User Ranking System
Adds tables for points, ranks, achievements, and leaderboards
"""

import sqlite3
from config import DB_PATH
from logger import get_logger

logger = get_logger('ranking_migration')

def create_ranking_tables():
    """Create all ranking system tables"""
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # User points and ranking table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_rankings (
            user_id INTEGER PRIMARY KEY,
            total_points INTEGER DEFAULT 0,
            current_rank_id INTEGER DEFAULT 1,
            rank_progress REAL DEFAULT 0.0,
            weekly_points INTEGER DEFAULT 0,
            monthly_points INTEGER DEFAULT 0,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            consecutive_days INTEGER DEFAULT 0,
            highest_rank_achieved INTEGER DEFAULT 1,
            total_achievements INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(current_rank_id) REFERENCES rank_definitions(rank_id)
        )''')
        
        # Rank definitions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rank_definitions (
            rank_id INTEGER PRIMARY KEY,
            rank_name TEXT NOT NULL,
            rank_emoji TEXT NOT NULL,
            points_required INTEGER NOT NULL,
            rank_color TEXT DEFAULT '#ffffff',
            special_perks TEXT, -- JSON string of perks
            rank_description TEXT,
            is_special_rank INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # User achievements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_type TEXT NOT NULL,
            achievement_name TEXT NOT NULL,
            achievement_description TEXT,
            points_awarded INTEGER DEFAULT 0,
            earned_date TEXT DEFAULT CURRENT_TIMESTAMP,
            is_special INTEGER DEFAULT 0,
            metadata TEXT, -- JSON for additional data
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        # Point transactions table (for tracking point changes)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS point_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            points_change INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            reference_id INTEGER, -- post_id, comment_id, etc.
            reference_type TEXT, -- 'confession', 'comment', 'like', etc.
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        # Weekly leaderboard table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS weekly_leaderboard (
            leaderboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            week_start DATE NOT NULL,
            week_end DATE NOT NULL,
            points_earned INTEGER NOT NULL,
            rank_position INTEGER NOT NULL,
            anonymous_display_name TEXT, -- Generated anonymous name
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        # Monthly leaderboard table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_leaderboard (
            leaderboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month_year TEXT NOT NULL, -- Format: 'YYYY-MM'
            points_earned INTEGER NOT NULL,
            rank_position INTEGER NOT NULL,
            anonymous_display_name TEXT,
            special_recognition TEXT, -- 'top_confessor', 'top_commenter', etc.
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        # Rank history table (track rank changes)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rank_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            old_rank_id INTEGER,
            new_rank_id INTEGER NOT NULL,
            points_at_change INTEGER NOT NULL,
            reason TEXT, -- What triggered the rank change
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(old_rank_id) REFERENCES rank_definitions(rank_id),
            FOREIGN KEY(new_rank_id) REFERENCES rank_definitions(rank_id)
        )''')
        
        conn.commit()
        logger.info("Ranking system tables created successfully")

def insert_default_ranks():
    """Insert default rank definitions"""
    
    ranks = [
        # Beginner Ranks
        (1, 'New Confessor', '🆕', 0, '#808080', '{}', 'Welcome to the community!', 0),
        (2, 'First Timer', '🌱', 50, '#90EE90', '{"daily_confessions": 2}', 'Getting started with confessions', 0),
        (3, 'Regular', '📝', 150, '#87CEEB', '{"daily_confessions": 3}', 'Regular community member', 0),
        
        # Intermediate Ranks
        (4, 'Active Member', '⚡', 300, '#FFD700', '{"daily_confessions": 4, "priority_review": true}', 'Active in the community', 0),
        (5, 'Community Helper', '🤝', 500, '#FF6347', '{"daily_confessions": 5, "comment_highlight": true}', 'Helps others with thoughtful comments', 0),
        (6, 'Trusted Confessor', '🌟', 750, '#FF69B4', '{"daily_confessions": 6, "featured_chance": 0.2}', 'Trusted community member', 0),
        
        # Advanced Ranks
        (7, 'Veteran', '🏆', 1200, '#8A2BE2', '{"daily_confessions": 8, "exclusive_categories": true}', 'Long-time community veteran', 0),
        (8, 'Elite Confessor', '💎', 2000, '#DC143C', '{"daily_confessions": 10, "custom_emoji": true}', 'Elite community member', 0),
        (9, 'Community Legend', '👑', 3500, '#B8860B', '{"daily_confessions": 15, "legend_badge": true}', 'Legendary status achieved', 1),
        
        # Special Ranks
        (10, 'Master Storyteller', '📚', 5000, '#4B0082', '{"unlimited_daily": true, "story_highlight": true}', 'Master of confession storytelling', 1),
        (11, 'Community Guardian', '🛡️', 7500, '#800000', '{"moderation_assist": true, "guardian_badge": true}', 'Helps maintain community standards', 1),
        (12, 'Confession Sage', '🧙‍♂️', 10000, '#FFD700', '{"all_perks": true, "sage_recognition": true}', 'Ultimate community wisdom', 1),
    ]
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT OR REPLACE INTO rank_definitions 
            (rank_id, rank_name, rank_emoji, points_required, rank_color, special_perks, rank_description, is_special_rank)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ranks)
        conn.commit()
        logger.info(f"Inserted {len(ranks)} default ranks")

def run_ranking_migration():
    """Run the complete ranking system migration"""
    try:
        logger.info("Starting ranking system migration...")
        create_ranking_tables()
        insert_default_ranks()
        logger.info("Ranking system migration completed successfully!")
        return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = run_ranking_migration()
    if success:
        print("✅ Ranking system migration completed!")
    else:
        print("❌ Migration failed. Check logs for details.")
