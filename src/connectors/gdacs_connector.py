import json
import os
from datetime import datetime

try:
    import feedparser
except ImportError:
    print("feedparser not installed. Installing...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'feedparser'])
    import feedparser

GDACS_FEED = "https://www.gdacs.org/xml/rss.xml"

def fetch_gdacs_alerts():
    """Parse GDACS RSS for disaster alerts"""

    alerts = []
    try:
        feed = feedparser.parse(GDACS_FEED)

        for entry in feed.entries:
            alert = {
                'title': entry.get('title'),
                'link': entry.get('link'),
                'published': entry.get('published'),
                'summary': entry.get('summary'),
                'category': entry.get('tags', [{}])[0].get('term') if entry.get('tags') else None,
                'parsed_at': datetime.utcnow().isoformat()
            }
            alerts.append(alert)

    except Exception as e:
        print(f"Error parsing GDACS RSS: {str(e)}")

    os.makedirs('data/raw', exist_ok=True)
    with open('data/raw/gdacs_alerts.json', 'w') as f:
        json.dump(alerts, f, indent=2)

    return len(alerts)

if __name__ == "__main__":
    count = fetch_gdacs_alerts()
    print(f"Fetched {count} GDACS alerts")
