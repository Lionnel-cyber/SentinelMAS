# CLAUDE_AGENTS.md — SentinelMAS Specialist Agents

Use this ONLY for agent development. Saves 70% context.

---

## Agent Architecture

**Agent Zero Memory (FAISS):**
- All 12 agents write/read shared context
- Prevents duplicate reasoning
- Enables compound risk coordination
- Vector DB: FAISS (lightweight, no external dependency)

**Executor + Advisor:**
- Haiku 4.5 as primary executor (agent loop)
- Opus 4.7 as advisor (complex reasoning)
- Cost: Haiku rates + small Opus consultations

---

## 12 Specialist Agents

Each agent:
1. Reads relevant connectors
2. Stores state in FAISS memory
3. Scores event 0-100
4. Flags if severity ≥ 70 (alert)
5. Returns: EventScore (severity, confidence, reasoning)

---

## FloodAgent (Example Implementation)

```python
# src/agents/flood_agent.py

from crewai import Agent, Task
from langchain.llms import Anthropic
import os

def create_flood_agent():
    """Flood risk specialist agent"""
    
    llm = Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-haiku-4-5-20251001"
    )
    
    agent = Agent(
        role="Flood Risk Analyst",
        goal="Assess flood severity, propagation, and population impact",
        backstory="""
        Expert hydrologist specializing in:
        - Rainfall accumulation and intensity
        - Dam and levee stress
        - Downstream flood propagation
        - Historical flood patterns by region
        You analyze raw sensor data and produce threat scores.
        """,
        tools=[],  # Add tools later (fetch dam data, etc.)
        llm=llm,
        verbose=False
    )
    
    return agent

def score_flood_event(agent, event_data: dict) -> dict:
    """
    Score a flood event end-to-end.
    
    event_data:
      location: "Jakarta, Indonesia"
      rainfall_24h_mm: 450
      rainfall_forecast_48h_mm: 200
      area_affected_km2: 2500
      population_at_risk: 10000000
      dam_capacity_percent: 95
      rivers_above_flood_stage: 3
    """
    
    task = Task(
        description=f"""
        Analyze this flood event and return a severity score (0-100):
        
        Location: {event_data.get('location')}
        Rainfall (past 24h): {event_data.get('rainfall_24h_mm')}mm
        Rainfall (forecast 48h): {event_data.get('rainfall_forecast_48h_mm')}mm
        Area affected: {event_data.get('area_affected_km2')}km²
        Population at risk: {event_data.get('population_at_risk'):,}
        Dam capacity: {event_data.get('dam_capacity_percent')}%
        Rivers at flood stage: {event_data.get('rivers_above_flood_stage')}
        
        Return ONLY this JSON (no markdown, no extras):
        {{
          "severity_score": <0-100>,
          "threat_level": "monitor|elevated|critical",
          "confidence": "high|medium|low",
          "reasoning": "2-3 sentence explanation",
          "cascade_risk": "low|medium|high"
        }}
        """,
        agent=agent,
        expected_output="JSON"
    )
    
    result = task.execute()
    
    # Parse JSON from result
    import json
    import re
    json_str = re.search(r'\{.*\}', result, re.DOTALL)
    if json_str:
        return json.loads(json_str.group())
    return {"severity_score": 0, "error": str(result)}

if __name__ == "__main__":
    agent = create_flood_agent()
    
    test_event = {
        'location': 'Jakarta, Indonesia',
        'rainfall_24h_mm': 450,
        'rainfall_forecast_48h_mm': 200,
        'area_affected_km2': 2500,
        'population_at_risk': 10000000,
        'dam_capacity_percent': 95,
        'rivers_above_flood_stage': 3
    }
    
    score = score_flood_event(agent, test_event)
    print(json.dumps(score, indent=2))
```

---

## EarthquakeAgent

```python
# src/agents/earthquake_agent.py

from crewai import Agent, Task
from langchain.llms import Anthropic
import os
import json

def create_earthquake_agent():
    """Seismic specialist agent"""
    
    llm = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), model="claude-haiku-4-5-20251001")
    
    agent = Agent(
        role="Seismic Risk Analyst",
        goal="Assess earthquake severity, aftershock probability, and cascade risks",
        backstory="""
        Seismologist specializing in:
        - Magnitude and depth interpretation
        - Aftershock probability models
        - Liquefaction and landslide triggers
        - Building damage assessment
        You provide rapid severity scores for emergency response.
        """,
        llm=llm,
        verbose=False
    )
    return agent

def score_earthquake_event(agent, event_data: dict) -> dict:
    """
    event_data:
      magnitude: 7.2
      depth_km: 15
      location: "Manila, Philippines"
      population_at_risk: 15000000
      aftershock_probability: 0.65
      building_vulnerability: "high"  # low/medium/high
    """
    
    task = Task(
        description=f"""
        Analyze earthquake and return severity (0-100):
        
        Magnitude: {event_data.get('magnitude')}
        Depth: {event_data.get('depth_km')}km
        Location: {event_data.get('location')}
        Population: {event_data.get('population_at_risk'):,}
        Aftershock probability: {event_data.get('aftershock_probability')}
        Building vulnerability: {event_data.get('building_vulnerability')}
        
        Return JSON:
        {{
          "severity_score": <0-100>,
          "threat_level": "monitor|elevated|critical",
          "confidence": "high|medium|low",
          "aftershock_probability": <0.0-1.0>,
          "reasoning": "Brief explanation"
        }}
        """,
        agent=agent,
        expected_output="JSON"
    )
    result = task.execute()
    
    import re
    json_str = re.search(r'\{.*\}', result, re.DOTALL)
    if json_str:
        return json.loads(json_str.group())
    return {"severity_score": 0}
```

