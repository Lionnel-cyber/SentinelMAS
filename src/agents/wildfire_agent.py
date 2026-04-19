import math
import json
from datetime import datetime
from typing import Optional
from crewai import Agent, Task
from langchain.llms import Anthropic
import os


def log_scale(value: float, min_val: float, max_val: float, weight: float) -> float:
	if value <= min_val:
		return 0
	if value >= max_val:
		return weight
	if min_val <= 0:
		return weight * (value / max_val) if max_val > 0 else 0
	return weight * (math.log(value / min_val) / math.log(max_val / min_val))


FUEL_MOISTURE_SCORES = {
	"very dry": 25.0,
	"dry": 15.0,
	"normal": 7.0,
	"wet": 2.0,
}


def calculate_wildfire_rubric(event_data: dict) -> dict:
	"""
	Deterministic rubric scoring for WildfireAgent.

	event_data fields (all optional except location):
	  location: str
	  acres_burned: float
	  acres_threatened: float
	  wind_speed_mph: float
	  fuel_moisture: str  (very dry/dry/normal/wet)
	  containment_percent: float  (0-100)
	  population_threatened: int
	  containment_trend: str  (dropping/stable/rising)
	"""
	factors = {}

	# 1. Fire boundary size (acres_burned + acres_threatened, max 30 points)
	acres_burned = event_data.get("acres_burned", 0)
	acres_threatened = event_data.get("acres_threatened", 0)
	# Threatened acres weighted at 0.4 vs actual 1.0
	effective_acres = acres_burned + (acres_threatened * 0.4)

	if effective_acres >= 500_000:
		factors["fire_size"] = 30.0
	elif effective_acres >= 10_000:
		factors["fire_size"] = log_scale(effective_acres, 10_000, 500_000, 30.0)
	elif effective_acres > 0:
		factors["fire_size"] = log_scale(effective_acres, 0, 10_000, 30.0)
	else:
		factors["fire_size"] = 0.0

	# 2. Wind speed (max 20 points; > 30mph = full weight)
	wind_mph = event_data.get("wind_speed_mph", 0)
	if wind_mph >= 30:
		factors["wind"] = 20.0
		factors["wind_critical"] = True
	elif wind_mph >= 15:
		factors["wind"] = log_scale(wind_mph, 15, 30, 20.0)
		factors["wind_critical"] = False
	else:
		factors["wind"] = log_scale(wind_mph, 0, 15, 20.0)
		factors["wind_critical"] = False

	# 3. Fuel moisture (max 25 points)
	fuel_moisture = event_data.get("fuel_moisture", "normal").lower().strip()
	factors["fuel_moisture"] = FUEL_MOISTURE_SCORES.get(fuel_moisture, 7.0)
	factors["fuel_moisture_label"] = fuel_moisture

	# 4. Population threatened (max 15 points)
	pop = event_data.get("population_threatened", 0)
	if pop >= 5_000_000:
		factors["population"] = 15.0
	elif pop >= 500_000:
		factors["population"] = log_scale(pop, 500_000, 5_000_000, 15.0)
	else:
		factors["population"] = log_scale(pop, 0, 500_000, 15.0)

	# 5. Containment (max 10 points; < 50% = full weight)
	containment = event_data.get("containment_percent", 0)
	if containment < 50:
		factors["containment"] = 10.0
	elif containment < 80:
		factors["containment"] = log_scale(80 - containment, 0, 30, 10.0)
	else:
		factors["containment"] = 0.0

	# Containment dropping fast triggers advisor flag
	trend = event_data.get("containment_trend", "stable").lower()
	factors["containment_trend"] = trend
	factors["containment_dropping"] = trend == "dropping"

	raw_score = (
		factors["fire_size"] +
		factors["wind"] +
		factors["fuel_moisture"] +
		factors["population"] +
		factors["containment"]
	)

	severity_score = min(100, int(round(raw_score)))

	if factors["wind_critical"] and fuel_moisture == "very dry":
		threat_level = "critical"
	elif severity_score >= 70:
		threat_level = "critical"
	elif severity_score >= 45:
		threat_level = "elevated"
	else:
		threat_level = "monitor"

	return {
		"raw_score": raw_score,
		"severity_score": severity_score,
		"threat_level": threat_level,
		"factors": factors,
	}


def create_wildfire_agent():
	"""Create WildfireAgent using Haiku."""
	llm = Anthropic(
		api_key=os.getenv("ANTHROPIC_API_KEY"),
		model="claude-haiku-4-5-20251001"
	)

	agent = Agent(
		role="Wildfire Risk Analyst",
		goal="Assess wildfire severity, spread rate, and containment status with deterministic scoring",
		backstory="""
		Wildfire specialist with 10+ years in fire behavior prediction.
		Specializes in:
		- Fuel loads, moisture content, and ignition potential
		- Wind-driven fire spread and spotting distance
		- Terrain-driven fire behavior (slope, aspect, channeling)
		- Containment line effectiveness and resource allocation
		You produce rapid threat scores for emergency coordinators.
		""",
		tools=[],
		llm=llm,
		verbose=False
	)

	return agent


