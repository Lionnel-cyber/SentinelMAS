import re
import math
import json
from datetime import datetime
from crewai import Agent, Task
from langchain.llms import Anthropic
import os


EVENT_BASE_SCORES = {
	"tornado warning": 70,
	"tornado watch": 50,
	"severe thunderstorm warning": 50,
	"severe thunderstorm watch": 35,
	"winter storm warning": 40,
	"blizzard warning": 45,
	"storm warning": 35,
	"wind advisory": 10,
	"high wind warning": 20,
	"special marine warning": 20,
	"gale warning": 25,
	"red flag warning": 15,
	"fire weather watch": 10,
}

NOAA_SEVERITY_BONUS = {
	"Extreme": 15,
	"Severe": 10,
	"Moderate": 5,
	"Minor": 0,
	"Unknown": 0,
}


def extract_wind_mph(description: str) -> float:
	"""Parse max wind speed from NOAA description text."""
	gusts = re.findall(r'gusts?\s+(?:up\s+to\s+)?(\d+)\s*mph', description, re.IGNORECASE)
	sustained = re.findall(r'winds?\s+(?:\d+\s+to\s+)?(\d+)\s*mph', description, re.IGNORECASE)
	candidates = [int(x) for x in gusts + sustained if x]
	return max(candidates) if candidates else 0


def extract_hail_risk(description: str) -> bool:
	return bool(re.search(r'hail', description, re.IGNORECASE))


def estimate_population_from_area(area_desc: str) -> int:
	"""Rough population estimate from number of counties/zones mentioned."""
	# Count comma-separated areas as proxy
	areas = [a.strip() for a in area_desc.split(";") if a.strip()]
	# ~50k per county/zone average (conservative)
	return len(areas) * 50_000


def calculate_storm_rubric(event_data: dict) -> dict:
	"""
	Deterministic rubric for StormAgent.

	event_data fields:
	  event: str          NOAA event type
	  description: str    Full NOAA description text
	  severity: str       NOAA severity (Extreme/Severe/Moderate/Minor)
	  areaDesc: str       Affected areas string
	  headline: str       Optional headline
	  population_affected: int  Optional override
	"""
	factors = {}

	event_type = event_data.get("event", "").lower().strip()
	description = event_data.get("description", "")
	severity_label = event_data.get("severity", "Unknown")

	# 1. Base event score (tornado warning = 70, severe thunderstorm = 50, etc.)
	base = 0
	matched_event = "other"
	for key, val in EVENT_BASE_SCORES.items():
		if key in event_type:
			base = val
			matched_event = key
			break
	factors["event_base"] = float(base)
	factors["matched_event"] = matched_event

	# 2. Wind score (max 20 points, triggers at > 60mph)
	wind_mph = event_data.get("wind_speed_mph") or extract_wind_mph(description)
	factors["wind_mph"] = wind_mph
	if wind_mph >= 60:
		factors["wind"] = 20.0
	elif wind_mph >= 30:
		factors["wind"] = 20.0 * ((wind_mph - 30) / 30)
	else:
		factors["wind"] = 0.0

	# 3. Hail risk (+15 points)
	has_hail = event_data.get("hail_risk") or extract_hail_risk(description)
	factors["hail_risk"] = has_hail
	factors["hail"] = 15.0 if has_hail else 0.0

	# 4. Population affected (max 10 points)
	pop = event_data.get("population_affected") or \
		estimate_population_from_area(event_data.get("areaDesc", ""))
	factors["population_affected"] = pop
	if pop >= 1_000_000:
		factors["population"] = 10.0
	elif pop > 0:
		factors["population"] = 10.0 * math.log10(pop) / 6.0  # log10(1M) = 6
	else:
		factors["population"] = 0.0

	# 5. NOAA severity bonus
	factors["severity_bonus"] = float(NOAA_SEVERITY_BONUS.get(severity_label, 0))

	raw_score = (
		factors["event_base"] +
		factors["wind"] +
		factors["hail"] +
		factors["population"] +
		factors["severity_bonus"]
	)

	severity_score = min(100, int(round(raw_score)))

	if "tornado warning" in event_type:
		threat_level = "critical"
	elif "tornado watch" in event_type or severity_score >= 70:
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


def create_storm_agent():
	"""Create StormAgent using Haiku."""
	llm = Anthropic(
		api_key=os.getenv("ANTHROPIC_API_KEY"),
		model="claude-haiku-4-5-20251001"
	)

	agent = Agent(
		role="Severe Storm Risk Analyst",
		goal="Assess storm severity, tornado risk, and cascade threats with deterministic scoring",
		backstory="""
		Meteorologist with 15+ years in severe weather forecasting.
		Specializes in:
		- Tornado warning triage and track prediction
		- Severe thunderstorm wind and hail potential
		- Winter storm and blizzard impact assessment
		- Multi-cell and supercell storm system dynamics
		You produce rapid threat scores from NWS alerts for emergency coordinators.
		""",
		tools=[],
		llm=llm,
		verbose=False
	)

	return agent


