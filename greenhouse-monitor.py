#!/usr/bin/env python3

from flask import Flask
from flask import make_response
from flask import request

from flask_restful import Api, Resource, reqparse

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from enum import Enum

from epsolar_tracer.client import EPsolarTracerClient
from epsolar_tracer.enums.RegisterTypeEnum import RegisterTypeEnum

import configparser
import Adafruit_DHT
import urllib.request
import json
import numpy
import os
import logging
import wiringpi
import time
import pyowm

# Prepare GPIO
wiringpi.wiringPiSetupGpio()

# Prepare scheduler
scheduler = BackgroundScheduler(daemon=True)
scheduler.start()

# Parse configuration
config_path = '/etc/greenhouse-monitor.conf'
config = configparser.ConfigParser()
config.read(config_path)

# thingspeak config
thingspeak_base_url = ''
if config.has_option('thingspeak', 'api_key'):
    thingspeak_api_key = config.get('thingspeak', 'api_key').strip()
    if thingspeak_api_key:
        thingspeak_base_url = 'https://api.thingspeak.com/update?api_key=%s' % thingspeak_api_key

# smartthings config
smartthings_notify_url = ''
if config.has_option('smartthings', 'notify_url'):
    smartthings_notify_url = config.get('smartthings', 'notify_url')

# openweathermap config
owm = None
owm_city_id = 0
if config.has_option('openweathermap', 'api_key'):
    openweathermap_api_key = config.get('openweathermap', 'api_key').strip()
    owm_city_id = int(config.get('openweathermap', 'city_id'))
    owm = pyowm.OWM(openweathermap_api_key)

# epsolar config
epsolar_client = None
if config.has_option('epsolar', 'port'):
    epsolar_client = EPsolarTracerClient(port=config.get('epsolar', 'port'))

app = Flask(__name__)
api = Api(app)

def mail(subject, message):
    FROM="monitor@GreenHouse"
    TO="root"
    message = """\
From: %s
To: %s
Subject: %s

%s
""" % (FROM, TO, subject, message)
    p = os.popen("/usr/sbin/sendmail -t -i", "w")
    p.write(message)
    status = p.close()
    if status != 0:
        print("Sendmail exit status" + str(status))

class Switch:
    def __init__(self, gpio):
        self.__gpio = gpio
        self.__on = False

        # Prepare GPIO
        GPIO.setup(self.__gpio, GPIO.OUT)
        self.off()

    def is_on(self):
        return self.__on

    def off(self):
        GPIO.output(self.__gpio, GPIO.LOW)
        self.__on = False

    def on(self):
        GPIO.output(self.__gpio, GPIO.HIGH)
        self.__on = True

class SmartThingsAPIDevice:
    def __init__(self, device_name, device_type):
        self.device_type = device_type
        self.device_name = device_name
        self.__device_path = self.device_type + '/' + self.device_name
        self.data = {}

    def celcius_to_fahrenheit(self, tempC):
        return tempC * 9/5.0 + 32

    def fill_data(self, data):
        data[self.device_name] = self.data

    def update(self):
        '''
        Update the sensor data
        '''
        pass

    def notify(self):
        '''
        Push an unsolicited update to SmartThings
        '''
        body = self.get_body()
        headers = {
            'Content-Type': 'application/json',
            'Content-Length': len(body),
            'Device': self.__device_path
        }
        if smartthings_notify_url:
            req = urllib.request.Request(smartthings_notify_url, method='NOTIFY', headers=headers, data=body)
            urllib.request.urlopen(req, timeout=15)

    def get_response(self):
        '''
        Get a response for an HTTP GET or POST
        '''
        resp = make_response(self.get_body())
        resp.headers['Device'] = self.__device_path
        return resp

    def get_body(self):
        '''
        Get the body we send out for response/notify
        '''
        body = json.dumps(self.data).encode()
        return body

class AM2302Sensor(SmartThingsAPIDevice):
    def __init__(self, device_name, pin):
        super(AM2302Sensor, self).__init__(device_type='temp_humidity', device_name=device_name)
        self.pin = pin
        self.update()

    def update(self):
        humidity, tempC = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, self.pin, delay_seconds=2)
        if humidity is not None:
            self.data['humidity'] = humidity
            self.data['temperature'] = self.celcius_to_fahrenheit(tempC)
            self.data['timestamp'] = int(time.time() * 1000)

