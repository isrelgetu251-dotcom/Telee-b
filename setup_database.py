"""
Database setup script for the Enhanced Telegram Confession Bot
Run this script to initialize the database with proper schema
"""

from db import init_db
from config import DB_PATH

def main():
    """Initialize the database"""
    print("Setting up database...")
    init_db()
    print(f"Database initialized successfully at {DB_PATH}")
    print("\nTables created:")
    print("- users: Store user information and stats with join dates")
    print("- posts: Store confession submissions")
    print("- comments: Store comments and replies with like/dislike counts")
    print("- reactions: Store like/dislike data with unique constraints")
    print("- reports: Store abuse reports")
    print("- admin_messages: Store admin-user communications")
    print("\nDatabase setup complete!")
    print("\nNext steps:")
    print("1. Update your BOT_TOKEN in config.py")
    print("2. Add your admin user IDs to ADMIN_IDS in config.py")
    print("3. Set your CHANNEL_ID in config.py")
    print("4. Run: python main.py")

if __name__ == "__main__":
    main()