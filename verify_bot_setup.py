#!/usr/bin/env python3
"""
Comprehensive Bot Setup Verification Script
This script checks if everything is properly configured and identifies issues
"""

import sys
import os
import importlib
from pathlib import Path

# Add the bot directory to Python path
bot_dir = Path(__file__).parent
sys.path.insert(0, str(bot_dir))

def check_dependencies():
    """Check if all required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    critical_packages = {
        'telegram': 'python-telegram-bot',
        'dotenv': 'python-dotenv', 
        'schedule': 'schedule'
    }
    
    optional_packages = {
        'pandas': 'pandas',
        'redis': 'redis',
        'nltk': 'nltk',
        'psutil': 'psutil'
    }
    
    missing_critical = []
    missing_optional = []
    
    for module, package in critical_packages.items():
        try:
            if module == 'telegram':
                import telegram.ext
            elif module == 'dotenv':
                from dotenv import load_dotenv
            else:
                __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            missing_critical.append(package)
            print(f"  ❌ {package} - CRITICAL")
    
    for module, package in optional_packages.items():
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            missing_optional.append(package)
            print(f"  ⚠️  {package} - optional")
    
    if missing_critical:
        print(f"\n❌ Missing critical packages: {', '.join(missing_critical)}")
        print("Run: pip install " + ' '.join(missing_critical))
        return False
    
    if missing_optional:
        print(f"\n⚠️  Missing optional packages: {', '.join(missing_optional)}")
        print("For full functionality, run: pip install " + ' '.join(missing_optional))
    
    print("✅ All critical dependencies are available!")
    return True

def check_configuration():
    """Check if configuration is valid"""
    print("\n🔍 Checking configuration...")
    
    try:
        from config import BOT_TOKEN, CHANNEL_ID, ADMIN_IDS, DB_PATH
        
        issues = []
        
        # Check bot token
        if not BOT_TOKEN or BOT_TOKEN.startswith("YOUR_") or len(BOT_TOKEN) < 40:
            issues.append("❌ BOT_TOKEN is not properly set")
        else:
            print(f"  ✅ Bot token: {BOT_TOKEN[:10]}...")
        
        # Check channel ID  
        if not CHANNEL_ID or CHANNEL_ID == 0:
            issues.append("❌ CHANNEL_ID is not set")
        else:
            print(f"  ✅ Channel ID: {CHANNEL_ID}")
        
        # Check admin IDs
        if not ADMIN_IDS or len(ADMIN_IDS) == 0:
            issues.append("❌ No admin IDs configured")
        else:
            print(f"  ✅ Admin IDs: {len(ADMIN_IDS)} admin(s)")
        
        # Check database path
        if not DB_PATH:
            issues.append("❌ DB_PATH is not set")
        else:
            print(f"  ✅ Database path: {DB_PATH}")
        
        if issues:
            for issue in issues:
                print(f"  {issue}")
            return False
        
        print("✅ Configuration looks good!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def check_core_modules():
    """Check if core modules can be imported"""
    print("\n🔍 Checking core modules...")
    
    core_modules = [
        'db', 'config', 'utils', 'submission', 'comments', 'approval', 
        'admin_messaging', 'stats', 'migrations', 'logger'
    ]
    
    failed_modules = []
    
    for module in core_modules:
        try:
            importlib.import_module(module)
            print(f"  ✅ {module}")
        except Exception as e:
            failed_modules.append((module, str(e)))
            print(f"  ❌ {module} - {e}")
    
    if failed_modules:
        print(f"\n❌ Failed to import {len(failed_modules)} modules:")
        for module, error in failed_modules:
            print(f"  {module}: {error}")
        return False
    
    print("✅ All core modules imported successfully!")
    return True

def check_database():
    """Check database setup and structure"""
    print("\n🔍 Checking database...")
    
    try:
        from db import init_db, get_db
        from config import DB_PATH
        import sqlite3
        
        # Check if database exists
        if not os.path.exists(DB_PATH):
            print("  ⚠️  Database doesn't exist, creating...")
            init_db()
        
        # Check database connection
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['users', 'posts', 'comments', 'reactions', 'reports', 'admin_messages']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                print(f"  ⚠️  Missing tables: {missing_tables}")
            else:
                print("  ✅ All required tables exist")
            
            # Check table structures
            for table in ['posts', 'comments', 'users']:
                if table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [row[1] for row in cursor.fetchall()]
                    
                    if table == 'posts' and 'approved' not in columns:
                        print(f"  ⚠️  posts table missing 'approved' column")
                    elif table == 'comments' and ('likes' not in columns or 'dislikes' not in columns):
                        print(f"  ⚠️  comments table missing like/dislike columns")
                    elif table == 'users' and 'username' not in columns:
                        print(f"  ⚠️  users table missing 'username' column")
                    else:
                        print(f"  ✅ {table} table structure OK")
        
        print("✅ Database check completed!")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def check_bot_syntax():
    """Check if bot.py has syntax errors"""
    print("\n🔍 Checking bot syntax...")
    
    try:
        with open('bot.py', 'r', encoding='utf-8') as f:
            bot_code = f.read()
        
        # Try to compile the bot code
        compile(bot_code, 'bot.py', 'exec')
        print("  ✅ bot.py syntax is valid")
        return True
        
    except SyntaxError as e:
        print(f"  ❌ Syntax error in bot.py: {e}")
        print(f"     Line {e.lineno}: {e.text}")
        return False
    except Exception as e:
        print(f"  ❌ Error checking bot.py: {e}")
        return False

def check_file_structure():
    """Check if all required files exist"""
    print("\n🔍 Checking file structure...")
    
    required_files = [
        'bot.py', 'config.py', 'db.py', 'utils.py', 'submission.py',
        'comments.py', 'approval.py', 'admin_messaging.py', 'stats.py',
        'logger.py', 'migrations.py', '.env'
    ]
    
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            missing_files.append(file)
            print(f"  ❌ {file} - MISSING")
    
    if missing_files:
        print(f"\n❌ Missing files: {', '.join(missing_files)}")
        return False
    
    print("✅ All required files exist!")
    return True

def main():
    """Main verification function"""
    print("🤖 University Confession Bot - Setup Verification")
    print("=" * 60)
    
    checks = [
        ("File Structure", check_file_structure),
        ("Dependencies", check_dependencies),
        ("Configuration", check_configuration),
        ("Core Modules", check_core_modules),
        ("Bot Syntax", check_bot_syntax),
        ("Database", check_database)
    ]
    
    passed = 0
    failed = 0
    
    for check_name, check_func in checks:
        print(f"\n{'='*20} {check_name} {'='*20}")
        try:
            if check_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Error in {check_name}: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL CHECKS PASSED!")
        print("🚀 Your bot is ready to run!")
        print("   Next steps:")
        print("   1. Run: python fix_database.py (if you haven't already)")
        print("   2. Run: python start_bot.py")
    else:
        print(f"\n⚠️  {failed} ISSUES FOUND!")
        print("🔧 Please fix the issues above before running the bot.")
        print("💡 Tips:")
        print("   - Check your .env file for correct configuration")
        print("   - Install missing packages with pip")
        print("   - Run python fix_database.py to fix database issues")
    
    print("=" * 60)
    return failed == 0

if __name__ == "__main__":
    success = main()
    input("\nPress Enter to exit...")
    sys.exit(0 if success else 1)
