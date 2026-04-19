import os
import json
import sys

# Import individual connector modules
from . import usgs_connector, noaa_connector, firms_connector, gdacs_connector, news_connector, reliefweb_connector

def run_all_connectors():
    """Run all connectors and display summary"""

    print("=" * 60)
    print("Running all data connectors...")
    print("=" * 60)

    results = {}

    print("\n[1/7] EONET Events (from api/eonet.js)...")
    if os.path.exists('data/raw/eonet_events.json'):
        with open('data/raw/eonet_events.json', 'r') as f:
            eonet_data = json.load(f)
            results['eonet'] = len(eonet_data)
    else:
        print("  (EONET data not found - run: node api/eonet.js)")
        results['eonet'] = 0

    print("[2/7] USGS Earthquakes...")
    results['usgs'] = usgs_connector.fetch_usgs_earthquakes()

    print("[3/7] NOAA Alerts...")
    results['noaa'] = noaa_connector.fetch_noaa_alerts()

    print("[4/7] NASA FIRMS Fire Hotspots...")
    results['firms'] = firms_connector.fetch_nasa_firms()

    print("[5/7] GDACS Alerts...")
    results['gdacs'] = gdacs_connector.fetch_gdacs_alerts()

    print("[6/7] News Articles...")
    results['news'] = news_connector.fetch_news_articles()

    print("[7/7] ReliefWeb Updates...")
    results['reliefweb'] = reliefweb_connector.fetch_reliefweb()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total = 0
    for source, count in results.items():
        print(f"{source:15} {count:>7,} records")
        total += count

    print("-" * 60)
    print(f"{'TOTAL':15} {total:>7,} records")
    print("=" * 60)

    print("\nVerifying data files...")
    raw_dir = 'data/raw'
    expected_files = [
        'eonet_events.json',
        'usgs_earthquakes.json',
        'noaa_alerts.json',
        'nasa_firms.json',
        'gdacs_alerts.json',
        'news_articles.json',
        'reliefweb_updates.json'
    ]

    for filename in expected_files:
        filepath = os.path.join(raw_dir, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"[OK] {filename:30} {size:>10,} bytes")
        else:
            print(f"[NO] {filename:30} MISSING")

    print("\n[OK] All connectors completed successfully!")

if __name__ == "__main__":
    run_all_connectors()
