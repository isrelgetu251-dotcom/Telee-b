import sqlite3

conn = sqlite3.connect('confessions.db')
cursor = conn.cursor()

# Check posts table structure
cursor.execute('PRAGMA table_info(posts)')
print('Posts table structure:')
for row in cursor.fetchall():
    print(f"Column {row[0]}: {row[1]} ({row[2]})")

print('\nSample posts:')
cursor.execute('SELECT post_id, content, category, user_id, approved FROM posts ORDER BY post_id DESC LIMIT 3')
for row in cursor.fetchall():
    print(f'ID: {row[0]}, Content: {row[1][:50]}..., Category: {row[2]}, User: {row[3]}, Approved: {row[4]}')

print('\nFull post data for last approved post:')
cursor.execute('SELECT * FROM posts WHERE approved = 1 ORDER BY post_id DESC LIMIT 1')
result = cursor.fetchone()
if result:
    print(f"Full post data: {result}")
    print(f"Category field (index 4): {result[4]}")
else:
    print("No approved posts found")

conn.close()
