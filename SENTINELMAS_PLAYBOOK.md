# SentinelMAS Playbook

Exact steps to ship v0.1 in one week.

---

## MONDAY: Fork + Connectors (12-15 hours)

### Setup (10 mins)
```bash
# Fork World Monitor
https://github.com/koala73/worldmonitor → Fork to Lionnel-cyber/SentinelMAS

# Clone your fork
git clone https://github.com/Lionnel-cyber/SentinelMAS.git
cd SentinelMAS

# Create feature branch
git checkout -b feat/add-disaster-connectors
```

### EONET Connector (30 mins)
**File:** `src/connectors/eonet_connector.py`

```python
import requests
import json
from datetime import datetime

def fetch_eonet_events():
    """Fetch from NASA EONET v3 (no API key needed)"""
    url = "https://eonet.gsfc.nasa.gov/api/v3/events"
    response = requests.get(url)
    events = response.json()['events']
    
    # Save to data/raw/eonet_events.json
    with open('data/raw/eonet_events.json', 'w') as f:
        json.dump(events, f, indent=2)
    
    print(f"Fetched {len(events)} EONET events")
    return events

if __name__ == "__main__":
    fetch_eonet_events()
```

**Test:**
```bash
python -m src.connectors.eonet_connector
# Output: "Fetched N EONET events"
```

### USGS Earthquake Connector (30 mins)
**File:** `src/connectors/usgs_connector.py`

```python
import requests
import json

def fetch_usgs_earthquakes():
    """USGS Earthquake API (M4.5+, 30 days)"""
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        'format': 'geojson',
        'minmagnitude': 4.5,
        'starttime': '2026-03-19',
        'endtime': '2026-04-18'
    }
    response = requests.get(url, params=params)
    earthquakes = response.json()
    
    with open('data/raw/usgs_earthquakes.json', 'w') as f:
        json.dump(earthquakes, f, indent=2)
    
    print(f"Fetched {len(earthquakes['features'])} earthquakes")
    return earthquakes

if __name__ == "__main__":
    fetch_usgs_earthquakes()
```

### NOAA Flood Connector (30 mins)
**File:** `src/connectors/noaa_connector.py`

```python
import requests
import json

def fetch_noaa_alerts():
    """NOAA alerts API (floods, storms, etc.)"""
    url = "https://api.weather.gov/alerts/active"
    params = {'area': 'US'}
    response = requests.get(url)
    alerts = response.json()
    
    with open('data/raw/noaa_alerts.json', 'w') as f:
        json.dump(alerts, f, indent=2)
    
    print(f"Fetched {len(alerts.get('features', []))} NOAA alerts")
    return alerts

if __name__ == "__main__":
    fetch_noaa_alerts()
```

### NASA FIRMS Fire Connector (30 mins)
**File:** `src/connectors/firms_connector.py`

```python
import requests
import json
from datetime import datetime, timedelta

def fetch_nasa_firms_fires():
    """NASA FIRMS active fire boundaries (24h)"""
    # FIRMS data via GIBS (Imagery for Geospatial Data)
    # Simplified: fetch GeoJSON from public endpoint
    url = "https://firms.modaps.eosdis.nasa.gov/api/area/json"
    
    # For demo, use simple bounding box (world)
    params = {
        'source': 'VIIRS_NOAA20_NRT',
        'day_range': 1
    }
    
    # Note: FIRMS has rate limits, fallback to cached data if needed
    try:
        response = requests.get(url, params=params, timeout=5)
        fires = response.json()
    except:
        fires = {'data': []}
    
    with open('data/raw/nasa_firms.json', 'w') as f:
        json.dump(fires, f, indent=2)
    
    print(f"Fetched FIRMS fire data")
    return fires

if __name__ == "__main__":
    fetch_nasa_firms_fires()
```

### GDACS RSS Connector (30 mins)
**File:** `src/connectors/gdacs_connector.py`

```python
import feedparser
import json
from datetime import datetime

def fetch_gdacs_alerts():
    """UN GDACS disaster alerts RSS"""
    url = "https://www.gdacs.org/xml/rss.xml"
    feed = feedparser.parse(url)
    
    alerts = []
    for entry in feed.entries:
        alert = {
            'title': entry.title,
            'link': entry.link,
            'published': entry.published,
            'summary': entry.summary,
            'category': entry.get('category', '')
        }
        alerts.append(alert)
    
    with open('data/raw/gdacs_alerts.json', 'w') as f:
        json.dump(alerts, f, indent=2)
    
    print(f"Fetched {len(alerts)} GDACS alerts")
    return alerts

if __name__ == "__main__":
    fetch_gdacs_alerts()
```