class OpenWeatherMap(SmartThingsAPIDevice):
    def __init__(self, device_name):
        super(OpenWeatherMap, self).__init__(device_type='weather', device_name=device_name)
        self.update()

    def update(self):
        self.observation = owm.weather_at_id(owm_city_id)
        weather = self.observation.get_weather()

        self.data['temperature'] = weather.get_temperature('fahrenheit')['temp']
        self.data['humidity'] = weather.get_humidity()
        self.data['wind'] = weather.get_wind()
        self.data['sunrise'] = weather.get_sunrise_time()
        self.data['sunset'] = weather.get_sunset_time()
        self.data['pressure'] = weather.get_pressure()['press']
        self.data['clouds'] = weather.get_clouds()
        self.data['weather_icon_url'] = weather.get_weather_icon_url()

class EPSolarCharger(SmartThingsAPIDevice):
    def __init__(self, device_name):
        super(EPSolarCharger, self).__init__(device_type='charger', device_name=device_name)
        self.data['battery'] = {}
        self.data['charging'] = {}
        self.data['discharging'] = {}
        self.update()

    def update(self):
        # Get the battery temperature
        response = epsolar_client.read_input(RegisterTypeEnum.BATTERY_TEMPERATURE)
        self.data['battery']['temperature'] = self.celcius_to_fahrenheit(response.value)

        # Get the battery state of charge
        response = epsolar_client.read_input(RegisterTypeEnum.BATTERY_SOC)
        self.data['battery']['state_of_charge'] = response.value

        # Get the battery watts
        response = epsolar_client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_OUTPUT_POWER)
        self.data['battery']['output_power'] = response.value

        # Get the equipment temperature
        response = epsolar_client.read_input(RegisterTypeEnum.TEMPERATURE_INSIDE_EQUIPMENT)
        self.data['temperature'] = self.celcius_to_fahrenheit(response.value)

        # Get the solar watts
        response = epsolar_client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_INPUT_POWER)
        self.data['charging']['input_power'] = response.value

        # Get the load watts
        response = epsolar_client.read_input(RegisterTypeEnum.DISCHARGING_EQUIPMENT_OUTPUT_POWER)
        self.data['discharging']['output_power'] = response.value

class ExhaustFan(SmartThingsAPIDevice):
    def __init__(self, device_name, fwd_pin, bwd_pin, pwm_pin):
        super(ExhaustFan, self).__init__(device_type='fan', device_name=device_name)
        self.fwd_pin = fwd_pin
        self.bwd_pin = bwd_pin
        self.pwm_pin = pwm_pin

        # Prepare pins for output/pwm
        wiringpi.pinMode(self.fwd_pin, 1)
        wiringpi.pinMode(self.bwd_pin, 1)
        wiringpi.pinMode(self.pwm_pin, 2)
        wiringpi.pwmSetMode(wiringpi.PWM_MODE_MS)

        # Prepare PWM specs
        self.range = 480 # 20Khz
        self.clock = 2 # Must be at least 2
        wiringpi.pwmSetClock(self.clock)
        wiringpi.pwmSetRange(self.range)
        #freq = 19200000 / self.clock / self.range
        #print("Frequency:", freq)

        # Initialize to off
        self.data['speed'] = 0
        self.off()

    def fwd(self):
        wiringpi.digitalWrite(self.fwd_pin, 1)
        wiringpi.digitalWrite(self.bwd_pin, 0)
        self.data['state'] = 'fwd'

    def bwd(self):
        wiringpi.digitalWrite(self.bwd_pin, 1)
        wiringpi.digitalWrite(self.fwd_pin, 0)
        self.data['state'] = 'bwd'

    def off(self):
        wiringpi.digitalWrite(self.bwd_pin, 1)
        wiringpi.digitalWrite(self.fwd_pin, 1)
        self.data['state'] = 'off'

    def brake(self):
        wiringpi.digitalWrite(self.bwd_pin, 0)
        wiringpi.digitalWrite(self.fwd_pin, 0)
        self.data['state'] = 'brake'

    def set_speed(self, speed):
        if speed < 10:
            speed = 0
            self.off()
        else:
            self.fwd()

        if speed == self.data['speed']:
            return

        self.data['speed'] = speed
        duty = int(self.range * speed / 100)
        wiringpi.pwmWrite(self.pwm_pin, duty)

