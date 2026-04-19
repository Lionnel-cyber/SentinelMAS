"""
DroughtAgent — v0.1 limitations documented

TIER-LEVEL ACCURACY: ✓ High confidence
- DR1 green alerts → ~41-49 (monitor)
- DR2 orange alerts → ~73-81 (elevated)
- DR3 red alerts → 90+ (critical)

WITHIN-TIER GRANULARITY: ⚠ Limited
- No SPI index (Standardized Precipitation Index)
- No acreage measurements
- No duration tracking
- No water stress readings

Libya drought detected correctly at DR1/green tier.

FUTURE (v1.1):
- Integrate USDM (US Drought Monitor) for US
- Add CHIRPS precipitation anomalies
- SPI historical data via NOAA
- Will enable within-tier differentiation
"""
import re
import math
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from crewai import Agent, Task
from langchain.llms import Anthropic
import os


# GDACS DR category → (base_duration_days, base_agricultural_score, water_stress_score)
GDACS_LEVEL_MAP = {
	"DR1": {"level": "green",  "duration_days": 60,  "agri_score": 10.0, "water_stress": 5.0},
	"DR2": {"level": "orange", "duration_days": 120, "agri_score": 20.0, "water_stress": 12.0},
	"DR3": {"level": "red",    "duration_days": 180, "agri_score": 30.0, "water_stress": 20.0},
}

# High-agriculture regions — multiplier for agricultural score
AGRI_REGION_MULTIPLIERS = {
	"argentina": 1.4, "ukraine": 1.4, "russia": 1.3, "brazil": 1.3,
	"united states": 1.3, "china": 1.2, "india": 1.2, "australia": 1.2,
	"france": 1.1, "germany": 1.1, "canada": 1.1,
}


def log_scale(value: float, min_val: float, max_val: float, weight: float) -> float:
	if value <= min_val:
		return 0
	if value >= max_val:
		return weight
	if min_val <= 0:
		return weight * (value / max_val) if max_val > 0 else 0
	return weight * (math.log(value / min_val) / math.log(max_val / min_val))


def parse_countries_from_title(title: str) -> list[str]:
	"""Extract country names from GDACS title like 'Drought is on going in X, Y'."""
	match = re.search(r'in\s+(.+)$', title, re.IGNORECASE)
	if not match:
		return []
	raw = match.group(1)
	return [c.strip().lower() for c in raw.split(",")]


def parse_gdacs_level(summary: str, category: str) -> str:
	"""Return green/orange/red from GDACS summary or category."""
	lower = summary.lower()
	if "red" in lower:
		return "red"
	if "orange" in lower:
		return "orange"
	if "green" in lower:
		return "green"
	return GDACS_LEVEL_MAP.get(category, {}).get("level", "green")


def estimate_agri_multiplier(countries: list[str]) -> float:
	"""Max multiplier across all affected countries."""
	multipliers = [AGRI_REGION_MULTIPLIERS.get(c, 1.0) for c in countries]
	return max(multipliers) if multipliers else 1.0


def parse_published_date(published: str) -> datetime | None:
	"""Parse RFC 2822 or ISO date strings from GDACS/news."""
	try:
		return parsedate_to_datetime(published).replace(tzinfo=None)
	except Exception:
		pass
	try:
		return datetime.fromisoformat(published.replace("Z", "+00:00")).replace(tzinfo=None)
	except Exception:
		return None