def score_storm_event(agent: Agent, event_data: dict, memory=None, advisor_fn=None,
                      region_tornado_count: int = 0) -> dict:
	"""
	Score a storm/weather alert end-to-end.

	Args:
	  agent: CrewAI agent
	  event_data: dict with NOAA alert fields
	  memory: AgentMemory instance (optional)
	  advisor_fn: callable for Opus consultation (optional)
	  region_tornado_count: number of concurrent tornado warnings in same region

	Returns:
	  dict with severity_score (0-100), threat_level, confidence, reasoning
	"""

	event_id = event_data.get("alert_id", "STORM-UNKNOWN")
	event_type = event_data.get("event", "Unknown")
	location = event_data.get("areaDesc", "Unknown area")
	description = event_data.get("description", "")

	# 1. FAISS retrieval
	if memory:
		try:
			memory.retrieve_event_context(
				query=f"{location} storm tornado warning",
				top_k=3
			)
		except Exception:
			pass

	# 2. Deterministic rubric
	rubric = calculate_storm_rubric(event_data)
	raw_score = rubric["raw_score"]
	severity_score = rubric["severity_score"]
	threat_level = rubric["threat_level"]
	factors = rubric["factors"]

	# 3. Confidence from alert recency
	effective = event_data.get("effective", "")
	expires = event_data.get("expires", "")
	now = datetime.utcnow()
	confidence = "low"
	if effective:
		try:
			eff_dt = datetime.fromisoformat(effective.replace("Z", "+00:00")).replace(tzinfo=None)
			age_hours = (now - eff_dt).total_seconds() / 3600
			if age_hours < 6:
				confidence = "high"
			elif age_hours < 24:
				confidence = "medium"
		except Exception:
			confidence = "medium"

	# 4. Advisor trigger: multiple tornado warnings in region
	is_tornado = "tornado warning" in event_type.lower()
	needs_advisor = is_tornado and region_tornado_count >= 2

	advisor_context = ""
	if needs_advisor and advisor_fn:
		advisor_context = advisor_fn(
			event_id=event_id,
			location=location,
			severity=severity_score,
			tornado_count=region_tornado_count,
			reason=f"multiple tornado warnings in region ({region_tornado_count})"
		)

	# 5. Reasoning narrative
	dominant_factors = []
	if factors["event_base"] >= 50:
		dominant_factors.append(f"{event_type}")
	if factors["wind_mph"] >= 60:
		dominant_factors.append(f"extreme wind ({factors['wind_mph']}mph)")
	elif factors["wind_mph"] >= 30:
		dominant_factors.append(f"strong wind ({factors['wind_mph']}mph)")
	if factors["hail_risk"]:
		dominant_factors.append("hail risk")
	pop = factors.get("population_affected", 0)
	if pop >= 100_000:
		dominant_factors.append(f"~{pop:,} people affected")
	if region_tornado_count >= 2:
		dominant_factors.append(f"{region_tornado_count} concurrent tornado warnings")

	reasoning = f"Storm risk assessment for {location}: "
	if dominant_factors:
		reasoning += ", ".join(dominant_factors) + ". "

	if severity_score >= 80:
		reasoning += f"Severity {severity_score} indicates life-threatening storm conditions. "
	elif severity_score >= 60:
		reasoning += f"Severity {severity_score} indicates significant storm threat requiring action. "
	else:
		reasoning += f"Severity {severity_score} indicates hazardous conditions, monitor closely. "

	if advisor_context:
		reasoning += f"Advisor: {advisor_context} "

	# 6. Store in memory
	if memory:
		try:
			memory.store_event_analysis(
				event_id=event_id,
				agent_name="StormAgent",
				analysis={
					"severity_score": severity_score,
					"threat_level": threat_level,
					"confidence": confidence,
					"event_type": event_type,
				}
			)
		except Exception:
			pass

	return {
		"event_id": event_id,
		"agent": "StormAgent",
		"severity_score": severity_score,
		"threat_level": threat_level,
		"confidence": confidence,
		"reasoning": reasoning.strip(),
		"timestamp": datetime.utcnow().isoformat(),
		"event_type": event_type,
		"wind_mph": factors.get("wind_mph", 0),
		"hail_risk": factors.get("hail_risk", False),
		"factors": {k: v for k, v in factors.items()},
		"needs_advisor_review": needs_advisor,
	}


if __name__ == "__main__":
	agent = create_storm_agent()

	# Test: tornado warning
	tornado_event = {
		"alert_id": "TEST-TORNADO-001",
		"event": "Tornado Warning",
		"headline": "Tornado Warning issued for central Oklahoma",
		"description": "A tornado warning is in effect. Doppler radar indicated a tornado capable of producing winds in excess of 100 mph. Hail up to 2 inches possible. Immediate life-threatening situation.",
		"areaDesc": "Oklahoma County; Cleveland County; Pottawatomie County",
		"severity": "Extreme",
		"effective": datetime.utcnow().isoformat(),
		"expires": datetime.utcnow().isoformat(),
	}

	score = score_storm_event(agent, tornado_event, region_tornado_count=3)
	print("Tornado Warning:")
	print(json.dumps(score, indent=2))

	print()

	# Test: wind advisory from real NOAA data
	with open("data/raw/noaa_alerts.json") as f:
		alerts = json.load(f)
	storm_alerts = [a for a in alerts if any(
		k in a.get("event", "").lower()
		for k in ["tornado", "storm", "wind", "hail", "thunder"]
	)]
	if storm_alerts:
		print(f"\nReal NOAA alert ({storm_alerts[0]['event']}):")
		r = calculate_storm_rubric(storm_alerts[0])
		print(f"  Score: {r['severity_score']} | Threat: {r['threat_level']}")
		print(f"  Wind: {r['factors']['wind_mph']}mph | Hail: {r['factors']['hail_risk']}")
