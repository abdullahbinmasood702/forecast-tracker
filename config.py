# Edit this: add/remove cities (name -> (latitude, longitude)).
CITIES = {
    "Islamabad": (33.6844, 73.0479),
    "London": (51.5072, -0.1276),
    "New York": (40.7128, -74.0060),
}

# Open-Meteo daily variable names -> our column names
DAILY_VARS = {
    "temperature_2m_max": "temp_max",
    "temperature_2m_min": "temp_min",
    "precipitation_sum": "precip_sum",
    "wind_speed_10m_max": "wind_max",
}

FORECAST_DAYS = 8  # today + 7 days ahead
