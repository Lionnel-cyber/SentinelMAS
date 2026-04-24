# CLAUDE.md — SentinelMAS Project Context

**IMPORTANT: Use focused files, not this full document.**

Never load this entire file. Always use:

```
@CLAUDE_CONNECTORS.md     (for data ingestion work)
@CLAUDE_AGENTS.md         (for agent development)
@CLAUDE_FRONTEND.md       (for UI/globe work)
@CLAUDE_API.md            (for FastAPI endpoints)
```

This file is reference only. Split work by domain.

---

## Project Summary (quick reference)

**SentinelMAS** = Global disaster intelligence with 12 specialist agents reasoning about compound risks.

**Core mission:** Real-time early warning for earthquakes, floods, wildfires, storms, and cascading disasters. Open source. Self-hostable. For governments, NGOs, Red Cross.

**Stack:** World Monitor fork (base) + CrewAI agents + FAISS memory + FastAPI + React/deck.gl globe.

**Scope:** 6 data connectors → 12 agents → Compound risk detection → 3D globe + streaming briefings.

---

## Key Architecture Decisions

**1. Fork World Monitor, don't rebuild**
- Proven UI/UX for global intelligence
- Proto-based services (type-safe)
- Already has 3D globe, layers, data pipeline
- We customize for disasters only

**2. 12 specialist agents, not one big model**
- FloodAgent reasons about hydrology
- EarthquakeAgent about seismic cascades
- WildfireAgent about fuel + containment
- Etc. One per EONET category
- All share Agent Zero memory (FAISS)

**3. Compound risk detection**
- Earthquakes + floods = 1.8x amplifier
- Drought + wildfires = 2.1x amplifier
- Not just summing scores

**4. Signal tiers (same as PulseIQ)**
- Tier 1: USGS, NASA, NOAA (ground truth)
- Tier 2: GDACS, news (corroborating)
- Tier 3: Trends, social (early warning)
- Never treat tier 3 alone as high confidence

**5. Cost optimization**
- Opus 4.7 as advisor (reasoning only)
- Haiku 4.5 as executor (streaming generation)
- ~85% cost reduction vs. Opus solo
- Streaming briefings via FastAPI SSE

---

## Data Sources (all free, no keys required)

```
NASA EONET v3        → 12 disaster categories
USGS Earthquake API  → M4.5+ earthquakes
NOAA API             → Flood/storm data
GDACS RSS            → UN alerts
Reuters/BBC/AJ RSS   → News casualty counts
ReliefWeb RSS        → Humanitarian status
NASA FIRMS           → Active fire boundaries
```

---

## Focused File Breakdown

**CLAUDE_CONNECTORS.md**
- EONET, USGS, NOAA, GDACS, Reuters, ReliefWeb connectors
- Data structure (raw JSON to staging)
- Backfill logic, error handling

**CLAUDE_AGENTS.md**
- Agent Zero memory setup (FAISS)
- 12 agent specifications (FloodAgent, etc.)
- Reasoning patterns, tool calls
- CompoundEventDetector logic

**CLAUDE_API.md**
- FastAPI endpoints (/events/critical, /briefing/stream)
- Streaming setup (SSE, Opus advisor + Haiku executor)
- Rate limiting, error responses

**CLAUDE_FRONTEND.md**
- 3D globe (deck.gl on World Monitor base)
- Event cards (ranked by severity)
- Intel panel (click event, see agent reasoning)
- Health dashboard (source freshness)

---

## Use This for Sessions

```
Connector work?     → /claude-code /load CLAUDE_CONNECTORS.md
Agent development?  → /claude-code /load CLAUDE_AGENTS.md
API work?           → /claude-code /load CLAUDE_API.md
Frontend work?      → /claude-code /load CLAUDE_FRONTEND.md
Planning?           → Use this file only
```

Never load full CLAUDE.md into a session. Always pick one focused file.

This saves ~70% tokens compared to loading everything.

---

## Token Budget

Each session should use:
- One focused .md file (~400-600 tokens)
- Your task description (~200 tokens)
- Code reads as needed (~200-400 tokens)
- Total per message: ~1000-1200 tokens (vs. 4000+ for full context)

Over 100 messages: ~120K tokens (vs. 400K+ for full context).

---

## Execution Model

**Executor: Haiku 4.5**
- Implements code, reads files, runs tests
- Mechanical work: 90% of turns

**Advisor: Opus 4.7**
- Consults on architecture decisions
- Compound risk logic design
- Agent reasoning patterns
- Called ~10% of turns

Set `/model haiku` then `/advisor on` in Claude Code.

---

## Files to .claudeignore

```
node_modules/
frontend/.next/
frontend/node_modules/
dist/
build/
.git/
*.lock
__pycache__/
*.pyc
data/raw/
data/processed/
models/
chroma/
.dbt/
coverage/
*.min.js
*.map
*.egg-info/
.pytest_cache/
htmlcov/
```

One-time setup. Saves 50-70% tokens by not loading garbage.

---

## Quick Reference: Agent Specs

```
FloodAgent       → Hydrology, dam stress, upstream rainfall
EarthquakeAgent  → Seismic cascades, aftershock probability
WildfireAgent    → Fuel moisture, wind, containment lines
StormAgent       → Track projection, surge, tornado risk
VolcanoAgent     → Eruption progression, ash fall, lahar
LandslideAgent   → Slope stability, rainfall triggers
DroughtAgent     → Agricultural impact, fire correlation
DustHazeAgent    → Air quality, health risk
ManmadeAgent     → Industrial accident, contamination
IceAgent         → Shipping, coastal flooding
SnowAgent        → Avalanche, infrastructure load, melt flood
WaterColorAgent  → Algal bloom, water supply threat
```

Each agent:
- Reads relevant connectors
- Stores state in Agent Zero memory
- Outputs: EventScore (severity 0-100, confidence, reasoning)
- Triggers alerts when severity ≥ 70

---

## CompoundEventDetector Reference

```python
earthquakes + floods       → 1.8x (dam failure risk)
drought + wildfires        → 2.1x (extreme conditions)
storms + floods            → 1.6x (surge amplification)
earthquakes + landslides   → 1.9x (cascade)
volcanoes + storms         → 2.3x (lahar formation)

If 2+ agents score ≥60 in overlapping geos:
  compound_risk = True
  cascade_probability = calculated
  population_at_risk = combined
```

---

## Streaming Briefing Pattern

```
User clicks event
  ↓
Frontend calls /api/v1/briefing/{event_id}/stream (SSE)
  ↓
Backend:
  1. Haiku reads event data + all agent reasoning
  2. Calls Opus advisor: "Summarize this disaster for emergency coordinator"
  3. Opus returns: 400-700 token plan/briefing
  4. Haiku streams formatted briefing to frontend
  5. Frontend renders live as chunks arrive
  ↓
Result: Opus-quality briefing, Haiku streaming cost
```

Cost: ~$0.0003 per briefing (vs. $0.003 with Opus alone).

---

Done. Pick a focused file for Monday. Don't load this full document.
