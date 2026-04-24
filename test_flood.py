from src.agents.flood_agent import calculate_flood_rubric

result = calculate_flood_rubric({
    "population_at_risk": 10_000_000,
    "dam_capacity_percent": 95.0,
    "rainfall_24h_mm": 450.0,
    "rainfall_forecast_48h_mm": 200.0,
    "rivers_above_flood_stage": 3,
    "area_affected_km2": 2500.0,
    "time_to_peak_hours": 18.0,
    "region": "tropical",
})

print(f"Score: {result['severity_score']}")
print(f"Threat: {result['threat_level']}")