# Our sensors
am2302 = AM2302Sensor('air', 19)
epsolar = EPSolarCharger('epsolar')
exhaust_fan = ExhaustFan('exhaust_fan', fwd_pin=12, bwd_pin=16, pwm_pin=18)
weather = OpenWeatherMap('weather')

sensors = [am2302, epsolar, exhaust_fan, weather]

@scheduler.scheduled_job('interval', id='log_to_file', seconds=5)
def log_to_file():
    '''
    Used to log JSON for the web interface
    '''
    data = {}
    for sensor in sensors:
        sensor.update()
        sensor.fill_data(data)

    with open('/tmp/greenhouse_state.json', 'w') as outfile:
        json.dump(data, outfile)


class CoolingState(Enum):
    WAITING = 1
    COOLING = 2

cooling_state = CoolingState.WAITING

@scheduler.scheduled_job('interval', id='control_fan_speed', seconds=10)
def control_fan_speed():
    global cooling_state

    temp_readings = [am2302.data.get('temperature', 0)]
    max_temp = max(temp_readings)
    speed = 0

    if cooling_state == CoolingState.WAITING:
        '''
        The fan is off. Wait until a point to turn on.
        '''
        if max_temp > 82:
            # Turn on when the greenhouse is over 80F
            speed = 30 # Start off slow (ramp up)
            cooling_state = CoolingState.COOLING

    elif cooling_state == CoolingState.COOLING:
        '''
        The fan is on. Wait until we're below our target to turn off.
        '''
        if max_temp > 90:
            # 70% speed over 90F
            speed = 70
        elif max_temp > 85:
            # 60% speed over 85F
            speed = 60
        elif max_temp > 80:
            # 50% speed over 80F
            speed = 50
        elif max_temp > 78:
            # 40% speed over 78F
            speed = 40
        else:
            # Turn off when below 78F
            speed = 0
            cooling_state = CoolingState.WAITING

    exhaust_fan.set_speed(speed)

def log_to_thingspeak():
    tempC = temp_sensor.readC()
    tempF = temp_sensor.celcius_to_fahrenheit(tempC)
    pH = ph_sensor.read(tempC)
    try:
        f = urllib.request.urlopen(thingspeak_base_url + "&field1=%s&field2=%s" % (str(tempF), str(pH)), timeout=15)
        f.close()
    except Exception:
        # For some reason the data was not accepted
        # ThingSpeek gives a lot of 500 errors
        pass

#@scheduler.scheduled_job('cron', id='log_to_cloud', minute='*')
def log_to_cloud():
    am2302.update()
    epsolar.update()

    log_to_file()
    # Notify ThingSpeak
    #if thingspeak_base_url:
        #log_to_thingspeak()

    # Notify SmartThings
    #water_level_sensor.notify()
    #temp_sensor.notify()
    #ph_sensor.notify()

class Charger(Resource):
    def get(self, name):
        if(name == "epsolar"):
            return epsolar.get_response()

        return "Battery not found", 404

class Fan(Resource):
    def get(self, name):
        if(name == "exhaust"):
            return exhaust_fan.get_response()

        return "Fan not found", 404

class Temperature(Resource):
    def get(self, name):
        if(name == "air"):
            return am2302.get_response()

        return "Temperature sensor not found", 404

class Subscription(Resource):
    def get(self, name):
        global smartthings_notify_url

        # Update our NOTIFY URL for posting events to SmartThings
        new_smartthings_notify_url = 'http://' + name.strip()
        if new_smartthings_notify_url != smartthings_notify_url:
            smartthings_notify_url = new_smartthings_notify_url
            # Update our config file
            if not config.has_section('smartthings'):
                config.add_section('smartthings')
            config.set('smartthings', 'notify_url', smartthings_notify_url)
            # Write it back out
            with open(config_path, 'w') as f:
                config.write(f)


api.add_resource(Temperature, "/temperature/<string:name>")
api.add_resource(Charger, "/charger/<string:name>")
api.add_resource(Subscription, "/subscribe/<string:name>")
api.add_resource(Fan, "/fan/<string:name>")

try:
    # With the reloader enabled, apscheduler executes twice, one in each process
    # We could probably fix this correctly, but just disabling the reloader for now
    app.run(debug=True,host='0.0.0.0', use_reloader=False)
finally:
    print("GPIO Cleanup")
    exhaust_fan.off()

