import requests
import json
import os

def fetch_noaa_alerts():
    """Fetch active NOAA alerts"""

    url = "https://api.weather.gov/alerts/active"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()
    except Exception as e:
        print(f"NOAA API unavailable ({str(e)}), using empty fallback")
        data = {'features': []}

    alerts = []
    for feature in data.get('features', []):
        props = feature.get('properties', {})

        alerts.append({
            'alert_id': props.get('id'),
            'event': props.get('event'),
            'headline': props.get('headline'),
            'description': props.get('description'),
            'areaDesc': props.get('areaDesc'),
            'severity': props.get('severity'),
            'effective': props.get('effective'),
            'expires': props.get('expires')
        })

    os.makedirs('data/raw', exist_ok=True)
    with open('data/raw/noaa_alerts.json', 'w') as f:
        json.dump(alerts, f, indent=2)

    return len(alerts)

if __name__ == "__main__":
    count = fetch_noaa_alerts()
    print(f"Fetched {count} NOAA alerts")