### Reuters/BBC News RSS Connector (30 mins)
**File:** `src/connectors/news_connector.py`

```python
import feedparser
import json

def fetch_news_feeds():
    """Reuters, BBC, Al Jazeera disaster news"""
    feeds = {
        'reuters': 'https://www.reutersagency.com/feed/?taxonomy=all&sort=relevance',
        'bbc': 'http://feeds.bbc.co.uk/news/world/rss.xml',
        'aljazeera': 'https://www.aljazeera.com/xml/rss/all.xml'
    }
    
    all_articles = []
    for source, url in feeds.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            article = {
                'source': source,
                'title': entry.title,
                'link': entry.link,
                'published': entry.published,
                'summary': entry.get('summary', '')
            }
            all_articles.append(article)
    
    with open('data/raw/news_articles.json', 'w') as f:
        json.dump(all_articles, f, indent=2)
    
    print(f"Fetched {len(all_articles)} articles")
    return all_articles

if __name__ == "__main__":
    fetch_news_feeds()
```

### ReliefWeb RSS Connector (30 mins)
**File:** `src/connectors/reliefweb_connector.py`

```python
import feedparser
import json

def fetch_reliefweb_updates():
    """ReliefWeb humanitarian response status"""
    url = "https://reliefweb.int/updates?format=feed"
    feed = feedparser.parse(url)
    
    updates = []
    for entry in feed.entries:
        update = {
            'title': entry.title,
            'link': entry.link,
            'published': entry.published,
            'summary': entry.get('summary', '')
        }
        updates.append(update)
    
    with open('data/raw/reliefweb_updates.json', 'w') as f:
        json.dump(updates, f, indent=2)
    
    print(f"Fetched {len(updates)} ReliefWeb updates")
    return updates

if __name__ == "__main__":
    fetch_reliefweb_updates()
```

### Test all 6 connectors
```bash
python -m src.connectors.eonet_connector
python -m src.connectors.usgs_connector
python -m src.connectors.noaa_connector
python -m src.connectors.firms_connector
python -m src.connectors.gdacs_connector
python -m src.connectors.news_connector
python -m src.connectors.reliefweb_connector

# Verify data/raw/ has 7 JSON files
ls -lh data/raw/
```

### Commit
```bash
git add src/connectors/
git commit -m "feat: Add 6 disaster data connectors (EONET, USGS, NOAA, FIRMS, GDACS, News, ReliefWeb)"
git push origin feat/add-disaster-connectors
```

---

## TUESDAY: Wire to Globe + First Agents (12 hours)

### Create dbt models
**File:** `src/transforms/models/stg_eonet_events.sql`

```sql
SELECT
  event_id,
  title,
  categories[0] AS disaster_type,
  geometry.coordinates[0] AS longitude,
  geometry.coordinates[1] AS latitude,
  dates.start AS event_start,
  dates.end AS event_end,
  sources,
  _loaded_at
FROM {{ source('raw', 'eonet_events') }}
WHERE _loaded_at > NOW() - INTERVAL 24 HOUR
```

**File:** `src/transforms/models/int_compound_risks.sql`

```sql
WITH events AS (
  SELECT * FROM {{ ref('stg_eonet_events') }}
  UNION ALL
  SELECT * FROM {{ ref('stg_usgs_earthquakes') }}
  -- etc. for all 6 sources
)
SELECT
  event_id,
  disaster_type,
  latitude,
  longitude,
  -- Compound risk detection logic will go here
  CASE
    WHEN disaster_type = 'earthquakes' AND 
         EXISTS(SELECT 1 FROM events e2 
                WHERE e2.disaster_type = 'floods' 
                AND e2.latitude BETWEEN latitude - 2 AND latitude + 2
                AND e2._loaded_at > NOW() - INTERVAL 48 HOUR)
    THEN 1.8  -- Earthquake + flood amplifier
    ELSE 1.0
  END AS compound_amplifier
FROM events
```

### Wire to Globe (deck.gl)
**File:** `frontend/components/DisasterGlobe.tsx`

