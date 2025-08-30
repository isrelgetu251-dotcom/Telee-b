#!/usr/bin/env python3
"""
Test monitoring script for University Confession Bot
This script helps monitor database activity during testing
"""

import sqlite3
import time
from datetime import datetime
from config import DB_PATH

def show_stats():
    """Show current database statistics"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get user count
            cursor.execute("SELECT COUNT(*) FROM users")
            users = cursor.fetchone()[0]
            
            # Get posts by status
            cursor.execute("SELECT COUNT(*) FROM posts WHERE status = 'pending' OR status IS NULL")
            pending_posts = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM posts WHERE status = 'approved'")
            approved_posts = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM posts WHERE status = 'rejected'")
            rejected_posts = cursor.fetchone()[0]
            
            # Get comments
            cursor.execute("SELECT COUNT(*) FROM comments")
            comments = cursor.fetchone()[0]
            
            # Get reports
            cursor.execute("SELECT COUNT(*) FROM reports")
            reports = cursor.fetchone()[0]
            
            # Get admin messages
            cursor.execute("SELECT COUNT(*) FROM admin_messages")
            admin_messages = cursor.fetchone()[0]
            
            print(f"\n📊 Database Status - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 50)
            print(f"👥 Total Users: {users}")
            print(f"📝 Posts:")
            print(f"   - Pending: {pending_posts}")
            print(f"   - Approved: {approved_posts}")  
            print(f"   - Rejected: {rejected_posts}")
            print(f"💬 Comments: {comments}")
            print(f"🚩 Reports: {reports}")
            print(f"📨 Admin Messages: {admin_messages}")
            print("=" * 50)
            
    except Exception as e:
        print(f"❌ Error reading database: {e}")

def show_recent_activity():
    """Show recent database activity"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            print(f"\n📈 Recent Activity:")
            print("-" * 30)
            
            # Recent users
            cursor.execute("SELECT user_id, first_name, join_date FROM users ORDER BY join_date DESC LIMIT 3")
            recent_users = cursor.fetchall()
            if recent_users:
                print("👤 Recent Users:")
                for user in recent_users:
                    user_id, name, join_date = user
                    print(f"   - {name or 'No name'} (ID: {user_id}) - {join_date[:16] if join_date else 'Unknown'}")
            
            # Recent posts
            cursor.execute("SELECT post_id, content, status, timestamp FROM posts ORDER BY timestamp DESC LIMIT 3")
            recent_posts = cursor.fetchall()
            if recent_posts:
                print("\n📝 Recent Posts:")
                for post in recent_posts:
                    post_id, content, status, timestamp = post
                    preview = content[:50] + "..." if len(content) > 50 else content
                    status_text = status if status else "pending"
                    print(f"   - #{post_id}: {preview} ({status_text}) - {timestamp[:16] if timestamp else 'Unknown'}")
            
            # Recent comments
            cursor.execute("SELECT comment_id, post_id, content, timestamp FROM comments ORDER BY timestamp DESC LIMIT 3")
            recent_comments = cursor.fetchall()
            if recent_comments:
                print("\n💬 Recent Comments:")
                for comment in recent_comments:
                    comment_id, post_id, content, timestamp = comment
                    preview = content[:40] + "..." if len(content) > 40 else content
                    print(f"   - #{comment_id} (Post #{post_id}): {preview} - {timestamp[:16] if timestamp else 'Unknown'}")
            
            print("-" * 30)
            
    except Exception as e:
        print(f"❌ Error reading recent activity: {e}")

def main():
    """Main monitoring function"""
    print("🔍 University Confession Bot - Test Monitor")
    print("Press Ctrl+C to exit")
    print("This will refresh every 10 seconds...")
    
    try:
        while True:
            show_stats()
            show_recent_activity()
            print(f"\n⏱️  Next update in 10 seconds... (Ctrl+C to exit)")
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped.")
    except Exception as e:
        print(f"❌ Monitor error: {e}")

if __name__ == "__main__":
    main()
