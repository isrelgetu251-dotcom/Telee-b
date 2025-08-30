"""
Database migration system for the confession bot
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Callable
import hashlib

from config import DB_PATH
from logger import get_logger

logger = get_logger('migrations')


class Migration:
    """Represents a single database migration"""
    
    def __init__(self, version: int, name: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.checksum = hashlib.md5((up_sql + down_sql).encode()).hexdigest()


class MigrationManager:
    """Manages database schema migrations"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.migrations: List[Migration] = []
        self._setup_migration_table()
        self._register_migrations()
    
    def _setup_migration_table(self):
        """Create migrations table if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _register_migrations(self):
        """Register all available migrations"""
        self.migrations = [
            # Version 1: Initial schema (already exists)
            Migration(
                version=1,
                name="initial_schema",
                up_sql="-- Initial schema already exists",
                down_sql=""
            ),
            
            # Version 2: Add user preferences
            Migration(
                version=2,
                name="add_user_preferences",
                up_sql="""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    notification_enabled INTEGER DEFAULT 1,
                    daily_digest_enabled INTEGER DEFAULT 1,
                    language TEXT DEFAULT 'en',
                    timezone TEXT DEFAULT 'UTC',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                """,
                down_sql="DROP TABLE IF EXISTS user_preferences;"
            ),
            
            # Version 3: Add confession drafts
            Migration(
                version=3,
                name="add_confession_drafts",
                up_sql="""
                CREATE TABLE IF NOT EXISTS confession_drafts (
                    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_drafts_user_id ON confession_drafts(user_id);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_drafts_user_id;
                DROP TABLE IF EXISTS confession_drafts;
                """
            ),
            
            # Version 4: Add scheduled confessions
            Migration(
                version=4,
                name="add_scheduled_confessions",
                up_sql="""
                CREATE TABLE IF NOT EXISTS scheduled_confessions (
                    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    scheduled_for TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    posted_at TEXT,
                    post_id INTEGER,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(post_id) REFERENCES posts(post_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_scheduled_user_id ON scheduled_confessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_scheduled_status ON scheduled_confessions(status);
                CREATE INDEX IF NOT EXISTS idx_scheduled_time ON scheduled_confessions(scheduled_for);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_scheduled_time;
                DROP INDEX IF EXISTS idx_scheduled_status;
                DROP INDEX IF EXISTS idx_scheduled_user_id;
                DROP TABLE IF EXISTS scheduled_confessions;
                """
            ),
            
            # Version 5: Add analytics tables
            Migration(
                version=5,
                name="add_analytics_tables",
                up_sql="""
                CREATE TABLE IF NOT EXISTS user_activity_log (
                    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                
                CREATE TABLE IF NOT EXISTS daily_stats (
                    stat_date TEXT PRIMARY KEY,
                    new_users INTEGER DEFAULT 0,
                    total_confessions INTEGER DEFAULT 0,
                    approved_confessions INTEGER DEFAULT 0,
                    rejected_confessions INTEGER DEFAULT 0,
                    total_comments INTEGER DEFAULT 0,
                    active_users INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_activity_user_id ON user_activity_log(user_id);
                CREATE INDEX IF NOT EXISTS idx_activity_type ON user_activity_log(activity_type);
                CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON user_activity_log(timestamp);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_activity_timestamp;
                DROP INDEX IF EXISTS idx_activity_type;
                DROP INDEX IF EXISTS idx_activity_user_id;
                DROP TABLE IF EXISTS daily_stats;
                DROP TABLE IF EXISTS user_activity_log;
                """
            ),
            
            # Version 6: Add notification system
            Migration(
                version=6,
                name="add_notification_system",
                up_sql="""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    data TEXT,
                    read INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    read_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
                CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
                CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_notifications_type;
                DROP INDEX IF EXISTS idx_notifications_read;
                DROP INDEX IF EXISTS idx_notifications_user_id;
                DROP TABLE IF EXISTS notifications;
                """
            ),
            
            # Version 7: Add content moderation enhancements
            Migration(
                version=7,
                name="enhance_content_moderation",
                up_sql="""
                -- Add sentiment analysis results
                ALTER TABLE posts ADD COLUMN sentiment_score REAL DEFAULT 0.0;
                ALTER TABLE posts ADD COLUMN sentiment_label TEXT DEFAULT 'neutral';
                ALTER TABLE comments ADD COLUMN sentiment_score REAL DEFAULT 0.0;
                ALTER TABLE comments ADD COLUMN sentiment_label TEXT DEFAULT 'neutral';
                
                -- Add content filtering flags
                ALTER TABLE posts ADD COLUMN profanity_detected INTEGER DEFAULT 0;
                ALTER TABLE posts ADD COLUMN spam_score REAL DEFAULT 0.0;
                ALTER TABLE comments ADD COLUMN profanity_detected INTEGER DEFAULT 0;
                ALTER TABLE comments ADD COLUMN spam_score REAL DEFAULT 0.0;
                
                -- Create moderation log table
                CREATE TABLE IF NOT EXISTS moderation_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    moderator_id INTEGER NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(moderator_id) REFERENCES users(user_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_moderation_target ON moderation_log(target_type, target_id);
                CREATE INDEX IF NOT EXISTS idx_moderation_moderator ON moderation_log(moderator_id);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_moderation_moderator;
                DROP INDEX IF EXISTS idx_moderation_target;
                DROP TABLE IF EXISTS moderation_log;
                """
            ),
            
            # Version 8: Add performance indexes
            Migration(
                version=8,
                name="add_performance_indexes",
                up_sql="""
                CREATE INDEX IF NOT EXISTS idx_posts_approved_timestamp ON posts(approved, timestamp);
                CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category);
                CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id);
                CREATE INDEX IF NOT EXISTS idx_comments_post_id_timestamp ON comments(post_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_comments_user_id ON comments(user_id);
                CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_comment_id);
                CREATE INDEX IF NOT EXISTS idx_reactions_user_target ON reactions(user_id, target_type, target_id);
                CREATE INDEX IF NOT EXISTS idx_reactions_target ON reactions(target_type, target_id);
                CREATE INDEX IF NOT EXISTS idx_reports_target ON reports(target_type, target_id);
                CREATE INDEX IF NOT EXISTS idx_admin_messages_user ON admin_messages(user_id, replied);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_admin_messages_user;
                DROP INDEX IF EXISTS idx_reports_target;
                DROP INDEX IF EXISTS idx_reactions_target;
                DROP INDEX IF EXISTS idx_reactions_user_target;
                DROP INDEX IF EXISTS idx_comments_parent;
                DROP INDEX IF EXISTS idx_comments_user_id;
                DROP INDEX IF EXISTS idx_comments_post_id_timestamp;
                DROP INDEX IF EXISTS idx_posts_user_id;
                DROP INDEX IF EXISTS idx_posts_category;
                DROP INDEX IF EXISTS idx_posts_approved_timestamp;
                """
            ),
            
            # Version 9: Add backup metadata
            Migration(
                version=9,
                name="add_backup_metadata",
                up_sql="""
                CREATE TABLE IF NOT EXISTS backup_metadata (
                    backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    record_count INTEGER NOT NULL,
                    backup_type TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_backup_created ON backup_metadata(created_at);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_backup_created;
                DROP TABLE IF EXISTS backup_metadata;
                """
            ),
            
            # Version 10: Add missing user columns
            Migration(
                version=10,
                name="add_user_profile_columns",
                up_sql="""
                ALTER TABLE users ADD COLUMN join_date TEXT;
                """,
                down_sql=""
            ),
            
            # Version 11: Add channel_message_id column if missing
            Migration(
                version=11,
                name="add_channel_message_id",
                up_sql="""
                -- Add channel_message_id column to posts table if it doesn't exist
                ALTER TABLE posts ADD COLUMN channel_message_id INTEGER;
                """,
                down_sql=""
            )
        ]
    
    def get_current_version(self) -> int:
        """Get current database schema version"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) FROM migrations")
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0
    
    def get_applied_migrations(self) -> List[int]:
        """Get list of applied migration versions"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM migrations ORDER BY version")
            return [row[0] for row in cursor.fetchall()]
    
    def apply_migration(self, migration: Migration) -> bool:
        """Apply a single migration"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if migration is already applied
                cursor.execute("SELECT version FROM migrations WHERE version = ?", (migration.version,))
                if cursor.fetchone():
                    logger.info(f"Migration {migration.version} already applied, skipping")
                    return True
                
                # Apply the migration
                logger.info(f"Applying migration {migration.version}: {migration.name}")
                
                # Execute the up SQL
                if migration.up_sql.strip():
                    # Split by semicolon and execute each statement
                    statements = [stmt.strip() for stmt in migration.up_sql.split(';') if stmt.strip()]
                    for statement in statements:
                        cursor.execute(statement)
                
                # Record the migration
                cursor.execute("""
                    INSERT INTO migrations (version, name, checksum, applied_at)
                    VALUES (?, ?, ?, ?)
                """, (migration.version, migration.name, migration.checksum, datetime.now().isoformat()))
                
                conn.commit()
                logger.info(f"Migration {migration.version} applied successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to apply migration {migration.version}: {e}")
            return False
    
    def migrate_to_latest(self) -> bool:
        """Apply all pending migrations"""
        current_version = self.get_current_version()
        applied_versions = set(self.get_applied_migrations())
        
        # Find unapplied migrations
        unapplied_migrations = [
            migration for migration in self.migrations
            if migration.version not in applied_versions and migration.version > current_version
        ]
        
        # Sort by version
        unapplied_migrations.sort(key=lambda m: m.version)
        
        if not unapplied_migrations:
            logger.info("Database is up to date")
            return True
        
        logger.info(f"Applying {len(unapplied_migrations)} migrations")
        
        # Apply each migration
        for migration in unapplied_migrations:
            if not self.apply_migration(migration):
                logger.error(f"Migration failed at version {migration.version}")
                return False
        
        logger.info("All migrations applied successfully")
        return True
    
    def get_migration_status(self) -> dict:
        """Get detailed migration status"""
        current_version = self.get_current_version()
        applied_versions = set(self.get_applied_migrations())
        
        status = {
            'current_version': current_version,
            'latest_version': max(m.version for m in self.migrations),
            'applied_migrations': sorted(applied_versions),
            'pending_migrations': [
                m.version for m in self.migrations
                if m.version not in applied_versions
            ],
            'migration_details': []
        }
        
        for migration in self.migrations:
            status['migration_details'].append({
                'version': migration.version,
                'name': migration.name,
                'applied': migration.version in applied_versions,
                'checksum': migration.checksum
            })
        
        return status


# Global migration manager
migration_manager = MigrationManager()


def run_migrations():
    """Run all pending migrations"""
    return migration_manager.migrate_to_latest()


def get_migration_status():
    """Get migration status"""
    return migration_manager.get_migration_status()
