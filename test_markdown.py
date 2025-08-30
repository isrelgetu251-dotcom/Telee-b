from utils import escape_markdown_text, format_timestamp

# Test data from the first post
category = "🧠 Mental Health, 🤪 Weird"
content = "house is the difference in a paragraph like using a single payer coach John Edwards is a scalar analyst and a little bit more than a few years back and he try not that bad but still good at its butt don'ts telling him that he's going back home again"
timestamp = "2025-08-24 10:34:32"
post_id = 74
comment_count = 2

print("Testing MarkdownV2 formatting...")
print()

print("Original category:", repr(category))
print("Escaped category:", repr(escape_markdown_text(category)))
print()

print("Original content:", repr(content[:100]))
print("Escaped content:", repr(escape_markdown_text(content[:100])))
print()

print("Original timestamp:", repr(timestamp))
print("Formatted timestamp:", repr(format_timestamp(timestamp)))
print()

# Try to format the message like in the bot
try:
    confession_text = f"*{escape_markdown_text(category)}*\n\n{escape_markdown_text(content)}\n\n"
    confession_text += f"*\\#{post_id}* ✅ {escape_markdown_text('Approved')} \\| "
    confession_text += f"💬 {comment_count} comments \\| {escape_markdown_text(format_timestamp(timestamp))}"
    
    print("SUCCESS: Formatted message:")
    print(repr(confession_text))
    print()
    print("Actual message:")
    print(confession_text)
    
except Exception as e:
    print("ERROR:", e)
