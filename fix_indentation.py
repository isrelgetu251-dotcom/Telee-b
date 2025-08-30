#!/usr/bin/env python3
"""
Fix indentation error in bot.py
"""

def fix_bot_py():
    """Fix the indentation error in bot.py"""
    try:
        # Read the file
        with open('bot.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find and remove problematic lines
        new_lines = []
        skip_block = False
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Start skipping at the problematic block
            if line_num == 755 and 'reply_markup=reply_markup,' in line:
                skip_block = True
                continue
            
            # Stop skipping when we reach the next function
            if skip_block and line.strip().startswith('async def add_comment_callback'):
                skip_block = False
                new_lines.append(line)
                continue
            
            # Skip lines in the problematic block
            if skip_block:
                continue
            
            new_lines.append(line)
        
        # Write the fixed file
        with open('bot.py', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print("✅ Fixed indentation error in bot.py")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing bot.py: {e}")
        return False

if __name__ == "__main__":
    fix_bot_py()