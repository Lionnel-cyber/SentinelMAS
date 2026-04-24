# SentinelMAS

**Global Disaster Intelligence Platform**

Near real-time compound event detection and multi-agent reasoning for earthquakes, floods, wildfires, storms, and cascading disasters.

Built on World Monitor foundation. Open source. Self-hostable. For governments, NGOs, emergency services.

---

## What it does

- **6 data connectors** → NASA EONET, USGS, NOAA, GDACS, Reuters, ReliefWeb
- **12 specialist agents** → One per disaster type (flood, earthquake, fire, storm, volcano, landslide, drought, dust, manmade, ice, snow, water)
- **Compound risk detection** → When earthquakes + floods interact, risk amplifies 1.8x
- **Agent Zero memory** → Shared FAISS context across all 12 agents
- **3D globe** → Live disaster dots, auto-rotating, pulsing on critical events
- **Streaming briefings** → Opus 4.7 advisor + Haiku 4.5 executor (cost-optimized)

---

## Stack

**Backend:** Python, FastAPI, DuckDB, dbt, CrewAI, FAISS, Agent Zero
**Frontend:** React 18, TypeScript, deck.gl, Tailwind (on World Monitor base)
**Data:** NASA, USGS, NOAA, GDACS (all free APIs, no keys needed)
**LLM:** Opus 4.7 advisor, Haiku 4.5 executor (via Anthropic API)

---

## Quick Start

```bash
# Clone
git clone https://github.com/Lionnel-cyber/SentinelMAS.git
cd SentinelMAS

# Install
pip install -r requirements.txt
cd frontend && npm install

# Set env (only ANTHROPIC_API_KEY needed)
cp .env.example .env
# Add ANTHROPIC_API_KEY for streaming briefings

# Run connectors
python -m src.connectors.eonet_connector
python -m src.connectors.usgs_connector
python -m src.connectors.noaa_connector
python -m src.connectors.gdacs_connector
python -m src.connectors.reuters_connector
python -m src.connectors.reliefweb_connector

# Start backend
uvicorn src.api.main:app --reload

# Start frontend
cd frontend && npm run dev

# Open http://localhost:3000
```

---

## Architecture

```
Data Layer (6 connectors)
  EONET, USGS, NOAA, GDACS, Reuters, ReliefWeb
        ↓
dbt Transform (staging → marts)
  stg_eonet_events, stg_gdacs_alerts, stg_reuters_casualties
  int_compound_risks, mart_disaster_threat
        ↓
Agent Layer (12 specialists + Agent Zero memory)
  FloodAgent, EarthquakeAgent, WildfireAgent, StormAgent, ...
        ↓
CompoundEventDetector (risk amplification)
  Earthquakes + Floods → 1.8x amplifier
  Drought + Wildfires → 2.1x amplifier
        ↓
FastAPI (streaming + scoring)
  /api/v1/events/critical
  /api/v1/events/{event_id}
  /api/v1/compound-risks
  /api/v1/briefing/{event_id}/stream
        ↓
Frontend (3D globe + event cards + intel panel)
  Real-time threat visualization
  Click-through to agent reasoning
```

---

## EventScore Contract

```python
geo_id: str
disaster_type: str  # earthquake, flood, fire, storm, etc.
severity_score: float  # 0-100
threat_level: str  # monitor / elevated / critical
confidence: str  # high / medium / low
population_at_risk: int
compound_risk: bool
cascade_probability: float
missing_data_flags: list[str]
data_freshness_hours: int
agent_reasoning: dict  # All 12 agents' analysis
```

---

## Signal Tiers (like PulseIQ)

**Tier 1 (70%)** — Ground truth
- USGS earthquake magnitude/depth
- NASA FIRMS satellite fire boundaries
- NOAA gauge data

**Tier 2 (20%)** — Corroborating
- GDACS pre-calculated alerts
- News casualty counts

**Tier 3 (10%)** — Early warning
- Google Trends (disaster keyword spikes)
- Social media sentiment

Never treat Tier 3 alone as high confidence.

---

## Agent Reasoning

Each agent reads:
- Live event data from connectors
- Historical patterns (previous 30 days)
- Compound risk flags
- Population exposure

Example: **FloodAgent**
```
Input: NOAA rainfall 150mm/24h, elevation map, dam status
Analysis: High rainfall + low elevation + dam stress
Output: FloodScore 78/100, confidence=high, population_at_risk=2.3M
Reasoning: "Upstream dam at 95% capacity. 48-hour rainfall forecast 
shows additional 80mm. Breach probability 12% if sustained."
```

---

## Compound Risk Detection

```
Earthquake (M7.2) + Flood (100yr event) in same region
  → Base amplifier: 1.8x
  → Earthquake triggers landslides: +0.3x
  → Total: 2.1x multiplier
  → Final score: 78 * 2.1 = 163.8 (capped at 100, flags as CRITICAL)
  → Population impact: earthquake + flood + landslide cascade
```

---

## Confidence Layer

Every score shows:
- **Data freshness** — When each source last updated
- **Missing sources** — Which connectors are stale
- **Agent agreement** — Do 10+ agents agree on threat level?
- **Historical accuracy** — How often this agent was right

Example:
```
CRITICAL FLOOD
Severity: 78/100
Confidence: HIGH (NOAA data fresh 5min ago, 98% agent agreement)
Missing: Reddit sentiment (30min stale)
```

---

## Open Source For Good

- Free. No paywalls.
- Self-hostable. No cloud dependency.
- Auditable. All reasoning visible.
- Extensible. Add agents, data sources, rules.

Built for:
- **Red Cross/Red Crescent** — Real-time disaster response coordination
- **UN OCHA** — Global humanitarian situational awareness
- **National governments** — Early warning for civil protection
- **NGOs** — Community disaster preparedness
- **Researchers** — Open data for disaster science

---

## Development Roadmap

**v0.1 (Week 1-2):**
- 6 connectors live
- 3-4 agents reasoning
- Compound detection
- Basic streaming briefings

**v1.0 (Week 3-4):**
- All 12 agents
- Health dashboard
- Full test coverage
- Production Docker setup

**v2.0 (Q2):**
- Historical trend analysis
- Predictive 72-hour forecasts
- Local LLM support (Ollama)
- Satellite imagery integration

---

## Contributing

Fork it. Improve it. Ship it.

Issues, PRs, agent improvements welcome.

---

## License

MIT. Free for any use.

---

## Contact

Built by Lionnel-cyber for communities that need early warning.

GitHub: github.com/Lionnel-cyber/SentinelMAS

Next: AEGIS — Agent safety governance layer (v2.0).
