import requests
import json
from datetime import datetime, timedelta
import os

def fetch_usgs_earthquakes():
    """Fetch recent significant earthquakes"""

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        'format': 'geojson',
        'minmagnitude': 4.5,
        'starttime': start_date.isoformat(),
        'endtime': end_date.isoformat(),
        'limit': 10000
    }

    response = requests.get(url, params=params, timeout=10)
    data = response.json()

    earthquakes = []
    for feature in data['features']:
        props = feature['properties']
        coords = feature['geometry']['coordinates']

        earthquakes.append({
            'event_id': feature['id'],
            'magnitude': props['mag'],
            'latitude': coords[1],
            'longitude': coords[0],
            'depth_km': coords[2],
            'place': props['place'],
            'time': props['time'],
            'url': props['url']
        })

    os.makedirs('data/raw', exist_ok=True)
    with open('data/raw/usgs_earthquakes.json', 'w') as f:
        json.dump(earthquakes, f, indent=2)

    return len(earthquakes)

if __name__ == "__main__":
    count = fetch_usgs_earthquakes()
    print(f"Fetched {count} earthquakes")
