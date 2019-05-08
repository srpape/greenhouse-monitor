from w1thermsensor import W1ThermSensor
import w1thermsensor.errors
from .Sensor import Sensor

class DS18B20(Sensor):
    def __init__(self, device_name, device_config):
        super(DS18B20, self).__init__(device_type='temperature', device_name=device_name, device_config=device_config)
        self.hwid = device_config['hwid']
        self.__sensor = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, self.hwid)

    def update(self):
        try:
            self.data['temperature'] = self.__sensor.get_temperature(W1ThermSensor.DEGREES_F)
        except w1thermsensor.errors.SensorNotReadyError as e:
            print('No temperature data from DS18B20 (' + self.hwid + '):', e)
            self.data['temperature'] = 0
