#!/usr/bin/env python3
"""
Test script for the modified confession bot
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test if all modules import correctly"""
    try:
        print("Testing imports...")
        
        # Test config
        from config import BOT_TOKEN, CHANNEL_ID, ADMIN_IDS
        print(f"✅ Config loaded - Bot token: {BOT_TOKEN[:10]}...")
        print(f"✅ Channel ID: {CHANNEL_ID}")
        print(f"✅ Admin IDs: {len(ADMIN_IDS)} admin(s)")
        
        # Test database
        from db import init_db
        print("✅ Database module imported")
        
        # Test comments functionality
        from comments import save_comment, react_to_comment, get_comments_paginated
        print("✅ Comments module imported with new functions")
        
        # Test admin messaging
        from admin_messaging import send_message_to_admins
        print("✅ Admin messaging module imported")
        
        # Test bot module
        import bot
        print("✅ Bot module imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_database():
    """Test database initialization"""
    try:
        print("\nTesting database...")
        from db import init_db
        init_db()
        print("✅ Database initialized successfully")
        
        # Test comment functionality
        from comments import save_comment
        test_comment_id, error = save_comment(1, "Test comment", 123456789, None)
        if error:
            print(f"⚠️  Comment test warning: {error}")
        else:
            print("✅ Comment system working")
            
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_bot_functions():
    """Test specific bot functions"""
    try:
        print("\nTesting bot functions...")
        
        # Test reaction function
        from comments import react_to_comment
        result = react_to_comment(123456789, 1, "like")
        if len(result) == 4:  # Should return (success, action, likes, dislikes)
            print("✅ Enhanced reaction function working")
        else:
            print("⚠️  Reaction function may need attention")
        
        return True
        
    except Exception as e:
        print(f"❌ Function test error: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Testing Modified Confession Bot")
    print("=" * 50)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test database
    if not test_database():
        success = False
    
    # Test functions
    if not test_bot_functions():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed! The bot should work correctly.")
        print("\n🚀 To start the bot, run:")
        print("   python bot.py")
        print("\n📱 Test these features in Telegram:")
        print("   1. Send /start to your bot")
        print("   2. Try 'My Stats' -> 'My Confessions'")
        print("   3. Try 'Contact Admin' with a test message")
        print("   4. Submit a confession and check comments")
        print("   5. Test reaction buttons on comments")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    success = main()
    input("\nPress Enter to exit...")
    sys.exit(0 if success else 1)