def calculate_drought_rubric(event_data: dict) -> dict:
	"""
	Deterministic rubric for DroughtAgent.

	event_data fields:
	  title: str              GDACS title (parsed for countries)
	  summary: str            GDACS summary (notification level)
	  category: str           GDACS category (DR1/DR2/DR3)
	  published: str          Publication date
	  duration_days: float    Override duration estimate
	  agricultural_acres: float  Affected agricultural area
	  water_stress_index: float  0.0-1.0 water stress level
	  population_agri_dependent: int
	  wildfire_correlation: bool  Active wildfire in same region
	  sources: list
	"""
	factors = {}

	title = event_data.get("title", "")
	summary = event_data.get("summary", "")
	category = event_data.get("category", "DR1")
	countries = parse_countries_from_title(title)
	level_info = GDACS_LEVEL_MAP.get(category, GDACS_LEVEL_MAP["DR1"])
	agri_multiplier = estimate_agri_multiplier(countries)

	factors["countries"] = countries
	factors["gdacs_level"] = parse_gdacs_level(summary, category)
	factors["agri_multiplier"] = agri_multiplier

	# 1. Drought duration (max 40 points; > 90 days = full weight)
	duration_days = event_data.get("duration_days") or level_info["duration_days"]
	factors["duration_days"] = duration_days
	if duration_days >= 90:
		factors["duration"] = 40.0
	elif duration_days >= 30:
		factors["duration"] = log_scale(duration_days, 30, 90, 40.0)
	else:
		factors["duration"] = log_scale(duration_days, 0, 30, 40.0)

	# 2. Agricultural area (max 30 points)
	# When actual acreage is provided, scale it; otherwise derive from GDACS level directly.
	agri_acres = event_data.get("agricultural_acres")
	if agri_acres is not None:
		if agri_acres >= 1_000_000:
			factors["agriculture"] = 30.0
		elif agri_acres >= 100_000:
			factors["agriculture"] = log_scale(agri_acres, 100_000, 1_000_000, 30.0)
		else:
			factors["agriculture"] = log_scale(agri_acres, 0, 100_000, 30.0)
		factors["agricultural_acres"] = agri_acres
	else:
		# GDACS level already encodes severity; apply agri multiplier as a bonus only
		# DR1=10, DR2=20, DR3=30 — do NOT multiply by country count (avoids Libya inflation)
		factors["agriculture"] = min(30.0, level_info["agri_score"] * agri_multiplier)
		factors["agricultural_acres"] = None

	# 3. Water stress (max 20 points)
	water_stress = event_data.get("water_stress_index")
	if water_stress is not None:
		factors["water_stress"] = min(20.0, water_stress * 20.0)
	else:
		factors["water_stress"] = level_info["water_stress"]

	# 4. Wildfire correlation — same region active fire (max 15 points)
	wildfire_corr = event_data.get("wildfire_correlation", False)
	factors["wildfire_correlation"] = wildfire_corr
	factors["wildfire_cascade"] = 15.0 if wildfire_corr else 0.0

	# 5. Population dependent on agriculture (max 10 points)
	pop_agri = event_data.get("population_agri_dependent", 0)
	if pop_agri == 0:
		pop_agri = len(countries) * 2_000_000  # rough default per country
	factors["population_agri_dependent"] = pop_agri

	if pop_agri >= 50_000_000:
		factors["population"] = 10.0
	else:
		factors["population"] = log_scale(pop_agri, 0, 50_000_000, 10.0)

	raw_score = (
		factors["duration"] +
		factors["agriculture"] +
		factors["water_stress"] +
		factors["wildfire_cascade"] +
		factors["population"]
	)

	severity_score = min(100, int(round(raw_score)))

	gdacs_lvl = factors["gdacs_level"]
	if wildfire_corr and gdacs_lvl in ("orange", "red"):
		threat_level = "critical"
	elif gdacs_lvl == "red" or severity_score >= 70:
		threat_level = "critical"
	elif gdacs_lvl == "orange" or severity_score >= 45:
		threat_level = "elevated"
	else:
		threat_level = "monitor"

	return {
		"raw_score": raw_score,
		"severity_score": severity_score,
		"threat_level": threat_level,
		"factors": factors,
	}


def create_drought_agent():
	"""Create DroughtAgent using Haiku."""
	llm = Anthropic(
		api_key=os.getenv("ANTHROPIC_API_KEY"),
		model="claude-haiku-4-5-20251001"
	)

	agent = Agent(
		role="Drought Risk Analyst",
		goal="Assess drought severity, agricultural impact, and cascade risks with deterministic scoring",
		backstory="""
		Drought specialist with 12+ years in hydrology and agricultural risk.
		Specializes in:
		- Long-term precipitation deficit and SPI index analysis
		- Agricultural water demand vs. supply gaps
		- Water stress cascade into food security and wildfire risk
		- Regional drought pattern and multi-year drought cycles
		You produce rapid threat scores from GDACS and multi-source drought data.
		""",
		tools=[],
		llm=llm,
		verbose=False
	)

	return agent


