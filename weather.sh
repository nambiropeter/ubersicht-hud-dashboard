#!/bin/zsh
# Weather widget data for Nairobi from Open-Meteo (free, no API key). Change LAT/LON to move it.
LAT=-1.2833 LON=36.8167
curl -s -m 10 "https://api.open-meteo.com/v1/forecast?latitude=$LAT&longitude=$LON&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,sunrise,sunset&timezone=Africa%2FNairobi&forecast_days=6"
