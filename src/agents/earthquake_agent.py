import math
import json
from datetime import datetime, timedelta
from typing import Optional
from crewai import Agent, Task
from langchain.llms import Anthropic
import os

def estimate_aftershock_probability(magnitude: float, depth_km: float) -> float:
	"""Estimate aftershock probability from magnitude and depth."""
	if magnitude < 5.0:
		return 0.1

	# Higher magnitude = higher probability
	mag_factor = (magnitude - 5.0) / 3.0
	mag_prob = min(0.9, max(0.2, mag_factor))

	# Shallow depth = higher probability (more stress release triggers aftershocks)
	if depth_km < 30:
		depth_factor = 1.2
	elif depth_km < 70:
		depth_factor = 1.0
	else:
		depth_factor = 0.7

	return min(1.0, mag_prob * depth_factor)

def estimate_population_at_risk(magnitude: float, depth_km: float, place: str) -> int:
	"""Rough estimate of population at risk based on magnitude and depth."""
	# Base population estimate based on earthquake severity
	if magnitude >= 8.0:
		base_pop = 50_000_000
	elif magnitude >= 7.5:
		base_pop = 30_000_000
	elif magnitude >= 7.0:
		base_pop = 15_000_000
	elif magnitude >= 6.5:
		base_pop = 5_000_000
	else:
		base_pop = 1_000_000

	# Shallow earthquakes affect larger areas
	if depth_km < 30:
		depth_factor = 1.3
	elif depth_km < 70:
		depth_factor = 1.0
	else:
		depth_factor = 0.5

	return int(base_pop * depth_factor)

def log_scale(value: float, min_val: float, max_val: float, weight: float) -> float:
	"""Log-scale a value within a range to a weight."""
	if value <= min_val:
		return 0
	if value >= max_val:
		return weight

	# Handle min_val = 0 case with linear scale
	if min_val <= 0:
		return weight * (value / max_val) if max_val > 0 else 0

	return weight * (math.log(value / min_val) / math.log(max_val / min_val))

def calculate_earthquake_rubric(event_data: dict) -> dict:
	"""
	Deterministic rubric scoring for EarthquakeAgent.

	event_data must contain:
	  - event_id: str
	  - magnitude: float
	  - depth_km: float
	  - place: str
	  - latitude: float
	  - longitude: float
	  - time: Unix timestamp (ms)

	Returns dict with severity_score (0-100), threat_level, factors
	"""

	factors = {}

	# 1. Magnitude (max 60 points)
	magnitude = event_data.get("magnitude", 0.0)
	if magnitude >= 7.2:
		factors["magnitude"] = 60.0
		factors["magnitude_critical"] = True
	elif magnitude >= 6.5:
		factors["magnitude"] = log_scale(magnitude, 6.5, 7.2, 60.0)
		factors["magnitude_critical"] = False
	elif magnitude >= 5.5:
		factors["magnitude"] = log_scale(magnitude, 5.5, 6.5, 60.0)
		factors["magnitude_critical"] = False
	else:
		factors["magnitude"] = log_scale(magnitude, 0, 5.5, 60.0)
		factors["magnitude_critical"] = False

	# 2. Depth (max 15 points, shallow = higher score)
	depth_km = event_data.get("depth_km", 30.0)
	if depth_km < 30:
		factors["depth"] = 15.0
		factors["depth_shallow"] = True
	elif depth_km < 70:
		factors["depth"] = log_scale(70 - depth_km, 0, 40, 15.0)
		factors["depth_shallow"] = False
	else:
		factors["depth"] = 0.0
		factors["depth_shallow"] = False

	# 3. Estimated population at risk (max 15 points)
	place = event_data.get("place", "")
	pop_at_risk = event_data.get("population_at_risk")
	if pop_at_risk is None:
		pop_at_risk = estimate_population_at_risk(magnitude, depth_km, place)

	if pop_at_risk >= 15_000_000:
		factors["population"] = 15.0
	elif pop_at_risk >= 5_000_000:
		factors["population"] = log_scale(pop_at_risk, 5_000_000, 15_000_000, 15.0)
	else:
		factors["population"] = log_scale(pop_at_risk, 0, 5_000_000, 15.0)

	# 4. Aftershock probability (max 10 points)
	aftershock_prob = event_data.get("aftershock_probability")
	if aftershock_prob is None:
		aftershock_prob = estimate_aftershock_probability(magnitude, depth_km)

	factors["aftershock_probability"] = aftershock_prob
	if aftershock_prob > 0.6:
		factors["aftershock_score"] = 10.0
		factors["cascade_risk"] = "high"
	elif aftershock_prob > 0.4:
		factors["aftershock_score"] = log_scale(aftershock_prob, 0.4, 0.6, 10.0)
		factors["cascade_risk"] = "medium"
	else:
		factors["aftershock_score"] = log_scale(aftershock_prob, 0, 0.4, 10.0)
		factors["cascade_risk"] = "low"

	# Raw score (magnitude + depth + population + aftershock)
	raw_score = (
		factors["magnitude"] +
		factors["depth"] +
		factors["population"] +
		factors["aftershock_score"]
	)

	# Cap at 100
	severity_score = min(100, int(round(raw_score)))

	# Threat level
	if magnitude >= 7.0:
		threat_level = "critical" if severity_score >= 70 else "elevated"
	elif magnitude >= 6.5:
		threat_level = "critical" if severity_score >= 80 else "elevated"
	elif severity_score >= 75:
		threat_level = "elevated"
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

