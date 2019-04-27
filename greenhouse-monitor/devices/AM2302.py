import wiringpi
import Adafruit_DHT
import os
import time

from .Sensor import Sensor

class AM2302(Sensor):
    def __init__(self, device_name, device_config):
        super(AM2302, self).__init__(device_type='temperature_humidity', device_name=device_name, device_config=device_config)
        self.power_pin = int(device_config['power_pin'])
        self.data_pin = int(device_config['data_pin'])
        wiringpi.pinMode(self.power_pin, 1)

        self._enable()

    def _reset(self):
        '''
        When the sensor gets 'stuck', we can power cycle it here.
        '''
        wiringpi.digitalWrite(self.power_pin, 0)
        time.sleep(1)
        self._enable()

    def _enable(self):
        wiringpi.digitalWrite(self.power_pin, 1)
        time.sleep(2)

    def update(self):
        humidity, tempC = self._read()

        if humidity is None:
            '''
            Power cycle and try again
            '''
            print('Resetting AM2302Sensor')
            self._reset()
            humidity, tempC = self._read()

        if humidity is not None:
            self.data['humidity'] = humidity
            self.data['temperature'] = self.celcius_to_fahrenheit(tempC)
            self.data['timestamp'] = int(time.time() * 1000)
        else:
            print('No temperature data from AM2302Sensor')
            self.data['temperature'] = 0
            self.data['humidity'] = 0

    def _read(self):
        # Go high-priority when reading this sensor to make it more reliable
        os.nice(-20)
        humidity, tempC = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, self.data_pin, delay_seconds=0.25)
        os.nice(20)
        return humidity, tempC