```tsx
import { GlobeView } from '@deck.gl/core'
import { ScatterplotLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'

export function DisasterGlobe({ events }) {
  const layers = [
    new ScatterplotLayer({
      id: 'disaster-events',
      data: events,
      getPosition: d => [d.longitude, d.latitude],
      getRadius: d => 50000 * (d.severity_score / 100),
      getColor: d => ({
        'earthquake': [255, 0, 0],
        'flood': [0, 100, 255],
        'fire': [255, 165, 0],
        'storm': [128, 128, 128]
      }[d.disaster_type] || [255, 255, 255]),
      pickable: true,
      onHover: d => console.log(d),
      onClick: d => console.log('Clicked:', d)
    })
  ]
  
  return (
    <DeckGL
      views={new GlobeView()}
      layers={layers}
      initialViewState={{
        longitude: 0,
        latitude: 0,
        zoom: 1,
        pitch: 40,
        bearing: 0
      }}
      controller={true}
    />
  )
}
```

### Test: Render EONET events on globe
```bash
# Ensure data/raw/eonet_events.json is populated
# Start frontend, see dots on 3D globe
npm run dev
```

### FloodAgent (First Agent)
**File:** `src/agents/flood_agent.py`

```python
from crewai import Agent, Task
from langchain.llms import Anthropic

def create_flood_agent(api_key: str):
    flood_agent = Agent(
        role="Flood Risk Analyst",
        goal="Assess flood severity and cascade risks",
        backstory="Expert in hydrology, rainfall, dam systems, and flood propagation",
        tools=[],  # Add tools later
        llm=Anthropic(api_key=api_key, model="claude-haiku-4-5"),
    )
    return flood_agent

def score_flood_event(agent, event_data: dict) -> dict:
    """Score a flood event 0-100"""
    task = Task(
        description=f"""
        Analyze flood event:
        Location: {event_data['location']}
        Rainfall: {event_data['rainfall_mm']}
        Area: {event_data['area_km2']}
        Population at risk: {event_data['population']}
        
        Return JSON:
        {{
          "severity_score": 0-100,
          "confidence": "high/medium/low",
          "reasoning": "Brief explanation"
        }}
        """,
        agent=agent,
        expected_output="JSON with severity_score, confidence, reasoning"
    )
    result = task.execute()
    return result
```

### EarthquakeAgent
**File:** `src/agents/earthquake_agent.py`

```python
from crewai import Agent, Task

def create_earthquake_agent(api_key: str):
    eq_agent = Agent(
        role="Seismic Risk Analyst",
        goal="Assess earthquake severity and aftershock cascades",
        backstory="Expert in seismology, magnitude, depth, and fault lines",
        tools=[],
        llm=Anthropic(api_key=api_key, model="claude-haiku-4-5"),
    )
    return eq_agent

def score_earthquake_event(agent, event_data: dict) -> dict:
    """Score earthquake event 0-100"""
    task = Task(
        description=f"""
        Analyze earthquake:
        Magnitude: {event_data['magnitude']}
        Depth: {event_data['depth_km']}
        Location: {event_data['location']}
        Population at risk: {event_data['population']}
        Aftershock probability: {event_data['aftershock_prob']}
        
        Return JSON with severity_score, confidence, reasoning
        """,
        agent=agent,
        expected_output="JSON"
    )
    result = task.execute()
    return result
```

### WildfireAgent
**File:** `src/agents/wildfire_agent.py`

```python
from crewai import Agent, Task

def create_wildfire_agent(api_key: str):
    fire_agent = Agent(
        role="Wildfire Risk Analyst",
        goal="Assess wildfire severity and containment status",
        backstory="Expert in fuel loads, weather patterns, and fire propagation",
        tools=[],
        llm=Anthropic(api_key=api_key, model="claude-haiku-4-5"),
    )
    return fire_agent
```

### Test Agents
```bash
python -c "
from src.agents.flood_agent import create_flood_agent, score_flood_event
import os

agent = create_flood_agent(os.getenv('ANTHROPIC_API_KEY'))
result = score_flood_event(agent, {
    'location': 'Jakarta, Indonesia',
    'rainfall_mm': 450,
    'area_km2': 2500,
    'population': 10000000
})
print(result)
"
```

### Commit
```bash
git add src/agents/ frontend/components/DisasterGlobe.tsx src/transforms/models/
git commit -m "feat: Wire data to globe, add FloodAgent, EarthquakeAgent, WildfireAgent"
git push origin feat/add-disaster-connectors
```

