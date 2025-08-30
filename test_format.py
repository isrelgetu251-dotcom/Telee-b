import sqlite3
from config import DB_PATH
from approval import get_post_by_id

# Test the most recent post data
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get the most recent post
cursor.execute('SELECT * FROM posts ORDER BY post_id DESC LIMIT 1')
post = cursor.fetchone()

if post:
    print("Most recent post data:")
    print(f"Full post tuple: {post}")
    print(f"Post ID: {post[0]}")
    print(f"User ID: {post[1]}")  
    print(f"Content: {post[2][:100]}...")
    print(f"Status: {post[3]}")
    print(f"Category: {post[4]}")
    print(f"Approved: {post[13]}")
    
    # Test how the channel message would look
    category = post[4]
    content = post[2]
    
    print("\n" + "="*50)
    print("CHANNEL MESSAGE PREVIEW:")
    print("="*50)
    print(f"*{category}*")
    print("")  # Empty line
    print(content)
    print("="*50)
else:
    print("No posts found")

conn.close()
