#!/usr/bin/env python3
import board
import digitalio
import fcntl
import json
import pulseio
import time
import wiringpi # TODO

from simple_pid import PID
from datetime import datetime

class Fan:
    def __init__(self, fwd_pin, bwd_pin, pwm_pin):
        self._fwd = digitalio.DigitalInOut(fwd_pin)
        self._fwd.direction = digitalio.Direction.OUTPUT

        self._bwd = digitalio.DigitalInOut(bwd_pin)
        self._bwd.direction = digitalio.Direction.OUTPUT

        self._pwm_pin = pwm_pin
        wiringpi.pinMode(pwm_pin, 2)
        wiringpi.pwmSetMode(wiringpi.PWM_MODE_MS)

        self.range = 240 # 20Khz
        self.clock = 4 # Must be at least 2
        wiringpi.pwmSetClock(self.clock)
        wiringpi.pwmSetRange(self.range)

        self.speed = 0
        self.off()

    def fwd(self):
        self._fwd.value = True
        self._bwd.value = False

    def bwd(self):
        self._fwd.value = False
        self._bwd.value = True

    def off(self):
        self._fwd.value = True
        self._bwd.value = True

    def brake(self):
        self._fwd.value = False
        self._bwd.value = False

    def clamp_speed(self, speed):
        SpeedMin = 35
        SpeedMax = 80
        RangeMax = SpeedMax - SpeedMin

        if speed < 1:
            return 0

        # Speed into our range
        speed = (speed * RangeMax) / 100
        speed = speed + SpeedMin

        return speed

    def set_speed(self, speed):
        speed = self.clamp_speed(speed)
        if speed == self.speed:
            return

        if speed == 0:
            self.off()
        else:
            self.fwd()

        self.speed = speed

        duty = int(self.range * speed / 100)
        wiringpi.pwmWrite(self._pwm_pin, duty)

class JsonReader:
    def __init__(self, path):
        self._path = path
        self._json = None

    def update(self):
        try:
            with open(self._path, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                self._json = json.load(f)
        except json.JSONDecodeError as e:
            print("JSON error for " + self._path + ": " + str(e))
        except OSError as e:
            print("Error opening " + self._path + ": " + str(e))
            self._json = None

    def json(self):
        return self._json


class EpsolarReader(JsonReader):
    def __init__(self):
        JsonReader.__init__(self, "/tmp/epsolar.json")

    def _get_value(self, name, default=None):
        data = self.json()
        if not data:
            return default

        last_update = data.get("time")
        if not last_update:
            return None

        last_update = float(last_update)
        age = int(time.time() - last_update)
        if age > 30:
            # Temperature sensor is not responding
            return None
        # Sensor was updated recently enough,

        result_data = data.get(name, default)
        if not result_data:
            return default

        return result_data.get("value")

    def low_power_mode(self):
        """
        Returns True if we should work in low-power mode
        """
        if self.battery_soc() > 30:
            return False
        if self.input_power() > 50:
            return False

        return True

    def battery_temperature(self):
        return self._get_value("BATTERY_TEMPERATURE", None)

    def input_power(self):
        return self._get_value("CHARGING_EQUIPMENT_INPUT_POWER", 0)

    def equipment_power(self):
        return self._get_value("DISCHARGING_EQUIPMENT_OUTPUT_POWER", 0)

    def battery_soc(self):
        return self._get_value("BATTERY_SOC", 0)


class WeatherReader(JsonReader):
    def __init__(self):
        JsonReader.__init__(self, "/tmp/weather.json")

    def temperature(self):
        data = self.json()

        weather = data.get("weather")
        if not weather:
            return None
        temperature = weather.get("temperature")
        if not temperature:
            return None
        return temperature.get("temp")

    def sun_elevation(self):
        weather = self.json()
        if not weather:
            return None
        sun = weather.get("sun")
        if not sun:
            return None

        return sun.get("elevation")


class TempReader(JsonReader):
    def __init__(self):
        JsonReader.__init__(self, "/tmp/temp_sensors.json")

    def value(self, name):
        data = self.json()
        if not data:
            return None

        sensor = data.get(name)
        if not sensor:
            return None

        last_update = sensor.get("time")
        if not last_update:
            return None

        last_update = float(last_update)
        age = int(time.time() - last_update)
        if age > 10:
            # Temperature sensor is not responding
            return None

        # Sensor was updated recently and seems valid
        return sensor.get("temperature")



wiringpi.wiringPiSetupGpio()

fan = Fan(board.D12, board.D16, 18)
temp_reader = TempReader()
weather_reader = WeatherReader()
epsolar_reader = EpsolarReader()

targetT = 26.6667
P = 10
I = 0.25
D = 1.5

pid = PID(P, I, D, setpoint=targetT)
pid.output_limits = (-100, 0)
#pid.proportional_on_measurement = True
pid.sample_time = 3

def get_greenhouse_temp():
    """ Try hard to return some kind of useful temperature """

    # First, try the 1wire temp sensor
    greenhouse_temp = temp_reader.value("air")
    if greenhouse_temp:
        return greenhouse_temp

    # Try to read it from the EPSolar battery sensor
    greenhouse_temp = epsolar_reader.battery_temperature()
    if greenhouse_temp:
        return greenhouse_temp

    # Okay, now what?
    return None


while 1:
    now = datetime.now()

    # Update all of the json readers
    temp_reader.update()
    weather_reader.update()
    epsolar_reader.update()

    # Wait for a temperature to become available
    greenhouse_temp = get_greenhouse_temp()
    if not greenhouse_temp:
        # TODO: We could get stuck in here and run the fan forever
        print("Greenhouse temperature unavailable")
        time.sleep(5)
        continue

    # It's impossible to reach a temperature below the outside temperature
    # If it's hotter outside than our setpoint, use that value instead
    outside_temp = weather_reader.temperature()
    if outside_temp:
        pid.setpoint = max(targetT, outside_temp + 2)
    else:
        outside_temp = 0.0
        pid.setpoint = targetT

    # Calculate the fan speed
    target_pwm = abs(pid(greenhouse_temp))

    # Read some battery state
    battery_soc = epsolar_reader.battery_soc()
    input_power = epsolar_reader.input_power()
    equipment_power = epsolar_reader.equipment_power()

    # Check if the sun is low so we don't run the fan at night
    elevation = weather_reader.sun_elevation()
    if elevation is not None:
        if elevation < 10.0:
            # Sun's getting real low
            target_pwm = 0


    # Logging
    print("Outside: %.2fC | Inside: %.2fC | Target: %.2fC | Fan: %s%% | Solar Elevation: %s%% | SOC %s%% | Input Power %sW | Equipment Power: %sW"
        % (outside_temp, greenhouse_temp, pid.setpoint, target_pwm, str(elevation), battery_soc, input_power, equipment_power))

    # Adjust the fan speed
    fan.set_speed(target_pwm)

    # Sleep based on our sample time
    diff = datetime.now() - now
    seconds = diff.seconds + (diff.microseconds / 1000000)
    if pid.sample_time > seconds:
        time.sleep(pid.sample_time - seconds)


