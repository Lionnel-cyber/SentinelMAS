import math
import json
from datetime import datetime
from typing import Optional
from crewai import Agent, Task
from langchain.llms import Anthropic
import os

def log_scale(value: float, min_val: float, max_val: float, weight: float) -> float:
    """Log-scale a value within a range to a weight."""
    if value <= min_val:
        return 0
    if value >= max_val:
        return weight
    return weight * (math.log(value / min_val) / math.log(max_val / min_val))

def calculate_rainfall_score(rainfall_24h_mm: float, rainfall_forecast_48h_mm: float, region: str = "tropical") -> tuple[float, str]:
    """Score rainfall intensity with forecast cascade warning."""
    score = 20.0
    note = "normal"

    # Regional 95th percentiles (mm/24h)
    thresholds = {
        "tropical": 250,
        "temperate": 150,
        "arid": 80,
    }
    threshold = thresholds.get(region, 150)

    # Actual rainfall severity
    if rainfall_24h_mm > threshold * 1.5:
        score = 20.0  # Full weight for extreme
        note = "extreme"
    elif rainfall_24h_mm > threshold:
        score = log_scale(rainfall_24h_mm, threshold, threshold * 1.5, 20.0)
        note = "elevated"
    else:
        score = log_scale(rainfall_24h_mm, 0, threshold, 20.0)

    # Cascade bonus: forecast >200mm
    cascade_bonus = 0
    if rainfall_forecast_48h_mm > 200:
        cascade_bonus = 15.0

    return score, cascade_bonus, note

def calculate_flood_rubric(event_data: dict) -> dict:
    """
    Deterministic rubric scoring for FloodAgent.

    event_data must contain:
      - location: str
      - population_at_risk: int
      - dam_capacity_percent: float
      - rainfall_24h_mm: float
      - rainfall_forecast_48h_mm: float
      - rivers_above_flood_stage: int
      - area_affected_km2: float
      - time_to_peak_hours: float
      - region: str (optional, default "tropical")

    Returns dict with:
      - raw_score: before cap/rounding
      - severity_score: final 0-100
      - threat_level: monitor/elevated/critical
      - factors: dict of all weighted factors
    """

    factors = {}

    # 1. Population at risk (30 points max)
    pop = event_data.get("population_at_risk", 0)
    if pop >= 10_000_000:
        factors["population"] = 30.0
    elif pop >= 1_000_000:
        factors["population"] = log_scale(pop, 1_000_000, 10_000_000, 30.0)
    else:
        factors["population"] = log_scale(pop, 0, 1_000_000, 30.0)

    # 2. Dam/levee stress (25 points max)
    dam_pct = event_data.get("dam_capacity_percent", 0)
    if dam_pct >= 95:
        factors["dam_stress"] = 25.0
        factors["dam_critical_flag"] = True  # Triggers advisor
    elif dam_pct >= 80:
        factors["dam_stress"] = log_scale(dam_pct, 80, 95, 25.0)
        factors["dam_critical_flag"] = False
    else:
        factors["dam_stress"] = log_scale(dam_pct, 0, 80, 25.0)
        factors["dam_critical_flag"] = False

    # 3. Rainfall intensity + cascade bonus (20 points + up to 15 bonus)
    region = event_data.get("region", "tropical")
    rainfall_score, cascade_bonus, rainfall_note = calculate_rainfall_score(
        event_data.get("rainfall_24h_mm", 0),
        event_data.get("rainfall_forecast_48h_mm", 0),
        region
    )
    factors["rainfall"] = rainfall_score
    factors["cascade_bonus"] = cascade_bonus
    factors["rainfall_note"] = rainfall_note

    # 4. Rivers above flood stage (10 points max)
    rivers = min(event_data.get("rivers_above_flood_stage", 0), 5)
    factors["rivers"] = (rivers / 5.0) * 10.0

    # 5. Area affected (10 points max, log-scaled)
    area_km2 = event_data.get("area_affected_km2", 0)
    if area_km2 >= 5000:
        factors["area"] = 10.0
    elif area_km2 >= 100:
        factors["area"] = log_scale(area_km2, 100, 5000, 10.0)
    else:
        factors["area"] = log_scale(area_km2, 0, 100, 10.0)

    # 6. Time to peak (5 points max, inverse urgency)
    time_to_peak = event_data.get("time_to_peak_hours", 48)
    if time_to_peak < 12:
        factors["urgency"] = 5.0  # Full weight (imminent)
    elif time_to_peak < 48:
        factors["urgency"] = log_scale(time_to_peak, 12, 48, 5.0)
    else:
        factors["urgency"] = 5.0 * 0.5  # Reduced for slow-onset

    # Raw score
    raw_score = (
        factors["population"] +
        factors["dam_stress"] +
        rainfall_score +
        cascade_bonus +
        factors["rivers"] +
        factors["area"] +
        factors["urgency"]
    )

    # Cap at 100
    severity_score = min(100, int(round(raw_score)))

    # Threat level
    if factors.get("population", 0) > 5_000_000 and raw_score >= 60:
        threat_level = "critical"
    elif severity_score >= 70:
        threat_level = "critical"
    elif severity_score >= 50:
        threat_level = "elevated"
    else:
        threat_level = "monitor"

    return {
        "raw_score": raw_score,
        "severity_score": severity_score,
        "threat_level": threat_level,
        "factors": factors,
    }

