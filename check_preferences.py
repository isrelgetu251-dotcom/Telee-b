#!/usr/bin/env python3
"""
Script to check notification preferences in the database
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = "C:\\Users\\sende\\Desktop\\modified_bot\\confessions.db"

def check_preferences():
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        return
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Check if the table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='notification_preferences'
            """)
            
            if not cursor.fetchone():
                print("notification_preferences table does not exist")
                return
            
            # Get all notification preferences
            cursor.execute("""
                SELECT user_id, favorite_categories, last_updated, 
                       comment_notifications, daily_digest, trending_alerts, digest_time
                FROM notification_preferences 
                ORDER BY last_updated DESC
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                print("No notification preferences found")
                return
            
            print("Notification Preferences:")
            print("-" * 80)
            print(f"{'User ID':<10} {'Favorites':<30} {'Last Updated':<20} {'Settings':<20}")
            print("-" * 80)
            
            for row in rows:
                user_id, favorites, last_updated, comments, digest, trending, digest_time = row
                settings = f"C:{comments} D:{digest} T:{trending} @{digest_time}"
                print(f"{user_id:<10} {favorites:<30} {last_updated:<20} {settings:<20}")
            
            print("-" * 80)
            print(f"Total records: {len(rows)}")
            
    except Exception as e:
        print(f"Error checking preferences: {e}")

if __name__ == "__main__":
    check_preferences()
