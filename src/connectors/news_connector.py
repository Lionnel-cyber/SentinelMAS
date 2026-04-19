import json
import os

try:
    import feedparser
except ImportError:
    print("feedparser not installed. Installing...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'feedparser'])
    import feedparser

FEEDS = {
    'reuters': 'https://www.reuters.com/rssFeed/worldNews',
    'bbc': 'http://feeds.bbc.co.uk/news/world/rss.xml',
    'aljazeera': 'https://www.aljazeera.com/xml/rss/all.xml'
}

def fetch_news_articles():
    """Fetch disaster-related news from multiple sources"""

    articles = []

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)

            for entry in feed.entries:
                article = {
                    'source': source,
                    'title': entry.get('title'),
                    'link': entry.get('link'),
                    'published': entry.get('published'),
                    'summary': entry.get('summary', '')
                }
                articles.append(article)

        except Exception as e:
            print(f"Failed to parse {source}: {str(e)}")

    os.makedirs('data/raw', exist_ok=True)
    with open('data/raw/news_articles.json', 'w') as f:
        json.dump(articles, f, indent=2)

    return len(articles)

if __name__ == "__main__":
    count = fetch_news_articles()
    print(f"Fetched {count} news articles")