def create_earthquake_agent():
	"""Create EarthquakeAgent using Haiku."""
	llm = Anthropic(
		api_key=os.getenv("ANTHROPIC_API_KEY"),
		model="claude-haiku-4-5-20251001"
	)

	agent = Agent(
		role="Seismic Risk Analyst",
		goal="Assess earthquake severity, aftershock probability, and cascade risks with deterministic scoring",
		backstory="""
		Seismologist with 12+ years in seismic hazard assessment.
		Specializes in:
		- Magnitude and depth interpretation for damage potential
		- Aftershock probability models and cascade failures
		- Liquefaction and landslide trigger assessment
		- Building vulnerability and population exposure
		You produce rapid, auditable threat scores for emergency response.
		""",
		tools=[],
		llm=llm,
		verbose=False
	)

	return agent

def score_earthquake_event(agent: Agent, event_data: dict, memory=None, advisor_fn=None) -> dict:
	"""
	Score an earthquake event end-to-end.

	Args:
	  agent: CrewAI agent
	  event_data: dict with earthquake event details
	  memory: AgentMemory instance (optional, for FAISS retrieval)
	  advisor_fn: callable for Opus consultation (optional)

	Returns:
	  dict with severity_score (0-100), threat_level, confidence, reasoning, cascade_risk
	"""

	event_id = event_data.get("event_id", "EQ-UNKNOWN")
	location = event_data.get("place", "Unknown")
	magnitude = event_data.get("magnitude", 0.0)
	depth_km = event_data.get("depth_km", 0.0)

	# 1. FAISS retrieval (if memory provided)
	historical_context = ""
	if memory:
		try:
			historical_context = memory.retrieve_event_context(
				query=f"{location} earthquake historical aftershocks",
				top_k=3
			)
		except Exception:
			historical_context = ""

	# 2. Apply deterministic rubric
	rubric_result = calculate_earthquake_rubric(event_data)
	raw_score = rubric_result["raw_score"]
	severity_score = rubric_result["severity_score"]
	threat_level = rubric_result["threat_level"]
	factors = rubric_result["factors"]

	# 3. Determine confidence (based on USGS data recency)
	timestamp_ms = event_data.get("time", 0)
	if timestamp_ms > 0:
		event_time = datetime.utcfromtimestamp(timestamp_ms / 1000.0)
		age_hours = (datetime.utcnow() - event_time).total_seconds() / 3600

		if age_hours < 24:
			confidence = "high"
		elif age_hours < 72:
			confidence = "medium"
		else:
			confidence = "low"
	else:
		confidence = "medium"

	# 4. Advisor consultation triggers
	needs_advisor = (magnitude > 7.0) or (factors.get("aftershock_probability", 0) > 0.6)

	advisor_context = ""
	if needs_advisor and advisor_fn:
		advisor_context = advisor_fn(
			event_id=event_id,
			location=location,
			severity=severity_score,
			magnitude=magnitude,
			aftershock_prob=factors.get("aftershock_probability", 0),
			reason="magnitude > 7.0" if magnitude > 7.0 else "aftershock probability > 60%"
		)

	# 5. Build reasoning narrative
	dominant_factors = []
	if factors.get("magnitude", 0) >= 50:
		dominant_factors.append(f"high magnitude earthquake ({magnitude})")
	if factors.get("depth_shallow"):
		dominant_factors.append(f"shallow depth ({depth_km}km)")
	if factors.get("population", 0) >= 10:
		pop = event_data.get("population_at_risk", estimate_population_at_risk(magnitude, depth_km, location))
		dominant_factors.append(f"large population at risk (~{pop:,})")
	if factors.get("aftershock_probability", 0) > 0.6:
		dominant_factors.append(f"high aftershock probability ({factors.get('aftershock_probability'):.0%})")

	reasoning = f"Seismic risk assessment for {location}: "
	if dominant_factors:
		reasoning += ", ".join(dominant_factors) + ". "

	if severity_score >= 80:
		reasoning += f"Severity {severity_score} indicates major earthquake with significant damage potential. "
	elif severity_score >= 60:
		reasoning += f"Severity {severity_score} indicates moderate to significant seismic threat. "
	else:
		reasoning += f"Severity {severity_score} indicates minor to moderate event, monitoring recommended. "

	if advisor_context:
		reasoning += f"Advisor: {advisor_context} "

	cascade_risk = factors.get("cascade_risk", "low")

	# 6. Return structured output
	return {
		"event_id": event_id,
		"agent": "EarthquakeAgent",
		"severity_score": severity_score,
		"threat_level": threat_level,
		"confidence": confidence,
		"reasoning": reasoning.strip(),
		"cascade_risk": cascade_risk,
		"timestamp": datetime.utcnow().isoformat(),
		"magnitude": magnitude,
		"depth_km": depth_km,
		"aftershock_probability": factors.get("aftershock_probability", 0),
		"factors": {k: v for k, v in factors.items() if k not in ["magnitude_critical", "depth_shallow"]},
		"needs_advisor_review": needs_advisor,
	}

if __name__ == "__main__":
	agent = create_earthquake_agent()

	test_event = {
		"event_id": "us6000test001",
		"magnitude": 7.2,
		"depth_km": 15,
		"place": "Manila, Philippines",
		"latitude": 14.5,
		"longitude": 121.0,
		"time": int(datetime.utcnow().timestamp() * 1000),
		"population_at_risk": 15_000_000,
		"aftershock_probability": 0.65,
	}

	score = score_earthquake_event(agent, test_event)
	print(json.dumps(score, indent=2))
