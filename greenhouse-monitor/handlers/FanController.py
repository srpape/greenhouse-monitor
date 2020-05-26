from enum import Enum
from astral import *

from .Handler import Handler

class CoolingState(Enum):
    WAITING = 1
    COOLING = 2

class FanController(Handler):
    def __init__(self, handler_name, handler_config, devices):
        super(FanController, self).__init__(handler_name=handler_name, handler_config=handler_config, devices=devices)

        self.sun = Location(info=("Ithaca", "USA", 42.511680, -76.557191, "US/Eastern", 206))

        self.cooling_state = CoolingState.WAITING

        # Prepare the fan we're controlling
        self.fan = devices[handler_config['fan']]

        # Prepare sensors
        self.primary_sensors = []
        for s in handler_config['primary_temp_sensors'].split(','):
            self.primary_sensors.append(devices[s.strip()])

        self.backup_sensors = []
        if 'backup_temp_sensors' in handler_config:
            for s in handler_config['backup_temp_sensors'].split(','):
                self.backup_sensors.append(devices[s.strip()])

        # Throw exception if self.primary_sensors is empty
        if not self.primary_sensors:
            raise ValueError("No primary sensors given for FanController " + name)

    def process(self):
        speed = 0

        if self.sun.solar_elevation() < 10:
            # Sun's getting real low...
            self.cooling_state = CoolingState.WAITING
            self.fan.set_speed(0)
            return

        # Query primary sensors
        readings = []
        for sensor in self.primary_sensors:
            readings.append(sensor.data['temperature'])
        max_temp = max(readings)

        if not readings or not max_temp:
            # Try backup sensors
            for sensor in self.backup_sensors:
                readings.append(sensor.data['temperature'])
            max_temp = max(readings)

        if not readings or not max_temp:
            print("No primary or backup temperature data, ignoring...")
            return

        #print("Readings:", readings)
        #print("Max temp:", max_temp)

        # Actually determine the speed to set
        if self.cooling_state == CoolingState.WAITING:
            '''
            The fan is off. Wait until a point to turn on.
            '''
            if max_temp > 83:
                # Turn on when the greenhouse is over 80F
                speed = 30 # Start off slow (ramp up)
                self.cooling_state = CoolingState.COOLING

        elif self.cooling_state == CoolingState.COOLING:
            '''
            The fan is on. Wait until we're below our target to turn off.
            '''
            if max_temp > 100:
                # 80% speed over 100F
                speed = 80
            elif max_temp > 90:
                # 75% speed over 90F
                speed = 75
            elif max_temp > 85:
                # 60% speed over 85F
                speed = 60
            elif max_temp > 80:
                # 50% speed over 80F
                speed = 50
            else:
                # Turn off when below 78F
                speed = 0
                self.cooling_state = CoolingState.WAITING

        self.fan.set_speed(speed)
