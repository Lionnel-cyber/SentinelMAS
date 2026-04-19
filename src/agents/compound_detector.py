import json
import math
from datetime import datetime, timedelta
from typing import Optional
from .memory import AgentMemory


# Amplifiers for known compound disaster pairings
AMPLIFIERS: dict[frozenset, float] = {
	frozenset({"FloodAgent", "EarthquakeAgent"}):  1.8,  # dam failure risk
	frozenset({"DroughtAgent", "WildfireAgent"}):  2.1,  # extreme fire conditions
	frozenset({"StormAgent",  "FloodAgent"}):      1.6,  # surge amplification
}

DEFAULT_AMPLIFIER = 1.3  # any other co-occurring pair

GEO_RADIUS_KM    = 100.0
TIME_WINDOW_HOURS = 24


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
	"""Great-circle distance in km."""
	R = 6371.0
	phi1, phi2 = math.radians(lat1), math.radians(lat2)
	dphi = math.radians(lat2 - lat1)
	dlam = math.radians(lon2 - lon1)
	a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
	return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_ts(ts: str | None) -> datetime | None:
	if not ts:
		return None
	try:
		return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
	except Exception:
		return None


def _within_window(ts1: str | None, ts2: str | None, hours: float = TIME_WINDOW_HOURS) -> bool:
	t1, t2 = _parse_ts(ts1), _parse_ts(ts2)
	if t1 is None or t2 is None:
		return True  # assume overlap if timestamps missing
	return abs((t1 - t2).total_seconds()) <= hours * 3600


def _within_radius(e1: dict, e2: dict, radius_km: float = GEO_RADIUS_KM) -> bool:
	lat1 = e1.get("latitude") or e1.get("lat")
	lon1 = e1.get("longitude") or e1.get("lon")
	lat2 = e2.get("latitude") or e2.get("lat")
	lon2 = e2.get("longitude") or e2.get("lon")
	if None in (lat1, lon1, lat2, lon2):
		return False
	return haversine_km(lat1, lon1, lat2, lon2) <= radius_km


def compound_score(score1: int, score2: int, amplifier: float) -> int:
	"""Final compound score formula: min(s1 * s2 / 50 * amplifier, 100)."""
	raw = (score1 * score2 / 50.0) * amplifier
	return min(100, int(round(raw)))


def detect_compound_events(
	scored_events: list[dict],
	memory: Optional[AgentMemory] = None,
) -> list[dict]:
	"""
	Find all compound disaster pairs from a list of agent-scored events.

	Each element of scored_events must have:
	  agent: str            e.g. "FloodAgent"
	  event_id: str
	  severity_score: int
	  timestamp: str        ISO-8601
	  latitude: float       (optional but needed for geo check)
	  longitude: float      (optional but needed for geo check)

	Returns list of compound event dicts, sorted by compound_score descending.
	"""

	# Only consider events that scored ≥ 60
	candidates = [e for e in scored_events if e.get("severity_score", 0) >= 60]

	compounds: list[dict] = []
	seen_pairs: set[frozenset] = set()

	for i in range(len(candidates)):
		for j in range(i + 1, len(candidates)):
			e1, e2 = candidates[i], candidates[j]

			# Deduplicate by event_id pair
			pair_key = frozenset({e1["event_id"], e2["event_id"]})
			if pair_key in seen_pairs:
				continue

			# Same agent type — not a compound event
			if e1["agent"] == e2["agent"]:
				continue

			# Temporal overlap check
			if not _within_window(e1.get("timestamp"), e2.get("timestamp")):
				continue

			# Geographic overlap check (skip pair if both lack coordinates)
			has_geo = all(
				(e.get("latitude") or e.get("lat")) is not None
				for e in (e1, e2)
			)
			if has_geo and not _within_radius(e1, e2):
				continue

			seen_pairs.add(pair_key)

			agent_pair = frozenset({e1["agent"], e2["agent"]})
			amplifier = AMPLIFIERS.get(agent_pair, DEFAULT_AMPLIFIER)

			cscore = compound_score(e1["severity_score"], e2["severity_score"], amplifier)
			is_critical = cscore >= 85

			compound = {
				"compound_id": f"COMPOUND-{e1['event_id']}-{e2['event_id']}",
				"event_ids": [e1["event_id"], e2["event_id"]],
				"agents": [e1["agent"], e2["agent"]],
				"agent_pair": sorted(agent_pair),
				"score1": e1["severity_score"],
				"score2": e2["severity_score"],
				"amplifier": amplifier,
				"compound_score": cscore,
				"flag": "COMPOUND_CRITICAL" if is_critical else "COMPOUND_ELEVATED",
				"timestamp": datetime.utcnow().isoformat(),
				"reasoning": _build_reasoning(e1, e2, amplifier, cscore, is_critical),
			}

			# Store in Agent Zero memory
			if memory:
				try:
					memory.store_event_analysis(
						event_id=compound["compound_id"],
						agent_name="CompoundDetector",
						analysis={
							"compound_score": cscore,
							"flag": compound["flag"],
							"agents": compound["agents"],
							"amplifier": amplifier,
						},
					)
				except Exception:
					pass

			compounds.append(compound)

	compounds.sort(key=lambda x: x["compound_score"], reverse=True)
	return compounds


def _build_reasoning(e1: dict, e2: dict, amplifier: float, cscore: int, is_critical: bool) -> str:
	pair_label = f"{e1['agent'].replace('Agent','')} + {e2['agent'].replace('Agent','')}"
	loc1 = e1.get("place") or e1.get("location") or e1.get("event_id")
	loc2 = e2.get("place") or e2.get("location") or e2.get("event_id")

	reason = (
		f"Compound {pair_label} event detected: "
		f"{e1['agent']} scored {e1['severity_score']} ({loc1}), "
		f"{e2['agent']} scored {e2['severity_score']} ({loc2}). "
		f"Amplifier {amplifier}x applied → compound score {cscore}."
	)

	if amplifier == 1.8:
		reason += " Earthquake + flood interaction creates dam and levee failure risk."
	elif amplifier == 2.1:
		reason += " Drought + wildfire interaction produces extreme, self-reinforcing fire conditions."
	elif amplifier == 1.6:
		reason += " Storm + flood interaction amplifies surge and inundation risk."

	if is_critical:
		reason += " COMPOUND_CRITICAL: immediate multi-agency response required."

	return reason


if __name__ == "__main__":
	# Synthetic test: earthquake near a flood, same region
	test_events = [
		{
			"event_id": "EQ-001",
			"agent": "EarthquakeAgent",
			"severity_score": 75,
			"timestamp": datetime.utcnow().isoformat(),
			"latitude": 14.5,
			"longitude": 121.0,
			"place": "Manila, Philippines",
		},
		{
			"event_id": "FL-001",
			"agent": "FloodAgent",
			"severity_score": 80,
			"timestamp": datetime.utcnow().isoformat(),
			"latitude": 14.8,
			"longitude": 121.2,
			"location": "Metro Manila",
		},
		{
			"event_id": "DR-001",
			"agent": "DroughtAgent",
			"severity_score": 65,
			"timestamp": datetime.utcnow().isoformat(),
			"latitude": -34.0,
			"longitude": -64.0,
			"location": "Argentina",
		},
		{
			"event_id": "WF-001",
			"agent": "WildfireAgent",
			"severity_score": 72,
			"timestamp": datetime.utcnow().isoformat(),
			"latitude": -33.5,
			"longitude": -63.8,
			"location": "Northern Argentina",
		},
	]

	results = detect_compound_events(test_events)
	print(json.dumps(results, indent=2))
