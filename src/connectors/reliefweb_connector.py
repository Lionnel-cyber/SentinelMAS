import json
import os

try:
    import feedparser
except ImportError:
    print("feedparser not installed. Installing...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'feedparser'])
    import feedparser

RELIEFWEB_FEED = "https://reliefweb.int/updates?format=feed"

def fetch_reliefweb():
    """Fetch ReliefWeb humanitarian updates"""

    updates = []
    try:
        feed = feedparser.parse(RELIEFWEB_FEED)

        for entry in feed.entries:
            update = {
                'title': entry.get('title'),
                'link': entry.get('link'),
                'published': entry.get('published'),
                'summary': entry.get('summary', '')
            }
            updates.append(update)

    except Exception as e:
        print(f"Error parsing ReliefWeb RSS: {str(e)}")

    os.makedirs('data/raw', exist_ok=True)
    with open('data/raw/reliefweb_updates.json', 'w') as f:
        json.dump(updates, f, indent=2)

    return len(updates)

if __name__ == "__main__":
    count = fetch_reliefweb()
    print(f"Fetched {count} ReliefWeb updates")
