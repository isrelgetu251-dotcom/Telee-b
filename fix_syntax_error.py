#!/usr/bin/env python3
"""
Fix the specific indentation error in bot.py at line 757
"""

def fix_indentation_error():
    """Fix the indentation error by removing orphaned code"""
    try:
        # Read the file
        with open('bot.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Define the problematic block that needs to be removed
        problematic_block = '''
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        logger.error(f"Error updating comments view: {e}")
        # If the message is too long, try sending a simplified version
        if "too long" in str(e).lower():
            short_text = f"💬 *Comments \\({total_comments} total\\)*\\n*Page {current_page} of {total_pages}*\\n\\n"
            short_text += "Comments loaded but too many to display fully.\\nPlease navigate through pages to see all content."
            await query.edit_message_text(
                short_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
        else:
            await query.edit_message_text(
                "❗ An error occurred while displaying comments. Please try again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"view_post_{post_id}")]])
            )
'''
        
        # Remove the problematic block
        new_content = content.replace(problematic_block, '')
        
        # Write the fixed content back
        with open('bot.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ Fixed indentation error in bot.py")
        
        # Verify the fix by trying to compile
        try:
            compile(new_content, 'bot.py', 'exec')
            print("✅ Syntax verification passed!")
            return True
        except SyntaxError as e:
            print(f"❌ Syntax error still exists: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Error fixing file: {e}")
        return False

if __name__ == "__main__":
    if fix_indentation_error():
        print("\n🎉 SUCCESS: bot.py is now syntax-error free!")
        print("🚀 You can now run: python start_bot.py")
    else:
        print("\n❌ FAILED: Please check the file manually.")