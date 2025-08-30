#!/usr/bin/env python3
"""Test script to manually approve a post for testing deep links"""

from submission import approve_post, get_post_by_id

# Test with post 71
post_id = 71
post = get_post_by_id(post_id)

if post:
    print(f"Post {post_id} found:")
    print(f"Content preview: {post[2][:100]}...")
    print(f"Category: {post[4]}")
    print(f"Current status: {post[6]}")
    
    # Approve the post (set channel_message_id to a test value)
    test_channel_message_id = 999  # This would normally be from the actual channel message
    approve_post(post_id, test_channel_message_id)
    
    # Check the updated status
    updated_post = get_post_by_id(post_id)
    print(f"Updated status: {updated_post[6]}")
    print("Post approved for testing!")
    
else:
    print(f"Post {post_id} not found")