def score_drought_event(agent: Agent, event_data: dict, memory=None, advisor_fn=None,
                        active_wildfires_in_region: list | None = None) -> dict:
	"""
	Score a drought event end-to-end.

	Args:
	  agent: CrewAI agent
	  event_data: dict with GDACS/drought alert fields
	  memory: AgentMemory instance (optional)
	  advisor_fn: callable for Opus consultation (optional)
	  active_wildfires_in_region: list of active wildfire event_ids in same region

	Returns:
	  dict with severity_score (0-100), threat_level, confidence, reasoning
	"""

	event_id = event_data.get("link", event_data.get("event_id", "DROUGHT-UNKNOWN"))
	title = event_data.get("title", "Unknown drought")
	countries = parse_countries_from_title(title)

	# Inject wildfire correlation if caller provides active fires
	if active_wildfires_in_region:
		event_data = {**event_data, "wildfire_correlation": True}

	# 1. FAISS retrieval
	if memory:
		try:
			query = f"drought {' '.join(countries[:2])} agricultural water stress"
			memory.retrieve_event_context(query=query, top_k=3)
		except Exception:
			pass

	# 2. Deterministic rubric
	rubric = calculate_drought_rubric(event_data)
	raw_score = rubric["raw_score"]
	severity_score = rubric["severity_score"]
	threat_level = rubric["threat_level"]
	factors = rubric["factors"]

	# 3. Confidence from source count and recency
	published = event_data.get("published", "")
	sources = event_data.get("sources", [])
	recency_ok = False
	if published:
		pub_dt = parse_published_date(published)
		if pub_dt:
			age_days = (datetime.utcnow() - pub_dt).days
			recency_ok = age_days < 30  # drought data valid for ~30 days

	n_sources = len(sources) + (1 if published else 0)
	if recency_ok and n_sources >= 2:
		confidence = "high"
	elif recency_ok or n_sources >= 2:
		confidence = "medium"
	else:
		confidence = "low"

	# 4. Advisor trigger: drought + wildfire cascade in same region
	has_wildfire = factors.get("wildfire_correlation", False)
	needs_advisor = has_wildfire and severity_score >= 50

	advisor_context = ""
	if needs_advisor and advisor_fn:
		advisor_context = advisor_fn(
			event_id=event_id,
			location=", ".join(countries),
			severity=severity_score,
			wildfire_count=len(active_wildfires_in_region or []),
			reason="drought + active wildfire cascade risk in same region"
		)

	# 5. Reasoning narrative
	dominant_factors = []
	if factors["duration_days"] >= 90:
		dominant_factors.append(f"prolonged drought ({factors['duration_days']:.0f}+ days)")
	if factors["agriculture"] >= 20:
		dominant_factors.append(f"large agricultural area affected")
	if factors["water_stress"] >= 12:
		dominant_factors.append(f"high water stress (GDACS {factors['gdacs_level']})")
	if has_wildfire:
		dominant_factors.append("active wildfire cascade risk")
	region_str = ", ".join(c.title() for c in countries[:4])
	if len(countries) > 4:
		region_str += f" +{len(countries)-4} more"

	reasoning = f"Drought risk assessment for {region_str}: "
	if dominant_factors:
		reasoning += ", ".join(dominant_factors) + ". "

	if severity_score >= 80:
		reasoning += f"Severity {severity_score} indicates severe drought with critical agricultural and water supply impacts. "
	elif severity_score >= 60:
		reasoning += f"Severity {severity_score} indicates significant drought stress with growing cascade risk. "
	else:
		reasoning += f"Severity {severity_score} indicates developing drought, continued monitoring required. "

	if advisor_context:
		reasoning += f"Advisor: {advisor_context} "

	cascade_risk = "high" if has_wildfire else "medium" if severity_score >= 60 else "low"

	# 6. Store in memory
	if memory:
		try:
			memory.store_event_analysis(
				event_id=str(event_id),
				agent_name="DroughtAgent",
				analysis={
					"severity_score": severity_score,
					"threat_level": threat_level,
					"confidence": confidence,
					"cascade_risk": cascade_risk,
					"countries": countries,
				}
			)
		except Exception:
			pass

	return {
		"event_id": str(event_id),
		"agent": "DroughtAgent",
		"severity_score": severity_score,
		"threat_level": threat_level,
		"confidence": confidence,
		"reasoning": reasoning.strip(),
		"cascade_risk": cascade_risk,
		"timestamp": datetime.utcnow().isoformat(),
		"countries_affected": countries,
		"gdacs_level": factors["gdacs_level"],
		"wildfire_correlation": has_wildfire,
		"factors": {k: v for k, v in factors.items() if k != "countries"},
		"needs_advisor_review": needs_advisor,
	}


if __name__ == "__main__":
	agent = create_drought_agent()

	# Test with real GDACS drought data
	with open("data/raw/gdacs_alerts.json") as f:
		alerts = json.load(f)
	items = alerts if isinstance(alerts, list) else list(alerts.values())[0]
	droughts = [x for x in items if x.get("category", "").startswith("DR")]

	print(f"GDACS drought events: {len(droughts)}\n")

	for event in droughts[:5]:
		rubric = calculate_drought_rubric(event)
		print(f"{event['title'][:60]}")
		print(f"  Score: {rubric['severity_score']} | Threat: {rubric['threat_level']} | Level: {rubric['factors']['gdacs_level']}")

	print()
	# Test with wildfire cascade (Argentina drought + wildfire nearby)
	cascade_event = {**droughts[2], "wildfire_correlation": True}  # Argentina/Uruguay
	rubric2 = calculate_drought_rubric(cascade_event)
	print(f"With wildfire cascade: score={rubric2['severity_score']} threat={rubric2['threat_level']}")
