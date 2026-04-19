import requests
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_nasa_firms():
    """Fetch active fire hotspots from NASA FIRMS"""

    url = "https://firms.modaps.eosdis.nasa.gov/api/area/json"

    fires = []
    try:
        logger.info("Fetching NASA FIRMS fire data...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        logger.info(f"FIRMS API returned {len(data.get('data', []))} fire points")

        for point in data.get('data', []):
            fires.append({
                'latitude': point.get('latitude'),
                'longitude': point.get('longitude'),
                'brightness': point.get('brightness'),
                'confidence': point.get('confidence'),
                'acq_date': point.get('acq_date')
            })

    except requests.exceptions.Timeout:
        logger.warning("FIRMS API timeout - using empty fallback")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.warning("FIRMS API authentication failed (no API key) - using empty fallback")
        elif e.response.status_code == 429:
            logger.warning("FIRMS API rate limit exceeded - using empty fallback")
        else:
            logger.warning(f"FIRMS API error {e.response.status_code} - using empty fallback")
    except Exception as e:
        logger.warning(f"FIRMS API failed ({type(e).__name__}: {str(e)}) - using empty fallback")

    os.makedirs('data/raw', exist_ok=True)
    with open('data/raw/nasa_firms.json', 'w') as f:
        json.dump({"data": fires}, f, indent=2)

    return len(fires)

if __name__ == "__main__":
    count = fetch_nasa_firms()
    print(f"Fetched {count} fire hotspots")