---

## WildfireAgent

```python
# src/agents/wildfire_agent.py

from crewai import Agent, Task
from langchain.llms import Anthropic
import os
import json

def create_wildfire_agent():
    """Fire risk specialist"""
    
    llm = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), model="claude-haiku-4-5-20251001")
    
    agent = Agent(
        role="Wildfire Risk Analyst",
        goal="Assess wildfire severity, spread rate, and containment status",
        backstory="""
        Wildfire specialist expert in:
        - Fuel loads and moisture content
        - Wind speed and direction effects
        - Terrain-driven fire behavior
        - Containment line effectiveness
        You predict fire progression and threat to population.
        """,
        llm=llm,
        verbose=False
    )
    return agent

def score_wildfire_event(agent, event_data: dict) -> dict:
    """
    event_data:
      location: "Northern California"
      acres_burned: 125000
      acres_threatened: 500000
      wind_speed_mph: 45
      fuel_moisture: "very dry"  # wet/dry/very dry
      containment_percent: 35
      population_threatened: 2000000
    """
    
    task = Task(
        description=f"""
        Analyze wildfire and return severity (0-100):
        
        Location: {event_data.get('location')}
        Acres burned: {event_data.get('acres_burned'):,}
        Acres threatened: {event_data.get('acres_threatened'):,}
        Wind speed: {event_data.get('wind_speed_mph')}mph
        Fuel moisture: {event_data.get('fuel_moisture')}
        Containment: {event_data.get('containment_percent')}%
        Population threatened: {event_data.get('population_threatened'):,}
        
        Return JSON:
        {{
          "severity_score": <0-100>,
          "threat_level": "monitor|elevated|critical",
          "confidence": "high|medium|low",
          "spread_rate_mph": <0-50>,
          "reasoning": "Brief explanation"
        }}
        """,
        agent=agent,
        expected_output="JSON"
    )
    result = task.execute()
    
    import re
    json_str = re.search(r'\{.*\}', result, re.DOTALL)
    if json_str:
        return json.loads(json_str.group())
    return {"severity_score": 0}
```

---

## Agent Zero Memory (FAISS)

```python
# src/agents/memory.py

from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
import json
import os

class AgentMemory:
    """Shared memory for all 12 agents via FAISS"""
    
    def __init__(self, embedding_model="all-MiniLM-L6-v2"):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model
        )
        
        # Load or create FAISS index
        self.faiss_path = "data/faiss_memory"
        if os.path.exists(f"{self.faiss_path}"):
            self.db = FAISS.load_local(self.faiss_path, self.embeddings)
        else:
            # Start empty
            self.db = FAISS.from_texts(
                texts=["Initial memory"],
                embedding=self.embeddings
            )
    
    def store_event_analysis(self, event_id: str, agent_name: str, analysis: dict):
        """Store agent's analysis for this event"""
        
        text = f"""
        Event: {event_id}
        Agent: {agent_name}
        Analysis: {json.dumps(analysis)}
        """
        
        self.db.add_texts([text], metadatas=[{
            'event_id': event_id,
            'agent': agent_name
        }])
        
        # Save FAISS index
        self.db.save_local(self.faiss_path)
    
    def retrieve_event_context(self, event_id: str, top_k=5) -> list:
        """Get all agent analyses for this event"""
        
        query = f"Event {event_id} analysis"
        results = self.db.similarity_search(query, k=top_k)
        
        return [doc.page_content for doc in results]
    
    def get_compound_risk_context(self, event_ids: list) -> str:
        """Get context for compound risk detection"""
        
        context = []
        for event_id in event_ids:
            analyses = self.retrieve_event_context(event_id)
            context.extend(analyses)
        
        return "\n".join(context)

if __name__ == "__main__":
    memory = AgentMemory()
    
    # Store an analysis
    memory.store_event_analysis(
        event_id="FLOOD-20260418-001",
        agent_name="FloodAgent",
        analysis={
            "severity": 78,
            "confidence": "high",
            "population_risk": 10000000
        }
    )
    
    # Retrieve it
    context = memory.retrieve_event_context("FLOOD-20260418-001")
    print(context)
```

---

## Quick Agent Factory

```python
# src/agents/__init__.py

from .flood_agent import create_flood_agent, score_flood_event
from .earthquake_agent import create_earthquake_agent, score_earthquake_event
from .wildfire_agent import create_wildfire_agent, score_wildfire_event
from .memory import AgentMemory

# Create all 12 agents
AGENTS = {
    'flood': create_flood_agent(),
    'earthquake': create_earthquake_agent(),
    'wildfire': create_wildfire_agent(),
    # ... add remaining 9 agents same way
}

def score_all_agents(event_data: dict, agent_memory: AgentMemory) -> dict:
    """Score event across all agents"""
    
    scores = {}
    
    for agent_name, agent in AGENTS.items():
        score_fn = globals()[f'score_{agent_name}_event']
        score = score_fn(agent, event_data)
        scores[agent_name] = score
        
        # Store in memory
        agent_memory.store_event_analysis(
            event_id=event_data.get('event_id'),
            agent_name=agent_name,
            analysis=score
        )
    
    return scores
```

---

## Test All Agents

```bash
python -c "
from src.agents import AGENTS, score_all_agents, AgentMemory

memory = AgentMemory()

test_event = {
    'event_id': 'FLOOD-2026-04-18-001',
    'location': 'Jakarta',
    'rainfall_24h_mm': 450,
    'population_at_risk': 10000000,
    # ... add other required fields
}

scores = score_all_agents(test_event, memory)
print(scores)
"
```

---

Done. Implement agents one by one, store in memory, ship.
