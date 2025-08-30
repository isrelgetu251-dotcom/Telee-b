import sqlite3
import datetime
from config import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    """Initialize database with enhanced schema"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table with join date tracking
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT DEFAULT CURRENT_TIMESTAMP,
        questions_asked INTEGER DEFAULT 0,
        comments_posted INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0
    )''')
    
    # Posts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        post_id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        category TEXT NOT NULL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER NOT NULL,
        approved INTEGER DEFAULT NULL,
        channel_message_id INTEGER,
        flagged INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Comments table with enhanced structure
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        parent_comment_id INTEGER,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        likes INTEGER DEFAULT 0,
        dislikes INTEGER DEFAULT 0,
        flagged INTEGER DEFAULT 0,
        FOREIGN KEY(post_id) REFERENCES posts(post_id),
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(parent_comment_id) REFERENCES comments(comment_id)
    )''')
    
    # Likes/Reactions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reactions (
        reaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        target_type TEXT NOT NULL, -- "post" or "comment"
        target_id INTEGER NOT NULL,
        reaction_type TEXT NOT NULL, -- "like" or "dislike"
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, target_type, target_id),
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Reports table
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
    
    # Admin messages table for admin-user communication
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
    conn.close()

def add_user(user_id, username=None, first_name=None, last_name=None):
    """Add or update user information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, join_date, questions_asked, comments_posted, blocked)
            VALUES (?, ?, ?, ?, 
                COALESCE((SELECT join_date FROM users WHERE user_id = ? AND join_date IS NOT NULL), CURRENT_TIMESTAMP),
                COALESCE((SELECT questions_asked FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT comments_posted FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT blocked FROM users WHERE user_id = ?), 0)
            )
        ''', (user_id, username, first_name, last_name, user_id, user_id, user_id, user_id))
        conn.commit()

def get_user_info(user_id):
    """Get complete user information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, join_date, 
                   questions_asked, comments_posted, blocked
            FROM users WHERE user_id = ?
        ''', (user_id,))
        return cursor.fetchone()

def get_comment_count(post_id):
    """Get total comment count for a post (including replies)"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM comments WHERE post_id = ?', (post_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

def is_blocked_user(user_id):
    """Check if user is blocked"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT blocked FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1

def get_user_posts(user_id, limit=10):
    """Get user's posts with status and comment count"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.approved,
                   COUNT(c.comment_id) as comment_count
            FROM posts p
            LEFT JOIN comments c ON p.post_id = c.post_id
            WHERE p.user_id = ?
            GROUP BY p.post_id, p.content, p.category, p.timestamp, p.approved
            ORDER BY p.timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        return cursor.fetchall()