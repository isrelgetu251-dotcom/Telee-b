import sqlite3
from submission import get_user_posts

# Test with a known user ID
test_user_id = 1298849354  # User ID from previous logs

print(f"Testing get_user_posts for user {test_user_id}")
posts = get_user_posts(test_user_id, 10)

print(f"Number of posts returned: {len(posts) if posts else 0}")

if posts:
    print("\nPost data:")
    for i, post in enumerate(posts):
        print(f"Post {i+1}: {post}")
        print(f"  - post_id: {post[0]}")
        print(f"  - content: {post[1][:50]}...")
        print(f"  - category: {post[2]}")
        print(f"  - timestamp: {post[3]}")
        print(f"  - approved: {post[4]}")
        print(f"  - comment_count: {post[5]}")
        print()
else:
    print("No posts found!")

# Let's also check raw database
print("\nDirect database check:")
with sqlite3.connect('confessions.db') as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT post_id, user_id, content, category, approved FROM posts WHERE user_id = ? LIMIT 5', (test_user_id,))
    raw_posts = cursor.fetchall()
    
    print(f"Raw posts from database: {len(raw_posts)}")
    for post in raw_posts:
        print(f"Post ID {post[0]}: User {post[1]}, Approved: {post[4]}, Category: {post[3]}")
