#!/usr/bin/env python3
"""
Database Fix Script for University Confession Bot
This script fixes database schema issues and migrates data
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add the bot directory to Python path
bot_dir = Path(__file__).parent
sys.path.insert(0, str(bot_dir))

from config import DB_PATH

def backup_database():
    """Create a backup of the current database"""
    if os.path.exists(DB_PATH):
        backup_path = f"{DB_PATH}.backup"
        with open(DB_PATH, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        print(f"✅ Database backed up to {backup_path}")
        return True
    return False

def check_table_structure():
    """Check current table structure"""
    print("🔍 Checking current database structure...")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📋 Existing tables: {tables}")
        
        # Check posts table structure
        if 'posts' in tables:
            cursor.execute("PRAGMA table_info(posts)")
            posts_columns = [row[1] for row in cursor.fetchall()]
            print(f"📝 Posts columns: {posts_columns}")
            
        # Check comments table structure  
        if 'comments' in tables:
            cursor.execute("PRAGMA table_info(comments)")
            comments_columns = [row[1] for row in cursor.fetchall()]
            print(f"💬 Comments columns: {comments_columns}")
            
        # Check users table structure
        if 'users' in tables:
            cursor.execute("PRAGMA table_info(users)")
            users_columns = [row[1] for row in cursor.fetchall()]
            print(f"👥 Users columns: {users_columns}")

def fix_database_schema():
    """Fix database schema issues"""
    print("\n🔧 Fixing database schema...")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        try:
            # Check if posts table has 'approved' column, if not add it
            cursor.execute("PRAGMA table_info(posts)")
            posts_columns = [row[1] for row in cursor.fetchall()]
            
            if 'approved' not in posts_columns:
                print("🔄 Adding 'approved' column to posts table...")
                cursor.execute("ALTER TABLE posts ADD COLUMN approved INTEGER DEFAULT NULL")
                
                # Migrate data from 'status' column if it exists
                if 'status' in posts_columns:
                    print("🔄 Migrating data from 'status' to 'approved' column...")
                    cursor.execute("UPDATE posts SET approved = 1 WHERE status = 'approved'")
                    cursor.execute("UPDATE posts SET approved = 0 WHERE status = 'rejected'")
                    cursor.execute("UPDATE posts SET approved = NULL WHERE status = 'pending' OR status IS NULL")
            
            # Check if comments table has required columns
            cursor.execute("PRAGMA table_info(comments)")
            comments_columns = [row[1] for row in cursor.fetchall()]
            
            required_comment_columns = ['likes', 'dislikes']
            for col in required_comment_columns:
                if col not in comments_columns:
                    print(f"🔄 Adding '{col}' column to comments table...")
                    cursor.execute(f"ALTER TABLE comments ADD COLUMN {col} INTEGER DEFAULT 0")
            
            # Check users table
            cursor.execute("PRAGMA table_info(users)")
            users_columns = [row[1] for row in cursor.fetchall()]
            
            # Make sure required user columns exist
            if 'username' not in users_columns:
                print("🔄 Adding 'username' column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
                
            if 'join_date' not in users_columns:
                print("🔄 Adding 'join_date' column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN join_date TEXT DEFAULT CURRENT_TIMESTAMP")
            
            conn.commit()
            print("✅ Database schema fixed successfully!")
            
        except Exception as e:
            print(f"❌ Error fixing database schema: {e}")
            conn.rollback()
            return False
    
    return True

def create_missing_tables():
    """Create any missing tables"""
    print("\n🏗️  Creating missing tables...")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        try:
            # Ensure reactions table exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                reaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                reaction_type TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, target_type, target_id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )''')
            
            # Ensure reports table exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                reason TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )''')
            
            # Ensure admin_messages table exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                admin_id INTEGER,
                user_message TEXT,
                admin_reply TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                replied INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )''')
            
            conn.commit()
            print("✅ Missing tables created successfully!")
            
        except Exception as e:
            print(f"❌ Error creating missing tables: {e}")
            return False
            
    return True

def verify_database():
    """Verify the database is working correctly"""
    print("\n✅ Verifying database...")
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Test basic queries
            cursor.execute("SELECT COUNT(*) FROM users")
            users_count = cursor.fetchone()[0]
            print(f"📊 Users count: {users_count}")
            
            cursor.execute("SELECT COUNT(*) FROM posts")  
            posts_count = cursor.fetchone()[0]
            print(f"📊 Posts count: {posts_count}")
            
            cursor.execute("SELECT COUNT(*) FROM comments")
            comments_count = cursor.fetchone()[0]
            print(f"📊 Comments count: {comments_count}")
            
            # Test a query that was causing issues
            cursor.execute("SELECT COUNT(*) FROM posts WHERE approved = 1")
            approved_posts = cursor.fetchone()[0]
            print(f"📊 Approved posts: {approved_posts}")
            
            print("✅ Database verification passed!")
            return True
            
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

def main():
    """Main function"""
    print("🔧 University Confession Bot - Database Fix Script")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        print("💡 Please run the bot first to create the initial database.")
        return False
    
    # Create backup
    if not backup_database():
        print("⚠️  Warning: Could not create backup (database might not exist yet)")
    
    # Check current structure
    check_table_structure()
    
    # Fix schema
    if not fix_database_schema():
        print("❌ Failed to fix database schema")
        return False
    
    # Create missing tables
    if not create_missing_tables():
        print("❌ Failed to create missing tables")
        return False
    
    # Verify everything works
    if not verify_database():
        print("❌ Database verification failed")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS: Database has been fixed and is ready to use!")
    print("🚀 You can now start the bot with: python start_bot.py")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    input("\nPress Enter to exit...")
    sys.exit(0 if success else 1)
