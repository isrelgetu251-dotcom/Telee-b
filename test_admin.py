#!/usr/bin/env python3
"""
Admin command testing script
This script tests the new admin functions we implemented
"""

import sqlite3
from config import DB_PATH, ADMIN_IDS

def test_admin_functions():
    """Test all admin functions"""
    print("🧪 Testing Admin Functions")
    print("=" * 40)
    
    try:
        # Test database queries
        from moderation import get_reports, get_content_details
        from approval import block_user, unblock_user, is_blocked_user
        
        print("✅ Import test passed")
        
        # Test get_reports
        reports = get_reports()
        print(f"📊 Total reports in database: {len(reports)}")
        
        # Test with a sample user ID (use admin ID for testing)
        test_user_id = ADMIN_IDS[0] if ADMIN_IDS else 12345
        
        # Test blocking functions
        was_blocked = is_blocked_user(test_user_id)
        print(f"🔍 User {test_user_id} blocked status: {was_blocked}")
        
        # Check database structure
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            print(f"\n📋 Database tables: {', '.join(tables)}")
            
            # Check admin_messages table
            if 'admin_messages' in tables:
                cursor.execute("SELECT COUNT(*) FROM admin_messages")
                msg_count = cursor.fetchone()[0]
                print(f"📨 Admin messages: {msg_count}")
            
            # Check reports table  
            if 'reports' in tables:
                cursor.execute("SELECT COUNT(*) FROM reports")
                report_count = cursor.fetchone()[0]
                print(f"🚩 Reports: {report_count}")
        
        print("\n✅ All admin function tests passed!")
        
    except Exception as e:
        print(f"❌ Admin function test failed: {e}")
        import traceback
        traceback.print_exc()

def create_test_data():
    """Create some test data for testing purposes"""
    print("\n🗂️ Creating test data...")
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Add a test user if not exists
            test_user_id = 999999999
            cursor.execute("""
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, join_date, questions_asked, comments_posted, blocked)
                VALUES (?, ?, ?, ?, datetime('now'), 0, 0, 0)
            """, (test_user_id, "test_user", "Test", "User"))
            
            # Add a test confession
            cursor.execute("""
                INSERT OR IGNORE INTO posts 
                (content, category, timestamp, user_id, status)
                VALUES (?, ?, datetime('now'), ?, ?)
            """, ("This is a test confession for testing purposes.", "📚 Academics & University Life", test_user_id, "pending"))
            
            conn.commit()
            print("✅ Test data created successfully")
            
    except Exception as e:
        print(f"❌ Failed to create test data: {e}")

if __name__ == "__main__":
    test_admin_functions()
    create_test_data()
    
    print("\n" + "=" * 40)
    print("🎯 Ready for testing!")
    print("\nYou can now test the bot with:")
    print("1. Send /start to your bot on Telegram")
    print("2. Try submitting a confession")
    print("3. Test admin commands:")
    print("   - /admin (show admin help)")
    print("   - /stats (show statistics)")  
    print("   - /pending (show pending posts)")
    print("   - /reports (show reported content)")
    print("   - /users [user_id] (user management)")
    print("   - /blocked (show blocked users)")
    print("\n💡 Tip: Run 'python test_monitor.py' in another terminal")
    print("   to watch database activity in real-time!")