def score_wildfire_event(agent: Agent, event_data: dict, memory=None, advisor_fn=None) -> dict:
	"""
	Score a wildfire event end-to-end.

	Args:
	  agent: CrewAI agent
	  event_data: dict with wildfire event details
	  memory: AgentMemory instance (optional)
	  advisor_fn: callable for Opus consultation (optional)

	Returns:
	  dict with severity_score (0-100), threat_level, confidence, reasoning
	"""

	event_id = event_data.get("event_id", "FIRE-UNKNOWN")
	location = event_data.get("location", event_data.get("title", "Unknown"))
	wind_mph = event_data.get("wind_speed_mph", 0)

	# 1. FAISS retrieval
	historical_context = ""
	if memory:
		try:
			historical_context = memory.retrieve_event_context(
				query=f"{location} wildfire fire containment",
				top_k=3
			)
		except Exception:
			historical_context = ""

	# 2. Deterministic rubric
	rubric = calculate_wildfire_rubric(event_data)
	raw_score = rubric["raw_score"]
	severity_score = rubric["severity_score"]
	threat_level = rubric["threat_level"]
	factors = rubric["factors"]

	# 3. Confidence from data sources
	sources = event_data.get("sources", [])
	start_date = event_data.get("start_date", "")
	if start_date:
		try:
			event_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
			age_hours = (datetime.now(event_dt.tzinfo) - event_dt).total_seconds() / 3600
			recency_ok = age_hours < 48
		except Exception:
			recency_ok = False
	else:
		recency_ok = False

	if recency_ok and len(sources) >= 1:
		confidence = "high"
	elif recency_ok or len(sources) >= 1:
		confidence = "medium"
	else:
		confidence = "low"

	# 4. Advisor triggers: wind > 50mph OR containment dropping
	needs_advisor = (wind_mph > 50) or factors.get("containment_dropping", False)

	advisor_context = ""
	if needs_advisor and advisor_fn:
		advisor_context = advisor_fn(
			event_id=event_id,
			location=location,
			severity=severity_score,
			wind_mph=wind_mph,
			containment=event_data.get("containment_percent", 0),
			reason="wind > 50mph" if wind_mph > 50 else "containment dropping"
		)

	# 5. Reasoning narrative
	dominant_factors = []
	if factors.get("fire_size", 0) >= 20:
		acres = event_data.get("acres_burned", 0)
		dominant_factors.append(f"large fire boundary ({acres:,.0f} acres burned)")
	if factors.get("wind_critical"):
		dominant_factors.append(f"extreme wind ({wind_mph}mph)")
	fuel = factors.get("fuel_moisture_label", "")
	if fuel in ("very dry", "dry"):
		dominant_factors.append(f"fuel moisture: {fuel}")
	if factors.get("population", 0) >= 8:
		pop = event_data.get("population_threatened", 0)
		dominant_factors.append(f"large population at risk (~{pop:,})")
	containment = event_data.get("containment_percent", 0)
	if factors.get("containment", 0) >= 8:
		dominant_factors.append(f"low containment ({containment}%)")
	if factors.get("containment_dropping"):
		dominant_factors.append("containment trending down")

	reasoning = f"Wildfire risk assessment for {location}: "
	if dominant_factors:
		reasoning += ", ".join(dominant_factors) + ". "

	if severity_score >= 80:
		reasoning += f"Severity {severity_score} indicates rapidly spreading fire with critical threat. "
	elif severity_score >= 60:
		reasoning += f"Severity {severity_score} indicates active fire with significant spread risk. "
	else:
		reasoning += f"Severity {severity_score} indicates fire under monitoring conditions. "

	if advisor_context:
		reasoning += f"Advisor: {advisor_context} "

	spread_risk = "high" if factors.get("wind_critical") and fuel in ("very dry", "dry") else \
		"medium" if severity_score >= 60 else "low"

	# 6. Store in memory
	if memory:
		try:
			memory.store_event_analysis(
				event_id=event_id,
				agent_name="WildfireAgent",
				analysis={
					"severity_score": severity_score,
					"threat_level": threat_level,
					"confidence": confidence,
					"spread_risk": spread_risk,
				}
			)
		except Exception:
			pass

	return {
		"event_id": event_id,
		"agent": "WildfireAgent",
		"severity_score": severity_score,
		"threat_level": threat_level,
		"confidence": confidence,
		"reasoning": reasoning.strip(),
		"spread_risk": spread_risk,
		"timestamp": datetime.utcnow().isoformat(),
		"acres_burned": event_data.get("acres_burned", 0),
		"containment_percent": event_data.get("containment_percent", 0),
		"factors": {k: v for k, v in factors.items() if k not in ["wind_critical", "containment_dropping"]},
		"needs_advisor_review": needs_advisor,
	}


if __name__ == "__main__":
	agent = create_wildfire_agent()

	test_event = {
		"event_id": "EONET_FIRE_TEST_001",
		"title": "Bear Fire, Northern California",
		"location": "Northern California",
		"start_date": datetime.utcnow().isoformat() + "Z",
		"acres_burned": 125_000,
		"acres_threatened": 500_000,
		"wind_speed_mph": 45,
		"fuel_moisture": "very dry",
		"containment_percent": 35,
		"population_threatened": 2_000_000,
		"containment_trend": "stable",
		"sources": [{"id": "IRWIN"}],
	}

	score = score_wildfire_event(agent, test_event)
	print(json.dumps(score, indent=2))
