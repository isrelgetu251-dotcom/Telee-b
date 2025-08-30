import re
from config import SPAM_WORDS

def sanitize_content(text):
    """Sanitize and validate content"""
    if not text:
        return None
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Check for spam
    if is_spam(text):
        return None
    
    # Basic length check
    if len(text) < 10:
        return None
        
    return text

def is_spam(text):
    """Check if text contains spam keywords"""
    if not text:
        return False
    text_lower = text.lower()
    return any(spam_word in text_lower for spam_word in SPAM_WORDS)

def escape_markdown_text(text):
    """Escape text for MarkdownV2"""
    if not text:
        return ""
    # Convert to string if it's not already a string
    text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def truncate_text(text, max_length):
    """Truncate text to specified length"""
    if not text:
        return ""
    # Convert to string if it's not already a string
    text = str(text)
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def format_timestamp(timestamp_str):
    """Format timestamp for display"""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        formatted = dt.strftime('%Y-%m-%d %H:%M')
        # Escape markdown characters in the formatted timestamp
        return escape_markdown_text(formatted)
    except:
        return escape_markdown_text(str(timestamp_str))

def format_join_date(join_date_str):
    """Format join date for display"""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(join_date_str.replace('Z', '+00:00'))
        formatted = dt.strftime('%B %d, %Y')
        # Escape markdown characters in the formatted date
        return escape_markdown_text(formatted)
    except:
        return escape_markdown_text(str(join_date_str))

def extract_hashtags(text):
    """Extract hashtags from text content"""
    if not text:
        return []
    
    # Find hashtags - word characters after #, minimum 2 characters
    hashtags = re.findall(r'#(\w{2,})', text.lower())
    # Remove duplicates while preserving order
    seen = set()
    unique_hashtags = []
    for tag in hashtags:
        if tag not in seen:
            seen.add(tag)
            unique_hashtags.append(tag)
    
    return unique_hashtags

def format_hashtags(hashtags):
    """Format hashtags for display"""
    if not hashtags:
        return ""
    if isinstance(hashtags, str):
        hashtags = hashtags.split(',') if hashtags else []
    return " ".join([f"#{tag.strip()}" for tag in hashtags if tag.strip()])

def escape_hashtags(text):
    """Escape hashtags in text for MarkdownV2"""
    if not text:
        return text
    # Escape # in hashtags for MarkdownV2
    return re.sub(r'#(\w+)', r'\\#\1', text)

def format_time_ago(dt):
    """Format a datetime object to show time ago (e.g., '2h ago', '1d ago')"""
    from datetime import datetime, timezone
    
    # Make sure we're working with timezone-aware datetimes
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    diff = now - dt
    
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds // 60) % 60
    
    if days > 0:
        if days == 1:
            return "1 day ago"
        return f"{days} days ago"
    elif hours > 0:
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"
    elif minutes > 0:
        if minutes == 1:
            return "1 minute ago"
        return f"{minutes} minutes ago"
    else:
        return "just now"
