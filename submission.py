import sqlite3
from config import DB_PATH

def save_submission(user_id, content, category):
    """Save a new submission to the database"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO posts (content, category, user_id) VALUES (?, ?, ?)",
                (content, category, user_id)
            )
            post_id = cursor.lastrowid
            
            # Update user stats
            cursor.execute(
                "UPDATE users SET questions_asked = questions_asked + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return post_id, None
    except Exception as e:
        return None, f"Database error: {str(e)}"

def get_pending_submissions():
    """Get all submissions pending approval"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE approved IS NULL ORDER BY timestamp DESC")
        return cursor.fetchall()

def get_recent_posts(limit=10):
    """Get recent approved posts with comment counts"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, 
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.approved = 1
            ORDER BY p.timestamp DESC
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

def get_post_by_id(post_id):
    """Get a specific post by ID with comment count"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, 
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.post_id = ?
        ''', (post_id,))
        return cursor.fetchone()

def get_todays_posts():
    """Get all approved posts from today"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.approved,
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.approved = 1 
            AND date(p.timestamp) = date('now')
            ORDER BY p.timestamp DESC
        ''', ())
        return cursor.fetchall()

def get_user_posts(user_id, limit=20):
    """Get user's confession history"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.approved,
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.user_id = ?
            ORDER BY p.timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        return cursor.fetchall()