---

## WEDNESDAY: Compound Detection + Streaming (10 hours)

### CompoundEventDetector
**File:** `src/detectors/compound_detector.py`

```python
def detect_compound_risks(events: list[dict]) -> list[dict]:
    """Detect when 2+ disasters interact"""
    
    compound_risks = []
    
    for i, event1 in enumerate(events):
        for event2 in events[i+1:]:
            # Check if overlapping in space + time
            if overlaps(event1, event2):
                amplifier = get_amplifier(event1['type'], event2['type'])
                compound = {
                    'events': [event1['id'], event2['id']],
                    'amplifier': amplifier,
                    'compound_score': min(
                        event1['score'] * event2['score'] / 50 * amplifier,
                        100
                    ),
                    'cascade_probability': calculate_cascade(event1, event2)
                }
                compound_risks.append(compound)
    
    return compound_risks

def get_amplifier(type1: str, type2: str) -> float:
    """Return risk amplifier for disaster pairs"""
    amplifiers = {
        ('earthquake', 'flood'): 1.8,
        ('drought', 'wildfire'): 2.1,
        ('storm', 'flood'): 1.6,
        ('earthquake', 'landslide'): 1.9,
        ('volcano', 'storm'): 2.3,
    }
    key = tuple(sorted([type1, type2]))
    return amplifiers.get(key, 1.0)
```

### Streaming Briefing Endpoint
**File:** `src/api/routes/briefing.py`

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from src.agents.briefer import create_briefer_agent
import asyncio

router = APIRouter()

@router.get("/api/v1/briefing/{event_id}/stream")
async def stream_briefing(event_id: str):
    """Stream disaster briefing using Opus advisor + Haiku executor"""
    
    async def generate():
        # Get event + all agent reasoning
        event = get_event(event_id)
        
        # Call Opus advisor for plan
        prompt = f"""
        Summarize this disaster for emergency coordinator:
        {event['type']}: {event['location']}
        Severity: {event['severity']}/100
        Population at risk: {event['population']}
        Agent reasoning: {event['all_agent_analysis']}
        
        Return concise briefing (max 150 words)
        """
        
        # Haiku executor streams response
        async for chunk in call_haiku_with_opus_advisor(prompt):
            yield chunk + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

### Commit
```bash
git add src/detectors/ src/api/routes/briefing.py
git commit -m "feat: Add compound risk detection, streaming briefing endpoint"
git push origin feat/add-disaster-connectors
```

---

## THURSDAY: Polish + Push (8 hours)

### Update README with data diagram
```bash
# Add screenshot of globe with events
# Update quick start
```

### Full test
```bash
pytest tests/ -v
npm run build
```

### Merge to main
```bash
git checkout main
git pull
git merge feat/add-disaster-connectors
git push origin main
```

### Create GitHub release
```
Tag: v0.1-alpha
Title: SentinelMAS v0.1 Alpha - Live disaster detection

Description:
✓ 6 data connectors (EONET, USGS, NOAA, GDACS, News, ReliefWeb)
✓ 3 specialist agents (Flood, Earthquake, Wildfire)
✓ Compound risk detection
✓ 3D globe visualization
✓ Streaming briefings (Opus advisor + Haiku executor)

Next week: Expand to 12 agents, full health dashboard
```

---

## FRIDAY: Launch (2 hours)

### Final checks
```bash
# Verify all 6 connectors running
python -m src.connectors.eonet_connector
python -m src.connectors.usgs_connector
# ... etc

# Start system
uvicorn src.api.main:app
cd frontend && npm run dev

# Visit http://localhost:3000
# Click events on globe, see briefings stream
```

### GitHub
- All code pushed
- v0.1-alpha released
- README updated with screenshots

### LinkedIn post
```
🚀 SentinelMAS v0.1 Alpha

Real-time global disaster intelligence.
6 data sources. 3 specialist agents. Compound risk detection.
3D globe. Streaming briefings.

Open source. Self-hostable. For governments, NGOs, Red Cross.

Built on World Monitor. Powered by NASA EONET + USGS + NOAA.

github.com/Lionnel-cyber/SentinelMAS

#OpenSource #DisasterIntelligence #GlobalGood
```

---

Done. That's the week. You know how to do this.
