#!/usr/bin/env python3
import adafruit_dht
import board
import digitalio
import fcntl
import json
import os
import statistics
import time

from datetime import datetime

from w1thermsensor import W1ThermSensor
import w1thermsensor.errors

from collections import deque

class TempReader:
    def __init__(self, name):
        self._temps = deque(maxlen = 10)
        self._humids = deque(maxlen = 10)
        self.temp = None
        self.humidity = None
        self.time = None
        self.name = name
        self.time = 0

        for i in range(5):
            temp, humidity = self._read()
            if temp:
                self._temps.append(temp)
            if humidity:
                self._humids.append(humidity)

    def update(self):
        temp, humidity = self._read()

        if temp:
            self._temps.append(temp)
            if self.is_valid(temp, self._temps):
                self.temp = temp
                self.time = time.time()
            else:
                print(self.name + ": Invalid temperature reading")
        else:
            print("No temp")

        if humidity:
            self._humids.append(humidity)
            if self.is_valid(humidity, self._humids):
                self.humidity = humidity
                self.time = time.time()

        #print(self.name + ": " + str(temp) + "C " + str(humidity) + "%")


    def is_valid(self, value, values):
        # Calculate the mean of the previous values
        mean = statistics.mean(values)

        # Check if the value is within standard deviation of the mean
        diff = abs(mean - value)

        # If the swing is greater than 5, assume invalid
        valid = diff <= 5.0
        if not valid:
            print ("Invalid measurement: ", str(value), str(values))

        return valid


class AM2302Reader(TempReader):
    def __init__(self, name, power_pin, data_pin):
        self._power = digitalio.DigitalInOut(power_pin)
        self._power.direction = digitalio.Direction.OUTPUT

        self._on()
        self._sensor = adafruit_dht.DHT22(data_pin)
        self.model = "AM2302"

        super().__init__(name)

    def _off(self):
        self._power.value = False

    def _on(self):
        self._power.value = True

    def _reset(self):
        self._off()
        time.sleep(0.5)
        self._on()
        time.sleep(1)

    def _read(self, count=0):
        try:
            self._sensor.measure()

            if not self._sensor.temperature:
                raise Exception("Empty reading")

            return self._sensor.temperature, self._sensor.humidity
        except Exception as e:
            if count < 2:
                return self._read(count + 1)

            print(e)
            print("Resetting sensor")
            self._reset()
            return None, None

class DS18B20(TempReader):
    def __init__(self, name, hwid, power_pin):
        self.model = "DS18B20"
        self._power = digitalio.DigitalInOut(power_pin)
        self._power.direction = digitalio.Direction.OUTPUT
        self._on()
        time.sleep(5)
        self.__sensor = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, hwid)

        super().__init__(name)

    def _on(self):
        self._power.value = True

    def _off(self):
        self._power.value = False

    def _reset(self):
        self._off()
        time.sleep(0.5)
        self._on()
        time.sleep(1)

    def _read(self, count=0):
        try:
            return self.__sensor.get_temperature(W1ThermSensor.DEGREES_C), None
        except w1thermsensor.errors.SensorNotReadyError as e:
            if count < 2:
                return self._read(count + 1)

            print(e)
            print("Resetting 1wire bus")
            self._reset()
            return None, None

loop_time = 2

if __name__ == "__main__":
    # Power on the 1-Wire bus
    w1 = digitalio.DigitalInOut(board.D17)
    w1.direction = digitalio.Direction.OUTPUT
    w1.value = True

    time.sleep(10)

    #sensors = [AM2302Reader("air", board.D23, board.D24), DS18B20("soil", "02099177e85e", board.D17), DS18B20("air2", "020291772cf7", board.D17)]
    sensors = [DS18B20("soil", "02099177e85e", board.D17), DS18B20("air", "020291772cf7", board.D17)]
    output_filename = "/tmp/temp_sensors.json"

    while True:
        start = datetime.now()

        output = {}

        for sensor in sensors:
            sensor.update()
            output[sensor.name] = {}
            output[sensor.name]["temperature"] = sensor.temp
            output[sensor.name]["humidity"] = sensor.humidity
            output[sensor.name]["time"] = int(sensor.time)
            output[sensor.name]["model"] = sensor.model

        with open(output_filename, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(output))

            # Sleep so updates are constant
            diff = datetime.now() - start
            seconds = diff.seconds + (diff.microseconds / 1000000)
            if loop_time > seconds:
                time.sleep(loop_time - seconds)

