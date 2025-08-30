#!/usr/bin/env python3
"""
Quick test to verify bot.py syntax is fixed
"""

def test_syntax():
    """Test if bot.py can be compiled and imported"""
    try:
        # Test compilation
        print("🔍 Testing bot.py compilation...")
        with open('bot.py', 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        compile(source_code, 'bot.py', 'exec')
        print("✅ PASS: bot.py compiles without syntax errors!")
        
        # Test import
        print("🔍 Testing bot.py import...")
        import bot
        print("✅ PASS: bot.py imports successfully!")
        
        print("\n🎉 SUCCESS: All syntax issues are resolved!")
        print("🚀 Your bot is ready to run!")
        return True
        
    except SyntaxError as e:
        print(f"❌ FAIL: Syntax error still exists:")
        print(f"   Line {e.lineno}: {e.text}")
        print(f"   Error: {e.msg}")
        return False
        
    except Exception as e:
        print(f"❌ FAIL: Import error: {e}")
        return False

if __name__ == "__main__":
    if test_syntax():
        print("\n✅ Ready to test your bot features:")
        print("   1. Admin messaging")
        print("   2. Separate comments display")
        print("   3. Real-time reaction counts")
    else:
        print("\n❌ Please fix the errors above before running the bot.")