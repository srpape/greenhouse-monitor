#!/usr/bin/env python3
from astral import LocationInfo
from astral.location import Location
from astral.sun import sun

import astral
import fcntl
import json
import time
import pyowm
import pyowm.exceptions

if __name__ == "__main__":
    city = LocationInfo("Ithaca", "New York", "US/Eastern", 42.511680, -76.557191)
    location = Location(info=city)

    api_key = 'b6546cf6c172e28bf67ac7090d2ff65b'
    city_id = 5141508
    owm = pyowm.OWM(api_key)

    while True:
        try:
            observation = owm.weather_at_id(city_id)
        except pyowm.exceptions.OWMError as e:
            print("Error updating OpenWeatherMap data", e)
            time.sleep(30)
            continue

        weather = observation.get_weather()

        output = {
            "sun": {
                "elevation": location.solar_elevation()
            },
            "weather": {
                "temperature": weather.get_temperature(unit="celsius"),
                "pressure": weather.get_pressure(),
                "humidity": weather.get_humidity(),
                "wind": weather.get_wind(),
                "rain": weather.get_rain(),
                "snow": weather.get_snow(),
                "clouds": weather.get_clouds(),
                "dewpoint": weather.get_dewpoint(),
                "heat_index": weather.get_heat_index(),
                "status": weather.get_status(),
                "detailed_status": weather.get_detailed_status(),
                "weather_code": weather.get_weather_code(),
                "weather_icon_name": weather.get_weather_icon_name(),
                "weather_icon_url": weather.get_weather_icon_url(),
                "visibility_distance": weather.get_visibility_distance(),
                "time": weather.get_reference_time(),
            }
        }

        with open("/tmp/weather.json", 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(output))

        time.sleep(120)

