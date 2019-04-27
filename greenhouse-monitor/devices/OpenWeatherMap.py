import pyowm

from .Sensor import Sensor

class OpenWeatherMap(Sensor):
    def __init__(self, device_name, device_config):
        super(OpenWeatherMap, self).__init__(device_type='weather', device_name=device_name, device_config=device_config)
        api_key = device_config.get('api_key').strip()

        self.city_id = int(device_config.get('city_id'))
        self.owm = pyowm.OWM(api_key)

    def update(self):
        self.observation = self.owm.weather_at_id(self.city_id)
        weather = self.observation.get_weather()

        self.data['temperature'] = weather.get_temperature('fahrenheit')['temp']
        self.data['humidity'] = weather.get_humidity()
        self.data['wind'] = weather.get_wind()
        self.data['sunrise'] = weather.get_sunrise_time()
        self.data['sunset'] = weather.get_sunset_time()
        self.data['pressure'] = weather.get_pressure()['press']
        self.data['clouds'] = weather.get_clouds()
        self.data['weather_icon_url'] = weather.get_weather_icon_url()