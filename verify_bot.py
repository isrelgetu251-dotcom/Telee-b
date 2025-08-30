#!/usr/bin/env python3
"""
Verify bot.py syntax and functionality
"""

import sys
import os

def verify_bot():
    """Verify the bot can be imported and started"""
    try:
        print("🔍 Checking bot.py syntax...")
        
        # Try to compile the bot.py file
        with open('bot.py', 'r') as f:
            source = f.read()
        
        try:
            compile(source, 'bot.py', 'exec')
            print("✅ Bot.py syntax is correct!")
        except SyntaxError as e:
            print(f"❌ Syntax error in bot.py: {e}")
            print(f"   Line {e.lineno}: {e.text}")
            return False
        
        # Try to import the bot module
        try:
            import bot
            print("✅ Bot module imports successfully!")
        except Exception as e:
            print(f"❌ Import error: {e}")
            return False
        
        # Test configuration
        try:
            from config import BOT_TOKEN, ADMIN_IDS, CHANNEL_ID
            print(f"✅ Configuration loaded:")
            print(f"   - Bot token: {BOT_TOKEN[:10]}...")
            print(f"   - Admin IDs: {len(ADMIN_IDS)} configured")
            print(f"   - Channel ID: {CHANNEL_ID}")
        except Exception as e:
            print(f"❌ Configuration error: {e}")
            return False
        
        print("\n🎉 All checks passed! Bot is ready to run.")
        print("\n🚀 To start the bot, run:")
        print("   python start_bot.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    if verify_bot():
        print("\n✅ SUCCESS: Bot is ready!")
    else:
        print("\n❌ FAILED: Please fix the errors above.")
        sys.exit(1)