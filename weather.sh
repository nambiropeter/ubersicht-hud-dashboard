#!/bin/zsh
# Weather widget data for Nairobi from Open-Meteo (free, no API key). Change LAT/LON to move it.
LAT=-1.2833 LON=36.8167
URL="https://api.open-meteo.com/v1/forecast?latitude=$LAT&longitude=$LON&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max,uv_index_max,sunrise,sunset&timezone=Africa%2FNairobi&forecast_days=6"
# Open-Meteo sometimes answers "overloaded" for a moment, so retry a few times before giving up
for i in 1 2 3; do
  out=$(curl -s -m 10 "$URL")
  [[ -n $out && $out != *'"error":true'* ]] && break
  sleep 4
done
print -r -- "$out"