def create_flood_agent():
    """Create FloodAgent using Haiku."""
    llm = Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-haiku-4-5-20251001"
    )

    agent = Agent(
        role="Flood Risk Analyst",
        goal="Assess flood severity, propagation, and population impact with deterministic scoring",
        backstory="""
        Expert hydrologist with 15+ years in flood risk assessment.
        Specializes in:
        - Rainfall accumulation and intensity analysis
        - Dam and levee structural stress evaluation
        - Downstream flood propagation modeling
        - Historical flood patterns and regional vulnerability
        You produce rapid, auditable threat scores for emergency coordinators.
        """,
        tools=[],
        llm=llm,
        verbose=False
    )

    return agent

def score_flood_event(agent: Agent, event_data: dict, memory=None, advisor_fn=None) -> dict:
    """
    Score a flood event end-to-end.

    Args:
      agent: CrewAI agent
      event_data: dict with flood event details
      memory: AgentMemory instance (optional, for FAISS retrieval)
      advisor_fn: callable for Opus consultation (optional)

    Returns:
      dict with severity_score (0-100), threat_level, confidence, reasoning, cascade_risk
    """

    event_id = event_data.get("event_id", "FLOOD-UNKNOWN")
    location = event_data.get("location", "Unknown")

    # 1. FAISS retrieval (if memory provided)
    historical_context = ""
    if memory:
        try:
            historical_context = memory.retrieve_event_context(
                query=f"{location} flood historical",
                top_k=3
            )
        except Exception:
            historical_context = ""

    # 2. Apply deterministic rubric
    rubric_result = calculate_flood_rubric(event_data)
    raw_score = rubric_result["raw_score"]
    severity_score = rubric_result["severity_score"]
    threat_level = rubric_result["threat_level"]
    factors = rubric_result["factors"]

    # 3. Determine confidence (corroboration from connectors)
    sources = event_data.get("sources", [])
    confidence = "high" if len(sources) >= 2 else "medium" if sources else "low"

    # 4. Advisor consultation triggers
    needs_advisor = factors.get("dam_critical_flag", False) or severity_score >= 85

    advisor_context = ""
    if needs_advisor and advisor_fn:
        advisor_context = advisor_fn(
            event_id=event_id,
            location=location,
            severity=severity_score,
            factors=factors,
            reason="dam_stress >= 95%" if factors.get("dam_critical_flag") else "severity >= 85"
        )

    # 5. Build reasoning narrative
    dominant_factors = []
    if factors.get("population", 0) >= 25:
        dominant_factors.append(f"large population at risk ({event_data.get('population_at_risk', 0):,})")
    if factors.get("dam_stress", 0) >= 20:
        dominant_factors.append(f"critical dam stress ({event_data.get('dam_capacity_percent', 0)}%)")
    if factors.get("rainfall") >= 15:
        dominant_factors.append(f"extreme rainfall ({event_data.get('rainfall_24h_mm', 0)}mm/24h)")
    if factors.get("cascade_bonus", 0) > 0:
        dominant_factors.append("forecast rainfall compound risk")

    reasoning = f"Flood risk assessment for {location}: "
    if dominant_factors:
        reasoning += ", ".join(dominant_factors) + ". "

    if severity_score >= 80:
        reasoning += f"Severity {severity_score} indicates imminent catastrophic flooding. "
    elif severity_score >= 60:
        reasoning += f"Severity {severity_score} indicates significant flood threat. "
    else:
        reasoning += f"Severity {severity_score} indicates monitoring recommended. "

    if advisor_context:
        reasoning += f"Advisor: {advisor_context} "

    cascade_risk = "high" if factors.get("cascade_bonus", 0) > 5 else "medium" if raw_score >= 70 else "low"

    # 6. Return structured output
    return {
        "event_id": event_id,
        "agent": "FloodAgent",
        "severity_score": severity_score,
        "threat_level": threat_level,
        "confidence": confidence,
        "reasoning": reasoning.strip(),
        "cascade_risk": cascade_risk,
        "timestamp": datetime.utcnow().isoformat(),
        "factors": {k: v for k, v in factors.items() if k not in ["dam_critical_flag"]},
        "needs_advisor_review": needs_advisor,
    }

if __name__ == "__main__":
    agent = create_flood_agent()

    test_event = {
        "event_id": "FLOOD-20260419-JAKARTA-001",
        "location": "Jakarta, Indonesia",
        "population_at_risk": 10_000_000,
        "dam_capacity_percent": 95.0,
        "rainfall_24h_mm": 450.0,
        "rainfall_forecast_48h_mm": 200.0,
        "rivers_above_flood_stage": 3,
        "area_affected_km2": 2500.0,
        "time_to_peak_hours": 18.0,
        "region": "tropical",
        "sources": ["NOAA", "BMKG", "GDACS"],
    }

    score = score_flood_event(agent, test_event)
    print(json.dumps(score, indent=2))
