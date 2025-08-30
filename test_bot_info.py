#!/usr/bin/env python3
"""Test script to verify bot information"""

import asyncio
from telegram import Bot
from config import BOT_TOKEN

async def test_bot_info():
    bot = Bot(BOT_TOKEN)
    try:
        me = await bot.get_me()
        print(f"Bot ID: {me.id}")
        print(f"Bot username: @{me.username}")
        print(f"Bot first name: {me.first_name}")
        print(f"Bot can join groups: {me.can_join_groups}")
        print(f"Bot can read all group messages: {me.can_read_all_group_messages}")
        print(f"Bot supports inline queries: {me.supports_inline_queries}")
        
        # Test deep link URL format
        test_url = f"https://t.me/{me.username}?start=comment_71"
        print(f"\nTest deep link URL: {test_url}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_bot_info())
