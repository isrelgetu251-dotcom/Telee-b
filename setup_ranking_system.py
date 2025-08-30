"""
Setup script for the User Ranking System
Run this to install and configure the ranking system in your bot
"""

import sys
import os

def setup_ranking_system():
    """Main setup function"""
    print("🏆 Setting up User Ranking System...")
    
    try:
        # Step 1: Run database migration
        print("\n📊 Setting up database tables...")
        from ranking_migration import run_ranking_migration
        
        if run_ranking_migration():
            print("✅ Database tables created successfully!")
        else:
            print("❌ Database migration failed!")
            return False
        
        # Step 2: Test ranking system
        print("\n🔄 Testing ranking system...")
        from ranking_system import ranking_manager
        
        # Test with a dummy user
        test_user_id = 999999999
        ranking_manager.initialize_user_ranking(test_user_id)
        
        # Award test points
        success, points = ranking_manager.award_points(
            test_user_id, 
            'confession_submitted',
            description="Test points"
        )
        
        if success:
            print(f"✅ Ranking system test passed! Awarded {points} points")
            
            # Get user rank
            user_rank = ranking_manager.get_user_rank(test_user_id)
            if user_rank:
                print(f"✅ User rank retrieved: {user_rank.rank_name}")
            else:
                print("❌ Failed to retrieve user rank")
                return False
        else:
            print("❌ Ranking system test failed!")
            return False
            
        # Step 3: Clean up test data
        import sqlite3
        from config import DB_PATH
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_rankings WHERE user_id = ?", (test_user_id,))
            cursor.execute("DELETE FROM point_transactions WHERE user_id = ?", (test_user_id,))
            conn.commit()
        
        print("🧹 Test data cleaned up")
        
        # Step 4: Show integration instructions
        print("\n" + "="*50)
        print("🎉 RANKING SYSTEM SETUP COMPLETE!")
        print("="*50)
        
        show_integration_instructions()
        
        return True
        
    except Exception as e:
        print(f"❌ Setup failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_integration_instructions():
    """Show instructions for integrating with the existing bot"""
    
    instructions = """
🔧 INTEGRATION INSTRUCTIONS

To fully integrate the ranking system with your existing bot:

1. 📝 UPDATE MAIN BOT FILE (bot.py):
   
   Add these imports at the top:
   ```python
   from ranking_ui import ranking_callback_handler, show_ranking_menu
   from ranking_integration import (
       award_points_for_confession_submission,
       award_points_for_confession_approval, 
       award_points_for_comment,
       award_points_for_reaction_given,
       award_points_for_reaction_received
   )
   ```

2. 🎛️ UPDATE MAIN MENU:
   
   Change your MAIN_MENU in bot.py to:
   ```python
   MAIN_MENU = [
       ["🙊 Confess/Ask Question", "📰 View Recent Confessions"],
       ["🏆 My Rank", "📊 My Stats"], 
       ["📅 Daily Digest", "📞 Contact Admin"],
       ["❓ Help/About"]
   ]
   ```

3. 🔄 ADD CALLBACK HANDLERS:
   
   In your application setup, add:
   ```python
   application.add_handler(CallbackQueryHandler(ranking_callback_handler, pattern=r"^(rank_|leaderboard_)"))
   ```

4. 📍 INTEGRATE POINT AWARDS:
   
   In your existing functions, add these calls:
   
   📝 In confession submission handler:
   ```python
   await award_points_for_confession_submission(user_id, post_id, category, context)
   ```
   
   ✅ In confession approval handler:
   ```python  
   await award_points_for_confession_approval(user_id, post_id, admin_id, context)
   ```
   
   💬 In comment posting handler:
   ```python
   await award_points_for_comment(user_id, post_id, comment_id, content, context)
   ```
   
   👍 In reaction handlers:
   ```python
   # When someone gives a reaction
   await award_points_for_reaction_given(user_id, target_id, target_type, reaction_type)
   
   # When someone receives a reaction  
   await award_points_for_reaction_received(owner_id, target_id, target_type, reaction_type, context)
   ```

5. 🎯 UPDATE MENU HANDLER:
   
   In your handle_menu_choice function, add:
   ```python
   elif text == "🏆 My Rank":
       await show_ranking_menu(update, context)
   ```

6. 🗄️ BACKUP YOUR DATABASE:
   
   Before going live, backup your existing database:
   ```bash
   cp confessions.db confessions.db.backup
   ```

📊 FEATURES INCLUDED:

✅ 12 Rank Levels (New Confessor → Confession Sage)
✅ Point System (20+ different activities)  
✅ Achievement System (15+ achievements)
✅ Anonymous Leaderboards (Weekly/Monthly/All-time)
✅ Progress Tracking & Statistics
✅ Rank-up Notifications
✅ Special Perks for Higher Ranks
✅ Comprehensive UI with Inline Keyboards

🎮 RANK PROGRESSION:

🆕 New Confessor (0 pts) → 🌱 First Timer (50 pts) → 📝 Regular (150 pts) 
→ ⚡ Active Member (300 pts) → 🤝 Community Helper (500 pts) 
→ 🌟 Trusted Confessor (750 pts) → 🏆 Veteran (1200 pts)
→ 💎 Elite Confessor (2000 pts) → 👑 Community Legend (3500 pts)
→ 📚 Master Storyteller (5000 pts) → 🛡️ Community Guardian (7500 pts)
→ 🧙‍♂️ Confession Sage (10000 pts)

🎁 SPECIAL PERKS:
• Higher daily confession limits
• Priority review for submissions  
• Comment highlighting
• Featured post chances
• Custom emoji reactions
• Legend badges
• And much more!

🚀 READY TO LAUNCH!

Your ranking system is now ready! Users will start earning points immediately 
once integrated. The system tracks everything automatically and provides 
rich analytics and engagement features.

Need help? Check the individual files for detailed documentation.
"""
    
    print(instructions)

def show_example_integration():
    """Show example of how to integrate with existing code"""
    
    example = '''
📝 EXAMPLE INTEGRATION:

Here's how to modify your existing approval.py file:

```python
# In approval.py, modify the admin_callback function:

from ranking_integration import award_points_for_confession_approval

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin approval/rejection callbacks"""
    query = update.callback_query
    await query.answer()
    data = query.data
    admin_id = update.effective_user.id

    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❗ You are not authorized to moderate.")
        return

    if data.startswith("approve_"):
        post_id = int(data.split("_")[1])
        post = get_post_by_id(post_id)
        if not post:
            await query.edit_message_text("❗ Post not found.")
            return
        
        # Extract data from post tuple
        content = post[2]
        category = post[4] 
        submitter_id = post[1]
        
        try:
            # ... existing approval code ...
            
            approve_post(post_id, msg.message_id)
            await query.edit_message_text("✅ Approved and posted to channel.")
            
            # 🆕 ADD THIS: Award points for approval
            await award_points_for_confession_approval(
                submitter_id, post_id, admin_id, context
            )
            
            # ... rest of existing code ...
```

That's it! The ranking system will automatically:
✅ Award 25 points for approved confession
✅ Check for rank ups and notify user
✅ Award daily login bonus
✅ Track achievements
✅ Update leaderboards
'''
    
    print(example)

if __name__ == "__main__":
    print("🏆 User Ranking System Setup")
    print("=" * 40)
    
    # Run setup
    success = setup_ranking_system()
    
    if success:
        print("\n🎊 Setup completed successfully!")
        print("Follow the integration instructions above to activate the ranking system.")
        
        # Ask if they want to see example
        try:
            show_example = input("\n❓ Would you like to see integration examples? (y/n): ").lower().strip()
            if show_example in ['y', 'yes']:
                show_example_integration()
        except:
            pass  # In case input doesn't work in some environments
            
    else:
        print("\n❌ Setup failed! Please check the error messages above.")
        sys.exit(1)
